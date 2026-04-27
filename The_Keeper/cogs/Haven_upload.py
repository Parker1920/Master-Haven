# -------------------- Haven Upload---------------
import discord
from discord.ext import commands
import aiohttp
from discord.ui import Select, Button, TextInput
import traceback
import sys, os
import json

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

BASE_URL = os.getenv("HAVEN_API", "https://havenmap.online")
API_KEY = os.getenv("HAVEN_API_KEY")
if not API_KEY:
    raise RuntimeError("HAVEN_API_KEY must be set in .env")

# -------------------- API LAYER ----------------
class HavenAPI:
    def __init__(self):
        self.base = BASE_URL
        self.headers = {"X-API-Key": API_KEY}  
        self.DiscoveryTypeSelect = DiscoveryTypeSelect     

    async def validate_glyph(self, glyph: str):
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base}/api/validate_glyph", json={"glyph": glyph}) as resp:
                return await resp.json()

    async def check_duplicate(self, glyph: str, galaxy="Euclid", reality="Normal"):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base}/api/check_duplicate",
                params={"glyph_code": glyph, "galaxy": galaxy, "reality": reality},
                headers=self.headers
            ) as resp:
                return await resp.json()

    async def submit_system(self, payload: dict):
        print("Submitting payload:", payload)  
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base}/api/extraction", json=payload, headers=self.headers) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    data = None

                if resp.status not in (200, 201):
                    text = await resp.text()  
                    raise Exception(f"Status {resp.status}: {text}")

                return data

    async def submit_discovery(self, payload: dict):
        url = f"{self.base}/api/discoveries"

        print("\n--- API DEBUG ---")
        print("POST URL:", url)
        print("Payload:", payload)

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=self.headers) as resp:
                status = resp.status
                text = await resp.text()

                print("Status:", status)
                print("Response Text:", text)
                print("-----------------\n")

                try:
                    data = await resp.json()
                except Exception:
                    data = text  
                if status not in (200, 201):
                    raise Exception(f"Discovery submission failed: {data}")

                return data

# -------------------- REALITY MODAL-----------
class RealitySelectView(discord.ui.View):
    def __init__(self, glyph_code, user_id, api):
        super().__init__(timeout=60)
        self.glyph_code = glyph_code
        self.user_id = user_id
        self.api = api
        self.selected_reality = None

        options = [
            discord.SelectOption(label="Normal", value="Normal"),
            discord.SelectOption(label="Permadeath", value="Permadeath")
        ]
        self.reality_dropdown = Select(
            placeholder="Select Reality",
            options=options,
            custom_id="reality_select"
        )
        self.reality_dropdown.callback = self.select_callback
        self.add_item(self.reality_dropdown)

        next_btn = Button(label="Next", style=discord.ButtonStyle.green)
        next_btn.callback = self.on_next
        self.add_item(next_btn)

    async def select_callback(self, interaction: discord.Interaction):
        self.selected_reality = self.reality_dropdown.values[0]
        await interaction.response.defer()

    async def on_next(self, interaction: discord.Interaction):
        if not self.selected_reality:
            await interaction.response.send_message("Please select a reality before continuing.", ephemeral=True)
            return
        await interaction.response.send_modal(GalaxyModal(self.glyph_code, self.user_id, self.api, self.selected_reality))

# -------------------- GALAXY MODAL ----------------
class GalaxyModal(discord.ui.Modal):
    def __init__(self, glyph_code, user_id, api, reality):
        super().__init__(title="Galaxy Submission")
        self.glyph_code = glyph_code
        self.user_id = user_id
        self.api = api
        self.reality = reality

        self.galaxy_name = TextInput(
            label="Galaxy",
            placeholder="Enter the galaxy name",
            required=True,
            max_length=100
        )
        self.add_item(self.galaxy_name)

    async def on_submit(self, interaction: discord.Interaction):
        galaxy = self.galaxy_name.value
        view = LevelSelectView(self.glyph_code, self.user_id, self.api, galaxy, self.reality)
        await interaction.response.send_message("✅ Galaxy submitted. Now select system levels:", view=view, ephemeral=True)

# -------------------- LEVEL MODAL --------------
class LevelSelectView(discord.ui.View):
    def __init__(self, glyph_code, user_id, api, galaxy, reality):
        super().__init__(timeout=180)
        self.glyph_code = glyph_code
        self.user_id = user_id
        self.api = api
        self.galaxy = galaxy
        self.reality = reality
        self.values = {}

        self.star_dropdown = Select(
            placeholder="Select Star Type",
            options=[discord.SelectOption(label=s, value=s) for s in ["Yellow", "Red", "Green", "Blue", "Purple"]],
            custom_id="star_type_select"
        )
        self.star_dropdown.callback = self.star_callback
        self.add_item(self.star_dropdown)

        self.race_dropdown = Select(
            placeholder="Select Race",
            options=[discord.SelectOption(label=s, value=s) for s in ["Vy'keen", "Korvax", "Gek", "None"]],
            custom_id="race_select"
        )
        self.race_dropdown.callback = self.race_callback
        self.add_item(self.race_dropdown)

        self.econ_dropdown = Select(
            placeholder="Select Economy Level",
            options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(1,4)],
            custom_id="econ_select"
        )
        self.econ_dropdown.callback = self.econ_callback
        self.add_item(self.econ_dropdown)

        self.conflict_dropdown = Select(
            placeholder="Select Conflict Level",
            options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(1,4)],
            custom_id="conflict_select"
        )
        self.conflict_dropdown.callback = self.conflict_callback
        self.add_item(self.conflict_dropdown)

        submit_btn = Button(label="Submit Levels", style=discord.ButtonStyle.green)
        submit_btn.callback = self.submit_callback
        self.add_item(submit_btn)

    async def star_callback(self, interaction: discord.Interaction):
        self.values["star_type"] = self.star_dropdown.values[0]
        await interaction.response.defer()

    async def race_callback(self, interaction: discord.Interaction):
        self.values["race"] = self.race_dropdown.values[0]
        await interaction.response.defer()

    async def econ_callback(self, interaction: discord.Interaction):
        self.values["economy_lvl"] = self.econ_dropdown.values[0]
        await interaction.response.defer()

    async def conflict_callback(self, interaction: discord.Interaction):
        self.values["conflict_lvl"] = self.conflict_dropdown.values[0]
        await interaction.response.defer()

    async def submit_callback(self, interaction: discord.Interaction):
        missing = [k for k in ["star_type","race","economy_lvl","conflict_lvl"] if k not in self.values]
        if missing:
            await interaction.response.send_message(f"Please select all fields: {', '.join(missing)}", ephemeral=True)
            return
        await interaction.response.send_modal(
            SystemSubmissionModal(
                self.glyph_code, self.user_id, self.api,
                self.galaxy, self.reality, self.values
            )
        )
        self.stop()

# -------------------- SYSTEM MODAL -----------
class SystemSubmissionModal(discord.ui.Modal):
    def __init__(self, glyph_code, user_id, api, galaxy, reality, levels):
        super().__init__(title="Submit System Log")
        self.glyph_code = glyph_code
        self.user_id = user_id
        self.api = api
        self.galaxy = galaxy
        self.reality = reality
        self.levels = levels

        self.system_name = TextInput(label="System Name", max_length=50, required=True)
        self.add_item(self.system_name)

        self.community_tag = TextInput(
            label="Community Tag",
            placeholder="Enter Civ Tag",
            max_length=5,
            required=True
        )
        self.add_item(self.community_tag)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        payload = {
            "glyph_code": self.glyph_code,
            "system_name": self.system_name.value,
            "community_tag": self.community_tag.value,  
            "galaxy_name": self.galaxy,
            "reality": self.reality,
            "user_id": self.user_id,
            "star_type": self.levels["star_type"],
            "economy_type": self.levels["economy_lvl"],
            "race": self.levels["race"],
            "conflict_lvl": self.levels["conflict_lvl"]
        }

        try:
            await self.api.submit_system(payload)
            from cogs import xp_system
            from cogs.xp_system import get_user, DepartmentView, process_discovery_xp
            
            await process_discovery_xp(
                user_id=self.user_id,
                discovery_type="system",  
                channel_id=interaction.channel.id
            )
            embed = discord.Embed(
                title="✅ Submission Sent",
                description=f"**{self.system_name.value}** is now in review.",
                color=0x00FF00
            )
            embed.add_field(name="Glyph", value=f"`{self.glyph_code}`", inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Submission failed: {e}")

#-------------------Discovery Modal--------------
import sqlite3
from cogs import xp_system
from cogs.xp_system import get_user, process_discovery_xp, DISCOVERY_TYPE_MAP
from cogs.Data.xpdata import get_level, CONFIG

class DiscoveryTypeSelect(discord.ui.View):
    def __init__(self, api, glyph_emojis, owner_id):
        super().__init__(timeout=60)
        self.api = api
        self.glyph_emojis = glyph_emojis
        self.owner_id = owner_id

        self.selected_type = None
        self.selected_reality = None

        # ---------------- REALITY ----------------
        options = [
            discord.SelectOption(label="Normal", value="Normal"),
            discord.SelectOption(label="Permadeath", value="Permadeath")
        ]
        self.reality_dropdown = Select(
            placeholder="Select Reality",
            options=options,
            custom_id="reality_select"
        )
        self.reality_dropdown.callback = self.reality_callback
        self.add_item(self.reality_dropdown)

        # ---------------- DISCOVERY TYPE ----------------
        options = [
            discord.SelectOption(label="Starships", value="starship"),
            discord.SelectOption(label="Fauna", value="fauna"),
            discord.SelectOption(label="Flora", value="flora"),
            discord.SelectOption(label="Multi-tool", value="multitool"),
            discord.SelectOption(label="Bases", value="base")
        ]

        self.select = discord.ui.Select(
            placeholder="Select Discovery Type",
            options=options
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

        self.next_btn = discord.ui.Button(
            label="Next",
            style=discord.ButtonStyle.green,
            disabled=True
        )
        self.next_btn.callback = self.next_callback
        self.add_item(self.next_btn)

    async def reality_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This isn't your session.", ephemeral=True)
            return

        self.selected_reality = self.reality_dropdown.values[0]

        for option in self.reality_dropdown.options:
            option.default = option.value == self.selected_reality

        self.next_btn.disabled = not (self.selected_type and self.selected_reality)

        await interaction.response.edit_message(view=self)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This isn't your session.", ephemeral=True)
            return

        self.selected_type = self.select.values[0]

        for option in self.select.options:
            option.default = option.value == self.selected_type

        self.next_btn.disabled = not (self.selected_type and self.selected_reality)

        await interaction.response.edit_message(view=self)

    async def next_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This isn't your session.", ephemeral=True
            )
            return

        if not (self.selected_type and self.selected_reality):
            await interaction.response.send_message(
                "Select both Reality and Type first.", ephemeral=True
            )
            return

        haven_cog = interaction.client.get_cog("HavenSubmission")
        HexKeypad = getattr(haven_cog, "HexKeypad", None)

        try:
            view = HexKeypad(
                api=self.api,
                glyph_emojis=self.glyph_emojis,
                owner_id=self.owner_id,
                mode="discovery"
            )
            view.discovery_type = self.selected_type
            view.reality = self.selected_reality  

            embed = view.build_embed(
                title=f"Submit Discovery: {self.selected_type}"
            )

            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )

            self.stop()

        except Exception:
            import traceback
            traceback.print_exc()


# =========================
# DISCOVERY MODAL
# =========================
class DiscoverySubmissionModal(discord.ui.Modal):
    def __init__(self, glyph, user_id, api, discovery_type,
                 system_exists=False,
                 system_name=None,
                 system_id=None,
                 notes=None):
        super().__init__(title="Submit Discovery")

        self.glyph = glyph
        self.user_id = user_id
        self.api = api
        self.dtype = discovery_type
        self.system_exists = system_exists
        self.system_id = system_id
        self.prefill_notes = notes        

        self.galaxy_name = TextInput(
            label="Galaxy",
            placeholder="Enter the galaxy name",
            required=True,
            max_length=100
        )
        self.add_item(self.galaxy_name)
        
        self.system_name = TextInput(
            label="System Name",
            max_length=100,
            required=not system_exists
        )
        self.add_item(self.system_name)

        self.community_tag = TextInput(
            label="Community Tag",
            placeholder="Enter Civ Tag",
            max_length=5,
            required=True
        )
        self.add_item(self.community_tag)
        
        self.discovery_name = TextInput(label="Discovery Name", max_length=100)
        self.add_item(self.discovery_name)

        self.notes = TextInput(
            label="Notes",
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This isn't your discovery session.", ephemeral=True
            )
            return

        view = DiscoveryConfirmView(
            glyph=self.glyph,
            user_id=self.user_id,
            api=self.api,
            discovery_type=self.dtype,
            system_exists=self.system_exists,
            galaxy_name=self.galaxy_name.value,
            system_name=self.system_name.value,
            system_id=self.system_id,
            notes=self.notes.value,
            discovery_name=self.discovery_name.value,
            community_tag=self.community_tag.value    
        )

        embed = discord.Embed(
            title="Confirm Discovery Submission",
            color=0x00FFFF
        )
        embed.add_field(name="Name", value=self.discovery_name.value, inline=False)
        embed.add_field(name="Type", value=self.dtype, inline=True)
        embed.add_field(name="Glyph", value=self.glyph, inline=True)

        if self.notes.value:
            embed.add_field(name="Notes", value=self.notes.value, inline=False)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )


# =========================
# XP HOOK
# =========================
class DiscoveryConfirmView(discord.ui.View):
    def __init__(self, glyph, user_id, api, discovery_type,
                 system_exists=False,
                 galaxy_name=None,
                 system_name=None,
                 system_id=None,
                 notes=None,
                 discovery_name=None,
                 community_tag=None):  

        super().__init__(timeout=None)

        self.glyph = glyph
        self.user_id = user_id
        self.api = api
        self.discovery_type = discovery_type
        self.system_exists = system_exists
        self.galaxy_name = galaxy_name  
        self.system_name = system_name
        self.system_id = system_id 
        self.prefill_notes = notes  
        self.discovery_name = discovery_name
        self.community_tag = community_tag

        self.confirm_btn = discord.ui.Button(
            label="Confirm Submit",
            style=discord.ButtonStyle.green
        )
        self.confirm_btn.callback = self.confirm_callback
        self.add_item(self.confirm_btn)

    async def confirm_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(
                    "This isn't your session.", ephemeral=True
                )
                return

            discovery_name = self.discovery_name or f"{self.discovery_type} {self.glyph}"

            await interaction.response.defer(ephemeral=True)

            system_id = self.system_id

# ---------------- SYSTEM CREATION -----------
            if not self.system_exists:
                system_payload = {
                    "glyph_code": self.glyph,
                    "system_name": self.system_name,
                    "community_tag": self.community_tag,
                    "galaxy_name": self.galaxy_name,
                    "reality": getattr(self, "reality", "Normal"),
                    "user_id": self.user_id
                }

                system_result = await self.api.submit_system(system_payload)

                system_id = (
                    system_result.get("system_id")
                    or system_result.get("submission_id")
                    or system_result.get("id")
                    or (system_result.get("system") or {}).get("id")
                )

                if not system_id:
                    raise Exception(f"System creation failed: {system_result}")

# ---------------- DISCOVERY SUBMISSION -----
            payload = {
                "system_id": system_id,
                "discovery_name": discovery_name,
                "discovery_type": self.discovery_type.lower(),
                "community_tag": self.community_tag,
                "notes": self.prefill_notes,
                "discord_username": interaction.user.name,
                "discord_tag": self.community_tag
            }

            result = await self.api.submit_discovery(payload)
            
            msg = (
                f"✅ Discovery submitted!\n"
                f"System: `{self.system_name or 'Unknown'}`\n"
                f"Discovery: `{discovery_name}`"
            )
            
            system_xp = process_system_creation_xp( 
                user_id=self.user_id,
                system_name=self.system_name,
                channel_id=interaction.channel.id,
            )
            if system_xp:
                msg += f"\n✨ +{system_xp} XP for system creation"
            
            xp_gained = await process_discovery_xp(
                user_id=self.user_id,
                discovery_type=self.discovery_type.lower(),
                channel_id=interaction.channel.id,
            )
            if xp_gained:
                msg += f"\n✨ +{xp_gained} XP earned"

# ---------------- BONUS HINT -------------------
            role = DISCOVERY_TYPE_MAP.get(self.discovery_type.lower())
            role_channels = CONFIG.get("roles", {}).get(role, {}).get("channels", [])

            if role and interaction.channel.id not in role_channels:
                msg += "\n\n🧭 Tip: Submit in your department channel for bonus XP"

            await interaction.followup.send(msg, ephemeral=True)

        except Exception as e:
            try:
                await interaction.followup.send(
                    f"❌ Submission failed: {e}", ephemeral=True
                )
            except:
                await interaction.response.send_message(
                    f"❌ Submission failed: {e}", ephemeral=True
                )


# -------------------- HEX KEYBOARD VIEW ----
class HexKeypad(discord.ui.View):
    def __init__(self, api, glyph_emojis, owner_id: int, mode="system"):
        super().__init__(timeout=None)
        self.api = api
        self.owner_id = owner_id
        self.glyph_emojis = glyph_emojis
        self.input_string = ""
        self.emoji_sequence = []
        self.mode = mode
        self.discovery_type = None
        
        self.error_triggered = {
            "planet": False,
            "system": False,
            "yy": False,
            "zzz": False,
            "xxx": False,
            "galactic_core": False
        }

        hex_keys = [["0","1","2","3"],["4","5","6","7"],["8","9","A","B"],["C","D","E","F"]]
        for row_index, row in enumerate(hex_keys):
            for key in row:
                emoji = glyph_emojis.get(key)
                button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    emoji=emoji,
                    custom_id=f"hex_{key}_{owner_id}",
                    row=row_index
                )
                button.callback = self.make_callback(key, emoji)
                self.add_item(button)

        back = discord.ui.Button(label="←", style=discord.ButtonStyle.danger, custom_id=f"hex_back_{owner_id}", row=4)
        back.callback = self.backspace
        self.add_item(back)

        reset = discord.ui.Button(label="Reset", style=discord.ButtonStyle.primary, custom_id=f"hex_reset_{owner_id}", row=4)
        reset.callback = self.reset
        self.add_item(reset)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("This isn't your glyph session.", ephemeral=True)
            return False
        return True

    def build_embed(self, title="Glyph Input"):
        embed = discord.Embed(title=title, color=0x00FFFF)
        embed.add_field(name="Current Input", value=f"`{self.input_string or ' '}`", inline=False)
        if self.emoji_sequence:
            embed.add_field(name="Preview", value=" ".join(self.emoji_sequence), inline=False)
        return embed

    def make_callback(self, key, emoji):
        async def callback(interaction):
            self.input_string += key
            if emoji:
                self.emoji_sequence.append(f"<:{emoji.name}:{emoji.id}>")
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(embed=self.build_embed(), view=self)
                else:
                    await interaction.followup.edit_message(
                        interaction.message.id,
                        embed=self.build_embed(),
                        view=self
                    )
            except:
                await interaction.message.edit(embed=self.build_embed(), view=self)

        
            if len(self.input_string) != 12:
                return
               

            glyph = self.input_string
            self.emoji_sequence = self.emoji_sequence[:12]                   

        # ------------------ VALIDATION ------------------
            valid = await self.api.validate_glyph(glyph)
            if not valid.get("valid"):
                self.reset_state()
                return await interaction.followup.send(
                    "❌ Invalid glyph code.",
                    ephemeral=True
                )

            dup = await self.api.check_duplicate(glyph)

        # ------------------ DISCOVERY FLOW ------------------
            if self.mode == "discovery":
                system_exists = dup.get("exists")
                system_name = dup.get("system_name")
                system_id = dup.get("system_id")

                msg = (
                    f"⚠️ System already exists: **{system_name or 'Unknown'}**"
                    if system_exists
                    else "❌ System doesn't exist.\nCreating discovery..."
                )

                class ContinueView(discord.ui.View):
                    def __init__(self, outer):
                        super().__init__(timeout=60)
                        self.outer = outer

                    @discord.ui.button(label="Continue", style=discord.ButtonStyle.green)
                    async def continue_btn(self, interaction2: discord.Interaction, button: discord.ui.Button):
                        if interaction2.user.id != self.outer.owner_id:
                            await interaction2.response.send_message("Not your session.", ephemeral=True)
                            return

                        modal = DiscoverySubmissionModal(
                            glyph=glyph,
                            user_id=interaction2.user.id,
                            api=self.outer.api,
                            discovery_type=self.outer.discovery_type,
                            system_exists=system_exists,
                            system_name=system_name,
                            system_id=system_id,
                            notes=None
                        )

                        await interaction2.response.send_modal(modal)
                        self.stop()

                view = ContinueView(self)

                if interaction.response.is_done():
                    await interaction.followup.send(msg, view=view, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, view=view, ephemeral=True)

                self.stop()
                return

        # ------------------ SYSTEM FLOW (!addlog) ------------------
            else:
                if dup.get("exists"):
                    await interaction.followup.send(
                        f"⚠️ System already exists: **{dup.get('system_name','Unknown')}**",
                        ephemeral=True
                    )
                    self.stop()
                    return

                await interaction.followup.send(
                    f"**Glyph:** `{glyph}`\nSelect Reality:",
                    view=RealitySelectView(glyph, interaction.user.id, self.api),
                    ephemeral=True
                )

                self.stop()
                return

        return callback

    def reset_state(self):
        self.input_string = ""
        self.emoji_sequence = []

    async def backspace(self, interaction):
        self.input_string = self.input_string[:-1]
        self.emoji_sequence = self.emoji_sequence[:-1]
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=self.build_embed(), view=self)
            else:
                await interaction.followup.edit_message(interaction.message.id, embed=self.build_embed(), view=self)
        except:
            await interaction.message.edit(embed=self.build_embed(), view=self)

    async def reset(self, interaction):
        self.reset_state()
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=self.build_embed(), view=self)
            else:
                await interaction.followup.edit_message(interaction.message.id, embed=self.build_embed(), view=self)
        except:
            await interaction.message.edit(embed=self.build_embed(), view=self)
            
# ---------------- Hex Glyph Emojis ----------------
glyph_emojis = {
    "0": discord.PartialEmoji(name="0", id=1487546589269463211),
    "1": discord.PartialEmoji(name="1", id=1487546881692405843),
    "2": discord.PartialEmoji(name="2", id=1487546943319048222),
    "3": discord.PartialEmoji(name="3", id=1487546987858366615),
    "4": discord.PartialEmoji(name="4", id=1487547055651033129),
    "5": discord.PartialEmoji(name="5", id=1487547115688169754),
    "6": discord.PartialEmoji(name="6", id=1487547173934596226),
    "7": discord.PartialEmoji(name="7", id=1487547239361544403),
    "8": discord.PartialEmoji(name="8", id=1487547303932854353),
    "9": discord.PartialEmoji(name="9", id=1487547364553265152),
    "A": discord.PartialEmoji(name="A", id=1487547426406404126),
    "B": discord.PartialEmoji(name="B", id=1487547508065435728),
    "C": discord.PartialEmoji(name="C", id=1487547606140981379),
    "D": discord.PartialEmoji(name="D", id=1487547687229198369),
    "E": discord.PartialEmoji(name="E", id=1487547811003105300),
    "F": discord.PartialEmoji(name="F", id=1487547868922249479),
}

# -------------------- COG ----------------
class HavenSubmission(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = HavenAPI()
        self.HexKeypad = HexKeypad
        self.glyph_emojis = glyph_emojis
        self.DiscoveryTypeSelect = DiscoveryTypeSelect

# -------------------- SETUP ----------------
async def setup(bot):
    await bot.add_cog(HavenSubmission(bot))    