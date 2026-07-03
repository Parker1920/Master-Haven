import discord
from discord.ext import commands
from discord import app_commands
import os

from announcements import GoogleDocParser
from cogs.community import SearchView, AddCivView
from cogs.Haven_upload import *

DOC_URL = "https://docs.google.com/document/d/1FRfxnmXdhU_O-OGTxG52lM0298zzKnGp7W2Qs5njBPo/export?format=txt"


class CommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
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
        tag: discord.Member | discord.Role | None = None
    ):
        await interaction.response.defer()

        text = self.parser.get_doc_text()
        sections = self.parser.parse_blocks(text)

        for section in sections:
            if section:
                await channel.send(section[:2000])

        if tag:
            await channel.send(tag.mention)

        await interaction.followup.send(
            f"Sent to {channel.mention}",
            ephemeral=True
        )
#---------------say------------
    @app_commands.command(name="say", description="Send a message")
    @app_commands.describe(
        channel="Channel to send to",
        message="Message to send"
      )
    async def say(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str
    ):
        await channel.send(message)
        await     interaction.response.send_message("Sent.", ephemeral=True)

#-------------send--------------------
    @app_commands.describe(
        channel="Channel to send to",
        message="Message to send",
        color="Hex color like #ff0000",
        image="Optional image/gif URL"
    )
    async def send(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        message: str,
        color: str = "#5865F2",
        image: str | None = None
    ):
        embed = discord.Embed(
            description=message,
            color=discord.Color.from_str(color)
        )
    
        if image:
            embed.set_image(url=image)
    
        await channel.send(embed=embed)
        await interaction.response.send_message("Sent.", ephemeral=True)
    # ---------------- COMMUNITY ----------------
    @app_commands.command(name="community", description="Look up a civ/community")
    async def community(
        self,
        interaction: discord.Interaction,
        search: str | None = None
    ):
        
        community_cog = self.bot.get_cog("CommunityCog")

        if not community_cog:
            return await interaction.response.send_message("Community system not loaded.")
            
            await interaction.response.defer(thinking=True)
            view = SearchView(community_cog)

        await interaction.response.send_message("Open search:", view=SearchView(community_cog))

        if search:
            await community_cog.run_search(interaction, search)

    # ---------------- ADD CIV ----------------
    @app_commands.command(name="addciv", description="Add a civ/community")
    async def addciv(self, interaction: discord.Interaction):
        cog = self.bot.get_cog("CommunityCog")

        embed = discord.Embed(
            title="Add Entry",
            description="Click below to create a new entry.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, view=AddCivView(cog))

# ---------------- Systems ----------------
    @app_commands.command(name="newsystem", description="Upload a star system directly from the server")
    async def addlog(self, interaction: discord.Interaction):
        haven_cog = self.bot.get_cog("HavenSubmission")
        if not haven_cog:
            await interaction.response.send_message("⚠️ HavenSubmission cog is not loaded.", ephemeral=True)
            return
        
        api = getattr(haven_cog, "api", None)
        if api is None:
            await interaction.response.send_message("⚠️ HavenSubmission cog does not have an API instance.", ephemeral=True)
            return

        glyph_emojis = getattr(haven_cog, "glyph_emojis", {})
        HexKeypad = getattr(haven_cog, "HexKeypad", None)
        if HexKeypad is None:
            await interaction.response.send_message("⚠️ HavenSubmission cog does not have HexKeypad defined.", ephemeral=True)
            return

        view = HexKeypad(api=api, glyph_emojis=glyph_emojis, owner_id=interaction.user.id)
        
        embed = discord.Embed(
            title="🖋 Submit System Log",
            description="Press 12 glyphs to generate your system code.",
            color=0x00FFFF
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(CommandsCog(bot))