from __future__ import annotations

import asyncio
import calendar
import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Household, RecurringTransaction, Transaction
from app.services.common import fmt_money, t
from app.services.notify import notify

logger = logging.getLogger(__name__)


def add_months(d: date, n: int, anchor_day: int | None = None) -> date:
    idx = d.year * 12 + (d.month - 1) + n
    year, month = idx // 12, idx % 12 + 1
    day = min(anchor_day or d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def advance(rec: RecurringTransaction) -> date:
    d = rec.next_date
    if rec.frequency == "weekly":
        return d + timedelta(days=7 * rec.interval)
    if rec.frequency == "custom":
        return d + timedelta(days=rec.interval)
    months = {"monthly": 1, "quarterly": 3, "yearly": 12}[rec.frequency] * rec.interval
    return add_months(d, months, rec.anchor_day)


def monthly_equivalent(amount: int, frequency: str, interval: int) -> int:
    """Absolute cents per month this recurring roughly costs/earns."""
    interval = max(1, interval)
    value = Decimal(abs(amount))
    if frequency == "weekly":
        per_month = value * Decimal("4.345") / interval
    elif frequency == "monthly":
        per_month = value / interval
    elif frequency == "quarterly":
        per_month = value / (3 * interval)
    elif frequency == "yearly":
        per_month = value / (12 * interval)
    else:  # custom, every N days
        per_month = value * Decimal("30.44") / interval
    return int(per_month.to_integral_value(rounding=ROUND_HALF_UP))


async def _currency_map(db: AsyncSession, household_ids: set[int]) -> dict[int, str]:
    if not household_ids:
        return {}
    rows = (await db.execute(select(Household.id, Household.currency).where(Household.id.in_(household_ids)))).all()
    return dict(rows)


async def process_due(db: AsyncSession, today: date | None = None) -> int:
    """Book every recurring transaction that is due; advances next_date past today."""
    today = today or date.today()
    locale = get_settings().default_locale
    recs = (
        await db.execute(
            select(RecurringTransaction).where(
                RecurringTransaction.active.is_(True),
                RecurringTransaction.auto_create.is_(True),
                RecurringTransaction.next_date <= today,
            )
        )
    ).scalars().all()
    currencies = await _currency_map(db, {r.household_id for r in recs})
    created = 0
    for rec in recs:
        guard = 0
        while rec.active and rec.next_date <= today and guard < 36:
            if rec.end_date and rec.next_date > rec.end_date:
                rec.active = False
                break
            booked_date = rec.next_date
            db.add(
                Transaction(
                    household_id=rec.household_id,
                    account_id=rec.account_id,
                    date=booked_date,
                    amount=rec.amount,
                    payee=rec.payee,
                    notes=rec.notes,
                    category_id=rec.category_id,
                    status="cleared",
                    recurring_id=rec.id,
                )
            )
            created += 1
            rec.last_run_date = booked_date
            currency = currencies.get(rec.household_id, "CHF")
            await notify(
                db,
                rec.household_id,
                "recurring_created",
                t(locale, "recurring_created_title", payee=rec.payee or "—"),
                t(
                    locale,
                    "recurring_created_body",
                    payee=rec.payee or "—",
                    amount=fmt_money(rec.amount, currency),
                    date=booked_date.isoformat(),
                ),
                dedupe_key=f"rec:{rec.id}:{booked_date.isoformat()}",
                data={"recurring_id": rec.id},
            )
            rec.next_date = advance(rec)
            guard += 1
        if rec.end_date and rec.next_date > rec.end_date:
            rec.active = False
    await db.flush()
    return created


async def send_reminders(db: AsyncSession, today: date | None = None) -> int:
    """Bill reminders X days ahead (and same-day for manual recurrings)."""
    today = today or date.today()
    locale = get_settings().default_locale
    recs = (
        await db.execute(
            select(RecurringTransaction).where(
                RecurringTransaction.active.is_(True),
                RecurringTransaction.next_date <= today + timedelta(days=60),
                RecurringTransaction.next_date >= today,
            )
        )
    ).scalars().all()
    currencies = await _currency_map(db, {r.household_id for r in recs})
    sent = 0
    for rec in recs:
        delta = (rec.next_date - today).days
        if delta > rec.reminder_days:
            continue
        if delta == 0 and rec.auto_create:
            continue  # gets booked instead
        currency = currencies.get(rec.household_id, "CHF")
        result = await notify(
            db,
            rec.household_id,
            "bill_due",
            t(locale, "bill_due_title", payee=rec.payee or "—"),
            t(
                locale,
                "bill_due_body",
                payee=rec.payee or "—",
                amount=fmt_money(rec.amount, currency),
                date=rec.next_date.isoformat(),
            ),
            dedupe_key=f"bill:{rec.id}:{rec.next_date.isoformat()}",
            data={"recurring_id": rec.id, "due": rec.next_date.isoformat()},
            email=True,
        )
        if result is not None:
            sent += 1
    await db.flush()
    return sent


async def run_scheduler(stop_event: asyncio.Event) -> None:
    """Background loop started from the app lifespan; single-process by design."""
    from app.core.db import SessionLocal

    interval = get_settings().scheduler_interval_seconds
    while not stop_event.is_set():
        try:
            async with SessionLocal() as db:
                await process_due(db)
                await send_reminders(db)
                await db.commit()
        except Exception:
            logger.exception("Recurring scheduler run failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except (asyncio.TimeoutError, TimeoutError):
            pass
