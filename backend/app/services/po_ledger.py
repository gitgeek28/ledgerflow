"""Cumulative PO consumption and receipt figures (the 'ledger' behind split-invoice logic)."""
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import GoodsReceipt, GoodsReceiptLine, POLineConsumption, PurchaseOrder

ACTIVE = ("RESERVED", "APPROVED")


def consumed_by_line(db: Session, po_id: uuid.UUID, exclude_invoice_id: uuid.UUID | None) -> dict:
    q = (select(POLineConsumption.po_line_id, func.sum(POLineConsumption.quantity), func.sum(POLineConsumption.amount))
         .where(POLineConsumption.po_id == po_id, POLineConsumption.status.in_(ACTIVE)))
    if exclude_invoice_id:
        q = q.where(POLineConsumption.invoice_id != exclude_invoice_id)
    out = defaultdict(lambda: (Decimal(0), Decimal(0)))
    for line_id, qty, amount in db.execute(q.group_by(POLineConsumption.po_line_id)):
        out[line_id] = (qty or Decimal(0), amount or Decimal(0))
    return out


def received_by_line(db: Session, po_id: uuid.UUID) -> tuple[dict, list[str]]:
    rows = db.execute(select(GoodsReceiptLine.po_line_id, func.sum(GoodsReceiptLine.quantity_received))
                      .join(GoodsReceipt).where(GoodsReceipt.po_id == po_id, GoodsReceipt.status == "POSTED")
                      .group_by(GoodsReceiptLine.po_line_id)).all()
    grns = db.scalars(select(GoodsReceipt.grn_number).where(GoodsReceipt.po_id == po_id)
                      .order_by(GoodsReceipt.received_date)).all()
    return {line_id: qty for line_id, qty in rows}, list(grns)


def consumed_amount(db: Session, po_id: uuid.UUID, exclude_invoice_id: uuid.UUID | None) -> Decimal:
    return sum((amt for _, amt in consumed_by_line(db, po_id, exclude_invoice_id).values()), Decimal(0))


def release_reservations(db: Session, invoice_id: uuid.UUID) -> int:
    rows = db.scalars(select(POLineConsumption).where(POLineConsumption.invoice_id == invoice_id,
                                                      POLineConsumption.status.in_(ACTIVE))).all()
    for row in rows:
        row.status = "RELEASED"
        row.released_at = datetime.now(UTC)
    db.flush()  # released rows are kept for history; the partial unique index only covers active rows
    return len(rows)


def lock_po(db: Session, po_id: uuid.UUID) -> PurchaseOrder:
    """Row-level lock serialising reservations against one PO (prevents double consumption)."""
    return db.execute(select(PurchaseOrder).where(PurchaseOrder.id == po_id).with_for_update()).scalar_one()
