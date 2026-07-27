from __future__ import annotations

from datetime import date, timedelta

from conftest import auth_headers, make_account, register_user

from app.models import RecurringTransaction
from app.services.recurring import advance, monthly_equivalent, process_due, send_reminders


def test_monthly_equivalent():
    assert monthly_equivalent(-1200, "monthly", 1) == 1200
    assert monthly_equivalent(-1200, "yearly", 1) == 100
    assert monthly_equivalent(-3000, "quarterly", 1) == 1000
    assert monthly_equivalent(-1000, "weekly", 1) == 4345
    assert monthly_equivalent(-1000, "custom", 30) == 1015  # every 30 days


def test_advance_keeps_month_end_anchor():
    rec = RecurringTransaction(
        household_id=1,
        account_id=1,
        amount=-1,
        frequency="monthly",
        interval=1,
        next_date=date(2026, 1, 31),
        anchor_day=31,
    )
    d2 = advance(rec)
    assert d2 == date(2026, 2, 28)
    rec.next_date = d2
    assert advance(rec) == date(2026, 3, 31)


async def test_process_due_books_missed_occurrences(client, session_factory):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h)
    today = date.today()

    r = await client.post(
        "/api/v1/recurring",
        json={
            "account_id": acc["id"],
            "payee": "Netflix",
            "amount": -1790,
            "frequency": "monthly",
            "next_date": (today - timedelta(days=40)).isoformat(),
        },
        headers=h,
    )
    assert r.status_code == 201, r.text

    async with session_factory() as db:
        created = await process_due(db)
        await db.commit()
    assert created == 2  # 40 days back -> two monthly occurrences due

    txns = (await client.get("/api/v1/transactions", headers=h)).json()
    netflix = [t for t in txns["items"] if t["payee"] == "Netflix"]
    assert len(netflix) == 2
    assert all(t["recurring_id"] is not None for t in netflix)

    recs = (await client.get("/api/v1/recurring", headers=h)).json()
    assert recs["items"][0]["next_date"] > today.isoformat()
    assert recs["monthly_expense_total"] == 1790

    # running again must not double-book
    async with session_factory() as db:
        created = await process_due(db)
        await db.commit()
    assert created == 0


async def test_reminders_and_upcoming(client, session_factory):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h)
    today = date.today()

    r = await client.post(
        "/api/v1/recurring",
        json={
            "account_id": acc["id"],
            "payee": "Miete",
            "amount": -150000,
            "frequency": "monthly",
            "next_date": (today + timedelta(days=2)).isoformat(),
            "auto_create": False,
            "reminder_days": 3,
        },
        headers=h,
    )
    assert r.status_code == 201

    async with session_factory() as db:
        sent = await send_reminders(db)
        await db.commit()
    assert sent == 1
    async with session_factory() as db:
        sent = await send_reminders(db)
        await db.commit()
    assert sent == 0  # deduped

    notes = (await client.get("/api/v1/notifications", headers=h)).json()
    assert any(n["type"] == "bill_due" for n in notes["items"])

    upcoming = (await client.get("/api/v1/recurring/upcoming", headers=h)).json()
    assert len(upcoming) == 1
    assert upcoming[0]["days_until"] == 2


async def test_run_now(client):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h)
    today = date.today()

    r = await client.post(
        "/api/v1/recurring",
        json={
            "account_id": acc["id"],
            "payee": "Spotify",
            "amount": -1290,
            "frequency": "monthly",
            "next_date": today.isoformat(),
        },
        headers=h,
    )
    rec_id = r.json()["id"]
    r = await client.post(f"/api/v1/recurring/{rec_id}/run", headers=h)
    assert r.status_code == 201
    txns = (await client.get("/api/v1/transactions", headers=h)).json()
    assert txns["total"] == 1
    recs = (await client.get("/api/v1/recurring", headers=h)).json()
    assert recs["items"][0]["next_date"] > today.isoformat()
