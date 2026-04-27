import discord
from discord.ext import commands
import aiohttp
import os
import logging

log = logging.getLogger(__name__)

HAVEN_API = os.getenv("HAVEN_API")
HAVEN_URL = os.getenv("HAVEN_URL")
HAVEN_TIMEOUT = aiohttp.ClientTimeout(total=10)


class Haven_statsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_stats(self, channel):
        if not channel:
            return

        await channel.send("📡 Fetching Haven stats...")

        try:
            async with aiohttp.ClientSession(timeout=HAVEN_TIMEOUT) as session:
                async with session.get(f"{HAVEN_API}/api/db_stats") as resp:
                    if resp.status != 200:
                        await channel.send("Error fetching stats from API.")
                        log.warning(f"[STATS] API returned {resp.status}")
                        return

                    data = await resp.json()
                    totals = data.get("stats", {})

            embed = discord.Embed(title="🌌 Haven Stats", color=0x00FFCC)
            embed.set_footer(text="Haven DB Stats")

            embed.add_field(name="Systems", value=f"{totals.get('systems', 0):,}", inline=True)
            embed.add_field(name="Planets", value=f"{totals.get('planets', 0):,}", inline=True)
            embed.add_field(name="Moons", value=f"{totals.get('moons', 0):,}", inline=True)

            embed.add_field(name="Regions", value=f"{totals.get('regions', 0):,}", inline=True)
            embed.add_field(name="POIs", value=f"{totals.get('planet_pois', 0):,}", inline=True)
            embed.add_field(name="Discoveries", value=f"{totals.get('discoveries', 0):,}", inline=True)

            await channel.send(embed=embed)

        except Exception as e:
            await channel.send(f"Error: {e}")
            log.error(f"Stats error: {e}")

    async def send_best(self, channel, count=10, community=None):
        url = f"{HAVEN_API}/api/public/contributors?limit={count}"
        if community:
            url += f"&community={community}"

        await channel.send(f"📡 Fetching top {count} contributors...")

        try:
            async with aiohttp.ClientSession(timeout=HAVEN_TIMEOUT) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await channel.send("Error fetching contributors.")
                        return

                    data = await resp.json()

        except Exception as e:
            await channel.send(f"Error: {e}")
            return

        contributors = data.get("contributors")
        if not contributors:
            await channel.send("No contributors found.")
            return

        lines = [
            f"**#{c.get('rank', '?')}** {c.get('username')} — "
            f"{c.get('total_systems', 0)} systems"
            for c in contributors
        ]

        embed = discord.Embed(
            title=f"Top {count} Contributors",
            description="\n".join(lines),
            color=0x00FFCC
        )

        await channel.send(embed=embed)

    async def send_map(self, channel):
        button = discord.ui.Button(label="✨ Open the Haven Map 🌌", url=HAVEN_URL)
        view = discord.ui.View()
        view.add_item(button)

        await channel.send("Click below to see the Haven Map:", view=view)


# setup
async def setup(bot):
    await bot.add_cog(Haven_statsCog(bot))