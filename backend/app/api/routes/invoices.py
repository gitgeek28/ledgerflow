import csv
import io
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Paging
from app.api.serializers import invoice_detail, invoice_item
from app.core.config import get_settings
from app.core.errors import AppError, NotFound
from app.core.security import OPERATOR, current_user
from app.db.models import AuditEvent, IntakeBatch, Invoice, InvoiceNote, PurchaseOrder, RunEvent, User, Vendor
from app.db.session import get_db
from app.schemas import api
from app.services import audit
from app.services.ingestion import ingest
from app.services.reporting import decision_report_html
from app.services.review import latest_checks, perform
from app.services.storage import get_storage

router = APIRouter(prefix="/invoices", tags=["invoices"])

SORTS = {"created_at": Invoice.created_at, "invoice_date": Invoice.invoice_date, "grand_total": Invoice.grand_total,
         "status": Invoice.status, "reference": Invoice.reference, "priority": Invoice.priority}


def _get(db: Session, invoice_id: uuid.UUID) -> Invoice:
    inv = db.scalar(select(Invoice).options(selectinload(Invoice.lines), selectinload(Invoice.vendor),
                                            selectinload(Invoice.po), selectinload(Invoice.assignee))
                    .where(Invoice.id == invoice_id))
    if not inv:
        raise NotFound("Invoice not found.")
    return inv


def _upload_one(db: Session, f: UploadFile, data: bytes, user: User, batch_id=None) -> api.UploadResult:
    try:
        r = ingest(db, filename=f.filename, content_type=f.content_type, data=data, user=user, batch_id=batch_id)
    except AppError as exc:
        db.rollback()
        return api.UploadResult(filename=f.filename or "file", outcome="REJECTED", message=exc.message,
                                error_code=exc.code)
    if r.duplicate:
        return api.UploadResult(filename=f.filename or "file", outcome="DUPLICATE_FILE", invoice_id=r.invoice.id,
                                reference=r.invoice.reference,
                                message=f"Identical file already received as {r.invoice.reference} "
                                        f"({r.invoice.status.replace('_', ' ').lower()}). No new invoice was created.")
    return api.UploadResult(filename=f.filename or "file", outcome="CREATED", invoice_id=r.invoice.id,
                            reference=r.invoice.reference, run_id=r.run.id,
                            message=f"Received as {r.invoice.reference}; processing started.")


async def _read_limited(f: UploadFile) -> bytes:
    limit = get_settings().max_upload_bytes
    data = await f.read(limit + 1)
    if len(data) > limit:
        raise AppError(f"{f.filename}: file exceeds the {get_settings().max_upload_mb} MB limit.",
                       code="FILE_INVALID", status_code=413)
    return data


@router.post("", response_model=api.UploadResult, status_code=201)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(OPERATOR)):
    data = await _read_limited(file)
    result = _upload_one(db, file, data, user)
    if result.outcome == "REJECTED":
        raise AppError(result.message, code=result.error_code or "FILE_INVALID", status_code=422)
    return result


@router.post("/batch", response_model=api.BatchResult, status_code=201)
async def upload_batch(files: list[UploadFile] = File(...), db: Session = Depends(get_db),
                       user: User = Depends(OPERATOR)):
    if not files or len(files) > 25:
        raise AppError("Upload between 1 and 25 files per batch.", code="VALIDATION_ERROR", status_code=422)
    batch = IntakeBatch(created_by_id=user.id, file_count=len(files), results=[])
    db.add(batch)
    db.commit()
    results = []
    for f in files:
        try:
            data = await _read_limited(f)
            results.append(_upload_one(db, f, data, user, batch.id))
        except AppError as exc:
            results.append(api.UploadResult(filename=f.filename or "file", outcome="REJECTED", message=exc.message,
                                            error_code=exc.code))
    batch = db.get(IntakeBatch, batch.id)
    batch.results = [r.model_dump(mode="json") for r in results]
    db.commit()
    return api.BatchResult(batch_id=batch.id, results=results)


def _filtered(q, *, search, status, vendor_id, priority, date_from, date_to, min_amount, max_amount, assignee_id):
    if search:
        like = f"%{search.strip()}%"
        q = q.outerjoin(Vendor, Invoice.vendor_id == Vendor.id).outerjoin(
            PurchaseOrder, Invoice.po_id == PurchaseOrder.id).where(or_(
                Invoice.invoice_number.ilike(like), Invoice.reference.ilike(like),
                Invoice.original_filename.ilike(like), Vendor.legal_name.ilike(like),
                Invoice.vendor_name_raw.ilike(like), PurchaseOrder.po_number.ilike(like),
                Invoice.po_reference_raw.ilike(like)))
    if status:
        q = q.where(Invoice.status.in_(status))
    if vendor_id:
        q = q.where(Invoice.vendor_id == vendor_id)
    if priority:
        q = q.where(Invoice.priority == priority)
    if date_from:
        q = q.where(Invoice.invoice_date >= date_from)
    if date_to:
        q = q.where(Invoice.invoice_date <= date_to)
    if min_amount is not None:
        q = q.where(Invoice.grand_total >= min_amount)
    if max_amount is not None:
        q = q.where(Invoice.grand_total <= max_amount)
    if assignee_id:
        q = q.where(Invoice.assignee_id == assignee_id)
    return q


def _list_query(search=None, status=None, vendor_id=None, priority=None, date_from=None, date_to=None,
                min_amount=None, max_amount=None, assignee_id=None):
    q = select(Invoice).options(selectinload(Invoice.vendor), selectinload(Invoice.po), selectinload(Invoice.assignee))
    return _filtered(q, search=search, status=status, vendor_id=vendor_id, priority=priority, date_from=date_from,
                     date_to=date_to, min_amount=min_amount, max_amount=max_amount, assignee_id=assignee_id)


@router.get("", response_model=api.Page[api.InvoiceListItem])
def list_invoices(q: str | None = None, status: list[str] | None = Query(None), vendor_id: uuid.UUID | None = None,
                  priority: str | None = None, date_from: date | None = None, date_to: date | None = None,
                  min_amount: Decimal | None = None, max_amount: Decimal | None = None,
                  assignee_id: uuid.UUID | None = None, sort: str = "created_at",
                  order: str = Query("desc", pattern="^(asc|desc)$"), paging: Paging = Depends(),
                  db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = _list_query(q, status, vendor_id, priority, date_from, date_to, min_amount, max_amount, assignee_id)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    col = SORTS.get(sort, Invoice.created_at)
    query = query.order_by((asc if order == "asc" else desc)(col).nulls_last(), desc(Invoice.created_at))
    rows = db.scalars(query.offset(paging.offset).limit(paging.page_size)).all()
    return api.Page(items=[invoice_item(i) for i in rows], total=total, page=paging.page,
                    page_size=paging.page_size)


@router.get("/export.csv")
def export_csv(q: str | None = None, status: list[str] | None = Query(None), db: Session = Depends(get_db),
               _: User = Depends(current_user)):
    rows = db.scalars(_list_query(q, status).order_by(desc(Invoice.created_at))).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["reference", "received_at", "status", "decided_by", "priority", "vendor_code", "vendor",
                "invoice_number", "invoice_date", "po_number", "match_mode", "currency", "subtotal", "tax_total",
                "grand_total", "reason_codes", "next_action", "decision_summary"])
    for i in rows:
        w.writerow([i.reference, i.created_at.isoformat(), i.status, i.decided_by, i.priority,
                    i.vendor.vendor_code if i.vendor else "", i.vendor.legal_name if i.vendor else i.vendor_name_raw,
                    i.invoice_number, i.invoice_date, i.po.po_number if i.po else i.po_reference_raw, i.match_mode,
                    i.currency, i.subtotal, i.tax_total, i.grand_total, " ".join(i.reason_codes or []),
                    i.next_action, i.decision_summary])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ledgerflow-invoices.csv"})


@router.get("/{invoice_id}", response_model=api.InvoiceDetail)
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return invoice_detail(db, _get(db, invoice_id), user)


@router.get("/{invoice_id}/document")
def get_document(invoice_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)):
    inv = _get(db, invoice_id)
    path = get_storage().path(inv.storage_key)
    if not path.exists():
        raise NotFound("Stored document is missing.")
    safe = inv.original_filename.replace('"', "")
    return FileResponse(path, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{safe}"',
                                 "Cache-Control": "private, max-age=300"})


@router.get("/{invoice_id}/checks", response_model=list[api.CheckOut])
def get_checks(invoice_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [api.CheckOut.model_validate(c) for c in latest_checks(db, _get(db, invoice_id))]


@router.get("/{invoice_id}/audit", response_model=list[api.AuditOut])
def get_audit(invoice_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)):
    _get(db, invoice_id)
    return db.scalars(select(AuditEvent).where(AuditEvent.invoice_id == invoice_id)
                      .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())).all()


@router.get("/{invoice_id}/events", response_model=list[api.RunEventOut])
def get_invoice_events(invoice_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.scalars(select(RunEvent).where(RunEvent.invoice_id == invoice_id).order_by(RunEvent.id)).all()


@router.get("/{invoice_id}/report", response_class=HTMLResponse)
def decision_report(invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(current_user)):
    inv = _get(db, invoice_id)
    return HTMLResponse(decision_report_html(db, inv, user),
                        headers={"Content-Disposition": f'inline; filename="{inv.reference}-decision.html"'})


@router.post("/{invoice_id}/review-actions", response_model=api.ReviewActionOut)
def review_action(invoice_id: uuid.UUID, body: api.ReviewActionIn, db: Session = Depends(get_db),
                  user: User = Depends(OPERATOR)):
    r = perform(db, invoice_id, user, body.action, reason=body.reason, note=body.note, field=body.field,
                value=body.value, po_id=body.po_id, vendor_id=body.vendor_id)
    return api.ReviewActionOut(invoice_id=r.invoice.id, status=r.invoice.status,
                               run_id=r.run.id if r.run else None, draft=r.draft,
                               message=r.message or f"{body.action.replace('_', ' ').title()} recorded")


@router.post("/{invoice_id}/notes", response_model=api.NoteOut, status_code=201)
def add_note(invoice_id: uuid.UUID, body: api.NoteIn, db: Session = Depends(get_db), user: User = Depends(OPERATOR)):
    inv = _get(db, invoice_id)
    note = InvoiceNote(invoice_id=inv.id, author_id=user.id, body=body.body.strip())
    db.add(note)
    audit.record(db, action="NOTE_ADDED", actor=user, invoice=inv, note=body.body.strip()[:500])
    db.commit()
    return api.NoteOut(id=note.id, body=note.body, created_at=note.created_at, author=api.UserOut.model_validate(user))


@router.post("/{invoice_id}/assign", response_model=api.InvoiceListItem)
def assign(invoice_id: uuid.UUID, body: api.AssignIn, db: Session = Depends(get_db), user: User = Depends(OPERATOR)):
    inv = _get(db, invoice_id)
    assignee = db.get(User, body.assignee_id) if body.assignee_id else None
    if body.assignee_id and (not assignee or assignee.role == "AUDITOR"):
        raise AppError("Assignee must be an AP analyst or manager.", code="VALIDATION_ERROR", status_code=422)
    before = {"assignee": inv.assignee.name if inv.assignee else None}
    inv.assignee_id = assignee.id if assignee else None
    audit.record(db, action="ASSIGNED", actor=user, invoice=inv, before=before,
                 after={"assignee": assignee.name if assignee else None})
    db.commit()
    return invoice_item(_get(db, invoice_id))
