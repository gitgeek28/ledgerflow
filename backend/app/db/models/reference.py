import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk

JSONType = JSON().with_variant(JSONB(), "postgresql")


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))


class Vendor(UUIDPk, Timestamps, Base):
    __tablename__ = "vendors"
    vendor_code: Mapped[str] = mapped_column(String(20), unique=True)
    legal_name: Mapped[str] = mapped_column(String(200), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(JSONType, default=list)
    tax_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), default="IN")
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    registered_address: Mapped[str] = mapped_column(Text)
    city: Mapped[str] = mapped_column(String(80))
    approved_status: Mapped[str] = mapped_column(String(24), index=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    category: Mapped[str] = mapped_column(String(60))
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank_account_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bank_details_version: Mapped[int] = mapped_column(Integer, default=1)
    bank_details_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="vendor")


class PurchaseOrder(UUIDPk, Timestamps, Base):
    __tablename__ = "purchase_orders"
    po_number: Mapped[str] = mapped_column(String(30), unique=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    po_type: Mapped[str] = mapped_column(String(16))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    po_date: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(240))
    requester: Mapped[str] = mapped_column(String(120))
    cost_centre: Mapped[str] = mapped_column(String(40))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    tolerance_policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("policies.id"), nullable=True)

    vendor: Mapped[Vendor] = relationship(back_populates="purchase_orders")
    lines: Mapped[list["POLine"]] = relationship(back_populates="po", order_by="POLine.line_number",
                                                 cascade="all, delete-orphan")
    grns: Mapped[list["GoodsReceipt"]] = relationship(back_populates="po", order_by="GoodsReceipt.received_date")


class POLine(UUIDPk, Base):
    __tablename__ = "po_lines"
    __table_args__ = (UniqueConstraint("po_id", "line_number"),)
    po_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    item_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    description: Mapped[str] = mapped_column(String(240))
    normalised_description: Mapped[str] = mapped_column(String(240))
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    unit: Mapped[str] = mapped_column(String(16))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    line_subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))

    po: Mapped[PurchaseOrder] = relationship(back_populates="lines")


class GoodsReceipt(UUIDPk, Timestamps, Base):
    __tablename__ = "goods_receipts"
    grn_number: Mapped[str] = mapped_column(String(30), unique=True)
    po_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    received_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="POSTED")
    received_by: Mapped[str] = mapped_column(String(120))
    warehouse: Mapped[str] = mapped_column(String(80))

    po: Mapped[PurchaseOrder] = relationship(back_populates="grns")
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(back_populates="grn", cascade="all, delete-orphan")


class GoodsReceiptLine(UUIDPk, Base):
    __tablename__ = "goods_receipt_lines"
    grn_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("goods_receipts.id", ondelete="CASCADE"), index=True)
    po_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("po_lines.id"), index=True)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(18, 3))

    grn: Mapped[GoodsReceipt] = relationship(back_populates="lines")
    po_line: Mapped[POLine] = relationship()
