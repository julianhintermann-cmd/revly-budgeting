from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


class AccountOut(BaseModel):
    id: int
    name: str
    type: str
    currency: str
    initial_balance: int
    note: str
    archived: bool
    opening_date: date
    created_at: UTCDateTime
    balance: int
    cleared_balance: int
    # Balance converted into the household base currency.
    balance_base: int


class AccountCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str = Field(default="checking", pattern="^(checking|savings|credit_card|cash|loan|investment)$")
    currency: str = Field(default="", min_length=0, max_length=3)
    initial_balance: int = 0
    note: str = ""
    opening_date: date | None = None


class AccountUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type: str | None = Field(default=None, pattern="^(checking|savings|credit_card|cash|loan|investment)$")
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    initial_balance: int | None = None
    note: str | None = None
    archived: bool | None = None
    opening_date: date | None = None


class ReconcileIn(BaseModel):
    statement_balance: int


class ReconcileOut(BaseModel):
    difference: int
    adjustment_transaction_id: int | None
    reconciled_count: int
    new_balance: int


class RateItem(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    rate: float = Field(gt=0)


class RatesOut(BaseModel):
    base_currency: str
    rates: list[RateItem]


class RatesPutIn(BaseModel):
    rates: list[RateItem]
