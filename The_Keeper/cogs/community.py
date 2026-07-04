import discord
from discord.ext import commands
import aiohttp
import csv
import os
from io import StringIO
import asyncio
import gspread


# -------------------- PAGINATOR --------------------
class SearchPaginator(discord.ui.View):
    def __init__(self, cog, results, embed_builder):
        super().__init__(timeout=120)
        self.cog = cog
        self.results = results
        self.embed_builder = embed_builder
        self.index = 0

    async def build_page(self):
        row = self.results[self.index]
        # Await the async embed builder
        embed = await self.embed_builder(row, self.index + 1)

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

            embed, content = await self.build_page()

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

            embed, content = await self.build_page()

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
        # Defer immediately to give fetch_invite time to run
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
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        required=True
    )
    link = discord.ui.TextInput(label="Permanent Link", required=False)
    
    # NEW: 2-5 Letter Tag Input linked to Column J
    tag = discord.ui.TextInput(
        label="Haven Tag (2-5 Letters)", 
        min_length=2, 
        max_length=5, 
        required=False,
        placeholder="e.g. ABC"
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        loop = asyncio.get_running_loop()

        try:
            await loop.run_in_executor(None, self.cog.setup_gsheet)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Could not connect to Google Sheets: `{type(e).__name__}: {e}`",
                ephemeral=True,
            )
            return

        headers = await loop.run_in_executor(
            None,
            self.cog.sheet.row_values,
            1
        )

        existing_values = await loop.run_in_executor(
            None,
            self.cog.sheet.get_all_values
        )

        rows = existing_values[1:]
        new_name = self.name.value.strip().lower()

        for row in rows:
            if row and row[0].strip().lower() == new_name:
                await interaction.followup.send(
                    "⚠️ This community already has an entry. Would you like to edit it?",
                    view=EditConfirmView(
                        self.cog,
                        self.name.value,
                        self.description.value,
                        self.link.value
                    ),
                    ephemeral=True
                )
                return

        # Read the entered tag and uppercase it cleanly
        clean_tag = self.tag.value.strip().upper() if self.tag.value else ""

        def insert():
            next_row = len(self.cog.sheet.get_all_values()) + 1
            self.cog.sheet.update_cell(next_row, 1, self.name.value)
            self.cog.sheet.update_cell(next_row, 4, self.description.value)
            self.cog.sheet.update_cell(next_row, 5, self.link.value or "")
            
            # Updates Column 10 (Column J) directly with the Tag
            self.cog.sheet.update_cell(next_row, 10, clean_tag)

        await loop.run_in_executor(None, insert)
        await interaction.followup.send(
            "✅ Entry added successfully!",
            ephemeral=True
        )


# -------------------- VIEW --------------------
class AddCivView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=120)
        self.cog = cog

    @discord.ui.button(label="Create Entry", style=discord.ButtonStyle.success)
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddCivModal(self.cog))


# -------------------- EDIT CONFIRM VIEW --------------------
class EditConfirmView(discord.ui.View):
    def __init__(self, cog, name, description, link):
        super().__init__(timeout=60)
        self.cog = cog
        self.name = name
        self.description = description
        self.link = link

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.cog.setup_gsheet)

        values = await loop.run_in_executor(
            None,
            self.cog.sheet.get_all_values
        )

        target_row = None
        for i, row in enumerate(values[1:], start=2):
            if row and row[0].strip().lower() == self.name.lower():
                target_row = i
                break

        if not target_row:
            await interaction.followup.send(
                "Entry not found.",
                ephemeral=True
            )
            return

        def update():
            self.cog.sheet.update_cell(target_row, 4, self.description)
            self.cog.sheet.update_cell(target_row, 5, self.link or "")

        await loop.run_in_executor(None, update)
        await interaction.followup.send(
            f"✏ Updated **{self.name}** successfully.",
            ephemeral=True
        )

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Cancelled.",
            ephemeral=True
        )


# -------------------- SHEET --------------------
SHEET_ID = "1P1DvL7sm4qt3vKInWhkqVdKOl20ui_aVaCJNEHtQS64"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"


# -------------------- COG --------------------
class CommunityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.base_url = os.getenv("HAVEN_API", "https://havenmap.online")
        self.gc = None
        self.sheet = None

    async def cog_unload(self):
        await self.session.close()

    def setup_gsheet(self):
        if self.sheet:
            return

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds_path = os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "/app/creds.json"
        )
        self.gc = gspread.service_account(
            filename=creds_path,
            scopes=scopes
        )
        self.sheet = self.gc.open_by_key(SHEET_ID).sheet1

    async def fetch_sheet(self):
        async with self.session.get(SHEET_URL) as resp:
            text = await resp.text()
            return list(csv.reader(StringIO(text)))

    async def get_haven_preview(self, glyph: str, galaxy: str = "Euclid", reality: str = "Normal"):
        """Queries the public Haven endpoint to retrieve deterministic community stats metadata"""
        try:
            params = {"glyph": glyph, "galaxy": galaxy, "reality": reality}
            async with self.session.get(f"{self.base_url}/api/glyph/preview", params=params, timeout=5) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 503:
                    return "503"
        except Exception:
            return None

    async def run_search(self, interaction: discord.Interaction, search: str):
        rows = await self.fetch_sheet()

        if not rows:
            await interaction.edit_original_response(
                content="No data found.",
                embed=None,
                view=None
            )
            return

        headers = [h.strip() for h in rows[0]]
        data = []

        for r in rows[1:]:
            if not r:
                continue
            row_dict = {
                headers[i]: (r[i] if i < len(r) else "")
                for i in range(len(headers))
            }
            data.append(row_dict)

        search_words = search.lower().strip().split()
        scored = []

        for r in data:
            row_values = list(r.values())
            name = str(row_values[0]).strip().lower() if row_values else ""
            if not name:
                continue

            score = sum(1 for w in search_words if w in name)
            if score > 0:
                scored.append((score, r))

        matches = [
            r for _, r in sorted(
                scored,
                key=lambda x: x[0],
                reverse=True
            )
        ][:10]

        if not matches:
            await interaction.edit_original_response(
                content="No match found (try more specific terms).",
                embed=None,
                view=None
            )
            return

        async def build_embed(row, i):
            community_name = row.get("Community", f"Result {i}")
            
            # Dynamic header lookup: reads Column J's header text or falls back safely
            community_tag = row.get("Haven Tag", row.get("Tag", "UNALIGNED"))

            e = discord.Embed(
                title=str(community_name).strip(), 
                color=discord.Color.purple()
            )

            allowed = ["Description", "perma-link"]
            label_map = {                
                "Description": "Description",
                "perma-link": "Permanent Link"
            }

            for k in allowed:
                value = row.get(k)
                if value and str(value).strip():
                    e.add_field(
                        name=label_map.get(k, k),
                        value=value,
                        inline=False
                    )          

            # --- FETCH SYSTEMS LOGGED COUNT FROM ENDPOINT ---
            glyph_code = row.get("Glyph") or row.get("Glyph Code")
            galaxy_name = row.get("Galaxy", "Euclid")
            
            if glyph_code and len(str(glyph_code).strip()) == 12:
                preview = await self.get_haven_preview(str(glyph_code).strip(), galaxy=galaxy_name)
                
                if preview and preview != "503":
                    reg_status = preview.get("region_status", {})
                    sys_count = reg_status.get("system_count", 0)
                    e.add_field(name="📊 Systems Logged", value=f"`{sys_count}` community entries mapped", inline=True)
                elif preview == "503":
                    e.add_field(name="⚠️ Haven Status", value="Logging stats service temporarily offline.", inline=False)

            # Link with the newly extracted Haven Tag
            e.add_field(name="Identity Tag", value=f"`[{community_tag if community_tag else 'UNALIGNED'}]`", inline=True)

            link = next(
                (v for k, v in row.items() if "link" in k.lower() and v),
                None
            )

            member_text = "Members: Unknown"
            if link:
                link_str = str(link).strip()
                if not link_str.startswith("http"):
                    link_str = "https://" + link_str

                if "discord.gg" in link_str or "discord.com/invite" in link_str:
                    try:
                        invite_code = link_str.split("/")[-1]
                        invite = await self.bot.fetch_invite(invite_code, with_counts=True)
                        if invite and invite.approximate_member_count is not None:
                            member_text = f"👥 {invite.approximate_member_count:,} Members ({invite.approximate_presence_count:,} Online)"
                    except Exception:
                        member_text = "👥 Members: Link Expired/Invalid"

            e.set_footer(text=f"{member_text} | Result {i} of {len(matches)}")
            return e
    
        view = SearchPaginator(self, matches, build_embed)
        embed, content = await view.build_page()

        await interaction.edit_original_response(
            embed=embed,
            content=content,
            view=view
        )


# -------------------- SETUP --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(CommunityCog(bot))
