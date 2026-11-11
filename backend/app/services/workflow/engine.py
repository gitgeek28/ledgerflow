"""Executes a processing run stage by stage, persisting events, checks and outputs after every stage.

Failure semantics:
  * DocumentUnreadable  -> run FAILED, non-retryable (same bytes will fail again)  - never a business REJECTED
  * OCRUnavailable      -> run FAILED, retryable (infrastructure)
  * anything unexpected -> run FAILED, retryable, error class recorded (no stack traces leaked to the UI)
Stages are idempotent: a reclaimed job re-runs from the run's start stage and overwrites that run's outputs.
"""
import time
import traceback
import uuid
from collections.abc import Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Invoice, InvoiceCheck, Policy, ProcessingRun
from app.db.models.enums import STAGE_ORDER
from app.services import audit
from app.services.checks import CheckResult
from app.services.extraction.document import DocumentUnreadable, OCRUnavailable
from app.services.policy import PolicySettings, load_active_policy
from app.services.workflow.events import emit
from app.services.workflow.stages import HANDLERS, RunContext, StageOutcome

log = get_logger("workflow")
PIPELINE = [s.value for s in STAGE_ORDER if s.value != "RECEIVED"]


class RunAborted(Exception):
    pass


def _persist_checks(db: Session, run: ProcessingRun, stage: str, checks: list[CheckResult], version: int) -> None:
    db.execute(delete(InvoiceCheck).where(InvoiceCheck.run_id == run.id, InvoiceCheck.stage == stage))
    for c in checks:
        db.add(InvoiceCheck(invoice_id=run.invoice_id, run_id=run.id, stage=stage, code=c.code, name=c.name,
                            subject=c.subject, severity=c.severity, status=c.status, outcome=c.outcome,
                            message=c.message[:2000], actual=c.actual, expected=c.expected, delta=c.delta,
                            threshold=c.threshold, evidence=c.evidence or None, policy_version=version))


def _fail(db: Session, run_id: uuid.UUID, stage: str | None, code: str, message: str, retryable: bool,
          policy_version: int | None) -> None:
    db.rollback()
    run = db.get(ProcessingRun, run_id)
    invoice = db.get(Invoice, run.invoice_id)
    run.status, run.error_code, run.error_message, run.retryable = "FAILED", code, message[:1000], retryable
    run.finished_at = utcnow()
    invoice.status = "FAILED"
    invoice.decision_summary = (f"Processing failed at {stage.replace('_', ' ').lower() if stage else 'start'}: "
                                f"{message} This is a technical failure, not a business rejection.")
    invoice.next_action = "Retry processing" if retryable else "Ask the vendor to re-send a readable PDF"
    invoice.reason_codes = ["FILE_INVALID"] if code.startswith("PDF_") else [code]
    invoice.priority = "NORMAL"
    if code.startswith("PDF_") and stage:
        _persist_checks(db, run, stage, [CheckResult("FILE_INVALID", "FAIL", message, actual=code,
                                                     outcome="NONE")], policy_version or 0)
    emit(db, run, stage, "STAGE_FAILED", "FAILURE", message,
         details={"error_code": code, "retryable": retryable})
    emit(db, run, None, "RUN_FAILED", "FAILURE",
         f"Run failed ({'retryable' if retryable else 'not retryable'}): {code}",
         details={"error_code": code, "retryable": retryable})
    audit.record(db, action="PROCESSING_FAILED", actor=None, invoice=invoice, run_id=run.id, reason_code=code,
                 note=message[:500], after={"retryable": retryable})
    db.commit()


def execute_run(db: Session, run_id: uuid.UUID, heartbeat: Callable[[], None] | None = None) -> str:
    run = db.get(ProcessingRun, run_id)
    if run is None or run.status in ("COMPLETED", "FAILED"):
        return run.status if run else "MISSING"
    invoice = db.get(Invoice, run.invoice_id)
    resumed = run.status == "RUNNING"
    if run.policy_id:
        policy_row = db.get(Policy, run.policy_id)
        policy = PolicySettings.model_validate(policy_row.settings)
    else:
        policy_row, policy = load_active_policy(db)
        run.policy_id, run.policy_version = policy_row.id, policy_row.version
    run.status = "RUNNING"
    run.started_at = run.started_at or utcnow()
    emit(db, run, None, "RUN_RESUMED" if resumed else "RUN_STARTED", "INFO",
         (f"Run #{run.attempt} resumed after worker interruption; restarting from {run.start_stage}" if resumed else
          f"Run #{run.attempt} started from {run.start_stage.replace('_', ' ').lower()} using policy "
          f"v{policy_row.version}"), details={"policy_version": policy_row.version, "trigger": run.trigger})
    db.commit()

    ctx = RunContext(db=db, run=run, invoice=invoice, policy=policy, policy_version=policy_row.version)
    stages = PIPELINE[PIPELINE.index(run.start_stage):]
    total_ms = 0
    for stage in stages:
        run.current_stage = stage
        emit(db, run, stage, "STAGE_STARTED", "INFO", f"{stage.replace('_', ' ').title()} started")
        db.commit()
        started = time.perf_counter()
        try:
            outcome: StageOutcome = HANDLERS[stage](ctx)
        except DocumentUnreadable as exc:
            _fail(db, run_id, stage, exc.code, str(exc), False, policy_row.version)
            return "FAILED"
        except OCRUnavailable as exc:
            _fail(db, run_id, stage, "OCR_UNAVAILABLE", str(exc), True, policy_row.version)
            return "FAILED"
        except Exception as exc:  # noqa: BLE001 - recorded as a technical failure, never swallowed
            log.error("stage_error", run_id=str(run_id), stage=stage, error=type(exc).__name__,
                      trace=traceback.format_exc(limit=6))
            _fail(db, run_id, stage, "UNEXPECTED_ERROR",
                  f"{type(exc).__name__} during {stage.replace('_', ' ').lower()}.", True, policy_row.version)
            return "FAILED"
        duration = int((time.perf_counter() - started) * 1000)
        total_ms += duration
        ctx.checks.extend(outcome.checks)
        _persist_checks(db, run, stage, outcome.checks, policy_row.version)
        outputs = dict(run.stage_outputs or {})
        outputs[stage] = outcome.details
        run.stage_outputs = outputs
        failing = [c.code for c in outcome.checks if c.failing]
        emit(db, run, stage, "STAGE_COMPLETED", outcome.status, outcome.message,
             details={"checks_passed": sum(1 for c in outcome.checks if c.status == "PASS"),
                      "checks_failed": failing}, duration_ms=duration, evidence_refs=outcome.evidence_refs or None)
        db.commit()
        if heartbeat:
            heartbeat()
        if run.pacing_ms:
            time.sleep(run.pacing_ms / 1000)

    run.status = "COMPLETED"
    run.finished_at = utcnow()
    run.duration_ms = total_ms
    run.current_stage = None
    emit(db, run, None, "RUN_COMPLETED", "SUCCESS" if invoice.status == "READY_FOR_APPROVAL" else "WARNING",
         f"Run #{run.attempt} completed in {total_ms} ms of processing: {invoice.status.replace('_', ' ')}",
         details={"decision": invoice.status, "reason_codes": invoice.reason_codes, "processing_ms": total_ms})
    audit.record(db, action="SYSTEM_DECISION", actor=None, invoice=invoice, run_id=run.id,
                 reason_code=(invoice.reason_codes or [None])[0], note=invoice.decision_summary,
                 after={"status": invoice.status, "reason_codes": invoice.reason_codes,
                        "policy_version": policy_row.version, "extractor": run.extractor})
    db.commit()
    return "COMPLETED"


def latest_run(db: Session, invoice_id: uuid.UUID) -> ProcessingRun | None:
    return db.scalar(select(ProcessingRun).where(ProcessingRun.invoice_id == invoice_id)
                     .order_by(ProcessingRun.attempt.desc()).limit(1))
