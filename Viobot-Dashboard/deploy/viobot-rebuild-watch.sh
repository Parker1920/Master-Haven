#!/bin/bash
# viobot-rebuild-watch.sh — dashboard-triggered "Reimage" of the Viobot container.
#
# The dashboard's Reimage button drops a flag file (it has no Docker build power itself); this host
# cron sees the flag, pulls the latest code, and rebuilds + recreates viobot, then clears the flag.
# Install on the Pi at ~/scripts/ and run every minute via crontab:
#   * * * * * /home/pi8gb/scripts/viobot-rebuild-watch.sh
set -e

FLAG=/home/pi8gb/docker/viobot-dashboard-data/actions/rebuild-viobot
LOG="$HOME/logs/viobot-rebuild-watch.log"

[ -f "$FLAG" ] || exit 0        # nothing queued
rm -f "$FLAG"                   # clear FIRST so a failed build can't loop forever
mkdir -p "$HOME/logs"
echo "[$(date '+%F %T')] reimage triggered" >> "$LOG"

# Pull latest bot code (best-effort — a rebuild of current code is still useful).
cd /home/pi8gb/docker/viobot/Viobot
git fetch origin main --quiet || true
git pull origin main --quiet || true

# Rebuild + recreate just the viobot service from its compose project.
cd /home/pi8gb/docker
docker compose up -d --build viobot >> "$LOG" 2>&1

echo "[$(date '+%F %T')] reimage complete" >> "$LOG"
