# Haven smoke + verification test suite

**Version:** 1.0 (Phase 3 implementation)
**Phase docs:** [INVESTIGATION_REPORT.md](INVESTIGATION_REPORT.md), [PROPOSAL.md](PROPOSAL.md), [FOLLOWUP.md](FOLLOWUP.md), [PHASE3_REPORT.md](PHASE3_REPORT.md)

A 14-test suite that answers two questions on a schedule:

1. **Smoke tier** — is Haven up and serving the right shape of data?
2. **Verify tier** — do recently-fixed code paths still build the right URLs / persist the right data?

## Quick start

```bash
# 1. Install deps (typically into the existing Haven venv)
pip install -r tests/requirements.txt

# 2. Configure
cp tests/.env.example tests/.env
# Edit tests/.env — at minimum set HAVEN_BASE_URL and HAVEN_SMOKE_WEBHOOK_URL

# 3. Run — all tiers
cd tests
python -m pytest -v
```

## Runtime expectations

| Tier | Cold | Warm | Notes |
|---|---:|---:|---|
| Verify | ~10-30s on Pi (~3s on Win-dev) | ~3-10s | Pays the cost of running 71 migrations against the throwaway DB **once per session**; subsequent tests are fast |
| Smoke (fast) | ~5-10s | ~3-5s | Pure HTTP probes |
| Smoke (slow) | ~60s | ~15s | Playwright cold-start dominates the first run |
| `pi_check.sh` | ~2s | ~2s | Pure bash |

Run hourly (smoke fast) and daily (verify + smoke slow) per `cron/README.md`.

## Layout

```
tests/
├── conftest.py              # session setup; DB-path guard rail; haven_app fixture
├── pytest.ini               # marker registration, default options
├── requirements.txt         # pinned deps for the test environment
├── .env.example             # copy to .env (gitignored) and fill in
│
├── smoke/                   # live HTTP probes (read-only)
│   ├── test_haven_live.py             # 4 tests — /api/status, /api/db_stats, /api/communities, /api/systems
│   ├── test_haven_public_apis.py      # 2 tests — voyager-fingerprint, galaxy-atlas
│   ├── test_haven_posters.py          # 2 tests, @slow @p1 — poster PNG renders
│   └── test_exchange_live.py          # 1 test — /health
│
├── verify/                  # in-process; uses TestClient + throwaway SQLite
│   ├── test_extraction_roundtrip.py   # 2 tests — /api/extraction → pending_systems
│   ├── test_keeper_voyager.py         # 3 tests — /fingerprint and /atlas slash commands
│   └── test_safety_unit.py            # 10 tests — webhook redaction + DB-path guard rail
│
├── fixtures/                # extractor JSON payloads
├── haven_smoke/             # alerter + redaction + state-tracking helpers
├── cron/                    # run_smoke.sh, run_verify.sh, pi_check.sh + README
├── proposals/               # docs handed to other maintainers (e.g., Stars)
└── archive/                 # 5 stale tests moved here from Haven-UI/tests/
```

## Running individual tiers

```bash
# Just live HTTP probes (fast, hourly cron uses this)
python -m pytest smoke/ -m "not slow"

# Just the slow poster tests (daily cron)
python -m pytest smoke/ -m slow

# Just verify tier (in-process, no live infra)
python -m pytest verify/

# A specific test
python -m pytest verify/test_keeper_voyager.py::test_keeper_atlas_url_format -v
```

## Markers

| Marker | What it means |
|---|---|
| `smoke` | Hits live infrastructure |
| `verify` | In-process; no network |
| `slow` | Allow up to 60s per test (Playwright cold-start tolerance) |
| `p1` | Failures throttled — alert only on 3 consecutive failures |
| `keeper` | Exercises `The_Keeper` code (no Discord network) |
| `extractor` | Exercises `/api/extraction` |
| `redaction` | Webhook-URL redaction unit test |
| `guardrail` | DB-path safety guard rail |

## Running modes

| Mode | Use | `tests/.env` settings |
|---|---|---|
| **Pi cron** | Hourly automated runs on the Pi | `HAVEN_BASE_URL=http://localhost:8005`, `EXCHANGE_BASE_URL=http://localhost:8010` |
| **Win-dev manual** | Spot-checks against production | `HAVEN_BASE_URL=https://havenmap.online` |
| **CI / sandbox** | Just the verify tier (no live infra needed) | `python -m pytest verify/` |

## Safety rails

This suite refuses to run if anything points at production:

- `pytest_sessionstart` in `conftest.py` aborts the entire session with exit code 2 if `HAVEN_DB_PATH` resolves to a path outside the OS tempdir. The throwaway DB lives under `tempfile.gettempdir()`. There is a unit test (`test_guardrail_aborts_on_production_path`) that verifies this fires correctly.
- The webhook alerter (`haven_smoke/alerter.py`) redacts any string matching the Discord webhook URL pattern from the payload before posting. There are 8 redaction unit tests.
- Verify tests use a function-scoped TestClient and a session-scoped DB path. The DB is cleaned up by `pytest_sessionfinish`.

## Troubleshooting

| Symptom | Action |
|---|---|
| Smoke tests all fail with connection refused | Check `HAVEN_BASE_URL` in `.env` matches what's actually running. On the Pi, port 8005 is the default. |
| Verify extraction test fails with `no such table: user_profiles` | Migration runner failed unexpectedly. Check the warning lines for which migration broke. v1 expects ONLY 1.32.0 to fail (known issue). |
| Guard rail fails (subprocess exit 2) | Your `HAVEN_DB_PATH` is set to a real path. Unset it or point it under tempdir. |
| Poster smoke tests timeout repeatedly | Cold Playwright start. Check `Haven-UI/docker logs haven-control-room` for poster service errors. |
| `/fingerprint` URL test fails | The_Keeper's `cmds/voyager.py` has changed shape. Read the test failure for the actual URL — most likely the slug normalizer, base URL, or cache-buster format diverged. |

## What this suite does NOT cover

See [FOLLOWUP.md](FOLLOWUP.md) for the v2 backlog. Key gaps in v1:

- WarRoom subsystem (67 routes — too large for v1)
- Approval workflow round-trip (admin login + approve)
- Profile claim flow
- The_Keeper liveness beyond container-up (heartbeat proposal lives at [proposals/keeper-heartbeat-proposal.md](proposals/keeper-heartbeat-proposal.md))
- Visual regression for posters (only checks content-type + body size)

## Contributing

- Don't modify `The_Keeper/` or Viobot from here. Read-only.
- Don't commit `tests/.env`. It's gitignored; if it ever becomes un-ignored, fix `.gitignore` immediately.
- New tests follow the layout above: smoke = live HTTP, verify = in-process. Pick one.
- New env vars get documented in `.env.example` with a placeholder value, never a real one.
