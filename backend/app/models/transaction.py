from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.common import utcnow

TXN_STATUS = ("pending", "cleared", "reconciled")


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_household_date", "household_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    # Cents. Negative = outflow, positive = inflow.
    amount: Mapped[int] = mapped_column(BigInteger)
    payee: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True, default=None
    )
    status: Mapped[str] = mapped_column(String(12), default="cleared")
    # Both legs of a transfer share a group id; each leg points at the opposite account.
    transfer_group: Mapped[str | None] = mapped_column(String(36), index=True, default=None)
    transfer_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), default=None
    )
    is_split: Mapped[bool] = mapped_column(default=False)
    receipt_path: Mapped[str | None] = mapped_column(String(500), default=None)
    import_hash: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    recurring_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_transactions.id", ondelete="SET NULL"), default=None
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    splits: Mapped[list[TransactionSplit]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan", lazy="selectin"
    )


class TransactionSplit(Base):
    __tablename__ = "transaction_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), default=None)
    amount: Mapped[int] = mapped_column(BigInteger)
    note: Mapped[str] = mapped_column(String(200), default="")

    transaction: Mapped[Transaction] = relationship(back_populates="splits")


class TransactionTag(Base):
    __tablename__ = "transaction_tags"

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)
