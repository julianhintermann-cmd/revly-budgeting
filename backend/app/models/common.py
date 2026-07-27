from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp. Stored without timezone for cross-dialect consistency;
    the API serializes these as UTC ISO strings."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
