from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


class RecurringOut(BaseModel):
    id: int
    account_id: int
    category_id: int | None
    payee: str
    amount: int
    frequency: str
    interval: int
    next_date: date
    end_date: date | None
    auto_create: bool
    reminder_days: int
    active: bool
    notes: str
    last_run_date: date | None
    monthly_equivalent: int
    created_at: UTCDateTime


class RecurringCreateIn(BaseModel):
    account_id: int
    category_id: int | None = None
    payee: str = Field(default="", max_length=200)
    amount: int
    frequency: str = Field(default="monthly", pattern="^(weekly|monthly|quarterly|yearly|custom)$")
    interval: int = Field(default=1, ge=1, le=365)
    next_date: date
    end_date: date | None = None
    auto_create: bool = True
    reminder_days: int = Field(default=3, ge=0, le=60)
    notes: str = Field(default="", max_length=2000)


class RecurringUpdateIn(BaseModel):
    account_id: int | None = None
    category_id: int | None = None
    clear_category: bool = False
    payee: str | None = Field(default=None, max_length=200)
    amount: int | None = None
    frequency: str | None = Field(default=None, pattern="^(weekly|monthly|quarterly|yearly|custom)$")
    interval: int | None = Field(default=None, ge=1, le=365)
    next_date: date | None = None
    end_date: date | None = None
    clear_end_date: bool = False
    auto_create: bool | None = None
    reminder_days: int | None = Field(default=None, ge=0, le=60)
    active: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class RecurringListOut(BaseModel):
    items: list[RecurringOut]
    # Sum of monthly equivalents of active expense recurrings (absolute cents).
    monthly_expense_total: int


class UpcomingItem(BaseModel):
    id: int
    payee: str
    amount: int
    next_date: date
    days_until: int
    account_id: int
    category_id: int | None
    auto_create: bool
