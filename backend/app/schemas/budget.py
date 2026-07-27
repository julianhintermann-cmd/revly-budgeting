from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Month


class BudgetCategoryRow(BaseModel):
    category_id: int
    name: str
    icon: str
    color: str
    parent_id: int | None
    archived: bool
    rollover: bool
    assigned: int
    activity: int
    available: int


class BudgetMonthOut(BaseModel):
    month: Month
    to_budget: int
    income: int
    assigned_total: int
    activity_total: int
    available_total: int
    overspent_count: int
    categories: list[BudgetCategoryRow]


class AssignIn(BaseModel):
    month: Month
    category_id: int
    assigned: int = Field(ge=0)


class MoveIn(BaseModel):
    month: Month
    # None = "to be budgeted"
    from_category_id: int | None = None
    to_category_id: int | None = None
    amount: int = Field(gt=0)


class AutofillSuggestion(BaseModel):
    category_id: int
    suggested: int


class AutofillOut(BaseModel):
    month: Month
    suggestions: list[AutofillSuggestion]


class AutofillApplyIn(BaseModel):
    month: Month
