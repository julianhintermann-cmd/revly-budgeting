from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx
from app.api.v1.budgets import _validate_month
from app.core.db import get_db
from app.schemas.report import (
    CalendarOut,
    MoneyFlowOut,
    NetWorthRow,
    SpendingOut,
    TrendRow,
)
from app.services import reports as report_service
from app.services.budgets import month_bounds, month_of

router = APIRouter(prefix="/reports", tags=["reports"])


def _default_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    if date_from and date_to:
        return date_from, date_to
    start, end = month_bounds(month_of(date.today()))
    return date_from or start, date_to or end


@router.get("/spending", response_model=SpendingOut)
async def spending(
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> SpendingOut:
    start, end = _default_range(date_from, date_to)
    data = await report_service.spending(db, ctx.household, start, end, ctx.user.locale)
    return SpendingOut(**data)


@router.get("/trend", response_model=list[TrendRow])
async def trend(
    months: int = Query(default=12, ge=3, le=36),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> list[TrendRow]:
    rows = await report_service.trend(db, ctx.household, months)
    return [TrendRow(**r) for r in rows]


@router.get("/cashflow-calendar", response_model=CalendarOut)
async def cashflow_calendar(
    month: str | None = Query(default=None),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> CalendarOut:
    data = await report_service.cashflow_calendar(db, ctx.household, _validate_month(month))
    return CalendarOut(**data)


@router.get("/net-worth", response_model=list[NetWorthRow])
async def net_worth(
    months: int = Query(default=24, ge=6, le=60),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> list[NetWorthRow]:
    rows = await report_service.net_worth(db, ctx.household, months)
    return [NetWorthRow(**r) for r in rows]


@router.get("/money-flow", response_model=MoneyFlowOut)
async def money_flow(
    month: str | None = Query(default=None),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> MoneyFlowOut:
    data = await report_service.money_flow(db, ctx.household, _validate_month(month), ctx.user.locale)
    return MoneyFlowOut(**data)


@router.get("/export.csv")
async def export_csv(
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> Response:
    csv_text = await report_service.export_transactions_csv(db, ctx.household, date_from, date_to)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="revly-transactions.csv"'},
    )


@router.get("/export.pdf")
async def export_pdf(
    month: str | None = Query(default=None),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> Response:
    m = _validate_month(month)
    pdf = await report_service.monthly_pdf(db, ctx.household, m, ctx.user.locale)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="revly-report-{m}.pdf"'},
    )
