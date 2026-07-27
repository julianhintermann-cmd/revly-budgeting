from __future__ import annotations

from datetime import date

from conftest import auth_headers, get_categories, make_account, register_user

TODAY = date.today().isoformat()


async def _setup(client):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h, initial_balance=100000)
    cats = await get_categories(client, h)
    food = next(c for c in cats if c["name"] == "Lebensmittel")
    fun = next(c for c in cats if c["name"] == "Freizeit")
    return h, acc, food, fun


async def test_splits(client):
    h, acc, food, fun = await _setup(client)

    r = await client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "date": TODAY,
            "amount": -5000,
            "payee": "Warenhaus",
            "splits": [
                {"category_id": food["id"], "amount": -3000},
                {"category_id": fun["id"], "amount": -1000},
            ],
        },
        headers=h,
    )
    assert r.status_code == 422  # splits must sum to the total

    r = await client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "date": TODAY,
            "amount": -5000,
            "payee": "Warenhaus",
            "splits": [
                {"category_id": food["id"], "amount": -3000},
                {"category_id": fun["id"], "amount": -2000},
            ],
            "tags": ["wochenende"],
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    txn = r.json()
    assert txn["is_split"] is True
    assert txn["category_id"] is None
    assert len(txn["splits"]) == 2
    assert txn["tags"] == ["wochenende"]

    # category filter finds transactions via their splits
    r = await client.get("/api/v1/transactions", params={"category_id": fun["id"]}, headers=h)
    assert r.json()["total"] == 1

    # tag filter
    r = await client.get("/api/v1/transactions", params={"tag": "wochenende"}, headers=h)
    assert r.json()["total"] == 1


async def test_transfer(client):
    h, acc, food, _fun = await _setup(client)
    save = await make_account(client, h, name="Sparkonto", type="savings")

    r = await client.post(
        "/api/v1/transactions",
        json={
            "account_id": acc["id"],
            "date": TODAY,
            "amount": 5000,
            "transfer_to_account_id": save["id"],
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    src = r.json()
    assert src["amount"] == -5000
    assert src["transfer_account_id"] == save["id"]

    accounts = (await client.get("/api/v1/accounts", headers=h)).json()
    assert next(a for a in accounts if a["id"] == acc["id"])["balance"] == 95000
    assert next(a for a in accounts if a["id"] == save["id"])["balance"] == 5000

    # transfers never count as budget activity
    b = (await client.get("/api/v1/budgets", headers=h)).json()
    assert b["activity_total"] == 0

    # deleting one leg removes both
    r = await client.delete(f"/api/v1/transactions/{src['id']}", headers=h)
    assert r.status_code == 204
    r = await client.get("/api/v1/transactions", headers=h)
    assert r.json()["total"] == 0


async def test_filters_and_bulk(client):
    h, acc, food, fun = await _setup(client)
    for payee, amount in (("Migros", -1200), ("Coop", -800), ("Lohn AG", 500000)):
        r = await client.post(
            "/api/v1/transactions",
            json={"account_id": acc["id"], "date": TODAY, "amount": amount, "payee": payee},
            headers=h,
        )
        assert r.status_code == 201

    r = await client.get("/api/v1/transactions", params={"q": "migros"}, headers=h)
    assert r.json()["total"] == 1

    r = await client.get("/api/v1/transactions", params={"type": "in"}, headers=h)
    assert r.json()["total"] == 1

    r = await client.get("/api/v1/transactions", params={"uncategorized": True}, headers=h)
    ids = [t["id"] for t in r.json()["items"]]
    assert len(ids) == 3

    out_ids = [
        t["id"]
        for t in (await client.get("/api/v1/transactions", params={"type": "out"}, headers=h)).json()["items"]
    ]
    r = await client.post(
        "/api/v1/transactions/bulk",
        json={"ids": out_ids, "action": "set_category", "category_id": food["id"]},
        headers=h,
    )
    assert r.json()["affected"] == 2

    r = await client.get("/api/v1/transactions", params={"category_id": food["id"]}, headers=h)
    assert r.json()["total"] == 2

    r = await client.post(
        "/api/v1/transactions/bulk", json={"ids": out_ids, "action": "add_tag", "tag": "essen"}, headers=h
    )
    assert r.json()["affected"] == 2
    r = await client.get("/api/v1/transactions", params={"tag": "essen"}, headers=h)
    assert r.json()["total"] == 2

    r = await client.post("/api/v1/transactions/bulk", json={"ids": out_ids, "action": "delete"}, headers=h)
    assert r.json()["affected"] == 2
    r = await client.get("/api/v1/transactions", headers=h)
    assert r.json()["total"] == 1


async def test_update_transaction(client):
    h, acc, food, fun = await _setup(client)
    r = await client.post(
        "/api/v1/transactions",
        json={"account_id": acc["id"], "date": TODAY, "amount": -4000, "payee": "Restaurant"},
        headers=h,
    )
    txn = r.json()

    r = await client.patch(
        f"/api/v1/transactions/{txn['id']}",
        json={"amount": -4500, "category_id": fun["id"], "tags": ["ausgang", "date"]},
        headers=h,
    )
    body = r.json()
    assert body["amount"] == -4500
    assert body["category_id"] == fun["id"]
    assert sorted(body["tags"]) == ["ausgang", "date"]
