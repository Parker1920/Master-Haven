import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

# ---------------- DATABASE CONFIG ----------------

DB_PATH = "/home/pi8gb/docker/haven-ui/Master-Haven/The_Keeper/Data/guild.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Discord select menu limit
MAX_OPTIONS = 25

# ---------------- DATABASE SETUP ----------------

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS command_config (
    guild_id INTEGER NOT NULL,
    command_name TEXT NOT NULL,
    channel_id INTEGER NOT NULL,
    role_id INTEGER,
    PRIMARY KEY (guild_id, command_name, channel_id)
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLES_SQL)
        await db.commit()

# ---------------- COMMAND FETCHER ----------------

def get_all_commands(bot: commands.Bot):
    cmds = []

    # Slash Commands
    for cmd in bot.tree.get_commands():
        desc = cmd.description or "No description"
        cmds.append((f"/{cmd.name}", desc))

    # Prefix Commands
    for cmd in bot.commands:
        if cmd.hidden:
            continue

        name = f"!{cmd.name}"
        desc = cmd.help or "No description"
        cmds.append((name, desc))

    # Remove duplicates + sort
    cmds = list(dict.fromkeys(cmds))
    cmds.sort(key=lambda x: x[0])

    return cmds

# ---------------- DATABASE HELPERS ----------------

async def save_command_config(
    guild_id: int,
    command_name: str,
    channel_ids: list[int],
    role_id: int | None
):
    async with aiosqlite.connect(DB_PATH) as db:

        # Remove existing config
        await db.execute(
            """
            DELETE FROM command_config
            WHERE guild_id = ?
            AND command_name = ?
            """,
            (guild_id, command_name)
        )

        # Save new config
        for channel_id in channel_ids:
            await db.execute(
                """
                INSERT INTO command_config (
                    guild_id,
                    command_name,
                    channel_id,
                    role_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    guild_id,
                    command_name,
                    channel_id,
                    role_id
                )
            )

        await db.commit()


async def get_command_config(
    guild_id: int,
    command_name: str
):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT channel_id, role_id
            FROM command_config
            WHERE guild_id = ?
            AND command_name = ?
            """,
            (guild_id, command_name)
        )

        rows = await cursor.fetchall()

    if not rows:
        return None

    return {
        "channels": [r[0] for r in rows],
        "role_id": rows[0][1]
    }

# ---------------- UI: COMMAND SELECT ----------------

class CommandSelect(discord.ui.Select):
    def __init__(
        self,
        bot: commands.Bot,
        page: int = 0
    ):
        self.bot = bot
        self.page = page

        all_commands = get_all_commands(bot)

        start = page * MAX_OPTIONS
        end = start + MAX_OPTIONS

        page_commands = all_commands[start:end]

        options = [
            discord.SelectOption(
                label=name[:100],
                value=name,
                description=(desc or "No description")[:100]
            )
            for name, desc in page_commands
        ]

        super().__init__(
            placeholder=f"Select command page {page + 1}",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        command_name = self.values[0]

        await interaction.response.edit_message(
            content=(
                f"✅ Selected command: **{command_name}**\n"
                f"Now select allowed channels:"
            ),
            view=ChannelSelectView(command_name)
        )


class NextPageButton(discord.ui.Button):
    def __init__(
        self,
        bot: commands.Bot,
        page: int
    ):
        super().__init__(
            label="Next",
            style=discord.ButtonStyle.primary
        )

        self.bot = bot
        self.page = page

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        await interaction.response.edit_message(
            view=CommandSelectView(
                self.bot,
                self.page + 1
            )
        )


class PreviousPageButton(discord.ui.Button):
    def __init__(
        self,
        bot: commands.Bot,
        page: int
    ):
        super().__init__(
            label="Previous",
            style=discord.ButtonStyle.secondary
        )

        self.bot = bot
        self.page = page

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        await interaction.response.edit_message(
            view=CommandSelectView(
                self.bot,
                self.page - 1
            )
        )


class CommandSelectView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        page: int = 0
    ):
        super().__init__(timeout=180)

        self.bot = bot
        self.page = page

        all_commands = get_all_commands(bot)

        self.add_item(CommandSelect(bot, page))

        total_pages = (
            len(all_commands) - 1
        ) // MAX_OPTIONS

        if page > 0:
            self.add_item(
                PreviousPageButton(bot, page)
            )

        if page < total_pages:
            self.add_item(
                NextPageButton(bot, page)
            )

# ---------------- UI: CHANNEL SELECT ----------------

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, command_name: str):
        self.command_name = command_name

        super().__init__(
            placeholder="Select allowed channels...",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.text]
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        selected_channels = self.values

        await interaction.response.edit_message(
            content=(
                f"✅ Channels selected for "
                f"**{self.command_name}**.\n"
                f"Now select an optional role restriction."
            ),
            view=RoleSelectView(
                self.command_name,
                selected_channels
            )
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, command_name: str):
        super().__init__(timeout=180)

        self.add_item(
            ChannelSelect(command_name)
        )

# ---------------- UI: ROLE SELECT ----------------

class RoleSelect(discord.ui.RoleSelect):
    def __init__(
        self,
        command_name: str,
        channels: list[discord.abc.GuildChannel]
    ):
        self.command_name = command_name
        self.channels = channels

        super().__init__(
            placeholder="Optional role restriction...",
            min_values=0,
            max_values=1
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        if not interaction.guild:
            return

        role_id = None
        role_mention = "None"

        if self.values:
            role = self.values[0]
            role_id = role.id
            role_mention = role.mention

        await save_command_config(
            guild_id=interaction.guild.id,
            command_name=self.command_name,
            channel_ids=[
                c.id for c in self.channels
            ],
            role_id=role_id
        )

        mentions = ", ".join(
            c.mention for c in self.channels
        )

        await interaction.response.edit_message(
            content=(
                f"✅ Configuration saved!\n\n"
                f"**Command:** {self.command_name}\n"
                f"**Channels:** {mentions}\n"
                f"**Role Restriction:** "
                f"{role_mention}"
            ),
            view=None
        )


class RoleSelectView(discord.ui.View):
    def __init__(
        self,
        command_name: str,
        channels: list[discord.abc.GuildChannel]
    ):
        super().__init__(timeout=180)

        self.add_item(
            RoleSelect(
                command_name,
                channels
            )
        )




async def is_command_allowed(guild_id: int, command_name: str, channel_id: int, member: discord.Member):
    config = await get_command_config(guild_id, command_name)

    if not config:
        return True  # no restrictions set

    # Channel restriction
    if channel_id not in config["channels"]:
        return False

    # Role restriction
    role_id = config["role_id"]
    if role_id:
        role = member.get_role(role_id)
        if not role:
            return False

    return True

# ---------------- MAIN COG ----------------

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx: commands.Context):
        if not ctx.guild or not ctx.channel or not ctx.author:
            return

        command_name = f"!{ctx.command.name}"

        allowed = await is_command_allowed(
            guild_id=ctx.guild.id,
            command_name=command_name,
            channel_id=ctx.channel.id,
            member=ctx.author
        )

        if not allowed:
            raise commands.CheckFailure(
                "Command restricted for this channel or role."
            )

    @app_commands.command(
        name="setup",
        description="Configure bot commands per server"
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def setup(
        self,
        interaction: discord.Interaction
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Server only command.",
                ephemeral=True
            )

        await interaction.response.send_message(
            (
                "🔧 **Setup Wizard**\n"
                "Select a command to configure:"
            ),
            view=CommandSelectView(self.bot),
            ephemeral=True
        )
    @SetupCog.listener()
async def on_command_error(self, ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(
            "⛔ You are not allowed to use this command here.",
            delete_after=5
        )

# ---------------- EXTENSION ENTRYPOINT ----------------

async def setup(bot: commands.Bot):

    await init_db()

    await bot.add_cog(
        SetupCog(bot)
    )