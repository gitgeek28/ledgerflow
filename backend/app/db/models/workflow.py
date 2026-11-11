import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk, utcnow
from app.db.models.reference import JSONType


class ProcessingRun(UUIDPk, Base):
    __tablename__ = "processing_runs"
    __table_args__ = (Index("ix_runs_invoice_attempt", "invoice_id", "attempt", unique=True),
                      Index("ix_runs_created", "created_at"))
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    attempt: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(16))
    start_stage: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(12), index=True)
    current_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extractor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("policies.id"), nullable=True)
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reason_codes: Mapped[list[str]] = mapped_column(JSONType, default=list)
    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stage_outputs: Mapped[dict] = mapped_column(JSONType, default=dict)
    pacing_ms: Mapped[int] = mapped_column(Integer, default=0)
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    previous_run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)  # sum of stage work time


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (Index("ix_run_events_run_id_id", "run_id", "id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_runs.id", ondelete="CASCADE"))
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_type: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(12))  # SUCCESS | WARNING | FAILURE | INFO
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    evidence_refs: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(UUIDPk, Base):
    """DB-backed job queue row. Claimed with SELECT ... FOR UPDATE SKIP LOCKED and a time-bound lease."""
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_claim", "status", "available_at"),)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_runs.id", ondelete="CASCADE"), unique=True)
    kind: Mapped[str] = mapped_column(String(32), default="process_invoice")
    status: Mapped[str] = mapped_column(String(12))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditEvent(Base):
    """Append-only. A database trigger rejects UPDATE and DELETE on this table."""
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_invoice_time", "invoice_id", "occurred_at"),
                      Index("ix_audit_time", "occurred_at"))
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"),
                                                         nullable=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(48), index=True)
    reason_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    before: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
