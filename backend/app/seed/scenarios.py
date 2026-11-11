"""Scenario catalogue: synthetic invoice specifications + the outcome each one is expected to produce.

The PDF generator renders these specs; the evaluation harness and tests compare real pipeline output with
`expect`. "history" invoices are processed (through the real pipeline) to give the dashboard genuine history
and to set up prerequisites such as a prior split invoice or an original for the duplicate scenario.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class LineSpec:
    item: int          # index into the vendor's item catalogue
    qty: str
    price: str | None = None     # override the catalogue unit price (price-variance scenarios)
    tax_rate: str | None = None


@dataclass
class InvoiceSpec:
    sid: str
    title: str
    group: str                       # "demo" | "history"
    vendor_code: str
    invoice_number: str
    invoice_date: date
    po_number: str | None
    lines: list[LineSpec]
    layout: str = "A"                # A classic | B modern | C compact
    filename: str | None = None
    scanned: bool = False
    degrade: bool = False            # extra blur/noise over key fields (S07)
    corrupt: bool = False            # not a parseable PDF (S12)
    bank_override: str | None = None  # key into reference_data overrides
    printed_total_delta: str | None = None   # add to printed grand total only (S10 arithmetic error)
    printed_invoice_number: str | None = None  # how the number is printed if different (S03)
    show_po: bool = True
    prerequisites: list[str] = field(default_factory=list)
    description: str = ""
    expect: dict = field(default_factory=dict)

    @property
    def due_date(self) -> date:
        from app.seed.reference_data import VENDOR_BY_CODE
        return self.invoice_date + timedelta(days=VENDOR_BY_CODE[self.vendor_code].terms)

    @property
    def file_name(self) -> str:
        return self.filename or f"{self.sid}_{self.invoice_number.replace('/', '-')}.pdf"


L = LineSpec

HISTORY: list[InvoiceSpec] = [
    InvoiceSpec("H01", "Welding gases, October", "history", "V-1010", "KIG/26-27/1043", date(2026, 10, 12),
                "PO-450115", [L(0, "120"), L(1, "40")], layout="C",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY"}),
    InvoiceSpec("H02", "Hydraulics overhaul, partial delivery", "history", "V-1015", "SH/2026/0612",
                date(2026, 10, 7), "PO-450116", [L(0, "2"), L(1, "24"), L(2, "1")],
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY"}),
    InvoiceSpec("H03", "Spare pumps invoiced before receipt", "history", "V-1015", "SH/2026/0688",
                date(2026, 10, 30), "PO-450117", [L(2, "3")],
                expect={"status": "ON_HOLD", "codes": ["GRN_PENDING"]}),
    InvoiceSpec("H04", "Canteen services, October", "history", "V-1014", "LCS-1026", date(2026, 11, 2),
                "PO-450119", [L(0, "6200")], layout="C",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "TWO_WAY"}),
    InvoiceSpec("H05", "Lean advisory, 4 days", "history", "V-1011", "TNC/INV/2026/118", date(2026, 10, 20),
                "PO-450121", [L(0, "4")], layout="B",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "TWO_WAY"}),
    InvoiceSpec("H06", "Office consumables (original of S03)", "history", "V-1003", "MOS/2026/0457",
                date(2026, 10, 2), "PO-450103", [L(0, "200"), L(1, "30"), L(3, "150")], layout="B",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY"}),
    InvoiceSpec("H07", "Steel, first split invoice (S04a)", "history", "V-1002", "SGS/26-27/1187",
                date(2026, 10, 3), "PO-450110", [L(0, "250"), L(1, "80")],
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY"}),
    InvoiceSpec("H08", "Fasteners, first invoice (S05a)", "history", "V-1016", "IF/26/3301", date(2026, 9, 24),
                "PO-450120", [L(0, "3000"), L(1, "3000")], layout="C",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY"}),
    InvoiceSpec("H09", "PPE from vendor still in onboarding", "history", "V-1012", "ASE/2026/077",
                date(2026, 10, 29), "PO-450114", [L(0, "150"), L(1, "150")],
                expect={"status": "ON_HOLD", "codes": ["VENDOR_NOT_APPROVED"]}),
    InvoiceSpec("H10", "Housekeeping, October", "history", "V-1007", "OFM/2026/10/221", date(2026, 10, 31),
                "PO-450107", [L(0, "1")], layout="B",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "TWO_WAY"}),
    InvoiceSpec("H11", "Anchor bolts, price within tolerance", "history", "V-1017", "IFS-2026-0419",
                date(2026, 10, 22), "PO-450122", [L(0, "600", price="42.60"), L(1, "200")], layout="C",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY"}),
    InvoiceSpec("H12", "Invoice against a closed PO", "history", "V-1009", "BEPL/26-27/0371", date(2026, 10, 9),
                "PO-450124", [L(2, "2")],
                expect={"status": "NEEDS_REVIEW", "codes": ["PO_CLOSED"]}),
]

DEMO: list[InvoiceSpec] = [
    InvoiceSpec("S01", "Clean invoice, three-way match", "demo", "V-1005", "PBI/2026/0981", date(2026, 11, 5),
                "PO-450101", [L(0, "400"), L(1, "120"), L(2, "60")], layout="A",
                description="Approved vendor, exact PO reference, quantities fully received (GRN-780101), prices and "
                            "18% IGST match the PO.",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY", "vendor": "V-1005",
                        "po": "PO-450101", "invoice_number": "PBI/2026/0981", "grand_total": "330872.00",
                        "codes_absent": ["PRICE_VARIANCE_EXCEEDED", "QUANTITY_EXCEEDED"]}),
    InvoiceSpec("S03", "Same invoice re-sent in a different format", "demo", "V-1003", "MOS/2026/0457",
                date(2026, 10, 2), "PO-450103", [L(0, "200"), L(1, "30"), L(3, "150")], layout="C",
                printed_invoice_number="MOS-2026-0457", filename="Meridian_reminder_MOS-2026-0457.pdf",
                prerequisites=["H06"],
                description="Vendor re-sends invoice MOS/2026/0457 as a 'reminder' with a different layout and number "
                            "formatting. Bytes differ, so the file hash does not match; the business key does.",
                expect={"status": "ON_HOLD", "codes": ["INVOICE_DUPLICATE_SUSPECTED"], "vendor": "V-1003"}),
    InvoiceSpec("S04", "Second split invoice within PO balance", "demo", "V-1002", "SGS/26-27/1214",
                date(2026, 10, 23), "PO-450110", [L(0, "150"), L(1, "40")], layout="A", prerequisites=["H07"],
                description="PO-450110 ordered 400 angles and 120 plates. H07 already invoiced 250 + 80. This invoice "
                            "bills the remaining 150 + 40, all received across two GRNs.",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY", "po": "PO-450110"}),
    InvoiceSpec("S05", "Cumulative quantity exceeds PO and receipts", "demo", "V-1016", "IF/26/3388",
                date(2026, 10, 30), "PO-450120", [L(0, "2500"), L(1, "2500")], layout="C", prerequisites=["H08"],
                description="5,000 bolts ordered and received; 3,000 already invoiced (H08). This invoice claims "
                            "2,500 more: 500 over the ordered and received quantity.",
                expect={"status": "NEEDS_REVIEW", "codes": ["QUANTITY_EXCEEDED", "GRN_QUANTITY_MISMATCH"]}),
    InvoiceSpec("S06", "No PO reference, two plausible POs", "demo", "V-1004", "CL/2026/7781", date(2026, 11, 4),
                None, [L(0, "2"), L(1, "2")], layout="B", show_po=False,
                description="Freight invoice without a PO number. Two open POs (PO-450130, PO-450131) have identical "
                            "lanes and rates, so ranking cannot separate them.",
                expect={"status": "NEEDS_REVIEW", "codes": ["PO_AMBIGUOUS"], "vendor": "V-1004"}),
    InvoiceSpec("S07", "Poor-quality scan", "demo", "V-1008", "SPI/1311/26", date(2026, 11, 6), "PO-450108",
                [L(0, "3000"), L(1, "6000")], layout="A", scanned=True, degrade=True,
                description="Image-only scan with smudging over the header. OCR must be used and the critical fields "
                            "come back with low confidence; the system must not guess.",
                expect={"status": "NEEDS_REVIEW",
                        "codes_any": ["LOW_EXTRACTION_CONFIDENCE", "CRITICAL_FIELD_MISSING"]}),
    InvoiceSpec("S08", "Remittance bank details changed", "demo", "V-1006", "NCS/INV/26/1104", date(2026, 11, 3),
                "PO-450106", [L(0, "1"), L(1, "1")], layout="B", bank_override="S08",
                description="Monthly cloud invoice that is otherwise perfect, but asks for payment into a different "
                            "bank account than the verified vendor master.",
                expect={"status": "NEEDS_REVIEW", "codes": ["VENDOR_BANK_DETAILS_CHANGED"], "priority": "HIGH"}),
    InvoiceSpec("S09", "Unit price above tolerance", "demo", "V-1001", "VSS/26-27/0412", date(2026, 11, 7),
                "PO-450109", [L(0, "10", price="43500.00"), L(1, "5")], layout="A",
                description="Licences billed at 43,500 against a PO price of 42,000 (+3.57%, tolerance 2%).",
                expect={"status": "NEEDS_REVIEW", "codes": ["PRICE_VARIANCE_EXCEEDED"], "po": "PO-450109"}),
    InvoiceSpec("S10", "Totals do not add up", "demo", "V-1009", "BEPL/26-27/0402", date(2026, 11, 2),
                "PO-450112", [L(0, "40"), L(1, "500"), L(2, "4")], layout="A", printed_total_delta="10000.00",
                description="Line items and tax are correct but the printed grand total is 10,000 higher than "
                            "subtotal + tax.",
                expect={"status": "NEEDS_REVIEW", "codes": ["TOTAL_ARITHMETIC_MISMATCH"]}),
    InvoiceSpec("S11", "Blocked vendor", "demo", "V-1013", "RPM/2026/0559", date(2026, 11, 1), "PO-450113",
                [L(0, "1"), L(1, "6")], layout="B",
                description="Vendor exists in master data but was blocked after failed KYC re-verification.",
                expect={"status": "REJECTED", "codes": ["VENDOR_NOT_APPROVED"]}),
    InvoiceSpec("S12", "Corrupted PDF", "demo", "V-1009", "CORRUPT", date(2026, 11, 1), None, [],
                corrupt=True, filename="S12_corrupted_upload.pdf",
                description="A file that starts with a PDF header but whose body is damaged.",
                expect={"status": "FAILED", "retryable": False}),
    InvoiceSpec("S13", "Multi-page invoice, 26 lines", "demo", "V-1018", "GLH/2026/11/0093", date(2026, 11, 4),
                "PO-450118", [L(i, q) for i, q in enumerate(
                    ["12", "8", "20", "20", "6", "25", "20", "20", "15", "10", "2", "6", "80", "40", "4", "6", "2",
                     "8", "1", "1", "1", "1", "10", "6", "12", "4"])], layout="B",
                description="Line-item table spans two pages.",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY", "line_count": 26}),
    InvoiceSpec("S14", "Clean scanned invoice", "demo", "V-1010", "KIG/26-27/1268", date(2026, 11, 9),
                "PO-450128", [L(0, "120"), L(1, "40")], layout="A", scanned=True,
                description="Image-only PDF (no text layer) read by OCR; good scan quality, goods received.",
                expect={"status": "READY_FOR_APPROVAL", "match_mode": "THREE_WAY"}),
]

ALL_SPECS = HISTORY + DEMO
SPEC_BY_ID = {s.sid: s for s in ALL_SPECS}
# S02 has no separate document: it re-uploads the exact bytes of S01.
S02 = {"sid": "S02", "title": "Exact duplicate file", "source": "S01",
       "description": "Upload the S01 PDF a second time (identical bytes).",
       "expect": {"duplicate_file": True, "new_invoice_created": False}}
