from __future__ import annotations

from pydantic import BaseModel, Field


class ImportPreviewOut(BaseModel):
    cache_id: str
    format: str
    columns: list[str]
    # First rows for the mapping assistant (raw values for csv, normalized for ofx/qif).
    rows: list[dict[str, str]]
    row_count: int


class ColumnMapping(BaseModel):
    date: str
    amount: str
    payee: str | None = None
    notes: str | None = None


class ImportCommitIn(BaseModel):
    cache_id: str
    account_id: int
    mapping: ColumnMapping | None = None
    date_format: str | None = Field(default=None, max_length=20)
    # None = auto-detect per value
    decimal_comma: bool | None = None
    invert_amounts: bool = False
    skip_duplicates: bool = True
    default_category_id: int | None = None


class ImportResultOut(BaseModel):
    imported: int
    duplicates_skipped: int
    errors: int
