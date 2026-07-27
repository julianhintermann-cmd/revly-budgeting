from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import UTCDateTime


class HouseholdOut(BaseModel):
    id: int
    name: str
    currency: str
    role: str
    member_count: int


class HouseholdCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    currency: str = Field(default="CHF", min_length=3, max_length=3)


class HouseholdUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class MemberOut(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    role: str


class MemberRoleIn(BaseModel):
    role: str = Field(pattern="^(owner|editor|viewer)$")


class InviteCreateIn(BaseModel):
    role: str = Field(default="editor", pattern="^(owner|editor|viewer)$")
    expires_days: int = Field(default=7, ge=1, le=90)


class InviteOut(BaseModel):
    id: int
    code: str
    role: str
    expires_at: UTCDateTime
    used: bool


class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=32)
