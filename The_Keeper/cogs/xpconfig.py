import os
import asyncio
import gspread
import discord
from discord import app_commands
from discord.ext import commands

# -------------------- INITIAL PROMPT VIEW --------------------
class XPSetupPromptView(discord.ui.View):
    def __init__(self, cog, guild_id: str):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def initialize_guild():
            sheet = self.cog.get_sheet("guilds")
            rows = sheet.get_all_values()
            
            # Check if guild already exists
            exists = any(r and r[0] == self.guild_id for r in rows[1:])
            
            if not exists:
                # Layout: Guild ID, XP Per Msg, Level Up Msg En, Level Up Msg, Cooldown, Global XP
                default_row = [self.guild_id, "1", "False", "Congratulations {user}, you leveled up to {level}!", "5", "True"]
                sheet.append_row(default_row)

        # Provisions row on background thread
        await loop.run_in_executor(None, initialize_guild)

        embed = discord.Embed(
            title="📊 Multi-Guild XP Control Panel",
            description=(
                "Adjust metrics mapped directly to your spreadsheet setup.\n\n"
                "**⚙️ Core Settings** - Adjust basic rules, payouts, and cooldown structures.\n"
                "**🎭 Track Role** - Assign custom configurations directly to roles.\n"
                "**📈 Level Curve** - Set specific XP brackets for level progressions."
            ),
            color=discord.Color.brand_green()
        )
        # Forward to the primary Multi-Interaction Control Panel
        await interaction.followup.send(embed=embed, view=XPConfigWizard(self.cog, self.guild_id), ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ XP system setup cancelled.", embed=None, view=self)


# -------------------- THE MULTI-INTERACTION CONTROL WIZARD --------------------
class XPConfigWizard(discord.ui.View):
    def __init__(self, cog, guild_id: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="⚙️ Core Settings", style=discord.ButtonStyle.primary, row=0)
    async def core_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CoreSettingsModal(self.cog, self.guild_id))

    @discord.ui.button(label="🎭 Track Role", style=discord.ButtonStyle.secondary, row=0)
    async def role_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        view = discord.ui.View()
        view.add_item(RoleSelectMenu(self.cog, self.guild_id))
        await interaction.followup.send("Select a role to configure parameters:", view=view, ephemeral=True)

    @discord.ui.button(label="📈 Level Curve", style=discord.ButtonStyle.secondary, row=0)
    async def level_curve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LevelCurveModal(self.cog, self.guild_id))


# -------------------- CONFIG MODALS & COMPONENTS --------------------
class CoreSettingsModal(discord.ui.Modal, title="Configure Core XP Settings"):
    per_message = discord.ui.TextInput(label="XP Per Message", default="1", max_length=3)
    cooldown = discord.ui.TextInput(label="Cooldown (Seconds)", default="5", max_length=3)
    global_xp = discord.ui.TextInput(label="Enable Global XP? (True/False)", default="True", max_length=5)

    def __init__(self, cog, guild_id: str):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def save_core():
            sheet = self.cog.get_sheet("guilds")
            rows = sheet.get_all_values()
            
            target_row = next((i for i, r in enumerate(rows[1:], start=2) if r and r[0] == self.guild_id), None)
            
            # Maintain index structural data columns (2 and 3) if they already exist
            existing_msg_en = rows[target_row - 1][2] if target_row and len(rows[target_row - 1]) > 2 else "False"
            existing_msg = rows[target_row - 1][3] if target_row and len(rows[target_row - 1]) > 3 else ""

            new_row = [
                self.guild_id, 
                self.per_message.value, 
                existing_msg_en, 
                existing_msg, 
                self.cooldown.value, 
                self.global_xp.value.strip().capitalize()
            ]

            if target_row:
                sheet.update(range_name=f"A{target_row}:F{target_row}", values=[new_row])
            else:
                sheet.append_row(new_row)

        await loop.run_in_executor(None, save_core)
        await interaction.followup.send("✅ Core server configuration updated successfully!", ephemeral=True)


class LevelCurveModal(discord.ui.Modal, title="Configure Level Thresholds"):
    level = discord.ui.TextInput(label="Target Level", placeholder="e.g. 5")
    xp_required = discord.ui.TextInput(label="Total XP Required", placeholder="e.g. 500")

    def __init__(self, cog, guild_id: str):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def save_curve():
            sheet = self.cog.get_sheet("level_xp")
            rows = sheet.get_all_values()
            
            # Composite Match: Guild ID + Target Level
            target_row = next((i for i, r in enumerate(rows[1:], start=2) if r and r[0] == self.guild_id and r[1] == self.level.value), None)
            new_row = [self.guild_id, self.level.value, self.xp_required.value]
            
            if target_row:
                sheet.update(range_name=f"A{target_row}:C{target_row}", values=[new_row])
            else:
                sheet.append_row(new_row)

        await loop.run_in_executor(None, save_curve)
        await interaction.followup.send(f"✅ Level **{self.level.value}** curve set to **{self.xp_required.value} XP**!", ephemeral=True)


class RoleSelectMenu(discord.ui.RoleSelect):
    def __init__(self, cog, guild_id: str):
        super().__init__(placeholder="Choose a server role to configure...", min_values=1, max_values=1)
        self.cog = cog
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(RoleConfigModal(self.cog, self.guild_id, self.values[0]))


class RoleConfigModal(discord.ui.Modal):
    def __init__(self, cog, guild_id: str, role: discord.Role):
        super().__init__(title=f"Setup Tracks: {role.name[:20]}")
        self.cog = cog
        self.guild_id = guild_id
        self.role = role
        self.office_chan = discord.ui.TextInput(label="Office Channel ID (Optional)", required=False)
        self.add_item(self.office_chan)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def save_role():
            sheet = self.cog.get_sheet("server_roles")
            rows = sheet.get_all_values()
            
            # Composite Match: Guild ID + Role ID
            target_row = next((i for i, r in enumerate(rows[1:], start=2) if r and r[0] == self.guild_id and r[2] == str(self.role.id)), None)
            new_row = [self.guild_id, self.role.name, str(self.role.id), "", "", self.office_chan.value or ""]
            
            if target_row:
                sheet.update(range_name=f"A{target_row}:F{target_row}", values=[new_row])
            else:
                sheet.append_row(new_row)

        await loop.run_in_executor(None, save_role)
        await interaction.followup.send(f"✅ Configuration tracks saved for role: **{self.role.name}**", ephemeral=True)


# -------------------- MAIN COG & TRACKING LOGIC --------------------
class XPConfigCog(commands.Cog, name="xp"):
    def __init__(self, bot):
        self.bot = bot
        self.gc = None
        self.spreadsheet = None

    def get_sheet(self, tab_name: str):
        if not self.spreadsheet:
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/app/creds.json")
            self.gc = gspread.service_account(filename=creds_path, scopes=scopes)
            self.spreadsheet = self.gc.open_by_key("1nZFbIIZruXyrSBjy93ubHudVkV4xu2_pdatIwVd0YsU")
        try:
            return self.spreadsheet.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=tab_name, rows="500", cols="20")

    @app_commands.command(name="xp", description="Open the multi-interaction server XP configuration control panel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_dashboard(self, interaction: discord.Interaction):
        # Fire initial starter onboarding greeting sequence instead of loading dashboard layout directly
        await interaction.response.send_message(
            content="Would you like to set up an XP system for this server?", 
            view=XPSetupPromptView(self, str(interaction.guild_id)), 
            ephemeral=True
        )
    
    # ------------------ LIVE SPREADSHEET PROGRESSION DATA ENGINE ------------------
    async def add_spreadsheet_xp(self, guild_id: str, user_id: str, role_id: str, amount: int):
        """Adds xp to the user_roles worksheet for a specific guild context."""
        loop = asyncio.get_running_loop()

        def process():
            curve_sheet = self.get_sheet("level_xp")
            curves = {r[1]: int(r[2]) for r in curve_sheet.get_all_values()[1:] if r and r[0] == guild_id}
            max_level = max([int(lvl) for lvl in curves.keys()]) if curves else 10
            
            role_track_sheet = self.get_sheet("user_roles")
            all_records = role_track_sheet.get_all_values()
            
            target_row = None
            xp, level = 0, 1
            
            for i, r in enumerate(all_records[1:], start=2):
                if r and r[0] == guild_id and r[1] == user_id and r[2] == role_id:
                    target_row = i
                    xp, level = int(r[3]), int(r[4])
                    break
            
            xp += amount
            leveled_up = False
            
            while level < max_level:
                needed = curves.get(str(level), 100) 
                if xp < needed:
                    break
                xp -= needed
                level += 1
                leveled_up = True
            
            new_data = [guild_id, user_id, role_id, str(xp), str(level)]
            if target_row:
                role_track_sheet.update(range_name=f"A{target_row}:E{target_row}", values=[new_data])
            else:
                role_track_sheet.append_row(new_data)
                
            return xp, level, leveled_up

        return await loop.run_in_executor(None, process)

async def setup(bot: commands.Bot):
    await bot.add_cog(XPConfigCog(bot))
