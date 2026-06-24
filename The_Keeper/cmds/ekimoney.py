import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.app_commands import CommandTree
from cogs.exchange import ExchangeAPIClient, ExchangeAPIError

exchange = ExchangeAPIClient(
    base_url="https://travelers-exchange.online",
    api_key=os.getenv("ECHANGE_API")
)

class NationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    nation_group = app_commands.Group(name="nation", description="Manage your national alignment")

    @nation_group.command(name="bank", description="List all available nations.")
    async def nation_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        exchange_cog = self.bot.get_cog("ExchangeCog")
        if not exchange_cog:
            return await interaction.followup.send("❌ Exchange Service is currently unavailable.", ephemeral=True)
        
        api = exchange_cog.client

        try:
            nations = await api.list_nations()

            if not nations:
                return await interaction.followup.send("🌍 No nations found.", ephemeral=True)

            embed = discord.Embed(
                title="🌍 Registered Nations",
                description="Choose a nation ID to join using `/nation join <id>`.",
                color=0x3498DB
            )

            for nation in nations:
                nation_id = nation.get("id", "N/A")
                name = nation.get("name", "Unknown Nation")
                currency = nation.get("currency_code", "TC")
                gdp_mult = nation.get("gdp_multiplier_x100", 100)

                embed.add_field(
                    name=f"[{nation_id}] {name}",
                    value=f"**Currency:** {currency}\n**GDP Multiplier:** {gdp_mult/100:.2f}x",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        except ExchangeAPIError as e:
            await interaction.followup.send(f"❌ **Exchange Error:** {e.detail}", ephemeral=True)


    @nation_group.command(name="join", description="Join a nation by its ID.")
    @app_commands.describe(nation_id="The ID of the nation you want to join")
    async def nation_join(self, interaction: discord.Interaction, nation_id: int):
        await interaction.response.defer(ephemeral=True)

        exchange_cog = self.bot.get_cog("ExchangeCog")
        if not exchange_cog:
            return await interaction.followup.send("❌ Exchange Service is currently unavailable.", ephemeral=True)
        
        api = exchange_cog.client

        try:
            data = await api.join_nation(discord_user_id=str(interaction.user.id), nation_id=nation_id)
            
            nation_name = data.get("nation_name", f"Nation #{nation_id}")

            embed = discord.Embed(
                title="🎉 Nation Joined!",
                description=f"Welcome, Voyager! You have officially joined **{nation_name}**.",
                color=0x2ECC71
            )
            await interaction.followup.send(embed=embed)

        except ExchangeAPIError as e:
            await interaction.followup.send(f"❌ **Exchange Error:** {e.detail}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(NationCog(bot))
