# -------------------- bot.py ----------------
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio, os, sys
import json
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
# -------------------- Load Environment --------------------
ENV_PATH = '/storage/emulated/0/Voyage/The_Keeper/.env'
if not os.path.exists(ENV_PATH):
    raise FileNotFoundError(f".env file not found at {ENV_PATH}")

load_dotenv(ENV_PATH)

def get_env_int(key, default=None):
    value = os.getenv(key)
    if value is None or value == "":
        return default
    try:
        return int(value.strip())
    except Exception:
        print(f"[ENV WARNING] Invalid int for {key}: {value}")
        return default
        
def normalize(name: str):
    return name.split(" ")[-1].split(":")[-1]

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

HAVEN_API = os.getenv("HAVEN_API", "https://havenmap.online")


# -------------------- CONFIG --------------------
ROLES = {
    "cartographer": {
        "lead": get_env_int("ROLE_LEAD_CARTOGRAPHER"),
        "senior": get_env_int("ROLE_SENIOR_CARTOGRAPHER"),
        "voyager": get_env_int("ROLE_VOYAGER_CARTOGRAPHER"),
        "standard": get_env_int("ROLE_CARTOGRAPHER"),
        "initiate": get_env_int("ROLE_INITIATE_CARTOGRAPHER"),
        "primary": get_env_int("ROLE_PRIMARY_CARTOGRAPHER"),
    },
    "xenobiologist": {
        "lead": get_env_int("ROLE_LEAD_XENOBIOLOGIST"),
        "senior": get_env_int("ROLE_SENIOR_XENOBIOLOGIST"),
        "voyager": get_env_int("ROLE_VOYAGER_XENOBIOLOGIST"),
        "standard": get_env_int("ROLE_XENOBIOLOGIST"),
        "initiate": get_env_int("ROLE_INITIATE_XENOBIOLOGIST"),
        "primary": get_env_int("ROLE_PRIMARY_XENOBIOLOGIST"),
    },
    "diplomat": {
        "lead": get_env_int("ROLE_LEAD_DIPLOMAT"),
        "senior": get_env_int("ROLE_SENIOR_DIPLOMAT"),
        "voyager": get_env_int("ROLE_VOYAGER_DIPLOMAT"),
        "standard": get_env_int("ROLE_DIPLOMAT"),
        "initiate": get_env_int("ROLE_INITIATE_DIPLOMAT"),
        "primary": get_env_int("ROLE_PRIMARY_DIPLOMAT"),
    },
    "architect": {
        "lead": get_env_int("ROLE_LEAD_ARCHITECT"),
        "senior": get_env_int("ROLE_SENIOR_ARCHITECT"),
        "voyager": get_env_int("ROLE_VOYAGER_ARCHITECT"),
        "standard": get_env_int("ROLE_ARCHITECT"),
        "initiate": get_env_int("ROLE_INITIATE_ARCHITECT"),
        "primary": get_env_int("ROLE_PRIMARY_ARCHITECT"),
    },
    "engineer": {
        "lead": get_env_int("ROLE_LEAD_ENGINEER"),
        "senior": get_env_int("ROLE_SENIOR_ENGINEER"),
        "voyager": get_env_int("ROLE_VOYAGER_ENGINEER"),
        "standard": get_env_int("ROLE_ENGINEER"),
        "initiate": get_env_int("ROLE_INITIATE_ENGINEER"),
        "primary": get_env_int("ROLE_PRIMARY_ENGINEER"),
    },
    "historian": {
        "lead": get_env_int("ROLE_LEAD_HISTORIAN"),
        "senior": get_env_int("ROLE_SENIOR_HISTORIAN"),
        "voyager": get_env_int("ROLE_VOYAGER_HISTORIAN"),
        "standard": get_env_int("ROLE_HISTORIAN"),
        "initiate": get_env_int("ROLE_INITIATE_HISTORIAN"),
        "primary": get_env_int("ROLE_PRIMARY_HISTORIAN"),
    },
}

# -------------------- PRIMARY ROLE MAP --------------------
PRIMARY_ROLES = {
    "cartographer": get_env_int("ROLE_PRIMARY_CARTOGRAPHER"),
    "xenobiologist": get_env_int("ROLE_PRIMARY_XENOBIOLOGIST"),
    "diplomat": get_env_int("ROLE_PRIMARY_DIPLOMAT"),
    "architect": get_env_int("ROLE_PRIMARY_ARCHITECT"),
    "engineer": get_env_int("ROLE_PRIMARY_ENGINEER"),
    "historian": get_env_int("ROLE_PRIMARY_HISTORIAN"),
}

# -------------------- CHANNELS --------------------
CHANNELS = {
    "system": get_env_int("SYSTEM_CHANNEL_ID"),
    "planet": get_env_int("PLANET_CHANNEL_ID"),

    "fauna": get_env_int("FAUNA_CHANNEL_ID"),
    "flora": get_env_int("FLORA_CHANNEL_ID"),

    "base": get_env_int("BASE_CHANNEL_ID"),
    "out": get_env_int("OUT_CHANNEL_ID"),

    "ship": [get_env_int("CRASH_CHANNEL_ID"),
get_env_int("SENTINEL_CHANNEL_ID")],

    "tool": [get_env_int("TOOL_CHANNEL_ID"), get_env_int("STAFF_CHANNEL_ID")],

    "social": get_env_int("CHANNEL_SOCIAL_MEDIA"),
    "events": get_env_int("CHANNEL_EVENT"),
    "diplomat": get_env_int("CHANNEL_DIPLOMAT"),
    "voyagers": get_env_int("CHANNEL_VOYAGERS"),
    "haven_project": get_env_int("CHANNEL_HAVEN_PROJECT"),

    "welcome": get_env_int("WELCOME_CHANNEL_ID"),
    "photo": get_env_int("PHOTO_CHANNEL_ID"),
    "contact": get_env_int("CONTACT_CHANNEL_ID"),
    "featured": get_env_int("FEATURED_CHANNEL_ID"),
    "general": get_env_int("GENERAL_CHANNEL_ID"),
    "qualify":
get_env_int("QUALIFY_CHANNEL_ID"),
    "library":
get_env_int("LIBRARY_CHANNEL_ID"),
    "help":
get_env_int("HELP_CHANNEL_ID"),

    "cartographer_office": get_env_int("C_OFFICE_CHANNEL_ID"),
    "xeno_office": get_env_int("X_OFFICE_CHANNEL_ID"),
    "architect_office": get_env_int("A_OFFICE_CHANNEL_ID"),
    "engineer_office": get_env_int("E_OFFICE_CHANNEL_ID"),
    "historian_office": get_env_int("H_OFFICE_CHANNEL_ID"),
}
from exchange.exchange import BASE_URL, API_KEY

# -------------------- XP ENABLED CHANNELS
XP_ENABLED_CHANNELS = [
    CHANNELS["system"],
    CHANNELS["planet"],
    CHANNELS["fauna"],
    CHANNELS["flora"],
    CHANNELS["base"],
    CHANNELS["out"],
    CHANNELS["ship"],
    CHANNELS["tool"],
    CHANNELS["cartographer_office"],
    CHANNELS["xeno_office"],
    CHANNELS["architect_office"],
    CHANNELS["engineer_office"],
    CHANNELS["historian_office"],
]

HOME_ROLE_ID = get_env_int("HOME_ROLE_ID")
AWAY_ROLE_ID = get_env_int("AWAY_ROLE_ID")

FEATURED_THRESHOLD = 5
FEATURED_TIME_LIMIT = 7 * 24 * 60 * 60
LEADERBOARD_DAY = 5
LEADERBOARD_TOP = 5

role_welcome_messages = {
    HOME_ROLE_ID: "Welcome! We are glad to have a new Voyager in The Haven!",
    AWAY_ROLE_ID: (
        "Welcome! We are excited that our project has reached your community! "
        f"Feel free to stay and explore with us; or become a part of the project by opening a ticket in <#{CHANNELS['contact']}>"
    ),
}

# -------------------- BOT --------------------
intents = discord.Intents.all()

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    partials=["MESSAGE", "REACTION", "CHANNEL"],
    
)

# -------------------- BOT ATTRIBUTES -------
bot.CHANNELS = CHANNELS
bot.ROLES = ROLES
bot.PRIMARY_ROLES = PRIMARY_ROLES
bot.XP_ENABLED_CHANNELS = XP_ENABLED_CHANNELS
bot.role_welcome_messages = role_welcome_messages
from cogs.Data.xpdata import init_db, CONFIG
from exchange.exchange import TravelersExchangeAPI
# -------------------- COGS --------------------
COGS = [
    "cogs.personality",
    "cogs.xp_system",
    "cogs.xp_cog",
    "cogs.reaction",
    "cogs.Haven_stats",
    "cogs.featured",
    "cogs.community",
    "cogs.welcome",
    "cogs.Haven_upload",
    "cogs.announcements",
    "cogs.hex",
    "cogs.friend"
    "cmds.exclaim",
    "cmds.list",
    "cmds.slash",
    "cmds.voyager",
    "exchange.wallet",
    "exchange.connect",
    "setup",
]

from setup import is_command_allowed

# ---------------- PREFIX COMMANDS (!)
@bot.check
async def global_command_check(ctx):
    if ctx.guild is None:
        return True

    return await is_command_allowed(
        guild_id=ctx.guild.id,
        command_name=normalize(ctx.command.name),
        channel_id=ctx.channel.id,
        member=ctx.author
    )


# ---------------- SLASH COMMANDS (/)
async def global_app_command_check(interaction: discord.Interaction):
    if interaction.guild is None or interaction.channel is None:
        return False

    command = interaction.command
    if command is None:
        return False

    return await is_command_allowed(
        guild_id=interaction.guild.id,
        command_name=normalize(command.qualified_name),
        channel_id=interaction.channel.id,
        member=interaction.user
    )


bot.tree.interaction_check = global_app_command_check
# -------------------- EVENTS --------------------
@bot.event
async def on_ready():
    guild_folder = "Data/guilds"  
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")

    except Exception as e:
        print(e)

    print("COMMANDS:", [cmd.name for cmd in bot.commands])
    print("SLASH:", [cmd.name for cmd in bot.tree.get_commands()])
    print("[...The Keeper is watching...]")

    featured_cog = bot.get_cog("FeaturedCog")
    

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    print(f"[COMMAND ERROR] {ctx.command} -> {error}")

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.CheckFailure):
        return await ctx.send(
            "⛔ You are not allowed to use this command here."
        )

    if isinstance(error, commands.CommandOnCooldown):
        return await ctx.send(
            f"Slow down, Voyager. Try again in {error.retry_after:.1f}s."
        )

    if isinstance(error, commands.MissingPermissions):
        return await ctx.send(
            "You don't have permission to use that."
        )

    import logging
    logging.exception("Command error in %s", ctx.command, exc_info=error)

    await ctx.send(
        "Something went wrong. The Witness has been notified."
    )


# -------------------- RUN --------------------
async def main():
    api = TravelersExchangeAPI(
        bot=bot,
        base_url=BASE_URL,
        api_key=API_KEY,
        timeout=30
    )

    bot.exchange_api = api

    async def setup_hook():
        await init_db()

        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"[LOADED] {cog}")
        
            except Exception as e:
                print(f"[FAILED] {cog} -> {e}")

    bot.setup_hook = setup_hook

    await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())