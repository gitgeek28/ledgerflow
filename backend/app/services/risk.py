"""Vendor-status, remittance-security, extraction-confidence and date checks."""
from datetime import date, timedelta

from app.db.models import Vendor
from app.services.checks import CheckResult
from app.services.extraction.schema import CRITICAL_FIELDS, ExtractionResult
from app.services.identifiers import is_valid_gstin, mask_tax_id
from app.services.money import fmt
from app.services.policy import PolicySettings

LABEL = {"invoice_number": "Invoice number", "invoice_date": "Invoice date", "grand_total": "Grand total",
         "vendor_name": "Supplier name", "vendor_tax_id": "Supplier GSTIN", "po_number": "PO number"}


def risk_checks(ex: ExtractionResult, vendor: Vendor | None, policy: PolicySettings, today: date,
                bank: dict | None) -> tuple[list[CheckResult], dict]:
    """`bank` holds the invoice's remittance fingerprint/last4/IFSC (full account numbers are never stored)."""
    out: list[CheckResult] = []
    flags = {"security_escalation": False}
    threshold = float(policy.critical_field_confidence)

    for name in CRITICAL_FIELDS:
        f = ex.fields[name]
        if not f.present:
            out.append(CheckResult("CRITICAL_FIELD_MISSING", "FAIL", f"{LABEL[name]} could not be read from the "
                                   "document; it will not be guessed", subject=LABEL[name]))
        elif f.confidence < threshold:
            out.append(CheckResult("LOW_EXTRACTION_CONFIDENCE", "FAIL",
                                   f"{LABEL[name]} '{f.value}' read with confidence {f.confidence:.2f} "
                                   f"({f.method}); please confirm against the document", subject=LABEL[name],
                                   actual=f"{f.confidence:.2f}", expected=f">= {threshold:.2f}",
                                   evidence=f.evidence.model_dump() if f.evidence else {}))
        else:
            out.append(CheckResult("LOW_EXTRACTION_CONFIDENCE", "PASS",
                                   f"{LABEL[name]} confidence {f.confidence:.2f} ({f.method})", subject=LABEL[name],
                                   actual=f"{f.confidence:.2f}", expected=f">= {threshold:.2f}"))
    if not ex.fields["vendor_name"].present and not ex.fields["vendor_tax_id"].present:
        out.append(CheckResult("CRITICAL_FIELD_MISSING", "FAIL", "Neither supplier name nor GSTIN could be read",
                               subject="Supplier identity"))

    tax_id = ex.get("vendor_tax_id")
    if tax_id and not is_valid_gstin(tax_id):
        out.append(CheckResult("TAX_ID_INVALID", "FAIL", f"Printed GSTIN {mask_tax_id(tax_id)} fails the "
                               "format/checksum test", actual=mask_tax_id(tax_id)))

    inv_date, due = ex.date("invoice_date"), ex.date("due_date")
    if inv_date and inv_date > today + timedelta(days=1):
        out.append(CheckResult("DATE_INVALID", "FAIL", f"Invoice date {inv_date} is in the future",
                               actual=str(inv_date), expected=f"<= {today}"))
    if inv_date and due and due < inv_date:
        out.append(CheckResult("DATE_INVALID", "FAIL", f"Due date {due} precedes invoice date {inv_date}",
                               actual=str(due), expected=f">= {inv_date}"))

    if vendor is not None:
        if vendor.approved_status == "APPROVED":
            out.append(CheckResult("VENDOR_NOT_APPROVED", "PASS", f"{vendor.vendor_code} is an approved vendor",
                                   actual="APPROVED"))
        else:
            blocked = vendor.approved_status == "BLOCKED"
            outcome = policy.blocked_vendor_outcome if blocked else "HOLD"
            msg = (f"{vendor.legal_name} is {vendor.approved_status.replace('_', ' ').lower()}"
                   + (f": {vendor.status_reason}" if vendor.status_reason else ""))
            msg += ". Policy: blocked vendors are rejected." if blocked and outcome == "REJECT" else \
                ". Held until onboarding is complete." if not blocked else ""
            out.append(CheckResult("VENDOR_NOT_APPROVED", "FAIL", msg, actual=vendor.approved_status,
                                   expected="APPROVED", outcome=outcome))
        if bank and bank.get("fingerprint"):
            fp, last4, ifsc = bank["fingerprint"], bank["last4"], bank.get("ifsc")
            account_changed = vendor.bank_account_fingerprint and fp != vendor.bank_account_fingerprint
            ifsc_changed = bool(ifsc and vendor.bank_ifsc and ifsc != vendor.bank_ifsc)
            if not vendor.bank_account_fingerprint:
                out.append(CheckResult("VENDOR_BANK_DETAILS_CHANGED", "INDETERMINATE",
                                       "Vendor master has no verified bank details to compare against"))
            elif account_changed or ifsc_changed:
                flags["security_escalation"] = True
                what = " and ".join(x for x, c in (("account", account_changed), ("IFSC", ifsc_changed)) if c)
                out.append(CheckResult(
                    "VENDOR_BANK_DETAILS_CHANGED", "FAIL",
                    f"Remittance {what} differ(s) from the verified vendor master: invoice asks for account ending "
                    f"{last4} (IFSC {ifsc or 'not printed'}); master v{vendor.bank_details_version} is account ending "
                    f"{vendor.bank_account_last4} (IFSC {vendor.bank_ifsc}). Verify by calling the vendor on a known "
                    "number before any payment. Vendor master was NOT changed.",
                    actual=f"••••{last4} / {ifsc or '-'}",
                    expected=f"••••{vendor.bank_account_last4} / {vendor.bank_ifsc}",
                    evidence={"master_version": vendor.bank_details_version}))
            else:
                note = "" if ifsc else " (IFSC not readable; account number matched)"
                out.append(CheckResult("VENDOR_BANK_DETAILS_CHANGED", "PASS",
                                       f"Remittance account ••••{last4} matches verified vendor master "
                                       f"(v{vendor.bank_details_version}){note}"))
        else:
            out.append(CheckResult("VENDOR_BANK_DETAILS_CHANGED", "PASS",
                                   "No remittance details printed; payment will use the verified vendor master"))

    total = ex.decimal("grand_total")
    if total is not None and total > policy.manager_approval_above:
        out.append(CheckResult("MANAGER_APPROVAL_REQUIRED", "FAIL",
                               f"Value {fmt(total)} exceeds {fmt(policy.manager_approval_above)}: approval must be "
                               "given by an AP manager", actual=fmt(total),
                               threshold=fmt(policy.manager_approval_above), outcome="NONE", severity="INFO"))
    return out, flags

