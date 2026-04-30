# Haven Smoke + Verification Test Suite v1 — Phase 2 Proposal

**Phase:** 2 (proposal only — no test code written; Phase 3 implements after Parker approves)
**Date:** 2026-04-29
**Branch:** `claude/festive-ptolemy-7aa7c3`
**Predecessor:** [INVESTIGATION_REPORT.md](INVESTIGATION_REPORT.md)
**Companions:** [proposals/keeper-heartbeat-proposal.md](proposals/keeper-heartbeat-proposal.md), [FOLLOWUP.md](FOLLOWUP.md)

This is the contract for v1. If Parker signs off, Phase 3 implements exactly what's in here. Anything not in this document is out of scope for v1 and lives in [FOLLOWUP.md](FOLLOWUP.md).

---

## 1. Goals (and explicit non-goals)

### v1 must deliver

- A repeatable answer to "is Haven up and serving the right shape of data?" runnable from the Pi (cron) or from Win-dev (manual remote).
- A repeatable answer to "did the recently-fixed `/fingerprint` and `/atlas` slash commands construct the right embed URLs?" runnable as a Python unit test, no Discord network.
- A repeatable answer to "does `/api/extraction` accept a current-shape extractor payload and persist correctly?" runnable in-process against a throwaway DB.
- A Pi-side script that Parker runs (manually or via cron) to confirm container/disk/cron state.
- Discord webhook alerting on smoke failures with sane noise control.
- Repo hygiene: 5 stale files scheduled for deletion (authorized; happens in Phase 3).

### v1 explicitly will NOT deliver

- Coverage of the WarRoom subsystem (67 routes — too large for v1, not in the failure-mode hot path).
- Coverage of every Haven router. v1 covers the routes that fail in ways users notice or that just got fixed.
- A Keeper liveness check beyond container-up. The heartbeat work is a separate proposal for Stars.
- A Viobot verification tier. We test Viobot only at the Pi-process and file-existence level.
- Any modification to The_Keeper or Viobot source code.
- Any modification to production data. **Verification tests use a throwaway DB; smoke tests are read-only against live infra.**
- Off-Pi backup work. That's a separate task ([FOLLOWUP.md](FOLLOWUP.md)).

---

## 2. Final File Tree

```
tests/
├── INVESTIGATION_REPORT.md          # Phase 1 — done
├── PROPOSAL.md                      # this file
├── FOLLOWUP.md                      # deferred items
├── README.md                        # Phase 3 — how to run, env vars, troubleshooting
├── pytest.ini                       # marker registration, default options
├── conftest.py                      # shared fixtures (TestClient, tmp_db, fake_interaction)
├── requirements.txt                 # pytest pins, separate from Haven-UI/requirements.txt
├── .env.example                     # documents required env vars; never committed values
│
├── proposals/
│   └── keeper-heartbeat-proposal.md # Stars-facing — code change to The_Keeper
│
├── fixtures/
│   ├── extractor_payload_basic.json       # canonical from approvals.py:2425-2463
│   ├── extractor_payload_no_trade.json    # no_trade_data=true variant
│   └── extractor_payload_keeper_bot.json  # X-API-Key="Keeper 2.0" variant
│
├── smoke/                           # live-infra HTTP probes (pytest)
│   ├── __init__.py
│   ├── test_haven_live.py           # 4 tests
│   ├── test_haven_public_apis.py    # 2 tests (voyager-fingerprint, galaxy-atlas)
│   ├── test_haven_posters.py        # 2 tests, marked @slow (P1)
│   └── test_exchange_live.py        # 1 test
│
├── verify/                          # in-process TestClient, throwaway DB
│   ├── __init__.py
│   ├── test_extraction_roundtrip.py # 2 tests (basic + no_trade_data)
│   ├── test_keeper_voyager.py       # 3 tests (fingerprint URL, atlas URL, autocomplete)
│   └── test_haven_internal_isolation.py  # 0 tests; just the conftest guard rails
│
├── cron/
│   ├── pi_check.sh                  # Pi-side bash, no python deps
│   ├── run_smoke.sh                 # cron entry: runs smoke/ tier + alerts
│   ├── run_verify.sh                # nightly: runs verify/ tier
│   └── README.md                    # crontab examples + how to install
│
└── archive/                         # files moved here in Phase 3 (NOT deleted)
    └── README.md                    # explains why each file was archived

# In Haven-UI/scripts/, in Phase 3:
#   smoke_test.py is moved to tests/archive/legacy_smoke_test.py
# In Haven-UI/tests/, in Phase 3:
#   tests/api/test_endpoints.py     -> tests/archive/legacy_api_test_endpoints.py
#   tests/api/test_api_calls.py     -> tests/archive/legacy_api_test_api_calls.py
#   tests/api/test_post_discovery.py -> tests/archive/legacy_api_test_post_discovery.py
#   tests/integration/test_integration.py -> tests/archive/legacy_integration_test.py
```

**Why archive instead of delete:** the 5 stale files contain payload patterns and DB inspection helpers that may be useful as reference when Phase 3 writes new tests. Once v1 lands and is proven stable, [FOLLOWUP.md](FOLLOWUP.md) tracks deletion of the archive. Parker authorized deletion; archive-then-delete is a safer two-step.

### What stays where it is, untouched

- `Haven-UI/tests/test_nms_namegen.py` — works, unrelated to smoke suite
- `Haven-UI/tests/e2e/wizard-*.spec.ts` — Playwright frontend tests, separate concern
- `Haven-UI/tests/data/*` — test data generators, not test runners
- `The_Keeper/tests/test_commands.py` — Stars's territory; do not touch
- `Haven-Exchange/tests/smoke_test_e2e.py` — already comprehensive

---

## 3. Test List (v1: 14 tests, 10 P0 + 4 P1)

Per Q8: ~10 P0 + 3-4 highest-value P1. Final count is 14.

### Smoke tier — 9 tests

Targets live infrastructure. Read-only. No DB writes.

| # | Test | Pri | Endpoint | Pass criteria |
|---|---|---|---|---|
| 1 | `test_haven_status_ok` | **P0** | `GET /api/status` | 200; JSON has `status=="ok"`; `version` matches `^\d+\.\d+\.\d+$` |
| 2 | `test_haven_db_stats_sane` | **P0** | `GET /api/db_stats` | 200; `total_systems > 1000` (range, never `==`); each top-level numeric field is a non-negative int |
| 3 | `test_haven_communities_listed` | **P0** | `GET /api/communities` | 200; response is list with `len >= 1`; each entry has `name` and `tag` |
| 4 | `test_haven_systems_paged` | **P0** | `GET /api/systems?limit=10` | 200; `len(systems) <= 10`; each row has `id`, `glyph_code`, `galaxy` |
| 5 | `test_exchange_health_ok` | **P0** | `GET /health` (Exchange) | 200; `status=="ok"`; `service=="Travelers Exchange"` |
| 6 | `test_haven_voyager_fingerprint_api` | **P0** | `GET /api/public/voyager-fingerprint?username=parker1920` | 200; valid JSON; has expected top-level keys |
| 7 | `test_haven_galaxy_atlas_api` | **P0** | `GET /api/public/galaxy-atlas?galaxy=Euclid` | 200; valid JSON; has expected top-level keys |
| 8 | `test_haven_voyager_poster_renders` | P1 `@slow` | `GET /api/posters/voyager_og/parker1920.png` | 200; `Content-Type: image/png`; body length > 5 KB |
| 9 | `test_haven_atlas_poster_renders` | P1 `@slow` | `GET /api/posters/atlas/Euclid.png` | 200; `Content-Type: image/png`; body length > 5 KB |

### Verification tier — 5 tests

In-process. No live infra. Throwaway DB created from migrations at test setup, destroyed at teardown.

| # | Test | Pri | What it exercises | Pass criteria |
|---|---|---|---|---|
| 10 | `test_extraction_creates_pending_row` | **P0** | POST `extractor_payload_basic.json` to `/api/extraction` via TestClient | 201 (or 200 per current handler); a new row exists in `pending_systems` with `status='pending'`, `glyph_code` matching payload, `source` resolved to `haven_extractor` (no API key sent → manual; with X-API-Key for per-user extractor key → `haven_extractor`) |
| 11 | `test_extraction_no_trade_data_nullified` | P1 | POST `extractor_payload_no_trade.json` to `/api/extraction`; approve via `/api/approve_system/{id}` (admin session) | After approval, the `systems` row has `economy_type IS NULL`, `economy_level IS NULL`, `conflict_level IS NULL`, `dominant_lifeform IS NULL` — guards the v1.48.2 fix |
| 12 | `test_keeper_fingerprint_url_format` | **P0** | Construct fake `discord.Interaction`, invoke `VoyagerCog.fingerprint.callback` | `interaction.response.send_message` called once with embed; `embed.image.url` matches `https://havenmap.online/api/posters/voyager_og/<lowercase-slug>.png?v=<int>`; `embed.url` matches `https://havenmap.online/voyager/<slug>` |
| 13 | `test_keeper_atlas_url_format` | **P0** | Same with `galaxy="Hilbert Dimension"` | URL contains `Hilbert%20Dimension` (URL-encoded); `embed.set_image` called with the encoded path |
| 14 | `test_keeper_atlas_autocomplete_filters` | P1 | Invoke `VoyagerCog.atlas_autocomplete` with `current="hil"` | Returns `<= 25` `app_commands.Choice`; every choice's `.name` contains `"hil"` (case-insensitive); choice list is non-empty |

### Pi check — separate deliverable, not pytest

`tests/cron/pi_check.sh` runs as a bash script. **Not** part of the pytest suite. Contract in §6.

### Test counts by priority

| Priority | Smoke | Verify | Total |
|---|---:|---:|---:|
| P0 | 7 | 3 | 10 |
| P1 | 2 | 2 | 4 |
| **Total** | **9** | **5** | **14** |

P1 failures are tracked but do not page Parker on first failure; see §7.

---

## 4. Per-Service Test Pattern

Each service uses a different harness because the underlying code shapes differ.

### Haven-UI smoke tests — pure HTTP

```text
fixture: base_url (default https://havenmap.online; override with HAVEN_BASE_URL env)
fixture: requests_session  (auto-retries off; we want flake to surface)

pattern:
  resp = requests_session.get(f"{base_url}/api/status", timeout=10)
  assert resp.status_code == 200
  assert resp.json()["status"] == "ok"
```

No auth needed for the v1 smoke endpoints — all `/api/public/*`, `/api/status`, `/api/db_stats`, `/api/communities`, `/api/systems` are public.

### Haven-UI verification tests — TestClient + throwaway DB

**Architectural caveat (important):** Haven-UI's backend uses raw `sqlite3.connect()` via `Haven-UI/backend/paths.py`, **not** SQLAlchemy. The Haven-Exchange `StaticPool` pattern doesn't directly apply.

Approach for v1:

```text
fixture (session-scoped): tmp_haven_db
  1. Create tmp_path / haven_ui.db
  2. Monkeypatch the resolved DB path in paths.py module to point at tmp_path
  3. Run migrations.run_migrations() against the temp file to populate schema
  4. Yield the path
  5. Tear down: tmp_path is automatically cleaned by pytest

fixture (session-scoped): haven_app
  1. Depend on tmp_haven_db
  2. Import Haven-UI.backend.control_room_api and grab the FastAPI app
  3. Yield the app

fixture (function-scoped): haven_client
  1. Depend on haven_app
  2. Yield TestClient(haven_app)
  3. After yield: SELECT-based DB cleanup of any rows the test created (or skip if session DB is destroyed at end)
```

**Conftest guard rail (test #14a — internal, never fails normally):**

```text
def pytest_configure(config):
    resolved_db_path = paths.get_db_path()
    expected_temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    actual = pathlib.Path(resolved_db_path).resolve()
    if not str(actual).startswith(str(expected_temp_root)):
        pytest.exit(
            f"ABORT: tests resolved DB to {actual}, "
            f"expected something under {expected_temp_root}. "
            f"Refusing to run — this would touch production data."
        )
```

This is the safety net for Q7. If conftest.py is misconfigured or someone forgets the monkeypatch, we abort before any test touches `~/haven-data/haven_ui.db`.

### The_Keeper verification tests — fake Discord interaction, no network

Pattern from `The_Keeper/tests/test_commands.py` already exists. v1 reuses the `FakeBot`/`FakeContext` infrastructure but adds slash-command testing for `VoyagerCog`.

```text
fixture: fake_interaction
  Creates a Mock(spec=discord.Interaction) with:
    - .user.name, .user.id (configurable per test)
    - .response.send_message = AsyncMock()
    - .followup.send = AsyncMock()
    - .response is_done() returns False initially

pattern:
  cog = VoyagerCog(bot=Mock())
  await cog.fingerprint.callback(cog, interaction, user=None, username=None)
  call = interaction.response.send_message.await_args
  embed = call.kwargs["embed"]
  assert embed.image.url.startswith("https://havenmap.online/api/posters/voyager_og/")
  assert "?v=" in embed.image.url  # cache-buster present
```

No real `discord.py` connection. No `bot.tree.sync()`. The `app_commands.checks.cooldown` decorator is bypassed when calling `.callback` directly.

### Haven-Exchange smoke test — borrow existing

The 52-scenario `Haven-Exchange/tests/smoke_test_e2e.py` is the gold standard and stays put. v1 adds a *single* additional test in `tests/smoke/test_exchange_live.py` that probes the live `/health` endpoint. This is purely a "container is responding" check; the in-process tests in Haven-Exchange already cover behavior comprehensively.

### Viobot — file/process checks only, no pytest

Per Q1 — Viobot lives outside this repo, owned by art3mis_7129. v1 covers it via `pi_check.sh`:

- Container running: `docker ps --filter name=$VIOBOT_CONTAINER_NAME`
- Source path resolvable from `tests/.env` (`VIOBOT_SOURCE_PATH`)
- `package.json` parseable as JSON (if Node-based) or `pyproject.toml` parseable (if Python)
- Dockerfile exists and doesn't contain obvious red flags (latest tags, no HEALTHCHECK noted but not blocking)

If `VIOBOT_CONTAINER_NAME` or `VIOBOT_SOURCE_PATH` is unset in `tests/.env`, `pi_check.sh` reports `SKIP` for those rows, never `FAIL`. Parker can run the suite even before art3mis ships.

---

## 5. Cron Schedule + Alert Format

### Schedule (Pi-side)

| Cron entry | Frequency | What runs | What it covers |
|---|---|---|---|
| `0 * * * * /home/parker/haven-tests/run_smoke.sh` | Hourly | `pytest tests/smoke/ -m "not slow"` | Tests 1-7 |
| `15 6 * * * /home/parker/haven-tests/run_smoke.sh --slow` | Daily 06:15 | `pytest tests/smoke/ -m slow` | Tests 8-9 (poster renders) |
| `30 4 * * * /home/parker/haven-tests/pi_check.sh > ~/pi-check.log 2>&1` | Daily 04:30 | Pi state checks | Container/disk/cron/db |
| `0 3 * * * /home/parker/haven-tests/run_verify.sh` | Daily 03:00 | `pytest tests/verify/` | Tests 10-14 |

Verification tier runs **once daily** because (a) it's not flaky-prone like live HTTP and (b) running it hourly burns CPU on the Pi without much benefit. Smoke runs hourly because that's where outages surface.

### Alert format

```
POST $HAVEN_SMOKE_WEBHOOK_URL
Content-Type: application/json

{
  "embeds": [
    {
      "title": "Haven smoke FAILED",
      "description": "<failed-test-name>: <one-line-reason>",
      "color": 15158332,                                 // red (P0)
      "fields": [
        {"name": "Run time", "value": "<ISO timestamp>", "inline": true},
        {"name": "Host", "value": "<hostname>", "inline": true},
        {"name": "Mode", "value": "smoke|verify|pi_check", "inline": true}
      ],
      "footer": {"text": "haven-tests v1.0"}
    }
  ]
}
```

P1 failures use color `16753920` (orange) and only post after the consecutive-failure threshold below.

### Noise control (Q5)

- **P0 failures** → alert immediately, every run that fails.
- **P1 failures** (poster tests, autocomplete, no_trade_data) → state file at `~/.haven-smoke-state.json` tracks consecutive failures per test name. Alert only when `consecutive_failures >= 3`. Reset to 0 on next pass.
- **Pi check failures** → alert only on FAIL rows that did NOT FAIL yesterday (delta detection — same path as P0 except suppressed if state file shows the failure was already alerted on).
- **Webhook URL missing** → write to local log file `~/haven-smoke-alerts.log` and `echo` to stderr; never abort the run, never silently swallow.

### Webhook URL handling (Q3, hard rule #2)

- Lives in `tests/.env` (gitignored — verify `.gitignore` already covers `tests/.env`).
- Documented in `tests/.env.example` with placeholder: `HAVEN_SMOKE_WEBHOOK_URL=https://discord.com/api/webhooks/REDACTED_FILL_ME_IN`.
- Read by `run_smoke.sh` and `run_verify.sh` via `source .env 2>/dev/null || true`.
- **Alert payload generation MUST redact** any string matching `/https://discord(?:app)?\.com/api/webhooks/\S+/i` from test output, stack traces, and exception messages before sending — so a leaked URL in an error string can't echo itself back through the webhook into a logged Discord channel. This redaction is a hard requirement of the Phase 3 implementation.

---

## 6. `pi_check.sh` Contract

**Purpose:** A read-only Pi-side script that produces a single structured stream of state observations Parker (or cron + alerter) can grep.

### Inputs

- Optional `tests/.env` next to the script with overrides:
  - `KEEPER_CONTAINER_NAME` (default: `the-keeper`)
  - `HAVEN_CONTAINER_NAME` (default: `haven-control-room`)
  - `EXCHANGE_CONTAINER_NAME` (default: `economy`)
  - `VIOBOT_CONTAINER_NAME` (default: unset → SKIP)
  - `HAVEN_DATA_PATH` (default: `~/haven-data`)
  - `HAVEN_PHOTOS_PATH` (default: `~/haven-photos`)
  - `EXCHANGE_DATA_PATH` (default: `~/exchange-data` if exists, else SKIP)

### Output format (stdout, pipe-delimited)

One row per check:
```
<ISO timestamp>|<check.dotted.name>|<PASS|FAIL|SKIP|INFO>|<human-readable detail>
```

Example:
```
2026-04-29 04:30:00|docker.haven|PASS|haven-control-room (Up 4 days, healthy)
2026-04-29 04:30:00|docker.keeper|PASS|the-keeper (Up 4 days)
2026-04-29 04:30:00|docker.exchange|PASS|economy (Up 4 days, healthy)
2026-04-29 04:30:00|docker.viobot|SKIP|VIOBOT_CONTAINER_NAME not set in .env
2026-04-29 04:30:00|disk.root|PASS|34% used (212G/586G), 374G free
2026-04-29 04:30:00|disk.haven_data|PASS|present, 1.2G, mountable
2026-04-29 04:30:00|disk.haven_photos|PASS|present, 4.7G, 1842 webp files
2026-04-29 04:30:00|cron.smoke_hourly|PASS|entry found
2026-04-29 04:30:00|cron.smoke_slow|PASS|entry found
2026-04-29 04:30:00|cron.pi_check|PASS|entry found
2026-04-29 04:30:00|cron.verify|PASS|entry found
2026-04-29 04:30:00|db.haven_ui|PASS|exists, 1.1G, last write 23s ago
2026-04-29 04:30:00|db.haven_ui_wal|PASS|wal=12M, shm=32K
2026-04-29 04:30:00|db.economy|PASS|exists, 12M, last write 4h12m ago
2026-04-29 04:30:00|host.uptime|INFO|4 days, 12:34
2026-04-29 04:30:00|host.ntp|PASS|synchronized, +0.012s
2026-04-29 04:30:00|host.zram|PASS|zram0 4.0G (compressed swap active)
2026-04-29 04:30:00|host.temp|INFO|49.3'C
```

### Exit codes

- `0` if every row is PASS, SKIP, or INFO
- `1` if any row is FAIL
- `2` if the script itself crashed (bash `set -euo pipefail` triggers)

### Constraints

- Pure bash. No Python required. Must run on Raspberry Pi OS Lite without extra apt installs.
- Tools used: `docker`, `df`, `crontab`, `stat`, `awk`, `grep`, `swapon`, `vcgencmd`, `timedatectl`. All standard.
- Total runtime < 5 seconds.
- Must not write to anywhere except stdout/stderr. No log files of its own — cron captures the output.

### What it does NOT check

- Application correctness (that's smoke/verify tests).
- Network connectivity (smoke tests already exercise this end-to-end).
- DB row counts (covered by `/api/db_stats` smoke test).
- Backup file presence (covered by [FOLLOWUP.md](FOLLOWUP.md) — backup script doesn't exist yet).

---

## 7. Dependencies

### Python

`tests/requirements.txt` — separate from `Haven-UI/requirements.txt` to keep the test environment minimal:

```text
pytest>=7.0,<9
pytest-asyncio>=0.21
pytest-timeout>=2.1
requests>=2.31
httpx>=0.24                  # for fastapi.testclient
fastapi[all]>=0.100          # already a Haven-UI dep — version pinned to match
discord.py>=2.3              # already a The_Keeper dep
```

**Not** required:
- `playwright` — the poster smoke tests only verify HTTP response, they don't render anything client-side
- `selenium` / browser drivers — same
- `sqlalchemy` — Haven-UI uses raw sqlite3
- `freezegun` / `pyfakefs` — current test list doesn't need them

Phase 3 installs into the Pi's existing Haven-UI venv (no new venv) to keep deployment simple.

### Bash

- Standard POSIX bash (Raspberry Pi OS Lite default — version 5.x)
- `docker` CLI
- `crontab`
- `vcgencmd` (Pi-only; gracefully missing on non-Pi → SKIP)
- `timedatectl` (systemd; assumed present)

### Network

- Pi cron mode: `curl` to `http://localhost:8005`, `http://localhost:8010`. No outbound except the webhook URL.
- Win-dev manual mode: `requests` to `https://havenmap.online`. No SSH.

---

## 8. Estimated Runtime

| Tier | Tests | Runtime (cold) | Runtime (warm) | Notes |
|---|---:|---:|---:|---|
| Smoke (fast) | 7 | ~8s | ~5s | Pure HTTP probes, 10s timeout per test |
| Smoke (slow) | 2 | ~60s | ~15s | Poster Playwright render; cold-start dominates |
| Verify | 5 | ~25s | ~12s | Migrations + TestClient setup once per session |
| `pi_check.sh` | n/a | ~2s | ~2s | Bash; no setup |

**Total v1 cold run:** ~95 seconds. Warm: ~35 seconds. Fits comfortably within an hourly cron window.

P1 slow tests run only daily (see §5 schedule), so the hourly footprint is just the 7 fast smoke tests — under 10 seconds.

---

## 9. Repo Hygiene Plan (Phase 3)

Per Parker's authorization, these 5 files are deleted in Phase 3 (after Phase 2 sign-off). Phase 3 actually moves them to `tests/archive/` first; then [FOLLOWUP.md](FOLLOWUP.md) tracks final deletion 30 days after v1 lands stable.

| File | Reason | Phase 3 action |
|---|---|---|
| `Haven-UI/tests/api/test_endpoints.py` | Port 8000, pre-router | move → `tests/archive/legacy_api_test_endpoints.py` |
| `Haven-UI/tests/api/test_api_calls.py` | `/api/rtai/*` removed; `:8080/health` defunct | move → `tests/archive/legacy_api_test_api_calls.py` |
| `Haven-UI/tests/api/test_post_discovery.py` | Port 8000; predates discovery approval workflow | move → `tests/archive/legacy_api_test_post_discovery.py` |
| `Haven-UI/tests/integration/test_integration.py` | `data.json` removed; `/api/rtai/*` removed | move → `tests/archive/legacy_integration_test.py` |
| `Haven-UI/scripts/smoke_test.py` | Default port 8000; superseded by `tests/smoke/` | move → `tests/archive/legacy_scripts_smoke_test.py` |

Per Parker: do **not** touch `Haven-UI/tests/test_nms_namegen.py`, the e2e Playwright specs, or `tests/data/*`. Confirmed.

---

## 10. What Could Go Wrong

(Required section per Parker's brief.)

### 10.1 Schema changes mid-run

**Failure mode:** Migrations bump schema version while `tests/verify/` is mid-run. Test asserts against old column shape, false-fails, alert fires.

**Mitigation:** v1 conftest pins the migrations table by snapshotting the latest version at fixture setup; if the migrations module reports a higher version on fixture teardown vs. setup, the run is marked `skipped` (not failed) with a "schema migration during test" note. Phase 3 implements a `pytest.skip()` path that explicitly looks for this race.

This handles the case where migrations run on a freshly-pulled Pi while smoke tests are running. Skipping is safe — the next hourly run picks up the new schema.

### 10.2 Pi reboots

**Failure mode:** Pi reboots due to power loss / kernel update. Cron fires at the next scheduled minute, but Docker containers are still booting. `docker ps` returns empty. False-positive "containers not running" alerts.

**Mitigation:** `pi_check.sh` checks `host.uptime` first; if uptime < 5 minutes, the script prints `INFO|host.recently_booted|...|skipping container checks` and exits 0. Smoke tests use `requests` with a 10-second timeout — if Haven is mid-boot, the tests fail naturally and only alert on the **next** run if Haven is still down (reboot recovery is normally < 60 seconds).

Also: `run_smoke.sh` short-circuits early if `host.uptime < 120s` (waits one cycle before measuring).

### 10.3 Misconfigured webhook URL

**Failure mode:** `HAVEN_SMOKE_WEBHOOK_URL` is empty, expired, or malformed. Alerts silently fail. Outage goes unnoticed.

**Mitigation, three layers:**

1. `run_smoke.sh` checks that `$HAVEN_SMOKE_WEBHOOK_URL` is set and matches the prefix `https://discord.com/api/webhooks/`. If not, writes a `WARN` line to `~/haven-smoke-alerts.log` and continues with tests. The script never aborts on missing webhook.
2. The first alert each day includes a self-test field `"webhook_validated": true` — confirming the receiving end works. If the daily alert isn't seen in Discord, that's the smoke-of-the-smoke-system signal.
3. Phase 3 README (`tests/README.md`) ships a `make test-webhook` (or equivalent) one-liner Parker runs on first install: it posts a single embed saying "Haven smoke v1 webhook configured at <hostname>". Confirms the URL works before depending on it for outage alerts.

### 10.4 Flaky poster test → repeated alerts

**Failure mode:** Playwright cold-start takes 65s once, the daily 06:15 cron times out. Cron fires every day for the same false alarm. Parker stops trusting alerts.

**Mitigation:** poster tests are tagged `@pytest.mark.slow` AND `@pytest.mark.flaky_p1`. Per §5 noise control:

- Single failure: state file logs to `~/.haven-smoke-state.json`, no alert.
- Two consecutive failures: state file increments, no alert.
- Three consecutive failures: alert posted with embed color orange (P1) and message text including `"failed 3 days in a row — manual investigation needed"`.
- One success: counter resets to 0 silently.

This deliberately tolerates one or two cold-start blips per week. If the poster service is genuinely down for 72+ hours, Parker hears about it once.

### 10.5 Production DB grows past assertion ranges

**Failure mode:** `assert systems_count > 1000` is set during v1 install when there are ~9,000 systems. Two years later there are 60,000 systems. The assertion is now just background noise — passes whether the data is healthy or corrupted to 1,001 rows.

**Mitigation:**

- Assertions are **lower bounds based on a fraction of recent observation**, never exact. Phase 3 picks values that are at most ~10% of the live count at install time.
- [FOLLOWUP.md](FOLLOWUP.md) lists "rebaseline assertions" as a 6-month review item.
- Optional: a `tests/maintenance/rebaseline.py` helper (Phase 3 v1.1 — out of scope for v1) that queries live `/api/db_stats` and emits suggested new floors.

### 10.6 Local clock drift on Pi

**Failure mode:** Pi's clock drifts; cron fires at unexpected times; timestamps in alerts don't match Discord-server timestamps.

**Mitigation:** `pi_check.sh` reports `host.ntp` from `timedatectl status`. If `NTP service: active` is missing, row is `WARN` (not FAIL). Drift > 60s reports `WARN`. Doesn't gate any test, just visible in the daily check.

### 10.7 Webhook URL leakage via stack trace

**Failure mode:** A test's exception message includes the env var value (e.g., a malformed URL was passed to `requests.post()` and the URL appears in the traceback). The alerter posts the traceback verbatim. URL is now public in a Discord channel.

**Mitigation (hard requirement):** the alerter applies a redaction regex BEFORE building the embed payload:

```python
REDACT = re.compile(r"https://discord(?:app)?\.com/api/webhooks/\S+", re.I)
description = REDACT.sub("[REDACTED-WEBHOOK]", description)
```

Phase 3 implementation MUST include this regex AND a unit test that asserts the redaction happens. The unit test is a fixed-string round-trip: pass a known fake webhook URL through the alerter's redaction function and assert the output contains `[REDACTED-WEBHOOK]` instead of the URL.

This is in addition to the `tests/.env` gitignore — defense in depth.

### 10.8 TestClient accidentally hits production

**Failure mode:** Conftest forgets to monkeypatch the DB path. Verify tests run against `~/haven-data/haven_ui.db`. Production data corruption.

**Mitigation:** §4 conftest guard rail — at the **start of every pytest session**, before any test runs, conftest asserts the resolved DB path is under the system temp directory. If not, `pytest.exit("ABORT: ...")` aborts the whole session with a clear message. This was Q7's strong-agreement clause; we treat it as a P0 invariant.

Phase 3 also adds a regression test for the guard rail itself: a test that intentionally configures the DB path to a non-temp location and confirms `pytest.exit` fires.

### 10.9 Viobot directory not present locally

**Failure mode:** Parker hasn't cloned Viobot yet, or it's at a different path than `tests/.env` says. `pi_check.sh` errors out.

**Mitigation:** every Viobot-related check is gated on `[ -n "${VIOBOT_CONTAINER_NAME:-}" ] && [ -d "${VIOBOT_SOURCE_PATH:-/nonexistent}" ]`. If either isn't set, that row prints `SKIP|<check.name>|VIOBOT_* not configured` and the script continues. Never FAIL.

### 10.10 Keeper container name varies in production

**Failure mode:** Parker renamed the container to `keeper-bot` in prod; `the-keeper` from compose isn't the actual name. `pi_check.sh` reports `FAIL|docker.keeper|the-keeper not running` even though the bot is fine.

**Mitigation:** §6 — `KEEPER_CONTAINER_NAME` in `tests/.env` overrides the default. Documented in `.env.example`.

### 10.11 Slash command test invokes real Discord API

**Failure mode:** The `discord.Interaction` mock isn't tight enough; some attribute access falls through to a real network call. Test slows down or pollutes a real channel.

**Mitigation:** all Interaction objects are constructed with `Mock(spec=discord.Interaction)`. The `.response.send_message`, `.followup.send`, and any other I/O methods are explicitly assigned to `AsyncMock()`. Phase 3 implementation includes a conftest assertion that no `aiohttp.ClientSession` was created during the test (using a sentinel patch).

### 10.12 Test fixtures leak between runs

**Failure mode:** Verify test creates a `pending_systems` row in the throwaway DB. The next test in the same session sees that row and gets confused.

**Mitigation:** verify tests use **function-scoped TestClient** (new client per test), and the underlying DB is a session-scoped temp file. Each test that mutates state must use a database savepoint or explicitly DELETE rows it creates in a `finally` block. Phase 3 enforces this by running each verify test twice in CI — if the second run produces different output, the test isn't isolated.

### 10.13 Discord rate limits on alert webhook

**Failure mode:** Cron alerts fire too frequently (e.g., loop bug fires 10 alerts in 30 seconds), Discord rate-limits the webhook, subsequent alerts are dropped.

**Mitigation:** the alerter has a hardcoded floor of 30 seconds between consecutive POSTs to the same webhook. State stored in `~/.haven-smoke-state.json`. If a second alert fires within 30s, it's coalesced into a "+N similar alerts in last 30s" line on the next post.

---

## 11. Phase 3 Acceptance Criteria

For Phase 3 (implementation) to be considered complete:

- [ ] All 14 tests in §3 pass against the local Pi (or against `https://havenmap.online` from Win-dev) in a single `pytest` invocation.
- [ ] `pi_check.sh` runs cleanly on the Pi with all PASS or SKIP rows, exit 0.
- [ ] `tests/.env.example` is committed; `tests/.env` is in `.gitignore`.
- [ ] Webhook redaction regex is implemented AND has a unit test in `tests/verify/`.
- [ ] DB-path guard rail in `conftest.py` is implemented AND has a unit test that asserts `pytest.exit` fires when production path is detected.
- [ ] [tests/README.md](README.md) (Phase 3) documents how to run each tier, where env vars come from, and how to verify the webhook works.
- [ ] [tests/cron/README.md](cron/README.md) shows the four crontab entries from §5.
- [ ] 5 stale files moved to `tests/archive/` (per §9).
- [ ] No source files outside `tests/` are modified.
- [ ] No webhook URLs in any committed file.
- [ ] No git commits, pushes, or branch operations performed by Claude — Parker handles VCS.

---

## 12. Open Questions for Parker (before Phase 3)

These are smaller than the Phase-1 questions; default answers are noted.

1. **Crontab installation:** does Parker want the Phase-3 deliverable to include an `install_cron.sh` that adds the four entries automatically, or does Parker prefer to copy-paste from `tests/cron/README.md`? **Default:** ship a copy-pasteable example, no auto-install.
2. **Test username for fingerprint poster:** §3 uses `parker1920`. Acceptable, or use a sentinel like `smoke_test_user`? **Default:** `parker1920` — real data, will surface real failures.
3. **Webhook channel:** any preference for which Discord channel receives smoke alerts? Doesn't affect implementation; just confirming there is a target. **Default:** Parker's choice; not Claude's concern.
4. **`run_verify.sh` failure policy:** verify tier failures might be high-signal (DB schema break). Should they alert P0 (color red, immediate) like smoke, or P1 (3-failure threshold)? **Default:** P0 — schema breakage is rare and worth waking up for.
5. **PR / commit boundary:** Phase 3 will produce ~10-15 new files. Does Parker want them all in one commit, or split (proposal docs first, then test code, then cron scripts)? **Default:** Parker's call; Claude doesn't commit. Phase 3 produces a final summary listing files for Parker to stage.

---

**End of Phase 2 proposal.** Awaiting Parker's review. Phase 3 implementation begins on approval.
