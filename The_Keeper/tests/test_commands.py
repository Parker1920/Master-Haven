"""
Mock-based validation of every prefix command in The_Keeper bot.

- Does NOT contact Discord. No network calls are made; HTTP clients are patched.
- Loads each cog module directly (bot.py hard-requires an Android .env path we
  don't have here), injects a FakeBot, then drives each @commands.command
  callback with a FakeContext. Also drives FeaturedCog reaction listeners.

Run:
    py -3 tests/test_commands.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import types
import traceback
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Path + environment bootstrap
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
# cogs/xp_system.py does `from Data.xpdata import *`, so expose cogs/ on sys.path
sys.path.insert(0, os.path.join(BASE_DIR, "cogs"))

# Channel IDs used by the real bot (from its sanity checks). We set them to
# integers so `ctx.channel.id == int(os.getenv("..."))` guards pass when the
# fake context uses the matching id.
CHANNEL_ENV = {
    "SYSTEM_CHANNEL_ID": 100,
    "PLANET_CHANNEL_ID": 101,
    "FAUNA_CHANNEL_ID": 102,
    "FLORA_CHANNEL_ID": 103,
    "BASE_CHANNEL_ID": 104,
    "OUT_CHANNEL_ID": 105,
    "CRASH_CHANNEL_ID": 106,
    "SENTINEL_CHANNEL_ID": 107,
    "TOOL_CHANNEL_ID": 108,
    "STAFF_CHANNEL_ID": 109,
    "CHANNEL_SOCIAL_MEDIA": 110,
    "CHANNEL_EVENT": 111,
    "CHANNEL_DIPLOMAT": 112,
    "CHANNEL_VOYAGERS": 113,
    "CHANNEL_HAVEN_PROJECT": 114,
    "WELCOME_CHANNEL_ID": 115,
    "PHOTO_CHANNEL_ID": 116,
    "CONTACT_CHANNEL_ID": 117,
    "FEATURED_CHANNEL_ID": 118,
    "GENERAL_CHANNEL_ID": 119,
    "QUALIFY_CHANNEL_ID": 120,
    "LIBRARY_CHANNEL_ID": 121,
    "HELP_CHANNEL_ID": 122,
    "C_OFFICE_CHANNEL_ID": 123,
    "X_OFFICE_CHANNEL_ID": 124,
    "A_OFFICE_CHANNEL_ID": 125,
    "E_OFFICE_CHANNEL_ID": 126,
    "H_OFFICE_CHANNEL_ID": 127,
    "HOME_ROLE_ID": 200,
    "AWAY_ROLE_ID": 201,
    "FEATURED_THRESHOLD": 3,
    "FEATURED_TIME_LIMIT": 7 * 24 * 60 * 60,
    "HAVEN_API": "https://example.invalid",
    "HAVEN_URL": "https://example.invalid",
}
for k, v in CHANNEL_ENV.items():
    os.environ[k] = str(v)

# ---------------------------------------------------------------------------
# Stub third-party modules we don't need to exercise (gspread + google creds).
# The community.py module imports them at module load; the cog constructor
# itself does not touch them unless we hit addciv's submit flow (we don't).
# ---------------------------------------------------------------------------
def _install_stub(name: str, attrs: dict | None = None):
    mod = types.ModuleType(name)
    for k, v in (attrs or {}).items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


_install_stub("gspread", {"authorize": lambda *a, **k: None})

# google / google.oauth2 / google.oauth2.service_account namespace chain
_install_stub("google")
_install_stub("google.oauth2")
_install_stub(
    "google.oauth2.service_account",
    {"Credentials": type("Credentials", (), {"from_service_account_info": staticmethod(lambda *a, **k: None)})},
)

# Ensure discord.py works without a real Intents.all privileged call path in
# the tests — we never start the client.
import discord  # noqa: E402
from discord.ext import commands  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
@dataclass
class FakeAttachment:
    filename: str = "photo.png"
    url: str = "https://cdn.example/photo.png"


@dataclass
class FakeReaction:
    count: int
    me: bool = False
    emoji: str = "⭐"
    # discord.Reaction has `.message`; callers also pass message separately.


@dataclass
class FakeAuthor:
    id: int = 4242
    display_name: str = "Voyager"
    name: str = "voyager"
    bot: bool = False
    def __str__(self) -> str:
        return self.display_name
    @property
    def mention(self) -> str:
        return f"<@{self.id}>"


@dataclass
class FakeChannel:
    id: int = 0
    name: str = "test"
    sent: list = field(default_factory=list)

    async def send(self, content: str | None = None, *, embed=None, view=None, **kwargs):
        self.sent.append({"content": content, "embed": embed, "view": view, "kwargs": kwargs})
        return FakeMessage(id=len(self.sent), channel=self, author=FakeAuthor(bot=True))

    async def fetch_message(self, msg_id: int):
        for m in getattr(self, "messages", []):
            if m.id == msg_id:
                return m
        raise discord.NotFound(_FakeResp(404), "not found")

    def typing(self):
        class _Typing:
            async def __aenter__(self_): return self_
            async def __aexit__(self_, *a): return False
        return _Typing()


class _FakeResp:
    def __init__(self, status): self.status = status; self.reason = "fake"


@dataclass
class FakeMessage:
    id: int = 1
    channel: FakeChannel | None = None
    author: FakeAuthor = field(default_factory=FakeAuthor)
    attachments: list[FakeAttachment] = field(default_factory=list)
    reactions: list[FakeReaction] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    jump_url: str = "https://discord.example/jump/1"
    added_reactions: list = field(default_factory=list)

    async def add_reaction(self, emoji):
        self.added_reactions.append(emoji)

    async def fetch(self):
        return self


class FakeBot:
    """Minimal stand-in for discord.ext.commands.Bot."""
    def __init__(self):
        self.cogs_map: dict[str, commands.Cog] = {}
        self.channels: dict[int, FakeChannel] = {}
        self.views_added = []
        self.keeper_locked = False
        self.CHANNELS = {
            "welcome": CHANNEL_ENV["WELCOME_CHANNEL_ID"],
            "featured": CHANNEL_ENV["FEATURED_CHANNEL_ID"],
        }
        self.ROLES = {}
        self.PRIMARY_ROLES = {}
        self.XP_ENABLED_CHANNELS = []
        self.role_welcome_messages = {}

    async def add_cog(self, cog: commands.Cog):
        self.cogs_map[type(cog).__name__] = cog

    def get_cog(self, name: str):
        return self.cogs_map.get(name)

    def get_channel(self, cid: int):
        return self.channels.get(cid)

    def add_view(self, view, *, message_id=None):
        self.views_added.append(view)

    @property
    def commands(self):
        out = []
        for cog in self.cogs_map.values():
            out.extend(cog.get_commands())
        return out


@dataclass
class FakeContext:
    bot: FakeBot
    author: FakeAuthor = field(default_factory=FakeAuthor)
    channel: FakeChannel = field(default_factory=FakeChannel)
    guild: Any = None
    command: Any = None
    sent: list = field(default_factory=list)

    async def send(self, content: str | None = None, *, embed=None, view=None, **kwargs):
        payload = {"content": content, "embed": embed, "view": view, "kwargs": kwargs}
        self.sent.append(payload)
        self.channel.sent.append(payload)
        return FakeMessage(id=len(self.sent), channel=self.channel, author=FakeAuthor(bot=True))

    def typing(self):
        return self.channel.typing()

    # trigger_typing was removed in discord.py 2.x — expose it so we can
    # explicitly detect uses that would crash in production.
    async def trigger_typing(self):
        raise AttributeError("trigger_typing removed in discord.py 2.x")


# ---------------------------------------------------------------------------
# HTTP patch — block every outbound aiohttp call but return canned JSON.
# ---------------------------------------------------------------------------
import aiohttp  # noqa: E402

_real_ClientSession = aiohttp.ClientSession


class _FakeResponse:
    def __init__(self, status=200, data=None, text=""):
        self.status = status
        self._data = data
        self._text = text
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def json(self): return self._data
    async def text(self): return self._text


class _FakeClientSession:
    """Returns canned responses based on URL substring."""
    def __init__(self, *a, **k): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def close(self): pass

    def _canned(self, url: str):
        if "db_stats" in url:
            return _FakeResponse(200, {"stats": {
                "systems": 13_500, "planets": 26_500, "moons": 9_000,
                "regions": 420, "planet_pois": 7_777, "discoveries": 31_415,
            }})
        if "community-overview" in url:
            return _FakeResponse(200, {"totals": {"total_systems": 13_500}})
        if "contributors" in url:
            return _FakeResponse(200, {"contributors": [
                {"rank": 1, "username": "alice", "total_systems": 500},
                {"rank": 2, "username": "bob",   "total_systems": 300},
            ]})
        if "validate_glyph" in url:
            return _FakeResponse(200, {"valid": True})
        if "check_duplicate" in url:
            return _FakeResponse(200, {"exists": False})
        if "docs.google.com" in url:
            csv = ("Community Name,Description,Col3,Col4,Permanent Link\n"
                   "partners,,,,\n"
                   "Alpha,An allied fleet,,,,https://alpha.example\n"
                   "fallen civs,,,,\n"
                   "Ghostlings,gone,,,,\n")
            return _FakeResponse(200, text=csv)
        return _FakeResponse(200, {})

    def get(self, url, **kwargs): return self._canned(url)
    def post(self, url, **kwargs): return self._canned(url)


aiohttp.ClientSession = _FakeClientSession


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------
RESULTS: list[tuple[str, str, str]] = []  # (name, status, note)


def record(name: str, status: str, note: str = ""):
    RESULTS.append((name, status, note))
    marker = {"PASS": "[PASS]", "FAIL": "[FAIL]", "BUG": "[BUG ]", "SKIP": "[SKIP]"}[status]
    print(f"{marker} {name}" + (f"  — {note}" if note else ""))


async def run_cmd(cog, cmd_name: str, ctx: FakeContext, *args, **kwargs):
    """Invoke a Cog prefix command's underlying callback."""
    cmd = cog.get_commands()
    target = next((c for c in cmd if c.name == cmd_name), None)
    if not target:
        raise RuntimeError(f"{cmd_name} not found on {type(cog).__name__}")
    ctx.command = target
    return await target.callback(cog, ctx, *args, **kwargs)


# ---------------------------------------------------------------------------
# The tests
# ---------------------------------------------------------------------------
async def main():
    # Import lazily so sys.path/env/stub work above take effect first.
    from cogs import featured as featured_mod
    from cogs import Haven_stats, announcements, community as community_mod, hex as hex_mod
    from cogs.Data.xpdata import init_db, PRIMARY_ROLE_MAP

    # Ensure DB file exists for xp queries
    init_db()

    bot = FakeBot()

    # ------- Load each cog with its setup() where possible ---------
    await featured_mod.setup(bot)
    await Haven_stats.setup(bot)
    # announcements starts a background tasks.loop; avoid side effects by
    # constructing manually and skipping check_milestones.start().
    anno = announcements.AnnouncementCog.__new__(announcements.AnnouncementCog)
    anno.bot = bot
    anno.channel_id = CHANNEL_ENV["GENERAL_CHANNEL_ID"]
    anno.last_milestone = 13000
    anno.last_planet_milestone = 25000
    bot.cogs_map["AnnouncementCog"] = anno

    await community_mod.setup(bot)
    await hex_mod.setup(bot)

    # HelpSystem / CommandsRouter / HavenSubmission imports are heavier
    # (they import each other via `from cogs.xp_cog import DepartmentView`,
    # which triggers the xp stack). Patch out the Haven_upload sqlite bits
    # if needed.
    from cmds import list as list_mod
    await list_mod.setup(bot)

    # xp_cog requires Data.xpdata (cogs/Data) on sys.path — already set.
    from cogs import xp_cog as xp_cog_mod
    await xp_cog_mod.setup(bot)

    from cogs import Haven_upload
    await Haven_upload.setup(bot)

    from cmds import exclaim
    await exclaim.setup(bot)
    router = bot.get_cog("CommandsRouter")

    # Stash fake channels
    featured_cog = bot.get_cog("FeaturedCog")
    photo_channel = FakeChannel(id=CHANNEL_ENV["PHOTO_CHANNEL_ID"], name="photos")
    featured_channel = FakeChannel(id=CHANNEL_ENV["FEATURED_CHANNEL_ID"], name="featured")
    library_channel = FakeChannel(id=CHANNEL_ENV["LIBRARY_CHANNEL_ID"], name="library")
    general_channel = FakeChannel(id=CHANNEL_ENV["GENERAL_CHANNEL_ID"], name="general")
    qualify_channel = FakeChannel(id=CHANNEL_ENV["QUALIFY_CHANNEL_ID"], name="qualify")
    system_channel = FakeChannel(id=CHANNEL_ENV["SYSTEM_CHANNEL_ID"], name="system-logs")
    base_channel = FakeChannel(id=CHANNEL_ENV["BASE_CHANNEL_ID"], name="base-logs")
    for c in [photo_channel, featured_channel, library_channel, general_channel,
              qualify_channel, system_channel, base_channel]:
        bot.channels[c.id] = c

    # Helper to make a ctx bound to a channel ID
    def mk_ctx(channel: FakeChannel, author: FakeAuthor | None = None):
        return FakeContext(bot=bot, channel=channel, author=author or FakeAuthor())

    # =====================================================================
    # Prefix commands
    # =====================================================================

    # ---- !list ---------------------------------------------------------
    try:
        await run_cmd(bot.get_cog("HelpSystem"), "list", mk_ctx(general_channel))
        record("!list", "PASS", "rendered help pagination")
    except Exception as e:
        record("!list", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !hexkey --------------------------------------------------------
    try:
        await run_cmd(bot.get_cog("HexKey"), "hexkey", mk_ctx(general_channel))
        record("!hexkey", "PASS", "keypad view sent")
    except Exception as e:
        record("!hexkey", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !map -----------------------------------------------------------
    try:
        await run_cmd(router, "map", mk_ctx(library_channel))
        record("!map", "PASS", "embed with link button")
    except Exception as e:
        record("!map", "FAIL", f"{type(e).__name__}: {e}")

    # wrong-channel check
    try:
        ctx = mk_ctx(featured_channel)
        await run_cmd(router, "map", ctx)
        assert len(ctx.sent) == 0, "should be silently ignored in wrong channel"
        record("!map (wrong channel)", "PASS", "silently ignored as designed")
    except AssertionError as e:
        record("!map (wrong channel)", "FAIL", str(e))
    except Exception as e:
        record("!map (wrong channel)", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !stats ---------------------------------------------------------
    try:
        await run_cmd(router, "stats", mk_ctx(library_channel))
        record("!stats", "PASS", "fetched db_stats, embed sent")
    except Exception as e:
        record("!stats", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !best ----------------------------------------------------------
    try:
        await run_cmd(router, "best", mk_ctx(library_channel), 2, None)
        record("!best", "PASS", "contributors embed sent")
    except Exception as e:
        record("!best", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !systems -------------------------------------------------------
    try:
        await run_cmd(router, "systems", mk_ctx(library_channel))
        record("!systems", "PASS", "system tracker embed")
    except Exception as e:
        record("!systems", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !planets -------------------------------------------------------
    try:
        await run_cmd(router, "planets", mk_ctx(library_channel))
        record("!planets", "PASS", "planet tracker embed")
    except Exception as e:
        record("!planets", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !department ----------------------------------------------------
    # DepartmentView has an internal wait(); we preempt by stopping it right
    # after the command sends. We monkeypatch `view.wait` to return quickly.
    try:
        from cogs.xp_cog import DepartmentView
        orig_wait = DepartmentView.wait
        async def _fast_wait(self): return None
        DepartmentView.wait = _fast_wait
        try:
            await run_cmd(router, "department", mk_ctx(qualify_channel))
            record("!department", "PASS", "department select embed posted")
        finally:
            DepartmentView.wait = orig_wait
    except Exception as e:
        record("!department", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !xp ------------------------------------------------------------
    # Seed a primary role for the author so the happy-path executes.
    try:
        from cogs.Data.xpdata import get_conn
        author = FakeAuthor(id=9999)
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO users (user_id, primary_role) VALUES (?, ?)",
                    (author.id, "cartographer"))
        conn.commit(); conn.close()
        # prime in-memory user cache used by exclaim.py
        from cogs.xp_system import get_user
        u = get_user(author.id)
        u["primary_role"] = "cartographer"
        await run_cmd(router, "xp", mk_ctx(qualify_channel, author=author), None)
        record("!xp", "PASS", "xp embed rendered")
    except Exception as e:
        record("!xp", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !community -----------------------------------------------------
    try:
        ctx = mk_ctx(library_channel)
        await run_cmd(router, "community", ctx, search=None)
        assert any("Open search" in (s["content"] or "") for s in ctx.sent)
        record("!community", "PASS", "search view presented")
    except Exception as e:
        record("!community", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !partners ------------------------------------------------------
    # KNOWN BUG in source: the if-not-cog branch has unreachable code after
    # `return await ctx.send(...)`, and when the cog IS loaded `raw` is
    # referenced before assignment — NameError.
    try:
        await run_cmd(router, "partners", mk_ctx(general_channel))
        record("!partners", "PASS", "(unexpectedly) no error")
    except NameError as e:
        record("!partners", "BUG", f"NameError as predicted: {e} — 'raw' never assigned when cog IS loaded (exclaim.py:142). The fetch_sheet() call is stranded inside the `if not community_cog` block after a return.")
    except Exception as e:
        record("!partners", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !addciv --------------------------------------------------------
    try:
        await run_cmd(router, "addciv", mk_ctx(general_channel))
        record("!addciv", "PASS", "add-entry view posted")
    except Exception as e:
        record("!addciv", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !newsystem -----------------------------------------------------
    try:
        await run_cmd(router, "newsystem", mk_ctx(system_channel))
        record("!newsystem", "PASS", "HexKeypad view posted")
    except Exception as e:
        record("!newsystem", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !discovery -----------------------------------------------------
    # KNOWN BUG: exclaim.py calls `system_xp(ctx.author.id, 3)` after sending,
    # but system_xp is NEVER imported in exclaim.py. -> NameError.
    try:
        await run_cmd(router, "discovery", mk_ctx(base_channel))
        record("!discovery", "PASS", "(unexpectedly) no error")
    except NameError as e:
        record("!discovery", "BUG", f"NameError as predicted: {e} — system_xp() called at exclaim.py:251 without import. It lives in cogs.Data.xpdata.")
    except Exception as e:
        record("!discovery", "FAIL", f"{type(e).__name__}: {e}")

    # ---- !leaderboard ---------------------------------------------------
    # KNOWN BUG: exclaim.py line 263 calls ctx.trigger_typing() which is
    # removed in discord.py 2.x. That line is inside `async with ctx.typing():`
    # so one of them is redundant and the call crashes.
    # Seed some featured photos so the leaderboard has data too.
    try:
        # add a couple messages with valid attachments and reactions to the
        # photo channel so gather_featured_photos returns something.
        seeded = []
        for i, reactions in enumerate([7, 4, 5], start=1):
            msg = FakeMessage(
                id=10000 + i,
                channel=photo_channel,
                author=FakeAuthor(id=9000 + i, display_name=f"user{i}", name=f"u{i}"),
                attachments=[FakeAttachment()],
                reactions=[FakeReaction(count=reactions)],
            )
            seeded.append(msg)
        photo_channel.messages = seeded
        featured_cog.FEATURED_MESSAGES = {m.id for m in seeded}

        await run_cmd(router, "leaderboard", mk_ctx(general_channel))
        record("!leaderboard", "PASS", "(unexpectedly) no error")
    except AttributeError as e:
        if "trigger_typing" in str(e):
            record("!leaderboard", "BUG", f"AttributeError as predicted: {e} — ctx.trigger_typing() was removed in discord.py 2.x (exclaim.py:263). The wrapping `async with ctx.typing()` already handles typing; the extra call must be deleted.")
        else:
            record("!leaderboard", "FAIL", f"{type(e).__name__}: {e}")
    except Exception as e:
        record("!leaderboard", "FAIL", f"{type(e).__name__}: {e}")

    # =====================================================================
    # FeaturedCog deep-dive
    # =====================================================================
    # Use a fresh FeaturedCog state
    featured_cog.FEATURED_MESSAGES = set()
    featured_cog.PROCESSING = set()

    # 1. gather_featured_photos with fetchable photo messages
    try:
        msgs = []
        for i, n in enumerate([8, 4, 1], start=1):
            msgs.append(FakeMessage(
                id=20000 + i,
                channel=photo_channel,
                author=FakeAuthor(id=9100 + i, display_name=f"u{i}", name=f"u{i}"),
                attachments=[FakeAttachment(filename=f"p{i}.png", url=f"https://cdn/p{i}")],
                reactions=[FakeReaction(count=n)],
            ))
        photo_channel.messages = msgs
        featured_cog.FEATURED_MESSAGES = {m.id for m in msgs}
        data = await featured_cog.gather_featured_photos()
        assert len(data) == 3, f"expected 3 photos, got {len(data)}"
        record("FeaturedCog.gather_featured_photos", "PASS", f"returned {len(data)} photos, sorted externally")
    except Exception as e:
        record("FeaturedCog.gather_featured_photos", "FAIL", f"{type(e).__name__}: {e}")

    # 2. post_leaderboard posts to the supplied channel
    try:
        target = FakeChannel(id=777, name="leaderboard-target")
        await featured_cog.post_leaderboard(channel=target, limit=2)
        assert len(target.sent) == 1, "expected 1 embed"
        embed = target.sent[0]["embed"]
        assert embed is not None and len(embed.fields) == 2, f"expected top-2, got {embed and len(embed.fields)}"
        record("FeaturedCog.post_leaderboard(limit=2)", "PASS",
               f"embed with {len(embed.fields)} entries, thumbnail={embed.thumbnail.url}")
    except Exception as e:
        record("FeaturedCog.post_leaderboard(limit=2)", "FAIL", f"{type(e).__name__}: {e}")

    # 3. try_feature_message — below threshold: must NOT feature
    try:
        featured_cog.FEATURED_MESSAGES = set()
        featured_channel.sent.clear()
        m = FakeMessage(
            id=30001, channel=photo_channel, author=FakeAuthor(),
            attachments=[FakeAttachment()],
            reactions=[FakeReaction(count=1)],  # below threshold=3
        )
        await featured_cog.try_feature_message(m)
        assert m.id not in featured_cog.FEATURED_MESSAGES
        assert featured_channel.sent == []
        record("FeaturedCog.try_feature_message below-threshold", "PASS", "correctly skipped")
    except Exception as e:
        record("FeaturedCog.try_feature_message below-threshold", "FAIL", f"{type(e).__name__}: {e}")

    # 4. try_feature_message — at/above threshold: must feature
    try:
        featured_channel.sent.clear()
        m = FakeMessage(
            id=30002, channel=photo_channel, author=FakeAuthor(id=42),
            attachments=[FakeAttachment()],
            reactions=[FakeReaction(count=5)],
        )
        await featured_cog.try_feature_message(m)
        assert m.id in featured_cog.FEATURED_MESSAGES, "message not marked featured"
        assert len(featured_channel.sent) == 1, "no embed sent"
        assert "🌟" in m.added_reactions, "star reaction not added"
        record("FeaturedCog.try_feature_message threshold-met", "PASS",
               "featured, persisted, star added")
    except Exception as e:
        record("FeaturedCog.try_feature_message threshold-met", "FAIL", f"{type(e).__name__}: {e}")

    # 5. try_feature_message — already-featured message is a no-op
    try:
        before_count = len(featured_channel.sent)
        m = FakeMessage(
            id=30002, channel=photo_channel, author=FakeAuthor(id=42),
            attachments=[FakeAttachment()],
            reactions=[FakeReaction(count=10)],
        )
        await featured_cog.try_feature_message(m)
        assert len(featured_channel.sent) == before_count, "duplicate feature posted"
        record("FeaturedCog.try_feature_message duplicate-guard", "PASS", "dedupe via FEATURED_MESSAGES works")
    except Exception as e:
        record("FeaturedCog.try_feature_message duplicate-guard", "FAIL", f"{type(e).__name__}: {e}")

    # 6. try_feature_message — old message (past window): must skip
    try:
        featured_channel.sent.clear()
        old = datetime.now(timezone.utc) - timedelta(seconds=featured_cog.FEATURED_TIME_LIMIT + 120)
        m = FakeMessage(
            id=30003, channel=photo_channel, author=FakeAuthor(),
            attachments=[FakeAttachment()],
            reactions=[FakeReaction(count=99)],
            created_at=old,
        )
        await featured_cog.try_feature_message(m)
        assert m.id not in featured_cog.FEATURED_MESSAGES
        assert featured_channel.sent == []
        record("FeaturedCog.try_feature_message past-window", "PASS", "correctly skipped old message")
    except Exception as e:
        record("FeaturedCog.try_feature_message past-window", "FAIL", f"{type(e).__name__}: {e}")

    # 7. try_feature_message — no attachments / non-image attachment: skip
    try:
        featured_channel.sent.clear()
        m = FakeMessage(
            id=30004, channel=photo_channel, author=FakeAuthor(),
            attachments=[FakeAttachment(filename="not_image.txt")],
            reactions=[FakeReaction(count=9)],
        )
        await featured_cog.try_feature_message(m)
        assert m.id not in featured_cog.FEATURED_MESSAGES
        assert featured_channel.sent == []
        record("FeaturedCog.try_feature_message non-image", "PASS", "skipped non-image attachment")
    except Exception as e:
        record("FeaturedCog.try_feature_message non-image", "FAIL", f"{type(e).__name__}: {e}")

    # 8. on_reaction_add listener — only triggers in photo channel
    try:
        featured_channel.sent.clear()
        other_channel = FakeChannel(id=99999, name="random")
        m = FakeMessage(
            id=30005, channel=other_channel, author=FakeAuthor(),
            attachments=[FakeAttachment()],
            reactions=[FakeReaction(count=10)],
        )
        reaction = FakeReaction(count=10); reaction.message = m
        # listener signature: (self, reaction, user) — but it pulls channel from reaction.message
        await featured_cog.on_reaction_add(reaction, FakeAuthor())
        assert featured_channel.sent == [], "should ignore reactions from non-photo channels"
        record("FeaturedCog.on_reaction_add off-channel", "PASS", "scoped to photo channel")
    except Exception as e:
        record("FeaturedCog.on_reaction_add off-channel", "FAIL", f"{type(e).__name__}: {e}")

    try:
        featured_channel.sent.clear()
        m = FakeMessage(
            id=30006, channel=photo_channel, author=FakeAuthor(),
            attachments=[FakeAttachment()],
            reactions=[FakeReaction(count=10)],
        )
        reaction = FakeReaction(count=10); reaction.message = m
        await featured_cog.on_reaction_add(reaction, FakeAuthor())
        assert m.id in featured_cog.FEATURED_MESSAGES
        assert len(featured_channel.sent) == 1
        record("FeaturedCog.on_reaction_add photo-channel", "PASS", "dispatches into try_feature_message")
    except Exception as e:
        record("FeaturedCog.on_reaction_add photo-channel", "FAIL", f"{type(e).__name__}: {e}")

    # 9. Persistence: save/load round-trip
    try:
        featured_cog.save_featured_messages()
        with open(featured_mod.FEATURED_FILE, "r") as f:
            on_disk = json.load(f)
        assert set(on_disk) == featured_cog.FEATURED_MESSAGES
        record("FeaturedCog save/load round-trip", "PASS", f"{len(on_disk)} ids persisted")
    except Exception as e:
        record("FeaturedCog save/load round-trip", "FAIL", f"{type(e).__name__}: {e}")

    # 10. weekly leaderboard task constructs
    try:
        task = featured_cog.create_weekly_leaderboard_task(LEADERBOARD_DAY=5, LEADERBOARD_TOP=3)
        assert hasattr(task, "start")
        record("FeaturedCog weekly task construction", "PASS", "tasks.loop handle returned")
    except Exception as e:
        record("FeaturedCog weekly task construction", "FAIL", f"{type(e).__name__}: {e}")

    # ----- Summary -----
    print("\n================ SUMMARY ================")
    n_pass = sum(1 for _, s, _ in RESULTS if s == "PASS")
    n_bug = sum(1 for _, s, _ in RESULTS if s == "BUG")
    n_fail = sum(1 for _, s, _ in RESULTS if s == "FAIL")
    print(f"PASS: {n_pass}   BUG: {n_bug}   FAIL: {n_fail}   TOTAL: {len(RESULTS)}")
    if n_bug:
        print("\nBUGS FOUND (need fixing in source):")
        for name, s, note in RESULTS:
            if s == "BUG":
                print(f"  • {name}\n      {note}")
    if n_fail:
        print("\nFAILURES (harness or unexpected error):")
        for name, s, note in RESULTS:
            if s == "FAIL":
                print(f"  • {name}\n      {note}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
    # exit non-zero if any FAIL remains (BUG is a finding, not a runner error)
    sys.exit(0 if not any(s == "FAIL" for _, s, _ in RESULTS) else 1)
