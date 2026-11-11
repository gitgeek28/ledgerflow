"""Reserve PO-line quantity/value for an invoice at the decision/approval boundary, under a PO row lock."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Invoice, InvoiceLine, POLine, POLineConsumption
from app.services.money import q2, q3
from app.services.po_ledger import consumed_by_line, lock_po, received_by_line, release_reservations


def reserve(db: Session, invoice: Invoice, *, allow_over: bool = False) -> list[str]:
    """Returns a list of violations. When empty (or allow_over), active reservations are written.

    Concurrency: `lock_po` takes SELECT ... FOR UPDATE on the purchase order, so two invoices against the same
    PO serialise here and the second one sees the first one's reservation before checking remaining balance.
    """
    release_reservations(db, invoice.id)
    if invoice.po_id is None:
        return []
    po = lock_po(db, invoice.po_id)
    consumed = consumed_by_line(db, po.id, invoice.id)
    received, grns = received_by_line(db, po.id)
    three_way = po.po_type == "GOODS" and bool(grns)
    lines = db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id,
                                                 InvoiceLine.matched_po_line_id.is_not(None))).all()
    po_lines = {pl.id: pl for pl in db.scalars(select(POLine).where(POLine.po_id == po.id))}
    violations = []
    for ln in lines:
        pl = po_lines.get(ln.matched_po_line_id)
        if pl is None or ln.quantity is None:
            continue
        prev = consumed[pl.id][0]
        if ln.quantity > pl.quantity_ordered - prev:
            violations.append(f"Line {ln.line_number}: {q3(ln.quantity).normalize():f} exceeds remaining "
                              f"{q3(pl.quantity_ordered - prev).normalize():f} on {po.po_number} line "
                              f"{pl.line_number}")
        if three_way and ln.quantity > received.get(pl.id, Decimal(0)) - prev:
            violations.append(f"Line {ln.line_number}: exceeds received-not-invoiced quantity")
    if violations and not allow_over:
        return violations
    for ln in lines:
        if ln.quantity is None:
            continue
        amount = ln.line_subtotal if ln.line_subtotal is not None else q2(ln.quantity * (ln.unit_price or 0))
        db.add(POLineConsumption(po_id=po.id, po_line_id=ln.matched_po_line_id, invoice_id=invoice.id,
                                 invoice_line_id=ln.id, quantity=ln.quantity, amount=amount, status="RESERVED"))
    db.flush()
    return violations


def mark_consumed(db: Session, invoice: Invoice) -> None:
    for row in db.scalars(select(POLineConsumption).where(POLineConsumption.invoice_id == invoice.id,
                                                          POLineConsumption.status == "RESERVED")):
        row.status = "APPROVED"
