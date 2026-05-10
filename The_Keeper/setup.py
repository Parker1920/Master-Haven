import discord
from discord import app_commands
from discord.ext import commands
import json
import os


# ---------------- GUILD CONFIG SYSTEM ----------------

GUILD_FOLDER = "Data/guilds"
os.makedirs(GUILD_FOLDER, exist_ok=True)


def guild_path(guild_id: int):
    return os.path.join(GUILD_FOLDER, f"{guild_id}.json")


def load_guild_config(guild_id: int):
    path = guild_path(guild_id)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)


def save_guild_config(guild_id: int, data: dict):
    path = guild_path(guild_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


# ---------------- COMMAND FETCHER ----------------

def get_all_app_commands(bot: commands.Bot):
    """
    Pulls ALL slash commands from loaded cogs/extensions
    (exclaim.py, slash.py, Voyager.py, etc.)
    """
    cmds = []
    for cmd in bot.tree.get_commands():
        desc = cmd.description or "No description"
        cmds.append((cmd.name, desc))
    return cmds


# ---------------- UI: COMMAND SELECT ----------------

class CommandSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        options = [
            discord.SelectOption(label=name, value=name, description=desc[:100])
            for name, desc in get_all_app_commands(bot)
        ]

        super().__init__(
            placeholder="Select a command to configure...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        command_name = self.values[0]

        await interaction.response.edit_message(
            content=f"✅ Selected command: **/{command_name}**\nNow select channel(s):",
            view=ChannelSelectView(command_name)
        )


class CommandSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180)
        self.add_item(CommandSelect(bot))


# ---------------- UI: CHANNEL SELECT ----------------

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, command_name: str):
        self.command_name = command_name

        super().__init__(
            placeholder="Select channel(s)...",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.text]
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command only works in servers.",
                ephemeral=True
            )

        guild_id = interaction.guild.id
        channels = self.values

        config = load_guild_config(guild_id)

        # store by command name now
        config[self.command_name] = [c.id for c in channels]

        save_guild_config(guild_id, config)

        mentions = ", ".join(c.mention for c in channels)

        await interaction.response.edit_message(
            content=(
                f"✅ Setup saved!\n\n"
                f"**Command:** /{self.command_name}\n"
                f"**Channels:** {mentions}"
            ),
            view=None
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, command_name: str):
        super().__init__(timeout=180)
        self.add_item(ChannelSelect(command_name))


# ---------------- MAIN COG ----------------

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="Configure bot commands per server"
    )
    async def setup(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "❌ This command only works inside servers.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🔧 **Setup Wizard**\nSelect a command to configure:",
            view=CommandSelectView(self.bot),
            ephemeral=True
        )


# ---------------- EXTENSION ENTRYPOINT ----------------

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))