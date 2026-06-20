import re
from datetime import datetime, timezone

import discord
from discord.ext import commands

ACTIVATION_PHRASE = "Time:"

class TimeParser(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        
        self.time_pattern = re.compile(
            r"Time:\s*"
            r"(\d{1,2}/\d{1,2}/(?:\d{2}|\d{4}))"
            r"\s+"
            r"(\d{1,2}:\d{2}\s*[ap]m)",
            re.IGNORECASE
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        match = self.time_pattern.search(message.content)
        if not match:
            return

        date_str = match.group(1)
        time_str = match.group(2).replace(" ", "").lower()

        try:
            # Handle 2-digit or 4-digit years
            if len(date_str.split("/")[-1]) == 2:
                dt = datetime.strptime(
                    f"{date_str} {time_str}",
                    "%m/%d/%y %I:%M%p"
                )
            else:
                dt = datetime.strptime(
                    f"{date_str} {time_str}",
                    "%m/%d/%Y %I:%M%p"
                )

            dt = dt.replace(tzinfo=timezone.utc)

            unix_timestamp = int(dt.timestamp())

            await message.channel.send(
                f"UTC Timestamp: <t:{unix_timestamp}:F>\n"
                f"Raw: `{unix_timestamp}`"
            )

        except ValueError:
            await message.channel.send(
                "Invalid date/time format. Example: `Time: 1/1/26 4:00pm`"
            )


async def setup(bot):
    await bot.add_cog(TimeParser(bot))