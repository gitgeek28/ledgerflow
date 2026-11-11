import csv
import io
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import Paging
from app.core.security import current_user
from app.db.models import AuditEvent, User
from app.db.session import get_db
from app.schemas import api

router = APIRouter(prefix="/audit", tags=["audit"])


def _query(q, actor_type, action, invoice_id, since, until):
    query = select(AuditEvent)
    if q:
        like = f"%{q}%"
        query = query.where(or_(AuditEvent.entity_label.ilike(like), AuditEvent.actor_name.ilike(like),
                                AuditEvent.note.ilike(like), AuditEvent.action.ilike(like)))
    if actor_type:
        query = query.where(AuditEvent.actor_type == actor_type)
    if action:
        query = query.where(AuditEvent.action == action)
    if invoice_id:
        query = query.where(AuditEvent.invoice_id == invoice_id)
    if since:
        query = query.where(AuditEvent.occurred_at >= since)
    if until:
        query = query.where(AuditEvent.occurred_at <= until)
    return query


@router.get("", response_model=api.Page[api.AuditOut])
def list_audit(q: str | None = None, actor_type: str | None = None, action: str | None = None,
               invoice_id: uuid.UUID | None = None, since: datetime | None = None, until: datetime | None = None,
               paging: Paging = Depends(), db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = _query(q, actor_type, action, invoice_id, since, until)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(desc(AuditEvent.id)).offset(paging.offset).limit(paging.page_size)).all()
    return api.Page(items=rows, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/actions", response_model=list[str])
def actions(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.scalars(select(AuditEvent.action).distinct().order_by(AuditEvent.action)).all()


@router.get("/export.csv")
def export(q: str | None = None, actor_type: str | None = None, action: str | None = None,
           db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(_query(q, actor_type, action, None, None, None).order_by(AuditEvent.id)).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "occurred_at", "actor_type", "actor", "action", "entity_type", "entity", "reason_code", "note",
                "before", "after"])
    for e in rows:
        w.writerow([e.id, e.occurred_at.isoformat(), e.actor_type, e.actor_name, e.action, e.entity_type,
                    e.entity_label, e.reason_code, e.note, e.before, e.after])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ledgerflow-audit.csv"})
