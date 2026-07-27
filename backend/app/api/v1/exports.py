from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import HouseholdCtx, get_household_ctx
from app.core.db import get_db
from app.services import reports as report_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/full.json")
async def full_json(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    data = await report_service.export_full_json(db, ctx.household)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": 'attachment; filename="revly-export.json"'},
    )


@router.get("/transactions.csv")
async def transactions_csv(
    ctx: HouseholdCtx = Depends(get_household_ctx), db: AsyncSession = Depends(get_db)
) -> Response:
    csv_text = await report_service.export_transactions_csv(db, ctx.household)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="revly-transactions.csv"'},
    )
