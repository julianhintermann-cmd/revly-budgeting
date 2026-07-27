from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow

ROLE_OWNER = "owner"
ROLE_EDITOR = "editor"
ROLE_VIEWER = "viewer"
ROLES = (ROLE_OWNER, ROLE_EDITOR, ROLE_VIEWER)


class Household(Base):
    __tablename__ = "households"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="CHF")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (UniqueConstraint("household_id", "user_id", name="uq_member_household_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10), default=ROLE_EDITOR)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class HouseholdInvite(Base):
    __tablename__ = "household_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(10), default=ROLE_EDITOR)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    expires_at: Mapped[datetime] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
