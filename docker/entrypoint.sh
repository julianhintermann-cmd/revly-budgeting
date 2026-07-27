#!/bin/sh
set -e

cd /app/backend

echo "revly-budgeting: applying database migrations ..."
python -m alembic upgrade head

echo "revly-budgeting: starting server on port ${PORT:-8000} ..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
