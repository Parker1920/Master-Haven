import discord
from discord.ext import commands


class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------- MEMBER JOIN --------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        print(f"[JOIN] {member} joined")

        channel_id = self.bot.CHANNELS.get("welcome")

        if not channel_id:
            print("[ERROR] WELCOME channel not set.")
            return

        try:
            channel = await self.get_channel(int(channel_id))
        except Exception as e:
            print(f"[ERROR] Could not fetch channel: {e}")
            return

        await self.send_welcome_embed(channel, member)


    # -------------------- CHANNEL RESOLVER --------------------
    async def get_channel(self, channel_id: int):
        channel = self.bot.get_channel(channel_id)

        if channel is None:
            channel = await self.bot.fetch_channel(channel_id)

        return channel

    @commands.command(name="welcome")
    @commands.has_permissions(administrator=True)
    async def simulate_join(self, ctx, member: discord.Member = None):

        if member is None:
            member = ctx.author

        channel_id = self.bot.CHANNELS.get("welcome")

        if not channel_id:
            await ctx.send("❌ Welcome channel not configured.")
            return

        try:
            channel = await self.get_channel(int(channel_id))
        except Exception:
            await ctx.send("❌ Could not fetch welcome channel.")
            return

        await self.send_welcome_embed(channel, member)

        await ctx.send(f"✅ Simulated join for {member.mention}")

    # -------------------- WELCOME EMBED --------------------
    async def send_welcome_embed(self, channel, member: discord.Member):
        avatar = member.display_avatar.url

        embed = discord.Embed(
            title=f"Welcome, Voyager",
            description=(
                "Welcome to The Voyager's Haven — a community dedicated to exploration, research, archiving and stellar cartography. We are invested in several projects to chart and connect the universe of No Mans Sky! Stay and watch, or connect with us!\n"
                "Check out some of our projects here!"
            ),
            color=0x8A00C4
        )

        embed.add_field(
            name="Learn More",
            value=(
                "🌐 https://havenmap.online/\n"
                "📖 https://docs.google.com/document/d/1T0xEMTddToEbG5HAgmwE9BAPAlxlosvwxC9f74wonxU/edit?usp=drivesdk\n"
                "💫 https://travelers-exchange.online/"
            ),
            inline=False
        )

        embed.add_field(
        name="Join Us",
        value="To become part of our mapping project, sign a charter or to talk to one of our staff, please submit a ticket in <#1434762611504713829>",
        inline=False
    )

        embed.set_thumbnail(url=avatar)

        embed.set_image(
            url="https://cdn.discordapp.com/attachments/1483946204919501030/1483951736187256913/ezgif-36919d2af39654a6.gif"
        )
        members = sorted(
            [m for m in member.guild.members if m.joined_at],
            key=lambda m: m.joined_at
        )

        position = next((i for i, m in         enumerate(members, 1) if m.id == member.id), None)
        embed.set_footer(text=f"You are #{position} in the server")

        await channel.send(
            content=f"Welcome {member.mention}!",
            embed=embed,
            view=DeptView(member.guild.id)
        )

class DeptView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__()
        self.add_item(discord.ui.Button(
            label="Select Department",
            style=discord.ButtonStyle.link,
            url=f"https://discord.com/channels/{guild_id}/1502730838171713687"
        ))

# -------------------- SETUP --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
    print("[COG LOADED] WelcomeCog")