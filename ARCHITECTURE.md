# Architecture & decisions

Short rationale for the non-obvious choices in revly-budgeting.

## One container, not microservices

The target audience self-hosts on a NAS, Raspberry Pi or small VPS. A single image with
embedded SQLite (like Actual Budget) removes every moving part: `docker run -v … -p …`
is the whole deployment. FastAPI serves the built React SPA via `StaticFiles` with an
`index.html` fallback for client-side routes; the API lives under `/api/*` so the two
never collide. PostgreSQL stays available for power users purely through
`DATABASE_URL` — the code uses no SQLite-specific features (no SQL date functions,
portable `String(7)` month keys, `JSON` type, batch-mode Alembic migrations).

## Money and time

- **All amounts are integers in minor units** (Rappen/Cents), signed: negative =
  outflow. No floats anywhere in money math.
- Exchange rates are the one place `Decimal` appears; conversion happens only for
  display/aggregation (base-currency views), never mutating stored amounts.
- Budget months are `"YYYY-MM"` strings — lexicographically sortable and identical on
  every database dialect.
- DB timestamps are naive UTC; the API serializes them with an explicit `Z`.

## Envelope budget semantics

Per expense category and month:

```
available(M) = carryover + assigned(M) + activity(M)
carryover    = available(M-1)  if the category has rollover enabled, else 0
```

Non-rollover categories return their remainder — positive *or* negative — to
"left to budget" at the month boundary. "Left to budget" itself is computed
iteratively from the first month with data:

```
tbb(M) = tbb(M-1) + returned_by_non_rollover(M-1) + income(M) − Σ assigned(M)
```

Income = transactions in income-typed categories **plus uncategorized flows** (so no
money can silently escape the budget) **plus opening balances of cash-like accounts**
(checking/savings/cash) in their opening month. Credit-card/loan/investment opening
balances are debt/valuation, not assignable money, and are excluded. Future-month
assignments are intentionally ignored for the current month's TBB (documented
simplification vs. YNAB's "budgeted in future").

Transfers are two linked rows sharing a `transfer_group` UUID with mirrored amounts;
they are excluded from budget activity and flow reports, but naturally included in
account balances and net worth. Cross-currency transfers convert via the manual rates
at creation time.

## Security

- **Argon2 via `argon2-cffi` directly** — the prompt suggested Passlib/Argon2; Passlib
  is unmaintained and breaks on Python ≥ 3.13, so the maintained underlying library is
  used with the same algorithm.
- JWT access tokens (15 min) + refresh tokens (30 days) with **rotation**: each refresh
  revokes the previous `jti` (stored server-side). Reusing a rotated token revokes the
  user's whole token family. Password changes revoke all refresh tokens.
- TOTP 2FA (`pyotp`), enabled via QR code; login then becomes a two-step flow with a
  short-lived 2FA token.
- Personal API tokens are prefixed `rvb_`, stored as SHA-256 hashes, shown once.
- In-memory sliding-window rate limiter on login/2FA — adequate because the deployment
  model is a single process (see below).
- Every domain query filters by the active household; roles (owner/editor/viewer) are
  enforced in dependencies, viewers are read-only.

## Background work

Recurring transactions and bill reminders run on an asyncio task started in the app
lifespan (hourly). It books missed occurrences (bounded catch-up), anchors month-end
dates (`anchor_day` keeps "the 31st" on month ends), and dedupes notifications with
unique keys. Consequence: **the container runs one uvicorn worker**. That is the right
trade-off for a household app; horizontal scaling would need an external scheduler,
shared rate limiting and a shared import cache — out of scope by design.

## Imports

CSV/OFX/QIF parsers are small and dependency-free (the maintained ecosystem for OFX/QIF
is effectively dead). Parsing is tolerant: encoding sniffing (UTF-8/CP1252/Latin-1),
delimiter sniffing, decimal-comma auto-detection per value, several date formats plus a
user-supplied override. Uploads are parsed once into an in-memory preview cache
(TTL 30 min) so the mapping step doesn't re-upload. Duplicates: exact hash
(household+account+date+amount+payee) **or** fuzzy (same amount, ±3 days, payee
similarity ≥ 0.85).

Open-banking (Plaid-style) is deliberately not implemented; the integration seam is
documented in `backend/app/services/banking_adapter.py` (provider protocol + mapping
into the existing dedupe pipeline).

## Email

SMTP settings resolve as: admin-area values in the `app_settings` table override
environment variables. Sending uses stdlib `smtplib` in a thread executor,
fire-and-forget, so a slow mail server never blocks a request or the scheduler.

## Reports

Cross-dialect portability beats SQL cleverness here: range queries fetch compact tuple
rows and aggregate per month in Python. For a household-scale dataset (tens of
thousands of rows) this is comfortably fast and keeps SQLite/Postgres behavior
identical. PDF export uses reportlab (pure Python, small).

## Frontend

React 18 + Vite + Tailwind. Server state via TanStack Query (mutations invalidate the
affected domains), minimal UI state in Zustand. The fetch client refreshes tokens once
on 401 with a shared in-flight refresh promise. i18n via react-i18next with a test that
enforces key parity between `de.json` and `en.json`. Chart colors were validated with a
CVD/contrast palette validator against the real light/dark surfaces; series colors are
semantic and stable (green = income/assets, orange = expenses/liabilities, blue = net).
PWA: hand-written service worker (cache-first static assets, network-only API,
network-first navigation with offline shell) — no workbox dependency.

## Testing

Backend: pytest + httpx against the real ASGI app with in-memory SQLite per test —
covering auth flows (rotation, reuse detection, 2FA, rate limit), the budget engine
(rollover vs. reset, TBB, move, autofill), recurring catch-up and reminders, import
mapping/dedupe, goals/debts math and report shapes. Frontend: vitest + Testing Library
for the budget view and the transaction form (validation, signed amounts, split sums),
plus pure-function and i18n-parity tests.

## Known limitations

- Single-process design (see Background work) — intentional.
- Rate limiter and import cache are in-memory (reset on restart).
- Exchange rates are manual; conversions use current rates, not historical ones.
- Sankey report is implemented as the two-sided "money flow" bar view (allowed
  fallback in the spec).
