from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx, require_editor
from app.core.db import get_db
from app.schemas.budget import (
    AssignIn,
    AutofillApplyIn,
    AutofillOut,
    AutofillSuggestion,
    BudgetMonthOut,
    MoveIn,
)
from app.schemas.common import MONTH_RE
from app.services import budgets as budget_service

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _validate_month(month: str | None) -> str:
    if month is None:
        return budget_service.month_of(date.today())
    if not MONTH_RE.match(month):
        raise HTTPException(status_code=422, detail="month must be YYYY-MM")
    return month


@router.get("", response_model=BudgetMonthOut)
async def get_month(
    month: str | None = Query(default=None),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> BudgetMonthOut:
    data = await budget_service.compute_month(db, ctx.household, _validate_month(month))
    return BudgetMonthOut(**data)


@router.put("", response_model=BudgetMonthOut)
async def assign(
    payload: AssignIn, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> BudgetMonthOut:
    await budget_service.set_assigned(
        db, ctx.household.id, payload.month, payload.category_id, payload.assigned
    )
    await db.commit()
    data = await budget_service.compute_month(db, ctx.household, payload.month)
    return BudgetMonthOut(**data)


@router.post("/move", response_model=BudgetMonthOut)
async def move(
    payload: MoveIn, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> BudgetMonthOut:
    await budget_service.move(
        db, ctx.household.id, payload.month, payload.from_category_id, payload.to_category_id, payload.amount
    )
    await db.commit()
    data = await budget_service.compute_month(db, ctx.household, payload.month)
    return BudgetMonthOut(**data)


@router.get("/autofill", response_model=AutofillOut)
async def autofill(
    month: str | None = Query(default=None),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> AutofillOut:
    m = _validate_month(month)
    suggestions = await budget_service.autofill_suggestions(db, ctx.household, m)
    return AutofillOut(month=m, suggestions=[AutofillSuggestion(**s) for s in suggestions])


@router.post("/autofill/apply", response_model=BudgetMonthOut)
async def autofill_apply(
    payload: AutofillApplyIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> BudgetMonthOut:
    await budget_service.apply_autofill(db, ctx.household, payload.month)
    await db.commit()
    data = await budget_service.compute_month(db, ctx.household, payload.month)
    return BudgetMonthOut(**data)
