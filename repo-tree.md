# Master Haven — Complete Repository Tree
**Generated:** 2026-03-08 | **Version:** 1.43.0

---

## Project Overview

**Master Haven** is a comprehensive No Man's Sky (NMS) discovery mapping and archival system built for gaming communities to catalog, share, and preserve their in-game discoveries. The project spans an entire ecosystem: an in-game mod that extracts live data from memory, a queue manager that processes extractions, a FastAPI backend with SQLite storage, a React frontend for browsing and managing discoveries, a Discord bot for community engagement, and a 3D planetary visualization tool.

The repository is organized as a multi-component monorepo at `C:\Master-Haven\`. The primary application is **Haven-UI**, which contains both the React 18 frontend and the FastAPI backend that together serve as the main web dashboard. The **NMS-Haven-Extractor** mod hooks into the running game to extract system, planet, and resource data in real-time. Supporting tools include the **Save Watcher** (extraction queue manager), **Memory Browser** (live memory inspector), **Debug Enabler** (debug flag mod), **Planet Atlas** (3D cartography), and the **Keeper Discord Bot** (community engagement). The **Travelers-Collective** is a newer PostgreSQL-backed microservice for cross-community data aggregation, currently in early development.

Data flows from the NMS game through the Extractor mod → optional Save Watcher queue → Haven API (`/api/extraction`) → pending approval queue → admin review → production database → frontend display. Manual submissions follow a parallel path through the web Wizard form. The system supports multiple Discord communities with partner accounts, sub-admin delegation, per-community data restrictions, and a completeness grading system (C/B/A/S) for cataloged systems.

---

## Root Level (`C:\Master-Haven\`)

📁 **.git/** — Git version control history

📁 **.claude/** — Claude Code session state and project memory

📁 **.venv/** — Python virtual environment (development only, not committed)

📁 **__pycache__/** — Python bytecode cache (build artifact)

📄 **CLAUDE.md** — Comprehensive project instructions: architecture, version history (v1.0.0→v1.43.0), 37-table schema, role definitions, setup guides, and API reference

📄 **README.md** — Public-facing overview: 8 partner communities, feature highlights, and quickstart links

📄 **PARTNER_GUIDE.md** — User-facing guide for community partners and sub-admins

📄 **LICENSE** — MIT license

📄 **.gitignore** — Exclusion rules for Python/Node artifacts, databases, secrets, photos

📄 **.dockerignore** — Docker build exclusions to keep image lean

📄 **.gitmodules** — Git submodule config pointing to Planet_Atlas repository

📄 **update_planet_atlas.bat** — Fetch and pull latest Planet Atlas submodule updates

📄 **HavenExtractor-mod-v1.6.7.zip** — Current mod-only distribution (~53KB) for auto-updater

📄 **code-audit-report.md** — Pre-cleanup code quality audit identifying duplications and dead code

📄 **cleanup-pass-1-report.md** — Pass 1: merged duplicates, extracted shared utilities (103 lines removed)

📄 **cleanup-pass-2-report.md** — Pass 2: removed dead functions and components (271 lines removed)

📄 **cleanup-pass-3-report.md** — Pass 3: removed RTAI system, dead endpoints, 15 dead scripts (66 lines removed)

📄 **cleanup-pass-4-report.md** — Pass 4: removed migrate_hub_tags and DATA_JSON legacy system (202 lines removed)

📄 **systems-overlap-audit.md** — Data synchronization audit: 11 overlapping systems between hardcoded and DB-driven data

📄 **repo-tree.md** — This file

---

## Haven-UI/ — Main Application (React Frontend + FastAPI Backend)

The primary application. Contains the web dashboard frontend, the Python API backend, deployment scripts, tests, and runtime data.

### Haven-UI/ Root Files

📄 **package.json** — Node.js project (v1.42.0): React 18, Vite 7.2, Tailwind, Three.js, Recharts, Playwright

📄 **vite.config.mjs** — Vite bundler: dev proxy to :8005, PWA plugin, code splitting, base path `/haven-ui/`

📄 **tailwind.config.cjs** — Tailwind CSS configuration

📄 **postcss.config.cjs** — PostCSS + Autoprefixer

📄 **index.html** — SPA entry point with PWA manifest, og:meta for Discord embeds, service worker registration

📄 **CLAUDE.md** — Haven-UI specific docs: 25 pages, 38 components, API endpoints, auth system, theming

📄 **.env.example** — Environment template (HAVEN_ADMIN_PASSWORD, HAVEN_API_KEY, HAVEN_UI_DIR)

📄 **requirements.txt** — Python deps: FastAPI, Uvicorn, Pillow, Plotly, NumPy, pytest

📄 **Dockerfile** — Multi-stage build: Node build → Python slim runtime, health check on :8005

📄 **docker-compose.yml** — Container orchestration with volume mounts for data/photos persistence

📄 **server.py** — App launcher: imports FastAPI app from backend, runs uvicorn on :8005

📄 **run_server.bat** — Windows batch launcher

📄 **run_server.ps1** — PowerShell launcher with PID tracking and log capture

📄 **start_haven_ui.bat** — ASCII art banner startup script

📄 **start_server.bat** — Alternative batch entry point

📄 **stop_server.ps1** — PowerShell server shutdown

📄 **quick_health_check.bat** — Standalone endpoint health probe

📄 **playwright.config.ts** — E2E test runner config (Chromium, baseURL :5173)

📄 **run_server.pid** — Process ID file written by run_server.ps1

---

### Haven-UI/backend/ — Python FastAPI Backend

📁 **data/** — Bundled reference data
   📄 **galaxies.json** — All 256 NMS galaxy names (0-indexed), bundled for Pi deployment

📄 **control_room_api.py** — Main FastAPI application (~19,000 lines, 238 endpoints)

   **Imports & Globals**
   ├── `DISCOVERY_EMOJI_TO_SLUG` / `DISCOVERY_SLUG_TO_EMOJI` — 12 discovery type mappings
   ├── `DISCOVERY_TYPE_INFO` — Label, emoji, color per discovery type
   ├── `DISCOVERY_TYPE_FIELDS` — 2-3 metadata fields per discovery type
   ├── `GALAXIES_DATA` / `GALAXY_NAMES` / `GALAXY_BY_INDEX` — All 256 galaxies from galaxies.json
   ├── `SUPER_ADMIN_USERNAME` — Hardcoded "Haven"
   └── `PHOTOS_DIR` / `LOGS_DIR` / `HAVEN_UI_DIR` — Path constants

   **Utility Functions**
   ├── `normalize_discord_username()` — Remove #discriminator, lowercase
   ├── `find_matching_system()` — Fuzzy glyph match (last-11-chars + galaxy + reality)
   ├── `get_db_connection()` — SQLite with WAL mode, 30s timeout
   ├── `init_database()` — Schema initialization with integrity checks
   ├── `add_activity_log()` — Audit logging
   ├── `calculate_completeness_score()` — 7-category weighted scoring (0-100)
   ├── `update_completeness_score()` — Calculate and cache grade in DB
   └── `_build_advanced_filter_clauses()` — Shared SQL filter builder (12+ fields)

   **Authentication & Sessions**
   ├── `POST /api/admin/login` — Session creation (super admin, partner, sub-admin, correspondent)
   ├── `POST /api/admin/logout` — Session destroy
   ├── `GET /api/admin/status` — Session check + user info
   ├── `POST /api/change_password` — Password update
   ├── `POST /api/change_username` — Username update
   ├── `get_session()` — Returns session dict from token
   ├── `is_super_admin()` — Role check
   └── `verify_session()` — Token validation

   **Data Restriction Helpers**
   ├── `get_restriction_for_system()` — Per-system restriction lookup
   ├── `can_bypass_restriction()` — Permission check
   ├── `apply_field_restrictions()` — Field masking
   └── `apply_data_restrictions()` — System filtering + field hiding

   **Systems API**
   ├── `GET /api/systems` — List with 12+ advanced filters
   ├── `GET /api/systems/{id}` — Detail with planets, moons, completeness breakdown
   ├── `GET /api/systems/search` — Keyword search with filters
   ├── `GET /api/systems/recent` — Latest 10
   ├── `GET /api/systems/filter-options` — Distinct filterable values
   ├── `POST /api/save_system` — Partner direct save
   ├── `POST /api/systems/stub` — Create minimal placeholder
   ├── `DELETE /api/systems/{id}` — Delete system cascade
   └── `GET /api/systems_by_region` — Systems in a region

   **Galaxies & Regions**
   ├── `GET /api/galaxies` — Galaxy list
   ├── `GET /api/galaxies/summary` — Stats per galaxy with grade distribution
   ├── `GET /api/realities/summary` — Normal/Permadeath breakdown
   ├── `GET /api/regions` — Region list
   ├── `GET /api/regions/grouped` — Regions with aggregated data
   ├── `GET /api/regions/{rx}/{ry}/{rz}` — Region detail
   ├── `PUT /api/regions/{rx}/{ry}/{rz}` — Update region name (admin)
   └── Region name approval workflow (submit, pending, approve, reject)

   **Discoveries**
   ├── `GET /api/discoveries` — Browse with filters
   ├── `GET /api/discoveries/browse` — Advanced browse with planet/moon joins
   ├── `GET /api/discoveries/types` — Type list with metadata
   ├── `GET /api/discoveries/stats` — Type breakdown counts
   ├── `GET /api/discoveries/recent` — Latest 8
   ├── `GET /api/discoveries/{id}` — Detail with type_metadata
   ├── `POST /api/discoveries` — Direct creation
   ├── `POST /api/discoveries/{id}/feature` — Toggle featured
   ├── `POST /api/discoveries/{id}/view` — Increment view count
   └── `POST /api/submit_discovery` — Public submission to queue

   **Pending Discovery Approval**
   ├── `GET /api/pending_discoveries` — Scoped by discord_tag
   ├── `GET /api/pending_discoveries/{id}` — Detail
   ├── `POST /api/approve_discovery/{id}` — Approve (self-approval prevention)
   └── `POST /api/reject_discovery/{id}` — Reject with reason

   **System Approval Workflow**
   ├── `POST /api/submit_system` — Public submission
   ├── `GET /api/pending_systems` — Scoped queue
   ├── `GET /api/pending_systems/count` — Count badge
   ├── `GET /api/pending_systems/{id}` — Detail
   ├── `PUT /api/pending_systems/{id}` — Super admin edit
   ├── `POST /api/approve_system/{id}` — Approve (self-approval prevention)
   ├── `POST /api/reject_system/{id}` — Reject
   ├── `POST /api/approve_systems/batch` — Batch approve
   └── `POST /api/reject_systems/batch` — Batch reject

   **Partner Management**
   ├── `GET /api/partners` — Super admin list
   ├── `POST /api/partners` — Create partner
   ├── `PUT /api/partners/{id}` — Update
   ├── `DELETE /api/partners/{id}` — Deactivate
   └── Password reset, activate

   **Sub-Admin Management**
   ├── `GET /api/sub_admins` — Scoped list
   ├── `POST /api/sub_admins` — Create with delegated features
   ├── `PUT /api/sub_admins/{id}` — Update
   └── `DELETE /api/sub_admins/{id}` — Delete

   **Analytics**
   ├── `GET /api/analytics/submission-leaderboard` — Top contributors (filterable by source)
   ├── `GET /api/analytics/submissions-timeline` — Chart data
   ├── `GET /api/analytics/community-stats` — Per-community breakdown
   ├── `GET /api/analytics/source-breakdown` — Manual vs Extractor totals
   ├── `GET /api/analytics/extractor-summary` — Extractor-specific stats
   ├── `GET /api/analytics/discovery-leaderboard` — Top discoverers
   ├── `GET /api/analytics/discovery-timeline` — Discovery chart
   ├── `GET /api/analytics/discovery-type-breakdown` — Counts by type
   └── `GET /api/analytics/partner-overview` — Combined partner dashboard

   **Public Community Stats (no auth)**
   ├── `GET /api/public/community-overview` — Per-community stats with totals
   ├── `GET /api/public/contributors` — Ranked contributor list
   ├── `GET /api/public/activity-timeline` — Systems + discoveries over time
   ├── `GET /api/public/discovery-breakdown` — Discovery counts by type
   └── `GET /api/public/community-regions` — Regions + system lists

   **Extractor Integration**
   ├── `POST /api/extraction` — Receive extractor system data
   ├── `POST /api/check_glyph_codes` — Batch glyph validation
   ├── `POST /api/extractor/register` — Self-service per-user API key
   ├── `GET /api/extractor/users` — Admin user list
   ├── `PUT /api/extractor/users/{id}` — Edit rate limit/suspend
   └── `GET /api/communities` — Public community list for extractor dropdown

   **Events & Competitions**
   ├── `GET /api/events` — Event list with discovery counting
   ├── `POST /api/events` — Create (supports submissions/discoveries/both types)
   ├── `PUT /api/events/{id}` — Update
   ├── `DELETE /api/events/{id}` — Delete
   └── `GET /api/events/{id}/leaderboard` — Tabbed leaderboard

   **Partner Customization**
   ├── `GET/PUT /api/partner/theme` — Partner theme settings
   ├── `GET/PUT /api/partner/region_color` — 3D map region colors
   ├── `GET /api/discord_tag_colors` — Per-community color map
   └── `GET /api/discord_tags` — Community list from partner_accounts

   **Data Restrictions**
   ├── `GET /api/data_restrictions` — List restrictions
   ├── `POST /api/data_restrictions` — Create
   ├── `POST /api/data_restrictions/bulk` — Bulk create
   └── `DELETE /api/data_restrictions/{id}` — Remove

   **API Key Management**
   ├── `GET /api/keys` — List keys
   ├── `POST /api/keys` — Create key
   ├── `PUT /api/keys/{id}` — Update
   └── `DELETE /api/keys/{id}` — Revoke

   **Glyphs**
   ├── `POST /api/decode_glyph` — Glyph → coordinates
   ├── `POST /api/encode_glyph` — Coordinates → glyph
   ├── `POST /api/validate_glyph` — Format check
   └── `GET /api/glyph_images` — Base64 PNG glyph symbols

   **Photos & Media**
   ├── `POST /api/photos` — Upload with auto WebP compression + thumbnail
   └── `POST /api/warroom/media/upload` — War room media upload

   **Admin & Settings**
   ├── `GET /api/settings` — Global settings
   ├── `POST /api/settings` — Update settings
   ├── `GET /api/db_stats` — Database statistics
   ├── `POST /api/backup` — Create DB backup
   ├── `POST /api/db_upload` — Upload/restore DB
   ├── `POST /api/import_csv` — CSV import
   ├── `GET /api/approval_audit` — Paginated audit trail
   └── `GET /api/approval_audit/export` — CSV export

   **Pending Edits**
   ├── `GET /api/pending_edits` — List pending edit requests
   └── Approve/reject pending edits

   **WebSocket**
   └── `WS /ws/logs` — Real-time log streaming

   **War Room (~80 endpoints)**
   ├── Enrollment (5) — Join/leave, status, home region
   ├── Territory (4) — Claims, search, regions, ownership
   ├── Conflicts (15) — CRUD, multi-party, events, resolution
   ├── Peace Treaties (5) — Propose, accept, reject, negotiation status
   ├── News (5) — CRUD, ticker
   ├── Correspondents (3) — Register, login
   ├── Reporting Organizations (6) — CRUD, members
   ├── Statistics (3) — Leaderboard, recalculate
   ├── Notifications (3) — List, count, read-all
   ├── Webhooks (3) — CRUD for Discord webhooks
   ├── Map & Activity (3) — Map data, activity feed
   └── Media (4) — Upload, list, delete

   **SPA Catch-all Routes (~30)**
   └── Serves index.html for all React client-side routes

📄 **migrations.py** — Database schema migrations (3,661 lines, v1.0.0 → v1.47.0)
   ├── `@register_migration()` — Decorator pattern for versioned migrations
   ├── `run_pending_migrations()` — Auto-executes on server startup
   ├── `backup_database()` — Creates timestamped backup before migrations
   ├── 47 registered migrations covering: initial schema, glyph system, approvals, partners, sub-admins, events, war room (v1-v3), completeness scoring, discovery linking, per-user API keys, galaxy name fixes
   └── Key tables: systems, planets, moons, space_stations, regions, discoveries, planet_pois, pending_systems, pending_discoveries, partner_accounts, sub_admin_accounts, api_keys, data_restrictions, events, 18 war_room_* tables, schema_migrations

📄 **glyph_decoder.py** — Portal glyph encoding/decoding (723 lines)
   ├── `decode_glyph_to_coords()` — 12-char glyph → (x, y, z, system_index, planet)
   ├── `encode_coords_to_glyph()` — Coordinates → glyph (two's complement)
   ├── `validate_glyph_code()` — Format and range validation
   ├── `calculate_star_position_in_region()` — Deterministic star positioning
   ├── `is_in_core_void()` — Galactic center detection (8-unit radius)
   ├── `is_phantom_star()` — Inaccessible star detection (sys_index ≥ 0x258)
   ├── `calculate_region_name()` — Hex coordinate region name
   └── `GLYPH_IMAGES` — Base64 encoded glyph PNG images

📄 **image_processor.py** — WebP image compression and thumbnails (96 lines)
   └── `process_image()` — Resize to max 1920px (quality 80), generate 300px thumbnail (quality 75), convert to WebP

📄 **planet_atlas_wrapper.py** — 3D planet visualization (878 lines)
   ├── `generate_planet_html()` — Complete HTML page with Plotly 3D sphere + POI management UI
   ├── `create_planet_figure()` — Plotly 3D sphere with per-category POI traces
   └── `POI_CATEGORIES` — 15 categories (Base, Waypoint, Portal, etc.)

📄 **paths.py** — Centralized path configuration (180 lines)
   ├── `HavenPaths` class — Auto-detect directory structure across environments
   │   ├── `_resolve_haven_ui_dir()` / `_resolve_haven_db()` / `_resolve_keeper_*()` — Path resolution
   │   └── `get_logs_dir()` — Component-specific log directories
   └── `haven_paths` — Global singleton instance

📄 **migrate_atlas_pois.py** — POI color normalization migration tool (214 lines)

📄 **migrate_photos_to_webp.py** — Batch photo format conversion to WebP (352 lines)

---

### Haven-UI/src/ — React Frontend Source

📄 **main.jsx** — React 18 DOM render, BrowserRouter (basename `/haven-ui`), ThemeProvider, InactivityProvider (1hr timeout)

📄 **App.jsx** — Router setup with route guards
   ├── `RequireAdmin` — Guard: any logged-in admin
   ├── `RequireSuperAdmin` — Guard: super admin only
   ├── `RequireFeature` — Guard: specific feature flag
   └── `RequireWarRoomAccess` — Guard: enrolled partners, super admin, correspondents

---

#### Haven-UI/src/pages/ — 23 Route Components

📄 **Dashboard.jsx** — Landing page with stats, recent systems, activity feed, pending counts

📄 **Systems.jsx** — System browser with containerized hierarchy: Reality → Galaxy → Region → SystemsList

📄 **SystemDetail.jsx** — Full system detail with planets, moons, photos, completeness grade breakdown

📄 **RegionDetail.jsx** — Region view with expandable system cards

📄 **Wizard.jsx** — Create/edit systems with planets, moons, photos, glyph picker

📄 **Discoveries.jsx** — Discovery showcase landing with type grid, recent items, search

📄 **DiscoveryType.jsx** — Type-filtered discovery view with sorting and pagination

📄 **PendingApprovals.jsx** — Admin approval queue with tabs (systems/regions/discoveries), batch mode, edit mode

📄 **Analytics.jsx** — Admin analytics with manual vs extractor tabs, date range filtering

📄 **PartnerAnalytics.jsx** — Partner-scoped analytics dashboard

📄 **Events.jsx** — Community event/challenge management with tabbed leaderboard

📄 **ApiKeys.jsx** — Super admin API key CRUD

📄 **PartnerManagement.jsx** — Super admin partner account CRUD

📄 **SubAdminManagement.jsx** — Partner/super admin sub-admin CRUD with delegated features

📄 **ApprovalAudit.jsx** — Super admin approval audit trail with filtering and CSV export

📄 **ExtractorUsers.jsx** — Admin extractor user management with stats and rate limits

📄 **CommunityStats.jsx** — Public community contribution overview with charts

📄 **CommunityDetail.jsx** — Public per-community detail page with members, regions

📄 **DBStats.jsx** — Public database statistics

📄 **Settings.jsx** — Admin theme, password, and username settings

📄 **CsvImport.jsx** — Admin CSV import with drag-drop

📄 **DataRestrictions.jsx** — Partner data visibility restrictions per system

📄 **WarRoom.jsx** — War Room territorial conflict system with Three.js 3D map

📄 **WarRoomAdmin.jsx** — War Room admin management

---

#### Haven-UI/src/components/ — 29 Core Components

**Core UI:**
📄 **Navbar.jsx** — Navigation with login modal, pending count badge, dropdown menus (desktop + mobile)
📄 **Modal.jsx** — Reusable modal dialog with close button
📄 **Card.jsx** — Generic card wrapper with theme colors
📄 **Button.jsx** — Button with primary/ghost/neutral variants
📄 **FormField.jsx** — Form field wrapper with label + hint
📄 **StatCard.jsx** — Stat display card with optional Sparkline trend

**Charts & Display:**
📄 **LeaderboardTable.jsx** — Sortable ranking table with expandable rows, rank colors
📄 **SubmissionChart.jsx** — Recharts AreaChart for timeline data
📄 **CommunityPieChart.jsx** — Recharts PieChart for per-community breakdown
📄 **DateRangePicker.jsx** — Date range picker with presets (Last 7/30 days, All time)
📄 **Sparkline.jsx** — Inline SVG sparkline chart
📄 **AnimatedCounter.jsx** — Animated number counter with easing

**Specialized:**
📄 **SearchableSelect.jsx** — Dark-themed searchable dropdown (react-select)
📄 **GlyphPicker.jsx** — Visual glyph picker + hex text input with validation/decoding
📄 **GlyphDisplay.jsx** — Read-only glyph code visual display
📄 **PlanetEditor.jsx** — Complex planet form with moons editor, photo upload, special features
📄 **MoonEditor.jsx** — Moon editing form with photo upload, adjective fields
📄 **AdvancedFilters.jsx** — Collapsible 12+ field filter panel for systems
   └── `EMPTY_FILTERS` — Default empty filter state
📄 **SystemsList.jsx** — Paginated system list with grade badges and tag colors
📄 **GalaxyGrid.jsx** — Galaxy browser with completeness grade distribution bars (256 galaxies hardcoded with type/description)
📄 **RegionBrowser.jsx** — Region list with edit modal for custom names
📄 **RealitySelector.jsx** — Normal vs Permadeath reality selector cards
📄 **DiscoverySubmitModal.jsx** — Discovery submission modal with system linking + type-specific fields
📄 **DiscordTagBadge.jsx** — Community tag badge with color from tagColors.js

**System:**
📄 **ThemeProvider.jsx** — CSS custom property theming from /api/settings
   └── `ThemeContext` — Theme context
📄 **AdminLoginModal.jsx** — Admin + correspondent login modal with type selector
📄 **InactivityOverlay.jsx** — 1-hour inactivity disconnect warning overlay
📄 **WarMap3D.jsx** — Three.js 3D war room map with tactical grid, territory visualization

#### Haven-UI/src/components/discoveries/ — 4 Discovery Components

📄 **index.js** — Barrel export for discovery suite
📄 **DiscoveryCard.jsx** — Discovery grid card with type gradient, thumbnail
📄 **DiscoveryDetailModal.jsx** — Full discovery detail modal with evidence gallery
📄 **DiscoveryFilters.jsx** — Search + sort controls for discovery pages
📄 **TypeCard.jsx** — Large discovery type card with emoji, gradient background

---

#### Haven-UI/src/utils/ — 8 Utility Files

📄 **AuthContext.jsx** — Session management and role-based access
   ├── `AuthContext` — React context (isAdmin, isSuperAdmin, isPartner, isSubAdmin, isCorrespondent, user)
   ├── `FEATURES` — Enum of 11 feature flags (API_KEYS, APPROVALS, SYSTEM_CREATE, etc.)
   ├── `AuthProvider` — Provider calling /api/admin/status on mount
   └── `canAccess(feature)` — Feature access check

📄 **api.js** — API client helpers
   ├── `adminStatus()` — GET /api/admin/status
   ├── `uploadPhoto(file)` — POST /api/photos multipart
   ├── `getPhotoUrl(photo)` — Full-size photo URL construction
   └── `getThumbnailUrl(photo)` — 300px WebP thumbnail URL (fallback for legacy formats)

📄 **InactivityContext.jsx** — Auto-disconnect on 1hr idle
   ├── `InactivityContext` — React context
   └── `InactivityProvider` — Provider with connection cleanup

📄 **adjectiveColors.js** — Tier-based color functions for planet data
   ├── `getFaunaColor(value)` — 5-tier color (yellow/blue/orange/gray/purple)
   ├── `getFloraColor(value)` — 5-tier color (green/blue/orange/gray/purple)
   └── `getSentinelColor(value)` — 5-tier color (red/yellow/green/purple/gray)

📄 **tagColors.js** — Community tag color mappings
   ├── `tagColors` — Tailwind classes for 7 known communities
   ├── `tagBgColors` — Background-only Tailwind classes
   ├── `tagColorStyles` — RGBA style objects
   ├── `getTagColor(tag)` — Tailwind class with hash-based fallback
   └── `getTagColorStyle(tag)` — RGBA style with default fallback

📄 **usePersonalColor.js** — Personal color preference hook
   ├── `usePersonalColor()` — Fetches /api/settings, returns { personalColor, loading }
   └── `clearPersonalColorCache()` — Cache invalidation

📄 **economyTradeGoods.js** — Space station economy trade goods data
   ├── `getTradeGoodsForEconomy(type)` — All goods for an economy type
   ├── `getTradeGoodsForEconomyAndTier(type, tier)` — Filtered by wealth level
   └── `getTradeGoodById(id)` — Find specific trade good

📄 **stationPlacement.js** — Space station orbital positioning
   └── `generateStationPosition(planets, existingStations, options)` — Safe orbital position calculation

---

#### Haven-UI/src/data/ — 4 Static Data Files

📄 **galaxies.js** — All 256 NMS galaxies (1-indexed array) + REALITIES (Normal, Permadeath)
   ├── `GALAXIES` — Array of { index, name }
   └── `REALITIES` — Array of reality types

📄 **discoveryTypes.js** — Discovery type metadata (single source of truth)
   └── `TYPE_INFO` — Object: 12 types (fauna, flora, mineral, ancient, history, bones, alien, starship, multitool, lore, base, other) with emoji, label, color, description

📄 **adjectives.js** — NMS game adjective lists
   ├── `biomeAdjectives` — 200+ biome names
   ├── `weatherAdjectives` — Weather descriptors
   ├── `sentinelAdjectives` — Sentinel difficulty levels
   ├── `floraAdjectives` / `faunaAdjectives` — Life richness levels
   ├── `resourcesList` — Harvestable resources
   ├── `exoticTrophyList` — Exotic biome collectibles
   └── `toSelectOptions(array)` — Convert to react-select format

📄 **biomeCategoryMappings.js** — Biome aggregation and colors
   ├── `BIOME_CATEGORIES` — 17 parent categories (Lush, Toxic, Exotic, Marsh, etc.)
   ├── `BIOME_ADJECTIVE_MAP` — Maps 200+ adjectives to parent category
   ├── `aggregateBiomesByCategory(biomes)` — Group with counts
   └── `getBiomeCategoryColor(category)` — Tailwind color per category

---

#### Haven-UI/src/hooks/ — 1 Custom Hook

📄 **useInactivityAware.js** — Hook for components with real-time features
   └── `useInactivityAware()` — Returns { isDisconnected, registerConnection, unregisterConnection }

#### Haven-UI/src/styles/ — 1 CSS File

📄 **index.css** — Tailwind setup + custom CSS variables + utility classes (147 lines)

---

### Haven-UI/scripts/ — Deployment & Maintenance Scripts

📄 **deploy_to_pi.ps1** — *(active)* Interactive Pi deployment: create archive, SSH upload, extract

📄 **migrate.py** — *(active)* Schema migration CLI: status, run, history, backup commands

📄 **smoke_test.py** — *(active)* Basic endpoint health check (4 routes, 4s timeout)

📄 **create_update_archive.ps1** — *(active)* Creates tar.gz update archive for Pi deployment

📁 **archive/** — Archived scripts (broken imports, may fix later)
   📄 **preview.py** — Legacy Python preview script
   📄 **preview.ps1** — Legacy PowerShell preview script

---

### Haven-UI/data/ — Runtime Data

📄 **haven_ui.db** — SQLite production database (12MB, 37 tables)

📄 **haven_ui.db.backup** — Old DB backup snapshot (128KB)

📄 **.gitkeep** — Ensures folder tracked in git

📁 **archive/**
   📄 **data.json.bak** — Legacy pre-database system records (17MB, 6,542 systems, archived 2026-03-08)
   📄 **README.md** — Note: safe to delete after confirming production is stable

📁 **backups/**
   📄 **haven_ui_pre_webp_migration_20260307_231119.db** — Pre-WebP migration backup (12MB)

---

### Haven-UI/photos/ — User-Uploaded Discovery Photos

WebP compressed photos with thumbnails (~42MB total). Naming: `{id}.webp` + `{id}_thumb.webp`

### Haven-UI/public/ — Static Assets

📄 **favicon.svg** / **icon.svg** — Browser and PWA icons
📄 **VH-Map-Region.html** — 3D region map (Three.js, 59KB)
📄 **VH-Map-ThreeJS.html** — 3D system map (137KB)
📄 **VH-System-View.html** — System detail view (76KB)
📁 **assets/** — haven-preview.png (social preview)
📁 **war-media/** — War Room user uploads (WebP)

### Haven-UI/dist/ — Built Production Output (generated, not committed)

### Haven-UI/node_modules/ — Node.js Dependencies (generated)

---

### Haven-UI/tests/ — Test Suite

📁 **api/**
   📄 **test_endpoints.py** — Quick health check: /api/status, /api/systems, /haven-ui routes
   📄 **test_approvals_system.py** — Pending_systems table structure verification
   📄 **test_api_calls.py** — Basic endpoint probes
   📄 **test_post_discovery.py** — POST /api/submit_discovery workflow

📁 **data/**
   📄 **generate_test_data.py** — Creates 30 test systems with valid glyphs
   📄 **populate_test_data.py** — Bulk test data loading
   📄 **quick_test_systems.py** — Fast system creation
   📄 **test_station_placement.py** — Space station positioning validation

📁 **e2e/**
   📄 **wizard-enter.spec.ts** — Playwright: system create wizard UI flow
   📄 **wizard-glyph.spec.ts** — Playwright: glyph input validation

📁 **integration/**
   📄 **test_integration.py** — Full API + DB workflow
   📄 **test_keeper_integration.py** — Discord Keeper bot integration
   📄 **keeper_test_bot_startup.py** — Bot startup validation
   📄 **test_keeper_http_integration.py** — HTTP API for Keeper

---

### Haven-UI/raspberry/ — Raspberry Pi Deployment

📄 **README.md** — Pi deployment guide: venv setup, systemd installation

📄 **haven-control-room.service** — Systemd unit: runs as user `pi`, uvicorn on :8000

### Haven-UI/docs/ — Documentation

📄 **GOOGLE_FORMS_SUBMISSION_GUIDE.md** — External submission form integration
📄 **HOMELAB_MIGRATION.md** — Single-machine to homelab setup migration
📄 **PARTNER_GUIDE.md** — Community partner onboarding
📄 **RASPBERRY_PI_PRODUCTION_SETUP.md** — Pi deployment with SSL, Nginx, Docker

---

## NMS-Haven-Extractor/ — In-Game Data Extraction Mod

PyMHF-based mod that hooks into No Man's Sky to extract system, planet, and resource data in real-time.

### Root Files

📄 **pyproject.toml** — Python project metadata (v1.6.7, requires Python 3.11-3.13)
📄 **build_distributable.py** — Package builder for full distributable (~112MB)
📄 **haven_config.json.example** — Config template (api_url, api_key)

📁 **archive/** — Previous mod-only zip versions
   📄 **HavenExtractor-mod-v1.6.0.zip** through **v1.6.6.zip** — 7 archived versions (~50-60KB each)

📁 **docs/**
   📄 **CLAUDE.md** — Extractor architecture reference (17KB)
   📄 **README.md** — User-facing quickstart
   📄 **OFFSET_TOOLS_README.txt** — Binary analysis tool documentation

📁 **logs/** — Extraction log output

📁 **old_versions/** — Legacy mod versions

📁 **utility_scripts/** — Helper tools

---

### NMS-Haven-Extractor/dist/HavenExtractor/ — Production Distributable

📁 **python/** — Embedded Python 3.11 runtime + site-packages

📄 **FIRST_TIME_SETUP.bat** — 7-step verification: Python, mod files, nmspy, pymhf, hgpaktool, output directory

📄 **UPDATE_HAVEN_EXTRACTOR.bat** — Launches haven_updater.ps1

📄 **haven_updater.ps1** — Auto-updater: checks GitHub Releases, downloads mod-only zip, backs up, preserves config

#### NMS-Haven-Extractor/dist/HavenExtractor/mod/ — Mod Source Files

📄 **haven_extractor.py** — Main extractor mod (~4,057 lines, v1.6.7)

   **Constants & Mappings**
   ├── `GALAXY_NAMES` — All 256 NMS galaxies (0-indexed)
   ├── `STAR_TYPES` — {0:Yellow, 1:Green, 2:Blue, 3:Red, 4:Purple}
   ├── `BIOME_TYPES` — 17 types (Lush through All)
   ├── `BIOME_SUBTYPES` — 32 subtypes
   ├── `PLANET_SIZES` — {0:Large, 1:Medium, 2:Small, 3:Moon, 4:Giant}
   ├── `TRADING_CLASSES` — 7 economy types
   ├── `WEALTH_CLASSES` — {0:Poor, 1:Average, 2:Wealthy, 3:Pirate}
   ├── `CONFLICT_LEVELS` — {0:Low, 1:Default, 2:High, 3:Pirate}
   ├── `ALIEN_RACES` — {0:Gek, 1:Vy'keen, 2:Korvax, 3-6:None}
   ├── `RESOURCE_NAMES` — 80+ resource ID → name mappings
   ├── `FLORA_LEVELS` / `FAUNA_LEVELS` / `SENTINEL_LEVELS` — Integer enum fallbacks
   └── `_DEFAULT_COMMUNITY_TAGS` — 25 hardcoded fallback communities

   **Memory Offset Classes**
   ├── `SolarSystemDataOffsets` — System struct offsets (STAR_TYPE at 0x2270, etc.)
   ├── `TradingDataOffsets` / `ConflictDataOffsets` — Nested economy/conflict offsets
   └── `PlanetGenInputOffsets` — Planet gen struct (83 bytes per entry)

   **HavenExtractorMod Class**

   *Initialization:*
   ├── `__init__()` — Setup hooks, GUI, config
   ├── `_save_config_to_file()` — Persist to JSON
   └── `_register_api_key()` — Per-user key self-registration

   *Game Hooks:*
   ├── `on_translate()` — Capture text ID → display string pairs for adjective cache
   ├── `on_system_generate()` — Triggered on entering new solar system
   ├── `on_creature_roles_generate()` — Extract planet data, resolve adjectives immediately
   └── `on_appview()` — Player entered game view, auto-refresh adjectives

   *GUI Buttons (5):*
   ├── `apply_manual_system_name()` — Set custom system name
   ├── `check_system_data()` — Display current extraction
   ├── `check_batch_data()` — Show batch status
   ├── `show_config_status()` — Display config
   └── `export_to_haven_ui()` — Main export flow

   *Extraction Core:*
   ├── `_do_extraction()` — Core extraction logic on system load
   ├── `_extract_system_properties()` — Star type, economy, conflict, lifeform
   ├── `_extract_planets()` — Extract all planets in system
   ├── `_extract_single_planet()` — Biome, weather, resources, life, special features
   └── `_get_current_coordinates()` — Read system position from memory

   *Adjective Resolution (2-layer):*
   ├── `_load_adjective_cache()` — Load PAK/MBIN mappings from disk
   ├── `_resolve_adjective()` — PAK cache → Translate hook → raw text ID
   └── `_auto_refresh_for_export()` — Re-resolve from populated hook cache

   *Memory Operations:*
   ├── `_read_int32()` / `_read_uint32()` / `_read_string()` / `_read_uint64()` / `_read_bytes()`
   ├── `_read_system_data_direct()` — Read solar system struct
   └── `_read_planet_gen_input_direct()` — Read planet generation struct

   *Glyph Encoding:*
   ├── `_coords_to_glyphs()` — Bitwise masking (x & 0xFFF)
   └── `_coords_to_portal_code()` — Full portal code generation

   *API Communication:*
   ├── `_check_duplicates()` — Pre-flight via POST /api/check_glyph_codes
   ├── `_send_single_system_to_api()` — POST /api/extraction
   ├── `_upload_systems_to_api_log()` — Bulk submit
   └── `_run_export_flow()` — Complete export workflow

   *Data Output:*
   ├── `_write_extraction()` — Save to ~/Documents/Haven-Extractor/latest.json
   └── `_save_current_system_to_batch()` — Add to batch collection

📄 **nms_language.py** — Language data parser for adjective cache (~429 lines)
   ├── `LanguageMBINParser` — Parse language MBIN files for text ID → English mappings
   ├── `AdjectiveCacheBuilder` — Orchestrate PAK extraction, caching, invalidation
   └── `find_nms_install_path()` — Auto-detect NMS installation via Steam library

📄 **structs.py** — Data structure definitions and enums
   ├── 7 enums: StarType, ConflictLevel, EconomyStrength, DominantLifeform, BiomeType, SentinelLevel, FloraFaunaLevel
   ├── `ExtractedPlanetData` — Dataclass for planet extraction results
   ├── `ExtractedSystemData` — Dataclass for system extraction results
   ├── `coordinates_to_glyphs()` / `glyphs_to_coordinates()` — Coordinate conversion
   └── Partial `GALAXY_NAMES` dict (10 entries, fallback)

📄 **pymhf.toml** — PyMHF mod config (NMS.exe, Steam game ID 275850)

📄 **haven_config.json.example** — Config template

📄 **__init__.py** — Package marker

---

## NMS-Debug-Enabler/ — Debug Flag Enabler Mod

PyMHF mod that unlocks 260+ debug flags in the NMS release build.

📄 **README.md** — Usage guide

📁 **mod/**
   📄 **nms_debug_enabler.py** — Main mod (623 lines, v1.0.0)
      ├── `NMSDebugEnabler(Mod)` — Main class
      ├── `_on_boot()` — Auto-enable debug controls on game load
      ├── 7 presets: `preset_god_mode()`, `preset_explorer()`, `preset_builder()`, `preset_performance()`, `preset_modder()`, `preset_world_override()`, `preset_safe_online()`
      ├── 30+ individual toggles: god mode, no damage, infinite stamina, free warp, FPS, position, etc.
      └── `reset_all()` — Restore all flags to vanilla defaults

📁 **analysis/scripts/** — Binary analysis tools (not main code)
   📄 **assemble.py** / **bootstrap.py** / **pdb_parser.py** / **test2.py**

---

## NMS-Memory-Browser/ — Live Memory Inspection Tool

PyQt6 desktop application for real-time NMS game memory inspection.

📄 **CLAUDE.md** — Architecture reference (v3.8.5)
📄 **requirements.txt** — PyQt6, ctypes dependencies
📄 **launch_memory_browser.bat** — Windows launcher

📁 **nms_memory_browser/** — 27 Python modules
   📄 **main.py** — PyQt6 main window entry point
   📄 **config.py** — Configuration (106 lines)

   📁 **core/** — Memory reading layer
      📄 **memory_reader.py** — ctypes-based NMS.exe access (595 lines, safety bounds)
      📄 **struct_registry.py** — NMS.py struct enumeration (325 lines)
      📄 **struct_mapper.py** — Memory-to-struct mapping
      📄 **pointer_scanner.py** — Root pointer discovery
      📄 **type_inference.py** — Unknown memory type detection

   📁 **collectors/** — Data extraction
      📄 **player_collector.py** — Player state (637 lines)
      📄 **system_collector.py** — Solar system data
      📄 **multiplayer_collector.py** — Bases, settlements
      📄 **unknown_collector.py** — Unknown region analysis

   📁 **ui/** — GUI components
      📄 **main_window.py** — Main window
      📄 **tree_browser.py** — Hierarchical tree widget
      📄 **detail_panel.py** — Formatted view + hex dump tabs
      📄 **hex_viewer.py** — Enhanced hex viewer

   📁 **data/** — Data models
      📄 **tree_node.py** / **snapshot.py**

   📁 **export/** — JSON export
      📄 **json_exporter.py** / **schema.py**

---

## NMS-Save-Watcher/ — Extraction Queue Manager

Monitors Haven Extractor JSON outputs and queues submissions to Haven API.

📄 **CLAUDE.md** — Architecture reference (v2.1.0)
📄 **requirements.txt** — FastAPI, aiofiles
📄 **config.json** — User configuration (Haven URL, API key)

📁 **src/** — 13 Python modules
   📄 **main.py** — Entry point (177 lines)
   📄 **watcher.py** — LiveExtractionWatcher (479 lines)
   📄 **extraction_watcher.py** — File monitoring with learning mode (1,475 lines)
   📄 **api_client.py** — Haven API client (425 lines)
   📄 **database.py** — SQLite queue management (791 lines)
   📄 **config.py** — Configuration (233 lines)
   📄 **parser.py** — Legacy save parsing (369 lines)
   📄 **extractor.py** — Data extraction (886 lines)
   📄 **dashboard.py** — FastAPI web dashboard
   📄 **notifications.py** — Windows toast notifications (209 lines)

📁 **data/** — Reference data
   📄 **mapping.json** — Key deobfuscation
   📄 **resources.json** — Resource ID mappings
   📄 **galaxies.json** — 256 galaxy names
   📄 **levels.json** — Level mappings

📁 **web/** / **templates/** / **static/** — Dashboard frontend

---

## keeper-discord-bot-main/ — Community Discord Bot

Discord bot for discovery submissions, pattern recognition, and community engagement.

📄 **CLAUDE.md** — Architecture reference (v1.0.0)
📄 **requirements.txt** — discord.py, FastAPI
📄 **.env** — Discord token, Haven API configuration

📁 **src/** — 23 Python modules
   📄 **main.py** — Bot entry point
   📄 **config.json** — Themes and discovery types

   📁 **core/**
      📄 **keeper_personality.py** — Mysterious persona, embeds
      📄 **haven_integration_unified.py** — HTTP/DB/JSON Haven access
      📄 **channel_config.py** — Channel configuration

   📁 **database/**
      📄 **keeper_db.py** — SQLite handler
      📄 **sync_queue.py** — Sync queue manager

   📁 **api/**
      📄 **sync_api.py** — HTTP API server (port 8080)

   📁 **sync/**
      📄 **sync_worker.py** — Background sync task

   📁 **cogs/** — Feature modules
      📄 **enhanced_discovery.py** — Haven-integrated discovery system
      📄 **pattern_recognition.py** — Pattern detection and analysis
      📄 **archive_system.py** — Archive tools
      📄 **admin_tools.py** — Admin commands
      📄 **community_features.py** — Tiers, challenges, leaderboards
      📄 **discovery_modals.py** — Type-specific forms

📁 **data/** — keeper.db (bot database)
📁 **scripts/** / **tests/** / **logs/** — Supporting folders

---

## Planet_Atlas/ — 3D Planetary Cartography (Git Submodule)

Interactive 3D planetary mapping for POI visualization. Maintained in a separate repository, included as a git submodule.

📄 **main.py** — Dash + Plotly app (1,793 lines, v1.25.1, port 8050)
📄 **atlas_data.csv** — Local CSV database (SYSTEM/PLANET/POINT records)
📄 **requirements.txt** — dash, plotly, pandas
📄 **CLAUDE.md** — Architecture reference

📁 **assets/**
   📄 **carto.webp** — Logo
   📁 **glyphs/** — 16 portal symbol WebP images (PORTALSYMBOL.0.webp through .F.webp)

---

## Travelers-Collective/ — Community Data Sync Hub (In Development)

PostgreSQL-backed microservice for cross-community NMS data aggregation.

📄 **docker-compose.yml** — PostgreSQL 17 + Collective API
📄 **Dockerfile** — Container build
📄 **requirements.txt** — FastAPI, asyncpg, SQLAlchemy, Pydantic, APScheduler

📁 **src/collective/** — 27 Python modules
   📄 **main.py** — FastAPI app factory with lifecycle management
   📄 **config.py** — Pydantic BaseSettings (PostgreSQL, JWT, Steam API)

   📁 **auth/** — JWT + API key authentication
      📄 **jwt.py** / **api_key.py** / **dependencies.py** / **middleware.py** (rate limiting)

   📁 **db/** — Database layer
      📄 **engine.py** — AsyncPG connection pool
      📄 **seed.py** — Initial data seeding

   📁 **models/** — Pydantic schemas
      📄 **auth.py** / **common.py** / **communities.py** / **releases.py**

   📁 **routes/** — API endpoints
      📄 **admin.py** / **bot.py** / **public.py**

   📁 **services/**
      📄 **haven_sync.py** — Haven integration service

   📁 **tasks/** — Background jobs
      📄 **steam_watcher.py** — Monitors NMS updates on Steam (30-min intervals)
      📄 **worker.py** — Procrastinate job queue

   📁 **utils/**
      📄 **glyph_decoder.py** — Glyph encoding/decoding

📁 **alembic/** — Database migrations (SQLAlchemy + Alembic)

---

## How It All Connects

### Data Flow: Game → Database → User

```
NMS Game (running)
    │
    ├──[Hook]── NMS-Haven-Extractor (PyMHF mod)
    │           Hooks into game memory, reads system/planet data
    │           Resolves adjectives from PAK files + Translate hook
    │           Encodes portal glyphs from coordinates
    │               │
    │               ├──[JSON]── ~/Documents/Haven-Extractor/latest.json
    │               │               │
    │               │               └── NMS-Save-Watcher (optional queue manager)
    │               │                   Monitors folder, queues, submits via API
    │               │
    │               └──[HTTP]── POST /api/extraction (direct submission)
    │                               │
    │                               ▼
    │                   Haven Backend (FastAPI, port 8005)
    │                   ├── Validates glyph codes, detects duplicates
    │                   ├── Stores in pending_systems table
    │                   ├── Increments per-user API key counters
    │                   └── Awaits admin approval
    │
    └──[Manual]── Haven-UI Wizard (React form)
                  User enters system data manually via web UI
                      │
                      └──[HTTP]── POST /api/submit_system
                                      │
                                      ▼
                          pending_systems table (SQLite)
                                      │
                              [Admin Review]
                          Partner/Sub-admin reviews in
                          PendingApprovals page
                                      │
                              POST /api/approve_system/{id}
                                      │
                                      ▼
                          systems + planets + moons tables
                          completeness_score calculated
                          approval_audit_log entry created
                                      │
                                      ▼
                          Haven-UI Frontend (React, port 5173/8005)
                          ├── Dashboard: stats, recent, activity
                          ├── Systems: browse by Reality→Galaxy→Region
                          ├── SystemDetail: planets, photos, grade
                          ├── Discoveries: showcase by type
                          ├── CommunityStats: public analytics
                          ├── Analytics: admin submission stats
                          └── WarRoom: territorial conflicts
```

### Component Ports & Communication

| Port | Service | Component | Direction |
|------|---------|-----------|-----------|
| 5173 | Vite dev server | Haven-UI frontend | → proxies to 8005 |
| 8005 | FastAPI + static | Haven-UI backend | ← all clients |
| 8006 | Dashboard | NMS-Save-Watcher | → calls 8005 |
| 8010 | Collective API | Travelers-Collective | ↔ Haven + external |
| 8050 | Dash app | Planet Atlas | standalone |
| 8080 | Sync API | Keeper Discord Bot | → calls 8005 |

### The Keeper Bot Connection

The Keeper Discord Bot provides a Discord-native interface for Haven. Users in Discord can submit discoveries via slash commands (`/discovery-report`), which the bot stores locally and syncs to Haven via HTTP API calls to port 8005. The bot also queries Haven for system information (`/system-info`, `/list-systems`). The sync layer ensures Discord submissions eventually reach the same pending queue that web submissions use.

### The Travelers-Collective Future

The Travelers-Collective is being developed as a central aggregation layer that will sit between multiple Haven-like instances and external communities. It uses PostgreSQL (vs Haven's SQLite) for scalability, includes a Steam update watcher to detect NMS patches, and will provide cross-community data sharing. Currently in v0.1.0 with basic auth, routing, and database scaffolding.

### Production Deployment

Haven runs on a Raspberry Pi 5 (8GB) at `https://havenmap.online`, behind Nginx Proxy Manager + Cloudflare DNS + Let's Encrypt SSL. The backend serves both the API and the built React frontend on port 8005. Haven runs in Docker Compose on the Pi, served by uvicorn inside the container on port 8005. The container is managed by Docker, not systemd. The SQLite database, photos, and logs persist outside the git repo via Docker volume mounts.
