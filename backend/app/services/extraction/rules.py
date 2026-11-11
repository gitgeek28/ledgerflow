"""Deterministic, layout-aware invoice field extractor.

Works on positioned words (text layer or OCR). It finds label/value pairs (same segment, right neighbour,
or the line below), the totals block, and the line-item table by locating a header row and assigning each
data cell to the header column it sits under. It never guesses: if a value is not printed in a recognisable
way the field stays null and an issue is recorded.

Confidence is derived, not invented:
  * base confidence by how the value was located (label on same segment > neighbour > below > pattern),
  * multiplied by the OCR engine's own word confidence for OCR pages (1.0 for embedded text),
  * amounts that cross-validate arithmetically (qty x rate = amount; subtotal + tax = total) are raised to at
    least 0.95, because independent misreads that still reconcile exactly are very unlikely.
"""
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.core.config import get_settings
from app.services.extraction.document import DocumentText, Line, Segment
from app.services.extraction.schema import (
    CRITICAL_FIELDS,
    Evidence,
    ExtractedField,
    ExtractedLine,
    ExtractionIssue,
    ExtractionResult,
)
from app.services.identifiers import GSTIN_RE, IFSC_RE, is_valid_gstin
from app.services.money import parse_amount, parse_quantity, q2
from app.services.text_norm import normalise_name

BASE_CONF = {"label": 0.99, "label-right": 0.97, "label-below": 0.96, "pattern": 0.90, "layout": 0.90,
             "derived": 0.90}
CROSS_VALIDATED_FLOOR = 0.95

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

LABELS = {
    "invoice_number": r"(?:tax\s+)?(?:invoice|inv\.?|bill)\s*(?:no\.?|number|num|#|ref\.?)",
    "invoice_date": r"(?:invoice|inv\.?|bill)\s*date|date\s+of\s+invoice|dated",
    "due_date": r"due\s*date|payment\s*due(?:\s*date)?|pay\s*by",
    "po_number": r"(?:p\.?\s?o\.?|purchase\s*order|your\s*order|buyer'?s?\s*order|order)\s*"
                 r"(?:no\.?|number|ref\.?|reference|#)?",
    "currency": r"currency",
    "vendor_name": r"supplier|vendor|seller|sold\s*by|from",
    "bank_account": r"a/?c\.?\s*(?:no\.?|number)?|account\s*(?:no\.?|number|#)|bank\s*a/?c(?:\s*no\.?)?",
    "bank_ifsc": r"ifsc(?:\s*code)?",
    "vendor_tax_id": r"gstin(?:/uin)?|gst\s*(?:no\.?|number|reg(?:istration)?\.?\s*no\.?)",
}

TOTAL_LABELS = {
    "grand_total": r"grand\s*total|total\s*amount(?:\s*payable)?|amount\s*due|amount\s*payable|net\s*payable|"
                   r"invoice\s*total|total\s*payable|balance\s*due|total\s*invoice\s*value",
    "tax_total": r"total\s*tax(?:\s*amount)?|total\s*gst|tax\s*total|gst\s*total",
    "subtotal": r"sub[\s-]?total|taxable\s*amount|taxable\s*value|total\s*taxable\s*value|total\s*before\s*tax",
}
TAX_COMPONENT = re.compile(r"^(igst|cgst|sgst|utgst)\s*(?:@\s*(\d+(?:\.\d+)?)\s*%)?$", re.I)
TOTAL_LABEL_SUFFIX = r"\s*(?:\((?:inr|rs\.?|₹)\)|in\s+inr|\(₹\))?\s*:?"

HEADER_KEYS = {
    "sl": r"#|sl\.?|s\.?\s*no\.?|sr\.?\s*no\.?|no\.?",
    "description": r"description|particulars|item\s*description|item|details|description\s*of\s*goods|services",
    "hsn": r"hsn/sac|hsn|sac|hsn\s*code",
    "qty": r"qty\.?|quantity",
    "unit": r"unit|uom|units",
    "rate": r"rate|unit\s*price|price|unit\s*rate|rate\s*per\s*unit",
    "amount": r"amount|taxable\s*value|taxable\s*amount|value",
    "tax_rate": r"gst\s*%|tax\s*%|gst\s*rate|tax\s*rate|igst\s*%|gst\s*\(%\)",
    "tax_amount": r"tax|gst\s*amt|tax\s*amount|gst\s*amount",
    "total": r"total|line\s*total|amount\s*\(incl\.?\s*tax\)",
}
TABLE_END = re.compile(r"^(sub[\s-]?total|taxable\s*amount|total\b|grand\s*total|amount\s*due|net\s*payable|"
                       r"page\s+\d+\s+of|bank\s+details|payment\s+details|amount\s+in\s+words)", re.I)
COMPANY_SUFFIX = re.compile(r"\b(pvt|private|ltd|limited|llp|traders|industries|inc|co|company|corporation|"
                            r"services|solutions|systems|enterprises)\b\.?", re.I)
NOT_A_NAME = re.compile(r"invoice|gstin|date|bill\s*to|billed|synthetic|page\s+\d|email|phone|tel|www|"
                        r"currency|place of supply|^to$|buyer|pan\b|cin\b", re.I)


# ----------------------------------------------------------------------------------------- value parsers
def parse_date(text: str) -> tuple[date, str] | None:
    s = text.strip()
    patterns = [
        (r"(\d{1,2})[\s\-/.]([A-Za-z]{3,9})[\s\-/.,]+(\d{4})", "dmy_name"),
        (r"([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})", "mdy_name"),
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"),
        (r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", "dmy"),
    ]
    for pattern, kind in patterns:
        m = re.search(pattern, s)
        if not m:
            continue
        try:
            if kind == "dmy_name":
                d, mon, y = int(m.group(1)), MONTHS.get(m.group(2)[:3].lower()), int(m.group(3))
                if not mon:
                    continue
                return date(y, mon, d), m.group(0)
            if kind == "mdy_name":
                mon, d, y = MONTHS.get(m.group(1)[:3].lower()), int(m.group(2)), int(m.group(3))
                if not mon:
                    continue
                return date(y, mon, d), m.group(0)
            if kind == "ymd":
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), m.group(0)
            # Indian convention: day first
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))), m.group(0)
        except ValueError:
            continue
    return None


AMOUNT_TOKEN = re.compile(r"\(?-?(?:rs\.?|inr|₹)?\s*\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?\)?|\(?-?\d+(?:\.\d{1,2})?\)?",
                          re.I)


def parse_amount_text(text: str) -> tuple[Decimal, str] | None:
    s = text.strip().replace(":", ".") if re.fullmatch(r"[\d,]+:\d{2}", text.strip()) else text.strip()
    m = AMOUNT_TOKEN.fullmatch(s)
    if not m:
        return None
    value = parse_amount(s)
    return (value, s) if value is not None else None


def parse_invoice_number(text: str) -> tuple[str, str, list[str]] | None:
    s = text.strip().strip(":#.- ")
    if not s:
        return None
    notes = []
    if " " in s and re.fullmatch(r"[A-Za-z0-9/\-_. ]{3,40}", s) and re.search(r"\d\s+[\d/]", s):
        joined = re.sub(r"\s+", "", s)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/\-_.]{2,30}", joined):
            notes.append("whitespace inside the printed number was removed (OCR spacing)")
            s = joined
    m = re.match(r"[A-Za-z0-9][A-Za-z0-9/\-_.]*[A-Za-z0-9]", s)
    if not m or not re.search(r"\d", m.group(0)) or len(m.group(0)) < 3 or len(m.group(0)) > 30:
        return None
    return m.group(0).upper(), m.group(0), notes


def parse_po(text: str) -> tuple[str, str] | None:
    m = re.search(r"\b([A-Za-z]{1,5}[-/ ]?\d{4,10}(?:[-/]\d{1,6})?)\b", text)
    if not m:
        return None
    raw = m.group(1)
    return raw.upper().replace(" ", "-"), raw


def parse_currency(text: str) -> tuple[str, str] | None:
    m = re.search(r"\b(INR|USD|EUR|GBP|AED|SGD)\b", text, re.I)
    if m:
        return m.group(1).upper(), m.group(1)
    if re.search(r"indian\s+rupee|₹|\brs\.?\b", text, re.I):
        return "INR", text.strip()[:20]
    return None


def parse_account(text: str) -> tuple[str, str] | None:
    m = re.search(r"(\d[\d -]{6,24}\d)", text)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    return (digits, m.group(1)) if 8 <= len(digits) <= 20 else None


def parse_ifsc(text: str) -> tuple[str, str] | None:
    m = IFSC_RE.search(text.upper())
    return (m.group(1), m.group(1)) if m else None


def parse_gstin(text: str) -> tuple[str, str] | None:
    m = GSTIN_RE.search(text.upper())
    return (m.group(1), m.group(1)) if m else None


def parse_text(text: str) -> tuple[str, str] | None:
    s = text.strip(" :-")
    return (s, s) if len(s) >= 3 else None


# ----------------------------------------------------------------------------------------- helpers
def _value_conf(seg: Segment, raw: str) -> float:
    """Minimum OCR confidence of the words that make up `raw` within the segment."""
    parts = raw.split()
    confs = [w.conf for w in seg.words if any(p in w.text or w.text in p for p in parts)]
    return min(confs) if confs else seg.conf


def _evidence(line: Line, seg: Segment | None = None) -> Evidence:
    return Evidence(page=line.page, snippet=line.text[:300], bbox=seg.bbox() if seg else None)


def _field(value, raw, method, line, seg, conf_words: float, notes=None) -> ExtractedField:
    return ExtractedField(value=str(value), raw=raw, method=method,
                          confidence=round(BASE_CONF[method] * conf_words, 3),
                          evidence=_evidence(line, seg), notes=notes or [])


@dataclass
class _Ctx:
    doc: DocumentText
    lines: list[Line]


class RuleBasedExtractor:
    name = "rules-v1"

    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold

    def extract(self, doc: DocumentText) -> ExtractionResult:
        ctx = _Ctx(doc, doc.all_lines())
        fields: dict[str, ExtractedField] = {}
        issues: list[ExtractionIssue] = []

        fields["invoice_number"] = self._labelled(ctx, "invoice_number", parse_invoice_number)
        fields["invoice_date"] = self._labelled(ctx, "invoice_date", self._date_value)
        fields["due_date"] = self._labelled(ctx, "due_date", self._date_value)
        fields["po_number"] = self._labelled(ctx, "po_number", parse_po)
        if not fields["po_number"].present:
            fields["po_number"] = self._pattern(ctx, r"\bPO[-\s]?\d{6}\b", parse_po)
        fields["currency"] = self._labelled(ctx, "currency", parse_currency)
        if not fields["currency"].present:
            fields["currency"] = self._pattern(ctx, r"\b(INR|USD|EUR)\b", parse_currency)
        fields["vendor_tax_id"] = self._supplier_gstin(ctx)
        fields["vendor_name"] = self._vendor_name(ctx)
        fields["bank_account"] = self._labelled(ctx, "bank_account", parse_account)
        fields["bank_ifsc"] = self._labelled(ctx, "bank_ifsc", parse_ifsc)
        if not fields["bank_ifsc"].present:
            fields["bank_ifsc"] = self._pattern(ctx, IFSC_RE.pattern, parse_ifsc)

        totals, tax_rates = self._totals(ctx)
        fields.update(totals)
        lines = self._line_items(ctx, tax_rates)
        self._cross_validate(fields, lines)

        threshold = self.confidence_threshold
        for name in CRITICAL_FIELDS:
            f = fields[name]
            if not f.present:
                issues.append(ExtractionIssue(field=name, code="CRITICAL_FIELD_MISSING",
                                              message=f"{name.replace('_', ' ').capitalize()} could not be read."))
            elif f.confidence < threshold:
                issues.append(ExtractionIssue(field=name, code="LOW_EXTRACTION_CONFIDENCE",
                                              message=f"{name.replace('_', ' ').capitalize()} read with confidence "
                                                      f"{f.confidence:.2f}."))
        if not lines:
            issues.append(ExtractionIssue(field="line_items", code="LINE_ITEMS_NOT_FOUND",
                                          message="No line-item table could be identified."))
        methods = sorted(doc.methods)
        source = {"text": "embedded text", "ocr": "tesseract OCR"}
        extractor = f"{self.name} ({' + '.join(source[m] for m in methods)})"
        return ExtractionResult(fields=fields, lines=lines, issues=issues, extractor=extractor)

    # -- header fields -------------------------------------------------------------------------------------
    @staticmethod
    def _date_value(text: str):
        r = parse_date(text)
        return (r[0].isoformat(), r[1]) if r else None

    def _labelled(self, ctx: _Ctx, name: str, parser) -> ExtractedField:
        label_re = re.compile(rf"^\s*(?:{LABELS[name]})\s*[:.#-]?\s*", re.I)
        for li, line in enumerate(ctx.lines):
            for si, seg in enumerate(line.segments):
                m = label_re.match(seg.text)
                if not m:
                    continue
                rest = seg.text[m.end():]
                notes: list[str] = []
                parsed = parser(rest) if rest.strip() else None
                if parsed:
                    value, raw = parsed[0], parsed[1]
                    notes = parsed[2] if len(parsed) > 2 else []
                    conf = _value_conf(seg, raw) * (0.92 if notes else 1.0)
                    return _field(value, raw, "label", line, seg, conf, notes)
                if rest.strip():
                    continue  # label followed by something that is not a valid value: do not look elsewhere
                if si + 1 < len(line.segments):
                    nxt = line.segments[si + 1]
                    parsed = parser(nxt.text)
                    if parsed and nxt.x0 - seg.x1 < 160:
                        return _field(parsed[0], parsed[1], "label-right", line, nxt, _value_conf(nxt, parsed[1]),
                                      parsed[2] if len(parsed) > 2 else None)
                below = self._segment_below(ctx.lines, li, seg)
                if below:
                    bline, bseg = below
                    parsed = parser(bseg.text)
                    if parsed:
                        return _field(parsed[0], parsed[1], "label-below", bline, bseg,
                                      _value_conf(bseg, parsed[1]), parsed[2] if len(parsed) > 2 else None)
        return ExtractedField()

    @staticmethod
    def _segment_below(lines: list[Line], li: int, seg: Segment):
        for line in lines[li + 1: li + 4]:
            if line.page != lines[li].page:
                return None
            if line.y0 - seg.y1 > 2.6 * seg.height:
                return None
            for cand in line.segments:
                overlap = min(cand.x1, seg.x1 + 40) - max(cand.x0, seg.x0 - 5)
                if overlap > 0:
                    return line, cand
        return None

    def _pattern(self, ctx: _Ctx, pattern: str, parser) -> ExtractedField:
        rx = re.compile(pattern, re.I)
        for line in ctx.lines:
            for seg in line.segments:
                if rx.search(seg.text):
                    parsed = parser(seg.text)
                    if parsed:
                        return _field(parsed[0], parsed[1], "pattern", line, seg, _value_conf(seg, parsed[1]))
        return ExtractedField()

    def _supplier_gstin(self, ctx: _Ctx) -> ExtractedField:
        buyer = get_settings().buyer_gstin
        for line in ctx.lines:
            for seg in line.segments:
                parsed = parse_gstin(seg.text)
                if not parsed or parsed[0] == buyer:
                    continue
                method = "label" if re.search(LABELS["vendor_tax_id"], seg.text, re.I) else "pattern"
                f = _field(parsed[0], parsed[1], method, line, seg, _value_conf(seg, parsed[1]))
                if not is_valid_gstin(parsed[0]):
                    f.notes.append("GSTIN fails the format/checksum test")
                return f
        return ExtractedField()

    def _vendor_name(self, ctx: _Ctx) -> ExtractedField:
        labelled = self._labelled(ctx, "vendor_name", parse_text)
        if labelled.present and COMPANY_SUFFIX.search(labelled.value or ""):
            return labelled
        first = ctx.doc.pages[0]
        buyer = normalise_name(get_settings().buyer_name)
        best, best_score = None, 0.0
        for line in first.lines:
            if line.y0 > first.height * 0.32:
                break
            for seg in line.segments:
                text = seg.text.strip()
                if len(text) < 4 or NOT_A_NAME.search(text) or normalise_name(text) == buyer:
                    continue
                if sum(ch.isdigit() for ch in text) >= 3:
                    continue
                score = seg.height + (8 if COMPANY_SUFFIX.search(text) else 0)
                if score > best_score:
                    best, best_score = (line, seg), score
        if not best:
            return ExtractedField()
        line, seg = best
        f = _field(seg.text.strip(), seg.text.strip(), "layout", line, seg, seg.conf)
        if not COMPANY_SUFFIX.search(seg.text):
            f.confidence = round(f.confidence * 0.8, 3)
            f.notes.append("No legal-entity suffix; identified by position and type size only")
        return f

    # -- totals --------------------------------------------------------------------------------------------
    def _totals(self, ctx: _Ctx) -> tuple[dict[str, ExtractedField], list[Decimal]]:
        found: dict[str, ExtractedField] = {}
        components: list[tuple[str, Decimal | None, Decimal, Line, Segment, float]] = []
        compiled = {k: re.compile(rf"^(?:{v}){TOTAL_LABEL_SUFFIX}$", re.I) for k, v in TOTAL_LABELS.items()}
        generic_total = re.compile(rf"^total{TOTAL_LABEL_SUFFIX}$", re.I)
        generic: tuple | None = None
        for line in ctx.lines:
            for si, seg in enumerate(line.segments):
                label = seg.text.strip()
                amount = None
                for later in reversed(line.segments[si + 1:]):
                    amount = parse_amount_text(later.text)
                    if amount:
                        amount_seg = later
                        break
                if not amount:
                    continue
                comp = TAX_COMPONENT.match(label)
                if comp:
                    rate = Decimal(comp.group(2)) if comp.group(2) else None
                    components.append((comp.group(1).upper(), rate, amount[0], line, amount_seg,
                                       _value_conf(amount_seg, amount[1])))
                    continue
                for key, rx in compiled.items():
                    if rx.match(label):
                        found[key] = _field(q2(amount[0]), amount[1], "label", line, amount_seg,
                                            _value_conf(amount_seg, amount[1]))  # last occurrence wins
                        break
                else:
                    if generic_total.match(label):
                        generic = (amount, line, amount_seg)
        if "grand_total" not in found and generic:
            amount, line, seg = generic
            found["grand_total"] = _field(q2(amount[0]), amount[1], "label", line, seg, _value_conf(seg, amount[1]))
        if "tax_total" not in found and components:
            total = sum((c[2] for c in components), Decimal(0))
            line, seg = components[-1][3], components[-1][4]
            f = _field(q2(total), " + ".join(str(c[2]) for c in components), "derived", line, seg,
                       min(c[5] for c in components))
            f.notes.append("Sum of printed tax components (" + ", ".join(c[0] for c in components) + ")")
            found["tax_total"] = f
        rates = self._summary_rates(components)
        return found, rates

    @staticmethod
    def _summary_rates(components) -> list[Decimal]:
        """Total GST rates implied by the tax summary: IGST @ r -> r; CGST @ r/2 + SGST @ r/2 -> r."""
        rates = set()
        for kind, rate, *_ in components:
            if rate is None:
                continue
            rates.add(rate if kind == "IGST" else rate * 2)
        return sorted(rates)

    # -- line items ----------------------------------------------------------------------------------------
    def _header_columns(self, line: Line) -> dict[str, Segment] | None:
        cols: dict[str, Segment] = {}
        for seg in line.segments:
            label = seg.text.strip().lower()
            for key, pattern in HEADER_KEYS.items():
                if key not in cols and re.fullmatch(pattern, label, re.I):
                    cols[key] = seg
                    break
        if "description" in cols and "qty" in cols and ("rate" in cols or "amount" in cols):
            return cols
        return None

    def _line_items(self, ctx: _Ctx, summary_rates: list[Decimal]) -> list[ExtractedLine]:
        rows: list[dict] = []
        for page in ctx.doc.pages:
            header = None
            spans: list[tuple[str, float, float]] = []
            last_y = None
            for line in page.lines:
                if header is None:
                    cols = self._header_columns(line)
                    if cols:
                        header = cols
                        ordered = sorted(cols.items(), key=lambda kv: kv[1].x0)
                        for i, (key, seg) in enumerate(ordered):
                            left = 0.0 if i == 0 else (ordered[i - 1][1].x1 + seg.x0) / 2
                            right = page.width if i == len(ordered) - 1 else (seg.x1 + ordered[i + 1][1].x0) / 2
                            spans.append((key, left, right))
                        last_y = line.yc
                    continue
                first_text = line.segments[0].text.strip()
                if TABLE_END.match(first_text) or any(TABLE_END.match(s.text.strip()) for s in line.segments[1:]
                                                      if s.x0 > page.width * 0.55):
                    break
                if last_y is not None and line.yc - last_y > 60:
                    break
                cells: dict[str, list[Segment]] = {}
                for seg in line.segments:
                    xc = (seg.x0 + seg.x1) / 2
                    for key, left, right in spans:
                        if left <= xc < right:
                            cells.setdefault(key, []).append(seg)
                            break
                row = self._parse_row(cells)
                if row is None:
                    continue
                if row.get("continuation"):
                    if rows:
                        rows[-1]["description"] = f"{rows[-1]['description']} {row['description']}".strip()
                    continue
                row["evidence"] = Evidence(page=line.page, snippet=line.text[:300],
                                           bbox=[round(min(w.x0 for w in line.words), 1),
                                                 round(min(w.y0 for w in line.words), 1),
                                                 round(max(w.x1 for w in line.words), 1),
                                                 round(max(w.y1 for w in line.words), 1)])
                rows.append(row)
                last_y = line.yc
        result = []
        single_rate = summary_rates[0] if len(summary_rates) == 1 else None
        for n, row in enumerate(rows, start=1):
            tax_rate, source = row.get("tax_rate"), "column" if row.get("tax_rate") is not None else None
            if tax_rate is None and single_rate is not None:
                tax_rate, source = single_rate, "summary"
            qty, price, sub = row.get("qty"), row.get("rate"), row.get("amount")
            consistent = None
            if qty is not None and price is not None and sub is not None:
                consistent = abs(q2(qty * price) - sub) <= Decimal("0.01")
            conf = row["conf"]
            if consistent:
                conf = max(conf, CROSS_VALIDATED_FLOOR)
            result.append(ExtractedLine(
                line_number=n, description=row.get("description"), quantity=qty, unit=row.get("unit"),
                unit_price=price, tax_rate=tax_rate, tax_rate_source=source, line_subtotal=sub,
                line_total=row.get("total"), confidence=round(conf, 3), arithmetic_consistent=consistent,
                evidence=row["evidence"]))
        return result

    @staticmethod
    def _parse_row(cells: dict[str, list[Segment]]) -> dict | None:
        def text_of(key):
            return " ".join(s.text for s in cells.get(key, [])).strip()

        def conf_of(key):
            segs = cells.get(key, [])
            return min((s.conf for s in segs), default=1.0)

        description = text_of("description")
        numeric_keys = [k for k in ("qty", "rate", "amount", "total") if k in cells]
        if not numeric_keys:
            if description and not cells.get("sl"):
                return {"continuation": True, "description": description}
            return None
        row: dict = {"description": description or None}
        qty_text = text_of("qty")
        unit = text_of("unit") or None
        m = re.match(r"^([\d,]+(?:\.\d+)?)\s*([A-Za-z]{1,6})?$", qty_text)
        if m:
            row["qty"] = parse_quantity(m.group(1))
            unit = unit or m.group(2)
        row["unit"] = unit.upper() if unit else None
        for key in ("rate", "amount", "total"):
            parsed = parse_amount_text(text_of(key)) if key in cells else None
            row[key] = q2(parsed[0]) if parsed else None
        tr = re.match(r"^(\d{1,2}(?:\.\d{1,2})?)\s*%?$", text_of("tax_rate")) if "tax_rate" in cells else None
        row["tax_rate"] = Decimal(tr.group(1)) if tr else None
        if row.get("qty") is None and row.get("amount") is None:
            return None
        used = [k for k in ("qty", "rate", "amount") if k in cells]
        row["conf"] = min([conf_of(k) for k in used] + [conf_of("description") if description else 1.0])
        return row

    # -- cross validation ----------------------------------------------------------------------------------
    @staticmethod
    def _cross_validate(fields: dict[str, ExtractedField], lines: list[ExtractedLine]) -> None:
        sub, tax, grand = (fields.get(k) for k in ("subtotal", "tax_total", "grand_total"))
        if not (sub and tax and grand and sub.present and tax.present and grand.present):
            return
        s, t, g = Decimal(sub.value), Decimal(tax.value), Decimal(grand.value)
        lines_sum = sum((ln.line_subtotal for ln in lines if ln.line_subtotal is not None), Decimal(0))
        if abs(s + t - g) <= Decimal("0.01") and lines and abs(lines_sum - s) <= Decimal("0.01"):
            for f in (sub, tax, grand):
                if f.confidence < CROSS_VALIDATED_FLOOR:
                    f.confidence = CROSS_VALIDATED_FLOOR
                    f.notes.append("Confirmed by arithmetic: line amounts, subtotal, tax and total reconcile")
