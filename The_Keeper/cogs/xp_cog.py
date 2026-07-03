from Data.xpdata import *
import time
import discord
from discord.ext import commands
import aiosqlite  # Added explicit import for asynchronous database engines

_message_cache = set()
_role_locks = set()

# ---------------- UI ----------------
class DepartmentView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

        for role_name in PRIMARY_ROLE_MAP.keys():
            self.add_item(DepartmentButton(role_name, bot))


class DepartmentButton(discord.ui.Button):
    def __init__(self, role_name, bot):
        self.role_name = role_name
        self.bot = bot

        super().__init__(
            label=role_name.capitalize(),
            style=discord.ButtonStyle.primary
        )

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id in _role_locks:
            return await interaction.response.send_message(
                "You already selected a department.",
                ephemeral=True
            )

        _role_locks.add(user_id) 

        try:
            member = await interaction.guild.fetch_member(user_id)
        except Exception:
            _role_locks.discard(user_id)
            return await interaction.response.send_message(
                "Could not resolve member.",
                ephemeral=True
            )

        await set_primary_role(member, self.role_name, self.bot)

        for item in self.view.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=f"🧭 Set to **{self.role_name.capitalize()}**",
            view=self.view
        )

        self.view.stop()


# ---------------- COG ----------------
class XpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        msg_id = message.id
        if msg_id in _message_cache:
            return

        _message_cache.add(msg_id)

        if len(_message_cache) > 5000:
            _message_cache.clear()

        gained = await process_message_xp(message)        
        return gained


# ---------------- PRIMARY ROLE (DATABASE INTERFACES) ----------------
async def set_primary_role(member, role_name, bot):
    if not member:
        return

    role_name = role_name.lower()
    guild = member.guild

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, primary_role) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET primary_role = excluded.primary_role",
            (member.id, role_name)
        )
        await db.commit()

    roles_to_remove = []
    for rid in PRIMARY_ROLE_MAP.values():
        role = guild.get_role(rid)
        if role and role in member.roles:
            roles_to_remove.append(role)

    if roles_to_remove:
        try:
            await member.remove_roles(*roles_to_remove)
        except Exception as e:
            print(f"[ROLE REMOVE ERROR] {e}")

    role_id = PRIMARY_ROLE_MAP.get(role_name)
    if not role_id:
        return

    new_role = guild.get_role(role_id)
    if not new_role:
        return

    try:
        await member.add_roles(new_role)
    except Exception as e:
        print(f"[ROLE ADD ERROR] {e}")


# ---------------- LEVEL CURVE ----------------
def xp_needed(level):
    return 100 + (level * 50)

async def add_global_xp(user_id, amount):
    global_row = await get_global(user_id)
    if global_row:
        xp, level, dm = global_row
    else:
        xp, level, dm = 0, 1, 0

    xp += amount
    leveled_up = False

    while xp >= xp_needed(level):
        xp -= xp_needed(level)
        level += 1
        leveled_up = True

        if level == 7:
            dm = 1

    await save_global(user_id, xp, level, dm)
    return level, leveled_up, bool(dm)


# ---------------- XP PROCESS ----------------
async def process_message_xp(message):
    if message.author.bot:
        return 0

    user_id = message.author.id
    user_role = "voyager"
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT primary_role FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                user_role = row[0]


    cooldown = CONFIG.get("xp", {}).get("primary_cooldown", 5)
    if not check_cooldown(user_id, user_role, cooldown):
        return 0

    xp = CONFIG.get("xp", {}).get("primary_per_message", 1)

    await add_xp(user_id, user_role, xp)
    await add_global_xp(user_id, xp)

    return xp


# ---------------- SETUP ----------------
async def setup(bot):
    await bot.add_cog(XpCog(bot))
