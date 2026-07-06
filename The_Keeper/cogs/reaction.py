import discord
from discord.ext import commands
import asyncio
import aiosqlite

from cogs.Data.xpdata import PRIMARY_ROLE_MAP, save_panel, get_panel, DB_PATH, ensure_user

# ---------------- EMBED BUILDER ----------------

def build_main_embed(guild: discord.Guild):
    """
    Builds the dynamic control panel embed, live-tracking current server role counts.
    """
    lines = []

    for role_name, role_id in PRIMARY_ROLE_MAP.items():
        role = guild.get_role(role_id)
        
        count = len(role.members) if role else 0
        lines.append(f"• **{role_name.capitalize()}** — `{count} members`")

    embed = discord.Embed(
        title="🌌 Department Control Panel",
        description=(
            "Select a department below.\n"
            "Department activities and channels award bonus XP.\n\n"
            "**Live Department Counts**"
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Departments",
        value="\n".join(lines),
        inline=False
    )
    embed.set_footer(text="Live tracked • Updates instantly on click")
    return embed


# ---------------- VIEW ----------------

class DepartmentView(discord.ui.View):
    """
    Persistent view handling button interactions and instant embed live-updates.
    """
    def __init__(self):
        super().__init__(timeout=None)

    async def update_panel(self, guild: discord.Guild):
        data = await get_panel(guild.id)
        if not data:
            return

        channel_id, message_id = data
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        try:
            msg = await channel.fetch_message(message_id)
            await msg.edit(embed=build_main_embed(guild), view=self)
        except discord.NotFound:
            pass

    async def give_role(self, interaction: discord.Interaction, role_key: str):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        member = interaction.user

        await ensure_user(member.id)

        role_id = PRIMARY_ROLE_MAP.get(role_key)
        new_role = guild.get_role(role_id) if role_id else None

        if not new_role:
            await interaction.followup.send("❌ Role not found in server settings.", ephemeral=True)
            return

        # ---------------- LIVE ROLE UPDATES (DISCORD) ----------------
        roles_to_remove = [
            guild.get_role(r_id) for r_id in PRIMARY_ROLE_MAP.values()
            if r_id != role_id and guild.get_role(r_id) in member.roles
        ]

        try:
            if roles_to_remove:
                await member.remove_roles(*[r for r in roles_to_remove if r])
            
            if new_role not in member.roles:
                await member.add_roles(new_role)
                
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot cannot manage this role. Move my role higher in the hierarchy!", ephemeral=True)
            return

        # ---------------- DB UPDATE ----------------

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET primary_role=? WHERE user_id=?",
                (role_key, member.id)
            )
            await db.commit()

        await asyncio.sleep(0.3)

        # ---------------- REFRESH PANEL WITH NEW NUMBERS ----------------
        await self.update_panel(guild)

        # ---------------- CONFIRMATION ----------------
        await interaction.followup.send(f"✅ Assigned your primary department to **{new_role.name}**!", ephemeral=True)


    # ---------------- BUTTONS ----------------

    @discord.ui.button(label="Architecture", emoji="🔨", style=discord.ButtonStyle.secondary, custom_id="architect")
    async def architect_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_role(interaction, "architect")

    @discord.ui.button(label="Cartography", emoji="🗺️", style=discord.ButtonStyle.secondary, custom_id="cartographer")
    async def cartographer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_role(interaction, "cartographer")

    @discord.ui.button(label="Diplomacy", emoji="🕊️", style=discord.ButtonStyle.secondary, custom_id="diplomat")
    async def diplomat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_role(interaction, "diplomat")

    @discord.ui.button(label="Engineering", emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="engineer")
    async def engineer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_role(interaction, "engineer")

    @discord.ui.button(label="History", emoji="🖊️", style=discord.ButtonStyle.secondary, custom_id="historian")
    async def historian_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_role(interaction, "historian")

    @discord.ui.button(label="Xenobiology", emoji="🐾", style=discord.ButtonStyle.secondary, custom_id="xenobiologist")
    async def xenobiologist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.give_role(interaction, "xenobiologist")
# ---------------- COG ----------------

class ReactionRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(DepartmentView())

    @commands.command(name="react")
    @commands.has_permissions(administrator=True)
    async def react_panel(self, ctx):
        """
        Spawns or refreshes the live role-assignment panel.
        Usage: !react
        """
        embed = build_main_embed(ctx.guild)
        existing = await get_panel(ctx.guild.id)

        if existing:
            old_channel_id, old_message_id = existing
            old_channel = ctx.guild.get_channel(old_channel_id)

            if old_channel:
                try:
                    old_msg = await old_channel.fetch_message(old_message_id)
                    await old_msg.edit(embed=embed, view=DepartmentView())
                    await ctx.send("🔄 Live reaction panel refreshed and updated.", delete_after=5)
                    return
                except discord.NotFound:
                    pass

        msg = await ctx.send(embed=embed, view=DepartmentView())
        await save_panel(ctx.guild.id, ctx.channel.id, msg.id)
        await ctx.send("✨ Live reaction panel created and registered to database.", delete_after=5)


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
