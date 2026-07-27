from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


class SmtpOut(BaseModel):
    host: str
    port: int
    username: str
    from_email: str
    use_tls: bool
    has_password: bool
    configured: bool


class SmtpIn(BaseModel):
    host: str = Field(max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(default="", max_length=255)
    # None = keep the stored password.
    password: str | None = Field(default=None, max_length=255)
    from_email: str = Field(default="", max_length=255)
    use_tls: bool = True


class SmtpTestIn(BaseModel):
    to: str | None = None


class AuditRow(BaseModel):
    id: int
    user_id: int | None
    household_id: int | None
    action: str
    ip: str
    details: str
    created_at: UTCDateTime
