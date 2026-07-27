from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token, hash_token, utcnow
from app.models import ApiToken, Household, HouseholdMember, User

bearer_scheme = HTTPBearer(auto_error=False)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized()
    token = credentials.credentials

    if token.startswith("rvb_"):
        row = await db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(token)))
        if row is None:
            raise _unauthorized("Invalid API token")
        if row.expires_at is not None and row.expires_at < utcnow().replace(tzinfo=None):
            raise _unauthorized("API token expired")
        user = await db.get(User, row.user_id)
        if user is None or not user.is_active:
            raise _unauthorized("User inactive")
        row.last_used_at = utcnow().replace(tzinfo=None)
        return user

    payload = decode_token(token, "access")
    if payload is None:
        raise _unauthorized("Invalid or expired token")
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise _unauthorized("User inactive")
    return user


@dataclass
class HouseholdCtx:
    household: Household
    role: str
    user: User


async def get_household_ctx(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HouseholdCtx:
    if user.active_household_id is None:
        raise HTTPException(status_code=400, detail="NO_HOUSEHOLD")
    member = await db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == user.active_household_id,
            HouseholdMember.user_id == user.id,
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Not a member of this household")
    household = await db.get(Household, user.active_household_id)
    if household is None:
        raise HTTPException(status_code=400, detail="NO_HOUSEHOLD")
    return HouseholdCtx(household=household, role=member.role, user=user)


async def require_editor(ctx: HouseholdCtx = Depends(get_household_ctx)) -> HouseholdCtx:
    if ctx.role not in ("owner", "editor"):
        raise HTTPException(status_code=403, detail="Requires editor role")
    return ctx


async def require_owner(ctx: HouseholdCtx = Depends(get_household_ctx)) -> HouseholdCtx:
    if ctx.role != "owner":
        raise HTTPException(status_code=403, detail="Requires owner role")
    return ctx


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Requires instance admin")
    return user
