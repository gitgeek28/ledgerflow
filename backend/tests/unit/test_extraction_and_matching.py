from decimal import Decimal
from types import SimpleNamespace

import pytest
import yaml

from app.core.config import REPO_DIR
from app.services.extraction.document import DocumentUnreadable, load_document
from app.services.extraction.rules import RuleBasedExtractor, parse_date
from app.services.extraction.schema import ExtractedLine
from app.services.po_matching import match_lines
from app.services.policy import PolicySettings
from app.services.vendor_resolution import resolve_vendor

CATALOGUE = {c["id"]: c for c in yaml.safe_load((REPO_DIR / "data/fixtures/scenarios.yaml").read_text())}
TEXT_LAYER = [k for k, c in CATALOGUE.items() if "labelled" in c and not c["labelled"]["scanned"]]


@pytest.mark.parametrize("sid", TEXT_LAYER)
def test_rules_extract_labelled_values_from_text_pdfs(sid):
    c = CATALOGUE[sid]
    r = RuleBasedExtractor().extract(load_document(str(REPO_DIR / "data/fixtures" / c["file"])))
    lab = c["labelled"]
    assert r.get("invoice_number") == lab["invoice_number"].upper()
    assert r.get("invoice_date") == lab["invoice_date"]
    assert r.get("po_number") == lab["po_number"]
    assert Decimal(r.get("grand_total")) == Decimal(lab["grand_total"])
    assert Decimal(r.get("subtotal")) == Decimal(lab["subtotal"])
    assert r.get("vendor_tax_id") == lab["vendor_gstin"]
    assert len(r.lines) == lab["line_count"]
    for got, exp in zip(r.lines, lab["lines"], strict=True):
        assert got.quantity == Decimal(exp["quantity"]) and got.unit_price == Decimal(exp["unit_price"])


def test_ocr_scan_low_confidence_is_reported_not_guessed():
    c = CATALOGUE["S07"]
    r = RuleBasedExtractor(0.85).extract(load_document(str(REPO_DIR / "data/fixtures" / c["file"])))
    f = r.fields["invoice_number"]
    assert (not f.present) or f.confidence < 0.85
    assert any(i.field == "invoice_number" for i in r.issues)


def test_corrupt_pdf_is_unreadable():
    with pytest.raises(DocumentUnreadable) as exc:
        load_document(str(REPO_DIR / "data/fixtures" / CATALOGUE["S12"]["file"]))
    assert exc.value.code == "PDF_UNREADABLE"


@pytest.mark.parametrize("text,iso", [("05-Nov-2026", "2026-11-05"), ("03/11/2026", "2026-11-03"),
                                      ("12.10.2026", "2026-10-12"), ("2026-11-05", "2026-11-05"),
                                      ("Nov 5, 2026", "2026-11-05"), ("31/02/2026", None)])
def test_parse_date(text, iso):
    r = parse_date(text)
    assert (r[0].isoformat() if r else None) == iso


def _vendor(code, name, tax_id=None, aliases=(), state="27"):
    return SimpleNamespace(id=code, vendor_code=code, legal_name=name, display_name=name, aliases=list(aliases),
                           tax_id=tax_id, state_code=state, approved_status="APPROVED")


def test_vendor_resolution_prefers_tax_id_and_refuses_close_fuzzy_calls():
    from app.services.identifiers import make_gstin
    g1 = make_gstin("03", "AADCI6619J")
    vendors = [_vendor("V-1", "Indus Fasteners Pvt Ltd", g1), _vendor("V-2", "Indus Fastening Systems Pvt Ltd",
                                                                      make_gstin("03", "AADCI7720K"))]
    p = PolicySettings()
    assert resolve_vendor(vendors, tax_id=g1, name="Indus Fastening Systems", document_text="", policy=p).vendor.vendor_code == "V-1"
    amb = resolve_vendor(vendors, tax_id=None, name="Indus Fasten Pvt Ltd", document_text="", policy=p)
    assert amb.status in ("AMBIGUOUS", "NOT_FOUND") and amb.vendor is None
    exact = resolve_vendor(vendors, tax_id=None, name="INDUS FASTENERS PRIVATE LIMITED", document_text="", policy=p)
    assert exact.status == "RESOLVED" and exact.vendor.vendor_code == "V-1"


def test_line_matching_is_one_to_one_and_rejects_unrelated_items():
    po_lines = [SimpleNamespace(id="a", line_number=1, description="Hex bolt M12 x 60 HT 8.8, zinc plated", unit="EA",
                                unit_price=Decimal("14.50")),
                SimpleNamespace(id="b", line_number=2, description="Hex nut M12 HT, zinc plated", unit="EA",
                                unit_price=Decimal("4.20"))]
    inv = [ExtractedLine(line_number=1, description="Hex nut M12 HT zinc plated", unit="EA", unit_price=Decimal("4.20")),
           ExtractedLine(line_number=2, description="Hex bolt M12x60 HT 8.8 zinc plated", unit="EA",
                         unit_price=Decimal("14.50")),
           ExtractedLine(line_number=3, description="Laptop 14 in Core i7", unit="EA", unit_price=Decimal("4.20"))]
    m = {x.invoice_line: x for x in match_lines(inv, po_lines, 0.6)}
    assert m[1].po_line_id == "b" and m[2].po_line_id == "a" and m[3].po_line_id is None
