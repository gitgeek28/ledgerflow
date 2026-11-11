"""Human-in-the-loop review actions. Every action: permission + transition check -> persist -> audit ->
(where data changed) re-run the deterministic stages from vendor resolution as a new, visible run."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, Forbidden, InvalidTransition, NotFound
from app.db.base import utcnow
from app.db.models import Invoice, InvoiceCheck, ProcessingRun, PurchaseOrder, User, Vendor
from app.services import audit
from app.services.extraction.rules import parse_currency, parse_gstin, parse_invoice_number, parse_po
from app.services.ingestion import create_run
from app.services.money import fmt
from app.services.po_ledger import release_reservations
from app.services.policy import CATALOGUE
from app.services.reservation import mark_consumed, reserve

EDITABLE_FIELDS = {"invoice_number", "invoice_date", "due_date", "po_number", "currency", "subtotal", "tax_total",
                   "grand_total", "vendor_name", "vendor_tax_id"}
OPEN_STATES = {"NEEDS_REVIEW", "ON_HOLD", "READY_FOR_APPROVAL"}
ALLOWED_FROM = {
    "CORRECT_FIELD": OPEN_STATES, "CONFIRM_FIELD": OPEN_STATES, "MARK_UNREADABLE": OPEN_STATES,
    "SELECT_PO": OPEN_STATES, "SELECT_VENDOR": OPEN_STATES, "RE_EVALUATE": OPEN_STATES,
    "REQUEST_INFO": {"NEEDS_REVIEW", "ON_HOLD"}, "HOLD": {"NEEDS_REVIEW", "READY_FOR_APPROVAL"},
    "REJECT": OPEN_STATES, "MARK_READY": {"NEEDS_REVIEW", "ON_HOLD"}, "APPROVE": {"READY_FOR_APPROVAL"},
    "CANCEL": OPEN_STATES | {"FAILED"},
}
MANAGER_ONLY = {"CANCEL"}
REASON_REQUIRED = {"HOLD", "REJECT", "MARK_UNREADABLE", "CANCEL"}

INFO_REQUESTS = {
    "CRITICAL_FIELD_MISSING": "a legible copy showing the {subject}",
    "LOW_EXTRACTION_CONFIDENCE": "a clearer copy of the invoice (the {subject} is hard to read on the scan)",
    "TOTAL_ARITHMETIC_MISMATCH": "a corrected invoice: the line amounts, tax and grand total do not add up "
                                 "({message})",
    "PO_NOT_FOUND": "the purchase order number this invoice relates to",
    "PO_AMBIGUOUS": "the purchase order number this invoice relates to (we have more than one open order "
                    "for these items)",
    "PRICE_VARIANCE_EXCEEDED": "confirmation of the unit price, which differs from the agreed purchase order "
                               "price ({message})",
    "QUANTITY_EXCEEDED": "a corrected invoice or credit note: the quantity billed exceeds the ordered quantity "
                         "remaining ({message})",
    "GRN_QUANTITY_MISMATCH": "delivery evidence (signed delivery challan) for the quantity billed beyond what we "
                             "have received",
    "TAX_MISMATCH": "confirmation of the GST rate applied ({message})",
    "VENDOR_BANK_DETAILS_CHANGED": "nothing by email regarding bank details. Our team will call your registered "
                                   "contact to verify the change of remittance account; please do not send bank "
                                   "details in reply to this message",
    "TAX_ID_INVALID": "your correct GSTIN",
    "DATE_INVALID": "confirmation of the invoice date",
    "LINE_ITEM_UNMATCHED": "an itemised breakdown that matches the purchase order lines",
}


@dataclass
class ActionResult:
    invoice: Invoice
    run: ProcessingRun | None = None
    draft: str | None = None
    message: str = ""


def latest_checks(db: Session, invoice: Invoice) -> list[InvoiceCheck]:
    if not invoice.latest_run_id:
        return []
    return list(db.scalars(select(InvoiceCheck).where(InvoiceCheck.run_id == invoice.latest_run_id)
                           .order_by(InvoiceCheck.id)))


def _validate_value(field: str, value: str | None) -> str:
    if value is None or not str(value).strip():
        raise AppError("A value is required.", code="VALIDATION_ERROR", status_code=422)
    v = str(value).strip()
    try:
        if field in ("invoice_date", "due_date"):
            return date.fromisoformat(v).isoformat()
        if field in ("subtotal", "tax_total", "grand_total"):
            d = Decimal(v.replace(",", ""))
            if d < 0 or d.as_tuple().exponent < -2:
                raise InvalidOperation
            return str(d.quantize(Decimal("0.01")))
    except (ValueError, InvalidOperation) as exc:
        raise AppError(f"'{v}' is not a valid value for {field}.", code="VALIDATION_ERROR", status_code=422) from exc
    parsers = {"invoice_number": parse_invoice_number, "po_number": parse_po, "currency": parse_currency,
               "vendor_tax_id": parse_gstin}
    if field in parsers:
        parsed = parsers[field](v)
        if not parsed:
            raise AppError(f"'{v}' is not a valid {field.replace('_', ' ')}.", code="VALIDATION_ERROR",
                           status_code=422)
        return parsed[0]
    return v[:200]


def _reevaluate(db: Session, invoice: Invoice, user: User) -> ProcessingRun:
    previous = db.get(ProcessingRun, invoice.latest_run_id) if invoice.latest_run_id else None
    return create_run(db, invoice, trigger="REEVALUATION", start_stage="VENDOR_RESOLUTION", user=user,
                      previous=previous)


def draft_info_request(db: Session, invoice: Invoice, user: User) -> str:
    vendor = db.get(Vendor, invoice.vendor_id) if invoice.vendor_id else None
    asks = []
    for c in latest_checks(db, invoice):
        if not (c.status != "PASS" and c.outcome != "NONE") or c.code not in INFO_REQUESTS:
            continue
        ask = INFO_REQUESTS[c.code].format(subject=(c.subject or "field").lower(), message=c.message.rstrip("."))
        if ask not in asks:
            asks.append(ask)
    if not asks:
        asks.append("confirmation of the invoice details")
    when = invoice.invoice_date.strftime("%d %b %Y") if invoice.invoice_date else "(date unreadable)"
    amount = fmt(invoice.grand_total, invoice.currency) if invoice.grand_total is not None else "(amount unreadable)"
    bullets = "\n".join(f"  - {a}" for a in asks)
    return (
        f"DRAFT - NOT SENT. Review before sending from your mail client.\n\n"
        f"To: {vendor.contact_email if vendor and vendor.contact_email else '(vendor contact)'}\n"
        f"Subject: Invoice {invoice.invoice_number or invoice.original_filename} - information needed "
        f"(our ref {invoice.reference})\n\n"
        f"Dear {vendor.display_name if vendor else 'Supplier'} accounts team,\n\n"
        f"Thank you for invoice {invoice.invoice_number or '(number unreadable)'} dated {when} for {amount}. "
        f"Before we can process it for payment we need:\n{bullets}\n\n"
        f"Please reply to this email quoting our reference {invoice.reference}, or send a corrected invoice to "
        f"ap@kestrel.example. Payment terms start from receipt of a complete invoice.\n\n"
        f"Regards,\n{user.name}\nAccounts Payable, Kestrel Components Pvt Ltd")


def perform(db: Session, invoice_id, user: User, action: str, *, reason: str | None = None, note: str | None = None,
            field: str | None = None, value: str | None = None, po_id=None, vendor_id=None) -> ActionResult:
    invoice = db.execute(select(Invoice).where(Invoice.id == invoice_id).with_for_update()).scalar_one_or_none()
    if invoice is None:
        raise NotFound("Invoice not found.")
    if user.role == "AUDITOR":
        raise Forbidden("Auditors have read-only access.")
    if action not in ALLOWED_FROM:
        raise AppError(f"Unknown action {action}.", code="VALIDATION_ERROR", status_code=422)
    if invoice.status == "PROCESSING":
        raise InvalidTransition("The invoice is being processed; wait for the run to finish.")
    if invoice.status not in ALLOWED_FROM[action]:
        raise InvalidTransition(f"{action.replace('_', ' ').title()} is not allowed while the invoice is "
                                f"{invoice.status.replace('_', ' ').lower()}.")
    if action in MANAGER_ONLY and user.role != "AP_MANAGER":
        raise Forbidden("Only an AP manager can do this.")
    reason = (reason or "").strip() or None
    if action in REASON_REQUIRED and not reason:
        raise AppError("A reason is required for this action.", code="REASON_REQUIRED", status_code=422)

    before = {"status": invoice.status}
    stamp = {"by": user.name, "by_id": str(user.id), "at": utcnow().isoformat(), "reason": reason}
    result = ActionResult(invoice)

    if action in ("CORRECT_FIELD", "CONFIRM_FIELD", "MARK_UNREADABLE"):
        if field not in EDITABLE_FIELDS:
            raise AppError("This field cannot be edited.", code="VALIDATION_ERROR", status_code=422)
        overrides = dict(invoice.field_overrides or {})
        current = (invoice.extraction or {}).get("fields", {}).get(field, {}).get("value")
        prior = overrides.get(field, {}).get("value", current)
        if action == "CONFIRM_FIELD":
            if current is None and field not in overrides:
                raise AppError("There is no extracted value to confirm; enter a correction instead.",
                               code="VALIDATION_ERROR", status_code=422)
            overrides[field] = {**stamp, "value": overrides.get(field, {}).get("value", current), "confirmed": True}
        elif action == "CORRECT_FIELD":
            overrides[field] = {**stamp, "value": _validate_value(field, value)}
        else:
            overrides[field] = {**stamp, "value": None, "unreadable": True}
        invoice.field_overrides = overrides
        before.update({"field": field, "value": prior})
        after = {"field": field, "value": overrides[field].get("value"), "unreadable": action == "MARK_UNREADABLE"}
        result.run = _reevaluate(db, invoice, user)
        audit.record(db, action=action, actor=user, invoice=invoice, run_id=result.run.id, note=reason or note,
                     before=before, after=after)
    elif action == "SELECT_PO":
        po = db.get(PurchaseOrder, po_id) if po_id else None
        if po is None:
            raise NotFound("Purchase order not found.")
        if invoice.vendor_id and po.vendor_id != invoice.vendor_id:
            raise AppError("That purchase order belongs to a different vendor.", code="VALIDATION_ERROR",
                           status_code=422)
        before["po"] = invoice.po.po_number if invoice.po else None
        invoice.po_id, invoice.po_selected_by_human = po.id, True
        result.run = _reevaluate(db, invoice, user)
        audit.record(db, action=action, actor=user, invoice=invoice, run_id=result.run.id, note=reason or note,
                     before=before, after={"po": po.po_number})
    elif action == "SELECT_VENDOR":
        vendor = db.get(Vendor, vendor_id) if vendor_id else None
        if vendor is None:
            raise NotFound("Vendor not found.")
        overrides = dict(invoice.field_overrides or {})
        overrides["vendor_id"] = {**stamp, "value": str(vendor.id)}
        invoice.field_overrides = overrides
        result.run = _reevaluate(db, invoice, user)
        audit.record(db, action=action, actor=user, invoice=invoice, run_id=result.run.id, note=reason or note,
                     before=before, after={"vendor": vendor.vendor_code})
    elif action == "RE_EVALUATE":
        result.run = _reevaluate(db, invoice, user)
        audit.record(db, action=action, actor=user, invoice=invoice, run_id=result.run.id, note=reason or note,
                     before=before)
    elif action == "REQUEST_INFO":
        result.draft = draft_info_request(db, invoice, user)
        invoice.info_request_draft = result.draft
        invoice.status = "ON_HOLD"
        invoice.next_action = "Awaiting vendor response to information request (draft prepared, not sent)"
        audit.record(db, action=action, actor=user, invoice=invoice, note=reason or note, before=before,
                     after={"status": "ON_HOLD", "draft_prepared": True})
    elif action == "HOLD":
        invoice.status = "ON_HOLD"
        invoice.next_action = f"On hold: {reason}"
        release_reservations(db, invoice.id)
        audit.record(db, action=action, actor=user, invoice=invoice, note=reason, before=before,
                     after={"status": "ON_HOLD"})
    elif action in ("REJECT", "CANCEL"):
        status = "REJECTED" if action == "REJECT" else "CANCELLED"
        invoice.status = status
        invoice.decided_by, invoice.decided_at = "HUMAN", utcnow()
        invoice.next_action = None
        invoice.decision_summary = f"{status.title()} by {user.name}: {reason}"
        release_reservations(db, invoice.id)
        audit.record(db, action=action, actor=user, invoice=invoice, note=reason, before=before,
                     after={"status": status})
    elif action == "MARK_READY":
        result.message = _mark_ready(db, invoice, user, reason, before)
    elif action == "APPROVE":
        _approve(db, invoice, user, reason, before)
    db.commit()
    return result


def _mark_ready(db: Session, invoice: Invoice, user: User, reason: str | None, before: dict) -> str:
    failing = [c for c in latest_checks(db, invoice) if c.status != "PASS" and c.outcome != "NONE"]
    must_fix = [c for c in failing if CATALOGUE.get(c.code) and CATALOGUE[c.code].resolution in ("CORRECT", "NONE")]
    if must_fix:
        codes = ", ".join(dict.fromkeys(c.code for c in must_fix))
        raise InvalidTransition(f"Cannot mark ready: {codes} must be resolved by correcting data, selecting a PO/vendor "
                                "or waiting for the dependency; it cannot be accepted.")
    overrides = [c for c in failing if CATALOGUE.get(c.code) and CATALOGUE[c.code].resolution == "OVERRIDE"]
    if overrides and user.role != "AP_MANAGER":
        codes = ", ".join(dict.fromkeys(c.code for c in overrides))
        raise Forbidden(f"{codes} can only be overridden by an AP manager.")
    if failing and not reason:
        raise AppError("A reason is required to accept these exceptions.", code="REASON_REQUIRED", status_code=422)
    violations = reserve(db, invoice, allow_over=bool(overrides))
    if violations and not overrides:
        raise InvalidTransition("PO balance is no longer available: " + "; ".join(violations))
    for c in failing:
        c.accepted = True
    invoice.status = "READY_FOR_APPROVAL"
    invoice.decided_by, invoice.decided_at = "HUMAN", utcnow()
    invoice.accepted_exceptions = {**(invoice.accepted_exceptions or {}), "marked_ready_by": str(user.id),
                                   "codes": [c.code for c in failing], "reason": reason,
                                   "override": bool(overrides)}
    invoice.next_action = "Approval by a second person"
    accepted = ", ".join(dict.fromkeys(c.code for c in failing)) or "none"
    invoice.decision_summary = (f"Marked ready for approval by {user.name}" +
                                (f" accepting {accepted}: {reason}" if failing else "") + ".")
    audit.record(db, action="OVERRIDE_AND_MARK_READY" if overrides else "MARK_READY", actor=user, invoice=invoice,
                 note=reason, reason_code=failing[0].code if failing else None, before=before,
                 after={"status": "READY_FOR_APPROVAL", "accepted_codes": [c.code for c in failing],
                        "manager_override": bool(overrides)})
    return accepted


def _approve(db: Session, invoice: Invoice, user: User, reason: str | None, before: dict) -> None:
    needs_manager = any(c.code == "MANAGER_APPROVAL_REQUIRED" for c in latest_checks(db, invoice))
    if needs_manager and user.role != "AP_MANAGER":
        raise Forbidden("This invoice exceeds the manager-approval threshold; an AP manager must approve it.")
    if (invoice.accepted_exceptions or {}).get("marked_ready_by") == str(user.id):
        raise Forbidden("Separation of duties: the person who accepted the exceptions cannot also approve.")
    if invoice.po_id:
        violations = reserve(db, invoice, allow_over=(invoice.accepted_exceptions or {}).get("override", False))
        if violations and not (invoice.accepted_exceptions or {}).get("override"):
            raise InvalidTransition("PO balance is no longer available: " + "; ".join(violations))
    mark_consumed(db, invoice)
    invoice.status = "APPROVED"
    invoice.decided_by, invoice.decided_at = "HUMAN", utcnow()
    invoice.next_action = "Include in the next payment run (outside LedgerFlow)"
    invoice.decision_summary = (f"Approved by {user.name}. " + (invoice.decision_summary or "")).strip()
    audit.record(db, action="APPROVE", actor=user, invoice=invoice, note=reason, before=before,
                 after={"status": "APPROVED", "note": "Approval only; LedgerFlow does not execute payments"})
