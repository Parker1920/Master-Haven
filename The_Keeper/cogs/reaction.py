import discord
from discord.ext import commands

from .data import xpdata


class DepartmentView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    async def give_role(self, interaction, role_key):

        guild = interaction.guild
        member = interaction.user

        role_id = xpdata.PRIMARY_ROLE_MAP[role_key]
        role = guild.get_role(role_id)

        if role in member.roles:
            await member.remove_roles(role)

            await interaction.response.send_message(
                f"Removed {role.name}",
                ephemeral=True
            )

        else:
            await member.add_roles(role)

            await interaction.response.send_message(
                f"Added {role.name}",
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

        await ctx.send(
            embed=embed,
            view=DepartmentView()
        )


async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))