import gspread
from google.oauth2.service_account import Credentials
import aiosqlite
import discord
from discord.ext import commands

# Import your existing configuration and database path verbatim from xpdata.py
from cogs.Data.xpdata import DB_PATH, CONFIG  #[span_1](start_span)[span_1](end_span)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SPREADSHEET_ID = "1nemU7y99HJen1wZ13ubSLaZ0mT7h9UtP8nNbrvju8hc"

class TransferCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_sheets_client(self):
        """Helper to authenticate with Google Sheets."""
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
        return gspread.authorize(creds)

    def _update_sheet_data(self, sh, title, headers, rows):
        """Helper to create or overwrite a specific worksheet tab."""
        try:
            worksheet = sh.worksheet(title)
            worksheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sh.add_worksheet(title=title, rows=100, cols=20)
        
        # Combine headers and rows together for a single API batch update
        all_data = [headers] + rows
        worksheet.update("A1", all_data)

    @commands.command(name="transfer")
    @commands.has_permissions(administrator=True)  # Keeps the command restricted to admins
    async def transfer(self, ctx):
        """Transfers all local database tracks and CONFIG mappings to Google Sheets."""
        # Send an initial feedback message so the user knows it's processing
        status_msg = await ctx.send("🔄 Initiating data transfer to Google Sheets... Please wait.")

        try:
            # 1. Authenticate with Google Sheets
            client = self._get_sheets_client()
            sh = client.open_by_key(SPREADSHEET_ID)

            config_rows = []
            for section, settings in CONFIG.items():  
                if isinstance(settings, dict):
                    for key, val in settings.items():
                        config_rows.append([f"{section}.{key}", str(val)])
                elif isinstance(settings, list):
                    config_rows.append([section, str(settings)])
            
            self._update_sheet_data(sh, "Configs", ["Setting Key", "Value"], config_rows)

        
            async with aiosqlite.connect(DB_PATH) as db:  
                
               
                async with db.execute("SELECT user_id, role, xp, level FROM user_roles") as cursor:
                    user_roles_rows = [list(row) for row in await cursor.fetchall()]
                self._update_sheet_data(sh, "User Roles Tracker", ["User ID", "Role", "XP", "Level"], user_roles_rows)

              
                async with db.execute("SELECT user_id, xp, level, senior_dm_sent FROM global_levels") as cursor:
                    global_rows = [list(row) for row in await cursor.fetchall()]
                self._update_sheet_data(sh, "Global Levels", ["User ID", "Global XP", "Global Level", "Senior DM Sent?"], global_rows)
                
          
                async with db.execute("SELECT user_id, primary_role FROM users") as cursor:
                    users_rows = [list(row) for row in await cursor.fetchall()]
                self._update_sheet_data(sh, "Users Map", ["User ID", "Primary Role"], users_rows)

 
            await status_msg.edit(content="✅ **Success!** All configuration settings and database records have been securely backed up to your Google Sheet.")

        except Exception as e:
       
            await status_msg.edit(content=f"❌ **An error occurred during transfer:** `{str(e)}`")

async def setup(bot):
    await bot.add_cog(TransferCog(bot))
