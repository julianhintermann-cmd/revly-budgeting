from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx, require_editor
from app.core.db import get_db
from app.models import SavingsGoal
from app.models.common import utcnow
from app.schemas.goal import ContributeIn, GoalCreateIn, GoalOut, GoalUpdateIn
from app.services import transactions as txn_service
from app.services.common import fmt_money, t
from app.services.notify import notify

router = APIRouter(prefix="/goals", tags=["goals"])


def _months_until(target: date) -> int:
    today = date.today()
    return max(1, (target.year * 12 + target.month) - (today.year * 12 + today.month))


async def _effective_current(db: AsyncSession, household_id: int, goal: SavingsGoal) -> int:
    if goal.account_id is not None:
        try:
            return await txn_service.account_balance(db, household_id, goal.account_id)
        except HTTPException:
            return goal.current_amount
    return goal.current_amount


async def _to_out(db: AsyncSession, household_id: int, goal: SavingsGoal) -> GoalOut:
    current = await _effective_current(db, household_id, goal)
    remaining = max(0, goal.target_amount - current)
    monthly_needed = None
    if goal.target_date is not None:
        monthly_needed = 0 if remaining == 0 else -(-remaining // _months_until(goal.target_date))
    progress = 0.0
    if goal.target_amount > 0:
        progress = round(min(100.0, max(0.0, current * 100.0 / goal.target_amount)), 1)
    return GoalOut(
        id=goal.id,
        name=goal.name,
        icon=goal.icon,
        target_amount=goal.target_amount,
        current_amount=current,
        target_date=goal.target_date,
        account_id=goal.account_id,
        notes=goal.notes,
        progress_pct=progress,
        monthly_needed=monthly_needed,
        completed_at=goal.completed_at,
        created_at=goal.created_at,
    )


async def _get(db: AsyncSession, household_id: int, goal_id: int) -> SavingsGoal:
    goal = await db.scalar(
        select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.household_id == household_id)
    )
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.get("", response_model=list[GoalOut])
async def list_goals(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> list[GoalOut]:
    goals = (
        await db.execute(
            select(SavingsGoal).where(SavingsGoal.household_id == ctx.household.id).order_by(SavingsGoal.id)
        )
    ).scalars().all()
    return [await _to_out(db, ctx.household.id, g) for g in goals]


@router.post("", response_model=GoalOut, status_code=201)
async def create_goal(
    payload: GoalCreateIn, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> GoalOut:
    if payload.account_id is not None:
        await txn_service.get_account(db, ctx.household.id, payload.account_id)
    goal = SavingsGoal(
        household_id=ctx.household.id,
        name=payload.name,
        icon=payload.icon,
        target_amount=payload.target_amount,
        current_amount=payload.current_amount,
        target_date=payload.target_date,
        account_id=payload.account_id,
        notes=payload.notes,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return await _to_out(db, ctx.household.id, goal)


@router.patch("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: int,
    payload: GoalUpdateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> GoalOut:
    goal = await _get(db, ctx.household.id, goal_id)
    if payload.clear_account:
        goal.account_id = None
    elif payload.account_id is not None:
        await txn_service.get_account(db, ctx.household.id, payload.account_id)
        goal.account_id = payload.account_id
    if payload.clear_target_date:
        goal.target_date = None
    elif payload.target_date is not None:
        goal.target_date = payload.target_date
    for field in ("name", "icon", "target_amount", "current_amount", "notes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(goal, field, value)
    await db.commit()
    return await _to_out(db, ctx.household.id, goal)


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: int, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> None:
    goal = await _get(db, ctx.household.id, goal_id)
    await db.delete(goal)
    await db.commit()


@router.post("/{goal_id}/contribute", response_model=GoalOut)
async def contribute(
    goal_id: int,
    payload: ContributeIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> GoalOut:
    goal = await _get(db, ctx.household.id, goal_id)
    if goal.account_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Goal is linked to an account; its balance tracks progress automatically",
        )
    goal.current_amount = max(0, goal.current_amount + payload.amount)
    if goal.current_amount >= goal.target_amount and not goal.achieved_notified:
        goal.achieved_notified = True
        goal.completed_at = utcnow()
        await notify(
            db,
            ctx.household.id,
            "goal_reached",
            t(ctx.user.locale, "goal_reached_title", name=goal.name),
            t(
                ctx.user.locale,
                "goal_reached_body",
                name=goal.name,
                amount=fmt_money(goal.target_amount, ctx.household.currency),
            ),
            dedupe_key=f"goal:{goal.id}",
            email=True,
        )
    await db.commit()
    return await _to_out(db, ctx.household.id, goal)
