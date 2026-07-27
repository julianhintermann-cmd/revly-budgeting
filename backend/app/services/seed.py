from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, ExchangeRate

DEFAULT_CATEGORIES: dict[str, dict[str, list[tuple[str, str, str]]]] = {
    "de": {
        "expense": [
            ("Wohnen", "🏠", "#f59e0b"),
            ("Lebensmittel", "🛒", "#10b981"),
            ("Transport", "🚗", "#3b82f6"),
            ("Freizeit", "🎉", "#8b5cf6"),
            ("Versicherungen", "🛡️", "#64748b"),
            ("Abos", "📺", "#ec4899"),
            ("Gesundheit", "⚕️", "#ef4444"),
            ("Sparen", "🎯", "#14b8a6"),
            ("Sonstiges", "📦", "#6b7280"),
        ],
        "income": [
            ("Gehalt", "💼", "#22c55e"),
            ("Sonstige Einnahmen", "💰", "#84cc16"),
        ],
    },
    "en": {
        "expense": [
            ("Housing", "🏠", "#f59e0b"),
            ("Groceries", "🛒", "#10b981"),
            ("Transport", "🚗", "#3b82f6"),
            ("Leisure", "🎉", "#8b5cf6"),
            ("Insurance", "🛡️", "#64748b"),
            ("Subscriptions", "📺", "#ec4899"),
            ("Health", "⚕️", "#ef4444"),
            ("Savings", "🎯", "#14b8a6"),
            ("Other", "📦", "#6b7280"),
        ],
        "income": [
            ("Salary", "💼", "#22c55e"),
            ("Other income", "💰", "#84cc16"),
        ],
    },
}


async def seed_household(db: AsyncSession, household_id: int, base_currency: str, locale: str = "de") -> None:
    """Create the default category set and the base exchange rate for a fresh household."""
    catalog = DEFAULT_CATEGORIES.get(locale, DEFAULT_CATEGORIES["de"])
    order = 0
    for type_, entries in (("income", catalog["income"]), ("expense", catalog["expense"])):
        for name, icon, color in entries:
            db.add(
                Category(
                    household_id=household_id,
                    name=name,
                    icon=icon,
                    color=color,
                    type=type_,
                    sort_order=order,
                )
            )
            order += 1
    db.add(ExchangeRate(household_id=household_id, currency=base_currency, rate=Decimal("1")))
