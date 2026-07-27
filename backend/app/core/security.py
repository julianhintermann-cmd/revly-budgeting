from __future__ import annotations

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_ph = PasswordHasher()
# Verified against when the user does not exist, to keep timing comparable.
_DUMMY_HASH = _ph.hash("revly-dummy-password-for-timing")

_secret: str | None = None


def get_secret() -> str:
    global _secret
    if _secret is None:
        _secret = get_settings().resolve_secret_key()
    return _secret


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _ph.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_token(sub: str | int, token_type: str, lifetime: timedelta, extra: dict[str, Any] | None = None) -> str:
    payload: dict[str, Any] = {
        "sub": str(sub),
        "type": token_type,
        "iat": int(utcnow().timestamp()),
        "exp": utcnow() + lifetime,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_secret(), algorithm="HS256")


def decode_token(token: str, expected_type: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, get_secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_api_token() -> tuple[str, str, str]:
    """Returns (raw token shown once, sha256 hash for storage, display prefix)."""
    raw = "rvb_" + secrets.token_urlsafe(32)
    return raw, hash_token(raw), raw[:12]


class RateLimiter:
    """Small in-memory sliding-window limiter; sufficient for a single-process deployment."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, limit: int = 5, window_seconds: int = 300) -> bool:
        now = time.monotonic()
        hits = [t for t in self._hits.get(key, []) if now - t < window_seconds]
        if len(hits) >= limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


login_rate_limiter = RateLimiter()
