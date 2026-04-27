# The Keeper — Code Audit

Audit performed on 2026-04-23 against the source tree at `the_keeper/`.

Findings are grouped by impact. File:line references are clickable in most editors.

---

## Tier 1 — Functional bugs (bot is broken without these)

### 1. Hardcoded BASE_URL and API_KEY override the .env

**File:** `cogs/Haven_upload.py:12-13`

```python
BASE_URL = "https://havenmap.online"
API_KEY = "vh_live_REDACTED"
```

`HAVEN_API` from the .env is **completely ignored** by the main upload cog. Every `!newsystem` and `!discovery` posts to havenmap.online, which from inside the Pi container fails due to hairpin NAT.

The plaintext API key in source also needs to be revoked — it's been committed to git history.

**Fix:** Read both from environment, with no defaults that point at the public URL:

```python
BASE_URL = os.getenv("HAVEN_API")
API_KEY = os.getenv("HAVEN_API_KEY")
if not BASE_URL or not API_KEY:
    raise RuntimeError("HAVEN_API and HAVEN_API_KEY must be set")
```

---

### 2. `init_db()` runs ALTER before CREATE on first run

**File:** `cogs/Data/xpdata.py:174-185`

```python
cur.execute("PRAGMA table_info(users)")
cols = [c[1] for c in cur.fetchall()]
if "primary_role" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN primary_role TEXT")  # fails: table doesn't exist
cur.execute("CREATE TABLE IF NOT EXISTS users ...")
```

On a brand-new database the ALTER throws `no such table: users`. First-time install crashes.

**Fix:** CREATE first, then check PRAGMA and ALTER for migration:

```python
cur.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, primary_role TEXT)")
# ALTER no longer needed since the column is in the CREATE
```

---

### 3. `WELCOME_CHANNEL_ID` lookup always returns None

**File:** `cogs/welcome.py:31`

```python
channel_id = getattr(bot, "WELCOME_CHANNEL_ID", None)
```

`bot.py:182-187` only sets `bot.CHANNELS` (a dict), never `bot.WELCOME_CHANNEL_ID`. **Member-join welcomes never fire.**

**Fix:**

```python
channel_id = bot.CHANNELS.get("welcome")
```

---

### 4. `!partners` command is dead code

**File:** `cmds/exclaim.py:131-136`

The `if not community_cog:` branch over-indents the rest of the function inside the `else` of an early `return`, so `fetch_sheet` and the loop never execute when community_cog exists. Result: command always silently no-ops.

**Fix:** Dedent the block following the early return.

---

### 5. `await ctx.trigger_typing()` was removed in discord.py 2.0

**File:** `cmds/exclaim.py:262`

Crashes `!leaderboard` with AttributeError.

**Fix:**

```python
async with ctx.typing():
    await featured_cog.post_leaderboard(ctx.channel)
```

---

### 6. `process_system_creation_xp()` is undefined

**File:** `cogs/Haven_upload.py:572`

Function is never imported, never defined. Every discovery confirm raises NameError, caught by the broad except and reported as a submission failure to the user. **No XP is awarded for system creations from `!discovery`.**

**Fix:** Either define the function in `cogs/xp_system.py` and import it, or remove the call entirely.

---

### 7. Broken level-up role assignment in `process_discovery_xp`

**File:** `cogs/xp_system.py:259-262`

```python
if leveled_up:
    member = bot.get_guild(member.guild.id).get_member(user_id) if 'member' in globals() else None
```

`bot` and `member` are undefined at this scope; the `'member' in globals()` guard always returns None. **Rank role updates on level-up never run from discovery XP.**

**Fix:** Pass `member` and `bot` into `process_discovery_xp` as parameters from the caller.

---

### 8. `keeper` interactive session calls non-existent methods

**File:** `cogs/personality.py:107-122, 147`

```python
await stats_cog.stats(ctx)
await stats_cog.map_command(ctx)
await stats_cog.best(ctx, count=count, community=community)
await community_cog.show_logs(ctx, search=search_term)
```

None of these methods exist on `Haven_statsCog` or `CommunityCog` — they're commands defined on `CommandsRouter` in exclaim.py. The conversational keeper session crashes on every stats/best/map/show-logs request.

**Fix:** Either route through `bot.invoke()` with a synthetic message, or move the underlying logic to a public method on the right cog and call it directly.

---

### 9. Google service account credentials are incomplete

**File:** `cogs/community.py:181-188`

```python
creds_dict = {
    "type": "service_account",
    "project_id": "the-keeper-493501",
    "client_email": "whrstrsg@the-keeper-493501.iam.gserviceaccount.com",
    "token_uri": "https://oauth2.googleapis.com/token",
}
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
```

Missing `private_key`, `private_key_id`, `client_id`. `Credentials.from_service_account_info()` raises on first call. **`!addciv` is non-functional.**

**Fix:** Mount a real service account JSON file and use `Credentials.from_service_account_file()`, or inject the missing fields via environment variables.

---

### 10. Channel gates crash on missing env vars

**File:** `cmds/exclaim.py:50, 107, 188, 220, 268, 280, 290, 301, 327, 355`

Every command does `int(os.getenv("X"))` with no default. If any channel env var is missing or empty, the command crashes with `TypeError: int() argument must be... not 'NoneType'`.

**Fix:** Use `int(os.getenv("X", "0"))` or write a helper:

```python
def env_channel(name: str) -> int:
    return int(os.getenv(name) or 0)
```

---

## Tier 2 — Silent correctness bugs (works, but wrong)

### 11. Two different XP curves running in parallel

- `cogs/xp_system.py:29` — `100 + (level - 1) * 50`
- `cogs/xp_cog.py:130` — `100 + (level * 50)`

Level 1 needs 100 vs 150 XP depending on which `add_global_xp` runs. Both call `save_global` against the same row — XP curve depends on entry point. **Silent data corruption.**

**Fix:** Pick one, delete the duplicate, import from the canonical location.

---

### 12. Two `set_primary_role()` implementations

- `cogs/xp_system.py:146` — writes to DB
- `cogs/xp_cog.py:91` — only updates in-memory cache

Department selection (via `DepartmentView` in xp_cog) and welcome-cog auto-detection (via `from cogs.xp_system import set_primary_role`) use different paths. **Welcome-cog persists, department-select does not.**

**Fix:** Delete the xp_cog version, import the xp_system version.

---

### 13. Two `users = {}` caches

- `cogs/xp_system.py:63`
- `cogs/xp_cog.py:79`

Setting primary_role in one doesn't update the other. State drifts.

**Fix:** Move the cache into `xpdata.py` (single source) or behind a single getter.

---

### 14. Economy and conflict dropdowns clamp to 1-3

**File:** `cogs/Haven_upload.py:160-174`

```python
options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 4)]
```

Haven backend supports T1-T4 economy levels; this clamps to 3 max. Submissions get downgraded. Also missing "None" / "Pirate" / "Abandoned" options that the rest of the project supports.

**Fix:** Match the backend's enum: `["T1", "T2", "T3", "T4", "None"]` for economy level and `["Low", "Medium", "High", "Pirate", "None"]` for conflict.

---

## Tier 3 — Architecture & maintainability

### 15. Brittle import order

`from Data.xpdata import *` in `cogs/welcome.py:3`, `cogs/xp_system.py:1`, `cogs/xp_cog.py:1` only resolves because `cogs/personality.py:2` does `sys.path.append(os.path.dirname(__file__))` and personality is loaded first in COGS. Reorder the list and the bot won't load.

**Fix:** Use the full `from cogs.Data.xpdata import ...` import path everywhere. Remove the `sys.path.append()` hack from personality.py.

---

### 16. SQLite connection thrash

`cogs/Data/xpdata.py` opens and closes a sqlite connection on every `get_xp`, `add_xp`, `get_level`, `set_level`, `check_cooldown`, `get_global`, `save_global`. Every chat message → 2-3 open/close cycles.

**Fix:** Singleton connection (you already pass `check_same_thread=False`) or a context manager.

---

### 17. Per-request `aiohttp.ClientSession()`

`cogs/Haven_upload.py:23, 28, 38, 58` opens a fresh TCP+TLS handshake on every API call.

**Fix:** One session per cog, created in `cog_load`/`setup_hook`, closed in `cog_unload`.

---

### 18. Configuration hardcoded in bot.py

`bot.py:35-156` has ~150 lines of role/channel ID dicts. The bot can't be reused for another server without source edits.

**Fix:** Move to `Data/config.json` (the file already exists and is mostly empty). Load on startup.

---

### 19. Channel ID gating duplicated 12+ times

Every command in `exclaim.py` repeats:

```python
if ctx.channel.id != int(os.getenv("LIBRARY_CHANNEL_ID")): return
```

**Fix:** Decorator:

```python
def requires_channel(env_name: str):
    def predicate(ctx):
        target = int(os.getenv(env_name, "0"))
        return target and ctx.channel.id == target
    return commands.check(predicate)

@requires_channel("LIBRARY_CHANNEL_ID")
@commands.command()
async def stats(self, ctx):
    ...
```

---

### 20. `cogs/xpdata.py` (stale duplicate)

A 6 KB older copy sits next to `cogs/Data/xpdata.py`. Different content. One will silently win depending on import order.

**Fix:** Delete `cogs/xpdata.py`.

---

### 21. Invalid `partials` kwarg on `commands.Bot()`

**File:** `bot.py:175`

```python
bot = commands.Bot(... partials=["MESSAGE", "REACTION", "CHANNEL"])
```

Not a valid kwarg. Silently ignored. Partial-message handling actually requires per-event `await message.fetch()` (which `featured.py:122-126` already does).

**Fix:** Remove the kwarg.

---

### 22. `on_ready` starts tasks that accumulate on reconnect

**File:** `bot.py:209-218`

`on_ready` fires on every reconnect. Each fire starts a new `weekly_leaderboard_task` → duplicate posts after the first reconnect.

**Fix:** Move to `setup_hook` or guard with `if not hasattr(bot, "_tasks_started"):`.

---

### 23. Inconsistent logging

`bot.py:7` configures `logging.basicConfig(level=logging.INFO)`. About half of the cogs (Haven_upload, xp_cog, welcome, featured, etc.) use `print()` instead. Print bypasses log levels and doesn't show the source module.

**Fix:** Use `log = logging.getLogger(__name__)` at the top of each module, then `log.info(...)`, `log.error(...)`.

---

## Tier 4 — Cleanup

### 24. Nested duplicate folder

`the_keeper/The_Keeper/` contains a duplicate copy of `bot.py`, `cogs/`, `cmds/`, `.env`, `xp.db`, `milestones.json` (~89 KB). Already excluded from Docker build via `.dockerignore`. Should be deleted from disk to stop being a confusion source.

---

### 25. `cogs/Haven_upload` (0-byte file)

Stale empty file alongside `Haven_upload.py`. Delete.

---

### 26. `DB_PATH` resolves to nested `Data/Data/xp.db`

**File:** `cogs/Data/xpdata.py:5`

```python
DB_PATH = os.path.join(os.path.dirname(__file__), "Data", "xp.db")
```

`__file__` is already `cogs/Data/xpdata.py`, so `dirname` is `cogs/Data/` and the join produces `cogs/Data/Data/xp.db`. The two existing `xp.db` files (at repo root and `cogs/Data/`) are orphaned.

**Fix:**

```python
DB_PATH = os.path.join(os.path.dirname(__file__), "xp.db")
```

(Then move the existing `cogs/Data/xp.db` is already in the right spot — no migration needed.)

---

### 27. Three `Data/` directories with overlapping JSON files

- `the_keeper/Data/` — the live one (used by `cogs/announcements.py:7`, `cogs/featured.py:10` since CWD = `/app`)
- `the_keeper/cogs/Data/` — stale duplicates of the JSON files; legitimate `xpdata.py` and `__init__.py` live here
- `the_keeper/cmds/Data/` — stale (only `config.json` and `users.json`, both auto-created)

**Fix:** Delete the JSON files from `cogs/Data/` and the entire `cmds/Data/` folder. Keep `cogs/Data/__init__.py` and `cogs/Data/xpdata.py`.

---

### 28. Hardcoded ENV path inherited from Android

**File:** `bot.py:12`

```python
ENV_PATH = '/storage/emulated/0/Voyage/The_Keeper/.env'
```

Currently worked around in Docker by mounting the .env at this path inside the container. Should accept an override:

```python
ENV_PATH = os.getenv("KEEPER_ENV_PATH", "/app/.env")
```

Then mount `.env:/app/.env` and the bot stops depending on a fictional Android filesystem.

---

## Recommended fix order

If working through this, the order that gets the bot fully functional with the least churn:

1. **Tier 1** (#1-#10) — required to boot and to actually upload to Haven
2. **#11, #12, #13** — XP system stops drifting silently
3. **#26, #27, #20, #25, #24** — one cleanup pass to make the codebase navigable
4. **#15, #16, #17, #19** — architectural improvements
5. **#18, #21, #22, #23, #28** — polish

#1 is the single most important — without it, the keeper can never reach the Haven backend from inside the Pi container, regardless of how compose and networking are set up.
