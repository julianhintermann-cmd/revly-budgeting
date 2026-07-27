from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


class GoalOut(BaseModel):
    id: int
    name: str
    icon: str
    target_amount: int
    current_amount: int
    target_date: date | None
    account_id: int | None
    notes: str
    progress_pct: float
    # Cents per month needed to reach the target by target_date; None without a date.
    monthly_needed: int | None
    completed_at: UTCDateTime | None
    created_at: UTCDateTime


class GoalCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    icon: str = Field(default="🎯", max_length=16)
    target_amount: int = Field(gt=0)
    current_amount: int = Field(default=0, ge=0)
    target_date: date | None = None
    account_id: int | None = None
    notes: str = Field(default="", max_length=2000)


class GoalUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    icon: str | None = Field(default=None, max_length=16)
    target_amount: int | None = Field(default=None, gt=0)
    current_amount: int | None = Field(default=None, ge=0)
    target_date: date | None = None
    clear_target_date: bool = False
    account_id: int | None = None
    clear_account: bool = False
    notes: str | None = Field(default=None, max_length=2000)


class ContributeIn(BaseModel):
    amount: int
