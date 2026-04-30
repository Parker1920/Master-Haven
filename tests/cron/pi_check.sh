#!/usr/bin/env bash
# Pi-side state observer for the Haven Voyager's Haven stack.
#
# Output: pipe-delimited rows on stdout, one per check.
#   <ISO-timestamp>|<check.dotted.name>|<PASS|FAIL|SKIP|INFO|WARN>|<detail>
#
# Exit codes:
#   0 — every row PASS, SKIP, INFO, or WARN
#   1 — at least one row is FAIL
#   2 — script itself crashed (set -e triggered)
#
# This script is read-only. It runs `docker ps`, `df -h`, `crontab -l`,
# `stat`, and a few other inspection commands. It NEVER writes outside
# stdout/stderr. Designed for cron + manual invocation.
#
# Configurable via tests/.env (relative to this script's parent's parent).

set -euo pipefail

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TESTS_DIR=$(cd "${SCRIPT_DIR}/.." && pwd)

if [[ -f "${TESTS_DIR}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${TESTS_DIR}/.env"
    set +a
fi

# Defaults — overridable from tests/.env
HAVEN_CONTAINER_NAME="${HAVEN_CONTAINER_NAME:-haven-control-room}"
KEEPER_CONTAINER_NAME="${KEEPER_CONTAINER_NAME:-the-keeper}"
EXCHANGE_CONTAINER_NAME="${EXCHANGE_CONTAINER_NAME:-economy}"
VIOBOT_CONTAINER_NAME="${VIOBOT_CONTAINER_NAME:-}"  # unset → SKIP
VIOBOT_SOURCE_PATH="${VIOBOT_SOURCE_PATH:-}"
HAVEN_DATA_PATH="${HAVEN_DATA_PATH:-${HOME}/haven-data}"
HAVEN_PHOTOS_PATH="${HAVEN_PHOTOS_PATH:-${HOME}/haven-photos}"
EXCHANGE_DATA_PATH="${EXCHANGE_DATA_PATH:-${HOME}/exchange-data}"

TS=$(date '+%Y-%m-%d %H:%M:%S')
ANY_FAIL=0

emit() {
    # emit <check> <status> <detail>
    local check="$1" status="$2" detail="$3"
    printf '%s|%s|%s|%s\n' "${TS}" "${check}" "${status}" "${detail}"
    if [[ "${status}" == "FAIL" ]]; then
        ANY_FAIL=1
    fi
}

# ---------------------------------------------------------------------------
# Host info first — so we know what we're looking at
# ---------------------------------------------------------------------------
UPTIME_SECONDS=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 0)
UPTIME_HUMAN=$(uptime -p 2>/dev/null || echo "unknown")
emit "host.uptime" "INFO" "${UPTIME_HUMAN} (${UPTIME_SECONDS}s)"

# Recently-booted bypass: skip container checks for the first 5 min.
if [[ "${UPTIME_SECONDS}" -lt 300 ]]; then
    emit "host.recently_booted" "INFO" "uptime <5min — skipping container checks"
    SKIP_CONTAINERS=1
else
    SKIP_CONTAINERS=0
fi

# NTP / time sync
if command -v timedatectl >/dev/null 2>&1; then
    if timedatectl status 2>/dev/null | grep -qE 'NTP service: active|System clock synchronized: yes'; then
        emit "host.ntp" "PASS" "synchronized"
    else
        emit "host.ntp" "WARN" "NTP sync uncertain"
    fi
else
    emit "host.ntp" "SKIP" "timedatectl not available"
fi

# Pi-specific temp + freq (vcgencmd present only on Pi)
if command -v vcgencmd >/dev/null 2>&1; then
    TEMP=$(vcgencmd measure_temp 2>/dev/null | sed 's/temp=//')
    emit "host.temp" "INFO" "${TEMP}"
fi

# zram (presence + sizing)
if command -v swapon >/dev/null 2>&1; then
    ZRAM=$(swapon --show=NAME,SIZE 2>/dev/null | grep zram || true)
    if [[ -n "${ZRAM}" ]]; then
        emit "host.zram" "PASS" "$(echo "${ZRAM}" | head -1 | tr -s ' ')"
    else
        emit "host.zram" "WARN" "zram not configured (run scripts/pi_setup_stage3.sh)"
    fi
fi

# ---------------------------------------------------------------------------
# Container checks
# ---------------------------------------------------------------------------
check_container() {
    local check="$1" name="$2"
    if [[ -z "${name}" ]]; then
        emit "${check}" "SKIP" "container name not configured"
        return
    fi
    if [[ "${SKIP_CONTAINERS}" -eq 1 ]]; then
        emit "${check}" "SKIP" "host recently booted"
        return
    fi
    if ! command -v docker >/dev/null 2>&1; then
        emit "${check}" "FAIL" "docker CLI not found"
        return
    fi
    local status
    status=$(docker ps --filter "name=^/${name}\$" --format '{{.Status}}' 2>/dev/null || echo '')
    if [[ -z "${status}" ]]; then
        emit "${check}" "FAIL" "${name} not in 'docker ps'"
    else
        emit "${check}" "PASS" "${name} (${status})"
    fi
}

check_container "docker.haven" "${HAVEN_CONTAINER_NAME}"
check_container "docker.keeper" "${KEEPER_CONTAINER_NAME}"
check_container "docker.exchange" "${EXCHANGE_CONTAINER_NAME}"
check_container "docker.viobot" "${VIOBOT_CONTAINER_NAME}"

# Viobot source path (file/process check only — read-only)
if [[ -n "${VIOBOT_SOURCE_PATH}" ]]; then
    if [[ -d "${VIOBOT_SOURCE_PATH}" ]]; then
        emit "fs.viobot_source" "PASS" "${VIOBOT_SOURCE_PATH}"
    else
        emit "fs.viobot_source" "FAIL" "${VIOBOT_SOURCE_PATH} not a directory"
    fi
else
    emit "fs.viobot_source" "SKIP" "VIOBOT_SOURCE_PATH not set"
fi

# ---------------------------------------------------------------------------
# Disk checks
# ---------------------------------------------------------------------------
disk_check() {
    local check="$1" target="$2"
    if [[ ! -e "${target}" ]]; then
        emit "${check}" "FAIL" "${target} does not exist"
        return
    fi
    local usage
    usage=$(df -h "${target}" 2>/dev/null | awk 'NR==2 {printf "%s used (%s/%s), %s free", $5, $3, $2, $4}')
    emit "${check}" "PASS" "${usage}"
}

disk_check "disk.root" "/"
if [[ -e "${HAVEN_DATA_PATH}" ]]; then
    SIZE=$(du -sh "${HAVEN_DATA_PATH}" 2>/dev/null | awk '{print $1}')
    emit "disk.haven_data" "PASS" "present, ${SIZE}"
else
    emit "disk.haven_data" "FAIL" "${HAVEN_DATA_PATH} missing"
fi

if [[ -e "${HAVEN_PHOTOS_PATH}" ]]; then
    SIZE=$(du -sh "${HAVEN_PHOTOS_PATH}" 2>/dev/null | awk '{print $1}')
    COUNT=$(find "${HAVEN_PHOTOS_PATH}" -type f -name '*.webp' 2>/dev/null | wc -l)
    emit "disk.haven_photos" "PASS" "present, ${SIZE}, ${COUNT} webp files"
else
    emit "disk.haven_photos" "WARN" "${HAVEN_PHOTOS_PATH} missing"
fi

# ---------------------------------------------------------------------------
# Database freshness
# ---------------------------------------------------------------------------
db_check() {
    local check="$1" path="$2"
    if [[ ! -e "${path}" ]]; then
        emit "${check}" "FAIL" "${path} missing"
        return
    fi
    local size mtime now age_s
    size=$(stat -c '%s' "${path}" 2>/dev/null || echo 0)
    mtime=$(stat -c '%Y' "${path}" 2>/dev/null || echo 0)
    now=$(date +%s)
    age_s=$((now - mtime))
    # Convert size to MB-ish for readability
    if [[ "${size}" -gt 1048576 ]]; then
        size_h="$((size / 1048576))M"
    else
        size_h="${size}B"
    fi
    emit "${check}" "PASS" "exists, ${size_h}, last write ${age_s}s ago"
}

db_check "db.haven_ui" "${HAVEN_DATA_PATH}/haven_ui.db"
if [[ -e "${EXCHANGE_DATA_PATH}/economy.db" ]]; then
    db_check "db.economy" "${EXCHANGE_DATA_PATH}/economy.db"
else
    emit "db.economy" "SKIP" "${EXCHANGE_DATA_PATH}/economy.db not found"
fi

# WAL/SHM presence (informational)
WAL="${HAVEN_DATA_PATH}/haven_ui.db-wal"
if [[ -e "${WAL}" ]]; then
    SIZE=$(stat -c '%s' "${WAL}" 2>/dev/null || echo 0)
    if [[ "${SIZE}" -gt 0 ]]; then
        emit "db.haven_ui_wal" "INFO" "wal size ${SIZE}B"
    fi
fi

# ---------------------------------------------------------------------------
# Cron entries
# ---------------------------------------------------------------------------
if command -v crontab >/dev/null 2>&1; then
    if crontab -l 2>/dev/null | grep -qE 'run_smoke\.sh($|[^-])'; then
        emit "cron.smoke_hourly" "PASS" "entry found"
    else
        emit "cron.smoke_hourly" "WARN" "no run_smoke.sh entry"
    fi
    if crontab -l 2>/dev/null | grep -qE 'run_smoke\.sh.*--slow'; then
        emit "cron.smoke_slow" "PASS" "entry found"
    else
        emit "cron.smoke_slow" "WARN" "no run_smoke.sh --slow entry"
    fi
    if crontab -l 2>/dev/null | grep -q 'pi_check\.sh'; then
        emit "cron.pi_check" "PASS" "entry found"
    else
        emit "cron.pi_check" "WARN" "no pi_check.sh entry"
    fi
    if crontab -l 2>/dev/null | grep -q 'run_verify\.sh'; then
        emit "cron.verify" "PASS" "entry found"
    else
        emit "cron.verify" "WARN" "no run_verify.sh entry"
    fi
else
    emit "cron.smoke_hourly" "SKIP" "crontab not available"
fi

# ---------------------------------------------------------------------------
# Memory snapshot (informational)
# ---------------------------------------------------------------------------
if [[ -r /proc/meminfo ]]; then
    MEM_TOTAL=$(awk '/^MemTotal:/ {printf "%dM", $2/1024}' /proc/meminfo)
    MEM_AVAIL=$(awk '/^MemAvailable:/ {printf "%dM", $2/1024}' /proc/meminfo)
    emit "host.memory" "INFO" "total=${MEM_TOTAL} available=${MEM_AVAIL}"
fi

# ---------------------------------------------------------------------------
# Exit
# ---------------------------------------------------------------------------
if [[ "${ANY_FAIL}" -ne 0 ]]; then
    exit 1
fi
exit 0
