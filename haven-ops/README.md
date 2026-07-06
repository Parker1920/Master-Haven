# Haven Ops

Internal record-keeping app for **Voyager's Haven LLC** — engagements,
papertrail, ledger, registry, compliance, and the emitted Project
Instructions doc. Tailscale-internal, single container, port **8090**.
No public DNS, no NPM exposure, no login in Phase 1 (the tailnet is the
perimeter; the auth seam is `backend/app/auth.py`).

**Design contract:** `haven-ops-mockup-v0_7.html` — the frontend ports it 1:1.
⚠ The mockup file itself embeds the e-signature as base64 — keep it OUT of
this repo (reference it from Downloads/archive only).

## Stack

- **Backend:** FastAPI + SQLModel + SQLite (WAL + `busy_timeout` + FKs ON),
  pydantic-settings, Jinja2, WeasyPrint (PDF freeze).
- **Frontend:** React 18 + Vite, no Tailwind — the mockup's CSS tokens are
  used directly. FastAPI serves the built bundle; one origin, no CORS.
- **Migrations:** plain versioned `.sql` in `backend/app/migrations/`,
  tracked in a `schema_version` table. No Alembic.

## Data dir (never in the repo)

All state lives outside the repo in a data dir mounted at `/data`:

| Path | Contents |
|---|---|
| `haven-ops.db` (+ `-wal`, `-shm`) | the database |
| `uploads/generated/` | frozen generated PDFs |
| `signature.png` | Parker's e-signature — placed by hand, never committed |
| `.env` | runtime secrets/config |

- **Pi:** `~/docker/haven-ops-data/` (sibling of the repo clone — the compose
  default `../haven-ops-data` resolves to it).
- **Local dev:** `C:/Users/parke/docker/haven-ops-data` — set via
  `HAVEN_OPS_DATA` in the repo-local `.env` (see `.env.example`).

## Run locally (Docker)

```sh
cp .env.example .env        # set HAVEN_OPS_DATA for your machine
docker compose up --build
# → http://localhost:8090          (frontend shell)
# → http://localhost:8090/api/health  → {"ok": true}
# → http://localhost:8090/docs     (FastAPI docs)
```

## Migrations & seed

- Schema lives in `backend/app/migrations/NNN_*.sql`, applied in filename
  order and tracked in `schema_version` (each migration + its version row
  commit atomically). Never edit a shipped migration — add a new file.
- `python -m app.migrate` / `python -m app.seed` run them manually
  (inside the container: `docker compose exec haven-ops python -m app.migrate`).
- **Both also run automatically at app startup** and are idempotent: the
  seed only fills tables that are empty, so it never touches live data.

## API (Stage 2)

Interactive docs at `/docs`. Everything sits behind the auth seam
(`backend/app/auth.py`, a Phase 1 no-op); every create/update/delete writes
an `activity_log` row that commits atomically with the change.

| Route | Notes |
|---|---|
| `GET/PUT /api/company` · `GET /api/company/signature` | singleton; signature streamed from the data dir, never bundled |
| `/api/people` `/api/initiatives` `/api/environment` `/api/flags` `/api/clients` `/api/tasks` `/api/compliance` `/api/accounts` `/api/transactions` `/api/assets` `/api/templates` | full CRUD |
| `GET/POST /api/engagements` · `GET/PUT /api/engagements/{id}` | list/detail include client + live `missing_docs` |
| `GET/POST /api/engagements/{id}/events` | papertrail — **append-only**, ordered by id |
| `GET /api/engagements/{id}/documents` | docs + required + missing (the record-gap check) |
| `POST /api/engagements/{id}/documents` `{doc_type}` | generate → **freeze** (sha256, new version per re-issue, never overwritten); signature stamped on sow/completion/receipt |
| `GET /api/documents` · `GET /api/documents/{id}/file` | global list + file serving — inline by default (viewable), `?dl=1` = download |
| `POST /api/documents/upload` | multipart: create a new frozen record from a real file (governance PDFs, signed copies…) |
| `POST /api/documents/{id}/file` | attach the real file to a file-less record, once — fixing a wrong attach = new upload |
| `DELETE /api/documents/{id}` | **uploaded, unreferenced records only** — generated/seed rows are permanent |
| `POST /api/assets/{id}/receipt` | multipart: receipt scan → linked to the asset (the Itemize workflow) |
| `POST /api/engagements/{id}/advance` | forward-only stage move; appends the papertrail event, stamps closed_at |
| `GET /api/emit/project-instructions` | Part A (durable) + Part B (live from tables), `text/markdown` |
| `POST /api/hooks/inquiry` · `POST /api/hooks/payment` | **site → Ops relays** (voyagershaven.online backend only): inquiry → client + engagement + frozen intake; settled payment → ledger transaction + auto-receipt when the invoice number names a `VHAV-C-` code. Gated by `X-Ops-Token` = `OPS_SERVICE_TOKEN` (unset = 503) |

## Run bare (no Docker, for backend iteration)

```sh
cd frontend && npm install && npm run dev     # Vite on :5173, proxies /api → :8090
cd backend && pip install -r requirements.txt
uvicorn app.main:app --port 8090 --reload     # data dir defaults to ~/docker/haven-ops-data
```

## Backups

The DB is WAL-mode — **never raw-`cp` it** (a copy taken mid-write is
corrupt). Snapshot with `sqlite3 haven-ops.db ".backup '<dest>'"` plus a
mirror of the `uploads/` tree (frozen PDFs never change; new files only).

Ready-to-paste block for the Pi's existing `/usr/local/bin/backup-haven.sh`:
[deploy/backup-haven-ops.snippet.sh](deploy/backup-haven-ops.snippet.sh) —
reuses that script's `$BACKUP_DIR`/`$DATE` and its 7-day `*.db` retention.

## Deploy to the Pi (checklist — Parker runs this, never the agent)

1. `mkdir -p ~/docker/haven-ops-data/uploads/generated` on the Pi.
2. Place `signature.png` and (if needed) `.env` into `~/docker/haven-ops-data/`
   **by hand** — they never enter the repo.
3. Clone/pull the repo to `~/docker/haven-ops` (data dir is then the sibling
   the compose default `../haven-ops-data` expects).
4. `docker compose up -d --build` — startup migrates + seeds an empty DB
   automatically; check `docker logs haven-ops` for the `[migrate]`/`[seed]`
   lines and `docker ps` for `(healthy)`.
5. **Do NOT add an NPM/Cloudflare route** — port 8090 stays tailnet-internal;
   the tailnet is the security perimeter (auth tiers come post-Phase-1).
6. Append [deploy/backup-haven-ops.snippet.sh](deploy/backup-haven-ops.snippet.sh)
   to `/usr/local/bin/backup-haven.sh`.
7. Open `http://<pi-tailscale-ip>:8090` from a tailnet device; on the Company
   screen confirm the e-signature renders (proves the data-dir mount + file).
8. **Site relay (voyagershaven.online → Ops):** copy
   [deploy/docker-compose.pi.override.yml](deploy/docker-compose.pi.override.yml)
   to `docker-compose.override.yml` beside the compose file on the Pi (joins
   `docker_default` so the site container can reach `haven-ops:8090`
   server-to-server — NPM must still NEVER route to haven-ops). Set
   `OPS_SERVICE_TOKEN` in the Ops `.env`, and on the site side set
   `HAVEN_OPS_URL=http://haven-ops:8090` + `HAVEN_OPS_TOKEN=<same token>`.
   Inquiries then auto-open engagements with frozen intake records, and
   settled Stripe payments auto-record transactions + receipts.

## Build stages

| Stage | Scope | Status |
|---|---|---|
| 0 | Scaffold + Docker + health check + shell | ✅ |
| 1 | Schema + migrations + seed | ✅ |
| 2 | API + doc generation (freeze) + emit | ✅ |
| 3 | Frontend port of mockup v0.7, wired to API | ✅ |
| 4 | Compose polish, backup, run notes | ✅ — Phase 1 complete |
| 1.5 | Iterations 1+2: documents real (upload/attach/view), every register editable, lifecycle + ledger ops | ✅ this commit |
