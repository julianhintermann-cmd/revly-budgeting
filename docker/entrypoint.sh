#!/bin/sh
set -e

DATA="${DATA_DIR:-/data}"
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

# Started as root (the image default): prepare the mounted data directories,
# then either stay root (PUID=0, common on NAS setups whose ACL defaults break
# per-user file modes) or fix ownership and drop to the requested uid/gid.
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA"
    if [ -n "$UPLOAD_DIR" ]; then
        mkdir -p "$UPLOAD_DIR"
    fi
    if [ "$PUID" != "0" ]; then
        for dir in "$DATA" "$UPLOAD_DIR" /data /config; do
            if [ -n "$dir" ] && [ -d "$dir" ]; then
                chown -R "$PUID:$PGID" "$dir" 2>/dev/null || true
                chmod -R u+rwX "$dir" 2>/dev/null || true
            fi
        done
        exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$0" "$@"
    fi
fi

cd /app/backend

echo "revly-budgeting: applying database migrations ..."
python -m alembic upgrade head

echo "revly-budgeting: starting server on port ${PORT:-8000} ..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
