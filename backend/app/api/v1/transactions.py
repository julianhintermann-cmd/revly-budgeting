from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx, require_editor
from app.core.db import get_db
from app.models import Tag, Transaction, TransactionSplit, TransactionTag
from app.schemas.transaction import (
    BulkActionIn,
    BulkActionOut,
    TransactionCreateIn,
    TransactionListOut,
    TransactionOut,
    TransactionUpdateIn,
)
from app.services import transactions as txn_service
from app.services.budgets import month_of

router = APIRouter(prefix="/transactions", tags=["transactions"])

MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".pdf": "application/pdf"}


def _affected(txn: Transaction) -> set[tuple[int | None, str]]:
    month = month_of(txn.date)
    pairs: set[tuple[int | None, str]] = {(txn.category_id, month)}
    for split in txn.splits:
        pairs.add((split.category_id, month))
    return pairs


def _apply_filters(
    stmt: Select,
    *,
    household_id: int,
    q: str | None,
    account_id: int | None,
    category_id: int | None,
    tag: str | None,
    status: str | None,
    type_: str | None,
    date_from: date | None,
    date_to: date | None,
    min_amount: int | None,
    max_amount: int | None,
    uncategorized: bool,
) -> Select:
    stmt = stmt.where(Transaction.household_id == household_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Transaction.payee.ilike(like), Transaction.notes.ilike(like)))
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        split_match = select(TransactionSplit.transaction_id).where(
            TransactionSplit.category_id == category_id
        )
        stmt = stmt.where(
            or_(Transaction.category_id == category_id, Transaction.id.in_(split_match))
        )
    if uncategorized:
        stmt = stmt.where(
            Transaction.category_id.is_(None),
            Transaction.is_split.is_(False),
            Transaction.transfer_group.is_(None),
        )
    if tag:
        tag_match = (
            select(TransactionTag.transaction_id)
            .join(Tag, Tag.id == TransactionTag.tag_id)
            .where(Tag.name == tag)
        )
        stmt = stmt.where(Transaction.id.in_(tag_match))
    if status:
        stmt = stmt.where(Transaction.status == status)
    if type_ == "in":
        stmt = stmt.where(Transaction.amount > 0)
    elif type_ == "out":
        stmt = stmt.where(Transaction.amount < 0)
    if date_from:
        stmt = stmt.where(Transaction.date >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.date <= date_to)
    if min_amount is not None:
        stmt = stmt.where(func.abs(Transaction.amount) >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(func.abs(Transaction.amount) <= max_amount)
    return stmt


@router.get("", response_model=TransactionListOut)
async def list_transactions(
    q: str | None = None,
    account_id: int | None = None,
    category_id: int | None = None,
    tag: str | None = None,
    status: str | None = Query(default=None, pattern="^(pending|cleared|reconciled)$"),
    type_: str | None = Query(default=None, alias="type", pattern="^(in|out)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: int | None = None,
    max_amount: int | None = None,
    uncategorized: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    ctx: HouseholdCtx = Depends(get_household_ctx),
    db: AsyncSession = Depends(get_db),
) -> TransactionListOut:
    filters = dict(
        household_id=ctx.household.id,
        q=q,
        account_id=account_id,
        category_id=category_id,
        tag=tag,
        status=status,
        type_=type_,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        uncategorized=uncategorized,
    )
    base = _apply_filters(select(Transaction), **filters)
    total = await db.scalar(
        _apply_filters(select(func.count(Transaction.id)), **filters)
    )
    sum_amount = await db.scalar(
        _apply_filters(select(func.coalesce(func.sum(Transaction.amount), 0)), **filters)
    )
    rows = (
        await db.execute(
            base.order_by(Transaction.date.desc(), Transaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    tags_map = await txn_service.tags_for_transactions(db, [t.id for t in rows])
    return TransactionListOut(
        items=[txn_service.txn_to_out(t, tags_map.get(t.id, [])) for t in rows],
        total=total or 0,
        page=page,
        page_size=page_size,
        sum_amount=sum_amount or 0,
    )


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(
    payload: TransactionCreateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> TransactionOut:
    txn = await txn_service.create_transaction(db, ctx.household, ctx.user, payload)
    await txn_service.post_effects(
        db, ctx.household, ctx.user.locale, _affected(txn), {txn.account_id}
    )
    await db.commit()
    tags_map = await txn_service.tags_for_transactions(db, [txn.id])
    return txn_service.txn_to_out(txn, tags_map.get(txn.id, []))


@router.get("/{txn_id}", response_model=TransactionOut)
async def get_transaction(
    txn_id: int, ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> TransactionOut:
    txn = await txn_service.get_transaction(db, ctx.household.id, txn_id)
    tags_map = await txn_service.tags_for_transactions(db, [txn.id])
    return txn_service.txn_to_out(txn, tags_map.get(txn.id, []))


@router.patch("/{txn_id}", response_model=TransactionOut)
async def update_transaction(
    txn_id: int,
    payload: TransactionUpdateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> TransactionOut:
    before = await txn_service.get_transaction(db, ctx.household.id, txn_id)
    affected = _affected(before)
    accounts = {before.account_id}
    txn = await txn_service.update_transaction(db, ctx.household, txn_id, payload)
    affected |= _affected(txn)
    accounts.add(txn.account_id)
    await txn_service.post_effects(db, ctx.household, ctx.user.locale, affected, accounts)
    await db.commit()
    tags_map = await txn_service.tags_for_transactions(db, [txn.id])
    return txn_service.txn_to_out(txn, tags_map.get(txn.id, []))


@router.delete("/{txn_id}", status_code=204)
async def delete_transaction(
    txn_id: int, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> None:
    await txn_service.delete_transaction(db, ctx.household.id, txn_id)
    await db.commit()


@router.post("/bulk", response_model=BulkActionOut)
async def bulk_action(
    payload: BulkActionIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> BulkActionOut:
    affected = 0
    skipped = 0
    touched: set[tuple[int | None, str]] = set()
    touched_accounts: set[int] = set()

    if payload.action == "set_category" and payload.category_id is not None:
        await txn_service._check_category(db, ctx.household.id, payload.category_id)

    for txn_id in payload.ids:
        txn = await db.scalar(
            select(Transaction).where(
                Transaction.id == txn_id, Transaction.household_id == ctx.household.id
            )
        )
        if txn is None:
            skipped += 1
            continue
        touched |= _affected(txn)
        touched_accounts.add(txn.account_id)

        if payload.action == "delete":
            await txn_service.delete_transaction(db, ctx.household.id, txn.id)
            affected += 1
        elif payload.action == "set_category":
            if txn.transfer_group or txn.is_split:
                skipped += 1
                continue
            txn.category_id = payload.category_id
            touched.add((payload.category_id, month_of(txn.date)))
            affected += 1
        elif payload.action == "set_status":
            if not payload.status:
                raise HTTPException(status_code=422, detail="status required")
            txn.status = payload.status
            affected += 1
        elif payload.action in ("add_tag", "remove_tag"):
            if not payload.tag:
                raise HTTPException(status_code=422, detail="tag required")
            current = (await txn_service.tags_for_transactions(db, [txn.id])).get(txn.id, [])
            if payload.action == "add_tag":
                if payload.tag not in current:
                    current.append(payload.tag)
            else:
                current = [t for t in current if t != payload.tag]
            await txn_service._apply_tags(db, ctx.household.id, txn.id, current)
            affected += 1

    await txn_service.post_effects(db, ctx.household, ctx.user.locale, touched, touched_accounts)
    await db.commit()
    return BulkActionOut(affected=affected, skipped=skipped)


@router.post("/{txn_id}/receipt", response_model=TransactionOut)
async def upload_receipt(
    txn_id: int,
    file: UploadFile,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> TransactionOut:
    txn = await txn_service.save_receipt(db, ctx.household.id, txn_id, file)
    await db.commit()
    tags_map = await txn_service.tags_for_transactions(db, [txn.id])
    return txn_service.txn_to_out(txn, tags_map.get(txn.id, []))


@router.get("/{txn_id}/receipt")
async def download_receipt(
    txn_id: int, ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> FileResponse:
    txn = await txn_service.get_transaction(db, ctx.household.id, txn_id)
    path = txn_service.receipt_file(txn)
    media = MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, filename=path.name)
