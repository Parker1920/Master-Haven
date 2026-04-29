# Voyager Card & Galaxy Atlas — Poster System Plan

**Status:** Approved with Option C for atlas region picker · Ready to build
**Last updated:** 2026-04-28
**Owner:** Parker (single-developer project)
**Scope:** Haven-UI (web + backend) + The_Keeper (Discord bot)

---

## Why this document exists

The first attempt at building this drifted away from the spec — two hardcoded React pages instead of the templatization system that was designed. This doc is the **single source of truth**. Re-read at the start of every phase. Update the TODO list as work completes. Do not deviate without explicit approval and a corresponding doc update.

---

## Vision (user's words, reinterpreted)

Two artifact types, one templatization system, surfaces in three places (web UI, Discord bot, link-preview embeds), auto-updated, easy to add new poster types.

### 1. Galaxy Atlas
- One poster **per NMS galaxy** that has approved systems (auto-discovered, no hardcoding 256 names)
- Visualizes every populated region as a colored dot, colored by which civilization controls it
- Surfaces:
  - **Standalone URL** `havenmap.online/atlas/:galaxy` — full poster, fully shareable
  - **Galaxy cards in the Systems tab** — replaced with mini atlas thumbnails (small variant)
  - **Galaxy detail / Reality view** — link to full atlas
  - **Discord paste** — link unfurls into the poster as preview image
  - **Discord slash command** `/atlas <galaxy>` — embeds the poster in chat
  - **Auto-refresh weekly** — always reflects current state
  - **Event-driven invalidation** — region naming or system approval refreshes the affected galaxy

### 2. Voyager Card
- One card **per Haven member** with any approved contribution
- Live data: rank, totals, galaxy reach, lifeforms, top regions, first-charted, completeness
- Surfaces:
  - **Standalone URL** `havenmap.online/voyager/:username`
  - **Profile page** — embedded as the stats card on user's own profile
  - **Cross-links** — every contributor name in analytics, leaderboards, system pages, discoveries links to their card
  - **Discord paste** — link unfurls into the card
  - **Discord slash command** `/fingerprint [@user]` — embeds the card in chat
  - **Privacy opt-out** — `user_profiles.poster_public` flag (default opt-in)

### 3. Templatization (the ACTUAL goal)
- Adding a new poster type = **one registry entry + one React component**. Nothing else.
- All shared chrome (frame, fonts, brand mark, watermark, color helpers) lives in `posters/_shared/`
- Backend renders any registered poster via a single endpoint `GET /api/posters/{type}/{key}.png`
- One render pipeline (Playwright), one cache table (`poster_cache`), one OG SSR shim

---

## Decisions locked

| # | Question | Choice | Reason |
|---|----------|--------|--------|
| 1 | Galaxy card in Systems tab — full atlas or thumbnail? | **Thumbnail** (~400×400 simplified) + link to full poster | Heavy renders in card grids; small variant is cheap and beautiful |
| 2 | Voyager Card aspect ratio | **Two variants** — `voyager` (680×1040 full) + `voyager_og` (1200×630 condensed for embeds) | Full poster for the page, OG-spec for Twitter/Slack to avoid letterboxing |
| 3 | Profile page embed | **PNG with "View live" link** + freshness commitment (event-driven invalidation + 24h TTL + manual refresh button) | Lighter, single source of truth with Discord, freshness guaranteed |
| 4 | OG image fallback for non-mapped routes | **Dynamic** — all routes default to `/api/posters/og_site/global.png`; SSR shim overrides for share routes | One fewer thing rotting; static `haven-preview.png` retired |
| 5 | Username normalization | **Reuse existing backend `normalize_username_for_dedup`** + `voyager-fingerprint`'s inline canonical form. Add minimal frontend helper for share-link generation only. | No duplicated normalization |
| 6 | Atlas region picker | **Option C — faction-first with spatial deduplication** | Matches mockup distribution; each civ represented; markers spatially separated |

### Option C details (region picker algorithm)

```
1. Group regions by `dominant_tag` (the controlling civ).
2. For each unique tag, take that civ's BIGGEST region.
3. Sort the resulting list by system_count DESC.
4. Walk the sorted list, building the picked list:
   for candidate in sorted_list:
     if len(picked) >= 9: break
     if any(distance(candidate, p) < threshold for p in picked):
       continue   # too close to an already-picked marker
     picked.append(candidate)
5. If <9 picked after one pass, fall back to filling remaining slots
   with the next-largest regions of *any* civ (still respecting distance threshold).
6. Number 1..N in picked order (largest first).

threshold = 10% of galaxy bounding box diagonal (tunable).
```

**Result for Euclid (16 civs, sample):** 9 distinct civilizations represented, spatially distributed across the map. Galactic Hub gets one entry (its biggest region), not 8.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                  POSTER SERVICE (single source of truth)          │
│                                                                   │
│  REGISTRY ───▶ Render Queue ───▶ Playwright ───▶ PNG cache       │
│  (types,        (semaphore        (persistent      (disk +        │
│  versions,      max=2,            browser,         poster_cache    │
│  sizes,         15s timeout)      window.__        table)         │
│  ttls)                            POSTER_READY                    │
│                                   gate)                           │
└──────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
   /api/posters/         routes/ssr.py      Cache lifecycle:
   {type}/{key}.png      (OG meta tags      • TTL (registry)
   (PNG endpoint)        emitted before     • data_hash check
                         SPA fallback)      • event-driven
                                            • manual refresh
                                            • template version
            │                 │                 │
            ▼                 ▼                 ▼
   Consumed by:    Consumed by:        Triggered by:
   • <img> tags    • Discord scrap.    • approve_system
   • Profile page  • Twitter scrap.    • approve_region_name
   • Systems tab   • Slack/Reddit      • POST .../refresh
   • Discord bot                       • weekly /schedule cron
   • Direct share
```

---

## File map — Haven-UI

### Backend (`Haven-UI/backend/`)

| File | Action | Purpose | Est. lines |
|------|--------|---------|-----------|
| `services/poster_service.py` | **NEW** | `PosterTemplate` dataclass, `REGISTRY` dict, render queue, Playwright lifecycle, cache I/O, `get_or_render()`, `invalidate(type, key)` | ~320 |
| `routes/posters.py` | **NEW** | `GET /api/posters/{type}/{key}.png`, `POST /api/posters/{type}/{key}/refresh`, `GET /api/posters/admin/queue` | ~160 |
| `routes/ssr.py` | **NEW** | Jinja shim emitting og:* meta tags for `/voyager/:user`, `/atlas/:galaxy`, `/systems/:id`, `/community-stats/:tag`. Mounts BEFORE SPA fallback. | ~140 |
| `routes/analytics.py` | **MODIFY** | Tighten `/api/public/galaxy-atlas`: spatial-diversity region picker (Option C), display name lookup via `discord_tag_colors`, dedupe `Personal`/`personal` | ~80 lines changed |
| `routes/approvals.py` | **MODIFY** | Call `invalidate_poster_cache("voyager", username)` and `invalidate_poster_cache("atlas", galaxy)` after approving a system | ~10 lines added |
| `routes/regions.py` | **MODIFY** | Call `invalidate_poster_cache("atlas", galaxy)` after approving a region name | ~5 lines added |
| `control_room_api.py` | **MODIFY** | FastAPI `lifespan` boots the persistent Playwright browser instance; mount `posters` and `ssr` routers; mount SSR with HIGH priority (before SPA static fallback) | ~25 lines added |
| `templates/og.html` (or inline string) | **NEW** | The Jinja template emitting og:* + twitter:* meta tags + JS-redirect to SPA | ~60 |
| `requirements.txt` | **MODIFY** | Add `playwright>=1.45`. Jinja2 already pulled by FastAPI. | 1 line |

### Frontend (`Haven-UI/src/`)

| File | Action | Purpose | Est. lines |
|------|--------|---------|-----------|
| `posters/_shared/PosterFrame.jsx` | **NEW** | Chrome-less wrapper with viewport sizing, dark background, font loading | ~50 |
| `posters/_shared/CompassMark.jsx` | **NEW** | Brand mark (teal target circle, two sizes) | ~25 |
| `posters/_shared/Watermark.jsx` | **NEW** | Footer: havenmap.online + brand + drawn-from-live-data | ~40 |
| `posters/_shared/colors.js` | **NEW** | `getDisplayTagName(tag, apiColors)`, re-exports from existing tagColors.js | ~30 |
| `posters/_shared/identity.js` | **NEW** | `normalizeUsernameForUrl(name)` — small frontend helper for share-link generation. Mirrors backend normalize_username_for_dedup logic. | ~25 |
| `posters/_shared/ready.js` | **NEW** | `markPosterReady()` — sets `window.__POSTER_READY = true` after fonts + data settle. Hook for Playwright. | ~15 |
| `posters/registry.js` | **NEW** | Frontend mirror: `{ voyager: {component, w, h}, voyager_og: {...}, atlas: {...}, atlas_thumb: {...}, og_site: {...}, og_system: {...}, og_community: {...} }` | ~40 |
| `posters/VoyagerPoster.jsx` | **REFACTOR** | Use `_shared/`. Visual unchanged. | -100, +0 net |
| `posters/VoyagerOG.jsx` | **NEW** | 1200×630 condensed Voyager Card variant for embeds | ~150 |
| `posters/GalaxyAtlas.jsx` | **REFACTOR + FIX** | Use `_shared/`. Apply Option C region picker, ellipse projection centered on (2048, 2048), display names, tiered dot sizing | ~100 net |
| `posters/AtlasThumb.jsx` | **NEW** | 400×400 simplified atlas: dots only, no side panel, lighter. For Systems-tab cards. | ~80 |
| `posters/OGSiteCard.jsx` | **NEW** | 1200×630 global Haven preview replacing static `haven-preview.png` | ~120 |
| `posters/OGSystemCard.jsx` | **NEW** | 1200×630 per-system OG card (name, galaxy, glyph, completeness) | ~100 |
| `posters/OGCommunityCard.jsx` | **NEW** | 1200×630 per-community OG card (logo color, member count, system count) | ~100 |
| `pages/PosterRoute.jsx` | **NEW** | Single `/poster/:type/:key` route. Reads frontend registry, mounts correct component. Used by Playwright. | ~40 |
| `App.jsx` | **MODIFY** | Add `/poster/:type/:key` to chrome-less routes. Keep `/voyager/:user` and `/atlas/:galaxy` as friendly aliases. | ~15 lines added |
| `pages/Profile.jsx` | **MODIFY** | "Your Voyager Card" section at top: PNG embed + "View Live" + Copy Link + Download + Refresh + opt-out toggle | ~80 lines added |
| `pages/Systems.jsx` (or wherever galaxy cards render) | **MODIFY** | Replace galaxy card visual with `<img src="/api/posters/atlas_thumb/{galaxy}.png" />` + link to atlas | ~30 lines |
| `pages/SystemDetail.jsx` | **MODIFY** | "Discovered by" name → Link to voyager card | ~5 lines |
| `pages/CommunityStats.jsx`, `CommunityDetail.jsx`, `Analytics.jsx`, `PartnerAnalytics.jsx` | **MODIFY** | Contributor names become Links | ~10 lines each |
| `components/LeaderboardTable.jsx` | **MODIFY** | Wrap username cell in a Link to voyager card | ~10 lines |
| `pages/Settings.jsx` | **MODIFY (or skipped if Profile has it)** | `poster_public` toggle | ~20 lines |
| `index.html` | **MODIFY** | Default OG image points to `/api/posters/og_site/global.png` (relative) | ~3 lines |

### Database

- Migration v1.70.0 **already applied** — `user_profiles.poster_public` (default 1), `poster_cache` table with indexes
- **No additional migrations needed.**

### Auto-refresh

| Schedule | Action | Mechanism |
|----------|--------|-----------|
| Sunday 4am ET (weekly) | Re-render `og_site/global` + active galaxy atlases + top-50 voyager cards | Claude Code `/schedule` agent (recurring) |
| Daily | Drop `poster_cache` rows older than 90 days | Same agent or separate |
| On `approve_system` | Invalidate user's voyager + galaxy's atlas | Hook in `routes/approvals.py` |
| On `approve_region_name` | Invalidate galaxy's atlas | Hook in `routes/regions.py` |

---

## File map — The_Keeper (Discord bot)

| File | Action | Purpose | Est. lines |
|------|--------|---------|-----------|
| `cmds/voyager.py` | **NEW** | `/fingerprint` and `/atlas` slash commands. Use `embed.set_image(url=...)` pointing at `HAVEN_API/api/posters/...` | ~200 |
| `bot.py` | **MODIFY** | Add `"cmds.voyager"` to COGS list | 1 line |

Notes:
- `HAVEN_API` env var already exists (used by `cogs/Haven_stats.py`)
- `aiohttp` already imported, used for API calls
- `bot.tree.sync()` happens in `on_ready` → new commands auto-register
- No additional cog dependencies

---

## Existing code I MUST reuse (do not reinvent)

| What | Where | Why |
|------|-------|-----|
| Username normalization (backend) | `backend/services/auth_service.py::normalize_username_for_dedup` | Canonical normalization — frontend share-link helper must produce identical output |
| Tag color lookup | `Haven-UI/src/utils/tagColors.js::getTagColorFromAPI` | API-driven palette already cached on app load |
| Tag display names | `/api/discord_tag_colors` endpoint returns `{tag: {color, name}}` | Use `name` field for the legend, not raw tag |
| Region aggregation | `/api/map/regions-aggregated` (existing) | Atlas endpoint can build on this |
| Galaxies list | `backend/data/galaxies.json` (256 galaxies, in repo) | Atlas registry validation |
| Score-to-grade | `backend/constants.py::score_to_grade` | Voyager card completeness display |
| `getPhotoUrl` / `getThumbnailUrl` | `Haven-UI/src/utils/api.js` | URL pattern for poster images mirrors existing photo URLs |
| Voyager fingerprint endpoint | `/api/public/voyager-fingerprint?username=X` | Already returns rich payload — Voyager components self-fetch this |
| Galaxy atlas endpoint | `/api/public/galaxy-atlas?galaxy=X&reality=Y` | Already returns regions + factions — needs picker fix |
| Lazy loading + chrome-less route detection | `Haven-UI/src/App.jsx::POSTER_ROUTE_PREFIXES` and `isPosterRoute()` | Already implemented — extend with new prefixes |
| Discord tag colors API | `/api/discord_tag_colors` | Use for display name lookup in atlas legend |

---

## Build phases (sequential, no overlap)

### Phase 1 — Foundation (backend service layer)
**Deliverable:** `/api/posters/{type}/{key}.png` returns a valid PNG for at least one type, end-to-end.

1. Add `playwright` to `requirements.txt`. Run `pip install playwright && playwright install chromium`.
2. Create `services/poster_service.py`:
   - `PosterTemplate` dataclass
   - `REGISTRY` dict with 7 entries: `voyager`, `voyager_og`, `atlas`, `atlas_thumb`, `og_site`, `og_system`, `og_community`
   - `_browser` (module-level, lazy-init)
   - `get_browser()` — returns persistent Playwright browser, boots if needed
   - `_render_semaphore = asyncio.Semaphore(2)`
   - `render_poster(template, key, output_path)` — opens `/poster/:type/:key`, waits for `window.__POSTER_READY`, screenshots, writes file
   - `compute_data_hash(template, key)` — hash of the underlying source data, used to skip re-renders when nothing changed
   - `cache_lookup(type, key)` — query `poster_cache`, return file path if fresh
   - `cache_write(type, key, hash, path, ms)` — UPSERT into poster_cache
   - `invalidate(type, key)` — DELETE from poster_cache; remove file from disk
   - `get_or_render(type, key)` — main entry: lookup → return if fresh → render → cache → return
3. Create `routes/posters.py`:
   - `GET /api/posters/{type}/{key}.png` — main endpoint
   - `POST /api/posters/{type}/{key}/refresh` — manual rebuild (auth: super admin OR profile owner)
   - `GET /api/posters/admin/queue` — render queue status
4. Wire into `control_room_api.py`:
   - FastAPI `lifespan` context manager: boots Playwright on startup, closes on shutdown
   - Mount `posters_router` from `routes/posters.py`
5. Create `posters/_shared/PosterFrame.jsx`, `CompassMark.jsx`, `Watermark.jsx`, `colors.js`, `identity.js`, `ready.js`
6. Create `posters/registry.js`
7. Create `pages/PosterRoute.jsx` — reads registry, mounts component
8. Modify `App.jsx`:
   - Add `/poster/:type/:key` route
   - Keep `/voyager/:user` and `/atlas/:galaxy` as friendly URLs
9. **Smoke check:** `curl /api/posters/voyager/turpitzz.png` returns a valid PNG

### Phase 2 — Refactor existing posters + visual fix
**Deliverable:** Both existing posters use `_shared/` components; Atlas visual matches mockup quality.

10. Refactor `VoyagerPoster.jsx` to use `_shared/`. Visual unchanged. Verify by visual comparison.
11. Fix `routes/analytics.py::public_galaxy_atlas`:
    - Implement Option C region picker (faction-first + spatial dedup)
    - Display name lookup via `/api/discord_tag_colors` (return display names in `factions` list)
    - Dedupe `Personal`/`personal` via LOWER() before grouping
    - Add `display_name` field to faction entries
12. Refactor `GalaxyAtlas.jsx`:
    - Use `_shared/` components
    - Project regions onto (region_x, region_z) plane centered on (2048, 2048) — actual NMS galaxy center
    - Apply circular/elliptical visible mask
    - Tiered dot sizing: background dots tiny (1px), top regions larger (3-6px)
    - Render display names in factions panel and index, not raw tags
    - Cull regions outside max radius (clip to galaxy bounds)
13. **Visual check:** `/atlas/Euclid` looks like the mockup, not a flat scatter
14. **Smoke check:** open in browser, console has no errors, fonts load

### Phase 3 — OG cards + SSR shim
**Deliverable:** Pasting any covered URL into Discord debugger shows the right per-page preview.

15. Create `OGSiteCard.jsx` — replaces stale haven-preview.png. Pulls site stats from existing endpoints.
16. Create `OGSystemCard.jsx` — pulls from `/api/systems/:id`
17. Create `OGCommunityCard.jsx` — pulls from `/api/public/community-overview`
18. Create `posters/VoyagerOG.jsx` — 1200×630 condensed variant
19. Create `AtlasThumb.jsx` — 400×400 simplified
20. Create `routes/ssr.py`:
    - `SHAREABLE_ROUTES` dict mapping URL patterns to OG-builders
    - `build_voyager_og(username)`, `build_atlas_og(galaxy)`, `build_system_og(id)`, `build_community_og(tag)`
    - Each returns `{title, description, image_url, image_w, image_h}`
    - Single Jinja template renders the HTML
21. Mount SSR router with HIGHER priority than the SPA static fallback in `control_room_api.py`
22. Modify `index.html` default OG to point at `/api/posters/og_site/global.png`
23. **Validation:** test with [Open Graph debugger](https://www.opengraph.xyz/) on `localhost:8005/voyager/turpitzz`, `/atlas/Euclid`, `/systems/123`, `/community-stats/Haven`

### Phase 4 — UI integration (the discoverability layer)
**Deliverable:** Users can find their card and atlas without knowing the URLs.

24. Modify `pages/Profile.jsx`:
    - "Your Voyager Card" section at top
    - `<img src="/api/posters/voyager/{username}.png">` with skeleton placeholder
    - Buttons: View Live (→ `/voyager/:user`), Copy Link, Download PNG, Refresh
    - Opt-out toggle for `poster_public`
25. Modify Systems page galaxy cards:
    - Find current galaxy card render (Galaxies summary view)
    - Replace card body with `<img src="/api/posters/atlas_thumb/{galaxy}.png">`
    - Click → navigate to `/atlas/:galaxy`
26. Modify `SystemDetail.jsx` — "Discovered by" → Link to voyager card
27. Modify `CommunityStats.jsx`, `CommunityDetail.jsx`, `Analytics.jsx`, `PartnerAnalytics.jsx` — all contributor name cells → Link
28. Modify `LeaderboardTable.jsx` — username cell → Link

### Phase 5 — Discord bot
**Deliverable:** `/fingerprint` and `/atlas` slash commands work in The_Keeper.

29. Create `The_Keeper/cmds/voyager.py`:
    - `CommandsCog` class
    - `/fingerprint [user] [username]` — `embed.set_image(url=f"{HAVEN_API}/api/posters/voyager_og/{name}.png")`
    - `/atlas [galaxy]` — `embed.set_image(url=f"{HAVEN_API}/api/posters/atlas/{galaxy_slug}.png")`
    - Galaxy autocomplete from popular galaxies + dynamic fetch
    - 10s per-user cooldown
30. Modify `The_Keeper/bot.py` — add `"cmds.voyager"` to COGS list

### Phase 6 — Cache invalidation hooks + auto-refresh
**Deliverable:** PNGs never lag meaningfully behind live data.

31. Modify `routes/approvals.py`:
    - In `approve_system` (and `batch_approve_systems`): after successful approval, call `invalidate_poster_cache("voyager", normalized_username)` and `invalidate_poster_cache("atlas", galaxy)`
32. Modify `routes/regions.py`:
    - In region name approval handlers: call `invalidate_poster_cache("atlas", galaxy)`
33. Set up Claude Code `/schedule` agent for weekly poster warmup (Sunday 4am ET):
    - Re-render `og_site/global`
    - Re-render every active galaxy's atlas (galaxies with >0 approved systems in last 90 days)
    - Re-render top-50 voyager cards by recent submission activity
34. **NOT in scope for this phase, deferred:** complex stale-on-publish cron with multiple cadences. Just one weekly job + event-driven invalidation.

### Phase 7 — Verification + smoke test + local production
**Deliverable:** End-to-end functionality verified, ready to push.

35. Run backend verification suite (curl tests):
    - All `/api/public/*` endpoints return well-formed JSON
    - `/api/posters/{type}/{key}.png` returns valid PNG (Content-Type, dimensions)
    - Cache layer: 2nd request < 100ms
    - Manual refresh deletes cache row
    - Submission approval invalidates affected posters
36. Browser smoke walk:
    - `/voyager/turpitzz` loads, renders, no errors
    - `/atlas/Euclid` loads, dots distributed correctly
    - `/profile` shows embedded card (logged in)
    - `/systems` shows galaxy thumbnails, click → atlas
    - Click any contributor name → goes to their voyager card
    - Open Graph debugger validates meta tags on all share routes
37. Local production server:
    - `npm run build` in `Haven-UI/`
    - Restart `python Haven-UI/server.py`
    - User walks through everything in browser
38. After Parker validates → write commits per phase, push to git

---

## TODO list (extensive, follow this exactly)

### Phase 1 — Foundation
- [ ] Run `pip install playwright` in venv
- [ ] Run `playwright install chromium` to download browser binary
- [ ] Add `playwright>=1.45` to `Haven-UI/backend/requirements.txt`
- [ ] Create `Haven-UI/backend/services/poster_service.py` with REGISTRY (7 entries) + render queue + Playwright lifecycle + cache helpers
- [ ] Create `Haven-UI/backend/routes/posters.py` with PNG endpoint, refresh endpoint, queue status endpoint
- [ ] Modify `Haven-UI/backend/control_room_api.py` to add Playwright lifespan + mount posters router
- [ ] Create `Haven-UI/src/posters/_shared/PosterFrame.jsx`
- [ ] Create `Haven-UI/src/posters/_shared/CompassMark.jsx`
- [ ] Create `Haven-UI/src/posters/_shared/Watermark.jsx`
- [ ] Create `Haven-UI/src/posters/_shared/colors.js` (with display name resolver from API)
- [ ] Create `Haven-UI/src/posters/_shared/identity.js` (frontend username normalization for share links)
- [ ] Create `Haven-UI/src/posters/_shared/ready.js` (markPosterReady helper)
- [ ] Create `Haven-UI/src/posters/registry.js` (frontend registry mirror)
- [ ] Create `Haven-UI/src/pages/PosterRoute.jsx` (single registry-driven route)
- [ ] Modify `Haven-UI/src/App.jsx` to add `/poster/:type/:key` route
- [ ] Smoke test: backend running, `curl http://127.0.0.1:8005/api/posters/voyager/turpitzz.png > test.png` returns valid PNG

### Phase 2 — Refactor + visual fix
- [ ] Refactor `VoyagerPoster.jsx` to use `_shared/` components (visual unchanged)
- [ ] Modify `routes/analytics.py::public_galaxy_atlas`: implement Option C region picker
- [ ] Modify `routes/analytics.py::public_galaxy_atlas`: add display name lookup via discord_tag_colors
- [ ] Modify `routes/analytics.py::public_galaxy_atlas`: dedupe `Personal`/`personal` case-insensitively
- [ ] Refactor `GalaxyAtlas.jsx` to use `_shared/` components
- [ ] Fix `GalaxyAtlas.jsx` projection: center on (2048, 2048), apply circular mask
- [ ] Fix `GalaxyAtlas.jsx` dot sizing: tiered (background 1px, top regions 3-6px)
- [ ] Fix `GalaxyAtlas.jsx` factions panel: use display names not raw tags
- [ ] Verify visual: `/atlas/Euclid` looks like the mockup (not flat scatter)

### Phase 3 — OG cards + SSR shim
- [ ] Create `posters/VoyagerOG.jsx` (1200×630 condensed)
- [ ] Create `posters/AtlasThumb.jsx` (400×400 simplified)
- [ ] Create `posters/OGSiteCard.jsx` (1200×630 global)
- [ ] Create `posters/OGSystemCard.jsx`
- [ ] Create `posters/OGCommunityCard.jsx`
- [ ] Create `backend/templates/og.html` (Jinja template) OR inline string in ssr.py
- [ ] Create `backend/routes/ssr.py` with SHAREABLE_ROUTES + builders
- [ ] Mount SSR router in control_room_api.py BEFORE SPA static fallback
- [ ] Modify `index.html` default OG → /api/posters/og_site/global.png
- [ ] Validate with Open Graph debugger on `/voyager/turpitzz`, `/atlas/Euclid`, `/systems/{id}`, `/community-stats/Haven`

### Phase 4 — UI integration
- [ ] Find galaxy-card component in Systems page (locate exact file)
- [ ] Replace galaxy card visual with `<img src="/api/posters/atlas_thumb/{galaxy}.png">` + link to /atlas/:galaxy
- [ ] Modify `Profile.jsx`: add "Your Voyager Card" section (PNG embed + 4 buttons + opt-out toggle)
- [ ] Modify `SystemDetail.jsx`: "Discovered by" → Link to voyager card
- [ ] Modify `CommunityStats.jsx`: contributor names → Link
- [ ] Modify `CommunityDetail.jsx`: contributor names → Link
- [ ] Modify `Analytics.jsx`: contributor/submitter names → Link
- [ ] Modify `PartnerAnalytics.jsx`: contributor/submitter names → Link
- [ ] Modify `LeaderboardTable.jsx`: username cell → Link

### Phase 5 — Discord bot
- [ ] Create `The_Keeper/cmds/voyager.py` with /fingerprint and /atlas
- [ ] Add 10s cooldown decorator
- [ ] Add galaxy autocomplete (popular list + dynamic fallback)
- [ ] Modify `The_Keeper/bot.py`: add `"cmds.voyager"` to COGS

### Phase 6 — Cache invalidation hooks + cron
- [ ] Modify `routes/approvals.py::approve_system` to invalidate voyager + atlas
- [ ] Modify `routes/approvals.py::batch_approve_systems` to invalidate voyager + atlas
- [ ] Modify `routes/regions.py` (region name approval) to invalidate atlas
- [ ] Set up `/schedule` weekly poster warmup (Sunday 4am ET)
- [ ] Document the schedule in this plan doc

### Phase 7 — Verification + smoke + production
- [ ] Backend curl: all aggregator endpoints return well-formed JSON
- [ ] Backend curl: `/api/posters/{type}/{key}.png` returns valid PNG with correct dimensions
- [ ] Backend test: 2nd request hits cache (<100ms)
- [ ] Backend test: manual refresh works
- [ ] Backend test: approval invalidates correct cache rows
- [ ] Frontend smoke: `/voyager/turpitzz` renders, no console errors
- [ ] Frontend smoke: `/atlas/Euclid` matches mockup quality
- [ ] Frontend smoke: `/profile` embedded card works
- [ ] Frontend smoke: galaxy thumbnails on Systems tab work
- [ ] Frontend smoke: contributor name cross-links work
- [ ] OG debugger validates each share route
- [ ] Bot test: `/fingerprint` and `/atlas` work locally if bot can be tested
- [ ] Build frontend: `npm run build`
- [ ] Restart server: `python Haven-UI/server.py`
- [ ] Hand off to Parker for browser walk-through

---

## Open watchpoints

These are things I (Claude) need to be careful about. Re-read at the start of each phase.

1. **Playwright on Pi 5.** `playwright install chromium` downloads ~150MB. RAM impact: ~200MB resident for the persistent browser. Verify the Pi can handle it before deploying. Local dev (Windows) should be fine.

2. **SSR shim mount priority.** FastAPI route order matters. If the SPA static fallback catches `/voyager/:user` before `routes/ssr.py` does, scrapers see the SPA's static OG tags and the per-route override never fires. Mount SSR router **first** in startup sequence.

3. **Browser cache vs. PNG cache.** `Cache-Control` headers on `/api/posters/...png` need a sensible TTL (e.g., `max-age=300, must-revalidate`). Aggressive browser caching defeats event-driven invalidation. Use `?v={version}` query string trick for hard busting if needed.

4. **`window.__POSTER_READY` gate.** If a poster errors before setting the flag, Playwright hangs until 15s timeout. EVERY poster component must set the flag in both success and error paths.

5. **Atlas projection.** NMS galaxy is 4096×256×4096. Stars are NOT centered uniformly — the galactic core is dense, edges sparse. A linear projection of `region_x` to viewport will look wrong. Center on (2048, 2048) AND apply a slight visual correction (e.g., logarithmic radial scaling) if needed.

6. **Display tag names.** `/api/discord_tag_colors` returns `{tag: {color, name}}`. The `name` field MAY be missing for some tags. Fallback chain: `name` → `tag` → "Unknown". Test with a galaxy that has `personal` tag and `Personal` tag to verify case-folding works.

7. **First-charted vs first-submission discrepancy.** Voyager fingerprint endpoint currently uses two sources. Don't change without explicit decision.

8. **Discord scrapers don't run JS.** The SSR shim returns HTML that real browsers re-mount the SPA over. Test in Chrome incognito to verify the JS-redirect works without race conditions.

9. **Username normalization parity.** The frontend `normalizeUsernameForUrl()` must produce the SAME output as the backend's normalization. If they diverge, share links break. Test: `TurpitZz#9999` should yield `turpitzz` from both.

10. **The mockup's region picker.** Re-read Option C above before starting. Don't re-revert to "top N by count."

11. **Two zip variants for The_Keeper.** The bot lives at `C:\Master-Haven\The_Keeper\` (per memory). Don't accidentally edit the abandoned `keeper-discord-bot-main/` directory.

12. **`poster_cache` table schema lock.** Migration v1.70.0 already shipped. Don't re-create or alter without a new migration.

13. **Photo URL pattern.** `Haven-UI/src/utils/api.js::getPhotoUrl` and `getThumbnailUrl` show how to build asset URLs that work in both dev (`/photos/...`) and prod (`/haven-ui-photos/...`). The poster URL helpers should mirror this pattern: `/api/posters/...` works the same in both modes.

---

## Reference data

### Galaxy projection helpful constants
```
NMS galaxy bounds: (region_x: 0-4096, region_y: 0-256, region_z: 0-4096)
Galactic center:   (2048, 128, 2048)
Useful galaxies for testing (active in our DB):
  Euclid (most data, 9,687 stars, 16+ civs)
  Hilbert Dimension (~1k stars)
  Eissentam (sparse, good for low-data fallback test)
  Calypso, Hesperius Dimension, Aptarkaba, Budullangr (mid-range)
```

### Existing endpoint signatures (input → output shape)
```
GET /api/public/voyager-fingerprint?username=X
  → { username, poster_public, first_submission, last_submission,
      primary_community: {name, systems, pct_of_community, manual,
                          extractor, rank},
      totals: {systems, manual, extractor, communities, global_rank},
      galaxy_reach: [{galaxy, systems}],
      lifeforms: [{name, systems, pct}],
      inhabited_systems, named_regions,
      top_regions: [{name, systems}],
      first_charted: {name, region, galaxy, charted_at},
      completeness: {avg_score, grade, grade_s/a/b/c} }

GET /api/public/galaxy-atlas?galaxy=X&reality=Y
  → { galaxy, reality, total_systems, total_regions,
      total_named_regions, total_factions,
      regions: [{region_x, region_y, region_z, region_name,
                 system_count, dominant_tag, tag_breakdown,
                 cx, cy, cz, index_number?}],
      named_regions: [...same with index_number 1-9],
      factions: [{tag, systems}] }
  ← Phase 2 changes:
    + display_name on factions
    + named_regions uses Option C picker (faction-first + spatial dedup)
    + dedupe Personal/personal case-insensitively

GET /api/discord_tag_colors
  → { Haven: {color: "#06b6d4", name: "Haven"},
      GHUB: {color: "#5b21b6", name: "Galactic Hub"}, ... }
```

### Registry shape (target)
```python
@dataclass
class PosterTemplate:
    type: str
    version: int
    width: int
    height: int
    spa_route: str           # path Playwright opens
    ttl_hours: int
    public: bool = True
    requires_opt_in_check: bool = False  # voyager only
    cache_key_validator: Optional[Callable[[str], bool]] = None

REGISTRY = {
    "voyager":      PosterTemplate(type="voyager",      version=1, width=680,  height=1040, spa_route="/poster/voyager/{key}",      ttl_hours=24,  requires_opt_in_check=True),
    "voyager_og":   PosterTemplate(type="voyager_og",   version=1, width=1200, height=630,  spa_route="/poster/voyager_og/{key}",   ttl_hours=24,  requires_opt_in_check=True),
    "atlas":        PosterTemplate(type="atlas",        version=1, width=680,  height=920,  spa_route="/poster/atlas/{key}",        ttl_hours=24),
    "atlas_thumb":  PosterTemplate(type="atlas_thumb",  version=1, width=400,  height=400,  spa_route="/poster/atlas_thumb/{key}",  ttl_hours=24),
    "og_site":      PosterTemplate(type="og_site",      version=1, width=1200, height=630,  spa_route="/poster/og_site/global",     ttl_hours=168),
    "og_system":    PosterTemplate(type="og_system",    version=1, width=1200, height=630,  spa_route="/poster/og_system/{key}",    ttl_hours=24),
    "og_community": PosterTemplate(type="og_community", version=1, width=1200, height=630,  spa_route="/poster/og_community/{key}", ttl_hours=24),
}
```

### Reference key normalizer (frontend, mirrors backend)
```javascript
// posters/_shared/identity.js
export function normalizeUsernameForUrl(name) {
  if (!name) return ''
  let clean = name.replace(/#/g, '').trim()
  // Strip trailing 4-digit Discord discriminator
  if (clean.length > 4 &&
      /^\d{4}$/.test(clean.slice(-4)) &&
      (clean.length === 4 || !/^\d$/.test(clean.charAt(clean.length - 5)))) {
    clean = clean.slice(0, -4)
  }
  return clean.toLowerCase().trim()
}
// Test: 'TurpitZz#9999' → 'turpitzz'
//       'Parker1920'    → 'parker'    (4-digit suffix stripped)
//       'X1234567'      → 'x1234567'  (no leading non-digit before suffix)
```

---

## Build invariants (do not violate)

1. **Adding a new poster type must be:** registry entry + React component. Nothing else.
2. **Every poster component must set `window.__POSTER_READY = true`** in both success and error paths.
3. **The PNG endpoint is the single share-source.** The bot, OG embeds, in-UI embeds, and direct shares all hit the same URL.
4. **Cache invalidation is event-driven first, TTL second.** If a system gets approved, the affected cache must drop within seconds.
5. **No commits until Parker has visually verified in browser.**
6. **If a phase blocks: stop, document, ask. Never improvise around the spec.**
7. **Re-read the "Open watchpoints" section at the start of every phase.**

---

## Phase status tracker

(Update as phases complete.)

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| 1 — Foundation | ⏸ pending approval | – | – | |
| 2 — Refactor + visual fix | ⏸ pending | – | – | |
| 3 — OG cards + SSR shim | ⏸ pending | – | – | |
| 4 — UI integration | ⏸ pending | – | – | |
| 5 — Discord bot | ⏸ pending | – | – | |
| 6 — Cache invalidation + cron | ⏸ pending | – | – | |
| 7 — Verification + production | ⏸ pending | – | – | |

---

## Glossary

- **Poster** — any rendered visual artifact: voyager card, galaxy atlas, OG card, etc.
- **Type** — registry key: `voyager`, `atlas`, `og_site`, etc.
- **Key** — instance identifier: `turpitzz`, `Euclid`, `global`, `42`
- **Render** — the act of opening a poster route in headless Playwright and screenshotting
- **Cache hit** — `poster_cache` row exists, file on disk, no invalidation flag → serve directly
- **Cache miss** — no row, file missing, or hash differs → render fresh, write cache
- **Invalidation** — drop poster_cache row + delete file → next request renders fresh
- **OG SSR shim** — small FastAPI route that emits OG meta tags before the SPA fallback catches the URL
- **Friendly URL** — user-facing share URL: `/voyager/:user`, `/atlas/:galaxy`
- **Renderer URL** — internal URL Playwright opens: `/poster/:type/:key`. Same components, no chrome, lighter mount.
- **POSTER_READY** — JavaScript flag set on `window` once a poster has finished fetching data and rendering. Hook for headless screenshot timing.
- **Option C** — atlas region picker: faction-first with spatial deduplication. Locked decision.
