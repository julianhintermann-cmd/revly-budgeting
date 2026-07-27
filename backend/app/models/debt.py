from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.common import utcnow

DEBT_METHODS = ("snowball", "avalanche")


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), default=None)
    # Positive amount owed in cents. When an account is linked, -balance wins.
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    # Annual percentage rate in basis points (12.5% -> 1250).
    apr_bps: Mapped[int] = mapped_column(default=0)
    min_payment: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class DebtPlan(Base):
    """Per-household payoff strategy settings."""

    __tablename__ = "debt_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), unique=True, index=True
    )
    method: Mapped[str] = mapped_column(String(10), default="snowball")
    monthly_budget: Mapped[int] = mapped_column(BigInteger, default=0)
