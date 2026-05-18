#!/usr/bin/env bash
# =====================================================================
# Travelers Archive — container entrypoint
# =====================================================================
# Runs on every container start:
#   1. Makes sure /data exists and has a media subfolder
#   2. Runs alembic migrations (idempotent — `alembic upgrade head`
#      only applies new ones)
#   3. Starts uvicorn on 0.0.0.0:8020
#
# Any step failing aborts the boot so the container is marked as
# unhealthy and we don't serve a half-broken stack.

set -euo pipefail

echo "[entrypoint] Travelers Archive starting..."
echo "[entrypoint] ENV=${ENV:-unset}  DATABASE_PATH=${DATABASE_PATH:-unset}"

# Make sure the data dir + media dir exist. /data itself is a bind
# mount from the host; subfolders may not exist on first boot.
mkdir -p "$(dirname "${DATABASE_PATH:-/data/archive.db}")"
mkdir -p "${MEDIA_PATH:-/data/media}"

# Apply any pending Alembic migrations. Alembic stores its applied-
# revision pointer in the `alembic_version` table inside the same DB,
# so re-running is safe.
echo "[entrypoint] running alembic upgrade head"
alembic upgrade head

# Optional: seed demo content (the Phase 2 mockup data — 10 civs,
# 8 personas, 9 stories, 3 inquisitions). Gated behind ARCHIVE_SEED=demo
# so production boots don't re-insert demo content the v0.6 migration
# explicitly wiped. To repopulate: docker exec archive python -m app.seed --demo
if [ "${ARCHIVE_SEED:-}" = "demo" ]; then
    echo "[entrypoint] ARCHIVE_SEED=demo — running demo seed"
    python -m app.seed
else
    echo "[entrypoint] ARCHIVE_SEED not 'demo' — skipping seed (production behavior)"
fi

# Start the ASGI server.
echo "[entrypoint] starting uvicorn on 0.0.0.0:8020"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8020 \
    --proxy-headers \
    --forwarded-allow-ips='*'
