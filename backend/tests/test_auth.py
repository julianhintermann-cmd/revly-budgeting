from __future__ import annotations

import pyotp
from conftest import auth_headers, register_user

EMAIL = "julian@example.com"
PASSWORD = "supersecret1"


async def test_register_and_login(client):
    data = await register_user(client)
    assert data["user"]["email"] == EMAIL
    assert data["user"]["is_admin"] is True  # first user becomes instance admin
    assert data["user"]["active_household_id"] is not None
    assert data["access_token"] and data["refresh_token"]

    r = await client.post(
        "/api/v1/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": "Dup"}
    )
    assert r.status_code == 409

    r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert "access_token" in r.json()

    r = await client.get("/api/v1/users/me", headers=auth_headers(data))
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL

    r = await client.get("/api/v1/users/me")
    assert r.status_code in (401, 403)


async def test_login_rate_limit(client):
    await register_user(client)
    for _ in range(5):
        r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong-pass"})
        assert r.status_code == 401
    r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong-pass"})
    assert r.status_code == 429


async def test_refresh_rotation_and_reuse_detection(client):
    data = await register_user(client)
    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r1.status_code == 200
    assert r1.json()["refresh_token"] != data["refresh_token"]

    # Reusing the rotated-out token must fail and revoke the whole family.
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r2.status_code == 401
    r3 = await client.post("/api/v1/auth/refresh", json={"refresh_token": r1.json()["refresh_token"]})
    assert r3.status_code == 401


async def test_2fa_flow(client):
    data = await register_user(client)
    h = auth_headers(data)

    r = await client.post("/api/v1/auth/2fa/setup", headers=h)
    assert r.status_code == 200
    secret = r.json()["secret"]
    assert "otpauth://" in r.json()["otpauth_uri"]

    r = await client.post(
        "/api/v1/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=h
    )
    assert r.status_code == 204

    r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    body = r.json()
    assert body.get("requires_2fa") is True

    r = await client.post(
        "/api/v1/auth/2fa/verify",
        json={"temp_token": body["temp_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert r.status_code == 200
    assert "access_token" in r.json()

    r = await client.post(
        "/api/v1/auth/2fa/disable", json={"code": pyotp.TOTP(secret).now()}, headers=h
    )
    assert r.status_code == 204
    r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert "access_token" in r.json()


async def test_password_change_revokes_sessions(client):
    data = await register_user(client)
    h = auth_headers(data)

    r = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": "nope-wrong", "new_password": "evenmoresecret2"},
        headers=h,
    )
    assert r.status_code == 422

    r = await client.post(
        "/api/v1/users/me/password",
        json={"current_password": PASSWORD, "new_password": "evenmoresecret2"},
        headers=h,
    )
    assert r.status_code == 204

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 401

    r = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "evenmoresecret2"})
    assert r.status_code == 200


async def test_api_tokens(client):
    data = await register_user(client)
    h = auth_headers(data)

    r = await client.post("/api/v1/users/me/tokens", json={"name": "script"}, headers=h)
    assert r.status_code == 201
    body = r.json()
    token = body["token"]
    assert token.startswith("rvb_")

    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    r = await client.delete(f"/api/v1/users/me/tokens/{body['id']}", headers=h)
    assert r.status_code == 204
    r = await client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
