# Haven smoke suite — cron setup

This directory contains the runtime pieces:

- `run_smoke.sh` — pytest smoke tier; alerts on failure
- `run_verify.sh` — pytest verify tier (in-process); alerts on failure
- `pi_check.sh` — read-only Pi state observer; emits pipe-delimited rows

## Crontab — copy and paste

After cloning the repo and creating `tests/.env` (see `tests/.env.example`),
add these lines to Parker's crontab on the Pi:

```cron
# Haven smoke suite — copy-pasteable from tests/cron/README.md
# Adjust the path to wherever the repo lives on the Pi (typically
# ~/docker/haven-ui/Master-Haven/).

HAVEN_TESTS=/home/parker/docker/haven-ui/Master-Haven/tests

# Hourly fast smoke (4 Haven + 1 Exchange + 2 public-API tests, ~10s)
0 * * * * $HAVEN_TESTS/cron/run_smoke.sh

# Daily slow smoke (poster Playwright renders, ~60s)
15 6 * * * $HAVEN_TESTS/cron/run_smoke.sh --slow

# Daily verify tier (in-process TestClient, ~30s)
0 3 * * * $HAVEN_TESTS/cron/run_verify.sh

# Daily Pi state check
30 4 * * * $HAVEN_TESTS/cron/pi_check.sh > /home/parker/pi-check.log 2>&1
```

Install with:

```bash
crontab -e
# Paste the above (with $HAVEN_TESTS replaced by the absolute path),
# save, and exit.
crontab -l   # confirm
```

## Verifying the webhook works

After populating `tests/.env` with `HAVEN_SMOKE_WEBHOOK_URL=...`, run a
no-op alert from the Pi:

```bash
cd $HAVEN_TESTS
python -c "from haven_smoke.alerter import alert; alert(title='Haven smoke v1 webhook test', body='If you see this in Discord, the webhook works.', severity='info', mode='smoke')"
```

This posts a single embed (color blue, severity=info). If you don't see it
in Discord within ~10 seconds, the webhook URL is wrong or the channel
permissions are off. The alerter writes a fallback log to
`~/haven-smoke-alerts.log` so failures aren't silent.

## Reading pi_check.sh output

Output is pipe-delimited:

```
2026-04-29 04:30:00|docker.haven|PASS|haven-control-room (Up 4 days)
2026-04-29 04:30:00|docker.keeper|PASS|the-keeper (Up 4 days)
2026-04-29 04:30:00|disk.root|PASS|34% used (212G/586G), 374G free
2026-04-29 04:30:00|cron.smoke_hourly|PASS|entry found
...
```

Status values:
- `PASS` — check succeeded
- `FAIL` — check failed (exit code 1)
- `SKIP` — check not applicable (config missing, optional component)
- `WARN` — non-blocking issue (e.g., NTP sync uncertain)
- `INFO` — informational only (uptime, memory totals)

Quick scan for problems:

```bash
$HAVEN_TESTS/cron/pi_check.sh | grep -E '\|FAIL\|'
```

## Logs

- Smoke run logs: `~/haven-smoke-logs/smoke-<timestamp>.log` (kept 14 days)
- Verify run logs: `~/haven-smoke-logs/verify-<timestamp>.log` (kept 14 days)
- pi_check.sh: redirected to `~/pi-check.log` per cron line above (overwrites)
- Alert fallback log (when webhook unset): `~/haven-smoke-alerts.log`

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Cron silently does nothing | Cron runs in a minimal env. Make sure `tests/.env` exists and the script's shebang `#!/usr/bin/env bash` works. Check `/var/log/syslog` for cron errors. |
| All smoke tests 401 | The /api/public/* endpoints don't need auth — but if the Haven container is misconfigured (e.g., behind a bad proxy), they may. Check Haven logs. |
| Poster tests timeout repeatedly | First Playwright render is ~30-60s cold. The `--slow` cron has a 60s timeout — bump `SMOKE_SLOW_TIMEOUT_SECONDS` in `.env` if needed. |
| Verify tests fail with `no such table` | The throwaway DB migration runner is documented to tolerate one known-broken migration (1.32.0). If others start failing too, see `tests/PHASE3_REPORT.md`. |
| Cron alerts not arriving | (1) `HAVEN_SMOKE_WEBHOOK_URL` empty, (2) Discord rate limit hit, (3) firewall blocking outbound. Check `~/haven-smoke-alerts.log`. |

## Manual invocation (Win-dev mode)

To run smoke tests against `havenmap.online` from a development machine,
without cron:

```bash
cd path/to/Master-Haven/tests
HAVEN_BASE_URL=https://havenmap.online \
EXCHANGE_BASE_URL=https://exchange.havenmap.online \
python -m pytest smoke/ -v
```

(Substitute the real Exchange URL once it's set.)
