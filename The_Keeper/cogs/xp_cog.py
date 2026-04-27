from Data.xpdata import *
import time
import discord
from discord.ext import commands

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
        user_id = interaction.user.id  # ✅ FIX: define user_id

        # 🔒 prevent duplicate selection
        if user_id in _role_locks:
            return await interaction.response.send_message(
                "You already selected a department.",
                ephemeral=True
            )

        _role_locks.add(user_id)  # ✅ FIX: actually lock user

        try:
            member = await interaction.guild.fetch_member(user_id)
        except Exception:
            _role_locks.discard(user_id)
            return await interaction.response.send_message(
                "Could not resolve member.",
                ephemeral=True
            )

        from cogs.xp_system import set_primary_role as _xp_set_primary_role
        await _xp_set_primary_role(member, self.role_name, self.bot)

        user_cache = get_user(user_id)
        user_cache["primary_role"] = self.role_name.lower()

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


# ---------------- USER CACHE ----------------
users = {}

def get_user(user_id):
    if user_id not in users:
        from cogs.xp_system import get_primary_role
        users[user_id] = {
            "primary_role": get_primary_role(user_id),
            "last": {}
        }
    return users[user_id]


# ---------------- LEVEL CURVE ----------------
def xp_needed(level):
    return 100 + (level * 50)


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


# ---------------- XP PROCESS ----------------
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

    xp = get_cfg("xp.primary_per_message", 1)

    add_xp(user_id, role, xp)

    level, leveled_up, dm = add_global_xp(user_id, xp)

    return xp


# ---------------- SETUP ----------------
async def setup(bot):
    await bot.add_cog(XpCog(bot))