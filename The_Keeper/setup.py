import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

SESSIONS = {}

# ---------------- DATABASE CONFIG ----------------

DB_PATH = os.path.join(os.path.dirname(__file__), "Data", "guild.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

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
    cmds = {}

    for cmd in bot.tree.get_commands():
        desc = cmd.description or "No description"
        cmds.setdefault(cmd.name, desc)

    for cmd in bot.commands:
        if cmd.hidden:
            continue

        name = cmd.name
        desc = cmd.help or "No description"
        cmds.setdefault(name, desc)

    result = sorted(cmds.items(), key=lambda x: x[0])

    return result

# ---------------- DATABASE HELPERS ----------------

async def save_command_config(
    guild_id: int,
    command_name: str,
    channel_ids: list[int]
):
    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute(
            """
            DELETE FROM command_config
            WHERE guild_id = ?
            AND command_name = ?
            """,
            (guild_id, command_name)
        )

        for channel_id in channel_ids:
            await db.execute(
                """
                INSERT INTO command_config (
                    guild_id,
                    command_name,
                    channel_id
                )
                VALUES (?, ?, ?)
                """,
                (
                    guild_id,
                    command_name,
                    channel_id
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
            SELECT channel_id
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
        "channels": [r[0] for r in rows]
    }


async def get_guild_command_config(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT command_name, channel_id
            FROM command_config
            WHERE guild_id = ?
            """,
            (guild_id,)
        )

        rows = await cursor.fetchall()

    return rows

# ---------------- UI: COMMAND SELECT ----------------

class CommandSelect(discord.ui.Select):
    def __init__(
        self,
        commands_data: list[tuple[str, str]],
        page: int = 0
    ):
        self.page = page

        start = page * MAX_OPTIONS
        end = start + MAX_OPTIONS

        page_commands = commands_data[start:end]

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
            options=options,
            custom_id=f"command_select:{page}"
        )

    async def callback(self, interaction: discord.Interaction):
        selected_command = self.values[0]

        await interaction.response.edit_message(
            content=f"🔧 Configuring `{selected_command}`",
            view=ChannelSetupView(selected_command)
        )


class NextPageButton(discord.ui.Button):
    def __init__(
        self,
        bot: commands.Bot,
        page: int
    ):
        super().__init__(
            label="Next",
            style=discord.ButtonStyle.primary,
            custom_id=f"command_next:{page}"
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
            style=discord.ButtonStyle.secondary,
            custom_id=f"command_previous:{page}"
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

        self.add_item(CommandSelect(all_commands, page))

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

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class ChannelSetupView(discord.ui.View):
    def __init__(self, command_name):
        super().__init__(timeout=180)

        self.command_name = command_name

        self.add_item(ChannelPicker())


class ChannelPicker(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="Select channels...",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.text]
        )

    async def callback(self, interaction):
        key = (
            interaction.guild.id,
            interaction.user.id,
            self.view.command_name
        )

        SESSIONS[key] = {
            "channels": list(self.values)
        }

        await interaction.response.edit_message(
            content="Channels selected.",
            view=RoleSetupView(self.view.command_name))


class PostChannelView(discord.ui.View):
    def __init__(self, command_name):
        super().__init__(timeout=180)

        self.command_name = command_name

        self.add_item(SaveButton())

class RoleSetupView(discord.ui.View):
    def __init__(self, command_name):
        super().__init__(timeout=180)

        self.command_name = command_name

        self.add_item(RolePicker())
        self.add_item(SkipRoleButton())
        self.add_item(SaveButton())
        
class RolePicker(discord.ui.RoleSelect):
    def __init__(self):
        super().__init__(
            placeholder="Optional role...",
            min_values=0,
            max_values=1
        )

    async def callback(self, interaction):
        key = (
            interaction.guild.id,
            interaction.user.id,
            self.view.command_name
        )

        session = SESSIONS[key]

        session["role"] = (
            self.values[0] if self.values else None
        )

        await interaction.response.defer()
class SkipRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="No Role",
            style=discord.ButtonStyle.secondary
        )

    async def callback(self, interaction):
        key = (
            interaction.guild.id,
            interaction.user.id,
            self.view.command_name
        )

        SESSIONS[key]["role"] = None

        await interaction.response.edit_message(
            content="Role skipped. Press Save.",
            view=self.view
        )
                
class SaveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Save",
            style=discord.ButtonStyle.success
        )

    async def callback(self, interaction):
        key = (
            interaction.guild.id,
            interaction.user.id,
            self.view.command_name
        )

        session = SESSIONS.get(key)
        role = session.get("role")
        role_id = role.id if role else None

        if not session:
            return await interaction.response.edit_message(
                content="Session expired. Restart setup.",
                view=None
            )

        await save_command_config(
            interaction.guild.id,
            self.view.command_name,
            [c.id for c in session["channels"]]
        )

        SESSIONS.pop(key, None)

        await interaction.response.edit_message(
            content="✅ Saved.",
            view=None
        )


async def is_command_allowed(
    guild_id: int,
    command_name: str,
    channel_id: int,
    member: discord.Member | discord.User
):
    config = await get_command_config(
        guild_id,
        command_name
    )

    if not config:
        return True

    return channel_id in config["channels"]

# ---------------- MAIN COG ----------------

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx: commands.Context):
        if not ctx.guild or not ctx.channel or not ctx.author:
            return

    @app_commands.command(
        name="setup",
        description="Configure bot commands per server"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):

        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ Server only command.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🔧 **Setup Wizard**\nSelect a command to configure:",
            view=CommandSelectView(self.bot),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    RESET_DB = False

    if RESET_DB:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DROP TABLE IF EXISTS command_config"
            )
            await db.commit()

    await init_db()

    await bot.add_cog(
        SetupCog(bot)
    )