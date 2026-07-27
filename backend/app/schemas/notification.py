from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str
    data: dict[str, Any] | None
    read: bool
    created_at: UTCDateTime


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int


class MarkReadIn(BaseModel):
    ids: list[int] | None = None
    all: bool = False
