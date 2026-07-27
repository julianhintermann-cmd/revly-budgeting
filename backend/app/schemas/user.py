from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UTCDateTime


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    locale: str
    is_admin: bool
    totp_enabled: bool
    email_notifications: bool
    active_household_id: int | None
    created_at: UTCDateTime


class UserUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    locale: str | None = Field(default=None, pattern="^(de|en)$")
    email_notifications: bool | None = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class ActiveHouseholdIn(BaseModel):
    household_id: int


class ApiTokenOut(ORMModel):
    id: int
    name: str
    prefix: str
    last_used_at: UTCDateTime | None
    expires_at: UTCDateTime | None
    created_at: UTCDateTime


class ApiTokenCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    expires_days: int | None = Field(default=None, ge=1, le=3650)


class ApiTokenCreatedOut(ApiTokenOut):
    token: str
