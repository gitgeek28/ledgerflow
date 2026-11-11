from decimal import Decimal

from app.services.checks import CheckResult
from app.services.decision import decide
from app.services.extraction.schema import ExtractedLine
from app.services.reconciliation import arithmetic_checks


def _decide(checks):
    return decide(checks, match_mode="THREE_WAY", po_number="PO-1", vendor_name="V", grand_total=Decimal("100"),
                  currency="INR", requires_manager=False, security=False)


def test_all_pass_is_ready():
    d = _decide([CheckResult("PRICE_VARIANCE_EXCEEDED", "PASS", "ok")])
    assert d.status == "READY_FOR_APPROVAL" and d.reason_codes == []


def test_precedence_reject_over_hold_over_review():
    checks = [CheckResult("PRICE_VARIANCE_EXCEEDED", "FAIL", "x"), CheckResult("GRN_PENDING", "FAIL", "y")]
    assert _decide(checks).status == "ON_HOLD"
    checks.append(CheckResult("VENDOR_NOT_APPROVED", "FAIL", "z", outcome="REJECT"))
    d = _decide(checks)
    assert d.status == "REJECTED" and d.reason_codes[0] == "VENDOR_NOT_APPROVED"


def test_indeterminate_fails_closed_and_info_does_not_block():
    assert _decide([CheckResult("TOTAL_ARITHMETIC_MISMATCH", "INDETERMINATE", "?", outcome="REVIEW")]).status \
        == "NEEDS_REVIEW"
    assert _decide([CheckResult("MANAGER_APPROVAL_REQUIRED", "FAIL", "big", outcome="NONE",
                                severity="INFO")]).status == "READY_FOR_APPROVAL"
    assert _decide([CheckResult("INVOICE_NEAR_DUPLICATE", "FAIL", "similar")]).status == "READY_FOR_APPROVAL"


def test_security_flag_sets_high_priority():
    d = decide([CheckResult("VENDOR_BANK_DETAILS_CHANGED", "FAIL", "bank")], match_mode=None, po_number=None,
               vendor_name="V", grand_total=None, currency=None, requires_manager=False, security=True)
    assert d.status == "NEEDS_REVIEW" and d.priority == "HIGH"


def _line(n, q, p, s):
    return ExtractedLine(line_number=n, quantity=Decimal(q), unit_price=Decimal(p), line_subtotal=Decimal(s))


def test_arithmetic_reconciles_within_tolerance():
    lines = [_line(1, "10", "5000.00", "50000.00"), _line(2, "2", "250.50", "501.00")]
    checks = arithmetic_checks(lines, Decimal("50501.00"), Decimal("9090.18"), Decimal("59591.18"), Decimal("1.00"),
                               "INR")
    assert all(c.status == "PASS" for c in checks)


def test_arithmetic_detects_grand_total_error_with_exact_delta():
    lines = [_line(1, "10", "5000.00", "50000.00")]
    checks = arithmetic_checks(lines, Decimal("50000.00"), Decimal("9000.00"), Decimal("69000.00"), Decimal("1.00"),
                               "INR")
    bad = [c for c in checks if c.status == "FAIL"]
    assert len(bad) == 1 and bad[0].subject == "grand total" and bad[0].delta == "10,000.00"


def test_arithmetic_detects_line_extension_error():
    checks = arithmetic_checks([_line(1, "3", "100.00", "310.00")], None, None, None, Decimal("1.00"), "INR")
    assert checks[0].status == "FAIL" and checks[0].expected == "300.00"


def test_rounding_tolerance_boundary():
    lines = [_line(1, "1", "100.00", "100.00")]
    at = arithmetic_checks(lines, Decimal("100.00"), Decimal("18.00"), Decimal("119.00"), Decimal("1.00"), "INR")
    over = arithmetic_checks(lines, Decimal("100.00"), Decimal("18.00"), Decimal("119.01"), Decimal("1.00"), "INR")
    assert at[-1].status == "PASS" and over[-1].status == "FAIL"
