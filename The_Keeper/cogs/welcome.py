import discord
from discord.ext import commands


class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # -------------------- MEMBER JOIN --------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        print(f"[JOIN] {member} joined")

        channel_id = getattr(self.bot, "WELCOME_CHANNEL_ID", None)

        if not channel_id:
            print("[ERROR] WELCOME_CHANNEL_ID not set.")
            return

        channel = self.bot.get_channel(channel_id)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception as e:
                print(f"[ERROR] Could not fetch channel: {e}")
                return

        await self.send_welcome_embed(channel, member)

    # -------------------- WELCOME message--------------------
    async def send_welcome_embed(self, channel, member: discord.Member):
        avatar = member.avatar.url if member.avatar else member.default_avatar.url

        embed = discord.Embed(
            title=f"Welcome to The Haven, {member.display_name}!",
            description="Welcome to The Haven — stay and explore, connect, and chart your journey among the stars.",
            color=0x8A00C4
        )

        embed.add_field(
            name="Learn More",
            value=(
                "🌐 https://havenmap.online/haven-ui/\n"
                "📖 https://docs.google.com/document/d/...\n"
                "💫 https://travelers-exchange.online/"
            ),
            inline=False
        )

        embed.set_thumbnail(url=avatar)

        embed.set_image(
            url="https://cdn.discordapp.com/attachments/1483946204919501030/1483951736187256913/ezgif-36919d2af39654a6.gif"
        )

        await channel.send(embed=embed)

#----------------The simulation----------
@commands.command(name="welcome")
@commands.has_permissions(administrator=True)
async def simulate_join(self, ctx, member: discord.Member = None):
    """
    Simulates a member joining and sends the welcome embed.
    """

    if member is None:
        member = ctx.author  # fallback for testing

    channel_id = getattr(self.bot, "WELCOME_CHANNEL_ID", None)

    if not channel_id:
        await ctx.send(" WELCOME_CHANNEL_ID not set.")
        return

    channel = self.bot.get_channel(channel_id)

    if channel is None:
        try:
            channel = await self.bot.fetch_channel(channel_id)
        except Exception:
            await ctx.send("Could not find welcome channel.")
            return

    await self.send_welcome_embed(channel, member)

    await ctx.send(f"Simulated join for {member.mention}")


# -------------------- SETUP --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))
    print("[COG LOADED] WelcomeCog")