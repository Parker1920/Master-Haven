import json
import os
import discord
import aiohttp
from discord.ext import tasks, commands
import requests, re
MILESTONE_FILE = "milestones.json"
HAVEN_API = os.getenv("HAVEN_API")

START_MILESTONE = 13000 
PLANET_START_MILESTONE = 25000
PLANET_STEP = 5000

def load_milestone():
    if not os.path.exists(MILESTONE_FILE):
        return {}
    with open(MILESTONE_FILE, "r") as f:
        return json.load(f)

def save_milestone(data):
    with open(MILESTONE_FILE, "w") as f:
        json.dump(data, f)


HAVEN_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def fetch_system_count():
    if not HAVEN_API:
        raise ValueError("Missing HAVEN_API")

    async with aiohttp.ClientSession(timeout=HAVEN_TIMEOUT) as session:
        async with session.get(f"{HAVEN_API}/api/public/community-overview") as resp:
            if resp.status != 200:
                raise RuntimeError(f"API returned {resp.status}")

            data = await resp.json()

    totals = data.get("totals", {})
    return totals.get("total_systems", 0)

async def fetch_planet_count():
    if not HAVEN_API:
        raise ValueError("Missing HAVEN_API")

    async with aiohttp.ClientSession(timeout=HAVEN_TIMEOUT) as session:
        async with session.get(f"{HAVEN_API}/api/db_stats") as resp:
            if resp.status != 200:
                raise RuntimeError(f"API returned {resp.status}")

            data = await resp.json()

    stats = data.get("stats", {})
    return stats.get("planets", 0)


class AnnouncementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        channel_id = os.getenv("GENERAL_CHANNEL_ID")
        try:
            self.channel_id = int(channel_id)
        except (TypeError, ValueError):
            print("⚠️ GENERAL_CHANNEL_ID missing or invalid")
            self.channel_id = None

        if not self.channel_id:
            print("❌ No valid channel ID — announcements disabled")

        data = load_milestone()

        # systems
        self.last_milestone = max(data.get("systems", 0), START_MILESTONE)

        # ✅ planets
        self.last_planet_milestone = max(data.get("planets", 0), PLANET_START_MILESTONE)

        self.check_milestones.start()

    def cog_unload(self):
        self.check_milestones.cancel()

    # expose for commands
    async def get_system_count(self):
        return await fetch_system_count()

    async def get_planet_count(self):
        return await fetch_planet_count()

    @tasks.loop(minutes=5)
    async def check_milestones(self):
        if not self.channel_id:
            return

        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return

        try:
            current = await fetch_system_count()
            planets = await fetch_planet_count()
        except Exception as e:
            print(f"API error: {e}")
            return

        data = load_milestone()

        # -------- SYSTEMS --------
        milestone = (current // 1000) * 1000

        if milestone >= START_MILESTONE:
            while self.last_milestone < milestone:
                self.last_milestone += 1000
                data["systems"] = self.last_milestone

                embed = discord.Embed(
                    title="🚀 Milestone Achieved!",
                    description=f"{self.last_milestone:,} systems tracked!",
                    color=0x8A00C4
                )
                embed.add_field(name="Current Total", value=f"{current:,}")

                await channel.send(embed=embed)

        # -------- PLANETS --------
        planet_milestone = (planets // PLANET_STEP) * PLANET_STEP

        if planet_milestone >= PLANET_START_MILESTONE:
            while self.last_planet_milestone < planet_milestone:
                self.last_planet_milestone += PLANET_STEP
                data["planets"] = self.last_planet_milestone

                embed = discord.Embed(
                    title="🪐 Planet Milestone Achieved!",
                    description=f"{self.last_planet_milestone:,} planets tracked!",
                    color=0x00FFCC
                )
                embed.add_field(name="Current Total", value=f"{planets:,}")

                await channel.send(embed=embed)

        save_milestone(data)

    @check_milestones.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


DOC_URL = "https://docs.google.com/document/d/1FRfxnmXdhU_O-OGTxG52lM0298zzKnGp7W2Qs5njBPo/export?format=txt"



class GoogleDocParser:
    def __init__(self, url: str):
        self.url = url

    def get_doc_text(self):
        return requests.get(self.url, timeout=10).text

    def parse_sections(self, text: str):
        return [s.strip() for s in text.split("##") if s.strip()]

    def parse_inline_blocks(self, text: str):
        pattern = r"```(.*?)```|\"(.*?)\""
        matches = re.finditer(pattern, text, re.DOTALL)

        sections = []
        for m in matches:
            content = m.group(1) or m.group(2)
            if content:
                sections.append(content.strip())

        return sections

    def parse_blocks(self, text: str):
        lines = text.splitlines()

        chunks = []
        buffer = []

        empty_count = 0

        for line in lines:
            buffer.append(line)

            if line.strip() == "":
                empty_count += 1
            else:
                empty_count = 0

            if empty_count >= 5:
                chunks.append("\n".join(buffer[:-5]).strip())
                buffer = []
                empty_count = 0

        if buffer:
            chunks.append("\n".join(buffer).strip())

        return [c for c in chunks if c]

async def setup(bot):
    await bot.add_cog(AnnouncementCog(bot))