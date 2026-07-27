from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow

ACCOUNT_TYPES = ("checking", "savings", "credit_card", "cash", "loan", "investment")
# Types whose opening balance counts as money available for budgeting.
CASH_LIKE_TYPES = ("checking", "savings", "cash")
DEBT_TYPES = ("credit_card", "loan")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="checking")
    currency: Mapped[str] = mapped_column(String(3), default="CHF")
    initial_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(default=False)
    opening_date: Mapped[date] = mapped_column(Date, default=date.today)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ExchangeRate(Base):
    """Manual conversion rate of `currency` into the household base currency."""

    __tablename__ = "exchange_rates"
    __table_args__ = (UniqueConstraint("household_id", "currency", name="uq_rate_household_currency"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    currency: Mapped[str] = mapped_column(String(3))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal("1"))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
