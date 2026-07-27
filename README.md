# revly-budgeting

**Self-hosted, privacy-friendly envelope budgeting — YNAB-style, in a single Docker container.**

Give every franc a job: accounts, transactions, monthly envelope budgets with rollover,
recurring bills, savings goals, debt payoff plans, reports and imports — all stored on
*your* machine, in one container, with SQLite by default and PostgreSQL as an option.

UI in **German (default) and English** · installable **PWA** · dark & light mode.

> Screenshots: *(placeholder — dashboard, budget view, reports)*

---

## Quick start

```bash
docker run -d --name revly -p 8000:8000 -v revly-data:/data <DOCKERHUB_USERNAME>/revly-budgeting:latest
```

Open http://localhost:8000, register the first user (becomes instance admin) and follow
the onboarding. That's it — data, uploads and the auto-generated secret live in the
`revly-data` volume.

Or build locally from source:

```bash
git clone https://github.com/<GITHUB_USERNAME>/revly-budgeting.git
cd revly-budgeting
docker build -t revly-budgeting .
docker run -d --name revly -p 8000:8000 -v revly-data:/data revly-budgeting
```

Or with compose: `docker compose up -d` (see `docker-compose.yml`, including an optional
PostgreSQL service).

## Features

- **Accounts** – checking, savings, credit card, cash, loan, investment; multi-currency
  with manual exchange rates; statement reconciliation with automatic adjustment entries;
  archiving without losing history; net-worth overview and history.
- **Transactions** – fast entry, split transactions, transfers between accounts (never
  double-counted), tags, receipt uploads (image/PDF), pending vs. cleared vs. reconciled,
  full-text search, rich filters, bulk edit, pagination.
- **Envelope budgeting** – monthly assignments per category, "left to budget" always
  visible, per-category rollover (carry over or reset), overspend highlighting with
  one-click *move money*, autofill suggestions from the last three months.
- **Categories** – icons & colors, income/expense types, subcategories, archiving,
  sensible German/English default set on first start.
- **Recurring & bills** – weekly/monthly/quarterly/yearly/custom intervals, automatic
  booking by a built-in scheduler (missed occurrences are caught up, month-end dates
  anchored), reminders X days ahead, subscription cost overview.
- **Savings goals** – target amount/date, linked account (balance = progress) or manual
  contributions, required-per-month calculation, reached-notifications.
- **Debt payoff** – snowball & avalanche plans with interest, minimum payments,
  month-by-month schedule, strategy comparison and what-if budget.
- **Reports** – spending by category, income vs. expenses trend, cashflow calendar
  ("which days are tight"), net-worth history, money-flow view; export as **PDF** and
  **CSV**; full JSON backup export.
- **Import** – CSV with a column-mapping assistant (auto-detects delimiters, decimal
  commas, date formats), OFX/QFX and QIF; duplicate detection (exact + fuzzy).
- **Multi-user households** – invite by code/link, roles (owner / editor / viewer),
  strict per-household data isolation, multiple households per user.
- **Notifications** – in-app center plus optional email (SMTP configurable in the admin
  area, with test-send button).
- **Security** – Argon2 password hashing, JWT access+refresh with rotation and reuse
  detection, optional TOTP 2FA, login rate limiting, personal API tokens (`rvb_…`),
  audit log.
- **API-first** – full REST API under `/api/v1`, OpenAPI docs at `/api/docs` and
  `/api/redoc`.

## Configuration

Everything is configured via environment variables (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:////data/revly.db` | Any SQLAlchemy URL; `postgresql://…` works out of the box (asyncpg included) |
| `SECRET_KEY` | auto-generated into `/data` | JWT signing key |
| `DATA_DIR` | `/data` | SQLite DB, generated secret, receipt uploads |
| `ALLOWED_ORIGINS` | *(empty)* | Extra CORS origins (not needed same-origin) |
| `DEFAULT_LOCALE` | `de` | Language for scheduler-generated notifications |
| `SMTP_*` | *(empty)* | Email fallback config; the in-app admin area overrides it |
| `PORT` | `8000` | Listen port |

## Development

```bash
# backend
cd backend
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python -m alembic upgrade head
uvicorn app.main:app --reload            # http://localhost:8000/api/docs

# frontend (second terminal)
cd frontend
npm install
npm run dev                              # http://localhost:5173 (proxies /api)
```

Or containerized with hot reload: `docker compose --profile dev up`.

### Tests

```bash
cd backend && python -m pytest           # 37 tests: auth/2FA, budget math, recurring, imports, reports
cd frontend && npm test                  # 12 tests: budget view, transaction form, formats, i18n parity
```

## Releases & CI

Pushes to `main` and tags `v*` build and publish a **multi-arch image
(linux/amd64 + linux/arm64)** to Docker Hub via GitHub Actions — set the repo secrets
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`. Versioning starts at `0.1.0`.

## Architecture

Single container: FastAPI serves both the REST API and the built React SPA; migrations
run automatically on startup. Design decisions and trade-offs are documented in
[ARCHITECTURE.md](ARCHITECTURE.md).

## License

[MIT](LICENSE) © 2026 Julian Hintermann
