from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Debt, DebtPlan, Household
from app.services.budgets import month_add, month_of
from app.services.transactions import account_balance

MAX_MONTHS = 600
SCHEDULE_LIMIT = 120


async def effective_debts(db: AsyncSession, household: Household) -> list[dict]:
    debts = (
        await db.execute(select(Debt).where(Debt.household_id == household.id).order_by(Debt.id))
    ).scalars().all()
    out = []
    for d in debts:
        balance = d.balance
        if d.account_id is not None:
            balance = max(0, -(await account_balance(db, household.id, d.account_id)))
        out.append(
            {
                "id": d.id,
                "name": d.name,
                "account_id": d.account_id,
                "balance": balance,
                "apr_bps": d.apr_bps,
                "min_payment": d.min_payment,
            }
        )
    return out


async def get_plan_settings(db: AsyncSession, household_id: int) -> DebtPlan:
    plan = await db.scalar(select(DebtPlan).where(DebtPlan.household_id == household_id))
    if plan is None:
        plan = DebtPlan(household_id=household_id)
        db.add(plan)
        await db.flush()
    return plan


def _simulate(debts: list[dict], method: str, monthly_budget: int) -> dict:
    balances = {d["id"]: d["balance"] for d in debts}
    if method == "avalanche":
        order = sorted(debts, key=lambda d: (-d["apr_bps"], d["balance"], d["id"]))
    else:
        order = sorted(debts, key=lambda d: (d["balance"], d["id"]))

    schedule: list[dict] = []
    total_interest = 0
    warning: str | None = None
    start_month = month_of(date.today())
    month_i = 0

    while any(b > 0 for b in balances.values()) and month_i < MAX_MONTHS:
        month_i += 1
        interest_m = 0
        for d in debts:
            b = balances[d["id"]]
            if b <= 0:
                continue
            # apr_bps/10000 yearly => /120000 monthly, rounded half-up
            interest = (b * d["apr_bps"] + 60000) // 120000
            balances[d["id"]] = b + interest
            interest_m += interest
        total_interest += interest_m

        min_sum = sum(min(d["min_payment"], balances[d["id"]]) for d in debts if balances[d["id"]] > 0)
        budget = monthly_budget
        if budget < min_sum:
            warning = "budget_below_minimums"
            budget = min_sum
        if budget <= 0:
            warning = "no_budget"
            break

        paid_m = 0
        for d in debts:
            b = balances[d["id"]]
            if b <= 0:
                continue
            pay = min(d["min_payment"], b, budget)
            balances[d["id"]] = b - pay
            budget -= pay
            paid_m += pay
        for d in order:
            if budget <= 0:
                break
            b = balances[d["id"]]
            if b <= 0:
                continue
            pay = min(budget, b)
            balances[d["id"]] = b - pay
            budget -= pay
            paid_m += pay

        schedule.append(
            {
                "index": month_i,
                "month": month_add(start_month, month_i),
                "total_paid": paid_m,
                "interest": interest_m,
                "remaining": sum(balances.values()),
                "balances": {str(k): v for k, v in balances.items()},
            }
        )

    done = all(b <= 0 for b in balances.values())
    return {
        "months": month_i,
        "interest": total_interest,
        "schedule": schedule,
        "warning": warning,
        "done": done,
    }


def compute_plan(debts: list[dict], method: str, monthly_budget: int) -> dict:
    with_balance = [d for d in debts if d["balance"] > 0]
    summaries = {}
    chosen = None
    for m in ("snowball", "avalanche"):
        res = _simulate([dict(d) for d in with_balance], m, monthly_budget)
        summaries[m] = {"months": res["months"], "total_interest": res["interest"]}
        if m == method:
            chosen = res

    assert chosen is not None
    schedule = chosen["schedule"]
    truncated = len(schedule) > SCHEDULE_LIMIT
    debt_free = schedule[-1]["month"] if schedule and chosen["done"] else None
    return {
        "method": method,
        "monthly_budget": monthly_budget,
        "months_to_free": chosen["months"] if chosen["done"] else 0,
        "total_interest": chosen["interest"],
        "debt_free_month": debt_free,
        "truncated": truncated,
        "warning": chosen["warning"] if chosen["warning"] else (None if chosen["done"] else "not_payable"),
        "schedule": schedule[:SCHEDULE_LIMIT],
        "summaries": summaries,
    }
