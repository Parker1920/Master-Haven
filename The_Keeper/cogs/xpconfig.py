import os
import asyncio
import gspread
import discord
from discord import app_commands
from discord.ext import commands

# -------------------- INITIAL PROMPT VIEW --------------------
class XPSetupPromptView(discord.ui.View):
    def __init__(self, cog, guild_id: str, exists: bool = False):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id
        
        if exists:
            self.confirm.label = "Update Settings"
            self.confirm.style = discord.ButtonStyle.primary

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def initialize_or_update_guild():
            sheet = self.cog.get_guild_tab(self.guild_id)
            rows = sheet.get_all_values()
            
            # If configuration row 2 elements are blank, inject standard defaults
            if len(rows) < 2 or len(rows[1]) < 7 or rows[1][6] == "":
                config_defaults = [
                    "", "", "", "", "", "",                               # Pad Columns A-F
                    "1",                                                   # G: XP Per Msg
                    "True",                                                # H: Msg Enabled
                    "Congratulations {user}, you leveled up to {level}!",  # I: Msg Text
                    "5",                                                   # J: Cooldown Sec
                    "True",                                                # K: Global Track Enabled
                    "False",                                               # L: Custom Theme Enabled
                    "✨ {name}'s Level Progress",                           # M: Embed Title Template
                    "#99cc00",                                             # N: Border Hex Color
                    "🟩",                                                  # O: Filled Bar Emoji
                    "⬛",                                                  # P: Empty Bar Emoji
                    "10",                                                  # Q: Max Level Tiers
                    "100,200,300,400,500,600,700,800,900,1000",            # R: Custom XP brackets list
                    "Level 1,Level 2,Level 3,Level 4,Level 5,Level 6,Level 7,Level 8,Level 9,Level 10" # S: Level Names
                ]
                sheet.update(range_name="A2:S2", values=[config_defaults])

        await loop.run_in_executor(None, initialize_or_update_guild)

        embed = discord.Embed(
            title="🎯 Dedicated Server Dashboard",
            description=(
                f"This guild's database environment is completely locked to Sheet Tab: `{self.guild_id}`.\n\n"
                "**⚙️ Core Settings** — Change XP payout numbers, chat cooldown rules, and level alerts.\n"
                "**🚀 Quick Level Setup** — Configuration for bulk milestone thresholds and custom tier titles.\n"
                "**🎨 Customize Layout** — Set structural hex card colors, bar assets, and text naming templates."
            ),
            color=discord.Color.brand_green()
        )
        await interaction.followup.send(embed=embed, view=XPConfigWizard(self.cog, self.guild_id), ephemeral=True)

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="❌ Database setup adjustment cancelled.", embed=None, view=self)


# -------------------- SYSTEM CONFIGURATION CONTROL PANEL --------------------
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

    @discord.ui.button(label="🎨 Customize Layout", style=discord.ButtonStyle.success, row=0)
    async def customize_layout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomLayoutModal(self.cog, self.guild_id))


# -------------------- INPUT CAPTURE FORMS --------------------
class CoreSettingsModal(discord.ui.Modal, title="Configure Core XP Parameters"):
    per_message = discord.ui.TextInput(label="XP Per Message Awarded", default="1", max_length=3)
    cooldown = discord.ui.TextInput(label="Chat Cooldown (Seconds)", default="5", max_length=3)
    msg_enabled = discord.ui.TextInput(label="Enable Level Announcements? (True/False)", default="True", max_length=5)
    level_up_msg = discord.ui.TextInput(label="Level Up Notification Template", default="Congratulations {user}, you leveled up to {level}!", style=discord.TextStyle.paragraph)

    def __init__(self, cog, guild_id: str):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def save_core():
            sheet = self.cog.get_guild_tab(self.guild_id)
            sheet.update(range_name="G2:K2", values=[[
                self.per_message.value.strip(),
                self.msg_enabled.value.strip().capitalize(),
                self.level_up_msg.value,
                self.cooldown.value.strip(),
                "True"
            ]])

        await loop.run_in_executor(None, save_core)
        await interaction.followup.send("✅ Server runtime mechanics written successfully to Row 2!", ephemeral=True)


class LevelOnboardingModal(discord.ui.Modal, title="Bulk Level Setup Wizard"):
    num_levels = discord.ui.TextInput(label="Number of Levels", placeholder="e.g., 5", max_length=2)
    level_names = discord.ui.TextInput(
        label="Level Names (separate by comma)", 
        placeholder="Bronze, Silver, Gold, Platinum, Diamond", 
        style=discord.TextStyle.paragraph
    )
    xp_per_level = discord.ui.TextInput(label="XP Required Per Level", placeholder="e.g., 500", max_length=5)

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
            await interaction.followup.send("❌ Error: Number of levels and XP must be valid numbers!", ephemeral=True)
            return

        # Clean individual name items from comma split array
        names_list = [name.strip() for name in self.level_names.value.split(",") if name.strip()]
        while len(names_list) < total_levels:
            names_list.append(f"Level {len(names_list) + 1}")
        names_list = names_list[:total_levels]

        # Generate linear progression multiplier thresholds
        brackets_list = [str(base_xp * idx) for idx in range(1, total_levels + 1)]

        # Consolidate back into clean strings to fill exactly inside columns Q, R, and S
        final_max_tiers = str(total_levels)
        final_brackets = ",".join(brackets_list)
        final_names = ",".join(names_list)

        def save_bulk_levels():
            sheet = self.cog.get_guild_tab(self.guild_id)
            sheet.update(range_name="Q2:S2", values=[[final_max_tiers, final_brackets, final_names]])

        await loop.run_in_executor(None, save_bulk_levels)
        await interaction.followup.send(f"🚀 Successfully initialized **{total_levels}** tiers! Configurations saved into Row 2 (Columns Q, R, S).", ephemeral=True)


class CustomLayoutModal(discord.ui.Modal, title="Customize Card UI Styles"):
    embed_title = discord.ui.TextInput(label="Card UI Title Pattern", default="✨ {name}'s Level Progress")
    border_color = discord.ui.TextInput(label="Embed Border Color (Hex Code / Color Name)", default="#99cc00")
    filled_bar = discord.ui.TextInput(label="Filled Progression Block Emoji", default="🟩")
    empty_bar = discord.ui.TextInput(label="Empty Progression Block Emoji", default="⬛")

    def __init__(self, cog, guild_id: str):
        super().__init__()
        self.cog = cog
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        loop = asyncio.get_running_loop()

        def save_layout():
            sheet = self.cog.get_guild_tab(self.guild_id)
            sheet.update(range_name="L2:P2", values=[[
                "True",
                self.embed_title.value.strip(),
                self.border_color.value.strip(),
                self.filled_bar.value.strip(),
                self.empty_bar.value.strip()
            ]])

        await loop.run_in_executor(None, save_layout)
        await interaction.followup.send("✨ Theme layout assets updated successfully inside row 2!", ephemeral=True)


# -------------------- MAIN COG LOGIC & ROUTING ENGINE --------------------
class XPConfigCog(commands.Cog, name="xp"):
    def __init__(self, bot):
        self.bot = bot
        self.gc = None
        self.spreadsheet = None

    def get_guild_tab(self, guild_id: str):
        """Fetches or builds a designated, isolated sheet workspace for a specific server."""
        if not self.spreadsheet:
            scopes = ["https://www.googleapis.com/auth/spreadsheets"]
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/app/creds.json")
            self.gc = gspread.service_account(filename=creds_path, scopes=scopes)
            self.spreadsheet = self.gc.open_by_key("1nZFbIIZruXyrSBjy93ubHudVkV4xu2_pdatIwVd0YsU")
        try:
            return self.spreadsheet.worksheet(guild_id)
        except gspread.exceptions.WorksheetNotFound:
            new_tab = self.spreadsheet.add_worksheet(title=guild_id, rows="1000", cols="20")
            headers = [
                "User ID", "XP Track", "Current XP", "Level", "Last Msg Timestamp", "", 
                "XP Per Msg", "Msg Enabled", "Msg Text", "Cooldown Sec", "Global Track Enabled",
                "Custom Theme Enabled", "Embed Title Template", "Border Hex Color", "Filled Bar Emoji", "Empty Bar Emoji",
                "Level Curve Max Total Tiers", "Level Curve Brackets", "Level Names List"
            ]
            new_tab.update(range_name="A1:S1", values=[headers])
            return new_tab

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        now = asyncio.get_running_loop().time()

        loop = asyncio.get_running_loop()
        sheet = await loop.run_in_executor(None, self.get_guild_tab, guild_id)
        rows = await loop.run_in_executor(None, sheet.get_all_values)
        
        if len(rows) < 2 or len(rows[1]) < 10 or rows[1][6] == "":
            return 

        config_row = rows[1]
        xp_per_msg = int(config_row[6]) if config_row[6].isdigit() else 1
        msg_enabled = config_row[7] == "True"
        lvl_up_template = config_row[8] if config_row[8] else "Congratulations {user}, you leveled up to {level}!"
        cooldown_sec = float(config_row[9]) if config_row[9].replace('.', '', 1).isdigit() else 5.0
        
        max_level = int(config_row[16]) if len(config_row) > 16 and config_row[16].isdigit() else 10
        raw_curves = config_row[17] if len(config_row) > 17 and config_row[17] else ""
        
        curves = {}
        if raw_curves:
            split_brackets = [x.strip() for x in raw_curves.split(",") if x.strip().isdigit()]
            for lvl_idx, xp_val in enumerate(split_brackets, start=1):
                curves[str(lvl_idx)] = int(xp_val)
                
        user_row_idx = None
        current_xp, current_level, last_timestamp = 0, 1, 0.0

        for idx, row in enumerate(rows[1:], start=2):
            if row and row[0] == user_id:
                user_row_idx = idx
                current_xp = int(row[2]) if len(row) > 2 and row[2].isdigit() else 0
                current_level = int(row[3]) if len(row) > 3 and row[3].isdigit() else 1
                last_timestamp = float(row[4]) if len(row) > 4 and row[4].replace('.','',1).isdigit() else 0.0
                break

        if now - last_timestamp < cooldown_sec:
            return

        current_xp += xp_per_msg
        leveled_up = False

        while current_level < max_level:
            xp_needed = curves.get(str(current_level), 100)
            if current_xp < xp_needed:
                break
            current_xp -= xp_needed
            current_level += 1
            leveled_up = True

        user_payload = [user_id, "GLOBAL", str(current_xp), str(current_level), str(now)]

        def save_user_record():
            if user_row_idx:
                sheet.update(range_name=f"A{user_row_idx}:E{user_row_idx}", values=[user_payload])
            else:
                sheet.append_row(user_payload)

        await loop.run_in_executor(None, save_user_record)

        if leveled_up and msg_enabled:
            formatted_msg = lvl_up_template.replace("{user}", message.author.mention).replace("{level}", str(current_level))
            try:
                await message.channel.send(formatted_msg)
            except discord.Forbidden:
                pass

    @app_commands.command(name="xp", description="Manage settings for this server's dedicated tracking tab.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def xp_dashboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)
        
        loop = asyncio.get_running_loop()
        def check_tab_exists():
            if not self.spreadsheet:
                self.get_guild_tab(guild_id)
            titles = [w.title for w in self.spreadsheet.worksheets()]
            return guild_id in titles

        tab_exists = await loop.run_in_executor(None, check_tab_exists)
        content_text = "🔄 Standalone data tab found for this guild. Update your settings?" if tab_exists else "📊 No tab found for this server. Initialize an isolated server XP system?"

        await interaction.followup.send(
            content=content_text, 
            view=XPSetupPromptView(self, guild_id, exists=tab_exists), 
            ephemeral=True
        )

    @commands.command(name="level")
    async def show_level(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        if member.bot:
            return

        guild_id = str(ctx.guild.id)
        user_id = str(member.id)
        
        async with ctx.typing():
            loop = asyncio.get_running_loop()
            sheet = await loop.run_in_executor(None, self.get_guild_tab, guild_id)
            rows = await loop.run_in_executor(None, sheet.get_all_values)

            custom_enabled = False
            embed_title = "✨ {name}'s Level Progress"
            border_hex = "purple"
            filled_emoji = "🟩"
            empty_emoji = "⬛"
            raw_curves = ""
            raw_names = ""
            
            if len(rows) >= 2:
                config = rows[1]
                custom_enabled = len(config) > 11 and config[11] == "True"
                if len(config) > 12 and config[12]: embed_title = config[12]
                if len(config) > 13 and config[13]: border_hex = config[13]
                if len(config) > 14 and config[14]: filled_emoji = config[14]
                if len(config) > 15 and config[15]: empty_emoji = config[15]
                if len(config) > 17 and config[17]: raw_curves = config[17]
                if len(config) > 18 and config[18]: raw_names = config[18]

            curves = {}
            if raw_curves:
                split_brackets = [x.strip() for x in raw_curves.split(",") if x.strip().isdigit()]
                for lvl_idx, xp_val in enumerate(split_brackets, start=1):
                    curves[str(lvl_idx)] = int(xp_val)

            names_lookup = []
            if raw_names:
                names_lookup = [n.strip() for n in raw_names.split(",")]

            current_xp, current_level = 0, 1
            for row in rows[1:]:
                if row and row[0] == user_id:
                    current_xp = int(row[2]) if len(row) > 2 and row[2].isdigit() else 0
                    current_level = int(row[3]) if len(row) > 3 and row[3].isdigit() else 1
                    break

            xp_needed = curves.get(str(current_level), 100)
            if xp_needed <= 0:
                xp_needed = 100
                
            progress_ratio = min(current_xp / xp_needed, 1.0)
            percentage = int(progress_ratio * 100)
            
            bar_length = 10
            filled_blocks = int(progress_ratio * bar_length)
            empty_blocks = bar_length - filled_blocks
            progress_bar = (filled_emoji * filled_blocks) + (empty_emoji * empty_blocks)

            embed_color = discord.Color.purple()
            if custom_enabled:
                try:
                    if border_hex.startswith("#"):
                        embed_color = discord.Color.from_str(border_hex)
                    else:
                        embed_color = getattr(discord.Color, border_hex.lower())()
                except Exception:
                    embed_color = discord.Color.purple()

            # Dynamically grab custom display name if it exists inside column S index
            tier_display_title = f"Level {current_level}"
            if names_lookup and len(names_lookup) >= current_level:
                tier_display_title = f"{names_lookup[current_level - 1]} (Lvl {current_level})"

            formatted_title = embed_title.replace("{name}", member.display_name).replace("{level}", str(current_level))
            embed = discord.Embed(title=formatted_title, color=embed_color)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name=" Rank / Tier", value=f"`{tier_display_title}`", inline=True)
            embed.add_field(name=" Experience", value=f"`{current_xp} / {xp_needed} XP`", inline=True)
            embed.add_field(name=f" Progress to Next Tier ({percentage}%)", value=progress_bar, inline=False)
            embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)

            await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(XPConfigCog(bot))