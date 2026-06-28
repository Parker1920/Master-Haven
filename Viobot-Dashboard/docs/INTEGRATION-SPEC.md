# Viobot Dashboard — Integration Spec (DRAFT)

Working document for Phase 0. Reconstructed from a Jun-5 copy of the Viobot SQLite DB and the public
docs; **to be confirmed against the live Viobot repo** once art3mis grants access.

## 1. Dependency status (updated 2026-06-28 from live Pi inspection)

**RESOLVED from the Pi — no external input needed:**
- **Deployment topology** — `viobot` runs on our Pi 8GB via `~/docker/docker-compose.yml` (built from
  `./viobot/Viobot`, network `haven-net`). Live DB: host `/home/pi8gb/docker/viobot-data/db/viobot.db`
  → container `/app/data`, **WAL mode**. The dashboard co-locates as a new service in that compose,
  mounting the same `./viobot-data/db` volume + joining `haven-net`. We control hosting end-to-end.
- **Config schema** — confirmed from the bot source `src/lib/ConfigManager.js` `DEFAULTS` (see §3);
  the registry is updated to match. The bot auto-creates/migrates its tables at startup.
- **client_id** = `1428174657172799500` (app "Viobot"; a Discord **Team** app, `bot_public:true`).
- **DB read access** — direct on the Pi. Live counts: 19 guild_configs / 69 aliases / 274 violations.

**STILL NEEDED — one Developer-Portal action (NOT on the Pi, not derivable):**
- **OAuth2 `client_secret` + registered redirect URIs.** The Pi has the *bot token* (a different
  credential) and the *client_id*, but never an OAuth secret — this app has no OAuth set up
  (`redirect_uris: []`). A ~2-minute Developer-Portal action by any Viobot-Team member, **or
  (recommended) a separate Haven-owned Discord app** for the dashboard login: it needs only
  `identify`+`guilds`, and bot-presence comes from our DB (§2), so it need not be Viobot's app.
  Result goes into `server/.env` (`DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` / `DISCORD_REDIRECT_URI`).

**STILL NEEDED — from art3mis (small, real):**
- **A config-reload hook in Viobot's code.** The bot caches config in memory (§4), so a direct DB write
  won't take effect live until the bot reloads that guild. The trigger must land in **art3mis's repo**
  (the Pi auto-pulls the bot from his GitHub via the cron updater, so a Pi-only edit would be overwritten).
  In-scope "integration" work, but it needs his repo.

**STILL NEEDED — scoping answers:**
- **v1 config scope** (proposed: full `config_json` v1 — §3).
- **Premium/tier model** — Free/Plus/Beta lives in `beta_guilds` / `beta_guild_features` + a Plus SKU
  (env `VIOBOT_PLUS_SKU_ID`), **not** in `config_json`. Confirm whether the dashboard reflects/enforces it.
- **The v1.8 dashboard tech-preview** — design reference for the Phase 4 customization layer.

## 2. Viobot DB — observed shape

Node.js bot; SQLite DB (`~/docker/viobot/Viobot` on the Pi 8GB). Tables:

| Table | Role for the dashboard |
|-------|------------------------|
| `guild_configs(guild_id PK, guild_name, config_json, created_at, updated_at)` | **Primary write surface.** One JSON blob of per-server config. |
| `aliases(guild_id, alias_name, scope, owner_id, …)` | Alias CRUD (Phase 3; reuse Alias Generator engine). |
| `guild_variables(guild_id, var_name, var_value, …)` | Server `!var` KV editor (Phase 3). |
| `violations(id, guild_id, user_id, type, …)` | Read-only moderation log viewer (Phase 3). |
| `mute_role_data`, `member_role_snapshots`, `reminders` | Runtime state — not config; out of scope / read-only at most. |

**A guild is "bot-present / registered" iff it has a `guild_configs` row** — this is the source for the
admin∩present intersection (no separate bot guild-list call required when co-located).

## 3. `config_json` v1 (the modular config surface)

```json
{
  "version": 1,
  "meta":    { "guildId": "…", "createdAt": "…", "updatedAt": "…" },
  "roles":   { "moderatorRoleId": null, "muteRoleId": null, "voiceMuteRoleId": null,
               "verificationRequiredRoleId": null, "staffRoleIds": [] },
  "channels":{ "loggingChannelId": null, "contactMemberChannelId": null, "contactMutedChannelId": null,
               "papertrailChannelId": null, "violationsChannelId": null },
  "features":{ "tickets": false, "logger": false }
}
```

This blob *is* why the "modular config system" requirement is cheap: a new Viobot option is a new JSON
key + one entry in the dashboard's config registry (`server/src/viobot/configRegistry.js`) — no schema
migration. Field types map cleanly to UI controls: **role picker**, **role multi-select**, **channel
picker**, **boolean**.

**Proposed MVP (Phase 2) config scope:** the full `config_json` v1 above (roles, channels, features).
Aliases + variables + the mod-log viewer follow in Phase 3.

## 4. Write protocol (Phase 2 — to confirm)

- Connection: WAL mode, `busy_timeout`, opened against the **same file** the bot uses.
- Update = read `config_json` → mutate the targeted path → bump `meta.updatedAt` + row `updated_at` →
  write back in a single transaction.
- **Optimistic concurrency:** reject the write if `updated_at` changed since the client loaded it (so a
  dashboard write never silently clobbers a write the bot made in between).
- **Backup-before-write** per the agreed workflow.
- **Cache invalidation — CONFIRMED REQUIRED.** The bot caches config in memory (`ConfigManager.cache`,
  filled on `load()`, cleared only via `reload()`/`invalidate()`). A dashboard DB write alone will NOT
  take effect for an already-cached guild. Phase 2 must signal the bot to reload the guild after a write —
  a small upstream hook in art3mis's repo (e.g. the dashboard writes a `config_reload` signal row or pings
  a local socket → bot calls `configManager.reload(guild)`). The live DB is already WAL, so concurrent
  dashboard reads + the bot are safe; writes serialize via `busy_timeout`.

## 5. Auth & access (Phase 1 — implemented)

- Discord OAuth2, scopes `identify` + `guilds`.
- Admin = guild `owner === true` **or** the `ADMINISTRATOR` (0x8) bit set in the guild's `permissions`.
- Accessible guilds = (user's admin guilds) ∩ (guilds with a `guild_configs` row).
- Admin status is **re-verified server-side** against Discord on each guild-list load — the browser's
  guild list is never trusted.
