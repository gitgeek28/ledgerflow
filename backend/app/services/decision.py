"""Decision matrix. No weighted score: the most severe outcome among failing checks decides.

    REJECT  > HOLD  > REVIEW  > (none) = READY_FOR_APPROVAL
"""
from dataclasses import dataclass

from app.services.checks import CheckResult
from app.services.money import fmt
from app.services.policy import CATALOGUE

ORDER = {"REJECT": 3, "HOLD": 2, "REVIEW": 1, "NONE": 0}
STATUS = {"REJECT": "REJECTED", "HOLD": "ON_HOLD", "REVIEW": "NEEDS_REVIEW", "NONE": "READY_FOR_APPROVAL"}
HIGH_PRIORITY = {"VENDOR_BANK_DETAILS_CHANGED", "INVOICE_DUPLICATE_SUSPECTED"}

NEXT_ACTION = {
    "VENDOR_BANK_DETAILS_CHANGED": "Verify the remittance change with the vendor via a known contact (not the "
                                   "invoice) before any payment",
    "INVOICE_DUPLICATE_SUSPECTED": "Compare with the original invoice; reject as duplicate or override with reason",
    "VENDOR_NOT_APPROVED": "Vendor must complete onboarding / be unblocked by procurement",
    "GRN_PENDING": "Wait for the goods receipt to be posted; the invoice will be re-checked",
    "PO_AMBIGUOUS": "Select the correct purchase order from the ranked candidates",
    "PO_NOT_FOUND": "Identify the purchase order or request it from the requester",
    "PO_VENDOR_MISMATCH": "Confirm the PO number with the vendor",
    "VENDOR_AMBIGUOUS": "Select the correct vendor record",
    "VENDOR_NOT_FOUND": "Identify the vendor or start onboarding",
    "CRITICAL_FIELD_MISSING": "Enter the missing field from the document or request a corrected invoice",
    "LOW_EXTRACTION_CONFIDENCE": "Confirm or correct the low-confidence fields against the document",
    "TOTAL_ARITHMETIC_MISMATCH": "Request a corrected invoice from the vendor",
    "PRICE_VARIANCE_EXCEEDED": "Confirm the price with the buyer: accept the variance with a reason, or request "
                               "a credit note",
    "AMOUNT_VARIANCE_EXCEEDED": "Confirm the amount difference with the buyer",
    "QUANTITY_EXCEEDED": "Ask the vendor for a corrected invoice or get a PO amendment",
    "GRN_QUANTITY_MISMATCH": "Check with stores whether the remaining goods were received",
    "PO_BALANCE_EXCEEDED": "Request a PO amendment or a corrected invoice",
    "TAX_MISMATCH": "Check the GST rate with tax/procurement",
    "LINE_ITEM_UNMATCHED": "Match the line to a PO line or ask the vendor to itemise",
    "CURRENCY_MISMATCH": "Confirm the billing currency with the vendor",
    "PO_CLOSED": "Ask procurement whether the PO can be reopened",
    "DATE_INVALID": "Confirm the invoice date",
    "TAX_ID_INVALID": "Confirm the supplier's GSTIN",
}


@dataclass
class Decision:
    status: str
    reason_codes: list[str]
    priority: str
    summary: str
    next_action: str


def decide(checks: list[CheckResult], *, match_mode: str | None, po_number: str | None, vendor_name: str | None,
           grand_total, currency: str | None, requires_manager: bool, security: bool) -> Decision:
    failing = [c for c in checks if c.failing]
    worst = max((c.outcome for c in failing), key=lambda o: ORDER[o], default="NONE")
    status = STATUS[worst]
    ordered = sorted(failing, key=lambda c: (-ORDER[c.outcome], c.code))
    codes = list(dict.fromkeys(c.code for c in ordered))
    priority = "HIGH" if (security or HIGH_PRIORITY & set(codes)) else ("NORMAL" if failing else "LOW")
    mode = {"THREE_WAY": "three-way match (invoice / PO / goods receipt)", "TWO_WAY": "two-way match (invoice / PO)"}
    value = fmt(grand_total, currency) if grand_total is not None else "unknown value"
    if status == "READY_FOR_APPROVAL":
        passed = sum(1 for c in checks if c.status == "PASS")
        summary = (f"Ready for approval. {vendor_name or 'Vendor'} invoice for {value} passed {passed} checks with a "
                   f"{mode.get(match_mode, 'match')} against {po_number}. No exceptions.")
        if requires_manager:
            summary += " Value is above the manager-approval threshold: an AP manager must approve."
        next_action = "AP manager approval" if requires_manager else "Approve for payment run"
    else:
        lead = {"REJECTED": "Rejected", "ON_HOLD": "On hold", "NEEDS_REVIEW": "Needs review"}[status]
        reasons = [f"{CATALOGUE[c.code].title if c.code in CATALOGUE else c.code} ({c.message.rstrip('.')})"
                   for c in ordered[:3]]
        summary = f"{lead}: " + "; ".join(reasons) + "."
        if len(ordered) > 3:
            summary += f" Plus {len(ordered) - 3} more exception(s)."
        summary += " Not payable until resolved." if status != "REJECTED" else " No payment will be made."
        next_action = NEXT_ACTION.get(ordered[0].code, "Review the exceptions")
    return Decision(status, codes, priority, summary, next_action)
