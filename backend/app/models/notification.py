from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow

NOTIFICATION_TYPES = (
    "bill_due",
    "budget_overspent",
    "goal_reached",
    "recurring_created",
    "member_joined",
    "generic",
)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("household_id", "dedupe_key", name="uq_notification_dedupe"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    # None = visible to every household member.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), default=None)
    type: Mapped[str] = mapped_column(String(30), default="generic")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), default=None)
    read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
