#!/usr/bin/env bash
# Pi-side hardening for the Haven backend (Stage 3 of the freeze-mitigation work).
#
# Run this ONCE on the Raspberry Pi (10.0.0.229) as a user with sudo.
# It is idempotent — running twice is safe.
#
# What it does:
#   1. Enables zram-backed swap (compressed RAM swap, no SD-card writes). When
#      the kernel runs out of physical RAM, it pages to compressed memory rather
#      than the SD card. This is the difference between "Pi gets slow" and "Pi
#      hard-freezes" under sustained load.
#   2. Installs a small wrapper script that pings /api/admin/maintenance/vacuum
#      and writes timestamped logs.
#   3. Adds a cron entry to run that wrapper Sunday 04:00 weekly. This keeps the
#      DB defragmented and the WAL bounded with no manual intervention.
#
# What it does NOT do:
#   - Touch the Haven container, the database, or any application code.
#   - Open new ports or change firewall rules.
#
# After running, verify with:
#   swapon --show          # zram0 should appear with a non-zero size
#   crontab -l             # the haven-vacuum line should appear
#   tail -n 20 ~/haven-maintenance.log   # populated after first cron fire

set -euo pipefail

if [[ $EUID -eq 0 ]]; then
  echo "Run this as your normal user (it will sudo where needed)." >&2
  exit 1
fi

echo "=== Stage 3 Pi hardening ==="

# ---------------------------------------------------------------------------
# 1. zram swap
# ---------------------------------------------------------------------------
if ! command -v zramctl >/dev/null 2>&1; then
  echo "[zram] installing zram-tools..."
  sudo apt-get update -qq
  sudo apt-get install -y zram-tools
else
  echo "[zram] zram-tools already installed"
fi

# Configure zram to use ~50% of RAM, lz4 compression (cheap on the Pi 5's CPUs).
ZRAM_CONF=/etc/default/zramswap
if ! grep -q '^PERCENT=' "$ZRAM_CONF" 2>/dev/null; then
  echo "[zram] writing $ZRAM_CONF"
  sudo tee "$ZRAM_CONF" >/dev/null <<'EOF'
# Managed by Master-Haven pi_setup_stage3.sh
ALGO=lz4
PERCENT=50
PRIORITY=100
EOF
fi

sudo systemctl enable zramswap.service >/dev/null 2>&1 || true
sudo systemctl restart zramswap.service
echo "[zram] swap status:"
swapon --show || true

# ---------------------------------------------------------------------------
# 2. Maintenance wrapper script
# ---------------------------------------------------------------------------
WRAPPER=$HOME/haven-maintenance.sh
LOG=$HOME/haven-maintenance.log

cat > "$WRAPPER" <<'EOF'
#!/usr/bin/env bash
# Hits the Haven backend running on this Pi and asks it to VACUUM the DB.
# The container exposes 8005 on the docker_default network as `haven`, but
# from the Pi host we go through the published port (or localhost fallback).
#
# Auth: the endpoint is super-admin only. Drop a session cookie file at
# ~/haven-admin-cookie.txt (created with `curl -c ...` after a login) and
# this script will use it; otherwise the call will 401 and the failure is
# logged but harmless.
set -euo pipefail
TS=$(date '+%Y-%m-%d %H:%M:%S')
COOKIE=$HOME/haven-admin-cookie.txt
LOG=$HOME/haven-maintenance.log
URL=http://127.0.0.1:8005/api/admin/maintenance/vacuum

if [[ -f "$COOKIE" ]]; then
  out=$(curl -s -X POST -b "$COOKIE" "$URL" || true)
else
  out=$(curl -s -X POST "$URL" || true)
fi

echo "[$TS] $out" >> "$LOG"
EOF
chmod +x "$WRAPPER"
touch "$LOG"
echo "[maintenance] wrote $WRAPPER (logs to $LOG)"

# ---------------------------------------------------------------------------
# 3. Weekly cron — Sundays at 04:00 local time
# ---------------------------------------------------------------------------
CRON_LINE="0 4 * * 0 $WRAPPER"
if crontab -l 2>/dev/null | grep -qF "$WRAPPER"; then
  echo "[cron] weekly vacuum cron already installed"
else
  ( crontab -l 2>/dev/null; echo "$CRON_LINE" ) | crontab -
  echo "[cron] installed: $CRON_LINE"
fi

echo
echo "Done. Verify with: swapon --show && crontab -l"
