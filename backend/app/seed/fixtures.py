"""Synthetic invoice PDF generator (three vendor layouts, multi-page tables, scanned and corrupt variants).

Usage:  uv run python -m app.seed.fixtures            # writes data/fixtures/{pdfs,scenarios.yaml}
"""
import io
import random
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pymupdf as fitz
import yaml
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.core.config import REPO_DIR
from app.seed.reference_data import BUYER, S08_INVOICE_BANK, VENDOR_BY_CODE
from app.seed.scenarios import ALL_SPECS, S02, InvoiceSpec
from app.services.identifiers import make_gstin
from app.services.money import q2

OUT_DIR = REPO_DIR / "data" / "fixtures"
PDF_DIR = OUT_DIR / "pdfs"
W, H = A4
INK = HexColor("#1d2433")
MUTED = HexColor("#5b6475")
RULE = HexColor("#c9ced8")
STATE_NAMES = {"27": "Maharashtra", "29": "Karnataka", "33": "Tamil Nadu", "24": "Gujarat", "36": "Telangana",
               "07": "Delhi", "06": "Haryana", "03": "Punjab"}


@dataclass
class Row:
    n: int
    description: str
    hsn: str
    qty: Decimal
    unit: str
    price: Decimal
    rate: Decimal
    taxable: Decimal
    tax: Decimal
    total: Decimal


def indian(value: Decimal) -> str:
    """Format with Indian digit grouping: 3,30,872.00"""
    s = f"{q2(value):.2f}"
    whole, frac = s.split(".")
    neg = whole.startswith("-")
    whole = whole.lstrip("-")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{'-' if neg else ''}{whole}.{frac}"


def intl(value: Decimal) -> str:
    return f"{q2(value):,.2f}"


def qty_str(q: Decimal) -> str:
    return f"{q.normalize():f}" if q == q.to_integral() else f"{q:.3f}".rstrip("0")


def build_rows(spec: InvoiceSpec) -> list[Row]:
    vendor = VENDOR_BY_CODE[spec.vendor_code]
    rows = []
    for n, ls in enumerate(spec.lines, start=1):
        item = vendor.items[ls.item]
        qty = Decimal(ls.qty)
        price = Decimal(ls.price or item.price)
        rate = Decimal(ls.tax_rate or item.tax_rate)
        taxable = q2(qty * price)
        tax = q2(taxable * rate / 100)
        rows.append(Row(n, item.description, item.hsn, qty, item.unit, price, rate, taxable, tax, taxable + tax))
    return rows


def fmt_date(d: date, layout: str) -> str:
    if layout == "A":
        return d.strftime("%d-%b-%Y")
    if layout == "B":
        return d.strftime("%d/%m/%Y")
    return d.strftime("%d.%m.%Y")


class Doc:
    def __init__(self, spec: InvoiceSpec):
        self.spec = spec
        self.vendor = VENDOR_BY_CODE[spec.vendor_code]
        self.gstin = make_gstin(self.vendor.state_code, self.vendor.pan)
        self.buyer_gstin = make_gstin(BUYER["state_code"], BUYER["gstin_pan"])
        self.rows = build_rows(spec)
        self.subtotal = sum((r.taxable for r in self.rows), Decimal(0))
        self.tax = sum((r.tax for r in self.rows), Decimal(0))
        self.grand = self.subtotal + self.tax
        self.printed_grand = self.grand + Decimal(spec.printed_total_delta or "0")
        self.intra = self.vendor.state_code == BUYER["state_code"]
        self.number = spec.printed_invoice_number or spec.invoice_number
        bank = S08_INVOICE_BANK if spec.bank_override == "S08" else {
            "bank_name": self.vendor.bank_name, "account": self.vendor.account, "ifsc": self.vendor.ifsc}
        self.bank = bank
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.c.setTitle(f"Invoice {self.number}")
        self.c.setAuthor(self.vendor.legal_name)
        self.c.setSubject("Synthetic demo document - LedgerFlow case study")

    # -- primitives ---------------------------------------------------------------------------------------
    def text(self, x, y, s, size=9, bold=False, color=INK, align="left"):
        c = self.c
        c.setFillColor(color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if align == "right":
            c.drawRightString(x, y, s)
        elif align == "center":
            c.drawCentredString(x, y, s)
        else:
            c.drawString(x, y, s)

    def rule(self, x1, y, x2, color=RULE, width=0.6):
        self.c.setStrokeColor(color)
        self.c.setLineWidth(width)
        self.c.line(x1, y, x2, y)

    def banner(self, page: int, pages: int):
        self.text(W / 2, H - 18, "SYNTHETIC DEMO DOCUMENT  -  LedgerFlow case study  -  not a real invoice",
                  size=6.5, color=Color(0.55, 0.58, 0.64), align="center")
        self.text(W - 40, 24, f"Page {page} of {pages}", size=7.5, color=MUTED, align="right")

    def tax_lines(self) -> list[tuple[str, Decimal]]:
        rates = sorted({r.rate for r in self.rows})
        out = []
        for rate in rates:
            tax = sum((r.tax for r in self.rows if r.rate == rate), Decimal(0))
            if self.intra:
                half = q2(tax / 2)
                out.append((f"CGST @ {rate / 2:g}%", half))
                out.append((f"SGST @ {rate / 2:g}%", tax - half))
            else:
                out.append((f"IGST @ {rate:g}%", tax))
        return out

    def bank_block(self, x, y, style="A"):
        b = self.bank
        if style == "B":
            self.text(x, y, "PAYMENT DETAILS", size=7.5, bold=True, color=MUTED)
            self.text(x, y - 13, f"Bank: {b['bank_name']}", size=8.5)
            self.text(x, y - 25, f"Account Number: {b['account']}", size=8.5)
            self.text(x, y - 37, f"IFSC: {b['ifsc']}", size=8.5)
            self.text(x, y - 49, f"Account Name: {self.vendor.legal_name}", size=8.5)
        else:
            self.text(x, y, "Bank details for remittance", size=8.5, bold=True)
            self.text(x, y - 12, f"Bank: {b['bank_name']}", size=8.5)
            self.text(x, y - 24, f"A/c No: {b['account']}", size=8.5)
            self.text(x, y - 36, f"IFSC: {b['ifsc']}", size=8.5)

    # -- layouts ------------------------------------------------------------------------------------------
    def render(self) -> bytes:
        getattr(self, f"layout_{self.spec.layout.lower()}")()
        self.c.save()
        return self.buf.getvalue()

    def layout_a(self):
        s, v = self.spec, self.vendor
        rows_per_first, rows_per_next = 18, 34
        chunks = paginate(self.rows, rows_per_first, rows_per_next)
        for pi, chunk in enumerate(chunks):
            if pi:
                self.c.showPage()
            self.banner(pi + 1, len(chunks))
            top = H - 52
            if pi == 0:
                self.text(40, top, v.legal_name, size=15, bold=True)
                y = top - 15
                for line in wrap(v.address, 60):
                    self.text(40, y, line, size=8.5, color=MUTED)
                    y -= 11
                self.text(40, y, f"GSTIN: {self.gstin}", size=8.5)
                self.text(40, y - 11, f"Email: {v.email}", size=8.5, color=MUTED)
                self.text(W - 40, top, "TAX INVOICE", size=17, bold=True, align="right")
                meta = [("Invoice No:", self.number), ("Invoice Date:", fmt_date(s.invoice_date, "A")),
                        ("Due Date:", fmt_date(s.due_date, "A"))]
                if s.show_po and s.po_number:
                    meta.append(("PO Number:", s.po_number))
                my = top - 22
                for label, value in meta:
                    self.text(372, my, f"{label} {value}", size=9)
                    my -= 13
                by = top - 92
                self.rule(40, by + 10, W - 40)
                self.text(40, by - 4, "Bill To:", size=8.5, bold=True, color=MUTED)
                self.text(40, by - 17, BUYER["name"], size=9.5, bold=True)
                self.text(40, by - 29, BUYER["address"], size=8.5, color=MUTED)
                self.text(40, by - 41, f"GSTIN: {self.buyer_gstin}", size=8.5)
                pos = STATE_NAMES[BUYER["state_code"]]
                self.text(372, by - 4, f"Place of Supply: {pos} ({BUYER['state_code']})", size=8.5)
                self.text(372, by - 17, "Currency: INR", size=8.5)
                ty = by - 70
            else:
                self.text(40, top, f"{v.legal_name}  -  Invoice {self.number} (continued)", size=9, bold=True)
                ty = top - 30
            cols = [("#", 40, "l"), ("Description", 60, "l"), ("HSN/SAC", 268, "l"), ("Qty", 362, "r"),
                    ("Unit", 374, "l"), ("Rate", 452, "r"), ("GST %", 497, "r"), ("Amount", W - 40, "r")]
            self.rule(40, ty + 12, W - 40, INK, 0.8)
            for label, x, al in cols:
                self.text(x, ty, label, size=8.5, bold=True, align="right" if al == "r" else "left")
            self.rule(40, ty - 6, W - 40, INK, 0.8)
            y = ty - 20
            for r in chunk:
                vals = [str(r.n), r.description, r.hsn, qty_str(r.qty), r.unit, indian(r.price), f"{r.rate:g}",
                        indian(r.taxable)]
                for (_label, x, al), val in zip(cols, vals, strict=True):
                    self.text(x, y, val, size=8.5, align="right" if al == "r" else "left")
                y -= 16
            self.rule(40, y + 8, W - 40)
            if pi == len(chunks) - 1:
                ty2 = y - 10
                lines = [("Subtotal", self.subtotal)] + self.tax_lines() + [("Total Tax", self.tax)]
                for label, amount in lines:
                    self.text(372, ty2, label, size=9)
                    self.text(W - 40, ty2, indian(amount), size=9, align="right")
                    ty2 -= 14
                self.rule(372, ty2 + 9, W - 40, INK, 0.8)
                self.text(372, ty2 - 4, "Grand Total (INR)", size=10, bold=True)
                self.text(W - 40, ty2 - 4, indian(self.printed_grand), size=10, bold=True, align="right")
                self.bank_block(40, y - 10)
                self.text(40, 60, "Payment terms: " + f"{v.terms} days from invoice date.", size=8, color=MUTED)
                self.text(40, 48, "This is a computer generated invoice.", size=8, color=MUTED)

    def layout_b(self):
        s, v = self.spec, self.vendor
        chunks = paginate(self.rows, 16, 34)
        for pi, chunk in enumerate(chunks):
            if pi:
                self.c.showPage()
            self.banner(pi + 1, len(chunks))
            top = H - 56
            if pi == 0:
                self.text(40, top, "INVOICE", size=24, bold=True)
                self.text(40, top - 16, "Tax invoice under GST", size=8.5, color=MUTED)
                self.text(W - 40, top + 4, v.legal_name, size=12, bold=True, align="right")
                y = top - 10
                for line in wrap(v.address, 55):
                    self.text(W - 40, y, line, size=8, color=MUTED, align="right")
                    y -= 10
                self.text(W - 40, y, f"GSTIN: {self.gstin}", size=8, align="right")
                my = top - 70
                meta = [("INVOICE NUMBER", self.number), ("INVOICE DATE", fmt_date(s.invoice_date, "B")),
                        ("DUE DATE", fmt_date(s.due_date, "B"))]
                if s.show_po and s.po_number:
                    meta.append(("PURCHASE ORDER", s.po_number))
                meta.append(("CURRENCY", "INR"))
                for i, (label, value) in enumerate(meta):
                    x = 40 + i * 106
                    self.text(x, my, label, size=7, bold=True, color=MUTED)
                    self.text(x, my - 14, value, size=10)
                by = my - 44
                self.text(40, by, "BILLED TO", size=7, bold=True, color=MUTED)
                self.text(40, by - 13, BUYER["name"], size=9.5, bold=True)
                self.text(40, by - 25, BUYER["address"], size=8.5, color=MUTED)
                self.text(40, by - 37, f"GSTIN: {self.buyer_gstin}", size=8.5)
                ty = by - 66
            else:
                self.text(40, top, f"Invoice {self.number} - continued", size=10, bold=True)
                self.text(W - 40, top, v.legal_name, size=9, align="right")
                ty = top - 30
            cols = [("Description", 40, "l"), ("Qty", 290, "r"), ("UoM", 302, "l"), ("Unit Price", 392, "r"),
                    ("Taxable Value", 468, "r"), ("Tax %", 503, "r"), ("Total", W - 40, "r")]
            self.c.setFillColor(HexColor("#eef1f6"))
            self.c.rect(36, ty - 6, W - 72, 18, stroke=0, fill=1)
            for label, x, al in cols:
                self.text(x, ty, label, size=8, bold=True, align="right" if al == "r" else "left")
            y = ty - 20
            for r in chunk:
                vals = [r.description, qty_str(r.qty), r.unit, intl(r.price), intl(r.taxable), f"{r.rate:g}",
                        intl(r.total)]
                for (_label, x, al), val in zip(cols, vals, strict=True):
                    self.text(x, y, val, size=8, align="right" if al == "r" else "left")
                self.rule(40, y - 5, W - 40, HexColor("#e3e6ec"), 0.4)
                y -= 16
            if pi == len(chunks) - 1:
                ty2 = y - 14
                lines = [("Sub-total", self.subtotal)] + self.tax_lines() + [("Total Tax", self.tax)]
                for label, amount in lines:
                    self.text(392, ty2, label, size=9, align="right")
                    self.text(W - 40, ty2, intl(amount), size=9, align="right")
                    ty2 -= 14
                self.text(392, ty2 - 6, "Amount Due (INR)", size=11, bold=True, align="right")
                self.text(W - 40, ty2 - 6, intl(self.printed_grand), size=11, bold=True, align="right")
                self.bank_block(40, y - 14, style="B")
                self.text(40, 50, f"Please quote invoice number {self.number} with your remittance.", size=8,
                          color=MUTED)

    def layout_c(self):
        s, v = self.spec, self.vendor
        chunks = paginate(self.rows, 20, 36)
        for pi, chunk in enumerate(chunks):
            if pi:
                self.c.showPage()
            self.banner(pi + 1, len(chunks))
            top = H - 50
            if pi == 0:
                self.text(W / 2, top, v.legal_name.upper(), size=13, bold=True, align="center")
                self.text(W / 2, top - 13, v.address, size=8, color=MUTED, align="center")
                self.text(W / 2, top - 25, f"GSTIN: {self.gstin}", size=8, align="center")
                self.text(W / 2, top - 44, "TAX INVOICE", size=11, bold=True, align="center")
                self.rule(40, top - 52, W - 40, INK, 0.8)
                my = top - 68
                left = [("Bill No.:", self.number), ("Bill Date:", fmt_date(s.invoice_date, "C"))]
                if s.show_po and s.po_number:
                    left.append(("Your Order Ref:", s.po_number))
                for label, value in left:
                    self.text(40, my, f"{label} {value}", size=9)
                    my -= 13
                self.text(330, top - 68, "Buyer:", size=8.5, bold=True)
                self.text(330, top - 81, BUYER["name"], size=9)
                self.text(330, top - 94, f"GSTIN: {self.buyer_gstin}", size=8.5)
                self.text(40, my - 4, "All amounts in INR", size=8, color=MUTED)
                ty = my - 30
            else:
                self.text(40, top, f"{v.legal_name} - Bill {self.number} (contd.)", size=9, bold=True)
                ty = top - 30
            cols = [("Sl", 40, "l"), ("Particulars", 62, "l"), ("Qty", 380, "r"), ("Rate", 460, "r"),
                    ("Amount", W - 40, "r")]
            self.rule(40, ty + 12, W - 40, INK, 0.6)
            for label, x, al in cols:
                self.text(x, ty, label, size=8.5, bold=True, align="right" if al == "r" else "left")
            self.rule(40, ty - 6, W - 40, INK, 0.6)
            y = ty - 19
            for r in chunk:
                vals = [str(r.n), r.description, f"{qty_str(r.qty)} {r.unit}", indian(r.price), indian(r.taxable)]
                for (_label, x, al), val in zip(cols, vals, strict=True):
                    self.text(x, y, val, size=8.5, align="right" if al == "r" else "left")
                y -= 15
            self.rule(40, y + 7, W - 40, INK, 0.6)
            if pi == len(chunks) - 1:
                ty2 = y - 10
                lines = [("Taxable Amount", self.subtotal)] + self.tax_lines()
                for label, amount in lines:
                    self.text(460, ty2, label, size=9, align="right")
                    self.text(W - 40, ty2, indian(amount), size=9, align="right")
                    ty2 -= 14
                self.text(460, ty2 - 4, "Net Payable", size=10, bold=True, align="right")
                self.text(W - 40, ty2 - 4, indian(self.printed_grand), size=10, bold=True, align="right")
                self.bank_block(40, ty2 - 40)
                self.text(40, 50, "Subject to local jurisdiction. E. & O.E.", size=7.5, color=MUTED)


def paginate(rows, first, nxt):
    if len(rows) <= first:
        return [rows]
    chunks = [rows[:first]]
    rest = rows[first:]
    while rest:
        chunks.append(rest[:nxt])
        rest = rest[nxt:]
    return chunks


def wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


SCAN_CLEAN = {"dpi": 300, "rotate": 0.1, "speckles": 100, "blur": 0.0, "jpeg": 90}
SCAN_POOR = {"dpi": 300, "rotate": 0.5, "speckles": 4000, "blur": 0.4, "jpeg": 55,
             "smudge_blur": 1.2, "smudge_contrast": 0.65}


def to_scanned(pdf_bytes: bytes, seed: int, degrade: bool) -> bytes:
    """Rasterise each page into a noisy grayscale image (no text layer), like a photocopier scan."""
    p = SCAN_POOR if degrade else SCAN_CLEAN
    rnd = random.Random(seed)
    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    out = fitz.open()
    dpi = p["dpi"]
    for page in src:
        pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        if degrade:
            # Smudge the header metadata block (invoice no / dates / PO) as if a thumb or coffee ring hit it.
            scale = dpi / 72
            box = tuple(int(v * scale) for v in (360, 60, 560, 135))
            region = img.crop(box).filter(ImageFilter.GaussianBlur(p["smudge_blur"]))
            region = ImageEnhance.Contrast(region).enhance(p["smudge_contrast"])
            img.paste(region, box)
        img = img.rotate(rnd.uniform(-p["rotate"], p["rotate"]), resample=Image.BICUBIC, fillcolor=255)
        px = img.load()
        w, h = img.size
        for _ in range(p["speckles"]):
            x, y = rnd.randrange(w), rnd.randrange(h)
            px[x, y] = rnd.choice((0, 60, 200))
        if p["blur"]:
            img = img.filter(ImageFilter.GaussianBlur(p["blur"]))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=p["jpeg"])
        rect = page.rect
        new = out.new_page(width=rect.width, height=rect.height)
        new.insert_image(rect, stream=buf.getvalue())
    out.set_metadata({"title": "Scanned document", "producer": "LedgerFlow synthetic scanner"})
    return out.tobytes(garbage=3, deflate=True)


def corrupt_bytes(seed: int) -> bytes:
    rnd = random.Random(seed)
    return b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + rnd.randbytes(6000)


def render_spec(spec: InvoiceSpec) -> bytes:
    if spec.corrupt:
        return corrupt_bytes(1212)
    pdf = Doc(spec).render()
    if spec.scanned:
        pdf = to_scanned(pdf, seed=sum(map(ord, spec.sid)), degrade=spec.degrade)
    return pdf


def catalogue_entry(spec: InvoiceSpec) -> dict:
    entry = {"id": spec.sid, "title": spec.title, "group": spec.group, "file": f"pdfs/{spec.file_name}",
             "description": spec.description, "vendor_code": spec.vendor_code,
             "prerequisites": spec.prerequisites, "expect": spec.expect}
    if not spec.corrupt:
        d = Doc(spec)
        entry["labelled"] = {
            "invoice_number": spec.printed_invoice_number or spec.invoice_number,
            "invoice_date": spec.invoice_date.isoformat(),
            "due_date": spec.due_date.isoformat() if spec.layout != "C" else None,
            "po_number": spec.po_number if spec.show_po else None, "currency": "INR",
            "subtotal": str(d.subtotal), "tax_total": str(d.tax), "grand_total": str(d.printed_grand),
            "vendor_gstin": d.gstin, "line_count": len(d.rows), "scanned": spec.scanned,
            "lines": [{"description": r.description, "quantity": qty_str(r.qty), "unit_price": str(r.price),
                       "line_subtotal": str(r.taxable)} for r in d.rows],
        }
    return entry


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    catalogue = []
    for spec in ALL_SPECS:
        (PDF_DIR / spec.file_name).write_bytes(render_spec(spec))
        catalogue.append(catalogue_entry(spec))
    catalogue.append({"id": S02["sid"], "title": S02["title"], "group": "demo",
                      "file": catalogue[[c["id"] for c in catalogue].index("S01")]["file"],
                      "description": S02["description"], "prerequisites": ["S01"], "expect": S02["expect"]})
    header = ("# Generated by `python -m app.seed.fixtures` - do not edit by hand.\n"
              "# Synthetic scenario catalogue for LedgerFlow. Labelled values are the ground truth used by the\n"
              "# evaluation harness; `expect` is the outcome the decision engine should produce.\n")
    (OUT_DIR / "scenarios.yaml").write_text(header + yaml.safe_dump(catalogue, sort_keys=False, width=110))
    print(f"wrote {len(ALL_SPECS)} PDFs to {PDF_DIR.relative_to(REPO_DIR)}")


if __name__ == "__main__":
    main()
