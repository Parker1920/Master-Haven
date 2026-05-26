# Grand Festival — Summer Unification Day

Public site + admin for the No Man's Sky mid-year **Summer Unification Day** gathering.
Built from the `summer-ud-mockup.html` design contract per `grand-festival-dispatch-v1.md`.

- **Public site** (5 pages): Main · About · Lore · Who's Going · Sign Up
- **Civ submission**: anyone can submit their civilization (optional logo) → lands in a `pending` queue
- **Admin** (`/admin`): single-password login → review queue, approve/reject, edit, delete, audit log
- **Stack**: FastAPI + SQLite + Pillow (backend) · React 18 + Vite + React Router (frontend). One container serves both.

Only the **civ list** is dynamic. Everything else (copy, attractions, schedule, lore) is in code.

---

## Layout

```
grand-festival/
├── backend/
│   ├── main.py            FastAPI app: /api routes + SPA serving + startup init
│   ├── db.py              SQLite connection + one-time schema/seed
│   ├── schema.sql         civilizations + admin_log tables
│   ├── seed.sql           initial roster (runs only if civilizations is empty)
│   ├── models.py          Pydantic schemas
│   ├── auth.py            single-password cookie sessions (in-memory tokens)
│   ├── images.py          Pillow validation + WebP normalization (≤512px, ≤2MB)
│   ├── serialize.py       row → dict helpers
│   ├── routes/
│   │   ├── public.py      GET /civs, /civs/:id, /uploads/:file, /health
│   │   ├── submit.py      POST /civs/submit  (multipart, optional logo)
│   │   └── admin.py       login/logout, review queue, approve/reject/edit/delete, log
│   ├── requirements.txt
│   └── _smoke_test.py     standalone TestClient regression test (dev only)
├── frontend/
│   ├── src/
│   │   ├── pages/         Main, About, Lore, WhosGoing, SignUp, SubmitCiv, Admin
│   │   ├── components/    Nav, Footer, CivCard
│   │   ├── hooks/         useCountdown
│   │   ├── api.js         fetch wrapper (credentials: include)
│   │   ├── config.js      DISCORD_INVITE_URL, FESTIVAL_TARGET_UTC
│   │   ├── styles.css     design contract — lifted VERBATIM from the mockup
│   │   └── app.css        additive styles for forms / admin / states
│   ├── index.html
│   ├── package.json
│   └── vite.config.js     dev proxy /api → :8000
├── Dockerfile             multi-stage: build frontend → serve via FastAPI
├── docker-compose.yml     standalone service (port 8082 → 8000)
├── .env.example
└── README.md

# Persistent data lives OUTSIDE the repo (host-mounted at /data):
~/docker/grand-festival-data/
├── grand_festival.db
├── uploads/               civ logos (WebP)
└── .env                   real ADMIN_PASSWORD
```

---

## Local development

**Backend** (Python 3.11):
```bash
cd grand-festival/backend
py -3.11 -m venv .venv
./.venv/Scripts/python -m pip install -r requirements.txt   # (Linux/macOS: source .venv/bin/activate)
# run from the package root (grand-festival/) so `backend.main` resolves:
cd ..
ADMIN_PASSWORD=dev GF_COOKIE_SECURE=0 backend/.venv/Scripts/python -m uvicorn backend.main:app --port 8000 --reload
```

**Frontend** (hot reload, proxies /api → :8000):
```bash
cd grand-festival/frontend
npm install
npm run dev          # http://localhost:5173
```

**Run the backend test suite:**
```bash
cd grand-festival
backend/.venv/Scripts/python -m pip install httpx     # test-only dep
backend/.venv/Scripts/python -m backend._smoke_test
```

**Production-style single-server run** (backend serves the built SPA):
```bash
cd grand-festival/frontend && npm run build
cd ..
ADMIN_PASSWORD=dev GF_COOKIE_SECURE=0 backend/.venv/Scripts/python -m uvicorn backend.main:app --port 8000
# → http://localhost:8000  (site + API on one origin)
```

---

## Docker

```bash
cd grand-festival
GF_DATA_DIR=~/docker/grand-festival-data GF_ADMIN_PASSWORD="$(openssl rand -base64 32)" \
  docker compose up -d --build
```

- App listens on container `:8000`, published on host `:8082`.
- `GF_DATA_DIR` is the host folder mounted to `/data` (DB + uploads). Keep it outside the repo.
- `docker ps` should show the container `healthy` (HEALTHCHECK hits `/api/health`).

---

## Deploy to the Pi (handoff — Parker)

The build is committed in the repo; the Pi's auto-deploy pulls + rebuilds. Steps that are **not** Claude Code's to do (no local Docker, git push is Parker's):

1. **Admin password** — on the Pi:
   ```bash
   mkdir -p ~/docker/grand-festival-data
   echo "GF_ADMIN_PASSWORD=$(openssl rand -base64 32)" >> ~/docker/.env
   ```
2. **Wire the service.** Either run the standalone compose from the repo folder, or add this block to the root `~/docker/docker-compose.yml` alongside Haven (note the build context points into the repo clone):
   ```yaml
   grand-festival:
     build: ./haven-ui/Master-Haven/grand-festival
     container_name: grand-festival
     restart: unless-stopped
     ports:
       - "8082:8000"
     volumes:
       - ./grand-festival-data:/data
     environment:
       - ADMIN_PASSWORD=${GF_ADMIN_PASSWORD}
       - DATA_DIR=/data
       - DB_PATH=/data/grand_festival.db
       - UPLOAD_DIR=/data/uploads
       - GF_COOKIE_SECURE=1
   ```
   > Confirm `8082` is free first (`docker ps`); Haven is on `8005`.
3. **Auto-deploy** — add to `~/scripts/auto-deploy.sh` after the existing `git pull`:
   ```bash
   CHANGED=$(git diff --name-only HEAD@{1} HEAD)
   if echo "$CHANGED" | grep -q '^grand-festival/'; then
       cd ~/docker && docker compose up -d --build grand-festival
   fi
   ```
4. **Domain / DNS / proxy / SSL** (Parker): buy domain → Cloudflare A record → NPM proxy host `<domain>` → `http://127.0.0.1:8082` → Let's Encrypt cert.
5. **First boot** auto-creates the DB and seeds the 7 placeholder civs.

---

## API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | — | `{"ok": true}` |
| GET | `/api/civs` | — | approved civs, ordered by `display_order` |
| GET | `/api/civs/{id}` | — | one approved civ |
| GET | `/api/uploads/{file}` | — | serve a logo |
| GET | `/api/schedule` | — | live festival schedule, parsed + cached (5 min) from the Google Sheet |
| POST | `/api/civs/submit` | — | submit a civ (multipart, optional `logo`) → `pending` |
| POST | `/api/admin/login` | — | `{password}` → sets `gf_admin` cookie |
| POST | `/api/admin/logout` | cookie | clear session |
| GET | `/api/admin/me` | cookie | `{authenticated: true}` / 401 |
| GET | `/api/admin/civs` | cookie | all civs + `pending_count` |
| GET | `/api/admin/civs/pending` | cookie | pending only |
| POST | `/api/admin/civs/{id}/approve` | cookie | approve |
| POST | `/api/admin/civs/{id}/reject` | cookie | reject (optional `{notes}`) |
| PATCH | `/api/admin/civs/{id}` | cookie | edit name/role/description/status/display_order |
| DELETE | `/api/admin/civs/{id}` | cookie | delete (removes logo file too) |
| GET | `/api/admin/log` | cookie | recent admin actions |

---

## Live schedule (Google Sheet)

The Who's Going → Schedule tab renders a **read-only** view of the public festival
schedule sheet. The backend fetches the sheet's CSV server-side (no browser CORS),
parses it, and caches it — so edits to the sheet appear on the site within the TTL
without anyone touching the website. Configurable via env (defaults baked in):

- `GF_SCHEDULE_SHEET_ID` — Google Sheet ID (default: the festival schedule sheet)
- `GF_SCHEDULE_GID` — tab gid (default `0`)
- `GF_SCHEDULE_TTL` — cache seconds (default `300`)

The sheet must stay link-viewable ("Anyone with the link → Viewer"). If the fetch
fails, the endpoint serves the last good copy (stale) and the UI falls back to a
static outline. Editing happens only in the sheet — never from the site.

## Before launch (in `frontend/src/config.js`)

- `DISCORD_INVITE_URL` — set the real invite (empty = button shows a "coming soon" note, Nav routes to Sign Up).
- `FESTIVAL_TARGET_UTC` — currently `2026-06-19T12:00:00Z` (Fri 19 June, "Grand Festival Open" from the schedule sheet); adjust if the start time moves.
