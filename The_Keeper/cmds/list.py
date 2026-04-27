import discord
from discord.ext import commands


class HelpPagination(discord.ui.View):
    def __init__(self, ctx, commands_list):
        super().__init__(timeout=120)
        self.ctx = ctx

        cmd_map = {
            c.name: c
            for c in commands_list
            if not getattr(c, "hidden", False)
        }

        PAGE_MAP = {
            0: {
                "title": "🧭 Help and Library Commands",
                "commands": ["addciv", "community", "list", "map", "partners", "hexkey"]
            },
            1: {
                "title": "📊 XP System",
                "commands": ["xp", "department"]
            },
            2: {
                "title": "📡 Stats",
                "commands": ["stats", "best", "planets", "systems"]
            },
            3: {
                "title": "💾 Upload",
                "commands": ["newsystem", "discovery"],
                "note": "Uploads will not work outside of the correct discovery thread. Find threads in: <#1432875487503585290> category."
            }
        }

        self.pages = self.build_pages(cmd_map, PAGE_MAP)
        self.page = 0
        self.max_page = len(self.pages) - 1
        self.message = None

    def build_pages(self, cmd_map, page_map):
        pages = []

        for i in sorted(page_map.keys()):
            page_data = page_map[i]

            cmds = [
                cmd_map[name]
                for name in page_data["commands"]
                if name in cmd_map
            ]

            pages.append({
                "title": page_data["title"],
                "commands": cmds,
                "note": page_data.get("note")
            })

        return pages

    def build_embed(self):
        page = self.pages[self.page]
        chunk = page["commands"]

        embed = discord.Embed(
            title=page["title"],
            description=f"Page {self.page + 1}/{self.max_page + 1}",
            color=0x8A00C4
        )

        # Optional page note (Upload warning)
        if page.get("note"):
            embed.add_field(
                name="⚠️ Notice",
                value=page["note"],
                inline=False
            )

        # XP channel hint (kept from previous fix)
        if "XP System" in page["title"]:
            embed.description += "\nLive XP Tracking: <#1434695249510400020>"

        for command in chunk:
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

        return embed

    async def update(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self
        )

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.defer()

        if self.page > 0:
            self.page -= 1
            await self.update(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.defer()

        if self.page < self.max_page:
            self.page += 1
            await self.update(interaction)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass


class HelpSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="list")
    async def help_command(self, ctx):
        commands_list = list(self.bot.commands)

        view = HelpPagination(ctx, commands_list)
        msg = await ctx.send(embed=view.build_embed(), view=view)
        view.message = msg


async def setup(bot):
    await bot.add_cog(HelpSystem(bot))