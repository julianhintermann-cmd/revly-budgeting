from __future__ import annotations

# Alias: fields named "date" would otherwise shadow the type during annotation evaluation.
from datetime import date as DateType

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


class SplitIn(BaseModel):
    category_id: int | None = None
    amount: int
    note: str = Field(default="", max_length=200)


class SplitOut(BaseModel):
    id: int
    category_id: int | None
    amount: int
    note: str


class TransactionOut(BaseModel):
    id: int
    account_id: int
    date: DateType
    amount: int
    payee: str
    notes: str
    category_id: int | None
    status: str
    transfer_account_id: int | None
    transfer_group: str | None
    is_split: bool
    splits: list[SplitOut]
    tags: list[str]
    has_receipt: bool
    recurring_id: int | None
    created_at: UTCDateTime


class TransactionCreateIn(BaseModel):
    account_id: int
    date: DateType
    # Cents; negative = expense, positive = income. For transfers send the positive amount to move.
    amount: int
    payee: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)
    category_id: int | None = None
    status: str = Field(default="cleared", pattern="^(pending|cleared|reconciled)$")
    splits: list[SplitIn] | None = None
    tags: list[str] | None = None
    transfer_to_account_id: int | None = None


class TransactionUpdateIn(BaseModel):
    account_id: int | None = None
    date: DateType | None = None
    amount: int | None = None
    payee: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    category_id: int | None = None
    clear_category: bool = False
    status: str | None = Field(default=None, pattern="^(pending|cleared|reconciled)$")
    splits: list[SplitIn] | None = None
    clear_splits: bool = False
    tags: list[str] | None = None


class TransactionListOut(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    page_size: int
    sum_amount: int


class BulkActionIn(BaseModel):
    ids: list[int] = Field(min_length=1)
    action: str = Field(pattern="^(set_category|add_tag|remove_tag|set_status|delete)$")
    category_id: int | None = None
    tag: str | None = None
    status: str | None = Field(default=None, pattern="^(pending|cleared|reconciled)$")


class BulkActionOut(BaseModel):
    affected: int
    skipped: int
