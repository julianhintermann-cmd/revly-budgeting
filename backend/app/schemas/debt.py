from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Month


class DebtOut(BaseModel):
    id: int
    name: str
    account_id: int | None
    balance: int
    apr_bps: int
    min_payment: int


class DebtCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_id: int | None = None
    balance: int = Field(default=0, ge=0)
    apr_bps: int = Field(default=0, ge=0, le=100000)
    min_payment: int = Field(default=0, ge=0)


class DebtUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    account_id: int | None = None
    clear_account: bool = False
    balance: int | None = Field(default=None, ge=0)
    apr_bps: int | None = Field(default=None, ge=0, le=100000)
    min_payment: int | None = Field(default=None, ge=0)


class PlanSettingsIn(BaseModel):
    method: str = Field(pattern="^(snowball|avalanche)$")
    monthly_budget: int = Field(ge=0)


class PlanSettingsOut(BaseModel):
    method: str
    monthly_budget: int


class PlanMonthRow(BaseModel):
    index: int
    month: Month
    total_paid: int
    interest: int
    remaining: int
    # Debt balances after this month, keyed by debt id (as string).
    balances: dict[str, int]


class MethodSummary(BaseModel):
    months: int
    total_interest: int


class PlanOut(BaseModel):
    method: str
    monthly_budget: int
    months_to_free: int
    total_interest: int
    debt_free_month: Month | None
    truncated: bool
    warning: str | None
    schedule: list[PlanMonthRow]
    summaries: dict[str, MethodSummary]
