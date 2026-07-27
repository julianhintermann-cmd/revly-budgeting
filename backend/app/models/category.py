from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow

CATEGORY_TYPES = ("income", "expense")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), default=None)
    name: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(16), default="📁")
    color: Mapped[str] = mapped_column(String(9), default="#10b981")
    type: Mapped[str] = mapped_column(String(10), default="expense")
    rollover: Mapped[bool] = mapped_column(default=True)
    archived: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("household_id", "name", name="uq_tag_household_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
