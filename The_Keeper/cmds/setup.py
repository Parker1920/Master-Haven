import discord
from discord import app_commands
from discord.ext import commands

# ---------------- CONFIG ----------------
SETUP_ROLE_ID = 123456789012345678  # <-- ONLY this role can use /setup

# guild_id -> { command_name: set(channel_ids) }
guild_config = {}


# ---------------- PERMISSION CHECK ----------------
def setup_admin_only(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator


# ---------------- UI VIEW ----------------
class SetupView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180)
        self.bot = bot

    @discord.ui.select(
        placeholder="Select a command to configure",
        min_values=1,
        max_values=1,
        options=[]
    )
    async def select_command(self, interaction: discord.Interaction, select: discord.ui.Select):
        pass  # replaced dynamically below


# ---------------- COMMAND SELECT VIEW ----------------
class CommandSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot

        options = [
            discord.SelectOption(label=cmd.name, description=cmd.description or "No description")
            for cmd in bot.tree.get_commands()
        ]

        super().__init__(
            placeholder="Choose a command to restrict",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        command_name = self.values[0]

        await interaction.response.send_message(
            f"Now select allowed channels for `/ {command_name}`",
            view=ChannelSelectView(command_name),
            ephemeral=True
        )


class CommandSelectView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=180)
        self.add_item(CommandSelect(bot))


# ---------------- CHANNEL SELECT ----------------
class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, command_name: str):
        self.command_name = command_name

        super().__init__(
            placeholder="Select allowed channels",
            min_values=1,
            max_values=10,
            channel_types=[discord.ChannelType.text]
        )

    async def callback(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id

        guild_config.setdefault(guild_id, {})
        guild_config[guild_id][self.command_name] = {c.id for c in self.values}

        await interaction.response.send_message(
            f"✅ Updated `{self.command_name}` allowed channels.",
            ephemeral=True
        )


class ChannelSelectView(discord.ui.View):
    def __init__(self, command_name: str):
        super().__init__(timeout=180)
        self.add_item(ChannelSelect(command_name))


# ---------------- BOT SETUP COMMAND ----------------
class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configure bot command permissions")
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "❌ You must be a server administrator to use this.",
            ephemeral=True
        )

        embed = discord.Embed(
            title="Bot Setup Panel",
            description="Select a command to configure channel restrictions.",
            color=0x8A00C4
        )

        await interaction.response.send_message(
            embed=embed,
            view=CommandSelectView(self.bot),
            ephemeral=True
        )


# ---------------- PERMISSION CHECK FOR OTHER COMMANDS ----------------
def is_channel_allowed(command_name: str):
    async def predicate(interaction: discord.Interaction):
        guild_data = guild_config.get(interaction.guild.id, {})
        allowed = guild_data.get(command_name)

        if allowed is None:
            return True  # no restriction set

        return interaction.channel.id in allowed

    return app_commands.check(predicate)