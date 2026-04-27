# ---------------- exclaim.py ----------------
import discord
from discord.ext import commands
from discord import app_commands

import sys, os
import json
from difflib import get_close_matches
import aiohttp
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

sys.path.append(os.path.join(BASE_DIR, "cogs"))

from cogs import xp_system, personality, Haven_stats, Haven_upload, featured, community
from cogs.xp_cog import DepartmentView
from cogs.xp_system import get_user, get_level_from_xp, make_progress_bar, get_rank, xp_needed
from cogs.community import SearchView, AddCivView
from cogs.Data.xpdata import get_level, get_xp, CONFIG, get_global, system_xp
import logging
log = logging.getLogger("commands")
   
# =========================
# MAIN COG
# =========================
class CommandsRouter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.local_data = []
        self.session = aiohttp.ClientSession()
        self._active_commands = set()

        if not hasattr(bot, "keeper_locked"):
            bot.keeper_locked = False

        print("[(!)Commands]: loaded ✅")

    async def cog_unload(self):
        await self.session.close()
    @commands.Cog.listener()
    async def on_command(self, ctx):
        log.info(f"{ctx.author} used {ctx.command} in #{ctx.channel}")
        
# ---------------- XP ----------------
    @commands.command(name="xp", help="check rank and level progress")
    async def xp(self, ctx, member: discord.Member = None):
    
        if ctx.channel.id != int(os.getenv("QUALIFY_CHANNEL_ID")):
            return
    
        member = member or ctx.author
        user = get_user(member.id)
    
        primary = user.get("primary_role")
        if not primary:
            await ctx.send(f"{member.display_name} has no primary role assigned.")
            return
    
        ROLE_COLORS = {
            "architect": discord.Color.blue(),
            "cartographer": discord.Color.purple(),
            "diplomat": discord.Color.teal(),
            "xenobiologist": discord.Color.green(),
            "engineer": discord.Color.orange(),
            "historian": discord.Color.gold()
        }
    
        color = ROLE_COLORS.get(primary, discord.Color.green())

    # ---------------- XP SYSTEM ------------------
    
        role_xp = get_xp(member.id, primary)
    
        global_xp, level, _ = get_global(member.id)
        level = int(level)
        
        rank = get_rank(level)
    
        xp_for_level = xp_needed(level)
    
        xp_into_level = role_xp % xp_for_level if xp_for_level else role_xp
    
        bar = make_progress_bar(xp_into_level, xp_for_level, role=primary)
    
        embed = discord.Embed(
            title=f"{member.display_name}'s XP",
            color=color
        )
    
        embed.add_field(
            name=f"{primary.capitalize()} (Primary)",
            value=(
                f"Role XP: {role_xp}\n"
                f"Level: {level}\n"
                f"Rank: {rank['name']}\n"
                f"{bar}"
            ),
            inline=False
        )
    
        await ctx.send(embed=embed)
# ---------------- Community ----------------
    @commands.command(name="community", help="Look up a No Man's Sky civ or commmunity")    
    async def community(self, ctx, *, search: str = None):
        if ctx.channel.id != int(os.getenv("LIBRARY_CHANNEL_ID")): return
        community_cog = self.bot.get_cog("CommunityCog")
        

        if not community_cog:
            return await ctx.send("Community system not loaded.")

        await ctx.send("Open search:", view=SearchView(community_cog))

        if not search:
            return

        await community_cog.run_search(ctx, search)

# ---------------- Add Civ ----------------
    @commands.command(name="addciv", help="add a civ or community to our ever growing list!")
    async def addciv(self, ctx: commands.Context):
        cog = self.bot.get_cog("CommunityCog")

        embed = discord.Embed(
            title="Add Entry",
            description="Click below to create a new entry.",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed, view=AddCivView(cog))

# ---------------- Systems ----------------
    @commands.command(name="newsystem", help="upload a system directly from the server")
    async def addlog(self, ctx):
        if ctx.channel.id != int(os.getenv("SYSTEM_CHANNEL_ID")): return
        haven_cog = self.bot.get_cog("HavenSubmission")
        if not haven_cog:
            await ctx.send("⚠️ HavenSubmission cog is not loaded.")
            return
        
        api = getattr(haven_cog, "api", None)
        if api is None:
            await ctx.send("⚠️ HavenSubmission cog does not have an API instance.")
            return

        glyph_emojis = getattr(haven_cog, "glyph_emojis", {})
        HexKeypad = getattr(haven_cog, "HexKeypad", None)
        if HexKeypad is None:
            await ctx.send("⚠️ HavenSubmission cog does not have HexKeypad defined.")
            return

        view = HexKeypad(api=api, glyph_emojis=glyph_emojis, owner_id=ctx.author.id)
        self.bot.add_view(view)

        embed = discord.Embed(
            title="🖋 Submit System Log",
            description="Press 12 glyphs to generate your system code.",
            color=0x00FFFF
        )

        message = await ctx.send(embed=embed, view=view)
        view.message = message

# ---------------- Discoveries ----------------
    @commands.command(name="discovery", help="upload a disxovery directly from the server")
    async def discovery(self, ctx):       
        if ctx.channel.id not in [
            int(os.getenv("BASE_CHANNEL_ID")),
            int(os.getenv("OUT_CHANNEL_ID")),
            int(os.getenv("CRASH_CHANNEL_ID")),
            int(os.getenv("SENTINEL_CHANNEL_ID")),
            int(os.getenv("TOOL_CHANNEL_ID")),
            int(os.getenv("STAFF_CHANNEL_ID")),
            int(os.getenv("FAUNA_CHANNEL_ID")),
            int(os.getenv("FLORA_CHANNEL_ID")),
        ]:
            return

        haven_cog = self.bot.get_cog("HavenSubmission")
        if not haven_cog:
            await ctx.send("⚠️ HavenSubmission cog is not loaded.")
            return
        
        DiscoveryTypeSelect = getattr(haven_cog, "DiscoveryTypeSelect", None)
        if DiscoveryTypeSelect is None:
            await ctx.send("⚠️ DiscoveryTypeSelect not found.")
            return

        api = getattr(haven_cog, "api", None)
        if api is None:
            await ctx.send("⚠️ HavenSubmission API missing.")
            return

        glyph_emojis = getattr(haven_cog, "glyph_emojis", {})
        view = DiscoveryTypeSelect(api, glyph_emojis, ctx.author.id)

        await ctx.send("Select the type of discovery to submit:", view=view)
        system_xp(ctx.author.id, 3)

# ---------------- Leaderboard ----------------
    @commands.command(name="leaderboard", help="Featured photo leaderboard")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def leaderboard(self, ctx):
        featured_cog = self.bot.get_cog("FeaturedCog")
    
        if not featured_cog:
            await ctx.send("Featured system is not loaded.")
            return
    
        async with ctx.typing():      
            await featured_cog.post_leaderboard(ctx.channel)

# ---------------- Map ----------------
    @commands.command(name="map", help="a link to the Haven map")
    async def map_command(self, ctx: commands.Context):
        if ctx.channel.id not in [int(os.getenv("GENERAL_CHANNEL_ID")), int(os.getenv("HELP_CHANNEL_ID")), int(os.getenv("LIBRARY_CHANNEL_ID"))]: return
        HAVEN_MAP_URL = "https://havenmap.online/map/latest"

        button = discord.ui.Button(label="✨ Open the Haven Map 🌌", url=HAVEN_MAP_URL)
        view = discord.ui.View()
        view.add_item(button)

        await ctx.send("Click below to see the Haven Map:", view=view)

# ---------------- Stats ----------------
    @commands.command(name="stats", help="a general overview of Haven map stats")
    async def stats(self, ctx):
        if ctx.channel.id != int(os.getenv("LIBRARY_CHANNEL_ID")): return
        cog = self.bot.get_cog("Haven_statsCog")
        if not cog:
            return await ctx.send("Stats system not loaded.")

        await cog.send_stats(ctx.channel)

# ---------------- Best ----------------
    @commands.command(name="best", help="a user leaderboard for Haven map stats")
    async def best(self, ctx, count: int = 10, community: str = None):
        if ctx.channel.id != int(os.getenv("LIBRARY_CHANNEL_ID")): return
        cog = self.bot.get_cog("Haven_statsCog")
        if not cog:
            return await ctx.send("Stats system not loaded.")

        await cog.send_best(ctx.channel, count, community)


# ---------------- Systems Count ----------------
    @commands.command(name="systems", help="number of current systems")
    async def system(self, ctx):
        if ctx.channel.id != int(os.getenv("LIBRARY_CHANNEL_ID")): return
        cog = self.bot.get_cog("AnnouncementCog")

        if not cog:
            await ctx.send("⚠️ Stats system not available.")
            return

        try:
            current = await cog.get_system_count()
        except Exception as e:
            log.warning(f"systems lookup failed: {e}")
            await ctx.send("⚠️ Couldn't reach the Haven archives right now. Try again shortly.")
            return

        milestone = (current // 1000) * 1000
        if milestone < 13000:
            milestone = 13000

        next_milestone = milestone + 1000
        remaining = next_milestone - current

        embed = discord.Embed(title="📡 System Tracker", color=0x8A00C4)
        embed.add_field(name="Current Systems", value=f"{current:,}", inline=False)
        embed.add_field(name="Next Milestone", value=f"{next_milestone:,}", inline=True)
        embed.add_field(name="Remaining", value=f"{remaining:,}", inline=True)

        await ctx.send(embed=embed)

# ---------------- Planets Count ----------------
    @commands.command(name="planets", help="number if current planets")
    async def planets(self, ctx):
        if ctx.channel.id != int(os.getenv("LIBRARY_CHANNEL_ID")): return
        cog = self.bot.get_cog("AnnouncementCog")

        if not cog:
            await ctx.send("⚠️ Planet tracker not available.")
            return

        try:
            current = await cog.get_planet_count()
        except Exception as e:
            log.warning(f"planets lookup failed: {e}")
            await ctx.send("⚠️ Couldn't reach the Haven archives right now. Try again shortly.")
            return

        milestone = (current // 5000) * 5000
        if milestone < 25000:
            milestone = 25000

        next_milestone = milestone + 5000
        remaining = next_milestone - current

        embed = discord.Embed(title="🪐 Planet Tracker", color=0x00FFCC)
        embed.add_field(name="Current Planets", value=f"{current:,}", inline=False)
        embed.add_field(name="Next Milestone", value=f"{next_milestone:,}", inline=True)
        embed.add_field(name="Remaining", value=f"{remaining:,}", inline=True)

        await ctx.send(embed=embed)        

    @commands.command(
    name="department",
    help="select or reselect a primary department to utilize the Haven XP system"
)
    async def department(self, ctx):
        if ctx.channel.id != int(os.getenv("QUALIFY_CHANNEL_ID")):
            return
    
        embed = discord.Embed(
            title="🧭 Department Selection",
            description="Please pick a primary department:",
            color=discord.Color.blurple()
        )
    
        view = DepartmentView(self.bot)
    
        message = await ctx.send(embed=embed, view=view)
    
        await view.wait()
    
        try:
            await message.edit(view=None)
        except Exception:
            pass
    
    
    async def setup(bot):
        await bot.add_cog(Department(bot))

# ---------------- Setup --------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(CommandsRouter(bot))
    


def setup_global_checks(bot: commands.Bot):
    @bot.check
    async def global_channel_lock(ctx):
        if ctx.guild is None:
            return True

        if not bot.keeper_locked:
            return True

        return ctx.channel.id == BOT_DEV_CHANNEL_ID