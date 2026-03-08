# Systems Overlap Audit
**Generated:** 2026-03-08
**Status:** AUDIT ONLY — nothing modified

---

## Executive Summary
- Total overlapping systems found: 11
- Critical (data could diverge right now): 3
- Moderate (hardcoded but stable): 5
- Minor (cosmetic or low risk): 3

---

## Findings

### [Area 1]: Community Tag Colors
**Severity:** Critical

**Hardcoded version:**
- Location: `Haven-UI/src/utils/tagColors.js` (lines 5-24)
- Contains: 7 hardcoded community tags with 3 color formats each (Tailwind classes, bg-only Tailwind, RGBA style objects): Haven, IEA, B.E.S, ARCH, TBH, EVRN, Personal
- Used by: `DiscordTagBadge.jsx` (line 21), `SystemsList.jsx` (line 141), `LeaderboardTable.jsx` (line 2), `CommunityDetail.jsx` (line 4), `CommunityStats.jsx` (line 8)

**Database version:**
- Table: `partner_accounts` (columns: `discord_tag`, `region_color`, `theme_settings`)
- API endpoints: `GET /api/discord_tag_colors` (line 5479), `GET/PUT /api/partner/theme`, `GET/PUT /api/partner/region_color`
- Stores: Per-partner hex colors for 3D map regions, theme customization JSON

**Are they in sync?** No — they serve different purposes. Badge colors are hardcoded in JS; map region colors come from DB. The endpoint `GET /api/discord_tag_colors` exists to bridge this gap but **the frontend never calls it**.
**Authoritative version should be:** Database
**To fix:** Frontend should call `GET /api/discord_tag_colors` on startup, cache the response, and use it for badge colors. Add a `badge_color` field to `partner_accounts` or extend the existing endpoint to return badge-specific colors. Remove `tagColors.js` hardcoded object after migration.

---

### [Area 2a]: Discovery Type Colors — Frontend vs Backend
**Severity:** Critical

**Hardcoded version (frontend):**
- Location: `Haven-UI/src/data/discoveryTypes.js` (lines 4-17)
- Contains: 12 discovery types with emoji, label, color hex, description

**Hardcoded version (backend):**
- Location: `Haven-UI/backend/control_room_api.py` (lines 86-120)
- Contains: `DISCOVERY_EMOJI_TO_SLUG`, `DISCOVERY_SLUG_TO_EMOJI`, `DISCOVERY_TYPE_SLUGS`, `DISCOVERY_TYPE_INFO` — backend's own copy with emoji, label, color

**Are they in sync?** No — **9 out of 12 colors are different**:

| Type | Frontend | Backend |
|------|----------|---------|
| mineral | #6366f1 | #a855f7 |
| ancient | #f59e0b | #eab308 |
| history | #eab308 | #f59e0b |
| bones | #a3a3a3 | #78716c |
| alien | #8b5cf6 | #06b6d4 |
| multitool | #64748b | #f97316 |
| lore | #d946ef | #6366f1 |
| base | #f97316 | #14b8a6 |
| other | #737373 | #6b7280 |

**Database version:** None — no `discovery_types` table exists. Types are hardcoded in both JS and Python.
**Authoritative version should be:** Frontend (`discoveryTypes.js` was designated as the single source of truth in Pass 1)
**To fix:** Sync backend `DISCOVERY_TYPE_INFO` colors to match `discoveryTypes.js`. Or better: remove backend colors entirely (backend doesn't need colors — that's a frontend concern). Backend only needs slug/emoji mappings for validation.

---

### [Area 2b]: Discovery Types in DiscoverySubmitModal
**Severity:** Moderate

**Hardcoded version:**
- Location: `Haven-UI/src/components/DiscoverySubmitModal.jsx` (lines 8-22)
- Contains: Hardcoded `DISCOVERY_TYPES` array with emojis and labels, plus `TYPE_FIELDS` object (lines 25-69) with per-type input field definitions
- Does NOT import from `discoveryTypes.js`

**Shared version:**
- Location: `Haven-UI/src/data/discoveryTypes.js`
- Contains: Same 12 types with same emojis and labels

**Are they in sync?** Yes — currently identical data, but maintained separately.
**To fix:** Import from `discoveryTypes.js` instead of duplicating. `TYPE_FIELDS` is unique to this component and should stay.

---

### [Area 3]: Galaxy Names — Three Independent Copies
**Severity:** Moderate

**Copy 1 — Frontend data file:**
- Location: `Haven-UI/src/data/galaxies.js` (lines 4-261)
- Contains: 256 galaxies as array of `{index, name}` objects (1-indexed)
- Used by: `Wizard.jsx`, `RegionDetail.jsx`

**Copy 2 — Frontend hardcoded in component:**
- Location: `Haven-UI/src/components/GalaxyGrid.jsx` (lines 7-264)
- Contains: 256 galaxies as object `{name: {num, type, desc}}` — adds galaxy type and description not present in copy 1
- Used by: GalaxyGrid display/sorting only

**Copy 3 — Backend JSON file:**
- Location: `Haven-UI/backend/data/galaxies.json` (258 lines)
- Contains: 256 galaxies as `{"0": "name"}` object (0-indexed)
- Used by: Backend API, validation, migrations

**Copy 4 — Extractor hardcoded:**
- Location: `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py` (lines 87-156)
- Contains: Same 256 galaxies as Python dict (0-indexed)

**Are they in sync?** Yes — all 256 names are currently identical across all 4 copies.
**Risk:** If NMS adds a new galaxy, all 4 files must be updated independently. No shared source exists.
**Authoritative version should be:** Backend `galaxies.json` (bundled for deployment)
**To fix:** Frontend should fetch galaxy list from `GET /api/galaxies` endpoint (already exists, line 1521) instead of using hardcoded arrays. GalaxyGrid's extra metadata (type, description) could be added to the API response or kept as a frontend-only enhancement layer on top of the API data.

---

### [Area 4]: Settings In-Memory Only
**Severity:** Moderate

**Implementation:**
- Location: `Haven-UI/backend/control_room_api.py` (line 1843)
- `_settings_cache` is an in-memory dict
- `GET /api/settings` returns from memory cache
- `POST /api/settings` writes to memory cache only

**Database version:**
- Table: `super_admin_settings` (key/value store, line 763-768)
- Stores: `password_hash`, `personal_color`

**Are they in sync?** Partially — `password_hash` and `personal_color` are persisted to the table via dedicated endpoints (`/api/change_password`, `/api/settings` POST for personal_color). But the generic settings cache is in-memory only — any settings stored via `POST /api/settings` that aren't explicitly saved to the table are lost on restart.
**To fix:** Ensure all settings writes persist to `super_admin_settings` table, not just the in-memory cache.

---

### [Area 5]: Feature Flags — Frontend Enum vs Backend Enforcement
**Severity:** Moderate

**Frontend enum:**
- Location: `Haven-UI/src/utils/AuthContext.jsx` (lines 4-16)
- Contains: 11 feature flag names (API_KEYS, BACKUP_RESTORE, PARTNER_MANAGEMENT, SYSTEM_CREATE, SYSTEM_EDIT, APPROVALS, STATS, SETTINGS, CSV_IMPORT, BATCH_APPROVALS, WAR_ROOM)
- Used for: Route guards, UI visibility via `canAccess(feature)`

**Backend enforcement:**
- `enabled_features` stored per partner/sub-admin in database (JSON array)
- Super admin gets `['all']` (lines 2291, 2308)

**Are they in sync?** Partially — 4 features have **no backend enforcement**: `BACKUP_RESTORE`, `SYSTEM_CREATE`, `SYSTEM_EDIT`, `BATCH_APPROVALS`. These are frontend-only visibility tokens. The backend uses role-based checks (`user_type`) instead of feature-based checks for these operations.
**Risk:** A partner without `SYSTEM_CREATE` in their `enabled_features` could still call the backend create endpoint directly — the backend doesn't check the feature flag.
**To fix:** Either add backend feature flag checks to the 4 unprotected endpoints, or document that these are frontend-only UI hints and backend relies on role checks.

---

### [Area 6a]: Economy Type Naming — Frontend vs Extractor
**Severity:** Critical

**Frontend Wizard:**
- Location: `Haven-UI/src/pages/Wizard.jsx` (lines 390-402)
- Values: Trading, Mining, Manufacturing, Technology, Scientific, Power Generation, Mass Production, Advanced Materials, Pirate, None, Abandoned (11 types)

**Frontend PendingApprovals:**
- Location: `Haven-UI/src/pages/PendingApprovals.jsx` (line 1194)
- Values: Trading, Scientific, **Industrial**, Technology, Mining, Power Generation, Manufacturing, None (8 types)
- **"Industrial" exists here but not in Wizard** — different subset

**Extractor:**
- Location: `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py` (lines 402-405)
- Values: Mining, **HighTech**, Trading, Manufacturing, **Fusion**, Scientific, **PowerGeneration** (7 types)
- **"HighTech"** (not "Technology"), **"Fusion"** (not in frontend), **"PowerGeneration"** (no space)

**Backend:** No validation enum — stores whatever string is submitted.

**Are they in sync?** No — three different naming schemes:
- "Technology" (frontend) vs "HighTech" (extractor)
- "Power Generation" (frontend) vs "PowerGeneration" (extractor, no space)
- "Industrial" appears only in PendingApprovals edit dropdown
- "Fusion" appears only in extractor
- Frontend has "Mass Production", "Advanced Materials", "Pirate", "Abandoned" that extractor never sends

**To fix:** Define canonical economy type names in one place. Either normalize extractor output to match frontend labels before sending, or add a mapping layer in the backend `/api/extraction` endpoint.

---

### [Area 6b]: Economy Tier / Wealth Naming
**Severity:** Moderate

**Frontend Wizard:** T1 (Low), T2 (Medium), T3 (High), T4 (Pirate), None
**Frontend PendingApprovals:** Low, Medium, High, None (no Pirate)
**Extractor:** Poor, Average, Wealthy, Pirate (different names entirely)
**Backend:** Stores as-is, no normalization

**Are they in sync?** No — "T1"/"Low"/"Poor" all mean the same thing but are stored as different strings depending on submission source.
**To fix:** Normalize in backend `/api/extraction` endpoint: map Poor→Low, Average→Medium, Wealthy→High before storage.

---

### [Area 6c]: Conflict Level Naming
**Severity:** Minor

**Frontend:** Low, Medium, High, None
**Extractor:** Low, **Default**, High, Pirate
**Difference:** "Default" vs "Medium", "Pirate" vs "None"

**To fix:** Map Default→Medium and Pirate→None in backend extraction endpoint.

---

### [Area 6d]: Biome Type Naming
**Severity:** Minor

**Frontend** (`biomeCategoryMappings.js`): Exotic, Mega Exotic, Chromatic Red/Green/Blue, Marsh, Volcanic, Infested (17 categories)
**Extractor**: Weird (not Exotic), Red/Green/Blue (not Chromatic), Swamp (not Marsh), Lava (not Volcanic), Test, All

**Are they in sync?** No — different naming for same biomes. Frontend has mapping functions (`getBiomeCategory()`) that translate between formats, so this works in practice but is fragile.
**To fix:** Add normalization mapping in backend extraction endpoint.

---

### [Area 7]: Extractor Hardcoded Community Fallback
**Severity:** Minor

**Hardcoded version:**
- Location: `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py` (lines 232-236)
- Contains: 25 hardcoded community tags as `_DEFAULT_COMMUNITY_TAGS`

**Database version:**
- Table: `partner_accounts`
- Endpoint: `GET /api/communities` (line 6394)

**Are they in sync?** Unknown — the hardcoded list has 25 communities, the database has however many active partners exist. The fallback is only used when both the API fetch and local cache fail.
**Risk:** Low — 3-tier fallback (API → cache → hardcoded) means the hardcoded list is rarely reached.
**To fix:** Keep as-is (defensive fallback), but periodically verify the hardcoded list matches active partners.

---

### [Area 8]: Super Admin Credentials Hardcoded
**Severity:** Moderate (operational, not a divergence issue)

**Hardcoded:**
- Location: `Haven-UI/backend/control_room_api.py` (lines 1866-1867)
- Contains: `SUPER_ADMIN_USERNAME = "Haven"` and `DEFAULT_SUPER_ADMIN_PASSWORD_HASH`

**Database:** `super_admin_settings` table stores `password_hash` (overrides default after first password change)

**Risk:** Default credentials are in source code. Password can be changed at runtime but username "Haven" is permanently hardcoded.

---

## Priority Order for Fixes

1. **[Critical] Economy Type Naming (6a)** — Extractor submissions store different economy names than manual submissions. Data is actively diverging in the database right now. Fix: normalize in `/api/extraction` endpoint.

2. **[Critical] Discovery Type Colors (2a)** — 9/12 colors mismatch between frontend and backend. Backend `DISCOVERY_TYPE_INFO` colors should match `discoveryTypes.js` or be removed (backend doesn't render colors). Fix: sync or remove backend colors.

3. **[Critical] Tag Colors Not API-Driven (1)** — `GET /api/discord_tag_colors` endpoint exists but frontend ignores it, using hardcoded colors. New communities get hash-based random colors. Fix: call the API endpoint.

4. **[Moderate] Economy Tier Naming (6b)** — Poor/Average/Wealthy (extractor) vs Low/Medium/High (frontend) stored as different strings. Fix: normalize in extraction endpoint.

5. **[Moderate] Galaxy Names 4 Copies (3)** — Currently in sync but fragile. Fix: frontend fetches from API instead of hardcoded arrays.

6. **[Moderate] Settings In-Memory (4)** — Some settings may not persist across restarts. Fix: ensure all writes go to `super_admin_settings` table.

7. **[Moderate] Feature Flags No Backend Enforcement (5)** — 4/11 features are frontend-only visibility hints. Fix: add backend checks or document as intentional.

8. **[Moderate] DiscoverySubmitModal Not Using Shared Types (2b)** — Duplicates `discoveryTypes.js` data. Fix: import from shared file.

9. **[Minor] Conflict Level Naming (6c)** — Default vs Medium, Pirate vs None. Fix: normalize in extraction endpoint.

10. **[Minor] Biome Type Naming (6d)** — Different naming conventions. Frontend has mapping layer so it works, but fragile. Fix: normalize in extraction endpoint.

11. **[Minor] Extractor Community Fallback (7)** — Hardcoded 25-community list as last-resort fallback. Low risk. Fix: periodic sync.

---

## Summary Statistics
- Critical overlaps: 3 (tag colors, discovery type colors, economy naming)
- Moderate overlaps: 5 (economy tiers, galaxy copies, settings persistence, feature flags enforcement, submit modal types)
- Minor overlaps: 3 (conflict naming, biome naming, extractor community fallback)
- Components affected: Haven-UI frontend, Haven-UI backend, Haven Extractor
