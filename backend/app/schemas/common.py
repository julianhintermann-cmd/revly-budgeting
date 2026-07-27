from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _serialize_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


# DB timestamps are naive UTC; serialize them with an explicit Z suffix.
UTCDateTime = Annotated[datetime, PlainSerializer(_serialize_utc, return_type=str, when_used="json")]

Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
