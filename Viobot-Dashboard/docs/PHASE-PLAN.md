# Viobot Dashboard — Phase Plan (VHAV-C-2026-001)

Approved 2026-06-28. Decisions locked: **Node.js + better-sqlite3**; **co-located, direct-SQLite**
integration; phased delivery (auth → config → modular → customization → handoff).

Each phase maps to the SOW §7 acceptance criteria.

## Phase 0 — Discovery & dependency intake (GATE)
Nothing Viobot-real ships until the client deliverables arrive. Obtain from art3mis:
- Viobot **repo** + read access (to mirror the exact `config_json` schema the bot reads).
- Discord **OAuth app credentials** (client_id / secret / redirect URI) — confirm we use Viobot's
  existing Discord application.
- A fresh **DB copy** + the agreed **sqlite3 backup / safe-transfer workflow**.
- **Deployment topology** confirmation (dashboard co-located on the Pi sharing Viobot's DB volume).
- **v1 config scope** — which options the dashboard manages first.
- The **v1.8 dashboard tech-preview** as the design reference (Phase 4).

Output: the integration spec in [`INTEGRATION-SPEC.md`](INTEGRATION-SPEC.md).

## Phase 1 — Framework + auth → acceptance #1, #6  ✅ done
Separable framework scaffold (framework vs viobot layers), Discord OAuth2 login, secure sessions,
and the **admin-scoped guild picker** (only servers where the user is admin AND Viobot is present).
The bot-present set = guilds with a `guild_configs` row.

## Phase 2 — Per-server config CRUD + safe writes → acceptance #2, #3  ✅ done
Render/edit `config_json` (roles / channels / features) with Discord role & channel pickers and
validation. Persistence is concurrency-safe: WAL + `busy_timeout`, atomic read-modify-write,
optimistic concurrency on `updated_at`, backup-before-write. Live and writing to the Viobot DB.

**No bot-side config-reload hook is required** (verified): the bot re-reads config from the DB via a
~30s cache TTL + pervasive `forceReload`, so a dashboard save applies automatically within ~30 seconds.
The "Restart Viobot" button is an optional force-now convenience, not a dependency. An optional
`VIOBOT_DB_READONLY` kill-switch makes the write endpoints refuse with HTTP 403.

## Phase 3 — Modularize + extend → acceptance #4  ✅ done
Generalize Phase 2 into the data-driven **config registry** (a new option = one registry entry).
Add **alias management** (reuse the existing Viobot Alias Generator engine), **server-variable**
editing, and a **read-only violations / mod-activity** viewer.

## Phase 4 — Customization layer → acceptance #5  ✅ done
Theme tokens + branding/nav config + documented swappable section components so the Client restyles
via config, not core logic. Depth defined against the v1.8 tech-preview.

## Phase 5 — Handoff & deploy → acceptance #7  🔨 in progress
Deployed and live on the Pi (Docker, NPM, Haven pattern) at `viobot.havenmap.online`. Remaining:
deliver docs — architecture, "how to add a config option," deploy/runbook, safe-transfer workflow.
Walk-through → acceptance sign-off → final payment.

## Top risks
1. **Client-deliverable dependency** (repo / DB / OAuth) — gates everything. #1 schedule risk.
2. **SQLite concurrency** with the live bot — WAL / busy_timeout / backup-on-write / optimistic concurrency.
3. **Config-schema drift** between bot and dashboard — registry must mirror what the bot reads.
4. **Security** — server-side admin re-verification, OAuth CSRF, session hardening, least-privilege DB.
5. **Stale/real data** — the DB copy is real users' data; read-only reference, never a write target in dev.
