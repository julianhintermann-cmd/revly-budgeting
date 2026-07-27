from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import client_ip, require_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.models import AppSetting, AuditLog, User
from app.schemas.admin import AuditRow, SmtpIn, SmtpOut, SmtpTestIn
from app.services import audit
from app.services.common import t
from app.services.emailer import get_smtp_config, send_email

router = APIRouter(prefix="/admin", tags=["admin"])


async def _set_setting(db: AsyncSession, key: str, value: str) -> None:
    row = await db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value


@router.get("/smtp", response_model=SmtpOut)
async def get_smtp(user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> SmtpOut:
    rows = (await db.execute(select(AppSetting))).scalars().all()
    stored = {r.key: r.value for r in rows}
    s = get_settings()
    host = stored.get("smtp_host", s.smtp_host) or ""
    password = stored.get("smtp_password", s.smtp_password) or ""
    return SmtpOut(
        host=host,
        port=int(stored.get("smtp_port") or s.smtp_port or 587),
        username=stored.get("smtp_username", s.smtp_username) or "",
        from_email=stored.get("smtp_from", s.smtp_from) or "",
        use_tls=str(stored.get("smtp_use_tls", s.smtp_use_tls)).lower() in ("1", "true", "yes"),
        has_password=bool(password),
        configured=bool(host),
    )


@router.put("/smtp", response_model=SmtpOut)
async def put_smtp(
    payload: SmtpIn,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SmtpOut:
    await _set_setting(db, "smtp_host", payload.host)
    await _set_setting(db, "smtp_port", str(payload.port))
    await _set_setting(db, "smtp_username", payload.username)
    await _set_setting(db, "smtp_from", payload.from_email)
    await _set_setting(db, "smtp_use_tls", "true" if payload.use_tls else "false")
    if payload.password is not None:
        await _set_setting(db, "smtp_password", payload.password)
    await audit.log(db, "smtp_updated", user_id=user.id, ip=client_ip(request))
    await db.commit()
    return await get_smtp(user, db)


@router.post("/smtp/test")
async def smtp_test(
    payload: SmtpTestIn, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict:
    cfg = await get_smtp_config(db)
    if cfg is None:
        raise HTTPException(status_code=422, detail="SMTP is not configured")
    to = payload.to or user.email
    ok = await send_email(cfg, to, t(user.locale, "smtp_test_subject"), t(user.locale, "smtp_test_body"))
    return {"sent": ok, "to": to}


@router.get("/audit", response_model=list[AuditRow])
async def audit_list(
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AuditRow]:
    rows = (
        await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit))
    ).scalars().all()
    return [
        AuditRow(
            id=r.id,
            user_id=r.user_id,
            household_id=r.household_id,
            action=r.action,
            ip=r.ip,
            details=r.details,
            created_at=r.created_at,
        )
        for r in rows
    ]
