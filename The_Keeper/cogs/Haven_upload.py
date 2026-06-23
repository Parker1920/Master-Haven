# -------------------- Haven Upload---------------
import discord
from discord.ext import commands
import aiohttp
from discord.ui import Select, Button, TextInput
import traceback
import sys, os
import json
import logging
import re
import aiohttp
import asyncio

logger = logging.getLogger(__name__)    
    
    
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
    
    async def validate_glyph(self, glyph: str):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base}/api/validate_glyph",
                json={"glyph": glyph}
            ) as resp:
    
                if resp.status != 200:
                    return {
                        "valid": False,
                        "error": f"HTTP {resp.status}",
                    }
    
                data = await resp.json()
    
                if not isinstance(data, dict):
                    return {
                        "valid": False,
                        "error": "Invalid API response",
                    }
    
                return data
    
    async def check_duplicate(self, glyph, galaxy="Euclid", reality="Normal"):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base}/api/check_duplicate",
                params={"glyph_code": glyph, "galaxy": galaxy, "reality": reality},
                headers=self.headers
            ) as resp:
    
                if resp.status != 200:
                    return {
                        "duplicate": False,
                        "error": f"HTTP {resp.status}",
                    }
    
                data = await resp.json()
    
                if not isinstance(data, dict):
                    return {
                        "duplicate": False,
                        "error": "Invalid API response",
                    }
    
                return data
    
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
        
#----------------------NAMEGEN------------------
def generate_system_name(glyph_code: str, community_tag: str, levels_data: dict) -> str:
    """
    Autogenerates a standard Haven system name using:
    [Civ Tag] [Star/Economy Type Class] [Truncated Glyph Index Identifier]
    """
    
    civ = community_tag.strip().upper() if community_tag else "HAVEN"
    
    
    unique_suffix = glyph_code[-4:].upper()
    
    star_type = levels_data.get("star_type", "F").strip().upper()
    conflict = levels_data.get("conflict_lvl", "1")
    
    class_indicator = f"{star_type[0]}{conflict}" if star_type else "G4"
    
    return f"[{civ}] {class_indicator}-{unique_suffix}"
    
# -------------------- REALITY MODAL-----------
class RealitySelectView(discord.ui.View):
    def __init__(self, glyph_code, user_id, api, api_generated_name):
        super().__init__(timeout=60)
        self.glyph_code = glyph_code
        self.user_id = user_id
        self.api = api
        self.api_generated_name = api_generated_name 
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
      
        await interaction.response.send_modal(
            GalaxyModal(self.glyph_code, self.user_id, self.api, self.selected_reality, self.api_generated_name)
        )

        
# -------------------- GALAXY MODAL -----------
class GalaxyModal(discord.ui.Modal):
    def __init__(self, glyph_code, user_id, api, reality, api_generated_name):
        super().__init__(title="Galaxy Submission")
        self.glyph_code = glyph_code
        self.user_id = user_id
        self.api = api
        self.reality = reality
        self.api_generated_name = api_generated_name
    
        self.galaxy_name = TextInput(
            label="Galaxy",
            placeholder="Enter the galaxy name",
            required=True,
            max_length=100
        )
        self.add_item(self.galaxy_name)
    
    async def on_submit(self, interaction: discord.Interaction):
        galaxy = self.galaxy_name.value
        view = LevelSelectView(self.glyph_code, self.user_id, self.api, galaxy, self.reality, self.api_generated_name)
        await interaction.response.send_message("✅ Galaxy submitted. Now select system levels:", view=view, ephemeral=True)

#-------------------- LEVEL SELECT VIEW ------
class LevelSelectView(discord.ui.View):
    def __init__(self, glyph_code, user_id, api, galaxy, reality, api_generated_name):
        super().__init__(timeout=180)
        self.glyph_code = glyph_code
        self.user_id = user_id
        self.api = api
        self.galaxy = galaxy
        self.reality = reality
        self.api_generated_name = api_generated_name 
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
                self.galaxy, self.reality, self.values, self.api_generated_name
            )
        )

  
    
# -------------------- SYSTEM MODAL -----------
class SystemSubmissionModal(discord.ui.Modal):
    def __init__(self, glyph_code, user_id, api, galaxy, reality, levels, api_generated_name):
        super().__init__(title="Submit System Log")
        self.glyph_code = glyph_code
        self.user_id = user_id
        self.api = api
        self.galaxy = galaxy
        self.reality = reality
        self.levels = levels
        self.api_generated_name = api_generated_name 
    
        
        self.system_name = TextInput(
            label="System Name", 
            placeholder="Leave blank to use official API name", 
            max_length=50, 
            required=False
        )
        self.add_item(self.system_name)
    
        self.community_tag = TextInput(
            label="Community Tag",
            placeholder="Enter Civ Tag",
            max_length=5,
            required=True
        )
        self.add_item(self.community_tag)
    
    async def on_submit(self, interaction: discord.Interaction):
        provided_name = self.system_name.value.strip()
        
      
        final_system_name = provided_name if provided_name else self.api_generated_name

        system_payload = {
            "glyph_code": self.glyph_code,
            "system_name": final_system_name,
            "discord_tag": self.community_tag.value,
            "galaxy_name": self.galaxy,
            "reality": self.reality,
            "dominant_lifeform": self.levels.get("race", "Unknown"),
            "conflict_level": self.levels.get("conflict_lvl", "Unknown"),
            "economy_type": self.levels.get("star_type", "Unknown"),
            "economy_strength": self.levels.get("economy_lvl", "1"),
            "user_id": self.user_id
        }
        
        view = PlanetPromptView(self.user_id, self.api, system_payload)
        await interaction.response.send_message(
            f"Captured details for **{final_system_name}**!\n"
            "Would you like to add planets to this system before final submission?", 
            view=view, 
            ephemeral=True
        )


class PlanetPromptView(discord.ui.View):
    def __init__(self, user_id, api, system_payload):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.api = api
        self.system_payload = system_payload
        self.planets = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your submission session.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Yes, add a planet", style=discord.ButtonStyle.primary)
    async def yes_btn(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_modal(PlanetInputModal(self))

    @discord.ui.button(label="No, submit system", style=discord.ButtonStyle.green)
    async def no_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        await self.execute_final_submission(interaction)

    async def execute_final_submission(self, interaction: discord.Interaction):
        try:
            system_result = await self.api.submit_system(self.system_payload)
            
            system_id = (
                system_result.get("system_id")
                or system_result.get("submission_id")
                or system_result.get("id")
                or (system_result.get("system") or {}).get("id")
            )

            for planet in self.planets:
                planet_payload = {
                    "system_id": system_id,
                    "discovery_name": planet["name"],
                    "discovery_type": "planet",
                    "community_tag": self.system_payload["discord_tag"],
                    "discord_tag": self.system_payload["discord_tag"],
                    "notes": f"Biome: {planet['biome']} | Fauna: {planet['fauna']} | Flora: {planet['flora']} | Sentinels: {planet['sentinel']}",
                    "discord_username": interaction.user.name,
                }
                await self.api.submit_discovery(planet_payload)

            from cogs.xp_system import process_discovery_xp
            await process_discovery_xp(
                user_id=self.user_id,
                discovery_type="system",  
                channel_id=interaction.channel.id
            )

            if self.planets:
                for _ in self.planets:
                    await process_discovery_xp(user_id=self.user_id, discovery_type="planet", channel_id=interaction.channel.id)

           
            embed = discord.Embed(
                title="✅ Submission Complete!",
                description=f"**{self.system_payload['system_name']}** and {len(self.planets)} planet(s) are now in review.",
                color=0x00FF00
            )
            embed.add_field(name="Glyph", value=f"`{self.system_payload['glyph_code']}`", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.stop()

        except Exception as e:
            await interaction.followup.send(f"❌ Submission failed: {e}", ephemeral=True)
            
#--------------------INPUT MODAL-------------
class PlanetInputModal(discord.ui.Modal):
    def __init__(self, prompt_view: PlanetPromptView):
        super().__init__(title=f"Planet #{len(prompt_view.planets) + 1} Details")
        self.prompt_view = prompt_view

        self.p_name = TextInput(label="Planet Name", required=True, max_length=100)
        self.biome = TextInput(label="Biome Type", placeholder="e.g. Lush, Desert, Toxic, Frozen...", required=True, max_length=50)
        self.fauna = TextInput(label="Fauna Description / Count", placeholder="e.g. 12 Fauna, Aggressive...", required=False, max_length=100)
        self.flora = TextInput(label="Flora Description", placeholder="e.g. Abundant, Vermilion...", required=False, max_length=100)
        self.sentinel = TextInput(label="Sentinel Activity", placeholder="e.g. Low, High, Aggressive...", required=False, max_length=50)

        self.add_item(self.p_name)
        self.add_item(self.biome)
        self.add_item(self.fauna)
        self.add_item(self.flora)
        self.add_item(self.sentinel)

    async def on_submit(self, interaction: discord.Interaction):
        self.prompt_view.planets.append({
            "name": self.p_name.value,
            "biome": self.biome.value,
            "fauna": self.fauna.value or "Unknown",
            "flora": self.flora.value or "Unknown",
            "sentinel": self.sentinel.value or "Unknown"
        })

        
        planet_list = "\n".join([f"• `{p['name']}` ({p['biome']})" for p in self.prompt_view.planets])
        msg = (
            f"### Current Queue to Submit:\n"
            f"**System**: `{self.prompt_view.system_payload['system_name']}`\n"
            f"**Planets Added:**\n{planet_list}\n\n"
            f"Would you like to add another planet, or proceed with final submission?"
        )
        
        await interaction.response.edit_message(content=msg, view=self.prompt_view)
   
#-------------------Discovery Modal--------------
import sqlite3
from cogs import xp_system
from cogs.xp_system import get_user, process_discovery_xp, DISCOVERY_TYPE_MAP
from Data.xpdata import get_level, CONFIG
import discord
    
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
                 notes=None,
                 reality=None):
        super().__init__(title="Submit Discovery")
    
        self.glyph = glyph
        self.user_id = user_id
        self.api = api
        self.dtype = discovery_type
        self.system_exists = system_exists
        self.system_id = system_id
        self.reality = reality
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

        super().__init__(timeout=60)

        self.glyph = glyph
        self.user_id = user_id
        self.api = api
        self.discovery_type = discovery_type
        self.galaxy_name = galaxy_name
        self.system_name = system_name
        self.system_id = system_id
        self.prefill_notes = notes
        self.discovery_name = discovery_name
        self.community_tag = community_tag
        self.system_exists = system_exists
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

            discovery_name = (
                self.discovery_name
                or f"{self.discovery_type} {self.glyph}"
            )

            await interaction.response.defer(ephemeral=True)

            system_result, system_id = await self.get_system()
            
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
            
            xp_gained = process_discovery_xp(
                user_id=self.user_id,
                discovery_type=self.discovery_type,
                channel_id=interaction.channel.id,
            )
            
            if xp_gained:
                msg += f"\n✨ +{xp_gained} XP earned"
            
            try:
                bonus_tip = get_bonus_tip(system_result)
            
                if bonus_tip:
                    msg += f"\n\n💡 {bonus_tip}"
            
            except Exception:
                logger.exception("Bonus hint failed")
            
            await interaction.followup.send(msg, ephemeral=True)

        except Exception as e:
            logger.exception("Discovery submission failed")

            await interaction.followup.send(
                f"❌ Submission failed: {e}",
                ephemeral=True
            )                             
                     
# ---------------- SYSTEM CREATION -----------
    async def get_system(self):
        if self.system_exists:
            if self.system_id:
                return {"id": self.system_id}, self.system_id
        
            
            dup = await self.api.check_duplicate(self.glyph)
        
            system_id = dup.get("system_id") or dup.get("id")
        
            if not system_id:
                raise Exception("System exists but API did not return system_id")
        
            return {"id": system_id}, system_id                      
        system_payload = {
            "glyph_code": self.glyph,
            "system_name": self.system_name,
            "community_tag": self.community_tag,
            "galaxy_name": self.galaxy_name,
            "reality": getattr(self, "reality", "Normal"),
            "user_id": self.user_id
        }
                    
        system_result = await self.api.submit_system(system_payload)
                    
        if not system_result:
            raise Exception("System API returned empty response")
                    
        system_id = (
            system_result.get("system_id")
            or system_result.get("submission_id")
            or system_result.get("id")
            or (system_result.get("system") or {}).get("id")
        )
                    
        if not system_id:
            raise Exception(f"System creation failed: {system_result}")
                    
        return system_result, system_id
    
    
# -------------------- HEX KEYBOARD VIEW ---
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

        back = discord.ui.Button(
            label="←",
            style=discord.ButtonStyle.danger,
            custom_id=f"hex_back_{owner_id}",
            row=4
        )
        back.callback = self.backspace
        self.add_item(back)

        reset = discord.ui.Button(
            label="Reset",
            style=discord.ButtonStyle.primary,
            custom_id=f"hex_reset_{owner_id}",
            row=4
        )
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
        
# ---------------- CALLBACK FACTORY ---------
    def make_callback(self, key, emoji):
        async def callback(interaction: discord.Interaction):
            if len(self.input_string) >= 12:
                return
        
            self.input_string += key
            self.emoji_sequence.append(str(emoji))
            await interaction.response.edit_message(
                embed=self.build_embed(),
                view=self
            )
        
            if len(self.input_string) == 12:
                glyph = self.input_string
                self.emoji_sequence = self.emoji_sequence[:12]
                
                await interaction.followup.send("🔄 Validating glyph coordinate with Haven API...", ephemeral=True)
                
                try:
                    # 1. Fetch data from validation endpoint
                    valid = await self.api.validate_glyph(glyph)
                    if not valid.get("valid"):
                        self.reset_state()
                        await interaction.followup.send(
                            "❌ Invalid glyph code sequence. Please check your coordinate and try again.",
                            ephemeral=True
                        )
                        return

                    # Extract the actual API procedural/in-game name
                    api_generated_name = valid.get("system_name") or valid.get("generated_name") or valid.get("name") or "Unknown System"

                    # 2. Check for database duplicates
                    dup = await self.api.check_duplicate(glyph)
                    system_exists = dup.get("exists")
                    system_name = dup.get("system_name") or api_generated_name
                    system_id = dup.get("system_id")

                    # 3. Handle DISCOVERY Mode routing
                    if self.mode == "discovery":
                        msg = (
                            f"⚠️ System already exists: **{system_name}**"
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
                                    notes=None,
                                    reality=self.outer.reality
                                )
                                await interaction2.response.send_modal(modal)
                                self.stop()

                        view = ContinueView(self)
                        await interaction.followup.send(msg, view=view, ephemeral=True)
                        self.stop()
                        return

                    if system_exists:
                        await interaction.followup.send(
                            f"⚠️ This system has already been logged: **{system_name}**",
                            ephemeral=True
                        )
                        self.reset_state()
                        self.stop()
                        return

                    await interaction.followup.send(
                        f"🌐 **System Recognized by API:** `{api_generated_name}`\nSelect Reality:",
                        view=RealitySelectView(glyph, interaction.user.id, self.api, api_generated_name),
                        ephemeral=True
                    )
                    self.stop()

                except Exception as e:
                    await interaction.followup.send(f"❌ An error occurred during verification: {e}", ephemeral=True)
                    self.reset_state()

        return callback

    def reset_state(self):
        self.input_string = ""
        self.emoji_sequence = []

    async def backspace(self, interaction):
        self.input_string = self.input_string[:-1]
        self.emoji_sequence = self.emoji_sequence[:-1]

        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    embed=self.build_embed(),
                    view=self
                )
            else:
                await interaction.message.edit(
                    embed=self.build_embed(),
                    view=self
                )
        except:
            await interaction.message.edit(embed=self.build_embed(), view=self)

    async def reset(self, interaction):
        self.reset_state()

        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    embed=self.build_embed(),
                    view=self
                )
            else:
                await interaction.message.edit(
                    embed=self.build_embed(),
                    view=self
                )
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
    "F": discord.PartialEmoji(name="F", id=1487547868922249479)  
}

#---------------MANUAL READER---------------
#---------------MANUAL READER---------------
import asyncio  
import re

class HavenScraperCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.forum_channel_id = 1482814608745168916
        self.api = HavenAPI() 

    def parse_forum_template(self, content: str) -> dict:
        """Parses the structured text markdown template into an API payload."""
        
        def extract_field(pattern, text):
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1).strip() if match else None

        # Extract system data fields
        system_name = extract_field(r"\*\*System Name:\*\*\s*(.*)", content)
        glyphs = extract_field(r"\*\*Glyphs:\*\*\s*(.*)", content)
        system_class = extract_field(r"\*\*System class:\*\*\s*(.*)", content)
        galaxy = extract_field(r"\*\*Galaxy:\*\*\s*(.*)", content)
        
        # Validation for required fields ('r')
        if not all([system_name, glyphs, system_class, galaxy]):
            return None

        # Ensure Glyphs contain valid Hex strings
        cleaned_glyphs = re.sub(r'[^0-9A-Fa-f]', '', glyphs)
        if not cleaned_glyphs:
            return None

        # Gather optional fields
        payload = {
            "system_name": system_name,
            "glyph_code": cleaned_glyphs,
            "system_class": system_class,
            "galaxy_name": galaxy,
            "region": extract_field(r"\*\*Region:\*\*\s*(.*)", content) or "Unknown",
            "distance_from_core": extract_field(r"\*\*Distance From Core:\*\*\s*(.*)", content) or "Unknown",
            "dominant_lifeform": extract_field(r"\*\*Primary lifeform:\*\*\s*(.*)", content) or "Unknown",
            "economy": extract_field(r"\*\*Economy:\*\*\s*(.*)", content) or "Unknown",
            "conflict_level": extract_field(r"\*\*Conflict Level:\*\*\s*(.*)", content) or "Unknown",
            "stardate": extract_field(r"\*\*Stardate:\*\*\s*(.*)", content) or "Unknown",
            "planets": []
        }
        if "**Planets / Moons**" in content:
            planets_section = content.split("**Planets / Moons**")[1]
            planet_blocks = re.split(r"\*\s+\*\*(.*?)\*\*", planets_section)
            
            if len(planet_blocks) > 1:
                for i in range(1, len(planet_blocks), 2):
                    p_name = planet_blocks[i].strip()
                    p_body = planet_blocks[i+1] if i+1 < len(planet_blocks) else ""
                    
                    def extract_subfield(sub_pattern, text):
                        match = re.search(sub_pattern, text, re.IGNORECASE)
                        return match.group(1).strip() if match else "Unknown"

                    payload["planets"].append({
                        "name": p_name,
                        "biome": extract_subfield(r"-\s*Biome:\s*(.*)", p_body),
                        "weather": extract_subfield(r"\*\s*Weather:\s*(.*)", p_body),
                        "age": extract_subfield(r"\*\s*Age:\s*(.*)", p_body),
                        "atmosphere": extract_subfield(r"\*\s*Atmosphere:\s*(.*)", p_body),
                        "primary_core_element": extract_subfield(r"\*\s*Primary Core Element:\s*(.*)", p_body),
                        "sentinels": extract_subfield(r"\*\s*Sentinels:\s*(.*)", p_body),
                        "flora": extract_subfield(r"\*\s*Flora:\s*(.*)", p_body),
                        "fauna": extract_subfield(r"\*\s*Fauna:\s*(.*)", p_body),
                        "resources": extract_subfield(r"\*\s*Resources:\s*(.*)", p_body),
                        "outposts": extract_subfield(r"\*\s*Outposts:\s*(.*)", p_body),
                        "other_notes": extract_subfield(r"\*\s*Other Notes:\s*(.*)", p_body)
                    })

        return payload

    @commands.command(name="sync_forum")
    @commands.has_permissions(administrator=True)
    async def sync_forum(self, ctx: commands.Context):
        """Command to manually trigger a sync of all existing historical posts."""
        channel = self.bot.get_channel(self.forum_channel_id)
        if not channel or not isinstance(channel, discord.ForumChannel):
            await ctx.send("Target forum channel not found or invalid type.")
            return

        await ctx.send("Starting structural forum sync processing...")
        success_count = 0
        
        threads = channel.threads + [t async for t in channel.archived_threads()]
        for thread in threads:
            try:
                starter_message = thread.starter_message or await thread.fetch_message(thread.id)
            except discord.HTTPException:
                continue

            if any(r.me and r.emoji == "✅" for r in starter_message.reactions):
                continue

            payload = self.parse_forum_template(starter_message.content)
            if not payload:
                continue

            payload["submitted_by"] = starter_message.author.name

            try:
                await self.api.submit_system(payload)
                success_count += 1
                await starter_message.add_reaction("✅")
            except Exception as e:
                print(f"Failed to sync thread {thread.id}: {e}")
                try:
                    await starter_message.add_reaction("❌")
                except:
                    pass

        await ctx.send(f"Sync complete! Successfully submitted {success_count} structural logs to Haven API.")

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """Automatically fires and processes when a new structural post arrives."""
        if thread.parent_id != self.forum_channel_id:
            return

        await asyncio.sleep(3) 

        try:
            starter_message = thread.starter_message or await thread.fetch_message(thread.id)
        except discord.HTTPException as e:
            print(f"Failed to fetch live starter message {thread.id}: {e}")
            return

        payload = self.parse_forum_template(starter_message.content)
        if not payload:
            print(f"Live Thread {thread.id} skipped: Missing required fields or invalid hex glyphs.")
            return

        payload["submitted_by"] = starter_message.author.name

        try:
            await self.api.submit_system(payload)
            await starter_message.add_reaction("✅")
            print(f"Successfully auto-submitted structural log: {payload['system_name']}")
        except Exception as e:
            print(f"Failed to auto-submit live system {thread.id}: {e}")
            try:
                await starter_message.add_reaction("❌")
            except:
                pass
                   
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
    await bot.add_cog(HavenScraperCog(bot))  