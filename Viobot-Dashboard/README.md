# Viobot Dashboard

Web configuration dashboard for **Viobot** (the Discord bot owned by art3mis / Owen Gaffney).
Built by **Voyager's Haven LLC** under SOW **VHAV-C-2026-001**.

Server admins log in with Discord, pick a server they administer, and view / change / create
Viobot's per-server configuration. Changes write directly into Viobot's SQLite database and take
effect for the bot — in the manner of Carl-bot's dashboard.

## Status

| Phase | Scope | State |
|------:|-------|-------|
| 0 | Discovery & dependency intake (Viobot repo, OAuth creds, DB access, safe-transfer workflow, topology) | ⏳ depends on client deliverables — see [`docs/INTEGRATION-SPEC.md`](docs/INTEGRATION-SPEC.md) |
| **1** | **Framework + Discord OAuth2 login + admin-scoped guild access** | 🔨 **in progress (this scaffold)** |
| 2 | Per-server config view/change/create on `config_json` + safe SQLite writes | ⬜ |
| 3 | Modular config registry + alias & variable management + read-only mod log | ⬜ |
| 4 | Customization / theming layer | ⬜ |
| 5 | Handoff + deploy on Pi | ⬜ |

Full plan: [`docs/PHASE-PLAN.md`](docs/PHASE-PLAN.md).

## Architecture (and the IP split that drives it)

The SOW retains the **reusable framework** for the Company while the **Viobot-specific** dashboard
is owned by the Client. That split is structural in the code, not just legal:

```
server/src/
  framework/   ← REUSABLE engine (Company-retained). Generic Discord OAuth2, sessions,
                 guild-access scoping, and the config-rendering engine. Reusable on any future
                 bot-dashboard contract — knows nothing about Viobot.
  viobot/      ← Viobot-SPECIFIC (Client-owned). The bot-present guild source and the config
                 registry that mirrors Viobot's guild_configs.config_json. Adding a new Viobot
                 option = one registry entry here ("modular config system").
```

- **Backend:** Node.js + Fastify + `better-sqlite3` (same language as Viobot; transactional SQLite).
- **Frontend:** React + Vite.
- **DB model:** the dashboard runs **co-located** with Viobot and reads/writes the **same SQLite file**.
  Phase 1 opens the DB **read-only**. Writes (Phase 2) use WAL + `busy_timeout`, atomic
  read-modify-write of `config_json` with optimistic concurrency, and **backup-before-write** per the
  agreed sqlite3 safe-transfer workflow.

## Run it (Phase 1)

Two processes. From `Viobot-Dashboard/`:

```bash
# 1. Backend
cd server
cp .env.example .env          # then set VIOBOT_DB_PATH (+ Discord creds when available)
npm install
npm run dev                   # http://localhost:8090  (GET /api/health)

# 2. Frontend (separate terminal)
cd web
npm install
npm run dev                   # http://localhost:5173  (proxies /api -> :8090)
```

**Discord login** needs `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` from art3mis (Viobot's Discord
application). Until those are set, `/api/health` reports `oauthConfigured: false` and the login button
is disabled — but the core guild-scoping logic is independently tested (`cd server && npm test`).

**DB fixture:** point `VIOBOT_DB_PATH` at a *local copy* of the Viobot SQLite DB. Never the live file
during dev. Copies are git-ignored (`dev-fixtures/`).
