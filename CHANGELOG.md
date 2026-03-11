# Haven Project — Full Changelog

> **Last Updated:** March 9, 2026
> **Repos:** Parker1920/Haven_mdev (legacy, archived) → Parker1920/Master-Haven (active)
> **Timeline:** November 3, 2025 → Present

---

## How This Started

Haven started as a desktop Python app called **Haven Control Room** — a Tkinter/CustomTkinter GUI that managed NMS discovery data locally. It had its own compiled `.exe` (built with PyInstaller), handled system/planet data entry, and talked to a local SQLite database. The whole thing lived in the `Haven_mdev` repo.

Around the same time I was building the **Keeper Discord Bot** — a separate bot that let community members submit discoveries through Discord slash commands. The bot had its own lore system (The Keeper character from Voyager's Haven), phase-based deployment docs, and NMS integration guides. All of that documentation still lives in the `Haven-lore` folder on my desktop.

By mid-November 2025 I realized the desktop app approach wasn't going to scale. I needed a web UI that anyone could use from a browser, proper API endpoints, and a real approval workflow. That kicked off the migration to what became **Master-Haven** — a monorepo with a React frontend, FastAPI backend, and all the game integration tools under one roof.

---

## Haven_mdev Era (November 3 – November 17, 2025)

This was the original repo. The local copy is cleaned out now (all code moved to Master-Haven), but the archive timestamps and directory skeleton tell the story.

### November 3–4 — Project Origin
- Created the Haven_mdev repo and started building
- Built **Haven Mobile Map** — a universal mobile app for viewing the star map on any phone
- Made an **iOS PWA** version with custom loading screen, fixed a bunch of iOS-specific touch/button bugs
- Tested on Mac for compatibility
- Reorganized the entire file structure, set up the docs folder with a "chapters" approach
- Started stress testing — ran 100K record load tests, had to update the file-based data method to handle it
- Added hover capabilities to the galaxy map view, settings panel, and stress test tooling
- Fixed a galaxy map rendering bug
- Fixed icon sizing across the app
- Cleaned up old iOS PWA export code, archived legacy files

### November 5 — Data Structure Overhaul
This was a big day. Rebuilt the entire data architecture in 6 phases:
- **Phase 1:** Started the data structure overhaul
- **Phase 2:** Got the Control Room integrated with the new database schema
- **Phase 3:** Got the Wizard (system entry flow) integrated
- **Phases 4–6:** Integration testing, all passing
- Fixed a duplicate moon bug and updated the moon orbit system
- Found and fixed a garbage `nul` file issue, added those to `.gitignore`
- Added large test data files to `.gitignore` too

### November 6–8
- Big update after resolving some Git issues that had been blocking commits
- Started significant work on the Discord bot integration

### November 10 — Haven Control Room Beta + Discord Integration
This was basically launch day for the Control Room as a web-accessible thing:
- **Haven Control Room beta** released
- Merged the Haven-lore Discord bot into Haven_mdev so everything lived in one place
- Hooked the Keeper bot into the Haven Master database
- Built Discord bot discovery management UI into the Control Room (Phase 4)
- Removed old discovery workflows, replaced with Discord bot integration
- Fixed a circular import in `discoveries_window.py`
- Fixed a Unicode encoding crash in Control Room logging
- Fixed the wizard's "load existing systems" dropdown
- **Phase 5** complete — testing and integration verification done

### November 11 — Official Discord Launch
This is when the community Discord went live with Haven integration:
- Community discoveries now showed up on the star map
- Pushed multiple rounds of updates to the submission wizard, photo handling, and the Keeper bot
- Updated the desktop EXE launcher
- General quality-of-life improvements throughout the day

### November 13 — Migration Begins
- Merged remote tracking branch, resolved conflicts keeping local changes
- Formally initialized the project as "Haven Star Mapping System with Keeper Discord Bot"
- Started moving files to `Archive-Dump` — created dated backup folders for the desktop-era code

### November 14
- Large feature push
- Started architectural groundwork for hosting on the **Raspberry Pi 5**
- More Keeper bot improvements

### November 15
- Wrote up the AI integration docs — a plan for multi-agent AI using Anthropic/OpenAI APIs
- Started the **Round Table AI** concept: 3 agents (Archivist, Sentinel, Lorekeeper) with a Conductor orchestrator
- Continued Pi 5 migration prep

### November 16–17 — Final Haven_mdev Work
- Implemented Phase 2 UI theming: ThemeProvider, FormField, themed Button/Card/Modal components
- Polished the Systems and Discoveries layout
- Backend fixes: coerced numeric coordinate strings before validation, handled missing `jsonschema`, fixed package-qualified imports
- Archived the legacy desktop code into `legacy_desktop_20251116/`
- Created test script for the Round Table AI framework
- Two final large update commits before the repo went dormant

After this, Haven_mdev was done. Everything moved forward in Master-Haven.

---

## The Gap Period (November 18 – December 21, 2025)

Between the last Haven_mdev work and the first Master-Haven commit, I was restructuring everything. The **old Master-Haven snapshot** on my desktop (dated Nov 17-19) shows the intermediate state:
- Standalone migration scripts at the root level (`complete_migration.py`, `force_migrate.py`, `migrate_galaxy_terminology.py`, `migrate_glyph_system.py`)
- Test scripts scattered at the root (`test_approvals_system.py`, `test_station_placement.py`, etc.)
- A `roundtable_ai/` directory for the AI agent prototype
- The `VH-Database.db` file (empty — fresh start)
- `Haven-UI/` already existed as a subdirectory with the React frontend taking shape
- `keeper-discord-bot-main/` brought over from Haven_mdev

This was the period where the project went from "desktop app with a web layer bolted on" to "proper web-first architecture with a monorepo structure."

---

## Master-Haven (December 22, 2025 – Present)

### December 2025

**Dec 22 — Initial Commit**
- Created the Master-Haven monorepo. This was the clean starting point with:
  - `Haven-UI/` — React frontend + FastAPI backend
  - `NMS-Haven-Extractor/` — In-game data extraction mod
  - `NMS-Memory-Browser/` — Live memory inspection tool (PyQt6)
  - `NMS-Save-Watcher/` — Extraction queue manager
  - `keeper-discord-bot-main/` — Discord bot
  - `Planet_Atlas/` — 3D cartography (as a git submodule)

**Dec 27 — Multi-Component Update**
- Simultaneous updates across Haven UI (MoonEditor, PlanetEditor), the NMS Haven Extractor, NMS Memory Browser (collectors, pointer scanner, UI), NMS Save Watcher (config, database, watcher), and the Control Room API

**Dec 31 — End of Year Push**
- Updates to both the extractor and Haven UI

---

### January 2026

**Jan 5 — Major Project Update**
- Large feature push across the board
- Got the README current with the actual state of the project

**Jan 6**
- Removed a screenshot placeholder from the UI
- Several smaller improvement commits

**Jan 7**
- Updated hardcoded URLs
- README improvements and mobile layout updates

**Jan 18–20**
- General updates and extractor improvements

**Jan 27 — Big Update + Cleanup**
- Significant feature additions with code cleanup pass
- Updated the Planet Atlas submodule reference
- This was the **v1.31.0 baseline** — the pre-2.0 state with:
  - Discoveries showcase with featured items and view tracking
  - War Room v1-v3 (territorial conflicts, activity feed, media, peace treaties)
  - Events tracking for community competitions
  - Analytics dashboard with date ranges
  - Sub-admin management, partner accounts, approval workflow with audit logging
  - Haven Extractor at v1.3.8 with direct API submission

---

### February 2026

**Feb 2 — URL Migration Prep**
- Started preparing for the move from ngrok tunneling to `havenmap.online`
- Bulk data transfer from the old system

**Feb 5 — The Big Migration**
- Executed a large-scale data migration
- **Removed secrets from the repo** — API keys and tokens that had been committed. Critical security fix.

**Feb 6 — Docker Deployment**
- Fixed Dockerfile build context paths for Haven-UI
- Fixed Docker config file issues
- Set up auto npm build on Docker container restart
- Added Discord region ID tracking to discoveries
- War Room page improvements
- Fixed various file path issues from the project restructure

**Feb 12**
- Updated the NMS procedural generation adjective reference list
- Cleaned up legacy text reference files

**Feb 21–22 — Discovery + Data Quality**
- Improvements to the discoveries listing page
- Implemented the **data quality scoring system** (C/B/A/S grading)
- Fixed a contributor tracking bug that showed up during batch uploads
- Fixed spectral class handling
- Fixed wrong username values being stored

**Feb 23**
- Added timestamps to contributor activity records

**Feb 24**
- More extractor improvements

**Feb 25 — Planet Data Expansion**
This was a marathon day. Pushed 8 commits covering:
- **Create tab + abandoned systems** — new create tab that properly handles solar systems without space stations
- Rescored data quality levels with updated thresholds
- Added grading dropdown info panels
- **Special planet features** — added tracking for Vile Brood, Dissonance, Ancient Bones, Salvageable Scrap, Storm Crystals, Gravitino Balls, Infested planets, and Exotic Trophies
- Backend database columns for all the special attributes
- Increased the attributes window display size
- Polished the extractor, updated moon card UI
- Final pass on planetary information display

**Feb 26 — The Integration Marathon**
12 commits in one day. This is when the Haven Extractor and Haven UI finally came together end-to-end:
- Added `has_rings` tracking to planet database
- Added `has_moon` table tracking
- **Extractor batch upload + star color migration** — batch upload support with star color data
- System names now color-coded by star spectral class
- Fixed a batch upload bug in the extractor
- Pending submissions edit UI improvements
- **Finalized Haven UI ↔ Extractor mod connection** — full end-to-end integration
- Pre-release cleanup
- Added connection rate limiting to the API
- Fixed config loading bug
- Updated display lists
- Fixed galaxy migration for incorrectly assigned values (0-indexed vs 1-indexed galaxy names)

**Feb 27 — The Great Cleanup**
Post-integration cleanup and documentation day:
- Replaced all ngrok URLs with `havenmap.online` across the entire codebase
- Updated OpenGraph meta tags
- Fixed all port references from `8000` to `8005`
- Removed dead scripts, stale databases, superseded static files, and empty directories
- Updated stale version strings in all `.bat` launcher scripts
- Excluded unnecessary sub-projects from Docker build context (faster builds)
- Added README for NMS-Debug-Enabler
- Regenerated CLAUDE.md with current metrics (235 endpoints, 37 tables, 18,752 lines of code)
- Full post-cleanup audit documentation
- Tagged **v1.6.0** of the Haven Extractor

**Feb 28 — Mod Auto-Updater + Galaxy Fixes**
- Built the mod auto-updater system: `UPDATE_HAVEN_EXTRACTOR.bat` + `haven_updater.ps1`
- Auto-updater checks version, downloads mod-only zip from GitHub Releases, backs up current mod, preserves user config
- Updated community names and descriptions in README
- Replaced the galaxy names list with all 256 NMS galaxies
- Spectral class handling updates
- Tagged Extractor **v1.6.1 through v1.6.4**

---

### March 2026

**Mar 1 — Extractor Star Color + Resource Fixes**
- Migration to backfill star colors for existing records
- Star color extraction from the game now works properly
- Changed approval permissions for partner accounts
- Fixed extractor empty array `[]` edge case
- Fixed all 3 gas resource mappings (they were all wrong — Sulphurine/Radon/Nitrogen were shuffled)
- Fixed purple stellar metal mapping (Quartzite, not Indium — changed in Worlds Part II)
- Gated plant resource on flora level > 0
- Tagged Extractor **v1.6.5 through v1.6.7**

**Mar 2 — Upload Method Tracking**
- Separated analytics by submission method — manual web entry vs Haven Extractor mod vs companion app
- Analytics page got tabs for Manual Submissions and Haven Extractor with source overview bars

**Mar 5 — Community Pages**
- Added the **Community Stats page** — fully public, no auth required
- Per-community cards with system counts, discovery counts, member counts, upload method split
- Activity timeline, discovery type breakdown, contributors table
- Bug fixes throughout the day — community list display, card color defaults

**Mar 7 — Photo Compression**
- Built the full **photo compression pipeline** — automatic WebP conversion with thumbnails
- Uploads auto-compressed to WebP (quality 80, max 1920px) with 300px thumbnails
- Storage reduced ~80%, page loads significantly faster
- Added CLI flags (`--db`, `--photos`) to the photo migration script for Docker/Pi paths
- Cleaned up popup windows on the PC galaxy map view

**Mar 8 — The Big Audit**
The final push to get everything solid. 7 commits in one day:
- Fixed comma-separated photo parsing bug
- Updated glyph photo paths after compression migration
- Fixed a glyph rendering bug on the 3D galaxy map
- **Massive codebase audit** — comprehensive review and cleanup across all components
- Hot fix right after the audit
- Removed unneeded/stale documentation
- War Room media assets updated
- Final photo path adjustments

---

## Current State (March 9, 2026)

| Component | Version | Status |
|-----------|---------|--------|
| Master Haven | 1.43.0 | Active |
| Haven-UI (frontend) | 1.42.1 | Stable |
| Backend API | 1.42.1 | Stable |
| Haven Extractor | 1.6.7 | Stable |
| Debug Enabler | 1.0.0 | Stable |
| Planet Atlas | 1.25.1 | Stable (submodule) |
| Memory Browser | 3.8.5 | Stable |
| Save Watcher | 2.1.0 | Stable |
| Keeper Bot | 1.0.0 | Community-maintained |

**By the numbers:**
- 235 API endpoints
- 37 database tables
- ~18,750 lines of backend code
- 23 frontend pages, 37 components
- 48 schema migrations (v1.0.0 → v1.48.0)
- Self-hosted on a Raspberry Pi 5 at `havenmap.online`

**What's Next:**
- Travelers Collective Phase B (Had.Sh sync) and Phase C (AGT CSV pipeline)
- Haven Exchange (simulated economy — spec complete, not built yet)
- Repo needs to go private + API key rotation (it's still public on GitHub)
- Compute node build (Phase 3) for the Verification Bot
- AI/voice assistant work on Jetson Orin Nano (Phase 4-5, way down the road)
