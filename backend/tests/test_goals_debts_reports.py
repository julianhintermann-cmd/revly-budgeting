from __future__ import annotations

from datetime import date

from conftest import auth_headers, get_categories, make_account, register_user

TODAY = date.today()


async def test_goal_manual_progress_and_reached(client):
    data = await register_user(client)
    h = auth_headers(data)

    r = await client.post("/api/v1/goals", json={"name": "Ferien", "target_amount": 100000}, headers=h)
    assert r.status_code == 201
    goal = r.json()
    assert goal["progress_pct"] == 0.0

    r = await client.post(f"/api/v1/goals/{goal['id']}/contribute", json={"amount": 40000}, headers=h)
    assert r.json()["progress_pct"] == 40.0
    assert r.json()["completed_at"] is None

    r = await client.post(f"/api/v1/goals/{goal['id']}/contribute", json={"amount": 60000}, headers=h)
    assert r.json()["completed_at"] is not None

    notes = (await client.get("/api/v1/notifications", headers=h)).json()
    assert any(n["type"] == "goal_reached" for n in notes["items"])


async def test_goal_linked_account_and_monthly_needed(client):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h, name="Sparen", type="savings", initial_balance=20000)

    target_date = date(TODAY.year + 1, TODAY.month, 15)
    r = await client.post(
        "/api/v1/goals",
        json={
            "name": "Notgroschen",
            "target_amount": 50000,
            "account_id": acc["id"],
            "target_date": target_date.isoformat(),
        },
        headers=h,
    )
    goal = r.json()
    assert goal["current_amount"] == 20000
    months = (target_date.year * 12 + target_date.month) - (TODAY.year * 12 + TODAY.month)
    expected = -(-30000 // months)  # ceil division
    assert goal["monthly_needed"] == expected

    # linked goals cannot take manual contributions
    r = await client.post(f"/api/v1/goals/{goal['id']}/contribute", json={"amount": 100}, headers=h)
    assert r.status_code == 409

    # topping up the account moves the progress
    await client.post(
        "/api/v1/transactions",
        json={"account_id": acc["id"], "date": TODAY.isoformat(), "amount": 30000},
        headers=h,
    )
    goals = (await client.get("/api/v1/goals", headers=h)).json()
    assert goals[0]["current_amount"] == 50000
    assert goals[0]["progress_pct"] == 100.0


async def test_debt_plan_snowball_vs_avalanche(client):
    data = await register_user(client)
    h = auth_headers(data)

    r = await client.post(
        "/api/v1/debts",
        json={"name": "Kreditkarte", "balance": 100000, "apr_bps": 1200, "min_payment": 2000},
        headers=h,
    )
    assert r.status_code == 201
    await client.post(
        "/api/v1/debts",
        json={"name": "Privatkredit", "balance": 50000, "apr_bps": 0, "min_payment": 1000},
        headers=h,
    )

    r = await client.put(
        "/api/v1/debts/plan-settings", json={"method": "snowball", "monthly_budget": 20000}, headers=h
    )
    assert r.status_code == 200

    plan = (await client.get("/api/v1/debts/plan", headers=h)).json()
    assert plan["method"] == "snowball"
    assert plan["months_to_free"] > 0
    assert plan["debt_free_month"] is not None
    # First month interest: 12% APR on 1000.00 -> 10.00; the 0% loan adds nothing.
    assert plan["schedule"][0]["interest"] == 1000
    assert (
        plan["summaries"]["avalanche"]["total_interest"]
        <= plan["summaries"]["snowball"]["total_interest"]
    )

    # what-if override via query params
    faster = (await client.get("/api/v1/debts/plan", params={"monthly_budget": 50000}, headers=h)).json()
    assert faster["months_to_free"] < plan["months_to_free"]


async def test_reports_and_exports(client):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h, initial_balance=200000)
    cats = await get_categories(client, h)
    food = next(c for c in cats if c["name"] == "Lebensmittel")
    salary = next(c for c in cats if c["name"] == "Gehalt")

    for amount, cid, payee in ((-4500, food["id"], "Migros"), (350000, salary["id"], "Lohn")):
        await client.post(
            "/api/v1/transactions",
            json={
                "account_id": acc["id"],
                "date": TODAY.isoformat(),
                "amount": amount,
                "category_id": cid,
                "payee": payee,
            },
            headers=h,
        )

    r = await client.get("/api/v1/reports/spending", headers=h)
    body = r.json()
    assert body["total"] == 4500
    assert body["rows"][0]["name"] == "Lebensmittel"

    r = await client.get("/api/v1/reports/trend", headers=h)
    months = r.json()
    assert len(months) == 12
    assert months[-1]["income"] == 350000  # flow report: opening balances are not income flows
    assert months[-1]["expenses"] == 4500

    r = await client.get("/api/v1/reports/net-worth", headers=h)
    rows = r.json()
    assert rows[-1]["net"] == 200000 + 350000 - 4500

    r = await client.get("/api/v1/reports/money-flow", headers=h)
    flow = r.json()
    assert flow["expense_total"] == 4500
    assert flow["income_total"] == 350000  # opening balance is not a flow row

    r = await client.get("/api/v1/reports/cashflow-calendar", headers=h)
    cal = r.json()
    assert len(cal["days"]) >= 28
    assert cal["days"][-1]["balance"] == 200000 + 350000 - 4500

    r = await client.get("/api/v1/reports/export.csv", headers=h)
    assert r.status_code == 200
    assert "Migros" in r.text

    r = await client.get("/api/v1/reports/export.pdf", headers=h)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"

    r = await client.get("/api/v1/export/full.json", headers=h)
    body = r.json()
    assert body["household"]["currency"] == "CHF"
    assert len(body["transactions"]) == 2

    r = await client.get("/api/v1/export/transactions.csv", headers=h)
    assert r.status_code == 200


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
