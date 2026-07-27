from __future__ import annotations

import os
import tempfile

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="revly-test-"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.db import Base, get_db
from app.core.security import login_rate_limiter
from app.main import create_app


@pytest.fixture
async def db_setup():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, factory
    await engine.dispose()


@pytest.fixture
async def session_factory(db_setup):
    return db_setup[1]


@pytest.fixture
async def client(db_setup):
    _engine, factory = db_setup

    async def override_get_db():
        async with factory() as session:
            yield session

    app = create_app(serve_static=False, with_scheduler=False)
    app.dependency_overrides[get_db] = override_get_db
    login_rate_limiter._hits.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def register_user(
    client: AsyncClient,
    email: str = "julian@example.com",
    name: str = "Julian",
    password: str = "supersecret1",
    **extra,
) -> dict:
    payload = {"email": email, "password": password, "name": name, **extra}
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def auth_headers(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def make_account(client: AsyncClient, headers: dict, name: str = "Giro", **kw) -> dict:
    r = await client.post("/api/v1/accounts", json={"name": name, **kw}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def get_categories(client: AsyncClient, headers: dict) -> list[dict]:
    r = await client.get("/api/v1/categories", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()
