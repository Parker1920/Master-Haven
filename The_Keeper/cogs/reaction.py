import discord
from discord.ext import commands

from Data.xpdata import PRIMARY_ROLE_MAP


class DepartmentView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def give_role(self, interaction: discord.Interaction, role_key: str):
        guild = interaction.guild
        member = interaction.user

        role_id = PRIMARY_ROLE_MAP[role_key]
        new_role = guild.get_role(role_id)

        if new_role is None:
            await interaction.response.send_message(
                "Role not found in server.",
                ephemeral=True
            )
            return

        # remove old primary roles
        for r_id in PRIMARY_ROLE_MAP.values():
            role = guild.get_role(r_id)
            if role in member.roles:
                await member.remove_roles(role)

        await member.add_roles(new_role)

        await interaction.response.send_message(
            f"Set primary role to {new_role.name}",
            ephemeral=True
        )

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


class ReactionRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(DepartmentView())

    @commands.command(name="react")
    @commands.has_permissions(administrator=True)
    async def react_panel(self, ctx):

        embed = discord.Embed(
            title="🌌 Choose Your Department",
            description=(
                "Select a department below.\n"
                "Department activities award bonus XP."
            ),
            color=discord.Color.blurple()
        )

        await ctx.send(embed=embed, view=DepartmentView())


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))