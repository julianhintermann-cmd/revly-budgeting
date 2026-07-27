from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.common import Month


class SpendingRow(BaseModel):
    category_id: int | None
    name: str
    icon: str
    color: str
    amount: int


class SpendingOut(BaseModel):
    start: date
    end: date
    total: int
    rows: list[SpendingRow]


class TrendRow(BaseModel):
    month: Month
    income: int
    expenses: int
    net: int


class CalendarDay(BaseModel):
    day: date
    inflow: int
    outflow: int
    net: int
    balance: int


class CalendarOut(BaseModel):
    month: Month
    start_balance: int
    days: list[CalendarDay]
    # Days where the running liquid balance dips below zero.
    tight_days: int


class NetWorthRow(BaseModel):
    month: Month
    assets: int
    liabilities: int
    net: int


class FlowRow(BaseModel):
    name: str
    icon: str
    color: str
    amount: int


class MoneyFlowOut(BaseModel):
    month: Month
    income: list[FlowRow]
    expenses: list[FlowRow]
    income_total: int
    expense_total: int
