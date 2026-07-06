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
| **The_Keeper** | Discord community bot | - | Python, discord.py |
| **Planet_Atlas** | 3D planetary cartography | 8050 | Python, Dash, Plotly |

> **Note:** The_Keeper is the active Discord bot, maintained by a community member (Stars). The legacy `keeper-discord-bot-main` was retired and archived on 2026-04-28 — see `C:\Master-Haven-Archives\2026-Q2\2026-04-28-keeper-discord-bot-main\`.

## Version History

### Current Versions
| Component | Version | Last Updated | Notes |
|-----------|---------|--------------|-------|
| 🔧 **VERSION AUDIT — TRUE NUMBERS** | **Master Haven 1.78.0 · Backend 1.77.1 · Frontend 1.68.1** | 2026-06-22 | **Version renumber after a full git + changelog audit (Parker: "we really messed up the update version of the backend and front end").** The live files now read the corrected truth: `routes/auth.py` `/api/status` = **1.77.1** (was 1.91.0); `package.json` = **1.68.1** (was 1.81.0). **Why they were inflated:** (a) several commits **bundled multiple releases** and bumped the version files in big jumps that skipped numbers (`693d190`, `c805dd5`, `18e5abb`, `001e584` — the last advanced backend 3 minors for a commit titled "bug updates"); (b) many **bug-fix deploys were bumped as MINOR** instead of patch. **Method:** anchored at the last clean, sequential git point — **Backend 1.60.0 / Frontend 1.52.1** (2026-05-05, the commit before `008c95c`) — then applied one bump per real deploy classified by its dominant change per the rule below (bug → patch, feature → minor). 32 deploys → Backend 1.77.1, Frontend 1.68.1. **IMPORTANT:** the per-release version cells in the rows *below this one* are the **OLD inflated labels** (1.82.0–1.94.0 era) and the inline "`/api/status` → X, `package.json` → Y" notes throughout the changelog are the old desynced fiction — they were **not** retroactively rewritten (history preserved). The mapping baseline→now lives in the changelog entry "Version Audit (2026-06-22)". **Master Haven umbrella → `1.78.0`** (was 1.94.0): the literal recompute (one bump per deploy, minor if *either* track shipped a feature; 18 feature + 14 fix deploys from baseline 1.58.0) lands at 1.76.1, then **set to 1.78.0 so the umbrella leads the components** (Parker's call) — Backend 1.77.1 / Frontend 1.68.1. **Structural note:** the deep `#### Changelog` prose narrates more "releases" than there were deploys (several commits bundled 2–4 documented releases), so its per-entry numbers can't map 1:1 onto the true per-deploy series — this canonical table carries the corrected numbers; the deep prose keeps its historically-accurate "file showed X at deploy time" notes under this banner. |
| **Master Haven** | 1.84.1 | 2026-07-02 | **Fix: admin direct-save (`/api/save_system`) edit of any system that HAS moons 500'd with `UNIQUE constraint failed: moons.id` — reported by Parker on `[RES]Memoro` ("keeps shooting back Database error").** **Root cause:** [control_room_api.py](Haven-UI/backend/control_room_api.py) defines its OWN `get_db_connection()` (~line 781) that — unlike [db.py](Haven-UI/backend/db.py)'s — omits `PRAGMA foreign_keys=ON`. `save_system` uses that FK-**off** connection, so its `DELETE FROM planets WHERE system_id=?` never fired the `moons.planet_id ON DELETE CASCADE` — the old moon rows survived, and the id-reuse re-insert (Fix B, 1.82.2) then collided on the still-present `moons.id`. Systems without moons never hit it (no moon reuse), which is why it wasn't universal. This same FK-off connection is the root of the recurring orphaned-discovery / "planet tags wiped" family on this path — Memoro carries **58 orphaned moon rows** from years of it. **Diagnosis (fully verified against a live-DB copy):** empirically proved the cascade works with FK ON but the deployed `save_system` connection had FK **0**, and reproduced the exact 500 by invoking the real `save_system`; instrumentation showed moons 5382/5383 still present after the DELETE. **Fix (targeted, low-risk):** `save_system` now runs `conn.execute('PRAGMA foreign_keys=ON')` on its own connection right after acquiring it — deliberately NOT flipped globally at line 781, since other endpoints in this file (e.g. delete-system) route through the same factory and a cascade `SET NULL` on a non-space discovery could trip its `CHECK (system_id IS NOT NULL OR location_type IN ('space','deep_space'))`. **Verified live:** the exact save that 500'd now succeeds and preserves Memoro's moons; 0 `moons.id` errors post-deploy; `/api/status` 1.83.1. Backend-only `--build`, no migration, no frontend. **Follow-ups (not done):** clean up the 58 orphaned moons + any dangling discovery links; consider auditing `control_room_api.py`'s DELETE paths and bringing its local `get_db_connection` to FK-on for consistency with `db.py`. `/api/status` 1.83.0 → 1.83.1. |
| Backend API | 1.83.1 | 2026-07-02 | See Master Haven 1.84.1. [control_room_api.py](Haven-UI/backend/control_room_api.py) `save_system` adds `conn.execute('PRAGMA foreign_keys=ON')` immediately after `conn = get_db_connection()`, so its planet delete-and-reinsert cascade-deletes moons (and `SET NULL`s discoveries) exactly as the `capture_discovery_links`/`restore_discovery_links` + id-reuse machinery already assume — fixing `UNIQUE constraint failed: moons.id` when edit-saving any moon-bearing system. Scoped to this endpoint only; the file's module-level `get_db_connection` (line ~781, FK-off — the historical divergence from [db.py:94](Haven-UI/backend/db.py)) is left unchanged to avoid altering cascade behavior of sibling endpoints. No schema/migration. `/api/status` 1.83.0 → 1.83.1. Backend `--build`/restart. |
| **Master Haven** | 1.84.0 | 2026-06-30 | **Keeper ⇄ Cartography: new `GET /api/glyph/system` — paste a portal glyph, get a deep link straight to that system's 3D map view.** Parker's ask: a user inputs glyphs through a Keeper connection and gets back a URL that opens that exact system on the cartography map. **Investigation:** `/map/system/{id}` ([control_room_api.py](Haven-UI/backend/control_room_api.py)) resolves by `id` **only** ("Lookup by ID only"), so `/map/system/<glyph>` 404s — a glyph must be resolved to an id first, and the *correct* match is the canonical **last-11-glyph-chars + galaxy + reality** rule (`find_matching_system` in [db.py](Haven-UI/backend/db.py), indexed via `glyph_code_suffix`) because the leading glyph digit is the planet index and varies every portal-in. (`/api/systems/{id}`'s inline glyph branch does an exact-12-char, un-scoped match — deliberately NOT reused.) **New endpoint** ([routes/systems.py](Haven-UI/backend/routes/systems.py)) `GET /api/glyph/system?glyph=&galaxy=Euclid&reality=Normal` (public, read-only, matching `/api/glyph/preview`): resolves via `find_matching_system` → `find_matching_pending_system`; returns `status` (`approved`/`pending`/`not_found`), `system_id`, `name`, `completeness_grade`, decoded region (via `_decode_glyph_parts`), the region's custom name, and **relative** `map_url` (`/map/system/{id}`, the 3D view — primary), `detail_url`, `cartographer_url`. Approved matches are run through `apply_data_restrictions` so a hidden system never leaks a link (falls through to `not_found`). `not_found` returns the decoded region + procedural region name + a `/create?glyph=…` submit link. URLs are relative so the caller prefixes the public site URL (never the internal docker host). Reuses existing helpers only — **no schema change, no migration, no frontend change.** **Keeper side is a spec doc** ([The_Keeper/HAVEN_GLYPH_MAP_SPEC.md](The_Keeper/HAVEN_GLYPH_MAP_SPEC.md)) for Stars to wire a `/glyphmap` command (or extend `/hexkey`); no `The_Keeper/` code edited. **Verified:** both edited backend files byte-compile; local-DB smoke test proved a glyph AND its planet-index variant (`20720193DFA9` / `F0720193DFA9`) both resolve to the same system (Oculi) → identical `/map/system/{id}`. Backend `--build` deploy (backend-only, no migration). `/api/status` 1.82.0 → 1.83.0. |
| Backend API | 1.83.0 | 2026-06-30 | See Master Haven 1.84.0. New public read-only `GET /api/glyph/system` in [routes/systems.py](Haven-UI/backend/routes/systems.py) (glyph → catalogued system + relative deep-link URLs). Resolves with the canonical `find_matching_system`/`find_matching_pending_system` (last-11 + galaxy + reality) so the varying planet-index digit is tolerated; new module helper `_region_custom_name()`; reuses `_decode_glyph_parts`, `apply_data_restrictions` (hidden-system gate), `calculate_completeness_score`, `generate_names`. Returns `approved`/`pending`/`not_found` with `map_url`/`detail_url`/`cartographer_url` (relative) or a `/create?glyph=…` submit link. Read-only; no schema/migration. `/api/status` 1.82.0 → 1.83.0. Backend `--build`/restart. |
| Haven-UI | 1.72.5 | 2026-06-28 | **Adjective dropdowns guaranteed alphabetical.** Parker: the searchable adjective pickers in the Create/Edit Wizard weren't showing A→Z. Investigation: the curated lists in [optionCatalog.json](Haven-UI/src/data/optionCatalog.json) already test sorted, and the React `SearchableSelect` renders options in array order — so the Wizard/editor pickers were already alphabetical in source (a stale deployed build was the likely live symptom). Made it a build-time guarantee instead of relying on hand-sorted JSON: [adjectives.js](Haven-UI/src/data/adjectives.js) `toSelectOptions` now sorts case-insensitively (`localeCompare`, `sensitivity:'base'`) before mapping, so **all 7** [CelestialBodyEditor](Haven-UI/src/components/CelestialBodyEditor.jsx) searchable dropdowns (biome / weather / sentinel / flora / fauna / resources / exotic trophy — the Wizard planet/moon pickers via `PlanetEditor`) render A→Z regardless of source order or future appends. Also sorted the genuinely-unsorted hardcoded biome `<select>` in the approval-edit UI ([SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)) — the two duplicated `['Lush','Toxic',…]` arrays consolidated into one module-level `BIOME_EDIT_OPTIONS` const, sorted, so the planet + moon edit lists can't drift. The Systems-tab Filter dropdowns + Cartographer resource box were **verified already alphabetical** (backend `_dedup_clean`/`get_distinct_resources` in [systems.py](Haven-UI/backend/routes/systems.py) already return `sorted(...)`) — no change. Frontend-only, no backend/schema/migration change; `npm run build` clean (16.37s, 0 errors). `package.json` 1.72.4 → 1.72.5. |
| **Master Haven** | 1.83.0 | 2026-06-26 | **Keeper bot enablement: server-side procedural naming + a one-call glyph preview + a canonical option-catalog endpoint (backend only; no `The_Keeper/` edits — Stars spec to follow).** Parker: the Keeper can upload systems into the pending queue but lacks the auto region/system-name generation the extractor + wizard have, and its field entry is free-text instead of searchable adjective dropdowns. Investigation found both gaps are mostly *Keeper-side wiring* — the backend already had `/api/namegen`, `/api/decode_glyph`, `/api/regions/...`. This deploy ships the backend pieces so the Keeper integration is trivial. **(1) `GET /api/glyph/preview`** ([systems.py](Haven-UI/backend/routes/systems.py)) — one call returns decoded coords + procedural system & region names + the region's naming status (named / pending / system_count), mirroring the Wizard's glyph→names flow in a single round-trip. **(2) `GET /api/option-catalog`** ([systems.py](Haven-UI/backend/routes/systems.py)) — serves the curated lists (223 biomes / 368 weather / sentinel / flora / fauna / resources / exotic trophies + star/economy/conflict/lifeform/game-mode enums + planet sizes + the 17 planet/moon boolean attributes) for the Keeper's slash-command autocomplete. **Single source of truth:** the lists now live in new [src/data/optionCatalog.json](Haven-UI/src/data/optionCatalog.json) — the web wizard reads it ([adjectives.js](Haven-UI/src/data/adjectives.js) re-exports from it) AND the backend serves it ([option_catalog.py](Haven-UI/backend/option_catalog.py)), so the Keeper's autocomplete can never drift from the wizard's dropdowns. (It lives under `src/` because the Dockerfile's frontend build stage only copies `src/`; the backend reaches it at runtime via `COPY . .`.) **(3) Server-side name safety net** on `/api/extraction` ([approvals.py](Haven-UI/backend/routes/approvals.py)) — when a client submits a blank/placeholder name (`System_<glyph>` or the Keeper's `[TAG] X#-XXXX`), the backend fills the real procedural name and queues the procedural region name for approval (reuses the Wizard's Option-B region path; idempotent via one-pending-per-voxel). A tight placeholder regex never clobbers civ-tag-prefixed REAL names like `[RES]Boulde`, so the *current* Keeper's data improves before any Keeper rework ships. Shared logic extracted to [services/namegen_service.py](Haven-UI/backend/services/namegen_service.py) (`/api/namegen` refactored onto it — identical output). **Verified:** all backend files byte-compile + route modules import clean; `npm run build` clean (17.79s, 0 errors — Vite inlines the JSON); endpoints exercised against the live DB (namegen, option-catalog 17 lists, glyph/preview full payload, bad-glyph→400); placeholder detector confirmed `[HAVEN] F4-ABCD`→replace, `[RES]Boulde`→keep, `Oculi`→keep. **Hands-off:** no `The_Keeper/` edits (Stars's project) — the Keeper-side wiring ships as a spec doc (`The_Keeper/HAVEN_INTEGRATION_SPEC.md`). Backend `--build` + frontend rebuild; no schema change, no migration. `/api/status` 1.81.3 → 1.82.0, `package.json` 1.72.3 → 1.72.4. |
| Backend API | 1.82.0 | 2026-06-26 | See Master Haven 1.83.0. New [option_catalog.py](Haven-UI/backend/option_catalog.py) (`get_option_catalog()` loads `src/data/optionCatalog.json`, cached) + new [services/namegen_service.py](Haven-UI/backend/services/namegen_service.py) (`generate_names(glyph, galaxy_name) → (system, region) | (None, None)`, `looks_like_placeholder_name()`, `galaxy_name_to_index()`). [routes/systems.py](Haven-UI/backend/routes/systems.py): `GET /api/option-catalog` + `GET /api/glyph/preview` (public; decode via existing `_decode_glyph_parts`, names via the service, region status via the same query `GET /api/regions/{rx}/{ry}/{rz}` uses, `apply_data_restrictions`-scoped count); `/api/namegen` refactored onto the service (same `{system_name, region_name}`; 400 on bad glyph / 503 if nms_namegen missing). [routes/approvals.py](Haven-UI/backend/routes/approvals.py) `/api/extraction`: name safety net (placeholder → procedural) placed before the merge/insert branch so both paths use the fixed name; deferred region-name proposal in the new-insert path (client `proposed_region_name` else the generated one; guarded by already-named / one-pending-per-voxel; wrapped so it never blocks the submission). Read/write-side only — no schema change, no migration. `/api/status` 1.81.3 → 1.82.0. Backend `--build`/restart. |
| Haven-UI | 1.72.4 | 2026-06-26 | See Master Haven 1.83.0. New canonical [src/data/optionCatalog.json](Haven-UI/src/data/optionCatalog.json) (all curated NMS submission option lists — generated exactly from the prior `adjectives.js` arrays + the Wizard's system enums + CelestialBodyEditor attributes). [src/data/adjectives.js](Haven-UI/src/data/adjectives.js) rewritten to a thin re-export of the JSON (`biomeAdjectives` / `weatherAdjectives` / `sentinelAdjectives` / `floraAdjectives` / `faunaAdjectives` / `resourcesList` / `exoticTrophyList` + `toSelectOptions`) so every existing importer is unchanged and the wizard dropdowns + the backend's `/api/option-catalog` share one source. No UX/behavior change (identical values); Vite inlines the JSON. The Wizard's inline emoji `<option>` enums + `resource_catalog.py` stay as mirrors (documented in the JSON `_comment`). Build clean (17.79s, 0 errors). `package.json` 1.72.3 → 1.72.4. |
| **Master Haven** | 1.82.5 | 2026-06-26 | **Fix: `/api/systems` (browse list) + both search endpoints returned only 2,648 of 14,524 systems — a regions `LEFT JOIN` missing reality+galaxy.** Surfaced by bringing up the **Travelers-Collective** sync hub against Haven: a sync that processed 14,598 rows landed only 2,646 distinct systems. Traced on the live prod DB — there are **14,524 distinct systems** but `/api/systems` could only ever return ~2,648. **Root cause:** the `regions` table is uniquely keyed on 5 cols (`reality, galaxy, region_x, region_y, region_z`) since migration v1.49.0 (same coord triple named separately per galaxy/reality), but the list/search joins matched **only the 3 coordinate columns** → a system whose coords are named in N galaxies fans out into N rows (worst case `(4095,7,4095)` is named in all 256 galaxies → 256×). The join turned 14,524 systems into **81,786 rows**; since `total`/`pages` come from an un-joined `COUNT(*)` (→73 pages), pagination stopped after ~14,600 fanned rows = only the first **2,648 distinct systems** (82% invisible). Sibling queries in the same file (`systems.py:317-320`, `644-647` map endpoints) already did the join right — this was sibling-query drift never caught because the list `COUNT` (no join) made the "14,524 systems" total *look* correct. **Fix:** added `AND COALESCE(r.reality,'Normal')=COALESCE(s.reality,'Normal') AND COALESCE(r.galaxy,'Euclid')=COALESCE(s.galaxy,'Euclid')` to every buggy regions join (matching the existing correct pattern). Primary: [systems.py](Haven-UI/backend/routes/systems.py) `/api/systems` (list), `/api/systems/search` (count+fetch), `/api/search` (count+fetch), `/api/glyph/resolve` (join template). Secondary same-bug: [control_room_api.py](Haven-UI/backend/control_room_api.py) DB export, [analytics.py](Haven-UI/backend/routes/analytics.py) community detail, [partners.py](Haven-UI/backend/routes/partners.py) my-systems, [warroom.py](Haven-UI/backend/routes/warroom.py) territory/conflict queries (3 had galaxy but missing reality; the territory `system_count` subquery was cross-galaxy-inflated). **Verified on prod copy:** 3-col join → 81,786 rows; **5-col join → exactly 14,524, no fan-out.** **Safe for Create/Systems/3D-map:** the Wizard never lists via these endpoints (single-row `/api/systems/{id}` + exact-name dup search); SystemsList does no client dedup and the region drill-down (`/api/systems_by_region`) has no join; the 3D map's star/region clouds come from `/api/map/snapshot` + `/api/map/regions-aggregated` which **already** use the 5-col join (untouched), and the Cartographer filter dedups by glyph into a Set. Region-name display: 14,333 systems keep their correct name; only **76** lose a name (each a *wrong* cross-galaxy match; `regions` has 0 NULL galaxy/reality on prod). Backend-only — no schema change, no migration, no frontend change. Backend `--build` deploy/restart. `/api/status` 1.81.2 → 1.81.3. |
| Backend API | 1.81.3 | 2026-06-26 | See Master Haven 1.82.5. The buggy 3-column `LEFT JOIN regions r ON s.region_x=r.region_x AND s.region_y=r.region_y AND s.region_z=r.region_z` fanned out systems by every galaxy/reality that named the same coords; every such join now appends `AND COALESCE(r.reality,'Normal')=COALESCE(s.reality,'Normal') AND COALESCE(r.galaxy,'Euclid')=COALESCE(s.galaxy,'Euclid')` (warroom's 3 conflict joins already had galaxy → only reality added; its territory-search `system_count` subquery galaxy/reality-scoped to the outer system). COUNT queries in the search paths got the identical change so totals match the (now un-fanned) fetch; the search WHERE still references `r.custom_name`, so the join stays and region-name search now matches only a system's own region. Left intentionally untouched (verified harmless): the already-5-col map/contributor joins, and `regions.py`/`poster_service.py` region counts which use `COUNT(DISTINCT s.id)` + `GROUP BY`. All 5 edited files byte-compile. No schema/migration. `/api/status` 1.81.2 → 1.81.3. Backend `--build`/restart. |
| **Master Haven** | 1.82.4 | 2026-06-25 | **Fix: the dashboard mini-map preview was shrouded by the cartographer's search bar + filter gear.** The "Galaxy Overview" preview on the Dashboard is an iframe of `/map/latest?embed=true&hideUI=true` (→ [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html), served by [control_room_api.py](Haven-UI/backend/control_room_api.py) `get_map`). The cartographer already has an embed mode — `IS_EMBED` resolves true for the iframe and `applyEmbedMode()` runs at init — but its hide list was **stale**: it covered `.topbar/.hint/#legend/#zoom-bar/#map-breadcrumb/#focus-chip/#detail/#crosshair` and never included the later-added "v11 SEARCH + FILTER" UI, so the search bar (`#carto-search`) and gear (`#carto-filter-toggle`) stayed visible over the preview. **Fix (one-line, embed-only):** added `#carto-search`, `#carto-filter-toggle`, `#carto-pills`, `#carto-filters`, `#carto-filter-backdrop` to the `applyEmbedMode()` hide list. **Full-map view is provably unaffected** — "Open Full Map →" loads `/map/latest` with no `embed`/`hideUI` params, so `IS_EMBED` is false and `applyEmbedMode()` early-returns; its search/filter UI is untouched. Edited `public/VH-Cartographer.html` + copied to `dist/` (byte-identical; `get_map` reads `dist/` first). Frontend map-asset only — no backend/JS-logic/API/migration change. Backend `--build` deploy ships the updated `dist/`. `package.json` 1.72.2 → 1.72.3. |
| Haven-UI | 1.72.3 | 2026-06-25 | See Master Haven 1.82.4. [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) `applyEmbedMode()` hide-list extended with `#carto-search`, `#carto-filter-toggle`, `#carto-pills`, `#carto-filters`, `#carto-filter-backdrop` so the dashboard embed (`?embed=true&hideUI=true`) no longer renders the search bar + filter gear over the mini-map. Guarded by the existing `IS_EMBED` check (early-returns for the non-embed full map). `initSearch()`/`initFilters()` only attach listeners + populate dropdowns — they never set `display`, and `applyEmbedMode()` runs last in init, so the inline hide sticks. `public/` → `dist/` copied (identical). `package.json` 1.72.2 → 1.72.3. |
| **Master Haven** | 1.82.3 | 2026-06-25 | **Fix: the auto-generated region name from the first system stays stuck in the Create tab when you "Submit Another" and start the next system (all users, logged-in or out).** The 1.82.0 region-create work made the namegen effect *re-fire* on glyph change but didn't fix this — the stale value survived a different way. **Root cause (frontend state):** [`handleSubmitAnother`](Haven-UI/src/pages/Wizard.jsx) reset the system + the region guard refs (`userEditedRegionRef`, `lastProceduralRegionRef = ''`) **but never cleared the `proposedRegionName` state itself**. The region auto-fill guard only overwrites when the field is empty OR still equals the last value it auto-filled (`prev === lastProceduralRegionRef`); after Submit Another it saw a non-empty leftover name that no longer matched the now-empty `lastProceduralRegionRef`, so it **misread the stale value as a user-typed customization and preserved it** — meaning system 2 displayed (and could be submitted with, via `proposed_region_name` in `buildPayload`) system 1's region name. **Fix (frontend-only):** (1) `handleSubmitAnother` now also clears `proposedRegionName`/`regionNameSavedAt`/`regionInfo` alongside the refs, restoring the invariant `proposedRegionName === '' === lastProceduralRegionRef` so the next system's namegen fills cleanly; (2) defensive safety-net in the namegen guard — also overwrite when `lastProceduralRegionRef === ''` (with `userEditedRegionRef` already false above, a non-empty value when nothing's been auto-filled can only be a stale carry-over, never a user edit), so any future reset that forgets `proposedRegionName` can't resurrect this class of bug. **Verified:** sibling reset paths (`restoreDraft`, edit-mode hydration) start from a fresh mount / already-named region and were already clean; `npm run build` clean (14.69s, 0 errors). Frontend rebuild only — no backend change, no migration, no API change. `package.json` 1.72.1 → 1.72.2. |
| Haven-UI | 1.72.2 | 2026-06-25 | See Master Haven 1.82.3. [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx): `handleSubmitAnother` now calls `setProposedRegionName('')` + `setRegionNameSavedAt(null)` + `setRegionInfo(null)` next to the existing ref resets (the actual fix — the prior code reset `lastProceduralRegionRef`/`userEditedRegionRef` but left `proposedRegionName` stale, so the region-namegen guard `prev === lastProceduralRegionRef` treated the carry-over as a user edit and preserved system 1's region name on system 2). Region-namegen guard gains a third overwrite clause `|| !lastProceduralRegionRef.current` (safety net: nothing auto-filled yet + user hasn't typed ⇒ any non-empty value is a stale carry-over). Frontend-only; build clean. `package.json` 1.72.1 → 1.72.2. |
| **Master Haven** | 1.82.2 | 2026-06-25 | **Fix B (structural): system rebuilds no longer orphan their discoveries — cascade-proof relink + planet/moon id reuse.** Investigating Fix B revealed the real, broad bug behind the recurring "discoveries went to space" incidents: the `discoveries` FKs are `ON DELETE SET NULL` and the app runs `PRAGMA foreign_keys=ON`, so the `DELETE FROM planets` in every `save_system`/batch rebuild **immediately nulls every linked discovery** — and the existing `relink_discoveries_after_rebuild` (which matches `discoveries.planet_id = old_id`) then finds nothing, because the cascade already set them to NULL. So the relink has been a **no-op under FK-on**, and **every system edit silently orphaned its discoveries**. Measured on prod: **111 of 433 discoveries (26%) currently orphaned** (top: [RES]Memoro 47, [RES]Imdales 38, HRCC/Haven systems). **Fix:** new cascade-proof helpers in [db.py](Haven-UI/backend/db.py) — `capture_discovery_links()` records each discovery's planet/moon **name** BEFORE the delete (while the link is intact), `restore_discovery_links()` re-points by name AFTER the reinsert (survives the cascade; the broken id→id `relink_discoveries_after_rebuild` is retired from both callers). Plus **planet/moon id reuse**: the rebuild now re-inserts each body with its **pre-delete id** (from `snapshot_child_name_maps`, popped from a copy; new bodies get a NULL id → AUTOINCREMENT assigns) so primary keys are **stable across edits** — which fixes the original [RES]Boulde pending-discovery race (a queued discovery's `planet_id` stays valid) and protects any other id reference. Wired into [save_system](Haven-UI/backend/control_room_api.py) + batch-approve ([approvals.py](Haven-UI/backend/routes/approvals.py)); single-approve (already merge-by-name) untouched. **Verified on a prod DB copy:** column/placeholder balance of all 4 edited INSERTs (planets 60=60, moons 45=45); a full Boulde rebuild **preserves planet ids [37333–37336]** and **restores all 37 discovery links** (27 Oomo 56/W4 / 10 Crewsb Alpha / 1 genuinely-unlinked) where the current code would orphan all 38. **Open follow-up:** the 111 pre-existing orphans aren't auto-fixed by this (it prevents *future* orphaning) — most are recoverable via the same Boulde pending-snapshot backfill, offered as a separate pass. No schema change, no migration. `/api/status` 1.81.1 → 1.81.2. Backend `--build`/restart. |
| Backend API | 1.81.2 | 2026-06-25 | See Master Haven 1.82.2. [db.py](Haven-UI/backend/db.py): new `capture_discovery_links(cursor, system_id)` (pre-delete, returns `[(discovery_id, planet_name_lower|None, (parent_lower,moon_lower)|None)]`) + `restore_discovery_links(cursor, system_id, captured)` (post-reinsert, re-points by name; cascade-proof). [control_room_api.py](Haven-UI/backend/control_room_api.py) `save_system` + [routes/approvals.py](Haven-UI/backend/routes/approvals.py) batch-approve: capture links before the planet DELETE, restore after (replacing the FK-on-dead `relink_discoveries_after_rebuild`); planet + moon INSERTs gain a leading `id` column fed `_reuse_planets.pop(name)` / `_reuse_moons.pop((planet,moon))` from `snapshot_child_name_maps` (copy, pop-on-use; None → AUTOINCREMENT) so ids survive the rebuild; `planet_id`/`set_base_fields` ids use the reused value. `relink_discoveries_after_rebuild` left defined but no longer imported/called. Backend-only; no schema/migration. `/api/status` 1.81.1 → 1.81.2. Backend `--build`/restart. |
| **Master Haven** | 1.82.1 | 2026-06-25 | **Fix: discoveries lose their planet/moon tag when a system's planets are rebuilt (planet-id churn) + backfilled `[RES]Boulde`.** A RES sub-admin's 38 fauna/flora on `[RES]Boulde` all rendered "in space" (no `planet_id`/`moon_id`). **Root cause:** `planet_id` is a volatile autoincrement FK; `save_system`/batch DELETE+INSERT planets on edit → new ids (`37126→37333`…). The discoveries carried only the (now-stale) ids with empty `location_name`, and the submitter's own direct-save rebuilt the planets ~190ms *before* the discovery burst, so the submit-time `planet_id→planet_name` denormalization returned nothing → at approval `_resolve_discovery_links` had no name to recover by → it nulled every link (correct fail-safe, just nothing to recover). Same id-churn family as 1.79.0/1.81.1/1.88.1, worst variant (dropdown submit = empty `location_name`). **Backfill (done on prod, full backup taken first):** mapped each old `planet_id`→name from the rebuilding edit's `pending_systems` snapshot (#10314 embeds id+name) → current planet by name, joined live↔pending by exact timestamp; **37/38 relinked** (27 Oomo 56/W4, 10 Crewsb Alpha), 1 left unlinked (no planet was ever chosen for it). Verified via `/api/systems/{id}`. **Fix A (this deploy, backend-only):** [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py) — capture the body **name** at submit even when the id is stale (client-name fallback + mirror into the blob) and relink by the captured `planet_name`/`moon_name` first (new `_match_body_by_exact_name`), then the `location_name` heuristic — closes the common queued-then-rebuilt case. **Fix B (next, structural):** stop churning planet ids — make `save_system`+batch UPDATE planets in place by name (like single-approve) — the only thing that prevents the same-second race. No schema change, no migration. `/api/status` 1.81.0 → 1.81.1. Backend `--build`/restart. |
| Backend API | 1.81.1 | 2026-06-25 | See Master Haven 1.82.1. [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py): new `_match_body_by_exact_name(cursor, system_id, kind, name)` (case-insensitive exact match vs the system's current planets/moons; None on ambiguity). `_resolve_discovery_links` gains `planet_name`/`moon_name` params and tries the captured-name exact match **before** the `location_name` substring heuristic; `_apply_discovery_approval` passes `submission['planet_name']`/`['moon_name']` (falls back to the JSON blob). `submit_discovery` + `create_discovery` keep a client-supplied `planet_name`/`moon_name` when the id can't be resolved (already rebuilt) and mirror both into the `discovery_data` blob, so the relink key survives id churn. Byte-compiles. Backend-only; no schema/migration. `/api/status` 1.81.0 → 1.81.1. Backend `--build`/restart. |
| **Master Haven** | 1.82.0 | 2026-06-23 | **Member-reported bug sweep: resource-filter overhaul (moons + multi-select), region-name create-tab fixes, live-preview colours, navbar fit, and conflict-level "None" now scores.** Five items from an active member's list. **(1) Resource filter:** the Systems-tab Resource control now reads `moons.materials` as well as `planets.materials` (a moon-only resource was previously unlisted AND unfilterable) and is **multi-select** (pick several; OR / "any of") — [get_distinct_resources](Haven-UI/backend/routes/systems.py) + the `resource` clause in [db.py](Haven-UI/backend/db.py) gained a `moons` subquery; [FilterModal.jsx](Haven-UI/src/components/FilterModal.jsx) chip multi-select with `resource` promoted to the OR-multi key set in [useFilters.js](Haven-UI/src/hooks/useFilters.js) + [SystemsContext.jsx](Haven-UI/src/contexts/SystemsContext.jsx). **(2) Region names on Create:** `GET /api/regions/{rx}/{ry}/{rz}` ([regions.py](Haven-UI/backend/routes/regions.py)) and the admin direct-save ([control_room_api.py](Haven-UI/backend/control_room_api.py)) now `normalize_reality()` like every other region path (a region named under the normalized reality is finally found → the "already named" badge stops re-prompting); the Wizard region effect re-suggests on glyph change and no longer silently waives the required-name rule on a failed lookup ([Wizard.jsx](Haven-UI/src/pages/Wizard.jsx)). **(3) Mock-up colours:** the create-tab live previews route biome through `getBiomeCategory()` so descriptive adjectives (Paradise/Icy/Crimson…) colour correctly instead of falling to grey, and star colours are unified to the canonical `.pill-star-*` palette — new single-source `biomeTintHex()` in [biomeCategoryMappings.js](Haven-UI/src/data/biomeCategoryMappings.js) + [starColors.js](Haven-UI/src/utils/starColors.js) wired into WizardPreviewPanel / WizardAdvancedPreview / OrbitalDiagram / PlanetSphere / SystemThumb (divergent local maps removed). **(4) Navbar:** the top bar is now full-width + wraps ([Navbar.jsx](Haven-UI/src/components/Navbar.jsx)) so a logged-in super-admin sees every item without scrolling sideways. **(5) Conflict "None":** a non-abandoned system with `conflict_level='None'` now counts toward completeness (was scored as missing) — [completeness.py](Haven-UI/backend/services/completeness.py) + client mirror [useCompletenessScore.js](Haven-UI/src/hooks/useCompletenessScore.js); migration **1.99.0** re-scores all systems. **Verified:** all 6 touched backend files byte-compile; `npm run build` clean (twice). Backend `--build` (migration 1.99.0 auto-runs) + frontend rebuild. `/api/status` 1.80.0 → 1.81.0, `package.json` 1.71.0 → 1.72.0. |
| Backend API | 1.81.0 | 2026-06-23 | See Master Haven 1.82.0. [routes/systems.py](Haven-UI/backend/routes/systems.py) `get_distinct_resources` now also scans `moons.materials` (joined via planets) alongside `planets.materials`. [db.py](Haven-UI/backend/db.py) `_build_advanced_filter_clauses` `resource` clause: `_split_csv` → multi-select OR across resources, each matched against `planets.materials` **and** a new `moons` EXISTS subquery (planet common/uncommon/rare kept as fallback). [routes/regions.py](Haven-UI/backend/routes/regions.py) `api_get_region` now `normalize_reality(reality)` (was the only region read that didn't). [control_room_api.py](Haven-UI/backend/control_room_api.py): `normalize_reality` imported + applied to the admin direct-save region write. [services/completeness.py](Haven-UI/backend/services/completeness.py): `conflict_level='None'` counts as filled on non-abandoned systems (new branch, `allow_none_sentinel=True`, parallel to `dominant_lifeform`). Migration **1.99.0** ([migrations.py](Haven-UI/backend/migrations.py)) re-scores all systems (idempotent; reuses `update_completeness_score`). `/api/status` 1.80.0 → 1.81.0. Backend `--build` deploy; migration auto-runs. |
| Haven-UI | 1.72.0 | 2026-06-23 | See Master Haven 1.82.0. [FilterModal.jsx](Haven-UI/src/components/FilterModal.jsx): new `MultiSelectField` (chip multi-add) replaces the single-select Resource control. [useFilters.js](Haven-UI/src/hooks/useFilters.js) + [SystemsContext.jsx](Haven-UI/src/contexts/SystemsContext.jsx): `resource` moved into the OR-multi key set (URL round-trips it as a list). New single-source [src/utils/starColors.js](Haven-UI/src/utils/starColors.js) (`STAR_HEX`, mirrors `.pill-star-*`) + `BIOME_CATEGORY_HEX`/`biomeTintHex()` in [biomeCategoryMappings.js](Haven-UI/src/data/biomeCategoryMappings.js); both wired into [WizardPreviewPanel.jsx](Haven-UI/src/components/wizard/WizardPreviewPanel.jsx) (now biome-tints planet dots too), [WizardAdvancedPreview.jsx](Haven-UI/src/components/wizard/WizardAdvancedPreview.jsx), [OrbitalDiagram.jsx](Haven-UI/src/components/shared/OrbitalDiagram.jsx), [PlanetSphere.jsx](Haven-UI/src/components/shared/PlanetSphere.jsx), [SystemThumb.jsx](Haven-UI/src/posters/SystemThumb.jsx) (local divergent maps removed). [Navbar.jsx](Haven-UI/src/components/Navbar.jsx): wrapper `container mx-auto`→`w-full`, desktop nav `flex-1 min-w-0 flex-wrap justify-end`, item padding `px-3`→`px-2`. [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx): region-lookup effect depends on `glyph_code`; required-name guard no longer waived on a null/failed lookup. [useCompletenessScore.js](Haven-UI/src/hooks/useCompletenessScore.js): `conflict_level='None'` counts (mirrors backend). Build clean. `package.json` 1.71.0 → 1.72.0. |
| **Master Haven** | 1.81.0 | 2026-06-23 | **Planet/moon count dropdowns (auto-generate shells, 6-body cap) + the grade is now weighted by planet AND moon count.** Two asks. **(1) Body-count dropdowns:** [SectionPlanets](Haven-UI/src/pages/Wizard.jsx) gets **Planets (0–6)** and **Moons (0…6−planets)** selects + a live "Bodies N/6" chip; picking a count generates/trims empty shells instead of clicking "Add" repeatedly. NMS caps a system at 6 celestial bodies (planets+moons) — enforced in the dropdowns, a submit-validation rule, AND `validate_system_data` ([approvals.py](Haven-UI/backend/routes/approvals.py)) so direct-save/API are bounded too. New moons attach to the first planet with a per-moon **"Orbits"** selector ([PlanetEditor.jsx](Haven-UI/src/components/PlanetEditor.jsx)) to move them; trimming removes empty shells first and confirms before deleting filled-in bodies. Shared `PLANET_DEFAULTS`/`MOON_DEFAULTS` extracted to [bodyDefaults.js](Haven-UI/src/data/bodyDefaults.js) so the generator and the manual "Add Moon" modal build identical shells. **(2) Moon-weighted grade:** Planet Environment (25) + Planet Life (15) now average over ALL bodies (planets + moons), so each weighs 1/(planets+moons) — a 5-planet + 1-moon system = ~16.7% each, and a blank moon drags the grade down like an undocumented planet. Moons are scored on their own biome/weather/sentinel + fauna/flora/resources via new per-body helpers in [completeness.py](Haven-UI/backend/services/completeness.py); SystemDetail lists each moon as its own breakdown row. Migration **1.98.0** re-scores all systems (idempotent). **Verified:** backend byte-compiles; grading sim (5P + 1 empty moon → env 21 / life 12, ~16.7% each; full moon earns its share); body-cap (6 ok, 7 rejected); `npm run build` clean. `/api/status` 1.79.0 → 1.80.0, `package.json` 1.70.0 → 1.71.0. |
| Backend API | 1.80.0 | 2026-06-23 | See Master Haven 1.81.0. [completeness.py](Haven-UI/backend/services/completeness.py): new `_score_body_environment`/`_score_body_life` helpers; `calculate_completeness_score` builds a combined `bodies` list (planets + each planet's moons) and averages Planet Environment/Life over all of them (each body 1/N), adds `body_count` to the breakdown, and labels moon detail rows `🌙 … (moon of …)`. `validate_system_data` ([approvals.py](Haven-UI/backend/routes/approvals.py)) rejects >6 total bodies (planets + moons), so every intake path is bounded. Migration **1.98.0** ([migrations.py](Haven-UI/backend/migrations.py)) re-scores every system so the cached grade picks up the moon weighting (idempotent; reuses `update_completeness_score`). `/api/status` 1.79.0 → 1.80.0. Backend `--build` deploy; migration auto-runs. |
| Haven-UI | 1.71.0 | 2026-06-23 | See Master Haven 1.81.0. New [bodyDefaults.js](Haven-UI/src/data/bodyDefaults.js) (`PLANET_DEFAULTS`/`MOON_DEFAULTS`, single source) imported by [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) + [PlanetEditor.jsx](Haven-UI/src/components/PlanetEditor.jsx). Wizard: new `setPlanetCount`/`setMoonCount`/`reassignMoon`/`trimMoons`/`bodyHasData`/`countMoons`; `SectionPlanets` renders the Planets/Moons count selects + "Bodies N/6" chip (replacing "Generate Placeholders"); 6-body submit-validation rule; "Add Planet" disabled at cap. PlanetEditor: per-moon "Orbits" planet selector (shown when >1 planet), cap-aware "Add Moon", uses shared `MOON_DEFAULTS`. Build clean. `package.json` 1.70.0 → 1.71.0. |
| **Master Haven** | 1.80.0 | 2026-06-23 | **Grading rework: S+ renamed to "X" (Platinum), the "fully charted" checklist relaxed, and base coordinates added + connected to discoveries.** Parker's three asks. **(1) X tier:** the top "fully charted" grade now displays **X** in **Platinum `#E5E4E2`** (NMS's above-S X-class; the game renders X purple, which collides with our A=purple, so platinum) instead of "S+ Diamond Cyan" — display-only: `GRADE_SPLUS = 'X'` in [constants.py](Haven-UI/backend/constants.py), recolored `TIER_COLORS`/`GRADE_BADGE` in [gradeColors.js](Haven-UI/src/utils/gradeColors.js) + `.grade-splus`/`.bar-splus` in [index.css](Haven-UI/src/styles/index.css) + both map HTML inline copies; internal names (`is_fully_charted`, `grade_splus`, `check_splus_eligible`) unchanged. **(2) Base ↔ discovery connected (either/or):** the X "documented base" item is now satisfied by **base lat/long on any planet/moon OR a base-type discovery** — new `base_latitude`/`base_longitude` on `planets`+`moons` (+ `base_location` on moons, which never had the column) via migration **1.97.0**, collected with the shared `LatLngInput` in [CelestialBodyEditor.jsx](Haven-UI/src/components/CelestialBodyEditor.jsx) (now shown for moons too), persisted via a new `set_base_fields` helper after every planet/moon INSERT, shown on SystemDetail + the approval review. Legacy free-text `base_location` still counts (no demotions). **(3) Wonder relaxed:** wonder notes now required on **at least one** planet/moon (was every planet; moons now count). [`check_splus_eligible`](Haven-UI/backend/services/completeness.py) reworked + migration 1.97.0 re-scores all systems (net a loosening → more X). **Verified:** all backend files byte-compile; `npm run build` clean. Backend `--build` (migration 1.97.0 auto-runs) + frontend rebuild. `/api/status` 1.78.0 → 1.79.0, `package.json` 1.69.0 → 1.70.0. |
| Backend API | 1.79.0 | 2026-06-23 | See Master Haven 1.80.0. [constants.py](Haven-UI/backend/constants.py) `GRADE_SPLUS` 'S+'→'X'. [completeness.py](Haven-UI/backend/services/completeness.py) `check_splus_eligible`: wonder passes on ANY planet OR moon (now queries moon wonder fields too); base passes via base lat/long on any body, a `type_slug='base'` discovery, or legacy `base_location` text (new `_has_base_coords`/`_has_base_discovery` helpers). New `set_base_fields(cursor, table, id, body)` in [db.py](Haven-UI/backend/db.py) writes base_location/lat/long via a follow-up UPDATE after each planet/moon INSERT (save_system + single/batch approve), coords range-validated via `normalize_discovery_coords` — no-op without base data so it can't wipe untouched bases. Migration **1.97.0**: `base_latitude`/`base_longitude` on planets+moons + `base_location` on moons, then re-score every system. `/api/status` 1.78.0 → 1.79.0. Backend `--build`; migration auto-runs. |
| Haven-UI | 1.70.0 | 2026-06-23 | See Master Haven 1.80.0. [gradeColors.js](Haven-UI/src/utils/gradeColors.js): `TIER_COLORS`/`GRADE_BADGE` key 'S+'→'X', color → Platinum `#E5E4E2`. [index.css](Haven-UI/src/styles/index.css): `.grade-splus`/`.bar-splus` recolored platinum (token kept, matches backend `grade_splus`). Grade letter + `=== 'X'` comparison in [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx), [GalaxyGrid.jsx](Haven-UI/src/components/GalaxyGrid.jsx), [GlyphFinder.jsx](Haven-UI/src/pages/GlyphFinder.jsx), [Profile.jsx](Haven-UI/src/pages/Profile.jsx); SystemsList/ComparePanel already render via `GRADE_BADGE_STYLE[completeness_grade]` (now 'X'). [CelestialBodyEditor.jsx](Haven-UI/src/components/CelestialBodyEditor.jsx): base section ungated for moons + `LatLngInput` for base coords (new `setFields` multi-key setter). [useCompletenessScore.js](Haven-UI/src/hooks/useCompletenessScore.js): X relabel + any-body wonder + base lat/long guidance. Base coords displayed on [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) + [SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx). [HelpPanel.jsx](Haven-UI/src/components/wizard/HelpPanel.jsx) X copy. Map HTML X/platinum, copied to dist. `package.json` 1.69.0 → 1.70.0. |
| **Master Haven** | 1.79.0 | 2026-06-23 | **New planet/moon attributes (Swarm Debris, Trash Debris, High Sentinel Activity, Aggressive Sentinel Activity), a definitive "No space station" option, and Ancient Bones / Salvageable Scrap / Vile Brood removed from the materials list (they were duplicated as attributes).** Parker's three asks, done end-to-end. **Attributes:** four new boolean columns on `planets` + `moons` (migration **1.96.0**), wired through every write path ([save_system](Haven-UI/backend/control_room_api.py), single + batch [approve](Haven-UI/backend/routes/approvals.py), [csv_import](Haven-UI/backend/routes/csv_import.py)), the editor toggle grid ([CelestialBodyEditor.jsx](Haven-UI/src/components/CelestialBodyEditor.jsx)), wizard defaults ([Wizard.jsx](Haven-UI/src/pages/Wizard.jsx)), system-detail badges ([SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx)), the approval review UI ([SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)), the 3D map ([VH-System-View.html](Haven-UI/public/VH-System-View.html)) and CSV note-keyword parsing. **No station:** new `systems.no_space_station` flag, surfaced as a **3-way radio** (Has a station / No station / Not documented) in the wizard Space Station section; a flagged system gets full station completeness credit + S+ exemption (like an Abandoned system) in [completeness.py](Haven-UI/backend/services/completeness.py) + the client mirror [useCompletenessScore.js](Haven-UI/src/hooks/useCompletenessScore.js), and renders a "No Space Station" note on SystemDetail / approval. **Materials:** the three harvestables removed from [adjectives.js](Haven-UI/src/data/adjectives.js) `resourcesList` + [resource_catalog.py](Haven-UI/backend/resource_catalog.py) (canonical list + aliases); `normalize_materials()` now drops them, and migration **1.96.0** lifts existing occurrences onto the matching attribute flag, strips them from `materials`, and re-scores affected systems. **Verified:** all backend files byte-compile; an AST pass found **0 placeholder/value mismatches** across every INSERT/execute; `npm run build` clean (11.59s, 0 errors); migration (incl. idempotent re-run), completeness no-station credit, and the materials normalizer all tested on throwaway DBs. Backend `--build` deploy (migration auto-runs at startup) + frontend rebuild. `/api/status` → 1.78.0, `package.json` → 1.69.0. |
| Backend API | 1.78.0 | 2026-06-23 | See Master Haven 1.79.0. Migration **1.96.0** ([migrations.py](Haven-UI/backend/migrations.py)): +4 boolean cols (`swarm_debris`, `trash_debris`, `high_sentinel_activity`, `aggressive_sentinel_activity`) on `planets`+`moons`, `systems.no_space_station`, + a materials→attribute backfill/re-score for the 3 harvestables (idempotent). New cols written at every planet/moon INSERT/UPDATE in [control_room_api.py](Haven-UI/backend/control_room_api.py) `save_system`, [approvals.py](Haven-UI/backend/routes/approvals.py) approve (planet UPDATE/INSERT + 2 moon INSERTs) + batch, and [csv_import.py](Haven-UI/backend/routes/csv_import.py) (which also lifts harvestables out of CSV materials + maps new note keywords). `no_space_station` written on every system INSERT/UPDATE (save/approve/batch) with station-row skip on create + clear on edit-to-none; [completeness.py](Haven-UI/backend/services/completeness.py) grants full station credit + S+ exemption when set. [resource_catalog.py](Haven-UI/backend/resource_catalog.py): 3 harvestables dropped from `CANONICAL_RESOURCES` + aliases, new `NON_MATERIAL_TOKENS` drop-set in `normalize_materials()`. Init-time `add_column_if_missing` safety net added for fresh DBs. `/api/status` 1.77.1 → 1.78.0. Backend `--build` deploy; migration auto-runs. |
| Haven-UI | 1.69.0 | 2026-06-23 | See Master Haven 1.79.0. [CelestialBodyEditor.jsx](Haven-UI/src/components/CelestialBodyEditor.jsx): 4 new toggles in `SHARED_ATTRIBUTES`. [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx): `PLANET_DEFAULTS` + 4 attrs, `EMPTY_SYSTEM.no_space_station`, `toggleStation`→`setStationMode` 3-way + `SectionStation` radio, station-credit in the completeness preview. [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx): 4 `FEATURE_FLAGS` badges + "No Space Station" indicator. [SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx): 4 checkboxes + badges across all 5 planet/moon blocks + station "no station" review. [adjectives.js](Haven-UI/src/data/adjectives.js): 3 harvestables removed from `resourcesList`. [useCompletenessScore.js](Haven-UI/src/hooks/useCompletenessScore.js): `no_space_station` station credit + S+. [VH-System-View.html](Haven-UI/public/VH-System-View.html): 4 specials in both cards (copied to dist on build). Build clean (11.59s, 0 errors). `package.json` 1.68.1 → 1.69.0. |
| **Master Haven** | 1.78.0 _(was 1.94.0)_ | 2026-06-22 | **A sub-admin can no longer be granted a feature the civ itself doesn't have.** Parker: "leaders are still able to give sub admin permissions the civ itself didn't have — I didn't get RES civ the CSV uploads but they were still able to give a sub admin those perms." **Root cause:** a sub-admin's effective features were taken straight from their per-member override with **no ceiling against the civ's `enabled_features_default`**. Two code paths had this bug identically: [`_recompute_profile_features`](Haven-UI/backend/routes/civilizations.py) (`effective = per_member if … else default`, line ~595 — this materializes `user_profiles.enabled_features`, the **session/route-guard** source) and the Sub-Admins roster [`GET /api/sub_admins`](Haven-UI/backend/routes/partners.py) (`effective = override if … else civ_default`, the **display**). So an override containing `csv_import` granted/showed `csv_import` even on a civ without it. **Fix — cap the sub-admin override at the civ's own feature set (`override ∩ enabled_features_default`) at every layer:** **(1)** `_recompute_profile_features` now intersects the override with the civ default → the **authoritative server-side ceiling** (an out-of-civ grant simply never reaches the session, no matter who set it or how). **(2)** `GET /api/sub_admins` caps the `effective` it reports so the roster display matches. **(3)** The two editors ([CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx) `MemberRow`, [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx) `SubAdminRow`) now **only offer the civ's own features** as checkboxes (filtered by `civDefaults` / `member.civ_default_features`) and **intersect the saved set** with them, so you can't even check (or store) `csv_import` for a sub-admin of a civ without it; an empty civ feature set shows a "super admin sets the civ's feature set first" note. **Verified:** `civilizations.py` + `partners.py` byte-compile; `npm run build` clean (11.65s, 0 errors); all 6 edits confirmed intact after concurrent editing. Frontend rebuild + backend restart. No schema/migration. **Existing data:** the ceiling applies the moment a profile is recomputed (any membership/role/feature change) and the roster display is corrected immediately; already-over-granted sub-admins keep the stale grant in their *session* only until their next recompute — say the word and I'll add a one-time recompute migration (like v1.95.0) to flush them all on deploy. `/api/status` → 1.91.0, `package.json` → 1.81.0. |
| Backend API | 1.77.1 _(was 1.91.0)_ | 2026-06-22 | See Master Haven 1.94.0. [civilizations.py](Haven-UI/backend/routes/civilizations.py) `_recompute_profile_features`: a sub_admin's effective set is now `{f for f in effective if f != 'war_room' and f in set(default)}` — capped at the civ's `enabled_features_default` (the authoritative ceiling on `user_profiles.enabled_features`). [partners.py](Haven-UI/backend/routes/partners.py) `GET /api/sub_admins`: `effective` for display is capped the same way (`[f for f in override if f in set(civ_default)]`). Read/compute-side only; no schema/migration. `/api/status` → 1.91.0. Backend restart required. |
| Haven-UI | 1.68.1 _(was 1.81.0)_ | 2026-06-22 | See Master Haven 1.94.0. [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx) `MemberRow`: the per-member feature checkboxes are filtered to `(civDefaults).includes(f.id)`, and Save intersects the draft with `civDefaults`. [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx) `SubAdminRow`: checkboxes filtered to `member.civ_default_features`, Save intersects with it, plus an empty-civ-feature-set note. Build clean (11.65s, 0 errors). `package.json` → 1.81.0. |
| **Master Haven** | 1.93.0 | 2026-06-22 | **Civ leaders can no longer change permissions — they manage the roster (add / role / remove); permissions stay super-admin-controlled.** Parker: "civ leaders themselves should not have the ability to change their own perms — just add leaders, co-leaders, or sub-admins." Narrows 1.92.0, which had let leaders "edit brand/defaults": a leader could still open their civ's **feature-defaults grid** and the **per-member Perms editor**, a self-/team-escalation surface. **Fix (server guard + UI hide):** **Backend** ([civilizations.py](Haven-UI/backend/routes/civilizations.py)) — `update_civilization` now **strips `enabled_features_default` from any non-super-admin update** (the old code only stripped `war_room`; this subsumes it), so a leader edits brand (name/color/theme) but not the feature template; `add_member` forces `enabled_features = None` for non-super-admins (a leader-added sub-admin still lands on the zero-perm `[]` default from 1.92.0 until a super admin grants features); `update_member` only writes `enabled_features` when the caller is super admin (role + approve-personal-cap changes still allowed for leaders). **Frontend** — [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx): the edit-mode feature-defaults grid is super-admin-only, and `MemberRow`'s "Perms" editor is hidden for non-super-admins (leaders see role + cap + remove). [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx): `SubAdminRow`'s "Edit perms" editor is hidden for non-super-admins (the read-only feature summary, approve-personal, revoke, and **Add Sub-Admin** remain), and the page blurb is role-aware ("a super admin grants what each one can do"). Founding a civ + its feature grid were already super-admin-only. Leaders retain full roster management. **Verified:** `civilizations.py` byte-compiles, `is_super` scoped in all 3 handlers; `npm run build` clean (12.96s, 0 errors); all edits survived concurrent editing. Frontend rebuild + backend restart. No schema/migration. `/api/status` → 1.90.0, `package.json` → 1.80.0. |
| Backend API | 1.90.0 | 2026-06-22 | See Master Haven 1.93.0. [civilizations.py](Haven-UI/backend/routes/civilizations.py): `update_civilization` strips `enabled_features_default` for non-super-admins (replaces the narrower war_room-only strip); `add_member` sets `features = payload.get('enabled_features') if is_super else None`; `update_member` captures `session_data`/`is_super` and only writes `enabled_features` when super admin (role + `can_approve_personal_uploads` still allowed for leaders). Permission writes are super-admin-only across the civ-management surface; leaders keep roster management. No schema/migration. `/api/status` → 1.90.0. Backend restart required. |
| Haven-UI | 1.80.0 | 2026-06-22 | See Master Haven 1.93.0. [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx): edit-mode feature-defaults grid wrapped in `auth.isSuperAdmin`; `MemberRow` gains an `isSuperAdmin` prop that gates the "Perms" button + per-member feature editor. [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx): `SubAdminRow` gains `isSuperAdmin`, gating the "Edit perms" button + editor; header blurb role-aware for non-super-admins. Build clean (12.96s, 0 errors). `package.json` → 1.80.0. |
| **Master Haven** | 1.92.0 | 2026-06-22 | **Sub-admins now start with ZERO permissions until a leader explicitly grants them, and civ leaders can manage their own civilization (not just super admins).** Parker: "the creation of sub admins and permission feels very broken when logged in as another civ, not super admin … sub admin permissions should be completely removed until a leader allows them." **Root cause:** adding a sub-admin POSTed `{profile_id, role:'sub_admin'}` with no features → `civilization_members.enabled_features` stored **NULL** → [`_recompute_profile_features`](Haven-UI/backend/routes/civilizations.py) fell through to the civ default (seeded `approvals/system_create/system_edit/stats`), so a brand-new sub-admin silently had perms nobody granted. Compounding it: civ leaders were locked out of `/admin/civilizations` (super-admin-only) although the backend already permitted them via `_require_civ_manage_access` (the Sub-Admins banner linked there → dead-end redirect); the Sub-Admins grid still exposed `war_room` (could leak it into an override out of civ-scope, undoing 1.90.0); and the Add dropdown offered civs the leader couldn't manage. **Fix (per Parker's calls — keep civ default as opt-in; open scoped civ-mgmt to leaders):** (1) `add_member` seeds a new sub_admin with an **empty override `[]`** = zero perms (leaders keep NULL = full-by-role); "Reset to civ default" stays a one-click opt-in. (2) `_recompute_profile_features` strips `war_room` from every sub_admin override (civ-scoped only). (3) `update_civilization` relaxed to `_require_civ_manage_access` (leaders edit brand/defaults) with archive still super-admin-only; `/admin/civilizations` → `RequireAdmin`, page self-gates to leader-like and hides Found/Archive for non-super; new "Civilization" navbar entry for leaders. (4) Add-Sub-Admin dropdown scoped to manageable civs. (5) **Migration v1.95.0** flips existing NULL sub_admin overrides to `[]` and re-syncs all active-membership profiles (also retroactively strips leaked war_room). **Operational:** on deploy, existing sub-admins drop to zero access until their leader re-grants (or clicks "Reset to civ default"). **Verified:** 3 backend files byte-compile; `migrations.py` imports clean; an in-memory v1.95.0 simulation passed every assertion; `npm run build` clean (11.32s, 0 errors). Backend `--build` + frontend rebuild. `/api/status` → 1.89.0, `package.json` → 1.79.0. |
| Backend API | 1.89.0 | 2026-06-22 | See Master Haven 1.92.0. [routes/civilizations.py](Haven-UI/backend/routes/civilizations.py): `add_member` seeds a new `sub_admin` with an empty override `[]` (not NULL) so they start at zero perms; `_recompute_profile_features` strips `war_room` from sub_admin effective overrides (civ-scoped grant only); `update_civilization` auth relaxed from `_require_super_admin` to `_require_civ_manage_access` with `is_active` archive/unarchive kept super-admin-only; dead `session_user_id` helper removed (its one caller now reads the guard's session). Migration **v1.95.0** ([migrations.py](Haven-UI/backend/migrations.py)) flips implicit NULL sub_admin overrides to `[]` and re-syncs `enabled_features` for every active-membership profile (also strips previously-leaked war_room from sub_admin overrides; idempotent). `/api/status` → 1.89.0. Backend `--build` deploy; migration auto-runs at startup. |
| Haven-UI | 1.79.0 | 2026-06-22 | See Master Haven 1.92.0. [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx): `war_room` removed from the per-member grid (+ stripped on save), Add-Sub-Admin civ dropdown scoped to civs the user leads (super admin → all), copy clarifies new sub-admins start at zero perms, Add button hidden when no manageable civ. [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx): page now allows leaders/co-leaders (`isSuperAdmin || isPartner`); "+ Found new civilization" and Archive/Unarchive hidden for non-super-admins. [App.jsx](Haven-UI/src/App.jsx): `/admin/civilizations` + `/admin/partners` `RequireSuperAdmin` → `RequireAdmin`. [Navbar.jsx](Haven-UI/src/components/Navbar.jsx): "Civilization" entry added to the Admin dropdown for leaders (`isPartner`). Build clean (11.32s, 0 errors). `package.json` → 1.79.0. |
| **Master Haven** | 1.91.0 | 2026-06-22 | **Discoveries are now editable from the system page AND the system-edit wizard (not just the Discoveries page), with a root fix so the planet/moon dropdown always loads.** Parker: discovery edits "need to be accessible to everyone" and editable "from both the discoveries page and the systems page." **Investigation (verified live — anonymous Playwright run against prod):** the Discoveries-page edit already worked for every role — [DiscoverySubmitModal](Haven-UI/src/components/DiscoverySubmitModal.jsx) has no role-gating and `get_system` serves planets to anonymous callers (confirmed 5/5 planets populate for an anon edit). The real gaps were: (a) **no discovery Edit on the system page** — [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) rendered `DiscoveryDetailModal` without `onEdit`; (b) the **wizard's existing-discovery list was read-only** ([Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) `SectionDiscoveries` — the "small pill box"); and (c) **`get_system`'s discoveries SELECT omitted `d.system_id`** ([control_room_api.py](Haven-UI/backend/control_room_api.py)) — so any edit launched from a system context opened the modal with no `system_id` → **empty planet dropdown** (the exact "no planets show" symptom). **Fix:** (1) added `d.system_id` to the SELECT so the payload is self-describing; (2) SystemDetail passes `onEdit` → opens the shared `DiscoverySubmitModal` in edit mode (discovery already enriched with `system_id`/`system_name`); (3) each row of the wizard's existing-discovery list gets an **Edit** button that opens the same modal, enriched with the edited system's id/name as a fallback for pre-`system_id` payloads. Every edit rides the existing discovery-edit flow → `pending_discoveries` (`edit_discovery_id`) → normal approval, **separate** from the system's own edit. The PWA service worker re-precaches on build, so members on a stale bundle pick up the current code. **Verified:** `npm run build` clean (14.78s, 0 errors); backend byte-compiles; new identifiers wired consistently across both pages. Frontend rebuild + backend restart (the read-side SELECT add). No schema/migration. `/api/status` → 1.88.0, `package.json` → 1.78.0. |
| Backend API | 1.88.0 | 2026-06-22 | See Master Haven 1.91.0. The `get_system` discoveries SELECT ([control_room_api.py](Haven-UI/backend/control_room_api.py)) now includes `d.system_id`, so the system-detail/wizard discovery payloads carry their own system id and the shared discovery edit modal can load the planet/moon dropdowns without client-side patching (closes the "empty planet dropdown when editing from a system context" trap). Read-side only; no schema/migration. `/api/status` → 1.88.0. Backend restart required. |
| Haven-UI | 1.78.0 | 2026-06-22 | See Master Haven 1.91.0. [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx): new `editingDiscovery` state + `handleEditDiscovery` (enriches `system_id`/`system_name` from the parent system), `onEdit` wired into `DiscoveryDetailModal`, and `DiscoverySubmitModal` mounted in edit mode. [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx): new `editingDiscovery` state + `handleEditExistingDiscovery`; `SectionDiscoveries` gains an `onEditExisting` prop + a per-row **Edit** button (the existing-discovery list is no longer "read-only"); `DiscoverySubmitModal` mounted in edit mode. Build clean (0 errors). `package.json` → 1.78.0. |
| **Master Haven** | 1.90.0 | 2026-06-22 | **Fix: the War Room showed for every civ leader regardless of whether their civ was given it — War Room is now a per-civ feature granted to the whole moderator team.** Parker: "the war room is displaying to everyone that has a login regardless if they are assigned to the war room." **Root cause:** `war_room` was a member of `LEADER_FEATURES` ([constants.py](Haven-UI/backend/constants.py)), and `_recompute_profile_features` ([routes/civilizations.py](Haven-UI/backend/routes/civilizations.py)) grants the **whole** `LEADER_FEATURES` set to every civ leader/co-leader **by role** — so any leader got `war_room` regardless of their civ's stored permission. Migration 1.84.0 even baked it into `user_profiles.enabled_features` for all leaders. Confirmed on **prod**: the IEA civ default = `[system_create, system_edit, approvals, stats, settings]` (no war_room) yet the IEA leader's profile had `war_room`. The frontend gate (navbar [Navbar.jsx](Haven-UI/src/components/Navbar.jsx) + route [App.jsx](Haven-UI/src/App.jsx)) was already correct — it just read an over-granted features list. **Fix (per Parker's "permission-only" choice — enrollment stays a separate super-admin step):** (1) **removed `war_room` from `LEADER_FEATURES`** so it's no longer a by-role grant. (2) `_recompute_profile_features` now grants `war_room` **civ-scoped**: any moderator (leader / co-leader / sub-admin) whose **active civ has `war_room` in `enabled_features_default`** gets it — and nobody else (super admin always has it). Because `update_civilization` already fans out a recompute to every member when `enabled_features_default` changes, **checking "War Room" on a civ instantly grants the whole moderator team; unchecking revokes all of them**. (3) **Migration v1.94.0** re-runs the role-aware union for every profile with an active civ membership (mirrors the helper; war_room civ-scoped), and first ensures any **actively-enrolled** civ keeps `war_room` in its default. **Dry-run on a prod snapshot: 40 over-granted civ leaders lose `war_room` (incl. IEA), the 7 actively-enrolled civs (Everion / Nicea / Pirate Syndicate / N//X / Shadow Worlds / Helghast / Indominus) keep it, 0 lose access who shouldn't.** (4) The legacy enroll/unenroll endpoints ([routes/warroom.py](Haven-UI/backend/routes/warroom.py)) wrote `war_room` to the dead `partner_accounts.enabled_features` (session reads `user_profiles`) — repointed to toggle it on the enrolled **civ's** `enabled_features_default` + member recompute, so the War Room Admin "Enroll" path and the civ feature grid stay consistent. **Frontend** ([CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx)): War Room labeled the per-civ all-moderators feature, excluded from the per-member sub-admin override grid (it's civ-controlled), grid captions clarified. **Verified:** 4 backend files byte-compile; `npm run build` clean (11.49s, 0 errors); prod dry-run as above. Backend `--build` deploy (migration v1.94.0 auto-runs at startup) + frontend rebuild. `/api/status` 1.85.0 → 1.86.0, `package.json` 1.75.0 → 1.75.1. |
| Backend API | 1.86.0 | 2026-06-22 | See Master Haven 1.90.0. `war_room` removed from `LEADER_FEATURES` ([constants.py](Haven-UI/backend/constants.py)). `_recompute_profile_features` ([routes/civilizations.py](Haven-UI/backend/routes/civilizations.py)) now parses each civ's `enabled_features_default` up front and adds `war_room` to the union for ANY role when the civ has it (civ-scoped), before the by-role `LEADER_FEATURES` grant. New `_set_civ_war_room_feature(cursor, partner_id, enabled)` ([routes/warroom.py](Haven-UI/backend/routes/warroom.py)) resolves the partner→civ (enrollment `civ_id`, else discord_tag→civ tag), toggles `war_room` on the civ's `enabled_features_default`, and fans out `_recompute_profile_features` to all members; `enroll_in_war_room`/`unenroll_from_war_room` call it instead of the dead `partner_accounts.enabled_features` write. Migration **v1.94.0** ([migrations.py](Haven-UI/backend/migrations.py)): ensure active-enrollment civs keep `war_room` in their default, then re-run the role-aware + civ-scoped union for every profile with an active civ membership (tier≠1), inlined leader set (no war_room). No schema change. `/api/status` 1.85.0 → 1.86.0. Backend `--build` deploy; migration auto-runs at startup. |
| Haven-UI | 1.75.1 | 2026-06-22 | See Master Haven 1.90.0. [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx): `FEATURE_DEFAULTS` War Room relabeled "War Room (all moderators)"; comment block documents war_room as the civ-scoped exception (not by-role); both feature-grid captions note War Room applies to ALL moderators; the per-member sub-admin override grid now filters out `war_room` (it's civ-controlled) with a hint, and "Save permissions" strips `war_room` from the saved override so overrides never carry it. No gating-logic change (navbar/route already read `enabled_features`). Build clean (11.49s, 0 errors). `package.json` 1.75.0 → 1.75.1. |
| **Master Haven** | 1.89.0 | 2026-06-21 | **Filter dropdowns fully de-duplicated + collapsed options still match (case / spacing / punctuation-insensitive).** Follow-up to the resource fix: while verifying the filters still worked, the Economy-Type dropdown still showed near-dupes my 1.86.0 `_dedup_clean` (case + edge-whitespace only) missed — `Power Generation` AND `PowerGeneration` as separate entries — plus junk like `1`. **Root risk:** simply hiding `PowerGeneration` in the dropdown would make those systems **unfilterable** (the filter used exact `=`, so picking `Power Generation` wouldn't match `PowerGeneration` rows). **Fix (two-sided, shared normalizer):** new `norm_token()` in [db.py](Haven-UI/backend/db.py) (lowercase + keep only alphanumerics), registered as a SQLite function on every connection. The filter-options dedup ([routes/systems.py](Haven-UI/backend/routes/systems.py) `_dedup_clean`) now groups by `norm_token` (collapsing case **and** internal spacing/punctuation), drops single-char / pure-numeric noise (`1`), and surfaces the best-formatted variant (most word breaks → mixed case → longest). The categorical filter clauses in `_build_advanced_filter_clauses` ([db.py](Haven-UI/backend/db.py)) — `star_type`, `economy_type`, `economy_level`, `conflict_level`, `dominant_lifeform`, `stellar_classification`, `biome`, `weather`, `sentinel` — now match through `norm_token(col) = norm_token(value)` (same normalizer both sides), so a collapsed dropdown option matches **every** stored variant. **Verified** on the local DB: `economy_type` = `Power Generation` / `PowerGeneration` / `power generation` all return the **same 1084 systems** (raw DB confirms both spellings exist); dropdowns dupe-free + `1` dropped; resource, multi-select (`Yellow,Blue`), and combos still match. Backend-only (no frontend — both the Systems tab and Cartographer read the same `filter-options`); no schema/migration. `/api/status` 1.84.1 → 1.85.0. Backend restart required. |
| Backend API | 1.85.0 | 2026-06-21 | See Master Haven 1.89.0. New `norm_token(value)` in [db.py](Haven-UI/backend/db.py) (lowercase + alphanumerics-only), registered via `conn.create_function('norm_token', 1, …, deterministic=True)` (try/except fallback for old sqlite) in `get_db_connection`. `_build_advanced_filter_clauses` matches all categorical fields (`star_type`/`economy_type`/`economy_level`/`conflict_level`/`dominant_lifeform`/`stellar_classification`/`biome`/`weather`/`sentinel`) via `norm_token(col)` against `norm_token`-ed params (single `=` and multi `IN`). `get_distinct_*` dedup in [routes/systems.py](Haven-UI/backend/routes/systems.py) `_dedup_clean` rewritten to group by `norm_token` (imported from db), drop `len<2`/all-digit keys, and pick the best-formatted display per group. Read/filter-side only; no schema change. **Migration runner hardened (prompted by a parallel "war room visibility" fix that also carries a migration):** the legacy runner used a high-water-mark — `get_current_version` = last-applied version, run only migrations numbered *above* it — so any migration added at-or-below that number (a duplicate, or a lower number from a parallel branch) **silently never ran** on a DB that had already passed it. [migrations.py](Haven-UI/backend/migrations.py) now does **per-migration tracking**: a one-time `_backfill_applied_versions_once` bridges legacy DBs (records every registered version ≤ the current watermark as applied, so pre-tracking migrations don't re-run, + a `_per_migration_backfill` marker), then `run_pending_migrations` runs any migration whose version isn't in the applied set — order/number independent. `get_current_version` now returns the numerically-highest applied real version (Python tuple sort; excludes the marker). `register_migration` also raises on a **duplicate version** at import (the applied set is keyed by version, so exact dupes still need preventing). Verified end-to-end on temp DBs: bridge runs only the new `1.93.0`; a later **lower** `1.50.5` now runs; idempotent re-runs are no-ops; fresh DB runs everything. So the war-room migration is safe at **any** unique number. 93 migrations import clean. `/api/status` 1.84.1 → 1.85.0. |
| **Master Haven** | 1.88.1 | 2026-06-21 | **Fix: discovery approval (single AND batch) failing with `FOREIGN KEY constraint failed` on stale planet/moon links.** Parker batch-approved a discovery backlog (#92–#215) and every item failed `FOREIGN KEY constraint failed`. **Root cause (pre-existing, not batch-specific):** the live `discoveries` table has FKs `planet_id→planets(id)` / `moon_id→moons(id)` (and `PRAGMA foreign_keys=ON` since 1.65.0), but planet/moon rows are deleted-and-reinserted with **new ids** on every system rebuild (the planet-churn bug), so old pending discoveries hold `planet_id`/`moon_id` values that no longer exist → the approval INSERT/UPDATE aborts. Confirmed on a DB copy: rows have a valid `system_id` (stable UUID) but a **MISSING** `planet_id` (e.g. #1 planet 7620, #3 planet 3703); a raw insert reproduces the exact error. Single-approve had the same latent bug — batch just surfaced the whole backlog. **Fix** (shared helper `_apply_discovery_approval` in [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py), so single + batch both benefit): new `_resolve_discovery_links()` resolves `planet_id`/`moon_id` against live FKs before the insert/update — (1) keep ids that still exist; (2) for a dropped link, **best-effort re-link to the correct CURRENT planet/moon by matching its name inside `location_name`** (conservative `_match_body_by_name`: whole-name match bounded by non-alphanumerics, ≥3 chars, longest match wins, ties → no guess); (3) only null (approve "unlinked") when no name resolves. So a rebuilt-planet discovery lands back on the **right** planet, not orphaned. The edit-target lookup moved up front so the matcher knows the (fixed) system. `system_id` (stable UUID) left as-is. **Verified** on a DB copy: dead planet 7620→live **Usaling**, dead 3703→live **Nafut Gamma**, coords-only row→unlinked; raw dangling insert FK-fails while the guarded path succeeds; `discoveries.py` byte-compiles. Backend-only, no schema/migration/frontend change. `/api/status` 1.84.0 → 1.84.1. Backend restart required. |
| Backend API | 1.84.1 | 2026-06-21 | See Master Haven 1.88.1. New `_existing_link_id()`, `_match_body_by_name()`, `_resolve_discovery_links()` in [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py); `_apply_discovery_approval()` resolves edit target up front then calls `_resolve_discovery_links()` for both the edit UPDATE and new INSERT — keeps live ids, re-links a rebuilt planet/moon by name from `location_name`, nulls only when unrecoverable. Fixes `FOREIGN KEY constraint failed` on approval of discoveries whose planet/moon rows were rebuilt, and reassigns them to the correct current body. `/api/status` 1.84.0 → 1.84.1. Backend restart required. |
| **Master Haven** | 1.88.0 | 2026-06-21 | **Batch approve / reject for discoveries (parity with systems + region names).** Parker: "look over our batch approval functions and figure out how to add batch approval into discoveries." **Investigation:** systems have a heavyweight **async job-queue** batch (`/api/approve_systems/batch` → 202+job_id, `batch_jobs` table, frontend polls) built only because system approval is expensive (planet rebuilds, glyph decode, completeness, discovery promotion) and 100-system batches blew the 60s proxy timeout. Region names use a simpler **synchronous per-item loop**. Discovery approval is light (one insert/update + a completeness recompute) and low-volume, so it follows the **region pattern** — no job queue, no new table, no polling. **Backend** ([routes/discoveries.py](Haven-UI/backend/routes/discoveries.py)): extracted the body of `approve_discovery`/`reject_discovery` into shared `_apply_discovery_approval()` / `_apply_discovery_rejection()` helpers (open-cursor, no commit) so the single and batch paths can't drift — the single endpoints now delegate to them. New `POST /api/approve_discoveries/batch` + `POST /api/reject_discoveries/batch`: same gate as systems (`approvals` feature + `batch_approvals` for non-super-admins), per-item loop returning `{approved/rejected, failed, skipped}`, idempotency + self-submission rows **skipped not failed** (safe select-all), and each approve item wrapped in a `SAVEPOINT` so one bad row rolls back only itself. No schema change (`pending_discoveries` already has every column). **Frontend:** [DiscoveryApprovalTab.jsx](Haven-UI/src/components/approvals/DiscoveryApprovalTab.jsx) gains Batch Mode (toggle gated on `canAccess(FEATURES.BATCH_APPROVALS)`, per-card checkboxes with self-submissions disabled, select-all-eligible, batch reject-reason modal, results modal) mirroring [SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx); [PendingApprovals.jsx](Haven-UI/src/pages/PendingApprovals.jsx) now passes `canAccess` to the tab (was missing); `batchApproveDiscoveries`/`batchRejectDiscoveries` added to [api.js](Haven-UI/src/utils/api.js). **Verified:** discoveries.py byte-compiles; `npm run build` clean (13.34s, 0 errors). Backend restart + frontend rebuild required; no migration. `/api/status` 1.83.0 → 1.84.0, `package.json` 1.74.0 → 1.75.0. |
| Backend API | 1.84.0 | 2026-06-21 | See Master Haven 1.88.0. [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py): new module helpers `_resolve_account_id()`, `_apply_discovery_approval(cursor, submission, session_data)` (returns `{discovery_id,is_edit,discovery_name,discovery_type,parent_system_id}`; raises HTTPException(400) pre-write if an edit target is gone), `_apply_discovery_rejection(cursor, submission, reason, session_data)`. `approve_discovery`/`reject_discovery` refactored to call them (no behavior change). New `POST /api/approve_discoveries/batch` (per-item `SAVEPOINT`, ≤1000) + `POST /api/reject_discoveries/batch` (shared reason). Both: `require_feature('approvals')` + `batch_approvals` for non-super, skip already-reviewed + self-submissions, per-item try/except, single `conn.commit()`, one summary `add_activity_log`. No schema change/migration. `/api/status` 1.83.0 → 1.84.0. Backend restart required. |
| Haven-UI | 1.75.0 | 2026-06-21 | See Master Haven 1.88.0. [DiscoveryApprovalTab.jsx](Haven-UI/src/components/approvals/DiscoveryApprovalTab.jsx): batch state (`batchMode`/`selectedIds`/`batchInProgress`/`batchRejectModalOpen`/`batchRejectionReason`/`batchResultsModalOpen`/`batchResults`), `toggleSelection`/`selectAllEligible`/`clearSelection`/`exitBatchMode`/`handleBatchApprove`/`handleBatchReject`, a Batch Mode toggle + action bar, per-pending-card checkboxes (self-submissions disabled, selected = `ring-2 ring-indigo-400`), and batch reject + results modals (flat `{approved/rejected,failed,skipped}` shape). New `canAccess` prop. [PendingApprovals.jsx](Haven-UI/src/pages/PendingApprovals.jsx) passes `canAccess`. [api.js](Haven-UI/src/utils/api.js): `batchApproveDiscoveries(ids)` / `batchRejectDiscoveries(ids, reason)`. Build clean (13.34s, 0 errors). `package.json` 1.74.0 → 1.75.0. |
| **Master Haven** | 1.87.0 | 2026-06-21 | **Cartographer Resource filter fixed end-to-end — was reading a ~empty column (matched almost nothing), now matches the real `materials` data, with a clean canonical list + a searchable dropdown.** Parker: "the resource dropdown list is hella broken and there's no search." **Diagnosis:** the dropdown + filter used `planets.common/uncommon/rare_resource` (filled on **12 of 3,121 planets**); the real resources live in `planets.materials` (comma-joined, **2,598 planets**). So filtering "Gold" matched **1 system** vs the **258** that actually have it. And parsing `materials` raw gives a **170-entry mess** (case dupes `Copper`/`copper`, typos `Cooper`/`kupfer`/`uramium`, bad separators `Salt. Gold. Copper`, non-resources `Dissonance`). **Fix (Parker's call: normalize the data, don't drop info; reuse the Systems-tab search UX):** new [resource_catalog.py](Haven-UI/backend/resource_catalog.py) — canonical resource list (mirrors the curated [adjectives.js](Haven-UI/src/data/adjectives.js) `resourcesList`, 107 entries) + an alias map for the observed typos/variants + `normalize_materials()` that re-splits a cell (comma/period/" and "/etc), maps every recognizable token to its canonical name, and **preserves** unrecognized tokens verbatim. New **migration v1.93.0** normalizes `planets.materials` + `moons.materials` in place (idempotent; the runner snapshots the DB first) — local sim: 814 rows cleaned, re-run 0. `GET /api/systems/filter-options` now builds the resource list from normalized `materials ∩ canonical` (170 → **42 real resources**); the resource WHERE clause ([db.py](Haven-UI/backend/db.py)) matches `materials` as a comma-bounded, case-insensitive token (normalizing stray `.`/`and` separators inline; dedicated columns kept as fallback). **Frontend:** the `cf-resource` `<select>` is replaced by a **searchable combobox** (vanilla equivalent of the Systems-tab `SearchableSelect` — type to filter, ↑↓/Enter, ×-clear; hidden input carries the value so `applyFilters`/`updatePills` are unchanged). **Verified:** all backend files AST-clean, all 3 script blocks syntax-clean, end-to-end sim (migration→filter→dropdown) on a DB copy — Gold 258 / Copper 435 / Salt 357 systems, 42-item dropdown; `public`→`dist` identical. Frontend rebuild + backend `--build` deploy; migration auto-runs at startup. Also fixes the React Systems FilterModal (shares the endpoint + clause). `/api/status` 1.82.0 → 1.83.0, `package.json` 1.73.1 → 1.74.0. |
| Backend API | 1.83.0 | 2026-06-21 | See Master Haven 1.87.0. New [resource_catalog.py](Haven-UI/backend/resource_catalog.py): `CANONICAL_RESOURCES` (mirrors `adjectives.js resourcesList`), `RESOURCE_ALIASES` (typo/variant→canonical), `normalize_resource_token()` (+1-edit fallback), `normalize_materials()` (re-split, map, preserve unknowns, dedupe). Migration **v1.93.0** normalizes `planets.materials` + `moons.materials` in place (idempotent). `get_distinct_resources()` in [routes/systems.py](Haven-UI/backend/routes/systems.py) rewritten to source from normalized `materials ∩ canonical`. The `resource` clause in `_build_advanced_filter_clauses` ([db.py](Haven-UI/backend/db.py)) now matches `materials` via a comma-bounded `LIKE` (inline `.`/`and` separator normalization) with the dedicated columns as a fallback. No schema change. `/api/status` 1.82.0 → 1.83.0. Backend `--build` deploy + migration auto-runs at startup. |
| Haven-UI | 1.74.0 | 2026-06-21 | See Master Haven 1.87.0. [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html): the Resource `<select>` is replaced by a searchable combobox (`#cf-resource-combo`: hidden `#cf-resource` value + visible `#cf-resource-search` + `#cf-resource-menu`). New `initResourceCombo()` (focus opens menu, type filters, ↑↓/Enter/Esc, mousedown-select, click-outside close), `_renderResourceMenu()`, `_highlightResourceRow()`, `clearResourceFilter()`, and `_resourceOptions`/`_resourceActiveRow` state; `.cf-combo*` dark-theme CSS. `cf-resource` dropped from the `<select>` populate map; resource pill clears via `clearResourceFilter()`. `dist/VH-Cartographer.html` re-copied. `package.json` 1.73.1 → 1.74.0. |
| **Master Haven** | 1.86.0 | 2026-06-20 | **Cartographer filter polish (follow-up to 1.84.0): new Community filter, real galaxy list, Has Moons, deduped Economy Type, camera frames on galaxy switch.** Parker, after the filters started working: "we filter some things and not all the good ones like galaxy / civ tags — economy type also has repeats — has planets should be has moons." Five fixes to [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) + [routes/systems.py](Haven-UI/backend/routes/systems.py): **(1) Community (civ-tag) filter** — new `#cf-civ-tag` dropdown populated from the snapshot's `tag_pool` (drops only the empty/untagged bucket, "Personal" kept), filtered **client-side** via `S.tagIndices` (no fetch); folds into the same matched-set + pills as the other filters. **(2) Real galaxy list** — the Galaxy dropdown was 10 hardcoded options; the snapshot now returns `galaxies` (distinct, reality-scoped but NOT galaxy-scoped so the list stays complete when narrowed) and the dropdown is data-driven, preserving selection across reloads. **(3) Has Planets → Has Moons** — nearly every system has planets (useless filter); replaced with `Has Moons`, derived client-side from `planets_by_idx` (each planet tuple's moon_count) into `S.hasMoons`. **(4) Economy-type repeats** — `GET /api/systems/filter-options` now collapses case/whitespace-variant duplicates (`_dedup_clean`: trim + case-insensitive, keep first casing) across every system/planet text field, so "Trading"/"Trading "/"trading" surface once (fixes the React FilterModal too, same source). **(5) Galaxy/Reality switch now visibly applies** — `reloadSnapshot` frames the camera back to the galaxy-home view (`flyTo` origin), since per-galaxy region coords meant the old camera target pointed at empty space and the change "looked like nothing happened." Frontend (map HTML) + read-side backend; no schema/migration. **Verified:** systems.py AST-clean, all 3 script blocks syntax-clean, no stale refs, `public`→`dist` identical. Frontend rebuild + backend `--build` deploy (new snapshot fields). `/api/status` 1.81.0 → 1.82.0, `package.json` 1.72.0 → 1.73.1. |
| Backend API | 1.82.0 | 2026-06-20 | See Master Haven 1.86.0. `GET /api/map/snapshot` ([routes/systems.py](Haven-UI/backend/routes/systems.py)) adds a `galaxies` array (distinct non-empty galaxies, reality-scoped only, so the map's Galaxy dropdown stays complete even when the snapshot is narrowed to one galaxy) — added to the result + empty envelope. `GET /api/systems/filter-options` gains `_dedup_clean()` (trim + case-insensitive dedupe, keep first-seen casing) applied to every `get_distinct_system`/`get_distinct_planet` result — collapses the duplicate economy-type (and other) options SQL `DISTINCT` left split by case/whitespace. Read-only, no schema/migration. `/api/status` 1.81.0 → 1.82.0. Backend `--build` deploy required (new snapshot field). |
| Haven-UI | 1.73.1 | 2026-06-20 | See Master Haven 1.86.0. [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html): new Community `#cf-civ-tag` select (client filter via `S.tagIndices`/`tag_pool`, `_populateCivTagDropdown` preserves selection across reload, **"Personal" included** per Parker); data-driven Galaxy dropdown (`_populateGalaxyDropdown` from snapshot `galaxies`); `Has Planets`→`Has Moons` (`#cf-has-moons`, `S.hasMoons` derived from `planets_by_idx` in `parseSnapshot`); both new selects folded into `applyFilters` matched-set + `updatePills`; `reloadSnapshot` now `flyTo`-frames the galaxy-home view and repopulates the civ-tag + galaxy lists. `dist/VH-Cartographer.html` re-copied. `package.json` 1.72.0 → 1.73.1. |
| **Master Haven** | 1.85.0 | 2026-06-20 | **Trusted-member direct DB saves are now tracked for events + analytics (were invisible everywhere but the systems table and the approval log).** Parker: direct DB submissions from trusted members "just submit and [there's] nothing for the ongoing events and tracking page." Root cause: `POST /api/save_system` ([control_room_api.py](Haven-UI/backend/control_room_api.py)) — the trusted direct-save path (super admin, or partner/sub-admin with `system_create`/`system_edit`) — writes straight to the live `systems` table and skips the `pending_systems` queue. On the tracking side it only wrote an `approval_audit_log` row (`direct_add`/`direct_edit`); it **never** set `event_id` on the system (the wizard's EventPicker already sends it — the backend just dropped it) and **never** created a `pending_systems` row or an `activity_logs` entry. But events count `FROM systems WHERE event_id` and the entire analytics layer (submission leaderboard, community-stats, submissions-timeline, partner-overview) + the public contributors list + public activity-timeline all derive `FROM pending_systems` — so a trusted member's upload counted toward **none** of them. **Decisions (Parker):** model a direct save as "submitted AND approved in one step" → write a **pre-approved `pending_systems` mirror row** (so every analytics query works unchanged, no rewrites); mirror **both** new saves AND edits (parity with the public queue where each approved submission is a row); and **backfill** historical direct saves. **Fix (backend only — the frontend already sends `event_id`):** (1) `save_system` resolves `event_id` via the existing `resolve_submission_event_id(...)` and writes it onto the `systems` row (INSERT + `COALESCE` UPDATE so an edit can't wipe a link) → direct saves now count toward live events. (2) In the same transaction it writes a `status='approved'`, self-reviewed `pending_systems` row (`source='manual'`, `api_key_name='direct_save'` marker, `edit_system_id` back-link, `username_normalized`, `discord_tag`, `event_id`, full `system_data`) and calls `add_activity_log('system_approved', …)` so it shows in the Dashboard feed. The mirror row never appears in the pending queue (filters `status='pending'`) and `find_matching_pending_system` ignores it (filters `status='pending'`), so no false duplicate warnings. (3) New migration **v1.92.0** backfills one mirror row per historical direct-saved system, identified precisely from `approval_audit_log` `direct_add`/`direct_edit` rows (so a queue-approved system is never mistaken for a direct save → no double-count); idempotent (`api_key_name='direct_save'` guard). **Verified** against the local DB: forward INSERT fires the glyph-suffix trigger + stores approved/manual/normalized cleanly; backfill created 199 mirror rows and a re-run created 0 more. Backend `--build` deploy + migration auto-runs at startup. `/api/status` 1.80.0 → 1.81.0; no frontend change. |
| Backend API | 1.81.0 | 2026-06-20 | See Master Haven 1.85.0. `save_system` ([control_room_api.py](Haven-UI/backend/control_room_api.py)) now: imports `resolve_submission_event_id` (from [services/events.py](Haven-UI/backend/services/events.py)) and resolves `event_id` from the payload; adds `event_id` to the systems INSERT and `event_id = COALESCE(?, event_id)` to the systems UPDATE; writes a pre-approved `pending_systems` mirror row (`status='approved'`, `reviewed_by`=self, `source='manual'`, `api_key_name='direct_save'`, `edit_system_id`=live system id back-link, `username_normalized` via `normalize_username_for_dedup`, full `system_data`, `event_id`) in the same transaction for **both** create and edit; and calls `add_activity_log('system_approved', …)`. New migration **v1.92.0** ([migrations.py](Haven-UI/backend/migrations.py)) backfills mirror rows for historical direct-saved systems (candidate set from `approval_audit_log` `direct_add`/`direct_edit` notes → system_id; attribution from the live `systems` row; one row per system; idempotent on `api_key_name='direct_save'`). Read/write-side change to one endpoint + one migration; no schema change. `/api/status` 1.80.0 → 1.81.0. Backend `--build` deploy required; migration auto-runs at startup. |
| **Master Haven** | 1.84.0 | 2026-06-20 | **Cartographer left-sidebar filters now actually work — they hide non-matching systems AND regions, and the Reality/Galaxy controls re-scope the map.** Parker: "on the cartography page the filter on the left does not work at all — nothing filters and nothing gets hidden." Root cause was architectural, not a broken handler: the [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) sidebar's `applyFilters` only recolored the **system** star cloud (`S.starPoints`), but the map is a zoom-LOD crossfade — at the default galaxy view (`radius 4400` ≫ the `CROSSFADE_MAX 345` cutoff) the system layer renders at `opacity 0` and only the **region** centroid dot cloud is visible, which the filter never touched. So the filter modified an invisible layer → zero visible effect until you zoomed all the way in. It also ignored the region-mask/label-dim machinery the civ/contributor **territory focus** filter (`applyFocusFilter`) already had 30 lines above it, and its Reality/Galaxy controls were dead (read by nothing). **Fix (reuse-first, per Parker's decisions = hide both layers + wire reality/galaxy):** (1) one unified matched-system set feeds **both** layers — systems hidden via color `(0,0,0)` (additive blending → truly invisible, not the old `0.05` dim), regions hidden via the same `applyFocusFilter` painter, now composing the attribute mask (hard hide) with the territory-focus mask (its existing `0.06` ghost). A region is hidden iff **none** of its systems match, so a hidden region's systems are hidden too (Parker's explicit ask). (2) New per-system **region index** added to `/api/map/snapshot` (`ri`, Uint16 → `S.systemRegionIdx`) so a matched system maps to its region for region-layer hiding (guarded: older snapshots without `ri` degrade to system-only hide, never "hide everything"). (3) The system-hide is re-applied at the tail of `updateColorMode` so color-mode switches preserve it. (4) **Reality + Galaxy wired properly** — "All" added to both, changing either calls a new `reloadSnapshot()` that tears down + disposes the star/region/grid clouds, refetches `/api/map/snapshot?reality=&galaxy=` (endpoint already supported the params), rebuilds, and re-applies the active filter; the attribute fetch also passes the active scope. (5) A "**N systems match**" pill gives feedback even when matches are off-screen. Removed the dead `_applyColorOverlay`/`resetStarColors`. **Verified:** all 3 script blocks pass JS syntax check; backend AST-clean; `public` copied to `dist` (identical). Frontend rebuild + backend `--build` deploy required (snapshot `ri` field is new). `/api/status` 1.79.0 → 1.80.0, `package.json` 1.71.0 → 1.72.0. |
| Backend API | 1.80.0 | 2026-06-20 | See Master Haven 1.84.0. `GET /api/map/snapshot` ([routes/systems.py](Haven-UI/backend/routes/systems.py)) now emits a per-system **region index** array `ri` (base64 little-endian Uint16, aligned to the per-system arrays, valued by position in the `regions` pool; `65535` = system with no region). Built by capturing each system's `(region_x,region_y,region_z)` during the row walk, then mapping through a `region_key→pool_index` dict after the region aggregation. Added to the result payload and the empty-DB envelope. Lets the Cartographer derive which regions contain a filter match (for region-layer hiding). Read-only, no schema/migration; cache key unchanged (already keyed on reality/galaxy/token). `/api/status` 1.79.0 → 1.80.0. Backend `--build` deploy required so the running image serves the new field. |
| Haven-UI | 1.72.0 | 2026-06-20 | See Master Haven 1.84.0. [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) filter core rewritten: `applyFilters` builds one matched-system `Set` (server `/api/systems`+`/api/systems/search` results intersected with client star-type/has-station/has-planets predicates), `_setMatched` derives `_matchingRegions`/`_matchingRegionKeys` via the new `S.systemRegionIdx` and repaints both layers through one choke point; `_applySystemFilterHide` (true-hide `(0,0,0)`) runs at the tail of `updateColorMode`; `applyFocusFilter` now composes the attribute mask (hide) with the territory-focus mask (ghost) for dots **and** labels. New `decodeU16`, `S.systemRegionIdx` decode in `parseSnapshot`, `_scopeReality`/`_scopeGalaxy` + `_snapshotScopeQuery`, `reloadSnapshot`/`_teardownClouds`/`showBoot`, dedicated Reality(pills, +All)/Galaxy(select, +All Galaxies) listeners (excluded from the generic attribute-filter handlers), and a `N systems match` pill (`.carto-pill.count`). Removed `_applyColorOverlay` + `resetStarColors`. `dist/VH-Cartographer.html` re-copied from `public`. `package.json` 1.71.0 → 1.72.0. |
| **Master Haven** | 1.83.0 | 2026-06-20 | **Sub-admin membership cleanup — retired the legacy username+password sub-admin creation; the Sub-Admins page is now a moderation panel over the civ system.** Parker: the old "Access Control → Sub-Admins" page still let you mint a sub-admin by username+password into the legacy `sub_admin_accounts` table — a split-brain path that login silently shadows (login resolves `user_profiles` by normalized username **first**, so anyone who'd ever submitted got their tier-4 member profile and never reached the `sub_admin_accounts` fallback → the account was dead on arrival, invisible in Civilization Management, with no `profile_id`). Sub-admins have been `civilization_members` rows (role `sub_admin`) since migration 1.80.0; the legacy create flow was a dead-end. **Decisions (Parker):** remove the manual create; require an **existing profile** to elevate; turn the page into a moderation surface where permissions/features can be added/removed/changed. **Backend:** `GET /api/sub_admins` ([routes/partners.py](Haven-UI/backend/routes/partners.py)) repurposed from a `sub_admin_accounts` CRUD list into a **roster** over `civilization_members JOIN user_profiles JOIN civilizations` (role=`sub_admin`), returning each member's civ + effective features (override-vs-civ-default) + personal-upload cap; scoped to all civs for super admin, to led civs for a leader/co_leader, empty otherwise. The four legacy `sub_admin_accounts` writers (`POST/PUT/DELETE /api/sub_admins`, `POST .../reset_password`) were **removed**. New `_require_civ_manage_access(civ_id)` in [routes/civilizations.py](Haven-UI/backend/routes/civilizations.py) replaces `_require_super_admin` on `add_member`/`update_member`/`remove_member` so a civ's own **leaders/co-leaders** can moderate their sub-admins (super admin still manages any civ) — restoring the partner self-management the old page had. **Frontend:** [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx) rewritten — roster grouped by civ, per-member feature editor (override + reset-to-civ-default), personal-upload toggle, **Revoke**, and **Add Sub-Admin** via username lookup (`/api/profiles/lookup`, existing-profile-only) + civ select → `POST /api/civilizations/{id}/members` role `sub_admin`. No username/password/reset UI. A banner points leader/co-leader management at Civilization Management. The legacy login fallback for any pre-existing `sub_admin_accounts` rows is untouched (so nobody is locked out); stranded legacy rows aren't auto-migrated — re-elevate via the new flow if needed. Frontend build clean (12.23s, 0 errors); both backend files byte-compile. Frontend rebuild + backend restart required. `/api/status` 1.78.0 → 1.79.0, `package.json` 1.70.0 → 1.71.0. |
| Backend API | 1.79.0 | 2026-06-20 | See Master Haven 1.83.0. `GET /api/sub_admins` ([routes/partners.py](Haven-UI/backend/routes/partners.py)) now returns a sub-admin **roster** from `civilization_members` (role=`sub_admin`) joined to `user_profiles` + `civilizations` — fields: civ tag/name, effective `enabled_features`, raw `enabled_features_override` (null = inheriting), `civ_default_features`, `can_approve_personal_uploads`, last login; super admin sees all (optional `?civ_id`), leader/co_leader sees only led civs. Removed the legacy `sub_admin_accounts` writers `POST/PUT/DELETE /api/sub_admins` + `POST /api/sub_admins/{id}/reset_password`. New `_require_civ_manage_access(session, civ_id)` ([routes/civilizations.py](Haven-UI/backend/routes/civilizations.py)) — super admin OR a leader/co_leader of that civ (read from session memberships, no DB hit) — now gates `add_member`/`update_member`/`remove_member` (was super-admin-only). Read/permission-side only; no schema change, no migration. `/api/status` 1.78.0 → 1.79.0. Backend restart required. |
| Haven-UI | 1.71.0 | 2026-06-20 | See Master Haven 1.83.0. [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx) fully rewritten from a `sub_admin_accounts` create/edit page into a moderation panel backed by the civ system: loads `GET /api/sub_admins` (roster) + `GET /api/civilizations` (elevation targets), groups sub-admins by civ, and per member exposes a feature editor (per-member override with **Save permissions** / **Reset to civ default**), an **Approve personal** toggle, and **Revoke** — all via `PUT`/`DELETE /api/civilizations/{civ_id}/members/{profile_id}`. **Add Sub-Admin** elevates an existing profile only (`/api/profiles/lookup` → `POST /api/civilizations/{id}/members` role `sub_admin`); no account/password creation. [AccessControl.jsx](Haven-UI/src/pages/AccessControl.jsx) Sub-Admins tab description updated. `package.json` 1.70.0 → 1.71.0. |
| **Master Haven** | 1.82.0 | 2026-06-20 | **New "Find Glyph by Name" tool — reverse-resolve a system name to its 12-glyph portal code.** Productionizes the standalone `glyphtool` resolver Parker wanted easier to use. New public page [GlyphFinder.jsx](Haven-UI/src/pages/GlyphFinder.jsx) at `/glyph-finder` (top-nav "Glyph Finder" link) backed by new `GET /api/glyph/resolve` ([routes/systems.py](Haven-UI/backend/routes/systems.py)). Resolves the name against Haven's uploaded systems **server-side from the local DB** — instant, none of the public-API round-trips the standalone tool made. Returns each match's stored glyph code with decoded SSI/region, the actual glyph art (reuses [GlyphDisplay.jsx](Haven-UI/src/components/GlyphDisplay.jsx)), a copy-code button, a link to the system, and a **confidence** (high = 1 match / medium = 2-5 / low = >5 — NMS procgen names repeat, so one name can map to many systems; all candidates shown with galaxy + region to disambiguate). Optional galaxy/reality filters narrow repeats; no exact match falls back to fuzzy "did you mean" suggestions. Honors `archived_civ_filter` (non-super-admins) + `apply_data_restrictions`, exactly like the search endpoint. **Verified in-process against the local DB (13,609 systems):** exact→high (`Oculi`→`20720193DFA9`, SSI/planet decoded, grade S), ambiguous→low (11× `Jinoomo-Iryun XIX`, each with distinct glyph/region), 2-char short-guard, and fuzzy suggestions on a partial. Frontend + read-only backend; **no schema change, no migration.** Frontend rebuild + backend restart required. `/api/status` 1.77.1 → 1.78.0, `package.json` 1.69.0 → 1.70.0. |
| Backend API | 1.78.0 | 2026-06-20 | See Master Haven 1.82.0. New `GET /api/glyph/resolve?name=&galaxy=&reality=` in [routes/systems.py](Haven-UI/backend/routes/systems.py): exact name match (`COLLATE NOCASE`) over `systems` (optional galaxy/reality scoping), dedupes by `glyph_code`, decodes planet/SSI/region from the 12-char code via new module-level `_decode_glyph_parts()` (the same validated bit-packing the standalone `glyphtool` uses), returns candidates with `completeness_grade` (via `score_to_grade`) + a confidence tier, and fuzzy name-LIKE suggestions when count == 0. Applies `archived_civ_filter('s')` for non-super-admins + `apply_data_restrictions`. Read-only — no schema/migration. `/api/status` 1.77.1 → 1.78.0. Backend restart required. |
| Haven-UI | 1.70.0 | 2026-06-20 | See Master Haven 1.82.0. New public page [GlyphFinder.jsx](Haven-UI/src/pages/GlyphFinder.jsx) at `/glyph-finder` — name input + optional galaxy/reality selects, confidence banner, candidate cards rendering `GlyphDisplay` glyph art + copy-code + "View system →", and a fuzzy-suggestions fallback on no exact match (all using the 2.0 `.haven-card`/`.haven-btn-*`/`.pill`/`.grade-*` utilities). New `resolveGlyphByName` helper in [api.js](Haven-UI/src/utils/api.js); lazy route in [App.jsx](Haven-UI/src/App.jsx); "Glyph Finder" top-level entry in [Navbar.jsx](Haven-UI/src/components/Navbar.jsx) `NAV_LINKS` (desktop + mobile from the one source). Build clean (11.73s, 0 errors); `GlyphFinder` chunk emitted. `package.json` 1.69.0 → 1.70.0. |
| **Master Haven** | 1.81.1 | 2026-06-19 | **Fix: the fully-charted Mabaya showed S, not S+, everywhere except its own detail page — and ZERO systems were flagged S+ across all of prod.** Parker: on `/systems/Mabaya` the disambiguation picker showed both Mabayas as S; the second (the 64-discovery showcase, system `5547c89d`) should be S+. **Diagnosis:** two grade code paths had diverged. The **live** path (system detail header + disambiguation picker, via `calculate_completeness_score`) already returned **S+** correctly — the deployed API confirmed it. But the **cached** path (systems list / search / galaxy grade bars / 3D map / cards / posters, via the `systems.is_fully_charted` column) returned **S**, because that column was `0`. Root cause: migration **1.90.0** re-scored every system and ran the S+ checklist while the showcase Mabaya's discoveries were still **orphaned** (planet_id pointing at deleted planet rows — the recurring "Mabaya planet tags wiped" bug); the 1.79.0 one-off prod relink then fixed `discoveries.planet_id` but **never re-ran `update_completeness_score`**, leaving `is_fully_charted=0` stuck. Net: **0 of 14,137 systems were flagged S+** despite 7,738 in the S band — the S+ tier was effectively dormant. **Fix (durable):** **(1)** `approve_discovery` ([routes/discoveries.py](Haven-UI/backend/routes/discoveries.py)) now recomputes the parent system's completeness after the live discovery insert/EDIT (a discovery's planet/moon link is a primary S+ input that previously never refreshed the parent's cached grade). **(2)** New repair migration **v1.91.0** ([migrations.py](Haven-UI/backend/migrations.py)) re-scores every system (idempotent, reuses `update_completeness_score`) to flip drifted `is_fully_charted` flags — the same proven pass 1.90.0 used. The two planet-rebuild paths (`save_system`, batch-approve) already recompute after `relink_discoveries_after_rebuild`, so no change there. **Verified** against a live prod snapshot: the live scorer returns score 100 / **grade S+ / fully_charted=True** for the showcase Mabaya and S / False for the mining one. **Backend restart required**; migration v1.91.0 auto-runs at startup and lights up every genuinely fully-charted system. `/api/status` 1.77.0 → 1.77.1. |
| Backend API | 1.77.1 | 2026-06-19 | See Master Haven 1.81.1. `approve_discovery` ([routes/discoveries.py](Haven-UI/backend/routes/discoveries.py)) imports `update_completeness_score` and recomputes the parent system's cached completeness/`is_fully_charted` after the discovery insert/EDIT (EDIT reads the live row's preserved `system_id`; INSERT uses `discovery_data['system_id']`) — closes the gap where approving a discovery could satisfy the S+ "discovery on every body" rule without ever refreshing the cached grade the list/map/search read. New migration **v1.91.0** ([migrations.py](Haven-UI/backend/migrations.py)) re-scores all systems to repair stale `is_fully_charted` drift left by the 1.79.0 one-off relink (1.90.0 had scored Mabaya while its discoveries were orphaned). Idempotent; reuses the live scorer. `/api/status` 1.77.0 → 1.77.1. Backend restart required. |
| **Master Haven** | 1.81.0 | 2026-06-19 | **System cards + system detail header now show the actual NMS portal glyphs under the hex code.** Parker: on the Systems-tab card we only displayed the 12-char hex glyph string and "people don't understand the hex fully" — they wanted the real glyph symbols. Pure frontend, pure reuse: dropped the existing [GlyphDisplay.jsx](Haven-UI/src/components/GlyphDisplay.jsx) component (already used in the approval tab, backed by the single-source [glyphAssets.js](Haven-UI/src/utils/glyphAssets.js) whose 16 webp glyphs are Vite-inlined as data URIs) onto **(1)** the [SystemsList.jsx](Haven-UI/src/components/SystemsList.jsx) `SystemCard` body — a `size="small"` 12-glyph row between the planet/lifeform stats and the footer — and **(2)** the [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) hero header, under the `glyph · class · discovered by` subtitle. Both gated on a present `glyph_code` (GlyphDisplay already falls back to plain text for missing/non-12-char codes, so legacy rows degrade cleanly). Table view left as hex (column too narrow for 12 tiles). **No backend/data/schema/migration change** — `glyph_code` is already in the `/api/systems` + system-detail payloads, and the glyph art is bundled. Frontend rebuild only (no backend restart). `package.json` 1.68.0 → 1.69.0. |
| Haven-UI | 1.69.0 | 2026-06-19 | See Master Haven 1.81.0. Visual glyph row added under the hex on system cards and the system detail header by reusing `GlyphDisplay`. [SystemsList.jsx](Haven-UI/src/components/SystemsList.jsx): import `GlyphDisplay`, render `<GlyphDisplay glyphCode={s.glyph_code} size="small" />` in the `SystemCard` body (above the completeness/discoverer footer) when `s.glyph_code` is set. [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx): import `GlyphDisplay`, render the same `size="small"` row in a `mt-2` div directly under the mono `glyph_code · stellar_classification · discovered by` subtitle when `system.glyph_code` is set. Build clean (13.08s, 0 errors). `package.json` 1.68.0 → 1.69.0. |
| **Master Haven** | 1.80.0 | 2026-06-19 | **Events are now globally opt-in — anyone can enter the hosting civ's event, regardless of which civ they upload under.** Parker: the Events page is "kinda broken" during a live event — people had to *upload as the hosting civ* to participate, and Raven Storm Clan discoveries approved today never counted. Root cause: the v1.77.0 rebuild locked event participation to the hosting community at **intake** in three places, while the leaderboard already counts community-agnostically (`WHERE event_id = ?`). **(1)** `services/events.py::resolve_submission_event_id()` dropped any `event_id` whose submission `discord_tag` != the event's hosting tag — block removed (keeps the real guards: exists, active, in-window, type-accepts-kind). **(2)** `GET /api/events/active` no longer auto-scopes the picker feed to the caller's civ / passed tag — returns ALL active in-window events (`discord_tag` kept as an optional filter, not a gate). **(3) Frontend [EventPicker.jsx](Haven-UI/src/components/wizard/EventPicker.jsx)** no longer hides under Personal/blank or scopes to the chosen community — it lists every active event for the kind for everyone, in the Wizard + DiscoverySubmitModal Identity sections, and labels each option with its hosting civ so cross-civ events are distinguishable. **Backfill (Part B):** new preview-by-default [scripts/backfill_event_discoveries.py](scripts/backfill_event_discoveries.py) stamps `event_id` onto the already-approved Raven Storm discoveries (tag + window match; backs up the DB and runs in one transaction on `--commit`) — **run on the Pi prod DB pending Parker's event id + preview review.** Frontend build clean; backend parses clean. Frontend rebuild + backend restart required. `/api/status` 1.76.1 → 1.77.0, `package.json` 1.67.1 → 1.68.0. |
| Backend API | 1.77.0 | 2026-06-19 | See Master Haven 1.80.0. `services/events.py::resolve_submission_event_id()` drops the community-match gate (`discord_tag != event.discord_tag → None`) so event participation is global opt-in (signature keeps `discord_tag` for compat; no longer a filter). `GET /api/events/active` ([routes/events.py](Haven-UI/backend/routes/events.py)) drops the caller-civ auto-scoping — returns every active in-window event for the kind; `discord_tag` is now an optional filter only. Read/intake-side only — no schema change, no migration. `/api/status` 1.76.1 → 1.77.0. Backend restart required. |
| Haven-UI | 1.68.0 | 2026-06-19 | See Master Haven 1.80.0. [EventPicker.jsx](Haven-UI/src/components/wizard/EventPicker.jsx): removed the `!discordTag/personal` early-return + community-scoped fetch — now calls `getActiveEvents({ kind })` and lists all active in-window events for everyone; option labels + selected chip show the hosting `discord_tag`. The ignored `discordTag` prop dropped at both call sites ([Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) SectionIdentity, [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx)). `package.json` 1.67.1 → 1.68.0. |
| **Master Haven** | 1.79.1 | 2026-06-19 | **Fix: clicking a search result opened the "choose which system" disambiguation page.** Regression from the 1.78.0 Pretty-URLs feature: every system link navigated to `/systems/<name>`, but NMS procgen system names repeat constantly, so the backend's name lookup returned its **HTTP 300** disambiguation list — and the user got the picker even though they'd already clicked one specific result. Two-part fix. **(1) Frontend:** all 8 "user picked a specific system" navigation sites now route by **id** (`/systems/<uuid>`, which resolves to exactly one system, no 300) instead of by name — SearchOverlay, SystemsList, Search, RegionDetail, CommunityDetail, Profile, DiscoverySubmitModal's location link, and the Wizard success screen. **(2) Backend + SystemDetail:** `GET /api/systems/{id}` now returns a `name_unique` boolean (one indexed `COUNT(*) … WHERE name = ? COLLATE NOCASE`); SystemDetail only rewrites the address bar to the pretty `/systems/<name>` when `name_unique` is true. For a non-unique name it keeps the id URL, so a refresh/share of a duplicate-named system stays on that exact system instead of bouncing to the picker. Pretty URLs still apply for unique names (the common case). Frontend rebuild + backend restart required. `/api/status` 1.76.0 → 1.76.1, `package.json` 1.67.0 → 1.67.1. |
| Backend API | 1.76.1 | 2026-06-19 | See Master Haven 1.79.1. `GET /api/systems/{system_id}` adds a `name_unique` boolean to the response (`COUNT(*) FROM systems WHERE name = ? COLLATE NOCASE <= 1`) so SystemDetail can decide whether to prettify the URL to `/systems/<name>` or keep the unambiguous id URL. `/api/status` 1.76.0 → 1.76.1. |
| Haven-UI | 1.67.1 | 2026-06-19 | See Master Haven 1.79.1. All specific-system navigation routes by id, not name (SearchOverlay, SystemsList, Search, RegionDetail, CommunityDetail, Profile, DiscoveryDetailModal, Wizard success) — fixes search-result clicks landing on the 300 disambiguation picker. SystemDetail's `replaceState` pretty-URL rewrite now gated on the backend's `name_unique` flag. `package.json` 1.67.0 → 1.67.1. |
| Backend API | 1.76.0 | 2026-06-19 | See Master Haven 1.79.0. **Discovery links now survive planet rebuilds.** New shared `snapshot_child_name_maps()` + `relink_discoveries_after_rebuild()` in [db.py](Haven-UI/backend/db.py): capture planet/moon `name→id` BEFORE a delete-and-reinsert, then re-point `discoveries.planet_id`/`moon_id` to the new ids by name afterward. Wired into the two delete-and-reinsert paths that churned planet ids and orphaned discoveries — `save_system` ([control_room_api.py](Haven-UI/backend/control_room_api.py), admin direct-save) and the batch-approve edit path ([routes/approvals.py](Haven-UI/backend/routes/approvals.py)). `/api/status` 1.75.0 → 1.76.0. Backend restart required. |
| **Master Haven** | 1.79.0 | 2026-06-19 | **Fix the recurring "Mabaya planet tags wiped" bug — discoveries orphaned on every system edit.** Mabaya (Ekimo's 64-discovery showcase, system `5547c89d`) lost all its discovery→planet links again: every discovery rendered under "✦ In space." Root cause (confirmed): the admin direct-save path `POST /api/save_system` does `DELETE FROM planets WHERE system_id=?` then re-inserts all planets with **brand-new database ids** ([control_room_api.py:2808](Haven-UI/backend/control_room_api.py)), but never re-pointed the existing `discoveries.planet_id` rows — so a logged-in admin clicking **Save** in the wizard silently orphaned all 64 discoveries (the system's `last_updated_at` was a direct save 10 min after the last pending approval, matching the report). The batch-approve edit path had the identical gap. This is the same bug class as the 06-18 incident (that time via an empty-edit approval). **Data fix:** the 64 discoveries weren't lost (still `approved`, ids 68–142) — re-pointed each from its dead planet id (35149–35154) to the current planet of the same name (36524–36529) using the verbatim `pending_systems` snapshot (id 9835); 64/64 mapped cleanly, 0 orphaned after. **Code fix:** new `snapshot_child_name_maps()`/`relink_discoveries_after_rebuild()` helpers re-link discoveries by name across both delete-and-reinsert paths (`save_system` + batch approve); the single-approve path already merges planets by name and preserves ids, so it was left as-is. Helper verified with an end-to-end simulation (planet relink, trailing-space tolerance, moon relink, other-system rows untouched, zero orphans). Backend-only; no schema change, no migration. **Backend restart required.** Durable follow-up: add the same guard to any future planet-rebuild path. |
| Backend API | 1.75.0 | 2026-06-19 | See Master Haven 1.78.0. `GET /api/systems/{system_id}` now resolves by id **or** name (case-insensitive, `COLLATE NOCASE`): tries `WHERE id = ?` first (old numeric bookmarks keep working), then `WHERE name = ?`; a name shared by >1 system returns **HTTP 300** `{multiple:true, systems:[{id,name,galaxy,reality,glyph_code,discord_tag,completeness_grade}]}` for frontend disambiguation. The system-detail discoveries SELECT gained `evidence_url`, `photo_url`, `is_featured`, and a per-row `type_info` (emoji/label) so the discovery modal renders without a client-side lookup. `/api/status` 1.74.2 → 1.75.0. |
| Haven-UI | 1.67.0 | 2026-06-19 | See Master Haven 1.78.0. **Pretty system URLs** — all system navigation (SystemsList, SearchOverlay, Search, RegionDetail, CommunityDetail, Profile, Wizard success screen, DiscoveryDetailModal location link) now routes to `/systems/<name>` instead of `/systems/<id>`; SystemDetail rewrites old numeric-id URLs to the clean name via `window.history.replaceState`, and renders a disambiguation picker on the backend's 300. **Discovery modal on SystemDetail** — discovery chips open `DiscoveryDetailModal` in place (URL-synced via `?discovery=<id>`, deep-linkable) instead of routing away to the type page. `package.json` 1.66.4 → 1.67.0. |
| **Master Haven** | 1.78.0 | 2026-06-19 | **Pretty system URLs + clickable discovery links on SystemDetail.** Two UX features. **(1) Pretty URLs:** systems are now linked by name (`/systems/Mabaya`) everywhere instead of numeric IDs. `GET /api/systems/{system_id}` resolves id-first (old `/systems/1234` bookmarks still work) then falls back to a case-insensitive name lookup; duplicate names return HTTP 300 with a candidate list that SystemDetail renders as a picker (each card loads the specific system by id, which then `replaceState`s to the clean name). All 8 frontend navigation sites + the discovery modal's system link now use `encodeURIComponent(name)`. **(2) Discovery links:** discovery chips on SystemDetail open the full `DiscoveryDetailModal` inline (URL-synced `?discovery=<id>` so it's deep-linkable/shareable) instead of navigating to the discovery-type page; the backend system-detail discoveries payload gained `evidence_url`/`photo_url`/`is_featured`/`type_info` so the modal renders complete. Frontend + read-side backend only — no schema change, no migration. Backend restart required for the new read fields. |
| Backend API | 1.74.2 | 2026-06-19 | See Haven-UI 1.66.4. New `star_category` field in `/api/glyph/decode` response. `/api/status` 1.74.1 → 1.74.2. |
| Haven-UI | 1.66.4 | 2026-06-19 | Add star category badge (YRGB/Purple/Glass/Phantom) to GlyphPicker decoded coordinates popup. |
| **Master Haven** | 1.77.1 | 2026-06-19 | **Phantom star detection fix — Purple (SSI 1001-1065) and Shadow (SSI 1000) stars no longer falsely flagged.** The Wizard's glyph decoder used a simple threshold (`solar_system_index >= 600`) which incorrectly flagged all Purple stars and the Shadow star as phantoms. Replaced with range-based validation: SSI 1-767 (YRGB), 1000 (Shadow/Glass), 1001-1065 (Purple/Atlantid Drive) are valid; SSI 0, 768-999 (phantom gap), and 1066+ are phantom. Backend-only fix in `glyph_decoder.py`; no frontend change needed (GlyphPicker.jsx reads the backend's `is_phantom` flag). Requires backend restart on the Pi. |
| Backend API | 1.74.1 | 2026-06-19 | See Haven-UI 1.66.3. Phantom star SSI range fix in glyph_decoder.py. `/api/status` 1.74.0 → 1.74.1 in routes/auth.py. |
| Haven-UI | 1.66.3 | 2026-06-19 | **Fix phantom star detection for Purple and Shadow stars.** `is_phantom_star()` in glyph_decoder.py replaced simple `>=600` threshold with range-based SSI validation: 1–767 valid (YRGB), 1000 valid (Shadow/Glass), 1001–1065 valid (Purple/Atlantid Drive), everything else phantom. Fixes false "PHANTOM" warnings on Purple star system uploads in the Wizard. `package.json` 1.66.2 → 1.66.3. |
| Haven-UI | 1.66.2 | 2026-06-19 | **Completeness breakdown: expandable per-category detail + zero = neutral grey (not red).** Primarily two SystemDetail completeness-breakdown UI tweaks, but the same commit (`7640051`) also touched the backend — 7 backend files changed and the backend version bumped 1.73.0 → 1.74.0 (see the Backend API 1.74.0 row). (1) Each category row in `CompletenessBreakdown` ([SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx)) is now a `<details>`/`<summary>` that expands to the backend per-field detail: flat categories (`system_core`/`system_extra`/`planet_coverage`/`space_station`) list `{name, value, status}` rows; planet-grouped categories (`planet_environment`/`planet_life`) render each planet as a sub-header with `filled/total` and its fields indented. New `CompletenessField` helper + `COMPLETENESS_STATUS` map render `filled`→green ✓ + value, `missing`→red ✕ + "Missing", `skipped`→muted – + "N/A" (dead-biome fauna/flora). Compact `text-[11px]`, mobile-first; rotating ▶ caret via `group-open:rotate-90`. (2) **Zero-score categories now render grey (`#6b7280`)** for both bar + score text instead of red — Parker: the red Space Station bar "seems derogatory" when a system simply hasn't had a station uploaded yet. Red (`#f87171`) is now reserved for 1-39% (has SOME data but little); 0% = "not filled in yet" = neutral. Built + 3 map HTML files re-copied to `dist/`. `package.json` 1.66.1 → 1.66.2. |
| Backend API | 1.74.0 | 2026-06-19 | See Haven-UI 1.66.2. Backend version bumped 1.73.0 → 1.74.0 in routes/auth.py. |
| Haven-UI | 1.66.1 | 2026-06-19 | **Fix: SystemDetail completeness breakdown bars rendered empty (data-shape mismatch).** Backend `services/completeness.py` returns `breakdown.<category>` as a **raw number** (e.g. `system_core: 35`), but `CompletenessBreakdown` in [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) read `cat.score`/`cat.max` off it — both `undefined`, so pct=0 and every bar was empty. Three-part fix, **frontend only** (backend shape is correct, untouched): (1) `COMPLETENESS_CATEGORIES` now carries the max weight as a third tuple element (`['system_core','System Core',35]`, …) sourced from the backend caps (35/10/10/25/15/5 = 100); render computes `pct = catScore/max`. (2) Falsy guard `if (!cat)` → `if (catScore == null)` so a category scoring exactly **0** renders an empty bar instead of vanishing. (3) Removed the phantom `['planet_detail','Planet Detail']` category — the backend never returns a `planet_detail` key. Also confirmed S+ (diamond cyan `#22d3ee`) is present in both map grade scales ([VH-System-View.html](Haven-UI/public/VH-System-View.html) `TIER_COLORS`/`getGradeStyle`, [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) `cf-grade` pills) — no change needed. Built + map HTML re-copied to `dist/`. `package.json` 1.66.0 → 1.66.1. |
| **Master Haven** | 1.77.0 | 2026-06-18 | **Events rebuilt into real, opt-in, public competitions (was a tag+date slice of the firehose).** Parker: the Events page "seems very broken." Diagnosis: an "event" stored only `(name, discord_tag, start, end)` and the leaderboard sliced ALL of a community's `pending_systems`/`discoveries` by tag+date — no link between a submission and an event, so events couldn't overlap, nobody opted in, pending/rejected rows inflated counts, the page was admin-only (the people competing couldn't see it), and the `combined` tab double-counted users (submissions normalized the `#1234` discriminator, discoveries didn't). Decisions (Parker): **real participation via `event_id`**, **public-facing**, **approved-only scoring**, opt-in = **pick an event at submit time** (mirrors `expedition_id`), on **web wizard (systems) + discovery** paths (NOT the in-game extractor). **Model:** migration **v1.89.0** adds nullable `event_id` to `pending_systems`, `systems`, `pending_discoveries`, `discoveries` (+ indexes; no backfill). New `services/events.py::resolve_submission_event_id()` validates a chosen event (exists, active, in window, community match, type accepts the kind) at every intake — a bad/expired pick is silently dropped, never 400s the upload. **Threaded through** ([routes/approvals.py](Haven-UI/backend/routes/approvals.py) submit_system + both approve_system paths + both batch paths + `_promote_draft_discoveries` so co-submitted discoveries inherit the system's event; [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py) submit_discovery + create_discovery intake, approve_discovery carry-to-live). **Scoring rewrite** ([routes/events.py](Haven-UI/backend/routes/events.py)): leaderboard + card counts now count APPROVED rows from `systems`/`discoveries` `WHERE event_id = ?`, with one shared username normalization on both sides (fixes the combined double-count); the `list_events` cross-community leak (tag-less admin saw everything) is closed by scoping to `civ_tags`; new `GET /api/events/active` (picker feed) + public `GET /api/public/events[/{id}[/leaderboard]]`. **Frontend:** new [EventPicker.jsx](Haven-UI/src/components/wizard/EventPicker.jsx) in the [Wizard](Haven-UI/src/pages/Wizard.jsx) (`event_id` in state→payload) + [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx) (new submissions only — edits preserve the live link); `/events` is now a **public** showcase ([EventsPublic.jsx](Haven-UI/src/pages/EventsPublic.jsx), grouped Active/Upcoming/Past + leaderboard modal), admin create/manage moved to `/events/manage` + the Analytics Hub Events tab; Navbar "Events" now visible to all; admin [Events.jsx](Haven-UI/src/pages/Events.jsx) status pill uses the backend-computed status (kills the timezone-mismatch bug). **Backend restart required**; migration v1.89.0 auto-runs at startup. |
| Backend API | 1.73.0 | 2026-06-18 | See Master Haven 1.77.0. Migration **v1.89.0** (`event_id` on pending_systems/systems/pending_discoveries/discoveries + indexes). New [services/events.py](Haven-UI/backend/services/events.py) `resolve_submission_event_id()`. event_id threaded through all system + discovery intake/approve/batch/promote paths in [routes/approvals.py](Haven-UI/backend/routes/approvals.py) + [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py). [routes/events.py](Haven-UI/backend/routes/events.py) fully rewritten: approved-only event_id-keyed leaderboard/counts, consistent username normalization, civ_tags scoping (leak fix), `end>=start` validation, new `GET /api/events/active` + public `GET /api/public/events`, `/api/public/events/{id}`, `/api/public/events/{id}/leaderboard`. `/api/status` 1.72.0 → 1.73.0. |
| Haven-UI | 1.65.0 | 2026-06-18 | See Master Haven 1.77.0. New [src/components/wizard/EventPicker.jsx](Haven-UI/src/components/wizard/EventPicker.jsx) (read-only active-event picker, auto-hides when none, clears stale selection on community change). Wired into [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) (`event_id` in EMPTY_SYSTEM + Submit-Another preserve + Identity section) and [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx) (new submissions only). New public [src/pages/EventsPublic.jsx](Haven-UI/src/pages/EventsPublic.jsx) at `/events`; admin [Events.jsx](Haven-UI/src/pages/Events.jsx) moved to `/events/manage` (still embedded in Analytics Hub) with status from backend + opt-in/approved-only copy. [App.jsx](Haven-UI/src/App.jsx) routes, [Navbar.jsx](Haven-UI/src/components/Navbar.jsx) Events now public, [api.js](Haven-UI/src/utils/api.js) `getActiveEvents`/`getPublicEvents`/`getPublicEventLeaderboard`. `package.json` 1.64.0 → 1.65.0. |
| **Master Haven** | 1.76.0 | 2026-06-18 | **Production 500 hotfixes — discovery search, region-name approval, and write-lock hardening.** Parker reported "internal server error everywhere"; the Pi logs showed it was **three specific bugs**, not an outage (all reads were 200). **(1) Discovery text search 500'd** — `GET /api/discoveries/browse?q=…` raised `ambiguous column name: description` because the fetch query LEFT JOINs `systems` (which also has `description`/`discovered_by`) while the WHERE columns were unqualified. Fixed by `d.`-qualifying every filter column in [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py) (count + fetch both alias the table `d`). **(2) Region-name approval 500'd** — `POST /api/pending_region_names/{id}/approve` raised `UNIQUE constraint failed: regions.custom_name`. Root cause: the `regions` table carried a **global** `UNIQUE(custom_name)`, but NMS region names legitimately repeat across galaxies (e.g. "Muxali Terminus" exists in both Euclid and Odyalutai), and the approve handler only checked for dupes *within the same galaxy*, so a cross-galaxy clash crashed on INSERT. Per Parker (names CAN repeat), migration **v1.88.0** rebuilds `regions` dropping `UNIQUE(custom_name)` (keeps the 5-key composite + all indexes), and the four region write paths (PUT direct-update, submit, per-id approve, batch approve in [routes/regions.py](Haven-UI/backend/routes/regions.py)) no longer reject on name reuse — the only uniqueness is one row per voxel via `ON CONFLICT(reality,galaxy,region_x,region_y,region_z)`. **Migration verified against a copy of the live prod DB: 2831 rows preserved, constraint dropped, duplicate-name insert now succeeds, idempotent.** **(3) `database is locked` on `submit_discovery`** (intermittent, member submits) — an audit found no slow I/O inside any write transaction (Playwright/Pillow/webhooks all run outside the txn); the systemic risk is failed writes not rolling back (130 commits vs 2 rollbacks). The lock events correlated tightly with the burst of failing region-approve writes from (2), so fixing (2) removes the practical trigger; added defensive `conn.rollback()` on the error paths of the discovery-submit + region write handlers so a failed write can't linger holding the lock. **Backend-only; restart + migration v1.88.0 auto-runs at startup.** Durable follow-up (not done): switch `get_db_connection` to autocommit + `with conn:` to kill the missing-rollback class repo-wide. |
| Backend API | 1.72.0 | 2026-06-18 | See Master Haven 1.76.0. [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py): `browse_discoveries` filter columns qualified `d.` (fixes `ambiguous column name: description`); `submit_discovery` error path now `conn.rollback()`s. [routes/regions.py](Haven-UI/backend/routes/regions.py): `import sqlite3`; removed the global/cross-galaxy `custom_name` rejection from the PUT update, submit, per-id approve, and batch approve paths (region names may repeat); per-id approve keeps a defensive `IntegrityError→409`; `conn.rollback()` added to the update/submit/approve error paths. Migration **v1.88.0** rebuilds `regions` without `UNIQUE(custom_name)` (idempotent, recreates `idx_regions_reality_galaxy_coords`/`idx_regions_coords_scoped`/`idx_regions_coords`/`idx_regions_discord_tag`). `/api/status` 1.71.2 → 1.72.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). Requires a backend restart. |
| **Master Haven** | 1.75.0 | 2026-06-17 | **Edit discoveries through the approval queue (mirrors the system edit flow).** Discoveries could be submitted + approved but never *edited*; now anyone can edit an existing discovery and the change rides through `pending_discoveries` for non-self approval, exactly like a system edit. **Model:** new nullable `pending_discoveries.edit_discovery_id` (migration **v1.87.0**) — the direct mirror of `pending_systems.edit_system_id` (the narrow super-admin-only `pending_edit_requests` table was deliberately NOT reused). **Backend** ([routes/discoveries.py](Haven-UI/backend/routes/discoveries.py)): `submit_discovery` accepts + validates `edit_discovery_id` (must exist + live on the **same system** — an edit can change planet/moon but never move systems; 400/404 otherwise, and the missing `except HTTPException: raise` guard was added so those 4xx aren't swallowed as 500); `approve_discovery` branches — when `edit_discovery_id` is set it **UPDATEs the live discovery in place** (editable fields only) while **preserving** `discovered_by` / `submission_timestamp` / `system_id` / `discord_tag` / `profile_id` / `source`, else it INSERTs as before; new super-admin `PUT /api/pending_discoveries/{id}` for inline edits of a queued row; `edit_discovery_id` added to the pending-list SELECT. **Frontend:** [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx) gains an **edit mode** (`editDiscovery` prop — prefills every field incl. type_metadata, locks the system, keeps the existing photo unless a new one is uploaded, submits `edit_discovery_id`); an **Edit** button on [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx) (visible to everyone, like the system Edit button) wired through [Discoveries.jsx](Haven-UI/src/pages/Discoveries.jsx) + [DiscoveryType.jsx](Haven-UI/src/pages/DiscoveryType.jsx); [DiscoveryApprovalTab.jsx](Haven-UI/src/components/approvals/DiscoveryApprovalTab.jsx) shows a **NEW/EDIT badge** and, for edits, an **old → new diff** (fetches the live discovery and compares each field incl. type_metadata). **Verified:** migration applied; submit-edit creates a flagged pending row; wrong-system guard 400s; approve-edit UPDATE confirmed to change editable fields while preserving attribution (rolled-back SQL test). No live-`discoveries` schema change. **Backend restart required** (uvicorn not `--reload`); migration v1.87.0 auto-runs at startup. **Not built (endpoint ready):** the super-admin *inline* editor UI in the approval modal — the `PUT` endpoint exists; editing via the Edit button already covers super admins through the queue. |
| Backend API | 1.71.2 | 2026-06-17 | See Master Haven 1.75.0. Migration **v1.87.0** adds nullable `pending_discoveries.edit_discovery_id` (column-guarded). [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py): `submit_discovery` accepts/validates `edit_discovery_id` (same-system guard, `except HTTPException: raise` added) and stores it in the column + `discovery_data` blob; `approve_discovery` UPDATEs the live row in place when it's an edit (preserves discovered_by/timestamp/system_id/discord_tag/profile_id/source) else INSERTs; new super-admin `PUT /api/pending_discoveries/{id}` (inline edit, audit `edit_pending_discovery`); `edit_discovery_id` added to `GET /api/pending_discoveries`. `/api/status` 1.71.1 → 1.71.2 in [routes/auth.py](Haven-UI/backend/routes/auth.py). Requires a backend restart. |
| Haven-UI | 1.64.0 | 2026-06-17 | See Master Haven 1.75.0. [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx) edit mode (`editDiscovery` prop: prefill incl. type_metadata with a type-change-clear guard, locked system, photo preservation, `edit_discovery_id` in payload, "Submit Edit" CTA + amber banner). [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx) Edit button (`onEdit`). [Discoveries.jsx](Haven-UI/src/pages/Discoveries.jsx) + [DiscoveryType.jsx](Haven-UI/src/pages/DiscoveryType.jsx) wire `handleEditDiscovery` → open the submit modal in edit mode. [DiscoveryApprovalTab.jsx](Haven-UI/src/components/approvals/DiscoveryApprovalTab.jsx): NEW/EDIT badge + old→new diff (fetches `/api/discoveries/{edit_discovery_id}` for the original). `package.json` 1.63.0 → 1.64.0. |
| **Master Haven** | 1.74.0 | 2026-06-17 | **Discovery type-metadata now actually displays everywhere + unified in-game C/B/A/S color scale.** Two fixes Parker + Star asked for. **(1) Metadata display:** every discovery type's per-type fields (fauna `species_name`/`behavior`/`height`/`weight`, multi-tool `tool_*`, base/structure/flora/etc.) are stored in `discoveries.type_metadata` (JSON) but were **never rendered** on the Discovery-tab cards, and the detail modal's "Details" grid was **silently dead** — the `browse`/`recent` endpoints returned the blob as a raw JSON *string* while the modal only rendered it when `typeof === 'object'`. No data was missing (44/66 local rows had populated metadata); a pure read/render bug, so **no backfill migration** — the data was always there. Fix: new shared [discoveryMeta.js](Haven-UI/src/utils/discoveryMeta.js) (`parseTypeMetadata` handles object OR string, `metaEntries` returns labelled+colored entries, labels sourced from the curated `DISCOVERY_TYPE_FIELDS`), wired into [DiscoveryCard.jsx](Haven-UI/src/components/discoveries/DiscoveryCard.jsx) (new compact metadata line) and [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx) (Details grid now string-safe); backend [discoveries.py](Haven-UI/backend/routes/discoveries.py) `browse`/`recent` now `json.loads` the blob; 3D map [VH-System-View.html](Haven-UI/public/VH-System-View.html) `buildDiscCard` renders all fields. **(2) In-game color scale:** new single-source [gradeColors.js](Haven-UI/src/utils/gradeColors.js) `TIER_COLORS` (**S=Gold `#ffd700`, A=Purple `#c084fc`, B=Blue `#60a5fa`, C=Green `#4ade80`**) + mineral `RICHNESS_COLORS` (Extraordinary=Gold, Rare=Purple, Common=Green). Starship/multi-tool `*_class` and mineral `deposit_richness` values now render as colored chips on card/modal/3D-map (color derived from each field's `recordKind` in `DISCOVERY_TYPE_FIELDS`). The **completeness grade pills were recolored to match** (`.grade-*`/`.bar-*` in [index.css](Haven-UI/src/styles/index.css): A green→purple, C gray→green) plus the Wizard preview/sidebar/progress maps, the [SystemThumb.jsx](Haven-UI/src/posters/SystemThumb.jsx) poster `GRADE_BG`, and the 3D map grade styles ([VH-System-View.html](Haven-UI/public/VH-System-View.html) `getGradeStyle`, [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) `cf-grade` pills). Map HTML keeps its own inline copy of the palette (can't import JS); edited in `public/` + copied to `dist/`. Frontend + a read-side backend parse; **no schema change, no migration.** Backend needs a restart for the `browse`/`recent` parse (frontend parses defensively regardless). |
| Backend API | 1.71.1 | 2026-06-17 | See Master Haven 1.74.0. `browse` + `recent` in [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py) now `json.loads(type_metadata)` per row (mirrors the detail endpoint) so list responses return the blob as an object instead of a raw string — closes the gap where the discovery detail modal's `typeof === 'object'` guard silently dropped every per-type field. Read-side only, no schema/migration. `/api/status` 1.71.0 → 1.71.1 in [routes/auth.py](Haven-UI/backend/routes/auth.py). Requires a backend restart (uvicorn not `--reload`). |
| Haven-UI | 1.63.0 | 2026-06-17 | See Master Haven 1.74.0. New [src/utils/discoveryMeta.js](Haven-UI/src/utils/discoveryMeta.js) (`parseTypeMetadata`, `metaEntries`, `metaValueColor`, `prettyMetaLabel`) and [src/utils/gradeColors.js](Haven-UI/src/utils/gradeColors.js) (`TIER_COLORS`, `RICHNESS_COLORS`, `classColor`/`gradeColor`, `richnessColor`). [DiscoveryCard.jsx](Haven-UI/src/components/discoveries/DiscoveryCard.jsx) renders a compact metadata line w/ colored class/richness chips; [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx) Details grid is string-safe + colored. Grade-pill recolor: [index.css](Haven-UI/src/styles/index.css) `.grade-*`/`.bar-*`, [WizardPreviewPanel.jsx](Haven-UI/src/components/wizard/WizardPreviewPanel.jsx)/[WizardSidebar.jsx](Haven-UI/src/components/wizard/WizardSidebar.jsx)/[WizardProgressBar.jsx](Haven-UI/src/components/wizard/WizardProgressBar.jsx) now pull from `TIER_COLORS`, [SystemThumb.jsx](Haven-UI/src/posters/SystemThumb.jsx) `GRADE_BG`. `package.json` 1.62.1 → 1.63.0. |
| Haven Extractor | 1.10.5 | 2026-06-17 | **HOTFIX — reverts the 1.10.4 Option-C `Generate.before` hook that broke mod loading.** 1.10.4 was published with a `@nms.cGcSolarSystem.Generate.before` hook (Option C batch fix). It registered on Parker's machine but **failed on at least one member's pyMHF/nmspy build** (`cGcSolarSystem ... not found` at mod load) — and a failed hook decorator aborts the ENTIRE mod load. This codebase has only ever used `.after`; `.before` was unverified (exactly the load-time risk flagged at release time). **1.10.5 removes the `.before` decorator** ([haven_extractor.py:1598](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py#L1598) — method kept unhooked as dead code for reference; only `.after` remains). All **confirmed** fixes stay: galaxy resolution, phantom-planet filter (1.10.2), and the single-upload display-adjective builder fix (1.10.3, proven in the 19:36 log). Batch (non-last-system adjectives) is **again deferred** — Plan B is a throttled collect-while-live on the proven `GenerateCreatureRoles` `.after` hook (which fires ~135k×/system), NOT a `.before` hook. `__version__` 1.10.4 → 1.10.5 (+ pyproject); compiles clean, smoke test 56/56. **Re-release: v1.10.5 with 3 assets** — `HavenExtractor-mod-v1.10.5.zip` PLUS the standalone `UPDATE_HAVEN_EXTRACTOR.bat` + `_haven_updater_helper.py` (a member hit "_haven_updater_helper.py not found" because the v1.10.4 release shipped only the mod zip, so the .bat's "re-download from releases/latest" repair instruction had nothing to fetch). v1.10.4 release to be **deleted**. Two member-side errors were not code bugs: running the updater **as Administrator** starts it in `C:\Windows\System32` → "embedded Python not found" (fix: double-click from the HavenExtractor folder), and the missing-helper case (fixed by adding the helper to the release). Broken-mod members recover by re-running the updater once v1.10.5 is live (the updater .bat runs even when the mod won't load). |
| **Master Haven** | 1.73.3 | 2026-06-17 | **Extractor display-adjective fix — wrong Weather/Sentinel/Flora/Fauna on uploads (single AND batch).** Ekimo's Odusto upload had correct names/biomes/resources but the per-planet adjectives were the generic enum tier, not the game's display strings (in-game *Superheated Drizzle / Malicious / Infrequent* → submitted *Humid / High / Sparse*; *Heated Atmosphere / Observant / Abundant / Full* → *Scorched / Limited / Copious / Bountiful*; etc.). Root cause is a single bug that breaks **single uploads too**: NMS only exposes the exact adjectives in the live `PlanetInfo` array (populated after entry); `_auto_refresh_for_export()` reads them and stashes the resolved strings into the captured `flora_display`/`fauna_display`/`sentinel_display`/`weather_display` keys — but the payload builder [`build_planet_entry`](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py) read the plain `flora`/`fauna`/`sentinel`/`weather` **enum-tier** keys and **discarded the collected display strings**. The display-preference logic only ever lived in the now-dead memory-read path (`_extract_single_planet`); when the captured-only path became primary (v1.9.7) it was never carried forward (confirmed against git `86354aa`). **Fix = Haven Extractor 1.10.3 (Fix 1 of 2 — the builder):** `build_planet_entry` now prefers `captured['*_display']` (already resolved at capture time) and falls back to the enum tier only when the display string wasn't captured; a `clean_weather` callable (passed from the wrapper as `clean_weather_string`) normalises weather exactly as the legacy path did. This makes single uploads correct deterministically, because the export refresh already collected the right values — we just stopped throwing them away. **Tested:** `test_extraction_core.py` gains a `test_display_adjective_preference` (display wins over enum for all four fields; enum fallback when no display; `clean_weather` applied) — **56 checks pass**; both mod files byte-compile clean. **Deferred to a Fix 2 (NOT in 1.10.3, by decision):** multi-system *batch* uploads — non-last systems are frozen on warp before any refresh runs, so their `*_display` was never collected and can't be (memory recycled). They'll still send the enum tier until a collect-while-live mechanism is added. Single uploads and the last system of a batch are fixed now. **Odusto 9761 adjectives left as-is** (the display strings were never captured, so unrecoverable from the DB) — Ekimo will correct them at approval. **Mod zip `HavenExtractor-mod-v1.10.3.zip` built** in the repo root (bundles both the 1.10.2 phantom fix and this; supersedes the now-archived v1.10.2 zip). **Open (Parker's manual step):** upload v1.10.3 to the GitHub Release for the auto-updater. |
| Haven Extractor | 1.10.3 | 2026-06-17 | See Master Haven 1.73.3. Display-adjective fix (Fix 1, builder). [`build_planet_entry`](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py) now resolves flora/fauna/sentinel/weather as `captured['*_display'] or captured['*'] or 'Unknown'` (display string preferred, enum-tier fallback), with a new optional `clean_weather` callable param; the wrapper `_planet_from_captured` passes `clean_weather=clean_weather_string`. No game-memory read added (display strings are already collected by `_auto_refresh_for_export`; the builder was just discarding them). `__version__` 1.10.2 → 1.10.3 (+ [pyproject.toml](NMS-Haven-Extractor/pyproject.toml)). `test_extraction_core.py` +7 checks (56 total, all pass). Mod zip `HavenExtractor-mod-v1.10.3.zip` (supersedes archived v1.10.2); **needs uploading to the GitHub Release**. Batch non-last-system display adjectives are a deferred Fix 2. |
| **Master Haven** | 1.73.2 | 2026-06-17 | **Extractor phantom-planet fix — "random made-up planets" on extractor uploads.** Ekimo's Odusto upload (now galaxy-correct: Mushonponte) landed in the pending queue with **6 planets when the system only has 3**: the 3 real bodies (Reolus XIII / Umerisc Tau / Caeanoi Sigma, proper procgen names + varied biomes) plus **3 phantoms** named `Planet_4/5/6`, all identical default Lush/Small. Root cause: the v1.10.0 "captured-only" rewrite builds the planet list purely from `_captured_planets` with **no planet-count bound** (unlike the legacy `_extract_planets`, which clamps to the authoritative `PLANETS_COUNT`). The `GenerateCreatureRoles` hook fires ~60×/sec while in-system; most fires resolve a real planet name and dedupe, but a fire whose name can't be read yet was stored as a distinct `_unnamed_N` entry ([haven_extractor.py:2039](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py#L2039)) with default data and rendered as `Planet_{n}` at export ([extraction_core.py:96](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py#L96)). Intermittent (a DB scan of the last 40 extractor submissions found Odusto the **only** one with phantoms; Kaksim XI from the same session was clean) — it only triggers when spurious nameless fires happen to land while the system is live. **Fix = Haven Extractor 1.10.2** (two parts): **(A)** new pure `select_captures()` in [extraction_core.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py) — a real NMS body always has a name, so when ANY named capture exists it drops ALL nameless `_unnamed_*` phantoms; falls back to unnamed only if *nothing* got a name (never planetless); the live `_planets_count` (planets+moons, 1..6) snapshot is used as an UPPER cap only, never to pad with placeholders (the post-Voyagers count read is unreliable). `build_planet_list` filters through it; `_planets_from_captured` passes the snapshot hint. **(B)** hook-quota hardening: only NAMED captures count toward the 6-body cap, and a real planet evicts a phantom if the dict is full — so a phantom fire arriving *before* the real planets can never displace one. **Tested:** `test_extraction_core.py` gains 7 phantom-filter checks (Odusto shape, no-pad, over-long trim, degraded all-unnamed fallback, no-hint) — all 49 checks pass; both mod files byte-compile clean. **The already-submitted Odusto row (pending id 9761)** was patched in place on the Pi (3 `Planet_*` phantoms dropped from `system_data.planets`; backup at `/home/pi8gb/odusto_9761_system_data.bak.json`). **`HavenExtractor-mod-v1.10.2.zip` built** (17 entries, incl. `nms_namegen/`) — **now superseded by and folded into the v1.10.3 zip** (the v1.10.2 zip was moved to `NMS-Haven-Extractor/archive/`; neither was ever released). The v1.10.3 zip is the one to upload — it carries this phantom fix, the 1.10.3 adjective fix, AND the first published copy of the 1.10.x galaxy fix (no 1.10.0/1.10.1 zip was ever published, which is why new uploads kept needing the galaxy backfill). |
| Haven Extractor | 1.10.2 | 2026-06-17 | See Master Haven 1.73.2. Phantom-planet fix. New pure `select_captures(captured_planets, count_hint=)` + `_capture_has_name()` in [extraction_core.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py); `build_planet_list` gains a `count_hint` param and filters through `select_captures` (drop nameless `_unnamed_*` captures when any named capture exists; `count_hint` = live `PLANETS_COUNT` planets+moons is an upper cap only, never pads). [haven_extractor.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py): `_planets_from_captured` passes `_current_system_snapshot['_planets_count']` as the hint and logs dropped-phantom count; the GenerateCreatureRoles capture block now counts only NAMED captures toward the 6-body cap and evicts a phantom to seat a real planet. `__version__` 1.10.1 → 1.10.2 (+ [pyproject.toml](NMS-Haven-Extractor/pyproject.toml)). `test_extraction_core.py` +7 checks (49 total, all pass). Mod-only zip `HavenExtractor-mod-v1.10.2.zip` **superseded by v1.10.3** (archived to `NMS-Haven-Extractor/archive/`); upload the v1.10.3 zip instead. |
| **Master Haven** | 1.73.1 | 2026-06-16 | **Backfill migration v1.86.0 — fixes MidGenX's "always Euclid" extractor uploads (galaxy + galaxy-dependent procedural names).** The pre-1.10 Haven Extractor stamped every system/region as Euclid for MidGenXGamer while he was galaxy-hopping; 272 of his systems sit in the pending queue wrongly labelled Euclid, and the procgen **system AND region names** are Euclid-seeded (a deterministic check confirmed all 272 stored system names exactly equal `systemName(glyph, galaxy=0)` — the buggy Euclid fallback, not real in-game names). MidGenX confirmed the galaxy per upload **session** (Discord reports, times resolve cleanly to **EDT**): 5/18 → **Hyades**, 5/19 → **Ickjamatew** *except the single last system* (he crossed the Ickjamatew core into **Budullangr**), 5/24 → **Budullangr**. Two further sessions (5/23 = 10 systems, 5/25 = 53) were **not** reported and are intentionally **left Euclid** for a follow-up. New migration **v1.86.0** ([migrations.py](Haven-UI/backend/migrations.py)) corrects the **3 confirmed sessions = 209 systems**: rewrites galaxy in BOTH the `pending_systems.galaxy` column and the `system_data` JSON `galaxy` key (approval reads the blob — [approvals.py:1571](Haven-UI/backend/routes/approvals.py#L1571)), and regenerates the system name via the backend-vendored [nms_namegen](Haven-UI/backend/nms_namegen/) **only when the stored name matches the Euclid procgen** (per-row guard; preserves any real/custom name). It also moves the **already-approved** region names (the extractor auto-submitted + approved them separately, so they're live under `galaxy='Euclid'` in the `regions` table) to the correct galaxy with regenerated names — handling the `regions` `UNIQUE(custom_name)` constraint (a name already taken by a *different* region is **deferred + logged**, not clobbered: 1 case, `'Sea of Izzy'`) and shared voxels (1 voxel still referenced by another live Euclid system — MidGenX's own earlier approved duplicate of `Nahuiju XIII` — gets a fresh correct-galaxy row while the Euclid row is left intact). **Dry-run verified** against a 2026-06-16 prod snapshot: 209 systems re-galaxied (Hyades 128 / Ickjamatew 44 / Budullangr 37), 209 names regenerated, 204 regions moved + 1 inserted + 1 collision deferred, 205 region-name records corrected, 63 held systems + other contributors untouched, idempotent re-run. **Requires a backend `--build` deploy** (the running Pi image predates `nms_namegen`; rebuilding bundles it); migration auto-runs at startup. **Not addressed here (open):** the 5/23 + 5/25 galaxies (need MidGenX), the unreleased 1.10.1 mod zip (root cause of *new* Euclid uploads — the auto-updater still serves a pre-1.10 build), and the pre-existing approved-Euclid duplicate of `Nahuiju XIII`. |
| Backend API | 1.71.0 | 2026-06-16 | See Master Haven 1.73.1. New migration **v1.86.0** in [migrations.py](Haven-UI/backend/migrations.py) (MidGenX "always Euclid" backfill: 209 pending systems across 3 confirmed upload sessions + their live region names; per-row Euclid-procgen guard for name regen via [nms_namegen](Haven-UI/backend/nms_namegen/); `regions.UNIQUE(custom_name)` collision deferral; shared-voxel handling; idempotent). No endpoint/schema changes. `/api/status` 1.70.1 → 1.71.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). **Requires a `--build` deploy** so the image includes `nms_namegen` (the running Pi image predates it). |
| **Master Haven** | 1.73.0 | 2026-05-31 | **Discovery surface coordinates (latitude/longitude).** Discoveries (any type — fauna/flora/mineral/ancient/etc.) can now carry the precise surface lat/long NMS shows in the analysis visor, on top of the existing `location_type`/`planet_id`/`moon_id` links and free-text `location_name` (which is kept — coords complement it, they don't replace it). **Schema:** migration v1.85.0 adds nullable `latitude REAL`/`longitude REAL` to BOTH `discoveries` and `pending_discoveries` (column-presence guarded, no backfill). **Backend:** new `normalize_discovery_coords()` in [constants.py](Haven-UI/backend/constants.py) range-checks (lat ∈ [-90,90], lng ∈ [-180,180]), coerces to float, nulls anything invalid OR any `location_type='space'` discovery — applied at every one of the FOUR discovery INSERT paths so a coord can't silently drop: `POST /api/submit_discovery` and `POST /api/discoveries` (both → `pending_discoveries`, also stamped into the `discovery_data` JSON blob), `POST /api/approve_discovery/{id}` (→ live `discoveries`, reads the dedicated pending columns w/ JSON-blob fallback), and `_promote_draft_discoveries` (wizard co-submitted discoveries, both single + batch system approval) plus its `_sanitize_discoveries_draft` intake. **Reads:** `GET /api/systems/{id}` discoveries SELECT gains `latitude`/`longitude` — and in the same edit fixes a latent bug where that explicit-column SELECT referenced non-existent `d.photos`/`d.featured` columns (aliased to the real `d.photo_url`/`d.is_featured`), which had been throwing and returning `discoveries: []` on EVERY SystemDetail load. `GET /api/pending_discoveries` list SELECT gains the two columns for the approval card; browse/recent/detail already `SELECT *`. **Frontend:** new shared [LatLngInput.jsx](Haven-UI/src/components/LatLngInput.jsx) (two decimal fields + paste-parse that splits a pasted "+45.23, -12.85" across both, amber out-of-range hint) plus `coordToFloat`/`formatCoords` helpers; wired into all three submission surfaces (DiscoverySubmitModal, Wizard inline DiscoveryInlineList, Wizard `buildDiscoveryDraftEntry`) and four display surfaces (DiscoveryDetailModal Location section, DiscoveryCard chip, SystemDetail discovery chips, DiscoveryApprovalTab review modal — which also now surfaces the previously-hidden `location_name`). Inputs hide for space discoveries. **Requires backend restart** on the Pi (uvicorn not running with `--reload`); migration v1.85.0 runs at startup. |
| Backend API | 1.70.0 | 2026-05-31 | See Master Haven 1.73.0. Migration v1.85.0 (`latitude`/`longitude REAL` on `discoveries` + `pending_discoveries`). New `normalize_discovery_coords(lat, lng)` in [constants.py](Haven-UI/backend/constants.py). Wired into 4 INSERT paths across [routes/discoveries.py](Haven-UI/backend/routes/discoveries.py) (`submit_discovery`, `create_discovery`, `approve_discovery`) and [routes/approvals.py](Haven-UI/backend/routes/approvals.py) (`_sanitize_discoveries_draft` + `_promote_draft_discoveries`). READ: `pending_discoveries` list SELECT + the `GET /api/systems/{id}` discoveries SELECT in [control_room_api.py](Haven-UI/backend/control_room_api.py) (also fixed the `d.photos`/`d.featured` → `d.photo_url`/`d.is_featured` alias bug that was erroring that subquery). `/api/status` 1.69.0 → 1.70.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). |
| Haven-UI | 1.62.0 | 2026-05-31 | See Master Haven 1.73.0. New [src/components/LatLngInput.jsx](Haven-UI/src/components/LatLngInput.jsx) (shared two-field coordinate input with paste-parse + range validation; exports `coordToFloat`, `coordValid`, `formatCoords`). Submission: [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx) (form state `latitude`/`longitude`, payload, input gated on non-space), [DiscoveryInlineList.jsx](Haven-UI/src/components/wizard/DiscoveryInlineList.jsx) (empty-entry shape + input), [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) `buildDiscoveryDraftEntry` (float-or-null, nulled for space). Display: [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx) Location section, [DiscoveryCard.jsx](Haven-UI/src/components/discoveries/DiscoveryCard.jsx) chip, [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) discovery chips, [DiscoveryApprovalTab.jsx](Haven-UI/src/components/approvals/DiscoveryApprovalTab.jsx) review modal (also surfaces `location_name`). `package.json` 1.61.0 → 1.62.0. |
| **Master Haven** | 1.72.0 | 2026-05-26 | **Sitewide glyph art swapped to the Summer Unification Day festival glyph set.** Replaced the old opaque `IMG_92xx.webp` portal-glyph photos — which were served from the gitignored `/haven-ui-photos/` user-photo volume (`Haven-UI/photos/*` is in `.gitignore`), so they were never committed and couldn't be relied on across deploys — with the transparent mint-on-clear festival glyph art, now committed at [Haven-UI/src/assets/glyphs/{0-F}.webp](Haven-UI/src/assets/glyphs/). New single-source-of-truth module [glyphAssets.js](Haven-UI/src/utils/glyphAssets.js) (`GLYPH_NAMES`, `HEX_DIGITS`, `glyphImageSrc()`) now backs **all four** glyph render paths — [GlyphPicker.jsx](Haven-UI/src/components/GlyphPicker.jsx) (the wizard / discovery-submission picker), [GlyphDisplay.jsx](Haven-UI/src/components/GlyphDisplay.jsx) (read-only approval display), [WizardAdvancedPreview.jsx](Haven-UI/src/components/wizard/WizardAdvancedPreview.jsx) live preview, and the Playwright-rendered [SystemThumb.jsx](Haven-UI/src/posters/SystemThumb.jsx) poster — replacing four duplicated hardcoded glyph maps and the runtime `/api/glyph_images` axios fetch. Per Parker, Haven's existing button chrome (dark tile + purple border) is **unchanged** — only the symbol art swapped. The poster's `mix-blend-mode:screen` / `brightness(1.4)` black-background-dropping hack is removed (Parker's prior note in SystemThumb explicitly called the old glyphs "placeholders pending transparent-bg replacements" — these are those replacements). **Crucial routing detail:** glyphs are resolved through Vite's bundler (`import.meta.glob` + `?url`), NOT a `public/` path — the backend's `/haven-ui/{path:path}` catch-all ([control_room_api.py](Haven-UI/backend/control_room_api.py) `spa_catchall`) returns 404 for any `*.webp` not under `/haven-ui/assets/`, so a `public/glyphs/*.webp` URL would 404 in prod even though it works in the dev server. All 16 glyphs are <4 KB, so Vite inlines them as base64 data URIs in the `glyphAssets` chunk — zero mount dependency, correct in dev, prod, and the headless poster renderer alike. Frontend-only — no backend change; the now-unused `/api/glyph_images` endpoint + `GLYPH_IMAGES` map in `glyph_decoder.py` are left in place (dead, optional cleanup). Build verified clean; 16 data URIs confirmed in the built `glyphAssets` chunk. |
| Haven-UI | 1.61.0 | 2026-05-26 | See Master Haven 1.72.0. New [src/utils/glyphAssets.js](Haven-UI/src/utils/glyphAssets.js) is the single source for glyph names + served art URLs (resolved via `import.meta.glob('../assets/glyphs/*.webp', { eager, query:'?url' })`). [GlyphPicker.jsx](Haven-UI/src/components/GlyphPicker.jsx) drops its `glyphImages` state + `/api/glyph_images` fetch and renders `glyphImageSrc(digit)` directly (axios kept — still used for validate/decode). [GlyphDisplay.jsx](Haven-UI/src/components/GlyphDisplay.jsx) rewritten to drop axios/useState/useEffect entirely (static import). [WizardAdvancedPreview.jsx](Haven-UI/src/components/wizard/WizardAdvancedPreview.jsx) and [SystemThumb.jsx](Haven-UI/src/posters/SystemThumb.jsx) drop their local `GLYPH_FILE` maps; poster `GlyphIcon` switched from `objectFit:cover` + blend hack to clean `objectFit:contain` 30×30 inside the existing chip. 16 festival glyphs copied from `grand-festival/frontend/public/glyphs/` into [src/assets/glyphs/](Haven-UI/src/assets/glyphs/) (under `src/`, not `public/`, so they route through the bundler — see Master Haven 1.72.0 for why `public/` would 404 in prod). `package.json` 1.60.0 → 1.61.0 (note: the prior 1.60.0 was a stray version bump inside the unrelated `5de1b37 "docker mount of guild db"` commit, never given a changelog row). Build clean. |
| **Master Haven** | 1.71.0 | 2026-05-25 | **Haven Extractor batch + galaxy rewrite (data-loss + "always Euclid" fixes).** Two long-standing extractor bugs fixed together. **(1) Batch data loss:** finalizing a batched system used to re-read live game memory (`_auto_refresh_for_export` + `_get_current_coordinates` inside the save path), but NMS reuses ONE solar-system object, so once you warp away the old memory holds the NEXT system — every non-last batched system inherited the next system's star/economy/conflict/lifeform/glyph/galaxy. Now each system is FROZEN purely from data captured while it was live (snapshot + coords + captured planets), via a new import-safe pure module [extraction_core.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py) — no memory read at finalize, so a frozen system is immutable against later warps. **(2) "Always Euclid":** galaxy came from a single zeroed scratch read (`sys_data+0x1EA0+0x44`) that was accepted as a literal Euclid (`0 is not None`), short-circuiting the authoritative player-location source. Now `_resolve_galaxy_index` votes across three nmspy-accessor reads (player `mLocation.RealityIndex`, per-planet `mPlanetGenerationInputData.RealityIndex` @0x3A60, and the sysdata scratch copy) via pure `decide_galaxy()`: prefer any non-zero, accept 0 only when positively read, return UNKNOWN (never fabricate Euclid) when unreadable; galaxy re-resolves on every creature-roles fire while live; export HOLDS galaxy-unknown systems instead of uploading them as Euclid. Fixed `PlanetGenInputOffsets.STRUCT_SIZE` 0x53→0x58 (latent slot-stride bug). **Verified** by a standalone smoke test ([tests/test_extraction_core.py](NMS-Haven-Extractor/tests/test_extraction_core.py), 41 checks PASS on embedded Py3.11): single-upload parity, 3-system batch independence, freeze-isolation, galaxy edge cases. Mod-only zip needs rebuilding (now also includes `extraction_core.py`). Deferred (noted, not done): heartbeat refresh for late display-adjectives (not in payload today) and removal of the dead `_do_extraction`/`_extract_planets`/`_extract_single_planet` path. |
| Haven Extractor | 1.10.1 | 2026-05-26 | **Follow-up to 1.10.0 (per Parker: no Euclid fallback — it makes wrong systems AND wrong region names).** (1) Procedural system/region names are galaxy-DEPENDENT, so they're no longer seeded with a fallback galaxy 0 when the galaxy is unknown — new `_make_proc_names()` leaves the region name EMPTY + system name a placeholder until the galaxy resolves. (2) `_refresh_galaxy_on_current_coords` now REGENERATES the region + (proc) system names with the corrected galaxy when it resolves while live, so a stale Euclid-seeded name can never be the one submitted (won't clobber a user-applied custom name). (3) Held (galaxy-unknown) systems are now LOUDLY visible in the GUI Status field (`HELD N: galaxy unknown - re-warp & re-export (NOT uploaded)` / `Uploaded X; HELD N`) instead of silently vanishing. Held systems stay in the batch for re-export. `__version__` 1.10.0→1.10.1. NOTE: if the galaxy resolves UNKNOWN on a given setup, EVERY system is held (nothing uploads) — that's intentional (no bad data) but means the galaxy read must actually work; confirm via the `[GALAXY] resolved=… via=…` log line. |
| Haven Extractor | 1.10.0 | 2026-05-25 | See Master Haven 1.71.0. New pure module [extraction_core.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py) (`decide_galaxy`, `build_planet_entry`, `build_planet_list`, `build_system_payload`, `galaxy_is_known`) — zero pymhf/nmspy imports so it's smoke-testable outside the game. `_save_current_system_to_batch` rewritten to freeze from the live-captured cache (no `_auto_refresh_for_export`/`_get_current_coordinates`/`_get_actual_system_name` re-reads); `_planets_from_captured`/`_planet_from_captured` now thin wrappers over the core. Galaxy: new `_read_galaxy_from_location` + `_read_galaxy_from_planet_geninput` (nmspy accessors), `_resolve_galaxy_index` returns Optional[int] (None=UNKNOWN), coord builders carry `galaxy_unknown`, `_refresh_galaxy_on_current_coords` re-resolves while live, `_run_export_flow` holds unknown-galaxy systems (kept in batch for re-export), `STRUCT_SIZE` 0x53→0x58. `__version__` 1.9.8→1.10.0. **Requires the mod-only zip to be rebuilt** (include `extraction_core.py`) and uploaded to the GitHub Release for auto-update. |
| **Master Haven** | 1.70.0 | 2026-05-19 | **Root-cause fix for "new partners/sub-admins can't see Approvals" — leaders are now full-power BY ROLE.** v1.69.0 fixed the *plumbing* (sync civ features → `user_profiles.enabled_features`, the column the session/route-guards read) but not the *source*: a civ leader's features still came **only** from `civilizations.enabled_features_default` (or a per-member override the UI never sent). The "Found new civilization" modal seeds that default **empty** (its feature grid is framed "for sub-admins"), so every leader of a newly-founded civ got `tier=2`/"Partner" with `enabled_features=[]` and zero feature access — `canAccess('approvals')` false → Approvals route redirects, navbar link hidden. Existing civs (Haven, GHUB…) worked because migration v1.80.0 backfilled their default from the legacy `partner_accounts.enabled_features`; only **new** civs were born empty. **Fix (3 layers + UI):** (1) new `LEADER_FEATURES` frozenset in [constants.py](Haven-UI/backend/constants.py) (the 8 partner-grade features); `_recompute_profile_features` in [routes/civilizations.py](Haven-UI/backend/routes/civilizations.py) now reads `cm.role` and grants the full set to `leader`/`co_leader` **regardless** of civ default/override — sub_admins keep override-else-civ-default so they stay scopable. (2) Migration v1.84.0 re-runs the role-aware union for every profile with an active civ membership, repairing existing+freshly-broken leaders on deploy. (3) `GET /api/admin/status` now re-reads `tier`+`enabled_features` from `user_profiles` on every poll and writes them back into the live session, so a super admin's permission change takes effect on the user's **next page load** instead of requiring a logout/login. **UI** ([CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx)): per-member permissions editor in `MemberRow` (sub-admin override via PUT, with inherit/reset-to-civ-default; leaders show "full access by role"), both feature grids relabeled "(leaders & co-leaders always get full access)", create modal seeds a sensible sub-admin default set. **Requires backend restart** on the Pi (uvicorn not running with `--reload`); migration v1.84.0 runs at startup. |
| Backend API | 1.68.0 | 2026-05-19 | `_recompute_profile_features` ([routes/civilizations.py](Haven-UI/backend/routes/civilizations.py)) rewritten role-aware: SELECT now includes `cm.role`; `leader`/`co_leader` memberships union the new `LEADER_FEATURES` frozenset from [constants.py](Haven-UI/backend/constants.py) (`system_create, system_edit, approvals, batch_approvals, stats, settings, csv_import, war_room`) independent of civ default/override; `sub_admin` keeps per-member-override-else-`enabled_features_default`. Applies at all 5 existing callsites (founder, add_member, update_member on role/features change, remove_member, update_civilization fan-out). New migration **v1.84.0** ([migrations.py](Haven-UI/backend/migrations.py)) re-runs the role-aware union for every profile with an active civ membership (leader feature set inlined as a frozen historical record). `GET /api/admin/status` ([routes/auth.py](Haven-UI/backend/routes/auth.py)) now re-reads `tier`+`enabled_features` from `user_profiles` per call, writes them back into the live session, and re-derives `user_type` via `TIER_TO_USER_TYPE` — closes the stale-session gap where a logged-in partner kept old permissions until re-login. `/api/status` 1.67.0 → 1.68.0. |
| Haven-UI | 1.59.0 | 2026-05-19 | [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx): `MemberRow` gains a collapsible per-member **permissions editor** — for sub-admins it renders the feature grid seeded from the member's override (or inherited civ default), with **Save permissions** (PUT `enabled_features` array → explicit override) and **Reset to civ default** (PUT `enabled_features: null`); leaders/co-leaders show a "full access by role" note instead. New `setMemberFeatures()` handler. Both `enabled_features_default` grids (create + edit) relabeled "Default features for sub-admins (leaders & co-leaders always get full access)". Create modal now seeds `DEFAULT_SUB_ADMIN_FEATURES` (`approvals, system_create, system_edit, stats`) instead of `[]` so a civ founded without touching the grid still has working sub-admins. No new deps. |
| **Master Haven** | 1.69.0 | 2026-05-18 | **Civ-derived permissions actually take effect now + legacy tier endpoint locked down (Option A).** Parker reported that members elevated to civ leader via CivilizationManagement → Add Member ended up with tier=2 but **no permissions** — they could log in but couldn't open the War Room, hit Approvals, or use any feature-gated route. Root cause: `_recompute_profile_tier` in [routes/civilizations.py](Haven-UI/backend/routes/civilizations.py) only synced `tier`, never touched `enabled_features`. The session at login reads `user_profiles.enabled_features` ([auth.py:238](Haven-UI/backend/routes/auth.py#L238)), so a leader added via the new flow had tier=2 + features=[] — right title, zero access. Fix is three-layer: (1) new `_recompute_profile_features(cur, profile_id)` helper computes the UNION of effective features across all active civ memberships (per-member `civilization_members.enabled_features` override wins, else civ `enabled_features_default`), wired into all 4 callsites that touch membership state — `create_civilization` (founder), `add_member`, `update_member` on role-OR-features change, `remove_member`, and `update_civilization` when `enabled_features_default`/`is_active` change (which fans out to every member). (2) Migration v1.83.0 backfills existing leaders/sub-admins so they don't have to wait for the next civ event. (3) `PUT /api/admin/profiles/{id}/tier` ([routes/profiles.py:856](Haven-UI/backend/routes/profiles.py#L856)) now **rejects tier 2/3** with a 400 pointing to the Civilizations endpoint, and **rejects tier 4/5 demotion** with a 409 when the target still has active civ memberships (would be silently reverted by `_recompute_profile_tier` otherwise). Only valid uses now: promote/demote Super Admin, demote a no-civ user to Member/Read-Only. **Cleanup**: dead reads of `theme_settings` and `region_color` dropped from the login SELECT in [auth.py:158](Haven-UI/backend/routes/auth.py#L158) (selected for years, never written to session — superseded by `civilizations.theme_settings`/`region_color`). UserManagement.jsx Demote button removed (would always 409 against the new backend; Civilizations → Remove is the canonical path). Elevate modal's tier-4/5 advisory warning rewritten from "may be overridden" → "will be rejected with 409" to match the new hard guard. **Requires backend restart** on the Pi. |
| Backend API | 1.67.0 | 2026-05-18 | New `_recompute_profile_features(cur, profile_id)` helper in [routes/civilizations.py](Haven-UI/backend/routes/civilizations.py): unions effective features across active civ memberships (per-member override wins over civ default) and writes to `user_profiles.enabled_features`. Skips super admins (tier 1) and inactive civs. Wired into 5 callsites: `create_civilization` (founder), `add_member`, `update_member` on role-or-features change, `remove_member`, `update_civilization` when `enabled_features_default`/`is_active` changes (fans out to all members). `PUT /api/admin/profiles/{id}/tier` rewritten: allowed tiers reduced to `{TIER_SUPER_ADMIN, TIER_MEMBER, TIER_MEMBER_READONLY}`; tier 2/3 returns 400 with civ-endpoint pointer; tier 4/5 returns 409 when target has any `civilization_members` row joined to an active civ. Dropped `theme_settings`/`region_color` from the login SELECT in [routes/auth.py:158](Haven-UI/backend/routes/auth.py#L158) — verified dead reads via codebase audit (selected but never assigned to session_dict for years). Migration v1.83.0 backfills `user_profiles.enabled_features` for every profile with an active civ membership using the same union logic the runtime helper does. `/api/status` 1.66.1 → 1.67.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). |
| Haven-UI | 1.58.6 | 2026-05-18 | Removed the "Demote" pill button from [UserManagement.jsx](Haven-UI/src/pages/UserManagement.jsx) — it called `PUT /api/admin/profiles/{id}/tier` with `tier: 4`, which now always 409s for users with civ memberships and is a no-op-then-revert pattern that misled super admins. Canonical demotion path is the Civilizations page → Remove Member. Elevate modal's tier 4/5 warning text updated from advisory ("may be overridden") to declarative ("will be rejected with 409"). Build state unchanged — no new dependencies, no new pages, two edits to one file. |
| **Master Haven** | 1.68.1 | 2026-05-18 | Patch: super admin tier elevation was rejected by the backend with `Invalid tier. Must be 2-5.` whenever a super admin tried to promote a user via UserManagement → Change Tier. Root cause: the frontend elevate modal exposes Super Admin (tier 1) as a target tier (correct per the v1.55.0 civ-membership-derived design where partner/sub-admin tiers moved to the Civilizations page), but the validation tuple at [routes/profiles.py:869](Haven-UI/backend/routes/profiles.py#L869) only allowed `{TIER_PARTNER, TIER_SUB_ADMIN, TIER_MEMBER, TIER_MEMBER_READONLY}` — `TIER_SUPER_ADMIN` (=1) was conspicuously absent from the set check, so every tier-1 PUT 400'd. One-line fix: added `TIER_SUPER_ADMIN` to the allowed tuple and updated the error string to "Must be 1-5". All adjacent guards already handle tier 1 correctly with no other changes needed: auth gate requires super_admin session, password gate's `new_tier <= TIER_SUB_ADMIN` already covers tier 1, the else-branch clearing partner/parent fields is the correct behavior for super admin promotion (super admin doesn't need civ-scoped denormalized fields), `_recompute_profile_tier` in civilizations.py uses `WHERE tier != 1` so civ membership changes won't clobber a super admin, and the audit log's `tier_names` dict already has `1: 'Super Admin'`. Trigger context: Parker promoting Watcher (lead diplo) to super admin. **Requires backend restart** on the Pi (uvicorn not running with --reload per CLAUDE.md). |
| Backend API | 1.66.1 | 2026-05-18 | See Master Haven 1.68.1 above. One-line validation fix at [routes/profiles.py:869](Haven-UI/backend/routes/profiles.py#L869) in `PUT /api/admin/profiles/{id}/tier`: `TIER_SUPER_ADMIN` added to the allowed tier set, error string updated 2-5 → 1-5. `/api/status` 1.66.0 → 1.66.1 in [routes/auth.py](Haven-UI/backend/routes/auth.py). |
| **Master Haven** | 1.68.0 | 2026-05-16 | **Layered map navigation + cross-layer focus highlighting.** The map was three disjoint static pages with no memory of context across layers — clicking "View on Map" from anywhere dropped you at a leaf with no breadcrumb back. Now: unified `?focus=<type>:<id>` URL contract on all 3 map pages (galaxy / region / system). Each page parses the param, finds the matching entity, applies the existing pulsing-ring + auto-pan (reused from the search-result code path, identical visual). Persistent breadcrumb bar on every map page with `↑ Galaxy` / `↑ Region` up-links that carry the current entity as focus so the parent layer arrives with that entity highlighted. **Down-navigation already worked** (click region → enter region, click system → enter system) — only the up-navigation + the focus-pulse-on-arrival were missing. **Civ / Contributor view-on-map**: galaxy view fetches `/api/map/regions-aggregated?focus_civ=X` (or `focus_user=Y`) — backend returns ALL regions with a new `is_focused: bool` flag, frontend hides non-focused by default and shows their territory only, with a `🎯 civ: ARCH [Show all regions] [✕]` chip overlay that toggles the filter or clears it entirely. **Search popover map buttons**: every result row in `SearchOverlay` now has a small `🗺` icon on the right that opens the matching map page focused on that entity — system → `/map/system/{id}`, region → `/map/region?rx=&ry=&rz=`, civ → `/map/latest?focus=civ:TAG`, contributor → `/map/latest?focus=user:NAME`. Row click stays as-is (navigates to the React detail page). **SystemDetail sister buttons**: the single "Show on Map" button became three side-by-side buttons (`⭐ System Map` / `📍 Region Map` / `🌌 Galaxy Map`), each carrying the right focus param so the user lands at any layer with the smoke-test system pulsing. **Bread-and-butter detail**: discovered mid-implementation that `vite build` copies `public/*.html` → `dist/*.html`, clobbering any edits to the dist copies. The 3 map HTML files live in `public/` as the source of truth; dist is the build output. Edits now made in public/ and propagated to dist/ via cp post-build. **13 live HTTP tests pass** against the running backend: focus param parsing, civ/user filter, unknown-civ false-positive guard, baseline-no-focus correctness, all 4 focus URL shapes on /map/latest, region page accepts focus=system:ID, system page accepts focus=planet:ID, SearchOverlay map buttons wired, SystemDetail sister buttons wired. |
| Backend API | 1.66.0 | 2026-05-16 | `/api/map/regions-aggregated` ([routes/systems.py](Haven-UI/backend/routes/systems.py)) now accepts `?focus_civ=<tag>` and `?focus_user=<username>` query params. Adds an `is_focused: bool` field to every returned region — true when that region contains systems matching the civ/user filter, false otherwise (always present even with no filter). Response envelope gains `focus_active: bool`, `focus_civ`, `focus_user` for client-side state. Implementation: pre-computes the focused (rx,ry,rz) set with one DISTINCT query before the main aggregation loop, then does O(1) tuple lookup per region. No SQL filter on the main query — the full region list is returned so the frontend toggle can switch between "show only focused" and "show all" without a re-fetch. `/api/status` 1.65.1 → 1.66.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). |
| Haven-UI | 1.58.0 | 2026-05-16 | Map focus + breadcrumb rebuild across 3 static HTML files + 2 React components. [public/VH-Map-ThreeJS.html](Haven-UI/public/VH-Map-ThreeJS.html): `parseMapFocus()`, `focusOnRegionCoords()` (reuses existing `highlightSystem` pulse-ring + `focusOnSystem` camera pan), `mapFocusFilterEnabled` state with `toggleMapFocusFilter()` / `clearMapFocus()`, `updateFocusFilterChip()` for the floating civ/user chip overlay. URL builder for `/api/map/regions-aggregated` includes `focus_civ` / `focus_user` from URL param. Region render loop respects `is_focused` flag when filter is on. Galaxy system-count display switches between filtered/total. System count chip overlay above the existing controls. [public/VH-Map-Region.html](Haven-UI/public/VH-Map-Region.html): `getRegionFromURL()` extended to parse `?focus=system:<id>` shape (routes through existing `highlightSystemId` path), `dropFocusPulseRing()` for the cross-layer-consistent pulse, persistent `#map-nav-bar` breadcrumb with `↑ Galaxy` link carrying current region as focus. [public/VH-System-View.html](Haven-UI/public/VH-System-View.html): `parseSystemFocus()` + `dropFocusPulseRing()` + `applySystemFocus()` IIFE in init that finds matching planet/moon by `userData.data.id` and pulses it. Breadcrumb with `↑ Galaxy` (carries `focus=region:rx,ry,rz`) + `↑ Region` (carries `focus=system:ID`). [SearchOverlay.jsx](Haven-UI/src/components/SearchOverlay.jsx): `buildMapHref()` per category, `SearchRow` refactored from `<button>` to flex `<div>` with two clickable regions (row body + `🗺` map-icon link). [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx): single Show-on-Map button replaced with three sister buttons in both `block` and `ghost` variants. **`vite build` copies `public/` over `dist/`** — public is source of truth, dist is build output. After editing public, run `cp public/VH*.html dist/` to propagate without a full rebuild. Build clean in 11.80s. |
| **Master Haven** | 1.67.1 | 2026-05-16 | Pre-deploy audit patch — 5 issues caught by a final-pass audit combining code review + live HTTP tests against the running backend before the Pi push. **Backend (live-test catches):** (1) `/api/systems/search` now 2-char minimum on free-text queries — single keystroke previously returned 20 noise rows of partial matches across name/glyph/galaxy/region/community/contributor columns. Glyph-shaped queries (≥11 hex chars) and NMSPortals URLs bypass the guard since they hit indexed exact-match paths. Matches the existing `/api/search` popover guard. (2) `_NMSPORTAL_RE` regex extended from `nmsportals?\.com` to also accept `nmsportals?\.(?:github\.io\|com)` — the live NMSPortals site is `nmsportals.github.io`, the `.com` form was never registered. Pasting a real share URL silently fell back to free-text LIKE which doesn't match the URL-shaped string; now extracts the embedded glyph as intended. **Frontend (agent catches):** (3) `restoreDraft()` now sets `userEditedNameRef.current = true` if the restored snapshot has a name — without this, restoring a draft then changing reality/galaxy let `/api/namegen` overwrite the user's typed-and-saved name. (4) `handleSubmitAnother` now preserves `game_mode` alongside reality/galaxy/discord_tag/coauthors/expedition/game_version — Submit Another was silently resetting difficulty to Normal between submissions even though the user is still in the same NMS session. (5) `FilterModal.SelectField` now shows `(no options)` placeholder + disables the dropdown when the option array is empty for ANY field (was only wired for Resources) — fulfills the v1.66.0 spec promise across Biome / Weather / Sentinel / Stellar Class / Lifeform / Economy Type. **Live test coverage:** 17 HTTP tests against `/api/systems`, `/api/systems/search`, `/api/search`, `/api/systems/filter-options`, `/api/regions/grouped`, `/api/galaxies/summary` — all pass post-fix. Combined with the v1.67.0 end-to-end smoke test (submission → pending → approve → systems → DB round-trip) this represents the most thorough pre-deploy validation pass to date. |
| Backend API | 1.65.1 | 2026-05-16 | Two backend fixes from pre-deploy live HTTP tests. `_NMSPORTAL_RE` in [routes/systems.py](Haven-UI/backend/routes/systems.py) extended to match `nmsportals.github.io` (the actual live site) in addition to the historical `.com` form — pasted share URLs now extract their 12-char glyph as intended. `/api/systems/search` ([routes/systems.py:1177](Haven-UI/backend/routes/systems.py#L1177)) now rejects free-text queries shorter than 2 characters, matching the existing `/api/search` popover guard ([routes/systems.py:1416](Haven-UI/backend/routes/systems.py#L1416)). Glyph-shaped queries (≥11 hex chars) and nmsportal URLs bypass the guard since they hit indexed exact-match paths. `/api/status` version 1.65.0 → 1.65.1 in [routes/auth.py](Haven-UI/backend/routes/auth.py). |
| Haven-UI | 1.57.1 | 2026-05-16 | Three frontend fixes from pre-deploy audit. [Wizard.jsx:restoreDraft](Haven-UI/src/pages/Wizard.jsx) now sets `userEditedNameRef.current = true` when the restored snapshot has a name — closes the gap where restoring a draft then changing reality/galaxy let `/api/namegen` overwrite the user's saved name. [Wizard.jsx:handleSubmitAnother](Haven-UI/src/pages/Wizard.jsx) preserves `game_mode` across resets — was silently dropping the player's difficulty selection between submissions. [FilterModal.jsx:SelectField](Haven-UI/src/components/FilterModal.jsx) renders `(no options)` placeholder + disables the `<select>` when the option array is empty for any field — previously only wired for Resources, so the other 5 scoped dropdowns (Biome / Weather / Sentinel / Stellar Class / Lifeform / Economy Type) deceptively claimed "Any X" against an empty list. Resources dropdown's now-redundant per-field placeholder simplified to match. Build clean in 10.76s. |
| **Master Haven** | 1.67.0 | 2026-05-16 | Wizard / Create page audit + fix pass across 3 phases. **Phase 1 (data-loss stops):** auto-namegen no longer overwrites a user-typed System Name — gated behind a `userEditedNameRef` that flips on first keystroke (was triggering on every reality/galaxy change + every type→erase→retype loop because the stale `_lastProceduralName` sentinel matched empty / matched-procgen states). `game_mode` finally exposed in the UI — wizard never sent it before, so every wizard submission silently landed as Normal regardless of player difficulty. Edit-mode hydration now loads live discoveries into a read-only sidecar panel in SectionDiscoveries (previously empty, editors couldn't see what was attached). `toggleStation(true)` restores the loaded `space_station` from `originalStationRef` instead of stamping `<system> Station / Gek / default goods` over a real loaded station. `pullExistingIntoForm` now pops a per-field confirm naming every populated field that would be overwritten — silent 11-field clobber on "Pull existing data" eliminated. Wizard validation blocks duplicate planet/moon names (root cause of `_promote_draft_discoveries` `setdefault` orphan-link bug — second body with same name lost its discoveries to NULL FK). **Phase 2 (approver visibility — the "stuff disappears" complaint):** SystemApprovalTab now renders four system-header fields that were previously invisible to approvers (`submitter_notes`, `coauthors`, `expedition_id`, `proposed_region_name`); Wonders Page Notes (5 fields × planet + moon: `estimated_age`, `core_element`, `lore_notes`, `root_structure`, `nutrient_source`) rendered as a collapsed amber subsection on each body card when populated; `CoSubmittedDiscoveriesPanel` expanded to surface `photo_url`, `evidence_urls`, and `type_metadata` so approvers see all attached evidence; CelestialBodyEditor `SHARED_ATTRIBUTES` got 4 missing moon toggles (`ancient_bones`, `salvageable_scrap`, `storm_crystals`, `gravitino_balls`) — backend has the columns since v1.65.0 but UI only exposed them on planets. **Phase 3 (UX polish):** region name validation now requires Discord username (else attribution lost); edit-mode validation skips required-field checks on fields the user didn't change (legacy systems missing required fields no longer block small fixes); FastAPI validation errors flattened from `[object Object]` to `field.path: message • field.path: message`; SystemDetail renders new "Unlinked" group for discoveries with `location_type='planet'|'moon'` but NULL FK link (was masquerading as "in space"); coauthor `credited_at` + `profile_id` metadata preserved on edit round-trip via `originalCoauthorsRef`. **Backend change requires uvicorn restart**: `/api/systems/{id}` SELECT now includes `d.location_type` so the orphan badge can distinguish broken links from intentional space discoveries. |
| Backend API | 1.65.0 | 2026-05-16 | `/api/systems/{system_id}` ([control_room_api.py:2284](Haven-UI/backend/control_room_api.py#L2284)) discoveries SELECT extended to include `d.location_type` alongside `d.planet_id` / `d.moon_id` — required for SystemDetail.jsx to differentiate orphaned discoveries (intent was planet/moon but link is NULL because name didn't resolve at approval time) from intentional space discoveries. Pure read-side change, no schema migration, no INSERT-path impact. `/api/status` version 1.64.0 → 1.65.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). **Requires backend restart** (uvicorn not running with --reload per CLAUDE.md). |
| Haven-UI | 1.57.0 | 2026-05-16 | See Master Haven 1.67.0 above for full Phase 1-3 breakdown. Touches: [src/pages/Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) (largest — userEditedNameRef + originalStationRef + originalCoauthorsRef refs, game_mode in EMPTY_SYSTEM + SectionAttrs dropdown, existingDiscoveries hydration + read-only panel in SectionDiscoveries, toggleStation preservation, pullExistingIntoForm confirm, duplicate-body-name validation, edit-mode `editPreserved()` validation gate, region-name attribution check, FastAPI error prettifier, coauthor metadata merge in buildPayload), [src/pages/SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) (Unlinked group in SystemDiscoveriesList), [src/components/approvals/SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx) (Wizard Submission Extras panel, Wonders Page Notes block in renderBodyFields + moon inline render, CoSubmittedDiscoveriesPanel evidence expansion), [src/components/CelestialBodyEditor.jsx](Haven-UI/src/components/CelestialBodyEditor.jsx) (4 new moon attributes in SHARED_ATTRIBUTES), [src/components/PlanetEditor.jsx](Haven-UI/src/components/PlanetEditor.jsx) (moon init sync). Build clean in 10.53s. Vite HMR serves all edits live without page reload. |
| **Master Haven** | 1.66.0 | 2026-05-15 | Systems Tab search + filter rebuild (Tiers A-E from the 2026-05-15 audit). **Filters:** FilterModal was reading `options.lifeforms` / `options.sentinels` but the backend returns `dominant_lifeforms` / `sentinel_levels` — every dropdown silently fell back to a hardcoded list containing stale values like sentinel "Low" that the extractor never writes. Fixed the key reads. Dropped all hardcoded fallback lists so dropdowns reflect actual DB content (or show "(no options)" if scope is empty). Added Weather + Stellar Classification controls — backend already supported them; UI never exposed them. Replaced the Resource text input (which placeholder-promised free-text but did exact-match SQL → typing "indium" returned 0) with a `SearchableSelect` driven by `options.resources`. FilterModal also now scopes its option fetch to current reality + galaxy. Deleted the orphaned `AdvancedFilters.jsx` (no caller). **Search:** placeholder always claimed "name, glyph code, contributor, or community" but the backend only matched name + glyph + galaxy + description. Extended `/api/systems/search` WHERE to also OR-span `r.custom_name` (region name — already joined for display, just unused), `s.discord_tag` (community tag), `s.discovered_by` + `s.personal_discord_username` (contributor on the row), plus an EXISTS subquery against `system_coauthors.username_normalized` for multi-author submissions. Added a glyph-shape detector (`^[0-9A-Fa-f]{11,12}$` and NMSPortals URL extraction) that routes glyph queries through the indexed `glyph_code` / `glyph_code_suffix` path instead of substring LIKE — faster and avoids spurious description matches. Each result row gets a `match_reason` field naming the winning column so the UI can render "matched on community/region/contributor" chips. **New `/api/search` endpoint** returns a categorized envelope `{communities, regions, contributors, systems, totals}` powering the rebuilt SearchOverlay popover: 4 separate sections, each ≤6 results in the popover, click-through routes to the entity's native page. Communities use `civilizations` as canonical source with a secondary pass picking up unregistered `discord_tag` values from `systems`. Contributors merge `user_profiles` rows with anonymous submitter strings. **Filter + Search compose** — every search request includes the active filters (`...apiParams`); when `q` is set, `SystemsList` switches from `/api/systems` to `/api/systems/search` so the grid view applies both. **URL-as-source-of-truth** — `q` now lives in URL state alongside hierarchy + filters, so refresh / share / Back button all preserve the search query. **New `/search` page** at `/search?q=...` is the "View all" target from the popover — full per-category sections with deep-link routing. Keyboard nav in the popover (`↑↓` walk results across categories, `↵` activates, `Esc` closes, `/` focuses the input from anywhere). Search-query chip added to `FilterPillsRow` (amber-tinted to distinguish from teal filter pills) so users have one consistent place to see + remove every active constraint. |
| Backend API | 1.64.0 | 2026-05-15 | New `/api/search` endpoint at [routes/systems.py](Haven-UI/backend/routes/systems.py) returning categorized `{communities, regions, contributors, systems, totals}` envelope. Communities sourced from `civilizations WHERE is_active = 1` (canonical, v1.80.0+) with LEFT JOIN system counts and a secondary pass over `systems.discord_tag` for unregistered tags. Regions matched by `r.custom_name LIKE` scoped by reality/galaxy. Contributors merge `user_profiles` rows with DISTINCT anonymous `systems.discovered_by` / `personal_discord_username` (only for `profile_id IS NULL` rows, to avoid double-counting). Systems reuse the same multi-column WHERE the rewritten `/api/systems/search` uses. **`/api/systems/search` rewrite:** new `_parse_search_query()` helper detects glyph-shaped queries (12-char hex → full match, 11-char hex → `glyph_code_suffix` indexed match from migration v1.73.0, NMSPortals URL → extract embedded glyph). WHERE clause extended to OR-span `r.custom_name`, `s.discord_tag`, `s.discovered_by`, `s.personal_discord_username`, and `EXISTS (... system_coauthors ...)` alongside the existing name/glyph/galaxy columns. New `_compute_match_reason()` annotates each row with `{kind, snippet}` so the frontend can render "matched on contributor/community/region" chips without re-checking strings. Description-column LIKE removed from the free-text WHERE (was producing spurious matches; description field was repurposed in v1.50.12 for procgen-name stashing). All advanced filters compose AND with the search WHERE. Response shape gains `parsed_kind` so the UI can show "NMSPortals link" / "glyph" badges. `/api/status` version 1.63.0 → 1.64.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). |
| Haven-UI | 1.56.0 | 2026-05-15 | **FilterModal fixes** ([src/components/FilterModal.jsx](Haven-UI/src/components/FilterModal.jsx)): `options.lifeforms` → `options.dominant_lifeforms`, `options.sentinels` → `options.sentinel_levels`. Dropped every hardcoded fallback list (`['Low','Standard','High','Aggressive','Frenzied','None']` etc.) — empty options now show "(no options)" placeholder. Added `Weather` control under Planet Properties and `Stellar Classification` control under new Star Class section. `Resource` field changed from `<input type="text">` to `SelectField` reading `options.resources`. FilterModal option fetch now scoped by current `reality` + `galaxy` so dropdowns shrink to in-scope values. Removed dead `lowsentinel` preset (referenced the bogus "Low" value). **SearchOverlay rebuilt** ([src/components/SearchOverlay.jsx](Haven-UI/src/components/SearchOverlay.jsx)): hits `/api/search` instead of `/api/systems/search`, renders 4 categorized sections (Communities / Regions / Contributors / Systems) with section headers showing counts. Click-through routes by kind: community → `/community-stats/<tag>`, region → drills into Systems browser with reality/galaxy/region pre-set, contributor → re-searches by their name in the new `/search` page, system → `/systems/<id>`. Local input state is URL-synced via `SystemsContext.q` after a 300ms debounce. Keyboard nav: `↑↓` walks all rows across sections, `↵` activates the highlighted row, `Esc` closes, `/` focuses input from anywhere. Match-reason snippets (`matched on contributor: ekimo`) shown on system rows when the win column wasn't the system name. **SystemsList composes** ([src/components/SystemsList.jsx](Haven-UI/src/components/SystemsList.jsx)): when `q` is set, switches from `/api/systems` to `/api/systems/search` so the grid view filters by both `q` AND active filters simultaneously. **SystemsContext** ([src/contexts/SystemsContext.jsx](Haven-UI/src/contexts/SystemsContext.jsx)): added `q` as a URL-synced reserved key alongside hierarchy params. `setFilters` and `writeHierarchy` both preserve `q` on transitions so navigating between regions / changing filters doesn't drop the search query. **FilterPillsRow** ([src/components/FilterPillsRow.jsx](Haven-UI/src/components/FilterPillsRow.jsx)): renders an amber search-query pill alongside teal filter pills; "Clear all" clears both. **New `/search` page** at [src/pages/Search.jsx](Haven-UI/src/pages/Search.jsx): the "View all" target from the popover. Full per-category sections (24 rows each), search input persists across refresh via URL `?q=`. Wired into [src/App.jsx](Haven-UI/src/App.jsx) routing. Deleted orphan [src/components/AdvancedFilters.jsx](Haven-UI/src/components/AdvancedFilters.jsx) — no caller in the repo (Systems.jsx mounts FilterModal). |
| **Master Haven** | 1.65.0 | 2026-05-15 | Full-website audit + fix pass across 7 phases. Audit report at [AUDIT_REPORT_2026-05-13.md](AUDIT_REPORT_2026-05-13.md) — ~125 findings, 13 CRITICAL fixed in this release. **Phase 1 (security + silent loss):** `/api/keys*` super-admin gated (was any-admin); SQLite FK PRAGMA enabled (every `ON DELETE CASCADE` in the schema was dead code); `submit_system` INSERT now includes `glyph_code`/`reality`/coords/`region_*`/`game_mode` so wizard pending rows have indexed `glyph_code_suffix` (broken dedup hit every wizard submission); `GET /api/pending_systems/{id}` and `GET /api/pending_discoveries/{id}` now community-scoped (partner could iterate IDs to read other civs' submissions); `discoveries_draft` no longer dropped in profile-claim flow (v1.64.0 fix only covered the happy path — modal-resubmit lost the array); partner self-elevation via `PUT /api/admin/profiles/{id}` blocked; legacy partner NULL==NULL match guarded; region single-approve/reject got self-check + non-empty reason; region batch reject same; `/api/pending_edits/*` actually applies the edit + audit logs (was approve-no-op + literal `'super_admin'` reviewer string); `/api/discord_tag_colors` reads from `civilizations`; analytics endpoints' cross-community leak closed via `_scope_analytics_discord_tag()`. **Phase 2:** `check_self_submission()` no longer exempts partners (leaderboard-fraud risk); `reject_discovery` uses canonical helper. **Phase 3:** SystemDetail now renders game_mode badge, completeness_breakdown panel, space_station card, system discoveries list, is_stub banner+badge — all features the prior changelog claimed shipped but the file never had; `adjectiveColors.js` actually imported (was dead code); Show on Map button → `/map/latest`; RegionDetail threads reality+galaxy through queries; backend `/api/regions/.../systems` accepts reality+galaxy; Discoveries quick-search SPA-nav to `/discoveries/all`; `/api/discoveries/browse` got 2-char minimum guard. **Phase 4 (DB column drift):** `save_system` moon INSERT now has 8 fields it dropped (biome/biome_subtype/weather/planet_size/common/uncommon/rare/plant_resource); `save_system` system INSERT+UPDATE set `game_mode`; `approve_system` UPDATE on edit sets `game_mode`; `batch_approve` UPDATE adds `game_version`/`expedition_id`/`game_mode`; batch new-system INSERT adds `game_version`/`expedition_id`; `/api/extraction` planet_entry passes through 16+ additional fields it dropped; approve_system DELETEs existing space_station before INSERT on edit. **Phase 5:** `PUT /api/partner/region_color` dual-writes to `civilizations.region_color` (canonical) AND legacy `partner_accounts.region_color`; `GET /api/partner/region_color` reads civilizations first; Profile.jsx default-civ dropdown uses `/api/discord_tags` (was `/api/communities`); civilization tag uniqueness case-insensitive. **Phase 6 (mobile):** SearchableSelect `minWidth: min(280px, calc(100vw - 32px))`; hub pages negative margin scoped per breakpoint; WarRoom war-goal grid 5→2/3/5; WarRoom command tab header flex-wrap + sm: stacking; WarMap3D drill-down becomes bottom sheet on phone; WarRoom DECLARE WAR modal gets backdrop padding + overflow-y-auto; CSV Import column-mapping rows wrap on phone; Navbar mobile menu `max-h-[80vh] overflow-y-auto`. **Phase 7:** `adjectiveColors.js` tier sets extended with live values (Plentiful, Vibrant, Bountiful, Lavish, Brutal, Patrolling, etc.); audit-log Source dropdown drops dead `companion_app`, adds `keeper_bot`; SystemsList star pill class whitelisted so legacy `Unknown(N)`/`White` rows don't generate invalid CSS. **Known follow-ups:** War Room enrollment migration to civilizations key (large surface, 67 routes); CSV import planet INSERT column-list sync (drops 40+ fields). |
| Backend API | 1.63.0 | 2026-05-15 | See Master Haven 1.65.0 above for the full Phase 1-7 audit-fix breakdown. Touches db.py + 10 route modules + control_room_api.py + auth_service.py. Foreign-key PRAGMA + 8 INSERT-path column-list alignments are the largest blast-radius items. |
| Haven-UI | 1.55.0 | 2026-05-15 | SystemDetail wired up to render the 4 features the prior changelog claimed it had but never wired (game_mode, completeness_breakdown, space_station, discoveries). adjectiveColors.js imported into planet/moon stat cells. is_stub banner + badge. Show on Map routes to real path. RegionDetail accepts reality+galaxy URL params. Mobile fixes per Phase 6. See Master Haven 1.65.0 for the full breakdown. |
| **Master Haven** | 1.64.0 | 2026-05-13 | Wizard discoveries co-submission fix. The wizard's public (member/anonymous) submit path was building a discoveries array in section 05 and then **silently dropping it** — the post-submit code just counted entries into a `deferred_discoveries` field for the success screen and never POSTed them. The intent comment said "discoveries are deferred — added once the system is approved" but no backend mechanism for that ever existed. Members who tagged a discovery to a planet/moon while uploading their system saw the system land in the queue and the discoveries vanish. Fix is Option B from the audit: discoveries ride along on the pending row as a JSON array on the new `pending_systems.discoveries_draft` column, and on approval a backend helper resolves planet/moon names against the just-inserted planets/moons and inserts directly into the live `discoveries` table with status='approved'. Names are the join key (DB IDs don't exist at submit time since planets are still inside the system_data blob). Admin direct-save path (which does have a real system_id immediately) keeps using the existing `submitDiscoveries()` round-trip — no change there. Reviewer sees a "Co-submitted discoveries (N)" panel in the review modal so they know what they're auto-approving. Cap at 20 entries; 400 on invalid shape so silent drops can't recur. |
| Backend API | 1.62.0 | 2026-05-13 | New migration v1.82.0 adds nullable `pending_systems.discoveries_draft TEXT` column. `/api/submit_system` ([routes/approvals.py](Haven-UI/backend/routes/approvals.py)) accepts optional `discoveries_draft` array on the payload; `_sanitize_discoveries_draft()` validates shape (≤20 entries, required name+type, location_type ∈ {planet,moon,space}, location_type='space' nullifies any leaked planet/moon names), returns 400 on violation. Sanitized list stored as JSON in the new column (also popped from the system_data blob so it's not double-stored). New `_promote_draft_discoveries(cursor, system_id, submission, current_username)` helper runs inside the same transaction as the system/planet/moon inserts in both `approve_system` and the batch worker `_process_batch_approvals_sync`, after `update_completeness_score()` and before the `UPDATE pending_systems SET status='approved'`. Resolves `planet_name` against the system's just-inserted planets and `(planet_name, moon_name)` against the planet→moons join — NULL link + warning log on unresolved names. Each promoted draft becomes one `discoveries` row with `analysis_status='approved'`, inheriting `discord_tag`, `discord_username`, `submitter_profile_id`, and `source` from the parent pending row, plus a `discovery_auto_approved_with_system` audit row. `/api/status` 1.61.0 → 1.62.0. |
| Haven-UI | 1.54.0 | 2026-05-13 | [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) public submit path now builds a `discoveries_draft` array via new `buildDiscoveryDraftEntry()` helper and attaches it to the `/api/submit_system` payload (cap 20, matching backend). Helper resolves the wizard's synthetic `planet-N` / `<planet>::<moon>::<idx>` picker IDs back to real planet/moon names by walking `system.planets` local state — those synthetic IDs were `NaN`-coerced to `null` previously, so even the dead-pre-1.64.0 path wouldn't have linked correctly. Dead `deferred_discoveries` counter renamed to `submitted_discoveries` (now actually true). Admin direct-save path untouched. [SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx) gets a new `CoSubmittedDiscoveriesPanel` component rendered between system info and action buttons in the review modal: parses `selectedSubmission.discoveries_draft`, lists each entry's name/type/target with a "Auto-approved with the system" header chip and a footer note about NULL-link fallback semantics. |
| **Master Haven** | 1.62.0 | 2026-05-13 | Super-admin page consolidation. Three new tabbed hub pages added alongside existing single-purpose pages — additive merge, zero behavior duplication. `/analytics-hub` consolidates Analytics + PartnerAnalytics + Events into one tabbed shell (Overview / By Source / Events). `/admin/access` consolidates UserManagement + SubAdminManagement + ExtractorUsers + ApiKeys into one tabbed shell (Users / Sub-Admins / Extractor Users / API Keys). `/admin/tools` extracts destructive operations (DB backup, hub-tag migration) out of `/settings` so they don't sit next to personal preferences. All original routes remain mounted unchanged — the new hubs are additive, lazy-loaded, and compose the existing pages so zero behavior is branched. Navbar dropdowns now surface the new hubs at the top (marked with ★) and individual pages as "— Indented" entries below. New Governance dropdown for super admins surfaces Data Restrictions + Audit Log. Settings.jsx trimmed: removed the dead `doBackup` / `migrateHubTags` handlers + the two ops sections; added a one-line pointer to /admin/tools for super admins. Known v1 limitation: embedded child pages still render their own `min-h-screen p-6` containers and headers inside the hub shell, so you'll see two layers of chrome — the hub wrapper uses `-mx-6 -mt-6` to claw back outer padding; full chrome-stripping (via an `embedded` prop on each child page) is a follow-up. |
| **Master Haven** | 1.63.0 | 2026-05-13 | Community-overview source consolidation — extends the v1.61.0 civ-dropdown fix to the public stats page. The `/community-stats` page was showing fewer "communities" than `/admin/civilizations` because the two read from different sources: civilizations table (canonical, 41 active rows locally) vs. distinct discord_tags in the systems table (31 distinct tags). Result: civs newly created via CivilizationManagement that haven't received any submissions yet were invisible on the public stats page, and the case-split between `Personal` and `personal` was being shown as two separate communities. Fixed in [Haven-UI/backend/routes/analytics.py](Haven-UI/backend/routes/analytics.py) by rewriting `/api/public/community-overview` to source the civ roster from `civilizations WHERE is_active = 1` (same source CivilizationManagement uses), LEFT JOIN aggregates from `systems` / `discoveries` / `pending_systems`. Civs with zero submissions now appear with zero stats so the two pages always agree on the civ count. The synthetic `Personal` row is now a single consolidated bucket (normalizer maps NULL/''/'personal'/'Personal' all to one). Orphan tags in the systems table that don't match any civilizations row (e.g. local DB has 8 systems tagged `UFE` with no matching civ) are surfaced as `<tag> (unregistered)` at the bottom of the list so they're not silently dropped. Backend version bumped 1.60.0 → 1.61.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). Requires a backend restart (uvicorn is not running with --reload). |
| Backend API | 1.61.0 | 2026-05-13 | `/api/public/community-overview` rewritten: SQL `FROM civilizations WHERE is_active = 1` is now canonical (matches `/api/civilizations` source), LEFT JOIN aggregates from systems / discoveries / pending_systems. Adds a single consolidated `Personal` synthetic row + an orphan-tag tail so no data silently disappears. Response shape unchanged — same `{communities: [...], totals: {...}}` envelope with the same per-row keys (`discord_tag`, `display_name`, `total_systems`, `total_discoveries`, `unique_contributors`, `manual_systems`, `extractor_systems`). CommunityStats frontend needs no change. Display names sourced from `civilizations.display_name` instead of stale `partner_accounts.display_name` — same upgrade path as the v1.60.0 civ-dropdown fix. |
| Haven-UI | 1.53.1 | 2026-05-13 | Hub appearance + navbar cleanup follow-up to 1.53.0. **Chrome dedup:** added an `embedded` prop to all 7 pages composed inside hubs ([Analytics.jsx](Haven-UI/src/pages/Analytics.jsx), [PartnerAnalytics.jsx](Haven-UI/src/pages/PartnerAnalytics.jsx), [Events.jsx](Haven-UI/src/pages/Events.jsx), [UserManagement.jsx](Haven-UI/src/pages/UserManagement.jsx), [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx), [ExtractorUsers.jsx](Haven-UI/src/pages/ExtractorUsers.jsx), [ApiKeys.jsx](Haven-UI/src/pages/ApiKeys.jsx)). When `embedded={true}`, each page skips its outer `min-h-screen p-6` wrapper and its own page-title block (the hub provides them). Filters and action buttons stay visible. Both hubs now pass `embedded` on their child mounts and wrap the tab body in a single shared `<div className="p-6">` so all three hubs (AnalyticsHub, AccessControl, AdminTools) have identical inner padding. [AdminTools.jsx](Haven-UI/src/pages/AdminTools.jsx) restyled with the same hub-header bar pattern as the other two so the three pages look uniform. **Navbar cleanup:** the v1.53.0 navbar kept the old single-purpose pages as `— Indented` entries below each hub — that was clutter, not consolidation. v1.53.1 removes them entirely. The dropdown groups now read: Analytics → (Analytics Hub, DB Stats); Admin → (Approvals, Access Control, CSV Import, Settings); Governance → (Data Restrictions, Audit Log); Super Admin → (Civilizations, Admin Tools). The legacy URLs (`/analytics`, `/partner-analytics`, `/events`, `/admin/users`, `/admin/sub-admins`, `/admin/extractors`, `/api-keys`) are still mounted in [App.jsx](Haven-UI/src/App.jsx) so deep links and bookmarks still resolve — they're just no longer in the navbar. Build clean in 11.64s. |
| Haven-UI | 1.53.0 | 2026-05-13 | Three new admin hub pages: [AnalyticsHub.jsx](Haven-UI/src/pages/AnalyticsHub.jsx), [AccessControl.jsx](Haven-UI/src/pages/AccessControl.jsx), [AdminTools.jsx](Haven-UI/src/pages/AdminTools.jsx). Each hub uses `useSearchParams` so deep links survive (`/analytics-hub?tab=events`, `/admin/access?tab=sub-admins`). Each child page is `lazy()`-imported so only the active tab compiles. Navbar's `NAV_GROUPS` reorganized in [Navbar.jsx](Haven-UI/src/components/Navbar.jsx): hubs at top (★ Analytics Hub / ★ Access Control / ★ Admin Tools), individual pages indented underneath as `— Label`. New Governance dropdown for super admins. Settings.jsx trimmed: backup + migration sections removed (moved to AdminTools); dead handlers + `migrating` state removed. All original routes preserved as alias paths in [App.jsx](Haven-UI/src/App.jsx). Bundle: 3 new chunks (AnalyticsHub-ChF_yoyf.js, AccessControl-BUxAZyDh.js, AdminTools-Do6NlTi6.js); production build clean in 13.31s with zero errors. |
| **Master Haven** | 1.61.0 | 2026-05-13 | Civ-dropdown source consolidation. The new `CivilizationManagement` page (added with the v1.80.0 `civilizations` table migration) writes to `civilizations.tag`, but the three endpoints that power every civ/community dropdown in the app — `/api/discord_tags` (used by Wizard, PendingApprovals, Analytics, Events, ApprovalAudit, ApiKeys, PartnerAnalytics, RegionDetail, DiscoverySubmitModal), `/api/communities` (used by the Haven Extractor mod + Profile.jsx), and `/api/available_discord_tags` (used by SubAdminManagement) — were still UNION-ing legacy `partner_accounts.discord_tag` and `user_profiles.partner_discord_tag` and didn't query `civilizations` at all. Net effect: any civ created via the new page was invisible everywhere (Wizard dropdown, in-game extractor, sub-admin assignment) until you also manually created legacy table rows. Fix consolidates all three endpoints to read from a single source: `SELECT tag, display_name FROM civilizations WHERE is_active = 1`. Backfill from v1.80.0 already seeded `civilizations` with every legacy civ (verified live against the Pi: 41 active rows including Haven, GHUB, IEA, Everion, plus the new HRCC). Legacy hardcoded "Haven" prefix entry in `/api/discord_tags` dropped since it's a real `civilizations` row now; "Personal (Not affiliated)" remains hardcoded since it's a non-civ option. Response shapes preserved for all three endpoints — zero frontend changes, zero extractor changes (auto-picks up next mod load via the existing dynamic-communities flow from v1.6.0). |
| Backend API | 1.60.0 | 2026-05-13 | `/api/discord_tags` ([control_room_api.py:1950](Haven-UI/backend/control_room_api.py#L1950)), `/api/communities` ([routes/extractor.py:377](Haven-UI/backend/routes/extractor.py#L377)), and `/api/available_discord_tags` ([routes/partners.py:664](Haven-UI/backend/routes/partners.py#L664)) all rewritten to query `SELECT tag, display_name FROM civilizations WHERE is_active = 1`. Removed UNION arms against `partner_accounts` and `user_profiles.partner_discord_tag` — migration v1.80.0's backfill (verified live on Pi: 41 active civilizations rows) already covers every legacy civ. Removed hardcoded "Haven" prefix entry from `/api/discord_tags` (real row in `civilizations` now); kept hardcoded "Personal (Not affiliated)" entry there since it's a non-civ option. Response keys unchanged per endpoint (`tag`/`name` for the first two, `discord_tag`/`display_name` for the third) so no caller breaks. |
| **Master Haven** | 1.60.0 | 2026-05-12 | Three-layer fix for the `RealityMode.Normal` phantom-reality bug discovered on production by Parker on 2026-05-12 (50 systems showing as a third reality card alongside Normal + Permadeath in the Systems Browser). **Layer 1 — Extractor source** (1.9.7 → 1.9.8): pymhf's DearPyGUI sometimes round-trips ENUM gui_variables back as the Python `repr` string ("RealityMode.Normal") instead of as the enum instance. The old `reality_mode` / `community_tag` setter fallback `str(value) if not isinstance(...)` persisted that bad string verbatim into `config.json` and every submission payload. New `_normalize_reality()` / `_normalize_community_tag()` module-level helpers strip the enum-class prefix and validate against known values; setters now route through them. Module-init also scrubs `USER_REALITY` / `USER_DISCORD_TAG` at config load so any pre-existing bad config self-heals on next mod load. **Layer 2 — Backend intake guard** (1.58.0 → 1.59.0): new `normalize_reality()` in `constants.py` applied at all 6 reality-read sites in `routes/approvals.py` (`/api/submit_system`, `/api/check_glyph_codes`, `/api/extraction`, region-name approval) and `routes/regions.py` (`PUT /api/regions/{rx}/{ry}/{rz}`, `POST /api/regions/{rx}/{ry}/{rz}/submit`) so even unfixed extractor installs can't poison the DB going forward. **Layer 3 — Cleanup migration v1.81.0**: re-runs the same idempotent `UPDATE ... SET reality = 'Normal' WHERE reality = 'RealityMode.Normal'` across `systems` / `pending_systems` / `regions` that v1.79.0 already ran once. v1.79.0 cleaned the rows existing at that point, but 50 new bad rows arrived between then and the intake guard shipping — v1.81.0 catches those on next Pi deploy. |
| Backend API | 1.59.0 | 2026-05-12 | RealityMode.Normal intake guard + cleanup migration. Added `normalize_reality()` to [constants.py](Haven-UI/backend/constants.py) (strips any enum-class prefix like "RealityMode." → "Normal", validates against the {Normal, Permadeath} set, defaults to "Normal" on anything else). Applied at all 6 reality-read sites that accept submission payloads: 4 in [routes/approvals.py](Haven-UI/backend/routes/approvals.py) (`/api/submit_system` line 198, `/api/check_glyph_codes` line 352, region-name approval line 2894, `/api/extraction` line 3045) and 2 in [routes/regions.py](Haven-UI/backend/routes/regions.py) (`PUT /api/regions/{rx}/{ry}/{rz}` line 1032, `POST /api/regions/{rx}/{ry}/{rz}/submit` line 1128). New migration v1.81.0 re-runs the same idempotent cleanup that v1.79.0 ran ("RealityMode.Normal" → "Normal" across `systems`, `pending_systems`, `regions`) since v1.79.0 only ran once and 50 bad rows arrived after it from stale extractor installs. |
| Haven Extractor | 1.9.8 | 2026-05-12 | Module-level `_normalize_reality()` and `_normalize_community_tag()` helpers (haven_extractor.py:825-855); applied in `reality_mode` and `community_tag` setters in place of the broken `value.value if isinstance(...) else str(value)` fallback. The fallback persisted pymhf's DearPyGUI enum repr ("RealityMode.Normal") verbatim into config.json and the submission payload's `reality` field. Module init scrubs `USER_REALITY` and `USER_DISCORD_TAG` at config load time (inline since the helpers are defined later in the file) so any pre-1.9.8 config self-heals. Mod-only zip needs rebuilding per the workflow in CLAUDE.md before GitHub Release upload. |
| Haven-UI | 1.52.1 | 2026-05-12 | Wizard mobile reflow for the Advanced flow live preview. `WizardAdvancedPreview` was built landscape — hard `gridTemplateColumns: '220px 1fr'` hero row + `grid-cols-5` stat grid + `position: sticky; top: 16` — which on phones left ~140px for the right column (smooshed unreadable stat tiles) and stacked under the already-sticky toolbar+pill nav to eat >50% of the viewport. Mobile-only changes (all gated behind `lg:` so desktop is byte-identical): outer aside drops sticky on <lg (scrolls away with the form), hero row stacks (orbit 140px on top, content below), stat grid `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5`, glyph/planet badges 5×5 instead of 6×6, side padding `px-3 sm:px-5`, glyph_code text hidden on <sm. In [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) the advanced preview banner now renders twice: `hidden lg:block` keeps the desktop mount unchanged; `lg:hidden` wraps it in a collapsed-by-default `<details>` with a compact summary chip (`📊 Live preview · GRADE · %`) so mobile users see the key signal without the card eating screen real estate until they tap to expand. |
| **Master Haven** | 1.59.0 | 2026-05-05 | Latency fix dispatch + Centralization Roadmap Entry 9. New `services/dispatch.py` exposes `fire_and_forget()` for async side effects; FastAPI `BackgroundTasks` is the sync transport. Single-system approval and batch approval handlers no longer hold connections open while writing audit/activity-log/poster-invalidation side effects — those fire after the response. `/api/approve_systems/batch` is now an async job-queue endpoint: returns 202 + `job_id`, frontend polls `GET /api/batch_jobs/{job_id}` every 3s with a progress bar. War-room Discord webhook delivery moved off the event loop via `asyncio.to_thread(requests.post, ...)`. Three new migrations (v1.72.0–v1.74.0): indexable `username_normalized` on `pending_systems` (analytics leaderboard groups by indexed column instead of full-scan CASE/SUBSTR/GLOB), trigger-maintained `glyph_code_suffix` on `systems` and `pending_systems` (find_matching_system uses index instead of `SUBSTR(glyph_code, -11)`), and `batch_jobs` table for async job tracking. SQLite PRAGMA tuning: synchronous=NORMAL, 64 MB cache, 256 MB mmap, temp_store=MEMORY. Landing/site OG poster TTL dropped 168h → 1h; event-driven invalidation now covers `landing_og`/`og_site`/`og_atlas`/`og_community`/`voyager*` on every system approval and region naming. `/api/pending_systems/count` for non-super-admins now uses pure SQL `COUNT(*)` with self-submission filter inlined as WHERE clause instead of fetching+filtering rows in Python. See [LATENCY_FIX_REPORT.md](LATENCY_FIX_REPORT.md). |
| Backend API | 1.55.0 | 2026-05-05 | New `services/dispatch.py` (Centralization Entry 9). Approval handlers (`approve_system`, `batch_approve_systems`, `submit_system`, `reject_system`, `batch_reject_systems`) now accept `BackgroundTasks` and dispatch activity-log + poster-invalidation work post-response. War-room `send_war_notification` keeps the in-app notification INSERT inline but moves Discord webhook delivery to `fire_and_forget(_deliver_discord_webhook, ...)` using `asyncio.to_thread(requests.post, ...)`. Region-name approval + direct-update endpoints fire poster invalidation post-response. `_invalidate_posters_for_submission` expanded to cover landing_og/og_site/og_atlas/og_community/voyager_og. `/api/approve_systems/batch` returns 202 + job_id; new `_process_batch_approvals_sync` worker runs in `asyncio.to_thread`, commits per-submission, updates `batch_jobs` row every 5 submissions; new `GET /api/batch_jobs/{job_id}` polled by frontend. Migrations v1.72.0 (`username_normalized`), v1.73.0 (`glyph_code_suffix` triggers + index), v1.74.0 (`batch_jobs` table). PRAGMA tuning in `db.get_db_connection`. `find_matching_system`/`find_matching_pending_system` query `glyph_code_suffix` instead of `SUBSTR(glyph_code, -11)`. Analytics leaderboard `GROUP BY username_normalized` instead of expression-based normalization. Pending count endpoint inlines self-submission filter as SQL. |
| Haven-UI | 1.51.0 | 2026-05-05 | `SystemApprovalTab.handleBatchApprove` rewritten for the new async batch endpoint: POST returns `job_id`, polls `GET /api/batch_jobs/{job_id}` every 3 seconds (30-minute timeout), shows a progress bar (`Processing batch: 47 / 100`). Final result mapped into the legacy `batchResults` shape so the existing results modal renders without changes. New `getBatchJobStatus(jobId)` helper in `api.js`. |
| **Master Haven** | 1.58.0 | 2026-05-04 | Poster/embed system audit pass: fixed `/community-stats/{tag}` Discord embed (OGCommunityCard had a stale field-name contract — looked for `tag`/`systems`/`discoveries`/`contributors`/`manual`/`extractor` keys but the API returns `discord_tag`/`total_systems`/`total_discoveries`/`unique_contributors`/`manual_systems`/`extractor_systems`, so every match-by-tag failed and every stat rendered as `—`); bumped `og_community` template version 1→2 to invalidate cached blank PNGs. Added 7 new SSR routes in [Haven-UI/backend/routes/ssr.py](Haven-UI/backend/routes/ssr.py): a 301 alias from `/voyagers/{username}` (plural) to `/voyager/{username}` (singular), plus per-route OG meta tags for `/discoveries`, `/discoveries/{type}`, `/regions/{rx}/{ry}/{rz}`, `/changelog`, `/docs`, and `/docs/{slug}` so Discord/Twitter previews on those pages now show route-specific titles instead of the generic "Voyager's Haven" embed. The image is the existing `landing_og` card for all six (no new poster types — title and description carry the per-page meaning); custom poster cards per page can be a follow-up. Pages explicitly NOT covered: `/wizard`, `/create`, `/db_stats` — interactive/internal-feeling, low share value. |
| Backend API | 1.54.0 | 2026-05-04 | [routes/ssr.py](Haven-UI/backend/routes/ssr.py) gained `build_discoveries_og`, `build_discovery_type_og`, `build_region_og`, `build_changelog_og`, `build_docs_index_og`, `build_doc_page_og` payload builders and matching `@router.get` handlers, plus a `/voyagers/{username}` 301 alias to the singular route. All chromed routes follow the existing pattern (bot UA → OG template, real browser → 302 to `/haven-ui/...`). Title generation for `/discoveries/{type}` and `/docs/{slug}` derives a pretty title from the URL slug — for region pages the title is the bare coordinates ("Region 1F,F0,12 — Voyager's Haven"); upgrading these to use the named-region lookup is a follow-up that requires DB access from the SSR layer. [services/poster_service.py](Haven-UI/backend/services/poster_service.py) `og_community` PosterTemplate version bumped 1→2 — `is_cache_fresh()` will reject the v1 cached PNG and re-render with the fixed [src/posters/OGCommunityCard.jsx](Haven-UI/src/posters/OGCommunityCard.jsx). |
| Haven-UI | 1.51.0 | 2026-05-04 | [src/posters/OGCommunityCard.jsx](Haven-UI/src/posters/OGCommunityCard.jsx) field names corrected: `c.tag` → `c.discord_tag` for community lookup, and the four stat tiles now read `total_systems` / `total_discoveries` / `unique_contributors` / `manual_systems` / `extractor_systems` instead of the never-populated `systems` / `discoveries` / `contributors` / `manual` / `extractor`. The component fetches `/api/public/community-overview` which has always returned the longer field names — the poster was just looking for the wrong keys, so every rendered card showed `—` for every stat. Cached blank PNG is invalidated by the `og_community` version bump on the backend. |
| **Master Haven** | 1.57.0 | 2026-04-30 | New public **Haven Docs** hub at `havenmap.online/haven-ui/docs` — replaces the **Changelog** slot in the navbar and the Docs button on the landing page now points here. Three docs on day one: "Getting Started" (member onboarding, draft), "For Civilization Leaders" (partner pitch, draft), and "Under the Hood" — a long-form technical doc that embeds WhrStrsG's community guide to the No Man's Sky glyph and portal coordinate system, with the four reference images extracted from the source Google Doc. Each long-form doc has a numbered, scroll-tracking sidebar (auto-built from H2 headings via IntersectionObserver), top docs-switcher pill row, and renders Markdown bodies via `react-markdown` + `remark-gfm`. The original `/changelog` story page is preserved untouched and reachable via a card on the docs hub. |
| Haven-UI | 1.50.0 | 2026-04-30 | New `Docs` page at [pages/Docs.jsx](Haven-UI/src/pages/Docs.jsx) (hub) and [pages/DocPage.jsx](Haven-UI/src/pages/DocPage.jsx) (long-form). Markdown content lives at `Haven-UI/src/data/docs/*.md` (loaded via Vite `import.meta.glob` with `?raw`); manifest at [data/docs/manifest.json](Haven-UI/src/data/docs/manifest.json). Reuses the existing `--app-primary` / `--app-accent-2` / `--app-accent-amber` accent tokens — teal for member docs, amber for leadership, violet for advanced. Sidebar TOC is auto-generated by parsing H2 headings; active section is tracked with `IntersectionObserver`. New deps: `react-markdown@^10.1.0`, `remark-gfm@^4.0.1`. New static asset path: `Haven-UI/public/docs/images/` (4 images extracted from the source Google Doc DOCX). Navbar `Changelog` top-level link replaced with `Docs`; the `/changelog` route + page are unchanged. Landing page "Docs" button updated from `/haven-ui/changelog` to `/haven-ui/docs`. |
| **Master Haven** | 1.56.0 | 2026-04-29 | Custom Discord/Twitter embed for the landing page: new `landing_og` poster type at [Haven-UI/src/posters/LandingOG.jsx](Haven-UI/src/posters/LandingOG.jsx) renders a 1200×630 PNG matching the landing page aesthetic — cosmic-compass logo on the left, "VOYAGER'S HAVEN / Cartographers of the Unknown" wordmark in Cinzel on the right, three live stat tiles (Star Systems / Named Regions / Galaxies Explored), starfield + radial-gradient background, teal/purple accent dots. Replaces the dashboard-era `og_site` card as the default for `havenmap.online/` embeds. Routing fix: Map button on the landing page now points at `/map/latest` (the actual 3D map, matching the Navbar) instead of `/haven-ui/systems`; Search button now correctly points at `/haven-ui/systems` (advanced search w/ planet+system filters). |
| Backend API | 1.53.0 | 2026-04-29 | New `landing_og` PosterTemplate registered in [services/poster_service.py](Haven-UI/backend/services/poster_service.py) (1200×630, weekly TTL, SPA route `/poster/landing_og/global`). `build_site_og()` in [routes/ssr.py](Haven-UI/backend/routes/ssr.py) now points root-domain embeds at `landing_og` instead of `og_site` — both posters remain in the registry, but only landing_og is wired to `/`. |
| **Master Haven** | 1.55.0 | 2026-04-29 | Public landing page at `havenmap.online/` (the bare root): standalone HTML at [Haven-UI/landing/index.html](Haven-UI/landing/index.html) with starfield canvas, animated cosmic-compass logo (play-once → freeze → hover-replay), and 4 destination buttons (Map / Create / Search / Docs). Served by the existing haven backend (no new container, no NPM reconfig). The SSR root handler now injects dynamic OG/Twitter meta tags into the landing page so Discord/Twitter previews keep using the live OG poster. |
| Backend API | 1.52.0 | 2026-04-29 | New `/assets` static mount serves `Haven-UI/landing/assets/` (logo webm/mp4/webp) with the same `CachedStaticFiles` + 30-day immutable cache headers used for user photos. SSR `og_root` handler in [routes/ssr.py](Haven-UI/backend/routes/ssr.py) rewritten: instead of returning the OG-only template that auto-redirected real browsers to `/haven-ui/`, it now reads `landing/index.html` and injects a per-request OG/Twitter meta block at the top of `<head>` (scrapers honor first-tag-wins, so the dynamic block beats the static fallback further down). The legacy template still serves as fallback when `landing/` is missing. The `@app.get('/')` handler in `control_room_api.py` also kept as a final safety-net redirect to `/haven-ui/` when neither SSR nor landing is available. |
| **Master Haven** | 1.54.0 | 2026-04-29 | Pi freeze mitigation Stages 2 + 3: bounded result sizes on hot endpoints, browser caching for photos, new operational endpoints (`/api/admin/health`, `wal_checkpoint`, `vacuum`), periodic WAL checkpoint background task, Pi-side zram + weekly VACUUM cron via `scripts/pi_setup_stage3.sh`. |
| Backend API | 1.51.0 | 2026-04-29 | Stage 2: caller-supplied `limit` on `/api/approval_audit` clamped to ≤500; `/api/discoveries?q=` requires ≥2-char query (single-char wildcard searches now no-op); user-photo and war-media static mounts now use `CachedStaticFiles` with `Cache-Control: public, max-age=2592000, immutable`. Stage 3: new `/api/admin/health` returns DB / WAL / freelist sizes, schema version, hot-table row counts, and process memory (psutil → `/proc/meminfo` fallback); new super-admin `/api/admin/maintenance/wal_checkpoint` and `/api/admin/maintenance/vacuum` endpoints; startup task now runs `PRAGMA wal_checkpoint(TRUNCATE)` every 30 minutes to bound WAL growth. Pi-side `scripts/pi_setup_stage3.sh` enables zram-backed swap and installs a weekly VACUUM cron. |
| **Master Haven** | 1.53.0 | 2026-04-28 | Pi freeze mitigation Stage 1: hot-path indexes on activity_logs / approval_audit_log / pending_systems, and rewritten activity-log trim that no longer holds the write lock on every insert. |
| Backend API | 1.50.0 | 2026-04-28 | Migration v1.71.0 adds `idx_activity_logs_timestamp`, `idx_audit_submitter` / `idx_audit_action` / `idx_audit_submission_type` / `idx_audit_source` on approval_audit_log, and `idx_pending_systems_status_date` + `idx_pending_systems_discord_status`. `add_activity_log()` rewritten: trim now uses an indexed cutoff lookup (no full scan, no in-memory sort) and only runs every 100th insert via an in-process counter. Together this removes the write-lock pile-up that almost certainly caused the 2026-04-28 Pi hard-freeze under sustained submission load. |
| **Master Haven** | 1.52.1 | 2026-04-28 | Retired `keeper-discord-bot-main`: archived to `C:\Master-Haven-Archives\2026-Q2\2026-04-28-keeper-discord-bot-main\`, GitHub repo `Parker1920/Keeper-bot` tagged `v1.0-archived`. Removed dead keeper resolver code from `paths.py` and 3 obsolete integration test files. |
| Backend API | 1.49.1 | 2026-04-28 | Removed `_resolve_keeper_bot_dir()`, `_resolve_keeper_db()`, `get_keeper_database()`, and `keeper_bot_dir`/`keeper_db` attrs from [paths.py](Haven-UI/backend/paths.py). Removed `'keeper'` branch from `get_logs_dir()` / `get_data_dir()`. Removed `keeper_bot_dir / 'data'` from `find_database()` and `find_data_file()` search paths. Zero external callers existed for any of this. |
| **Master Haven** | 1.52.0 | 2026-04-28 | Unified submission source attribution across all pending/approved tables (Stage 1 of pending-card refactor) |
| Backend API | 1.49.0 | 2026-04-28 | New `source` column on pending_discoveries / discoveries / pending_region_names / regions; canonical `resolve_source()` helper; `keeper_bot` split out of `haven_extractor`; `companion_app` folded into `haven_extractor` |
| **Master Haven** | 1.51.1 | 2026-04-28 | DB Stats: `populated_regions` now scoped by `(reality, galaxy, rx, ry, rz)` to match `regions` table — fixes Named vs Populated count asymmetry |
| Backend API | 1.48.8 | 2026-04-28 | `populated_regions` in `/api/db_stats` now distincts on reality + galaxy + (rx,ry,rz) instead of bare coords (matches v1.49.0 regions UNIQUE constraint) |
| **Master Haven** | 1.51.0 | 2026-04-27 | Public `/changelog` page (Voyager's Haven story page) + animated brand-mark swap across the navbar |
| Haven-UI | 1.49.0 | 2026-04-27 | New public Changelog page, nav link, animated GIF brand mark replaces SparklesIcon, new `--app-accent-amber` token |
| **Master Haven** | 1.50.13 | 2026-04-21 | Numpy auto-install on mod load + INFO-level galaxy diagnostics for "always Euclid" reports |
| Haven Extractor | 1.9.3 | 2026-04-21 | Auto-installs numpy if `nms_namegen` import fails; promotes RealityIndex + universe_addr resolution logs from DEBUG to INFO |
| **Master Haven** | 1.50.12 | 2026-04-21 | Custom system name field re-added to extractor for renamed systems; procgen preserved in description |
| Haven Extractor | 1.9.2 | 2026-04-21 | "Custom System Name" field + "Apply Custom Name" button; procgen name stashed in `description` when user overrides |
| Backend API | 1.48.7 | 2026-04-21 | `/api/extraction` accepts `description` field (carries procgen name for renamed systems) |
| Master Haven | 1.50.11 | 2026-04-21 | Super admin can reissue extractor API keys for users who lost theirs |
| Haven-UI | 1.48.2 | 2026-04-21 | Reissue Key button + new-key display modal on Extractor Users admin page |
| Backend API | 1.48.6 | 2026-04-21 | New `POST /api/extractor/users/{id}/reissue-key` super admin endpoint |
| Backend API | 1.48.5 | 2026-04-18 | Fix galaxy column missing from Haven sub-admin pending_systems queries (always showed Euclid) |
| Backend API | 1.48.4 | 2026-04-15 | New `GET /api/public/user-stats?username=X` endpoint for Discord bot personal stat lookups |
| Backend API | 1.48.3 | 2026-04-14 | `/api/discoveries` + `/discoveries` POST now enqueue to `pending_discoveries` instead of inserting directly (closes bot approval-bypass) |
| Backend API | 1.48.2 | 2026-04-13 | Accept no_trade_data flag, store NULL (not "Unknown") for economy/conflict/lifeform when NMS reports no data |
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

1. **Create the new zip** from `NMS-Haven-Extractor/dist/HavenExtractor/mod/` containing only: `haven_extractor.py`, `extraction_core.py`, `nms_language.py`, `structs.py`, `pymhf.toml`, `__init__.py`, `haven_config.json.example`, and the entire `nms_namegen/` directory
2. **Name it** `HavenExtractor-mod-v{VERSION}.zip` and place it in the repo root
3. **Archive the old zip** by moving the previous version's zip to `NMS-Haven-Extractor/archive/`
4. **Upload** the new zip to the GitHub Release (edit the existing release or create a new one with tag `v{VERSION}`)

The auto-updater (`haven_updater.ps1`) looks for assets matching `HavenExtractor-mod-*` in the latest GitHub Release.

**Two zip types exist:**
- **Mod-only zip** (~50-60 KB): Contains just the `mod/` files. Used by the auto-updater for existing users.
- **Full distributable** (~112 MB): The entire `NMS-Haven-Extractor/dist/HavenExtractor/` folder. For new users who need the embedded Python runtime, batch scripts, etc. Created manually by zipping the full `dist/HavenExtractor/` directory.

### Changelog

#### Version Audit (2026-06-22) - True Backend/Frontend Renumber
Parker: "we changed how the migrations are uploaded to the backend and we really messed up the update version of the backend and front end — get the true version number (bug → patch, feature → minor, major → first digit)."

**What was wrong.** The web app has three independent counters (Master Haven umbrella, Backend `/api/status`, Frontend `package.json`). The backend and frontend numbers had drifted **upward** for two reasons:
1. **Bundled commits / jumps.** Several commits packed multiple logical releases and bumped the version files in one big leap, skipping numbers — `693d190` (backend 1.62.0→1.65.1), `c805dd5` (1.74.2→1.76.0, skip 1.75.0), `18e5abb` (1.78.0→1.81.0, skip 2), `001e584` (1.86.0→1.89.0, skip 2 — a commit literally titled "bug updates" that advanced 3 minors). Frontend had the matching jumps.
2. **Bug-fix-as-minor.** Many pure bug-fix deploys were bumped MINOR instead of patch.

Also note: the changelog's per-row "Backend API X / Haven-UI X" labels and the inline "`/api/status` → X / `package.json` → Y" notes have been a **separate, lower fiction desynced from the actual code since ~early May** — the git version lines are the only real shipped numbers.

**Safety.** Nothing in the frontend, build, service worker, or extractor auto-updater compares the `/api/status` version or `package.json` version (verified) — they're informational only. So resetting them to lower true values has no downgrade/cache effect.

**Baseline + method.** Anchored at the last clean, sequential git point — **Backend `1.60.0` / Frontend `1.52.1`** (2026-05-05, the commit before `008c95c`). Applied one bump per real deploy (one version-bumping commit), classified by dominant change: `Fix`/bug → patch, new feature/endpoint/page/tool → minor. This collapses the 4 artificial jumps.

**Ledger (baseline → now):**

| # | commit | dominant change | type | →Backend | →Frontend |
|--|--------|------|------|--------|---------|
|—|baseline (pre-`008c95c`, 05-05)| | |**1.60.0**|**1.52.1**|
|1|`008c95c` poster latency / async batch queue|feat|min|1.61.0|1.53.0|
|2|`cd6820c` civ-source consolidation + admin hubs|feat|min|1.62.0|1.54.0|
|3|`693d190` search rebuild ("major rework")|feat|min|1.63.0|1.55.0|
|4|`1661464` new `/api/search` + SearchOverlay|feat|min|1.64.0|1.56.0|
|5|`b6f8119` "big update"|feat|min|1.65.0|—|
|6|`2c4b021` partner perms tweak|fix|pat|1.65.1|1.56.1|
|7|`b95ac05` per-member perms editor|feat|min|1.65.2|1.57.0|
|8|`5de1b37` docker guild-db mount (stray bump)|fix|pat|1.65.3|1.57.1|
|9|`48520cb` festival glyph art swap|fix|pat|—|1.57.2|
|10|`829105b` true-scale Map rework|feat|min|1.66.0|1.58.0|
|11|`b36620e` fix tag log spam|fix|pat|1.66.1|—|
|12|`0d4c185` MidGenX galaxy backfill|fix|pat|1.66.2|—|
|13|`76ac99f` "major update" cruise backlog|feat|min|1.67.0|1.59.0|
|14|`f10e191` events + glyph-tool start|feat|min|1.68.0|1.60.0|
|15|`7640051` completeness/grading rework|feat|min|1.69.0|1.61.0|
|16|`346706b` fix phantom-star detection|fix|pat|1.69.1|1.61.1|
|17|`2949180` star-category field/badge|feat|min|1.70.0|1.61.2|
|18|`c805dd5` pretty URLs + discovery modal|feat|min|1.71.0|1.62.0|
|19|`6399514` fix search-result picker|fix|pat|1.71.1|1.62.1|
|20|`4a0a0cc` events global opt-in|feat|min|1.72.0|1.63.0|
|21|`c4ab4b6` fix search card|fix|pat|1.72.1|1.63.1|
|22|`c1b286b` Glyph Finder tool|feat|min|1.73.0|1.64.0|
|23|`18e5abb` "update bug fixes" (S+ fix etc.)|fix|pat|1.73.1|1.64.1|
|24|`0ac468f` Cartographer filters + community filter|feat|min|1.74.0|1.65.0|
|25|`fd08593` resource-filter rework|feat|min|1.75.0|1.66.0|
|26|`aa53858` batch approve/reject discoveries|feat|min|1.76.0|1.67.0|
|27|`f614227` fix discovery FK relink|fix|pat|1.76.1|—|
|28|`d0375fc` migration-runner overhaul (bugs)|fix|pat|1.76.2|—|
|29|`f105ea0` war-room per-civ gating fix|fix|pat|1.76.3|1.67.1|
|30|`001e584` "bug updates" (sub-admin zero-perm)|fix|pat|1.76.4|1.67.2|
|31|`ee0b571` leader-scoped civ admin page|feat|min|1.77.0|1.68.0|
|32|`485c598` sub-admin feature-cap fix|fix|pat|**1.77.1**|**1.68.1**|

**True current versions: Master Haven `1.78.0`, Backend `1.77.1`, Frontend `1.68.1`.** Live files updated (`routes/auth.py`, `package.json`); the Current Versions table top rows + component CLAUDE.md headers carry the corrected numbers with `_(was X)_` annotations. The historical row labels below (1.82.0–1.94.0 era) and their inline version notes are the OLD inflated numbering — left intact to preserve history.

**Master Haven umbrella → `1.78.0`** (was 1.94.0). Same method, from MH baseline `1.58.0`: one bump per deploy, **minor if *either* track shipped a feature that deploy**, else patch → 18 feature-deploys + 14 fix-deploys = a literal recompute of `1.76.1`. Per Parker, **set to `1.78.0` so the umbrella always leads** the components (the recompute landed 1 under Backend 1.77.1 because the umbrella's pre-baseline number, 1.58.0, already trailed the backend git line, 1.60.0, at the anchor).

**One missed deploy caught during mapping:** `b217495` (mobile Cartographer top-bar fix) is a frontend-only **patch** between `829105b` and `76ac99f` — it slots in as Frontend 1.58.0→1.58.1, then `76ac99f`'s minor resets it, so the **final Frontend number is unchanged** (1.68.1). It only affects the mid-series mapping (OLD Frontend 1.62.1 → TRUE 1.58.1).

**Borderline classifications** (each flip = ±1 on the minor; flag to retune): #5 `b6f8119` "big update", #8 `5de1b37` stray bump, #17 star-category, and the perms/war-room cluster #6/#7/#29 (if treated as features not fixes, Backend rises toward ~1.80).

**Go-forward rule (so this stops happening):** one version bump **per deploy**, classified by the highest-severity change in it — bug-only → patch (third digit), any feature → minor (second digit), breaking/major → first digit. Don't bundle multiple "releases" into one commit's version jump; if a deploy genuinely contains N features, it's still ONE minor bump.

**OLD → TRUE mapping** (use this to resolve any historical label to its true number; OLD = what the version file/changelog showed, TRUE = corrected). Below the baseline, OLD = TRUE (unchanged).

Backend `/api/status`:
`1.91.0→1.77.1` · `1.90.0→1.77.0` · `1.89.0→1.76.4` · `1.86.0→1.76.3` · `1.85.0→1.76.2` · `1.84.1→1.76.1` · `1.84.0→1.76.0` · `1.83.0→1.75.0` · `1.82.0→1.74.0` · `1.81.0→1.73.1` · `1.78.0→1.73.0` · `1.77.1→1.72.1` · `1.77.0→1.72.0` · `1.76.1→1.71.1` · `1.76.0→1.71.0` · `1.74.2→1.70.0` · `1.74.1→1.69.1` · `1.74.0→1.69.0` · `1.73.0→1.68.0` · `1.72.0→1.67.0` · `1.71.0→1.66.2` · `1.70.1→1.66.1` · `1.70.0→1.66.0` · `1.69.0→1.65.3` · `1.68.0→1.65.2` · `1.67.0→1.65.1` · `1.66.1→1.65.0` · `1.66.0→1.64.0` · `1.65.1→1.63.0` · `1.62.0`/`1.61.0` unchanged. (Backend `1.87.0`/`1.88.0` are **phantom** — the changelog labels them for the editable-discoveries release but the file jumped 1.86.0→1.89.0 and never wrote them; they fold into TRUE 1.76.x.)

Frontend `package.json`:
`1.81.0→1.68.1` · `1.80.0→1.68.0` · `1.79.0→1.67.2` · `1.75.1→1.67.1` · `1.75.0→1.67.0` · `1.74.0→1.66.0` · `1.73.1→1.65.0` · `1.72.0→1.64.1` · `1.70.0→1.64.0` · `1.69.0→1.63.1` · `1.68.0→1.63.0` · `1.67.1→1.62.1` · `1.67.0→1.62.0` · `1.66.4→1.61.2` · `1.66.3→1.61.1` · `1.66.2→1.61.0` · `1.65.0→1.60.0` · `1.64.0→1.59.0` · `1.62.1→1.58.1` · `1.62.0→1.58.0` · `1.61.0→1.57.2` · `1.60.0→1.57.1` · `1.59.0→1.57.0` · `1.58.6→1.56.1` · `1.58.5→1.56.0` · `1.57.1→1.55.0` · `1.54.0` unchanged · `1.53.1→1.53.0` · `1.52.1` and below unchanged.

**Decisions (resolved):** Master Haven set to `1.78.0` (umbrella leads the components). Deep `#### Changelog` history is **not** renumbered in place — this entry's OLD→TRUE mapping is the authoritative resolver, and the deep prose keeps its historically-accurate "file showed X at deploy time" notes under the audit banner.

---

#### Master Haven 1.84.1 (2026-07-02) - Fix `UNIQUE constraint failed: moons.id` on Admin Edit-Save (FK-off connection)
Parker: submitting revisions to `[RES]Memoro` through the wizard "keeps shooting back Database error" (updated station, added planet photos + a few planet attributes). The wizard just shows a generic "Database error".

**What it actually was.** The generic message is a 500 from `POST /api/save_system` (the admin direct-save path — Parker is logged in, so the button reads "Save System"), which wraps its whole transaction in `except Exception → HTTPException(500, "Database error")` ([control_room_api.py:3415](Haven-UI/backend/control_room_api.py#L3415)). The real SQLite error in the Pi logs was `UNIQUE constraint failed: moons.id` at the moon INSERT ([line 3080](Haven-UI/backend/control_room_api.py#L3080)) — failing every retry (30+ in 12h), all on Memoro.

**Root cause (verified end-to-end against a copy of the live prod DB).** `save_system` does a delete-and-reinsert of the system's bodies: `DELETE FROM planets WHERE system_id=?` and relies on `moons.planet_id … ON DELETE CASCADE` to remove the moons, then the id-reuse feature (Fix B, 1.82.2) re-inserts each moon **with its original id**. That's only safe if the cascade actually freed those ids. It didn't — because **[control_room_api.py](Haven-UI/backend/control_room_api.py) defines its own `get_db_connection()` (~line 781) that omits `PRAGMA foreign_keys=ON`**, unlike the one in [db.py:94](Haven-UI/backend/db.py). Probes on the deployed connection showed `foreign_keys = 0`, and instrumenting the real `save_system` showed Memoro's moons `5382`/`5383` **still present after the DELETE** → the reused-id INSERT collided. Systems without moons never trip it (no moon reuse), so it wasn't universal. The same FK-off connection is the root of the recurring "discoveries went to space" / "planet tags wiped" family on this path — Memoro alone carries **58 orphaned moon rows** and 5 duplicate moon-pairs accumulated from years of non-cascading saves.

**Why not the "obvious" global fix.** Flipping `foreign_keys=ON` in the shared `get_db_connection` at line 781 would change cascade behavior for **every** endpoint in this file. The risky one is delete-system: with FK on, deleting a system would `SET NULL` its discoveries' `system_id`, which for a non-space discovery violates `CHECK (system_id IS NOT NULL OR location_type IN ('space','deep_space'))` and would abort the delete. So the global flip is a separate, test-gated change.

**Fix (targeted).** `save_system` now runs `conn.execute('PRAGMA foreign_keys=ON')` on its own connection immediately after `conn = get_db_connection()`. This makes its rebuild transaction cascade-delete moons and `SET NULL` discoveries exactly as the `capture_discovery_links`/`restore_discovery_links` + id-reuse machinery already assume (discovery links are then restored by name post-rebuild). Proven: invoking the **real, deployed** `save_system` against a live-DB copy — the exact save that 500'd now returns OK and preserves Memoro's moons; the module-level connection stays FK-off so sibling endpoints are untouched.

**Deploy.** Applied to the Pi build clone (backups saved), rebuilt the `haven` image (`docker compose up -d --build haven-control-room`), verified live: `/api/status` 1.83.1, container healthy, 0 `moons.id` errors post-restart. Backend-only; no migration; no frontend change. `/api/status` 1.83.0 → 1.83.1, Master Haven 1.84.0 → 1.84.1.

**Open follow-ups (not done):** (1) data cleanup — the 58 orphaned moon rows + any dangling discovery links left by past FK-off saves won't self-heal (harmless dead rows, but worth a pass). (2) Audit `control_room_api.py`'s DELETE paths and bring its local `get_db_connection` to FK-on to end the divergence from `db.py` and close this class on every endpoint in the file.

---

#### Master Haven 1.84.0 (2026-06-30) - Keeper ⇄ Cartography: Glyph → System-View Map Link
Parker's change request: "a combination of Keeper and the cartography map — if a user inputs glyphs through a Keeper connection can we return a URL that would take them directly to that system view."

**Investigation (three parts, verified in code).**
1. **The map system view resolves by id only.** `/map/system/{system_id}` ([control_room_api.py:4041](Haven-UI/backend/control_room_api.py#L4041)) is `SELECT * FROM systems WHERE id = ?` and nothing else ("Lookup by ID only — system identity is glyph-based, not name-based"). So `/map/system/<glyph>` 404s today; a glyph must first be turned into an id.
2. **The correct glyph→system match is galaxy-scoped, suffix-based.** `find_matching_system` ([db.py:394](Haven-UI/backend/db.py#L394)) matches on `glyph_code_suffix` (last 11 chars) + galaxy + reality, because the leading glyph digit is the *planet index* and changes every portal-in. `/api/systems/{id}`'s inline glyph branch ([control_room_api.py:2262](Haven-UI/backend/control_room_api.py#L2262)) instead does an exact-12-char, un-scoped match — it would miss a system read from a different planet and isn't galaxy-safe, so it was deliberately NOT reused. `/api/check_duplicate` already uses the correct rule but is API-key-gated and returns only id/name.
3. **Keeper (Stars's project) needs a spec, not our edits.** It has `HAVEN_API` (internal `http://haven:8005`) and `HAVEN_PUBLIC_URL` (public `havenmap.online`, required for Discord embeds), already holds the `Keeper 2.0` API key, and already calls `/api/check_duplicate` in `/hexkey` — it just never built a URL from the result.

**Decisions (Parker, via approval):** target the 3D system view (`/map/system/{id}`); resolver-endpoint approach (id-based URL, backend owns the format); on not-found return the decoded region preview + a submit link. Endpoint left **unauthenticated** (systems + the map page are already public).

**Backend** ([routes/systems.py](Haven-UI/backend/routes/systems.py)) — new public read-only `GET /api/glyph/system?glyph=&galaxy=Euclid&reality=Normal`:
- Validates the 12-hex glyph (`_decode_glyph_parts`), normalizes reality, defaults galaxy `Euclid` / reality `Normal`.
- Resolves `find_matching_system` (approved) → `find_matching_pending_system` (pending). Approved rows are passed through `apply_data_restrictions` for the calling session so a hidden/restricted system never leaks a map link (it falls through to `not_found`).
- **approved** → `{status, system_id, name, completeness_grade, galaxy, reality, region_name, decoded, map_url:/map/system/{id}, detail_url:/systems/{id}, cartographer_url:/map/latest?focus=system:{id}}`. Grade via `calculate_completeness_score` (best-effort).
- **pending** → `{status, submission_id, name, …}`, no `map_url` (not on the live map yet).
- **not_found** → decoded region + region name (custom if named, else procedural via `generate_names`) + `region_system_count` + `submit_url:/create?glyph=…&galaxy=…&reality=…`.
- URLs are **relative** on purpose — the caller prefixes `HAVEN_PUBLIC_URL`, never the internal docker host (avoids the Discord 400 "not a well formed URL"). New module helper `_region_custom_name()`; everything else reuses existing helpers. **No schema change, no migration, no frontend change.**

**Keeper handoff** — [The_Keeper/HAVEN_GLYPH_MAP_SPEC.md](The_Keeper/HAVEN_GLYPH_MAP_SPEC.md) for Stars: endpoint contract, the relative-URL/`HAVEN_PUBLIC_URL` rule, a suggested `/glyphmap <glyph> [galaxy] [reality]` command (or bolt onto the existing `/hexkey`), and a minimal aiohttp example. No `The_Keeper/` code edited (Stars's project).

**Verified.** Both edited backend files byte-compile. Local-DB smoke test: a real glyph (`20720193DFA9`, system Oculi) and a synthetic planet-index variant (`F0720193DFA9`) both resolve to the same system id → identical `/map/system/{id}` — proving the leading-digit tolerance. Backend-only `--build` deploy (no migration). `/api/status` 1.82.0 → 1.83.0; Master Haven → 1.84.0.

---

#### Haven-UI 1.72.5 (2026-06-28) - Adjective Dropdowns Guaranteed Alphabetical
> Component-only patch (per the version rule, a small fix bumps the component, not the umbrella). `package.json` 1.72.4 → 1.72.5; Master Haven umbrella unchanged.

Parker: "make all the dropdown searchable menus for the adjectives alphabetical." He confirmed he meant the **Create/Edit Wizard planet pickers**.

**Investigation.** The biome / weather / sentinel / flora / fauna / resources / exotic-trophy searchable dropdowns all live in one component — [CelestialBodyEditor.jsx](Haven-UI/src/components/CelestialBodyEditor.jsx) (used by the Wizard's planet/moon editor via `PlanetEditor`, and by the approval edit flow). They read [optionCatalog.json](Haven-UI/src/data/optionCatalog.json) through [adjectives.js](Haven-UI/src/data/adjectives.js), and the React `SearchableSelect` (react-select) renders options **in array order**. A programmatic check found all 7 source arrays already test A→Z (case-insensitive), so the pickers were already alphabetical in source — the likely live symptom was a **stale deployed build** (or a future hand-edit landing out of order, like the recent "SCARCE" inserts).

**Fix.** Rather than rely on the JSON staying hand-sorted, made alphabetical order a **build-time guarantee**: [adjectives.js](Haven-UI/src/data/adjectives.js) `toSelectOptions` now sorts (`localeCompare`, `sensitivity:'base'`) before mapping to `{value,label}`. It's the sole consumer feeding all 7 searchable pickers, so every one renders A→Z regardless of source order or future appends. (`[REDACTED]` stays pinned at the top of biome/weather, same as before.)

**Also (Parker chose "do all").** Sorted the one genuinely-unsorted adjective dropdown found elsewhere: the hardcoded **native** biome `<select>` in the approval-edit UI ([SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)) was `['Lush','Toxic','Scorched',…]` and duplicated across the planet + moon edit blocks — consolidated into one module-level `BIOME_EDIT_OPTIONS` const, sorted, so the two lists can't drift. (Weather/sentinel/flora/fauna/resources are free-text inputs in that UI, and size is already L→M→S, so biome was the only dropdown to touch there.) The Systems-tab Filter dropdowns + the Cartographer resource combobox were **verified already alphabetical** — they pull from `/api/systems/filter-options`, whose `_dedup_clean` / `get_distinct_resources` ([systems.py](Haven-UI/backend/routes/systems.py)) already return `sorted(...)` — so no change there.

Frontend-only — no backend, schema, or migration change. `npm run build` clean (16.37s, 0 errors). `package.json` 1.72.4 → 1.72.5.

---

#### Master Haven 1.79.0 (2026-06-23) - New Attributes (Swarm Debris / Trash Debris / Sentinel Activity), "No Space Station" Flag, Harvestables Out of Materials
> Numbered on the TRUE post-audit scheme (see "Version Audit (2026-06-22)"); it sits above the OLD-scheme 1.94.0 entry below because it's the newest deploy.

Parker's three requests: (1) add **Swarm Debris**, **Trash Debris**, **High Sentinel Activity**, **Aggressive Sentinel Activity** to the planet/moon attributes; (2) remove **Ancient Bones**, **Salvageable Scrap**, **Vile Brood** from the materials list (they were already boolean attributes — duplicated); (3) a **space-station "None" tickbox** so a system can definitively say it has no station (a null station was ambiguous — "none" vs "not uploaded yet"). Decisions captured up front: Swarm Debris and Trash Debris are **two separate** attributes; the station control is a **3-way radio** (Has / None / Not documented); existing materials data is **converted + stripped** (lift onto the flag, remove from materials).

**Attributes (4 new boolean columns on `planets` + `moons`).** Modeled exactly on the existing `vile_brood`/`water_world` specials. Added at every layer: migration **1.96.0** (schema) + the init-time `add_column_if_missing` safety net; written at every body INSERT/UPDATE — [`save_system`](Haven-UI/backend/control_room_api.py) (planet + moon), [`approve_system`](Haven-UI/backend/routes/approvals.py) (planet UPDATE, planet INSERT, both moon INSERTs), batch-approve (planet + moon), and [csv_import](Haven-UI/backend/routes/csv_import.py); editable in the wizard toggle grid ([CelestialBodyEditor.jsx](Haven-UI/src/components/CelestialBodyEditor.jsx)) with `PLANET_DEFAULTS` updated; rendered as badges on [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) (`FEATURE_FLAGS`), in the approval review UI ([SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx) — checkboxes + badges across all five planet/moon blocks), and on the 3D map ([VH-System-View.html](Haven-UI/public/VH-System-View.html), both cards); CSV note keywords map "swarm" / "trash debris" / "high sentinel activity" / "aggressive sentinel activity" onto the flags. (Note: the extractor doesn't detect these, so extractor-submitted bodies default them to 0 — they're a manual/curated attribute, consistent with the wizard being the gold-standard data path.) Heads-up kept for Parker: High/Aggressive Sentinel Activity are intentionally separate quick-flags alongside the existing per-planet **Sentinel** adjective field.

**No space station.** New `systems.no_space_station` (migration 1.96.0; pending rows carry it in the `system_data` JSON). The wizard Space Station section is now a 3-way radio: "Has a space station" (fills the station form), "No space station" (sets the flag, clears any station data), "Not documented yet" (neutral default). Persisted on every system INSERT/UPDATE in save/approve/batch, with the station row skipped on create and cleared on an edit-to-none. In scoring ([completeness.py](Haven-UI/backend/services/completeness.py) + the client mirror [useCompletenessScore.js](Haven-UI/src/hooks/useCompletenessScore.js)) a no-station system gets full 5/5 station credit and is exempt from the S+ station requirement — exactly like an Abandoned-economy system, which fixes the prior trap where a genuinely station-less system scored 0/5 and could never reach S/S+. SystemDetail and the approval modal show a "No Space Station" note instead of a blank.

**Materials cleanup.** The three harvestables were removed from the curated [adjectives.js](Haven-UI/src/data/adjectives.js) `resourcesList` and from [resource_catalog.py](Haven-UI/backend/resource_catalog.py) (`CANONICAL_RESOURCES` + their aliases); a new `NON_MATERIAL_TOKENS` set makes `normalize_materials()` **drop** them so they can't reappear. Migration **1.96.0** sweeps existing `planets`/`moons`: any `materials` cell containing one of the three has the matching boolean flag set and the token stripped, then affected systems are re-scored. CSV import does the same lift-and-strip at ingest.

**Verification.** All six touched backend files byte-compile; an AST audit of every `cursor.execute(...)` reported **0 placeholder/value mismatches** (the real risk with positional SQL — the only flagged COL-MISMATCH rows were pre-existing inline-literal INSERTs, not anything edited here). `npm run build` clean (11.59s, 0 errors; `public/VH-System-View.html` copied to `dist/`). On throwaway SQLite DBs: migration 1.96.0 adds the columns, lifts "Ancient Bones"/"Vile Brood Detected" → flags + strips them (P1 "Gold, Ancient Bones, Copper, Vile Brood Detected" → "Gold, Copper", ancient_bones=1, vile_brood=1; moon "Salvageable Scrap, Cobalt" → "Cobalt", salvageable_scrap=1) and is idempotent on re-run; `normalize_materials` drops the three; and a `no_space_station` system scores station 5/5 + grade S while the same system without the flag (and no station row) scores 0/5.

**Deploy:** backend `--build` (migration 1.96.0 auto-runs at startup) + frontend rebuild. `/api/status` 1.77.1 → 1.78.0, `package.json` 1.68.1 → 1.69.0, Master Haven → 1.79.0. The_Keeper bot left untouched (its unrelated "Sentinel Activity" input stays as-is).

---

#### Master Haven 1.94.0 (2026-06-22) - Sub-Admins Can't Exceed Their Civ's Feature Set
Parker: "leaders are still able to give sub admin permissions the civ itself didn't have — I didn't get RES civ the CSV uploads but they were still able to give a sub admin those perms."

**Root cause.** A sub-admin's effective features came straight from their per-member override with **no ceiling against the civ's own feature set** (`civilizations.enabled_features_default`). The same uncapped computation existed in two places:
- [`_recompute_profile_features`](Haven-UI/backend/routes/civilizations.py) — `effective = per_member if per_member is not None else default`. This is what materializes `user_profiles.enabled_features`, the list the **session and route guards** actually check. So an override with `csv_import` gave real `csv_import` access even on a civ that was never granted it.
- [`GET /api/sub_admins`](Haven-UI/backend/routes/partners.py) — `effective = override if override is not None else civ_default`, for the Sub-Admins page **display**, so the roster reported the inflated set too.

**Fix — cap the override at the civ's set (`override ∩ enabled_features_default`) at every layer:**
1. **Authoritative ceiling** ([civilizations.py](Haven-UI/backend/routes/civilizations.py)): `_recompute_profile_features` now does `union.update(f for f in effective if f != 'war_room' and f in set(default))`. Because this controls the session source, an out-of-civ grant can **never take effect** — regardless of who set the override or via which path (UI or raw API). This is the real fix.
2. **Honest display** ([partners.py](Haven-UI/backend/routes/partners.py)): the roster's `effective` is capped the same way, so the Sub-Admins page shows what's truly in effect.
3. **Honest editors** ([CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx) `MemberRow`, [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx) `SubAdminRow`): the per-member feature checkboxes are filtered to the civ's own features (`civDefaults` / `member.civ_default_features`), and Save intersects the draft with that set — so a super admin isn't even offered (and can't store) `csv_import` for a sub-admin of a civ without it. A civ with no grantable features shows a "super admin sets the civ's feature set first" note.

The model is now consistent: **the civ's `enabled_features_default` is the ceiling for all of its sub-admins.** To give a sub-admin a new capability you first add it to the civ's feature set.

**Verified:** `civilizations.py` + `partners.py` byte-compile; `npm run build` clean (11.65s, 0 errors); all six edits confirmed intact after concurrent editing of the same files. Frontend rebuild + backend restart. No schema change, no migration.

> **Existing data:** the ceiling takes effect for a profile the next time it's recomputed (any role/feature/membership change, or a civ-default change fans out to all members), and the roster display is corrected immediately. Already-over-granted sub-admins keep the stale grant in their **session** only until that next recompute. If you want every existing over-grant flushed on deploy, I can add a one-time recompute migration (same shape as v1.95.0) — say the word.

---

#### Master Haven 1.93.0 (2026-06-22) - Civ Leaders Manage the Roster, Not Permissions
Parker, looking at the civ feature-defaults grid: "civ leaders themselves should not have the ability to change their own perms — just add leaders, co-leaders, or sub-admins."

This narrows the 1.92.0 work, which had relaxed `update_civilization` so leaders could "edit brand/defaults." The problem: the feature-defaults grid (and the per-member Perms editor) is a **permission** surface — a leader editing it can change what their moderators (and, via War Room being civ-scoped, effectively themselves) can do. Leaders should build their team; super admins set what the team can do.

**Backend** ([civilizations.py](Haven-UI/backend/routes/civilizations.py)) — permission writes are now super-admin-only, enforced server-side (not just hidden in the UI):
- `update_civilization`: strips `enabled_features_default` from any non-super-admin update (the previous code only stripped `war_room`; this subsumes it). A leader can still edit brand — display name, region color, theme.
- `add_member`: `features = payload.get('enabled_features') if is_super else None`. A leader adds a member with a role; a leader-added sub-admin still lands on the zero-perm `[]` default (from 1.92.0) until a super admin grants features.
- `update_member`: captures `session_data`/`is_super`; `enabled_features` is only written when the caller is super admin. Role changes and the approve-personal-cap toggle remain available to leaders.

**Frontend** — controls that no longer do anything for a leader are hidden so they don't see a dead button:
- [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx): the edit-mode feature-defaults grid is wrapped in `auth.isSuperAdmin`; `MemberRow` takes an `isSuperAdmin` prop that hides the "Perms" button + per-member feature editor (leaders see role dropdown + approve-personal + remove).
- [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx): `SubAdminRow` takes `isSuperAdmin` and hides the "Edit perms" button + editor; the read-only feature summary, approve-personal, revoke, and **Add Sub-Admin** stay; the header blurb is role-aware ("a super admin grants what each one can do").

Founding a civ and its initial feature grid were already super-admin-only. Leaders keep full roster management: add a member of any role, change a member's role, toggle approve-personal, remove a member.

**Verified:** `civilizations.py` byte-compiles with `is_super` correctly scoped in all three handlers; `npm run build` clean (12.96s, 0 errors); all edits confirmed intact after concurrent editing of the same files. Frontend rebuild + backend restart. No schema change, no migration. `/api/status` → 1.90.0, `package.json` → 1.80.0.

> Note: the approve-personal cap and member-role changes are intentionally left available to leaders (roster management). If you want those locked to super admins too, say so and I'll gate them the same way.

---

#### Master Haven 1.92.0 (2026-06-22) - Sub-Admins Start at Zero Permissions + Leader-Scoped Civ Management
Parker: "the creation of sub admins and permission feels very broken when logged in as another civ, not super admin … sub admin permissions should also be completely removed until a leader allows them to have it."

**Investigation (how it worked + what was broken).** Sub-admins are `civilization_members` rows with `role='sub_admin'` (no separate account since 1.83.0); you elevate an existing profile. Effective features = per-member override (`civilization_members.enabled_features`) **else** the civ default (`civilizations.enabled_features_default`), materialized into `user_profiles.enabled_features` by `_recompute_profile_features` ([routes/civilizations.py](Haven-UI/backend/routes/civilizations.py)) and read by every route guard. Four real problems:
1. **Sub-admins were NOT zero-perm on creation.** Both add flows ([SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx) "+ Add Sub-Admin" and [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx) "+ Add member") POST `{profile_id, role:'sub_admin'}` with no features → override stored as **NULL** → `_recompute_profile_features` fell through to the civ default (seeded `['approvals','system_create','system_edit','stats']`). So a brand-new sub-admin could already approve/create/edit/view stats with nobody granting it — the "permissions feel broken" complaint.
2. **Leaders were locked out of the page the UI pointed them to.** The Sub-Admins banner said "use Civilization Management" but `/admin/civilizations` was `RequireSuperAdmin` — a leader clicking it got bounced to `/`. The backend (`_require_civ_manage_access`) already let a civ's own leader manage members, but there was **no UI door** for a leader to add a co-leader or edit their own civ.
3. **War Room could leak out of civ-scope.** SubAdminManagement's editable feature grid still listed `war_room`; ticking it wrote it into a sub-admin's override, which `_recompute_profile_features` unioned verbatim — granting War Room even when the civ never had it (breaking the 1.90.0 civ-scoped rule). 1.94.0 re-synced but did **not** strip war_room from sub_admin overrides.
4. **The "Add Sub-Admin" civ dropdown offered civs the leader couldn't manage** (any civ they merely belong to) → 403 on submit.

**Decisions (Parker).** New sub-admins = zero perms; keep the civ default as a one-click "Reset to civ default" **opt-in** template (not auto-applied). Open a **scoped** Civilization Management to leaders/co-leaders (manage their own roster + brand), keeping founding & archiving super-admin-only.

**Fix.**
- **Zero-default** ([add_member](Haven-UI/backend/routes/civilizations.py)): a `sub_admin` added with no explicit features now gets an **empty override `[]`**, not NULL — so they start with nothing until a leader grants it. Leaders/co-leaders keep NULL (full power by role). "Reset to civ default" (sets override → NULL) still restores the civ's standard set on demand.
- **War Room leak closed at the invariant** (`_recompute_profile_features`): `war_room` is now **stripped from every sub-admin effective override** — it's granted only via the civ-scoped default check, never per-member. Frontend also drops `war_room` from the Sub-Admins grid and strips it on save (defense in depth).
- **Leader-scoped Civilization Management**: `update_civilization` auth relaxed from super-admin-only to `_require_civ_manage_access` (a civ's own leader can edit brand/color/theme/defaults), with **`is_active` (archive/unarchive) still super-admin-only**. Route `/admin/civilizations` + `/admin/partners` changed `RequireSuperAdmin` → `RequireAdmin`; the page self-gates to leader-like (super admin OR partner) and hides "+ Found new civilization" and Archive for non-super-admins. New "Civilization" entry in the Admin navbar dropdown for leaders (`isPartner`); super admins keep theirs in the Super Admin dropdown.
- **Dropdown scoping**: the Add-Sub-Admin civ list is filtered to civs the user can actually manage (super admin → all; leader → civs they lead, from session `civ_memberships` role).
- **Migration v1.95.0**: flips every **implicit (NULL-override) sub_admin** grant to explicit `[]` (zero), then re-syncs `user_profiles.enabled_features` for **all** profiles with an active membership (same sweep scope as 1.94.0) — which also retroactively strips any leaked `war_room` from existing sub-admin overrides. Explicit overrides are left as someone's choice. Idempotent. **Operational note:** on deploy, existing sub-admins drop to zero access until their leader re-grants (or clicks "Reset to civ default").

**Verified.** All 3 backend files byte-compile; `migrations.py` imports clean (no duplicate-version error); an in-memory simulation of v1.95.0 + the recompute logic passed every assertion (NULL sub_admin → zero; explicit override preserved; leader → full + civ-scoped war_room; stray war_room in a no-war_room civ stripped; idempotent re-run). `npm run build` clean (11.32s, 0 errors).

**Deploy:** backend `--build` (migration v1.95.0 auto-runs at startup) + frontend rebuild. `/api/status` → 1.89.0, `package.json` → 1.79.0.

---

#### Master Haven 1.91.0 (2026-06-22) - Editable Discoveries from the System Page + Wizard (and the Planet-Dropdown Root Fix)
Parker: discovery edits "need to be accessible to everyone for the admins to approve," and he wants them editable "from both the discoveries page and the systems page." He'd reported that "only super admin can even see the planets show" when editing a discovery.

**Investigation (verified live, not just code-read).** I drove a real browser against `havenmap.online` as an **anonymous (non-super-admin) user** and edited several discoveries on a fully-mapped system: the planet dropdown populated with all 5 planets every time, and `/api/systems/{id}` returned 200 with the full planet list to the anonymous client. The [DiscoverySubmitModal](Haven-UI/src/components/DiscoverySubmitModal.jsx) has **zero role-gating** on planets, and `get_system` applies no per-role planet stripping for discovery-bearing systems (0 discoveries sit on the 24 `is_hidden_from_public` systems). So the **Discoveries-page** edit already worked for everyone — "only super admin" did not reproduce there. (If members still saw an empty dropdown on that page, the likely cause was a **stale PWA bundle** — the discovery-edit feature was only days old; the service worker re-precaches on this build.)

**The real gaps:**
1. **No discovery Edit on the system page.** [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) rendered `DiscoveryDetailModal` without an `onEdit` handler — you literally couldn't edit a discovery from a system.
2. **Wizard existing-discoveries were read-only.** [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) `SectionDiscoveries` showed them as a static list (the "small pill box") with no edit affordance.
3. **`get_system` omitted `d.system_id`.** Its discoveries SELECT ([control_room_api.py](Haven-UI/backend/control_room_api.py)) didn't return `system_id`; SystemDetail patched that client-side but the wizard list didn't — so any edit launched from a system context would open the modal with no `system_id` → **empty planet dropdown**. That's the exact "no planets" symptom, and it's the trap that bites once system-side editing exists.

**Fix.**
- **Backend (root):** added `d.system_id` to the `get_system` discoveries SELECT so the payload is self-describing everywhere.
- **System page:** `SystemDetail` now passes `onEdit` to `DiscoveryDetailModal`, opening the shared `DiscoverySubmitModal` in edit mode (the discovery is already enriched with `system_id`/`system_name`).
- **Wizard:** each existing-discovery row gets an **Edit** button that opens the same modal, enriched with the edited system's id/name as a fallback for older payloads that predate the `system_id` field.

Every edit rides the existing discovery-edit flow → `pending_discoveries` (`edit_discovery_id`) → normal approval, **separate** from the system's own pending edit (a discovery edit shouldn't be silently bundled into the system row). One shared modal, one approval path — no duplicated edit UI.

**Verified:** `npm run build` clean (14.78s, 0 errors); backend byte-compiles; all new identifiers wired consistently across both pages; the anonymous live repro confirmed the modal + planet dropdown work end-to-end. Frontend rebuild + backend restart (for the read-side SELECT add). No schema change, no migration. `/api/status` → 1.88.0, `package.json` → 1.78.0.

---

#### Master Haven 1.90.0 (2026-06-22) - War Room Is a Per-Civ Feature (Stop Showing It to Every Civ Leader)
Parker: "the war room is displaying to everyone that has a login regardless if they are assigned to the war room or not — fix this so the feature perm settings when creating a civ is correct, and when a civ is given that permission all the 'moderators' of that civ (leaders, co-leaders, sub-admins) get to see and use the war room."

**Root cause.** `war_room` was in `LEADER_FEATURES` ([constants.py](Haven-UI/backend/constants.py)). `_recompute_profile_features` ([routes/civilizations.py](Haven-UI/backend/routes/civilizations.py)) grants the **entire** `LEADER_FEATURES` set to every civ leader/co-leader **by role**, independent of the civ's stored permission — so any civ leader got `war_room`, and migration 1.84.0 persisted it into `user_profiles.enabled_features` for all of them. The frontend gate (navbar [Navbar.jsx](Haven-UI/src/components/Navbar.jsx) line 119 + route guard [App.jsx](Haven-UI/src/App.jsx) `RequireWarRoomAccess`) was already correct — it just read an over-granted features list. Confirmed against **prod** (read-only): the IEA civ's `enabled_features_default` = `[system_create, system_edit, approvals, stats, settings]` (no `war_room`), yet the IEA leader profile's `enabled_features` contained `war_room`. That's "not synced to what the civ has stored."

**Decision (Parker).** Permission-only fix: the per-civ "War Room" checkbox is the single source of truth for visibility, granted to **all moderators** of that civ; super-admin **enrollment** (territory/home-region setup) stays a separate step.

**Fix.**
- **[constants.py](Haven-UI/backend/constants.py):** removed `'war_room'` from `LEADER_FEATURES` (no longer a by-role grant) + documented why.
- **[routes/civilizations.py](Haven-UI/backend/routes/civilizations.py) `_recompute_profile_features`:** parses each membership's civ `enabled_features_default` up front and adds `war_room` to the union for **any** role when the civ has it — *before* the by-role `LEADER_FEATURES` grant. Net: a leader of a War-Room civ keeps it; a leader of a non-War-Room civ loses it; a sub-admin of a War-Room civ gets it. `update_civilization` already fans out a recompute to every member when `enabled_features_default` changes, so **checking War Room on a civ instantly grants the whole moderator team and unchecking revokes all of them**.
- **Migration v1.94.0** ([migrations.py](Haven-UI/backend/migrations.py)): first ensures any **actively-enrolled** civ has `war_room` in its default (belt-and-suspenders), then re-runs the role-aware + civ-scoped union for every profile with an active civ membership (tier≠1), inlining the leader set (no war_room). Scope matches 1.83.0/1.84.0 (only profiles with active memberships — legacy Haven sub-admins with directly-assigned features are untouched). The migration runs cleanly under the new per-migration tracking (the 1.89.0 hardening was done in anticipation of exactly this).
- **[routes/warroom.py](Haven-UI/backend/routes/warroom.py):** the enroll/unenroll endpoints wrote `war_room` to `partner_accounts.enabled_features` — a dead write (the civ-era session reads `user_profiles`). Repointed via new `_set_civ_war_room_feature()` (resolves partner→civ via enrollment `civ_id` or discord_tag→civ tag, toggles `war_room` on the civ's `enabled_features_default`, fans out the member recompute) so the War Room Admin "Enroll" path and the civ feature grid stay consistent.
- **[CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx):** War Room relabeled "War Room (all moderators)"; comment/captions document it as the civ-scoped exception; removed from the per-member sub-admin override grid (it's civ-controlled) and stripped from saved overrides.

**Verification (read-only dry-run on a current prod snapshot).** With the new logic, **40 of 55** profiles lose the over-granted `war_room` (including IEA), `0` lose access they should keep, and the **7 actively-enrolled civs** — Everion, Nicea, The Pirate Syndicate, N//X, Shadow Worlds, Helghast, The Indominus Legion (all of which already carry `war_room` in their civ default via the 1.80.0 partner→civ backfill) — **keep** it for all their moderators. IEA leader before: `[…, war_room]`; after: `[approvals, batch_approvals, csv_import, settings, stats, system_create, system_edit]`. All 4 backend files byte-compile; `npm run build` clean (11.49s, 0 errors).

**Heads-up for deploy.** After the migration, the only non-super-admins who see the War Room are moderators of the 7 currently-enrolled civs. If any *other* civ should have it, grant it by editing that civ and checking **War Room** (or enrolling it via War Room Admin, which now sets the same flag).

**Deploy:** backend `--build` (migration v1.94.0 auto-runs at startup) + frontend rebuild. `/api/status` 1.85.0 → 1.86.0, `package.json` 1.75.0 → 1.75.1.

---

#### Master Haven 1.89.0 (2026-06-21) - Filter Dropdowns Fully De-duplicated + Variant-Tolerant Matching
While verifying the resource fix didn't break the Systems-tab / Cartographer filters, I flagged that the Economy-Type dropdown still showed near-duplicates the 1.86.0 `_dedup_clean` (case + edge-whitespace only) missed — e.g. `Power Generation` **and** `PowerGeneration` as two entries — plus junk like `1`. Parker: "fix the thing you noticed to make sure all are cleaned up."

**Why a naive dedup would have made it worse.** Collapsing `PowerGeneration` into `Power Generation` in the dropdown, while the filter still used exact `s.economy_type = ?`, would leave the `PowerGeneration`-stored systems **unfilterable** (you could no longer pick their spelling, and the canonical one wouldn't match them). So the dropdown and the filter have to share one normalization.

**Fix (two-sided, one normalizer).**
- New `norm_token(value)` in [db.py](Haven-UI/backend/db.py): lowercase, keep only alphanumerics (so `Power Generation` / `PowerGeneration` / `power-generation` all → `powergeneration`). Registered as a SQLite function on every connection in `get_db_connection` (`create_function(..., deterministic=True)` with a try/except fallback for older sqlite).
- **Dropdowns** ([routes/systems.py](Haven-UI/backend/routes/systems.py) `_dedup_clean`): group distinct values by `norm_token` (collapsing case **and** internal spacing/punctuation), drop single-char / pure-numeric keys (`1`), and surface the best-formatted variant per group (most word breaks → mixed case → longest). Applies to every system/planet categorical field.
- **Filter clauses** (`_build_advanced_filter_clauses`, [db.py](Haven-UI/backend/db.py)): `star_type`, `economy_type`, `economy_level`, `conflict_level`, `dominant_lifeform`, `stellar_classification`, `biome`, `weather`, `sentinel` now match via `norm_token(col) = norm_token(value)` (single `=` and multi `IN`) — the identical normalizer, so a collapsed option matches every stored variant. `is_complete` (grades) and `resource` (already materials/`LIKE`, case-insensitive) are unchanged.

**Verified** against the local DB: `economy_type` filtered as `Power Generation`, `PowerGeneration`, and `power generation` all return the **same 1084 systems** (and the raw DB confirms both spellings are stored); the economy/conflict/lifeform/star dropdowns come back dupe-free with `1` dropped; resource, multi-select (`Yellow,Blue`), and combined filters still match. AST-clean.

**Scope.** Backend-only — both the React Systems FilterModal and the Cartographer consume the same `/api/systems/filter-options` + `_build_advanced_filter_clauses`, so the fix lands on both with no frontend change. No schema change, no migration. Backend restart required. `/api/status` 1.84.1 → 1.85.0.

**Note (kept on purpose):** distinct-but-uncommon economy values like `Fusion` / `HighTech` / `Unknown` remain in the dropdown — they're real stored values (some system has them), not duplicates, so they stay filterable. A curated per-field allow-list (like resources got) would be the stricter option if those should be canonicalized too.

**Migration runner overhaul (added this pass).** Prompted by a heads-up that a parallel "war room visibility" fix also carries a DB migration. Parker correctly pushed back on the first cut ("just renumber to 1.94.0"): the deeper problem is the runner's *high-water-mark* model. `get_current_version` returned the **last-applied** version and `run_pending_migrations` ran only migrations numbered **strictly above** it — it never asked "did *this* migration run?" So any migration added at-or-below the watermark (an exact duplicate, OR a genuinely lower number added later by a parallel branch) was treated as already-in-the-past and **silently never ran** on a DB that had already passed that number (e.g. prod). Renumbering up only works because a higher number clears the watermark — a band-aid over a brittle design.

**Real fix — per-migration tracking** ([migrations.py](Haven-UI/backend/migrations.py)):
- New `_backfill_applied_versions_once()` bridges legacy DBs exactly once: it records every registered migration version ≤ the current watermark as applied (faithfully capturing the old logic's "everything ≤ watermark is done" assumption, so pre-tracking migrations don't suddenly re-run), then drops a `_per_migration_backfill` marker so it never repeats. Migrations above the watermark — and anything added later at any number — are deliberately NOT backfilled.
- `run_pending_migrations` now runs **any migration whose version isn't in the applied set** (`success=1`), independent of numeric ordering. A lower-numbered migration added later runs; a duplicate version still needs preventing (the set is keyed by version), so `register_migration` **raises on a duplicate version at import**.
- `get_current_version` now returns the **numerically-highest** applied real version (Python tuple sort, excludes the marker) instead of last-by-id — correct for display and for the bridge watermark.

**Verified end-to-end on temp DBs** simulating the real runner: a legacy DB at watermark `1.92.0` (pre-`1.13.0` unrecorded) bridges and runs only the new `1.93.0`; a re-run is a no-op; a later **lower** `1.50.5` (the exact landmine) now **runs**; war-room `1.94.0` runs; a fresh DB runs everything. The apparent `1.2.0` "duplicate" was a docstring example, never executed (93 migrations import clean). My materials migration `1.93.0` touches only `planets`/`moons` — zero war-room tables — and the war-room migration is now safe at **any** unique number.

---

#### Master Haven 1.88.1 (2026-06-21) - Fix Discovery Approval FK Failure + Re-link Rebuilt Planets/Moons by Name
Parker batch-approved a discovery backlog and every item came back `FOREIGN KEY constraint failed` (#92–#129, #169–#215): "these should of posted but for some reason are not."

**Root cause (pre-existing, surfaced by batch — not a batch bug).** The live `discoveries` table carries FK constraints the base `CREATE TABLE IF NOT EXISTS` in code never shows (that statement is a dead no-op against the long-existing prod table):
```
FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE SET NULL
FOREIGN KEY (planet_id) REFERENCES planets(id) ON DELETE SET NULL
FOREIGN KEY (moon_id)   REFERENCES moons(id)   ON DELETE SET NULL
```
With `PRAGMA foreign_keys=ON` (enabled in migration 1.65.0), approving a discovery whose stored `planet_id`/`moon_id` points at a row that no longer exists aborts the INSERT/UPDATE. Planet and moon rows are **deleted-and-reinserted with brand-new ids on every system rebuild** (the recurring planet-churn bug), so an old pending discovery routinely holds a dangling `planet_id`/`moon_id`. Confirmed on a copy of the local DB: pending rows have a valid `system_id` (stable UUID) but a **MISSING** `planet_id` (#1 → planet 7620, #3 → planet 3703); a raw insert with such an id reproduces the exact `FOREIGN KEY constraint failed`. Single-approve shares the identical INSERT, so it had the same latent failure — batch just ran it across the whole backlog and made it visible.

**Fix.** In the shared helper `_apply_discovery_approval` ([routes/discoveries.py](Haven-UI/backend/routes/discoveries.py)) — used by both single and batch approval — a new `_resolve_discovery_links()` resolves `planet_id`/`moon_id` against the live FKs before the insert/update:
1. **Keep** stored ids that still reference a live row (assigned to the right planet, unchanged).
2. For a dropped link (planet/moon rebuilt with a new id), **best-effort re-link to the correct CURRENT body by matching its name inside the discovery's `location_name`** against the system's planets/moons. `_match_body_by_name` is deliberately conservative — whole-name match bounded by non-alphanumerics, names ≥3 chars, the longest (most specific) match wins, and a tie between two distinct same-length names returns nothing rather than risk pinning the discovery to the wrong planet.
3. Only when nothing resolves does it **null the link** (approve "unlinked" / system-level, `location_name` text preserved) — so the FK can never fail.

The edit-target lookup was moved up front so the matcher knows the discovery's (fixed) system. `system_id` (a stable UUID, always resolved in the data) is left untouched, so the table's `CHECK ((system_id IS NOT NULL) OR location_type IN ('space','deep_space'))` is never tripped.

So the answer to "will they land on the right planet?" is **yes** for any discovery whose planet name appears in its location text (the common case), and unlinked-but-not-lost for the rest.

**Verified** on a copy of the local DB by replaying the resolver over the real pending rows: dead `planet_id 7620` → live **Usaling** (20995), dead `3703` → live **Nafut Gamma** (20958), and a coordinates-only row (`"-11.35, +53.07"`) correctly stays unlinked. A raw insert with a dangling planet still reproduces `FOREIGN KEY constraint failed`, while the guarded path succeeds. `discoveries.py` byte-compiles. Backend-only — no schema, no migration, no frontend change. `/api/status` 1.84.0 → 1.84.1. **Backend restart required.**

---

#### Master Haven 1.88.0 (2026-06-21) - Batch Approve / Reject for Discoveries
Parker: "look over our batch approval functions and see how we can put it for discoveries — do a full investigation and figure out how we can add the batch approval into discoveries."

**Investigation.** Three batch precedents existed; discoveries had none:
- **Systems** — `POST /api/approve_systems/batch` is an **async job queue**: returns `202 + job_id`, spawns a `fire_and_forget` worker (`_process_batch_approvals_sync`), writes progress to a `batch_jobs` table, and the frontend polls `GET /api/batch_jobs/{job_id}`. This heavy machinery exists for exactly one reason — system approval is expensive (glyph decode, planet/moon rebuild, completeness scoring, discovery promotion) and a ~100-system batch blew past Nginx Proxy Manager's 60s timeout, leaving the queue half-processed.
- **Region names** — `POST /api/approve_region_names/batch` is a simple **synchronous per-item loop** returning `{approved, failed, skipped}`.
- **Discoveries** — only single `approve_discovery` / `reject_discovery`; [DiscoveryApprovalTab.jsx](Haven-UI/src/components/approvals/DiscoveryApprovalTab.jsx) had no batch UI at all.

**Decision.** Per-discovery approval is light (parse JSON → one INSERT/UPDATE on `discoveries` → status flip → audit log → one `update_completeness_score`) and volume is low, so it follows the **region (synchronous) pattern**, NOT the systems job queue — there's no timeout problem to justify the async infra.

**Backend** ([routes/discoveries.py](Haven-UI/backend/routes/discoveries.py)). To avoid the recurring "sibling INSERT paths drift" problem, the body of `approve_discovery` and `reject_discovery` was extracted into shared, open-cursor, no-commit helpers — `_apply_discovery_approval(cursor, submission, session_data)` (handles the edit-vs-new branch, surface coords, status flip, audit log, completeness recompute; returns `{discovery_id, is_edit, discovery_name, discovery_type, parent_system_id}`; raises `HTTPException(400)` *before any write* if an edit's target discovery is gone) and `_apply_discovery_rejection(cursor, submission, reason, session_data)`. The single endpoints now delegate to them (no behavior change). Two new endpoints:
- `POST /api/approve_discoveries/batch` — per-item loop, ≤1000 ids, each item wrapped in a `SAVEPOINT` so one bad row rolls back only itself.
- `POST /api/reject_discoveries/batch` — one shared reason applied to all.

Both gate on `require_feature('approvals')` plus `batch_approvals` for non-super-admins, **skip (not fail)** already-reviewed rows and self-submissions so a partner can safely select-all, do one `conn.commit()` + one summary `add_activity_log`, and return `{approved|rejected, failed, skipped}`. No schema change — `pending_discoveries` already has `status`/`reviewed_by`/`review_date`/`rejection_reason`/`edit_discovery_id`.

**Frontend.** [DiscoveryApprovalTab.jsx](Haven-UI/src/components/approvals/DiscoveryApprovalTab.jsx) gains Batch Mode mirroring [SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx): a toggle (gated on `canAccess(FEATURES.BATCH_APPROVALS)`), per-pending-card checkboxes (self-submissions disabled, selected card gets `ring-2 ring-indigo-400`), a select-all-eligible / clear action bar with Approve(N) / Reject(N), a batch reject-reason modal, and a results modal (reads the flat `{approved/rejected, failed, skipped}` shape — no job polling). [PendingApprovals.jsx](Haven-UI/src/pages/PendingApprovals.jsx) now passes the `canAccess` prop (it wasn't before). `batchApproveDiscoveries(ids)` / `batchRejectDiscoveries(ids, reason)` added to [api.js](Haven-UI/src/utils/api.js).

**Verified.** `routes/discoveries.py` byte-compiles; `INSERT INTO discoveries` appears exactly once (helper only — no duplication); `npm run build` clean (13.34s, 0 errors, `PendingApprovals` chunk emitted). Backend restart + frontend rebuild required; **no migration**. `/api/status` 1.83.0 → 1.84.0, `package.json` 1.74.0 → 1.75.0.

---

#### Master Haven 1.87.0 (2026-06-21) - Cartographer Resource Filter Fixed End-to-End (Right Column, Canonical List, Searchable Dropdown)
Parker: "the resource dropdown list is hella broken and there's no search function to easily find the resource."

**Diagnosis (the breakage was data-deep, not just UI).** Three compounding problems:
1. **Wrong column.** The dropdown + the filter WHERE clause both used `planets.common_resource` / `uncommon_resource` / `rare_resource` — populated on **12 of 3,121 planets (0.4%)**. The real resource data lives in `planets.materials` (comma-joined, e.g. `"Salt, Gold, Copper"`), filled on **2,598 planets (83%)**. So filtering "Gold" matched **1 system** vs the **258** that actually have it. The filter was effectively dead.
2. **170-entry mess.** Parsing `materials` raw yields 170 "resources": case dupes (`Copper`/`copper`), typos/non-English (`Cooper`, `kupfer`, `uramium`, `doixit`, `Phsphorus`), bad separators (`Salt. Gold. Copper`, `Copper and uranium`), and non-resources (`Dissonance`, `High Sentinel Activity`).
3. **No search** — a native `<select>` of even ~40 items is painful.

**Decisions (Parker).** Do the deeper data fix AND *convert* the messy values to real resources rather than dropping them; reuse the same searchable dropdown UX as the Systems tab.

**Fix.**
- New [resource_catalog.py](Haven-UI/backend/resource_catalog.py): `CANONICAL_RESOURCES` (107 names, mirrors the curated front-end [adjectives.js](Haven-UI/src/data/adjectives.js) `resourcesList`) + `RESOURCE_ALIASES` (typo/variant → canonical, built from a live-data audit) + `normalize_materials()` — re-splits a cell on the various separators seen in the data, maps each recognizable token to its canonical name (with a conservative 1-edit fallback), and **preserves unrecognized tokens verbatim** so no information is lost.
- **Migration v1.93.0** normalizes `planets.materials` + `moons.materials` in place. Idempotent (a re-run changes nothing); the migration runner snapshots the DB first. Local dry-run: every typo/case/separator variant mapped correctly, the only preserved-verbatim tokens were genuine non-resources (`Dissonance`, `log`, `High Sentinel Activity`), 814 rows cleaned, second run 0 changes.
- `GET /api/systems/filter-options` `get_distinct_resources()` rewritten to source from normalized `materials ∩ canonical` → **170 → 42** real resources actually present.
- The `resource` clause in `_build_advanced_filter_clauses` ([db.py](Haven-UI/backend/db.py)) now matches against `materials` as a **comma-bounded, case-insensitive** token (normalizing stray `.` / ` and ` separators inline so pre-migration rows still match), with the dedicated columns kept as a fallback. End-to-end sim on a DB copy: Gold 258 / Copper 435 / Salt 357 / Magnetised Ferrite 356 systems.
- **Frontend** ([VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html)): the resource `<select>` is replaced by a **searchable combobox** — the vanilla-JS equivalent of the Systems-tab `SearchableSelect` (`react-select` can't run in the standalone map HTML). Type to filter, ↑↓/Enter to pick, ×/"Any" to clear, click-outside to close; a hidden `#cf-resource` input carries the selected value so `applyFilters()` / `updatePills()` are unchanged. Dark-theme `.cf-combo*` styling matches the panel.

**Scope/verify.** Also fixes the React Systems FilterModal (shares the same endpoint + filter clause; it already had a SearchableSelect). All backend files AST-clean; all 3 `<script>` blocks syntax-clean; `public/VH-Cartographer.html` copied to `dist/` (identical). Frontend rebuild + backend `--build` deploy; migration v1.93.0 auto-runs at startup.

**Follow-up (not done):** ingest-time normalization — new extractor uploads still write raw `materials`, so they'll re-pollute until `normalize_materials()` is also applied at the planet/moon INSERT paths (save/approve/extraction). The filter tolerates un-normalized rows (inline separator handling + case-insensitive match), and a future re-run of the v1.93.0 logic would re-clean, but the durable fix is to normalize on the way in.

`/api/status` 1.82.0 → 1.83.0, `package.json` 1.73.1 → 1.74.0.

---

#### Master Haven 1.86.0 (2026-06-20) - Cartographer Filter Polish (Community Filter, Real Galaxy List, Has Moons, Economy Dedup, Camera Framing)
Follow-up to 1.84.0 once the filters were working. Parker: "the filters are kinda weird — we filter some things and not all the good ones like galaxy / civ tags; economy type also has repeats in it; has planets should be has moons." Five targeted fixes ([VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) + [routes/systems.py](Haven-UI/backend/routes/systems.py)):

1. **Community (civ-tag) filter — new.** A `#cf-civ-tag` dropdown populated from the snapshot's `tag_pool` (skips only the empty/untagged bucket — "Personal" is a selectable option, per Parker), filtered **client-side** through `S.tagIndices` (the snapshot already carries each system's tag, so no fetch). Folds into the same matched-system set, hide logic, and pills as every other filter. `_populateCivTagDropdown` preserves the selection across a reality/galaxy reload.
2. **Galaxy list is now real, not 10 hardcoded options.** The snapshot returns a `galaxies` array (distinct, **reality-scoped but not galaxy-scoped** so the list stays complete even when the map is narrowed to one galaxy); `_populateGalaxyDropdown` builds the dropdown from it and preserves the current selection. Falls back to the static markup on an older snapshot.
3. **Has Planets → Has Moons.** Nearly every system has planets, so that toggle filtered almost nothing. Replaced with **Has Moons**, derived client-side in `parseSnapshot` from `planets_by_idx` (each planet tuple carries its `moon_count`) into `S.hasMoons`. (`S.hasPlanets` stays for the hover card.)
4. **Economy-type repeats fixed at the source.** `GET /api/systems/filter-options` now runs every distinct system/planet field through `_dedup_clean` (trim + case-insensitive dedupe, keeping the first-seen casing), so case/whitespace variants like "Trading" / "Trading " / "trading" collapse to one option. SQL `DISTINCT` had kept them split. Fixes the React Systems FilterModal too (same endpoint).
5. **Reality/Galaxy switch now visibly applies.** `reloadSnapshot` frames the camera back to the galaxy-home view (`flyTo` to origin at galaxy radius). Region coords differ per galaxy, so after a scope change the old camera target was pointing at empty space — the switch worked but "looked like nothing happened."

**Scope/verify.** Frontend map HTML + two read-side backend additions (`galaxies` field, filter-options dedup). No schema change, no migration. `routes/systems.py` AST-clean; all 3 `<script>` blocks syntax-clean; no stale `cf-has-planets`/`wantPlanets` refs; `public/VH-Cartographer.html` copied to `dist/` (identical). Frontend rebuild + backend `--build` deploy (the snapshot `galaxies` + the earlier `ri` field need the rebuilt image). `/api/status` 1.81.0 → 1.82.0, `package.json` 1.72.0 → 1.73.1.

---

#### Master Haven 1.85.0 (2026-06-20) - Track Trusted-Member Direct DB Saves (Events + Analytics)
Parker: "direct db submissions from trusted members are not tracked anywhere and it's just submitting and nothing for the ongoing events and tracking page." An end-to-end trace confirmed the oversight and found the root cause is a two-track pipeline gap, not a broken handler.

**The path.** "Direct DB submission" = `POST /api/save_system` ([control_room_api.py:2611](Haven-UI/backend/control_room_api.py#L2611)) — the trusted direct-save route used by super admins and partners/sub-admins with `system_create`/`system_edit`. It writes straight into the live `systems` table and **skips the `pending_systems` queue by design** (trusted bypass). On the tracking side it did exactly one thing: write an `approval_audit_log` row (`direct_add`/`direct_edit`) — the approval-log entry Parker already knew about. It did **not**:
- set `event_id` on the systems row — even though the wizard's EventPicker already puts `event_id` in the payload for everyone (admins included); the backend just dropped it.
- create a `pending_systems` row, or call `add_activity_log(...)`.

**Why that silently breaks tracking.**

| Surface | Reads from | Direct save showed? |
|---|---|---|
| Ongoing events (leaderboards) | `systems WHERE event_id = ?` ([events.py](Haven-UI/backend/routes/events.py)) | ❌ event_id was NULL |
| Analytics (leaderboard, community-stats, timeline, partner-overview) | `pending_systems` ([analytics.py](Haven-UI/backend/routes/analytics.py)) | ❌ no pending row |
| Public contributors + activity timeline | `pending_systems` | ❌ no pending row |
| Dashboard activity feed | `activity_logs` | ❌ no log entry |
| Browse / `/community-stats` system *totals* | `systems` table directly | ✅ (only place it counted) |

So a trusted member's upload existed and was browsable, but counted toward **no** event and **none** of the analytics/feed surfaces — exactly "just submits."

**Decisions (Parker, via approval):** (1) for analytics, **mirror each direct save as a pre-approved `pending_systems` row** rather than rewriting the analytics queries (those queries also depend on the approved/rejected/approval-rate columns that only `pending_systems` has — a `systems`-table rewrite would lose that); (2) **mirror both new saves and edits** (parity with the public queue, where every approved (re)submission is its own row); (3) **backfill** historical direct saves so past contributions count too.

**Fix (backend only — the frontend already collects + sends `event_id`).**
- **Event attribution.** `save_system` now imports and runs `resolve_submission_event_id(cursor, payload.get('event_id'), payload.get('discord_tag'), 'submission')` (the same validator the public path uses — a bad/expired pick resolves to None) and writes `event_id` onto the systems row: added to the INSERT, and `event_id = COALESCE(?, event_id)` on the UPDATE so an edit can't blank an existing link (mirrors `approve_system`). Direct saves now count toward live events immediately, since the event leaderboard keys off `systems.event_id`.
- **Analytics + feed visibility.** In the same transaction, `save_system` writes a pre-approved `pending_systems` mirror row: `status='approved'`, `reviewed_by`=self, `review_date`=now, `source='manual'`, `api_key_name='direct_save'` (marker), `edit_system_id`=the live system id (a back-link only — analytics ignores it and an already-approved row is never re-approved), `username_normalized` via `normalize_username_for_dedup`, `discord_tag`, `event_id`, and the full payload as `system_data`. Every existing analytics/contributors/timeline query then counts it with **zero query changes**, the manual/extractor split on `/community-stats` fills in (it was under-counting direct saves), and no double-count occurs (system totals come from the `systems` table independently). It never appears in the pending queue (filters `status='pending'`), and `find_matching_pending_system` ignores it (also filters `status='pending'`) so no false "pending duplicate" warnings. A matching `add_activity_log('system_approved', …)` call surfaces it in the Dashboard feed.
- **Backfill — migration v1.92.0** ([migrations.py](Haven-UI/backend/migrations.py)). Creates one mirror row per historical direct-saved system. The candidate set is taken **precisely** from `approval_audit_log` rows with `action IN ('direct_add','direct_edit')` (system_id parsed from the notes) — a queue-approved system has no such audit row, so a normal submission can never be mistaken for a direct save and double-counted. Attribution (`discovered_by`, `discord_tag`, `discovered_at`, glyph/region/galaxy/reality, `event_id`) is read from the live `systems` row; the blob is a minimal valid `system_data`. Idempotent: skips any system that already has a mirror row (`api_key_name='direct_save'`) and any system_id that no longer exists.

**Verification (local DB):** all four touched Python files byte-compile; the forward mirror INSERT fires the `glyph_code_suffix` trigger and stores `status='approved'` / `source='manual'` / `username_normalized` correctly; migration v1.92.0 created **199** mirror rows and a re-run created **0** more (idempotent).

**Scope/deploy:** backend-only, one endpoint + one migration; no schema change; no frontend change (EventPicker + `buildPayload` already ship `event_id`). Backend `--build` deploy required; migration v1.92.0 auto-runs at startup. `/api/status` 1.80.0 → 1.81.0.

---

#### Master Haven 1.84.0 (2026-06-20) - Cartographer Left-Sidebar Filters Actually Hide (Both Layers) + Reality/Galaxy Wired
Parker: "on the cartography page, the filter on the left does not work at all — nothing filters and nothing gets hidden." A full end-to-end trace found it wasn't a broken handler — it was an **architectural mismatch with the zoom-LOD render model**, and the sidebar had reinvented filtering while ignoring machinery that already existed in the same file.

**Root cause.** [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) renders two point clouds that crossfade by camera radius in `updateTier`: the **region** centroid dots (`S.regionPoints`, shown when zoomed out) and the **system** stars (`S.starPoints`, shown only when zoomed in — `systemOp = 0` above `CROSSFADE_MAX = 345`). The page loads at `radius 4400` (galaxy view), so the system layer is invisible. The sidebar's `applyFilters` → `_applyColorOverlay` only **dimmed the system cloud** (`0.05` grey), so at the default view it modified an invisible layer and never touched the visible region layer → "nothing filters." It only became visible if you zoomed all the way in.

**What already existed (the under-search Parker caught).** Three filter systems were in play and the sidebar was the odd one out: (1) the civ/contributor **territory focus** filter (`applyFocusFilter`, ~30 lines above the broken code) already masks + recolors the region cloud and dims labels; (2) the React **Systems FilterModal** is the canonical attribute filter over `/api/systems` + `/api/systems/filter-options` + `_build_advanced_filter_clauses`; (3) the broken `#carto-filters` sidebar reused #2's endpoints but applied the result to the wrong layer and ignored #1's region machinery. Both clouds use `THREE.AdditiveBlending`, so a point colored `(0,0,0)` is **truly invisible** — no shader changes needed to "hide."

**Fix (Parker's decisions: hide both layers + wire reality/galaxy).**
- **Unified matched set.** `applyFilters` now builds one matched-system `Set` (server `/api/systems`/`/api/systems/search` results intersected with the client-side star-type/has-station/has-planets predicates), routed through a single `_setMatched` choke point so the two layers can never drift.
- **True-hide systems.** New `_applySystemFilterHide` blacks out non-matching stars `(0,0,0)` and runs at the **tail of `updateColorMode`**, so any base repaint (color-mode switch, reload) re-applies the hide.
- **Hide regions consistently.** `_deriveMatchingRegions` maps matched systems → their regions via a new per-system region index; `applyFocusFilter` was generalized to compose the **attribute mask (hard hide, `k=0`)** with the **territory-focus mask (ghost, `k=0.06`)** for both dots and labels. A region is hidden iff **none** of its systems match — so a hidden region's systems are hidden too (Parker's explicit requirement).
- **Per-system region index (backend).** `GET /api/map/snapshot` ([routes/systems.py](Haven-UI/backend/routes/systems.py)) now emits `ri` (base64 LE Uint16, aligned to the per-system arrays, valued by position in the `regions` pool; `65535` = no region), decoded client-side into `S.systemRegionIdx`. Guarded: a snapshot without `ri` degrades to system-only hide rather than hiding every region.
- **Reality + Galaxy wired properly.** Both controls were dead (read by nothing). Added "All" to each; changing either now calls `reloadSnapshot()` — tears down + disposes the star/region/grid clouds, refetches `/api/map/snapshot?reality=&galaxy=` (the endpoint already supported the params and cache-keyed them), rebuilds, resets focus state, and re-applies the active attribute filter. The attribute fetch also passes the active scope so the matched set stays consistent.
- **Feedback.** A teal "N systems match" pill (`.carto-pill.count`) so an active filter is legible even when matches are off-screen.
- **Removed** the dead `_applyColorOverlay` and `resetStarColors`.

**Verification.** All 3 `<script>` blocks pass a `vm.Script` syntax check (incl. the large app script); `routes/systems.py` AST-parses clean; no dangling references to the removed functions; `public/VH-Cartographer.html` copied to `dist/` and confirmed byte-identical.

**Scope/deploy.** Frontend (map HTML) + one read-side backend field. No schema change, no migration. Requires a frontend rebuild **and** a backend `--build` deploy so the running image serves the new snapshot `ri` field (until then the frontend guard degrades to system-only hiding). `/api/status` 1.79.0 → 1.80.0, `package.json` 1.71.0 → 1.72.0.

---

#### Master Haven 1.83.0 (2026-06-20) - Sub-Admin Membership Cleanup (Retire Legacy Creation, Moderation Page)
Parker: "the sub admin membership is kinda broken … there is the old method of manually creating a subadmin profile by username and password in the access control - sub admin page - we need to clean this up and make sure it works."

**The problem — two parallel sub-admin systems, the old one a silent dead-end.**
- **New (canonical, since migration 1.80.0):** identity in `user_profiles`, civ membership + role (leader / co_leader / sub_admin) in `civilization_members`. You elevate someone via [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx) → Add member. `tier` + `enabled_features` are *derived* from membership (`_recompute_profile_tier` / `_recompute_profile_features`).
- **Old (legacy leftover):** [SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx) "Create Sub-Admin" wrote a username+password row into `sub_admin_accounts` **only** — no `user_profiles` row, no `civilization_members` row.

**Why the old page was broken, not just redundant:** login ([routes/auth.py](Haven-UI/backend/routes/auth.py)) checks `user_profiles` by normalized username **first** and only falls back to `sub_admin_accounts` if no profile exists. Anyone you'd make a sub-admin has usually already submitted → they already have a `user_profiles` row → login resolves to that (a plain tier-4 member) and **never reaches the fallback**. So the account was dead on arrival, invisible in Civilization Management, with no `profile_id` (breaking profile-based self-approval / "acting as"). Migration 1.80.0 already folded existing sub-admins into `civilization_members`, so the table was purely a creation dead-end.

**Decisions (Parker):** (1) remove the manual username+password creation; (2) require an **existing profile** to elevate (no account-from-scratch); (3) make the page a **moderation panel** where a sub-admin's permissions/features can be added/removed/changed.

**Backend** ([routes/partners.py](Haven-UI/backend/routes/partners.py), [routes/civilizations.py](Haven-UI/backend/routes/civilizations.py)):
- `GET /api/sub_admins` repurposed from a `sub_admin_accounts` CRUD list into a **roster** over `civilization_members JOIN user_profiles JOIN civilizations` (role=`sub_admin`). Each row carries the civ (tag/name), effective `enabled_features`, the raw `enabled_features_override` (null ⇒ inheriting the civ default), `civ_default_features`, `can_approve_personal_uploads`, and last login. Scope: super admin → all civs (optional `?civ_id`); leader/co_leader → only civs they lead; anyone else → empty.
- **Removed** the four legacy `sub_admin_accounts` writers: `POST /api/sub_admins`, `PUT /api/sub_admins/{id}`, `DELETE /api/sub_admins/{id}`, `POST /api/sub_admins/{id}/reset_password`. (`SubAdminManagement` was the only caller.)
- New `_require_civ_manage_access(session, civ_id)` — super admin OR a leader/co_leader of that civ (read from the session's `civ_memberships`, no DB hit) — now gates `add_member` / `update_member` / `remove_member` (previously super-admin-only). This lets a civ's own leaders moderate their sub-admins, restoring the self-management partners had on the old page, while super admin still manages any civ. The H-CM1 last-leader guard and tier/feature recompute are unchanged.

**Frontend** ([SubAdminManagement.jsx](Haven-UI/src/pages/SubAdminManagement.jsx)): rewritten into a moderation panel — sub-admins grouped by civilization, each with a feature editor (per-member override + **Save permissions** / **Reset to civ default**), an **Approve personal** toggle, and **Revoke**, all hitting `PUT`/`DELETE /api/civilizations/{civ_id}/members/{profile_id}`. **Add Sub-Admin** elevates an *existing* profile only (`/api/profiles/lookup` → `POST /api/civilizations/{id}/members` with role `sub_admin`); no username/password/reset UI remains. An amber banner points leader/co-leader management + brand edits at [CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx). [AccessControl.jsx](Haven-UI/src/pages/AccessControl.jsx) Sub-Admins tab description updated.

**Scope/safety:** read- and permission-side only; **no schema change, no migration.** The legacy login fallback for any pre-existing `sub_admin_accounts` rows is left intact so nobody is locked out; stranded legacy rows are not auto-migrated (re-elevate via the new flow if a specific account needs it). The recurrence is structurally prevented because no new `sub_admin_accounts` rows can be created.

**Verification:** `partners.py` + `civilizations.py` byte-compile; `npm run build` clean (12.23s, 0 errors). Frontend rebuild + backend restart required. `/api/status` 1.78.0 → 1.79.0, `package.json` 1.70.0 → 1.71.0.

---

#### Master Haven 1.82.0 (2026-06-20) - "Find Glyph by Name" Tool (Reverse Glyph Resolver, On-Site)
Parker had a standalone `glyphtool` (a reverse glyph resolver: system name → 12-glyph portal code, by leaning on Haven's catalogue) and asked to make it **easier to use**. He chose to put it **on the website** rather than keep it as a Python CLI, so this productionizes it as a first-class web feature.

**What it does.** You know a system by name (off a spreadsheet, a Discord post, the site) and want the portal glyphs to actually travel there in-game. The standalone tool did this in three tiers (catalog → region → namegen) by hitting the public API over HTTP. On the site, the backend already *has* the systems DB locally, so the high-value Tier 1 (catalogue) becomes a single instant SQL query — no HTTP round-trips at all.

**Backend** — new `GET /api/glyph/resolve?name=&galaxy=&reality=` ([routes/systems.py](Haven-UI/backend/routes/systems.py)):
- Exact name match (`COLLATE NOCASE`) over `systems`, optional galaxy/reality scoping, dedupe by `glyph_code`.
- New module-level `_decode_glyph_parts()` splits the 12-char code into planet / SSI / region_x/y/z using the **same validated bit-packing** the standalone tool uses (P·SSS·YY·ZZZ·XXX).
- Each candidate carries the stored glyph, decoded SSI/region, star type, discoverer, and `completeness_grade` (via `score_to_grade`).
- **Confidence** reflects ambiguity (NMS procgen names repeat heavily): high = 1 match, medium = 2-5, low = >5, none = 0. All candidates are returned with galaxy + region so the user picks the right one.
- No exact match → fuzzy name-`LIKE` **suggestions** (capped 12), flagged as non-authoritative.
- Honors `archived_civ_filter('s')` for non-super-admins + `apply_data_restrictions`, same privacy posture as `/api/systems/search`. Read-only — no schema, no migration.

**Frontend** — new public page [GlyphFinder.jsx](Haven-UI/src/pages/GlyphFinder.jsx) at `/glyph-finder`:
- Name input + optional galaxy dropdown (from [galaxies.js](Haven-UI/src/data/galaxies.js)) + reality select; Enter submits.
- Results render a confidence banner and candidate cards showing the **actual glyph art** (reuses [GlyphDisplay.jsx](Haven-UI/src/components/GlyphDisplay.jsx)), the copyable hex code (one-click Copy with a `window.prompt` fallback for non-HTTPS), star pill, grade letter, region/SSI, and a "View system →" link by id (avoids the duplicate-name disambiguation bounce).
- No-match state shows fuzzy "did you mean" suggestions or a helpful empty message; initial state explains the tool.
- Styled entirely with the 2.0 utilities (`.haven-card`, `.haven-btn-*`, `.pill`, `.pill-star-*`, `.grade-*`).
- Wiring: `resolveGlyphByName` in [api.js](Haven-UI/src/utils/api.js); lazy route in [App.jsx](Haven-UI/src/App.jsx); "Glyph Finder" top-level link in [Navbar.jsx](Haven-UI/src/components/Navbar.jsx) `NAV_LINKS` (renders in desktop + mobile from the one source).

**Verification.** Backend byte-compiles; frontend `npm run build` clean (11.73s, 0 errors, `GlyphFinder` chunk emitted). The endpoint was exercised in-process against the local DB (13,609 glyphed systems): exact unique → high (`Oculi` → `20720193DFA9`, SSI 114 / planet 2, grade S); ambiguous → low (11× `Jinoomo-Iryun XIX`, each a distinct glyph in region 4091,5,4); 2-char short-guard returns empty; partial "Ocul" returns 0 exact + 2 suggestions.

**Scope/deploy.** Frontend + read-only backend; no schema change, no migration. Frontend rebuild + backend restart required. `/api/status` 1.77.1 → 1.78.0, `package.json` 1.69.0 → 1.70.0. The standalone `glyphtool/` stays as-is for CLI/automation use; its Tier-3 namegen path remains the only thing not mirrored on the site (it's off in the tool too).

---

#### Master Haven 1.81.1 (2026-06-19) - Fix Dormant S+ Grade (Cached `is_fully_charted` Drift)
Parker: on `https://havenmap.online/haven-ui/systems/Mabaya` the disambiguation picker shows two Mabayas, "they both show S class when the second one — the one we've been working on that's fully uploaded — is S+ and it doesn't display."

**Diagnosis (traced end-to-end against live prod).** There are two grade code paths and they had silently diverged:

- **Live recompute** — used by the SystemDetail header *and the disambiguation picker* (`calculate_completeness_score` → runs the S+ checklist live). The deployed API already returned the correct grades: first Mabaya `8b714092` = **S**, showcase `5547c89d` = **S+**. The deployed frontend (`gradeColors` + `SystemDetail`) also renders S+ in cyan. So this path was *already correct*.
- **Cached column** — `score_to_grade(score, bool(is_fully_charted))`, used by the systems list, search, galaxy-summary grade bars, the 3D map, system cards/thumbnails, and posters. The showcase Mabaya had `is_fully_charted = 0` (score 100), so all of these rendered **S**, permanently disagreeing with the detail page's S+.

Querying prod made the scale of it clear: **0 of 14,137 systems were flagged S+**, despite 7,738 sitting in the S band — the whole S+ tier was effectively dormant.

**Root cause.** Migration **1.90.0** added `is_fully_charted` and re-scored every system, running the S+ checklist — but it ran while the showcase Mabaya's discoveries were still **orphaned** (`discoveries.planet_id` pointing at planet rows that had been deleted-and-reinserted with new ids — the recurring "Mabaya planet tags wiped" bug). The S+ checklist requires a discovery on every planet, so it correctly scored 0 at that moment. The Master Haven 1.79.0 one-off prod data script then re-pointed `discoveries.planet_id` to the live planets but **never re-ran `update_completeness_score`**, so `is_fully_charted` stayed frozen at 0. Confirmed the live checklist now passes for `5547c89d`: 6 planets, every planet has a wonder note + a linked discovery, a documented base (Gelt), a recorded station, 0 moons, 66 discoveries all linked.

A code audit found the systemic gap behind the drift: `update_completeness_score` runs on the save/approve-system/stub/csv paths, but **not** when a discovery is approved — even though a discovery's planet/moon link is a primary S+ input. (The two planet-rebuild paths, `save_system` and batch-approve, already recompute *after* `relink_discoveries_after_rebuild`, so they were fine; the stale data came purely from the out-of-band 1.79.0 script.)

**Fix (durable, backend-only).**
1. **`approve_discovery`** ([routes/discoveries.py](Haven-UI/backend/routes/discoveries.py)) now recomputes the parent system's completeness after the live discovery insert/EDIT, before commit. The parent is `discovery_data['system_id']` on insert, or the live row's preserved `system_id` on an edit (edits can change planet/moon but never the system). Wrapped in a try/except so a scoring hiccup can't fail the approval. This stops the drift at the source going forward.
2. **Migration v1.91.0** ([migrations.py](Haven-UI/backend/migrations.py)) re-scores every system to repair the existing drift — the same idempotent pass 1.90.0 used (reuses `update_completeness_score`, sets `sqlite3.Row` factory, restores it after). On deploy this flips the showcase Mabaya (and every other genuinely fully-charted system) to `is_fully_charted = 1`, so the list / map / search / posters finally agree with the detail page on S+.

**Verification.** Ran the live scorer against a current prod snapshot inside the container (rolled back, no writes): showcase Mabaya → score 100 / **grade S+ / fully_charted True**; mining Mabaya → score 95 / grade S / False. All three edited Python files AST-parse clean.

**Scope.** Backend-only; no schema change beyond the (already-present) `is_fully_charted` column, no frontend change (both the live and cached paths already know how to render S+). **Backend restart required**; migration v1.91.0 auto-runs at startup. `/api/status` 1.77.0 → 1.77.1.

---

#### Master Haven 1.81.0 (2026-06-19) - Visual Glyphs Under the Hex (System Cards + Detail Header)
Parker: on the Systems-tab system card "we don't display the actual glyphs — we only display the hex value and people don't understand the hex fully." He wanted the real NMS portal glyph symbols shown directly under the 12-char hex code.

**Pure frontend, pure reuse — no backend touch.** Everything needed already existed:
- [GlyphDisplay.jsx](Haven-UI/src/components/GlyphDisplay.jsx) renders a 12-char `glyphCode` string as the actual glyph images (already used in [SystemApprovalTab.jsx](Haven-UI/src/components/approvals/SystemApprovalTab.jsx)).
- It's backed by the single-source [glyphAssets.js](Haven-UI/src/utils/glyphAssets.js), whose 16 `.webp` glyphs are tiny enough that Vite inlines them as base64 data URIs — so they render in dev, prod, and posters with zero mount/runtime dependency.
- `glyph_code` is already present in both the `/api/systems` list payload and the system-detail payload (the card and table already rendered the hex from it), so there was nothing to add server-side.

**Two placements (decided with Parker up front):**
1. **System card** — [SystemsList.jsx](Haven-UI/src/components/SystemsList.jsx) `SystemCard`: a `size="small"` (20px tile) glyph row in the card body, between the planet/lifeform stat block and the completeness/discoverer footer. The 12-glyph row is ~260px and fits one line, wrapping gracefully on narrow cards. Placed in the body (not overlaid on the poster) to keep the thumbnail art clean.
2. **System detail header** — [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx): the same `size="small"` row in an `mt-2` div directly under the mono `glyph_code · stellar_classification · discovered by` subtitle (the Mabaya-style hero).

**Scope/safety:** both rows are gated on a present `glyph_code`, and GlyphDisplay itself falls back to plain text for missing or non-12-char codes, so legacy/stub systems without a clean glyph degrade without breaking. The table view stays hex (the Glyph column is too narrow for 12 tiles). No schema change, no migration, no backend restart — frontend rebuild + `--build` deploy only.

**Verification:** `npm run build` clean (13.08s, 0 errors); the `glyphAssets` chunk and the `Systems` chunk both emit. `package.json` 1.68.0 → 1.69.0.

---

#### Master Haven 1.78.0 (2026-06-19) - Pretty System URLs + Discovery Links on SystemDetail
Two UX features Parker asked for: clean, human-readable system URLs, and being able to open a discovery from the system page without leaving it.

**Feature 1 — pretty system URLs (`/systems/Mabaya` instead of `/systems/1234`)**

Every share/bookmark URL was an opaque `/systems/1234` numeric ID. Systems are now linked by name everywhere.

- **Backend** (`get_system` in [control_room_api.py](Haven-UI/backend/control_room_api.py)): resolves **id-first** (`SELECT * FROM systems WHERE id = ?`) so every existing numeric bookmark keeps working, then falls back to a **case-insensitive name lookup** (`WHERE name = ? COLLATE NOCASE`, backed by the existing `idx_systems_name`). A name shared by more than one system returns **HTTP 300** with `{multiple: true, systems: [{id, name, galaxy, reality, glyph_code, discord_tag, completeness_grade}]}` instead of guessing.
- **Frontend** — all 8 navigation sites now route to `/systems/${encodeURIComponent(name)}`: [SystemsList.jsx](Haven-UI/src/components/SystemsList.jsx), [SearchOverlay.jsx](Haven-UI/src/components/SearchOverlay.jsx), [Search.jsx](Haven-UI/src/pages/Search.jsx), [RegionDetail.jsx](Haven-UI/src/pages/RegionDetail.jsx), [CommunityDetail.jsx](Haven-UI/src/pages/CommunityDetail.jsx), [Profile.jsx](Haven-UI/src/pages/Profile.jsx) (keeps its `/haven-ui/` prefix), [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) success screen, and [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx)'s location link. [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) `reload()` rewrites the address bar to the canonical name via `window.history.replaceState` whenever it arrived via an id or non-canonical casing (no re-fetch), and renders a **disambiguation picker** when the API returns 300 (each card loads its specific system by id, which then replaceState's to the name). The `/systems/:id` route is unchanged — `:id` matches any string.

**Feature 2 — clickable discovery links on SystemDetail (hybrid modal + URL sync)**

The system page already listed linked discoveries (grouped by planet / moon / space / unlinked) but each chip was a `<Link>` that navigated away to the discovery-type page. Chips now open the full [DiscoveryDetailModal](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx) **in place**:

- State `selectedDiscovery` + URL sync via the existing `searchParams`: clicking sets `?discovery=<id>`; closing removes it; on load, `?discovery=<id>` auto-opens the matching discovery (deep-linkable / shareable).
- The system-detail discovery shape is bridged to what the modal expects: each opened discovery is enriched with `system_id`/`system_name`/`system_galaxy`/`system_is_stub` from the parent and `is_featured` (mapped from the `featured` alias). `type_info` (emoji/label), `evidence_url`, and `photo_url` are now supplied by the **backend** discoveries SELECT (mirrors what browse/recent do) so no client-side type map is needed and the modal's photo gallery + external-links sections render.

**Scope:** frontend + read-side backend only. No schema change, no migration. The backend needs a restart for the new discovery read fields (`evidence_url`/`photo_url`/`is_featured`/`type_info`); the frontend degrades gracefully without them.

**Verification:** `npm run build` clean (2738 modules, 0 errors). Resolution paths confirmed: numeric-id → 200, exact name → 200, lowercase name → 200, nonexistent → 404, duplicate name → 300 with the 7-key candidate cards; and that a system's discoveries come back with `type_info`/`evidence_url`/`photo_url`/`is_featured`.

---

#### Backend API 1.75.0 (2026-06-19) - Name-Based System Lookup + Discovery Read Fields
See Master Haven 1.78.0. `GET /api/systems/{system_id}` ([control_room_api.py](Haven-UI/backend/control_room_api.py)) now tries `SELECT * FROM systems WHERE id = ?` first (preserves old numeric bookmarks), then `SELECT * FROM systems WHERE name = ? COLLATE NOCASE`; >1 name match → `JSONResponse(status_code=300, {multiple, systems:[…7 fields incl. completeness_grade…]})`. The system-detail discoveries SELECT adds `d.evidence_url`, `d.photo_url`, `d.is_featured`, and attaches `type_info = DISCOVERY_TYPE_INFO[slug]` per row (slug via `get_discovery_type_slug`). Read-side only; no schema/migration. `/api/status` 1.74.2 → 1.75.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py). Requires a backend restart.

---

#### Haven-UI 1.67.0 (2026-06-19) - Pretty System URLs + SystemDetail Discovery Modal
See Master Haven 1.78.0. Every system nav link now uses `encodeURIComponent(name)` ([SystemsList.jsx](Haven-UI/src/components/SystemsList.jsx), [SearchOverlay.jsx](Haven-UI/src/components/SearchOverlay.jsx), [Search.jsx](Haven-UI/src/pages/Search.jsx), [RegionDetail.jsx](Haven-UI/src/pages/RegionDetail.jsx), [CommunityDetail.jsx](Haven-UI/src/pages/CommunityDetail.jsx), [Profile.jsx](Haven-UI/src/pages/Profile.jsx), [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx), [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx)). [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx): `replaceState` to the clean name URL after an id/non-canonical load, a 300-disambiguation picker, and `DiscoveryGroup`/orphan chips converted from `<Link>` to buttons that open `DiscoveryDetailModal` with `?discovery=<id>` URL sync + parent-system enrichment. `package.json` 1.66.4 → 1.67.0.

---

#### Master Haven 1.79.1 (2026-06-19) - Fix Search-Result Clicks Opening the Disambiguation Picker
Parker: "the search is broken — when you search a system and click on the right one it takes me to the page to 'choose which system,' and I think it's from the URL change."

**Cause.** The 1.78.0 Pretty-URLs feature made every system link navigate to `/systems/<name>`. The backend resolves that by name and, when more than one system shares the name, returns **HTTP 300** with a candidate list for SystemDetail to render as a disambiguation picker. NMS procgen system names repeat constantly (e.g. there are two "Mabaya"), so clicking a *specific* search result — where the user has already chosen exactly one system — still navigated by name and re-ambiguated it into the picker. It looked like search was broken.

**Fix, two parts:**
1. **Navigate by id, not name.** All 8 sites where a user clicks a specific system now route to `/systems/<uuid>` (the id resolves to exactly one system — no 300): [SearchOverlay.jsx](Haven-UI/src/components/SearchOverlay.jsx), [SystemsList.jsx](Haven-UI/src/components/SystemsList.jsx), [Search.jsx](Haven-UI/src/pages/Search.jsx), [RegionDetail.jsx](Haven-UI/src/pages/RegionDetail.jsx), [CommunityDetail.jsx](Haven-UI/src/pages/CommunityDetail.jsx), [Profile.jsx](Haven-UI/src/pages/Profile.jsx), [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx), and the [Wizard.jsx](Haven-UI/src/pages/Wizard.jsx) success screen (recently-viewed hrefs updated to match).
2. **Only prettify unique names.** `GET /api/systems/{id}` now returns `name_unique` (`COUNT(*) FROM systems WHERE name = ? COLLATE NOCASE <= 1`). [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) rewrites the address bar to `/systems/<name>` **only when `name_unique` is true**; for a duplicate-named system it keeps the id URL, so refresh/share lands on that exact system instead of the picker.

Net: pretty `/systems/<name>` URLs still apply for unique names (the common case); duplicate-named systems get a stable id URL; the disambiguation picker now appears only when someone genuinely visits an ambiguous name directly, never on a result click. Frontend build verified clean; backend compiles. **Frontend rebuild + backend restart required.** `/api/status` 1.76.0 → 1.76.1, `package.json` 1.67.0 → 1.67.1.

---

#### Master Haven 1.79.0 (2026-06-19) - Fix Recurring Mabaya "Planet Tags Wiped" (Discoveries Orphaned on Every Edit)
Parker: "with mabaya there is an issue again — the planet tags got wiped again … i think the super admin login caused it." On the SystemDetail page all 64 of Mabaya's discoveries had fallen into the "✦ In space" group.

**Diagnosis.** The system in question is `5547c89d-1663-45ca-9cdd-c2e79b38d50f` (Ekimo / WhrStrsG, 64 discoveries). Its planets, moons, station, and special-attribute tags (`ancient_bones`, `water_world`, `salvageable_scrap`, `gravitino_balls`) were all **intact and correct** — what broke was the discovery→planet *links*. All 64 discoveries pointed at planet ids **35149–35154**, which no longer existed; the live planets had been re-created with ids **36524–36529**. So every discovery's `planet_id` was dangling and rendered as in-space ("planet tags" = which planet each discovery is pinned to).

**Root cause (confirmed).** The admin direct-save path `POST /api/save_system` — what runs when a logged-in admin clicks **Save** in the wizard — does `DELETE FROM planets WHERE system_id=?` and re-inserts every planet with brand-new auto-increment ids ([control_room_api.py](Haven-UI/backend/control_room_api.py#L2808)), but never re-pointed the existing `discoveries.planet_id` rows. The system's `last_updated_at` (2026-06-19 23:07:43, by 'Haven') was a direct save ~10 min after the last pending approval — exactly Parker's "super admin login" hypothesis. The batch-approve edit path ([routes/approvals.py](Haven-UI/backend/routes/approvals.py)) had the identical gap. This is the same bug *class* that hit Mabaya on 06-18 (that time the planets were fully wiped by an empty-edit approval); Mabaya keeps breaking because it's a 64-discovery showcase and every edit churns its planet ids.

**Data fix (already applied to prod).** The discoveries were never lost — all 64 still exist (`discoveries` ids 68–142, status `approved`). Re-uploading would have created 64 duplicates; instead each was re-pointed to the planet of the same name. The `pending_systems` snapshot id 9835 (a verbatim 61 KB JSON snapshot) preserves each discovery's original `planet_id` and each planet's id↔name, giving a deterministic remap: 35149→36524, 35150→36525, 35151→36526, 35152→36527, 35153→36528, 35154→36529. **64/64 remapped cleanly, 0 orphaned afterward.** Live DB was copied to a `FORENSIC_mabaya_relink_*.db` first; the relink ran in one transaction.

**Code fix (prevents recurrence).** Two shared helpers in [db.py](Haven-UI/backend/db.py): `snapshot_child_name_maps(cursor, system_id)` captures `{planet_name → old id}` and `{(parent_planet, moon_name) → old moon id}` BEFORE a delete-and-reinsert; `relink_discoveries_after_rebuild(...)` re-points `discoveries.planet_id`/`moon_id` to the new ids by name AFTER. Wired into both delete-and-reinsert paths (`save_system` + batch-approve edit). The single-approve edit path already merges planets by name (preserves ids), so it was left untouched. Name matching is stripped + case-insensitive (tolerates the trailing spaces in Mabaya's planet names). Verified with an end-to-end simulation: planet relink, trailing-space tolerance, moon relink, other-system discoveries untouched, zero orphans.

**Scope.** Backend-only; no schema change, no migration. `/api/status` 1.75.0 → 1.76.0. **Backend restart required** for the code fix to take effect (the data fix is already live).

---

#### Master Haven 1.77.1 (2026-06-19) - Phantom Star Detection Fix for Purple and Shadow Stars
The Wizard's glyph decoder flagged Purple star systems (SSI 1001-1065, added by NMS Worlds Part II with the Atlantid Drive) and the Shadow/Glass star (SSI 1000) as "PHANTOM" because `is_phantom_star()` used a simple threshold of `solar_system_index >= 600`. The threshold predated Purple stars entirely and only had a single hardcoded exception for SSI 1000.

**Root cause:** The Solar System Index (SSI) address space has valid ranges separated by phantom gaps:
- SSI 0: Phantom (always)
- SSI 1–767 (0x001–0x2FF): Valid — Yellow/Red/Green/Blue stars (~600 practically found, extends to 767)
- SSI 768–999 (0x300–0x3E7): Phantom gap between YRGB and Shadow/Purple
- SSI 1000 (0x3E8): Valid — Shadow/Glass star (hyperjump only, invisible on galactic map)
- SSI 1001–1065 (0x3E9–0x429): Valid — Purple stars (require Atlantid Drive, added Worlds Part II)
- SSI 1066+ (0x42A–0xFFF): Phantom (upper range)

The old code had `PHANTOM_SSS_THRESHOLD = 0x258` (600) with a single exception for `PHANTOM_SSS_EXCEPTION = 0x3E8` (1000). Everything ≥600 except 1000 was flagged phantom — including the entire valid YRGB range from 600-767 and all Purple stars.

**Fix:** Replaced the three threshold constants with range constants (`VALID_SSI_YRGB`, `VALID_SSI_SHADOW`, `VALID_SSI_PURPLE`) and rewrote `is_phantom_star()` to check membership in valid ranges. No frontend change — `GlyphPicker.jsx` reads the backend's `is_phantom` flag from the `/api/glyph/decode` response.

**Backend only** — `glyph_decoder.py` + version bumps. Requires backend restart on the Pi.

---

#### Haven-UI 1.66.2 (2026-06-19) - Expandable Completeness Detail + Neutral Zero-Score Bars
Two follow-up tweaks to the completeness breakdown panel on the SystemDetail page (the one fixed in 1.66.1). **Frontend only** — the backend already returns everything needed in `breakdown.details` and is untouched.

**1. Expandable per-category detail**

Each category row in `CompletenessBreakdown` ([SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx)) became a `<details>`/`<summary>` element. The summary keeps the existing label + `score/max` + progress bar; expanding reveals the backend's per-field detail for that category:

- **Flat categories** (`system_core`, `system_extra`, `planet_coverage`, `space_station`): a list of `{name, value, status}` rows.
- **Planet-grouped categories** (`planet_environment`, `planet_life`): each planet renders as a sub-header with its `filled/total` count and its fields indented under a left border. Detection is structural — `Array.isArray(item.fields)` — so it stays correct regardless of category key.

New `CompletenessField` helper + `COMPLETENESS_STATUS` map drive the per-field styling: `status:'filled'` → green ✓ and the value text; `status:'missing'` → red ✕ and muted "Missing"; `status:'skipped'` → muted – and "N/A" (dead-biome planets legitimately skip fauna/flora). Layout is compact and mobile-first (`text-[11px]`, truncation, value capped at 58% width). A small ▶ caret rotates open via `group-open:rotate-90`; the default `<summary>` marker is hidden with `[&::-webkit-details-marker]:hidden` + `list-none`. No new state — `<details>` carries its own open/closed.

**2. Zero-score categories render neutral grey, not red**

Per Parker, the red Space Station bar "seems derogatory" when a system simply hasn't had a station uploaded yet. The bar color logic now special-cases `catScore === 0` to grey (`#6b7280`) for both the bar fill and the `score/max` text. Red (`#f87171`) is reserved for categories with SOME data but little (1-39%); 85+ green, 65+ blue, 40+ amber unchanged. Zero now reads as "not filled in yet" (neutral) instead of "bad."

**Build/deploy.** `npm run build` ran clean; the three map HTML files (`VH-System-View.html`, `VH-Cartographer.html`, `VH-Map-ThreeJS.html`) were re-copied `public/` → `dist/` (vite clobbers them on build). `package.json` 1.66.1 → 1.66.2. Frontend-only; no backend change, no migration.

---

#### Haven-UI 1.66.1 (2026-06-19) - Fix Empty Completeness Breakdown Bars on SystemDetail
The completeness breakdown panel on the SystemDetail page rendered every per-category progress bar empty. Pure frontend data-shape mismatch — **the backend was always correct and is untouched.**

**Root cause (3 compounding bugs)**
1. **Shape mismatch.** `services/completeness.py` returns `breakdown.<category>` as a **raw number** (`{'system_core': 35, 'system_extra': 10, …}`). The `CompletenessBreakdown` component in [SystemDetail.jsx](Haven-UI/src/pages/SystemDetail.jsx) read `cat.score` and `cat.max` off that number — both `undefined`, so `pct` computed to `0` and every bar filled to 0% width with a `undefined/undefined` label.
2. **Falsy guard.** The row guard was `if (!cat) return null`. For a category scoring exactly `0`, `!0 === true`, so that category's row vanished entirely instead of showing a legitimately-empty bar.
3. **Phantom category.** `COMPLETENESS_CATEGORIES` listed `['planet_detail', 'Planet Detail']`, but the backend `breakdown` has no `planet_detail` key (the scorer has 6 categories: system_core, system_extra, planet_coverage, planet_environment, planet_life, space_station). That row was always hidden anyway.

**Fix (frontend only)**
- `COMPLETENESS_CATEGORIES` now carries the per-category max weight as a third tuple element, sourced from the backend's scoring caps (verified in `completeness.py`: 35 / 10 / 10 / 25 / 15 / 5 = 100). Dropped `planet_detail`.
- Render reads the raw number directly: `const catScore = breakdown[key]`, `pct = max ? round(catScore / max * 100) : 0`.
- Guard changed to `if (catScore == null) return null` so missing categories still hide but a genuine `0` renders an empty bar.

**Map grade scale (verified, no change)**
Confirmed S+ (diamond cyan `#22d3ee`) is already present in both inline map grade scales — [VH-System-View.html](Haven-UI/public/VH-System-View.html) (`TIER_COLORS` consumed by `getGradeStyle`) and [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) (`cf-grade` filter pills). No edit needed; the prior S+ code pass covered both.

**Build/deploy.** `npm run build` ran clean; the three map HTML files were re-copied `public/` → `dist/` (vite's `public` copy clobbers them on build). `package.json` 1.66.0 → 1.66.1. Frontend-only; no backend change, no migration.

---

#### Master Haven 1.75.0 (2026-06-17) - Edit Discoveries Through the Approval Queue
Discoveries could be submitted and approved, but there was no way to *edit* an existing one — unlike systems, which have a full edit-through-approvals flow. Parker asked for parity: "edit the discoveries the same way everything else is edited — going through pending approvals."

**Design (confirmed with Parker)**
- **Anyone** can edit (same as the system Edit button, which is ungated) — the approval queue is the safety net.
- The approval card shows an **old → new diff**.
- An edit can change the planet/moon (location within a system) but **cannot move a discovery to a different system**.

**Model — `edit_discovery_id`, the mirror of `edit_system_id`**

Migration **v1.87.0** adds a nullable `pending_discoveries.edit_discovery_id`. NULL = a brand-new submission (unchanged behavior); set = an edit of the live discovery with that id. This is the exact shape of `pending_systems.edit_system_id`. The separate `pending_edit_requests` table was deliberately NOT reused — it's a narrow, super-admin-only, partner-request, system-metadata-only mechanism that can't carry photos/type_metadata/location.

**Backend** ([routes/discoveries.py](Haven-UI/backend/routes/discoveries.py))
- `submit_discovery` accepts + validates `edit_discovery_id`: the target must exist and live on the **same system** (else 404/400). Stored in the new column and the `discovery_data` blob. The missing `except HTTPException: raise` guard was added so these 4xx validations aren't swallowed into a generic 500.
- `approve_discovery` now branches: when `edit_discovery_id` is set it **UPDATEs the live discovery in place** (discovery_type, name, type_slug, planet/moon, location_type/name, description, significance, mystery_tier, photo, evidence, type_metadata, lat/long) while **preserving** the original `discovered_by`, `submission_timestamp`, `system_id`, `discord_tag`, `profile_id`, and `source`. Otherwise it INSERTs exactly as before. Guards against the target having been deleted between submit and approve.
- New super-admin `PUT /api/pending_discoveries/{id}` — inline edit of a queued row's `discovery_data` (mirror of `PUT /api/pending_systems/{id}`), audit `edit_pending_discovery`. (Endpoint shipped; the inline-editor UI in the approval modal is a deferred follow-up — editing via the Edit button already lets super admins revise through the queue.)
- `edit_discovery_id` added to the `GET /api/pending_discoveries` SELECT so the UI can badge/diff.
- Self-approval prevention, discord_tag scoping, and audit logging all apply unchanged. The wizard co-submitted path (`_promote_draft_discoveries`) is untouched (it only INSERTs on system approval).

**Frontend**
- [DiscoverySubmitModal.jsx](Haven-UI/src/components/DiscoverySubmitModal.jsx): new **edit mode** via an `editDiscovery` prop — prefills every field (including `type_metadata`, with a guard so the "clear metadata on type change" effect doesn't wipe the prefill), locks the system selector, keeps the existing primary photo unless a new one is uploaded, submits `edit_discovery_id`, swaps the title/CTA to "Edit Discovery"/"Submit Edit", and shows an amber "changes go to the approval queue" banner.
- [DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx): an **Edit** button (visible to everyone, beside the admin Feature toggle) via a new `onEdit` callback.
- [Discoveries.jsx](Haven-UI/src/pages/Discoveries.jsx) + [DiscoveryType.jsx](Haven-UI/src/pages/DiscoveryType.jsx): a `handleEditDiscovery` that closes the detail modal and reopens the submit modal in edit mode; both clear the edit state on close/success.
- [DiscoveryApprovalTab.jsx](Haven-UI/src/components/approvals/DiscoveryApprovalTab.jsx): a **NEW/EDIT badge** on each pending card, and for edits an **old → new diff** in the review modal (fetches `GET /api/discoveries/{edit_discovery_id}` for the original and compares every field including each `type_metadata` key; warns if the original is gone).

**Verification** (against the local dev DB): migration applied (`edit_discovery_id` present); a submit-edit created a flagged pending row (id 46) with the correct "edit submitted" message; the wrong-system guard correctly returned 400; and a rolled-back SQL simulation of the approve-edit UPDATE confirmed the editable fields change while `discovered_by`/`submission_timestamp`/`system_id`/`discord_tag` are preserved. Frontend compiled clean (Vite HMR, all modules resolve).

**Deploy:** requires a backend restart on the Pi (uvicorn not `--reload`); migration v1.87.0 auto-runs at startup. No live-`discoveries` schema change, no data writes.

---

#### Master Haven 1.74.0 (2026-06-17) - Discovery Metadata Display + In-Game C/B/A/S Color Scale
Star wanted to edit discovery metadata by hand and noticed the per-type fields (fauna species/behavior, etc.) weren't showing on the Discovery tab or the 3D map. Investigation found a pure display bug, and the same pass added the in-game class/grade colors.

**Part 1 — type metadata now displays for every type (no migration)**

The per-type fields are stored as a JSON blob in `discoveries.type_metadata` and were being **saved correctly all along** (verified: 44 of 66 local rows had populated metadata — e.g. `{"species_name":"Child of Helios","behavior":"Passive"}`, `{"tool_class":"B"}`). Nothing was lost, so a backfill migration would have had nothing to fill. The bug was entirely read/render-side:
- The **card** ([DiscoveryCard.jsx](Haven-UI/src/components/discoveries/DiscoveryCard.jsx)) never rendered metadata at all.
- The **detail modal** ([DiscoveryDetailModal.jsx](Haven-UI/src/components/discoveries/DiscoveryDetailModal.jsx)) had a "Details" section but gated it on `typeof type_metadata === 'object'` — and the `browse`/`recent` endpoints returned the blob as a raw JSON **string** (only the detail endpoint parsed it), and the pages pass the list-row straight to the modal, so the section was silently skipped 100% of the time.
- The **3D map** "View Discoveries" pop-up (`buildDiscCard` in [VH-System-View.html](Haven-UI/public/VH-System-View.html)) never rendered metadata either.

Fix: new shared [discoveryMeta.js](Haven-UI/src/utils/discoveryMeta.js) — `parseTypeMetadata` accepts an object *or* a string, `metaEntries` returns ordered `{key,label,value,color}` entries skipping empties, labels sourced from the curated `DISCOVERY_TYPE_FIELDS` (falling back to title-case so no field is ever missed). Card renders a compact metadata line; modal Details grid uses the helper (now string-safe). Backend [discoveries.py](Haven-UI/backend/routes/discoveries.py) `browse`/`recent` now `json.loads` the blob per row (mirrors the detail endpoint) — verified the API returns objects for all rows with metadata. Map `buildDiscCard` renders all fields generically.

**Part 2 — unified in-game C/B/A/S color scale (per Parker)**

New single source [gradeColors.js](Haven-UI/src/utils/gradeColors.js): `TIER_COLORS` = **S Gold `#ffd700`, A Purple `#c084fc`, B Blue `#60a5fa`, C Green `#4ade80`**; `RICHNESS_COLORS` for minerals (Extraordinary Gold, Rare Purple, Common Green). `classColor`/`gradeColor` (same scale) + `richnessColor`.
- **Discovery class chips:** starship/multi-tool `*_class` and mineral `deposit_richness` values now render colored on the card, modal, and 3D map. The "is this a class/richness field" decision is derived from each field's `recordKind` in `DISCOVERY_TYPE_FIELDS` (`rank_class` → class scale, `rank_rich` → richness scale), so it stays in sync with the curated field list.
- **Completeness grade pills recolored to match:** `.grade-*` and `.bar-*` in [index.css](Haven-UI/src/styles/index.css) (A green→purple, C faded-gray→green; S→gold, B→blue), plus the Wizard inline maps ([WizardPreviewPanel](Haven-UI/src/components/wizard/WizardPreviewPanel.jsx)/[WizardSidebar](Haven-UI/src/components/wizard/WizardSidebar.jsx)/[WizardProgressBar](Haven-UI/src/components/wizard/WizardProgressBar.jsx) now import `TIER_COLORS`), the [SystemThumb.jsx](Haven-UI/src/posters/SystemThumb.jsx) poster `GRADE_BG`, and the 3D map grade styles ([VH-System-View.html](Haven-UI/public/VH-System-View.html) `getGradeStyle`, [VH-Cartographer.html](Haven-UI/public/VH-Cartographer.html) `cf-grade` pills). Map HTML keeps its own inline copy of the palette (can't import JS modules); edited in `public/` and copied to `dist/`.

**Scope:** frontend + a read-side backend parse. No schema change, no migration, no data writes. The backend needs a restart for the `browse`/`recent` parse to take effect, though the frontend parses defensively so it works regardless. `/api/status` 1.71.0 → 1.71.1, `package.json` 1.62.1 → 1.63.0.

---

#### Master Haven 1.73.3 (2026-06-17) - Extractor Display-Adjective Fix (Haven Extractor 1.10.3, Fix 1)
Right after the phantom-planet fix, Ekimo re-checked Odusto and found everything correct **except** the per-planet adjectives. Side-by-side (in-game analysis visor vs the submitted card):

| Planet | Weather | Sentinel | Flora | Fauna |
|---|---|---|---|---|
| Reolus XIII | Superheated Drizzle → **Humid** | Malicious → **High** | Bountiful ✅ | Infrequent → **Sparse** |
| Umerisc Tau | Heated Atmosphere → **Scorched** | Observant → **Limited** | Full → **Bountiful** | Abundant → **Copious** |
| Caeanoi Sigma | Absent → **ClearCold** | Frequent → **Limited** | Absent → None | Undetected → None |

Names, biomes, sizes, and resources were all correct — only the adjectives, and the submitted ones are the **generic enum tier**, not the game's exact display strings.

**Root cause (breaks single uploads too — not just batch).** NMS only exposes the exact adjectives ("Superheated Drizzle", "Observant", "Abundant"...) in the live `solar_system.maPlanets[].PlanetInfo`, which the game fills in *after* you enter the system. The `GenerateCreatureRoles` capture hook sees only the transient `lPlanetData` (empty at generation), so it captures just the enum tier (`FLORA_LEVELS` etc.). The fix for that was always `_auto_refresh_for_export()`, which reads the *persistent* live array and stashes the resolved display strings into the captured `flora_display`/`fauna_display`/`sentinel_display`/`weather_display` keys. **But the payload builder `build_planet_entry` read the plain enum keys and ignored the `*_display` keys entirely — so the refresh collected the right values and the builder threw them away.** This is why even a single upload (which *does* refresh at Export, while still in the system) came out wrong. The display-preference logic only ever existed in the now-dead memory-read path `_extract_single_planet`; when the captured-only path became the primary upload path at v1.9.7, `_planet_from_captured` was written with the enum keys and the preference was never carried forward (verified against git `86354aa`).

**Fix 1 (the builder — approved scope).** `build_planet_entry` ([extraction_core.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py)) now resolves each adjective as `captured['*_display'] or captured['*'] or 'Unknown'` — preferring the exact display string the refresh already collected, falling back to the enum tier only when the display string wasn't captured (e.g. you left the system before PlanetInfo populated). A new optional `clean_weather` callable param normalises weather exactly as the legacy `_extract_single_planet` did; the wrapper `_planet_from_captured` passes `clean_weather=clean_weather_string`. No new game-memory access — the data was already being collected, we just start using it. This deterministically fixes **single uploads** (and the last system of any batch).

**What's deliberately NOT in this release (Fix 2, deferred by decision).** Multi-system *batch* uploads: every system except the last is frozen the instant you warp out (`on_system_generate`), before any refresh runs, and its memory is immediately recycled — so its `*_display` was never collected and is unrecoverable after warp. Those non-last systems will still send the enum tier until a "collect-while-live, per system" mechanism is added (the old `APPVIEW`-triggered refresh that did this is dead on Voyagers). We chose to ship the builder fix alone first; the batch collection design is a separate follow-up.

**Verification.** `test_extraction_core.py` gains `test_display_adjective_preference` (display wins over enum for all four fields; enum fallback when no display present; `clean_weather` applied to the chosen value) — **all 56 checks pass**; both mod files byte-compile clean.

**Odusto 9761.** Its adjectives are left as-is — the correct display strings were never captured, so they can't be recovered from the DB. Ekimo will correct the three planets at approval (the screenshots are the reference).

**Batch-leak audit (explicitly requested).** Confirmed intact: the freeze (`build_system_payload`) reads no memory → no cross-system bleed; `_captured_planets.clear()` on every warp → no carryover; the 1.10.2 phantom filter bounds the planet list; and Fix 1 is a pure builder change that touches no capture/freeze timing. This release adds nothing that reads live memory, so it cannot reintroduce the batch data-loss bug.

**Deploy.** `__version__` 1.10.2 → 1.10.3 (+ pyproject). `HavenExtractor-mod-v1.10.3.zip` built in the repo root (supersedes the archived v1.10.2 zip; bundles the phantom fix, this adjective fix, and the first published 1.10.x galaxy fix). **Parker's manual step:** upload v1.10.3 to the GitHub Release for the auto-updater.

---

#### Master Haven 1.73.2 (2026-06-17) - Extractor Phantom-Planet Fix (Haven Extractor 1.10.2)
Ekimo reported the extractor "finally got the right galaxy but now it's making random planets up" — Odusto submitted with 6 planets when the system only has 3.

**Evidence (Pi pending DB, source of truth)**
- Odusto = pending id **9761**, glyph `0FFF615E0CC5`, galaxy **Mushonponte** (galaxy now correct ✅). Stored `system_data.planets` held 6 entries: 3 real (Reolus XIII / Umerisc Tau / Caeanoi Sigma — proper procgen names, varied biomes) + 3 phantoms named `Planet_4/5/6`, all identical default **Lush/Small**.
- A scan of the last 40 extractor submissions found Odusto the **only** one with phantoms. Kaksim XI (same upload session, today) was clean (4/4); all 38 May-25 systems clean. So the bug is **new and timing-dependent**, not a blanket regression.

**Root cause**
The v1.10.0 "captured-only" rewrite builds the planet list purely from `_captured_planets` ([extraction_core.py build_planet_list](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py)) with **no planet-count bound** — unlike the legacy `_extract_planets`, which clamps to the authoritative `PLANETS_COUNT` (0x2264). The `GenerateCreatureRoles` hook fires ~60×/sec while in-system; most fires resolve a real planet name and dedupe by name, but a fire whose name can't be read yet was stored as a distinct `_unnamed_N` entry ([haven_extractor.py:2039](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py#L2039)) carrying default Lush/Small data, then rendered as `Planet_{index+1}` at export ([extraction_core.py:96](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py#L96)). Odusto happened to catch 3 such spurious fires after its 3 real captures (→ indices 3,4,5 → `Planet_4/5/6`); Kaksim XI caught none.

**Fix — Haven Extractor 1.10.2 (two parts)**
- **Part A (the fix; pure + test-covered):** new `select_captures(captured_planets, count_hint=)` + `_capture_has_name()` in [extraction_core.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/extraction_core.py). A real NMS body always has a name, so: if ANY named capture exists, drop ALL nameless `_unnamed_*` phantoms; fall back to the unnamed set only when *nothing* got a name (a fully degraded read — never upload planetless). The live `_planets_count` (planets+moons, 1..6) snapshot is an UPPER cap only — it can trim an over-long list but is NEVER a reason to keep/pad a phantom (the post-Voyagers count read is unreliable). `build_planet_list` filters through `select_captures`; [`_planets_from_captured`](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py#L3241) passes `_current_system_snapshot['_planets_count']` as the hint and logs how many phantoms were dropped.
- **Part B (hardening):** the capture block ([~line 2050](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py#L2050)) now counts only NAMED captures toward the 6-body cap, and a real (named) planet evicts a phantom when the dict is physically full — so a phantom fire arriving *before* the real planets can never displace a real one out of the cap (the latent ordering risk Odusto didn't hit because its reals came first).

**Verification**
- [test_extraction_core.py](NMS-Haven-Extractor/tests/test_extraction_core.py) gains a `test_phantom_filter` (7 checks: Odusto 3-named+3-phantom shape, count_hint-doesn't-pad, over-long-named trim, all-unnamed degraded fallback kept, no-hint still drops phantoms). **All 49 checks PASS.** Both mod files byte-compile clean.
- **Existing Odusto row (9761) patched in place** on the Pi: the 3 `Planet_*` phantoms dropped from `system_data.planets` (now exactly Reolus XIII / Umerisc Tau / Caeanoi Sigma). Original blob backed up to `/home/pi8gb/odusto_9761_system_data.bak.json` before the write.

**Deploy**
- `__version__` 1.10.1 → 1.10.2 (+ [pyproject.toml](NMS-Haven-Extractor/pyproject.toml)). Mod-only zip **`HavenExtractor-mod-v1.10.2.zip` built in the repo root** (17 entries incl. the full `nms_namegen/`).
- **Parker's manual step:** upload `HavenExtractor-mod-v1.10.2.zip` to the GitHub Release so `haven_updater.ps1` ships it. This is also the **first** published zip to carry the 1.10.x galaxy fix — no 1.10.0/1.10.1 zip was ever released, which is why fresh uploads kept arriving as Euclid and needed the v1.86.0 backfill.

---

#### Master Haven 1.73.1 (2026-06-16) - Backfill MidGenX "Always Euclid" Extractor Uploads (Migration v1.86.0)
MidGenXGamer reported repeatedly (via Ekimo's Discord thread) that his extractor uploads show as **Euclid** in the approval queue when he was actually galaxy-hopping (Hyades → Ickjamatew → Budullangr…). This is the long-standing pre-1.10 extractor "always Euclid" bug: a single zeroed scratch read was accepted as a definitive Euclid, so galaxy AND the galaxy-dependent procedural names were all Euclid-seeded.

**Investigation (read-only, against a live Pi snapshot)**
- **272** MidGenX extractor systems sit `status='pending'`, all `galaxy='Euclid'`, in **5 tight upload sessions** (each a ~10–40s batch export). Timezone resolved to **EDT** — session 2 uploaded 5/19 07:34 UTC = 03:34 EDT, ~18 min before his "the 5/19 systems are all Ickjamatew except the last" message; and the galaxy sequence matches the NMS "cross the core → galaxy index +1" mechanic (Hyades 4 → Ickjamatew 5 → Budullangr 6).
- A deterministic namegen check proved **every stored system `name` equals `systemName(glyph, galaxy=0)`** — i.e. the buggy Euclid procgen fallback, not a real in-game name. So names are wrong and safe to regenerate (with a per-row guard).
- Region names were auto-submitted by the extractor and **already approved separately** — **346** MidGenX `pending_region_names` rows are `status='approved'`, all `galaxy='Euclid'`, and live in the `regions` table under Euclid. `regions` has no per-user column and 1,885 Euclid rows belong to many contributors, so the region fix had to be coordinate-driven and collision-aware.

**Confirmed galaxy mapping (MidGenX's own reports)**
| Session (UTC) | Count | Galaxy |
|---|---|---|
| 2026-05-18 | 128 | Hyades (4) |
| 2026-05-19 | 45 | Ickjamatew (5), **last system → Budullangr (6)** |
| 2026-05-24 | 36 | Budullangr (6) |
| 2026-05-23 | 10 | **unconfirmed → held** |
| 2026-05-25 | 53 | **unconfirmed → held** |

**Migration v1.86.0** ([migrations.py](Haven-UI/backend/migrations.py)) — corrects the **3 confirmed sessions (209 systems)** only:
- **Systems:** rewrites galaxy in BOTH the `pending_systems.galaxy` column and the `system_data` JSON `galaxy` key (approval reads the blob, [approvals.py:1571](Haven-UI/backend/routes/approvals.py#L1571)); regenerates the system name to the correct galaxy via the backend-vendored [nms_namegen](Haven-UI/backend/nms_namegen/) **only when the stored name == the Euclid procgen name** for that glyph (so a real/custom name is never clobbered). The single last 5/19 system is pinned to Budullangr.
- **Regions + already-approved region names:** for each affected voxel, moves the live `regions` row + the approved `pending_region_names` record to the correct galaxy with a regenerated name. Custom (non-procgen) names are preserved verbatim. `regions.UNIQUE(custom_name)` is respected — if the regenerated name is already taken by a *different* region (NMS region names repeat across the universe), that one voxel is **left as-is and logged** rather than clobbered. A voxel still referenced by another live Euclid system gets a fresh correct-galaxy row while the Euclid row stays intact.
- **Scope guard:** `source='haven_extractor'`, `galaxy='Euclid'`, submitter `LIKE 'MidGenX%'`, confirmed session days only. Manual rows, other contributors, and the 2 unconfirmed sessions are never touched. **Idempotent** — once a row leaves `galaxy='Euclid'` it no longer matches.

**Dry-run verification** (against a fresh copy of the 2026-06-16 prod snapshot): 209 systems re-galaxied (Hyades 128 / Ickjamatew 44 / Budullangr 37), all 209 names regenerated; regions moved 204, inserted 1 (shared voxel), 1 collision deferred (`'Sea of Izzy'`); 205 region-name records corrected; 63 held systems + manual/other-contributor data unchanged; second run a clean no-op.

**Deploy:** requires a backend **`--build`** deploy — the running Pi image predates `nms_namegen` (the module is git-tracked under `Haven-UI/backend/`, so the rebuilt image bundles it). The migration then auto-runs at startup.

**Open follow-ups (NOT in this release):**
1. **5/23 (10) + 5/25 (53) galaxies** — get them from MidGenX, then a sibling migration with the same logic.
2. **Release the 1.10.1 mod zip** — the galaxy fix exists in source (`HavenExtractor 1.10.1`) but no `HavenExtractor-mod-v1.10.x.zip` was ever built/uploaded, so the auto-updater still serves a pre-1.10 build and **new** uploads keep landing as Euclid. This is the root cause; the migration only cleans the backlog.
3. **`'Sea of Izzy'` region-name collision** — 1 deferred voxel needs a manual call (rename or accept).
4. **Pre-existing approved-Euclid duplicate of `Nahuiju XIII`** — MidGenX has an earlier already-approved (wrongly-Euclid) copy at the same voxel as a pending one; approving the corrected pending copy may create a duplicate since dedup keys on galaxy+reality.

---

#### Master Haven 1.73.0 (2026-05-31) - Discovery Surface Coordinates (Latitude/Longitude)
Parker asked to let discoveries carry the precise surface coordinate (the latitude/longitude NMS shows in the analysis visor) for any discovery type on a planet or moon, with submission + display + approval UI and the backend/migration plumbing to back it.

**Design (confirmed with Parker before building)**
- **Dedicated `latitude`/`longitude REAL` columns**, NOT stuffed into the type-specific `type_metadata` JSON bag — coords are cross-type and warrant numeric range validation and future map/query use.
- **Two fields + paste-parse**: a shared `<LatLngInput>` renders separate Latitude/Longitude decimal inputs AND splits a pasted combined `"+45.23, -12.85"` string across both (players already paste that into the old free-text field).
- **Keep `location_name`**: the free-text "specific location" field stays for descriptive notes; lat/lng is the precise pin alongside it.
- **Space discoveries** carry no coordinates — inputs hide and values are nulled on every path.

**Backend**
- Migration **v1.85.0**: nullable `latitude REAL` + `longitude REAL` added to BOTH `discoveries` and `pending_discoveries`, column-presence guarded, no backfill.
- New `normalize_discovery_coords(lat, lng)` in [constants.py](Haven-UI/backend/constants.py): float-coerce, NaN-reject, range-check (lat [-90,90], lng [-180,180]); each axis independent so one bad value doesn't void the other.
- Wired into **all four** discovery INSERT paths (the data-flow trace that this codebase always needs) so a coordinate can't silently drop: `POST /api/submit_discovery` and `POST /api/discoveries` (both insert into `pending_discoveries`, and write the cleaned values back into the `discovery_data` JSON blob so the approval path can read them), `POST /api/approve_discovery/{id}` (live `discoveries`, prefers the dedicated pending columns and falls back to the JSON blob for rows queued before the columns existed), and `_promote_draft_discoveries` for wizard co-submitted discoveries (both single + batch system approval) — with the matching `_sanitize_discoveries_draft` intake validator carrying the two fields through.
- READ: added the columns to the `GET /api/pending_discoveries` list SELECT (for the approval card) and to the `GET /api/systems/{id}` discoveries SELECT. **Latent bug fixed in passing**: that SystemDetail discoveries subquery selected `d.photos` and `d.featured`, which are not real columns (`photo_url`/`is_featured` are) — the query had been raising and the `try/except` was returning `discoveries: []` on every system page. Aliased to the real columns so system pages now actually show their linked discoveries. Browse/recent/detail already use `SELECT *`.
- `/api/status` bumped 1.69.0 → 1.70.0.

**Frontend**
- New shared [LatLngInput.jsx](Haven-UI/src/components/LatLngInput.jsx) + `coordToFloat` / `coordValid` / `formatCoords` helpers.
- Submission surfaces: DiscoverySubmitModal (standalone discovery submit), Wizard inline DiscoveryInlineList (per-entry), and Wizard `buildDiscoveryDraftEntry` (the draft that rides on `pending_systems.discoveries_draft` and the admin direct path).
- Display surfaces: DiscoveryDetailModal (Location section coordinate row), DiscoveryCard (📍 chip), SystemDetail discovery chips, and DiscoveryApprovalTab review modal (coords + the previously-never-rendered `location_name`).

**Deploy**: requires a backend restart on the Pi (uvicorn not running with `--reload`); migration v1.85.0 runs automatically at startup. Extractor unchanged — it submits systems, not discoveries.

---

#### Master Haven 1.70.0 (2026-05-19) - Civ Leaders Are Full-Power BY ROLE (the real "new partner can't see Approvals" fix)
Parker, after v1.69.0: "the partners and sub admin accounts post overhaul are still not working … a new partner account user says they can't see the approvals and that's not the only thing broken." A full end-to-end trace of the permission flow (civ creation → member assignment → feature computation → session → frontend gating) found that v1.69.0 fixed the *plumbing* but not the *source*.

**What v1.69.0 got right, and what it missed**

v1.69.0 correctly made `_recompute_profile_features` materialize a user's effective civ features into `user_profiles.enabled_features` — the column the login session reads ([auth.py:209](Haven-UI/backend/routes/auth.py#L209)) and that every route guard (`canAccess('approvals')` on the frontend, `require_feature` on the backend) checks. That closed the "tier synced but features never written" gap.

But it computed those features as `union(per_member_override if set else civ.enabled_features_default)` — **with no notion of role**. So a civ leader's permissions came **entirely** from `civilizations.enabled_features_default` (or a per-member override the UI never sent). And the "Found new civilization" modal seeds `enabled_features_default` **empty** — its feature checkbox grid is literally labeled "Default features for sub-admins," so a super admin founding a civ for a new partner has no reason to tick it. Net for every newly-founded civ:

- Founder seated as `leader` with `enabled_features = NULL` → recompute falls through to the empty civ default → `user_profiles.enabled_features = []`.
- `tier = 2` → `user_type = 'partner'` → `isAdmin = true`, navbar shows "Partner", but `canAccess('approvals')` is **false** → the `/pending-approvals` route redirects to `/` and the navbar link is hidden.
- `union([]) == []`, so even v1.69.0's migration v1.83.0 faithfully backfilled these leaders as empty.

Existing civs (Haven, GHUB, IEA…) worked the whole time only because migration v1.80.0 had backfilled their `enabled_features_default` from the legacy `partner_accounts.enabled_features`. **Only civs created through the new flow were born empty** — exactly matching "the new way we make civs" being broken while old partners were fine.

There is no role→features mapping anywhere in the codebase; the schema even states "'leader' and 'co_leader' are functionally identical … full power" ([migrations.py:6115](Haven-UI/backend/migrations.py#L6115)), but nothing granted them that power.

**The fix — leaders get the full set by role**

1. **`LEADER_FEATURES` frozenset** in [constants.py](Haven-UI/backend/constants.py): the 8 partner-grade features (`system_create, system_edit, approvals, batch_approvals, stats, settings, csv_import, war_room`). Super-admin-only flags (`api_keys, backup_restore, partner_management`) are intentionally excluded — those gate on `user_type == 'super_admin'` / `RequireSuperAdmin`, not on the features list.

2. **`_recompute_profile_features` is now role-aware** ([routes/civilizations.py](Haven-UI/backend/routes/civilizations.py)): the SELECT adds `cm.role`; a `leader`/`co_leader` membership contributes the full `LEADER_FEATURES` set to the union regardless of civ default or override, while `sub_admin` keeps the existing per-member-override-else-civ-default behavior (so sub-admins stay delegable/restrictable). This flows through all 5 existing callsites automatically — founder creation, add_member, update_member (role/features change), remove_member, and the update_civilization fan-out.

3. **Migration v1.84.0** ([migrations.py](Haven-UI/backend/migrations.py)) re-runs the role-aware union for every profile with an active civ membership, repairing existing and freshly-broken leaders on deploy without waiting for a civ event. The leader feature set is inlined (a migration is a frozen historical record) and mirrors `LEADER_FEATURES` as of 1.84.0.

4. **Session freshness** — `GET /api/admin/status` ([routes/auth.py](Haven-UI/backend/routes/auth.py)) now re-reads `tier` + `enabled_features` from `user_profiles` on every call, writes them back into the live session, and re-derives `user_type` via `TIER_TO_USER_TYPE`. Previously features were frozen into the session at login, so a super admin fixing a user's permissions left that user stuck until they logged out and back in. Now the change takes effect on the user's next page load (AuthContext polls `/api/admin/status` on mount). One indexed PK lookup per status check.

**Frontend** ([CivilizationManagement.jsx](Haven-UI/src/pages/CivilizationManagement.jsx))

- `MemberRow` gains a collapsible **per-member permissions editor**. Sub-admins get the feature grid seeded from their override (or the inherited civ default) with **Save permissions** (PUT `enabled_features` array → explicit override) and **Reset to civ default** (PUT `enabled_features: null`). Leaders/co-leaders show "full access by role — demote to Sub-Admin to scope." This finally exposes the per-member override the backend has supported since v1.69.0 but the UI never sent.
- Both `enabled_features_default` grids (create + edit) relabeled "Default features for sub-admins (leaders & co-leaders always get full access)."
- The create modal seeds `DEFAULT_SUB_ADMIN_FEATURES` (`approvals, system_create, system_edit, stats`) instead of `[]`, so a civ founded without touching the grid still has working sub-admins.

**Deploy**: requires a backend restart on the Pi (uvicorn not running with `--reload`); migration v1.84.0 runs automatically at startup. After restart, affected partners get correct access on their next page load — no manual re-login needed.

**What's intentionally NOT changed**: sub_admin feature semantics (still override-else-civ-default — that's the point of a delegable role); the `'all'` sentinel stays reserved for super admin; `add_member` still accepts `{profile_id, role}` only (leaders no longer need features in the payload, and sub-admin features are now editable post-add via the new MemberRow editor).

---

#### Master Haven 1.69.0 (2026-05-18) - Civ-Derived Permissions Auto-Sync + Legacy Tier Endpoint Lockdown (Option A)
Parker reported: "when I take a member and elevate them to partner civ or add them while I create the civ they don't get the correct permissions assigned to them." Investigation found two distinct gaps — a real data-flow bug and a half-finished migration — both papering over each other in confusing ways.

**The two gaps**

1. **`_recompute_profile_tier` only synced `tier`, never `enabled_features`.** Migration v1.80.0 made `civilization_members` the source of truth for civ membership and added a helper that re-derives `user_profiles.tier` from the membership set after any add/update/remove. But the session at login reads `user_profiles.enabled_features` ([routes/auth.py:238](Haven-UI/backend/routes/auth.py#L238)) — and nothing populated that column from civ data. So a member added via CivilizationManagement → Add Member as `role='leader'` got `tier=2` (visible as "Partner" in the UI) and `enabled_features=[]` (no actual permissions). They could log in, the navbar said "Partner", and every feature-gated route refused them. The session builder is correct; the auto-sync was just missing on the features axis.

2. **Two parallel write paths for tier still existed.** The v1.55.0 work updated `CivilizationManagement.jsx` to be the new source of truth (Add Member → role → `_recompute_profile_tier` does the rest) and updated `UserManagement.jsx`'s elevate modal to only offer tier 1/4/5 — but the backend `PUT /api/admin/profiles/{id}/tier` still accepted tier 2/3 and still set `partner_discord_tag` + `enabled_features` directly on `user_profiles`, bypassing `civilization_members` entirely. The Demote button at [UserManagement.jsx:310](Haven-UI/src/pages/UserManagement.jsx#L310) still called the legacy path with `{tier: 4}` to demote a partner, which would write `tier=4` to the user profile row, leave their `civilization_members` rows alone, then get silently reverted on the next civ event because `_recompute_profile_tier` re-derived `tier=2` from the still-present leader membership. Two months of "I demoted them, they're still a leader" surprise.

**Fix Layer 1 — auto-sync features from civ memberships**

New helper `_recompute_profile_features(cur, profile_id)` in [routes/civilizations.py](Haven-UI/backend/routes/civilizations.py):

```python
def _recompute_profile_features(cur, profile_id: int) -> None:
    cur.execute("""
        SELECT cm.enabled_features, c.enabled_features_default
        FROM civilization_members cm
        JOIN civilizations c ON c.id = cm.civ_id
        WHERE cm.profile_id = ? AND c.is_active = 1
    """, (profile_id,))
    union: set = set()
    for row in cur.fetchall():
        per_member_raw, default_raw = row[0], row[1]
        try:
            per_member = json.loads(per_member_raw) if per_member_raw else None
        except (TypeError, json.JSONDecodeError):
            per_member = None
        try:
            default = json.loads(default_raw) if default_raw else []
        except (TypeError, json.JSONDecodeError):
            default = []
        effective = per_member if per_member is not None else default
        if isinstance(effective, list):
            union.update(effective)
    cur.execute(
        "UPDATE user_profiles SET enabled_features = ? WHERE id = ? AND tier != 1",
        (json.dumps(sorted(union)), profile_id),
    )
```

Semantics: union of effective features across all active civ memberships. Per-member override (`civilization_members.enabled_features`) wins over civ default (`civilizations.enabled_features_default`). Inactive civs skipped — a deactivated civ stops granting its features. Super admin (tier 1) untouched — their permission comes from `user_type` check, not the features list. Zero memberships → features cleared to `[]` (correctly strips access from someone removed from their last civ).

Wired into 5 callsites — every place where membership state changes or could change effective features:
- `create_civilization` → after founder INSERT (closes the bug where the founder themselves had empty features)
- `add_member` → after `_recompute_profile_tier`
- `update_member` → when `role` OR `enabled_features` is in the payload (the existing tier recompute only fired on role change)
- `remove_member` → after `_recompute_profile_tier`, so removing a leader correctly strips their features
- `update_civilization` → when `enabled_features_default` OR `is_active` changes, fans out to every member of the affected civ (otherwise civ-default brand changes are stuck behind the next per-member event)

**Fix Layer 2 — lock down the legacy tier endpoint**

[`PUT /api/admin/profiles/{id}/tier`](Haven-UI/backend/routes/profiles.py) rewritten with three guards:

```python
if new_tier not in (TIER_SUPER_ADMIN, TIER_MEMBER, TIER_MEMBER_READONLY):
    raise HTTPException(
        status_code=400,
        detail=(
            "This endpoint only handles tier 1 (Super Admin), 4 (Member), "
            "and 5 (Read-Only). Partner and Sub-Admin tiers are derived from "
            "civilization membership — manage them via the Civilizations page "
            "(POST /api/civilizations/{civ_id}/members)."
        ),
    )
```

Tier 2/3 hits a 400 with a clear pointer. Tier 4/5 with any active civ membership hits a 409 telling the caller to remove the user from each civ first via the Civilizations page — there's no point in accepting a write that `_recompute_profile_tier` would revert on the next civ event. Tier 1 (super admin promote/demote) keeps the existing password gate from v1.68.1. The legacy `partner_discord_tag` + `enabled_features` write branches for tier 2/3 are gone entirely.

**Fix Layer 3 — migration v1.83.0 backfills existing leaders**

Without a backfill, all existing leaders/sub-admins keep their stale empty `enabled_features` until something triggers a per-user recompute (which might be never). Migration v1.83.0 iterates every profile with at least one active civ membership, runs the same union logic the runtime helper uses, and writes back. Idempotent — re-running produces the same result. Mirrors `_recompute_profile_features` exactly to avoid drift between the migration-time and runtime code paths.

**Cleanup — `theme_settings` and `region_color` dropped from login SELECT**

Audit found these `user_profiles` columns selected in [auth.py:158](Haven-UI/backend/routes/auth.py#L158) but never assigned to `session_dict` (lines 231-248). Verified zero downstream readers consume them from the session. Superseded years ago by `civilizations.theme_settings` and `civilizations.region_color` (loaded via `load_memberships_for_profile` and surfaced per-membership). The columns themselves are kept on `user_profiles` since other readers like `/api/admin/profiles/{id}` still expose them for legacy detail views — only the dead SELECT in the hot login path was removed.

**Frontend changes**

[`UserManagement.jsx`](Haven-UI/src/pages/UserManagement.jsx):
- Demote button removed entirely. Replaced with a code comment explaining the new model and pointing future-self at the Civilizations page.
- Elevate modal's tier-4/5 warning rewritten from advisory ("may be overridden") to declarative ("will be rejected with 409") to match the new backend behavior. Generic error handler (`alert(err.response?.data?.detail)`) surfaces the backend's detail messages verbatim, so users see "remove them from N civilization(s) first" without any extra wiring.
- Edit modal's `enabled_features` checkbox grid intentionally left in place — it still writes to `user_profiles.enabled_features` via `PUT /api/admin/profiles/{id}` (separate endpoint), which is not yet auto-synced from civ memberships. For users with civ memberships those writes will get overwritten on the next civ event; for legacy Haven sub-admins (tier 3 with `parent_profile_id IS NULL` and no civ_members rows) the writes still work normally. This is a known follow-up — eventually the feature editor should move to the Civilizations page → Edit Member.

**What's NOT changed (intentional)**

- `user_profiles.partner_discord_tag`, `parent_profile_id`, `additional_discord_tags`, `can_approve_personal_uploads` still actively read in the session builder for back-compat with the Haven sub-admin multi-tag pattern. Audit confirmed all four are still load-bearing.
- `civilizations.id` for tier 1 (super admin) — `_recompute_profile_features` and `_recompute_profile_tier` both skip tier 1 explicitly. Super admin permissions come from `user_type` check, not enabled_features.
- The civ-membership UNION semantics for features (vs. "active civ only" semantics) — chose union so a leader of civ X with `war_room` feature can still open the War Room page when "acting as" sub-admin of civ Y. The page itself then filters to civ X data via `civ_scope_filter`. Per-civ feature semantics would force constant civ-switching.

**Pi deploy**: requires backend restart (uvicorn not running with `--reload`). Migration v1.83.0 runs automatically at startup. Pre-deploy local validation: started backend, observed `Migration 1.83.0: backfilled enabled_features for N profiles with active civ memberships` log line.

---

#### Master Haven 1.68.1 (2026-05-18) - Super Admin Tier Elevation Fix
Parker tried to promote Watcher (lead diplo) to super admin via UserManagement → Change Tier and the website rejected it with `Invalid tier. Must be 2-5.` This is the second time this corner of the code has been broken — Parker's framing was "you didn't change the variables properly last time we edited this." Investigation traced it to a single missing element in the backend validation tuple.

**Root cause**

[Haven-UI/backend/routes/profiles.py:868-870](Haven-UI/backend/routes/profiles.py#L868-L870) (the `PUT /api/admin/profiles/{id}/tier` endpoint):

```python
new_tier = body.get('tier')
if new_tier not in (TIER_PARTNER, TIER_SUB_ADMIN, TIER_MEMBER, TIER_MEMBER_READONLY):
    raise HTTPException(status_code=400, detail="Invalid tier. Must be 2-5.")
```

`TIER_SUPER_ADMIN` (=1) was conspicuously absent from the set check, so any PUT with `{tier: 1}` failed the gate and produced the error verbatim. Meanwhile the frontend elevate modal at [Haven-UI/src/pages/UserManagement.jsx:497-505](Haven-UI/src/pages/UserManagement.jsx#L497-L505) explicitly exposes Super Admin as an option (`<option value={1}>Super Admin</option>`), per the v1.55.0 design that moved partner/sub-admin tiers to the Civilizations page and made super admin promotion the primary use case for this modal. The frontend was updated; the backend allow-list never was.

**Why the fix really is one line**

Every adjacent guard in the endpoint already handles tier 1 correctly — I checked each one before deciding the fix was just the validation tuple:

- **Auth gate** ([profiles.py:864](Haven-UI/backend/routes/profiles.py#L864)) — already requires `session.user_type == 'super_admin'`. Only super admins can call this endpoint, which is the right gate for super admin promotion.
- **Password gate** ([profiles.py:883](Haven-UI/backend/routes/profiles.py#L883)) — `if new_tier <= TIER_SUB_ADMIN and not row['password_hash']` covers tier 1 (1 ≤ 3) and refuses to elevate users without a password. The UserManagement Change Tier button only renders when `p.has_password`, so the gate is also enforced upstream in the UI.
- **The else-branch** ([profiles.py:917-923](Haven-UI/backend/routes/profiles.py#L917-L923)) clears `partner_discord_tag`, `parent_profile_id`, `enabled_features`, `additional_discord_tags`, and `can_approve_personal_uploads`. That's exactly the right behavior for super admin promotion too — super admin has unrestricted access by definition and doesn't need civ-scoped denormalized convenience fields.
- **Civ auto-sync** ([routes/civilizations.py:431](Haven-UI/backend/routes/civilizations.py#L431)) — `_recompute_profile_tier` does `UPDATE user_profiles SET tier = ? WHERE id = ? AND tier != 1`. The explicit `tier != 1` clause means civilization membership changes will never demote a super admin back down. Safe to promote even if Watcher is currently a civ leader.
- **Audit log** ([profiles.py:933](Haven-UI/backend/routes/profiles.py#L933)) — the `tier_names` dict already has `1: 'Super Admin'`, so the audit row will render the right name.

**The fix**

```diff
-    if new_tier not in (TIER_PARTNER, TIER_SUB_ADMIN, TIER_MEMBER, TIER_MEMBER_READONLY):
-        raise HTTPException(status_code=400, detail="Invalid tier. Must be 2-5.")
+    if new_tier not in (TIER_SUPER_ADMIN, TIER_PARTNER, TIER_SUB_ADMIN, TIER_MEMBER, TIER_MEMBER_READONLY):
+        raise HTTPException(status_code=400, detail="Invalid tier. Must be 1-5.")
```

`TIER_SUPER_ADMIN` was already in the constants import on line 11 of profiles.py — no additional import needed. `/api/status` bumped 1.66.0 → 1.66.1 in [routes/auth.py](Haven-UI/backend/routes/auth.py).

**What I'm NOT changing (flagged as separate concerns)**

- Frontend dropdown is already correct — no UI change.
- Tier 2 (`TIER_PARTNER`) and tier 3 (`TIER_SUB_ADMIN`) stay in the allowed set because the demote button at [UserManagement.jsx:310](Haven-UI/src/pages/UserManagement.jsx#L310) sends `tier: 4` for partner/sub-admin demotion, which still uses this endpoint. The v1.55.0 design comment in the modal says civ-membership tiers should be set via the Civilizations page, but the demote-to-member path still legitimately needs to write tier 4 here.
- Latent denormalization concern: promoting a civ leader to super admin clears their `partner_discord_tag` convenience field but leaves their `civilization_members` row intact. If they're later demoted, `_recompute_profile_tier` will reset their tier from the membership table but won't repopulate the convenience field. Existing design choice, unrelated to this bug, worth a separate ticket if it becomes a real problem.

**Deploy**

Requires a backend restart on the Pi — uvicorn is not running with `--reload` per the standing convention in CLAUDE.md. Watcher's tier change should work on the next backend restart.

---

#### Master Haven 1.61.0 (2026-05-13) - Civ Dropdown Source Consolidation
Parker created a new civilization ("Haven Royal Cartography Corps", tag `HRCC`) via the new `CivilizationManagement` page and noticed it didn't appear in the Wizard's community dropdown on `/create`. Traced to a stale-legacy-paths problem in three backend endpoints that were written before the `civilizations` table existed (migration v1.80.0) and never updated when it was added.

**The disconnect**

`CivilizationManagement` ([Haven-UI/src/pages/CivilizationManagement.jsx:177-204](Haven-UI/src/pages/CivilizationManagement.jsx#L177-L204)) POSTs to `/api/civilizations` which inserts into the `civilizations` table — `tag`, `display_name`, `is_active`. But every civ/community dropdown in the app pulls from one of three endpoints, none of which knew `civilizations` existed:

- `/api/discord_tags` at [control_room_api.py:1950](Haven-UI/backend/control_room_api.py#L1950) — used by Wizard, PendingApprovals, Analytics, Events, ApprovalAudit, ApiKeys, PartnerAnalytics, RegionDetail, DiscoverySubmitModal (9 frontend consumers). Was UNION-ing `partner_accounts.discord_tag` and `user_profiles.partner_discord_tag` (tier 2/3).
- `/api/communities` at [routes/extractor.py:377](Haven-UI/backend/routes/extractor.py#L377) — used by the Haven Extractor mod's dynamic-communities feature (haven_extractor.py:302, v1.6.0+) and `Profile.jsx`. Same UNION shape.
- `/api/available_discord_tags` at [routes/partners.py:664](Haven-UI/backend/routes/partners.py#L664) — used by SubAdminManagement. Read only from `partner_accounts.discord_tag`, didn't even cover `user_profiles`.

Net effect: any civ created via the new page was invisible everywhere — Wizard dropdown, in-game extractor mod, sub-admin assignment screen — unless you also manually created a legacy `partner_accounts` or tier-2 `user_profiles` row with a matching tag. HRCC was created at `2026-05-13T03:07:39+00:00`, sat in `civilizations` correctly, and didn't appear anywhere.

**The wrong fix I initially proposed**

I first proposed UNION-ing `civilizations` into each endpoint alongside the legacy arms. Parker pushed back — "why are we making union and not using one streamline variable name." He was right. The UNION is the kind of backwards-compat shim CLAUDE.md says to avoid. The real problem is that the dropdowns were never updated when migration v1.80.0 moved civ identity to its own canonical table.

**The real fix**

Three endpoints, one SQL query each:

```sql
SELECT tag, display_name FROM civilizations WHERE is_active = 1 ORDER BY display_name
```

Verified safe by querying production directly from a browser DevTools console hitting `/api/civilizations`: 41 active rows, every legacy civ present (Haven, GHUB, IEA, Everion Empire, Atlas-CSD/ETARC, Galactic Hub Project, Shadow Worlds, Tugarv Compendium, etc.) plus the newly-created HRCC. Backfill from v1.80.0 ([migrations.py:6174-6202](Haven-UI/backend/migrations.py#L6174-L6202)) had already seeded it from every tier-2 `user_profiles` row, which in turn had been backfilled from `partner_accounts` in v1.57.0. The legacy UNION arms were just stale code paths reading from the same data, one indirection level removed.

**Response shapes preserved**

Each endpoint keeps its existing response keys so zero frontend callers break:
- `/api/discord_tags` returns `{tags: [{tag, name}]}` — same as before, just with a smaller hardcoded prefix list ("Personal" only; "Haven" is now a real `civilizations` row and falls out of the SQL naturally).
- `/api/communities` returns `{communities: [{tag, name}]}` — unchanged.
- `/api/available_discord_tags` returns `{discord_tags: [{discord_tag, display_name}]}` — column aliased on the way out (`tag AS discord_tag`) so SubAdminManagement keeps working without touching the React side.

**What this fixes downstream automatically**

- Wizard dropdown shows new civs immediately on next page load.
- Haven Extractor mod picks up new civs on next mod load — the v1.6.0 dynamic-communities cache fetches `/api/communities`, caches at `~/Documents/Haven-Extractor/communities_cache.json`, and falls back to a hardcoded default list only if the fetch fails. No mod-zip rebuild required.
- SubAdminManagement civ assignment dropdown sees new civs.
- All 9 frontend pages that hit `/api/discord_tags` get the new civ without code changes.

**Related issue surfaced but NOT fixed in this release**

`/api/discord_tag_colors` (used by ThemeProvider and the poster system) still reads from `super_admin_settings.discord_tag_colors` JSON blob, not from `civilizations.region_color`. So a new civ's color won't show in poster tinting / region color overlays until either (a) the JSON blob is also updated, or (b) that endpoint is migrated to read from `civilizations.region_color`. Same one-source-of-truth pattern; deferred to keep this release focused on the dropdown bug. Flagged in [user/feedback memory](C:\Users\parke\.claude\projects\c--Master-Haven\memory\MEMORY.md) as a known follow-up.

---

#### Master Haven 1.60.0 (2026-05-12) - RealityMode.Normal Phantom-Reality Bug (Three-Layer Fix)
Parker spotted a third reality card "RealityMode.Normal" with 50 systems showing on production's Systems Browser, alongside the real Normal (12,698) and Permadeath (21) cards. Diagnosis traced it to pymhf's DearPyGUI sometimes round-tripping `ENUM` gui_variables back as their Python `repr` string ("RealityMode.Normal") instead of as the enum instance — the extractor's setter fallback `str(value)` persisted that bad string verbatim into `config.json`, every submission's `reality` field, and ultimately the `systems.reality` column. v1.79.0 had already cleaned the rows that existed at that time, but the source bug in the extractor was never patched, so new submissions from any still-bad install kept poisoning the column. Three-layer fix this release so it can't come back.

**Layer 1 — Extractor source (Haven Extractor 1.9.8)**
- New module-level helpers `_normalize_reality(value)` and `_normalize_community_tag(value)` in [haven_extractor.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py): strip any "EnumName." class prefix, validate against the known enum values, default to safe values otherwise. Handle `None`, the actual enum instance, and the string forms ("Normal", "RealityMode.Normal").
- `reality_mode` setter now calls `_normalize_reality(value)` instead of the brittle `value.value if isinstance(value, RealityMode) else str(value)` one-liner.
- `community_tag` setter has identical treatment via `_normalize_community_tag(value)` — same latent bug existed (any community tag containing a "." would have triggered the same shape, though only the reality variant has been observed in the wild).
- Module-init config load at [haven_extractor.py:268](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py#L268) now inline-scrubs `USER_REALITY` and `USER_DISCORD_TAG` immediately after `_config.get(...)` — needed because the normalizer helpers are defined later in the file (after the enum classes) so can't be called at module init. Inline scrub is the same prefix-strip-and-validate logic. Effect: any pre-1.9.8 config with the bad value self-heals on next mod load (the first save_config will write back the cleaned value).
- Version bumped 1.9.7 → 1.9.8 in both [haven_extractor.py](NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py) `__version__` and [pyproject.toml](NMS-Haven-Extractor/pyproject.toml). Mod-only zip needs rebuilding + uploading to GitHub Release per the workflow in this CLAUDE.md.

**Layer 2 — Backend intake guard (Backend API 1.59.0)**
- New `normalize_reality()` in [Haven-UI/backend/constants.py](Haven-UI/backend/constants.py) sitting next to `validate_reality()`. Same shape as the extractor's helper (strip class prefix, validate, default). Importable from any route module.
- Applied at every backend intake site that reads `reality` from a submission payload. Six total: `/api/submit_system` ([approvals.py:198](Haven-UI/backend/routes/approvals.py#L198)), `/api/check_glyph_codes` ([approvals.py:352](Haven-UI/backend/routes/approvals.py#L352)), region-name approval handler ([approvals.py:2894](Haven-UI/backend/routes/approvals.py#L2894)), `/api/extraction` ([approvals.py:3045](Haven-UI/backend/routes/approvals.py#L3045)), `PUT /api/regions/{rx}/{ry}/{rz}` ([regions.py:1032](Haven-UI/backend/routes/regions.py#L1032)), `POST /api/regions/{rx}/{ry}/{rz}/submit` ([regions.py:1128](Haven-UI/backend/routes/regions.py#L1128)).
- Result: even users running a stale Haven Extractor that's still sending the bad string cannot land a bad row in the DB. Closes the door from the server side regardless of client state.
- `/api/status` version bumped 1.58.0 → 1.59.0 in [routes/auth.py](Haven-UI/backend/routes/auth.py).

**Layer 3 — Cleanup migration v1.81.0**
- v1.79.0 ran the `UPDATE ... SET reality = 'Normal' WHERE reality = 'RealityMode.Normal'` UPDATEs once across `systems`, `pending_systems`, `regions`. Migrations run exactly once per database. 50 new bad rows landed between v1.79.0 running and the intake guard shipping.
- v1.81.0 in [migrations.py](Haven-UI/backend/migrations.py) re-runs the same three idempotent UPDATEs. Harmless on rows that don't have the bad value. Will scrub the prod Pi's 50 bad rows on next deploy.
- No `_metadata` table version bump beyond what `register_migration` handles. Verified locally: backend started clean, migration 1.81.0 logged to `schema_migrations`, zero bad rows remain in the local DB.

**Why three layers and not just one**
Layer 1 alone would leave the prod DB dirty until every extractor user updates. Layer 2 alone (intake guard) protects new submissions but doesn't clean the existing 50 rows. Layer 3 alone (cleanup) would re-pollute as soon as the next bad submission landed. The combo: source fix prevents new bad data at the producer, intake guard catches any data from stale producers, migration scrubs the existing rows. Same defense-in-depth pattern used for the `Galaxy_N` and `Unknown(N)` star-type cleanups in prior releases.

**What's still not done**
- Extractor mod-only zip not yet rebuilt for GitHub Release upload (per the standard workflow in this CLAUDE.md — manual step, ~50-60 KB zip from `dist/HavenExtractor/mod/`). Until that ships and users auto-update via `haven_updater.ps1`, the Layer 2 intake guard is what's catching submissions from old installs.
- The Pi DB still has its 50 bad rows until the next backend deploy triggers migration 1.81.0. No frontend banner / admin-visible warning was added — the rows just silently fix themselves on deploy.

---

#### Haven-UI 1.52.1 (2026-05-12) - Wizard Advanced-Flow Mobile Reflow
Fixes two mobile-only issues on `/create` (Wizard) Advanced flow reported by Parker: (1) the live preview card was smooshed and unreadable on phone screens, and (2) the basic/advanced toolbar + section pill nav + live preview combined to eat >50% of the viewport when scrolling.

**Root cause**: [WizardAdvancedPreview.jsx](Haven-UI/src/components/wizard/WizardAdvancedPreview.jsx) was built explicitly landscape — hero row used a hard inline `gridTemplateColumns: '220px 1fr'` (220px orbital diagram + 1fr right column), the stat-tile row was `grid-cols-5`, and the outer `<aside>` was `position: sticky; top: 16`. On ~360-400px phone widths the orbital diagram alone took >half the width, leaving the 5-tile stat grid jammed into ~140px (each tile under 30px wide). The sticky toolbar+pill container above ([Wizard.jsx:996-1058](Haven-UI/src/pages/Wizard.jsx#L996-L1058)) at `top-0 z-20` plus the preview's `top: 16` z-10 sticky meant both rendered as permanent chrome simultaneously.

**Haven-UI 1.52.1**
- **WizardAdvancedPreview outer aside**: replaced inline `style={{ position: 'sticky', top: 16, zIndex: 10 }}` with classes `lg:sticky lg:top-4 lg:z-10` — sticky behavior preserved on desktop, dropped on <lg so the card scrolls away with the form on mobile.
- **Hero row**: replaced hard 220px/1fr two-column with `flex flex-col lg:grid lg:[grid-template-columns:220px_1fr]` — mobile stacks the orbital diagram above the right column instead of squeezing them side-by-side.
- **Orbital diagram size**: 220px on desktop, 140px on mobile (two separate mounts gated by `lg:hidden` / `hidden lg:block`).
- **Stat-tile grid**: `grid-cols-5` → `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5`.
- **Detail-strip icons** (planet biome thumbnails, glyph squares): `w-6 h-6` → `w-5 h-5 lg:w-6 lg:h-6`; inner glyph image `22×22` → `18×18` on mobile.
- **Side padding**: eyebrow/hero/detail-strip/footer `px-5` → `px-3 sm:px-5`.
- **Glyph-code mono text** to the right of the 12 glyph squares: `hidden sm:inline` (saves a line on narrow screens; the squares themselves carry the info).
- **Wizard.jsx advanced preview mount** ([Wizard.jsx:1085-1087](Haven-UI/src/pages/Wizard.jsx#L1085-L1087)): rendered twice — `hidden lg:block` wraps the desktop instance (unchanged from before), `lg:hidden` wraps the same component inside a collapsed-by-default `<details>` with a compact summary chip (`📊 Live preview · GRADE · %`). Mobile users see the grade pill in the summary row without the full card on screen; tap-to-expand renders the now-reflowed card inline below.

**What's intentionally NOT changed**:
- Desktop layout — every change is gated behind Tailwind `lg:` modifiers so the desktop render path is byte-identical.
- The sticky toolbar+pill nav container — that's the more useful sticky element since the pill row is navigational. The preview was informational.
- Basic flow — only Advanced renders `WizardAdvancedPreview`; Basic was never affected.

---

#### Master Haven 1.54.0 (2026-04-29) - Pi Freeze Mitigation, Stages 2 + 3 (Bounded Hot Paths + Operational Hardening)
Follow-up to v1.53.0's Stage 1 work. Stage 1 ended the write-lock pile-up; Stages 2 and 3 keep individual requests from blowing the memory budget on their own and give us visibility plus operational tools so the next problem (whatever it is) doesn't take the box down.

**Stage 2 — bounded hot paths**

- **Audit-log `limit` clamped** ([routes/partners.py:706-738](Haven-UI/backend/routes/partners.py#L706-L738)). The `/api/approval_audit` endpoint accepted any caller-supplied `limit` and used it directly in the `LIMIT ?` clause. A buggy or malicious request with `?limit=999999` would have pulled the entire growing audit table into Python memory. Now clamped: `limit > 500 → 500`, `limit < 1 → 100`, `offset < 0 → 0`. The frontend paginates at 50/100 so this is invisible to legitimate use.
- **Short-query guard on discoveries search** ([routes/discoveries.py:44-56](Haven-UI/backend/routes/discoveries.py#L44-L56)). `?q=a` would expand to `LIKE '%a%'` against `discovery_name`, `description`, AND `location_name` — three full-text scans that match almost every row. The endpoint now strips and length-checks `q`; anything under 2 chars is treated as no query at all. The `limit` param on the user-id branch is also clamped (≤500).
- **`CachedStaticFiles` for user-uploaded images** ([control_room_api.py:21-44, 638-647](Haven-UI/backend/control_room_api.py#L21-L44)). New StaticFiles subclass that adds `Cache-Control: public, max-age=2592000, immutable` to every 200 response. Mounted on `/haven-ui-photos/*` and `/war-media/*`. Filenames are immutable on upload (the WebP pipeline writes a new filename per upload and never overwrites), so a 30-day cache is safe. Browser stops re-fetching every thumbnail on every page load — big win on a page with 20-30 images.

**Stage 3 — operational hardening + visibility**

- **`GET /api/admin/health`** ([control_room_api.py:3404-3502](Haven-UI/backend/control_room_api.py#L3404-L3502)). Authenticated admin endpoint (any tier) returning live operational metrics: DB / WAL / SHM file sizes, SQLite freelist size (how much VACUUM would reclaim), schema version + applied-migration count, hot-table row counts (systems, planets, moons, discoveries, pending_systems, pending_discoveries, activity_logs, approval_audit_log, regions, user_profiles), and process memory (uses psutil if available, falls back to parsing `/proc/meminfo` so the Pi works without a new dependency). Designed to surface the warning signs a freeze produces *before* the freeze happens — runaway WAL, table-row growth without retention, low free RAM.
- **`POST /api/admin/maintenance/wal_checkpoint`** (super admin) — forces `PRAGMA wal_checkpoint(TRUNCATE)`. Returns the (busy, log_pages, checkpointed_pages) tuple from PRAGMA so the caller can see whether a long-held reader prevented checkpointing.
- **`POST /api/admin/maintenance/vacuum`** (super admin) — runs `PRAGMA wal_checkpoint(TRUNCATE)` followed by full `VACUUM`. Uses a fresh autocommit connection (VACUUM cannot run inside a transaction) with a 60-second timeout. Returns size-before / size-after / reclaimed-bytes / elapsed-seconds.
- **Periodic WAL checkpoint background task** ([control_room_api.py:1556-1583](Haven-UI/backend/control_room_api.py#L1556-L1583)). On startup, schedules `_periodic_wal_checkpoint(interval_seconds=1800)` as an asyncio task. Every 30 minutes it opens a short-lived connection, runs `PRAGMA wal_checkpoint(TRUNCATE)`, logs the result, and closes. Errors are logged but don't kill the loop. Bounds WAL growth even when the SQLite auto-checkpoint threshold isn't reached or a long-held reader prevents it — the runaway-WAL scenario seen during the 2026-04-28 freeze.
- **Pi-side hardening script** at [scripts/pi_setup_stage3.sh](scripts/pi_setup_stage3.sh). Idempotent. Run once on the Pi as a sudo-capable user; it installs zram-tools, configures a 50%-RAM zram-backed swap with lz4 compression (compressed RAM swap, no SD-card writes), drops a maintenance wrapper at `~/haven-maintenance.sh` that hits `/api/admin/maintenance/vacuum`, and installs a Sunday 04:00 cron entry. zram is the actual answer to "why did it fully freeze instead of throwing OOM errors" — with no swap, the kernel OOM killer can deadlock if its target is blocked on I/O; with zram, the box degrades gracefully into compressed-RAM paging instead.

**Why these specific limits / cadences**

- 30-minute WAL checkpoint: aggressive enough to prevent multi-hundred-MB WAL accumulation under sustained writes, gentle enough that the per-checkpoint blip is unnoticeable. Tuned for the Pi 5's I/O budget.
- 30-day photo cache (`max-age=2592000`): aligns with Cloudflare's max edge-cache TTL on the free tier and lets us purge with a manual edge-cache invalidation if we ever need to.
- Sunday 04:00 weekly VACUUM: low-traffic window in US/EU timezones; weekly is enough to keep the freelist bounded without the daily lock-window cost.
- 50% RAM zram, lz4 compression: standard recommendation for Pi-class boxes — leaves enough physical RAM for the Python process + Docker overhead, lz4 is fastest of the supported algorithms with negligible Pi 5 CPU cost.

**What's still not fixed (by design — out of scope for the freeze work)**

- Leading-wildcard `LIKE '%term%'` on audit-log multi-field search still defeats indexes. With Stage 2's hard `limit ≤ 500` and the existing exact-match indexes from Stage 1, the worst case is bounded — but FTS5 would be faster. Deferred until there's a concrete complaint.
- No automated alerting on `/api/admin/health` — this provides the data, not the watchdog. A small frontend page or external check (UptimeRobot, etc.) is the next obvious step.
- The `idx_pending_systems_status` (status alone) index from a prior migration is now subsumed by Stage 1's `idx_pending_systems_status_date` composite. Harmless redundancy; can be pruned later.

---

#### Master Haven 1.53.0 (2026-04-28) - Pi Freeze Mitigation, Stage 1 (Hot-Path Indexes + Trim Rewrite)
First of three planned stages addressing the 2026-04-28 Raspberry Pi hard-freeze (full lockup, monitor + keyboard unresponsive, required power cycle). Diagnosis traced the freeze to write-lock pile-up triggered by `db.add_activity_log()` running an unbounded `DELETE ... WHERE id NOT IN (... ORDER BY timestamp DESC LIMIT N)` on every single submission. With no index on `activity_logs.timestamp`, that DELETE forced SQLite into a full scan plus in-memory sort while holding the write lock. Under sustained submission load (queue traffic, audit log queries, polling endpoints), every other writer queued behind it, each holding a Python connection plus partial response in memory — eventual OOM, kernel deadlock, frozen box. Stage 1 removes this single hot path; Stages 2 (memory hot paths) and 3 (operational hardening / swap / monitoring) are not yet started.

**Backend API 1.50.0**
- New migration **v1.71.0** adds the missing indexes on hot tables:
  - `idx_activity_logs_timestamp` on `activity_logs(timestamp DESC)` — the load-bearing one. The whole point of Stage 1.
  - `idx_audit_submitter`, `idx_audit_action`, `idx_audit_submission_type` on `approval_audit_log` — partner audit-log search filters were full-scanning a continuously-growing table.
  - `idx_audit_source` on `approval_audit_log(source)` — guarded with a column-presence check since `source` was added in v1.61.0.
  - `idx_pending_systems_status_date` on `pending_systems(status, submission_date DESC)` — every pending-queue listing query.
  - `idx_pending_systems_discord_status` on `pending_systems(discord_tag, status)` — partner-scoped queue listings.
- **`db.add_activity_log()` rewritten** ([db.py:98-141](Haven-UI/backend/db.py#L98-L141)):
  - Trim query now uses indexed cutoff lookup: `DELETE FROM activity_logs WHERE timestamp < (SELECT timestamp FROM activity_logs ORDER BY timestamp DESC LIMIT 1 OFFSET ?)`. With the new index, this is one b-tree walk to find the cutoff timestamp and a range scan for deletion. No `NOT IN`, no full scan, no in-memory sort. `COALESCE` to empty string handles the bootstrap case where the table has fewer than `ACTIVITY_LOG_MAX` rows.
  - Trim moved off the per-write hot path: a process-local counter `_activity_log_insert_counter` now only triggers trim every 100th insert. 99 of every 100 activity-log writes now pay zero trim cost — just `INSERT + commit + close`.
- Bumped `/api/status` version `1.49.1 → 1.50.0` in [routes/auth.py](Haven-UI/backend/routes/auth.py).

**Why these specific tables**: an audit pass against `Haven-UI/backend/routes/*.py` and the SQLite `init_database` block confirmed (1) zero indexes on `activity_logs` (the trim path), (2) `approval_audit_log` already had `timestamp`, `approver_username`, and `submission_discord_tag` indexes from migration v1.10.0 but was missing the four other filter columns the partner audit-log endpoint uses, and (3) `pending_systems` only had `idx_pending_systems_glyph_code`. The compounding factor was that the audit log and pending queue are both polled by the partner UI — every poll on a busy day hit a full table scan that fought for the write lock that the activity-log trim was holding.

**Not in this stage** (intentional — kept the diff small):
- `SELECT *` + Python-side filtering in [discoveries.py](Haven-UI/backend/routes/discoveries.py) and [systems.py](Haven-UI/backend/routes/systems.py) still loads big result sets into RAM; that's the Stage 2 memory-bound work.
- Leading-wildcard `LIKE '%term%'` searches on audit log and discoveries still defeat indexes — Stage 2 should swap these for FTS5.
- No swap file / zram on the Pi yet — Stage 3.
- No `VACUUM` / WAL checkpoint cron on the Pi yet — Stage 3.
- No health/monitoring page yet — Stage 3.

**Migration is idempotent and zero-downtime**: every `CREATE INDEX` uses `IF NOT EXISTS`; the source-column index is column-presence-guarded. On the production Pi DB this should run in well under a second — the tables are small (the freeze was lock contention, not data volume).

---

#### Master Haven 1.52.1 (2026-04-28) - Retired keeper-discord-bot-main (Archived)
The legacy Discord bot `keeper-discord-bot-main` was retired and archived. The active bot is `The_Keeper/` (community-maintained by Stars), which has been the only bot running in production for some time — the legacy folder was unused dead weight.

**What moved**:
- `C:\Master-Haven\keeper-discord-bot-main\` (78 MB, working tree + `.git`) → `C:\Master-Haven-Archives\2026-Q2\2026-04-28-keeper-discord-bot-main\keeper-discord-bot-main\`
- `C:\Master-Haven\keeper-discord-bot-main.zip` (1.0 GB, March 2026 backup) → same archive folder
- ARCHIVE_NOTE.md alongside, explaining what / why / where the live replacement is / GitHub state / restore notes

**GitHub state**:
- Repo: `https://github.com/Parker1920/Keeper-bot` (separate from `Parker1920/Master-Haven` — the legacy bot was never tracked in Master-Haven; gitignored since the start)
- Final commit: `92b4e22` "Final snapshot before archival" — preserves uncommitted work that was on disk (new `screenshot_reader.py` cog wired into `main.py`, bulk `.gitignore` import, `requirements.txt` +1, `.claude/settings.json`)
- Tag: `v1.0-archived` pushed
- **Manual follow-up needed**: archive the GitHub repo via Settings → Danger Zone → "Archive this repository" (makes it read-only).

**Backend API 1.49.1**
- Removed `_resolve_keeper_bot_dir()` and `_resolve_keeper_db()` methods from [Haven-UI/backend/paths.py](Haven-UI/backend/paths.py).
- Removed `self.keeper_bot_dir` and `self.keeper_db` attributes from `HavenPaths.__init__`.
- Removed `get_keeper_database()` convenience function.
- Removed `'keeper'` branch from `get_logs_dir()` and `get_data_dir()` — only `'haven-ui'` and `main` (default) remain.
- Removed `keeper_bot_dir / 'data'` entries from `find_database()` and `find_data_file()` search paths.
- Removed `keeper_bot_dir` / `keeper_db` lines from `__repr__` and `KEEPER_DB_PATH` from the `__main__` debug block.
- Zero external callers existed — verified via repo-wide grep for `haven_paths.keeper`, `get_keeper_database`, `get_logs_dir('keeper')`, `get_data_dir('keeper')`. The resolver code was load-bearing for nothing.
- Bumped `/api/status` version `1.49.0 → 1.49.1` in [routes/auth.py](Haven-UI/backend/routes/auth.py).

**Test cleanup**: Deleted three obsolete integration test files that imported `Path('keeper-discord-bot-main') / 'src'`:
- `Haven-UI/tests/integration/keeper_test_bot_startup.py`
- `Haven-UI/tests/integration/keeper_test_integration.py`
- `Haven-UI/tests/integration/test_keeper_http_integration.py`

These had been broken since the archive move and would have stayed broken — they tested the retired bot, not The_Keeper.

**Quick Reference table**: `keeper-discord-bot` row replaced with `The_Keeper`; the explanatory note now points future-self to the archive location.

**Pi follow-up** (separate task, not done in this release): verify no standalone `Parker1920/Keeper-bot` clone exists on `pi8gb@10.0.0.229` outside `~/docker/haven-ui/Master-Haven/` (that path's clone is fine — `keeper-discord-bot-main` is gitignored in Master-Haven so it should not exist there). Confirm `the-keeper` container is the only Discord bot running.

---

#### Master Haven 1.52.0 (2026-04-28) - Unified Submission Source Attribution (Pending-Card Refactor: Stage 1)
First stage of the pending-approval-card unification work. Backend-only — no UI change yet. Adds a canonical `source` enum to every pending and approved table so the UI (Stage 2) can render consistent source badges and analytics can split keeper-bot uploads out of generic extractor stats.

**The problem this solves**: production had three competing values in `pending_systems.source` (`manual`, `haven_extractor`, `companion_app`) but `haven_extractor` was overloaded — it bucketed per-user extractor mod uploads, the legacy shared `Haven Extractor` system key, AND the live `Keeper 2.0` Discord bot key all together. `pending_discoveries`, `discoveries`, `pending_region_names`, and `regions` had no `source` column at all, so Keeper bot uploads looked identical to web wizard submissions in the data layer. The 30-row `companion_app` bucket turned out to be early extractor prototype data from Dec 2025 (before the dedicated extractor key existed) — verified against the live Pi DB by tracing api_keys.created_at against the row timeline.

**Final source enum** (canonical across all five tables):
- `manual` — web wizard, no API key on the request
- `haven_extractor` — every authenticated extractor-style key (per-user `Extractor - <username>` keys, the legacy `Haven Extractor` system key, the prototype `Haven` admin key)
- `keeper_bot` — dedicated Keeper Discord bot keys (`Keeper 2.0` + dormant `Keeper Bot` v1)

**Backend API 1.49.0**
- New `resolve_source(api_key_name)` helper + `SOURCE_*` constants + `KEEPER_API_KEY_NAMES` frozenset in [Haven-UI/backend/constants.py](Haven-UI/backend/constants.py). Single source of truth for the enum, used by every submission route.
- `submit_system` ([approvals.py:127](Haven-UI/backend/routes/approvals.py#L127)): replaced 9-line `if/elif/else` source-decision block with a one-line `resolve_source()` call. The watcher-vs-manual activity-log branch keys off `source != 'manual'` instead of the old `'companion_app'` literal.
- `/api/extraction` ([approvals.py:2681](Haven-UI/backend/routes/approvals.py#L2681)): replaced the brittle `key_type not in ('extractor','extractor_user')` check (which would store the literal API key name like "Keeper 2.0" in the source column) with the resolver. Also fixed the same pattern in the JSON `submission_data['source']` field at [approvals.py:2475](Haven-UI/backend/routes/approvals.py#L2475) so the JSON blob source matches the column.
- `/api/discoveries` + `/discoveries` ([discoveries.py:87](Haven-UI/backend/routes/discoveries.py#L87)): now read `X-API-Key` header and resolve source. INSERT statement adds `source` column. Keeper bot continues to work with no client-side change — the resolver maps its key name to `keeper_bot` automatically.
- `/api/submit_discovery` ([discoveries.py:612](Haven-UI/backend/routes/discoveries.py#L612)): hard-coded `source=SOURCE_MANUAL` since this is the web wizard path.
- `approve_discovery` ([discoveries.py:907](Haven-UI/backend/routes/discoveries.py#L907)): copies `source` from the pending row to the approved `discoveries` row on approval.
- `/api/regions/{rx}/{ry}/{rz}/submit` ([regions.py:944](Haven-UI/backend/routes/regions.py#L944)): now reads `X-API-Key` and resolves source. Three INSERT INTO regions sites updated to carry source through approval (single approve, batch approve, and the direct admin update path).
- CSV import region INSERT ([csv_import.py:653](Haven-UI/backend/routes/csv_import.py#L653)): explicit `source='manual'`.

**Migration 1.69.0** (run automatically on backend startup; takes ~100ms on Pi DB):
- Adds `source TEXT NOT NULL DEFAULT 'manual'` column to `pending_discoveries`, `discoveries`, `pending_region_names`, and `regions` (skipped if column already exists — idempotent).
- Backfills all existing `pending_discoveries` (26 rows) and `discoveries` (46 rows) as `keeper_bot` — the only ingest path that's ever existed for those tables is the Keeper Discord bot, confirmed against payload shapes on the live DB.
- Splits Keeper traffic out of `pending_systems` (12 rows) and `systems` (2 rows) by matching `api_key_name IN ('Keeper 2.0', 'Keeper Bot')`. For approved systems, traces back through `pending_systems` on glyph + galaxy.
- Folds the 30-row `companion_app` bucket in `pending_systems` (and 1 row in `systems`) into `haven_extractor`. Those rows are early-Dec-2025 extractor prototype data submitted via the `Haven` admin key before `Haven Extractor` (id=4, created 2026-01-18) existed.
- Logs final source distributions per table for post-migration validation.

**Validated** against a 2026-04-28 Pi snapshot copied locally. Final distributions: pending_systems = `{manual: 4519, haven_extractor: 2791, keeper_bot: 12}`, systems = `{manual: 9331, haven_extractor: 2472, keeper_bot: 2}`, pending_discoveries = `{keeper_bot: 26}`, discoveries = `{keeper_bot: 46}`, pending_region_names = `{manual: 1346}`, regions = `{manual: 2057}`. Row totals preserved across every table.

**What this enables (Stage 2, not in this release)**: a unified `<PendingCard>` React component that renders consistent source badges (slate `manual` / teal `haven_extractor` / Discord-blurple `keeper_bot`) across pending systems, pending discoveries, pending region names, and edit requests — replacing the current per-card-type hardcoded color/layout divergence in [SystemApprovalTab.jsx](Haven-UI/src/components/SystemApprovalTab.jsx) and [DiscoveryApprovalTab.jsx](Haven-UI/src/components/DiscoveryApprovalTab.jsx).

---

#### Master Haven 1.51.1 (2026-04-28) - DB Stats Populated-Regions Scope Fix
Fixes asymmetric scoping between "Named Regions" and "Populated Regions" on the public DB Stats page. The `regions` table's UNIQUE constraint is `(reality, galaxy, region_x, region_y, region_z)` (set in migration v1.49.0 to support per-reality and per-galaxy region naming), so the same coordinate triple can legitimately have different names in different galaxies/realities and counts as N rows. The `populated_regions` query, however, was doing `SELECT DISTINCT region_x, region_y, region_z FROM systems` — collapsing those same multi-galaxy occurrences into a single populated count and producing an inflated gap between the two stats (e.g., 2,215 named vs 1,893 populated).

**Backend API 1.48.8**
- Both `populated_regions` queries in [Haven-UI/backend/control_room_api.py](Haven-UI/backend/control_room_api.py) (super admin path at line 2719 and public path at line 2873) now distinct on `(COALESCE(reality, 'Normal'), COALESCE(galaxy, 'Euclid'), region_x, region_y, region_z)`. `COALESCE` keeps legacy rows where reality/galaxy are NULL from being silently dropped — they bucket into `Normal`/`Euclid` which matches the historical default.
- No schema change, no migration. Pure read-side query update.
- Partner/sub-admin path unaffected (it doesn't compute `populated_regions`; it counts rows in the `regions` table directly via `SELECT COUNT(*) FROM regions WHERE discord_tag = ?`, which is already correctly scoped).

---

#### Master Haven 1.51.0 (2026-04-27) - Public Changelog Page + Voyager's Haven Brand Mark
New public-facing `/changelog` route at `havenmap.online/haven-ui/changelog` — the Voyager's Haven story page. Hero, "What We've Built" product grid, "Recent Witnessing" timeline grouped by month (newest first, computed at render time from `timeline.json`), "What's Still Being Made" three-horizon roadmap, and a footer with a Discord CTA placeholder. Page is publicly readable, no auth.

Same release replaces the global Haven brand mark in the navbar — previously a Heroicons `SparklesIcon` rendered inside a CSS gradient tile — with an animated GIF (`Haven-UI/public/assets/voyagers-haven-mark.gif`). The teal/violet gradient is preserved as a fallback shown if the image fails to load.

**Haven-UI 1.49.0**
- New page: [Haven-UI/src/pages/Changelog.jsx](Haven-UI/src/pages/Changelog.jsx) — uses existing `--app-primary` (teal) and `--app-accent-2` (violet) tokens; introduces a new `--app-accent-amber` (`#ffb44c`) token in [Haven-UI/src/styles/index.css](Haven-UI/src/styles/index.css) for in-development status pills.
- Static content lives in [Haven-UI/src/data/changelog/](Haven-UI/src/data/changelog/) — `products.json`, `timeline.json` (oldest-first; component reverses at render), `roadmap.json`. To add a new entry, append to the relevant JSON file and bump versions; no rebuild logic required beyond Vite's standard build.
- Lazy-loaded route added in [Haven-UI/src/App.jsx](Haven-UI/src/App.jsx); top-level "Changelog" link added to `NAV_LINKS` in [Haven-UI/src/components/Navbar.jsx](Haven-UI/src/components/Navbar.jsx) (renders in both desktop and mobile from a single source).
- Navbar logo: replaced the `SparklesIcon` JSX with an `<img>` resolved via `import.meta.env.BASE_URL` so the asset path works in both dev (`/assets/...`) and prod (`/haven-ui/assets/...`). Falls back to the existing teal/violet gradient if the GIF can't load.
- **Follow-up not done in this release**: favicon was left as the existing inline SVG; per the build prompt the favicon could be regenerated as a static PNG of the GIF's first frame, but image extraction tooling wasn't run in this session. The Discord CTA on the page footer is wired to `href="#"` with a `data-todo="discord-invite-url"` marker — needs a real invite URL.

---

#### Master Haven 1.50.13 (2026-04-21) - Numpy Auto-Install + Galaxy Diagnostic Logs (Extractor)
Fixes two problems reported from a live user session (user "chris"): (1) procgen system/region names not being generated — log showed `ModuleNotFoundError: No module named 'numpy'` at mod load, causing `nms_namegen` imports to fail and fall back to `System_{glyph}` / `Region_{glyph[:8]}`. Root cause: the auto-updater (`haven_updater.ps1` + `UPDATE_HAVEN_EXTRACTOR.bat`) only swaps the `mod/` folder from the mod-only GitHub release zip — it never touches the embedded Python's `site-packages`. Users who updated from v1.8.x to v1.9.x via the in-app updater silently lost procgen because the v1.9.0 numpy dependency added in `FIRST_TIME_SETUP.bat` never ran on their install. (2) Galaxy always reporting as Euclid in submissions — no INFO-level diagnostics in place to tell whether `player_state.mLocation.RealityIndex` is returning a genuine 0 or a broken struct access reading the wrong bytes post-Voyagers. v1.8.1 fixed out-of-range rejection but `0` is in range and gets accepted blindly.

**Haven Extractor 1.9.3**
- `nms_namegen` import block rewritten to attempt `python\python.exe -m pip install numpy` on `ImportError`, then retry the import. Mirrors the v1.6.3 hgpaktool auto-install pattern from `nms_language.py` — uses the embedded Python resolved via `Path(__file__).resolve().parent.parent / "python" / "python.exe"` (since `sys.executable` inside pyMHF is `NMS.exe`, not Python). 120s pip timeout.
- Logger creation moved above the namegen import so the auto-install block can log progress at module load time.
- `_read_galaxy_from_player_state()` raw-value log promoted from DEBUG to INFO and now includes the resolved galaxy name: `[GALAXY] RealityIndex=N -> Euclid`. Called once per primary-path coord resolution, so no log flooding.
- `_get_coords_from_universe_address()` success log promoted from DEBUG to INFO and renamed `[COORDS]`, showing raw `universe_addr` hex + resolved glyph/galaxy. Enables post-hoc correlation between packed address and reported galaxy.
- `_get_coords_from_player_state()` fallback-path raw `RealityIndex` + voxel log promoted from DEBUG to INFO. Rare path (only fires when mUniverseAddress unavailable) so negligible volume cost.
- `FIRST_TIME_SETUP.bat` title bumped to v1.9.3.
- **Does not yet fix the galaxy bug itself** — the next chris export will surface the raw RealityIndex value and lets us decide whether to add a direct-offset fallback read (similar to `DifficultySettingPreset` at `player_state + 0x11890`) in a subsequent release, or whether the struct access is fine and something else is wrong.

---

#### Master Haven 1.50.12 (2026-04-21) - Custom System Name Field Restored (Extractor)
Re-adds the "Custom System Name" text field and "Apply Custom Name" button to the Haven Extractor GUI. Removed in v1.9.0 when procgen name generation was added — but procgen can't capture **renamed** systems (players can rename any system they visit in-game, and that name lives in save state, not the procgen algorithm). With procgen-only, any renamed system got uploaded under its canonical name, erasing the community-assigned one. The restored flow preserves both names: custom name becomes the system name, procgen name is stuffed into the `description` field so the canonical name isn't lost for downstream tooling.

**Haven Extractor 1.9.2**
- New GUI field `custom_system_name` (STRING, editable) in the extractor config panel, positioned right above the read-only Status field.
- New `Apply Custom Name` button. Pressing it:
  - Validates the field is non-empty and that a current system is loaded (has a glyph code)
  - Sets `system_name` on `_current_system_coords` so the next `_save_current_system_to_batch` picks it up
  - If the current system is already in `_batch_systems` (e.g., warp triggered auto-save before Apply), patches that entry in place — updates `system_name`, ensures `procedural_name` is populated, and appends `Procedural name: <procgen>` to the `description` field (dedup-safe, won't repeat on multiple presses)
  - Clears the input field so the next system starts fresh
  - Updates status display with the applied name
- `_save_current_system_to_batch` now **always** computes the procgen name (previously only computed as fallback). Result stored as `procedural_name` on the batch entry regardless of which name wins.
- When the final `system_name` differs from the procgen name (user override path), `description` gets `Procedural name: <procgen>` appended. `custom_name_applied` flag also set on the batch entry for downstream consumers.
- No behavior change for systems the user doesn't rename — flow is identical to 1.9.0 (memory read → game state string → procgen fallback).

**Backend API 1.48.7**
- `/api/extraction` endpoint now accepts a `description` field from the extractor payload and passes it through to `submission_data['description']`. That flows into the existing `systems.description` column on approval ([approvals.py:1072, 1846](Haven-UI/backend/routes/approvals.py)) — no schema migration needed, the column already existed and was just never wired to extractor submissions.

**Why the description column (not a dedicated `procedural_name` column)**: `systems.description` already exists and is the only free-form text field on the system row that's visible in the Haven-UI SystemDetail page. Approvers see the procgen name at review time as a natural prose annotation ("Procedural name: Uhdeon VIII"), and historical tooling/exports that concatenate system fields keep working without migration. Cheaper than a new column with equivalent function.

---

#### Master Haven 1.50.11 (2026-04-21) - Reissue Extractor API Key (Super Admin Tool)
Super admin can now reissue an API key for any registered extractor user from the admin UI. Use case: a user loses their key (deleted config, bad update, swapped machines) and has no way to recover it — keys are SHA256 hashed one-way at storage so plaintext was never retrievable.

**Root cause of typical "lost key" reports (observed with member "dreams of a dark")**: The Haven Extractor 1.9.0 update added a numpy dependency. If numpy wasn't already installed, the `nms_namegen` import chain can fail, which on some pyMHF configurations leaves the mod partially loaded. Any subsequent GUI setter (discord_username, community_tag, reality_mode) calls `_save_config_to_file()` which writes `"api_key": API_KEY` where `API_KEY` is the module-level global. If `load_config_from_file()` didn't populate it (silent failure path), the setter writes an empty string back to `Documents/Haven-Extractor/config.json`, wiping the previously-saved key. Manually installing numpy afterward fixes the mod but the config is already empty, and the registration endpoint refuses to re-issue because `api_keys` already has a row for that username (`'already_registered'` branch, [extractor.py:296-321](Haven-UI/backend/routes/extractor.py#L296-L321)). The reissue endpoint is the recovery path.

**Backend API 1.48.6**
- New `POST /api/extractor/users/{key_id}/reissue-key`: super admin only. Generates a fresh `vh_live_...` key, overwrites `key_hash` + `key_prefix` on the existing `api_keys` row, re-activates the row, and returns the plaintext key exactly once. Preserves `total_submissions`, `profile_id`, `rate_limit`, `discord_username`, and all community linkage — the user's submission history stays intact.
- Writes an `approval_audit_log` entry with `action='reissue_api_key'`, `submission_type='extractor_user'`, recording which super admin performed the reissue.
- 404 if the key_id doesn't exist, 400 if the row isn't an extractor-type key, 403 if the session isn't super admin.

**Haven-UI 1.48.2**
- ExtractorUsers page: new **Reissue Key** button (amber) on every user card (super admin only), next to Edit/Suspend.
- Confirmation modal explains the action invalidates the user's current key and preserves submission history.
- Post-reissue modal displays the new plaintext key once in a monospace field with a Copy button (falls back to `window.prompt` on non-HTTPS where `navigator.clipboard` is blocked).
- Modal includes instructions for the user on how to restore the key on their side: either paste into `%USERPROFILE%\Documents\Haven-Extractor\config.json` under `"api_key"`, or delete that file and let the extractor auto-register (which now succeeds since the DB row has been refreshed).

---

#### Backend API 1.48.4 (2026-04-15) - Public User Stats Endpoint for Discord Bot
New public endpoint for Discord bots (or any HTTP client) to look up a player's contribution stats by username.

**Backend API 1.48.4**
- New `GET /api/public/user-stats?username=X`: returns manual system count, extractor system count, discovery count, community list, and last activity date for a given username
- No authentication required — designed for Discord bot slash commands
- Username normalization matches the contributor leaderboard: strips `#`, removes trailing 4-digit Discord discriminators, case-insensitive
- Systems counted from `pending_systems` (approved only), discoveries from `discoveries` table
- Returns 404 if no contributions found for that username

---

#### Haven Extractor 1.9.0 (2026-04-18) - Procedural Name Generation via Vendored nms_namegen
Vendored the `nms_namegen` library (MIT, https://github.com/stuart/nms_namegen) into the extractor as a native Python module. Generates canonical NMS procedural names for systems, regions, and planets from portal codes and planet seeds — matching the game's actual output. Previously, systems without a memory-readable name fell back to `System_{glyph}` and regions to `Region_{glyph[:4]}`.

**Haven Extractor 1.9.0**
- Vendored `nms_namegen` v2.0.0 at `mod/nms_namegen/` (8 Python files + 5.4 MB `letter_map.json` + MIT LICENCE). No modifications to upstream source.
- `_generate_system_name()` now called as fallback when game memory doesn't provide a system name (replaces `System_{glyph_code}` placeholder)
- `_generate_region_name()` now called in both `_get_coords_from_universe_address()` and `_get_coords_from_player_state()` (replaces `Region_{glyph_code[:4]}` placeholder)
- New `_generate_planet_name()` wrapper: generates planet names from seed when memory name read fails (replaces `Planet_{index}` placeholder)
- Planet seed (`GcSeed` at offset 0x20 in `PlanetGenInputData`) now read in `_read_planet_gen_input_direct()`
- Added `planetName` to the nms_namegen import block alongside existing `systemName` and `regionName`
- All name generation gracefully degrades: if nms_namegen import fails (e.g., missing numpy), falls back to glyph-based placeholders as before
- Added `numpy>=2.0` to `pyproject.toml` dependencies
- `FIRST_TIME_SETUP.bat` updated with numpy check/install step
- GUI: Removed "System Name" text field and "Apply Name" button (procedural names replace manual entry)
- GUI: Added read-only "Status" field showing upload results, batch count, and error messages
- Region auto-submit: export flow now submits procedural region names to `POST /api/regions/{rx}/{ry}/{rz}/submit` for admin approval
- Terminal output: condensed from ~120 lines to ~15 lines per system with aligned columns

**Backend API 1.48.5**
- Fixed: Haven sub-admin `pending_systems` SELECT queries missing `galaxy` column — galaxy always displayed as "Euclid" for Haven sub-admins (super admin and partner queries were correct)

---

#### Master Haven 1.50.10 (2026-04-14) - Keeper Discord Bot Discovery Approval Bypass Fix
Community-maintained Keeper Discord bot was uploading discoveries straight into the live `discoveries` table via `POST /api/discoveries` (and its legacy `/discoveries` alias), skipping the approval queue that every other submission path uses. Root cause: those two endpoints predated the discovery approval workflow introduced in v1.33.0 and were never retrofitted — they did a direct `INSERT INTO discoveries` with no auth, no self-approval check, and no discord_tag scoping.

**Backend API 1.48.3**
- `POST /api/discoveries` and `POST /discoveries` rewritten to insert into `pending_discoveries` with `status='pending'` instead of the live table. Same approval workflow (`/api/approve_discovery/{id}`, `/api/reject_discovery/{id}`) that covers web-UI submissions now covers Keeper bot uploads.
- Bot payload shape preserved: `discovered_by` still accepted as fallback for `discord_username`, `discord_tag`/`discord_user_id`/`discord_guild_id` stored in the payload JSON blob. Bot requires no code change.
- Response keeps backward-compatible `discovery_id` field (aliased to the new pending submission id) alongside the new `submission_id` + `status: 'pending'` fields so existing bot response parsing still works.
- Duplicate detection extended: now checks both live `discoveries` and `pending_discoveries` (prevents bot re-submitting while a prior submission sits in the queue).
- Activity log entry switched from `discovery_added` to `discovery_submitted` to match the rest of the pending-queue flow.

---

#### Master Haven 1.50.9 (2026-04-13) - Galaxy Defaulting-to-Euclid Bug Fix
Ekimo reported a system uploaded while in galaxy 256 (Odyalutai) but the admin page showed Euclid. Code audit turned up four issues combining to produce the symptom — the primary culprit was a silent galaxy-clamping default in the player_state fallback path.

**The root-cause chain**: (1) Player warps to non-Euclid galaxy → (2) `on_system_generate` fires before NMS populates `mPlanetDiscoveryData.mUniverseAddress` → (3) primary decode returns None → (4) player_state fallback runs, reads broken post-Voyagers struct → (5) `location.RealityIndex` returns garbage out of 0-255 range → (6) **code silently clamped galaxy_idx to 0 (Euclid)** instead of rejecting the read → (7) fabricated coords cached as `self._current_system_coords` → (8) retry guards elsewhere only ran if coords were None, so the bogus cached result was never replaced when mUniverseAddress became readable a beat later → (9) batch save used the cached fake-Euclid coords → (10) submission went out with `galaxy_name="Euclid"`.

**Haven Extractor 1.8.1**
- **Fix 1 (root cause)**: `_get_coords_from_player_state` no longer silently clamps out-of-range `RealityIndex` to 0. If the raw value is outside 0-255 the whole read is rejected (returns None), letting the caller retry or fall through without fabricating Euclid.
- **Fix 2**: `_check_duplicates` now receives the actual batch galaxy instead of defaulting to Euclid. Pulled from the batch's unique `galaxy_name`; if the batch spans multiple galaxies (unusual), per-system galaxy is handled by the backend.
- **Fix 3 (diagnostics)**: `_get_coords_from_universe_address` now logs the raw `universe_addr` hex value on every successful decode. `_get_coords_from_player_state` logs the raw `RealityIndex` value and the full GalacticAddress field contents before deciding. Any future galaxy-mismatch report can be diagnosed from the log alone.
- **Fix 4 (race recovery)**: New `_maybe_upgrade_coords()` helper replaces the `if self._current_system_coords is None` retry guard at every coord retry site (`on_system_generate`, `on_creature_roles_generate` early + post-capture, and APPVIEW). The helper re-attempts resolution whenever the cached coords are `None` OR have `from_fallback=True`, and promotes primary mUniverseAddress results over stale fallback results with a visible `[COORD UPGRADE]` log line.
- Player_state fallback results are now tagged `from_fallback=True` in the returned dict; mUniverseAddress results aren't.
- `on_system_generate` explicitly clears `self._current_system_coords = None` before running the first resolution attempt, so stale coords from a prior system can't carry over if the new resolution fails.

---

#### Master Haven 1.50.8 (2026-04-13) - Option B: Omit No-Data Fields, Preserve Real Game Data
Replaces v1.50.7's "send Unknown strings" approach with a cleaner payload omission. When NMS itself reports no data for economy/conflict/lifeform (race_raw > 6 signal, unchanged from v1.6.14), the extractor now leaves those four fields OUT of the submission payload entirely and adds a `no_trade_data: true` flag. The backend detects the flag and stores `NULL` for those columns in the `systems` table, so they're distinguishable from "Unknown" / unset at the data layer. Haven UI frontend can key off the null values (or the flag in `pending_systems.submission_data`) to render `-Data Unavailable-` / `Uncharted` specifically for those systems — future frontend follow-up.

**Haven Extractor 1.6.15**
- `_extract_system_properties()` pops `economy_type`, `economy_strength`, `conflict_level`, `dominant_lifeform` from `sys_props` when `system_no_data` is set, and adds `no_trade_data: True`. Payload sent to `/api/extraction` simply lacks those keys.
- Normal systems (race 0-6) keep all four fields as before — no change to scanned-system behavior.

**Backend API 1.48.2**
- `/api/extraction` accepts `no_trade_data` boolean from payload and stores it in `pending_systems.submission_data` JSON.
- When `no_trade_data` is `True`, backend sets `economy_type`/`economy_level`/`conflict_level`/`dominant_lifeform` to `None` in `submission_data` so approval inserts NULL into `systems` (not the literal string `"Unknown"`). Fields in the `systems` table for no-data systems are now genuinely null.
- When `no_trade_data` is `False` (or absent), existing `payload.get(..., 'Unknown')` default behavior is preserved — zero regression for manual submissions and pre-1.6.15 extractors.

---

#### Master Haven 1.50.7 (2026-04-13) - Extractor Respects No-Data System State
Fixes extractor submitting fabricated economy/conflict/lifeform data for systems that **legitimately have no values** for those fields in-game. Not a scan-progress issue — even after a full freighter scanner-room scan (which normally gets everything NMS can give), some systems categorically show `-Data Unavailable-` for economy/conflict and `Uncharted` for lifeform. The extractor was sending fake `Fusion / Low / None`-type data instead of honoring that state.

**The signal**: `INHABITING_RACE` raw value > 6 (real enum is 0-6: Gek, Vy'keen, Korvax, Robots, Atlas, Diplomats, Uninhabited). Value 7+ is NMS's in-memory marker for "no race data available for this system". The adjacent `TRADING_DATA` (0x2240) and `CONFLICT_DATA` (0x2250) fields in these systems still decode to valid-looking enum values like `Fusion / Poor / Low / Gek` — which we were accepting as real data. Wander Respite's log consistently showed `[DIRECT] Race: Unknown(7) (raw: 7)` — that's the marker.

**Haven Extractor 1.6.14**
- `_read_system_data_direct()` now clears `economy_type`, `economy_strength`, `conflict_level`, `dominant_lifeform` to `"Unknown"` when `race_val > 6`. Logs `System reports no economy/conflict/lifeform data (race=N) — matches in-game '-Data Unavailable-' / 'Uncharted'`.
- `_extract_system_properties()` tracks `system_no_data` flag and **suppresses the struct fallback** for economy/conflict/lifeform in that state. Struct access would read the same memory region and silently re-fabricate the fake values the direct read just cleared.
- Star color struct fallback still runs unconditionally (star type is visible regardless of scan state, independent signal).
- Submissions for no-data systems now correctly send `"Unknown"` / empty values, matching what the game shows in-game rather than fake `Fusion (Poor)` etc.

---

#### Master Haven 1.50.6 (2026-04-13) - Extractor Cleanup Pass (Log Spam, Alien Race, Cosmetic Output)
Housekeeping pass after v1.6.12 verified the refresh-timing fix works in production (Tython + Wander Respit VH both uploaded with correct per-planet adjectives — `Ample/Full/Observant` on Witheusian Dachi, `Empty/Not Present/Enforcing` on dead Ilminst VIII, varied adjectives across all planets).

**Haven Extractor 1.6.13**
- **Log spam eliminated**: `[HINTS] ExtraResourceHints: empty`, `Planet: '<name>'`, `[HINTS] HasScrap=True (hook time, deferred to extraction)` and hint enumeration lines demoted from INFO to DEBUG. The GenerateCreatureRoles hook fires ~60×/sec during galaxy map browsing on Voyagers — previously produced 10,000+ INFO-level lines per session from these three messages alone. The final `CAPTURED PLANET '<name>' DATA!` block still logs at INFO so actual captures remain visible.
- **`ALIEN_RACES` extended to cover post-Voyagers race enum value 7** (observed consistently for abandoned/no-race systems). Added entries for 7 and 8 as `"None"` to prevent `Unknown(7)` from reaching the submission payload. The 0-6 values are unchanged.
- **`Expected: N planets + M moons` log line suppressed when the values are untrustworthy**: Voyagers broke `PrimePlanets` at offset `0x2268` (returns 0 for every system). Previously produced misleading `Expected: 0 planets + 6 moons` on planet-heavy systems. The line only prints now when the direct read matches the extracted count.
- **Redundant `result["planet_name"] = captured['planet_name']` assignment removed** in `_extract_single_planet`. The memory name read at the top of the name-lookup block is the source of truth; captured name would be identical for name-matched entries (stale overwrite risk for any edge case where memory read returns a slightly-different name).
- **`[NOCAPTURE]` warning** now shows memory slot name instead of just array index.

---

#### Master Haven 1.50.5 (2026-04-13) - Extractor Refresh Timing + Dead-Code Cleanup
Fixes the batched-system regression where the *first* system in a multi-system batch uploaded with generic `Bountiful/Copious/Limited` enum-level flora/fauna/sentinel instead of the biome-appropriate per-planet display adjectives.

**Root cause**: `planet_data.PlanetInfo.Flora` (and Fauna/Sentinel/Weather) is *empty* at hook capture time — it's only populated later by the game. The sole way to get proper display strings is `_auto_refresh_for_export()`, which reads live memory. Pre-Voyagers the APPVIEW hook would fire when the player fully entered the system and trigger this refresh; on Voyagers the APPVIEW hook no longer fires. That left the export-time refresh as the only live path, which works for the *currently-loaded* system but not for already-queued batched systems (their memory has been overwritten by the time export runs).

**Haven Extractor 1.6.12**
- **Apply Name button now triggers `_auto_refresh_for_export()`**: the user clicking Apply Name is a strong "I am currently in this system" signal, and memory is guaranteed live at that moment. This guarantees batched systems get proper display strings as long as the user names them.
- **`_save_current_system_to_batch()` runs a safety-net refresh first**: harmless if memory has already transitioned (the name-match inside the refresh silently skips entries whose names don't exist in `_captured_planets`, which they won't when memory shows a new system).
- **Debug `check_planet_data` GUI button** updated from index-based `_captured_planets[i]` lookups to name-matching (memory slot name → captured entry). Previously reported stale garbage in logs after the name-keying change.
- **`_extract_single_planet` back-compat `elif index in self._captured_planets` branch removed** — all captures are name-keyed now, the fallback never ran.
- **Plant-resource derivation uses `captured is not None`** instead of re-checking index membership. Fixes a dead-code path that was always returning flora_raw=-1.
- Renamed stale `planet_index = len(self._captured_planets)` placeholder in the hook to use `planet_key` throughout (no behavioral change, just removes a misleading variable name).

---

#### Master Haven 1.50.4 (2026-04-13) - Name-Keyed Planet Capture (Voyagers Stride-Shift Recovery)
Fixes the 1.6.10 regression where per-planet biome/size/is_moon showed `Unknown(254)`/garbage for slots 1-5. Voyagers shifted the `PLANET_GEN_INPUTS` per-slot stride (`0x53` bytes no longer correct), so direct reads beyond slot 0 grab wrong memory. Solution: trust the GenerateCreatureRoles hook (which receives the actual `lPlanetData` per fire), but match captured entries to memory slots by **planet name** instead of array index.

**Haven Extractor 1.6.11**
- **`_captured_planets` now keyed by planet name** (was: hook-fire counter index). Duplicate hook fires for the same planet update the existing entry instead of consuming a new slot — this also fixed the case where hook fired twice for Sycihris T1 and dropped Roqeqchiq Isshi from the capture set.
- **6-planet quota is now per unique name** — updates always allowed, only new unique names count against the limit.
- **`_extract_single_planet` reads memory slot's name first, looks up captured data by name** — biome, biome_subtype, planet_size, is_moon come from the matching captured entry. Per-planet correct for all 6 slots.
- **`_auto_refresh_for_export` matches by name** before writing flora/fauna/sentinel/weather display strings — previously stomped wrong entries when hook order != memory order.
- **Direct PLANET_GEN_INPUTS reads made tolerant**: `Unknown(N)` values from shifted stride are now discarded rather than propagated, so slots without a name-match show clean `Unknown` instead of raw enum numbers.
- Restored the biome/size/is_moon captured override that 1.6.10 removed — it was correct, the bug was the index-based lookup.

---

#### Master Haven 1.50.3 (2026-04-13) - Extractor Planet/Moon Swap + Economy/Conflict Fixes
Follow-up to the Voyagers struct break — fixes the remaining struct-path regressions in per-planet and per-system extraction.

**Haven Extractor 1.6.10**
- **Planet/moon swap fix**: Removed the captured-hook-data override for `biome`, `biome_subtype`, `planet_size`, `is_moon` in `_extract_single_planet`. The hook fires in GenerateCreatureRoles order (not memory slot order) and sometimes fires for adjacent systems during galaxy discovery, so `_captured_planets[i]` did not reliably map to `maPlanets[i]`. Direct memory reads from the per-slot `PLANET_GEN_INPUTS` array (already present) are now authoritative for these fields. Captured flora/fauna/sentinel/weather are retained (they're refreshed per-memory-slot by `_auto_refresh_for_export`).
- **Economy/conflict/dominant-lifeform fix**: Wired up the previously-dead `_read_system_data_direct()` helper as primary in `_extract_system_properties`. Direct-offset reads for `TRADING_DATA` (0x2240), `CONFLICT_DATA` (0x2250), and `INHABITING_RACE` (0x2254) replace broken struct-access like `sys_data.TradingData.TradingClass`. Struct path retained as fallback.
- **PlanetCount/PrimePlanets fix**: `_extract_planets` now reads `PLANETS_COUNT` (0x2264) and `PRIME_PLANETS` (0x2268) via direct offsets first, falling back to struct access. Resolves `Expected: 0 planets + 6 moons` cosmetic log error.
- **Unknown-prefix detection**: The `_is_unresolved()` helper treats both `"Unknown"` and `"Unknown(N)"` as failure, so struct fallbacks actually trigger when direct reads return unmapped enum values (previously the `== "Unknown"` checks missed the `"Unknown(5)"` case).

---

#### Master Haven 1.50.2 (2026-04-12) - Extractor Coord Resolution Fix (NMS Voyagers Struct Break)
Structural fix for silent glyph-zero uploads after NMS Voyagers update shifted `cGcPlayerState.mLocation.GalacticAddress` struct offsets.

**Haven Extractor 1.6.9**
- **Primary coord source switched from `player_state.mLocation.GalacticAddress` to `mPlanetDiscoveryData.mUniverseAddress`**. The nested `GalacticAddress.VoxelX/Y/Z/SolarSystemIndex/RealityIndex` fields all returned 0 after Voyagers because NMS.py struct offsets shifted. `mUniverseAddress` is a single packed uint64 with a documented bit layout (X/Y/Z regions, system idx, planet idx, galaxy idx) — one offset vs. five, much less exposure to future NMS struct reshuffling.
- New helpers: `_coords_look_valid()`, `_decode_universe_address()`, `_get_coords_from_universe_address()`, `_get_coords_from_player_state()`, `_resolve_current_coordinates()`
- Consolidated 4 duplicate coord-extraction code blocks (~200 lines) into a single canonical resolver: mUniverseAddress primary → player_state fallback → cached tertiary
- `_coords_look_valid()` rejects all-zero coords (universe origin is impossible in practice) and out-of-range galaxy indices — prevents silent bad-data propagation
- Export-time hard stop in `_run_export_flow`: filters any system with glyph `000000000000` or empty, logs a clear error instead of submitting. Aborts if no valid systems remain.
- Removed obsolete player_state-first logic from `on_system_generate`, `on_creature_roles_generate` (both coord blocks), `on_appview`, and `_get_current_coordinates`

---

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
│   Extracts live data  │   Queues for upload                      