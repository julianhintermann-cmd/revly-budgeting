from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import client_ip, get_current_user
from app.core.db import get_db
from app.core.security import hash_password, new_api_token, utcnow, verify_password
from app.models import ApiToken, HouseholdMember, RefreshToken, User
from app.schemas.user import (
    ActiveHouseholdIn,
    ApiTokenCreatedOut,
    ApiTokenCreateIn,
    ApiTokenOut,
    PasswordChangeIn,
    UserOut,
    UserUpdateIn,
)
from app.services import audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> User:
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.locale is not None:
        user.locale = payload.locale
    if payload.email_notifications is not None:
        user.email_notifications = payload.email_notifications
    await db.commit()
    return user


@router.post("/me/password", status_code=204)
async def change_password(
    payload: PasswordChangeIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=422, detail="Current password is wrong")
    user.password_hash = hash_password(payload.new_password)
    # Force re-login everywhere else.
    await db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True))
    await audit.log(db, "password_changed", user_id=user.id, ip=client_ip(request))
    await db.commit()


@router.post("/me/active-household", response_model=UserOut)
async def set_active_household(
    payload: ActiveHouseholdIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    member = await db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == payload.household_id, HouseholdMember.user_id == user.id
        )
    )
    if member is None:
        raise HTTPException(status_code=403, detail="Not a member of this household")
    user.active_household_id = payload.household_id
    await db.commit()
    return user


@router.get("/me/tokens", response_model=list[ApiTokenOut])
async def list_tokens(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[ApiToken]:
    rows = await db.execute(
        select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc())
    )
    return list(rows.scalars().all())


@router.post("/me/tokens", response_model=ApiTokenCreatedOut, status_code=201)
async def create_token_endpoint(
    payload: ApiTokenCreateIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiTokenCreatedOut:
    raw, token_hash, prefix = new_api_token()
    expires_at = None
    if payload.expires_days:
        expires_at = (utcnow() + timedelta(days=payload.expires_days)).replace(tzinfo=None)
    row = ApiToken(user_id=user.id, name=payload.name, token_hash=token_hash, prefix=prefix, expires_at=expires_at)
    db.add(row)
    await audit.log(db, "api_token_created", user_id=user.id, ip=client_ip(request), details=payload.name)
    await db.commit()
    await db.refresh(row)
    return ApiTokenCreatedOut(
        id=row.id,
        name=row.name,
        prefix=row.prefix,
        last_used_at=row.last_used_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
        token=raw,
    )


@router.delete("/me/tokens/{token_id}", status_code=204)
async def delete_token(
    token_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.scalar(select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(row)
    await audit.log(db, "api_token_deleted", user_id=user.id, ip=client_ip(request), details=row.name)
    await db.commit()
