#!/bin/sh
set -e

DATA="${DATA_DIR:-/data}"

# Started as root (the image default): make sure the mounted data directories
# exist and belong to the unprivileged app user, then drop privileges.
# This lets bind mounts (NAS setups) work without manual mkdir/chown.
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA"
    if [ -n "$UPLOAD_DIR" ]; then
        mkdir -p "$UPLOAD_DIR"
    fi
    for dir in "$DATA" "$UPLOAD_DIR" /data /config; do
        if [ -n "$dir" ] && [ -d "$dir" ]; then
            if [ "$(stat -c %u "$dir")" != "1000" ]; then
                chown -R appuser:appuser "$dir"
            fi
        fi
    done
    exec setpriv --reuid=appuser --regid=appuser --init-groups "$0" "$@"
fi

cd /app/backend

echo "revly-budgeting: applying database migrations ..."
python -m alembic upgrade head

echo "revly-budgeting: starting server on port ${PORT:-8000} ..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
