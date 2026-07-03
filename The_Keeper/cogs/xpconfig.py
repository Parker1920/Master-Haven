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

        def initialize_or_update_guild():
            sheet = self.cog.get_sheet("guilds")
            rows = sheet.get_all_values()
            
            # Look up if an entry for this server already exists
            target_row = next((i for i, r in enumerate(rows[1:], start=2) if r and r[0] == self.guild_id), None)
            
            if target_row:
                # Keep previously saved configurations intact while safely refreshing the entry
                existing_xp_per_msg = rows[target_row - 1][1] if len(rows[target_row - 1]) > 1 else "1"
                existing_msg_en = rows[target_row - 1][2] if len(rows[target_row - 1]) > 2 else "False"
                existing_msg = rows[target_row - 1][3] if len(rows[target_row - 1]) > 3 else "Congratulations {user}, you leveled up to {level}!"
                existing_cooldown = rows[target_row - 1][4] if len(rows[target_row - 1]) > 4 else "5"
                existing_global = rows[target_row - 1][5] if len(rows[target_row - 1]) > 5 else "True"
                
                updated_row = [self.guild_id, existing_xp_per_msg, existing_msg_en, existing_msg, existing_cooldown, existing_global]
                sheet.update(range_name=f"A{target_row}:F{target_row}", values=[updated_row])
            else:
                # Default configuration mapping layout for new guilds
                default_row = [self.guild_id, "1", "False", "Congratulations {user}, you leveled up to {level}!", "5", "True"]
                sheet.append_row(default_row)

        # Runs the sheet transaction in an executor to keep the gateway completely unblocked
        await loop.run_in_executor(None, initialize_or_update_guild)

        embed = discord.Embed(
            title="📊 Multi-Guild XP Control Panel",
            description=(
                "Adjust metrics mapped directly to your spreadsheet setup.\n\n"
                "**⚙️ Core Settings** - Adjust basic rules, payouts, and cooldown structures.\n"
                "**🚀 Quick Level Setup** - Initialize multiple custom levels and XP tiers at once.\n"
                "**🎭 Track Role** - Assign custom configurations directly to roles.\n"
                "**📈 Level Curve** - Set specific individual XP brackets for level progressions."
            ),
            color=discord.Color.brand_green()
        )
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

    @discord.ui.button(label="🚀 Quick Level Setup", style=discord.ButtonStyle.success, row=0)
    async def quick_level_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LevelOnboardingModal(self.cog, self.guild_id))

    @discord.ui.button(label="🎭 Track Role", style=discord.ButtonStyle.secondary, row=1)
    async def role_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        view = discord.ui.View()
        view.add_item(RoleSelectMenu(self.cog, self.guild_id))
        await interaction.followup.send("Select a role to configure parameters:", view=view, ephemeral=True)

    @discord.ui.button(label="📈 Level Curve", style=discord.ButtonStyle.secondary, row=1)
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
        
        guild = interaction.guild
        member_ids = []
        if guild:
            member_ids = [str(member.id) for member in guild.members if not member.bot]

        loop = asyncio.get_running_loop()

        def save_core_and_sync_users():
            # 1. Update Core Guild Settings
            guild_sheet = self.cog.get_sheet("guilds")
            g_rows = guild_sheet.get_all_values()
            
            target_row = next((i for i, r in enumerate(g_rows[1:], start=2) if r and r[0] == self.guild_id), None)
            
            existing_msg_en = g_rows[target_row - 1][2] if target_row and len(g_rows[target_row - 1]) > 2 else "False"
            existing_msg = g_rows[target_row - 1][3] if target_row and len(g_rows[target_row - 1]) > 3 else ""

            new_row = [
                self.guild_id, 
                self.per_message.value, 
                existing_msg_en, 
                existing_msg, 
                self.cooldown.value, 
                self.global_xp.value.strip().capitalize()
            ]

            if target_row:
                guild_sheet.update(range_name=f"A{target_row}:F{target_row}", values=[new_row])
            else:
                guild_sheet.append_row(new_row)

            # 2. Fallback Sync: If no server roles are defined, initialize members on a global base track
            role_sheet = self.cog.get_sheet("server_roles")
            r_rows = role_sheet.get_all_values()
            has_roles = any(r and r[0] == self.guild_id for r in r_rows[1:])

            if not has_roles:
                user_sheet = self.cog.get_sheet("user_roles")
                u_rows = user_sheet.get_all_values()
                existing_users = {r[1] for r in u_rows[1:] if r and r[0] == self.guild_id}
                
                new_user_rows = []
                for m_id in member_ids:
                    if m_id not in existing_users:
                        new_user_rows.append([self.guild_id, m_id, "GLOBAL", "0", "1"])
                
                if new_user_rows:
                    user_sheet.append_rows(new_user_rows)

        await loop.run_in_executor(None, save_core_and_sync_users)
        await interaction.followup.send("✅ Core settings updated and synchronized successfully!", ephemeral=True)


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
            
            target_row = next((i for i, r in enumerate(rows[1:], start=2) if r and r[0] == self.guild_id and r[2] == str(self.role.id)), None)
            new_row = [self.guild_id, self.role.name, str(self.role.id), "", "", self.office_chan.value or ""]
            
            if target_row:
                sheet.update(range_name=f"A{target_row}:F{target_row}", values=[new_row])
            else:
                sheet.append_row(new_row)

        await loop.run_in_executor(None, save_role)
        await interaction.followup.send(f"✅ Configuration tracks saved for role: **{self.role.name}**", ephemeral=True)


class LevelOnboardingModal(discord.ui.Modal, title="Bulk Level Setup Wizard"):
    num_levels = discord.ui.TextInput(label="Number of Levels", placeholder="e.g., 5", max_length=2)
    level_names = discord.ui.TextInput(
        label="Level Names (separate by comma)", 
        placeholder="Bronze, Silver, Gold, Platinum, Diamond", 
        style=discord.TextStyle.paragraph
    )
    xp_per_level = discord.ui.TextInput(label="XP Required Per Level", placeholder="e.g., 500", max_length=5)
    level_up_msg = discord.ui.TextInput(
        label="Level Up Message (Optional)", 
        default="Congratulations {user}, you leveled up to {level}!", 
        required=False,
        style=discord.TextStyle.paragraph
    )

    def __init__(self, cog, guild_id: str):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        try:
            total_levels = int(self.num_levels.value.strip())
            base_xp = int(self.xp_per_level.value.strip())
        except ValueError:
            await interaction.followup.send("❌ Error: Number of levels and XP must be integers!", ephemeral=True)
            return

        names_list = [name.strip() for name in self.level_names.value.split(",") if name.strip()]
        while len(names_list) < total_levels:
            names_list.append(f"Level {len(names_list) + 1}")

        def save_bulk_levels():
            curve_sheet = self.cog.get_sheet("level_xp")
            existing_curves = curve_sheet.get_all_values()
            
            if self.level_up_msg.value:
                guild_sheet = self.cog.get_sheet("guilds")
                g_rows = guild_sheet.get_all_values()
                g_target = next((i for i, r in enumerate(g_rows[1:], start=2) if r and r[0] == self.guild_id), None)
                if g_target:
                    guild_sheet.update_cell(g_target, 3, "True")
                    guild_sheet.update_cell(g_target, 4, self.level_up_msg.value)

            for level_idx in range(1, total_levels + 1):
                level_str = str(level_idx)
                level_name = names_list[level_idx - 1]
                calculated_xp = str(base_xp * level_idx) 

                target_row = next((i for i, r in enumerate(existing_curves[1:], start=2) if r and r[0] == self.guild_id and r[1] == level_str), None)
                new_row = [self.guild_id, level_str, calculated_xp, level_name]

                if target_row:
                    curve_sheet.update(range_name=f"A{target_row}:D{target_row}", values=[new_row])
                else:
                    curve_sheet.append_row(new_row)

        await loop.run_in_executor(None, save_bulk_levels)
        await interaction.followup.send(f"✅ Successfully initialized **{total_levels}** custom layout levels in your sheet system!", ephemeral=True)


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
        await interaction.response.send_message(
            content="Would you like to set up an XP system for this server?", 
            view=XPSetupPromptView(self, str(interaction.guild_id)), 
            ephemeral=True
        )
        
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

    # ------------------ STRUCTURAL SHEETS MAINTENANCE ENGINE ------------------
    @commands.command(name="update")
    @commands.has_permissions(manage_guild=True)
    async def force_sheets_update(self, ctx: commands.Context):
        """Classic prefix command to verify, fix, and update all database schema tables."""
        await ctx.send("🔄 *Validating spreadsheet architecture and table tabs...*")
        loop = asyncio.get_running_loop()

        def sync_schema():
            required_tables = {
                "guilds": ["Guild ID", "XP Per Msg", "Msg Enabled", "Msg Text", "Cooldown", "Global XP"],
                "level_xp": ["Guild ID", "Level Num", "XP Required", "Level Name"],
                "server_roles": ["Guild ID", "Role Name", "Role ID", "Unused1", "Unused2", "Office Channel ID"],
                "user_roles": ["Guild ID", "User ID", "Role ID", "Current XP", "Current Level"]
            }
            
            self.get_sheet("guilds") 
            
            created_tabs = []
            fixed_headers = []

            for tab_name, headers in required_tables.items():
                try:
                    work_sheet = self.spreadsheet.worksheet(tab_name)
                    existing_values = work_sheet.get_all_values()
                    if not existing_values or not existing_values[0]:
                        work_sheet.update(range_name="A1", values=[headers])
                        fixed_headers.append(tab_name)
                except gspread.exceptions.WorksheetNotFound:
                    new_sheet = self.spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="20")
                    new_sheet.update(range_name="A1", values=[headers])
                    created_tabs.append(tab_name)
            
            return created_tabs, fixed_headers

        created, fixed = await loop.run_in_executor(None, sync_schema)

        status_report = "📊 **Spreadsheet Synchronization Complete!**\n"
        if not created and not fixed:
            status_report += "✅ All required worksheets and column headers are valid and online."
        else:
            if created:
                status_report += f"🛠️ **Created missing tabs:** {', '.join([f'`{c}`' for c in created])}\n"
            if fixed:
                status_report += f"📝 **Injected missing header columns into:** {', '.join([f'`{f}`' for f in fixed])}\n"
            status_report += "🚀 System is ready."

        await ctx.send(status_report)


async def setup(bot: commands.Bot):
    await bot.add_cog(XPConfigCog(bot))
