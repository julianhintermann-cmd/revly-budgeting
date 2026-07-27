from __future__ import annotations

from conftest import auth_headers, make_account, register_user


async def test_invites_roles_and_permissions(client):
    owner = await register_user(client)
    hid = owner["user"]["active_household_id"]
    oh = auth_headers(owner)

    r = await client.post(f"/api/v1/households/{hid}/invites", json={"role": "viewer"}, headers=oh)
    assert r.status_code == 201
    code = r.json()["code"]

    viewer = await register_user(client, email="viewer@example.com", name="Viewer", invite_code=code)
    assert viewer["user"]["active_household_id"] == hid
    vh = auth_headers(viewer)

    r = await client.get("/api/v1/accounts", headers=vh)
    assert r.status_code == 200

    r = await client.post("/api/v1/accounts", json={"name": "Konto"}, headers=vh)
    assert r.status_code == 403  # viewers are read-only

    r = await client.get(f"/api/v1/households/{hid}/members", headers=oh)
    members = r.json()
    assert len(members) == 2

    viewer_uid = viewer["user"]["id"]
    r = await client.patch(
        f"/api/v1/households/{hid}/members/{viewer_uid}", json={"role": "editor"}, headers=oh
    )
    assert r.status_code == 204
    r = await client.post("/api/v1/accounts", json={"name": "Konto"}, headers=vh)
    assert r.status_code == 201

    # invite is single use
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "supersecret1", "name": "X", "invite_code": code},
    )
    assert r.status_code == 422

    # last owner cannot be demoted
    owner_uid = owner["user"]["id"]
    r = await client.patch(
        f"/api/v1/households/{hid}/members/{owner_uid}", json={"role": "editor"}, headers=oh
    )
    assert r.status_code == 422


async def test_household_isolation(client):
    a = await register_user(client)
    b = await register_user(client, email="b@example.com", name="B")
    ah, bh = auth_headers(a), auth_headers(b)

    acc = await make_account(client, ah, name="A-Konto")
    r = await client.get(f"/api/v1/accounts/{acc['id']}", headers=bh)
    assert r.status_code == 404

    r = await client.get("/api/v1/accounts", headers=bh)
    assert all(x["id"] != acc["id"] for x in r.json())


async def test_multi_household_switch(client):
    a = await register_user(client)
    ah = auth_headers(a)
    first_hid = a["user"]["active_household_id"]

    r = await client.post("/api/v1/households", json={"name": "Zweitbudget"}, headers=ah)
    assert r.status_code == 201
    second_hid = r.json()["id"]

    me = (await client.get("/api/v1/users/me", headers=ah)).json()
    assert me["active_household_id"] == second_hid

    r = await client.get("/api/v1/households", headers=ah)
    assert {h["id"] for h in r.json()} == {first_hid, second_hid}

    r = await client.post(
        "/api/v1/users/me/active-household", json={"household_id": first_hid}, headers=ah
    )
    assert r.json()["active_household_id"] == first_hid
