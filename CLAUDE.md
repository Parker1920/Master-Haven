# Master Haven - Project Overview

A comprehensive No Man's Sky discovery mapping and archival system for communities to catalog, share, and preserve their discoveries.

## Quick Reference

| Component | Purpose | Port | Tech Stack |
|-----------|---------|------|------------|
| **Haven-UI** | Web dashboard | 5173 (dev) / 8005 (prod) | React 18, Vite, Tailwind, Three.js |
| **Haven-UI/backend/** | Backend API | 8005 | Python, FastAPI, SQLite |
| **NMS-Haven-Extractor** | In-game data extraction | - | Python, PyMHF, NMS.py |
| **NMS-Debug-Enabler** | Debug flag enabler mod | - | Python, PyMHF, NMS.py |
| **NMS-Memory-Browser** | Live memory inspection | - | Python, PyQt6, PyMHF |
| **NMS-Save-Watcher** | Extraction queue manager | 8006 | Python, FastAPI, SQLite |
| **keeper-discord-bot** | Discord community bot | 8080 (sync API) | Python, discord.py |
| **Planet_Atlas** | 3D planetary cartography | 8050 | Python, Dash, Plotly |

> **Note:** The Keeper Discord bot is being maintained by a community member. HTTP-only is the planned direction.

## Version History

### Current Versions
| Component | Version | Last Updated | Notes |
|-----------|---------|--------------|-------|
| **Master Haven** | 1.50.1 | 2026-04-11 | Voyagers Map HIGH-severity bug fixes |
| Haven-UI | 1.48.1 | 2026-04-11 | Search pagination, station checkbox, galaxy display fixes |
| Backend API | 1.48.1 | 2026-04-11 | Search pagination, moon dedup on edit, profile_id on save_system |
| Haven Extractor | 1.6.8 | 2026-03-12 | Auto-detect game mode, fix Swamp/Waterworld plant resource |
| Debug Enabler | 1.0.0 | 2026-02-27 | NMS debug flag mod |
| Planet Atlas | 1.25.1 | 2026-01-27 | 3D cartography (submodule) |
| Memory Browser | 3.8.5 | 2026-01-27 | PyQt6 memory inspector |
| Save Watcher | 2.1.0 | 2026-01-27 | Extraction queue manager |
| Keeper Bot | 1.0.0 | 2026-01-27 | Discord bot (community-maintained) |

### Version Numbering Rules

**Format**: `MAJOR.MINOR.PATCH`

| Change Type | Bump | Examples |
|-------------|------|----------|
| **PATCH** (+0.0.1) | Bug fixes, typos, small tweaks | Fix null check, correct typo, adjust styling |
| **MINOR** (+0.1.0) | New features, enhancements | Add new page, new API endpoint, new component |
| **MAJOR** (+1.0.0) | Breaking changes, major rewrites | Schema migration, API redesign, architecture change |

**When to bump Master Haven version:**
- MAJOR: Breaking changes affecting multiple components, major migrations
- MINOR: New feature in any component that adds significant functionality
- PATCH: Only bump component versions for small fixes

**Update Process (REQUIRED):**
1. After ANY code change, update the component's version in its source file
2. Update the "Current Versions" table above with new version and date
3. Add a changelog entry describing what changed
4. For MINOR+ changes, consider if Master Haven version should also bump

**Version File Locations:**
| Component | Version Location | Also Update |
|-----------|-----------------|-------------|
| Haven-UI | `Haven-UI/package.json` → `"version"` | |
| Backend API | `Haven-UI/backend/control_room_api.py` → `/api/status` endpoint | |
| Haven Extractor | `NMS-Haven-Extractor/dist/.../haven_extractor.py` → `__version__` | `pyproject.toml` |
| Debug Enabler | `NMS-Debug-Enabler/mod/nms_debug_enabler.py` → `__version__` | |
| Planet Atlas | `Planet_Atlas/main.py` → `ATLAS_VERSION` | Submodule repo |
| Memory Browser | `NMS-Memory-Browser/CLAUDE.md` → Quick Reference | |
| Save Watcher | `NMS-Save-Watcher/CLAUDE.md` → Quick Reference | |
| Keeper Bot | `keeper-discord-bot-main/CLAUDE.md` → Quick Reference | |

### Haven Extractor Mod Zip Workflow

When updating the Haven Extractor mod, a new mod-only zip must be created for GitHub Releases:

1. **Create the new zip** from `NMS-Haven-Extractor/dist/HavenExtractor/mod/` containing only: `haven_extractor.py`, `nms_language.py`, `structs.py`, `pymhf.toml`, `__init__.py`, `haven_config.json.example`
2. **Name it** `HavenExtractor-mod-v{VERSION}.zip` and place it in the repo root
3. **Archive the old zip** by moving the previous version's zip to `NMS-Haven-Extractor/archive/`
4. **Upload** the new zip to the GitHub Release (edit the existing release or create a new one with tag `v{VERSION}`)

The auto-updater (`haven_updater.ps1`) looks for assets matching `HavenExtractor-mod-*` in the latest GitHub Release.

**Two zip types exist:**
- **Mod-only zip** (~50-60 KB): Contains just the `mod/` files. Used by the auto-updater for existing users.
- **Full distributable** (~112 MB): The entire `NMS-Haven-Extractor/dist/HavenExtractor/` folder. For new users who need the embedded Python runtime, batch scripts, etc. Created manually by zipping the full `dist/HavenExtractor/` directory.

### Changelog

#### Master Haven 1.50.1 (2026-04-11) - Voyagers Map HIGH-severity Bug Fixes
Six HIGH-severity bugs from the Voyagers Map board fixed.

**Haven-UI 1.48.1**
- Wizard: Space station checkbox (`hasStation`) now syncs from loaded system data on edit — previously it always rendered unchecked even when the system had a station (Bug-013)
- SystemApprovalTab: Approval list card now reads galaxy from the `galaxy` column (with `system_data.galaxy` fallback) instead of the always-undefined `system_galaxy` — non-Euclid submissions no longer display as "Euclid" during review (Bug-009)
- Systems page: Search bar now supports paginated results — added `searchPage`/`searchTotalPages`/`searchTotal` state, Prev/Next buttons, and page reset on new query. Real match count displayed (Bug-002)

**Backend API 1.48.1**
- `/api/systems/search`: Added `page` parameter, COUNT query for totals, `LIMIT ? OFFSET ?` pagination. Response now includes `page` and `total_pages`. Map 3D search pagination starts working automatically since it already sent `page` (Bug-002, Bug-003)
- `approve_system`: Added targeted `DELETE FROM moons WHERE planet_id = ?` before the moon INSERT loop on edit — previously moons were INSERTed without deleting existing ones, causing duplication on every resubmit (Bug-005)
- `submit_system` INSERT now populates the `galaxy` column in `pending_systems` (previously galaxy was accidentally stored in `system_region` only) (Bug-009)
- All four `/api/pending_systems` list SELECTs now include the `galaxy` column (Bug-009)
- `save_system` INSERT now populates `profile_id`, `personal_discord_username`, and `source='manual'` columns on the systems row — admin/partner direct-create no longer produces orphan rows that My Profile can't match (Bug-014)
- Migration v1.66.0: Backfills `profile_id` on historical systems via `discovered_by`/`personal_discord_username` → `user_profiles.username_normalized` lookup, defaults `source='manual'` where NULL
- Migration v1.67.0: Backfills `pending_systems.galaxy` from `system_data` JSON for all legacy rows — approval view now shows correct galaxy for historical submissions

---

#### Master Haven 1.50.0 (2026-03-23) - Codebase Refactoring
Major structural refactoring to improve maintainability and reduce duplication. No functional changes.

**Backend Architecture**
- Extracted shared constants into `constants.py`: grade thresholds, pagination limits, session timeout, tier constants, discovery constants, galaxy data
- Extracted database helpers into `db.py`: connection management, context manager, system/glyph helpers, merge/mismatch logic
- Created `services/auth_service.py`: sessions, passwords, API keys, profile helpers, self-approval prevention
- Created `services/completeness.py`: scoring logic, grade conversion via single `score_to_grade()` function
- Created `services/restrictions.py`: data restriction pipeline (6 functions)
- Extracted 211 endpoints into 12 route modules using FastAPI `APIRouter`:
  - `routes/auth.py` (8 routes): login, logout, sessions, password, settings
  - `routes/analytics.py` (15 routes): analytics + public community stats
  - `routes/partners.py` (30 routes): partner/sub-admin mgmt, audit, themes, data restrictions
  - `routes/warroom.py` (67 routes): territorial conflicts, news, claims, peace treaties
  - `routes/systems.py` (18 routes): system CRUD, search, browse, galaxies, glyphs
  - `routes/approvals.py` (11 routes): pending systems, approve/reject, batch, extraction
  - `routes/discoveries.py` (15 routes): discovery CRUD, pending, approve/reject
  - `routes/profiles.py` (13 routes): user profiles, lookup, claim, admin management
  - `routes/events.py` (6 routes): events CRUD + leaderboard
  - `routes/regions.py` (17 routes): regions, pending names, batch approve/reject
  - `routes/extractor.py` (8 routes): API keys, registration, communities
  - `routes/csv_import.py` (3 routes): CSV preview/import, photo upload

**Haven-UI 1.48.0**
- New `useDebounce` hook in `hooks/useDebounce.js` — replaced 3 identical inline implementations in Systems, RegionDetail, DiscoveryType
- New `useDateFormat` utility in `hooks/useDateFormat.js` — `formatDate()`, `formatDateShort()`, `formatRelativeDate()`, `formatDateTime()` replacing 5+ inline implementations
- Navbar refactored to data-driven `NAV_LINKS` + `NAV_GROUPS` arrays — desktop and mobile views render from same source, eliminating manual sync requirement
- New `CelestialBodyEditor.jsx` — unified planet/moon form editor with `type` prop. PlanetEditor and MoonEditor are now thin wrappers (~10 lines each vs 300+230 lines duplicated before)

---

#### Master Haven 1.49.0 (2026-03-22) - Bubble/Floating Planet Tags, Required Region Naming, Batch Region Approve
Three features: new planet attribute tags, mandatory region naming in Wizard, and batch approve/reject for pending region names.

**Haven-UI 1.47.0**
- PlanetEditor: 2 new special feature toggles — "Bubble Planet" and "Floating Islands" fill the remaining grid slots
- MoonEditor: Same 2 new toggles added
- Wizard: Planet/moon defaults include `is_bubble: 0` and `is_floating_islands: 0`
- Wizard: Region naming now **required** for unnamed regions — submission blocked until a region name is proposed or already exists
- Wizard: Unnamed region section styled as amber/required instead of gray/optional
- Wizard: `submitter_profile_id` included in region name submission payload
- Wizard: `personal_discord_username` sent for all region submissions (not just personal tag)
- SystemDetail: Bubble Planet and Floating Islands badges displayed in Special Attributes section
- PendingApprovals: Bubble Planet and Floating Islands checkboxes in planet/moon edit mode
- PendingApprovals: Bubble Planet (pink) and Floating Islands (teal) badges in read-only mode for planets and moons
- PendingApprovals: Batch mode toggle for Pending Region Names section
- PendingApprovals: Region batch select-all, clear, approve/reject with self-submission prevention
- PendingApprovals: Batch region reject modal with reason field
- PendingApprovals: Reuses existing batch results modal for region batch operations

**Backend API 1.47.0**
- Migration v1.62.0: Add `is_bubble` and `is_floating_islands` INTEGER columns to `planets` and `moons` tables
- Migration v1.63.0: Add `submitter_profile_id` INTEGER column to `pending_region_names`, backfill from `user_profiles`
- `is_bubble` and `is_floating_islands` added to all 4 planet INSERT statements (save_system, approve_system, batch_approve, extraction)
- `is_bubble` and `is_floating_islands` added to all 4 moon INSERT statements
- `is_bubble` and `is_floating_islands` added to approve_system UPDATE statement
- `is_gas_giant` added to approve_system UPDATE (was previously missing)
- `is_gas_giant` added to extraction endpoint planet_entry dict (was previously missing)
- `POST /api/regions/{rx}/{ry}/{rz}/submit` now accepts and stores `submitter_profile_id`
- `POST /api/pending_region_names/batch/approve`: Batch approve region names with self-submission prevention, name uniqueness checks, audit logging
- `POST /api/pending_region_names/batch/reject`: Batch reject region names with reason and audit logging

---

#### Master Haven 1.48.0 (2026-03-18) - Unified User Profiles (Phase 1: Backend)
Unified user identity system replacing fragmented auth across partner_accounts, sub_admin_accounts, api_keys, and anonymous submitter fields. Single `user_profiles` table with 4.5-tier permission system.

**Backend API 1.46.0**
- New `user_profiles` table: single source of truth for all user identity (username, password, tier, defaults, partner/sub-admin fields)
- 4.5-tier system: Super Admin (1), Partner (2), Sub-Admin (3), Member with password (4), Member readonly (5)
- `POST /api/profiles/lookup`: Public fuzzy username matching with Levenshtein distance for "is this you?" flow
- `POST /api/profiles/create`: Auto-create profile on first submission with optional password
- `POST /api/profiles/claim`: Claim existing profile from fuzzy match suggestions
- `POST /api/profile/login`: Passwordless member login (tier 5 read-only session)
- `GET/PUT /api/profiles/me`: View/edit own profile preferences (default civ, reality, galaxy)
- `POST /api/profiles/me/set-password`: Set password, promotes tier 5 → tier 4
- `GET /api/admin/profiles`: Admin profile list with search, tier filter, community scoping
- `PUT /api/admin/profiles/{id}/tier`: Elevate/demote users (super admin only)
- `PUT /api/admin/profiles/{id}`: Edit profile (super admin or parent partner)
- `POST /api/admin/profiles/{id}/reset-password`: Admin password reset
- Login endpoint now uses `user_profiles` table as primary auth, legacy tables as fallback
- Session system includes `profile_id` for all user types
- Self-approval prevention simplified to `profile_id` comparison with username fallback
- `/api/extraction` resolves `submitter_profile_id` from payload, API key, or username
- `/api/extractor/register` now creates a profile alongside the API key, returns `profile_id`
- `verify_api_key()` returns `profile_id` from linked profile
- `get_submitter_identity()` returns `profile_id` for audit logging
- `normalize_username_for_dedup()`: Authoritative normalization for profile dedup
- `find_fuzzy_profile_matches()`: Levenshtein distance matching for similar usernames
- `get_or_create_profile()`: Idempotent profile creation helper
- `check_self_submission()`: Centralized self-approval check replacing 5 duplicated blocks
- Migration v1.55.0: Create `user_profiles` table with indexes
- Migration v1.56.0: Add `profile_id` FK columns to 8 existing tables
- Migration v1.57.0: Backfill profiles from partner_accounts, sub_admin_accounts, api_keys, anonymous submitters
- Migration v1.58.0: Backfill `profile_id` on systems, pending_systems, discoveries, audit_log rows

---

#### Haven-UI 1.45.3 (2026-03-17) - Fix Glyph Not Loading on Edit
Fix GlyphPicker clearing database glyph codes when editing existing systems, which blocked members from submitting edits and broke region name lookup.

**Haven-UI 1.45.3**
- Fixed: GlyphPicker `onChange` effect fired on mount with empty string, overwriting the glyph_code loaded from the API for edits
- Added `useRef` guard to skip empty-string `onChange` propagation on initial mount
- Fixed: `selectedGlyphs` initialized to empty array even when `value` prop was set — now initializes from `value`
- Region name lookup now works on edit (glyph decode triggers correctly, populating region coordinates)

---

#### Master Haven 1.47.0 (2026-03-16) - Advanced Filter Cascade
Advanced filters now cascade through all browse hierarchy levels: Galaxies → Regions → Systems → Planets/Moons.

**Haven-UI 1.45.2**
- RegionBrowser now accepts and passes advanced filters to `/api/regions/grouped`
- Regions with zero matching systems are excluded when filters are active
- Page resets to 1 when filters change at the region level
- Systems.jsx passes `filters` prop to RegionBrowser (was missing)

**Backend API 1.45.3**
- `/api/regions/grouped` now accepts all 14 advanced filter parameters (star_type, economy_type, biome, weather, sentinel, resource, etc.)
- Calls shared `_build_advanced_filter_clauses()` helper — same filter logic used by `/api/systems` and `/api/galaxies/summary`
- Regions aggregation query now filters by system and planet attributes before grouping

---

#### Haven-UI 1.45.1 (2026-03-16) - Planet/Moon Filtering on SystemDetail
Advanced filters now carry through to SystemDetail page, hiding non-matching planets and moons.

**Haven-UI 1.45.1**
- SystemsList passes active planet-level filters (biome, weather, sentinel, resource) as URL query params when linking to system detail
- SystemDetail reads filter params from URL and hides planets/moons that don't match
- Moons within matching planets also filtered independently
- Header shows "Planets (2 of 5)" with active filter badges when filtering
- "Show All" / "Apply Filters" toggle button to quickly switch between filtered and unfiltered views

---

#### Backend API 1.45.2 (2026-03-16) - Fix Advanced Filters
Fix broken advanced filters on Systems page: empty sentinel dropdown, non-functional sentinel filter, garbage symbols in resource dropdown.

**Backend API 1.45.2**
- Fixed sentinel dropdown empty: `filter-options` endpoint queried non-existent `sentinel_level` column — corrected to `sentinel` (actual column name)
- Fixed sentinel filter not filtering: `_build_advanced_filter_clauses()` used `p.sentinel_level` in WHERE — corrected to `p.sentinel`
- Fixed garbage symbols in resource dropdown: `get_distinct_resources()` now validates values are `len >= 2` and start with alpha character (matching `materials` field validation)
- Migration v1.53.0: Cleans existing garbage resource values (non-alpha starting chars) from `planets` and `moons` tables by setting them to NULL

---

#### Backend API 1.45.1 (2026-03-13) - Fix WebP Photo MIME Type
Fix .webp photos displaying as raw binary text on mobile browsers when opened in a new tab.

**Backend API 1.45.1**
- Register `image/webp` MIME type at startup via `mimetypes.add_type()` — Python's MIME database doesn't include `.webp` on many systems (Raspberry Pi OS, older Linux/Windows)
- Without this, Starlette's `StaticFiles` served `.webp` files with `text/plain` Content-Type, causing mobile browsers (which respect Content-Type strictly) to render binary as text
- Desktop Chrome masked the issue via content sniffing; mobile Safari/Chrome did not

---

#### Master Haven 1.46.0 (2026-03-12) - Game Mode Tracking & Biome Subtype Plant Fix
Track game mode (Normal/Creative/Relaxed/Survival/Permadeath/Custom) from extractor to detect adjective differences, fix plant resource assignment for biome subtypes.

**Haven Extractor 1.6.8**
- Auto-detect game mode from memory via `cGcDifficultySettingPreset` enum (offset 0x11890 from player_state)
- New `_detect_game_mode()` reads difficulty preset at extraction time: Normal, Creative, Relaxed, Survival, Permadeath, Custom
- `_get_difficulty_index()` now uses detected game mode instead of hardcoded Normal/Permadeath only
- `game_mode` field added to export payload alongside `reality`
- Fixed plant resource for biome subtypes: Swamp subtype of Lush now gets Faecium instead of Star Bulb
- Added `BIOME_SUBTYPE_PLANT_OVERRIDE` dict for subtype-specific plant resource overrides
- Added Waterworld → Kelp Sac to `BIOME_PLANT_RESOURCE` dict (was missing)

**Backend API 1.45.0**
- `/api/extraction` accepts `game_mode` field from extractor payload
- `game_mode` stored in `submission_data` JSON and `pending_systems.game_mode` column
- `approve_system` and `batch_approve` copy `game_mode` to `systems` table on approval
- System detail endpoint returns `game_mode` (via SELECT *)
- Migration v1.52.0: Adds `game_mode TEXT DEFAULT 'Normal'` to `systems` and `pending_systems` tables

**Haven-UI 1.45.0**
- PendingApprovals review modal: game mode badge with color per mode (Normal=gray, Survival=orange, Permadeath=red, Creative=cyan, Relaxed=green, Custom=purple)
- SystemDetail page: game mode displayed in system attributes with mode-specific color

---

#### Master Haven 1.45.0 (2026-03-12) - Dynamic CSV Import, Pirate Conflict, Gas Giant Attribute
Dynamic CSV importer supporting multiple community formats, Pirate conflict level, Gas Giant planet attribute.

**Haven-UI 1.44.0**
- CSV Import page redesigned with two-step flow: Analyze CSV → Review column mapping → Import
- Column mapping preview shows detected fields with dropdown overrides for each CSV column
- Data preview table shows first 5 rows mapped to Haven fields
- Validation warnings for missing coordinate or system name columns
- Import results show systems grouped, rows processed, and per-row errors
- Supports portal glyphs, galactic coordinates, and NMSPortals links automatically
- Added "Pirate" option to conflict level dropdowns (Wizard, PendingApprovals) with skull icon
- SystemDetail: Pirate conflict level displays in purple with skull emoji
- PendingApprovals: Fixed economy type dropdown (added Pirate, Advanced Materials, Mass Production, Abandoned)
- PendingApprovals: Fixed economy level dropdown (now uses T1/T2/T3/T4 matching Wizard)
- PendingApprovals: Expanded biome dropdown (added Marsh, Volcanic, Infested, Desolate, Exotic, Airless, Gas Giant)
- Added "Gas Giant" planet attribute checkbox in PlanetEditor alongside existing special features
- SystemDetail: Gas Giant badge displayed in Special Attributes section
- Wizard: Gas Giant included in planet defaults

**Backend API 1.44.0**
- New `POST /api/csv_preview`: Analyzes CSV file, returns detected column mappings and preview data without importing
- Reworked `POST /api/import_csv`: Dynamic header-driven CSV parser supporting multiple formats
- Auto-detects GHUB format (row 0=region, row 1=headers) vs dynamic format (row 0=headers)
- Groups planet-level CSV rows into systems by glyph coordinates (first char = planet index)
- Galaxy resolution via `galaxies.json` — supports all 256 NMS galaxies, not just Euclid
- Notes/resources parsing: extracts special features (Dissonant System, Vile Brood, Ancient Bones, etc.) into proper boolean columns
- Normalizes conflict level values (Outlaw → Pirate, '-Data Unavailable- → None)
- Normalizes economy type and dominant lifeform values from various CSV formats
- Extracts glyphs from NMSPortals links as coordinate fallback
- Per-system region name insertion from CSV region column
- Completeness score auto-calculated for imported systems
- Added `is_gas_giant` column to all 3 planet INSERT statements and all 4 moon INSERT statements
- Migration v1.50.0: Adds `is_gas_giant` INTEGER column to planets and moons tables

---

#### Haven-UI 1.43.1 + Backend API 1.43.1 (2026-03-10) - Remove Inactivity Overlay & Rate Limiting
Remove ngrok-era API rate limiting and inactivity session pausing since Haven is now self-hosted.

**Haven-UI 1.43.1**
- Removed InactivityOverlay component (full-screen "Session Paused" / "Reconnect" modal)
- Removed InactivityContext provider and useInactivityAware hook
- Removed InactivityProvider wrapper from main.jsx
- Simplified Dashboard, Navbar, Logs, TerminalViewer — polling and WebSockets no longer pause on idle

**Backend API 1.43.1**
- Removed `check_rate_limit()` (IP-based 60/hr limit on submissions)
- Removed `check_api_key_rate_limit()` (per-key 200/hr limit on extractor submissions)
- Removed rate limit enforcement from `/api/save_system`, `/api/submit_discovery`, `/api/extraction`, `/api/check_duplicate`
- Removed in-memory registration rate limiter from `/api/extractor/register`

---

#### Master Haven 1.44.0 (2026-03-10) - Region Naming in Wizard with Reality/Galaxy Scoping
Region info section in the system submission wizard and reality/galaxy-aware region naming.

**Haven-UI 1.43.0**
- New "Region Information" section in Wizard between Reality/Galaxy selectors and System Attributes
- Auto-lookups region name when glyphs + reality + galaxy are all set
- Named regions display with green badge and system count
- Unnamed regions show inline name proposal form
- Pending region names displayed with submitter info to prevent duplicates
- Named regions offer "Propose Name Change" button for rename submissions
- Success/error feedback shown inline after submission

**Backend API 1.43.0**
- `GET /api/regions/{rx}/{ry}/{rz}`: Added `reality` and `galaxy` query params, all queries now scoped by 5 keys
- `POST /api/regions/{rx}/{ry}/{rz}/submit`: Duplicate checks now include `reality` and `galaxy`; INSERT includes both columns
- `PUT /api/regions/{rx}/{ry}/{rz}`: Scoped by `reality`/`galaxy` from payload; ON CONFLICT uses new composite key
- Migration v1.49.0: Rebuilds `regions` table UNIQUE constraint from `(region_x, region_y, region_z)` to `(reality, galaxy, region_x, region_y, region_z)` for multi-dimension support
- Added scoped indexes on both `regions` and `pending_region_names` tables

---

#### Haven-UI 1.42.1 + Backend API 1.42.1 (2026-03-08) - War Media Thumbnail Persistence
Fix war room media thumbnails not being persisted or served after the v1.42.0 image compression feature.

**Backend API 1.42.1**
- Added `thumbnail` column to `war_media` table (migration v1.48.0) to persist thumbnail filenames
- Upload INSERT now stores `thumb_filename` in the new column
- `list_war_media`, `get_war_media`, and news article media endpoints now return `thumbnail_url`
- Migration backfills thumbnail filenames for existing `.webp` war media entries

**Haven-UI 1.42.1**
- War media grid now loads 300px WebP thumbnails (`m.thumbnail_url`) instead of full-size images, falling back to `m.url` for legacy entries

---

#### Master Haven 1.43.0 (2026-03-07) - Image Compression & Thumbnails
Automatic WebP compression and thumbnail generation for all photo uploads, reducing storage ~80% and speeding up page loads.

**Haven-UI 1.42.0**
- New shared `getPhotoUrl()` and `getThumbnailUrl()` utilities in `api.js` — removed 4 duplicate function definitions
- Card/grid views (DiscoveryCard, RegionDetail, PendingApprovals list) now load 300px WebP thumbnails (~7KB each)
- Detail views (SystemDetail, DiscoveryDetailModal hero, PendingApprovals modal) load full 1920px WebP images
- PlanetEditor and MoonEditor use shared `getPhotoUrl()` instead of inline URL construction

**Backend API 1.42.0**
- New `image_processor.py` module: Pillow-based resize + WebP compression pipeline
- `POST /api/photos`: uploads now auto-compressed to WebP (quality 80, max 1920px) with 300px thumbnail
- `POST /api/warroom/media/upload`: same compression pipeline for war room images
- Response includes `thumbnail` filename, `original_size`, and `compressed_size` for transparency
- Graceful fallback: if Pillow processing fails, raw file saved as before
- Pillow added to `requirements.txt`

---

#### Master Haven 1.42.0 (2026-03-05) - Community Detail Drill-Down
Click into any community card to see a dedicated detail page with member stats, regions, and direct system navigation.

**Haven-UI 1.41.0**
- New `CommunityDetail` page at `/community-stats/:tag` — full-page drill-down for each community
- Community header with stat cards (systems, discoveries, members, upload method split)
- Members table: ranked contributors with systems, discoveries, and per-member upload method bar
- Regions section: expandable list of all regions (named + unnamed) the community has uploaded to
- Click region to expand inline → shows system names with star type dot and completeness grade badge
- Click system name → navigates directly to `/systems/:id` detail page
- Back link returns to Community Stats overview
- Community cards on CommunityStats page now clickable with hover scale effect

**Backend API 1.41.0**
- New `GET /api/public/community-regions`: lightweight regions + system lists for a community (id, name, star_type, grade only)
- Named regions sorted first, then unnamed, both by system count descending

---

#### Master Haven 1.41.0 (2026-03-05) - Public Community Stats Page
New public-facing Community Stats page showcasing all Discord communities' contributions without requiring login.

**Haven-UI 1.40.0**
- New `CommunityStats` page at `/community-stats` — fully public, no auth required
- Overview stat cards: total systems mapped, discoveries, communities, contributors
- Community cards grid: per-community system count, discovery count, member count, upload method split bar (cyan=manual, purple=extractor)
- Activity timeline: dual-area chart showing systems and discoveries over time
- Discovery type breakdown: bar chart + type cards with counts and percentages (fauna, flora, mineral, etc.)
- Contributors table: ranked list with community tags, system/discovery counts, per-member upload method ratio bar
- Community filter dropdown on contributors table
- Top-level nav link added (desktop + mobile) after Discoveries

**Backend API 1.40.0**
- New `GET /api/public/community-overview`: per-community stats (systems, discoveries, contributors, manual/extractor split) with grand totals
- New `GET /api/public/contributors`: ranked contributor list with upload method per member, optional community filter
- New `GET /api/public/activity-timeline`: combined systems + discoveries timeline with configurable granularity (day/week/month)
- New `GET /api/public/discovery-breakdown`: discovery counts by type (all communities combined)

---

#### Master Haven 1.40.0 (2026-03-02) - Analytics Source Split (Manual vs Extractor)
Separate analytics for manual web submissions and Haven Extractor mod submissions with tabbed dashboard.

**Haven-UI 1.39.0**
- Analytics page redesigned with tab system: "Manual Submissions" (default) and "Haven Extractor"
- Source overview bar showing proportional split with colored segments (cyan=manual, purple=extractor)
- Manual tab: stat cards, timeline, community breakdown, leaderboard — all filtered to manual submissions only
- Extractor tab: stat cards (registered users, active users, avg per user), timeline, community breakdown, leaderboard
- Tab badges show submission count per source
- PartnerAnalytics page: new "Source" dropdown filter (All Sources / Manual Only / Extractor Only)

**Backend API 1.39.0**
- Added `source` query parameter to 4 analytics endpoints: `submission-leaderboard`, `submissions-timeline`, `community-stats`, `partner-overview`
- Source filter treats NULL/legacy rows as `'manual'` via `COALESCE`, `companion_app` excluded from both categories
- New `GET /api/analytics/source-breakdown`: returns per-source totals (manual vs extractor) for overview bar
- New `GET /api/analytics/extractor-summary`: returns extractor-specific stats (registered users, active users 7d, avg per user) from api_keys table

---

#### Haven Extractor 1.6.7 + Backend API 1.38.6 (2026-03-01) - Fix Garbage Characters in Resources
Fix garbage box characters (□) appearing in materials display from unvalidated direct memory reads.

**Haven Extractor 1.6.7**
- Fixed direct memory read path missing `_clean_resource_string()` validation — garbage bytes from PlanetGenInput COMMON_SUBSTANCE/RARE_SUBSTANCE passed through `translate_resource()` unfiltered and displayed as □ box characters
- Hook-time and struct-fallback paths already had this validation; only the primary direct-read path was missing it

**Backend API 1.38.6**
- Fixed materials filter allowing garbage single-char or non-alpha strings through — now requires `len >= 2`, starts with alpha, is a string, excludes literal "None"
- Individual resource fields (`common_resource`, `uncommon_resource`, `rare_resource`) now validated with same rules before DB storage

---

#### Haven Extractor 1.6.6 (2026-03-01) - Fix Resource Mappings & Plant Resource Gate
Fix all 3 gas resource mappings, purple stellar metal (Quartzite not Indium), and plant resource false positives.

**Haven Extractor 1.6.6**
- CRITICAL: All 3 gas resource mappings were wrong — GAS1=Sulphurine (was Nitrogen), GAS2=Radon (was Sulphurine), GAS3=Nitrogen (was Radon)
- Fixed purple star stellar metal: PURPLE/PURPLE2 now map to Quartzite (was Indium), EX_PURPLE to Activated Quartzite (was Activated Indium) — Quartzite added in Worlds Part II
- Plant resource now gated on flora level > 0: planets with no flora (flora_raw=0) no longer get a plant resource assigned

---

#### Haven Extractor 1.6.5 (2026-03-01) - Fix Star Type Enum Mapping
Fix STAR_TYPES dict ordering to match NMS.py `cGcGalaxyStarTypes` enum, add Purple star type support.

**Haven Extractor 1.6.5**
- CRITICAL: STAR_TYPES dict had wrong ordering `{0:Yellow, 1:Red, 2:Green, 3:Blue}` — corrected to match game enum `{0:Yellow, 1:Green, 2:Blue, 3:Red, 4:Purple}`
- Added Purple (value 4) to STAR_TYPES — was returning `"Unknown(4)"` for purple stars
- Fixed STAR_COLOR_MAP struct fallback to match corrected enum ordering and include Purple
- Removed hardcoded `'Yellow'` default from backend `/api/extraction` endpoint (now defaults to `'Unknown'`)
- Migration v1.47.0: Fixes any `Unknown(N)` star_type values in systems and pending_systems JSON
- Frontend: Added Purple to PendingApprovals dropdown and display, Systems page star badge

---

#### Master Haven 1.39.1 (2026-02-28) - Edit Detection Fix for Approvals
Fix pending submissions not being recognized as edits, causing glyph conflict errors on approval.

**Backend API 1.38.3**
- Fixed: `approve_system` endpoint ignored `edit_system_id` column from `pending_systems` row — only checked `system_data` JSON `id` field, missing edits detected by glyph coordinate matching
- Fixed: `batch_approve_systems` had same `edit_system_id` blind spot
- Fixed: batch approve used exact glyph match instead of `find_matching_system()` (last-11-chars + galaxy + reality), missing same-system submissions with different planet index
- Fixed: `/api/extraction` endpoint only checked exact 12-char glyph match for duplicates — now also uses `find_matching_system()` to detect coordinate matches and sets `edit_system_id` so approval workflow correctly treats them as edits
- Extraction INSERT now includes `edit_system_id` column (was missing entirely)

---

#### Haven Extractor 1.6.4 + Backend API 1.38.5 (2026-02-28) - Star Color, Resource & Galaxy Fixes
Fix star color always sending yellow, resource `[]` bracket issue, and galaxy validation failure on production Pi.

**Haven Extractor 1.6.4**
- Fixed: star color always sent as "Yellow" — `_extract_system_properties()` now uses direct memory read (offset 0x2270) as primary, NMS.py struct as fallback
- Removed hardcoded `'Yellow'` default from struct fallback — returns `None` if struct value unmapped, keeping "Unknown" for further fallback

**Backend API 1.38.4**
- Fixed: `resources` list field in `/api/extraction` stored as `[]` when all resources were Unknown — replaced with individual `common_resource`/`uncommon_resource`/`rare_resource` fields that approval system already handles
- `materials` comma-joined string now filters out empty strings in addition to `Unknown` and `None`

**Backend API 1.38.5**
- Fixed: editing extractor-submitted systems failed with "can't find galaxy 256" on production Pi
- Root cause: `galaxies.json` was loaded from `NMS-Save-Watcher/data/` which isn't deployed to the Pi
- Fallback only had `{"0": "Euclid"}`, making every non-Euclid galaxy fail `validate_galaxy()`
- Bundled `galaxies.json` (all 256 galaxies) into `Haven-UI/backend/data/` so it deploys with the API
- Updated `GALAXIES_JSON_PATH` to use `Path(__file__).parent / 'data' / 'galaxies.json'`

---

#### Haven Extractor 1.6.3 (2026-02-28) - Fix hgpaktool Auto-Install
Fix auto-install using embedded Python path instead of sys.executable (which is NMS.exe inside pyMHF).

**Haven Extractor 1.6.3**
- Fixed: `sys.executable` inside pyMHF returns `NMS.exe`, not Python — caused game restart on auto-install attempt
- Auto-install now locates embedded Python via `Path(__file__).parent.parent / "python" / "python.exe"`
- Increased pip install timeout from 60s to 120s
- FIRST_TIME_SETUP.bat: Added step [6/7] to check for hgpaktool and install if missing

---

#### Haven Extractor 1.6.1 (2026-02-28) - Remove Hardcoded Adjective Tables
Removes all Layer 3 hardcoded adjective mapping tables (~500 lines) that produced inaccurate values, simplifying to 2-layer resolution.

**Haven Extractor 1.6.1**
- Removed `map_display_string_to_adjective()` function (~180 lines of hardcoded RARITY_*/SENTINEL_* index maps)
- Removed `map_weather_enum_to_adjective()` function (~180 lines of hardcoded WEATHER_* enum maps)
- Removed `FLORA_BY_LEVEL`, `FAUNA_BY_LEVEL`, `SENTINEL_BY_LEVEL` class tables (list-based fallbacks)
- Removed `WEATHER_BY_TYPE_STORM` class table (~90-entry weather type+storm level lookup)
- Simplified `_resolve_adjective()` to 2-layer: PAK/MBIN disk cache (primary) → in-memory Translate hook (backup) → raw text ID
- Simplified export fallback code for flora/fauna/sentinel/weather (removed BY_LEVEL list selection and WEATHER_BY_TYPE_STORM hash lookup)
- Kept integer enum mappings (FLORA_LEVELS, FAUNA_LEVELS, SENTINEL_LEVELS, LIFE_LEVELS) for capture-time enum→name conversion

---

#### Master Haven 1.39.0 (2026-02-27) - Dynamic Communities, Login Fix, Star Colors
Multiple bug fixes and extractor feature upgrade.

**Haven-UI 1.38.2**
- Fixed: star color always displayed yellow on SystemDetail page — now conditional based on star_type (Yellow/Red/Green/Blue/Purple)
- Fixed: super admin login response missing `discord_tag`, `display_name`, `enabled_features`, `account_id`
- Fixed: partner login response missing `account_id`
- Fixed: sub-admin login response missing `account_id`

**Backend API 1.38.2**
- Login endpoint responses now include all fields that AuthContext expects (`account_id`, `discord_tag`, `display_name`, `enabled_features`)
- Matches `/api/admin/status` response shape for consistent auth state

**Haven Extractor 1.6.0**
- Dynamic community list: fetches from `/api/communities` on startup, caches locally, falls back to hardcoded defaults
- `CommunityTag` enum built dynamically from server response instead of static 25-entry class
- Cache stored at `~/Documents/Haven-Extractor/communities_cache.json`
- New communities added via partner dashboard appear in extractor dropdown automatically
- Auto-updater: new `UPDATE_HAVEN_EXTRACTOR.bat` + `haven_updater.ps1` for mod-only updates via GitHub Releases
- Updater checks version, downloads mod-only zip (~500 KB), backs up current mod, preserves user config

---

#### Master Haven 1.38.1 (2026-02-26) - Galaxy Name Fix
Fix extractor galaxy naming bug and merge misnamed galaxy entries.

**Haven Extractor 1.5.1**
- CRITICAL: Replaced 6 inline galaxy_names dicts (only 11 entries each) with single module-level GALAXY_NAMES dict covering all 256 NMS galaxies
- New `get_galaxy_name()` helper: lookups from complete dict, fallback uses 1-indexed numbering (community convention) instead of 0-indexed
- Fixed: extractor sent `Galaxy_255` (0-indexed) instead of `Odyalutai` or `Galaxy_256` (1-indexed) for unmapped galaxies
- Galaxy data sourced from authoritative `NMS-Save-Watcher/data/galaxies.json`

**Backend API 1.38.1**
- Migration v1.44.0: Finds all `Galaxy_N` entries in systems and pending_systems tables, maps 0-indexed N to correct galaxy name via galaxies.json, updates galaxy column and system_data JSON

---

#### Master Haven 1.38.0 (2026-02-26) - Per-User Extractor API Keys
Per-user API keys for Haven Extractor with self-service registration, admin management dashboard, and per-user analytics.

**Haven-UI 1.38.0**
- New ExtractorUsers admin page: view registered extractor users, submission stats, community breakdown
- Super admin: edit rate limits, suspend/reactivate users
- Partners: read-only view of users who submitted to their community
- Stat cards: total users, active (7 days), total submissions, avg rate limit
- Search and filter by username, status

**Backend API 1.38.0**
- New `POST /api/extractor/register`: self-service registration, generates per-user API key tied to Discord username
- New `GET /api/communities`: public endpoint returning partner community list for extractor dropdown
- New `GET /api/extractor/users`: admin-scoped extractor user listing with per-community submission breakdown
- New `PUT /api/extractor/users/{id}`: super admin edit of rate limit and active status
- `verify_api_key()` now returns `key_type` and `discord_username`
- `/api/extraction` increments `total_submissions` and `last_submission_at` per key
- Old shared key submissions tagged as "(unregistered)" in `api_key_name`
- Migration v1.43.0: `key_type`, `discord_username`, `total_submissions`, `last_submission_at` on `api_keys`

**Haven Extractor 1.5.0**
- Per-user API key registration: auto-registers on first Export with personal key tied to Discord username
- Removed hardcoded shared API key from source code
- Transparent migration: existing users with old shared key auto-register on next Export
- `_register_api_key()` method calls `/api/extractor/register` and saves key to config
- `_save_config_to_file()` now persists the per-user key (not the old constant)
- All API calls use the per-user key from config

---

#### Master Haven 1.37.1 (2026-02-26) - Adjective Color Tier Fix
Complete fauna, flora, and sentinel text color mapping on SystemDetail page using authoritative game tier data.

**Haven-UI 1.37.1**
- New `adjectiveColors.js` utility: tier-based color functions for fauna, flora, and sentinel adjectives
- Fauna colors: HIGH (yellow-400), MID (blue-300), LOW (orange-400), NONE (gray-500), WEIRD (purple-400)
- Flora colors: HIGH (green-400), MID (blue-300), LOW (orange-400), NONE (gray-500), WEIRD (purple-400)
- Sentinel colors: AGGRESSIVE (red-400), DEFAULT (yellow-400), LOW (green-400), CORRUPT (purple-400), NONE (gray-500)
- Fixed: planet summary row only colored "Rich" — now colors all 50+ adjectives across 5 tiers
- Fixed: planet expanded detail missed Abundant, Bountiful, Copious, and other HIGH-tier values
- Fixed: moon cards only colored "Rich" — now uses full tier system
- Fixed: sentinel "Require Orthodoxy", "Ever-present" etc. showed gray — now yellow (DEFAULT tier)
- None/Absent fauna/flora now displayed as grayed-out text instead of hidden

---

#### Master Haven 1.37.0 (2026-02-26) - Super Admin Edit Pending Submissions
Super admin can edit any field in pending submissions before approval, resolving duplicate name conflicts.

**Haven-UI 1.37.0**
- PendingApprovals: "Edit" button (super admin only) toggles review modal into inline edit mode
- Edit mode: all system fields become dropdowns/inputs (name, galaxy, reality, star color, economy, conflict, lifeform, spectral class)
- Edit mode: all planet/moon fields editable (name, size, biome, weather, sentinel, fauna, flora, resources, special features checkboxes)
- Save Changes persists edits to pending_systems JSON, Cancel Edit reverts without saving

**Backend API 1.37.0**
- New `PUT /api/pending_systems/{id}` endpoint: super admin only, updates system_data JSON + syncs system_name column
- Audit trail: edit_pending action logged to approval_audit_log with old/new name tracking

---

#### Master Haven 1.36.0 (2026-02-25) - Special Planet Features & Dynamic Life Scoring
Special planet feature tracking and biome-aware completeness scoring for planet life.

**Haven-UI 1.36.0**
- PlanetEditor: 7 special feature checkboxes (Vile Brood, Dissonance, Ancient Bones, Salvageable Scrap, Storm Crystals, Gravitino Balls, Infested)
- PlanetEditor: Exotic Trophy text field for exotic biome collectible names
- Wizard: planet defaults include all new special feature fields

**Backend API 1.36.0**
- Planet Life scoring uses biome-aware dynamic denominator: Dead/Airless/Gas Giant planets skip fauna/flora from scoring when not filled (not applicable)
- Any non-empty fauna/flora value counts as filled (including 'N/A', 'None', 'Absent') - these are valid "no life" answers
- New `_life_descriptor_filled()` helper and `NO_LIFE_BIOMES` set for biome-aware logic
- 8 new planet columns: vile_brood, dissonance, ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls, infested (INTEGER), exotic_trophy (TEXT)
- All 4 planet INSERT/UPDATE locations updated (save_system, approve_system, batch_approve, extraction)
- Migration v1.40.0: Adds special feature columns + re-scores all systems with v3 scoring (abandoned + dynamic life)

---

#### Master Haven 1.35.1 (2026-02-25) - Abandoned System Support
Handles solar systems without space stations (abandoned/empty systems) for economy, conflict, and completeness grading.

**Haven-UI 1.35.1**
- Economy Tier and Conflict Level dropdowns now include "None" option
- When Economy Type is set to "None" or "Abandoned", Economy Tier and Conflict Level auto-set to "None" and are disabled
- Validation skips economy tier/conflict level for abandoned systems
- Required field indicators (*) hidden for disabled fields

**Backend API 1.35.1**
- Completeness grading gives full credit for economy_type, economy_level, and conflict_level when system is abandoned (economy_type='None'/'Abandoned')
- Completeness grading gives full space station credit (5 pts) for abandoned systems since they can't have one
- Abandoned systems can now properly achieve S grade with good planet data

---

#### Haven Extractor 1.4.7 (2026-02-26) - Batch Adjective Refresh Fix
Fixes wrong adjectives on batch-uploaded systems (all except the last system had stale/incorrect flora, fauna, weather, sentinel values).

**Haven Extractor 1.4.7**
- CRITICAL: Added `_auto_refresh_for_export()` call in APPVIEW handler before batch auto-save, ensuring adjectives are re-resolved from the now-populated Translate hook cache
- Previously, `on_creature_roles_generate` captured PlanetInfo display strings before the game's Translate function had cached them, causing `_resolve_adjective()` to fall through to inaccurate legacy mapping tables
- Only the last system (still loaded at export time) was refreshed; systems 1..N-1 were locked in with stale data
- Now every system gets correct adjectives at APPVIEW time, matching the single-upload behavior

---

#### Haven Extractor 1.4.6 (2026-02-26) - Glyph Fix & Special Resource Detection
Critical glyph encoding fix and proper detection of Ancient Bones, Vile Brood, and other special resources.

**Haven Extractor 1.4.6**
- CRITICAL: Fixed glyph encoding — `(x + 2047) & 0xFFF` replaced with `x & 0xFFF` (two's complement masking). All previous Method 1 glyph codes had inverted XYZ coordinates.
- Fixed special resource hint matching: game uses `UI_BONES_HINT`, `UI_BUGS_HINT`, `UI_SCRAP_HINT`, `UI_STORM_HINT`, `UI_GRAV_HINT` — these were not recognized by the matching code
- Added UI hint IDs to both RESOURCE_NAMES dict and all hint-to-flag matching tuples (hook-time + extraction-time)
- Fixed extraction-time ExtraResourceHints backup read (was referencing `planet_data` before assignment — UnboundLocalError silently caught)
- Moved ExtraResourceHints + HasScrap reads from hook time (always empty) to extraction time (APPVIEW state)
- Removed incorrect fallback offsets (0x3300/0x3308/0x3318), kept only confirmed 0x3310
- HasScrap deferred from hook time to extraction time (avoids false positives from struct shift)
- SystemDetail page: added Ancient Bones, Salvageable Scrap, Storm Crystals, Gravitino Balls badges
- Fixed batch uploads dropping manual system names: APPVIEW auto-save locked batch entry with generic `System_XXXX` before user could type a name. "Apply Name" now propagates to existing batch entry
- Fixed star_color field name mismatch in approval code: extractor sends `star_color`, approval read `star_type` → NULL. Now accepts both
- Added migration 1.42.0: backfills star_type from pending_systems JSON for existing extractor-submitted systems
- Moon special resource badges now display in PendingApprovals (were only on planets)
- Fixed empty common_resource fallback: checked `== "Unknown"` but direct read returned `""`, now checks both
- Added 12 missing columns to moons table (has_rings, is_dissonant, ancient_bones, etc.) — all 4 INSERT statements updated

---

#### Haven Extractor 1.4.5 (2026-02-25) - Sentinel Fix & Auto-Resolve Adjectives
Fixes sentinel difficulty array index for NMS Worlds Part 1 update, resolves adjectives at capture time, and removes obsolete diagnostic buttons.

**Haven Extractor 1.4.5**
- Fixed SentinelsPerDifficulty index: [1]→[2] for Normal difficulty (Worlds Part 1 added Relaxed at index 1)
- Adjectives (flora, fauna, sentinel, weather) now resolved immediately at capture time in `on_creature_roles_generate` hook
- No longer requires manual "Refresh Adjectives" button press after freighter scanner
- Removed 3 obsolete GUI buttons: "Get Coordinates" (diagnostic), "Refresh Adjectives" (now automatic), "Rebuild Cache" (rarely needed)
- Remaining GUI: Apply Name, System Data, Batch Status, Config Status, Export to Haven

---

#### Haven Extractor 1.4.0 (2026-02-23) - Game-Data-Driven Adjective Resolution
Replaces fragile manual mapping tables with authoritative game data for all adjective types (biome, weather, flora, fauna, sentinel).

**Haven Extractor 1.4.0**
- Three-layer adjective resolution: runtime Translate hook → PAK/MBIN file cache → legacy mapping fallback
- Hook on `cTkLanguageManagerBase.Translate` captures (text_id → display_text) pairs during gameplay
- New `nms_language.py` module: PSARC/PAK reader, language MBIN parser, adjective cache builder with auto-detection of NMS install path
- Read PlanetDescription (0x300), PlanetType (0x380), IsWeatherExtreme (0x504) from cGcPlanetInfo struct
- Biome adjective extraction from PlanetDescription field (previously only captured category like "Lush" instead of "Paradise")
- All mapping calls (`map_display_string_to_adjective`, `map_weather_enum_to_adjective`) replaced with `_resolve_adjective()` layered lookup
- Background thread cache building from game PAK files with timestamp-based invalidation
- "Rebuild Adjective Cache" GUI button for manual refresh
- Legacy mapping tables preserved as last-resort fallback (not deleted)

---

#### Master Haven 1.34.0 (2026-02-22) - Data Completeness Grading System
NMS-style C-B-A-S grading system for system data completeness, visible across all browse views.

**Haven-UI 1.34.0**
- Grade badge (C/B/A/S) on every system card in SystemsList with tooltip showing score percentage
- Galaxy cards show grade distribution bar with color-coded S/A/B/C counts
- SystemDetail page shows full completeness breakdown panel with per-category progress bars
- Grade colors: S=Gold, A=Green, B=Blue, C=Gray

**Backend API 1.34.0**
- New helper: `calculate_completeness_score()` - weighted scoring across 7 categories (system core, system extra, planet coverage, planet environment, planet life, planet detail, space station)
- New helper: `update_completeness_score()` - calculate and cache score in DB
- Repurposed `is_complete` column from boolean (0/1) to score (0-100)
- Score auto-calculated on: save_system, approve_system, batch_approve, stub creation
- Systems list and search endpoints return `completeness_grade` and `completeness_score`
- System detail endpoint returns full `completeness_breakdown` with per-category scores
- Galaxy summary endpoint returns grade distribution (grade_s, grade_a, grade_b, grade_c, avg_score)
- Advanced filter updated to support grade-based filtering (S/A/B/C) alongside legacy boolean
- Migration v1.35.0: Backfills completeness scores for all existing systems, adds index

---

#### Master Haven 1.33.0 (2026-02-21) - Discovery System Linking & Approval Workflow
Discovery submissions now require linking to a solar system with full approval workflow.

**Haven-UI 1.33.0**
- Discovery submit modal overhaul: system selection required, location type selector (Planet/Moon/Space), dynamic type-specific fields per discovery type
- Inline stub system creation: "Create New System" flow for discoveries in systems not yet in the database, with yellow "Stub - Needs Update" badge
- Discovery approval workflow: new Discoveries tab in PendingApprovals page with review, approve, reject flow
- Discovery cards show planet/moon hierarchy, stub system badge, and space indicator
- Discovery detail modal shows type metadata (species, biome, behavior, etc.) and enhanced location hierarchy
- Tab switcher with pending count badges on PendingApprovals page

**Backend API 1.33.0**
- New endpoint: `POST /api/systems/stub` - create minimal placeholder systems for discovery linking
- New endpoint: `POST /api/submit_discovery` - public discovery submission to pending approval queue
- New endpoint: `GET /api/pending_discoveries` - scoped list of pending discovery submissions (discord_tag filtering, self-submission hiding)
- New endpoint: `GET /api/pending_discoveries/{id}` - full pending discovery detail with parsed discovery_data
- New endpoint: `POST /api/approve_discovery/{id}` - approve pending discovery with self-approval prevention and audit logging
- New endpoint: `POST /api/reject_discovery/{id}` - reject pending discovery with reason and audit logging
- Enhanced `GET /api/discoveries/browse`, `/recent`, `/{id}` with planet/moon LEFT JOINs, stub badge, type_metadata
- Enhanced `POST /api/discoveries` to accept type_metadata JSON column
- Enhanced `POST /api/save_system` to clear is_stub flag on full system save
- New `DISCOVERY_TYPE_FIELDS` dict defining 2-3 type-specific metadata fields per discovery type
- Migration v1.34.0: `is_stub` column on systems, `type_metadata` on discoveries, `pending_discoveries` table with indexes

---

#### Master Haven 1.32.0 (2026-02-05) - Advanced Filters, Partner Analytics & Discovery Events
Three major feature additions spanning frontend and backend.

**Haven-UI 1.32.0**
- Advanced search/filter overhaul: collapsible filter panel with 12+ filter fields (star type, economy, conflict, biome, weather, sentinel, resources, moons, planet count, data completeness, etc.)
- New AdvancedFilters component integrated into Systems page, SystemsList, and GalaxyGrid
- Partner Analytics dashboard: dedicated analytics page for partners with submission + discovery stats, dual leaderboards, discovery timeline chart, discovery type breakdown bar chart
- Discovery Events in Events tab: events now support 3 types (submissions, discoveries, both) with tabbed leaderboard (systems/discoveries/combined)
- Event cards display discovery counts and event type badges

**Backend API 1.32.0**
- New endpoint: `GET /api/systems/filter-options` - returns distinct filterable values from DB
- New endpoint: `GET /api/analytics/discovery-leaderboard` - top discoverers by community
- New endpoint: `GET /api/analytics/discovery-timeline` - discovery submission time series
- New endpoint: `GET /api/analytics/discovery-type-breakdown` - counts by discovery type
- New endpoint: `GET /api/analytics/partner-overview` - combined partner dashboard data
- Enhanced `GET /api/systems` with 12 new filter parameters using shared `_build_advanced_filter_clauses()` helper
- Enhanced `GET /api/systems/search` with same advanced filters
- Enhanced `GET /api/galaxies/summary` with filters and discord_tag support
- Enhanced `GET /api/events` with discovery counting for discovery/both event types
- Enhanced `GET /api/events/{id}/leaderboard` with tab param (submissions/discoveries/combined)
- Enhanced `POST/PUT /api/events` to accept event_type field
- Migration v1.32.0: Performance indexes on systems and planets for filter queries
- Migration v1.33.0: Added discord_tag to discoveries (backfilled from systems), event_type to events

---

#### Master Haven 1.31.0 (2026-01-27) - Pre-2.0 Baseline
Comprehensive audit and version alignment before major 2.0 migration.

**Haven-UI 1.31.0**
- Discoveries showcase overhaul with featured items and view tracking
- Type-based routing (`/discoveries/:type`) with URL slugs
- War Room v3: Peace treaties, multi-party conflicts, territory integration
- War Room v2: Activity feed, media uploads, reporting organizations
- War Room v1: Territorial conflicts, claims, news system
- Events tracking system for community competitions
- Analytics dashboard with date range filtering
- Sub-admin management with delegated permissions
- Partner account system with multi-tenant support
- Approval workflow with audit logging

**Haven Extractor 1.3.8** (reset from 10.3.8)
- Direct API submission to Haven backend
- Personal Discord ID tracking
- Weather/biome display value formatting
- Stellar classification extraction
- Multi-reality support (Normal/Permadeath)

**Planet Atlas 1.25.1**
- Multi-language support (English, Portuguese)
- Interactive 3D planet visualization
- POI marker system
- Color scheme customization

**Backend API 1.31.0** (32 migrations from 1.0.0)
- 70+ API endpoints
- War Room system (10 tables)
- Peace treaty negotiations
- System update tracking (contributors)
- Hierarchy indexes for performance

---

#### Master Haven 1.25.0 (2026-01-xx) - War Room Release
**Major Feature**: War Room territorial conflict system

- War Room enrollment for civilizations
- Territorial claims on systems
- Conflict declarations and resolutions
- War news and correspondents
- Live activity feed
- Discord webhook notifications
- Home region tracking
- Practice mode for testing

---

#### Master Haven 1.17.0 (2026-01-xx) - Events & Analytics
**Major Feature**: Community events and analytics

- Events table for time-boxed competitions
- Submission tracking per event
- Space station trade goods
- Anonymous username backfill
- Haven Extractor API integration

---

#### Master Haven 1.13.0 (2026-01-05) - Schema Versioning
**Major Feature**: Automated migration system

- Schema migrations table
- Version tracking in `_metadata`
- Automatic backup before migrations
- Migration rollback support

---

#### Master Haven 1.10.0 (2025-12) - Multi-Tenant System
**Major Feature**: Partner and sub-admin accounts

- Partner accounts table
- Sub-admin delegation system
- Approval audit logging
- Data restrictions per partner
- API key authentication

---

#### Master Haven 1.4.0 (2025-11-25) - Regions System
**Major Feature**: Custom region naming

- Regions table for named areas
- Pending region names queue
- Signed hex coordinate system

---

#### Master Haven 1.1.0 (2025-11-19) - Glyph System
**Major Feature**: Portal coordinate system

- Glyph code encoding/decoding
- 12-character portal addresses
- Coordinate calculation from glyphs
- Galaxy support

---

#### Master Haven 1.0.0 (2025-11-16) - Initial Release
**Foundation**: Core discovery system

- Systems, planets, moons tables
- Space stations table
- Discoveries table
- Pending systems queue
- Basic CRUD operations

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                              │
├───────────────┬───────────────┬───────────────┬─────────────────────┤
│   Haven-UI    │  Discord Bot  │ Planet Atlas  │  Memory Browser     │
│   (React)     │  (Keeper)     │  (3D Map)     │  (PyQt6)            │
└───────┬───────┴───────┬───────┴───────┬───────┴──────────┬──────────┘
        │               │               │                   │
        ▼               ▼               ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BACKEND API (FastAPI)                             │
│                Haven-UI/backend/control_room_api.py                  │
│  ┌─────────────┬─────────────┬─────────────┬─────────────────────┐  │
│  │ Systems API │ Approvals   │ Analytics   │ War Room (WIP)      │  │
│  │ Planets API │ Partners    │ Events      │ 18 tables, 73 EP    │  │
│  │ POIs API    │ Sub-Admins  │ API Keys    │                     │  │
│  └─────────────┴─────────────┴─────────────┴─────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE (SQLite)                                 │
│                Haven-UI/data/haven_ui.db                             │
│  ┌─────────────┬─────────────┬─────────────┬─────────────────────┐  │
│  │ systems     │ planets     │ moons       │ space_stations      │  │
│  │ regions     │ discoveries │ planet_pois │ pending_systems     │  │
│  │ api_keys    │ partners    │ sub_admins  │ approval_audit_log  │  │
│  │ events      │ war_room_*  │ conflicts   │ peace_proposals     │  │
│  └─────────────┴─────────────┴─────────────┴─────────────────────┘  │
│                    37 tables, schema v1.45.0                         │
└─────────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌───────────────────────────────┴─────────────────────────────────────┐
│                    DATA SOURCES                                      │
├───────────────────────┬─────────────────────────────────────────────┤
│   NMS-Haven-Extractor │   NMS-Save-Watcher                          │
│   (In-Game Mod)       │   (Extraction Queue)                        │
│   Hooks into NMS.exe  │   Monitors JSON files                       │
│   Extracts live data  │   Queues for upload                         │
└───────────────────────┴─────────────────────────────────────────────┘
```

## Data Flow

1. **Discovery Extraction**: Player uses NMS-Haven-Extractor mod while playing NMS
2. **JSON Output**: Extractor writes system/planet data to `~/Documents/Haven-Extractor/`
3. **Queue Management**: NMS-Save-Watcher monitors folder, queues extractions
4. **API Submission**: Data submitted to Haven API via `/api/extraction` or `/api/submit_system`
5. **Approval Queue**: Submissions land in `pending_systems` for admin review
6. **Approval**: Partners/Admins approve via Haven-UI → data moves to `systems` table
7. **Display**: Approved systems appear on 3D map and in browse interface

## Key Files Reference

### Backend (Haven-UI/backend/)
- `control_room_api.py` - Main FastAPI server (18,752 lines, 235 endpoints)
- `migrations.py` - Database schema migrations (v1.0.0 → v1.45.0)
- `glyph_decoder.py` - Portal glyph ↔ coordinate conversion
- `planet_atlas_wrapper.py` - 3D planet visualization generator

### Frontend (Haven-UI/)
- `src/App.jsx` - Main React app with routing
- `src/utils/AuthContext.jsx` - Session management and role-based access
- `src/utils/api.js` - API client helpers
- `src/pages/` - 23 page components
- `src/components/` - 37 reusable components

### Game Integration
- `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py` - Main extractor mod
- `NMS-Debug-Enabler/mod/nms_debug_enabler.py` - Debug flag enabler mod
- `NMS-Memory-Browser/nms_memory_browser/` - Memory inspection package
- `NMS-Save-Watcher/src/watcher.py` - Core watcher logic

## Database Schema (37 Tables)

**Core Data (7):**
- `systems` - Star systems with glyph codes and coordinates
- `planets` - Planets with biome, weather, resources
- `moons` - Moon data (orbital, climate)
- `space_stations` - Trading stations
- `regions` - Custom-named galaxy regions
- `discoveries` - Scientific discoveries (creatures, anomalies)
- `planet_pois` - Points of Interest on planet surfaces

**Approval Workflow (4):**
- `pending_systems` - Submission queue
- `pending_region_names` - Region name approval queue
- `pending_discoveries` - Discovery submission queue
- `approval_audit_log` - Full audit trail

**Authentication (5):**
- `partner_accounts` - Community partner logins
- `sub_admin_accounts` - Delegated sub-administrators
- `api_keys` - API authentication tokens (per-user extractor keys)
- `super_admin_settings` - System configuration
- `data_restrictions` - Per-partner data access rules

**Analytics (2):**
- `activity_logs` - Event logging
- `events` - Community challenges/competitions

**War Room (WIP) (18):**
- `war_room_enrollment` - Civilization enrollment
- `territorial_claims` - System territory claims
- `conflicts` - Active conflicts
- `conflict_events` - Conflict timeline events
- `conflict_parties` - Multi-party conflict participants
- `war_news` - News articles
- `war_correspondents` - Reporter accounts
- `current_debrief` - Active debrief data
- `war_statistics` - Aggregate stats
- `war_notifications` - Notification queue
- `war_activity_feed` - Activity stream
- `war_media` - Uploaded media
- `discord_webhooks` - Webhook configurations
- `reporting_organizations` - News organizations
- `reporting_org_members` - Organization membership
- `peace_proposals` - Peace treaty proposals
- `proposal_items` - Treaty item details
- `auto_news_events` - Auto-generated news

**System (1):**
- `schema_migrations` - Migration version tracking

## User Roles

| Role | Capabilities |
|------|-------------|
| **Public** | Browse systems, submit discoveries (goes to queue) |
| **Partner** | Approve own community's submissions, create systems directly, manage sub-admins |
| **Sub-Admin** | Delegated features (approvals, system create/edit) based on partner settings |
| **Super Admin** | Full access, partner management, global settings, all communities |

## Environment Setup

### Development Mode
```bash
# Terminal 1: Backend API
cd Master-Haven
python Haven-UI/backend/control_room_api.py  # Runs on :8005

# Terminal 2: Frontend (hot-reload)
cd Haven-UI
npm run dev  # Runs on :5173, proxies API to :8005
```

### Production Mode
```bash
# Build frontend
cd Haven-UI && npm run build

# Run single server (serves both API and built frontend)
cd Master-Haven
python Haven-UI/backend/control_room_api.py  # Serves everything on :8005
```

### Public Access
Haven is self-hosted at `https://havenmap.online` on a Raspberry Pi 5 (10.0.0.229) via Nginx Proxy Manager + Cloudflare DNS + Let's Encrypt SSL.

## Configuration Files

| File | Purpose |
|------|---------|
| `config/paths.py` | Centralized path resolution (cross-platform) |
| `Haven-UI/.env` | Frontend environment (API URL) |
| `NMS-Save-Watcher/config.json` | Watcher API key and settings |
| `keeper-discord-bot-main/.env` | Discord bot token and channel IDs |

## Common Development Tasks

### Adding a New API Endpoint
1. Add route in `Haven-UI/backend/control_room_api.py`
2. Add corresponding function in `Haven-UI/src/utils/api.js`
3. Use in React components

### Database Migration
1. Add migration function in `Haven-UI/backend/migrations.py` with `@register_migration`
2. Restart server - migrations run automatically

### Adding a New Discovery Type
1. Update `discovery_types` in keeper bot config
2. Add modal in `keeper-discord-bot-main/src/cogs/discovery_modals.py`
3. Update Haven-UI Discoveries page if needed

## Testing

```bash
# API endpoint tests
python tests/api/test_endpoints.py

# Approval system tests
python tests/api/test_approvals_system.py

# Generate test data (30 systems with proper glyphs)
python tests/data/generate_test_data.py
```

## Related Documentation

- [Haven-UI/CLAUDE.md](Haven-UI/CLAUDE.md) - React frontend details
- [Haven-UI/backend/CLAUDE.md](Haven-UI/backend/CLAUDE.md) - Backend API reference
- [NMS-Haven-Extractor/CLAUDE.md](NMS-Haven-Extractor/CLAUDE.md) - Game mod architecture
- [NMS-Debug-Enabler/README.md](NMS-Debug-Enabler/README.md) - Debug enabler mod
- [docs/START_HERE.md](docs/START_HERE.md) - Quick-start guide
- [docs/GLYPH_SYSTEM_IMPLEMENTATION.md](docs/GLYPH_SYSTEM_IMPLEMENTATION.md) - Coordinate system
- [docs/FUTURE_IMPROVEMENTS.md](docs/FUTURE_IMPROVEMENTS.md) - Roadmap

## Key Concepts

### Portal Glyph System
- 12-character hexadecimal code: `P-SSS-YY-ZZZ-XXX`
- P = Planet index, SSS = Solar system, YY = Y-axis, ZZZ = Z-axis, XXX = X-axis
- Bidirectional conversion in `Haven-UI/backend/glyph_decoder.py`

### Multi-Community Support
- Partners represent Discord communities (Haven, IEA, B.E.S, etc.)
- Submissions tagged with `discord_tag` for routing
- Partners only see their community's pending approvals
- Color-coded badges in UI

### Self-Approval Prevention
- Users cannot approve their own submissions
- Matched by account ID or Discord username
- Ensures data quality through peer review
