import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk, utcnow
from app.db.models.reference import JSONType, PurchaseOrder, User, Vendor


class IntakeBatch(UUIDPk, Base):
    __tablename__ = "intake_batches"
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    results: Mapped[list] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Invoice(UUIDPk, Timestamps, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_vendor_invoice_no", "vendor_id", "invoice_number_normalised"),
        Index("ix_invoices_status_created", "status", "created_at"),
    )
    reference: Mapped[str] = mapped_column(String(20), unique=True)  # human-friendly LF-000123
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(120), unique=True)
    file_sha256: Mapped[str] = mapped_column(String(64), unique=True)  # Layer-1 duplicate guard
    file_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("intake_batches.id"), nullable=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(24), index=True)
    priority: Mapped[str] = mapped_column(String(8), default="NORMAL")
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str] = mapped_column(String(8), default="SYSTEM")  # SYSTEM | HUMAN
    decision_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSONType, default=list)
    next_action: Mapped[str | None] = mapped_column(String(240), nullable=True)
    match_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)  # TWO_WAY | THREE_WAY

    # Extracted + normalised header fields (null until extracted / when unreadable)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vendors.id"), nullable=True, index=True)
    vendor_name_raw: Mapped[str | None] = mapped_column(String(240), nullable=True)
    vendor_tax_id_raw: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    invoice_number_normalised: Mapped[str | None] = mapped_column(String(60), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    po_reference_raw: Mapped[str | None] = mapped_column(String(60), nullable=True)
    po_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_orders.id"), nullable=True, index=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    grand_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True, index=True)
    bank_account_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    bank_account_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)

    extraction: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # field-level values + evidence
    extraction_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    document_text: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # per-page text + method
    field_overrides: Mapped[dict] = mapped_column(JSONType, default=dict)  # human corrections {field: {...}}
    accepted_exceptions: Mapped[dict] = mapped_column(JSONType, default=dict)  # code -> acceptance record
    po_selected_by_human: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    latest_run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    info_request_draft: Mapped[str | None] = mapped_column(Text, nullable=True)

    vendor: Mapped[Vendor | None] = relationship(foreign_keys=[vendor_id])
    po: Mapped[PurchaseOrder | None] = relationship(foreign_keys=[po_id])
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    lines: Mapped[list["InvoiceLine"]] = relationship(back_populates="invoice", order_by="InvoiceLine.line_number",
                                                      cascade="all, delete-orphan")


class InvoiceLine(UUIDPk, Base):
    __tablename__ = "invoice_lines"
    __table_args__ = (UniqueConstraint("invoice_id", "line_number"),)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    line_number: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    line_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    matched_po_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("po_lines.id"), nullable=True)
    match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class InvoiceCheck(Base):
    __tablename__ = "invoice_checks"
    __table_args__ = (Index("ix_invoice_checks_run", "run_id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_runs.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(32))
    code: Mapped[str] = mapped_column(String(48), index=True)
    name: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str | None] = mapped_column(String(120), nullable=True)  # e.g. "line 2"
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(16))
    outcome: Mapped[str] = mapped_column(String(10))  # NONE | REVIEW | HOLD | REJECT
    message: Mapped[str] = mapped_column(Text)
    actual: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expected: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delta: Mapped[str | None] = mapped_column(String(60), nullable=True)
    threshold: Mapped[str | None] = mapped_column(String(60), nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    policy_version: Mapped[int] = mapped_column(Integer)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class POLineConsumption(UUIDPk, Base):
    """Reservation of PO-line quantity/amount by an invoice. Created under a row lock on the PO."""
    __tablename__ = "po_line_consumptions"
    __table_args__ = (Index("uq_consumption_active_invoice_line", "invoice_line_id", unique=True,
                            postgresql_where=text("status IN ('RESERVED', 'APPROVED')")),)
    po_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    po_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("po_lines.id"), index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    invoice_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoice_lines.id", ondelete="CASCADE"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InvoiceNote(UUIDPk, Base):
    __tablename__ = "invoice_notes"
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    author: Mapped[User] = relationship()
