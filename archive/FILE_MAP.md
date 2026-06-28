# Travelers Archive — File Directory & Architecture Map

> A guide for anyone new to this codebase (hi Stars 👋). It explains **what every file
> does** and **what files talk to / share data with what**. Read the "Big Picture" and
> "How a request flows" sections first — the per-file directories below are reference.

**What this project is:** `haven-archive.online` — a No Man's Sky community archive. It's
four things in one app: a **news room** (briefs + features), a **civilizations
encyclopedia**, long-form **inquisitions** (historical investigations), and a **catalogue**
(a faceted wiki). It pulls live community stats from the main Haven site.

---

## 1. The Big Picture

```
                          ┌──────────────────────────────────────────┐
   Browser                │              ONE Docker container          │
 ┌─────────┐   HTTPS      │  ┌─────────────────────────────────────┐  │
 │ React   │ ───────────► │  │  FastAPI  (app/main.py, port 8020)  │  │
 │  SPA    │ ◄─────────── │  │   • serves the built React SPA at / │  │
 └─────────┘   JSON       │  │   • serves the API at /api/v1/*     │  │
      ▲                   │  └──────────────┬──────────────────────┘  │
      │                   │                 │                         │
      │ built by Vite     │                 ▼                         │
      │ and baked into    │        ┌────────────────┐                │
      │ the image at      │        │ SQLite DB      │  /data/archive.db
      │ /app/frontend_dist│        │ + media files  │  /data/media/   │
      │                   │        └────────────────┘                │
      └───────────────────┤                 ▲                         │
                          │      background job every 30 min          │
                          │                 │                         │
                          └─────────────────┼─────────────────────────┘
                                            │ HTTP
                                            ▼
                            Main Haven API (http://haven:8005)
                            /api/public/community-overview
```

**Two halves, one container.** The **frontend** (`frontend/`, React + TypeScript + Vite) is
built into static files during the Docker image build and copied into the Python image. The
**backend** (`app/`, FastAPI + SQLite) serves both the API *and* those static files. There
is no separate web server for the frontend in production — FastAPI does both.

**The single bridge between them** is `frontend/src/api/client.ts`. Every piece of data the
frontend shows comes through that one file calling the backend's `/api/v1/*` endpoints. If
you want to know "how does the frontend get X," the answer is always: a page/component calls
a function in `client.ts`, which calls a route in `app/routes/`.

**Tech stack at a glance**
| Layer | Tech | Where |
|-------|------|-------|
| Frontend | React 18, TypeScript, Vite (hash router, hand-written CSS, no UI framework) | `frontend/` |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic 2 | `app/` |
| Database | SQLite (single file, on the Pi — **not** in the repo) | `/data/archive.db` |
| Migrations | Alembic | `alembic/` |
| Background jobs | APScheduler | `app/jobs/`, `app/services/haven_sync.py` |
| Container | Multi-stage Docker (Node build → Python runtime) | `Dockerfile`, `docker-compose.yml` |

---

## 2. How a request flows (the "what talks to what" story)

**Reading a page (e.g. opening a civilization):**
1. Browser loads the SPA shell (`index.html` → `src/main.tsx` → `src/App.tsx`).
2. `src/router.tsx` reads the URL hash (`#/civ/everion`) and picks the page `pages/CivPage.tsx`.
3. `CivPage.tsx` calls `api('/civilizations/everion')` in `src/api/client.ts`.
4. `client.ts` does `fetch('/api/v1/civilizations/everion', {credentials})`.
5. FastAPI routes it to `app/routes/civilizations.py`.
6. That route uses `app/db.py` (database session) + `app/deps.py` (who's logged in?) and reads
   the `civilization` table, plus live figures via `app/services/haven_sync.py`.
7. The response is shaped by a Pydantic model in `app/models/schemas.py`, wrapped in an
   `{data, meta}` envelope, and sent back. `client.ts` unwraps it; `CivPage.tsx` renders it.

**Writing content (e.g. publishing a draft):** the same path, but write routes also call the
**cross-cutting helpers**: `app/audit.py` (log the action), `app/revisions.py` (snapshot the
old version), and `app/notifications.py` (tell watchers/co-authors). Those three helpers are
called by *many* routes — they're the shared "side-effect" layer.

**Live Haven stats:** independent of any request. A background scheduler in `app/main.py`
runs `app/services/haven_sync.py` every 30 min, which HTTP-fetches the main Haven API and
caches the numbers into the `atlas_*` tables. Routes then read those cached tables — they
never call Haven directly during a user request.

---

## 3. Backend directory — `app/`

### Core / wiring
| File | What it does | Talks to |
|------|--------------|----------|
| `main.py` | **The entrypoint.** Builds the FastAPI app, mounts every route module, serves the built SPA, mounts `/media`, and starts the Haven-sync background scheduler. | Imports every `routes/*`, `auth_dev`, `auth_claim`, `config`, `services/haven_sync` |
| `config.py` | Loads all settings from env vars (`DATABASE_PATH`, `SESSION_SECRET`, Discord creds, Haven sync config) into one `Settings` object via `get_settings()`. | Read by nearly everything |
| `db.py` | SQLAlchemy engine + session factory for SQLite. Exposes `get_db()` (FastAPI dependency every route uses) and `session_scope()` (for background jobs). Turns on foreign keys + WAL. | Used by every route, job, service |
| `deps.py` | **Auth & permissions.** Reads the signed session cookie, loads the current user, and the role gates: `require_login`, `require_team_role`, `require_historian_or_higher`, `require_editor`, `require_admin`, etc. | Reads `archive_user`; used by every protected route |
| `__init__.py` | Package version string (`__version__`). | — |

### Auth
| File | What it does | Talks to |
|------|--------------|----------|
| `auth_claim.py` | Username/password login (the real login). `POST /api/v1/auth/claim`, set/clear password. First admin auto-promotes on claim. | `passwords`, `audit`, `archive_user` |
| `auth_dev.py` | **Dev-only** fake login — pick a seeded persona, no password. Returns 404 in production. | `archive_user` |
| `auth_discord.py` | Discord OAuth — **stub / placeholder** (planned Phase 7). | (not implemented yet) |
| `routes/auth.py` | Shared auth endpoints: `GET /me`, `PATCH /me` (edit own profile), `POST /logout`. | `deps`, `audit`, `person` |
| `passwords.py` | PBKDF2 password hashing + constant-time verify. | used by `auth_claim` |

### Cross-cutting helpers (shared "side-effect" layer — called by many routes)
| File | What it does | Talks to |
|------|--------------|----------|
| `audit.py` | `log_audit(...)` — writes an entry to `audit_log` for every meaningful action. | `audit_log` |
| `revisions.py` | `record_revision(...)` — saves a JSON snapshot of a civ/person/event/place before edits (wiki-style history). | `entity_revision` |
| `notifications.py` | `notify_*()` helpers — fan-out notifications on draft state changes, comments (@mentions), watchlist updates. | `notification`, `watchlist`, `archive_user` |
| `facets.py` | Single source of truth for **catalogue filter schemas** (which filters each article namespace has). | used by `routes/articles`, `routes/timeline` |
| `namespaces.py` | Registry of catalogue namespaces (which are writable articles vs the civ table vs Haven-synced). | used by `routes/articles` |

### Models
| File | What it does |
|------|--------------|
| `models/schemas.py` | **All Pydantic request/response shapes.** `Envelope[T]` (the `{data, meta}` wrapper), plus `CivilizationDetail`, `StorySummary`, `DraftDetail`, `ArticleDetail`, etc. The contract the frontend's TypeScript interfaces mirror. |
| `models/__init__.py` | Placeholder. |

### Services & jobs
| File | What it does | Talks to |
|------|--------------|----------|
| `services/haven_sync.py` | **The bridge to the main Haven site.** `sync_haven_atlas()` HTTP-fetches `/api/public/community-overview`, caches per-civ + global stats. `lookup_atlas_stats()` resolves one civ's live figures. Read-only, defensive against Haven downtime. | Haven API → `atlas_community_stat`, `atlas_summary`, `haven_sync_run` |
| `jobs/discord_sync.py` | Discord role sync — **stub** (Phase 7). | (planned) |
| `jobs/source_check.py` | Source-URL validation — **stub** (future). | (planned) |

### Seeds (one-off data loaders, run by hand)
| File | What it does |
|------|--------------|
| `seed.py` | Mock dev data (personas, civs, stories, inquisitions). `python -m app.seed` |
| `seed_catalogue.py` | Small real NMS reference articles with facets. `python -m app.seed_catalogue` |
| `seed_partners.py` | The ~171 Voyager's Haven partner civilizations. `python -m app.seed_partners --force` |
| `seed_partner_stories.py` | Auto-generated briefs/features from civ metadata. `python -m app.seed_partner_stories --force` |

### Routes — `app/routes/` (one module per resource)
Every module exposes a `router` mounted by `main.py`. All use `db` + `deps` + `schemas`; the
**Extra** column lists the notable cross-cutting helpers each one also calls.

| File | URL prefix | What it serves | Main tables | Extra |
|------|-----------|----------------|-------------|-------|
| `admin.py` | `/api/v1/admin` | Audit log viewer; user role/civ management (admin only). | `audit_log`, `archive_user` | audit |
| `articles.py` | `/api/v1/articles` | The catalogue/wiki: list, namespaces, facet schemas, CRUD. | `article`, `article_facet`, `source_citation` | facets, namespaces, audit |
| `atlas.py` | `/api/v1/atlas` | Live Haven stats: global summary, sync status, force-sync. | `atlas_*` | haven_sync |
| `beats.py` | `/api/v1/beats` | Editorial sections (story beat tags) + their stories. | `story` | — |
| `civilizations.py` | `/api/v1/civilizations` | Civ encyclopedia: list, detail + live atlas figures, coverage, revisions, CRUD. | `civilization`, `entity_revision`, `*_civilization` joins | audit, revisions, notifications, haven_sync |
| `comments.py` | `/api/v1/drafts/{id}/comments` | Draft comments (inline-quoted or doc-level); parses @mentions. | `draft_comment` | notifications, audit |
| `drafts.py` | `/api/v1/drafts` | **The editorial workflow.** Create/auto-save WIP, submit → review → return/ready → publish (into a story or inquisition), co-authors. | `draft`, `draft_coauthor`, `story`, `inquisition` | audit, notifications |
| `events.py` | `/api/v1/events` | Timeline events: list, detail, revisions, CRUD. | `event`, `entity_revision` | audit, revisions, notifications |
| `inquisitions.py` | `/api/v1/inquisitions` | Long-form investigations: list, detail, lifecycle patches. | `inquisition`, `inquisition_author/_civilization`, `source_citation` | audit, notifications |
| `media.py` | `/api/v1/media` | Image upload (10 MB limit, image types) + metadata. Files served from the `/media` mount. | `media_asset` + filesystem `/data/media` | audit |
| `notifications.py` | `/api/v1/notifications` | Per-user inbox: list, unread count, mark read. | `notification` | — |
| `people.py` | `/api/v1/people` | Person encyclopedia: list, detail, revisions, CRUD. | `person`, `entity_revision` | audit, revisions, notifications |
| `places.py` | `/api/v1/places` | Galactic locations: list, detail, revisions, CRUD. | `place`, `entity_revision` | audit, revisions, notifications |
| `revisions.py` | `/api/v1/revisions` | Generic "history of any entity" reader. | `entity_revision` | — |
| `search.py` | `/api/v1/search` | Cross-content search (stories, inquisitions, civs, people). | those 4 tables | — |
| `sources.py` | `/api/v1/sources` | External references + citations (attach a source to anything). | `source`, `source_citation` | audit |
| `stories.py` | `/api/v1/stories` | Published briefs/features (writes happen via drafts→publish). | `story`, `story_civilization` | audit |
| `timeline.py` | `/api/v1/timeline` | Merged master timeline (events + stories + inquisitions + civ founding). | several | facets |
| `users.py` | `/api/v1/users` | User search (for the co-author picker). | `archive_user` | — |
| `watchlist.py` | `/api/v1/watchlist` | Per-user follow list for entities/inquisitions. | `watchlist` | — |

---

## 4. Frontend directory — `frontend/`

### Entry / wiring
| File | What it does |
|------|--------------|
| `index.html` | HTML shell; mounts the app into `#root`, loads `src/main.tsx`, holds Open Graph share tags. |
| `src/main.tsx` | Vite entry — renders `App` into `#root`, imports the two CSS files. |
| `src/App.tsx` | **Top-level shell.** Renders nav (desktop + mobile drawer), the current page (via the router), the toast, and the dev panel. Uses `useAuth()` for the logged-in pill. |
| `src/router.tsx` | **Hash router.** Parses `window.location.hash` into a typed route, exports `useRoute()` and `navigate(path)`. Maps every `#/...` URL to a page. |
| `package.json` / `vite.config.ts` / `tsconfig.json` | Build config. Dev server on 5173 proxies `/api/*` to the backend on 8020; production build outputs to `dist/` (baked into the Docker image). |

### The API bridge + hooks  ← **the most important frontend files to understand**
| File | What it does |
|------|--------------|
| `src/api/client.ts` | **The one and only door to the backend.** `api<T>()`, `apiRaw<T>()`, `apiUpload()`. Sends the session cookie with every request, unwraps the `{data, meta}` envelope, throws `ApiError` on failure. Also holds all the TypeScript interfaces mirroring the backend's Pydantic schemas. **Every page/component that needs data imports from here.** |
| `src/hooks/useAuth.ts` | Singleton "who am I" hook — caches `GET /auth/me`, broadcasts changes, exposes `refresh()` + `logoutClient()`. |
| `src/hooks/useToast.ts` | Singleton toast bus — `showToast(msg)` used everywhere for save/error feedback. |
| `src/data/namespaces.ts` | Frontend display metadata for catalogue namespaces (icons, groupings, labels). The display-side mirror of the backend's `namespaces.py`. |

### Pages — `frontend/src/pages/` (route → page → API)
| Page | Route | Calls (via `client.ts`) |
|------|-------|--------------------------|
| `Newsroom.tsx` | `#/` (home) | atlas summary, stories, inquisitions, articles |
| `Catalogue.tsx` | `#/catalogue` | article namespace counts |
| `Browse.tsx` | `#/browse/{namespace}` | `/articles?namespace=…&facets`, `/articles/facets/{ns}` |
| `Article.tsx` | `#/wiki/{slug}` | `/articles/{slug}` (+ edit/delete) |
| `ArticleNew.tsx` | `#/new-article` | `POST /articles` |
| `Civs.tsx` / `CivPage.tsx` | `#/civs`, `#/civ/{slug}` | `/civilizations…`, `/civilizations/{slug}/coverage` |
| `Inquisitions.tsx` / `InquisitionPage.tsx` | `#/inquisitions`, `#/inquisition/{id}` | `/inquisitions…` |
| `Beats.tsx` / `BeatPage.tsx` | `#/beats`, `#/beat/{slug}` | `/beats…` |
| `Story.tsx` | `#/story/{id-or-slug}` | `/stories/{id}` or `/stories/by-slug/{slug}` |
| `People.tsx` / `PersonPage.tsx` | `#/people`, `#/person/{slug}` | `/people…` |
| `Places.tsx` / `PlacePage.tsx` | `#/places`, `#/place/{slug}` | `/places…` |
| `Events.tsx` / `EventPage.tsx` | `#/events`, `#/event/{slug}` | `/events…` |
| `Timeline.tsx` | `#/timeline` | `/timeline`, `/civilizations` |
| `Search.tsx` | `#/search?q=…` | `/search?q=` |
| `Compose.tsx` | `#/compose/{doctype}` | `POST /drafts` |
| `Drafts.tsx` / `Draft.tsx` | `#/drafts`, `#/draft/{id}` | `/drafts…`, comments, coauthors, revisions, sources |
| `Dashboard.tsx` | `#/dashboard` | notifications, quick actions |
| `Watchlist.tsx` | `#/watchlist` | `/watchlist…` |
| `Profile.tsx` | `#/profile/{slug}` | `/people/{slug}`, `PATCH /auth/me` |
| `Login.tsx` | `#/login` | `POST /auth/claim` |
| `Admin.tsx` | `#/admin` | `/admin/users`, `/admin/audit_log` |

### Components — `frontend/src/components/`
Reusable UI pieces. The ones that **call the API themselves** are flagged; the rest are
presentational (fed data by their parent page).

| Component | Purpose | Calls API? |
|-----------|---------|-----------|
| `ArticleCard`, `CivCard`, `StoryCard`, `InquisitionCard`, `DraftRow` | List/result cards | no (presentational) |
| `ArticleForm` | Create/edit a catalogue article (fields, infobox, sources, facets) | loads facet schema |
| `CivPicker` | Multi-select civ tagger (cached civ list) | `GET /civilizations` |
| `FacetControl` / `FilterRail` | Catalogue filter inputs / sidebar | `FilterRail` loads facet schema |
| `CataloguePortal` | Namespace tile grid / spine | `GET /articles/namespaces` |
| `SearchBar` / `UserSearch` | Nav search / co-author typeahead | `GET /search` |
| `NotificationBell` | Unread badge (polls every 60s) | `GET /notifications/count` |
| `MediaUpload` | Drag-drop image upload | `POST /media` |
| `SourcesList` | View/add citations on a target | `/sources/for/…`, citations |
| `RevisionHistory` | Collapsible edit history | `GET /revisions/…` |
| `WatchButton` | Follow/unfollow toggle | `/watchlist…` |
| `PasswordPrompt` | Set/change password inline | `POST /auth/set-password` |
| `DevPanel` | Dev-only persona switcher | `/auth/dev/*` |
| `Avatar`, `Tag`, `StatusPill`, `Loading`, `Toast`, `Drawer`, `ProseBody` | Small shared UI (avatars, chips, spinner, toast, mobile menu, markdown renderer) | no |

### Styles
| File | What it styles |
|------|----------------|
| `src/styles/global.css` | The whole design system (purple-void + teal cosmic theme, `ta-*` classes, fonts, nav, cards, modals). |
| `src/styles/catalogue.css` | The catalogue/wiki half only (`ta-cat-*` classes, per-namespace accent colors). |

---

## 5. Database — the data model that ties it all together

The SQLite DB lives **only on the Pi** (`~/docker/archive-data/archive.db`), never in the
repo. The schema is created by Alembic migration `0001` from `sql/initial_schema.sql`, then
evolved by later migrations.

### Tables by domain
- **Users / auth:** `archive_user` (people who log in; roles, password, suspend flag), `discord_sync_log`
- **Encyclopedia (versioned):** `civilization`, `person`, `event`, `place`, and `entity_revision` (history snapshots for all four)
- **News:** `story` + `story_civilization` (which civs a story is about)
- **Inquisitions:** `inquisition` + `inquisition_author` + `inquisition_civilization`
- **Editorial workflow:** `draft` + `draft_coauthor` + `draft_civilization` + `draft_comment`
- **Catalogue/wiki:** `article` + `article_facet` (one row per filterable attribute)
- **Engagement:** `notification`, `watchlist`
- **Media:** `media_asset` + `media_attachment` (attach an image to anything)
- **Sources:** `source` + `source_citation` (cite a source on anything)
- **Audit:** `audit_log`
- **Haven cache (read-only, written by the sync job):** `atlas_community_stat`, `atlas_summary`, `haven_sync_run`

### Key relationships
- **`archive_user` is the hub** — it's the author/creator/editor FK on nearly everything (civs, people, events, places, stories, inquisitions, drafts, comments, media, sources, revisions).
- **draft → published content:** when a draft is published, `draft.published_as_story_id` *or* `draft.published_as_inquisition_id` points to the row it became.
- **Cascade-delete join tables:** `*_civilization`, `*_coauthor`, `*_author`, `draft_comment`, `article_facet`, `source_citation` all delete with their parent.
- **Polymorphic links (no DB foreign key — the app validates `target_type`/`target_id`):** `watchlist`, `media_attachment`, `source_citation`, and `entity_revision` each point at "any entity of type X". When working on these, check the app code for which types are valid — SQLite won't enforce it.

### Migrations — `alembic/versions/`
Run automatically on container start (`entrypoint.sh` → `alembic upgrade head`).
| Rev | Adds |
|-----|------|
| `0001` | Initial 17-table schema (from `sql/initial_schema.sql`). |
| `0002` | Wipes demo data; adds `archive_user.password_hash`. |
| `0003` | Cleans up orphaned stories/inquisitions. |
| `0004` | `archive_user.is_suspended`. |
| `0005` | Haven sync: `civilization.haven_tag` + the three `atlas_*` cache tables. |
| `0006` | `article` table (the catalogue). |
| `0007` | `article_facet` table (catalogue filters). |

---

## 6. Build, deploy & ops

| File | What it does |
|------|--------------|
| `Dockerfile` | **Multi-stage build.** Stage 1 (Node 22): `npm run build` the React app. Stage 2 (Python 3.12): install deps, copy the built SPA to `/app/frontend_dist`, set up the entrypoint. So one image holds both halves; FastAPI serves the SPA. |
| `entrypoint.sh` | On every start: ensure `/data` + `/data/media` exist → `alembic upgrade head` → (optional seed) → launch `uvicorn` on `0.0.0.0:8020`. |
| `docker-compose.yml` | Stand-alone stack (separate from the Pi's master compose). Publishes 8020, bind-mounts `~/docker/archive-data` to `/data`, joins `docker_default` so it can reach the Haven API as `http://haven:8005`. |
| `.env.example` | Template for all env vars (DB path, session secret, Discord creds, Haven sync). Copy to `.env` for local dev. |
| `requirements.txt` | Python deps: FastAPI, Uvicorn, SQLAlchemy, Alembic, Pydantic, APScheduler, Pillow, httpx, itsdangerous. |
| `alembic.ini` / `alembic/env.py` | Alembic config + runtime hook (points migrations at the configured SQLite DB). |
| `scripts/make_og_card.py` | Generates the social share image (`frontend/public/og-card.png`). Run by hand when the design changes. |
| `tests/test_phase4.sh` | End-to-end curl test of the full draft → review → publish workflow. |
| `docs/` | Design references: `v0.9-mockup.html`, `haven-wiki-v0.3.html` (visual contracts), `discord-roles.md`, `wiki-filters.md`, `phase6-npm-setup.md`. |

**State lives outside the repo:** the database and uploaded media are on the Pi only
(`~/docker/archive-data/`). The repo holds **code**, not data.

---

## 7. Where to start (orientation for a new dev)

1. **Run it locally** — follow `README.md` "Local dev" (venv → `pip install -r requirements.txt`
   → `alembic upgrade head` → `uvicorn app.main:app --reload --port 8020`), and in another
   terminal `cd frontend && npm install && npm run dev`. Use the **DevPanel** (bottom corner)
   to log in as a persona without a password.
2. **Read the contract first:** `app/models/schemas.py` (backend shapes) and
   `frontend/src/api/client.ts` (frontend's view of the same shapes). These two files define
   how the halves talk.
3. **Trace one feature end-to-end** using the flow in §2 (e.g. civilizations): `CivPage.tsx`
   → `client.ts` → `routes/civilizations.py` → `db.py` + `schemas.py`. Once one clicks, they
   all follow the same pattern.
4. **To add a new resource:** create `app/routes/<thing>.py` with a `router`, register it in
   `app/main.py`, add its Pydantic schema in `schemas.py`, add a migration in
   `alembic/versions/` for any new table, then add a page in `frontend/src/pages/`, a route
   in `router.tsx`, and the fetch calls in `client.ts`. (`main.py` has edit-friendly notes at
   the top describing exactly this.)
5. **Golden rules of this codebase:**
   - All frontend↔backend traffic goes through `client.ts` ↔ `/api/v1/*`. Don't fetch elsewhere.
   - Write routes should also call `audit.py`, and (for encyclopedia entities) `revisions.py`
     + `notifications.py`. Follow the pattern in `routes/civilizations.py`.
   - Polymorphic tables (`watchlist`, `media_attachment`, `source_citation`, `entity_revision`)
     have no DB foreign keys — the app enforces valid types. Be careful there.
   - The Haven sync is read-only and cached; never call the Haven API inside a request handler.
