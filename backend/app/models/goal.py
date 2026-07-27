from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow


class SavingsGoal(Base):
    __tablename__ = "savings_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(16), default="🎯")
    target_amount: Mapped[int] = mapped_column(BigInteger)
    # Manual progress; ignored when an account is linked (its balance is used instead).
    current_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    target_date: Mapped[date | None] = mapped_column(Date, default=None)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), default=None)
    notes: Mapped[str] = mapped_column(Text, default="")
    achieved_notified: Mapped[bool] = mapped_column(default=False)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
