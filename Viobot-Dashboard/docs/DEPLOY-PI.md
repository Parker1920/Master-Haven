# Viobot Dashboard — Pi deploy (Phase 1 testing)

Goal: stand the dashboard up next to `viobot` on the Pi, reading the **live** Viobot DB, so we can test
against real Haven servers — **before** any Discord OAuth app or art3mis change.

## How it runs
- One container (`viobot-dashboard`): the Node API also serves the built React SPA (same origin).
- Mounts the live DB volume `/home/pi8gb/docker/viobot-data/db` → `/app/data` (the same file the bot uses).
- **Read-only in Phase 1:** the connection runs `PRAGMA query_only=ON`, so it can read the live config but
  physically cannot write. (The mount is read-write only because WAL *readers* must write the `-shm` lock
  slots; the SQL-layer guard is what guarantees no data changes.)
- **Login:** `DEV_LOGIN=1` enables a testing bypass (no Discord app) — the session is treated as admin of
  every server Viobot is in, so the full server list + config are visible. Turn this off before real launch.

## Steps (on the Pi, after `git pull`)
The code lives in the Master-Haven clone after you pull. From the `Viobot-Dashboard/deploy/` folder there:

```bash
cd <master-haven-clone>/Viobot-Dashboard/deploy
cp .env.example .env
# edit .env → set SESSION_SECRET to a long random string (openssl rand -hex 32)
docker compose up -d --build
docker logs -f viobot-dashboard      # confirm it boots + reads the DB
```

Reach it at **http://<pi-ip>:8091** (LAN `10.0.0.229` or Tailscale `100.79.172.115`).
Click **Dev login (testing)** → you should see every server Viobot is in, read from the live DB.

> Build context is the `Viobot-Dashboard/` folder (one level up); `node_modules`, `.env`, and any `*.db`
> are excluded via `.dockerignore`. better-sqlite3 pulls a prebuilt arm64 binary (same `node:20-slim`
> base Viobot uses), so no build toolchain is needed.

## Health check
`GET http://<pi>:8091/api/health` →
```json
{ "ok": true, "phase": 1, "oauthConfigured": false, "devLogin": true, "serveStatic": true,
  "db": { "queryOnly": true, "journalMode": "wal", "registeredGuilds": 19, ... } }
```

## Later (not now)
- **Real login:** set `DISCORD_CLIENT_ID/SECRET/REDIRECT_URI`, set `DEV_LOGIN=false`, register the redirect
  URI on the Discord app, put it behind NPM + a domain, set `SESSION_SECURE=true`.
- **Writes (Phase 2):** set `VIOBOT_DB_READONLY=false` + add backup-before-write + the bot-side reload hook.
