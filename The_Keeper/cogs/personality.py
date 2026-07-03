import sys, os
sys.path.append(os.path.dirname(__file__))  
import discord
from discord.ext import commands
import random
from datetime import datetime, timedelta, timezone
import difflib 
import traceback

# -------------------- Constants --------------------
SESSION_TIMEOUT = 30
MAX_FAILS = 3
SPECIAL_USER_ID = 1265127644652109834
DWEEB_IMAGE_URL = "https://cdn.discordapp.com/attachments/1483946204919501030/1485174291338366976/VideoCapture_20260203-180628.jpg"

# -------------------- Globals --------------------
active_sessions = {}

keeper_responses = [
    "Hello, Voyager!",
    "Greetings, {member.mention}, voyager of the stars!",
    "The Keeper witnesses you.",
    "Hullo, Voyager! Fair voyage!",
    "Hello! May your Voyage be bright.",
    "I like map.",
    "We witness your voyage, {member.mention}"
]

fail_responses = ["huh?", "one more time?", "Gather your thoughts and resummon me."]

# -------------------- Mock Interaction for Slash Commands --------------------
class MockInteraction:
    def __init__(self, msg):
        self.channel = msg.channel
        self.user = msg.author
        self.guild = msg.guild
        self.response = self
        self.followup = self 
    
    async def send_message(self, content_str, *args, **kwargs):
        return await self.channel.send(content_str)
    
    async def send(self, content_str, *args, **kwargs):
        return await self.channel.send(content_str)
    
    async def defer(self, *args, **kwargs):
        pass


# -------------------- Cog --------------------
class PersonalityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------- Handle Session --------------------
    async def handle_session(self, message):
        user_id = message.author.id
        content = message.content.strip()
        lower_content = content.lower()
        
        now = datetime.now(timezone.utc)
        if active_sessions[user_id]["expiry"] < now:
            active_sessions.pop(user_id, None)
            return 
        active_sessions[user_id]["expiry"] = now + timedelta(seconds=SESSION_TIMEOUT)

        # Triggers for either "tell" or "say"
        if lower_content.startswith("tell") or lower_content.startswith("say"):
            await self.handle_tell(message)
            active_sessions.pop(user_id, None) 
            return

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

                active_sessions.pop(user_id, None) 
                return
            except Exception as e:
                print("[SLASH CALLBACK EXCEPTION DETECTED]")
                traceback.print_exc() 
                await message.channel.send("An error occurred.")
                active_sessions.pop(user_id, None)
                return

        active_sessions[user_id]["fails"] += 1
        
        if active_sessions[user_id]["fails"] >= MAX_FAILS:
            await message.channel.send(fail_responses[2])
            active_sessions.pop(user_id, None)
        else:
            await message.channel.send(random.choice(fail_responses[:2]))
        
        return

    # -------------------- Handle 'tell' or 'say' --------------------
    async def handle_tell(self, message):
        parts = message.content.split(" ", 2)
        if len(parts) < 3:
            cmd_used = parts[0].lower()
            await message.channel.send(f"Format: {cmd_used} <user> <message>")
            return

        target_name = parts[1].lower()
        msg_text = parts[2].strip()

        # ---- Special user tells everyone ----
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

        # ---- Normal target lookup ----
        target = discord.utils.find(
            lambda m: target_name in m.display_name.lower() or target_name in m.name.lower(),
            message.guild.members
        )
        if not target:
            await message.channel.send(f"User '{parts[1]}' not found.")
            return

        # ---- Smart Pronoun Mapper ----
        pronoun_map = {
            "he": "he is", "him": "he is", "he's": "he is",
            "she": "she is", "her": "she is", "she's": "she is",
            "they": "they are", "them": "they are", "they're": "they are",
            "it": "it is", "its": "it is", "it's": "it is"
        }

        words = msg_text.split()
        first_word = words[0].lower() if words else ""
        
        close_match = difflib.get_close_matches(first_word, list(pronoun_map.keys()), n=1, cutoff=0.7)
        
        if close_match:
            matched_pronoun = close_match[0]
            replacement_phrase = pronoun_map[matched_pronoun]
            immersive_text = f"{replacement_phrase} {' '.join(words[1:]).strip()}"
        else:
            immersive_text = msg_text

        await message.channel.send(f"{target.mention} {immersive_text}")

        if "dweeb" in msg_text.lower():
            try:
                await target.send(DWEEB_IMAGE_URL)
            except discord.Forbidden:
                await message.channel.send(f"Couldn't DM {target.display_name}, their DMs might be closed.")

    # -------------------- Listener --------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.lower().strip()
        user_id = message.author.id
        now = datetime.now(timezone.utc)
        
        # ---- Cleanup expired sessions globally ----
        expired = [uid for uid, sess in active_sessions.items() if sess["expiry"] < now]
        for uid in expired:
            active_sessions.pop(uid, None)

        # ---- Route Active session ----
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
            await message.channel.send(random.choice(keeper_responses).format(member=message.author))
            return

        # ---- Greetings outside session ----
        greetings = ["hello, keeper", "hello keeper", "hi keeper", "hey keeper"]
        if any(content.startswith(g) for g in greetings):
            await message.add_reaction("👋")
            await message.channel.send(random.choice(keeper_responses).format(member=message.author))
            return
            
        if "keeper" in content:
            await message.add_reaction("👀")
        if "right, keeper?" in content or "right keeper?" in content:
            await message.channel.send("yep")
            return

# -------------------- Setup --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(PersonalityCog(bot))
