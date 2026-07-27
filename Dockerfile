# syntax=docker/dockerfile:1

# ---------- Stage 1: build the frontend ----------
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: install backend dependencies ----------
FROM python:3.12-slim AS backend-deps
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-postgres.txt

# ---------- Stage 3: final image ----------
FROM python:3.12-slim

LABEL org.opencontainers.image.title="revly-budgeting" \
      org.opencontainers.image.description="Self-hosted envelope budgeting (YNAB-style) in a single container" \
      org.opencontainers.image.licenses="MIT"

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app
COPY --from=backend-deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin
COPY backend/ /app/backend/
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    DATABASE_URL=sqlite+aiosqlite:////data/revly.db \
    DEFAULT_LOCALE=de

USER appuser
WORKDIR /app/backend
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD \
  python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/app/entrypoint.sh"]
