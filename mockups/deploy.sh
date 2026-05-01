#!/usr/bin/env bash
# Travelers Archive v0.7 — Pi deploy script
# Idempotent: safe to re-run. Stops any prior python3 -m http.server in ~/mockup
# before starting a new one, so re-running picks up an updated file cleanly.
#
# Usage (over SSH on the Pi):
#   curl -sL https://raw.githubusercontent.com/Parker1920/Master-Haven/claude/deploy-mockup-pi-yZqGI/mockups/deploy.sh | bash

set -euo pipefail

REPO_BRANCH="claude/deploy-mockup-pi-yZqGI"
RAW_URL="https://raw.githubusercontent.com/Parker1920/Master-Haven/${REPO_BRANCH}/mockups/travelers-archive-v0.7.html"
EXPECTED_MD5="6b5de937fe9fdff8cd3b0a6af5eadcf7"
EXPECTED_BYTES=124161
DEST_DIR="${HOME}/mockup"
DEST_FILE="${DEST_DIR}/index.html"
LOG_FILE="/tmp/mockup-server.log"
PID_FILE="/tmp/mockup-server.pid"

echo ""
echo "=================================================="
echo "  Travelers Archive v0.7 — Pi deploy"
echo "=================================================="
echo ""

# 1. fetch the file
echo "[1/5] Downloading mockup from GitHub..."
mkdir -p "${DEST_DIR}"
if ! wget -q -O "${DEST_FILE}" "${RAW_URL}"; then
  echo "  FAILED: wget could not retrieve ${RAW_URL}"
  echo "  Check that the Pi has internet access and that the branch still exists."
  exit 1
fi

ACTUAL_BYTES=$(wc -c < "${DEST_FILE}")
ACTUAL_MD5=$(md5sum "${DEST_FILE}" | awk '{print $1}')
echo "  wrote ${ACTUAL_BYTES} bytes (expected ${EXPECTED_BYTES})"
echo "  md5  ${ACTUAL_MD5}"
echo "       ${EXPECTED_MD5}  (expected)"
if [[ "${ACTUAL_MD5}" != "${EXPECTED_MD5}" ]]; then
  echo "  WARNING: md5 mismatch — file may have been updated since this script was written."
  echo "  Continuing anyway since you may be deploying a newer version."
fi

# 2. stop any prior server we started (don't touch other things on 8080+)
echo ""
echo "[2/5] Stopping any prior mockup server..."
if [[ -f "${PID_FILE}" ]]; then
  OLD_PID=$(cat "${PID_FILE}")
  if kill -0 "${OLD_PID}" 2>/dev/null; then
    kill "${OLD_PID}" 2>/dev/null || true
    sleep 0.5
    echo "  stopped previous server (pid ${OLD_PID})"
  else
    echo "  no previous server running (stale pidfile)"
  fi
  rm -f "${PID_FILE}"
else
  echo "  no previous server pidfile"
fi

# 3. find a free port — start at 8080, climb until we find one
echo ""
echo "[3/5] Finding a free port..."
PORT=8080
while ss -tlnp 2>/dev/null | awk '{print $4}' | grep -q ":${PORT}$"; do
  PORT=$((PORT + 1))
  if [[ ${PORT} -gt 8099 ]]; then
    echo "  FAILED: no free port in 8080-8099 range. What is using these?"
    ss -tlnp 2>/dev/null | grep -E ':80[89][0-9] '
    exit 1
  fi
done
echo "  using port ${PORT}"

# 4. start server
echo ""
echo "[4/5] Starting python3 -m http.server on port ${PORT}..."
cd "${DEST_DIR}"
nohup python3 -m http.server "${PORT}" > "${LOG_FILE}" 2>&1 &
SERVER_PID=$!
echo "${SERVER_PID}" > "${PID_FILE}"
disown 2>/dev/null || true
sleep 1

if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
  echo "  FAILED: server died immediately. Log:"
  tail -20 "${LOG_FILE}"
  rm -f "${PID_FILE}"
  exit 1
fi
echo "  server pid ${SERVER_PID}, log at ${LOG_FILE}"

# 5. verify it actually serves
echo ""
echo "[5/5] Verifying server responds..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${PORT}/" || echo "000")
if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "  FAILED: localhost:${PORT}/ returned HTTP ${HTTP_CODE}"
  echo "  Log:"
  tail -20 "${LOG_FILE}"
  exit 1
fi
echo "  HTTP ${HTTP_CODE} OK"

echo ""
echo "=================================================="
echo "  DEPLOYED"
echo "=================================================="
echo ""
echo "  From your phone (Tailscale):"
echo "    http://pi8gb.tail86d21a.ts.net:${PORT}/"
echo "    http://100.79.172.115:${PORT}/"
echo ""
echo "  From this Pi:"
echo "    http://localhost:${PORT}/"
echo ""
echo "  To stop:   kill \$(cat ${PID_FILE})"
echo "  Server log: ${LOG_FILE}"
echo ""
