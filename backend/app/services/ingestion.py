"""Intake: validate upload, store bytes under a server key, detect exact-file duplicates, enqueue processing."""
import hashlib
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import Invoice, Job, ProcessingRun, User
from app.services import audit
from app.services.storage import get_storage
from app.services.workflow.events import emit

PDF_MIME = {"application/pdf", "application/x-pdf", "application/octet-stream", "binary/octet-stream", ""}


@dataclass
class IntakeResult:
    invoice: Invoice
    run: ProcessingRun | None
    duplicate: bool


def safe_filename(name: str | None) -> str:
    name = unicodedata.normalize("NFKC", name or "invoice.pdf")
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip() or "invoice.pdf"
    return name[:200]


def validate_upload(filename: str, content_type: str | None, data: bytes) -> None:
    settings = get_settings()
    if not filename.lower().endswith(".pdf"):
        raise AppError("Only PDF files are accepted.", code="FILE_INVALID", status_code=422,
                       details={"reason": "extension", "filename": filename})
    if (content_type or "").split(";")[0].strip().lower() not in PDF_MIME:
        raise AppError(f"Unsupported content type '{content_type}'. Upload a PDF.", code="FILE_INVALID",
                       status_code=422, details={"reason": "mime"})
    if len(data) == 0:
        raise AppError("The file is empty.", code="FILE_INVALID", status_code=422, details={"reason": "empty"})
    if len(data) > settings.max_upload_bytes:
        raise AppError(f"File is {len(data) / 1048576:.1f} MB; the limit is {settings.max_upload_mb} MB.",
                       code="FILE_INVALID", status_code=413, details={"reason": "size"})
    if not data[:1024].lstrip().startswith(b"%PDF-"):
        raise AppError("The file does not have a PDF signature (%PDF-).", code="FILE_INVALID", status_code=422,
                       details={"reason": "signature"})


def _link_duplicate(db: Session, existing: Invoice, filename: str, user: User | None, sha: str) -> IntakeResult:
    audit.record(db, action="FILE_DUPLICATE_RECEIVED", actor=user, invoice=existing, reason_code="FILE_DUPLICATE",
                 note=f"Identical file re-submitted as '{filename}'. No new invoice was created.",
                 after={"filename": filename, "sha256": sha})
    db.commit()
    return IntakeResult(existing, None, True)


def ingest(db: Session, *, filename: str | None, content_type: str | None, data: bytes, user: User | None,
           batch_id=None) -> IntakeResult:
    filename = safe_filename(filename)
    validate_upload(filename, content_type, data)
    sha = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(Invoice).where(Invoice.file_sha256 == sha))
    if existing:
        return _link_duplicate(db, existing, filename, user, sha)

    key = get_storage().put(data)
    seq = db.execute(text("SELECT nextval('invoice_reference_seq')")).scalar_one()
    invoice = Invoice(reference=f"LF-{seq:06d}", original_filename=filename, storage_key=key, file_sha256=sha,
                      file_size=len(data), status="PROCESSING", uploaded_by_id=user.id if user else None,
                      batch_id=batch_id, field_overrides={}, accepted_exceptions={}, reason_codes=[])
    try:
        with db.begin_nested():
            db.add(invoice)
            db.flush()
    except IntegrityError:
        # A concurrent upload of identical bytes won the race; link to it instead.
        db.rollback()
        existing = db.scalar(select(Invoice).where(Invoice.file_sha256 == sha))
        return _link_duplicate(db, existing, filename, user, sha)
    run = create_run(db, invoice, trigger="UPLOAD", start_stage="FILE_VALIDATION", user=user)
    emit(db, run, "RECEIVED", "STAGE_COMPLETED", "SUCCESS",
         f"Received '{filename}' ({len(data) / 1024:.1f} KB) from {user.name if user else 'system'}; stored under a "
         "server-generated key", details={"sha256": sha, "size_bytes": len(data)}, duration_ms=0)
    audit.record(db, action="INVOICE_RECEIVED", actor=user, invoice=invoice, run_id=run.id,
                 after={"filename": filename, "sha256": sha[:16] + "…", "size_bytes": len(data)})
    db.commit()
    return IntakeResult(invoice, run, False)


def create_run(db: Session, invoice: Invoice, *, trigger: str, start_stage: str, user: User | None,
               previous: ProcessingRun | None = None) -> ProcessingRun:
    attempt = (db.scalar(select(ProcessingRun.attempt).where(ProcessingRun.invoice_id == invoice.id)
                         .order_by(ProcessingRun.attempt.desc()).limit(1)) or 0) + 1
    run = ProcessingRun(invoice_id=invoice.id, attempt=attempt, trigger=trigger, start_stage=start_stage,
                        status="QUEUED", stage_outputs={}, reason_codes=[],
                        triggered_by_id=user.id if user else None, previous_run_id=previous.id if previous else None,
                        pacing_ms=get_settings().demo_stage_pacing_ms)
    db.add(run)
    db.flush()
    db.add(Job(run_id=run.id, status="QUEUED"))
    invoice.latest_run_id = run.id
    invoice.status = "PROCESSING"
    emit(db, run, None, "RUN_QUEUED", "INFO", f"Run #{attempt} queued ({trigger.lower()})",
         details={"trigger": trigger, "start_stage": start_stage})
    return run
