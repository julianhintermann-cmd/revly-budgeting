from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow

FREQUENCIES = ("weekly", "monthly", "quarterly", "yearly", "custom")


class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), default=None)
    payee: Mapped[str] = mapped_column(String(200), default="")
    amount: Mapped[int] = mapped_column(BigInteger)
    frequency: Mapped[str] = mapped_column(String(10), default="monthly")
    # every N weeks/months/quarters/years; for "custom" every N days
    interval: Mapped[int] = mapped_column(default=1)
    next_date: Mapped[date] = mapped_column(Date)
    # Keeps "31st of the month" recurring on month ends instead of drifting to the 28th.
    anchor_day: Mapped[int | None] = mapped_column(default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    auto_create: Mapped[bool] = mapped_column(default=True)
    reminder_days: Mapped[int] = mapped_column(default=3)
    active: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    last_run_date: Mapped[date | None] = mapped_column(Date, default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
