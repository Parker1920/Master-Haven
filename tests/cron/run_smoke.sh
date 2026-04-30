#!/usr/bin/env bash
# Hourly smoke runner — exercises the live HTTP probe tier and alerts on
# failure. Designed to run from cron without manual intervention.
#
# Usage:
#   ./run_smoke.sh           # fast tier only (default; matches hourly cron)
#   ./run_smoke.sh --slow    # include @slow poster tests (daily cron)
#
# Exit codes:
#   0 — all tests passed
#   1 — one or more tests failed (alert posted if webhook configured)
#   2 — environment / setup error (no tests ran)
set -uo pipefail  # NOT -e: we want to capture pytest exit status, not abort.

# ---- locate self -----------------------------------------------------------
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TESTS_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)
REPO_ROOT=$(cd "${TESTS_DIR}/.." && pwd)

# ---- load env --------------------------------------------------------------
if [[ -f "${TESTS_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${TESTS_DIR}/.env"
    set +a
fi

# ---- choose marker filter --------------------------------------------------
if [[ "${1:-}" == "--slow" ]]; then
    MARKER='slow'
    MODE='smoke-slow'
else
    MARKER='not slow'
    MODE='smoke'
fi

# ---- locate python ---------------------------------------------------------
# Prefer the venv python if present; fall back to system python3.
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

# ---- prepare log -----------------------------------------------------------
LOG_DIR="${HOME}/haven-smoke-logs"
mkdir -p "${LOG_DIR}"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
LOG="${LOG_DIR}/smoke-${TIMESTAMP}.log"

# ---- run pytest ------------------------------------------------------------
cd "${TESTS_DIR}"
"$PY" -m pytest smoke/ -m "${MARKER}" --tb=short --no-header -q \
    > "${LOG}" 2>&1
EXIT=$?

# ---- alert on failure ------------------------------------------------------
if [[ $EXIT -ne 0 ]]; then
    # Pick severity: --slow runs are P1; default is P0.
    if [[ "${MODE}" == 'smoke-slow' ]]; then
        SEV='p1'
    else
        SEV='p0'
    fi
    "$PY" -m haven_smoke.alerter \
        --log "${LOG}" --mode "${MODE}" --severity "${SEV}" \
        --title "Haven smoke FAILED (${MODE})" \
        || true
fi

# Trim old logs (keep 14 days)
find "${LOG_DIR}" -name 'smoke-*.log' -mtime +14 -delete 2>/dev/null || true

exit $EXIT
