from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Budget(Base):
    """Assigned amount for one category in one month ('YYYY-MM')."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("household_id", "category_id", "month", name="uq_budget_household_category_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    assigned: Mapped[int] = mapped_column(BigInteger, default=0)
