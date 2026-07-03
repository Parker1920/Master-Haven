# -------------------- cogs/ask.py --------------------
# "Ask the Guide" — lets people talk to the Voyager's Haven brain.
#
# Two ways in:
#   /ask <question>          — a slash command (discoverable, cooldown-limited)
#   @The Keeper <question>   — a natural @mention in any channel (or a DM)
#
# Both hit the Haven Brain's public "voyager" mind, a locally-run (Ollama),
# code-guarded RAG assistant that only answers about No Man's Sky and Haven.
# The bot is a thin client — all the knowledge, guardrails, and generation
# live in the brain service. It reaches that service by container name over the
# shared `haven-net` docker network (same way it reaches the Haven API).
#
# Env:
#   BRAIN_API      URL of the Haven Brain API.  Default http://haven-brain-api:8020
#   BRAIN_MIND     which mind to talk to.        Default "voyager"
#   BRAIN_BOT_KEY  optional shared secret; only sent if set (must match the
#                  brain's HAVEN_BRAIN_BOT_KEY).

import os
import logging
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("commands.ask")

BRAIN_API = os.getenv("BRAIN_API", "http://haven-brain-api:8020").rstrip("/")
BRAIN_MIND = os.getenv("BRAIN_MIND", "voyager")
BRAIN_BOT_KEY = os.getenv("BRAIN_BOT_KEY")  # optional

# Discord's hard message cap is 2000 chars; leave headroom.
MAX_DISCORD = 1990
# The local model can be slow to warm up / generate on modest hardware.
REQUEST_TIMEOUT = 120

RESTING_MSG = "The Guide is resting right now — try again in a moment. \U0001F30C"


def _chunk(text: str, size: int = MAX_DISCORD):
    """Split a long reply into Discord-sized pieces on nice boundaries."""
    text = (text or "").strip() or "…"
    out = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut < size // 2:
            cut = text.rfind(" ", 0, size)
        if cut <= 0:
            cut = size
        out.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        out.append(text)
    return out


class AskCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        )

    async def cog_unload(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _ask_brain(self, message: str, session_id: str) -> str:
        """Send one turn to the brain and return the answer text.

        `session_id` keys the conversation so the mind remembers context across
        calls — we use the Discord user id so each person has their own thread.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            )

        headers = {}
        if BRAIN_BOT_KEY:
            headers["X-Bot-Key"] = BRAIN_BOT_KEY

        url = f"{BRAIN_API}/api/minds/{BRAIN_MIND}/ask"
        payload = {"message": message, "session_id": session_id}

        async with self._session.post(url, json=payload, headers=headers) as resp:
            data = await resp.json(content_type=None)
            if resp.status != 200 or not isinstance(data, dict):
                detail = data.get("detail") if isinstance(data, dict) else None
                raise RuntimeError(detail or f"HTTP {resp.status}")
            return (data.get("answer") or "").strip() or "…"

    async def _reply_chunks(self, first_send, more_send, answer: str):
        """Send `answer` across as many messages as Discord's limit requires."""
        pieces = _chunk(answer)
        await first_send(pieces[0])
        for extra in pieces[1:]:
            await more_send(extra)

    # ============================================================
    # /ask
    # ============================================================
    @app_commands.command(
        name="ask",
        description="Ask the Voyager's Haven Guide about No Man's Sky or the Haven map.",
    )
    @app_commands.describe(question="What do you want to know?")
    @app_commands.checks.cooldown(1, 8.0, key=lambda i: i.user.id)
    async def ask(self, interaction: discord.Interaction, question: str):
        # Public thinking indicator — replies may take a few seconds.
        await interaction.response.defer(thinking=True)
        try:
            answer = await self._ask_brain(question, f"discord:{interaction.user.id}")
        except Exception:
            log.exception("ask command: brain request failed")
            await interaction.followup.send(RESTING_MSG)
            return

        await self._reply_chunks(
            interaction.followup.send,
            interaction.followup.send,
            answer,
        )

    @ask.error
    async def ask_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"Slow down, Voyager. Try again in {error.retry_after:.0f}s."
        else:
            log.exception("ask command error", exc_info=error)
            msg = "Something went wrong reaching the Guide."
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(msg, ephemeral=True)

    # ============================================================
    # @mention chat — "like people are talking to it"
    # ============================================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # This listener is ADDITIVE — the main on_message in bot.py (XP +
        # process_commands) still runs independently. We only act on a direct
        # @mention of the bot, so we never interfere with normal chatter.
        if message.author.bot or not self.bot.user:
            return
        if self.bot.user not in message.mentions or message.mention_everyone:
            return

        # Strip the bot mention out of the text.
        content = message.content or ""
        for token in (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"):
            content = content.replace(token, " ")
        content = content.strip()

        if not content:
            await message.reply(
                "Ask me about No Man's Sky or the Haven map, Voyager. \U0001F30C",
                mention_author=False,
            )
            return

        try:
            async with message.channel.typing():
                answer = await self._ask_brain(content, f"discord:{message.author.id}")
        except Exception:
            log.exception("mention chat: brain request failed")
            await message.reply(RESTING_MSG, mention_author=False)
            return

        pieces = _chunk(answer)
        await message.reply(pieces[0], mention_author=False)
        for extra in pieces[1:]:
            await message.channel.send(extra)


async def setup(bot: commands.Bot):
    await bot.add_cog(AskCog(bot))
