import discord
from discord.ext import commands
from discord import app_commands
import requests
import os, sys
import logging

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

    @app_commands.command(name="announce", description="Send doc to selected channel")
    @app_commands.describe(
        channel="Channel to send to",
        tag="User or role to mention"
    )
    async def announce(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        tag: discord.Member | discord.Role
    ):
        await interaction.response.defer()

        text = self.parser.get_doc_text()
        sections = self.parser.parse_blocks(text)

        # Send all sections first
        for section in sections:
            if section:
                await channel.send(section[:2000])

        # Send ONE mention at the end
        if tag:
            await channel.send(f"{tag.mention}")

        await interaction.followup.send(
            f"Sent to {channel.mention}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(CommandsCog(bot))