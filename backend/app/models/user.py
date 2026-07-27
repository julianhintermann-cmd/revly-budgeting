from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120), default="")
    locale: Mapped[str] = mapped_column(String(5), default="de")
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(64), default=None)
    totp_enabled: Mapped[bool] = mapped_column(default=False)
    email_notifications: Mapped[bool] = mapped_column(default=True)
    active_household_id: Mapped[int | None] = mapped_column(
        ForeignKey("households.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
