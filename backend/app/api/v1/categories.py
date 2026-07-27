from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx, require_editor
from app.core.db import get_db
from app.models import Budget, Category, RecurringTransaction, Tag, Transaction, TransactionSplit
from app.schemas.category import CategoryCreateIn, CategoryOut, CategoryUpdateIn, TagCreateIn, TagOut

router = APIRouter(prefix="/categories", tags=["categories"])
tags_router = APIRouter(prefix="/tags", tags=["categories"])


async def _get_category(db: AsyncSession, household_id: int, category_id: int) -> Category:
    cat = await db.scalar(
        select(Category).where(Category.id == category_id, Category.household_id == household_id)
    )
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


async def _validate_parent(db: AsyncSession, household_id: int, category_id: int | None, parent_id: int) -> None:
    if parent_id == category_id:
        raise HTTPException(status_code=422, detail="A category cannot be its own parent")
    parent = await _get_category(db, household_id, parent_id)
    # Walk up to detect cycles (hierarchies are shallow in practice).
    seen = 0
    current = parent
    while current.parent_id is not None and seen < 10:
        if current.parent_id == category_id:
            raise HTTPException(status_code=422, detail="Category hierarchy cycle")
        current = await _get_category(db, household_id, current.parent_id)
        seen += 1


@router.get("", response_model=list[CategoryOut])
async def list_categories(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> list[Category]:
    rows = await db.execute(
        select(Category)
        .where(Category.household_id == ctx.household.id)
        .order_by(Category.sort_order, Category.id)
    )
    return list(rows.scalars().all())


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(
    payload: CategoryCreateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> Category:
    if payload.parent_id is not None:
        await _validate_parent(db, ctx.household.id, None, payload.parent_id)
    cat = Category(
        household_id=ctx.household.id,
        name=payload.name,
        icon=payload.icon,
        color=payload.color,
        type=payload.type,
        parent_id=payload.parent_id,
        rollover=payload.rollover,
        sort_order=payload.sort_order,
    )
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return cat


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    payload: CategoryUpdateIn,
    ctx: HouseholdCtx = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
) -> Category:
    cat = await _get_category(db, ctx.household.id, category_id)
    if payload.clear_parent:
        cat.parent_id = None
    elif payload.parent_id is not None:
        await _validate_parent(db, ctx.household.id, category_id, payload.parent_id)
        cat.parent_id = payload.parent_id
    for field in ("name", "icon", "color", "rollover", "archived", "sort_order"):
        value = getattr(payload, field)
        if value is not None:
            setattr(cat, field, value)
    await db.commit()
    return cat


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: int, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> None:
    cat = await _get_category(db, ctx.household.id, category_id)
    used = (
        await db.scalar(select(func.count(Transaction.id)).where(Transaction.category_id == cat.id))
        or await db.scalar(
            select(func.count(TransactionSplit.id)).where(TransactionSplit.category_id == cat.id)
        )
        or await db.scalar(select(func.count(Budget.id)).where(Budget.category_id == cat.id))
        or await db.scalar(
            select(func.count(RecurringTransaction.id)).where(RecurringTransaction.category_id == cat.id)
        )
        or await db.scalar(select(func.count(Category.id)).where(Category.parent_id == cat.id))
    )
    if used:
        raise HTTPException(
            status_code=409, detail="Category is in use; archive it instead of deleting"
        )
    await db.delete(cat)
    await db.commit()


@tags_router.get("", response_model=list[TagOut])
async def list_tags(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> list[Tag]:
    rows = await db.execute(
        select(Tag).where(Tag.household_id == ctx.household.id).order_by(Tag.name)
    )
    return list(rows.scalars().all())


@tags_router.post("", response_model=TagOut, status_code=201)
async def create_tag(
    payload: TagCreateIn, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> Tag:
    existing = await db.scalar(
        select(Tag).where(Tag.household_id == ctx.household.id, Tag.name == payload.name.strip())
    )
    if existing:
        return existing
    tag = Tag(household_id=ctx.household.id, name=payload.name.strip())
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


@tags_router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: int, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> None:
    tag = await db.scalar(select(Tag).where(Tag.id == tag_id, Tag.household_id == ctx.household.id))
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    await db.delete(tag)
    await db.commit()
