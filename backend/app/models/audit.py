from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow


class AuditLog(Base):
    """Security-relevant events (logins, password changes, ...). Intentionally has no
    foreign keys so history survives user deletion."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(default=None)
    household_id: Mapped[int | None] = mapped_column(default=None)
    action: Mapped[str] = mapped_column(String(60), index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
