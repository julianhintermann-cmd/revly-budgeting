from __future__ import annotations

from datetime import date

from conftest import auth_headers, get_categories, make_account, register_user

from app.services.budgets import month_add, month_bounds, month_of

TODAY = date.today()
M0 = month_of(TODAY)
M1 = month_add(M0, 1)


async def _setup(client, initial: int = 100000):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h, initial_balance=initial)
    cats = await get_categories(client, h)
    food = next(c for c in cats if c["name"] == "Lebensmittel")
    fun = next(c for c in cats if c["name"] == "Freizeit")
    salary = next(c for c in cats if c["name"] == "Gehalt")
    return h, acc, food, fun, salary


async def test_to_budget_assignment_and_activity(client):
    h, acc, food, _fun, _salary = await _setup(client)

    b = (await client.get("/api/v1/budgets", headers=h)).json()
    assert b["to_budget"] == 100000  # opening balance is money to assign

    b = (
        await client.put(
            "/api/v1/budgets",
            json={"month": M0, "category_id": food["id"], "assigned": 30000},
            headers=h,
        )
    ).json()
    assert b["to_budget"] == 70000
    row = next(c for c in b["categories"] if c["category_id"] == food["id"])
    assert row["assigned"] == 30000
    assert row["available"] == 30000

    r = await client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "date": TODAY.isoformat(),
            "amount": -12050,
            "category_id": food["id"],
            "payee": "Migros",
        },
        headers=h,
    )
    assert r.status_code == 201

    b = (await client.get("/api/v1/budgets", headers=h)).json()
    row = next(c for c in b["categories"] if c["category_id"] == food["id"])
    assert row["activity"] == -12050
    assert row["available"] == 17950
    assert b["to_budget"] == 70000  # spending does not change to-budget


async def test_income_category_flows_into_to_budget(client):
    h, acc, _food, _fun, salary = await _setup(client)
    await client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "date": TODAY.isoformat(),
            "amount": 500000,
            "category_id": salary["id"],
            "payee": "Lohn",
        },
        headers=h,
    )
    b = (await client.get("/api/v1/budgets", headers=h)).json()
    assert b["to_budget"] == 600000
    assert b["income"] == 600000  # opening balance + salary this month


async def test_rollover_and_reset_semantics(client):
    h, acc, food, fun, _salary = await _setup(client)

    # food keeps leftovers (default), fun returns them to "to budget"
    r = await client.patch(f"/api/v1/categories/{fun['id']}", json={"rollover": False}, headers=h)
    assert r.json()["rollover"] is False

    await client.put(
        "/api/v1/budgets", json={"month": M0, "category_id": food["id"], "assigned": 20000}, headers=h
    )
    b0 = (
        await client.put(
            "/api/v1/budgets", json={"month": M0, "category_id": fun["id"], "assigned": 10000}, headers=h
        )
    ).json()
    assert b0["to_budget"] == 70000

    b1 = (await client.get("/api/v1/budgets", params={"month": M1}, headers=h)).json()
    food_row = next(c for c in b1["categories"] if c["category_id"] == food["id"])
    fun_row = next(c for c in b1["categories"] if c["category_id"] == fun["id"])
    assert food_row["available"] == 20000  # carried over
    assert fun_row["available"] == 0  # reset
    assert b1["to_budget"] == 80000  # 70000 + 10000 returned by fun


async def test_overspend_flag_notification_and_move(client):
    h, acc, food, fun, _salary = await _setup(client)
    await client.put(
        "/api/v1/budgets", json={"month": M0, "category_id": food["id"], "assigned": 5000}, headers=h
    )
    await client.post(
        "/api/v1/transactions",
        json={"account_id": acc["id"], "date": TODAY.isoformat(), "amount": -10000, "category_id": food["id"]},
        headers=h,
    )
    b = (await client.get("/api/v1/budgets", headers=h)).json()
    row = next(c for c in b["categories"] if c["category_id"] == food["id"])
    assert row["available"] == -5000
    assert b["overspent_count"] == 1

    notes = (await client.get("/api/v1/notifications", headers=h)).json()
    assert any(n["type"] == "budget_overspent" for n in notes["items"])
    assert notes["unread_count"] >= 1

    # move 50.00 from fun to cover it
    await client.put(
        "/api/v1/budgets", json={"month": M0, "category_id": fun["id"], "assigned": 10000}, headers=h
    )
    b = (
        await client.post(
            "/api/v1/budgets/move",
            json={"month": M0, "from_category_id": fun["id"], "to_category_id": food["id"], "amount": 5000},
            headers=h,
        )
    ).json()
    food_row = next(c for c in b["categories"] if c["category_id"] == food["id"])
    fun_row = next(c for c in b["categories"] if c["category_id"] == fun["id"])
    assert food_row["assigned"] == 10000
    assert food_row["available"] == 0
    assert fun_row["assigned"] == 5000

    # move from "to budget" into a category
    before = b["to_budget"]
    b = (
        await client.post(
            "/api/v1/budgets/move",
            json={"month": M0, "from_category_id": None, "to_category_id": food["id"], "amount": 1000},
            headers=h,
        )
    ).json()
    assert b["to_budget"] == before - 1000


async def test_autofill_suggestions_and_apply(client):
    h, acc, food, _fun, _salary = await _setup(client)
    for i in (1, 2, 3):
        d = month_bounds(month_add(M0, -i))[0].isoformat()
        await client.post(
            "/api/v1/transactions",
            json={"account_id": acc["id"], "date": d, "amount": -9000, "category_id": food["id"]},
            headers=h,
        )

    r = await client.get("/api/v1/budgets/autofill", headers=h)
    suggestions = r.json()["suggestions"]
    entry = next(s for s in suggestions if s["category_id"] == food["id"])
    assert entry["suggested"] == 9000  # avg of three months, rounded to whole francs

    b = (
        await client.post("/api/v1/budgets/autofill/apply", json={"month": M0}, headers=h)
    ).json()
    row = next(c for c in b["categories"] if c["category_id"] == food["id"])
    assert row["assigned"] == 9000

    # applying again must not override manual values
    await client.put(
        "/api/v1/budgets", json={"month": M0, "category_id": food["id"], "assigned": 12345}, headers=h
    )
    b = (
        await client.post("/api/v1/budgets/autofill/apply", json={"month": M0}, headers=h)
    ).json()
    row = next(c for c in b["categories"] if c["category_id"] == food["id"])
    assert row["assigned"] == 12345


async def test_budgeting_income_category_rejected(client):
    h, _acc, _food, _fun, salary = await _setup(client)
    r = await client.put(
        "/api/v1/budgets", json={"month": M0, "category_id": salary["id"], "assigned": 1000}, headers=h
    )
    assert r.status_code == 422
