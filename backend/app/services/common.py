from __future__ import annotations

# Tiny backend-side i18n for generated texts (notifications, PDF, adjustments).
# The UI has full react-i18next translations; the backend only needs these few strings.

_STRINGS: dict[str, dict[str, str]] = {
    "de": {
        "bill_due_title": "Rechnung fällig: {payee}",
        "bill_due_body": "{payee} über {amount} ist am {date} fällig.",
        "recurring_created_title": "Wiederkehrende Buchung erstellt: {payee}",
        "recurring_created_body": "{payee} über {amount} wurde am {date} automatisch gebucht.",
        "overspent_title": "Budget überschritten: {category}",
        "overspent_body": "Die Kategorie {category} ist im Monat {month} um {amount} überzogen.",
        "goal_reached_title": "Sparziel erreicht: {name}",
        "goal_reached_body": "Dein Sparziel {name} über {amount} ist erreicht. Glückwunsch!",
        "member_joined_title": "Neues Mitglied: {name}",
        "member_joined_body": "{name} ist dem Haushalt beigetreten.",
        "reconcile_adjustment": "Saldokorrektur",
        "transfer_to": "Übertrag an {name}",
        "transfer_from": "Übertrag von {name}",
        "smtp_test_subject": "revly-budgeting Test-E-Mail",
        "smtp_test_body": "Der E-Mail-Versand deiner revly-budgeting-Instanz funktioniert.",
        "pdf_title": "Monatsbericht {month}",
        "pdf_spending": "Ausgaben nach Kategorie",
        "pdf_trend": "Einnahmen vs. Ausgaben (letzte 6 Monate)",
        "pdf_income": "Einnahmen",
        "pdf_expenses": "Ausgaben",
        "pdf_net": "Netto",
        "pdf_category": "Kategorie",
        "pdf_amount": "Betrag",
        "pdf_month": "Monat",
        "pdf_to_budget": "Noch zu budgetieren",
        "pdf_generated": "Erstellt mit revly-budgeting",
        "uncategorized": "Ohne Kategorie",
    },
    "en": {
        "bill_due_title": "Bill due: {payee}",
        "bill_due_body": "{payee} of {amount} is due on {date}.",
        "recurring_created_title": "Recurring transaction created: {payee}",
        "recurring_created_body": "{payee} of {amount} was booked automatically on {date}.",
        "overspent_title": "Budget overspent: {category}",
        "overspent_body": "Category {category} is overspent by {amount} in {month}.",
        "goal_reached_title": "Savings goal reached: {name}",
        "goal_reached_body": "Your savings goal {name} of {amount} has been reached. Congratulations!",
        "member_joined_title": "New member: {name}",
        "member_joined_body": "{name} joined the household.",
        "reconcile_adjustment": "Balance adjustment",
        "transfer_to": "Transfer to {name}",
        "transfer_from": "Transfer from {name}",
        "smtp_test_subject": "revly-budgeting test email",
        "smtp_test_body": "Email delivery of your revly-budgeting instance works.",
        "pdf_title": "Monthly report {month}",
        "pdf_spending": "Spending by category",
        "pdf_trend": "Income vs. expenses (last 6 months)",
        "pdf_income": "Income",
        "pdf_expenses": "Expenses",
        "pdf_net": "Net",
        "pdf_category": "Category",
        "pdf_amount": "Amount",
        "pdf_month": "Month",
        "pdf_to_budget": "Left to budget",
        "pdf_generated": "Generated with revly-budgeting",
        "uncategorized": "Uncategorized",
    },
}


def t(locale: str, key: str, **kwargs: object) -> str:
    lang = locale if locale in _STRINGS else "de"
    template = _STRINGS[lang].get(key) or _STRINGS["de"].get(key) or key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def fmt_money(cents: int, currency: str = "CHF") -> str:
    sign = "-" if cents < 0 else ""
    value = abs(cents)
    return f"{sign}{currency} {value // 100}.{value % 100:02d}"
