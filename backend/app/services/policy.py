"""Policy settings (versioned) and the reason-code catalogue used by the decision engine."""
from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Policy


class PolicySettings(BaseModel):
    """Illustrative demo AP policy — not universal accounting advice."""
    model_config = ConfigDict(extra="forbid")

    unit_price_variance_pct: Decimal = Field(Decimal("2.00"), ge=0, le=50)
    invoice_total_variance_abs: Decimal = Field(Decimal("500.00"), ge=0, le=1_000_000)
    quantity_variance_pct: Decimal = Field(Decimal("0.00"), ge=0, le=50)
    rounding_tolerance_abs: Decimal = Field(Decimal("1.00"), ge=0, le=100)
    critical_field_confidence: Decimal = Field(Decimal("0.85"), ge=0, le=1)
    po_candidate_min_score: Decimal = Field(Decimal("0.90"), ge=0, le=1)
    po_candidate_min_margin: Decimal = Field(Decimal("0.08"), ge=0, le=1)
    vendor_fuzzy_min_score: Decimal = Field(Decimal("0.90"), ge=0, le=1)
    vendor_fuzzy_min_margin: Decimal = Field(Decimal("0.06"), ge=0, le=1)
    line_match_min_similarity: Decimal = Field(Decimal("0.60"), ge=0, le=1)
    require_grn_for_goods: bool = True
    near_duplicate_window_days: int = Field(45, ge=0, le=365)
    near_duplicate_amount_pct: Decimal = Field(Decimal("1.00"), ge=0, le=20)
    manager_approval_above: Decimal = Field(Decimal("250000.00"), ge=0)
    blocked_vendor_outcome: str = Field("REJECT", pattern="^(REJECT|HOLD)$")


@dataclass(frozen=True)
class ReasonCode:
    code: str
    title: str
    severity: str        # INFO | WARNING | REVIEW | BLOCKER
    outcome: str         # NONE | REVIEW | HOLD | REJECT  — what a FAIL does to the decision
    resolution: str      # ACCEPT (reviewer may accept w/ reason) | CORRECT (fix data, re-run) |
    #                      OVERRIDE (manager-only, audited) | NONE
    description: str


CATALOGUE: dict[str, ReasonCode] = {c.code: c for c in [
    ReasonCode("FILE_INVALID", "File invalid or unreadable", "BLOCKER", "NONE", "NONE",
               "The uploaded file could not be opened as a PDF. This is a technical failure, not a business rejection."),
    ReasonCode("FILE_DUPLICATE", "Exact file already received", "INFO", "NONE", "NONE",
               "Identical bytes (SHA-256) were uploaded before; the submission is linked to the original invoice."),
    ReasonCode("INVOICE_DUPLICATE_SUSPECTED", "Duplicate invoice suspected", "BLOCKER", "HOLD", "OVERRIDE",
               "Same vendor, invoice number, currency and amount as an existing invoice. Held so it cannot be paid twice."),
    ReasonCode("INVOICE_NEAR_DUPLICATE", "Similar invoice exists", "WARNING", "NONE", "ACCEPT",
               "A prior invoice is similar (amount/date/lines) but not conclusively the same. Shown for awareness."),
    ReasonCode("VENDOR_NOT_FOUND", "Vendor not in master data", "BLOCKER", "REVIEW", "CORRECT",
               "No approved-vendor record matched the supplier identity on the invoice."),
    ReasonCode("VENDOR_AMBIGUOUS", "Vendor ambiguous", "BLOCKER", "REVIEW", "CORRECT",
               "More than one vendor record is a plausible match; a person must choose."),
    ReasonCode("VENDOR_NOT_APPROVED", "Vendor not approved", "BLOCKER", "REJECT", "OVERRIDE",
               "The vendor exists but is blocked or still in onboarding; invoices cannot proceed to approval."),
    ReasonCode("VENDOR_BANK_DETAILS_CHANGED", "Remittance details differ from vendor master", "BLOCKER", "REVIEW",
               "OVERRIDE", "Bank details on the invoice do not match the verified vendor master. Possible payment "
               "diversion — verify with the vendor through a known contact before paying. Vendor master is never "
               "updated from an invoice."),
    ReasonCode("TAX_ID_INVALID", "Supplier GSTIN invalid", "REVIEW", "REVIEW", "ACCEPT",
               "The GSTIN printed on the invoice fails the format or checksum test."),
    ReasonCode("CRITICAL_FIELD_MISSING", "Critical field missing", "BLOCKER", "REVIEW", "CORRECT",
               "A field required to make a decision (invoice number, date, total, supplier identity) could not be read."),
    ReasonCode("LOW_EXTRACTION_CONFIDENCE", "Low extraction confidence", "REVIEW", "REVIEW", "CORRECT",
               "A critical field was read below the configured confidence threshold; a person should confirm it."),
    ReasonCode("PO_NOT_FOUND", "Purchase order not found", "BLOCKER", "REVIEW", "CORRECT",
               "The referenced PO does not exist for this vendor, or no eligible PO could be identified."),
    ReasonCode("PO_AMBIGUOUS", "Purchase order ambiguous", "BLOCKER", "REVIEW", "CORRECT",
               "Several open POs are plausible and the ranking margin is too small to auto-select."),
    ReasonCode("PO_CLOSED", "Purchase order closed", "BLOCKER", "REVIEW", "OVERRIDE",
               "The matched PO is closed or cancelled."),
    ReasonCode("PO_VENDOR_MISMATCH", "PO belongs to a different vendor", "BLOCKER", "REVIEW", "CORRECT",
               "The referenced PO exists but is issued to a different vendor."),
    ReasonCode("CURRENCY_MISMATCH", "Currency mismatch", "BLOCKER", "REVIEW", "OVERRIDE",
               "Invoice currency differs from PO currency. No FX conversion is performed."),
    ReasonCode("LINE_ITEM_UNMATCHED", "Line item not on PO", "REVIEW", "REVIEW", "ACCEPT",
               "An invoice line could not be matched one-to-one to a PO line."),
    ReasonCode("PRICE_VARIANCE_EXCEEDED", "Unit price variance above tolerance", "REVIEW", "REVIEW", "ACCEPT",
               "Invoiced unit price exceeds the PO price by more than the configured tolerance."),
    ReasonCode("AMOUNT_VARIANCE_EXCEEDED", "Invoice amount variance above tolerance", "REVIEW", "REVIEW", "ACCEPT",
               "Invoice subtotal differs from the PO-priced value of the invoiced quantities by more than tolerance."),
    ReasonCode("TAX_MISMATCH", "Tax mismatch", "REVIEW", "REVIEW", "ACCEPT",
               "Tax rate or tax amount differs from the PO or from the invoice's own line arithmetic."),
    ReasonCode("TOTAL_ARITHMETIC_MISMATCH", "Totals do not add up", "BLOCKER", "REVIEW", "CORRECT",
               "Line amounts, subtotal, tax and grand total on the invoice do not reconcile. Request a corrected invoice."),
    ReasonCode("QUANTITY_EXCEEDED", "Quantity exceeds PO remaining", "BLOCKER", "REVIEW", "OVERRIDE",
               "Cumulative invoiced quantity would exceed the quantity ordered on the PO line."),
    ReasonCode("GRN_QUANTITY_MISMATCH", "Invoiced more than received", "BLOCKER", "REVIEW", "OVERRIDE",
               "Cumulative invoiced quantity exceeds the quantity received on goods receipts (three-way match)."),
    ReasonCode("GRN_PENDING", "Goods receipt pending", "REVIEW", "HOLD", "NONE",
               "Goods PO with no goods receipt recorded yet. Held until receipt is posted."),
    ReasonCode("PO_BALANCE_EXCEEDED", "PO value exhausted", "BLOCKER", "REVIEW", "OVERRIDE",
               "Cumulative invoiced value would exceed the PO value plus tolerance."),
    ReasonCode("PO_EXPIRED", "PO validity lapsed", "WARNING", "NONE", "ACCEPT",
               "The invoice is dated after the PO's validity date."),
    ReasonCode("DATE_INVALID", "Invoice date implausible", "REVIEW", "REVIEW", "CORRECT",
               "The invoice date is in the future or the due date precedes the invoice date."),
    ReasonCode("MANUAL_REVIEW_REQUIRED", "Manual review required", "REVIEW", "REVIEW", "ACCEPT",
               "A reviewer has requested manual review."),
    ReasonCode("MANAGER_APPROVAL_REQUIRED", "Manager approval required", "INFO", "NONE", "NONE",
               "Invoice value exceeds the threshold that requires AP manager approval."),
]}


def load_active_policy(db: Session) -> tuple[Policy, PolicySettings]:
    policy = db.scalar(select(Policy).where(Policy.is_active.is_(True)).order_by(Policy.version.desc()))
    if policy is None:
        raise RuntimeError("No active policy configured; run the seed command")
    return policy, PolicySettings.model_validate(policy.settings)


def settings_to_json(settings: PolicySettings) -> dict:
    return settings.model_dump(mode="json")
