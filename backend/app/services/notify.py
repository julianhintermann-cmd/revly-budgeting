from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HouseholdMember, Notification, User
from app.services.emailer import get_smtp_config, send_email

logger = logging.getLogger(__name__)


async def notify(
    db: AsyncSession,
    household_id: int,
    type_: str,
    title: str,
    body: str = "",
    *,
    user_id: int | None = None,
    dedupe_key: str | None = None,
    data: dict[str, Any] | None = None,
    email: bool = False,
) -> Notification | None:
    """Create an in-app notification; optionally fan out an email to household members.

    A duplicate dedupe_key within the household is silently skipped."""
    if dedupe_key:
        existing = await db.scalar(
            select(Notification.id).where(
                Notification.household_id == household_id, Notification.dedupe_key == dedupe_key
            )
        )
        if existing:
            return None

    notification = Notification(
        household_id=household_id,
        user_id=user_id,
        type=type_,
        title=title,
        body=body,
        data=data,
        dedupe_key=dedupe_key,
    )
    db.add(notification)
    await db.flush()

    if email:
        cfg = await get_smtp_config(db)
        if cfg:
            rows = await db.execute(
                select(User.email)
                .join(HouseholdMember, HouseholdMember.user_id == User.id)
                .where(
                    HouseholdMember.household_id == household_id,
                    User.email_notifications.is_(True),
                    User.is_active.is_(True),
                )
            )
            recipients = [r[0] for r in rows]
            if user_id is not None:
                user_email = await db.scalar(select(User.email).where(User.id == user_id))
                recipients = [user_email] if user_email else []

            async def _fanout() -> None:
                for to in recipients:
                    await send_email(cfg, to, title, body or title)

            if recipients:
                asyncio.get_running_loop().create_task(_fanout())

    return notification
