from __future__ import annotations

import uuid
from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    login_rate_limiter,
    utcnow,
    verify_password,
)
from app.models import Household, HouseholdInvite, HouseholdMember, RefreshToken, User
from app.schemas.auth import (
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    TwoFACodeIn,
    TwoFARequired,
    TwoFASetupOut,
    TwoFAVerifyIn,
)
from app.schemas.user import UserOut
from app.api.v1.deps import client_ip, get_current_user
from app.services import audit
from app.services.common import t
from app.services.notify import notify
from app.services.seed import seed_household

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_pair(db: AsyncSession, user: User) -> TokenPair:
    settings = get_settings()
    access = create_token(user.id, "access", timedelta(minutes=settings.access_token_minutes))
    jti = str(uuid.uuid4())
    refresh = create_token(user.id, "refresh", timedelta(days=settings.refresh_token_days), {"jti": jti})
    db.add(
        RefreshToken(
            jti=jti,
            user_id=user.id,
            expires_at=(utcnow() + timedelta(days=settings.refresh_token_days)).replace(tzinfo=None),
        )
    )
    await db.flush()
    return TokenPair(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/register", response_model=TokenPair, status_code=201)
async def register(payload: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)) -> TokenPair:
    email = payload.email.lower().strip()
    existing = await db.scalar(select(User.id).where(User.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    first_user = (await db.scalar(select(func.count(User.id)))) == 0
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        locale=payload.locale,
        is_admin=first_user,
    )
    db.add(user)
    await db.flush()

    if payload.invite_code:
        invite = await db.scalar(
            select(HouseholdInvite).where(HouseholdInvite.code == payload.invite_code.strip())
        )
        if (
            invite is None
            or invite.used_by is not None
            or invite.expires_at < utcnow().replace(tzinfo=None)
        ):
            raise HTTPException(status_code=422, detail="Invite code is invalid or expired")
        db.add(HouseholdMember(household_id=invite.household_id, user_id=user.id, role=invite.role))
        invite.used_by = user.id
        user.active_household_id = invite.household_id
        await notify(
            db,
            invite.household_id,
            "member_joined",
            t(payload.locale, "member_joined_title", name=user.name),
            t(payload.locale, "member_joined_body", name=user.name),
        )
    else:
        household = Household(
            name=payload.household_name or f"{user.name} – Haushalt",
            currency=payload.currency.upper(),
        )
        db.add(household)
        await db.flush()
        db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
        await seed_household(db, household.id, household.currency, payload.locale)
        user.active_household_id = household.id

    await audit.log(db, "register", user_id=user.id, ip=client_ip(request))
    pair = await _issue_pair(db, user)
    await db.commit()
    return pair


@router.post("/login", response_model=TokenPair | TwoFARequired)
async def login(payload: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    email = payload.email.lower().strip()
    ip = client_ip(request)
    rate_key = f"login:{ip}:{email}"
    if not login_rate_limiter.allow(rate_key, limit=5, window_seconds=300):
        raise HTTPException(status_code=429, detail="Too many login attempts; try again later")

    user = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash if user else None):
        await audit.log(db, "login_failed", ip=ip, details=email)
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    if user.totp_enabled:
        temp = create_token(user.id, "2fa", timedelta(minutes=5))
        return TwoFARequired(temp_token=temp)

    login_rate_limiter.reset(rate_key)
    await audit.log(db, "login", user_id=user.id, ip=ip)
    pair = await _issue_pair(db, user)
    await db.commit()
    return pair


@router.post("/2fa/verify", response_model=TokenPair)
async def verify_2fa(payload: TwoFAVerifyIn, request: Request, db: AsyncSession = Depends(get_db)) -> TokenPair:
    ip = client_ip(request)
    data = decode_token(payload.temp_token, "2fa")
    if data is None:
        raise HTTPException(status_code=401, detail="2FA session expired; log in again")
    if not login_rate_limiter.allow(f"2fa:{ip}:{data['sub']}", limit=8, window_seconds=300):
        raise HTTPException(status_code=429, detail="Too many attempts; try again later")
    user = await db.get(User, int(data["sub"]))
    if user is None or not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=401, detail="2FA not active")
    if not pyotp.TOTP(user.totp_secret).verify(payload.code.replace(" ", ""), valid_window=1):
        await audit.log(db, "2fa_failed", user_id=user.id, ip=ip)
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid 2FA code")
    await audit.log(db, "login", user_id=user.id, ip=ip, details="2fa")
    pair = await _issue_pair(db, user)
    await db.commit()
    return pair


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshIn, db: AsyncSession = Depends(get_db)) -> TokenPair:
    data = decode_token(payload.refresh_token, "refresh")
    if data is None or "jti" not in data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    row = await db.get(RefreshToken, data["jti"])
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if row.revoked:
        # Reuse of a rotated token: revoke everything for this user.
        await db.execute(
            update(RefreshToken).where(RefreshToken.user_id == row.user_id).values(revoked=True)
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected; log in again")
    if row.expires_at < utcnow().replace(tzinfo=None):
        raise HTTPException(status_code=401, detail="Refresh token expired")
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    row.revoked = True
    pair = await _issue_pair(db, user)
    await db.commit()
    return pair


@router.post("/logout", status_code=204)
async def logout(payload: RefreshIn, db: AsyncSession = Depends(get_db)) -> None:
    data = decode_token(payload.refresh_token, "refresh")
    if data and "jti" in data:
        row = await db.get(RefreshToken, data["jti"])
        if row:
            row.revoked = True
            await db.commit()


@router.post("/2fa/setup", response_model=TwoFASetupOut)
async def setup_2fa(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> TwoFASetupOut:
    if user.totp_enabled:
        raise HTTPException(status_code=409, detail="2FA already enabled")
    secret = pyotp.random_base32()
    user.totp_secret = secret
    await db.commit()
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="revly-budgeting")
    return TwoFASetupOut(secret=secret, otpauth_uri=uri)


@router.post("/2fa/enable", status_code=204)
async def enable_2fa(
    payload: TwoFACodeIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Run 2FA setup first")
    if not pyotp.TOTP(user.totp_secret).verify(payload.code.replace(" ", ""), valid_window=1):
        raise HTTPException(status_code=422, detail="Invalid 2FA code")
    user.totp_enabled = True
    await audit.log(db, "2fa_enabled", user_id=user.id, ip=client_ip(request))
    await db.commit()


@router.post("/2fa/disable", status_code=204)
async def disable_2fa(
    payload: TwoFACodeIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    if not pyotp.TOTP(user.totp_secret).verify(payload.code.replace(" ", ""), valid_window=1):
        raise HTTPException(status_code=422, detail="Invalid 2FA code")
    user.totp_enabled = False
    user.totp_secret = None
    await audit.log(db, "2fa_disabled", user_id=user.id, ip=client_ip(request))
    await db.commit()
