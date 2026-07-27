"""Open-banking integration seam (placeholder, not wired to any provider).

revly-budgeting deliberately ships without live bank connections. This module
defines the contract a future provider integration (Plaid, GoCardless/Nordigen,
FinTS, ...) has to fulfil so it can plug into the existing import pipeline
without touching the rest of the app:

1. Implement `BankingProvider` for your provider.
2. Register it in `PROVIDERS`.
3. Feed the returned `ExternalTransaction`s through
   `app.services.imports.commit_import`-style dedupe (exact hash + fuzzy match)
   by mapping them to normalized rows {date, amount, payee, notes}.

Nothing else in the codebase imports this module yet, so a provider can be
developed and tested in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass
class ExternalAccount:
    provider_account_id: str
    name: str
    currency: str
    balance_cents: int | None


@dataclass
class ExternalTransaction:
    provider_txn_id: str
    date: date
    amount_cents: int
    payee: str
    notes: str


class BankingProvider(Protocol):
    """Contract for a bank-data provider adapter."""

    name: str

    async def connect(self, credentials: dict[str, str]) -> str:
        """Establish a connection/session; returns an opaque connection id."""
        ...

    async def list_accounts(self, connection_id: str) -> list[ExternalAccount]:
        ...

    async def fetch_transactions(
        self, connection_id: str, provider_account_id: str, since: date
    ) -> list[ExternalTransaction]:
        ...


# Register concrete implementations here, keyed by provider name.
PROVIDERS: dict[str, BankingProvider] = {}
