"""ORM -> API model conversion with masking and derived figures."""
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    GoodsReceipt,
    Invoice,
    InvoiceNote,
    POLineConsumption,
    ProcessingRun,
    PurchaseOrder,
    User,
    Vendor,
)
from app.schemas import api
from app.services.identifiers import mask_tax_id
from app.services.policy import CATALOGUE
from app.services.review import latest_checks


def vendor_ref(v: Vendor | None) -> api.VendorRef | None:
    return api.VendorRef.model_validate(v) if v else None


def user_out(u: User | None) -> api.UserOut | None:
    return api.UserOut.model_validate(u) if u else None


def vendor_out(db: Session, v: Vendor) -> api.VendorOut:
    open_pos = db.scalar(select(func.count()).select_from(PurchaseOrder)
                         .where(PurchaseOrder.vendor_id == v.id, PurchaseOrder.status == "OPEN")) or 0
    inv_count = db.scalar(select(func.count()).select_from(Invoice).where(Invoice.vendor_id == v.id)) or 0
    open_value = db.scalar(select(func.coalesce(func.sum(Invoice.grand_total), 0)).where(
        Invoice.vendor_id == v.id, Invoice.status.in_(["NEEDS_REVIEW", "ON_HOLD", "READY_FOR_APPROVAL"]))) or 0
    data = {c: getattr(v, c) for c in api.VendorOut.model_fields if hasattr(v, c)}
    data.update(tax_id_masked=mask_tax_id(v.tax_id), open_po_count=open_pos, invoice_count=inv_count,
                open_invoice_value=Decimal(open_value))
    return api.VendorOut(**data)


def po_figures(db: Session, po: PurchaseOrder) -> tuple[Decimal, int]:
    invoiced = db.scalar(select(func.coalesce(func.sum(POLineConsumption.amount), 0)).where(
        POLineConsumption.po_id == po.id, POLineConsumption.status.in_(["RESERVED", "APPROVED"]))) or 0
    grns = db.scalar(select(func.count()).select_from(GoodsReceipt).where(GoodsReceipt.po_id == po.id)) or 0
    return Decimal(invoiced), grns


def po_out(db: Session, po: PurchaseOrder) -> api.POOut:
    invoiced, grns = po_figures(db, po)
    data = {c: getattr(po, c) for c in api.POOut.model_fields if hasattr(po, c) and c != "vendor"}
    return api.POOut(**data, vendor=vendor_ref(po.vendor), invoiced_value=invoiced,
                     remaining_value=po.subtotal - invoiced, grn_count=grns)


def invoice_item(inv: Invoice) -> api.InvoiceListItem:
    data = {c: getattr(inv, c) for c in api.InvoiceListItem.model_fields
            if hasattr(inv, c) and c not in ("vendor", "assignee")}
    age = (datetime.now(UTC) - inv.created_at).total_seconds() / 3600
    return api.InvoiceListItem(**data, vendor=vendor_ref(inv.vendor), assignee=user_out(inv.assignee),
                               po_number=inv.po.po_number if inv.po else None, age_hours=round(age, 1))


def run_out(db: Session, run: ProcessingRun, detail: bool = False, invoice: Invoice | None = None):
    inv = invoice or db.get(Invoice, run.invoice_id)
    by = db.get(User, run.triggered_by_id) if run.triggered_by_id else None
    data = {c: getattr(run, c) for c in api.RunDetail.model_fields if hasattr(run, c)}
    data.update(invoice_reference=inv.reference if inv else None,
                invoice_filename=inv.original_filename if inv else None,
                vendor_name=(inv.vendor.legal_name if inv and inv.vendor else (inv.vendor_name_raw if inv else None)),
                triggered_by=by.name if by else "System")
    if detail:
        return api.RunDetail(**data)
    data.pop("stage_outputs", None)
    return api.RunOut(**data)


def invoice_detail(db: Session, inv: Invoice, user: User) -> api.InvoiceDetail:
    base = invoice_item(inv).model_dump()
    checks = []
    for c in latest_checks(db, inv):
        co = api.CheckOut.model_validate(c)
        co.resolution = CATALOGUE[c.code].resolution if c.code in CATALOGUE else None
        checks.append(co)
    runs = db.scalars(select(ProcessingRun).where(ProcessingRun.invoice_id == inv.id)
                      .order_by(ProcessingRun.attempt.desc())).all()
    latest = next((r for r in runs if r.id == inv.latest_run_id), runs[0] if runs else None)
    notes = db.scalars(select(InvoiceNote).where(InvoiceNote.invoice_id == inv.id)
                       .order_by(InvoiceNote.created_at.desc())).all()
    dup = db.get(Invoice, inv.duplicate_of_id) if inv.duplicate_of_id else None
    uploader = db.get(User, inv.uploaded_by_id) if inv.uploaded_by_id else None
    dup_subs = db.scalars(select(AuditEvent).where(AuditEvent.invoice_id == inv.id,
                                                   AuditEvent.action == "FILE_DUPLICATE_RECEIVED")
                          .order_by(AuditEvent.occurred_at.desc())).all()
    operator = user.role in ("AP_ANALYST", "AP_MANAGER")
    return api.InvoiceDetail(
        **base, file_size=inv.file_size, page_count=inv.page_count, file_sha256=inv.file_sha256,
        subtotal=inv.subtotal, tax_total=inv.tax_total, po_reference_raw=inv.po_reference_raw, po_id=inv.po_id,
        vendor_tax_id_masked=mask_tax_id(inv.vendor_tax_id_raw), bank_account_last4=inv.bank_account_last4,
        decision_summary=inv.decision_summary, extraction=inv.extraction, extraction_method=inv.extraction_method,
        field_overrides=inv.field_overrides or {}, accepted_exceptions=inv.accepted_exceptions or {},
        po_selected_by_human=inv.po_selected_by_human,
        duplicate_of={"id": str(dup.id), "reference": dup.reference, "status": dup.status} if dup else None,
        info_request_draft=inv.info_request_draft, document_text=inv.document_text,
        lines=[api.InvoiceLineOut.model_validate(ln) for ln in inv.lines], checks=checks,
        latest_run=run_out(db, latest, detail=True, invoice=inv) if latest else None,
        runs=[run_out(db, r, invoice=inv) for r in runs],
        notes=[api.NoteOut(id=n.id, body=n.body, created_at=n.created_at, author=user_out(n.author)) for n in notes],
        uploaded_by=uploader.name if uploader else None,
        duplicate_submissions=[{"at": e.occurred_at.isoformat(), "by": e.actor_name,
                                "filename": (e.after or {}).get("filename")} for e in dup_subs],
        permissions={"can_act": operator, "is_manager": user.role == "AP_MANAGER"})
