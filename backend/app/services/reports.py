from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CASH_LIKE_TYPES,
    DEBT_TYPES,
    Account,
    Budget,
    Category,
    Debt,
    Household,
    RecurringTransaction,
    SavingsGoal,
    Tag,
    Transaction,
)
from app.services.budgets import (
    compute_month,
    get_rates,
    month_add,
    month_bounds,
    month_of,
    months_between,
    to_base,
)
from app.services.common import fmt_money, t
from app.services.transactions import tags_for_transactions


async def _context(db: AsyncSession, household: Household):
    accounts = (
        await db.execute(select(Account).where(Account.household_id == household.id))
    ).scalars().all()
    cats = (
        await db.execute(select(Category).where(Category.household_id == household.id))
    ).scalars().all()
    rates = await get_rates(db, household.id)
    return {a.id: a for a in accounts}, {c.id: c for c in cats}, rates


async def _flow_rows(db: AsyncSession, household_id: int, start: date, end: date):
    """(amount, category_id, account_id) tuples for the range: plain transactions plus splits,
    transfers excluded."""
    txn_rows = (
        await db.execute(
            select(Transaction.amount, Transaction.category_id, Transaction.account_id).where(
                Transaction.household_id == household_id,
                Transaction.transfer_group.is_(None),
                Transaction.is_split.is_(False),
                Transaction.date >= start,
                Transaction.date <= end,
            )
        )
    ).all()
    from app.models import TransactionSplit

    split_rows = (
        await db.execute(
            select(TransactionSplit.amount, TransactionSplit.category_id, Transaction.account_id)
            .join(Transaction, TransactionSplit.transaction_id == Transaction.id)
            .where(
                Transaction.household_id == household_id,
                Transaction.transfer_group.is_(None),
                Transaction.date >= start,
                Transaction.date <= end,
            )
        )
    ).all()
    return list(txn_rows) + list(split_rows)


async def spending(
    db: AsyncSession, household: Household, start: date, end: date, locale: str = "de"
) -> dict:
    accounts, cats, rates = await _context(db, household)
    sums: dict[int | None, int] = defaultdict(int)

    for amount, cid, account_id in await _flow_rows(db, household.id, start, end):
        account = accounts.get(account_id)
        conv = to_base(amount, account.currency if account else household.currency, rates)
        cat = cats.get(cid) if cid else None
        if cat is None:
            if conv < 0:
                sums[None] += -conv
            continue
        if cat.type != "expense":
            continue
        sums[cid] += -conv

    rows = []
    for cid, amount in sums.items():
        if amount <= 0:
            continue
        if cid is None:
            rows.append(
                {
                    "category_id": None,
                    "name": t(locale, "uncategorized"),
                    "icon": "❓",
                    "color": "#94a3b8",
                    "amount": amount,
                }
            )
        else:
            c = cats[cid]
            rows.append(
                {"category_id": cid, "name": c.name, "icon": c.icon, "color": c.color, "amount": amount}
            )
    rows.sort(key=lambda r: -r["amount"])
    return {"start": start, "end": end, "total": sum(r["amount"] for r in rows), "rows": rows}


async def trend(db: AsyncSession, household: Household, months: int = 12) -> list[dict]:
    accounts, cats, rates = await _context(db, household)
    current = month_of(date.today())
    start_month = month_add(current, -(months - 1))
    start, _ = month_bounds(start_month)
    _, end = month_bounds(current)

    income: dict[str, int] = defaultdict(int)
    expense: dict[str, int] = defaultdict(int)

    txn_rows = (
        await db.execute(
            select(
                Transaction.date,
                Transaction.amount,
                Transaction.category_id,
                Transaction.is_split,
                Transaction.account_id,
            ).where(
                Transaction.household_id == household.id,
                Transaction.transfer_group.is_(None),
                Transaction.date >= start,
                Transaction.date <= end,
            )
        )
    ).all()
    from app.models import TransactionSplit

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
                Transaction.household_id == household.id,
                Transaction.transfer_group.is_(None),
                Transaction.date >= start,
                Transaction.date <= end,
            )
        )
    ).all()

    def add(d: date, amount: int, cid: int | None, account_id: int) -> None:
        account = accounts.get(account_id)
        conv = to_base(amount, account.currency if account else household.currency, rates)
        m = month_of(d)
        cat = cats.get(cid) if cid else None
        if cat is not None and cat.type == "income":
            income[m] += conv
        elif cat is not None:
            expense[m] += -conv
        elif conv >= 0:
            income[m] += conv
        else:
            expense[m] += -conv

    for d, amount, cid, is_split, account_id in txn_rows:
        if is_split:
            continue
        add(d, amount, cid, account_id)
    for d, amount, cid, account_id in split_rows:
        add(d, amount, cid, account_id)

    return [
        {
            "month": m,
            "income": income.get(m, 0),
            "expenses": expense.get(m, 0),
            "net": income.get(m, 0) - expense.get(m, 0),
        }
        for m in months_between(start_month, current)
    ]


async def cashflow_calendar(db: AsyncSession, household: Household, month: str) -> dict:
    accounts, _cats, rates = await _context(db, household)
    cash_accounts = [a for a in accounts.values() if a.type in CASH_LIKE_TYPES]
    cash_ids = [a.id for a in cash_accounts]
    start, end = month_bounds(month)
    if not cash_ids:
        return {"month": month, "start_balance": 0, "days": [], "tight_days": 0}

    prior_rows = (
        await db.execute(
            select(Transaction.account_id, func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.account_id.in_(cash_ids), Transaction.date < start)
            .group_by(Transaction.account_id)
        )
    ).all()
    start_balance = 0
    for a in cash_accounts:
        if a.opening_date < start:
            start_balance += to_base(a.initial_balance, a.currency, rates)
    for account_id, total in prior_rows:
        start_balance += to_base(int(total or 0), accounts[account_id].currency, rates)

    inflow: dict[date, int] = defaultdict(int)
    outflow: dict[date, int] = defaultdict(int)
    for a in cash_accounts:
        if start <= a.opening_date <= end and a.initial_balance:
            conv = to_base(a.initial_balance, a.currency, rates)
            if conv >= 0:
                inflow[a.opening_date] += conv
            else:
                outflow[a.opening_date] += -conv

    day_rows = (
        await db.execute(
            select(Transaction.date, Transaction.amount, Transaction.account_id).where(
                Transaction.account_id.in_(cash_ids),
                Transaction.date >= start,
                Transaction.date <= end,
            )
        )
    ).all()
    for d, amount, account_id in day_rows:
        conv = to_base(amount, accounts[account_id].currency, rates)
        if conv >= 0:
            inflow[d] += conv
        else:
            outflow[d] += -conv

    days = []
    balance = start_balance
    tight = 0
    cur = start
    while cur <= end:
        i, o = inflow.get(cur, 0), outflow.get(cur, 0)
        balance += i - o
        if balance < 0:
            tight += 1
        days.append({"day": cur, "inflow": i, "outflow": o, "net": i - o, "balance": balance})
        cur += timedelta(days=1)
    return {"month": month, "start_balance": start_balance, "days": days, "tight_days": tight}


async def net_worth(db: AsyncSession, household: Household, months: int = 24) -> list[dict]:
    accounts, _cats, rates = await _context(db, household)
    current = month_of(date.today())
    month_list = months_between(month_add(current, -(months - 1)), current)

    rows = (
        await db.execute(
            select(Transaction.account_id, Transaction.date, Transaction.amount).where(
                Transaction.household_id == household.id
            )
        )
    ).all()
    per_account_month: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for account_id, d, amount in rows:
        per_account_month[account_id][month_of(d)] += amount

    all_months = sorted({m for acc in per_account_month.values() for m in acc} | set(month_list))
    running: dict[int, int] = defaultdict(int)
    snapshot: dict[str, dict[int, int]] = {}
    for m in all_months:
        for account_id in accounts:
            delta = per_account_month.get(account_id, {}).get(m, 0)
            if delta:
                running[account_id] += delta
        snapshot[m] = dict(running)

    out = []
    for m in month_list:
        snap = snapshot.get(m, {})
        assets = liabilities = 0
        for a in accounts.values():
            if month_of(a.opening_date) > m:
                continue
            bal = a.initial_balance + snap.get(a.id, 0)
            conv = to_base(bal, a.currency, rates)
            if a.type in DEBT_TYPES:
                liabilities += conv
            else:
                assets += conv
        out.append({"month": m, "assets": assets, "liabilities": liabilities, "net": assets + liabilities})
    return out


async def money_flow(db: AsyncSession, household: Household, month: str, locale: str = "de") -> dict:
    start, end = month_bounds(month)
    accounts, cats, rates = await _context(db, household)
    income_sums: dict[int | None, int] = defaultdict(int)
    expense_sums: dict[int | None, int] = defaultdict(int)

    for amount, cid, account_id in await _flow_rows(db, household.id, start, end):
        account = accounts.get(account_id)
        conv = to_base(amount, account.currency if account else household.currency, rates)
        cat = cats.get(cid) if cid else None
        if cat is None:
            if conv >= 0:
                income_sums[None] += conv
            else:
                expense_sums[None] += -conv
        elif cat.type == "income":
            income_sums[cid] += conv
        else:
            expense_sums[cid] += -conv

    def build(sums: dict[int | None, int]) -> list[dict]:
        rows = []
        for cid, amount in sums.items():
            if amount <= 0:
                continue
            if cid is None:
                rows.append(
                    {"name": t(locale, "uncategorized"), "icon": "❓", "color": "#94a3b8", "amount": amount}
                )
            else:
                c = cats[cid]
                rows.append({"name": c.name, "icon": c.icon, "color": c.color, "amount": amount})
        rows.sort(key=lambda r: -r["amount"])
        return rows

    income_rows = build(income_sums)
    expense_rows = build(expense_sums)
    return {
        "month": month,
        "income": income_rows,
        "expenses": expense_rows,
        "income_total": sum(r["amount"] for r in income_rows),
        "expense_total": sum(r["amount"] for r in expense_rows),
    }


async def export_transactions_csv(
    db: AsyncSession, household: Household, start: date | None = None, end: date | None = None
) -> str:
    accounts, cats, _rates = await _context(db, household)
    query = select(Transaction).where(Transaction.household_id == household.id)
    if start:
        query = query.where(Transaction.date >= start)
    if end:
        query = query.where(Transaction.date <= end)
    txns = (await db.execute(query.order_by(Transaction.date, Transaction.id))).scalars().all()
    tags_map = await tags_for_transactions(db, [t_.id for t_ in txns])

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "date", "account", "payee", "category", "amount", "currency", "status", "notes", "tags", "transfer"]
    )
    for txn in txns:
        account = accounts.get(txn.account_id)
        cat = cats.get(txn.category_id) if txn.category_id else None
        writer.writerow(
            [
                txn.id,
                txn.date.isoformat(),
                account.name if account else "",
                txn.payee,
                cat.name if cat else "",
                f"{Decimal(txn.amount) / 100:.2f}",
                account.currency if account else household.currency,
                txn.status,
                txn.notes,
                ", ".join(tags_map.get(txn.id, [])),
                "yes" if txn.transfer_group else "",
            ]
        )
    return "﻿" + buf.getvalue()


def _iso(value):
    return value.isoformat() if value is not None else None


async def export_full_json(db: AsyncSession, household: Household) -> dict:
    hid = household.id
    accounts = (await db.execute(select(Account).where(Account.household_id == hid))).scalars().all()
    cats = (await db.execute(select(Category).where(Category.household_id == hid))).scalars().all()
    txns = (await db.execute(select(Transaction).where(Transaction.household_id == hid))).scalars().all()
    budgets = (await db.execute(select(Budget).where(Budget.household_id == hid))).scalars().all()
    recs = (
        await db.execute(select(RecurringTransaction).where(RecurringTransaction.household_id == hid))
    ).scalars().all()
    goals = (await db.execute(select(SavingsGoal).where(SavingsGoal.household_id == hid))).scalars().all()
    debts = (await db.execute(select(Debt).where(Debt.household_id == hid))).scalars().all()
    tags = (await db.execute(select(Tag).where(Tag.household_id == hid))).scalars().all()
    tags_map = await tags_for_transactions(db, [t_.id for t_ in txns])

    return {
        "exported_at": date.today().isoformat(),
        "household": {"name": household.name, "currency": household.currency},
        "accounts": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "currency": a.currency,
                "initial_balance": a.initial_balance,
                "archived": a.archived,
                "opening_date": _iso(a.opening_date),
                "note": a.note,
            }
            for a in accounts
        ],
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "icon": c.icon,
                "color": c.color,
                "type": c.type,
                "parent_id": c.parent_id,
                "rollover": c.rollover,
                "archived": c.archived,
            }
            for c in cats
        ],
        "tags": [{"id": t_.id, "name": t_.name} for t_ in tags],
        "transactions": [
            {
                "id": txn.id,
                "account_id": txn.account_id,
                "date": _iso(txn.date),
                "amount": txn.amount,
                "payee": txn.payee,
                "notes": txn.notes,
                "category_id": txn.category_id,
                "status": txn.status,
                "transfer_group": txn.transfer_group,
                "is_split": txn.is_split,
                "splits": [
                    {"category_id": s.category_id, "amount": s.amount, "note": s.note} for s in txn.splits
                ],
                "tags": tags_map.get(txn.id, []),
            }
            for txn in txns
        ],
        "budgets": [
            {"category_id": b.category_id, "month": b.month, "assigned": b.assigned} for b in budgets
        ],
        "recurring": [
            {
                "id": r.id,
                "account_id": r.account_id,
                "category_id": r.category_id,
                "payee": r.payee,
                "amount": r.amount,
                "frequency": r.frequency,
                "interval": r.interval,
                "next_date": _iso(r.next_date),
                "end_date": _iso(r.end_date),
                "auto_create": r.auto_create,
                "active": r.active,
            }
            for r in recs
        ],
        "savings_goals": [
            {
                "id": g.id,
                "name": g.name,
                "target_amount": g.target_amount,
                "current_amount": g.current_amount,
                "target_date": _iso(g.target_date),
                "account_id": g.account_id,
            }
            for g in goals
        ],
        "debts": [
            {
                "id": d.id,
                "name": d.name,
                "account_id": d.account_id,
                "balance": d.balance,
                "apr_bps": d.apr_bps,
                "min_payment": d.min_payment,
            }
            for d in debts
        ],
    }


async def monthly_pdf(db: AsyncSession, household: Household, month: str, locale: str = "de") -> bytes:
    from io import BytesIO

    from reportlab.lib import colors as rl_colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    start, end = month_bounds(month)
    sp = await spending(db, household, start, end, locale)
    tr = await trend(db, household, 6)
    bm = await compute_month(db, household, month)
    currency = household.currency

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=t(locale, "pdf_title", month=month))
    styles = getSampleStyleSheet()
    story = [Paragraph(t(locale, "pdf_title", month=month), styles["Title"]), Spacer(1, 4 * mm)]
    story.append(
        Paragraph(f"{t(locale, 'pdf_to_budget')}: {fmt_money(bm['to_budget'], currency)}", styles["Normal"])
    )
    story.append(Spacer(1, 6 * mm))

    header_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#10b981")),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.25, rl_colors.HexColor("#cbd5e1")),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]
    )

    story.append(Paragraph(t(locale, "pdf_spending"), styles["Heading2"]))
    data = [[t(locale, "pdf_category"), t(locale, "pdf_amount")]]
    for row in sp["rows"][:25]:
        data.append([row["name"], fmt_money(row["amount"], currency)])
    data.append(["Total", fmt_money(sp["total"], currency)])
    table = Table(data, colWidths=[110 * mm, 45 * mm])
    table.setStyle(header_style)
    story.append(table)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(t(locale, "pdf_trend"), styles["Heading2"]))
    data2 = [
        [t(locale, "pdf_month"), t(locale, "pdf_income"), t(locale, "pdf_expenses"), t(locale, "pdf_net")]
    ]
    for row in tr:
        data2.append(
            [
                row["month"],
                fmt_money(row["income"], currency),
                fmt_money(row["expenses"], currency),
                fmt_money(row["net"], currency),
            ]
        )
    table2 = Table(data2, colWidths=[35 * mm, 40 * mm, 40 * mm, 40 * mm])
    table2.setStyle(header_style)
    story.append(table2)
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(t(locale, "pdf_generated"), styles["Normal"]))

    doc.build(story)
    return buf.getvalue()
