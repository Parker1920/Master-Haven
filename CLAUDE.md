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
