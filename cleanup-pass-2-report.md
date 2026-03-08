# Cleanup Pass 2 Report
**Date:** 2026-03-08

## Fixes Applied

### Removal 1: Dead functions in control_room_api.py
- **Status:** Complete
- **Files modified:** `Haven-UI/backend/control_room_api.py`
- **Items removed:**
  - `_row_to_dict()` (4 lines) — zero call sites
  - `is_partner()` (4 lines) — zero function call sites (local variables with same name exist but are assignments, not calls)
  - `get_partner_discord_tag()` (6 lines) — zero call sites
  - `can_access_feature()` (11 lines) — zero call sites
  - `is_sub_admin()` (4 lines) — zero function call sites (same as is_partner)
  - `get_effective_discord_tag()` (8 lines) — zero call sites
  - `get_restrictions_by_discord_tag()` (33 lines) — zero call sites
  - `List` removed from `from typing import` (unused after Pass 1 removed `apiGet`/`apiPost`)
- **Lines removed:** 71
- **Decisions made:** All 7 functions verified with grep to have zero import/call sites across the entire codebase. `is_partner` and `is_sub_admin` have local *variable* assignments with those names in various endpoints, but no function calls.

### Removal 2: DATA_JSON legacy system
- **Status:** SKIPPED — NOT dead code
- **Reason:** `DATA_JSON`, `load_data_json()`, and `save_data_json()` have 6 active call sites in control_room_api.py. They manage persistent server state (themes, settings, region colors).

### Removal 3: Dead functions in paths.py
- **Status:** Complete
- **Files modified:** `Haven-UI/backend/paths.py`
- **Items removed:**
  - Class method `find_database()` (29 lines) — zero call sites via `haven_paths.find_database()`
  - Class method `find_data_file()` (34 lines) — zero call sites
  - Class method `get_backup_dir()` (5 lines) — zero call sites
  - Class method `get_data_dir()` (11 lines) — zero call sites
  - Standalone function `get_haven_paths()` (8 lines) — zero import sites
  - Standalone function `get_haven_database()` (3 lines) — zero import sites
  - Standalone function `get_keeper_database()` (3 lines) — zero import sites
  - Standalone function `get_project_root()` (3 lines) — zero import sites
  - `List` removed from `from typing import` (unused after removing `find_data_file`)
- **Lines removed:** 97
- **Kept:** `HavenPaths` class (with `__init__`, `_resolve_*` methods, `get_logs_dir`, `__repr__`), `haven_paths` global instance. `get_logs_dir` has 1 active call site in control_room_api.py.
- **Updated:** `__main__` block updated to use `haven_paths.haven_db` / `haven_paths.keeper_db` directly instead of removed convenience functions.

### Removal 4: Dead functions in glyph_decoder.py
- **Status:** Complete
- **Files modified:** `Haven-UI/backend/glyph_decoder.py`
- **Items removed:**
  - `get_glyph_image_path()` (11 lines) — zero call sites
  - `parse_glyph_sequence()` (21 lines) — zero call sites
- **Lines removed:** 32
- **Skipped:** `calculate_region_name()` — used by `tests/data/generate_test_data.py`

### Removal 5: Dead frontend components
- **Status:** Complete
- **Files deleted:** 6
  - `Haven-UI/src/components/Spinner.jsx` — zero imports
  - `Haven-UI/src/components/Toast.jsx` — zero imports
  - `Haven-UI/src/components/Tabs.jsx` — zero imports
  - `Haven-UI/src/components/TerminalViewer.jsx` — zero imports
  - `Haven-UI/src/components/QuickActions.jsx` — zero imports
  - `Haven-UI/src/pages/Logs.jsx` — zero imports
- **Decisions made:** All 6 files verified with grep to have zero import statements anywhere in the frontend codebase.

### Removal 6: Dead exports from utility files
- **Status:** Complete
- **Files modified:** 3

**`Haven-UI/src/utils/stationPlacement.js`:**
- Removed `generateRandomStationPosition()` (3 lines) — backwards-compat wrapper, zero imports
- Removed `validateStationOrbit()` (25 lines) — zero imports
- Removed `getOrbitalInfo()` (10 lines) — zero imports
- Removed `export { OBJECT_SIZES, MIN_DISTANCES }` line — zero external imports (used internally by kept `generateStationPosition`)
- Lines removed: 55
- Kept: `generateStationPosition()` (used by Wizard.jsx)

**`Haven-UI/src/data/galaxies.js`:**
- Removed `getGalaxyByIndex()` (3 lines) — zero imports
- Removed `getGalaxyByName()` (3 lines) — zero imports
- Lines removed: 6
- Kept: `GALAXIES` and `REALITIES` exports

**`Haven-UI/src/utils/economyTradeGoods.js`:**
- Removed `getAllTradeGoods()` (3 lines) — zero imports
- Removed `getTradeGoodNames()` (7 lines) — zero imports
- Changed `export const ECONOMY_TRADE_GOODS` → `const ECONOMY_TRADE_GOODS` (zero external imports, used internally)
- Lines removed: 10
- Kept: `getTradeGoodsForEconomy()`, `getTradeGoodById()`, `getTradeGoodsForEconomyAndTier()` (all have active import sites)

### Removal 7: useCallback in Python
- **Status:** N/A
- **Reason:** No `useCallback` found in any Python file. This was a speculative check from the audit.

## Items Skipped (Flagged for Parker's Review)

- `init_rtai()` and RTAI system — may have future use, needs Parker's decision
- `/api/generate_map` endpoint — may be used by external scripts
- `/api/migrate_hub_tags` endpoint — one-time migration, may be needed again
- `_systems_cache` / `_systems_lock` — caching mechanism, unclear if intentionally disabled

## Issues Encountered
- None. All removals applied cleanly.

## Verified Working
- **Backend compiles:** Yes (control_room_api.py, paths.py, glyph_decoder.py all pass `py_compile`)
- **Frontend builds:** Yes (`vite build` completes successfully)
- **Console errors:** None (only pre-existing Three.js chunk size warning)

## Summary Statistics

| Metric | Count |
|--------|-------|
| Files modified | 6 |
| Files deleted | 6 |
| Lines removed (modified files) | ~271 |
| Lines removed (deleted files) | ~6 files entirely |
| Dead functions removed | 18 (7 backend API, 8 paths.py, 2 glyph_decoder, 7 frontend utilities) |
| Dead exports removed | 2 (`ECONOMY_TRADE_GOODS`, `OBJECT_SIZES`/`MIN_DISTANCES`) |
| Unused imports removed | 2 (`List` from typing in 2 files) |
| Items skipped (not dead) | 1 (DATA_JSON system) |
| Items skipped (for review) | 4 (init_rtai, generate_map, migrate_hub_tags, systems_cache) |
| Items N/A | 1 (useCallback in Python) |

## Combined Pass 1 + Pass 2 Totals

| Metric | Pass 1 | Pass 2 | Total |
|--------|--------|--------|-------|
| Files modified | 11 | 6 | 17 |
| Files created | 2 | 0 | 2 |
| Files deleted | 0 | 6 | 6 |
| Net lines removed | ~103 | ~271+ | ~374+ |
| Dead functions removed | 5 | 18 | 23 |
| Duplicate definitions eliminated | 9 | 0 | 9 |
