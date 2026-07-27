from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, require_editor
from app.core.db import get_db
from app.schemas.imports import ImportCommitIn, ImportPreviewOut, ImportResultOut
from app.services import audit
from app.services.imports import build_preview, commit_import

router = APIRouter(prefix="/import", tags=["import"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("/preview", response_model=ImportPreviewOut)
async def preview(file: UploadFile, ctx: HouseholdCtx = Depends(require_editor)) -> ImportPreviewOut:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 5 MB limit")
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file")
    return ImportPreviewOut(**build_preview(file.filename or "", raw))


@router.post("/commit", response_model=ImportResultOut)
async def commit(
    payload: ImportCommitIn, ctx: HouseholdCtx = Depends(require_editor), db: AsyncSession = Depends(get_db)
) -> ImportResultOut:
    result = await commit_import(db, ctx.household, ctx.user, payload)
    await audit.log(
        db,
        "transactions_imported",
        user_id=ctx.user.id,
        household_id=ctx.household.id,
        details=f"imported {result['imported']}, duplicates {result['duplicates_skipped']}",
    )
    await db.commit()
    return ImportResultOut(**result)
