from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AppSetting

logger = logging.getLogger(__name__)

SMTP_KEYS = ("smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_from", "smtp_use_tls")


async def get_smtp_config(db: AsyncSession) -> dict[str, Any] | None:
    """DB-stored settings (admin area) win over environment variables."""
    rows = (await db.execute(select(AppSetting).where(AppSetting.key.in_(SMTP_KEYS)))).scalars().all()
    stored = {r.key: r.value for r in rows}
    s = get_settings()
    cfg = {
        "host": stored.get("smtp_host", s.smtp_host) or "",
        "port": int(stored.get("smtp_port") or s.smtp_port or 587),
        "username": stored.get("smtp_username", s.smtp_username) or "",
        "password": stored.get("smtp_password", s.smtp_password) or "",
        "from_email": stored.get("smtp_from", s.smtp_from) or "revly@localhost",
        "use_tls": str(stored.get("smtp_use_tls", s.smtp_use_tls)).lower() in ("1", "true", "yes"),
    }
    return cfg if cfg["host"] else None


def _send_sync(cfg: dict[str, Any], to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = cfg["from_email"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if cfg["port"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=15) as smtp:
            if cfg["username"]:
                smtp.login(cfg["username"], cfg["password"])
            smtp.send_message(msg)
        return
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as smtp:
        if cfg["use_tls"]:
            smtp.starttls()
        if cfg["username"]:
            smtp.login(cfg["username"], cfg["password"])
        smtp.send_message(msg)


async def send_email(cfg: dict[str, Any], to: str, subject: str, body: str) -> bool:
    try:
        await asyncio.to_thread(_send_sync, cfg, to, subject, body)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False
