from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx
from app.core.db import get_db
from app.models import Notification
from app.schemas.notification import MarkReadIn, NotificationListOut, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _visible(ctx: HouseholdCtx):
    return (
        Notification.household_id == ctx.household.id,
        or_(Notification.user_id.is_(None), Notification.user_id == ctx.user.id),
    )


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> NotificationListOut:
    rows = (
        await db.execute(
            select(Notification).where(*_visible(ctx)).order_by(Notification.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    unread = await db.scalar(
        select(func.count(Notification.id)).where(*_visible(ctx), Notification.read.is_(False))
    )
    return NotificationListOut(
        items=[
            NotificationOut(
                id=n.id,
                type=n.type,
                title=n.title,
                body=n.body,
                data=n.data,
                read=n.read,
                created_at=n.created_at,
            )
            for n in rows
        ],
        unread_count=unread or 0,
    )


@router.post("/read")
async def mark_read(
    payload: MarkReadIn, ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> dict:
    stmt = update(Notification).where(*_visible(ctx)).values(read=True)
    if not payload.all:
        ids = payload.ids or []
        if not ids:
            return {"updated": 0}
        stmt = stmt.where(Notification.id.in_(ids))
    result = await db.execute(stmt)
    await db.commit()
    return {"updated": result.rowcount or 0}
