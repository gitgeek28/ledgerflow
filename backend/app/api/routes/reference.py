import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import Paging
from app.api.serializers import invoice_item, po_out, vendor_out
from app.core.errors import NotFound
from app.core.security import current_user
from app.db.models import GoodsReceipt, Invoice, POLineConsumption, PurchaseOrder, User, Vendor
from app.db.session import get_db
from app.schemas import api
from app.services.po_ledger import consumed_by_line, received_by_line

router = APIRouter(tags=["reference data"])


@router.get("/vendors", response_model=api.Page[api.VendorOut])
def list_vendors(q: str | None = None, status: str | None = None, paging: Paging = Depends(),
                 db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(Vendor)
    if q:
        like = f"%{q}%"
        query = query.where(or_(Vendor.legal_name.ilike(like), Vendor.vendor_code.ilike(like),
                                Vendor.display_name.ilike(like), Vendor.city.ilike(like)))
    if status:
        query = query.where(Vendor.approved_status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Vendor.vendor_code).offset(paging.offset).limit(paging.page_size)).all()
    return api.Page(items=[vendor_out(db, v) for v in rows], total=total, page=paging.page,
                    page_size=paging.page_size)


@router.get("/vendors/{vendor_id}")
def get_vendor(vendor_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)):
    v = db.get(Vendor, vendor_id)
    if not v:
        raise NotFound("Vendor not found.")
    pos = db.scalars(select(PurchaseOrder).options(selectinload(PurchaseOrder.vendor))
                     .where(PurchaseOrder.vendor_id == v.id).order_by(desc(PurchaseOrder.po_date))).all()
    invoices = db.scalars(select(Invoice).options(selectinload(Invoice.vendor), selectinload(Invoice.po),
                                                  selectinload(Invoice.assignee))
                          .where(Invoice.vendor_id == v.id).order_by(desc(Invoice.created_at)).limit(50)).all()
    bank_alerts = db.scalar(select(func.count()).select_from(Invoice).where(
        Invoice.vendor_id == v.id, Invoice.reason_codes.contains(["VENDOR_BANK_DETAILS_CHANGED"]))) or 0
    return {"vendor": vendor_out(db, v), "purchase_orders": [po_out(db, p) for p in pos],
            "invoices": [invoice_item(i) for i in invoices], "bank_change_alerts": bank_alerts}


@router.get("/purchase-orders", response_model=api.Page[api.POOut])
def list_pos(q: str | None = None, status: str | None = None, vendor_id: uuid.UUID | None = None,
             paging: Paging = Depends(), db: Session = Depends(get_db), _: User = Depends(current_user)):
    query = select(PurchaseOrder).options(selectinload(PurchaseOrder.vendor)).join(Vendor)
    if q:
        like = f"%{q}%"
        query = query.where(or_(PurchaseOrder.po_number.ilike(like), PurchaseOrder.description.ilike(like),
                                Vendor.legal_name.ilike(like)))
    if status:
        query = query.where(PurchaseOrder.status == status)
    if vendor_id:
        query = query.where(PurchaseOrder.vendor_id == vendor_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(desc(PurchaseOrder.po_number)).offset(paging.offset)
                      .limit(paging.page_size)).all()
    return api.Page(items=[po_out(db, p) for p in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.get("/purchase-orders/{po_id}", response_model=api.PODetail)
def get_po(po_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(current_user)):
    po = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.vendor), selectinload(PurchaseOrder.lines),
                                                 selectinload(PurchaseOrder.grns).selectinload(GoodsReceipt.lines))
                   .where(PurchaseOrder.id == po_id))
    if not po:
        raise NotFound("Purchase order not found.")
    consumed = consumed_by_line(db, po.id, None)
    received, _grns = received_by_line(db, po.id)
    lines = []
    for pl in po.lines:
        lo = api.POLineOut.model_validate(pl)
        lo.quantity_invoiced = consumed[pl.id][0]
        lo.quantity_received = received.get(pl.id) if po.po_type == "GOODS" else None
        lo.quantity_remaining = pl.quantity_ordered - consumed[pl.id][0]
        lines.append(lo)
    by_line = {pl.id: pl.line_number for pl in po.lines}
    grns = [api.GRNOut(grn_number=g.grn_number, received_date=g.received_date, received_by=g.received_by,
                       warehouse=g.warehouse,
                       lines=[{"po_line": by_line.get(gl.po_line_id), "quantity_received": str(gl.quantity_received)}
                              for gl in g.lines]) for g in po.grns]
    rows = db.execute(select(Invoice, func.sum(POLineConsumption.amount), POLineConsumption.status)
                      .join(POLineConsumption, POLineConsumption.invoice_id == Invoice.id)
                      .where(POLineConsumption.po_id == po.id, POLineConsumption.status.in_(["RESERVED", "APPROVED"]))
                      .group_by(Invoice.id, POLineConsumption.status)).all()
    invoices = [{"id": str(i.id), "reference": i.reference, "invoice_number": i.invoice_number, "status": i.status,
                 "amount_consumed": str(amt), "consumption": st} for i, amt, st in rows]
    other = db.scalars(select(Invoice).where(Invoice.po_id == po.id, Invoice.id.notin_([r[0].id for r in rows]))).all()
    invoices += [{"id": str(i.id), "reference": i.reference, "invoice_number": i.invoice_number, "status": i.status,
                  "amount_consumed": "0", "consumption": "NONE"} for i in other]
    base = po_out(db, po).model_dump()
    return api.PODetail(**base, lines=lines, goods_receipts=grns, invoices=invoices)
