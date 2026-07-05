import re
from datetime import datetime, timezone
import discord
from discord.ext import commands

class TimeParser(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.time_pattern = re.compile(
            r"""
            Time:\s* # Matches "Time:" followed by optional spaces
            (\d{1,2}/\d{1,2}/(?:\d{2}|\d{4}))       # Group 1: Date (M/D/Y or D/M/Y)
            \s+                                     # Matches one or more spaces
            (\d{1,2}:\d{2})                         # Group 2: Time (H:MM)
            \s* # Optional spaces before AM/PM
            ([ap]m)                                 # Group 3: AM/PM
            """, 
            re.IGNORECASE | re.VERBOSE
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        match = self.time_pattern.search(message.content)
        if not match:
            return

        date_str = match.group(1)
        time_clock = match.group(2)
        am_pm = match.group(3).lower()
        
        full_time_str = f"{date_str} {time_clock}{am_pm}"

        try:
            year_format = "%y" if len(date_str.split("/")[-1]) == 2 else "%Y"
            
            dt = datetime.strptime(
                full_time_str,
                f"%m/%d/{year_format} %I:%M%p"
            )

            dt = dt.replace(tzinfo=timezone.utc)
            unix_timestamp = int(dt.timestamp())

            
            await message.channel.send(
                f"UTC Timestamp: <t:{unix_timestamp}:F>\n"
                f"Raw: `{unix_timestamp}`"
            )

        except ValueError:
            await message.channel.send(
                "Invalid date/time values. Note: Use `MM/DD/YY` format. Example: `Time: 1/1/26 4:00pm`"
            )

async def setup(bot):
    await bot.add_cog(TimeParser(bot))