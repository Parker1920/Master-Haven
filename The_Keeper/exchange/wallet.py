import os 
import aiohttp 
import discord 
from discord import app_commands 
from discord.ext import commands
from .exchange import TravelersExchangeAPI 

def tc(amount: int) -> str: return f"{amount:,} TC"

class WalletCog(commands.Cog): 
    def __init__(self, bot: commands.Bot):
        self.bot = bot 
        self.api = TravelersExchangeAPI(
            bot=bot,
            base_url=BASE_URL,
            api_key=API_KEY,
            timeout=30
        )
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()
    
    def _headers(self, discord_user_id: str):
        return {
            "Authorization": f"Bearer {API_KEY}",
            "X-Discord-User-Id": str(discord_user_id),
            "Content-Type": "application/json"
        }
    
    async def _get(self, path: str, discord_user_id: str, params: dict = None):
        async with self.session.get(
            f"{BASE_URL}{path}",
            headers=self._headers(discord_user_id),
            params=params or {}
        ) as r:
            return await r.json(), r.status
    
    async def _post(self, path: str, discord_user_id: str, payload: dict = None):
        async with self.session.post(
            f"{BASE_URL}{path}",
            headers=self._headers(discord_user_id),
            json=payload or {}
        ) as r:
            return await r.json(), r.status
    
    wallet_group = app_commands.Group(name="wallet", description="Travelers Exchange wallet commands")
    
    @wallet_group.command(name="me", description="View your wallet")
    async def wallet_me(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
    
        data, status = await self._get("/api/wallet", interaction.user.id)
    
        if status != 200:
            return await interaction.followup.send(data.get("detail", "Error fetching wallet"))
    
        embed = discord.Embed(title="Your Wallet", color=discord.Color.green())
        embed.add_field(name="Balance", value=tc(data.get("balance", 0)), inline=False)
        embed.add_field(name="Nation", value=data.get("nation", "None"), inline=False)
    
        await interaction.followup.send(embed=embed)
    
    @wallet_group.command(name="view", description="View another wallet")
    async def wallet_view(self, interaction: discord.Interaction, address: str):
        await interaction.response.defer(ephemeral=True)
    
        data, status = await self._get(f"/api/wallet/{address}", interaction.user.id)
    
        if status != 200:
            return await interaction.followup.send(data.get("detail", "Error fetching wallet"))
    
        embed = discord.Embed(title=f"Wallet {address[:6]}...", color=discord.Color.blue())
        embed.add_field(name="Balance", value=tc(data.get("balance", 0)), inline=False)
    
        await interaction.followup.send(embed=embed)
    
    @wallet_group.command(name="history", description="View wallet transactions")
    async def wallet_history(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
    
        data, status = await self._get("/api/wallet/me/transactions", interaction.user.id)
    
        if status != 200:
            return await interaction.followup.send(data.get("detail", "Error fetching history"))
    
        embed = discord.Embed(title="Recent Transactions", color=discord.Color.purple())
    
        for tx in data.get("items", [])[:10]:
            embed.add_field(
                name=tx.get("tx_hash", "unknown")[:10],
                value=f"{tx.get('from')} → {tx.get('to')} | {tc(tx.get('amount',0))}",
                inline=False
            )
    
        await interaction.followup.send(embed=embed)
    
    @wallet_group.command(name="send", description="Send TC to a wallet")
    async def wallet_send(self, interaction: discord.Interaction, to_address: str, amount: int, memo: str = ""):
        await interaction.response.defer(ephemeral=True)
    
        payload = {
            "to_address": to_address,
            "amount": amount,
            "memo": memo or None
        }
    
        data, status = await self._post("/api/transactions/transfer", interaction.user.id, payload)
    
        if status != 200:
            return await interaction.followup.send(data.get("detail", "Transfer failed"))
    
        embed = discord.Embed(title="Transfer Successful", color=discord.Color.gold())
        embed.add_field(name="Amount", value=tc(amount), inline=False)
        embed.add_field(name="To", value=to_address, inline=False)
    
        await interaction.followup.send(embed=embed)
    
    @wallet_group.command(name="tx", description="Lookup a transaction")
    async def wallet_tx(self, interaction: discord.Interaction, tx_hash: str):
        await interaction.response.defer(ephemeral=True)
    
        data, status = await self._get(f"/api/transactions/{tx_hash}", interaction.user.id)
    
        if status != 200:
            return await interaction.followup.send(data.get("detail", "Transaction not found"))
    
        embed = discord.Embed(title="Transaction", color=discord.Color.orange())
        embed.add_field(name="Hash", value=tx_hash, inline=False)
        embed.add_field(name="Amount", value=tc(data.get("amount",0)), inline=False)
        embed.add_field(name="From", value=data.get("from_address"))
        embed.add_field(name="To", value=data.get("to_address"))
    
        await interaction.followup.send(embed=embed)
    
async def setup(bot: commands.Bot): 
    await bot.add_cog(WalletCog(bot)) 

