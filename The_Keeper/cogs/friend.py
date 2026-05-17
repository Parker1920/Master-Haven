import os
import re
import aiosqlite
import discord
from discord.ext import commands
from discord import app_commands

DB_FILE = "friendcodes.db"
FRIENDCODE_CHANNEL_ID = 1424091032185868398


RESET_DATABASE = True

FRIEND_CODE_REGEX = re.compile(
    r"\b([A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{5})\b",
    re.IGNORECASE
)


class FriendCodes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):

        # ONE-TIME RESET
        if RESET_DATABASE and os.path.exists(DB_FILE):
            os.remove(DB_FILE)
            print("friendcodes.db reset")

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS friendcodes (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    friend_code TEXT NOT NULL UNIQUE
                )
                """
            )

            await db.commit()

    async def save_friend_code(
        self,
        user: discord.User,
        friend_code: str
    ):
        friend_code = friend_code.upper()

        async with aiosqlite.connect(DB_FILE) as db:

            # DUPLICATE CHECK
            async with db.execute(
                """
                SELECT user_id
                FROM friendcodes
                WHERE UPPER(friend_code) = ?
                """,
                (friend_code,)
            ) as cursor:

                existing = await cursor.fetchone()

            # CODE BELONGS TO ANOTHER USER
            if existing and existing[0] != user.id:
                return False

            # INSERT OR UPDATE
            await db.execute(
                """
                INSERT INTO friendcodes (
                    user_id,
                    username,
                    friend_code
                )
                VALUES (?, ?, ?)

                ON CONFLICT(user_id)
                DO UPDATE SET
                    username = excluded.username,
                    friend_code = excluded.friend_code
                """,
                (
                    user.id,
                    str(user),
                    friend_code
                )
            )

            await db.commit()

        return True

    async def get_friend_code(
        self,
        user: discord.User
    ):
        async with aiosqlite.connect(DB_FILE) as db:

            async with db.execute(
                """
                SELECT friend_code
                FROM friendcodes
                WHERE user_id = ?
                """,
                (user.id,)
            ) as cursor:

                row = await cursor.fetchone()

                return row[0] if row else None

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):
        if message.author.bot:
            return

        if message.channel.id != FRIENDCODE_CHANNEL_ID:
            return

        match = FRIEND_CODE_REGEX.search(
            message.content
        )

        if not match:
            return

        friend_code = match.group(1).upper()

        success = await self.save_friend_code(
            message.author,
            friend_code
        )

        if not success:

            await message.reply(
                "error: this friendcode already exists",
                delete_after=10
            )

            return

        await message.add_reaction("✅")

    @app_commands.command(
        name="friend",
        description="Get a user's No Man's Sky friend code"
    )
    @app_commands.describe(
        user="User to look up"
    )
    async def friend(
        self,
        interaction: discord.Interaction,
        user: discord.Member
    ):

        friend_code = await self.get_friend_code(user)

        if not friend_code:

            await interaction.response.send_message(
                f"No friend code saved for {user.mention}.",
                ephemeral=True
            )

            return

        embed = discord.Embed(
            title="No Man's Sky Friend Code",
            description=(
                f"**{user.display_name}**\n"
                f"`{friend_code}`"
            ),
            color=discord.Color.green()
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(
        FriendCodes(bot)
    )