import discord
from discord.ext import commands
import aiohttp
import csv
import os
from io import StringIO
import asyncio
import gspread


# -------------------- PAGINATOR -----------------
class SearchPaginator(discord.ui.View):
    def __init__(self, cog, results, embed_builder):
        super().__init__(timeout=120)
        self.cog = cog
        self.results = results
        self.embed_builder = embed_builder
        self.index = 0

    async def build_page(self):
        row = self.results[self.index]
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
# -------------------- ADD CIV MODAL --------------------
class AddCivModal(discord.ui.Modal, title="Add Entry"):
    name = discord.ui.TextInput(label="Community Name", required=True)
    
    # Tag field enforcing 2-5 characters natively via Discord UI
    tag = discord.ui.TextInput(
        label="Tag (2-5 characters)", 
        min_length=2, 
        max_length=5, 
        required=True,
        placeholder="e.g., CIV, USA, ROME"
    )
    
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        required=True
    )
    link = discord.ui.TextInput(label="Permanent Link", required=False)

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
                        self.tag.value.upper(), # Pass updated tag down
                        self.description.value,
                        self.link.value
                    ),
                    ephemeral=True
                )
                return

        # Ensure array is large enough to handle up to column 10 (J)
        num_columns = max(len(headers), 10)
        new_row = [""] * num_columns
        new_row[0] = self.name.value
        new_row[3] = self.description.value
        new_row[4] = self.link.value or ""
        new_row[9] = self.tag.value.upper() # 0-indexed tracking array

        def insert():
            next_row = len(self.cog.sheet.get_all_values()) + 1
            self.cog.sheet.update_cell(next_row, 1, self.name.value)
            self.cog.sheet.update_cell(next_row, 4, self.description.value)
            self.cog.sheet.update_cell(next_row, 5, self.link.value or "")
            self.cog.sheet.update_cell(next_row, 10, self.tag.value.upper()) # Save tag to column 10 (J)

        await loop.run_in_executor(None, insert)
        await interaction.followup.send(
            f"✅ Entry for **{self.name.value} [{self.tag.value.upper()}]** added successfully!",
            ephemeral=True
        )


# -------------------- EDIT CONFIRM VIEW --------------------
class EditConfirmView(discord.ui.View):
    def __init__(self, cog, name, tag, description, link):
        super().__init__(timeout=60)
        self.cog = cog
        self.name = name
        self.tag = tag
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
            self.cog.sheet.update_cell(target_row, 10, self.tag)

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

SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/"
    f"{SHEET_ID}/export?format=csv"
)


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

            async def run_search(self, interaction: discord.Interaction, search: str):
        # 1. First, check if the search term looks like a community tag (2-5 letters)
        clean_search = search.strip().upper()
        haven_community_name = None

        if 2 <= len(clean_search) <= 5:
            try:
                # Call Haven't discord_tags endpoint (using HAVEN_API from your config)
                # HAVEN_API = os.getenv("HAVEN_API", "https://havenmap.online")
                async with self.session.get(f"{self.cog.base_url}/api/discord_tags") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        tags_list = data.get("tags", [])
                        
                        # Look for a matching tag
                        for t in tags_list:
                            if t.get("tag", "").upper() == clean_search:
                                haven_community_name = t.get("name")
                                break
            except Exception as e:
                print(f"Failed to fetch tags from Haven: {e}")

        # 2. Continue with your existing local Google Sheets search logic
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
            row_dict["__tag_value"] = r[9] if len(r) > 9 else ""
            data.append(row_dict)

        search_words = search.lower().strip().split()
        scored = []

        for r in data:
            row_values = list(r.values())
            name = str(row_values[0]).strip().lower() if row_values else ""
            if not name:
                continue

            score = sum(1 for w in search_words if w in name)
            
            # Also score if the row's tag matches our search term
            if r.get("__tag_value", "").lower() == search.lower().strip():
                score += 2

            if score > 0:
                scored.append((score, r))

        matches = [
            r for _, r in sorted(
                scored,
                key=lambda x: x[0],
                reverse=True
            )
        ][:10]

        if not matches and not haven_community_name:
            await interaction.edit_original_response(
                content="No match found (try more specific terms).",
                embed=None,
                view=None
            )
            return

        # If there are no sheet matches but Haven verified the tag, construct a basic info embed
        if not matches and haven_community_name:
            e = discord.Embed(
                title=haven_community_name,
                description=f"**Tag:** `{clean_search}`\n\n*This community is registered on Haven, but has no local spreadsheet log yet.*",
                color=discord.Color.purple()
            )
            await interaction.edit_original_response(embed=e, view=None)
            return

        async def build_embed(row, i):
            community_name = row.get("Community", f"Result {i}")
            tag_value = row.get("__tag_value", "").strip()

            e = discord.Embed(
                title=str(community_name).strip(), 
                color=discord.Color.purple()
            )
            
            # Injecting verified Haven name info if it matches this row
            if tag_value:
                if tag_value.upper() == clean_search and haven_community_name:
                    e.description = f"**Tag:** `{tag_value.upper()}`\n**Haven Verified Name:** {haven_community_name}"
                else:
                    e.description = f"**Tag:** `{tag_value.upper()}`"

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