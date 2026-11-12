from decimal import Decimal

import pytest

from app.services.identifiers import gstin_check_char, is_valid_gstin, make_gstin
from app.services.money import D, parse_amount, pct_delta, q2
from app.services.redaction import mask_digits
from app.services.text_norm import (
    normalise_description,
    normalise_invoice_number,
    normalise_name,
    normalise_unit,
)


@pytest.mark.parametrize("raw,expected", [
    ("3,30,872.00", "330872.00"), ("Rs. 1,18,000", "118000"), ("INR 59,000.50", "59000.50"),
    ("(1,200.50)", "-1200.50"), ("330,872.00", "330872.00"), ("12.5.3", None), ("abc", None), ("", None),
])
def test_parse_amount(raw, expected):
    v = parse_amount(raw)
    assert (str(v) if v is not None else None) == expected


def test_floats_are_rejected_for_money():
    with pytest.raises(TypeError):
        D(0.1)


def test_rounding_is_half_up_and_exact():
    assert q2(Decimal("2.345")) == Decimal("2.35")
    assert q2(Decimal("0.1") + Decimal("0.2")) == Decimal("0.30")
    assert sum([Decimal("0.10")] * 10) == Decimal("1.00")


def test_pct_delta_boundaries():
    assert pct_delta(Decimal("42840"), Decimal("42000")) == Decimal("2.00")
    assert pct_delta(Decimal("43500"), Decimal("42000")) == Decimal("3.57")
    assert pct_delta(Decimal("1"), Decimal("0")) is None


def test_gstin_checksum():
    g = make_gstin("27", "AAGCK4821M")
    assert is_valid_gstin(g)
    assert not is_valid_gstin(g[:-1] + ("0" if g[-1] != "0" else "1"))
    assert not is_valid_gstin("27AAGCK4821M1Z")
    assert gstin_check_char(g[:14]) == g[14]


def test_name_and_description_normalisation():
    assert normalise_name("Acme Technologies Pvt. Ltd.") == normalise_name("ACME TECHNOLOGIES PRIVATE LIMITED")
    assert normalise_name("Shree Ganesh Steel & Co.") == "shree ganesh steel"
    assert normalise_description("Hex bolt M12 x 60, zinc plated") == normalise_description("hex bolt m12x60 zinc plated")
    assert normalise_unit("Nos") == normalise_unit("pcs") == "EA"
    assert normalise_invoice_number("MOS/2026/0457") == normalise_invoice_number("MOS-2026-0457") == "MOS20260457"


def test_mask_digits_keeps_last_four_and_leaves_amounts():
    assert mask_digits("A/c No: 38881234567") == "A/c No: ••••4567"
    assert mask_digits("Total 3,30,872.00 qty 4819 3000") == "Total 3,30,872.00 qty 4819 3000"


def test_bank_fingerprint_does_not_depend_on_session_secret(monkeypatch):
    from app.core.config import get_settings
    from app.services.identifiers import bank_fingerprint
    before = bank_fingerprint("38881234567")
    monkeypatch.setattr(get_settings(), "secret_key", "rotated-session-secret")
    assert bank_fingerprint("38881234567") == before
    assert bank_fingerprint("3888 1234 567") == before
