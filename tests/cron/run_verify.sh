#!/usr/bin/env bash
# Daily verify-tier runner — in-process TestClient + throwaway DB.
# Per Q12.4: ALL verify failures are P0, alert immediately.
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TESTS_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
REPO_ROOT=$(cd "${TESTS_DIR}/.." && pwd)

if [[ -f "${TESTS_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${TESTS_DIR}/.env"
    set +a
fi

if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    PY="${REPO_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
    PY=$(command -v python)
else
    echo "[$(date -u +%FT%TZ)] ERROR: no python interpreter found" >&2
    exit 2
fi

LOG_DIR="${HOME}/haven-smoke-logs"
mkdir -p "${LOG_DIR}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="${LOG_DIR}/verify-${TIMESTAMP}.log"

cd "${TESTS_DIR}"
"$PY" -m pytest verify/ --tb=short --no-header -q \
    > "${LOG}" 2>&1
EXIT=$?

if [[ $EXIT -ne 0 ]]; then
    "$PY" -m haven_smoke.alerter \
        --log "${LOG}" --mode verify --severity p0 \
        --title "Haven verify FAILED" \
        || true
fi

find "${LOG_DIR}" -name 'verify-*.log' -mtime +14 -delete 2>/dev/null || true

exit $EXIT
