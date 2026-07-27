from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    admin,
    auth,
    budgets,
    categories,
    debts,
    exports,
    goals,
    households,
    imports,
    notifications,
    recurring,
    reports,
    transactions,
    users,
)

api_router = APIRouter(prefix="/api/v1")

for sub_router in (
    auth.router,
    users.router,
    households.router,
    accounts.router,
    accounts.rates_router,
    categories.router,
    categories.tags_router,
    transactions.router,
    budgets.router,
    recurring.router,
    goals.router,
    debts.router,
    reports.router,
    imports.router,
    exports.router,
    notifications.router,
    admin.router,
):
    api_router.include_router(sub_router)
