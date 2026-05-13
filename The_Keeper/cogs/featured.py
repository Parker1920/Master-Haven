import os
import json
import asyncio
from datetime import datetime, timezone
import discord
from discord.ext import commands, tasks

os.makedirs("Data", exist_ok=True)

FEATURED_FILE = "Data/featured_messages.json"

def is_valid_image(filename: str):
    return filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))

class FeaturedCog(commands.Cog):
    def __init__(self, bot, PHOTO_CHANNEL_ID, FEATURED_CHANNEL_ID, FEATURED_THRESHOLD, FEATURED_TIME_LIMIT, log_func, count_total_reactions_func):
        self.bot = bot
        self.PHOTO_CHANNEL_ID = PHOTO_CHANNEL_ID
        self.FEATURED_CHANNEL_ID = FEATURED_CHANNEL_ID
        self.FEATURED_THRESHOLD = FEATURED_THRESHOLD
        self.FEATURED_TIME_LIMIT = FEATURED_TIME_LIMIT
        self.log = log_func
        self.count_total_reactions = count_total_reactions_func

        self.FEATURED_MESSAGES = self.load_featured_messages()
        self.PROCESSING = set()

        self.bootstrapped = False

    # -------------------- LOAD / SAVE --------------------
    def load_featured_messages(self):
        if not os.path.exists(FEATURED_FILE):
            with open(FEATURED_FILE, "w") as f:
                json.dump([], f, indent=4)

        try:
            with open(FEATURED_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    return set()
                data = json.loads(content)
                if isinstance(data, list):
                    return set(data)
                else:
                    print("featured_messages.json invalid format. Resetting.")
        except (json.JSONDecodeError, ValueError):
            print("featured_messages.json corrupted. Resetting.")

        with open(FEATURED_FILE, "w") as f:
            json.dump([], f, indent=4)
        return set()

    def save_featured_messages(self):
        try:
            with open(FEATURED_FILE, "w") as f:
                json.dump(list(self.FEATURED_MESSAGES), f, indent=4)
        except Exception as e:
            print(f"Failed saving featured messages: {e}")

    # -------------------- STARTUP BOOTSTRAP --------------------
    @commands.Cog.listener()
    async def on_ready(self):
        if self.bootstrapped:
            return
        self.bootstrapped = True
        await self.bootstrap_recent_photos()

    async def bootstrap_recent_photos(self):
        await self.bot.wait_until_ready()

        photo_channel = self.bot.get_channel(self.PHOTO_CHANNEL_ID)
        if not photo_channel:
            self.log("BOOTSTRAP", "Photo channel not found")
            return

        try:
            async for message in photo_channel.history(limit=5):
                await self.try_feature_message(message)
                await asyncio.sleep(0.2)

            self.log("BOOTSTRAP", "Checked last 5 photos on startup")

        except Exception as e:
            self.log("BOOTSTRAP_ERROR", str(e))

    # -------------------- FEATURE LOGIC --------------------
    async def try_feature_message(self, message: discord.Message):
        if message.id in self.FEATURED_MESSAGES or message.id in self.PROCESSING:
            return

        if any(reaction.me for reaction in message.reactions):
            return

        self.PROCESSING.add(message.id)
        try:
            now = datetime.now(timezone.utc)
            created = message.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (now - created).total_seconds() > self.FEATURED_TIME_LIMIT:
                return

            if not message.attachments:
                return

            total_reactions = self.count_total_reactions(message)
            if total_reactions < self.FEATURED_THRESHOLD:
                return

            featured_channel = self.bot.get_channel(self.FEATURED_CHANNEL_ID)
            if not featured_channel:
                self.log("ERROR", "Featured channel not found")
                return

            images = [a for a in message.attachments if is_valid_image(a.filename)]

            if not images:
                return
            
            for index, image in enumerate(images, start=1):
                embed = discord.Embed(
                    title=f"📸 Featured Photo #{index}",
                    description=f"Featured by {message.author.mention}",
                    color=0x008080
                )
            
                embed.set_image(url=image.url)
            
                embed.add_field(
                    name="Original Message",
                    value=f"[Jump to photo]({message.jump_url})",
                    inline=False
                )
            
                await featured_channel.send(embed=embed)

            self.FEATURED_MESSAGES.add(message.id)
            self.save_featured_messages()

            try:
                await message.add_reaction("🌟")
            except discord.HTTPException:
                pass

            self.log("FEATURE", f"Featured {message.id} ({total_reactions} reactions)")

        except Exception as e:
            self.log("ERROR", f"Feature error: {e}")
        finally:
            self.PROCESSING.discard(message.id)

    # -------------------- EVENT LISTENERS --------------------
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        message = reaction.message
        if isinstance(message, discord.PartialMessage):
            try:
                message = await message.fetch()
            except Exception as e:
                print(f"Failed to fetch partial message: {e}")
                return

        if message.channel.id != self.PHOTO_CHANNEL_ID:
            return

        await self.try_feature_message(message)

    # -------------------- LEADERBOARD HELPERS --------------------
    async def gather_featured_photos(self):
        photo_channel = self.bot.get_channel(self.PHOTO_CHANNEL_ID)
        if not photo_channel:
            return []

        photo_data = []
        for msg_id in self.FEATURED_MESSAGES:
            try:
                msg = await photo_channel.fetch_message(msg_id)
            except (discord.NotFound, discord.Forbidden):
                continue
            if not msg.attachments:
                continue
            total_reactions = self.count_total_reactions(msg)
            if total_reactions > 0:
                photo_data.append({
                    "author": msg.author.mention,
                    "reactions": total_reactions,
                    "url": msg.jump_url,
                    "image_url": msg.attachments[0].url
                })
            await asyncio.sleep(0.05)
        return photo_data
        
    async def gather_featured_user_stats(self):
        photo_channel = self.bot.get_channel(self.PHOTO_CHANNEL_ID)
        if not photo_channel:
            return {}
    
        user_stats = {}
    
        for msg_id in self.FEATURED_MESSAGES:
            try:
                msg = await photo_channel.fetch_message(msg_id)
            except (discord.NotFound, discord.Forbidden):
                continue
    
            user = msg.author.mention
            reactions = self.count_total_reactions(msg)
    
            if user not in user_stats:
                user_stats[user] = {
                    "photos": 0,
                    "reactions": 0
                }
    
            user_stats[user]["photos"] += 1
            user_stats[user]["reactions"] += reactions
    
            await asyncio.sleep(0.05)
    
        return user_stats

    # -------------------- WEEKLY LEADERBOARD TASK --------------------
    def create_weekly_leaderboard_task(self, LEADERBOARD_DAY, LEADERBOARD_TOP):
        LAST_LEADERBOARD_RUN = None

        @tasks.loop(hours=1)
        async def weekly_leaderboard():
            nonlocal LAST_LEADERBOARD_RUN
            now = datetime.now(timezone.utc)
            if LAST_LEADERBOARD_RUN == now.date() or now.weekday() != LEADERBOARD_DAY or now.hour != 12:
                return
            LAST_LEADERBOARD_RUN = now.date()

            leaderboard_channel = self.bot.get_channel(self.FEATURED_CHANNEL_ID)
            photo_data = await self.gather_featured_photos()
            if not leaderboard_channel or not photo_data:
                self.log("LEADERBOARD", "Cannot post weekly leaderboard")
                return

            top_photos = sorted(photo_data, key=lambda x: x["reactions"], reverse=True)[:LEADERBOARD_TOP]
            embed = discord.Embed(
                title="🏆 Weekly Featured Photo Leaderboard",
                description="Top photos by reactions this week",
                color=0xFFD700
            )
            for rank, photo in enumerate(top_photos, start=1):
                embed.add_field(
                    name=f"{rank}.",
                    value=(
                        f"{photo['author']}\n"
                        f"[Jump to photo]({photo['url']}) — "
                        f"{photo['reactions']} reactions"
                    ),
                    inline=False
                )
                if rank == 1 and photo["image_url"]:
                    embed.set_thumbnail(url=photo["image_url"])

            await leaderboard_channel.send(embed=embed)
            self.log("LEADERBOARD", f"Weekly leaderboard posted with {len(top_photos)} photos")

        return weekly_leaderboard

    # -------------------- IMMEDIATE LEADERBOARD --------------------
    async def post_leaderboard(self, channel=None, limit=None):

        leaderboard_channel = channel or self.bot.get_channel(self.PHOTO_CHANNEL_ID)
        photo_data = await self.gather_featured_photos()

        if not leaderboard_channel or not photo_data:
            self.log("LEADERBOARD", "Cannot post leaderboard")
            return

        top_photos = sorted(photo_data, key=lambda x: x["reactions"], reverse=True)

        if limit:
            top_photos = top_photos[:limit]

        embed = discord.Embed(
            title="🏆 Featured Photo Leaderboard",
            description="Current leaderboard of featured photos",
            color=0xFFD700
        )

        for rank, photo in enumerate(top_photos, start=1):
            embed.add_field(
                name=f"{rank}.",
                value=f"[Jump to photo]({photo['url']}) — {photo['reactions']} reactions",
                inline=False
            )

            if rank == 1 and photo["image_url"]:
                embed.set_thumbnail(url=photo["image_url"])

        await leaderboard_channel.send(embed=embed)
        self.log("LEADERBOARD", f"Leaderboard posted with {len(top_photos)} photos")


    @commands.command(name="pictest")
    @commands.has_permissions(administrator=True)
    async def pictest(self, ctx, limit: int = None):
        await self.post_leaderboard(channel=ctx.channel, limit=limit)


    @commands.command(name="picusers")
    @commands.has_permissions(administrator=True)
    async def picusers(self, ctx, limit: int = 10):
        user_stats = await self.gather_featured_user_stats()

        if not user_stats:
            await ctx.send("No featured photos found.")
            return

        sorted_users = sorted(
            user_stats.items(),
            key=lambda x: (x[1]["photos"], x[1]["reactions"]),
            reverse=True
        )

        embed = discord.Embed(
            title="🏆 Featured Photo User Leaderboard",
            description="Ranked by featured photos + total reactions",
            color=0x00AAFF
        )

        for rank, (user, stats) in enumerate(sorted_users[:limit], start=1):
            embed.add_field(
                name=f"{rank}.",
                value=(
                    f"{user}\n"
                    f"📸 Photos: {stats['photos']}\n"
                    f"⭐ Reactions: {stats['reactions']}"
                ),
                inline=False
            )

        await ctx.send(embed=embed)


# -------------------- SETUP --------------------
async def setup(bot: commands.Bot):
    PHOTO_CHANNEL_ID = int(os.getenv("PHOTO_CHANNEL_ID", "0"))
    FEATURED_CHANNEL_ID = int(os.getenv("FEATURED_CHANNEL_ID", "0"))
    FEATURED_THRESHOLD = int(os.getenv("FEATURED_THRESHOLD", "5"))
    FEATURED_TIME_LIMIT = int(os.getenv("FEATURED_TIME_LIMIT", str(7 * 24 * 60 * 60)))

    def log(tag, msg):
        print(f"[{tag}] {msg}")

    def count_total_reactions(message):
        return sum(r.count - (1 if r.me else 0) for r in message.reactions)

    cog = FeaturedCog(
        bot,
        PHOTO_CHANNEL_ID,
        FEATURED_CHANNEL_ID,
        FEATURED_THRESHOLD,
        FEATURED_TIME_LIMIT,
        log,
        count_total_reactions
    )

    await bot.add_cog(cog)