from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, client_ip, get_household_ctx, require_editor
from app.core.db import get_db
from app.models import Account, ExchangeRate, Transaction
from app.schemas.account import (
    AccountCreateIn,
    AccountOut,
    AccountUpdateIn,
    RateItem,
    RatesOut,
    RatesPutIn,
    ReconcileIn,
    ReconcileOut,
)
from app.services import audit
from app.services.budgets import get_rates, to_base
from app.services.transactions import balances as balances_service
from app.services.transactions import get_account, reconcile as reconcile_service

router = APIRouter(prefix="/accounts", tags=["accounts"])
rates_router = APIRouter(prefix="/exchange-rates", tags=["accounts"])


def _account_out(account: Account, balance: int, cleared: int, balance_base: int) -> AccountOut:
    return AccountOut(
        id=account.id,
        name=account.name,
        type=account.type,
        currency=account.currency,
        initial_balance=account.initial_balance,
        note=account.note,
        archived=account.archived,
        opening_date=account.opening_date,
        created_at=account.created_at,
        balance=balance,
        cleared_balance=cleared,
        balance_base=balance_base,
    )


@router.get("", response_model=list[AccountOut])
async def list_accounts(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> list[AccountOut]:
    accounts, sums = await balances_service(db, ctx.household.id)
    rates = await get_rates(db, ctx.household.id)
    return [
        _account_out(
            a,
            sums[a.id]["balance"],
            sums[a.id]["cleared"],
            to_base(sums[a.id]["balance"], a.currency, rates),
        )
        for a in accounts
    ]


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    payload: AccountCreateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> AccountOut:
    account = Account(
        household_id=ctx.household.id,
        name=payload.name,
        type=payload.type,
        currency=(payload.currency or ctx.household.currency).upper(),
        initial_balance=payload.initial_balance,
        note=payload.note,
        opening_date=payload.opening_date or date.today(),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    rates = await get_rates(db, ctx.household.id)
    return _account_out(
        account,
        account.initial_balance,
        account.initial_balance,
        to_base(account.initial_balance, account.currency, rates),
    )


@router.get("/{account_id}", response_model=AccountOut)
async def get_account_endpoint(
    account_id: int, ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> AccountOut:
    account = await get_account(db, ctx.household.id, account_id)
    accounts, sums = await balances_service(db, ctx.household.id)
    rates = await get_rates(db, ctx.household.id)
    s = sums[account.id]
    return _account_out(account, s["balance"], s["cleared"], to_base(s["balance"], account.currency, rates))


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: int,
    payload: AccountUpdateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> AccountOut:
    account = await get_account(db, ctx.household.id, account_id)
    for field in ("name", "type", "note", "archived", "opening_date", "initial_balance"):
        value = getattr(payload, field)
        if value is not None:
            setattr(account, field, value)
    if payload.currency is not None:
        account.currency = payload.currency.upper()
    await db.commit()
    accounts, sums = await balances_service(db, ctx.household.id)
    rates = await get_rates(db, ctx.household.id)
    s = sums[account.id]
    return _account_out(account, s["balance"], s["cleared"], to_base(s["balance"], account.currency, rates))


@router.delete("/{account_id}", status_code=204)
async def delete_account(
    account_id: int, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> None:
    account = await get_account(db, ctx.household.id, account_id)
    txn_count = await db.scalar(
        select(func.count(Transaction.id)).where(Transaction.account_id == account.id)
    )
    if txn_count:
        raise HTTPException(
            status_code=409, detail="Account has transactions; archive it instead of deleting"
        )
    await db.delete(account)
    await db.commit()


@router.post("/{account_id}/reconcile", response_model=ReconcileOut)
async def reconcile_account(
    account_id: int,
    payload: ReconcileIn,
    request: Request,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> ReconcileOut:
    result = await reconcile_service(db, ctx.household, ctx.user, account_id, payload.statement_balance)
    await audit.log(
        db,
        "account_reconciled",
        user_id=ctx.user.id,
        household_id=ctx.household.id,
        ip=client_ip(request),
        details=f"account {account_id}, diff {result['difference']}",
    )
    await db.commit()
    return ReconcileOut(**result)


@rates_router.get("", response_model=RatesOut)
async def list_rates(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> RatesOut:
    rows = (
        await db.execute(
            select(ExchangeRate).where(ExchangeRate.household_id == ctx.household.id).order_by(ExchangeRate.currency)
        )
    ).scalars().all()
    return RatesOut(
        base_currency=ctx.household.currency,
        rates=[RateItem(currency=r.currency, rate=float(r.rate)) for r in rows],
    )


@rates_router.put("", response_model=RatesOut)
async def put_rates(
    payload: RatesPutIn, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> RatesOut:
    for item in payload.rates:
        currency = item.currency.upper()
        rate = Decimal("1") if currency == ctx.household.currency else Decimal(str(item.rate))
        row = await db.scalar(
            select(ExchangeRate).where(
                ExchangeRate.household_id == ctx.household.id, ExchangeRate.currency == currency
            )
        )
        if row:
            row.rate = rate
        else:
            db.add(ExchangeRate(household_id=ctx.household.id, currency=currency, rate=rate))
    await db.commit()
    return await list_rates(ctx, db)
