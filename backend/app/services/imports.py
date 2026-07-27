from __future__ import annotations

import csv
import io
import re
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from difflib import SequenceMatcher

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Household, Transaction, User
from app.schemas.imports import ImportCommitIn
from app.services.transactions import _check_category, compute_import_hash, get_account

MAX_ROWS = 5000
_CACHE: dict[str, dict] = {}
_CACHE_TTL = 1800
_CACHE_MAX = 20

DATE_FORMATS = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y%m%d"]


def _cache_put(entry: dict) -> str:
    now = time.time()
    for key in [k for k, v in _CACHE.items() if now - v["ts"] > _CACHE_TTL]:
        _CACHE.pop(key, None)
    while len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    cache_id = uuid.uuid4().hex
    entry["ts"] = now
    _CACHE[cache_id] = entry
    return cache_id


def _cache_get(cache_id: str) -> dict:
    entry = _CACHE.get(cache_id)
    if not entry or time.time() - entry["ts"] > _CACHE_TTL:
        raise HTTPException(status_code=410, detail="Import session expired; upload the file again")
    return entry


def decode_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def parse_amount(raw: str, decimal_comma: bool | None = None) -> int:
    s = raw.strip().replace(" ", "").replace(" ", "").replace("'", "")
    s = re.sub(r"[A-Za-z€$£]", "", s).strip()
    if not s:
        raise ValueError("empty amount")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if decimal_comma is None:
        if "," in s and "." in s:
            decimal_comma = s.rfind(",") > s.rfind(".")
        elif "," in s:
            decimal_comma = len(s) - s.rfind(",") - 1 <= 2
        else:
            decimal_comma = False
    if decimal_comma:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        value = Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount {raw!r}") from exc
    if negative:
        value = -value
    return int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def parse_date_value(raw: str, fmt: str | None = None) -> date:
    s = raw.strip()
    formats = ([fmt] if fmt else []) + DATE_FORMATS
    for f in formats:
        try:
            return datetime.strptime(s, f).date()
        except (ValueError, TypeError):
            continue
    m = re.match(r"^(\d{1,2})/(\d{1,2})'(\d{2})$", s)  # QIF 03/27'24
    if m:
        return date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
    raise ValueError(f"unknown date format {raw!r}")


def parse_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        first_line = sample.splitlines()[0] if sample.splitlines() else ""
        delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    columns = [c.strip() for c in (reader.fieldnames or []) if c and c.strip()]
    rows: list[dict[str, str]] = []
    for raw in reader:
        row = {k.strip(): (v or "").strip() for k, v in raw.items() if isinstance(k, str) and k.strip()}
        if any(row.values()):
            rows.append(row)
        if len(rows) >= MAX_ROWS:
            break
    return columns, rows


def _ofx_field(block: str, name: str) -> str:
    m = re.search(rf"<{name}>([^<\r\n]*)", block, re.I)
    return m.group(1).strip() if m else ""


def parse_ofx(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for block in re.split(r"<STMTTRN>", text, flags=re.I)[1:]:
        block = re.split(r"</STMTTRN>", block, flags=re.I)[0]
        dt = _ofx_field(block, "DTPOSTED")[:8]
        amt = _ofx_field(block, "TRNAMT")
        if not dt or not amt:
            continue
        try:
            d = datetime.strptime(dt, "%Y%m%d").date()
            cents = parse_amount(amt, decimal_comma=False)
        except ValueError:
            continue
        payee = _ofx_field(block, "NAME") or _ofx_field(block, "PAYEE")
        memo = _ofx_field(block, "MEMO")
        rows.append(
            {"date": d.isoformat(), "amount": f"{cents / 100:.2f}", "payee": payee, "notes": memo}
        )
        if len(rows) >= MAX_ROWS:
            break
    return rows


def parse_qif(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        code, value = line[0].upper(), line[1:].strip()
        if code == "^":
            if "date" in current and "amount" in current:
                rows.append(
                    {
                        "date": current["date"],
                        "amount": current["amount"],
                        "payee": current.get("payee", ""),
                        "notes": current.get("notes", ""),
                    }
                )
            current = {}
            if len(rows) >= MAX_ROWS:
                break
            continue
        if code == "D":
            try:
                current["date"] = parse_date_value(value).isoformat()
            except ValueError:
                pass
        elif code in ("T", "U"):
            try:
                current["amount"] = f"{parse_amount(value) / 100:.2f}"
            except ValueError:
                pass
        elif code == "P":
            current["payee"] = value
        elif code == "M":
            current["notes"] = value
    return rows


def build_preview(filename: str, raw: bytes) -> dict:
    text = decode_bytes(raw)
    lower = (filename or "").lower()
    if lower.endswith((".ofx", ".qfx")) or "<OFX" in text[:2000].upper():
        fmt = "ofx"
        rows = parse_ofx(text)
        columns = ["date", "amount", "payee", "notes"]
    elif lower.endswith(".qif") or text.lstrip().startswith("!Type"):
        fmt = "qif"
        rows = parse_qif(text)
        columns = ["date", "amount", "payee", "notes"]
    else:
        fmt = "csv"
        columns, rows = parse_csv(text)
    if not rows:
        raise HTTPException(status_code=422, detail="No transactions found in the file")
    cache_id = _cache_put({"format": fmt, "columns": columns, "rows": rows})
    return {
        "cache_id": cache_id,
        "format": fmt,
        "columns": columns,
        "rows": rows[:20],
        "row_count": len(rows),
    }


async def commit_import(
    db: AsyncSession, household: Household, user: User, payload: ImportCommitIn
) -> dict:
    entry = _cache_get(payload.cache_id)
    account = await get_account(db, household.id, payload.account_id)
    if payload.default_category_id is not None:
        await _check_category(db, household.id, payload.default_category_id)

    normalized: list[dict] = []
    errors = 0
    for row in entry["rows"]:
        try:
            if entry["format"] == "csv":
                if payload.mapping is None:
                    raise HTTPException(status_code=422, detail="Column mapping required for CSV import")
                d = parse_date_value(row.get(payload.mapping.date, ""), payload.date_format)
                amount = parse_amount(row.get(payload.mapping.amount, ""), payload.decimal_comma)
                payee = row.get(payload.mapping.payee, "") if payload.mapping.payee else ""
                notes = row.get(payload.mapping.notes, "") if payload.mapping.notes else ""
            else:
                d = date.fromisoformat(row["date"])
                amount = parse_amount(row["amount"], decimal_comma=False)
                payee = row.get("payee", "")
                notes = row.get("notes", "")
            if payload.invert_amounts:
                amount = -amount
            normalized.append({"date": d, "amount": amount, "payee": payee[:200], "notes": notes[:2000]})
        except HTTPException:
            raise
        except (ValueError, KeyError):
            errors += 1

    if not normalized:
        return {"imported": 0, "duplicates_skipped": 0, "errors": errors}

    min_date = min(n["date"] for n in normalized) - timedelta(days=3)
    max_date = max(n["date"] for n in normalized) + timedelta(days=3)
    existing = (
        await db.execute(
            select(Transaction.date, Transaction.amount, Transaction.payee, Transaction.import_hash).where(
                Transaction.account_id == account.id,
                Transaction.date >= min_date,
                Transaction.date <= max_date,
            )
        )
    ).all()
    known_hashes = {e.import_hash for e in existing if e.import_hash}

    imported = 0
    duplicates = 0
    for n in normalized:
        h = compute_import_hash(household.id, account.id, n["date"], n["amount"], n["payee"])
        if payload.skip_duplicates:
            if h in known_hashes:
                duplicates += 1
                continue
            fuzzy = any(
                e.amount == n["amount"]
                and abs((e.date - n["date"]).days) <= 3
                and e.payee
                and n["payee"]
                and SequenceMatcher(None, e.payee.lower(), n["payee"].lower()).ratio() >= 0.85
                for e in existing
            )
            if fuzzy:
                duplicates += 1
                continue
        db.add(
            Transaction(
                household_id=household.id,
                account_id=account.id,
                date=n["date"],
                amount=n["amount"],
                payee=n["payee"],
                notes=n["notes"],
                category_id=payload.default_category_id,
                status="cleared",
                import_hash=h,
                created_by=user.id,
            )
        )
        known_hashes.add(h)
        imported += 1

    await db.flush()
    return {"imported": imported, "duplicates_skipped": duplicates, "errors": errors}
