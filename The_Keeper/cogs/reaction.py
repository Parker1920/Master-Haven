import discord
from discord.ext import commands
import asyncio
import aiosqlite

from Data.xpdata import PRIMARY_ROLE_MAP, save_panel, get_panel, DB_PATH, ensure_user

# ---------------- EMBED BUILDER ----------------

def build_main_embed(guild: discord.Guild):

    lines = []

    for role_name, role_id in PRIMARY_ROLE_MAP.items():

        role = guild.get_role(role_id)

        if role:
            count = sum(1 for _ in role.members)
        else:
            count = 0

        lines.append(f"• **{role_name.capitalize()}** — {count}")

    embed = discord.Embed(
        title="🌌 Department Control Panel",
        description=(
            "Select a department below.\n"
            "Department activities and channels award bonus XP.\n\n"
            "**Department Count**"
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="Departments",
        value="\n".join(lines),
        inline=False
    )

    return embed


# ---------------- VIEW ----------------

class DepartmentView(discord.ui.View):

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

            await msg.edit(
                embed=build_main_embed(guild),
                view=self
            )

        except discord.NotFound:
            pass

    async def give_role(self, interaction: discord.Interaction, role_key: str):

        guild = interaction.guild
        member = interaction.user

        await ensure_user(member.id)

        role_id = PRIMARY_ROLE_MAP[role_key]
        new_role = guild.get_role(role_id)

        if not new_role:
            msg = "Role not found in server."

            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)

            return

        # ---------------- REMOVE OLD ROLES ----------------

        for r_id in PRIMARY_ROLE_MAP.values():
            role = guild.get_role(r_id)

            if role and role in member.roles:
                await member.remove_roles(role)

        await asyncio.sleep(0.5)

        # ---------------- ADD NEW ROLE ----------------

        if new_role not in member.roles:
            await member.add_roles(new_role)

        # ---------------- DB UPDATE ----------------

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET primary_role=? WHERE user_id=?",
                (role_key, member.id)
            )
            await db.commit()

        await asyncio.sleep(0.5)

        # ---------------- FORCE CACHE REFRESH ----------------

        try:
            await guild.chunk(cache=True)
        except Exception:
            pass

        await asyncio.sleep(0.5)

        # ---------------- UPDATE PANEL ----------------

        await self.update_panel(guild)

        # ---------------- RESPONSE ----------------

        msg = f"Set primary role to {new_role.name}"

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

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

        for guild in self.bot.guilds:

            data = await get_panel(guild.id)

            if not data:
                continue

            channel_id, message_id = data
            channel = guild.get_channel(channel_id)

            if not channel:
                continue

            try:
                msg = await channel.fetch_message(message_id)

                await msg.edit(
                    embed=build_main_embed(guild),
                    view=DepartmentView()
                )

            except discord.NotFound:
                pass

    @commands.command(name="react")
    @commands.has_permissions(administrator=True)
    async def react_panel(self, ctx):

        embed = build_main_embed(ctx.guild)

        existing = await get_panel(ctx.guild.id)

        if existing:

            old_channel_id, old_message_id = existing
            old_channel = ctx.guild.get_channel(old_channel_id)

            if old_channel:

                try:
                    old_msg = await old_channel.fetch_message(old_message_id)

                    await old_msg.edit(
                        embed=embed,
                        view=DepartmentView()
                    )

                    await save_panel(ctx.guild.id, old_channel_id, old_message_id)

                    await ctx.send("Reaction panel updated.", delete_after=5)
                    return

                except discord.NotFound:
                    pass

        msg = await ctx.send(embed=embed, view=DepartmentView())

        await save_panel(ctx.guild.id, ctx.channel.id, msg.id)

        await ctx.send("Reaction panel created and saved.", delete_after=5)


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))