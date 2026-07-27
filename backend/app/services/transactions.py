from __future__ import annotations

import hashlib
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Account,
    Category,
    Household,
    SavingsGoal,
    Tag,
    Transaction,
    TransactionSplit,
    TransactionTag,
    User,
)
from app.models.common import utcnow
from app.schemas.transaction import (
    SplitOut,
    TransactionCreateIn,
    TransactionOut,
    TransactionUpdateIn,
)
from app.services import budgets as budget_service
from app.services.common import fmt_money, t
from app.services.notify import notify

ALLOWED_RECEIPT_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
}
MAX_RECEIPT_BYTES = 10 * 1024 * 1024


async def get_account(db: AsyncSession, household_id: int, account_id: int) -> Account:
    account = await db.scalar(
        select(Account).where(Account.id == account_id, Account.household_id == household_id)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


async def _check_category(db: AsyncSession, household_id: int, category_id: int) -> Category:
    cat = await db.scalar(
        select(Category).where(Category.id == category_id, Category.household_id == household_id)
    )
    if cat is None:
        raise HTTPException(status_code=422, detail="Unknown category")
    return cat


def compute_import_hash(household_id: int, account_id: int, d: date, amount: int, payee: str) -> str:
    raw = f"{household_id}|{account_id}|{d.isoformat()}|{amount}|{payee.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def balances(db: AsyncSession, household_id: int) -> tuple[list[Account], dict[int, dict[str, int]]]:
    accounts = (
        await db.execute(select(Account).where(Account.household_id == household_id).order_by(Account.id))
    ).scalars().all()
    sums = (
        await db.execute(
            select(Transaction.account_id, Transaction.status, func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.household_id == household_id)
            .group_by(Transaction.account_id, Transaction.status)
        )
    ).all()
    result = {a.id: {"balance": a.initial_balance, "cleared": a.initial_balance} for a in accounts}
    for account_id, status, total in sums:
        if account_id not in result:
            continue
        result[account_id]["balance"] += total
        if status in ("cleared", "reconciled"):
            result[account_id]["cleared"] += total
    return accounts, result


async def account_balance(db: AsyncSession, household_id: int, account_id: int) -> int:
    account = await get_account(db, household_id, account_id)
    total = await db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(Transaction.account_id == account_id)
    )
    return account.initial_balance + (total or 0)


async def tags_for_transactions(db: AsyncSession, txn_ids: list[int]) -> dict[int, list[str]]:
    if not txn_ids:
        return {}
    rows = (
        await db.execute(
            select(TransactionTag.transaction_id, Tag.name)
            .join(Tag, Tag.id == TransactionTag.tag_id)
            .where(TransactionTag.transaction_id.in_(txn_ids))
            .order_by(Tag.name)
        )
    ).all()
    out: dict[int, list[str]] = {}
    for txn_id, name in rows:
        out.setdefault(txn_id, []).append(name)
    return out


async def _apply_tags(db: AsyncSession, household_id: int, txn_id: int, names: list[str]) -> None:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()[:60]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            cleaned.append(name)

    await db.execute(delete(TransactionTag).where(TransactionTag.transaction_id == txn_id))
    if not cleaned:
        return
    existing = (
        await db.execute(select(Tag).where(Tag.household_id == household_id, Tag.name.in_(cleaned)))
    ).scalars().all()
    by_name = {t_.name: t_ for t_ in existing}
    for name in cleaned:
        tag = by_name.get(name)
        if tag is None:
            tag = Tag(household_id=household_id, name=name)
            db.add(tag)
            await db.flush()
        db.add(TransactionTag(transaction_id=txn_id, tag_id=tag.id))


def txn_to_out(txn: Transaction, tags: list[str]) -> TransactionOut:
    return TransactionOut(
        id=txn.id,
        account_id=txn.account_id,
        date=txn.date,
        amount=txn.amount,
        payee=txn.payee,
        notes=txn.notes,
        category_id=txn.category_id,
        status=txn.status,
        transfer_account_id=txn.transfer_account_id,
        transfer_group=txn.transfer_group,
        is_split=txn.is_split,
        splits=[
            SplitOut(id=s.id, category_id=s.category_id, amount=s.amount, note=s.note) for s in txn.splits
        ],
        tags=tags,
        has_receipt=txn.receipt_path is not None,
        recurring_id=txn.recurring_id,
        created_at=txn.created_at,
    )


async def create_transaction(
    db: AsyncSession, household: Household, user: User, data: TransactionCreateIn
) -> Transaction:
    hid = household.id
    account = await get_account(db, hid, data.account_id)

    if data.transfer_to_account_id is not None:
        if data.transfer_to_account_id == data.account_id:
            raise HTTPException(status_code=422, detail="Cannot transfer to the same account")
        dest = await get_account(db, hid, data.transfer_to_account_id)
        amount = abs(data.amount)
        if amount == 0:
            raise HTTPException(status_code=422, detail="Transfer amount must not be zero")
        dest_amount = amount
        if dest.currency != account.currency:
            rates = await budget_service.get_rates(db, hid)
            src_rate = rates.get(account.currency, Decimal("1"))
            dst_rate = rates.get(dest.currency, Decimal("1")) or Decimal("1")
            dest_amount = int(
                (Decimal(amount) * src_rate / dst_rate).to_integral_value(rounding=ROUND_HALF_UP)
            )
        group = str(uuid.uuid4())
        source_txn = Transaction(
            household_id=hid,
            account_id=account.id,
            date=data.date,
            amount=-amount,
            payee=data.payee or t(user.locale, "transfer_to", name=dest.name),
            notes=data.notes,
            status=data.status,
            transfer_group=group,
            transfer_account_id=dest.id,
            created_by=user.id,
        )
        dest_txn = Transaction(
            household_id=hid,
            account_id=dest.id,
            date=data.date,
            amount=dest_amount,
            payee=data.payee or t(user.locale, "transfer_from", name=account.name),
            notes=data.notes,
            status=data.status,
            transfer_group=group,
            transfer_account_id=account.id,
            created_by=user.id,
        )
        db.add_all([source_txn, dest_txn])
        await db.flush()
        return source_txn

    txn = Transaction(
        household_id=hid,
        account_id=account.id,
        date=data.date,
        amount=data.amount,
        payee=data.payee,
        notes=data.notes,
        status=data.status,
        created_by=user.id,
    )

    if data.splits:
        if len(data.splits) < 2:
            raise HTTPException(status_code=422, detail="A split needs at least two parts")
        if sum(s.amount for s in data.splits) != data.amount:
            raise HTTPException(status_code=422, detail="Split amounts must add up to the total")
        txn.is_split = True
        txn.category_id = None
        for s in data.splits:
            if s.category_id is not None:
                await _check_category(db, hid, s.category_id)
            txn.splits.append(TransactionSplit(category_id=s.category_id, amount=s.amount, note=s.note))
    elif data.category_id is not None:
        await _check_category(db, hid, data.category_id)
        txn.category_id = data.category_id

    db.add(txn)
    await db.flush()
    txn.import_hash = compute_import_hash(hid, account.id, txn.date, txn.amount, txn.payee)
    if data.tags:
        await _apply_tags(db, hid, txn.id, data.tags)
    return txn


async def get_transaction(db: AsyncSession, household_id: int, txn_id: int) -> Transaction:
    txn = await db.scalar(
        select(Transaction).where(Transaction.id == txn_id, Transaction.household_id == household_id)
    )
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn


async def _transfer_partner(db: AsyncSession, txn: Transaction) -> Transaction | None:
    if not txn.transfer_group:
        return None
    return await db.scalar(
        select(Transaction).where(
            Transaction.transfer_group == txn.transfer_group, Transaction.id != txn.id
        )
    )


async def update_transaction(
    db: AsyncSession, household: Household, txn_id: int, data: TransactionUpdateIn
) -> Transaction:
    hid = household.id
    txn = await get_transaction(db, hid, txn_id)

    if txn.transfer_group:
        if data.splits or data.category_id is not None or data.account_id is not None:
            raise HTTPException(
                status_code=422,
                detail="Transfers only support date, amount, status, payee and notes edits",
            )
        partner = await _transfer_partner(db, txn)
        if data.date is not None:
            txn.date = data.date
            if partner:
                partner.date = data.date
        if data.status is not None:
            txn.status = data.status
        if data.notes is not None:
            txn.notes = data.notes
            if partner:
                partner.notes = data.notes
        if data.payee is not None:
            txn.payee = data.payee
        if data.amount is not None:
            partner_account = await db.get(Account, partner.account_id) if partner else None
            own_account = await db.get(Account, txn.account_id)
            if partner and partner_account and own_account and partner_account.currency != own_account.currency:
                raise HTTPException(
                    status_code=422,
                    detail="Cross-currency transfers must be recreated to change the amount",
                )
            txn.amount = data.amount
            if partner:
                partner.amount = -data.amount
        await db.flush()
        return txn

    if data.account_id is not None:
        await get_account(db, hid, data.account_id)
        txn.account_id = data.account_id
    if data.date is not None:
        txn.date = data.date
    if data.amount is not None:
        txn.amount = data.amount
    if data.payee is not None:
        txn.payee = data.payee
    if data.notes is not None:
        txn.notes = data.notes
    if data.status is not None:
        txn.status = data.status

    if data.clear_category:
        txn.category_id = None
    elif data.category_id is not None:
        await _check_category(db, hid, data.category_id)
        txn.category_id = data.category_id
        if txn.is_split:
            txn.is_split = False
            txn.splits.clear()

    if data.clear_splits:
        txn.is_split = False
        txn.splits.clear()
    elif data.splits is not None:
        if len(data.splits) < 2:
            raise HTTPException(status_code=422, detail="A split needs at least two parts")
        if sum(s.amount for s in data.splits) != txn.amount:
            raise HTTPException(status_code=422, detail="Split amounts must add up to the total")
        for s in data.splits:
            if s.category_id is not None:
                await _check_category(db, hid, s.category_id)
        txn.is_split = True
        txn.category_id = None
        txn.splits.clear()
        for s in data.splits:
            txn.splits.append(TransactionSplit(category_id=s.category_id, amount=s.amount, note=s.note))

    if data.tags is not None:
        await _apply_tags(db, hid, txn.id, data.tags)

    txn.import_hash = compute_import_hash(hid, txn.account_id, txn.date, txn.amount, txn.payee)
    await db.flush()
    return txn


def _delete_receipt_file(txn: Transaction) -> None:
    if not txn.receipt_path:
        return
    path = get_settings().uploads_path / txn.receipt_path
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


async def delete_transaction(db: AsyncSession, household_id: int, txn_id: int) -> None:
    txn = await get_transaction(db, household_id, txn_id)
    partner = await _transfer_partner(db, txn)
    _delete_receipt_file(txn)
    await db.delete(txn)
    if partner:
        _delete_receipt_file(partner)
        await db.delete(partner)
    await db.flush()


async def save_receipt(db: AsyncSession, household_id: int, txn_id: int, upload: UploadFile) -> Transaction:
    txn = await get_transaction(db, household_id, txn_id)
    ext = ALLOWED_RECEIPT_TYPES.get(upload.content_type or "")
    if ext is None:
        raise HTTPException(status_code=422, detail="Only PNG, JPEG, WebP or PDF receipts are allowed")
    content = await upload.read()
    if len(content) > MAX_RECEIPT_BYTES:
        raise HTTPException(status_code=413, detail="Receipt exceeds the 10 MB limit")
    uploads = get_settings().uploads_path
    folder = uploads / f"h{household_id}"
    folder.mkdir(parents=True, exist_ok=True)
    _delete_receipt_file(txn)
    rel = f"h{household_id}/t{txn.id}{ext}"
    (uploads / rel).write_bytes(content)
    txn.receipt_path = rel
    await db.flush()
    return txn


def receipt_file(txn: Transaction) -> Path:
    if not txn.receipt_path:
        raise HTTPException(status_code=404, detail="No receipt")
    path = get_settings().uploads_path / txn.receipt_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Receipt file missing")
    return path


async def reconcile(
    db: AsyncSession, household: Household, user: User, account_id: int, statement_balance: int
) -> dict:
    account = await get_account(db, household.id, account_id)
    cleared = await db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.account_id == account.id, Transaction.status.in_(["cleared", "reconciled"])
        )
    )
    cleared_balance = account.initial_balance + (cleared or 0)
    difference = statement_balance - cleared_balance

    adjustment_id: int | None = None
    if difference != 0:
        adjustment = Transaction(
            household_id=household.id,
            account_id=account.id,
            date=date.today(),
            amount=difference,
            payee=t(user.locale, "reconcile_adjustment"),
            status="reconciled",
            created_by=user.id,
        )
        db.add(adjustment)
        await db.flush()
        adjustment_id = adjustment.id

    result = await db.execute(
        select(Transaction.id).where(Transaction.account_id == account.id, Transaction.status == "cleared")
    )
    ids = [r[0] for r in result]
    if ids:
        from sqlalchemy import update

        await db.execute(
            update(Transaction).where(Transaction.id.in_(ids)).values(status="reconciled")
        )

    return {
        "difference": difference,
        "adjustment_transaction_id": adjustment_id,
        "reconciled_count": len(ids),
        "new_balance": statement_balance,
    }


async def post_effects(
    db: AsyncSession,
    household: Household,
    locale: str,
    category_months: set[tuple[int | None, str]],
    account_ids: set[int],
) -> None:
    """After transaction mutations: overspend + savings goal notifications."""
    for category_id, month in category_months:
        if category_id is None:
            continue
        row = await budget_service.category_available(db, household, month, category_id)
        if row and row["available"] < 0:
            await notify(
                db,
                household.id,
                "budget_overspent",
                t(locale, "overspent_title", category=row["name"]),
                t(
                    locale,
                    "overspent_body",
                    category=row["name"],
                    month=month,
                    amount=fmt_money(-row["available"], household.currency),
                ),
                dedupe_key=f"overspent:{category_id}:{month}",
                data={"category_id": category_id, "month": month},
            )

    if account_ids:
        goals = (
            await db.execute(
                select(SavingsGoal).where(
                    SavingsGoal.household_id == household.id,
                    SavingsGoal.account_id.in_(account_ids),
                    SavingsGoal.achieved_notified.is_(False),
                )
            )
        ).scalars().all()
        for goal in goals:
            balance = await account_balance(db, household.id, goal.account_id)
            if balance >= goal.target_amount:
                goal.achieved_notified = True
                goal.completed_at = utcnow()
                await notify(
                    db,
                    household.id,
                    "goal_reached",
                    t(locale, "goal_reached_title", name=goal.name),
                    t(
                        locale,
                        "goal_reached_body",
                        name=goal.name,
                        amount=fmt_money(goal.target_amount, household.currency),
                    ),
                    dedupe_key=f"goal:{goal.id}",
                    data={"goal_id": goal.id},
                    email=True,
                )
