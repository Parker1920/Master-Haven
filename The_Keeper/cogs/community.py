import discord
from discord.ext import commands
import aiohttp
import csv
from io import StringIO
import asyncio
import gspread
from google.oauth2.service_account import Credentials


# -------------------- PAGINATOR --------------------
class SearchPaginator(discord.ui.View):
    def __init__(self, cog, results, embed_builder):
        super().__init__(timeout=120)
        self.cog = cog
        self.results = results
        self.embed_builder = embed_builder
        self.index = 0

    def build_page(self):
        row = self.results[self.index]
        embed = self.embed_builder(row, self.index + 1)

        link = next((v for k, v in row.items() if "link" in k.lower()), None)

        if link:
            link = str(link).strip()
            if not link.startswith("http"):
                link = f"https://{link}"
            content = link
        else:
            content = None

        return embed, content

    @discord.ui.button(label="⬅ Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
    
        await interaction.response.defer()
    
        try:
            if self.index > 0:
                self.index -= 1
    
            embed, content = self.build_page()
    
            await interaction.edit_original_response(
                embed=embed,
                content=content,
                view=self
            )
    
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @discord.ui.button(label="Next ➡", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
    
        await interaction.response.defer()
    
        try:
            if self.index < len(self.results) - 1:
                self.index += 1
    
            embed, content = self.build_page()
    
            await interaction.edit_original_response(
                embed=embed,
                content=content,
                view=self
            )
    
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

# -------------------- SEARCH MODAL --------------------
class SearchModal(discord.ui.Modal, title="Community Search"):
    search = discord.ui.TextInput(label="Enter search term", required=True)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.run_search(interaction, self.search.value)


# -------------------- SEARCH VIEW --------------------
class SearchView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog

    @discord.ui.button(label="Search", style=discord.ButtonStyle.primary)
    async def search_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchModal(self.cog))


# -------------------- ADD CIV MODAL --------------------
class AddCivModal(discord.ui.Modal, title="Add Entry"):
    name = discord.ui.TextInput(label="Community Name", required=True)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=True)
    link = discord.ui.TextInput(label="Permanent Link", required=False)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        loop = asyncio.get_running_loop()
        self.cog.setup_gsheet()

        headers = await loop.run_in_executor(None, self.cog.sheet.row_values, 1)
        existing_values = await loop.run_in_executor(None, self.cog.sheet.get_all_values)

        rows = existing_values[1:]
        new_name = self.name.value.strip().lower()

        for row in rows:
            if row and row[0].strip().lower() == new_name:
                await interaction.followup.send(
                    "⚠️ This community already exists in the sheet.",
                    ephemeral=True
                )
                return

        new_row = [""] * len(headers)

        col_link = next((i for i, h in enumerate(headers) if "link" in h.lower()), None)

        new_row[0] = self.name.value
        if len(headers) > 1:
            new_row[1] = self.description.value
        if col_link is not None:
            new_row[col_link] = self.link.value or ""

        def insert():
            self.cog.sheet.append_row(new_row, value_input_option="RAW")

        await loop.run_in_executor(None, insert)

        await interaction.followup.send("✅ Entry added successfully!", ephemeral=True)


# -------------------- VIEW --------------------
class AddCivView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=120)
        self.cog = cog

    @discord.ui.button(label="Create Entry", style=discord.ButtonStyle.success)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddCivModal(self.cog))


# -------------------- SHEET --------------------
SHEET_ID = "1P1DvL7sm4qt3vKInWhkqVdKOl20ui_aVaCJNEHtQS64"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"


# -------------------- COG --------------------
class CommunityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.gc = None
        self.sheet = None

    async def cog_unload(self):
        await self.session.close()

    def setup_gsheet(self):
        if self.sheet:
            return

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]

        creds_dict = {
            "type": "service_account",
            "project_id": "the-keeper-493501",
            "client_email": "whrstrsg@the-keeper-493501.iam.gserviceaccount.com",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        self.gc = gspread.authorize()
        self.sheet = self.gc.open_by_key(SHEET_ID).sheet1

    async def fetch_sheet(self):
        async with self.session.get(SHEET_URL) as resp:
            text = await resp.text()
            return list(csv.reader(StringIO(text)))

    async def run_search(self, interaction: discord.Interaction, search: str):
        rows = await self.fetch_sheet()
        headers = [h.strip() for h in rows[0]]

        data = []
        for r in rows[1:]:
            if not r:
                continue
            row_dict = {headers[i]: (r[i] if i < len(r) else "") for i in range(len(headers))}
            data.append(row_dict)

        search_words = search.lower().strip().split()

        scored = []
        for r in data:
            blob = " ".join(str(v) for v in r.values() if v).lower()
            score = sum(1 for w in search_words if w in blob)

            if score > 0:
                scored.append((score, r))

        matches = [r for _, r in sorted(scored, key=lambda x: x[0], reverse=True)][:10]

        if not matches:
            await interaction.edit_original_response(
                content="No match found (try more specific terms).",
                embed=None,
                view=None
            )
            return

        def build_embed(row, i):
            e = discord.Embed(title=f"Result {i}")

            allowed = ["Community Name", "Description", "Permanent Link"]
            for k in allowed:
                if row.get(k):
                    e.add_field(name=k, value=row[k], inline=False)
            link = next((v for k, v in row.items() if "link" in k.lower() and v), None)

            if link:
                if not link.startswith("http"):
                    link = "https://" + link
        
                e.add_field(
                    name="🔗 Link",
                    value=f"[Open]({link})",
                    inline=False
                )

            return e

        view = SearchPaginator(self, matches, build_embed)
        embed, content = view.build_page()

        await interaction.edit_original_response(
            embed=embed,
            content=content,
            view=view
        )


# -------------------- SETUP --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(CommunityCog(bot))
