# Code Audit Report
**Generated:** 2026-03-08
**Status:** AUDIT ONLY — nothing has been modified

---

## 1. Critical Issues (fix first)

These are the highest-impact items — duplicates that could cause bugs or confusion about which version is authoritative.

### 1.1 Two `normalize_discord_username` functions with different logic
- **Location:** `Haven-UI/backend/control_room_api.py` line 191 AND line 6395
- **Issue:** Two functions with the same purpose but different implementations. The public version (line 191) lowercases and strips `#` discriminator. The private `_normalize_discord_username` (line 6395) additionally strips trailing 4-digit numbers heuristically. They produce different results for usernames like `"User1234"`.
- **The private version is only called once** (line 6444, in `/api/extractor/register`). The public version is called ~20 times.
- **Recommendation:** Merge into one function. Decide which normalization logic is correct and use it everywhere.

### 1.2 `tagColors` duplicated in 5 frontend files
- **Location:**
  - `Haven-UI/src/components/DiscordTagBadge.jsx` line 4
  - `Haven-UI/src/pages/CommunityDetail.jsx` line 6
  - `Haven-UI/src/pages/CommunityStats.jsx` line 26
  - `Haven-UI/src/components/LeaderboardTable.jsx` line 9
  - `Haven-UI/src/components/SystemsList.jsx` line 128 (as `useMemo`)
- **Issue:** Same color mapping object defined in 5 places. Adding a new community requires editing 5 files.
- **Recommendation:** Extract to a shared utility (e.g., `src/utils/tagColors.js`) and import everywhere.

### 1.3 `TYPE_INFO` (discovery type metadata) duplicated in 3 files
- **Location:**
  - `Haven-UI/src/pages/CommunityStats.jsx` line 10
  - `Haven-UI/src/pages/DiscoveryType.jsx` line 16
  - `Haven-UI/src/pages/PartnerAnalytics.jsx` line 16
- **Issue:** Same discovery type emoji/label mapping defined in 3 places. Adding a discovery type requires editing 3 files.
- **Recommendation:** Extract to `src/data/discoveryTypes.js` and import everywhere.

### 1.4 `/api/settings` triple-fetched on every page load
- **Location:**
  - `Haven-UI/src/App.jsx` line 88 — applies theme CSS variables
  - `Haven-UI/src/components/ThemeProvider.jsx` line 12 — applies same theme CSS variables
  - `Haven-UI/src/utils/usePersonalColor.js` line 32 — reads personal color from settings
- **Issue:** Three independent network requests for the same endpoint on every page load. App.jsx and ThemeProvider.jsx do the **exact same thing** (apply theme CSS vars).
- **Recommendation:** Remove the duplicate theme-apply logic (keep ThemeProvider.jsx OR App.jsx, not both). Share settings via context instead of re-fetching.

### 1.5 Four dead exported functions in api.js
- **Location:** `Haven-UI/src/utils/api.js`
- **Issue:** `apiGet()`, `apiPost()`, `adminLogin()`, and `adminLogout()` are exported but **never imported anywhere**. `AuthContext.jsx` has its own login/logout implementations using raw fetch. The `apiGet`/`apiPost` wrappers were intended to be standard but the codebase evolved to use axios or raw fetch instead.
- **Recommendation:** Remove all four dead functions from api.js.

### 1.6 Inline photo upload bypasses shared utility
- **Location:** `Haven-UI/src/components/DiscoverySubmitModal.jsx` line 268
- **Issue:** Uses raw `fetch('/api/photos', { method: 'POST', body: formData })` instead of the shared `uploadPhoto()` from api.js, which was added in v1.42.0 to consolidate upload logic.
- **Recommendation:** Replace with `import { uploadPhoto } from '../utils/api'`.

---

## 2. Dead Code

### Backend — control_room_api.py

| Line | Name | Type | Safe to Remove |
|------|------|------|----------------|
| 943 | `_row_to_dict()` | Unused function (0 call sites) | Yes |
| 2018 | `is_partner()` | Unused function (0 call sites) | Yes |
| 2023 | `get_partner_discord_tag()` | Unused function (0 call sites) | Yes |
| 2030 | `can_access_feature()` | Unused function (0 call sites) | Yes |
| 2042 | `is_sub_admin()` | Unused function (0 call sites) | Yes |
| 2047 | `get_effective_discord_tag()` | Unused function (0 call sites) | Yes |
| 2173 | `get_restrictions_by_discord_tag()` | Unused function (0 call sites) | Yes |
| 4 | `List` from `typing` | Unused import | Yes |
| 12386 | `init_rtai()` | Unused function (never called) | Needs verification |
| 10410 | `/api/generate_map` endpoint | Non-functional stub (logs only, returns OK) | Needs verification |
| 11199 | `/api/migrate_hub_tags` endpoint | One-time migration, likely already run | Needs verification |
| 305-306 | `_systems_cache` / `_systems_lock` | Cache never populated; fallback always returns empty | Needs verification |
| 83, 308-318 | `DATA_JSON` / `load_data_json()` / `save_data_json()` | Legacy JSON file storage (SQLite is primary) | Needs verification |

### Backend — paths.py

| Function | Type | Safe to Remove |
|----------|------|----------------|
| `find_database()` | Unused (0 external callers) | Yes |
| `find_data_file()` | Unused (0 external callers) | Yes |
| `get_backup_dir()` | Unused (0 external callers) | Yes |
| `get_data_dir()` | Unused (0 external callers) | Yes |
| `get_haven_paths()` | Unused (0 external callers) | Yes |
| `get_haven_database()` | Unused (0 external callers) | Yes |
| `get_keeper_database()` | Unused (0 external callers) | Yes |
| `get_project_root()` | Unused (0 external callers) | Yes |
| All `_resolve_keeper_*` functions | Unused (Keeper bot paths) | Yes |

~60% of `paths.py` is dead code.

### Backend — glyph_decoder.py

| Function | Type | Safe to Remove |
|----------|------|----------------|
| `calculate_region_name()` (line 549) | Only used by test data generator | Yes |
| `parse_glyph_sequence()` (line 675) | Unused (0 callers) | Yes |
| `get_glyph_image_path()` (line 662) | Unused (0 callers) | Yes |

### Backend — standalone files

| File | Type | Safe to Remove |
|------|------|----------------|
| `migrate_atlas_pois.py` | One-time migration tool, completed | Yes (archive) |

### Frontend — Dead Components (never imported)

| File | Type | Safe to Remove |
|------|------|----------------|
| `src/components/Spinner.jsx` | Never imported anywhere | Yes |
| `src/components/Toast.jsx` | Never imported anywhere | Yes |
| `src/components/Tabs.jsx` | Never imported anywhere | Yes |
| `src/components/TerminalViewer.jsx` | Never imported anywhere | Yes |
| `src/components/QuickActions.jsx` | Never imported anywhere | Yes |
| `src/pages/Logs.jsx` | Dead page, no route in App.jsx | Yes |

### Frontend — Dead Exports in Utility Files

| File | Dead Exports |
|------|-------------|
| `src/utils/api.js` | `apiGet`, `apiPost`, `adminLogin`, `adminLogout` |
| `src/utils/stationPlacement.js` | `generateRandomStationPosition`, `validateStationOrbit`, `getOrbitalInfo`, `OBJECT_SIZES`/`MIN_DISTANCES` (4 of 5 exports unused) |
| `src/data/galaxies.js` | `getGalaxyByIndex`, `getGalaxyByName` (2 of 4 exports unused) |
| `src/utils/economyTradeGoods.js` | `ECONOMY_TRADE_GOODS`, `getAllTradeGoods`, `getTradeGoodNames` (3 of 6 exports unused) |

### Frontend — Unnecessary `React` Default Imports

~47 files import `React` as default (`import React, { useState } from 'react'`) but never use `React.` directly. Only 3 files actually need it: `main.jsx`, `Systems.jsx`, `LeaderboardTable.jsx`. Harmless but noisy. Low priority.

---

## 3. Inconsistent Patterns

### 3.1 Mixed HTTP client usage (axios vs fetch vs apiGet/apiPost)
- **Pattern:** Making API calls from React components
- **Current implementations:**
  - 27 files use `axios` directly
  - ~15 files use raw `fetch()`
  - `api.js` exports `apiGet`/`apiPost` wrappers around `fetch()` — never used
  - `AuthContext.jsx` has its own `login()`/`logout()` using raw `fetch()`
- **Recommended standard:** Pick one approach (axios is dominant). Remove dead `apiGet`/`apiPost`. Consider wrapping axios in a configured instance.

### 3.2 `/api/discord_tags` fetched independently in 11 components
- **Pattern:** Getting the list of Discord community tags
- **Current implementations:** Each of these components independently calls `GET /api/discord_tags` on mount: `RegionBrowser.jsx`, `Analytics.jsx`, `ApiKeys.jsx`, `DiscoverySubmitModal.jsx`, `ApprovalAudit.jsx`, `Events.jsx`, `PartnerAnalytics.jsx`, `PendingApprovals.jsx`, `RegionDetail.jsx`, `Systems.jsx`, `Wizard.jsx`
- **Recommended standard:** Extract to a custom hook `useDiscordTags()` with a cache/context to avoid 11 redundant network requests per navigation.

### 3.3 Date formatting done 3 different ways
- **Pattern:** Formatting dates for display
- **Current implementations:**
  - `new Date(x).toLocaleDateString()` — ~16 places across many files
  - `format()` from `date-fns` — `ApprovalAudit.jsx`, `DateRangePicker.jsx`
  - Custom relative time logic — `Dashboard.jsx` line 160
- **Recommended standard:** Standardize on `date-fns` since it's already a dependency.

### 3.4 Redundant local imports in control_room_api.py
- **Pattern:** Importing FastAPI response classes
- **Current implementations:** 8 route handlers at lines 1146, 1155, 1164, 1173, 1179, 1189, 1202, 1219 each do `from fastapi.responses import FileResponse, Response` despite these already being imported at line 2.
- **Recommended standard:** Remove all 8 redundant local imports.

### 3.5 Scattered imports in control_room_api.py
- **Pattern:** Import placement
- **Current implementations:**
  - Lines 1-19: Main imports
  - Lines 1892-1894: `Response`, `Cookie`, `Optional`, `secrets`
  - Line 6083: `Header`
- **Recommended standard:** Move all imports to the top of the file.

### 3.6 Two authentication verification patterns in control_room_api.py
- **Pattern:** Checking if user is authenticated and authorized
- **Current implementations:**
  - `verify_session(session)` + `is_super_admin(session)` — used in ~17 endpoints
  - `get_session(session)` → inline `session_data.get('user_type') == 'super_admin'` — used in most newer endpoints
- **Recommended standard:** Standardize on `get_session()` + inline checks (more flexible, already dominant). The `verify_session` + `is_super_admin` pattern is redundant since `is_super_admin` already calls `get_session` internally.

---

## 4. Scripts Folder Audit

All scripts are in `Haven-UI/scripts/`. The `c:\Master-Haven\scripts\` directory does not exist.

| File | Purpose | Status | Recommendation | Bugs |
|------|---------|--------|----------------|------|
| `preview.py` | Start uvicorn + open browser | Dead | Fix or archive | References `src.control_room_api:app` (moved) |
| `preview.ps1` | Same as above (PowerShell) | Dead | Fix or archive | Same broken path |
| `preview.pid` | Stale PID file | Dead artifact | Delete | N/A |
| `smoke_test.py` | HTTP smoke test | Active | Keep | None |
| `migrate.py` | CLI migration management | Active | Keep | None |
| `deploy_to_pi.ps1` | SCP upload to Pi | Active | Keep | None |
| `apply_update_remote.sh` | Pi-side archive extract | Active | Keep | None |
| `create_update_archive.ps1` | Build deploy archive | Active (broken) | Fix paths | References `src/control_room_api.py` |
| `sync_json_to_db.py` | JSON→SQLite import | Dead (one-time) | Delete | Obsolete schema |
| `check_oculi.py` | Debug: inspect one system | Dead (one-time) | Delete | N/A |
| `add_sample_data.py` | Add test data to 3 planets | Dead (one-time) | Delete | N/A |
| `remove_sample_data.py` | Reverse above | Dead (one-time) | Delete | N/A |
| `test_signed_hex_glyphs.py` | Glyph round-trip tests | Dead | Delete | Wrong `sys.path` |
| `backfill_star_positions.py` | Backfill star coords | Dead (one-time) | Archive | N/A |
| `migrate_star_positions.py` | Add star coord columns | Dead | Delete | Undefined `DB_PATHS` |
| `delete_core_void_systems.py` | Delete invalid systems | Dead | Delete | Missing `Path` import |
| `examine_discovery_records.py` | NMS save file research | Dead (one-time) | Delete | Hardcoded path |
| `fix_null_system_ids.py` | Assign UUIDs to systems | Dead (one-time) | Delete | N/A |
| `check_pending_submission.py` | Debug pending_systems | Dead (one-time) | Delete | N/A |
| `clean_broken_submissions.py` | Delete test submissions | Dead (one-time) | Delete | N/A |
| `test_approval.py` | Test approval workflow | Dead | Delete | Outdated schema |
| `migrations/add_missing_tables.py` | One-time Nov 2025 migration | Dead | Delete | Undefined variable |
| `migrations/update_planets_schema.py` | One-time Nov 2025 migration | Dead | Delete | N/A |

**Active (keep):** 5 scripts
**Dead (delete/archive):** 17 scripts + 1 artifact

---

## 5. Summary Statistics

| Metric | Count |
|--------|-------|
| **Duplicate function definitions** | 9 (tagColors×5, TYPE_INFO×3, normalize_discord_username×2) |
| **Dead functions in backend** | 14 (7 in control_room_api.py, 9+ in paths.py, 3 in glyph_decoder.py) |
| **Dead components/pages in frontend** | 6 (Spinner, Toast, Tabs, TerminalViewer, QuickActions, Logs) |
| **Dead exports in frontend utilities** | 13 (4 in api.js, 4 in stationPlacement, 2 in galaxies, 3 in economyTradeGoods) |
| **Unused imports (significant)** | 10 (1 backend `List`, 8 redundant local FastAPI imports, 1 backend `useCallback`) |
| **Unnecessary `React` imports** | ~47 files (harmless, low priority) |
| **Dead scripts to delete** | 15 files |
| **Dead scripts to archive** | 2 files (preview.py, backfill_star_positions.py) |
| **Broken scripts needing fixes** | 2 files (create_update_archive.ps1, preview.ps1) |
| **Redundant network requests** | 2 patterns (settings×3, discord_tags×11) |
| **Estimated lines of code that can be removed** | ~1,200-1,500 |

### Priority Order for Cleanup

1. **Critical duplicates** (items 1.1-1.6) — risk of bugs or divergent behavior
2. **Dead backend functions** (section 2, backend) — reduce 19k-line file size
3. **Dead frontend components** (section 2, frontend) — reduce bundle size
4. **Dead scripts** (section 4) — reduce repo clutter
5. **Inconsistent patterns** (section 3) — improve maintainability
6. **Unnecessary React imports** — cosmetic, lowest priority
