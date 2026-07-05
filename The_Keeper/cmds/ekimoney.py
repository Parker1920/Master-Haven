import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from cogs.exchange import ExchangeAPIError

class NationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Base Command Router Group
    nation_group = app_commands.Group(name="nation", description="Manage your national alignment and view economics")

    async def nation_autocomplete(self, interaction: discord.Interaction, current: str):
        """Fetches approved nations dynamically from the API to provide autocomplete choices"""
        exchange_cog = self.bot.get_cog("ExchangeCog")
        if not exchange_cog:
            return []
        
        # Public list endpoint: GET /api/nations
        url = f"https://travelers-exchange.online/api/nations"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return []
                    nations = await resp.json()
            
            return [
                app_commands.Choice(name=f"{n['name']} ({n['currency_code']})", value=str(n['id']))
                for n in nations 
                if current.lower() in n['name'].lower() or current.lower() in n['currency_code'].lower()
            ][:25] # Discord autocomplete limit
        except Exception:
            return []

    @nation_group.command(name="search_bank", description="Purely search for chartered banks within a specific nation.")
    @app_commands.autocomplete(nation_id=nation_autocomplete)
    @app_commands.describe(nation_id="Select the nation to view chartered banks for")
    async def search_bank(self, interaction: discord.Interaction, nation_id: str):
        await interaction.response.defer(ephemeral=True)

        exchange_cog = self.bot.get_cog("ExchangeCog")
        if not exchange_cog:
            return await interaction.followup.send("❌ Exchange Service is currently unavailable.", ephemeral=True)

        try:
            # Hit Section 4.3 Public Endpoint: GET /api/banks/nation/{nation_id}
            url = f"https://travelers-exchange.online/api/banks/nation/{nation_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send("❌ Error fetching bank data from the Exchange API.", ephemeral=True)
                    banks = await resp.json()

            if not banks:
                return await interaction.followup.send("🏛️ No chartered banks found for this nation.", ephemeral=True)

            # Lazy import to prevent circular dependency cycles on startup
            from cogs.exchange import BankPaginatorView
            
            view = BankPaginatorView(banks, per_page=3)
            embed = view.make_embed()
            
            # Send the initialized paginated view interface
            await interaction.followup.send(embed=embed, view=view)

        except Exception as e:
            await interaction.followup.send(f"❌ **An unexpected error occurred:** {str(e)}", ephemeral=True)

    @nation_group.command(name="list", description="List all available nations.")
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
