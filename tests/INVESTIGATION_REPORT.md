# Haven Smoke + Verification Test Suite v1 — Phase 1 Investigation Report

**Worktree:** `C:\Master-Haven\.claude\worktrees\festive-ptolemy-7aa7c3`
**Branch:** `claude/festive-ptolemy-7aa7c3` (clean)
**Date:** 2026-04-29
**Phase:** 1 (read-only investigation; no source files modified)

This document is the foundation for Phase 2. Source code was treated as ground truth; markdown specs and prior dispatch assumptions were verified against the files.

---

## 1. Haven Backend Route Inventory

The backend is a FastAPI app in `Haven-UI/backend/control_room_api.py` that mounts thirteen `APIRouter` modules from `Haven-UI/backend/routes/` plus a number of legacy routes still on the main `app` object. **Total: 221 routes in routers + 47 routes on `app` = ~268 endpoints.**

### Router modules included on the app

`control_room_api.py:1611-1628`:
```python
app.include_router(auth_router)        # routes/auth.py
app.include_router(systems_router)     # routes/systems.py
app.include_router(analytics_router)   # routes/analytics.py
app.include_router(partners_router)    # routes/partners.py
app.include_router(approvals_router)   # routes/approvals.py
app.include_router(discoveries_router) # routes/discoveries.py
app.include_router(profiles_router)    # routes/profiles.py
app.include_router(events_router)      # routes/events.py
app.include_router(regions_router)     # routes/regions.py
app.include_router(extractor_router)   # routes/extractor.py
app.include_router(csv_import_router)  # routes/csv_import.py
app.include_router(warroom_router)     # routes/warroom.py
app.include_router(posters_router)     # routes/posters.py
app.include_router(ssr_router)         # routes/ssr.py
```

### Per-module route count (router routes only)

| Module | Routes | Notes |
|---|---:|---|
| `routes/analytics.py` | 18 | 10 `/api/analytics/*` (auth-scoped), 8 `/api/public/*` (no auth, includes `voyager-fingerprint` and `galaxy-atlas`) |
| `routes/approvals.py` | 11 | `/api/submit_system`, `/api/pending_systems`, `/api/approve_system/{id}`, `/api/reject_system/{id}`, batch endpoints, **`/api/extraction`** (extractor target), `/api/check_glyph_codes` |
| `routes/auth.py` | 8 | `/api/status` (public, returns version), `/api/admin/login`, `/api/admin/logout`, `/api/admin/status`, `/api/settings` GET/POST, `/api/change_password`, `/api/change_username` |
| `routes/csv_import.py` | 3 | `/api/photos` (upload), `/api/csv_preview`, `/api/import_csv` |
| `routes/discoveries.py` | 15 | Browse/recent/types/stats, submit, approve/reject; also legacy `POST /discoveries` alias for the Keeper bot |
| `routes/events.py` | 6 | CRUD + `/api/events/{id}/leaderboard` |
| `routes/extractor.py` | 8 | API key CRUD, `/api/extractor/register` (public — anonymous self-service), `/api/communities` (public), reissue-key (super admin) |
| `routes/partners.py` | 30 | Partner/sub-admin CRUD, `/api/approval_audit`, `/api/pending_edits/*`, partner theme/region color, `/api/data_restrictions/*` |
| `routes/posters.py` | 3 | `GET /api/posters/{poster_type}/{cache_key}.png`, `POST .../refresh`, `GET /api/posters/admin/queue` |
| `routes/profiles.py` | 13 | Lookup/create/use/login (public), `/api/profiles/me*` (member auth), `/api/admin/profiles/*` (admin) |
| `routes/regions.py` | 17 | Regions list/grouped/scoped, planet POIs, region-name submit + approve/reject, batch approve |
| `routes/ssr.py` | 5 | `/`, `/voyager/{username}`, `/atlas/{galaxy}`, `/systems/{id}`, `/community-stats/{tag}` (HTMLResponse — server-rendered OG cards) |
| `routes/systems.py` | 18 | Stats, `/api/galaxies/summary`, `/api/realities/summary`, glyph encode/decode/validate, `/api/systems`, `/api/systems/search`, `/api/check_duplicate`, `/api/namegen`, `/api/activity_logs` |
| `routes/warroom.py` | 67 | Largest module: enrollment, conflicts, news, correspondents, claims, statistics, notifications, webhooks, media, reporting orgs, peace proposals, territory queries |

### Legacy routes still on `@app` (control_room_api.py)

These bypass the router system. The interesting/testable ones:

| Route | Method | Auth | Purpose |
|---|---|---|---|
| `/api/discord_tags` | GET | public | Used by frontend to color-code submissions |
| `/api/reject_region_names/batch` | POST | admin | Region-name batch reject |
| `/api/systems/bulk` | POST | admin | Bulk system create |
| `/api/systems/{id}` | GET | public | System detail |
| `/api/systems/{id}` | DELETE | super admin | |
| `/api/systems/stub` | POST | session-scoped | Discovery-flow stub system |
| `/api/save_system` | POST | session-scoped | Direct admin/partner save (bypasses approval) |
| `/api/db_stats` | GET | public | Public DB stats page |
| `/api/partner/stats` | GET | partner | |
| `/api/tests` | GET | admin | (Existing in-app "tests" runner — see §2) |
| `/api/tests/run` | POST | admin | |
| `/api/logs` | GET | admin | |
| `/api/backup` | POST | super admin | DB shutil-copy backup |
| `/api/admin/health` | GET | any admin | Schema version, row counts, WAL/SHM size, memory |
| `/api/admin/maintenance/wal_checkpoint` | POST | super admin | |
| `/api/admin/maintenance/vacuum` | POST | super admin | |
| `/systems`, `/systems/search` | GET | public | Legacy aliases |
| `/map/*`, `/map/system/{id}`, `/map/planet/{id}` | GET | public | 3D map HTML |
| `/`, `/haven-ui/*`, `/war-room`, etc. | GET | public | SPA fallbacks |

### Auth model summary

- **Session cookie:** `session` cookie set by `/api/admin/login` (and `/api/profile/login`). Validated by `get_session()` / `is_super_admin()` / partner-scoped checks.
- **API-key auth (extractor/keeper bot):** `X-API-Key` header validated by `verify_api_key()`. Used by `/api/extraction` and the Keeper bot's submission endpoints.
- **Public endpoints:** Everything under `/api/public/*`, plus `/api/status`, `/api/db_stats`, `/api/discord_tags`, `/api/communities`, `/api/galaxies`, glyph encode/decode/validate, `/api/profiles/lookup`, `/api/profiles/create`, `/api/profile/login`, `/api/extractor/register`, system browse (`/api/systems`, `/api/systems/{id}`, `/api/systems/search`), region browse, discovery browse/recent/stats, `/api/events`, all SPA HTML routes, all `/api/posters/*` PNG endpoints (the SSR routes call them internally).

### Endpoints worth smoke-testing first (highest signal/cost ratio)

1. `GET /api/status` — returns `{status, version, api}`. **The cheapest liveness probe.** This is what `Haven-UI/docker-compose.yml` healthcheck hits.
2. `GET /api/db_stats` — exercises DB connectivity + the regions/galaxy/reality scoping logic.
3. `GET /api/systems?page=1&limit=10` — exercises the main `_build_advanced_filter_clauses()` query path.
4. `GET /api/public/voyager-fingerprint?username=...` — feeds `/fingerprint` poster.
5. `GET /api/public/galaxy-atlas?galaxy=Euclid` — feeds `/atlas` poster.
6. `GET /api/posters/voyager_og/{slug}.png` — Playwright + Chromium render path. **Likely the most flake-prone in the repo.**
7. `GET /api/posters/atlas/{galaxy}.png` — same.
8. `GET /` and `GET /voyager/{username}` — SSR HTML.
9. `GET /api/admin/health` (with admin session) — operational dashboard.
10. `GET /api/communities` — used by the extractor at startup.

---

## 2. Existing Tests

Everything found is shown below. Most of it is stale — written when the API was on port 8000 and routes like `/api/rtai/*` existed.

| File | Size | Fresh? | What it covers | Notes |
|---|---:|---|---|---|
| `Haven-UI/tests/api/test_endpoints.py` | 344 B | **STALE** | `requests.get(":8000/api/{status,stats,systems}")` etc | Wrong port (8000 vs 8005). Not pytest — bare `print()`. |
| `Haven-UI/tests/api/test_api_calls.py` | 314 B | **STALE** | `:8000/api/rtai/status`, `:8000/api/rtai/analyze/discoveries`, `:8080/health` (Keeper Sync — defunct service) | All three endpoints removed. |
| `Haven-UI/tests/api/test_post_discovery.py` | 363 B | **STALE** | POST `:8000/discoveries` and `:8000/api/discoveries` | Wrong port. Predates discovery approval workflow (v1.33.0). |
| `Haven-UI/tests/api/test_approvals_system.py` | 5 KB | partially fresh | Direct sqlite3 inspection of `pending_systems` table existence, indexes, status counts | DB-only (no HTTP). Hardcoded path `Haven-UI/data/haven_ui.db` (local dev, NOT Pi production). |
| `Haven-UI/tests/integration/test_integration.py` | 1.2 KB | **STALE** | `:8000/api/rtai/status`, POST `:8000/api/discoveries`, reads `Haven-UI/data/data.json` | Wrong port. Reads `data.json` which the project hasn't used since switching to SQLite. |
| `Haven-UI/tests/data/generate_test_data.py` | 16 KB | unknown | Generates 30 test systems with valid glyph codes | Test data generator, not a test runner. |
| `Haven-UI/tests/data/populate_test_data.py` | 13 KB | unknown | Bulk insert helper | Same. |
| `Haven-UI/tests/data/quick_test_systems.py` | 2.5 KB | unknown | Smaller variant | Same. |
| `Haven-UI/tests/data/test_station_placement.py` | 6.6 KB | partially fresh | Tests station coordinate placement algorithm against existing systems | DB-only, hardcoded local path. |
| `Haven-UI/tests/e2e/wizard-glyph.spec.ts` | 0.9 KB | maybe fresh | Playwright: clicking glyphs in `/#/wizard` should not POST `/api/submit_system` or `/api/save_system` | Routing changed from hash routes to `/haven-ui/*` per `App.jsx`; selectors may need updating. |
| `Haven-UI/tests/e2e/wizard-enter.spec.ts` | 2.4 KB | maybe fresh | Playwright: pressing Enter inside wizard input should not auto-submit; clicking the submit button should | Same routing concern; uses `input[placeholder="Name"]` which may have changed. |
| `Haven-UI/tests/test_nms_namegen.py` | unknown | **fresh** | `unittest`: imports of vendored `nms_namegen` modules | The only test that's actually pytest-discoverable and likely passes today. |
| `Haven-UI/scripts/smoke_test.py` | 1.2 KB | half-fresh | `argparse` `--base http://127.0.0.1:8000`; checks `/api/status`, `/api/stats`, `/api/systems`, `/haven-ui` | Default port wrong; can be invoked with `--base http://127.0.0.1:8005` and the rest works. Optional admin login if `HAVEN_ADMIN_PASSWORD` env set. |
| `Haven-UI/scripts/test_approval.py` | 0.7 KB | partial | DB-only sqlite3 inspection of one pending submission | |
| `Haven-UI/scripts/test_signed_hex_glyphs.py` | unknown | unknown | Glyph signed-hex conversion helper | |
| `Haven-Exchange/tests/smoke_test_e2e.py` | 34 KB | **fresh** | 52 pytest scenarios using `fastapi.testclient.TestClient`, in-memory SQLite via `StaticPool`. Self-contained, well-isolated. | This is the **gold-standard test pattern** in the repo. |
| `The_Keeper/tests/test_commands.py` | 32 KB | **fresh** | Mock-based asyncio test of every prefix command + `FeaturedCog` listeners + leaderboard task. NO network calls. Stubs `gspread`/`google.oauth2`. Uses `asyncio.run(main())` — single entry point, not pytest-discoverable. | Tests `!list`, `!hexkey`, `!map`, `!stats`, `!best`, `!systems`, `!planets`, `!department`, `!xp`, `!community`, `!partners` (known-bug), `!addciv`, `!newsystem`, `!discovery` (known-bug), `!leaderboard` (known-bug), and 10 FeaturedCog scenarios. **Does NOT yet test the `/fingerprint` or `/atlas` slash commands.** |
| `NMS-Save-Watcher/test_parser.py` | unknown | unknown | Save watcher parser | Out of scope for this suite. |
| `NMS-Haven-Extractor/utility_scripts/test_extractor.py` | unknown | unknown | Game-mod debug helper | Cannot run without a live NMS process. |
| `NMS-Haven-Extractor/utility_scripts/debug_offset_test.py` | unknown | unknown | Memory offset debugging | Same. |

### Overlap with the new suite

- **Haven-UI smoke test** (`scripts/smoke_test.py`) is the closest existing analog. It was the right idea. Phase 2 should **replace it**, not augment it (port mismatch + stale paths make it actively misleading).
- **`tests/api/*`** files — all four should be **deleted in Phase 2** (or moved to an `archive/` subfolder). They reference `/api/rtai/`, `data.json`, port 8000, and the pre-discovery-approval `/discoveries` POST flow. They are not tests, they are dead `print()` scripts.
- **`tests/integration/test_integration.py`** — same fate.
- **`Haven-UI/tests/e2e/*`** — keep, but verify they still pass against the current SPA routing (`/haven-ui/wizard` is the live URL, not `/#/wizard`).
- **`tests/test_nms_namegen.py`** — keep as-is. It's a clean unittest that verifies vendored library imports.
- **`The_Keeper/tests/test_commands.py`** — keep. Add `/fingerprint` and `/atlas` coverage in Phase 2.
- **`Haven-Exchange/tests/smoke_test_e2e.py`** — keep. Its TestClient + StaticPool pattern is what we should adopt for Haven-UI in Phase 2.

---

## 3. The_Keeper Command Tree

**Bot file:** `The_Keeper/bot.py`. Loads cogs in order from `bot.py:193-208`:

```python
COGS = [
    "cogs.personality", "cogs.xp_system", "cogs.xp_cog",
    "cogs.Haven_stats", "cogs.featured", "cogs.community",
    "cogs.welcome", "cogs.Haven_upload", "cogs.announcements",
    "cogs.hex",
    "cmds.exclaim", "cmds.list", "cmds.slash", "cmds.voyager",
]
```

`bot.tree.sync()` runs in `on_ready` so all `app_commands` are auto-synced.

### Slash commands (`app_commands`)

| Command | File | Cog | Status | Testable in isolation? |
|---|---|---|---|---|
| `/fingerprint [user] [username]` | `cmds/voyager.py:75` | `VoyagerCog` | **just fixed — top priority per dispatch** | Yes — pure URL construction + embed; can mock `discord.Interaction` and inspect outgoing embed URL. The actual PNG fetch is done by Discord, not the bot. |
| `/atlas [galaxy]` | `cmds/voyager.py:139` | `VoyagerCog` | **just fixed — top priority** | Yes — same shape. Has autocomplete (`atlas_autocomplete`) which is also pure-function-testable. |
| `/announce` | `cmds/slash.py:24` | `CommandsCog` | unknown | Requires Discord channel objects; mock-testable. |

### Prefix commands (`commands.command`)

Defined in `cmds/exclaim.py` (`CommandsRouter` cog):

| Command | Help text | Channel-locked? |
|---|---|---|
| `!xp` | check rank and level progress | qualify channel |
| `!community` | Look up a No Man's Sky civ or community | library |
| `!addciv` | add a civ or community to our list | general |
| `!newsystem` | upload a system directly from the server | system channel |
| `!discovery` | upload a discovery from the server | base, fauna, flora, etc. (known bug — `system_xp` not imported) |
| `!leaderboard` | featured-photo leaderboard | general (known bug — `ctx.trigger_typing()` removed in discord.py 2.x) |
| `!map` | link to Haven map | library |
| `!stats` | overview of Haven map stats | library |
| `!best` | user leaderboard | library |
| `!systems` | number of current systems | library |
| `!planets` | number of current planets | library |
| `!department` | XP department selector | qualify |
| `!partners` | partner community list | general (known bug — `raw` referenced before assignment) |

Defined elsewhere:

| Command | File | Cog |
|---|---|---|
| `!list` | `cmds/list.py:142` | `HelpSystem` |
| `!hexkey` | `cogs/hex.py:208` | `HexKey` |

### Background tasks

| Task | File | Schedule |
|---|---|---|
| `check_milestones` | `cogs/announcements.py:91` | every 5 minutes |
| `weekly_leaderboard` | `cogs/featured.py:161` | every 1 hour (gates on day-of-week + hour) |

### Testable in isolation

**Yes (mockable):** `/fingerprint`, `/atlas`, autocomplete handlers, all command callbacks via the `FakeBot/FakeContext` infrastructure already built in `tests/test_commands.py`, all FeaturedCog listeners.

**No (require live Discord):** Bot startup, `bot.tree.sync()`, real OAuth, message reactions on real channels, the `welcome.py` `on_member_join` hook (relies on guild + role objects), milestone announcements (require a real channel to write to).

### `/fingerprint` and `/atlas` test plan (Phase 2 priority)

For each command:
1. Construct a fake `discord.Interaction` with `.user.name = "TestVoyager"`.
2. Invoke the callback directly: `await VoyagerCog(bot).fingerprint.callback(cog, interaction, user=None, username=None)`.
3. Assert `interaction.response.send_message` was called once with an embed.
4. Assert the embed's `.image.url` matches `https://havenmap.online/api/posters/voyager_og/testvoyager.png?v=<int>` (i.e. cache-buster format).
5. Assert the embed's `.url` matches `https://havenmap.online/voyager/testvoyager`.
6. For `/atlas`, repeat with `galaxy="Hilbert Dimension"` and assert URL-encoding (`Hilbert%20Dimension`).
7. Cooldown error path (`CommandOnCooldown`) — synthesize the exception and assert the ephemeral message.
8. Autocomplete returns ≤25 choices and filters by substring.

This can be added directly to `The_Keeper/tests/test_commands.py` with no new framework.

---

## 4. Extractor Submission Payload

### Where extractor sends from

`NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py:4266-4328` (`_send_to_api`):
- POST `{API_BASE_URL}/api/extraction`
- `API_BASE_URL` defaults to `https://havenmap.online` (`DEFAULT_API_URL` at line 105) but is read from per-user config `~/Documents/Haven-Extractor/config.json`.
- Headers: `Content-Type: application/json`, `User-Agent: HavenExtractor/<version>`, `X-API-Key: <per-user key>` (issued by `/api/extractor/register`).
- TLS verify disabled (`ctx.verify_mode = ssl.CERT_NONE`) — leftover from the ngrok era. Not relevant for Pi production.

### Payload shape (from `routes/approvals.py:2425-2463` doc comment)

```json
{
  "extraction_time": "2024-01-15T12:00:00",
  "extractor_version": "1.9.3",
  "glyph_code": "0123456789AB",
  "galaxy_name": "Euclid",
  "galaxy_index": 0,
  "voxel_x": 100, "voxel_y": 50, "voxel_z": -200,
  "solar_system_index": 123,
  "system_name": "System Name",
  "star_type": "Yellow",     // legacy; v10+ sends star_color
  "star_color": "Yellow",    // current
  "economy_type": "Trading",
  "economy_strength": "Wealthy",
  "conflict_level": "Low",
  "dominant_lifeform": "Gek",
  "reality": "Normal",
  "game_mode": "Normal",     // v1.6.8+
  "discord_username": "TurpitZz",
  "personal_id": "123456789012345678",
  "discord_tag": "Haven",
  "profile_id": null,        // optional — backend resolves if absent
  "no_trade_data": false,    // v1.48.2+ — if true, economy/conflict/lifeform are omitted
  "description": "",         // v1.48.7+ — procgen name when user renames
  "planets": [
    {
      "planet_index": 0,
      "planet_name": "Planet Name",
      "biome": "Lush",
      "biome_subtype": "Standard",
      "weather": "Pleasant",
      "sentinel_level": "Low",
      "flora_level": "High",
      "fauna_level": "Medium",
      "planet_size": "Large",
      "common_resource": "Copper",
      "uncommon_resource": "Carbon",
      "rare_resource": "Gold",
      "is_moon": false,
      "is_gas_giant": false,  // v1.45.0+
      "is_bubble": false,     // v1.49.0+
      "is_floating_islands": false  // v1.49.0+
      // … plus 7 special-feature flags (vile_brood, dissonance, etc.)
    }
  ]
}
```

### Captured payloads / fixtures

- **No saved fixtures** in the repo. No `*.json` or `tests/fixtures/` folder exists.
- The doc comment in `approvals.py:2425-2463` is the canonical schema reference.
- Phase 2 should **construct a fixture from the doc comment** and use it as the test payload.
- For round-trip tests (extractor → `/api/extraction` → `pending_systems` → `/api/approve_system/{id}` → `systems`), use the in-memory SQLite + TestClient pattern from `Haven-Exchange/tests/smoke_test_e2e.py`.

### `/api/extraction` important behaviors

- Resolves `source` via `resolve_source(api_key_info.get('name'))` — splits per-user extractor keys, the legacy "Haven Extractor" key, and the Keeper bot key.
- Uses `find_matching_system()` (last-11-chars + galaxy + reality) for duplicate detection; sets `edit_system_id` if found.
- Strips invalid resources: `len < 2`, non-string, "Unknown", "None", "" all map to `None` (line 2556-2558).
- The `payload['no_trade_data']` flag short-circuits economy/conflict/lifeform population to `None`.
- Any unrecognized planet fields are silently dropped — only fields whitelisted in `planet_entry` survive.

---

## 5. Haven-Exchange

**It exists.** Top-level directory: `Haven-Exchange/` with FastAPI app under `Haven-Exchange/app/`.

### Structure

```
Haven-Exchange/
  app/
    main.py            # FastAPI app, mounts 11 routers
    auth.py blockchain.py config.py database.py
    demurrage.py gdp.py interest.py models.py
    stimulus.py valuation.py wallet.py wallet_health.py
    routes/
      auth_routes.py bank_routes.py docs_routes.py
      mint_routes.py nation_routes.py page_routes.py
      shop_routes.py stock_routes.py transaction_routes.py
      wallet_routes.py
  tests/
    smoke_test_e2e.py  # 52 scenarios
  data/                # economy.db lives here
  docker-compose.yml   # service "travelers-exchange", container "economy", port 8010
  Dockerfile
  requirements.txt
  app/main.py:356  → @app.get("/health") returns {"status":"ok","service":"Travelers Exchange"}
```

### Routes (selected — full count ~80)

- `routes/auth_routes.py`: `POST /register`, `POST /login`, `POST /logout`
- `routes/bank_routes.py`: `/api/banks`, `/api/banks/{id}/loans`, `/api/loans/mine`, `/api/loans/{id}/pay`, mint settings
- `routes/nation_routes.py`: nation apply/join/leave/distribute/demurrage/stimulus
- `routes/mint_routes.py`: GDP/allocations/stimulus proposal flows (admin-heavy)
- `routes/shop_routes.py`: shop/listing/buy/sell flows
- `routes/stock_routes.py`: ticker buy/sell, portfolio, rankings, history
- `routes/page_routes.py`: HTML page renderers (Jinja templates)
- `routes/wallet_routes.py`, `routes/transaction_routes.py`: wallet/tx pages
- `routes/docs_routes.py`: `/docs`, `/docs/learn`, `/docs/nation-leaders`

### Health probe target

- `GET /health` → `{"status":"ok","service":"Travelers Exchange"}` (line 356).
- Used by `Haven-Exchange/docker-compose.yml` healthcheck (`curl -f http://localhost:8010/health`).

### Phase-2 test list (Haven-Exchange)

The existing 52-scenario `smoke_test_e2e.py` is comprehensive. Recommend:
- **Add a thin "is the live container reachable" smoke test** at `tests/smoke/test_haven_exchange_live.py` that simply hits `https://<host>:8010/health` (or whatever the prod URL is) and asserts `200`.
- **Do NOT duplicate** the existing E2E tests against the live DB — they were designed for in-memory SQLite isolation.

---

## 6. Viobot

**Does not exist in this repo.** No `Viobot/`, `viobot/`, `vio_bot/`, or any case variant directory at any depth. No source files reference "viobot" as a module.

The dispatch prompt's expectation that Viobot is part of the ecosystem appears to be from outside the repo. **Flag for Parker:** Is Viobot a separate Pi-side service or has it not yet been added to this repo?

---

## 7. The_Keeper Internals (heartbeat / healthcheck / container)

### Heartbeat / status file
**None.** Repo-wide grep for `heartbeat|HEARTBEAT` returned only WarRoom-internal references in the Haven backend. The_Keeper writes no status file.

### Dockerfile (`The_Keeper/Dockerfile`)
- Base: `python:3.11-slim`
- No `HEALTHCHECK` directive
- Hardcoded path: bot.py reads `.env` from `/storage/emulated/0/Voyage/The_Keeper/.env` (Android-style path; mounted as a volume in production)
- CMD: `python bot.py`

### docker-compose.yml (`The_Keeper/docker-compose.yml`)
- Container name: `the-keeper`
- **No `healthcheck:` section.**
- `restart: unless-stopped`
- Volumes: `./.env`, `./xp.db`, `./milestones.json`
- Network: joins external `haven-net` (must be created and Haven-UI must be attached to it manually — see compose comments)

### Implication for the test suite

There is no easy "is The_Keeper alive?" check from the Pi host. Two options for Phase 2:
1. **Process check via `docker ps --filter name=the-keeper --filter status=running`** — container-level liveness.
2. **Discord webhook ping from the bot itself** — would require code changes to The_Keeper (out of scope for read-only Phase 1; flag for Parker).

Container-level check is the safer Phase-2 recommendation.

---

## 8. docker-compose Files

### Top-level `docker-compose.yml`
**Does not exist.** Each service has its own compose in its subfolder.

### `Haven-UI/docker-compose.yml`
- Service: `haven`, container: `haven-control-room`
- Port mapping: `"8005:8005"` (publishes on host)
- Volumes: `~/haven-data:/app/Haven-UI/data`, `~/haven-photos:/app/Haven-UI/photos`
- **Has healthcheck**: `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/api/status')"` every 30s
- Restart: `unless-stopped`
- **Does NOT join `haven-net` external network in this file.** The Keeper's compose comments instruct Parker to manually `docker network connect haven-net haven-control-room` after first start.

### `The_Keeper/docker-compose.yml`
- Container: `the-keeper`
- Joins `haven-net` (external) — that's how it talks to Haven over the LAN
- **No healthcheck**

### `Haven-Exchange/docker-compose.yml`
- Service: `travelers-exchange`, container: `economy`
- Port mapping: `"8010:8010"`
- **Has healthcheck**: `curl -f http://localhost:8010/health` every 30s
- Restart: `unless-stopped`
- **Does NOT join `haven-net`.** Currently isolated from Haven-UI / Keeper by Docker networking.

### Networking summary (likely production state)

```
[ Pi host : 10.0.0.229 ]
  ├─ port 8005 → haven-control-room (default network + haven-net via manual connect)
  ├─ port 8010 → economy (own default network — isolated)
  └─ the-keeper (haven-net only — talks to haven via http://haven:8005, NOT havenmap.online)
```

The Haven-UI memory file ([project_pi_docker_layout.md](../C:/Users/parke/.claude/projects/C--Master-Haven/memory/project_pi_docker_layout.md)) implies all three containers should share `docker_default`, but the current compose files actually use `haven-net` for Haven↔Keeper. **This is a delta worth flagging.**

---

## 9. Discord Webhook Code

### Outbound to Discord webhooks

| Location | Direction | Purpose |
|---|---|---|
| `Haven-UI/backend/routes/warroom.py:109-126` | OUT | Posts war news / conflict events to per-partner Discord webhooks via `req_lib.post(webhook_url, json={"embeds":[embed]}, timeout=5)` |
| `Haven-UI/backend/routes/warroom.py:2099-2167` | n/a | CRUD for `discord_webhooks` table (`/api/warroom/webhooks`) |
| `Haven-UI/backend/migrations.py` | n/a | Schema for `discord_webhooks` |

That's the **only** outbound webhook code in the repo.

### No backup-script webhook

There is no script in `scripts/` that POSTs to a Discord webhook. The dispatch prompt's "existing webhook code" assumption is satisfied by the WarRoom path only.

### Implication for the test suite

Phase 2 should **NOT** write a webhook URL to disk. If the smoke suite needs to ping a Discord channel on success/failure, the URL must come from an env var (`SMOKE_DISCORD_WEBHOOK_URL`) and live only in `~/.env` or whatever Parker-managed config holds it. **Per dispatch hard rule #2, this report contains no webhook URLs.**

---

## 10. Backup Scripts

### What exists

| File | Purpose |
|---|---|
| `Haven-UI/backend/control_room_api.py:3419-3438` | `POST /api/backup` — super admin, `shutil.copy2` to `data/haven_ui_backup_<timestamp>.db` (single-file, in-place, on the same disk) |
| `Haven-UI/backend/migrations.py:124-187` | `backup_database()` — called automatically before each migration |
| `Haven-UI/backend/migrate_photos_to_webp.py:55,305` | One-off migration helper that backs up before running |
| `Haven-UI/scripts/apply_update_remote.sh` | Run on the Pi during deploy; copies `~/Master-Haven` → `~/Master-Haven-backup-<timestamp>` before extracting the update tarball |
| `scripts/pi_setup_stage3.sh` | Installs cron at `0 4 * * 0` calling `~/haven-maintenance.sh`, which hits `POST /api/admin/maintenance/vacuum`. **Not a backup — a maintenance VACUUM.** |

### What's missing

- **No off-Pi backup.** The `/api/backup` endpoint copies to the same volume.
- **No backup of `~/haven-photos`** (the docker volume). A photo loss event would be unrecoverable.
- **No retention policy** — `data/haven_ui_backup_*.db` files would accumulate without cleanup.

### Phase-2 implication

If the smoke suite is meant to verify that backups work, options are:
1. Run `POST /api/backup` and verify a new `*.db` file appears (cheap, what `/api/backup` already does).
2. Add a real backup script that rsyncs to a remote (out of scope for Phase 1; flag for Parker).

---

## 11. Git Deployment Workflow

### Pi-side (production) — confirmed by reading

- `Haven-UI/docker-compose.yml` instructs: `docker compose up -d --build` after `git pull`.
- `The_Keeper/docker-compose.yml` instructs: `docker compose up -d --build` (must `docker network create haven-net` first).
- `Haven-Exchange/docker-compose.yml` instructs: `docker compose up -d --build`.

The dispatch prompt's stated workflow:
```
cd ~/docker/haven-ui/Master-Haven && git pull && cd Haven-UI && docker compose up -d --build
```
matches the repo intent.

### Win-dev → Pi push helpers (mostly stale)

| File | Status | Notes |
|---|---|---|
| `Haven-UI/scripts/deploy_to_pi.ps1` | **legacy** | Designed for systemd-on-Pi era (`sudo systemctl restart haven-ui.service`). Builds a tarball + scps it. Does NOT use Docker. Pre-dates the container migration. |
| `Haven-UI/scripts/create_update_archive.ps1` | legacy | Tarball builder for the above. |
| `Haven-UI/scripts/apply_update_remote.sh` | legacy | Pi-side handler for the tarball. |
| `Haven-UI/raspberry/haven-control-room.service` | legacy | Old systemd unit. |
| `Haven-UI/raspberry/README.md` | legacy | Says "Python venv + systemd". Out of date — production is Docker now. |

### Phase-2 implication

Smoke tests should target the **Docker compose model**, not the legacy systemd model. Liveness checks should hit `http://localhost:8005/api/status` (Haven), `http://localhost:8010/health` (Exchange), and `docker ps --filter name=the-keeper` (Keeper). **Do not invoke the legacy PowerShell deploy scripts** — they're dead.

---

## 12. SSH Access

This Claude session runs on the Win-dev machine, **not** on the Pi (10.0.0.229). The harness has no SSH credentials configured for the Pi; explicit SSH is out of scope.

Phase-2 implication: **smoke tests that need to verify Pi-side state must be runnable from a remote (the Win-dev machine + WAN/LAN)**, e.g., HTTP probes against `https://havenmap.online/api/status`. Anything that requires shelling into the Pi (filesystem checks, `docker ps`, `crontab -l`, etc.) needs Parker to either:
1. Add SSH credentials to the test runner's environment (and bless that policy).
2. Provide a small Pi-side script Parker runs by hand and pastes the output.
3. Expose a new admin endpoint that exposes the relevant info (`/api/admin/health` already covers DB / WAL / memory).

---

## Deltas vs the dispatch prompt's assumptions

| Dispatch assumption | Reality | Severity |
|---|---|---|
| Routes are in `Haven-UI/backend/routes/` | Mostly true — but **47 routes still on `@app` in control_room_api.py**, including `/api/save_system`, `/api/systems/{id}`, `/api/db_stats`, `/api/admin/health`, `/api/backup`, all SPA HTML routes | medium — Phase 2 must include the @app routes in the inventory |
| `keeper-discord-bot-main/` is archived | Confirmed — see `C:\Master-Haven-Archives\2026-Q2\2026-04-28-keeper-discord-bot-main\`. The_Keeper is the active bot. | none (matches) |
| `/fingerprint` and `/atlas` were "just fixed" in `The_Keeper/cmds/voyager.py` | Confirmed file exists at that path with both commands. | none |
| `Haven-Exchange/` may not exist | **It DOES exist** with 11 routers, ~80 routes, a 52-test smoke suite, and `/health`. | medium — was treated as conditional; should be a first-class smoke target |
| `Viobot/` may exist | **Does NOT exist anywhere in repo.** | high — flag for Parker |
| Top-level `docker-compose.yml` | Does NOT exist. Each service has its own. | low — easy to handle |
| The_Keeper has a healthcheck | **No.** The_Keeper Dockerfile and compose have zero healthcheck. | medium — affects what "is keeper alive" means |
| The_Keeper writes a heartbeat file | **No.** No heartbeat code exists anywhere in the repo. | medium — same as above |
| Existing tests are mostly current | **Wrong.** 5 of 6 `Haven-UI/tests/` files reference port 8000 (current is 8005), `/api/rtai/*` (deleted), and `data.json` (deleted). | high — Phase 2 should delete or archive these |
| Backend on port 8000 (implicit in old smoke_test.py) | **Backend is on 8005.** All current docker-compose, server.py, healthchecks confirm. | high — any new smoke script must default to 8005 |
| Networks share `docker_default` | Compose files actually use external `haven-net` for Haven↔Keeper; Haven-UI doesn't join it automatically — manual `docker network connect` step required | medium — flag for Parker; production state may diverge from the compose files |
| Backup script exists | A `POST /api/backup` admin endpoint exists, plus `migrations.backup_database()`. **No standalone off-Pi backup script.** | medium — affects the "verify backup" test goal |
| `Haven-UI/tests/api/test_endpoints.py` is current | Stale; references port 8000 and a long-removed `/api/rtai/` namespace | low — easy to clean up |

---

## Proposed Test List (Phase 2 Revision)

Organized by service. Each row notes priority and a one-line implementation hint.

### Smoke tier (hit live infrastructure)

| Test | Service | Priority | Implementation |
|---|---|---|---|
| Haven `/api/status` returns 200 + version | Haven | P0 | `requests.get` from any networked machine |
| Haven `/api/db_stats` returns 200 + non-zero counts | Haven | P0 | as above |
| Haven `/api/communities` returns ≥1 community | Haven | P0 | as above |
| Haven `/api/systems?limit=10` returns ≤10 results, no 500 | Haven | P0 | as above |
| Haven `/api/public/voyager-fingerprint?username=parker1920` returns valid JSON | Haven | P1 | username slug from existing data |
| Haven `/api/public/galaxy-atlas?galaxy=Euclid` returns valid JSON | Haven | P1 | as above |
| Haven `/api/posters/voyager_og/parker1920.png` returns 200 with `image/png` content-type and >5 KB body | Haven | P1 | most expensive test; flake risk from Playwright |
| Haven `/api/posters/atlas/Euclid.png` returns 200 with `image/png` | Haven | P1 | as above |
| Haven `GET /` returns 200 with `<meta property="og:image">` containing https URL | Haven | P1 | exercises the `og:image` protocol fix from commit `0a75cee` |
| Haven `GET /voyager/parker1920` returns 200 HTML | Haven | P1 | SSR route |
| Haven-Exchange `/health` returns 200 | Exchange | P0 | `curl -f https://<host>:8010/health` |
| The_Keeper container is running | Keeper | P0 | `docker ps --filter name=the-keeper --filter status=running` (Pi-side; Parker runs) |

### Verification tier (in-process, in-memory DB)

| Test | Service | Priority | Implementation |
|---|---|---|---|
| `/api/extraction` accepts the canonical extractor payload and creates a `pending_systems` row | Haven | P0 | `fastapi.testclient.TestClient` + `StaticPool` SQLite + the doc-comment fixture |
| `/api/extraction` correctly resolves `source` for `Keeper 2.0` API key → `keeper_bot` | Haven | P0 | same harness, vary `X-API-Key` |
| `/api/extraction` honors `no_trade_data: true` (NULL economy/conflict/lifeform after approval) | Haven | P0 | round-trip submit + approve |
| `/api/discoveries POST` enqueues to `pending_discoveries` (not direct insert) | Haven | P0 | guards the v1.48.3 fix |
| `/api/posters/voyager_og/{slug}.png` cache key is `username` lowercased + `#`-stripped + 4-digit-discriminator-stripped | Haven | P1 | unit test on `normalize_username_for_dedup` |
| `/fingerprint` slash command builds the correct embed URL | Keeper | P0 | follow the §3 plan; add to `tests/test_commands.py` |
| `/atlas` slash command builds the correct URL with URL-encoded galaxy | Keeper | P0 | as above |
| `/atlas` autocomplete filters by substring and returns ≤25 | Keeper | P1 | as above |
| Existing 52 Haven-Exchange smoke scenarios still pass | Exchange | P1 | already exists; just wire into CI |

### Repo-hygiene tier (one-time housekeeping)

| Action | Priority |
|---|---|
| Delete or archive `Haven-UI/tests/api/test_api_calls.py`, `test_endpoints.py`, `test_post_discovery.py`, `tests/integration/test_integration.py`. They reference port 8000 / `/api/rtai/` / `data.json` and are not tests. | P0 |
| Update `Haven-UI/scripts/smoke_test.py` default port to 8005, OR delete it in favor of the new tests/smoke/ tree | P0 |
| Update Playwright `wizard-*.spec.ts` if route changed from `/#/wizard` to `/haven-ui/wizard` | P1 |

---

## Risks and Questions for Parker

1. **Viobot:** The dispatch lists Viobot as a service to investigate. **It does not exist in this repo.** Is it a separate project? If so, where? If not, should the test list assume it's coming?
2. **The_Keeper has no healthcheck or heartbeat.** The cleanest "is Keeper alive" probe is `docker ps` on the Pi, which the test runner can't do remotely without SSH. Options:
   - (a) Add a Discord webhook ping from `bot.py` on `on_ready` to a private channel — requires code change to The_Keeper, which Parker's instructions say is **read-only by default** without explicit per-task authorization. **Need explicit approval to touch `The_Keeper/*` in Phase 2.**
   - (b) Add a tiny HTTP server inside The_Keeper that returns 200 — same code-change concern.
   - (c) Limit Keeper checks to "the slash command builds the right URL" + Parker manually verifies the container is up. This is what I'd recommend for v1.
3. **Discord webhook for smoke notifications:** Should the suite post pass/fail to a webhook? If yes, **the URL must come from an env var, not a checked-in file.** I will not write any webhook URL to disk under any circumstances per dispatch hard rule #2.
4. **Pi access:** This Claude session can't SSH to the Pi. Pi-only verifications (zram status, cron entry, container `ps`) need Parker to run a small bash snippet locally and paste the output. I can ship that snippet as `tests/pi_check_v2.sh` if useful.
5. **Posters tests are flake-prone:** They render via Playwright + Chromium inside the Haven container. A first run after cold start can take ~30s; consider making the smoke timeout 60s for poster tests specifically.
6. **CI vs local:** Where will the smoke tests run? Options: (a) GitHub Actions hitting `https://havenmap.online`, (b) a `cron` job on the Pi hitting `localhost:8005`, (c) a manual `pytest` invocation by Parker. Each has different network/auth implications.
7. **Live-vs-test DB:** The verification-tier tests should NEVER touch `~/haven-data/haven_ui.db` on the Pi. Use `Haven-Exchange/tests/smoke_test_e2e.py`'s `StaticPool` in-memory pattern as the template. If we want round-trip extraction tests to run against a real DB, build a fixtures DB + restore-from-fixture script — don't share with prod.
8. **Phase 2 scope:** This report identifies ~20 candidate tests. A v1 suite probably wants 8-10 (the P0 ones plus the most useful P1s). Confirm the budget for v1.
9. **Database location:** `Haven-UI/data/haven_ui.db` exists locally but per the memory note, **production DB is on the Pi**. Local row counts ≠ production row counts. Tests that assert specific counts should use ranges or trends, not exact numbers, and should never quote local DB state as if it were production.

---

**End of Phase 1.** Stopping here per dispatch instructions. Awaiting Parker's review and answers to the questions above before proceeding to Phase 2.
