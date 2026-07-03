import os
import logging
import aiohttp
import discord
import random
import difflib
from datetime import datetime, timedelta, timezone
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("commands.ask")

BRAIN_API = os.getenv("BRAIN_API", "http://haven-brain-api:8020").rstrip("/")
BRAIN_MIND = os.getenv("BRAIN_MIND", "voyager")
BRAIN_BOT_KEY = os.getenv("BRAIN_BOT_KEY")

MAX_DISCORD = 1990
REQUEST_TIMEOUT = 120
RESTING_MSG = "The Guide is resting right now — try again in a moment. \U0001F30C"

# ---- Keeper Constants ----
SESSION_TIMEOUT = 30
SPECIAL_USER_ID = 1265127644652109834
DWEEB_IMAGE_URL = "https://cdn.discordapp.com/attachments/1483946204919501030/1485174291338366976/VideoCapture_20260203-180628.jpg"

KEEPER_RESPONSES = [
    "Hello, Voyager!",
    "Greetings, {member.mention}, voyager of the stars!",
    "The Keeper witnesses you.",
    "Hullo, Voyager! Fair voyage!",
    "Hello! May your Voyage be bright.",
    "I like map.",
    "We witness your voyage, {member.mention}"
]


# ---- Mock Interaction for executing Slash Commands inside text sessions ----
class MockInteraction:
    def __init__(self, msg: discord.Message):
        self.channel = msg.channel
        self.user = msg.author
        self.guild = msg.guild
        self.response = self
        self.followup = self 
    
    async def send_message(self, content_str: str, *args, **kwargs):
        return await self.channel.send(content_str)
    
    async def send(self, content_str: str, *args, **kwargs):
        return await self.channel.send(content_str)
    
    async def defer(self, *args, **kwargs):
        pass


def _chunk(text: str, size: int = MAX_DISCORD):
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
        # Track active keeper sessions
        self.active_sessions: dict[int, dict] = {}

    async def cog_load(self):
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        )

    async def cog_unload(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def _ask_brain(self, message: str, session_id: str) -> str:
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
        pieces = _chunk(answer)
        await first_send(pieces[0])
        for extra in pieces[1:]:
            await more_send(extra)

    # ============================================================
    # Keeper Session Handlers
    # ============================================================
    async def handle_tell(self, message: discord.Message):
        parts = message.content.split(" ", 2)
        if len(parts) < 3:
            cmd_used = parts[0].lower()
            await message.channel.send(f"Format: {cmd_used} <user> <message>")
            return

        target_name = parts[1].lower()
        msg_text = parts[2].strip()

        if message.author.id == SPECIAL_USER_ID and target_name == "everyone":
            await message.channel.send(f"@everyone You're {msg_text}")
            for member in message.channel.members:
                if member.bot or member == message.author:
                    continue
                try:
                    await member.send(DWEEB_IMAGE_URL)
                except discord.Forbidden:
                    continue
            return

        if not message.guild:
            return

        target = discord.utils.find(
            lambda m: target_name in m.display_name.lower() or target_name in m.name.lower(),
            message.guild.members
        )
        if not target:
            await message.channel.send(f"User '{parts[1]}' not found.")
            return

        pronoun_map = {
            "he": "you are", "him": "you", "he's": "you're", "his": "your",
            "she": "you are", "her": "you", "she's": "you're", "hers": "yours",
            "they": "you are", "them": "you", "they're": "you're", "their": "your", "theirs": "yours",
            "it": "you are", "its": "your", "it's": "you're"
        }

        words = msg_text.split()
        first_word = words[0].lower() if words else ""
        close_match = difflib.get_close_matches(first_word, list(pronoun_map.keys()), n=1, cutoff=0.7)
        
        if close_match:
            immersive_text = f"{pronoun_map[close_match[0]]} {' '.join(words[1:]).strip()}"
        else:
            immersive_text = msg_text

        await message.channel.send(f"{target.mention} {immersive_text}")

        if "dweeb" in msg_text.lower():
            try:
                await target.send(DWEEB_IMAGE_URL)
            except discord.Forbidden:
                await message.channel.send(f"Couldn't DM {target.display_name}, their DMs might be closed.")

    async def handle_keeper_session(self, message: discord.Message):
        user_id = message.author.id
        content = message.content.strip()
        lower_content = content.lower()
        
        now = datetime.now(timezone.utc)
        if self.active_sessions[user_id]["expiry"] < now:
            self.active_sessions.pop(user_id, None)
            return 
            
        # Refresh session window
        self.active_sessions[user_id]["expiry"] = now + timedelta(seconds=SESSION_TIMEOUT)

        # 1. Check for 'tell' or 'say'
        if lower_content.startswith("tell") or lower_content.startswith("say"):
            await self.handle_tell(message)
            self.active_sessions.pop(user_id, None) 
            return

        # 2. Check for matching App Slash Commands
        command_name = lower_content.split()[0] if lower_content.split() else ""
        slash_command = discord.utils.get(self.bot.tree.get_commands(), name=command_name)
        
        if slash_command and isinstance(slash_command, discord.app_commands.Command):
            args = content.split()[1:]
            mock_interaction = MockInteraction(message)
            try:
                cog_instance = slash_command.binding
                if cog_instance is not None:
                    await slash_command.callback(cog_instance, mock_interaction, *args)
                else:
                    await slash_command.callback(mock_interaction, *args)

                self.active_sessions.pop(user_id, None) 
                return
            except Exception:
                log.exception("Keeper session slash callback failed")
                await message.channel.send("An error occurred.")
                self.active_sessions.pop(user_id, None)
                return

        # 3. Fallback: Leave responses up to the Brain (AI file handling)
        # Instead of throwing a "huh?", we route the text directly to the AI guide.
        try:
            async with message.channel.typing():
                answer = await self._ask_brain(content, f"discord:{message.author.id}")
            pieces = _chunk(answer)
            await message.reply(pieces[0], mention_author=False)
            for extra in pieces[1:]:
                await message.channel.send(extra)
        except Exception:
            log.exception("Keeper session brain fallback failed")
            await message.reply(RESTING_MSG, mention_author=False)
            
        # Close the session after the AI fulfills the context window conversation turn
        self.active_sessions.pop(user_id, None)

    # ============================================================
    # /ask Command
    # ============================================================
    @app_commands.command(
        name="ask",
        description="Ask the Voyager's Haven Guide about No Man's Sky or the Haven map.",
    )
    @app_commands.describe(question="What do you want to know?")
    @app_commands.checks.cooldown(1, 8.0, key=lambda i: i.user.id)
    async def ask(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer(thinking=True)
        try:
            answer = await self._ask_brain(question, f"discord:{interaction.user.id}")
        except Exception:
            log.exception("ask command: brain request failed")
            await interaction.followup.send(RESTING_MSG)
            return

        await self._reply_chunks(interaction.followup.send, interaction.followup.send, answer)

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
    # Additive Message Listener
    # ============================================================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not self.bot.user:
            return

        content = message.content.lower().strip()
        user_id = message.author.id
        now = datetime.now(timezone.utc)
        
        # Cleanup expired sessions globally
        expired = [uid for uid, sess in self.active_sessions.items() if sess["expiry"] < now]
        for uid in expired:
            self.active_sessions.pop(uid, None)

        # ---- 1. Route ongoing active keeper sessions ----
        if user_id in self.active_sessions:
            await self.handle_keeper_session(message)
            return

        # ---- 2. Initialize new Keeper session ----
        if content == "keeper":
            self.active_sessions[user_id] = {
                "expiry": now + timedelta(seconds=SESSION_TIMEOUT)
            }
            await message.channel.send(random.choice(KEEPER_RESPONSES).format(member=message.author))
            return

        # ---- 3. Passive Context/Greeting checks outside sessions ----
        greetings = ["hello, keeper", "hello keeper", "hi keeper", "hey keeper"]
        if any(content.startswith(g) for g in greetings):
            await message.add_reaction("👋")
            await message.channel.send(random.choice(KEEPER_RESPONSES).format(member=message.author))
            return
            
        if "keeper" in content:
            await message.add_reaction("👀")
        if "right, keeper?" in content or "right keeper?" in content:
            await message.channel.send("yep")
            return

        # ---- 4. Direct @Mention handling (Standard ask behavior) ----
        if self.bot.user in message.mentions and not message.mention_everyone:
            tokens = (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>")
            cleaned_content = message.content or ""
            for token in tokens:
                cleaned_content = cleaned_content.replace(token, " ")
            cleaned_content = cleaned_content.strip()

            if not cleaned_content:
                await message.reply(
                    "Ask me about No Man's Sky or the Haven map, Voyager. \U0001F30C",
                    mention_author=False,
                )
                return

            try:
                async with message.channel.typing():
                    answer = await self._ask_brain(cleaned_content, f"discord:{message.author.id}")
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
