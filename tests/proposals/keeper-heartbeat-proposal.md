# The_Keeper Heartbeat — Proposal for Stars

**Audience:** Stars (maintainer of `The_Keeper/`)
**From:** Parker, via the Haven smoke-test work
**Status:** Proposal — no code change has been made. Decision is yours.
**Authorization required:** explicit before any code lands in `The_Keeper/`.

---

## 1. The problem

The Haven smoke test suite (v1, currently in proposal) needs a way to answer: **"Is The_Keeper actually working?"**

Today the only signal we have is `docker ps` showing the container is running. That's good but not great — a container can be "Up" while the bot is silently disconnected from Discord, or stuck in a Python exception loop on a background task, or processing 0 events because of a missing role-ID env var.

Voyager's Haven is a community service. If the bot quietly stops responding, nobody notices until somebody actually tries `!stats` or `/fingerprint`. By then it's been broken for hours.

We want a heartbeat: a small artifact the bot writes when it knows it's healthy, so external monitoring can read that artifact and know "yes, the bot processed something recently".

---

## 2. What we're asking for

A ~10-line addition to `The_Keeper/bot.py` (or its own cog) that:

1. Writes a JSON file (e.g., `/app/data/heartbeat.json`) on bot startup.
2. Refreshes that file every 5 minutes via a `tasks.loop`.
3. The JSON contains: timestamp, guild count, last-event-time.

The smoke suite reads that file (via the Pi host filesystem, since the file is in a Docker volume) and asserts it was written within the last ~10 minutes.

**That's it.** No HTTP server. No Discord pings. No outbound network. Just a small file write.

---

## 3. Why this design (vs. alternatives)

We considered three options:

### Option A: Heartbeat file (this proposal — recommended)

- **Pro:** ~10 lines of code; no new dependencies; zero outbound network; reuses existing volume mount; trivially read by `pi_check.sh`.
- **Pro:** Doesn't expose anything publicly. The file lives on the Pi disk.
- **Con:** Requires the smoke suite to have filesystem access to the volume — already true since both run on the Pi.

### Option B: HTTP healthcheck endpoint inside the bot

- **Pro:** Modern; Docker `HEALTHCHECK` can hit it; could expose more state.
- **Con:** Adds aiohttp/FastAPI as a runtime dep on a Discord bot that doesn't otherwise need it.
- **Con:** Opens a port on the container. Network surface area grows.
- **Con:** ~50 lines minimum.

### Option C: Bot pings a Discord webhook on `on_ready`

- **Pro:** No filesystem coupling.
- **Con:** Webhook URL has to live in `.env` or memory; one more secret to manage.
- **Con:** Couples liveness signal to Discord uptime — if Discord is degraded, you can't tell whether your bot is degraded too.
- **Con:** Spam noise in whatever channel receives the pings.

**Recommendation: Option A.** Smallest surface, smallest diff, smallest risk.

---

## 4. The actual code change

Concretely, here's what would land in `The_Keeper/`. **Not committed yet** — this is the proposal.

### File: `The_Keeper/cogs/heartbeat.py` (new, ~25 lines)

```python
"""
Heartbeat cog — writes a JSON file every 5 minutes so external monitoring
can verify the bot is alive and processing events.

File location: /app/data/heartbeat.json (mounted as a volume via docker-compose)
Read by: Haven smoke-test suite's pi_check.sh
"""
import json
import time
from pathlib import Path
from discord.ext import commands, tasks

HEARTBEAT_PATH = Path("/app/data/heartbeat.json")


class Heartbeat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._write_heartbeat()  # write once on cog load
        self._tick.start()

    def cog_unload(self):
        self._tick.cancel()

    def _write_heartbeat(self):
        try:
            HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "timestamp": time.time(),
                "iso_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "guild_count": len(self.bot.guilds),
                "user": str(self.bot.user) if self.bot.user else None,
                "latency_ms": round((self.bot.latency or 0) * 1000),
            }
            HEARTBEAT_PATH.write_text(json.dumps(payload))
        except Exception:
            # Heartbeat failure must NEVER take down the bot. Swallow.
            pass

    @tasks.loop(minutes=5)
    async def _tick(self):
        self._write_heartbeat()

    @_tick.before_loop
    async def _before_tick(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Heartbeat(bot))
```

### File: `The_Keeper/bot.py` — one-line addition to `COGS` list

```python
COGS = [
    "cogs.personality", "cogs.xp_system", "cogs.xp_cog",
    "cogs.Haven_stats", "cogs.featured", "cogs.community",
    "cogs.welcome", "cogs.Haven_upload", "cogs.announcements",
    "cogs.hex",
    "cogs.heartbeat",                      # ← NEW
    "cmds.exclaim", "cmds.list", "cmds.slash", "cmds.voyager",
]
```

### File: `The_Keeper/docker-compose.yml` — mount the data dir

```yaml
services:
  the-keeper:
    # ... existing config ...
    volumes:
      - ./.env:/storage/emulated/0/Voyage/The_Keeper/.env:ro
      - ./xp.db:/app/xp.db
      - ./milestones.json:/app/milestones.json
      - ./data:/app/data        # ← NEW (heartbeat + future state files)
```

Plus `mkdir data` once on the Pi (or let the cog create it on first run via `parents=True, exist_ok=True`).

### Optional: Dockerfile HEALTHCHECK

```dockerfile
HEALTHCHECK --interval=2m --timeout=10s --retries=3 \
  CMD python -c "import json, time, sys; d=json.load(open('/app/data/heartbeat.json')); sys.exit(0 if time.time() - d['timestamp'] < 600 else 1)" \
  || exit 1
```

Adds a Docker-level signal — `docker ps` shows `(healthy)` or `(unhealthy)`. Optional, not required for the smoke suite to work.

**Total diff size:** ~35 lines across 3 files (new cog, 1-line bot.py addition, 1-line compose volume). No new pip dependencies.

---

## 5. What the smoke suite consumes

### Phase 3 of the Haven smoke suite (after this lands)

`tests/cron/pi_check.sh` would add this row:

```
2026-04-29 04:30:00|keeper.heartbeat|PASS|written 47s ago, guilds=3, latency=42ms
```

Check logic in bash:

```bash
HEARTBEAT_FILE=$HOME/docker/the-keeper/data/heartbeat.json
if [ -f "$HEARTBEAT_FILE" ]; then
  ts=$(python3 -c "import json; print(json.load(open('$HEARTBEAT_FILE'))['timestamp'])")
  age=$(awk -v t="$ts" 'BEGIN { print int(systime() - t) }')
  if [ "$age" -lt 600 ]; then
    echo "$(date '+%F %T')|keeper.heartbeat|PASS|written ${age}s ago"
  else
    echo "$(date '+%F %T')|keeper.heartbeat|FAIL|stale by ${age}s"
  fi
else
  echo "$(date '+%F %T')|keeper.heartbeat|FAIL|file not found at $HEARTBEAT_FILE"
fi
```

If the heartbeat is stale > 10 minutes, the smoke suite alerts via the Haven Discord webhook (separate channel from anything Stars manages).

---

## 6. Privacy and data

The heartbeat file contains:

- A Unix timestamp (current time on the Pi)
- An ISO timestamp (same)
- Bot's guild count (an integer, e.g., `3`)
- Bot's username (e.g., `The Keeper#1234`)
- Bot's WebSocket latency (an integer ms)

**It does NOT contain:**

- Any user IDs
- Any Discord message content
- Any role/channel IDs
- The bot token
- Any environment variable values
- Anything that could identify users

The file lives on Parker's Pi, in a directory only Parker can read. It is **not** exposed via HTTP, never sent to Discord, never committed to git.

---

## 7. Risk and rollback

### Risks

- **None substantial.** The cog wraps every operation in `try/except` and silently swallows failures. A broken heartbeat cannot take down the bot.
- The `tasks.loop(minutes=5)` is the same pattern The_Keeper already uses for `cogs/announcements.py:check_milestones`. No new failure modes.

### Rollback

- Remove `"cogs.heartbeat"` from `COGS` list in `bot.py`.
- `git revert` the commit.
- Restart the container.
- That's it. No data migrations, no schema changes.

### Failure mode if the cog is buggy

Worst case: the cog raises on import (typo, missing dep). `bot.py:load_extension` will log the error and continue without that cog. The bot still starts; the heartbeat just won't be written. The smoke suite reports `FAIL|keeper.heartbeat|file not found` and Parker investigates.

This is the same behavior as if any other cog crashed on load — well-trodden path.

---

## 8. Timeline and ownership

- **Stars decides:** Yes / No / Yes-with-changes.
- **If Yes:** Stars writes the cog (estimated 30 minutes including the small docker-compose tweak). Parker tests it on the Pi. Smoke suite Phase 3 wires up `pi_check.sh` to read it (~10 minutes of bash).
- **If No:** Parker's smoke suite falls back to `docker ps` only. Container-up signal still works; it just doesn't tell us whether the bot is processing events.
- **If Yes-with-changes:** Stars iterates on the design before any code lands.

There is no deadline. The Haven smoke suite v1 ships with `docker ps`-only Keeper coverage and adds heartbeat coverage in v1.1 once Stars's code is in.

---

## 9. Questions Stars might have (with answers)

**Q: Do I have to add this? It's my repo.**
A: No. Parker's smoke suite works without it — just less informative. This is a request, not a requirement.

**Q: Why 5 minutes? Why not 1 minute?**
A: 5 is the same cadence as `check_milestones`, so it's a tested pattern in The_Keeper. 1 minute would be fine too; the smoke suite tolerates anything ≤ 10 minutes between writes. Pick whatever feels right.

**Q: Why `/app/data/heartbeat.json` and not `/tmp/heartbeat.json`?**
A: `/tmp` is wiped on container restart. We want the heartbeat to persist briefly across restarts so monitoring can distinguish "bot just restarted" from "bot is dead". Mounting `./data` as a volume gives it that property.

**Q: Can I put the cog somewhere other than `cogs/heartbeat.py`?**
A: Yes. Anywhere that gets loaded works. The proposal puts it in `cogs/` for consistency with the existing layout.

**Q: I want to add more fields to the heartbeat (event count, last command name, …). OK?**
A: Yes — anything that doesn't include user-identifying data is fine. The smoke suite only cares about the timestamp; everything else is bonus.

**Q: What if I want to rewrite this differently?**
A: Go for it. The contract is just: "a file at `/app/data/heartbeat.json` with a `timestamp` (Unix epoch) field, refreshed at least every 10 minutes". Implementation is yours.

---

**End of proposal.**

Send any questions or pushback to Parker. If approved, the change can land at Stars's pace — there's no blocker on the rest of the smoke suite.
