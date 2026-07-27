from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx, require_editor
from app.core.db import get_db
from app.models import Debt
from app.schemas.debt import (
    DebtCreateIn,
    DebtOut,
    DebtUpdateIn,
    PlanOut,
    PlanSettingsIn,
    PlanSettingsOut,
)
from app.services import debts as debt_service
from app.services import transactions as txn_service

router = APIRouter(prefix="/debts", tags=["debts"])


async def _get(db: AsyncSession, household_id: int, debt_id: int) -> Debt:
    debt = await db.scalar(select(Debt).where(Debt.id == debt_id, Debt.household_id == household_id))
    if debt is None:
        raise HTTPException(status_code=404, detail="Debt not found")
    return debt


@router.get("", response_model=list[DebtOut])
async def list_debts(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> list[DebtOut]:
    rows = await debt_service.effective_debts(db, ctx.household)
    return [DebtOut(**r) for r in rows]


@router.post("", response_model=DebtOut, status_code=201)
async def create_debt(
    payload: DebtCreateIn, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> DebtOut:
    if payload.account_id is not None:
        await txn_service.get_account(db, ctx.household.id, payload.account_id)
    debt = Debt(
        household_id=ctx.household.id,
        name=payload.name,
        account_id=payload.account_id,
        balance=payload.balance,
        apr_bps=payload.apr_bps,
        min_payment=payload.min_payment,
    )
    db.add(debt)
    await db.commit()
    rows = await debt_service.effective_debts(db, ctx.household)
    row = next(r for r in rows if r["id"] == debt.id)
    return DebtOut(**row)


@router.patch("/{debt_id}", response_model=DebtOut)
async def update_debt(
    debt_id: int,
    payload: DebtUpdateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> DebtOut:
    debt = await _get(db, ctx.household.id, debt_id)
    if payload.clear_account:
        debt.account_id = None
    elif payload.account_id is not None:
        await txn_service.get_account(db, ctx.household.id, payload.account_id)
        debt.account_id = payload.account_id
    for field in ("name", "balance", "apr_bps", "min_payment"):
        value = getattr(payload, field)
        if value is not None:
            setattr(debt, field, value)
    await db.commit()
    rows = await debt_service.effective_debts(db, ctx.household)
    row = next(r for r in rows if r["id"] == debt.id)
    return DebtOut(**row)


@router.delete("/{debt_id}", status_code=204)
async def delete_debt(
    debt_id: int, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> None:
    debt = await _get(db, ctx.household.id, debt_id)
    await db.delete(debt)
    await db.commit()


@router.get("/plan-settings", response_model=PlanSettingsOut)
async def get_plan_settings(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> PlanSettingsOut:
    plan = await debt_service.get_plan_settings(db, ctx.household.id)
    await db.commit()
    return PlanSettingsOut(method=plan.method, monthly_budget=plan.monthly_budget)


@router.put("/plan-settings", response_model=PlanSettingsOut)
async def put_plan_settings(
    payload: PlanSettingsIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> PlanSettingsOut:
    plan = await debt_service.get_plan_settings(db, ctx.household.id)
    plan.method = payload.method
    plan.monthly_budget = payload.monthly_budget
    await db.commit()
    return PlanSettingsOut(method=plan.method, monthly_budget=plan.monthly_budget)


@router.get("/plan", response_model=PlanOut)
async def get_plan(
    method: str | None = Query(default=None, pattern="^(snowball|avalanche)$"),
    monthly_budget: int | None = Query(default=None, ge=0),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> PlanOut:
    settings = await debt_service.get_plan_settings(db, ctx.household.id)
    debts = await debt_service.effective_debts(db, ctx.household)
    result = debt_service.compute_plan(
        debts,
        method or settings.method,
        monthly_budget if monthly_budget is not None else settings.monthly_budget,
    )
    await db.commit()
    return PlanOut(**result)
