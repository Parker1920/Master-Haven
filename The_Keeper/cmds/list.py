import discord
from discord.ext import commands


class HelpSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cmds")
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="# All Bot Commands",
            description="A complete list of all prefix and slash commands.",
            color=0x8A00C4
        )

        for command in self.bot.commands:

            if getattr(command, "hidden", False):
                continue

            description = (
                getattr(command, "short_doc", None)
                or getattr(command, "help", None)
                or getattr(command, "description", None)
                or "No description provided."
            )

            embed.add_field(
                name=f"`!{command.name}` (Prefix)",
                value=description,
                inline=False
            )

        
        slash_commands = self.bot.tree.get_commands()
        
        for command in slash_commands:
          
            description = getattr(command, "description", None) or "No description provided."
            
            embed.add_field(
                name=f"`/{command.name}` (Slash)",
                value=description,
                inline=False
            )

        
        if not embed.fields:
            embed.description = "No commands were found."

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HelpSystem(bot))
