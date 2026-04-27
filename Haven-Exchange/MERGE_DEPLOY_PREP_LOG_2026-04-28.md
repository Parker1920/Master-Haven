# Travelers Exchange — Merge & Deploy Prep Log

**Date:** 2026-04-28
**Source dispatch:** Merge-and-deploy-prep follow-up to the Phase A/B/C
remediation finalization.
**Branch flow:** `audit-v2-remediation` → `main` (no push, no Pi).

---

## Phase 1 — Stale Audit Prose Fix

**Goal:** The V3 audit's row at line 93 still described `interest_frozen`
as flipping "permanently when cap is reached" — superseded by the
Interpretation 2 switch in commit `d258b85`. Phase C flagged this as
the only stale claim found in the V3 audit. Phase 1 fixes the prose.

### Change

`Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md` line 93 —
replaced the "flips permanently when cap is reached" sentence with
language reflecting Interpretation 2:

- Notes the Phase B follow-up commit (`d258b85`).
- Describes the flag as toggling based on running balance: flips True
  when cap is reached, False when payments draw `accrued_interest`
  below cap.
- Cross-references `INTEREST_CAP_BEHAVIOR.md` for the full doc.

No score changes. No category changes. No other lines touched.

### Phase 1 commit
Committed as `b3e995b` — `fix: V3 audit line 93 stale interest cap prose`.

---

## Phase 2 — Merge to Main

**Goal:** Merge `audit-v2-remediation` into `main` with `--no-ff` so the
remediation work remains identifiable as a unit in history. Preserve
the unrelated NMS-Haven-Extractor dirty state in the main worktree.

### Pre-merge state

- Active branch: `main`
- Tip of `main`: `79f3bcd upgrades people upgrades`
- Tip of `audit-v2-remediation`: `b3e995b fix: V3 audit line 93 stale interest cap prose`
- Main worktree dirty (NMS-Haven-Extractor work, unrelated):
  - Modified: `CLAUDE.md`, `NMS-Haven-Extractor/dist/HavenExtractor/FIRST_TIME_SETUP.bat`, `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py`, `NMS-Haven-Extractor/pyproject.toml`
  - Deleted: `HavenExtractor-mod-v1.9.2.zip`
  - Untracked: `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT.md`, `HavenExtractor-mod-v1.9.3.zip`, `audit/`

### Blocker found and resolved

First merge attempt was refused by git:

```
error: The following untracked working tree files would be overwritten by merge:
	Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V2_2026-04-26.md
```

The untracked file in the main worktree was an older draft of the V2
audit that differed from the branch version by exactly one line (the
branch version added a closing sentence to the architectural finding
on `verify_chain()`). Parker authorised deletion of the redundant
untracked copy — branch version is a strict superset, nothing lost.

After `rm Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V2_2026-04-26.md`,
the merge proceeded cleanly.

### Merge command

```
git merge --no-ff audit-v2-remediation \
  -m "Merge audit-v2-remediation: full V2 remediation, V3 audit, smoke test, interest cap fix"
```

### Post-merge state

- Tip of `main`: `98b5e9d Merge audit-v2-remediation: full V2 remediation, V3 audit, smoke test, interest cap fix`
- 19 commits ahead of `origin/main`
- 17 phase commits + the prose fix + the merge commit all visible in `git log --oneline -20`
- Working tree dirty state from NMS-Haven-Extractor: **intact and untouched** (same five modified/deleted entries, same three untracked entries minus the deleted V2 audit)
- `audit-v2-remediation` branch: **retained** (not deleted)
- Not pushed to remote.

### Phase 2 commit
The merge commit `98b5e9d` is itself Phase 2's commit. The Phase 2 log
entry above is uncommitted in the working tree at this point and will
ride along on the Phase 3 commit.

---

## Phase 3 — Post-Merge Verification

**Verdict: MERGE VERIFIED**

All five checks pass.

### 1. Smoke test re-run on main

```
$ py -m pytest Haven-Exchange/tests/smoke_test_e2e.py --tb=short
======================= 52 passed, 6 warnings in 14.83s =======================
```

52/52 pass on the merged `main` tree. 6 warnings are pre-existing FastAPI
`on_event` deprecations.

### 2. Expected files present on main

All 11 expected files present:

- ✅ `Haven-Exchange/REMEDIATION_LOG_2026-04-26.md`
- ✅ `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md`
- ✅ `Haven-Exchange/AUDIT_DIFF_V2_TO_V3.md`
- ✅ `Haven-Exchange/SMOKE_TEST_REPORT.md`
- ✅ `Haven-Exchange/INTEREST_CAP_BEHAVIOR.md`
- ✅ `Haven-Exchange/MERGE_READINESS_REPORT.md`
- ✅ `Haven-Exchange/tests/smoke_test_e2e.py`
- ✅ `Haven-Exchange/app/interest.py`
- ✅ `Haven-Exchange/app/demurrage.py`
- ✅ `Haven-Exchange/app/stimulus.py`
- ✅ `Haven-Exchange/app/wallet_health.py`

### 3. Code spot-checks (5 of 5 pass)

| # | Claim | Verified at |
|---|-------|-------------|
| 1 | Phase 2K — `buy_stock` WM guard | `app/routes/stock_routes.py:345` |
| 2 | Phase 2D — Shop status workflow + `/approve` route | `app/routes/shop_routes.py:508-511` |
| 3 | Phase 2I — `DEMURRAGE_BURN` tx type | `app/blockchain.py:32, 213, 219` |
| 4 | Phase 2H — User wallet-health columns | `app/models.py:54, 59, 68, 71` |
| 5 | Phase 2A — interest accrual engine | `app/interest.py:48 (_accrue_loan), :124 (accrue_daily_interest)` |

### 4. Stale audit prose fix verified

Line 93 of `TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md` on main now reads:

> 100% interest cap on loans (max debt = 2× principal) — **IMPLEMENTED** —
> Phase 2A (cap behavior switched to Interpretation 2 in commit `d258b85`).
> `Loan.cap_amount = principal` at creation. `accrued_interest` never
> exceeds `cap_amount`. `interest_frozen` toggles based on running
> balance — flips True when cap is reached, False when payments draw
> `accrued_interest` below cap. See `INTEREST_CAP_BEHAVIOR.md`. Daily
> `accrue_daily_interest()` job in `interest.py`.

No "flips permanently" prose remains. The Phase 1 fix is correctly on main.

### 5. NMS-Haven-Extractor dirty state intact

Pre-merge dirty list (5 changed entries + 3 untracked) is preserved on
main, modulo the `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V2_2026-04-26.md`
untracked file deleted in Phase 2 (the redundant copy):

- ✅ Modified: `CLAUDE.md`
- ✅ Modified: `NMS-Haven-Extractor/dist/HavenExtractor/FIRST_TIME_SETUP.bat`
- ✅ Modified: `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py`
- ✅ Modified: `NMS-Haven-Extractor/pyproject.toml`
- ✅ Deleted: `HavenExtractor-mod-v1.9.2.zip`
- ✅ Untracked: `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT.md`
- ✅ Untracked: `HavenExtractor-mod-v1.9.3.zip`
- ✅ Untracked: `audit/`

(Plus the Phase 2/3 log appendage in `Haven-Exchange/MERGE_DEPLOY_PREP_LOG_2026-04-28.md` itself, which is the intended uncommitted change for this phase's commit.)

Nothing belonging to the Extractor work was modified, removed, or
otherwise touched by the merge.

### Phase 3 commit
This commit folds in the Phase 2 and Phase 3 log appendages to
`MERGE_DEPLOY_PREP_LOG_2026-04-28.md` (per dispatch: Phase 2 had no
separate commit since the merge was its commit). Commit message:
`Phase 3: post-merge verification log entries`. Committed as `ffb34ee`.

---

## Phase 4 — Deployment Prep

**Verdict: READY FOR scp DEPLOY — with one pre-deploy decision.**

Six checks below. Five are clean. One (the `data/` directory and
`scp -r` interaction) requires Parker's confirmation about how the Pi's
docker-compose.yml resolves the `./data:/app/data` bind mount before the
copy happens — without that confirmation, a naive `scp -r Haven-Exchange/`
risks overwriting the Pi's production `economy.db`.

### 1. Source folder structure — PASS

`Haven-Exchange/` contents:

- `app/` — present (24 modules including `interest.py`, `demurrage.py`,
  `stimulus.py`, `wallet_health.py`, plus existing `routes/`, `templates/`,
  `static/`)
- `tests/` — present (`smoke_test_e2e.py`, `__init__.py`, `__pycache__`)
- `Dockerfile` — present (`python:3.11-slim`, `EXPOSE 8010`)
- `docker-compose.yml` — present (bind mount + healthcheck)
- `requirements.txt` — present (8 deps)
- `data/` — present **and contains a 98 KB local dev `economy.db`**.
  This file is the source of the pre-deploy decision in §6.
- `.gitignore` — present
- `.python-version` — present (`3.11`)
- 8 `.md` documentation files (audit V2/V3, audit diff, smoke report,
  remediation log, interest cap behavior, merge readiness, this prep
  log) — sit at the Haven-Exchange root.
- Cruft also present: `.pytest_cache/`, `app/__pycache__/`,
  `tests/__pycache__/` — would be copied if the deploy uses raw
  `cp`/`scp -r` and not a filtered tool.

### 2. .dockerignore / .gitignore state — ATTENTION

- **`Haven-Exchange/.dockerignore` does NOT exist.** The `Dockerfile`
  uses `COPY . .`, so the build context (the entire `Haven-Exchange/`
  folder once scp'd to the Pi) gets copied into the image — including
  `data/economy.db`, all the `.md` docs, `tests/`, `__pycache__/`,
  `.pytest_cache/`, and `.gitignore`/`.python-version`.
- The runtime bind mount `./data:/app/data` masks whatever ends up in
  the image's `/app/data` at container start, so the **runtime** behaviour
  is correct: the bind-mounted `economy.db` wins. But the image is
  larger than it needs to be and ships dev-only artifacts.
- `Haven-Exchange/.gitignore` is sound: excludes `data/*.db`, `__pycache__/`,
  `.pytest_cache/`, `*.pyc`, IDE files, OS files. (This is git-side, not
  Docker-side — Docker still copies these unless a `.dockerignore` exists.)
- **Recommended (post-deploy or before next deploy):** add a
  `.dockerignore` with at minimum:
  ```
  data/
  __pycache__/
  *.pyc
  .pytest_cache/
  .git
  .gitignore
  *.md
  tests/        # debatable — see check 5
  ```
  This is image-hygiene only. It does not block this deploy.

### 3. docker-compose.yml configuration — PASS

```yaml
services:
  travelers-exchange:
    build: .
    container_name: economy
    volumes:
      - ./data:/app/data
    ports:
      - '8010:8010'
    healthcheck: ...
    restart: unless-stopped
```

- Bind mount `./data:/app/data` present.
- Port `8010:8010` exposed.
- Service name `travelers-exchange`, container name `economy`.
- Healthcheck hits `http://localhost:8010/health` every 30s.
- **No environment variables referenced.** SECRET_KEY and admin password
  are still hardcoded in source (Phase C `MERGE_READINESS_REPORT.md` §8 —
  pre-existing security debt, deploy-time decision).
- Inline comment notes the recommended NPM-behind change (`ports` →
  `expose`) for production. Parker can pick whichever based on his
  current Pi reverse proxy setup.

### 4. Database migration safety — RECONFIRMED

Re-spot-checked `app/main.py::_run_schema_migrations` (lines 65–131):

- 30+ `ALTER TABLE … ADD COLUMN` statements, all wrapped in a
  try/except that catches the SQLite "duplicate column" error.
  Re-running the job on an already-migrated DB is a no-op.
- New `stimulus_proposals` table (Phase 2J) created via
  `Base.metadata.create_all()` which is idempotent — no-op if the table
  already exists.
- Backfills present and idempotent (`UPDATE … WHERE … = 0` /
  `WHERE … IS NULL`).

The Pi's existing `economy.db` will migrate forward cleanly on container
start. No manual intervention needed. (This was verified in Phase C; this
is a sanity confirm.)

### 5. requirements.txt integrity — ATTENTION

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
bcrypt==4.2.1
jinja2==3.1.5
python-multipart==0.0.20
aiofiles==24.1.0
apscheduler==3.10.4
```

- ✅ `apscheduler==3.10.4` — used by `main.py` for the daily GDP /
  interest / wallet-health / demurrage / stimulus jobs.
- ✅ All other deps look correct for the production runtime.
- ⚠️ **`pytest` and `httpx` are NOT listed.** The smoke test
  (`tests/smoke_test_e2e.py`) imports `pytest` and uses FastAPI's
  `TestClient`, which depends on `httpx`. These are dev-only and should
  not be in the production `requirements.txt`. **Implication:** the
  smoke test cannot be run inside the deployed container without
  `pip install pytest httpx` first. If Parker wants on-Pi smoke
  verification, either:
  - Add a `requirements-dev.txt` and run a one-shot
    `pip install -r requirements-dev.txt` inside the container, or
  - Run the smoke test from his desktop against the Pi's deployed URL
    (the test currently uses an in-memory SQLite, not a remote API, so
    it isn't a remote-testing tool — desktop-only is the natural fit).

Not a blocker.

### 6. Deployment command preview — DECISION REQUIRED

The dispatch's draft command is:

```bash
scp -r Haven-Exchange/ parker@10.0.0.229:~/docker/haven-exchange/
ssh parker@10.0.0.229
cd ~/docker/haven-exchange/
docker compose up -d --build
docker compose logs -f exchange    # actual service name is travelers-exchange
```

**Two issues to address before running.**

#### Issue A — naive `scp -r` will overwrite the Pi's production DB

The local `data/economy.db` (98 KB dev state) sits in
`Haven-Exchange/data/`. Recursive scp will copy it to
`~/docker/haven-exchange/data/economy.db` on the Pi. The
`docker-compose.yml`'s bind mount `./data:/app/data` resolves relative
to the directory you run `docker compose` from, which is
`~/docker/haven-exchange/`. So `./data` on the Pi *is*
`~/docker/haven-exchange/data/`. The dispatch text mentioned
`~/docker/haven-exchange-data/economy.db` as the bind source; that's
inconsistent with the docker-compose.yml unless Parker has a different
compose file on the Pi.

**Three safe paths forward, pick one:**

1. **Exclude `data/` at copy time** (recommended):
   ```bash
   rsync -avz --delete \
     --exclude='data/' \
     --exclude='__pycache__/' \
     --exclude='.pytest_cache/' \
     --exclude='tests/' \
     --exclude='*.md' \
     Haven-Exchange/ parker@10.0.0.229:~/docker/haven-exchange/
   ```
   `rsync --delete` keeps the Pi's deploy dir clean of stale removed
   files. The `data/` exclude protects production data. `*.md` and
   `tests/` excludes are optional (image hygiene; tests aren't
   exercised in the container).

2. **Stage-and-scp:** clean `Haven-Exchange/data/` locally before
   scp'ing, scp the whole folder, then on the Pi re-create the empty
   `data/` directory if needed (the Dockerfile's
   `RUN mkdir -p /app/data` covers that anyway).

3. **Confirm the Pi runs a different docker-compose.yml** that points
   the bind mount somewhere outside `~/docker/haven-exchange/data/`.
   In that case the naive `scp -r` is safe — but you should verify by
   reading the Pi's compose file first.

#### Issue B — service name in `docker compose logs`

The compose file's service name is `travelers-exchange` (not `exchange`).
The container name is `economy`. The correct log command is:

```bash
docker compose logs -f travelers-exchange
# or, equivalently:
docker logs -f economy
```

#### Recommended deploy sequence (assembled)

```bash
# On Windows desktop, from C:/Master-Haven:
rsync -avz --delete \
  --exclude='data/' \
  --exclude='__pycache__/' \
  --exclude='.pytest_cache/' \
  --exclude='tests/' \
  --exclude='*.md' \
  Haven-Exchange/ parker@10.0.0.229:~/docker/haven-exchange/

# SSH to Pi:
ssh parker@10.0.0.229

# On Pi:
cd ~/docker/haven-exchange/
docker compose up -d --build

# Verify:
docker compose logs -f travelers-exchange
# (or: docker logs -f economy)

# Smoke test: hit the health endpoint
curl http://localhost:8010/health
```

Drop the `--exclude='*.md'` and `--exclude='tests/'` lines if Parker
wants the audit/remediation docs and the smoke test on the Pi.

### Phase 4 commit
Documentation-only. Commit message: `Phase 4: deployment prep readiness check`.
