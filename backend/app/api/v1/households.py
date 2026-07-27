from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import client_ip, get_current_user
from app.core.db import get_db
from app.core.security import utcnow
from app.models import Household, HouseholdInvite, HouseholdMember, User
from app.schemas.household import (
    HouseholdCreateIn,
    HouseholdOut,
    HouseholdUpdateIn,
    InviteCreateIn,
    InviteOut,
    JoinIn,
    MemberOut,
    MemberRoleIn,
)
from app.services import audit
from app.services.common import t
from app.services.notify import notify
from app.services.seed import seed_household

router = APIRouter(prefix="/households", tags=["households"])


async def _role_of(db: AsyncSession, household_id: int, user_id: int) -> str | None:
    return await db.scalar(
        select(HouseholdMember.role).where(
            HouseholdMember.household_id == household_id, HouseholdMember.user_id == user_id
        )
    )


async def _member_count(db: AsyncSession, household_id: int) -> int:
    return (
        await db.scalar(
            select(func.count(HouseholdMember.id)).where(HouseholdMember.household_id == household_id)
        )
    ) or 0


async def _require_owner(db: AsyncSession, household_id: int, user: User) -> None:
    if await _role_of(db, household_id, user.id) != "owner":
        raise HTTPException(status_code=403, detail="Requires owner role")


@router.get("", response_model=list[HouseholdOut])
async def list_households(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[HouseholdOut]:
    rows = (
        await db.execute(
            select(Household, HouseholdMember.role)
            .join(HouseholdMember, HouseholdMember.household_id == Household.id)
            .where(HouseholdMember.user_id == user.id)
            .order_by(Household.id)
        )
    ).all()
    out = []
    for household, role in rows:
        out.append(
            HouseholdOut(
                id=household.id,
                name=household.name,
                currency=household.currency,
                role=role,
                member_count=await _member_count(db, household.id),
            )
        )
    return out


@router.post("", response_model=HouseholdOut, status_code=201)
async def create_household(
    payload: HouseholdCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HouseholdOut:
    household = Household(name=payload.name, currency=payload.currency.upper())
    db.add(household)
    await db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    await seed_household(db, household.id, household.currency, user.locale)
    user.active_household_id = household.id
    await db.commit()
    return HouseholdOut(
        id=household.id, name=household.name, currency=household.currency, role="owner", member_count=1
    )


@router.patch("/{household_id}", response_model=HouseholdOut)
async def update_household(
    household_id: int,
    payload: HouseholdUpdateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HouseholdOut:
    await _require_owner(db, household_id, user)
    household = await db.get(Household, household_id)
    if household is None:
        raise HTTPException(status_code=404, detail="Household not found")
    if payload.name is not None:
        household.name = payload.name
    if payload.currency is not None:
        household.currency = payload.currency.upper()
    await db.commit()
    return HouseholdOut(
        id=household.id,
        name=household.name,
        currency=household.currency,
        role="owner",
        member_count=await _member_count(db, household.id),
    )


@router.get("/{household_id}/members", response_model=list[MemberOut])
async def list_members(
    household_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[MemberOut]:
    if await _role_of(db, household_id, user.id) is None:
        raise HTTPException(status_code=403, detail="Not a member of this household")
    rows = (
        await db.execute(
            select(HouseholdMember, User)
            .join(User, User.id == HouseholdMember.user_id)
            .where(HouseholdMember.household_id == household_id)
            .order_by(HouseholdMember.id)
        )
    ).all()
    return [
        MemberOut(id=m.id, user_id=u.id, name=u.name, email=u.email, role=m.role) for m, u in rows
    ]


async def _owner_count(db: AsyncSession, household_id: int) -> int:
    return (
        await db.scalar(
            select(func.count(HouseholdMember.id)).where(
                HouseholdMember.household_id == household_id, HouseholdMember.role == "owner"
            )
        )
    ) or 0


@router.patch("/{household_id}/members/{member_user_id}", status_code=204)
async def change_member_role(
    household_id: int,
    member_user_id: int,
    payload: MemberRoleIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_owner(db, household_id, user)
    member = await db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id, HouseholdMember.user_id == member_user_id
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner" and payload.role != "owner" and await _owner_count(db, household_id) <= 1:
        raise HTTPException(status_code=422, detail="A household needs at least one owner")
    member.role = payload.role
    await audit.log(db, "member_role_changed", user_id=user.id, household_id=household_id,
                    details=f"user {member_user_id} -> {payload.role}")
    await db.commit()


@router.delete("/{household_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    household_id: int,
    member_user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    role = await _role_of(db, household_id, user.id)
    if role != "owner" and member_user_id != user.id:
        raise HTTPException(status_code=403, detail="Requires owner role")
    member = await db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id, HouseholdMember.user_id == member_user_id
        )
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner" and await _owner_count(db, household_id) <= 1:
        raise HTTPException(status_code=422, detail="A household needs at least one owner")
    removed_user = await db.get(User, member_user_id)
    await db.delete(member)
    if removed_user and removed_user.active_household_id == household_id:
        other = await db.scalar(
            select(HouseholdMember.household_id).where(HouseholdMember.user_id == member_user_id)
        )
        removed_user.active_household_id = other
    await audit.log(db, "member_removed", user_id=user.id, household_id=household_id,
                    details=f"user {member_user_id}")
    await db.commit()


@router.post("/{household_id}/invites", response_model=InviteOut, status_code=201)
async def create_invite(
    household_id: int,
    payload: InviteCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteOut:
    await _require_owner(db, household_id, user)
    code = secrets.token_urlsafe(8)[:12]
    while await db.scalar(select(HouseholdInvite.id).where(HouseholdInvite.code == code)):
        code = secrets.token_urlsafe(8)[:12]
    invite = HouseholdInvite(
        household_id=household_id,
        code=code,
        role=payload.role,
        created_by=user.id,
        expires_at=(utcnow() + timedelta(days=payload.expires_days)).replace(tzinfo=None),
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return InviteOut(id=invite.id, code=invite.code, role=invite.role, expires_at=invite.expires_at, used=False)


@router.get("/{household_id}/invites", response_model=list[InviteOut])
async def list_invites(
    household_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[InviteOut]:
    await _require_owner(db, household_id, user)
    rows = (
        await db.execute(
            select(HouseholdInvite)
            .where(HouseholdInvite.household_id == household_id)
            .order_by(HouseholdInvite.id.desc())
        )
    ).scalars().all()
    return [
        InviteOut(id=i.id, code=i.code, role=i.role, expires_at=i.expires_at, used=i.used_by is not None)
        for i in rows
    ]


@router.delete("/{household_id}/invites/{invite_id}", status_code=204)
async def delete_invite(
    household_id: int,
    invite_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _require_owner(db, household_id, user)
    invite = await db.scalar(
        select(HouseholdInvite).where(
            HouseholdInvite.id == invite_id, HouseholdInvite.household_id == household_id
        )
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    await db.delete(invite)
    await db.commit()


@router.post("/join", response_model=HouseholdOut)
async def join_household(
    payload: JoinIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HouseholdOut:
    invite = await db.scalar(select(HouseholdInvite).where(HouseholdInvite.code == payload.code.strip()))
    if invite is None or invite.used_by is not None or invite.expires_at < utcnow().replace(tzinfo=None):
        raise HTTPException(status_code=422, detail="Invite code is invalid or expired")
    existing = await _role_of(db, invite.household_id, user.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Already a member of this household")
    db.add(HouseholdMember(household_id=invite.household_id, user_id=user.id, role=invite.role))
    invite.used_by = user.id
    user.active_household_id = invite.household_id
    household = await db.get(Household, invite.household_id)
    await notify(
        db,
        invite.household_id,
        "member_joined",
        t(user.locale, "member_joined_title", name=user.name),
        t(user.locale, "member_joined_body", name=user.name),
    )
    await audit.log(db, "household_joined", user_id=user.id, household_id=invite.household_id,
                    ip=client_ip(request))
    await db.commit()
    return HouseholdOut(
        id=household.id,
        name=household.name,
        currency=household.currency,
        role=invite.role,
        member_count=await _member_count(db, household.id),
    )
