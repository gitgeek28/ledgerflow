from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.api.serializers import invoice_item
from app.core.security import current_user
from app.db.models import Invoice, User
from app.db.session import get_db
from app.schemas import api

router = APIRouter(tags=["review queue"])


@router.get("/review-queue", response_model=list[api.InvoiceListItem])
def review_queue(view: str = Query("open", pattern="^(open|mine|approval|hold)$"), db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    """open: needs review + on hold; mine: assigned to me; approval: ready for approval; hold: on hold only."""
    statuses = {"open": ["NEEDS_REVIEW", "ON_HOLD"], "mine": ["NEEDS_REVIEW", "ON_HOLD", "READY_FOR_APPROVAL"],
                "approval": ["READY_FOR_APPROVAL"], "hold": ["ON_HOLD"]}[view]
    q = (select(Invoice).options(selectinload(Invoice.vendor), selectinload(Invoice.po), selectinload(Invoice.assignee))
         .where(Invoice.status.in_(statuses)))
    if view == "mine":
        q = q.where(Invoice.assignee_id == user.id)
    prio = case((Invoice.priority == "HIGH", 0), (Invoice.priority == "NORMAL", 1), else_=2)
    rows = db.scalars(q.order_by(prio, Invoice.created_at).limit(200)).all()
    return [invoice_item(i) for i in rows]
