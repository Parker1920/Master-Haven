# Viobot Dashboard — Pi deploy

Goal: run the dashboard next to `viobot` on the Pi, reading and **writing** the **live** Viobot DB, so
server admins manage real Haven-server config through it.

## How it runs
- One container (`viobot-dashboard`): the Node API also serves the built React SPA (same origin).
- Mounts the live DB volume `/home/pi8gb/docker/viobot-data/db` → `/app/data` (the same file the bot uses).
- **Live read-WRITE:** the dashboard is a full config editor. Writes persist to Viobot's SQLite DB with
  backup-before-write + optimistic concurrency (WAL + `busy_timeout`). Config changes apply automatically
  within ~30 seconds because the bot re-reads config from the DB (30s cache TTL + `forceReload`) — no
  reload hook needed. Set `VIOBOT_DB_READONLY=true` as an optional kill-switch to make write endpoints 403.
- **Login:** in the normal deploy this is real Discord OAuth. `DEV_LOGIN=1` is a dev-only bypass (no Discord
  app) that treats the session as admin of every server Viobot is in — keep it off for any real launch.

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
{ "ok": true, "oauthConfigured": true, "devLogin": false, "serveStatic": true,
  "db": { "queryOnly": false, "journalMode": "wal", "registeredGuilds": 19, ... } }
```
(`queryOnly` is `true` only when the `VIOBOT_DB_READONLY` kill-switch is enabled.)

## Real login (normal deploy)
- Set `DISCORD_CLIENT_ID/SECRET/REDIRECT_URI`, set `DEV_LOGIN=0`, register the redirect URI on the Discord
  app, put it behind NPM + a domain, set `SESSION_SECURE=true`. (Live at `viobot.havenmap.online`.)
