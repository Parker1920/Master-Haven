# Cleanup Pass 3 Report
**Date:** 2026-03-08

## Part A: Flagged Item Removals

### A1: Remove RTAI system
- **Verification results:** No frontend components import or reference any RTAI endpoint. All RTAI code is self-contained in control_room_api.py (try/except import, 4 endpoints, websocket, init function) + server.py (import + init call). The `roundtable_ai` package does not exist — the import always fails, `HAVE_RTAI` is always `False`.
- **Status:** Removed
- **Files modified:** 2 (`control_room_api.py`, `server.py`)
- **Items removed:**
  - try/except import block for `roundtable_ai` (7 lines)
  - `HAVE_RTAI` and `rtai_instance` globals (2 lines)
  - `GET /api/rtai/status` endpoint (5 lines)
  - `POST /api/rtai/analyze/discoveries` endpoint (5 lines)
  - `_rtai_history` list + `GET /api/rtai/history` endpoint (5 lines)
  - `POST /api/rtai/clear` endpoint (4 lines)
  - `WS /ws/rtai` websocket handler (13 lines)
  - `init_rtai()` function (8 lines)
  - server.py: removed `init_rtai` from import and removed init call (5 lines)
- **Lines removed:** ~54
- **Anything unexpected:** None

### A2: Remove /api/generate_map endpoint
- **Verification results:** No frontend, keeper bot, or Save Watcher code calls this endpoint. Only the definition exists.
- **Status:** Removed
- **Lines removed:** 12
- **Anything unexpected:** The endpoint did nothing — just logged an activity entry and returned OK.

### A3: Remove /api/migrate_hub_tags endpoint
- **Verification results:** **Settings.jsx (line 183) has an active button** that calls `POST /api/migrate_hub_tags`. The `migrateHubTags` function (lines 177-192) includes a confirm dialog and displays migration results to the user.
- **Status:** SKIPPED — active frontend caller exists
- **Decision for Parker:** The Settings page has a "Migrate Hub Tags" button that calls this endpoint. If the migration has already been run against production and won't be needed again, both the endpoint AND the Settings.jsx button/function should be removed together.

### A4: Remove _systems_cache and _systems_lock
- **Verification results:** The cache IS written to at 3 locations:
  - Line ~9503: `_systems_cache.clear()` + repopulate after system delete (JSON fallback path)
  - Line ~10066: `_systems_cache[name] = payload` after system save
  - Line ~10069: `save_data_json({'systems': list(_systems_cache.values())})` — syncs cache to data.json
  - Line ~7957: Read as fallback when "no DB" path is taken
- **Status:** SKIPPED — intertwined with DATA_JSON legacy system
- **Reason:** `_systems_cache` is the in-memory mirror of data.json. Writes to the cache trigger `save_data_json()` which persists to disk. Removing the cache independently would break the data.json sync mechanism. This should be addressed as part of a DATA_JSON removal decision (see Part C).

## Part B: Scripts Cleanup

### B1: Dead scripts deleted (15 files)
All verified with grep — zero import/call sites outside audit reports:
- `Haven-UI/scripts/sync_json_to_db.py`
- `Haven-UI/scripts/check_oculi.py`
- `Haven-UI/scripts/add_sample_data.py`
- `Haven-UI/scripts/remove_sample_data.py`
- `Haven-UI/scripts/test_signed_hex_glyphs.py`
- `Haven-UI/scripts/migrate_star_positions.py`
- `Haven-UI/scripts/delete_core_void_systems.py`
- `Haven-UI/scripts/examine_discovery_records.py`
- `Haven-UI/scripts/fix_null_system_ids.py`
- `Haven-UI/scripts/check_pending_submission.py`
- `Haven-UI/scripts/clean_broken_submissions.py`
- `Haven-UI/scripts/test_approval.py`
- `Haven-UI/scripts/backfill_star_positions.py`
- `Haven-UI/scripts/migrations/add_missing_tables.py`
- `Haven-UI/scripts/migrations/update_planets_schema.py`
- Empty `Haven-UI/scripts/migrations/` directory also removed

### B2: Artifact deleted
- `Haven-UI/scripts/preview.pid` — stale PID file

### B3: Scripts archived
Moved to `Haven-UI/scripts/archive/`:
- `preview.py` — broken import paths, may want to fix later
- `preview.ps1` — broken import paths, may want to fix later

### B4: Path fix in create_update_archive.ps1
- **Old path:** `src/control_room_api.py`
- **New path:** `backend/control_room_api.py`
- The backend was moved from `src/` to `backend/` but this script was never updated.

### B5: Active scripts kept (not touched)
- `smoke_test.py`
- `migrate.py`
- `deploy_to_pi.ps1`
- `apply_update_remote.sh`

## Part C: DATA_JSON Investigation

### DATA_JSON Investigation Results
- **File path:** `Haven-UI/data/data.json`
- **File exists:** Yes (17 MB, last modified 2026-01-30)
- **Fields stored in data.json:** `systems` (array of 6,542 system records with full planet/moon hierarchy). No `discoveries` key exists.
- **Call sites:**

| Line | Operation | What field | Purpose |
|------|-----------|------------|---------|
| ~9420 | READ | systems | `GET /api/systems/{id}` fallback when no DB |
| ~9496 | READ | systems | `DELETE /api/systems/{id}` fallback deletion |
| ~10069 | WRITE | systems | `POST /api/save_system` backup sync after DB write |
| ~11205 | READ | discoveries | `GET /api/discoveries` fallback (returns empty — key doesn't exist) |
| ~11594 | READ | discoveries | `GET /api/discoveries/{id}` fallback (returns empty) |

- **Does /api/settings use data.json or SQLite?** SQLite only. `_settings_cache` is initialized from `super_admin_settings` table at startup. data.json is not involved in settings.
- **SQLite settings table exists?** Yes — `super_admin_settings` (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT). Contains `personal_color` and `password_hash`.
- **Overlap between data.json and SQLite?** None. data.json stores system records; SQLite settings stores key-value config. Different domains entirely.
- **Migration feasibility:** Easy — no migration needed. Settings already live in SQLite. The data.json system is a legacy pre-database fallback. All primary operations go through SQLite. data.json is only used as:
  1. A read fallback when DB doesn't exist (lines 9420, 9496, 11205, 11594)
  2. A write-through backup mirror after DB saves (line 10069)
- **Recommendation:** The data.json fallback paths are dead code in practice — the DB always exists. The write-through at line 10069 wastes I/O writing 17MB to disk on every system save. Safe to remove all load_data_json/save_data_json calls, the `_systems_cache`/`_systems_lock` globals, and the DATA_JSON constant. The data.json file itself can be archived (not deleted) as a historical backup of pre-database system data.

## Verified Working
- **Backend compiles:** Yes (`py_compile` passes)
- **Frontend builds:** Yes (`vite build` completes successfully)
- **Errors:** None

## Combined Pass 1 + 2 + 3 Totals

| Metric | Pass 1 | Pass 2 | Pass 3 | Total |
|--------|--------|--------|--------|-------|
| Files modified | 11 | 6 | 3 | 20 |
| Files created | 2 | 0 | 1 (archive/) | 3 |
| Files deleted | 0 | 6 | 18 | 24 |
| Files archived | 0 | 0 | 2 | 2 |
| Net lines removed | ~103 | ~271 | ~66 | ~440 |
| Dead functions removed | 5 | 18 | 7 | 30 |
| Dead endpoints removed | 0 | 0 | 6 | 6 |
| Dead scripts removed | 0 | 0 | 15 | 15 |

## Ready for DATA_JSON Removal
Yes — all investigation complete. If Parker approves, the removal scope is:
1. Remove `DATA_JSON` constant, `load_data_json()`, `save_data_json()` functions
2. Remove `_systems_cache` dict and `_systems_lock` asyncio.Lock
3. Remove all 5 call sites (3 reads become no-ops since DB is always available; 2 writes removed entirely)
4. Remove the `import asyncio` if no longer needed (check other uses first)
5. Archive `Haven-UI/data/data.json` to `Haven-UI/data/archive/`
