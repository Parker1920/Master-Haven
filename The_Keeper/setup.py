import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

# ---------------- DATABASE CONFIG ----------------

DB_PATH = os.path.join(os.path.dirname(__file__), "Data", "guild.db")

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
    channel_ids: list[int],
    role_id: int | None
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

    role_ids = {
        r[1] for r in rows
        if r[1] is not None
    }

    return {
        "channels": [r[0] for r in rows],
        "role_id": next(iter(role_ids), None)
    }
async def get_guild_command_config(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT command_name, channel_id, role_id FROM command_config WHERE guild_id = ?",
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
            view=SetupFlowView(selected_command)
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



class SetupFlowView(discord.ui.View):
    def __init__(self, command_name: str):
        super().__init__(timeout=180)

        self.command_name = command_name
        self.channels = []

        self.channel_select = ChannelSelect(command_name)
        self.role_select = RoleSelect(command_name, [])

        self.add_item(self.channel_select)
        self.add_item(self.role_select)
        self.add_item(SubmitSkipRoleButton())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, command_name: str):
        self.command_name = command_name

        super().__init__(
            placeholder="Select allowed channels...",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.text],
            custom_id=f"channel_select:{command_name}"
        )

    async def callback(self, interaction: discord.Interaction):
        view: SetupFlowView = self.view

        view.channels = self.values

        # update channels inside role select
        view.role_select.channels = self.values

        await interaction.response.edit_message(
            content=(
                f"✅ Channels selected for **{self.command_name}**.\n"
                f"You may now optionally select a role,\n"
                f"or press **Skip role & Save**."
            ),
            view=view
        )


class SubmitSkipRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Skip role & Save",
            style=discord.ButtonStyle.success
        )

    async def callback(self, interaction: discord.Interaction):
        view: SetupFlowView = self.view

        if not view.channels:
            return await interaction.response.send_message(
                "❌ Select channels first.",
                ephemeral=True
            )

        await save_command_config(
            interaction.guild.id,
            view.command_name,
            [c.id for c in view.channels],
            None
        )

        mentions = ", ".join(c.mention for c in view.channels)

        await interaction.response.edit_message(
            content=(
                f"✅ Configuration saved!\n\n"
                f"**Command:** {view.command_name}\n"
                f"**Channels:** {mentions}\n"
                f"**Role Restriction:** None"
            ),
            view=None
        )


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
            max_values=1,
            custom_id=f"role_select:{command_name}"
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
            channel_ids=[c.id for c in self.channels],
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
                f"**Role Restriction:** {role_mention}"
            ),
            view=None
        )


async def is_command_allowed(
    guild_id: int,
    command_name: str,
    channel_id: int,
    member: discord.Member | discord.User
):
    config = await get_command_config(guild_id, command_name)

    if not config:
        return True

    if channel_id not in config["channels"]:
        return False

    role_id = config["role_id"]

    if role_id is None:
        return True

    if not isinstance(member, discord.Member):
        return False

    return member.get_role(role_id) is not None

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
    RESET_DB = True

    if RESET_DB:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DROP TABLE IF EXISTS command_config")
            await db.commit()

    
    await init_db()

    await bot.add_cog(
        SetupCog(bot)
    )