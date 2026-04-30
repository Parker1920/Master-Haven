from Data.xpdata import *
import time
import discord
from discord.ext import commands

_message_cache = set()


# ---------------- COG ----------------
class XpSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


# ---------------- DISCOVERY MAP ----------------
DISCOVERY_TYPE_MAP = {
    "system": "cartographer",
    "starship": "engineer",
    "multitool": "engineer",
    "fauna": "xenobiologist",
    "flora": "xenobiologist",
    "base": "architect"
}

# ---------------- XP CURVE ----------------
def xp_needed(level: int) -> int:
    if level < 1:
        level = 1
    return 100 + (level - 1) * 50

def get_level_from_xp(xp: int):
    level = 1
    remaining_xp = xp

    while True:
        cost = xp_needed(level)
        if remaining_xp < cost:
            break
        remaining_xp -= cost
        level += 1

    return level
        
def add_global_xp(user_id, amount):
    xp, level, dm = get_global(user_id)

    xp += amount
    leveled_up = False

    while xp >= xp_needed(level):
        xp -= xp_needed(level)
        level += 1
        leveled_up = True

        if level == 7:
            dm = 1

    save_global(user_id, xp, level, dm)
    return level, leveled_up, bool(dm)


# ---------------- CACHE ----------------
users = {}

def get_user(user_id):
    if user_id not in users:
        users[user_id] = {
            "primary_role": get_primary_role(user_id),
            "last": {}
        }
    return users[user_id]


def get_primary_role(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT primary_role FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def make_progress_bar(current: int, total: int, length: int = 12, role: str = None) -> str:

    ROLE_STYLES = {
        "cartographer": ("🟦", "⬛"),
        "xenobiologist": ("🟩", "⬛"),
        "engineer": ("🟧", "⬛"),
        "architect": ("🟪", "⬛"),
        "diplomat": ("🟨", "⬛"),
        "historian": ("🟥", "⬛"),
    }

    if not role or role.lower() not in ROLE_STYLES:
        return "No Department Set"

    role = role.lower()

    if total <= 0:
        total = 1

    fill_char, empty_char = ROLE_STYLES[role]

    current = max(0, min(current, total))

    ratio = current / total
    filled = int(ratio * length)
    empty = length - filled

    bar = fill_char * filled + empty_char * empty
    percent = int(ratio * 100)

    return f"{bar} {percent}%"
    


    return level

def get_rank(level):
    """
    Returns the rank dict that matches the user's level.
    Falls back to highest valid rank if level exceeds defined ranges.
    """

    ranks = CONFIG.get("ranks", [])
    if not ranks:
        return {"name": "Nope"}

    if level < 1:
       level = 1
    
    for rank in ranks:
        min_level = rank.get("min_level")
        max_level = rank.get("max_level")
        exact_level = rank.get("level")

        if exact_level is not None:
            if level == exact_level:
                return rank
            if level >= exact_level:
                fallback = rank
                continue


        if min_level is not None and max_level is not None:
             if min_level <= level <= max_level:
                 return rank
             if level >= min_level:
                 fallback = rank

    return fallback or ranks[1]

# ---------------- ROLE ASSIGN ----------------
async def set_primary_role(member, role_name, bot):
    if not member:
        return

    role_name = role_name.lower()

    user = get_user(member.id)
    current_role = user.get("primary_role")

    if current_role == role_name:
        return

    user["primary_role"] = role_name

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (user_id, primary_role)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET primary_role=excluded.primary_role
    """, (member.id, role_name))

    conn.commit()
    conn.close()

    guild = member.guild

    roles_to_remove = []
    for rid in PRIMARY_ROLE_MAP.values():
        role = guild.get_role(rid)
        if role and role in member.roles:
            roles_to_remove.append(role)

    if roles_to_remove:
        try:
            await member.remove_roles(*roles_to_remove, reason="Primary role update")
        except Exception as e:
            print(f"[ROLE REMOVE ERROR] {e}")

    role_id = PRIMARY_ROLE_MAP.get(role_name)
    if role_id:
        role_obj = member.guild.get_role(role_id)
        if role_obj and role_obj in member.roles:
            return

    new_role = guild.get_role(role_id)

    if new_role and new_role not in member.roles:
        try:
            await member.add_roles(new_role, reason="Primary role update")
        except Exception as e:
            print(f"[ROLE ADD ERROR] {e}")


# ---------------- MESSAGE XP ----------------
async def process_message_xp(message):
    if message.author.bot:
        return 0

    user_id = message.author.id
    user = get_user(user_id)

    role = user.get("primary_role")
    if not role:
        return 0

    cooldown = get_cfg("xp.primary_cooldown", 5)

    if not check_cooldown(user_id, role, cooldown):
        return 0

    xp_gain = get_cfg("xp.primary_per_message", 1)

    add_xp(user_id, role, xp_gain)

    level, leveled_up, dm = add_global_xp(user_id, xp_gain)

    return xp_gain


# ---------------- DISCOVERY XP ----------------
async def process_discovery_xp(user_id, discovery_type, channel_id):
    user = get_user(user_id)
    upload_channels = get_cfg("channels.upload_channel",[])
    office_channels = get_cfg("channels.office_channel",[])                     

    primary_role = user.get("primary_role")
    if not primary_role:
        return 0

    primary_role = primary_role.lower()
    expected_role = DISCOVERY_TYPE_MAP.get(discovery_type.lower())

    if not expected_role:
        return 0

    if not check_cooldown(user_id, f"discovery_{discovery_type}", get_cfg("xp_bonus.discovery_cooldown", 30)):
        return 0

    xp = get_cfg("xp_bonus.base_discovery_xp", 10)

    if primary_role == expected_role:
        xp += get_cfg("xp_bonus.role_match", 5)
    else:
        xp += get_cfg("xp_bonus.cross_role_penalty", -1)
    
    if channel_id in upload_channels:
        xp += get_cfg("xp_bonus.channel_match", 5)

    if office_channels and channel_id == office_channels[0]:
        xp += get_cfg("xp_bonus.channel_match", 5)

    add_xp(user_id, primary_role, xp)

    level, leveled_up, dm = add_global_xp(user_id, xp)

    if leveled_up:
        member = bot.get_guild(member.guild.id).get_member(user_id) if 'member' in globals() else None
        if member:
            await update_rank_role(member, level)

    return xp


# ---------------- SETUP ----------------
async def setup(bot):
    await bot.add_cog(XpSystemCog(bot))
