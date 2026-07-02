# Voyager's Haven — Studio Site

Public marketing + checkout site for **Voyager's Haven LLC**, at (eventually)
**voyagershaven.online**. Same stack as Haven Control Room / Grand Festival:
**FastAPI + React (Vite) + SQLite**, one container serving both the API and the
built SPA.

```
VoyagersHaven-Site/
  backend/            FastAPI app
    main.py           entry point — /api routes + SPA fallback
    config.py         env-driven config (Stripe mode, amounts, version)
    db.py             SQLite connection + schema init
    schema.sql        payments + inquiries tables
    routes/
      public.py       /api/health /api/status /api/config
      checkout.py     /api/checkout  (support + invoice)  + Stripe stub
      inquiries.py    /api/inquiries (start-a-project form)
  frontend/           React + Vite
    src/
      App.jsx         routes: / /success /privacy /terms
      components/     Nav, Hero, Services, Work, About, Support, Hire, Footer, Toast
      pages/          Success, Legal
      data/site.js    all editable copy / portfolio / tiers
  Dockerfile          2-stage: node build -> python runtime
  docker-compose.yml  port 8090, host-mounted data dir, docker_default network
```

## Local development

Two terminals (backend on 8090, Vite dev server proxies `/api` to it):

```bash
# 1) backend
cd backend
python -m venv .venv && . .venv/Scripts/activate   # (bash on Windows: source .venv/Scripts/activate)
pip install -r requirements.txt
cd ..
uvicorn backend.main:app --reload --port 8090
# -> API at http://localhost:8090/api/health

# 2) frontend (hot reload)
cd frontend
npm install
npm run dev
# -> http://localhost:5173  (proxies /api to :8090)
```

### Single-process (prod-like) local run

Build the SPA once, then let FastAPI serve everything on one port:

```bash
cd frontend && npm install && npm run build && cd ..
uvicorn backend.main:app --port 8090
# -> whole site at http://localhost:8090
```

## Payments

Payments are env-gated by `STRIPE_MODE`:

- **`simulated`** (default) — the Support/Invoice flow records a real
  `pending -> paid` row in SQLite and drives an in-page mock Stripe modal. Fully
  usable locally with **no Stripe account**.
- **`live`** — `POST /api/checkout` creates a real Stripe Checkout Session and
  returns its hosted URL; the browser is redirected there, and Stripe redirects
  back to `/success?ref=...`. Requires `STRIPE_SECRET_KEY`,
  `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, and `SITE_URL`.
  > TODO before going live: implement the `POST /api/stripe/webhook` handler to
  > mark rows `paid` on `checkout.session.completed` (the session-create path is
  > already wired in `routes/checkout.py`).

## Deploy (Pi, once the domain is registered)

Mirrors Grand Festival. On the Pi:

```bash
cd ~/docker/.../VoyagersHaven-Site
VH_DATA_DIR=~/docker/voyagers-haven-data docker compose up -d --build
```

Then point **voyagershaven.online** at the `voyagers-haven` container in Nginx
Proxy Manager (port 8000 inside the container / 8090 on the host). The service
shares the external `docker_default` network so NPM can reach it by name.

## Data

`payments` (support + invoice) and `inquiries` (start-a-project) live in
`voyagers_haven.db`, mounted from the host **outside** the repo so pulls and
rebuilds never touch it.
