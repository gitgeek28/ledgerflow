"""PO candidate retrieval/ranking and one-to-one invoice-line to PO-line matching."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import POLine, PurchaseOrder, Vendor
from app.services.checks import CheckResult
from app.services.extraction.schema import ExtractedLine
from app.services.money import pct_delta
from app.services.po_ledger import consumed_amount
from app.services.policy import PolicySettings
from app.services.text_norm import normalise_description, normalise_po_number, normalise_unit


def description_similarity(a: str | None, b: str | None) -> float:
    na, nb = normalise_description(a), normalise_description(b)
    if not na or not nb:
        return 0.0
    return round(max(fuzz.token_set_ratio(na, nb), fuzz.token_sort_ratio(na, nb)) / 100.0, 4)


@dataclass
class LineMatch:
    invoice_line: int
    po_line_id: str | None
    po_line_number: int | None
    score: float
    description_similarity: float
    reason: str


def match_lines(inv_lines: list[ExtractedLine], po_lines: list[POLine], min_similarity: float) -> list[LineMatch]:
    """Greedy one-to-one assignment on a transparent score; unrelated items never match on price alone."""
    pairs = []
    for il in inv_lines:
        for pl in po_lines:
            sim = description_similarity(il.description, pl.description)
            if sim < min_similarity:
                continue
            unit_ok = 1.0 if (not il.unit or normalise_unit(il.unit) == normalise_unit(pl.unit)) else 0.0
            price_close = 0.0
            if il.unit_price is not None and pl.unit_price:
                delta = abs(pct_delta(Decimal(il.unit_price), pl.unit_price) or Decimal(0))
                price_close = max(0.0, 1.0 - float(delta) / 20.0)
            score = round(0.7 * sim + 0.15 * unit_ok + 0.15 * price_close, 4)
            pairs.append((score, sim, il.line_number, pl))
    pairs.sort(key=lambda p: p[0], reverse=True)
    used_inv, used_po, matches = set(), set(), {}
    for score, sim, inv_no, pl in pairs:
        if inv_no in used_inv or pl.id in used_po:
            continue
        used_inv.add(inv_no)
        used_po.add(pl.id)
        matches[inv_no] = LineMatch(inv_no, str(pl.id), pl.line_number, score, sim,
                                    f"description {sim:.2f}, combined {score:.2f}")
    result = []
    for il in inv_lines:
        result.append(matches.get(il.line_number) or LineMatch(
            il.line_number, None, None, 0.0, 0.0, f"no PO line with description similarity >= {min_similarity}"))
    return result


@dataclass
class POMatch:
    status: str                    # MATCHED | AMBIGUOUS | NOT_FOUND | VENDOR_MISMATCH | SKIPPED
    po: PurchaseOrder | None = None
    method: str | None = None
    candidates: list[dict] = field(default_factory=list)
    line_matches: list[LineMatch] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"status": self.status, "po_id": str(self.po.id) if self.po else None,
                "po_number": self.po.po_number if self.po else None, "method": self.method,
                "candidates": self.candidates, "notes": self.notes,
                "line_matches": [lm.__dict__ for lm in self.line_matches]}


def _load_po(db: Session, **where) -> PurchaseOrder | None:
    q = select(PurchaseOrder).options(selectinload(PurchaseOrder.lines))
    for k, v in where.items():
        q = q.where(getattr(PurchaseOrder, k) == v)
    return db.scalar(q)


def score_candidate(db: Session, po: PurchaseOrder, inv_lines: list[ExtractedLine], invoice_date: date | None,
                    subtotal: Decimal | None, policy: PolicySettings, invoice_id) -> dict:
    lm = match_lines(inv_lines, po.lines, float(policy.line_match_min_similarity))
    matched = [m for m in lm if m.po_line_id]
    n = max(len(inv_lines), 1)
    desc = sum(m.description_similarity for m in lm) / n
    structure = len(matched) / n
    by_id = {str(pl.id): pl for pl in po.lines}
    in_tol = 0
    for m in matched:
        il = next(x for x in inv_lines if x.line_number == m.invoice_line)
        pl = by_id[m.po_line_id]
        if il.unit_price is not None and (pct_delta(Decimal(il.unit_price), pl.unit_price) or 0) \
                <= policy.unit_price_variance_pct:
            in_tol += 1
    price = in_tol / n
    remaining = po.subtotal - consumed_amount(db, po.id, invoice_id)
    amount = 1.0
    if subtotal is not None and subtotal > remaining:
        amount = max(0.0, 1.0 - float((subtotal - remaining) / subtotal))
    date_ok = 1.0 if (invoice_date and po.po_date <= invoice_date <= po.valid_until) else 0.5
    score = round(0.35 * desc + 0.25 * structure + 0.2 * price + 0.1 * amount + 0.1 * date_ok, 4)
    return {"po_id": str(po.id), "po_number": po.po_number, "score": score, "description": round(desc, 3),
            "structure": round(structure, 3), "price": round(price, 3), "amount": round(amount, 3),
            "date": date_ok, "remaining_value": str(remaining), "po_date": po.po_date.isoformat(),
            "lines_matched": f"{len(matched)}/{len(inv_lines)}", "_lines": lm}


def match_po(db: Session, *, vendor: Vendor | None, po_reference: str | None, inv_lines: list[ExtractedLine],
             invoice_date: date | None, currency: str | None, subtotal: Decimal | None, policy: PolicySettings,
             invoice_id, human_po_id=None) -> POMatch:
    min_sim = float(policy.line_match_min_similarity)
    if human_po_id:
        po = _load_po(db, id=human_po_id)
        if po:
            return POMatch("MATCHED", po, "human-selected", line_matches=match_lines(inv_lines, po.lines, min_sim),
                           notes=["PO selected by a reviewer"])
    if po_reference:
        norm = normalise_po_number(po_reference)
        po = next((p for p in db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines)))
                   if normalise_po_number(p.po_number) == norm), None)
        if po is None:
            return POMatch("NOT_FOUND", notes=[f"Referenced PO '{po_reference}' does not exist in the PO register"])
        if vendor and po.vendor_id != vendor.id:
            return POMatch("VENDOR_MISMATCH", po, "reference",
                           notes=[f"{po.po_number} is issued to a different vendor"])
        return POMatch("MATCHED", po, "reference", line_matches=match_lines(inv_lines, po.lines, min_sim),
                       notes=[f"PO reference {po_reference} printed on invoice"])
    if vendor is None:
        return POMatch("SKIPPED", notes=["No PO reference and vendor unresolved; cannot search POs"])
    pos = db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.lines))
                     .where(PurchaseOrder.vendor_id == vendor.id, PurchaseOrder.status == "OPEN")).all()
    eligible = [p for p in pos if not currency or p.currency == currency]
    if not eligible:
        return POMatch("NOT_FOUND", notes=[f"No open PO for {vendor.vendor_code} in {currency or 'any currency'}"])
    scored = sorted((score_candidate(db, p, inv_lines, invoice_date, subtotal, policy, invoice_id)
                     for p in eligible), key=lambda c: c["score"], reverse=True)
    candidates = [{k: v for k, v in c.items() if k != "_lines"} for c in scored[:5]]
    top = scored[0]
    second = scored[1]["score"] if len(scored) > 1 else 0.0
    margin = round(top["score"] - second, 4)
    if Decimal(str(top["score"])) >= policy.po_candidate_min_score and Decimal(str(margin)) >= \
            policy.po_candidate_min_margin:
        po = next(p for p in eligible if str(p.id) == top["po_id"])
        return POMatch("MATCHED", po, "ranked", candidates, top["_lines"],
                       [f"No PO reference; {po.po_number} ranked first ({top['score']:.2f}, margin {margin:.2f})"])
    reason = (f"top score {top['score']:.2f} below threshold {policy.po_candidate_min_score}"
              if Decimal(str(top["score"])) < policy.po_candidate_min_score
              else f"margin {margin:.2f} below required {policy.po_candidate_min_margin}")
    return POMatch("AMBIGUOUS", None, "ranked", candidates,
                   notes=[f"No PO reference on invoice; {len(scored)} open POs considered; {reason}"])


def po_checks(m: POMatch) -> list[CheckResult]:
    ev = {"candidates": m.candidates, "notes": m.notes}
    if m.status == "MATCHED":
        out = [CheckResult("PO_NOT_FOUND", "PASS", f"{m.po.po_number} matched ({m.method})",
                           actual=m.po.po_number, evidence=ev)]
        if m.po.status != "OPEN":
            out.append(CheckResult("PO_CLOSED", "FAIL", f"{m.po.po_number} is {m.po.status.lower()}",
                                   actual=m.po.status, expected="OPEN"))
        return out
    if m.status == "AMBIGUOUS":
        return [CheckResult("PO_AMBIGUOUS", "FAIL", "Several open POs are plausible; a reviewer must choose. "
                            + " ".join(m.notes), actual=", ".join(c["po_number"] for c in m.candidates[:3]),
                            evidence=ev)]
    if m.status == "VENDOR_MISMATCH":
        return [CheckResult("PO_VENDOR_MISMATCH", "FAIL", " ".join(m.notes), actual=m.po.po_number, evidence=ev)]
    if m.status == "SKIPPED":
        return [CheckResult("PO_NOT_FOUND", "INDETERMINATE", " ".join(m.notes), evidence=ev)]
    return [CheckResult("PO_NOT_FOUND", "FAIL", " ".join(m.notes), evidence=ev)]
