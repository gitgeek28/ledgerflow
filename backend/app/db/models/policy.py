import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPk, utcnow
from app.db.models.reference import JSONType


class Policy(UUIDPk, Base):
    __tablename__ = "policies"
    version: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(120))
    settings: Mapped[dict] = mapped_column(JSONType)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
