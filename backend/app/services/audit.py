"""Append-only audit trail. System and human actions are recorded distinctly."""
import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Invoice, User


def record(db: Session, *, action: str, actor: User | None, invoice: Invoice | None = None,
           run_id: uuid.UUID | None = None, entity_type: str = "invoice", entity_id: str | None = None,
           entity_label: str | None = None, note: str | None = None, reason_code: str | None = None,
           before: dict | None = None, after: dict | None = None) -> AuditEvent:
    event = AuditEvent(
        invoice_id=invoice.id if invoice else None, run_id=run_id, entity_type=entity_type,
        entity_id=entity_id or (str(invoice.id) if invoice else None),
        entity_label=entity_label or (invoice.reference if invoice else None),
        actor_type="USER" if actor else "SYSTEM", actor_id=actor.id if actor else None,
        actor_name=f"{actor.name} ({actor.title})" if actor else "LedgerFlow workflow",
        action=action, reason_code=reason_code, note=note, before=before, after=after)
    db.add(event)
    return event
