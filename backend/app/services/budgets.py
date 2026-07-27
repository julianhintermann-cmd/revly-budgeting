from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CASH_LIKE_TYPES,
    Account,
    Budget,
    Category,
    ExchangeRate,
    Household,
    Transaction,
    TransactionSplit,
)

# ---------------------------------------------------------------------------
# Month helpers ('YYYY-MM' strings sort correctly and work on every dialect)
# ---------------------------------------------------------------------------


def month_of(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def month_add(month: str, delta: int) -> str:
    y, m = int(month[:4]), int(month[5:7])
    idx = y * 12 + (m - 1) + delta
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_bounds(month: str) -> tuple[date, date]:
    y, m = int(month[:4]), int(month[5:7])
    return date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])


def months_between(start: str, end: str) -> list[str]:
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur = month_add(cur, 1)
    return out


def to_base(amount: int, currency: str, rates: dict[str, Decimal]) -> int:
    rate = rates.get(currency)
    if rate is None or rate == Decimal("1"):
        return amount
    return int((Decimal(amount) * rate).to_integral_value(rounding=ROUND_HALF_UP))


async def get_rates(db: AsyncSession, household_id: int) -> dict[str, Decimal]:
    rows = (await db.execute(select(ExchangeRate).where(ExchangeRate.household_id == household_id))).scalars().all()
    return {r.currency: Decimal(r.rate) for r in rows}


# ---------------------------------------------------------------------------
# Envelope engine
# ---------------------------------------------------------------------------
#
# Semantics (documented in ARCHITECTURE.md):
# * Every expense category has, per month: assigned (budget rows), activity
#   (categorized transactions incl. splits, converted to base currency) and
#   available = carryover + assigned + activity.
# * rollover=True carries the remaining available (positive or negative) into
#   the next month; rollover=False returns it to "to budget" at month end.
# * "To budget" = cumulative income (income categories + uncategorized flows +
#   opening balances of cash-like accounts) minus cumulative assignments plus
#   everything returned by non-rollover categories.


async def compute_month(db: AsyncSession, household: Household, month: str) -> dict:
    hid = household.id
    cats = (await db.execute(select(Category).where(Category.household_id == hid))).scalars().all()
    cat_map = {c.id: c for c in cats}
    expense_ids = [c.id for c in cats if c.type == "expense"]

    accounts = (await db.execute(select(Account).where(Account.household_id == hid))).scalars().all()
    acc_cur = {a.id: a.currency for a in accounts}
    rates = await get_rates(db, hid)

    _, last_day = month_bounds(month)

    budget_rows = (
        await db.execute(select(Budget).where(Budget.household_id == hid, Budget.month <= month))
    ).scalars().all()
    assigned_by_month: dict[str, dict[int, int]] = defaultdict(dict)
    for b in budget_rows:
        assigned_by_month[b.month][b.category_id] = b.assigned

    txn_rows = (
        await db.execute(
            select(
                Transaction.date,
                Transaction.amount,
                Transaction.category_id,
                Transaction.is_split,
                Transaction.account_id,
            ).where(
                Transaction.household_id == hid,
                Transaction.transfer_group.is_(None),
                Transaction.date <= last_day,
            )
        )
    ).all()
    split_rows = (
        await db.execute(
            select(
                Transaction.date,
                TransactionSplit.amount,
                TransactionSplit.category_id,
                Transaction.account_id,
            )
            .join(Transaction, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == hid,
                Transaction.transfer_group.is_(None),
                Transaction.date <= last_day,
            )
        )
    ).all()

    activity: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    income_by_month: dict[str, int] = defaultdict(int)

    def add_flow(d: date, amount: int, category_id: int | None, account_id: int) -> None:
        m = month_of(d)
        conv = to_base(amount, acc_cur.get(account_id, household.currency), rates)
        cat = cat_map.get(category_id) if category_id else None
        if cat is None or cat.type == "income":
            # Income and uncategorized flows go straight into "to budget".
            income_by_month[m] += conv
        else:
            activity[m][cat.id] += conv

    for d, amount, category_id, is_split, account_id in txn_rows:
        if is_split:
            continue  # represented by its splits
        add_flow(d, amount, category_id, account_id)
    for d, amount, category_id, account_id in split_rows:
        add_flow(d, amount, category_id, account_id)

    for a in accounts:
        if a.type in CASH_LIKE_TYPES and a.initial_balance and a.opening_date <= last_day:
            income_by_month[month_of(a.opening_date)] += to_base(a.initial_balance, a.currency, rates)

    month_keys = set(income_by_month) | set(activity) | set(assigned_by_month) | {month}
    start = min(month_keys)

    tbb = 0
    avail: dict[int, int] = {}
    for m in months_between(start, month):
        a_m = assigned_by_month.get(m, {})
        act_m = activity.get(m, {})
        returned = sum(v for cid, v in avail.items() if not cat_map[cid].rollover)
        tbb += returned + income_by_month.get(m, 0) - sum(a_m.values())
        new_avail: dict[int, int] = {}
        for cid in expense_ids:
            prev = avail.get(cid, 0) if cat_map[cid].rollover else 0
            new_avail[cid] = prev + a_m.get(cid, 0) + act_m.get(cid, 0)
        avail = new_avail

    a_target = assigned_by_month.get(month, {})
    act_target = activity.get(month, {})
    categories_out = []
    overspent = 0
    for c in sorted((cat_map[cid] for cid in expense_ids), key=lambda c: (c.sort_order, c.id)):
        row = {
            "category_id": c.id,
            "name": c.name,
            "icon": c.icon,
            "color": c.color,
            "parent_id": c.parent_id,
            "archived": c.archived,
            "rollover": c.rollover,
            "assigned": a_target.get(c.id, 0),
            "activity": act_target.get(c.id, 0),
            "available": avail.get(c.id, 0),
        }
        if row["available"] < 0:
            overspent += 1
        categories_out.append(row)

    return {
        "month": month,
        "to_budget": tbb,
        "income": income_by_month.get(month, 0),
        "assigned_total": sum(a_target.values()),
        "activity_total": sum(act_target.values()),
        "available_total": sum(r["available"] for r in categories_out),
        "overspent_count": overspent,
        "categories": categories_out,
    }


async def category_available(db: AsyncSession, household: Household, month: str, category_id: int) -> dict | None:
    data = await compute_month(db, household, month)
    return next((r for r in data["categories"] if r["category_id"] == category_id), None)


async def set_assigned(db: AsyncSession, household_id: int, month: str, category_id: int, assigned: int) -> None:
    cat = await db.scalar(
        select(Category).where(Category.id == category_id, Category.household_id == household_id)
    )
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if cat.type != "expense":
        raise HTTPException(status_code=422, detail="Only expense categories can be budgeted")
    row = await db.scalar(
        select(Budget).where(
            Budget.household_id == household_id,
            Budget.category_id == category_id,
            Budget.month == month,
        )
    )
    if row:
        row.assigned = assigned
    else:
        db.add(Budget(household_id=household_id, category_id=category_id, month=month, assigned=assigned))


async def get_assigned(db: AsyncSession, household_id: int, month: str, category_id: int) -> int:
    value = await db.scalar(
        select(Budget.assigned).where(
            Budget.household_id == household_id,
            Budget.category_id == category_id,
            Budget.month == month,
        )
    )
    return value or 0


async def move(
    db: AsyncSession,
    household_id: int,
    month: str,
    from_category_id: int | None,
    to_category_id: int | None,
    amount: int,
) -> None:
    """Move assigned budget between categories; None means 'to budget'.
    Assigned amounts may go negative (money is pulled back), like in YNAB."""
    if from_category_id is None and to_category_id is None:
        raise HTTPException(status_code=422, detail="Nothing to move")
    if from_category_id is not None:
        current = await get_assigned(db, household_id, month, from_category_id)
        await _set_assigned_unchecked(db, household_id, month, from_category_id, current - amount)
    if to_category_id is not None:
        current = await get_assigned(db, household_id, month, to_category_id)
        await _set_assigned_unchecked(db, household_id, month, to_category_id, current + amount)


async def _set_assigned_unchecked(
    db: AsyncSession, household_id: int, month: str, category_id: int, assigned: int
) -> None:
    cat = await db.scalar(
        select(Category).where(Category.id == category_id, Category.household_id == household_id)
    )
    if cat is None or cat.type != "expense":
        raise HTTPException(status_code=422, detail="Invalid category")
    row = await db.scalar(
        select(Budget).where(
            Budget.household_id == household_id,
            Budget.category_id == category_id,
            Budget.month == month,
        )
    )
    if row:
        row.assigned = assigned
    else:
        db.add(Budget(household_id=household_id, category_id=category_id, month=month, assigned=assigned))


async def autofill_suggestions(db: AsyncSession, household: Household, month: str) -> list[dict]:
    """Suggest per-category budgets from the average spending of the previous three months,
    rounded to whole units. Only categories without an assignment yet get a suggestion applied."""
    hid = household.id
    window_start, _ = month_bounds(month_add(month, -3))
    _, window_end = month_bounds(month_add(month, -1))

    cats = (await db.execute(select(Category).where(Category.household_id == hid))).scalars().all()
    cat_map = {c.id: c for c in cats}
    accounts = (await db.execute(select(Account).where(Account.household_id == hid))).scalars().all()
    acc_cur = {a.id: a.currency for a in accounts}
    rates = await get_rates(db, hid)

    net: dict[int, int] = defaultdict(int)

    txn_rows = (
        await db.execute(
            select(Transaction.amount, Transaction.category_id, Transaction.account_id).where(
                Transaction.household_id == hid,
                Transaction.transfer_group.is_(None),
                Transaction.is_split.is_(False),
                Transaction.category_id.is_not(None),
                Transaction.date >= window_start,
                Transaction.date <= window_end,
            )
        )
    ).all()
    split_rows = (
        await db.execute(
            select(TransactionSplit.amount, TransactionSplit.category_id, Transaction.account_id)
            .join(Transaction, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == hid,
                Transaction.transfer_group.is_(None),
                Transaction.date >= window_start,
                Transaction.date <= window_end,
                TransactionSplit.category_id.is_not(None),
            )
        )
    ).all()

    for amount, category_id, account_id in list(txn_rows) + list(split_rows):
        cat = cat_map.get(category_id)
        if cat is None or cat.type != "expense":
            continue
        net[category_id] += to_base(amount, acc_cur.get(account_id, household.currency), rates)

    suggestions = []
    for cid, value in net.items():
        spent = -value if value < 0 else 0
        if spent <= 0 or cat_map[cid].archived:
            continue
        avg = spent // 3
        rounded = ((avg + 50) // 100) * 100  # nearest whole franc/euro
        if rounded > 0:
            suggestions.append({"category_id": cid, "suggested": rounded})
    suggestions.sort(key=lambda s: -s["suggested"])
    return suggestions


async def apply_autofill(db: AsyncSession, household: Household, month: str) -> int:
    applied = 0
    for s in await autofill_suggestions(db, household, month):
        current = await get_assigned(db, household.id, month, s["category_id"])
        if current == 0:
            await set_assigned(db, household.id, month, s["category_id"], s["suggested"])
            applied += 1
    return applied
