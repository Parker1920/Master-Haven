import sys, os
sys.path.append(os.path.dirname(__file__))  
import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta, timezone
from Haven_stats import Haven_statsCog
import difflib 

# -------------------- Constants --------------------
SESSION_TIMEOUT = 30
MAX_COMMANDS_PER_SESSION = 3
MAX_FAILS = 3
SPECIAL_USER_ID = 1265127644652109834
DWEEB_IMAGE_URL = "https://cdn.discordapp.com/attachments/1483946204919501030/1485174291338366976/VideoCapture_20260203-180628.jpg"

# -------------------- Globals --------------------
active_sessions = {}

keeper_responses = [
    "Hello, Voyager!",
    "Greetings, voyager of the stars!",
    "The Keeper witnesses you.",
    "Hullo, Voyager! Fair voyage!",
    "Hello! May your Voyage be bright.",
    "I like map.",
    "We witness your voyage"
]

fail_responses = ["huh?", "one more time?", "Gather your thoughts and resummon me"]

# -------------------- Cog --------------------
class PersonalityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------- Handle 'tell' --------------------
    async def handle_tell(self, message):
        parts = message.content.split(" ", 2)
        if len(parts) < 3:
            await message.channel.send("Format: tell <user> <message>")
            return

        target_name = parts[1].lower()
        msg_text = parts[2].strip()

        # ---- Special user tells everyone ----
        if message.author.id == SPECIAL_USER_ID and target_name == "everyone":
            if message.author.id in active_sessions:
                await message.channel.send(f"@everyone You're {msg_text[len('everyone'):].strip()}")
                for member in message.channel.members:
                    if member.bot or member == message.author:
                        continue
                    try:
                        await member.send(DWEEB_IMAGE_URL)
                    except discord.Forbidden:
                        continue
                return

        # ---- Normal target lookup ----
        target = discord.utils.find(
            lambda m: target_name in m.display_name.lower() or target_name in m.name.lower(),
            message.guild.members
        )
        if not target:
            await message.channel.send(f"User '{parts[1]}' not found.")
            return

        pronouns = ["he", "she", "they", "it", "him", "her", "them", "he's", "she's", "they're"]
        words = msg_text.split()
        first_word = words[0].lower() if words else ""

        close = difflib.get_close_matches(first_word, pronouns, n=1, cutoff=0.7)
        immersive_text = f"You're {' '.join(words[1:]).strip()}" if close else msg_text

        await message.channel.send(f"{target.mention} {immersive_text}")

        if "dweeb" in msg_text.lower():
            try:
                await target.send(DWEEB_IMAGE_URL)
            except discord.Forbidden:
                await message.channel.send(f"Couldn't DM {target.display_name}, their DMs might be closed.")

    # -------------------- Handle active session --------------------
    async def handle_session(self, message):
        user_id = message.author.id
        session = active_sessions.get(user_id)
        if not session:
            return

        now = datetime.now(timezone.utc)
        if session["expiry"] < now:
            active_sessions.pop(user_id, None)
            return

        content = message.content.lower().strip()
        valid_command = False

        # ---- tell ----
        if content.startswith("tell "):
            await self.handle_tell(message)
            valid_command = True
        # ---- stats / map / best ----
        elif content in ["stats", "show me the stars"] or content.startswith("best"):
            stats_cog = self.bot.get_cog("Haven_statsCog")
            if stats_cog:
                if content == "stats":
                    await stats_cog.send_stats(message.channel)
                elif content == "show me the stars":
                    await stats_cog.send_map(message.channel)
                elif content.startswith("best"):
                    parts = message.content.split()
                    count = 10
                    community = None
                    if len(parts) >= 2 and parts[1].isdigit():
                        count = int(parts[1])
                        if len(parts) >= 3:
                            community = parts[2].upper()
                    elif len(parts) >= 2:
                        community = parts[1].upper()
                    await stats_cog.send_best(message.channel, count=count, community=community)
            else:
                await message.channel.send("Haven stats commands are currently unavailable.")
            valid_command = True

        # ---- leaderboard (featured) ----
        elif "leaderboard" in content:
            FEATURED_CHANNEL_ID = int(os.getenv("FEATURED_CHANNEL_ID", "0"))
            if message.channel.id != FEATURED_CHANNEL_ID:
                await message.channel.send("You can only run this command in the Featured channel.")
            else:
                featured_cog = self.bot.get_cog("FeaturedCog")
                if featured_cog:
                    await featured_cog.post_leaderboard()
                else:
                    await message.channel.send("My Archives are failing")
            valid_command = True

        # ---- logs (CommunityCog) ----
        elif content.startswith("show logs"):
            parts = message.content.split(" ", 2)
            search_term = parts[2] if len(parts) >= 3 else None
            community_cog = self.bot.get_cog("CommunityCog")
            if community_cog:
                ctx = await self.bot.get_context(message)
                await community_cog.show_logs(ctx, search=search_term)
            else:
                await message.channel.send("The archives are unreachable.")
            valid_command = True

        # ---- End session if valid ----
        if valid_command:
            active_sessions.pop(user_id, None)
            return

        # ---- Fail handling ----
        session["fails"] += 1
        fail_index = min(session["fails"] - 1, len(fail_responses) - 1)
        await message.channel.send(fail_responses[fail_index])

        if session["fails"] >= MAX_FAILS:
            active_sessions.pop(user_id, None)

    # -------------------- Listener --------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.lower().strip()
        user_id = message.author.id
        now = datetime.now(timezone.utc)

        # ---- Cleanup expired sessions ----
        expired = [uid for uid, sess in active_sessions.items() if sess["expiry"] < now]
        for uid in expired:
            active_sessions.pop(uid, None)

        # ---- Active session ----
        if user_id in active_sessions:
            await self.handle_session(message)
            return

        # ---- Start new Keeper session ----
        if content == "keeper":
            active_sessions[user_id] = {
                "expiry": now + timedelta(seconds=SESSION_TIMEOUT),
                "count": 0,
                "fails": 0
            }
            await message.channel.send(random.choice(keeper_responses))
            return

        # ---- Greetings outside session ----
        greetings = ["hello, keeper", "hello keeper", "hi keeper"]
        if any(content.startswith(g) for g in greetings):
            await message.channel.send(random.choice(keeper_responses))
            return
# -------------------- Setup --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(PersonalityCog(bot))