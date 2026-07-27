from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx, require_editor
from app.core.db import get_db
from app.models import Account, RecurringTransaction, Transaction
from app.schemas.recurring import (
    RecurringCreateIn,
    RecurringListOut,
    RecurringOut,
    RecurringUpdateIn,
    UpcomingItem,
)
from app.services import transactions as txn_service
from app.services.budgets import get_rates, month_of, to_base
from app.services.recurring import advance, monthly_equivalent

router = APIRouter(prefix="/recurring", tags=["recurring"])

_ANCHOR_FREQS = ("monthly", "quarterly", "yearly")


def _to_out(rec: RecurringTransaction) -> RecurringOut:
    return RecurringOut(
        id=rec.id,
        account_id=rec.account_id,
        category_id=rec.category_id,
        payee=rec.payee,
        amount=rec.amount,
        frequency=rec.frequency,
        interval=rec.interval,
        next_date=rec.next_date,
        end_date=rec.end_date,
        auto_create=rec.auto_create,
        reminder_days=rec.reminder_days,
        active=rec.active,
        notes=rec.notes,
        last_run_date=rec.last_run_date,
        monthly_equivalent=monthly_equivalent(rec.amount, rec.frequency, rec.interval),
        created_at=rec.created_at,
    )


async def _get(db: AsyncSession, household_id: int, rec_id: int) -> RecurringTransaction:
    rec = await db.scalar(
        select(RecurringTransaction).where(
            RecurringTransaction.id == rec_id, RecurringTransaction.household_id == household_id
        )
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Recurring transaction not found")
    return rec


@router.get("", response_model=RecurringListOut)
async def list_recurring(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> RecurringListOut:
    recs = (
        await db.execute(
            select(RecurringTransaction)
            .where(RecurringTransaction.household_id == ctx.household.id)
            .order_by(RecurringTransaction.next_date)
        )
    ).scalars().all()
    accounts = (
        await db.execute(select(Account).where(Account.household_id == ctx.household.id))
    ).scalars().all()
    currency_of = {a.id: a.currency for a in accounts}
    rates = await get_rates(db, ctx.household.id)
    total = 0
    for rec in recs:
        if rec.active and rec.amount < 0:
            equivalent = monthly_equivalent(rec.amount, rec.frequency, rec.interval)
            total += to_base(equivalent, currency_of.get(rec.account_id, ctx.household.currency), rates)
    return RecurringListOut(items=[_to_out(r) for r in recs], monthly_expense_total=total)


@router.post("", response_model=RecurringOut, status_code=201)
async def create_recurring(
    payload: RecurringCreateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> RecurringOut:
    await txn_service.get_account(db, ctx.household.id, payload.account_id)
    if payload.category_id is not None:
        await txn_service._check_category(db, ctx.household.id, payload.category_id)
    rec = RecurringTransaction(
        household_id=ctx.household.id,
        account_id=payload.account_id,
        category_id=payload.category_id,
        payee=payload.payee,
        amount=payload.amount,
        frequency=payload.frequency,
        interval=payload.interval,
        next_date=payload.next_date,
        anchor_day=payload.next_date.day if payload.frequency in _ANCHOR_FREQS else None,
        end_date=payload.end_date,
        auto_create=payload.auto_create,
        reminder_days=payload.reminder_days,
        notes=payload.notes,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return _to_out(rec)


@router.patch("/{rec_id}", response_model=RecurringOut)
async def update_recurring(
    rec_id: int,
    payload: RecurringUpdateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> RecurringOut:
    rec = await _get(db, ctx.household.id, rec_id)
    if payload.account_id is not None:
        await txn_service.get_account(db, ctx.household.id, payload.account_id)
        rec.account_id = payload.account_id
    if payload.clear_category:
        rec.category_id = None
    elif payload.category_id is not None:
        await txn_service._check_category(db, ctx.household.id, payload.category_id)
        rec.category_id = payload.category_id
    for field in ("payee", "amount", "frequency", "interval", "auto_create", "reminder_days", "active", "notes"):
        value = getattr(payload, field)
        if value is not None:
            setattr(rec, field, value)
    if payload.next_date is not None:
        rec.next_date = payload.next_date
    if payload.clear_end_date:
        rec.end_date = None
    elif payload.end_date is not None:
        rec.end_date = payload.end_date
    rec.anchor_day = rec.next_date.day if rec.frequency in _ANCHOR_FREQS else None
    await db.commit()
    return _to_out(rec)


@router.delete("/{rec_id}", status_code=204)
async def delete_recurring(
    rec_id: int, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> None:
    rec = await _get(db, ctx.household.id, rec_id)
    await db.delete(rec)
    await db.commit()


@router.get("/upcoming", response_model=list[UpcomingItem])
async def upcoming(
    days: int = Query(default=30, ge=1, le=120),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> list[UpcomingItem]:
    today = date.today()
    recs = (
        await db.execute(
            select(RecurringTransaction)
            .where(
                RecurringTransaction.household_id == ctx.household.id,
                RecurringTransaction.active.is_(True),
                RecurringTransaction.next_date <= today + timedelta(days=days),
            )
            .order_by(RecurringTransaction.next_date)
        )
    ).scalars().all()
    return [
        UpcomingItem(
            id=r.id,
            payee=r.payee,
            amount=r.amount,
            next_date=r.next_date,
            days_until=(r.next_date - today).days,
            account_id=r.account_id,
            category_id=r.category_id,
            auto_create=r.auto_create,
        )
        for r in recs
    ]


@router.post("/{rec_id}/run", status_code=201)
async def run_now(
    rec_id: int, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> dict:
    rec = await _get(db, ctx.household.id, rec_id)
    today = date.today()
    txn = Transaction(
        household_id=ctx.household.id,
        account_id=rec.account_id,
        date=today,
        amount=rec.amount,
        payee=rec.payee,
        notes=rec.notes,
        category_id=rec.category_id,
        status="cleared",
        recurring_id=rec.id,
        created_by=ctx.user.id,
    )
    db.add(txn)
    rec.last_run_date = today
    if rec.next_date <= today:
        rec.next_date = advance(rec)
    await db.flush()
    await txn_service.post_effects(
        db, ctx.household, ctx.user.locale, {(rec.category_id, month_of(today))}, {rec.account_id}
    )
    await db.commit()
    return {"transaction_id": txn.id}
