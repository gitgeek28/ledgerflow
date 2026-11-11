from sqlalchemy.orm import Session

from app.db.models import ProcessingRun, RunEvent


def emit(db: Session, run: ProcessingRun, stage: str | None, event_type: str, status: str, message: str, *,
         details: dict | None = None, duration_ms: int | None = None, evidence_refs: list | None = None) -> RunEvent:
    event = RunEvent(run_id=run.id, invoice_id=run.invoice_id, stage=stage, event_type=event_type, status=status,
                     message=message, details=details, duration_ms=duration_ms, evidence_refs=evidence_refs)
    db.add(event)
    db.flush()
    return event
