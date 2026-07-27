from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def log(
    db: AsyncSession,
    action: str,
    *,
    user_id: int | None = None,
    household_id: int | None = None,
    ip: str = "",
    details: str = "",
) -> None:
    db.add(AuditLog(action=action, user_id=user_id, household_id=household_id, ip=ip[:64], details=details[:2000]))
