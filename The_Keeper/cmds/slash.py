import discord
from discord.ext import commands
from discord import app_commands
import requests
import os, sys
import logging
from cogs.community import SearchView, AddCivView, EditConfirmView
from typing import Optional


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

sys.path.append(os.path.join(BASE_DIR, "cogs"))

log = logging.getLogger("commands")

from announcements import GoogleDocParser
DOC_URL = "https://docs.google.com/document/d/1FRfxnmXdhU_O-OGTxG52lM0298zzKnGp7W2Qs5njBPo/export?format=txt"


class CommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.parser = GoogleDocParser(DOC_URL)

    # ---------------- Announce ----------------
    @app_commands.command(name="announce", description="Send doc to selected channel")
    @app_commands.describe(
        channel="Channel to send to",
        tag="User or role to mention (optional)"
    )
    async def announce(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        tag: Optional[discord.Member | discord.Role] = None
    ):
        await interaction.response.defer()

        text = self.parser.get_doc_text()
        sections = self.parser.parse_blocks(text)

        for section in sections:
            if section:
                await channel.send(section[:2000])

        if tag:
            await channel.send(f"{tag.mention}")

        await interaction.followup.send(
            f"Sent to {channel.mention}",
            ephemeral=True
        )

# ---------------- Community ----------------
    @app_commands.command(name="community", description="Look up a No Man's Sky civ or commmunity")    
    async def community(self, interaction: discord.Interaction, *, search: str = None):
        if interaction.channel.id != int(os.getenv("LIBRARY_CHANNEL_ID")): return
        community_cog = self.bot.get_cog("CommunityCog")
        

        if not community_cog:
            return await interaction.response.send_message("Community system not loaded.")

        await interaction.response.send_message("Open search:", view=SearchView(community_cog))

        if not search:
            return

        await community_cog.run_search(interaction, search)

# ---------------- Add Civ ----------------
    @app_commands.command(name="addciv", description="add a civ or community to our ever growing list!")
    async def addciv(self, interaction: discord.Interaction):
        cog = self.bot.get_cog("CommunityCog")

        embed = discord.Embed(
            title="Add Entry",
            description="Click below to create a new entry.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, view=AddCivView(cog))


async def setup(bot):
    await bot.add_cog(CommandsCog(bot))
