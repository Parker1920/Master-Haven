import discord
from discord.ext import commands


class EmbedPaginator(discord.ui.View):
    """A simple UI view to handle multi-page embeds using buttons."""
    def __init__(self, pages: list[discord.Embed], author_id: int):
        super().__init__(timeout=60.0)  # Buttons expire after 60 seconds of inactivity
        self.pages = pages
        self.author_id = author_id
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This menu isn't for you!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.blurple)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)


class HelpSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cmds")
    async def help_command(self, ctx):
        all_fields = []

        # Gather Prefix Commands
        for command in self.bot.commands:
            if getattr(command, "hidden", False):
                continue
            description = (
                getattr(command, "short_doc", None)
                or getattr(command, "help", None)
                or getattr(command, "description", None)
                or "No description provided."
            )
            all_fields.append({
                "name": f"`!{command.name}` (Prefix)",
                "value": description
            })

        # Gather Slash Commands
        slash_commands = self.bot.tree.get_commands()
        for command in slash_commands:
            description = getattr(command, "description", None) or "No description provided."
            all_fields.append({
                "name": f"`/{command.name}` (Slash)",
                "value": description
            })

        if not all_fields:
            embed = discord.Embed(
                title="All Bot Commands",
                description="No commands were found.",
                color=0x8A00C4
            )
            await ctx.send(embed=embed)
            return

        # Split into chunks of 10
        fields_per_page = 10
        chunks = [all_fields[i:i + fields_per_page] for i in range(0, len(all_fields), fields_per_page)]
        
        pages = []
        for index, chunk in enumerate(chunks):
            embed = discord.Embed(
                title="All Bot Commands",
                description="A complete list of all prefix and slash commands.",
                color=0x8A00C4
            )
            for field in chunk:
                embed.add_field(name=field["name"], value=field["value"], inline=False)
            
            embed.set_footer(text=f"Page {index + 1} of {len(chunks)}")
            pages.append(embed)

        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            view = EmbedPaginator(pages, ctx.author.id)
            await ctx.send(embed=pages[0], view=view)


async def setup(bot):
    await bot.add_cog(HelpSystem(bot))
