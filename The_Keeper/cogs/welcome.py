import discord
from discord.ext import commands
from Data.xpdata import PRIMARY_ROLE_MAP

class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

#---------------call for cmds---------------    
    async def send_welcome_embed(self, channel, member):
        avatar = member.avatar.url if member.avatar else member.default_avatar.url

        embed = discord.Embed(
            title=f"We witness you, Voyager {member.display_name}!",
            description=(
                "Welcome to the Haven! Our mission is to chart the stars and archive discoveries. "
                "We observe the history and universe of no man's sky in an attempt to learn and archive. "
                "Our main project is the Voyager's Haven map: https://havenmap.online/map/latest"
            ),
            color=0x8A00C4
        )

        embed.set_thumbnail(url=avatar)
        await channel.send(embed=embed)

    # -------------------- Welcome System --------------------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        bot = self.bot

        channel_id = getattr(bot, "WELCOME_CHANNEL_ID", None)

        if not channel_id:
            print("[ERROR] WELCOME_CHANNEL_ID not set.")
            return

        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"[ERROR] Channel {channel_id} not found.")
            return

        await self.send_welcome_embed(channel, member)
        print(f"[WELCOME] Sent welcome embed for {member.name}")

    # -------------------- Role Update System --------------------
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        bot = self.bot

        new_roles = [role for role in after.roles if role not in before.roles]
        if not new_roles:
            return

        # PRIMARY_ROLE_MAP is already correct format:
        # { "cartographer": role_id, ... }

        role_id_to_name = {v: k for k, v in PRIMARY_ROLE_MAP.items()}

        for new_role in new_roles:

            # ---------------- PRIMARY ROLE SET ----------------
            if new_role.id in role_id_to_name:
                try:
                    from cogs.xp_system import set_primary_role  # FIXED IMPORT LOCATION

                    role_name = role_id_to_name[new_role.id]
                    await set_primary_role(after, role_name, bot)

                except Exception as e:
                    print(f"[XP ERROR] {e}")

            # ---------------- WELCOME DM ----------------
            role_messages = getattr(bot, "role_welcome_messages", {})

            if new_role.id in role_messages:
                try:
                    avatar = after.avatar.url if after.avatar else after.default_avatar.url

                    embed = discord.Embed(
                        title=f"Welcome to The Haven, {after.display_name}!",
                        description=role_messages[new_role.id],
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

                    await after.send(embed=embed)
                    print(f"[WELCOME] Sent DM to {after.name} for role {new_role.name}")

                except discord.Forbidden:
                    print(f"[WELCOME] Cannot DM {after.name} - DMs are closed.")
                except Exception as e:
                    print(f"[WELCOME ERROR] {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.content.strip().lower() == "welcome, voyager!":
            await self.send_welcome_embed(message.channel, message.author)


# -------------------- Setup --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeCog(bot))