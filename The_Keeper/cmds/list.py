import discord
from discord.ext import commands


class HelpSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cmds")
    async def help_command(self, ctx):
        commands_list = [c for c in self.bot.commands if not getattr(c, "hidden", False)]

        embed = discord.Embed(
            title=" Command List",
            description="Here is a list of all available commands.",
            color=0x8A00C4
        )

        for command in commands_list:
            description = (
                getattr(command, "short_doc", None)
                or getattr(command, "help", None)
                or getattr(command, "description", None)
                or "No description provided."
            )

            embed.add_field(
                name=f"`!{command.name}`",
                value=description,
                inline=False
            )

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HelpSystem(bot))
