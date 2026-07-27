from __future__ import annotations

from datetime import date

from conftest import auth_headers, get_categories, make_account, register_user

TODAY = date.today().isoformat()


async def test_balances_and_reconcile(client):
    data = await register_user(client)
    h = auth_headers(data)
    acc = await make_account(client, h, initial_balance=50000)
    cats = await get_categories(client, h)
    food = next(c for c in cats if c["type"] == "expense")

    r = await client.post(
        "/api/v1/transactions",
        json={"account_id": acc["id"], "date": TODAY, "amount": -1500, "category_id": food["id"]},
        headers=h,
    )
    assert r.status_code == 201
    r = await client.post(
        "/api/v1/transactions",
        json={"account_id": acc["id"], "date": TODAY, "amount": -2000, "status": "pending"},
        headers=h,
    )
    assert r.status_code == 201

    accounts = (await client.get("/api/v1/accounts", headers=h)).json()
    a = next(x for x in accounts if x["id"] == acc["id"])
    assert a["balance"] == 50000 - 1500 - 2000
    assert a["cleared_balance"] == 50000 - 1500

    # Statement says 480.00 -> adjustment of -5.00 gets created, all cleared become reconciled.
    r = await client.post(
        f"/api/v1/accounts/{acc['id']}/reconcile", json={"statement_balance": 48000}, headers=h
    )
    body = r.json()
    assert body["difference"] == -500
    assert body["adjustment_transaction_id"] is not None

    accounts = (await client.get("/api/v1/accounts", headers=h)).json()
    a = next(x for x in accounts if x["id"] == acc["id"])
    assert a["cleared_balance"] == 48000
    assert a["balance"] == 48000 - 2000  # pending stays pending

    r = await client.delete(f"/api/v1/accounts/{acc['id']}", headers=h)
    assert r.status_code == 409  # has transactions

    r = await client.patch(f"/api/v1/accounts/{acc['id']}", json={"archived": True}, headers=h)
    assert r.json()["archived"] is True

    empty = await make_account(client, h, name="Leer")
    r = await client.delete(f"/api/v1/accounts/{empty['id']}", headers=h)
    assert r.status_code == 204


async def test_exchange_rates_and_base_conversion(client):
    data = await register_user(client)
    h = auth_headers(data)

    r = await client.put(
        "/api/v1/exchange-rates", json={"rates": [{"currency": "EUR", "rate": 0.95}]}, headers=h
    )
    assert r.status_code == 200
    rates = {x["currency"]: x["rate"] for x in r.json()["rates"]}
    assert rates["EUR"] == 0.95
    assert rates["CHF"] == 1.0
    assert r.json()["base_currency"] == "CHF"

    eur = await make_account(client, h, name="EUR Konto", currency="EUR", initial_balance=10000)
    accounts = (await client.get("/api/v1/accounts", headers=h)).json()
    a = next(x for x in accounts if x["id"] == eur["id"])
    assert a["balance_base"] == 9500
