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
            
            # Retain potential channel mapping column index if editing
            existing_channel = rows[target_row - 1][4] if target_row and len(rows[target_row - 1]) > 4 else ""
            existing_name = rows[target_row - 1][3] if target_row and len(rows[target_row - 1]) > 3 else f"Level {self.level.value}"
            
            new_row = [self.guild_id, self.level.value, self.xp_required.value, existing_name, existing_channel]
            
            if target_row:
                sheet.update(range_name=f"A{target_row}:E{target_row}", values=[new_row])
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


# -------------------- BULK ONBOARDING & CHANNELS MAPPING INTERACTION --------------------
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
                
                existing_chan = existing_curves[target_row - 1][4] if target_row and len(existing_curves[target_row - 1]) > 4 else ""
                new_row = [self.guild_id, level_str, calculated_xp, level_name, existing_chan]

                if target_row:
                    curve_sheet.update(range_name=f"A{target_row}:E{target_row}", values=[new_row])
                else:
                    curve_sheet.append_row(new_row)

        await loop.run_in_executor(None, save_bulk_levels)
        
        prompt_view = LevelUpChannelPromptView(self.cog, self.guild_id, total_levels)
        await interaction.followup.send(
            content=f"✅ Successfully initialized **{total_levels}** custom layout levels in your system!\n\n**Would you like to add a level up channel?**",
            view=prompt_view,
            ephemeral=True
        )


class LevelUpChannelPromptView(discord.ui.View):
    def __init__(self, cog, guild_id: str, total_levels: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id
        self.total_levels = total_levels

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def choice_yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LevelUpChannelModal(self.cog, self.guild_id, self.total_levels))

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def choice_no(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="ℹ️ Core setup finalized without setting a dedicated level up channel.", view=self)


class LevelUpChannelModal(discord.ui.Modal, title="Configure Level Up Channel"):
    channel_input = discord.ui.TextInput(
        label="Channel Name, ID, or Mention", 
        placeholder="e.g., #level-ups or 123456789012345678"
    )

    def __init__(self, cog, guild_id: str, total_levels: int):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id
        self.total_levels = total_levels

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        raw_input = self.channel_input.value.strip()
        
        clean_input = raw_input.replace("<#", "").replace(">", "")
        resolved_channel = None
        
        if interaction.guild:
            if clean_input.isdigit():
                resolved_channel = interaction.guild.get_channel(int(clean_input))
            if not resolved_channel:
                resolved_channel = discord.utils.get(interaction.guild.text_channels, name=clean_input)

        if not resolved_channel:
            await interaction.followup.send(f"⚠️ Could not verify channel `{raw_input}` inside this server. Saving raw text input value directly.", ephemeral=True)
            channel_id_str = raw_input
        else:
            channel_id_str = str(resolved_channel.id)

        loop = asyncio.get_running_loop()

        def update_channel_in_sheets():
            sheet = self.cog.get_sheet("level_xp")
            rows = sheet.get_all_values()
            
            for idx in range(1, self.total_levels + 1):
                level_str = str(idx)
                target_row = next((i for i, r in enumerate(rows[1:], start=2) if r and r[0] == self.guild_id and r[1] == level_str), None)
                
                if target_row:
                    sheet.update_cell(target_row, 5, channel_id_str)

        await loop.run_in_executor(None, update_channel_in_sheets)
        display_name = resolved_channel.mention if resolved_channel else f"`{channel_id_str}`"
        await interaction.followup.send(f"✅ Successfully linked level up messages to {display_name} across onboarding layout tracks!", ephemeral=True)


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

class CustomTrackerPromptView(discord.ui.View):
    def __init__(self, cog, guild_id: str):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Admin chose to configure custom colors/titles
        await interaction.response.send_modal(CustomLayoutModal(self.cog, self.guild_id))

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Admin chose standard default options, record "False" to bypass future prompts
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def set_standard_fallback():
            sheet = self.cog.get_sheet("guilds")
            rows = sheet.get_all_values()
            target_row = next((i for i, r in enumerate(rows[1:], start=2) if r and r[0] == self.guild_id), None)
            
            if target_row:
                # Fill up to index 6 with 'False' to indicate custom is disabled
                while len(rows[target_row - 1]) < 6:
                    rows[target_row - 1].append("")
                sheet.update_cell(target_row, 7, "False")

        await loop.run_in_executor(None, set_standard_fallback)
        await interaction.followup.send("✅ System configured to use the default embedded tracking profile theme layout.", ephemeral=True)


class CustomLayoutModal(discord.ui.Modal, title="Customize Level Embed Theme"):
    embed_title = discord.ui.TextInput(
        label="Embed Title Template", 
        default="✨ {name}'s Level Progress",
        placeholder="Variables allowed: {name} and {level}"
    )
    border_color = discord.ui.TextInput(
        label="Embed Border Color (Hex Code or Name)", 
        default="#99cc00", 
        placeholder="e.g., #ff0055, gold, blue, blurple"
    )
    filled_bar = discord.ui.TextInput(
        label="Filled Progress Bar Emoji", 
        default="🟩", 
        max_length=2, 
        placeholder="Paste a single emoji icon character"
    )
    empty_bar = discord.ui.TextInput(
        label="Empty Progress Bar Emoji", 
        default="⬛", 
        max_length=2, 
        placeholder="Paste a single emoji icon character"
    )

    def __init__(self, cog, guild_id: str):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def save_custom_design_specs():
            sheet = self.cog.get_sheet("guilds")
            rows = sheet.get_all_values()
            target_row = next((i for i, r in enumerate(rows[1:], start=2) if r and r[0] == self.guild_id), None)

            if target_row:
                current_row_data = rows[target_row - 1]
                while len(current_row_data) < 6:
                    current_row_data.append("")
                
                base_info = current_row_data[:6]
                updated_row = base_info + [
                    "True", 
                    self.embed_title.value.strip(), 
                    self.border_color.value.strip(), 
                    self.filled_bar.value.strip(), 
                    self.empty_bar.value.strip()
                ]
                sheet.update(range_name=f"A{target_row}:K{target_row}", values=[updated_row])

        await loop.run_in_executor(None, save_custom_design_specs)
        await interaction.followup.send(" Custom theme configuration saved successfully! Run `!level` again to see it.", ephemeral=True)

    # ------------------ STRUCTURAL SHEETS MAINTENANCE ENGINE ------------------
    @commands.command(name="update")
    @commands.has_permissions(manage_guild=True)
    async def force_sheets_update(self, ctx: commands.Context):
        """Classic prefix command to verify, fix, and update all database schema tables."""
        await ctx.send("🔄 *Validating spreadsheet architecture and table tabs...*")
        loop = asyncio.get_running_loop()

        def sync_schema():
            required_tables = {
                "guilds": [
    "Guild ID", "XP Per Msg", "Msg Enabled", "Msg Text", "Cooldown", "Global XP", 
    "Custom Layout Enabled", "Embed Title", "Border Hex Color", "Filled Bar Emoji", "Empty Bar Emoji"
],
                "level_xp": ["Guild ID", "Level Num", "XP Required", "Level Name", "Level Up Channel ID"],
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
                    else:
                        current_headers = existing_values[0]
                        if len(current_headers) < len(headers):
                            work_sheet.update(range_name="A1", values=[headers])
                            fixed_headers.append(f"{tab_name} (Updated Schema Columns)")
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
            status_report += "🚀 System architecture updated successfully."

        await ctx.send(status_report)

        @commands.command(name="level")
        async def show_level(self, ctx: commands.Context, member: discord.Member = None):
            """Displays the user's current level, XP, and customizable progress bar."""
            member = member or ctx.author
            if member.bot:
                await ctx.send("🤖 Bots don't have XP levels!")
                return
    
            guild_id = str(ctx.guild.id)
            user_id = str(member.id)
            await ctx.trigger_typing()
            
            loop = asyncio.get_running_loop()
    
            def fetch_guild_and_user_data():
                g_sheet = self.get_sheet("guilds")
                g_rows = g_sheet.get_all_values()
                g_row = next((r for r in g_rows[1:] if r and r[0] == guild_id), None)
                
                custom_enabled = g_row[6] == "True" if g_row and len(g_row) > 6 else False
                embed_title = g_row[7] if g_row and len(g_row) > 7 and g_row[7] else "✨ {name}'s Level Progress"
                border_hex = g_row[8] if g_row and len(g_row) > 8 and g_row[8] else "purple"
                filled_emoji = g_row[9] if g_row and len(g_row) > 9 and g_row[9] else "🟩"
                empty_emoji = g_row[10] if g_row and len(g_row) > 10 and g_row[10] else "⬛"
    
                is_first_use = g_row is None or len(g_row) <= 6 or g_row[6] == ""
    
                user_sheet = self.get_sheet("user_roles")
                user_records = user_sheet.get_all_values()
                user_row = next((r for r in user_records[1:] if r and r[0] == guild_id and r[1] == user_id), None)
                
                current_xp = int(user_row[3]) if user_row and len(user_row) > 3 else 0
                current_level = int(user_row[4]) if user_row and len(user_row) > 4 else 1
                
                curve_sheet = self.get_sheet("level_xp")
                curves = {r[1]: int(r[2]) for r in curve_sheet.get_all_values()[1:] if r and r[0] == guild_id}
                xp_needed_for_next = curves.get(str(current_level), 100)
    
                return is_first_use, custom_enabled, embed_title, border_hex, filled_emoji, empty_emoji, current_xp, current_level, xp_needed_for_next
    
            (is_first_use, custom_enabled, embed_title, border_hex, 
             filled_emoji, empty_emoji, current_xp, current_level, xp_needed_for_next) = await loop.run_in_executor(None, fetch_guild_and_user_data)
    
            if is_first_use:
                if not ctx.author.guild_permissions.manage_guild:
                    await ctx.send("This server's level tracker layout hasn't been configured by an Administrator yet.")
                    return
                    
                prompt_view = CustomTrackerPromptView(self, guild_id)
                await ctx.send(
                    "**First Use Detected!** Would you like to set up a custom layout for your server's level embeds?", 
                    view=prompt_view
                )
                return
    
            if xp_needed_for_next <= 0:
                xp_needed_for_next = 100
            progress_ratio = min(current_xp / xp_needed_for_next, 1.0)
            
            bar_length = 10
            filled_blocks = int(progress_ratio * bar_length)
            empty_blocks = bar_length - filled_blocks
            progress_bar = (filled_emoji * filled_blocks) + (empty_emoji * empty_blocks)
            percentage = int(progress_ratio * 100)
    
            embed_color = discord.Color.purple()
            if custom_enabled:
                try:
                    if border_hex.startswith("#"):
                        embed_color = discord.Color.from_str(border_hex)
                    else:
                        embed_color = getattr(discord.Color, border_hex.lower())()
                except Exception:
                    embed_color = discord.Color.purple()
    
            formatted_title = embed_title.replace("{name}", member.display_name).replace("{level}", str(current_level))
    
            embed = discord.Embed(title=formatted_title, color=embed_color)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name=" Level", value=f"`{current_level}`", inline=True)
            embed.add_field(name=" Experience", value=f"`{current_xp} / {xp_needed_for_next} XP`", inline=True)
            embed.add_field(name=f" Progress to Level {current_level + 1} ({percentage}%)", value=progress_bar, inline=False)
            embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
            await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(XPConfigCog(bot))
