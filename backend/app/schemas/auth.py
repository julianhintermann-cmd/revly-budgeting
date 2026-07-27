from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserOut


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    household_name: str | None = Field(default=None, max_length=120)
    currency: str = Field(default="CHF", min_length=3, max_length=3)
    invite_code: str | None = None
    locale: str = Field(default="de", pattern="^(de|en)$")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class TwoFARequired(BaseModel):
    requires_2fa: bool = True
    temp_token: str


class RefreshIn(BaseModel):
    refresh_token: str


class TwoFAVerifyIn(BaseModel):
    temp_token: str
    code: str = Field(min_length=6, max_length=8)


class TwoFASetupOut(BaseModel):
    secret: str
    otpauth_uri: str


class TwoFACodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)
