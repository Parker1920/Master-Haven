import json
import os
import time
import discord
import aiohttp
from discord.ext import tasks, commands
import requests, re

MILESTONE_FILE = "milestones.json"
HAVEN_API = os.getenv("HAVEN_API")

START_MILESTONE = 13000
PLANET_START_MILESTONE = 25000
PLANET_STEP = 5000
SYSTEM_STEP = 1000
RECENT_WINDOW = 43200  # 12 hours


def load_milestone():
    if not os.path.exists(MILESTONE_FILE):
        return {}

    with open(MILESTONE_FILE, "r") as f:
        data = json.load(f)

    data.setdefault("announced_systems", [])
    data.setdefault("announced_planets", [])

    return data


def save_milestone(data):
    with open(MILESTONE_FILE, "w") as f:
        json.dump(data, f)


async def fetch_system_count():
    if not HAVEN_API:
        raise ValueError("Missing HAVEN_API")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{HAVEN_API}/api/public/community-overview") as resp:
            if resp.status != 200:
                raise RuntimeError(f"API returned {resp.status}")

            data = await resp.json()

    totals = data.get("totals", {})
    return totals.get("total_systems", 0)


async def fetch_planet_count():
    if not HAVEN_API:
        raise ValueError("Missing HAVEN_API")

    async with aiohttp.ClientSession() as session:
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

        self.last_milestone = max(
            data.get("systems", 0),
            START_MILESTONE
        )

        self.last_planet_milestone = max(
            data.get("planets", 0),
            PLANET_START_MILESTONE
        )

        self.boot_time = int(time.time())

        self.check_milestones.start()

    def cog_unload(self):
        self.check_milestones.cancel()

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
            current_systems = await fetch_system_count()
            current_planets = await fetch_planet_count()

            print(
                "systems/planets:",
                current_systems,
                current_planets
            )

        except Exception as e:
            print(f"API error: {e}")
            return

        data = load_milestone()
        now = int(time.time())

        # -------- SYSTEMS --------
        system_milestone = (
            current_systems // SYSTEM_STEP
        ) * SYSTEM_STEP

        if system_milestone >= START_MILESTONE:

            while self.last_milestone < system_milestone:

                self.last_milestone += SYSTEM_STEP

                data["systems"] = self.last_milestone
                data["systems_time"] = now

                recent = (
                    now - self.boot_time
                ) <= RECENT_WINDOW

                already_sent = (
                    self.last_milestone
                    in data.get("announced_systems", [])
                )

                if recent and not already_sent:

                    embed = discord.Embed(
                        title="🚀 Milestone Achieved!",
                        description=f"{self.last_milestone:,} systems tracked!",
                        color=0x8A00C4
                    )

                    embed.add_field(
                        name="Current Total",
                        value=f"{current_systems:,}"
                    )

                    await channel.send(embed=embed)

                    data["announced_systems"].append(
                        self.last_milestone
                    )

        # -------- PLANETS --------
        planet_milestone = (
            current_planets // PLANET_STEP
        ) * PLANET_STEP

        if planet_milestone >= PLANET_START_MILESTONE:

            while self.last_planet_milestone < planet_milestone:

                self.last_planet_milestone += PLANET_STEP

                data["planets"] = self.last_planet_milestone
                data["planets_time"] = now

                recent = (
                    now - self.boot_time
                ) <= RECENT_WINDOW

                already_sent = (
                    self.last_planet_milestone
                    in data.get("announced_planets", [])
                )

                if recent and not already_sent:

                    embed = discord.Embed(
                        title="🪐 Planet Milestone Achieved!",
                        description=f"{self.last_planet_milestone:,} planets tracked!",
                        color=0x00FFCC
                    )

                    embed.add_field(
                        name="Current Total",
                        value=f"{current_planets:,}"
                    )

                    await channel.send(embed=embed)

                    data["announced_planets"].append(
                        self.last_planet_milestone
                    )

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
    @commands.command(name="announce")
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx):
    
        channel = self.bot.get_channel(self.channel_id)
    
        if not channel:
            await ctx.send("Channel not found.")
            return
    
        current_systems = await fetch_system_count()
        current_planets = await fetch_planet_count()
    
        embed = discord.Embed(
            title="🚀 Milestone Achieved!",
            description=f"{self.last_milestone:,} systems tracked!",
            color=0x8A00C4
        )
    
        embed.add_field(
            name="Current Total",
            value=f"{current_systems:,}"
        )
    
        await channel.send(embed=embed)
    
        embed = discord.Embed(
            title="🪐 Planet Milestone Achieved!",
            description=f"{self.last_planet_milestone:,} planets tracked!",
            color=0x00FFCC
        )

    embed.add_field(
        name="Current Total",
        value=f"{current_planets:,}"
    )

    await channel.send(embed=embed)

    await ctx.send("Announcements sent.")

async def setup(bot):
    await bot.add_cog(AnnouncementCog(bot))