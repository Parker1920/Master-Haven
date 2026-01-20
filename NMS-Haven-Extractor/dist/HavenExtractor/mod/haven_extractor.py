# /// script
# [tool.pymhf]
# exe = "NMS.exe"
# steam_gameid = 275850
# start_exe = true
# ///
"""
Haven Extractor v10.1.4 - Display formatting fixes for weather/biome

Extracts planet data from NMS and sends directly to Haven UI via API.
Features session configuration for user identification and community routing.

WORKFLOW:
1. Run the extractor - Config GUI appears on first launch
2. Enter Discord Username, Discord ID, Community Tag, Reality
3. Start the game and warp to systems - data captured automatically
4. Click "Export to Haven UI" to upload systems

GUI BUTTONS:
- Check System Data: Shows current system info in log
- Check Batch Data: Shows batch collection status in log
- Export to Haven UI: Opens export dialog with duplicate check

FEATURES:
- Direct API integration (no watcher needed)
- Pre-flight duplicate checking
- User identification (Discord username + ID)
- Community tag routing (Haven, IEA, personal, etc.)
- Reality mode support (Normal/Permadeath)

Data extracted per system:
- star_type, economy_type, economy_strength, conflict_level
- dominant_lifeform, planet count

Data extracted per planet:
- biome, biome_subtype, weather
- flora_level, fauna_level, sentinel_level
- common_resource, uncommon_resource, rare_resource
- is_moon, planet_size, planet_name
"""


import json
import logging
import time
import ctypes
import re
import urllib.request
import urllib.error
import ssl
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, List, Dict

from pymhf import Mod
from pymhf.core.memutils import map_struct, get_addressof
from pymhf.gui.decorators import gui_button, gui_combobox, gui_variable
import nmspy.data.types as nms
import nmspy.data.exported_types as nmse
from nmspy.decorators import on_state_change
from nmspy.common import gameData
from ctypes import c_uint64, pointer, sizeof

# NMS procedural name generation (ported from nms_namegen)
try:
    from nms_namegen.system import systemName as nms_system_name
    from nms_namegen.region import regionName as nms_region_name
    NMS_NAMEGEN_AVAILABLE = True
except ImportError:
    NMS_NAMEGEN_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# API CONFIGURATION - HARDCODED FOR DIST VERSION
# =============================================================================
# Direct API integration with Haven UI
# API key is embedded for the official Haven Extractor distribution
# =============================================================================
DEFAULT_API_URL = "https://voyagers-haven-3dmap.ngrok.io"
HAVEN_EXTRACTOR_API_KEY = "vh_live_HvnXtr8k9Lm2NpQ4rStUvWxYz1A3bC5dE7fG"

# Default user config (populated by config GUI)
DEFAULT_USER_CONFIG = {
    "discord_username": "",
    "personal_id": "",
    "discord_tag": "personal",
    "reality": "Normal",
}


# Note: Config GUI now uses pymhf's native DearPyGUI via gui_variable and gui_combobox decorators
# in the HavenExtractorMod class. See the class definition for config fields.


def load_config_from_file() -> dict:
    """
    Load configuration from config file only - NO GUI.
    This is safe to call at module load time.
    """
    config = {
        "api_url": DEFAULT_API_URL,
        "api_key": HAVEN_EXTRACTOR_API_KEY,
        "discord_username": "",
        "personal_id": "",
        "discord_tag": "personal",
        "reality": "Normal",
    }

    # Try loading from various locations
    config_locations = [
        Path(__file__).parent / "haven_config.json",  # Same folder as mod
        Path.home() / "Documents" / "Haven-Extractor" / "config.json",  # User documents
    ]

    for config_path in config_locations:
        try:
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    # Load all config fields
                    for key in config:
                        if key in file_config and file_config[key]:
                            config[key] = file_config[key]
                    logger.info(f"Loaded config from: {config_path}")
                    break
        except Exception as e:
            logger.debug(f"Could not load config from {config_path}: {e}")

    return config


def save_config(config: dict):
    """Save configuration to file."""
    save_path = Path.home() / "Documents" / "Haven-Extractor" / "config.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    logger.info(f"Saved user config to: {save_path}")


def config_needs_setup(config: dict) -> bool:
    """Check if configuration needs user setup (missing required fields)."""
    return not config.get("discord_username")


# Load config at module level - NO GUI (deferred to button/export)
_config = load_config_from_file()
API_BASE_URL = _config["api_url"]
API_KEY = _config["api_key"]
USER_DISCORD_USERNAME = _config.get("discord_username", "")
USER_PERSONAL_ID = _config.get("personal_id", "")
USER_DISCORD_TAG = _config.get("discord_tag", "personal")
USER_REALITY = _config.get("reality", "Normal")

# =============================================================================
# MEMORY OFFSET CONSTANTS (from MBINCompiler / NMS 4.13 PDB)
# These may need adjustment for different game versions
# =============================================================================

# GcSolarSystemData offsets (total size ~0x1F50)
class SolarSystemDataOffsets:
    """Offsets within cGcSolarSystemData struct."""
    PLANETS_COUNT = 0x2264        # int - total planet + moon count
    PRIME_PLANETS = 0x2268        # int - non-moon planet count
    STAR_CLASS = 0x224C           # GcSolarSystemClass enum
    STAR_TYPE = 0x2270            # GcGalaxyStarTypes enum
    NAME = 0x2274                 # cTkFixedString0x80 - system name (128 bytes)
    TRADING_DATA = 0x2240         # GcPlanetTradingData struct
    CONFLICT_DATA = 0x2250        # GcPlayerConflictData struct
    INHABITING_RACE = 0x2254      # GcAlienRace enum
    SEED = 0x21A0                 # GcSeed struct
    PLANET_GEN_INPUTS = 0x1EA0    # GcPlanetGenerationInputData[6] array

# GcPlanetTradingData offsets (nested at SolarSystemData + 0x2240)
class TradingDataOffsets:
    """Offsets within GcPlanetTradingData struct."""
    TRADING_CLASS = 0x0           # Economy type enum
    WEALTH_CLASS = 0x4            # Economy strength enum

# GcPlayerConflictData offsets (nested at SolarSystemData + 0x2250)
class ConflictDataOffsets:
    """Offsets within GcPlayerConflictData struct."""
    CONFLICT_LEVEL = 0x0          # Conflict level enum

# GcPlanetGenerationInputData offsets (size 0x53 per planet = 83 bytes)
class PlanetGenInputOffsets:
    """Offsets within GcPlanetGenerationInputData struct."""
    STRUCT_SIZE = 0x53            # Size of each planet gen input entry (83 bytes verified from nmspy)
    COMMON_SUBSTANCE = 0x00       # NMSString0x10
    RARE_SUBSTANCE = 0x10         # NMSString0x10
    SEED = 0x20                   # GcSeed
    BIOME = 0x30                  # GcBiomeType enum (4 bytes)
    BIOME_SUBTYPE = 0x34          # GcBiomeSubType enum
    PLANET_CLASS = 0x38           # GcPlanetClass enum
    PLANET_INDEX = 0x3C           # int
    PLANET_SIZE = 0x40            # GcPlanetSize enum (4 bytes)
    REALITY_INDEX = 0x44          # int (galaxy index)
    STAR_TYPE = 0x48              # GcGalaxyStarTypes enum

# =============================================================================
# ENUM VALUE MAPPINGS (from MBINCompiler)
# =============================================================================

BIOME_TYPES = {
    0: "Lush", 1: "Toxic", 2: "Scorched", 3: "Radioactive", 4: "Frozen",
    5: "Barren", 6: "Dead", 7: "Weird", 8: "Red", 9: "Green", 10: "Blue",
    11: "Test", 12: "Swamp", 13: "Lava", 14: "Waterworld", 15: "GasGiant", 16: "All"
}

# GcBiomeSubType enum values (from MBINCompiler/libMBIN - full 32 value enum)
# Mapped to user-friendly display names
BIOME_SUBTYPES = {
    0: "Standard",      # None_ -> Standard for display
    1: "Standard",      # Standard
    2: "High Quality",  # HighQuality
    3: "Exotic",        # Structure (exotic planet type)
    4: "Exotic",        # Beam (exotic planet type)
    5: "Exotic",        # Hexagon (exotic planet type)
    6: "Exotic",        # FractCube (exotic planet type)
    7: "Exotic",        # Bubble (exotic planet type)
    8: "Exotic",        # Shards (exotic planet type)
    9: "Exotic",        # Contour (exotic planet type)
    10: "Exotic",       # Shell (exotic planet type)
    11: "Exotic",       # BoneSpire (exotic planet type)
    12: "Exotic",       # WireCell (exotic planet type)
    13: "Exotic",       # HydroGarden (exotic planet type)
    14: "Mega Flora",   # HugePlant - large plants
    15: "Mega Flora",   # HugeLush - large lush vegetation
    16: "Mega Fauna",   # HugeRing - large ring formations
    17: "Mega Terrain", # HugeRock - large rock formations
    18: "Mega Terrain", # HugeScorch - large scorched terrain
    19: "Mega Toxic",   # HugeToxic - large toxic formations
    20: "Variant A",    # Variant_A
    21: "Variant B",    # Variant_B
    22: "Variant C",    # Variant_C
    23: "Variant D",    # Variant_D
    24: "Infested",     # Infested
    25: "Swamp",        # Swamp
    26: "Lava",         # Lava
    27: "Worlds",       # Worlds
    28: "Remix A",      # Remix_A
    29: "Remix B",      # Remix_B
    30: "Remix C",      # Remix_C
    31: "Remix D",      # Remix_D
}

PLANET_SIZES = {
    0: "Large", 1: "Medium", 2: "Small", 3: "Moon", 4: "Giant"
}

TRADING_CLASSES = {
    0: "Mining", 1: "HighTech", 2: "Trading", 3: "Manufacturing",
    4: "Fusion", 5: "Scientific", 6: "PowerGeneration"
}

WEALTH_CLASSES = {
    0: "Poor", 1: "Average", 2: "Wealthy", 3: "Pirate"
}

CONFLICT_LEVELS = {
    0: "Low", 1: "Default", 2: "High", 3: "Pirate"
}

ALIEN_RACES = {
    0: "Gek",
    1: "Vy'keen",
    2: "Korvax",
    3: "None",       # Robots/Sentinel systems
    4: "None",       # Atlas
    5: "None",       # Diplomats (unused)
    6: "None"        # Uninhabited
}

STAR_TYPES = {
    0: "Yellow", 1: "Red", 2: "Green", 3: "Blue"
}

# cGcWeatherOptions enum values (from nmspy/libMBIN - 17 values)
# This is used for planet_data.Weather.WeatherType (reliable for all planets)
WEATHER_OPTIONS = {
    0: "Clear",
    1: "Dust",
    2: "Humid",
    3: "Snow",
    4: "Toxic",
    5: "Scorched",
    6: "Radioactive",
    7: "RedWeather",
    8: "GreenWeather",
    9: "BlueWeather",
    10: "Swamp",
    11: "Lava",
    12: "Bubble",
    13: "Weird",
    14: "Fire",
    15: "ClearCold",
    16: "GasGiant",
}

# Storm frequency enum for weather data
STORM_FREQUENCY = {
    0: "None",
    1: "Low",
    2: "High",
    3: "Always",
}

# Resource ID to human-readable name mapping
RESOURCE_NAMES = {
    # Stellar metals (found in deposits)
    "YELLOW": "Copper",
    "YELLOW2": "Chromatic Metal",
    "RED": "Cadmium",
    "RED2": "Chromatic Metal",
    "GREEN": "Emeril",
    "GREEN2": "Chromatic Metal",
    "BLUE": "Indium",
    "BLUE2": "Chromatic Metal",
    "PURPLE": "Indium",
    "PURPLE2": "Indium",
    # Activated stellar metals (extreme weather planets)
    "EX_YELLOW": "Activated Copper",
    "EX_RED": "Activated Cadmium",
    "EX_GREEN": "Activated Emeril",
    "EX_BLUE": "Activated Indium",
    "EX_PURPLE": "Activated Indium",
    # Biome-specific resources
    "COLD1": "Dioxite",
    "SNOW1": "Dioxite",
    "HOT1": "Phosphorus",
    "LUSH1": "Paraffinium",
    "DUSTY1": "Pyrite",
    "TOXIC1": "Ammonia",
    "RADIO1": "Uranium",
    "SWAMP1": "Faecium",
    "LAVA1": "Basalt",
    "WEIRD1": "Magnetised Ferrite",
    # Common elements
    "FUEL1": "Carbon",
    "FUEL2": "Condensed Carbon",
    "LAND1": "Ferrite Dust",
    "LAND2": "Pure Ferrite",
    "LAND3": "Magnetised Ferrite",
    "OXYGEN": "Oxygen",
    "CATALYST1": "Sodium",
    "CATALYST2": "Sodium Nitrate",
    "LAUNCHSUB": "Di-hydrogen",
    "LAUNCHSUB2": "Di-hydrogen Jelly",
    "CAVE1": "Cobalt",
    "CAVE2": "Ionised Cobalt",
    "WATER1": "Salt",
    "WATER2": "Chlorine",
    "ASTEROID1": "Silver",
    "ASTEROID2": "Gold",
    "ASTEROID3": "Platinum",
    # Plant/Flora resources
    "PLANT_POOP": "Mordite",
    "PLANT_TOXIC": "Fungal Mould",
    "PLANT_SNOW": "Frost Crystal",
    "PLANT_HOT": "Solanium",
    "PLANT_RADIO": "Gamma Root",
    "PLANT_DUST": "Cactus Flesh",
    "PLANT_LUSH": "Star Bulb",
    "PLANT_CAVE": "Marrow Bulb",
    "PLANT_WATER": "Kelp Sac",
    # Rare resources
    "RARE1": "Rusted Metal",
    "RARE2": "Living Pearl",
    # Space/Anomaly resources
    "SPACEGUNK1": "Residual Goop",
    "SPACEGUNK2": "Runaway Mould",
    "SPACEGUNK3": "Living Slime",
    "SPACEGUNK4": "Viscous Fluids",
    "SPACEGUNK5": "Tainted Metal",
    # Special biome resources
    "ROBOT1": "Pugneum",
    "GAS1": "Nitrogen",
    "GAS2": "Sulphurine",
    "GAS3": "Radon",
}


def translate_resource(resource_id: str) -> str:
    """Translate a resource ID to human-readable name."""
    if not resource_id or resource_id == "Unknown" or resource_id == "":
        return resource_id
    # Direct lookup
    if resource_id in RESOURCE_NAMES:
        return RESOURCE_NAMES[resource_id]
    # Try uppercase
    if resource_id.upper() in RESOURCE_NAMES:
        return RESOURCE_NAMES[resource_id.upper()]
    # Return original if no mapping found
    return resource_id


def clean_weather_string(weather_str: str) -> str:
    """Clean raw weather strings like 'weather_glitch 6' to readable names.

    Maps raw game weather values to EXACT adjectives from Haven UI's
    weatherAdjectives list (adjectives.js) for consistent display.

    Valid weatherAdjectives include: Pleasant, Temperate, Hot, Extreme Heat,
    Humid, Frozen, Freezing, Radioactive, Anomalous, Arid, Airless, Clear, etc.
    """
    if not weather_str or weather_str == "Unknown" or weather_str == "":
        return weather_str

    # Values that are already valid weatherAdjectives (from adjectives.js)
    # Only include values that ACTUALLY exist in the weatherAdjectives list
    valid_adjectives = [
        "Clear", "Humid", "Radioactive", "Pleasant", "Temperate", "Mild",
        "Beautiful", "Blissful", "Balmy", "Frozen", "Freezing", "Cold", "Icy",
        "Arid", "Parched", "Hot", "Heated", "Extreme Heat", "Anomalous",
        "Airless", "No Atmosphere", "Inferno", "Toxic Rain", "Extreme Toxicity"
    ]
    if weather_str in valid_adjectives:
        return weather_str

    # Normalize: lowercase and replace spaces with underscores for matching
    normalized = weather_str.lower().replace(' ', '_')

    # Map raw weather values to EXACT weatherAdjectives from adjectives.js
    # These must match entries in Haven-UI/src/data/adjectives.js weatherAdjectives
    exact_mappings = {
        # Lush planet weather
        "weather_lush": "Pleasant",
        "weather lush": "Pleasant",
        "lush": "Pleasant",
        # Toxic planet weather
        "weather_toxic": "Toxic Rain",
        "toxic": "Toxic Rain",
        # Scorched/Hot planet weather
        "weather_scorched": "Extreme Heat",
        "weather_hot": "Extreme Heat",
        "weather_fire": "Inferno",
        "scorched": "Extreme Heat",
        # Radioactive planet weather
        "weather_radioactive": "Radioactive",
        "radioactive": "Radioactive",
        # Frozen/Cold planet weather
        "weather_frozen": "Frozen",
        "weather_cold": "Freezing",
        "weather_snow": "Frozen",
        "weather_blizzard": "Freezing",
        "frozen": "Frozen",
        "cold": "Freezing",
        # Barren/Dust planet weather
        "weather_barren": "Arid",
        "weather_dust": "Arid",
        "barren": "Arid",
        "dust": "Arid",
        # Dead planet weather
        "weather_dead": "Airless",
        "dead": "Airless",
        # Weird/Exotic planet weather
        "weather_weird": "Anomalous",
        "weather_glitch": "Anomalous",
        "weather_bubble": "Anomalous",
        "weird": "Anomalous",
        "glitch": "Anomalous",
        # Swamp planet weather
        "weather_swamp": "Humid",
        "swamp": "Humid",
        # Lava planet weather
        "weather_lava": "Inferno",
        "lava": "Inferno",
        # Humid weather
        "weather_humid": "Humid",
        "humid": "Humid",
        # Clear/Normal weather
        "weather_clear": "Clear",
        "weather_normal": "Temperate",
        "clear": "Clear",
        "normal": "Temperate",
        # Extreme weather
        "weather_extreme": "Extreme Heat",
        # Color-based exotic weather
        "redweather": "Anomalous",
        "greenweather": "Anomalous",
        "blueweather": "Anomalous",
    }

    if normalized in exact_mappings:
        return exact_mappings[normalized]

    # Try prefix matching for partial matches
    weather_prefix_mappings = {
        "weather_glitch": "Anomalous",
        "weather_lava": "Inferno",
        "weather_frozen": "Frozen",
        "weather_cold": "Freezing",
        "weather_hot": "Extreme Heat",
        "weather_toxic": "Toxic Rain",
        "weather_radioactive": "Radioactive",
        "weather_dust": "Arid",
        "weather_humid": "Humid",
        "weather_scorched": "Extreme Heat",
        "weather_swamp": "Humid",
        "weather_bubble": "Anomalous",
        "weather_weird": "Anomalous",
        "weather_fire": "Inferno",
        "weather_clear": "Clear",
        "weather_normal": "Temperate",
        "weather_snow": "Frozen",
        "weather_blizzard": "Freezing",
        "weather_extreme": "Extreme Heat",
        "weather_lush": "Pleasant",
    }

    for prefix, readable in weather_prefix_mappings.items():
        if normalized.startswith(prefix):
            return readable

    # Biome-based weather fallbacks using valid weatherAdjectives
    biome_weather_defaults = {
        "lush": "Pleasant",
        "toxic": "Toxic Rain",
        "scorched": "Extreme Heat",
        "radioactive": "Radioactive",
        "frozen": "Frozen",
        "barren": "Arid",
        "dead": "Airless",
        "weird": "Anomalous",
        "swamp": "Humid",
        "lava": "Inferno",
    }

    for biome, weather in biome_weather_defaults.items():
        if biome in normalized:
            return weather

    # Try to extract meaningful part (remove numbers and underscores)
    import re
    cleaned = re.sub(r'[_\d]+$', '', weather_str)  # Remove trailing numbers and underscores
    cleaned = cleaned.replace('_', ' ').strip()

    # Title case and return if we got something different
    if cleaned and cleaned.lower() != weather_str.lower():
        return cleaned.title()

    return weather_str


class HavenExtractorMod(Mod):
    __author__ = "Voyagers Haven"
    __version__ = "10.2.0"
    __description__ = "Batch mode planet data extraction with contextual adjectives"

    # ==========================================================================
    # CONTEXTUAL ADJECTIVE MAPPINGS (v10.2.0)
    # Uses valid adjectives from Haven UI's adjectives.js for variety
    # Selection is based on biome type + level for contextual accuracy
    # ==========================================================================

    # Flora level adjectives by biome type (from floraAdjectives in adjectives.js)
    FLORA_BY_BIOME = {
        # Lush biomes - varied vegetation descriptions
        "Lush": {0: "Absent", 1: "Occasional", 2: "Frequent", 3: "Lush"},
        "Swamp": {0: "Devoid", 1: "Sparse", 2: "Ample", 3: "Abundant"},
        # Harsh biomes - survival-focused descriptions
        "Toxic": {0: "None", 1: "Deficient", 2: "Limited", 3: "Moderate"},
        "Scorched": {0: "Nonexistent", 1: "Rare", 2: "Sparse", 3: "Typical"},
        "Radioactive": {0: "Absent", 1: "Uncommon", 2: "Regular", 3: "Common"},
        "Frozen": {0: "Empty", 1: "Lacking", 2: "Fair", 3: "Average"},
        # Barren/Dead - minimal vegetation
        "Barren": {0: "None", 1: "Sporadic", 2: "Infrequent", 3: "Occasional"},
        "Dead": {0: "Nonexistent", 1: "Not Present", 2: "Sparse", 3: "Rare"},
        # Exotic/Weird - unusual descriptions
        "Weird": {0: "Undetected", 1: "Unusual", 2: "Moderate", 3: "Bountiful"},
        "Red": {0: "Absent", 1: "Intermittent", 2: "Average", 3: "Rich"},
        "Green": {0: "Empty", 1: "Sparse", 2: "Regular", 3: "Generous"},
        "Blue": {0: "Devoid", 1: "Infrequent", 2: "Frequent", 3: "Full"},
        # Special biomes
        "Lava": {0: "None", 1: "Rare", 2: "Uncommon", 3: "Occasional"},
        "Waterworld": {0: "Absent", 1: "Sparse", 2: "Moderate", 3: "Copious"},
        "GasGiant": {0: "None", 1: "None", 2: "None", 3: "None"},
    }

    # Fauna level adjectives by biome type (from faunaAdjectives in adjectives.js)
    FAUNA_BY_BIOME = {
        # Lush biomes - abundant wildlife
        "Lush": {0: "Absent", 1: "Occasional", 2: "Frequent", 3: "Bountiful"},
        "Swamp": {0: "Devoid", 1: "Uncommon", 2: "Common", 3: "Copious"},
        # Harsh biomes - survival adaptations
        "Toxic": {0: "None", 1: "Rare", 2: "Average", 3: "Ample"},
        "Scorched": {0: "Empty", 1: "Sparse", 2: "Limited", 3: "Moderate"},
        "Radioactive": {0: "Nonexistent", 1: "Deficient", 2: "Regular", 3: "Typical"},
        "Frozen": {0: "Absent", 1: "Infrequent", 2: "Fair", 3: "Generous"},
        # Barren/Dead - minimal life
        "Barren": {0: "None", 1: "Rare", 2: "Sporadic", 3: "Occasional"},
        "Dead": {0: "Not Present", 1: "Lacking", 2: "Sparse", 3: "Few"},
        # Exotic/Weird - unusual fauna
        "Weird": {0: "Undetected", 1: "Unusual", 2: "Intermittent", 3: "Rich"},
        "Red": {0: "Empty", 1: "Uncommon", 2: "Average", 3: "Numerous"},
        "Green": {0: "Devoid", 1: "Infrequent", 2: "Frequent", 3: "Abundant"},
        "Blue": {0: "Absent", 1: "Sparse", 2: "Regular", 3: "Full"},
        # Special biomes
        "Lava": {0: "None", 1: "Rare", 2: "Sporadic", 3: "Few"},
        "Waterworld": {0: "Empty", 1: "Occasional", 2: "Common", 3: "Copious"},
        "GasGiant": {0: "None", 1: "None", 2: "None", 3: "None"},
    }

    # Sentinel level adjectives by biome type (from sentinelAdjectives in adjectives.js)
    SENTINEL_BY_BIOME = {
        # Lush biomes - typically lower security
        "Lush": {0: "None Present", 1: "Low Security", 2: "Observant", 3: "Aggressive"},
        "Swamp": {0: "Absent", 1: "Few", 2: "Frequent", 3: "Hateful"},
        # Harsh biomes - often higher security
        "Toxic": {0: "Missing", 1: "Infrequent", 2: "Attentive", 3: "Frenzied"},
        "Scorched": {0: "Not Present", 1: "Sparse", 2: "Regular Patrols", 3: "Threatening"},
        "Radioactive": {0: "None", 1: "Limited", 2: "Hostile Patrols", 3: "Zealous"},
        "Frozen": {0: "Absent", 1: "Intermittent", 2: "High Security", 3: "Enforcing"},
        # Barren/Dead - variable
        "Barren": {0: "Missing", 1: "Remote", 2: "Spread Thin", 3: "Unwavering"},
        "Dead": {0: "None Present", 1: "Isolated", 2: "Infrequent", 3: "Hateful"},
        # Exotic/Weird - unusual behavior
        "Weird": {0: "Forsaken", 1: "Irregular Patrols", 2: "Normal", 3: "Malicious"},
        "Red": {0: "Absent", 1: "Low", 2: "Observant", 3: "Aggressive"},
        "Green": {0: "Not Present", 1: "Few", 2: "Attentive", 3: "Zealous"},
        "Blue": {0: "None", 1: "Sparse", 2: "Frequent", 3: "Threatening"},
        # Special biomes
        "Lava": {0: "Missing", 1: "Few", 2: "Hostile Patrols", 3: "Frenzied"},
        "Waterworld": {0: "Absent", 1: "Low", 2: "Limited", 3: "Enforcing"},
        "GasGiant": {0: "None", 1: "None", 2: "None", 3: "None"},
    }

    # Weather adjectives by biome + storm frequency (from weatherAdjectives in adjectives.js)
    # Key: (biome, weather_enum, storm_frequency) -> adjective
    # Storm frequency: 0=None, 1=Low, 2=High, 3=Always
    WEATHER_CONTEXTUAL = {
        # Lush biomes
        ("Lush", 0, 0): "Peaceful",       # Clear, no storms
        ("Lush", 0, 1): "Mild",           # Clear, low storms
        ("Lush", 2, 0): "Humid",          # Humid, no storms
        ("Lush", 2, 1): "Tropical Storms", # Humid, low storms
        ("Lush", 2, 2): "Heavy Rain",     # Humid, high storms
        # Toxic biomes
        ("Toxic", 4, 0): "Toxic Clouds",  # Toxic, no storms
        ("Toxic", 4, 1): "Toxic Rain",    # Toxic, low storms
        ("Toxic", 4, 2): "Toxic Superstorms", # Toxic, high storms
        ("Toxic", 4, 3): "Extreme Toxicity", # Toxic, constant storms
        # Scorched biomes
        ("Scorched", 5, 0): "Hot",        # Scorched, no storms
        ("Scorched", 5, 1): "Heated Atmosphere", # Scorched, low storms
        ("Scorched", 5, 2): "Firestorms", # Scorched, high storms
        ("Scorched", 5, 3): "Inferno",    # Scorched, constant storms
        ("Scorched", 14, 2): "Walls of Flame", # Fire weather
        ("Scorched", 14, 3): "Colossal Firestorms",
        # Radioactive biomes
        ("Radioactive", 6, 0): "Radioactive",
        ("Radioactive", 6, 1): "Irradiated",
        ("Radioactive", 6, 2): "Radioactive Storms",
        ("Radioactive", 6, 3): "Extreme Radioactivity",
        # Frozen biomes
        ("Frozen", 3, 0): "Frozen",       # Snow, no storms
        ("Frozen", 3, 1): "Freezing",     # Snow, low storms
        ("Frozen", 3, 2): "Blizzard",     # Snow, high storms
        ("Frozen", 3, 3): "Extreme Cold", # Snow, constant storms
        ("Frozen", 15, 0): "Icy",         # ClearCold
        ("Frozen", 15, 1): "Frozen Clouds",
        # Barren/Dead
        ("Barren", 1, 0): "Arid",         # Dust, no storms
        ("Barren", 1, 1): "Dusty",        # Dust, low storms
        ("Barren", 1, 2): "Sandstorms",   # Dust, high storms
        ("Dead", 0, 0): "Airless",
        ("Dead", 0, 1): "No Atmosphere",
        # Swamp
        ("Swamp", 10, 0): "Humid",
        ("Swamp", 10, 1): "Damp",
        ("Swamp", 10, 2): "Monsoon",
        ("Swamp", 10, 3): "Choking Humidity",
        # Lava
        ("Lava", 11, 0): "Molten",
        ("Lava", 11, 1): "Magma Geysers",
        ("Lava", 11, 2): "Magma Rain",
        ("Lava", 11, 3): "Inferno",
        # Exotic/Weird
        ("Weird", 13, 0): "Anomalous",
        ("Weird", 13, 1): "Unstable",
        ("Weird", 13, 2): "Unfathomable Storms",
        ("Weird", 12, 0): "Anomalous",    # Bubble weather
    }

    # Fallback mappings (simple level-based, used when biome not found)
    FLORA_LEVELS = {0: "None", 1: "Sparse", 2: "Average", 3: "Bountiful"}
    FAUNA_LEVELS = {0: "None", 1: "Scarce", 2: "Regular", 3: "Copious"}
    # Legacy mapping for compatibility
    LIFE_LEVELS = {0: "None", 1: "Sparse", 2: "Average", 3: "Abundant"}
    # Sentinel activity levels
    SENTINEL_LEVELS = {0: "Minimal", 1: "Limited", 2: "High", 3: "Aggressive"}

    # v10.2.0: Convert WEATHER_OPTIONS internal names to user-friendly adjectives
    # Used when WEATHER_CONTEXTUAL doesn't have a specific entry
    WEATHER_FALLBACK = {
        "Clear": "Pleasant",
        "Dust": "Arid",
        "Humid": "Humid",
        "Snow": "Frozen",
        "Toxic": "Toxic Rain",
        "Scorched": "Extreme Heat",
        "Radioactive": "Radioactive",
        "RedWeather": "Anomalous",
        "GreenWeather": "Anomalous",
        "BlueWeather": "Anomalous",
        "Swamp": "Humid",
        "Lava": "Inferno",
        "Bubble": "Anomalous",
        "Weird": "Anomalous",
        "Fire": "Inferno",
        "ClearCold": "Icy",
        "GasGiant": "No Atmosphere",
    }

    # =========================================================================
    # CONFIG GUI FIELDS - Using pymhf's native DearPyGUI
    # These appear as editable fields in the mod's GUI tab
    # =========================================================================

    @property
    @gui_variable.STRING(label="Discord Username")
    def discord_username(self) -> str:
        return self._discord_username

    @discord_username.setter
    def discord_username(self, value: str):
        global USER_DISCORD_USERNAME
        self._discord_username = value
        USER_DISCORD_USERNAME = value
        self._save_config_to_file()

    # All community partner tags - alphabetically sorted by display name
    COMMUNITY_TAGS = [
        "personal",      # Independent Explorers (default)
        "Haven",         # Haven Hub
        "AGT",           # Alliance of Galactic Travelers
        "ARCH",          # ARCH
        "AA",            # AstroAcutioneer
        "AP",            # Aurelis Prime
        "B.E.S",         # B.E.S
        "YGS",           # Circle of Yggdrasil
        "CR",            # Crimson Runners
        "EVRN",          # EVRN
        "GHUB",          # Galactic Hub Project
        "IEA",           # IEA
        "NEO",           # Neo Terra Collective
        "O.Q",           # Outskirt Queers
        "Ph-Z0",         # Phantom-Zer0
        "QRR",           # The Quasar Republic Reforged
        "RwR",           # Red Water Runners
        "SHDW",          # Shadow Worlds
        "Veil1",         # Soren Veil
        "TBH",           # T-BH (The Black Hole)
        "INDM",          # The Indominus Legion
        "TMA",           # The Mourning Amity
        "UFE",           # UltimateFeudEnterprise
        "VCTH",          # Void Citadel
        "ZBA",           # Zabia
    ]

    @gui_combobox("Community Tag", items=COMMUNITY_TAGS)
    def set_discord_tag(self, sender, app_data, user_data=None):
        """Called when user selects a community tag from dropdown.
        DearPyGUI callback signature: (sender, app_data, user_data)
        app_data contains the selected string value.
        """
        global USER_DISCORD_TAG
        tag = app_data  # The selected tag string
        self._discord_tag = tag
        USER_DISCORD_TAG = tag
        self._save_config_to_file()
        logger.info(f"[CONFIG] Community tag set to: {tag}")

    @gui_combobox("Reality Mode", items=["Normal", "Permadeath"])
    def set_reality(self, sender, app_data, user_data=None):
        """Called when user selects reality mode from dropdown.
        DearPyGUI callback signature: (sender, app_data, user_data)
        app_data contains the selected string value.
        """
        global USER_REALITY
        reality = app_data  # The selected reality string
        self._reality = reality
        USER_REALITY = reality
        self._save_config_to_file()
        logger.info(f"[CONFIG] Reality mode set to: {reality}")

    # =========================================================================
    # MANUAL SYSTEM NAME INPUT
    # Since automatic name extraction doesn't work reliably, users can manually
    # enter the system name they see in-game.
    # =========================================================================

    @property
    @gui_variable.STRING(label="Manual System Name")
    def manual_system_name(self) -> str:
        return getattr(self, '_manual_system_name', '')

    @manual_system_name.setter
    def manual_system_name(self, value: str):
        self._manual_system_name = value

    @gui_button("Apply System Name")
    def apply_manual_system_name(self):
        """Apply the manually entered system name to the current system."""
        name = getattr(self, '_manual_system_name', '').strip()
        if not name:
            logger.warning("[MANUAL] No system name entered. Type the name in 'Manual System Name' field first.")
            return

        # Update the current system coordinates
        if self._current_system_coords:
            old_name = self._current_system_coords.get('system_name', 'Unknown')
            self._current_system_coords['system_name'] = name
            logger.info(f"[MANUAL] System name updated: '{old_name}' -> '{name}'")
            logger.info(f"[MANUAL] This name will be used when the system is saved to batch.")
        else:
            logger.warning("[MANUAL] No current system data. Warp to a system first.")
            return

        # Clear the input field
        self._manual_system_name = ''
        logger.info(f"[MANUAL] System name '{name}' applied successfully!")

    def _save_config_to_file(self):
        """Save current config to file."""
        try:
            config = {
                "api_url": DEFAULT_API_URL,
                "api_key": HAVEN_EXTRACTOR_API_KEY,
                "discord_username": self._discord_username,
                "personal_id": self._personal_id,
                "discord_tag": self._discord_tag,
                "reality": self._reality,
            }
            save_config(config)
        except Exception as e:
            logger.debug(f"Could not save config: {e}")

    def __init__(self):
        super().__init__()
        self._output_dir = Path.home() / "Documents" / "Haven-Extractor"
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize config fields from loaded config
        self._discord_username = USER_DISCORD_USERNAME
        self._personal_id = USER_PERSONAL_ID  # Discord snowflake ID for tracking
        self._discord_tag = USER_DISCORD_TAG
        self._reality = USER_REALITY
        self._manual_system_name = ''  # For manual system name input

        self._pending_extraction = False
        self._last_extracted_seed = None
        self._cached_solar_system = None
        self._cached_sys_data_addr = None  # Cache the sys_data address for direct reads

        # Debouncing - don't re-extract more often than this
        self._last_extraction_time = 0
        self._extraction_debounce_seconds = 3

        # =====================================================
        # CRITICAL v8.1.0: Captured planet data from GenerateCreatureRoles hook
        # This dictionary stores Flora, Fauna, Sentinels captured by the hook
        # Key: planet_index, Value: dict with captured data
        # =====================================================
        self._captured_planets = {}
        self._capture_enabled = False  # Only capture after system generates

        # =====================================================
        # v8.2.0: BATCH MODE - Store multiple star systems
        # Allows collecting data from many systems before export
        # =====================================================
        self._batch_systems = []  # List of completed system extractions
        self._current_system_coords = None  # Coords captured when entering system
        self._current_system_props = None  # System properties captured when entering
        self._batch_mode_enabled = True  # Enable batch collection by default

        # =====================================================
        # Track if current system has been saved to batch
        # Prevents duplicate saves
        # =====================================================
        self._system_saved_to_batch = False

        logger.info("=" * 60)
        logger.info("Haven Extractor v10.1.4 - Direct API Integration")
        logger.info(f"Local backup: {self._output_dir}")
        logger.info("=" * 60)
        logger.info("")
        logger.info("*** CONFIGURATION ***")
        logger.info("Use the text fields and dropdowns above to set:")
        logger.info("  - Discord Username (required)")
        logger.info("  - Discord ID (18-digit, optional)")
        logger.info("  - Community Tag (dropdown)")
        logger.info("  - Reality Mode (dropdown)")
        logger.info("")
        logger.info("*** WORKFLOW ***")
        logger.info("1. Enter your Discord username above")
        logger.info("2. Warp to systems - data captured automatically")
        logger.info("3. Click 'Export to Haven UI' when ready")
        logger.info("=" * 60)


    # =========================================================================
    # DIRECT MEMORY READ UTILITIES
    # =========================================================================

    def _read_int32(self, base_addr: int, offset: int) -> int:
        """Read a 32-bit integer from memory at base + offset."""
        try:
            addr = base_addr + offset
            # Use ctypes to read from process memory
            value = ctypes.c_int32()
            ctypes.memmove(ctypes.addressof(value), addr, 4)
            return value.value
        except Exception as e:
            logger.debug(f"Failed to read int32 at 0x{base_addr:X}+0x{offset:X}: {e}")
            return 0

    def _read_uint32(self, base_addr: int, offset: int) -> int:
        """Read a 32-bit unsigned integer from memory at base + offset."""
        try:
            addr = base_addr + offset
            value = ctypes.c_uint32()
            ctypes.memmove(ctypes.addressof(value), addr, 4)
            return value.value
        except Exception as e:
            logger.debug(f"Failed to read uint32 at 0x{base_addr:X}+0x{offset:X}: {e}")
            return 0

    def _read_string(self, base_addr: int, offset: int, max_len: int = 16) -> str:
        """Read a null-terminated string from memory."""
        try:
            addr = base_addr + offset
            buffer = ctypes.create_string_buffer(max_len)
            ctypes.memmove(buffer, addr, max_len)
            # Decode and strip null terminator
            raw = buffer.raw
            null_pos = raw.find(b'\x00')
            if null_pos >= 0:
                raw = raw[:null_pos]
            return raw.decode('utf-8', errors='ignore').strip()
        except Exception as e:
            logger.debug(f"Failed to read string at 0x{base_addr:X}+0x{offset:X}: {e}")
            return ""

    def _read_system_data_direct(self, sys_data_addr: int) -> dict:
        """Read solar system data using direct memory offsets."""
        result = {
            "system_name": "",
            "star_color": "Unknown",
            "economy_type": "Unknown",
            "economy_strength": "Unknown",
            "conflict_level": "Unknown",
            "dominant_lifeform": "Unknown",
            "system_seed": 0,
            "planet_count": 0,
            "prime_planets": 0,
        }

        try:
            # Read system name (128-byte fixed string at offset 0x2274)
            system_name = self._read_string(sys_data_addr, SolarSystemDataOffsets.NAME, max_len=128)
            if system_name:
                result["system_name"] = system_name
                logger.info(f"  [DIRECT] System name: {system_name}")

            # Read planet counts
            result["planet_count"] = self._read_int32(sys_data_addr, SolarSystemDataOffsets.PLANETS_COUNT)
            result["prime_planets"] = self._read_int32(sys_data_addr, SolarSystemDataOffsets.PRIME_PLANETS)
            logger.info(f"  [DIRECT] Planet count: {result['planet_count']}, Prime: {result['prime_planets']}")

            # Read star type (now called star_color)
            star_type_val = self._read_uint32(sys_data_addr, SolarSystemDataOffsets.STAR_TYPE)
            result["star_color"] = STAR_TYPES.get(star_type_val, f"Unknown({star_type_val})")
            logger.info(f"  [DIRECT] Star color: {result['star_color']} (raw: {star_type_val})")

            # Read trading data (economy)
            trading_addr = sys_data_addr + SolarSystemDataOffsets.TRADING_DATA
            trading_class = self._read_uint32(trading_addr, TradingDataOffsets.TRADING_CLASS)
            wealth_class = self._read_uint32(trading_addr, TradingDataOffsets.WEALTH_CLASS)
            result["economy_type"] = TRADING_CLASSES.get(trading_class, f"Unknown({trading_class})")
            result["economy_strength"] = WEALTH_CLASSES.get(wealth_class, f"Unknown({wealth_class})")
            logger.info(f"  [DIRECT] Economy: {result['economy_type']} / {result['economy_strength']} (raw: {trading_class}/{wealth_class})")

            # Read conflict data
            conflict_addr = sys_data_addr + SolarSystemDataOffsets.CONFLICT_DATA
            conflict_val = self._read_uint32(conflict_addr, ConflictDataOffsets.CONFLICT_LEVEL)
            result["conflict_level"] = CONFLICT_LEVELS.get(conflict_val, f"Unknown({conflict_val})")
            logger.info(f"  [DIRECT] Conflict: {result['conflict_level']} (raw: {conflict_val})")

            # Read dominant race
            race_val = self._read_uint32(sys_data_addr, SolarSystemDataOffsets.INHABITING_RACE)
            result["dominant_lifeform"] = ALIEN_RACES.get(race_val, f"Unknown({race_val})")
            logger.info(f"  [DIRECT] Race: {result['dominant_lifeform']} (raw: {race_val})")

        except Exception as e:
            logger.error(f"Direct system data read failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return result

    def _read_planet_gen_input_direct(self, sys_data_addr: int, planet_index: int) -> dict:
        """Read planet generation input data using direct offsets."""
        result = {
            "biome": "Unknown",
            "biome_raw": -1,
            "biome_subtype": "Unknown",
            "biome_subtype_raw": -1,
            "planet_size": "Unknown",
            "planet_size_raw": -1,
            "is_moon": False,
            "common_resource": "",
            "rare_resource": "",
        }

        try:
            # Calculate address for this planet's gen input data
            # Array starts at PLANET_GEN_INPUTS, each entry is STRUCT_SIZE bytes
            planet_gen_addr = sys_data_addr + SolarSystemDataOffsets.PLANET_GEN_INPUTS
            planet_gen_addr += planet_index * PlanetGenInputOffsets.STRUCT_SIZE

            logger.info(f"    [DIRECT] Planet {planet_index} gen input at 0x{planet_gen_addr:X}")

            # Read biome
            biome_val = self._read_uint32(planet_gen_addr, PlanetGenInputOffsets.BIOME)
            result["biome_raw"] = biome_val
            result["biome"] = BIOME_TYPES.get(biome_val, f"Unknown({biome_val})")
            logger.info(f"    [DIRECT] Biome: {result['biome']} (raw: {biome_val})")

            # Read biome subtype
            biome_subtype_val = self._read_uint32(planet_gen_addr, PlanetGenInputOffsets.BIOME_SUBTYPE)
            result["biome_subtype_raw"] = biome_subtype_val
            result["biome_subtype"] = BIOME_SUBTYPES.get(biome_subtype_val, f"Unknown({biome_subtype_val})")
            logger.info(f"    [DIRECT] BiomeSubType: {result['biome_subtype']} (raw: {biome_subtype_val})")

            # Read planet size (critical for moon detection)
            size_val = self._read_uint32(planet_gen_addr, PlanetGenInputOffsets.PLANET_SIZE)
            result["planet_size_raw"] = size_val
            result["planet_size"] = PLANET_SIZES.get(size_val, f"Unknown({size_val})")
            result["is_moon"] = (size_val == 3)  # Moon = 3
            logger.info(f"    [DIRECT] Size: {result['planet_size']} (raw: {size_val}, is_moon: {result['is_moon']})")

            # Read resources (16-byte strings) and translate to human-readable names
            raw_common = self._read_string(planet_gen_addr, PlanetGenInputOffsets.COMMON_SUBSTANCE, 16)
            raw_rare = self._read_string(planet_gen_addr, PlanetGenInputOffsets.RARE_SUBSTANCE, 16)
            result["common_resource"] = translate_resource(raw_common)
            result["rare_resource"] = translate_resource(raw_rare)
            logger.info(f"    [DIRECT] Resources: common={result['common_resource']} ({raw_common}), rare={result['rare_resource']} ({raw_rare})")

        except Exception as e:
            logger.error(f"Direct planet gen input read failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        return result

    # =========================================================================
    # UTILITY FUNCTIONS
    # =========================================================================

    def _safe_float(self, val, default: float = 0.0) -> float:
        """Safely convert a value to float."""
        if val is None:
            return default
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    def _safe_enum(self, val, default: str = "Unknown") -> str:
        """Safely get enum name."""
        if val is None:
            return default
        if hasattr(val, 'name'):
            return str(val.name)
        if hasattr(val, 'value'):
            return str(val.value)
        return str(val)

    # =========================================================================
    # v8.2.0: BATCH MODE - Save current system to batch storage
    # =========================================================================

    def _save_current_system_to_batch(self):
        """
        Save the current system's captured data to batch storage.
        Called automatically when warping to a new system.
        """
        # Skip if batch mode disabled or no captured data
        if not self._batch_mode_enabled:
            return
        if not self._captured_planets:
            logger.debug("[BATCH] No captured planets to save")
            return
        if not self._cached_solar_system:
            logger.debug("[BATCH] No cached solar system to save")
            return

        try:
            # Get coordinates for the system we're leaving
            coords = self._get_current_coordinates()
            if not coords:
                logger.warning("[BATCH] Could not get coordinates for batch save")
                return

            # Check if this system is already in batch (by glyph code)
            glyph_code = coords.get('glyph_code', '')
            for existing in self._batch_systems:
                if existing.get('glyph_code') == glyph_code:
                    logger.info(f"[BATCH] System {glyph_code} already in batch, skipping duplicate")
                    return

            # Get system data
            sys_data = self._cached_solar_system.mSolarSystemData

            # Build the system extraction
            data_source = "captured_hook" if len(self._captured_planets) > 0 else "memory_read"

            # Get system properties (includes system_name from memory)
            sys_props = self._extract_system_properties(sys_data)

            # Preserve manual system name from coords if set (takes priority over memory read)
            manual_name = coords.get('system_name', '')
            has_manual_name = manual_name and not manual_name.startswith('System_')

            system_data = {
                "extraction_time": datetime.now().isoformat(),
                "extractor_version": "10.0.0",
                "trigger": "batch_auto_save",
                "source": "live_extraction",
                "data_source": data_source,
                "captured_planet_count": len(self._captured_planets),
                "discoverer_name": "HavenExtractor",
                "discovery_timestamp": int(datetime.now().timestamp()),
                **sys_props,  # System properties from memory first
                **coords,     # Coords AFTER so manual name overwrites
                "planets": self._extract_planets(self._cached_solar_system),
            }
            system_data["planet_count"] = len(system_data["planets"])

            # If we have a manual name, use it and skip other lookups
            if has_manual_name:
                system_data['system_name'] = manual_name
                logger.info(f"[BATCH] Using manual system name: '{manual_name}'")
            # Otherwise try to get actual system name (might be populated by batch save time)
            elif not system_data.get('system_name') or system_data['system_name'].startswith('System_'):
                # Try reading from Name field (might be populated now)
                actual_name = self._get_actual_system_name()
                if actual_name:
                    system_data['system_name'] = actual_name
                    logger.info(f"[BATCH] Got actual system name: '{actual_name}'")
                else:
                    # Try game state notification string
                    try:
                        game_state = gameData.game_state
                        if game_state:
                            gs_addr = get_addressof(game_state)
                            if gs_addr:
                                notif = self._read_string(gs_addr, 0x38, max_len=256)
                                if notif:
                                    match = re.match(r"In the (.+) system", notif)
                                    if match:
                                        system_data['system_name'] = match.group(1).strip()
                                        logger.info(f"[BATCH] Got name from game state: '{system_data['system_name']}'")
                    except Exception:
                        pass

            # Use glyph-based fallback if system_name is still empty
            if not system_data.get('system_name') or system_data['system_name'].startswith('System_'):
                system_data['system_name'] = f"System_{glyph_code}"

            # Add to batch
            self._batch_systems.append(system_data)

            logger.info("")
            logger.info("*" * 60)
            logger.info(f">>> [BATCH] SYSTEM SAVED TO BATCH! <<<")
            logger.info(f"    Glyph: {glyph_code}")
            logger.info(f"    Planets: {system_data['planet_count']}")
            logger.info(f"    Total systems in batch: {len(self._batch_systems)}")
            logger.info("*" * 60)
            logger.info("")

        except Exception as e:
            logger.error(f"[BATCH] Failed to save system to batch: {e}")
            import traceback
            logger.error(traceback.format_exc())

    @nms.cGcSolarSystem.Generate.after
    def on_system_generate(self, this, lbUseSettingsFile, lSeed):
        """Fires AFTER solar system generation - data is now ready."""
        logger.info("")
        logger.info("=== NEW SYSTEM DETECTED ===")

        # =====================================================
        # v8.2.0: BATCH MODE - Save previous system BEFORE clearing!
        # This preserves the data from the system we just left
        # =====================================================
        if self._batch_mode_enabled and self._captured_planets and not self._system_saved_to_batch:
            logger.info("  Saving previous system to batch...")
            self._save_current_system_to_batch()

        addr = get_addressof(this)
        if addr == 0:
            return

        try:
            self._cached_solar_system = map_struct(addr, nms.cGcSolarSystem)
            self._pending_extraction = True

            # =====================================================
            # v10.0.7: Try multiple sources for coordinates
            # 1. gameData.player_state.mLocation (if available)
            # 2. mUniverseAddress from planet discovery data (packed uint64)
            # =====================================================
            self._current_system_coords = None
            self._current_system_name = None  # v10.0.7: Store system name separately

            # v10.0.12: System name is procedurally generated from seed, not stored in Name field
            # The Name field is only populated for user-renamed systems
            # We'll use the glyph code as the system identifier
            self._current_system_name = None  # Will be set from glyph code later

            galaxy_names = {
                0: "Euclid", 1: "Hilbert Dimension", 2: "Calypso",
                3: "Hesperius Dimension", 4: "Hyades", 5: "Ickjamatew",
                6: "Budullangr", 7: "Kikolgallr", 8: "Eltiensleen",
                9: "Eissentam", 10: "Elkupalos",
            }

            # Method 1: Try player_state (usually None during warp)
            try:
                player_state = gameData.player_state
                if player_state:
                    location = player_state.mLocation
                    galactic_addr = location.GalacticAddress

                    voxel_x = self._safe_int(galactic_addr.VoxelX)
                    voxel_y = self._safe_int(galactic_addr.VoxelY)
                    voxel_z = self._safe_int(galactic_addr.VoxelZ)
                    system_idx = self._safe_int(galactic_addr.SolarSystemIndex)
                    planet_idx = self._safe_int(galactic_addr.PlanetIndex)
                    galaxy_idx = self._safe_int(location.RealityIndex)

                    # DEBUG: Log raw values from GalacticAddress struct
                    logger.info(f"  [DEBUG] GalacticAddress struct fields:")
                    logger.info(f"    VoxelX={voxel_x}, VoxelY={voxel_y}, VoxelZ={voxel_z}")
                    logger.info(f"    SolarSystemIndex={system_idx}, PlanetIndex={planet_idx}, Galaxy={galaxy_idx}")
                    # Calculate what portal/region values these produce
                    dbg_px = (voxel_x + 2047) & 0xFFF
                    dbg_py = (voxel_y + 127) & 0xFF
                    dbg_pz = (voxel_z + 2047) & 0xFFF
                    logger.info(f"    -> Region coords: [{dbg_px}, {dbg_py}, {dbg_pz}]")

                    if galaxy_idx < 0 or galaxy_idx > 255:
                        galaxy_idx = 0

                    galaxy_name = galaxy_names.get(galaxy_idx, f"Galaxy_{galaxy_idx}")
                    glyph_code = self._coords_to_glyphs(planet_idx, system_idx, voxel_x, voxel_y, voxel_z)

                    # Get actual system name from mGameState
                    system_name = self._get_actual_system_name()
                    if not system_name:
                        system_name = f"System_{glyph_code}"
                    region_name = f"Region_{glyph_code[:4]}"
                    self._current_system_coords = {
                        "system_name": system_name,
                        "region_name": region_name,
                        "glyph_code": glyph_code,
                        "galaxy_name": galaxy_name,
                        "galaxy_index": galaxy_idx,
                        "voxel_x": voxel_x,
                        "voxel_y": voxel_y,
                        "voxel_z": voxel_z,
                        "solar_system_index": system_idx,
                    }
                    logger.info(f"  [SUCCESS via Method 1] Cached coords: '{system_name}' in '{region_name}' @ {glyph_code} ({galaxy_name})")
            except Exception as e:
                logger.debug(f"  [v10.0.5] player_state method failed: {e}")

            # Method 2: Try mUniverseAddress from planet discovery data (packed uint64)
            # Note: Planets may not be fully initialized at this point - that's OK, we'll try again later
            if self._current_system_coords is None:
                try:
                    # Access first planet's discovery data
                    planets = self._cached_solar_system.maPlanets
                    first_planet = planets[0]
                    discovery_data = first_planet.mPlanetDiscoveryData

                    # mUniverseAddress is a packed c_uint64, not a struct pointer
                    universe_addr = self._safe_int(discovery_data.mUniverseAddress)

                    # Skip if uninitialized (all 1s or 0) - expected during system generate
                    if universe_addr == 0 or universe_addr == 0xFFFFFFFFFFFFFFFF:
                        raise ValueError("Uninitialized mUniverseAddress")

                    # v10.1.0: CORRECT bit layout for mUniverseAddress (verified via diagnostic)
                    # mUniverseAddress stores REGION coordinates DIRECTLY, not signed voxel offsets!
                    # Diagnostic proved: 0x001126000193DFA9 contains Sea of Gidzenuf [4009, 1, 2365]
                    #
                    # Bits 0-11:  X region (direct, 0-4095)
                    # Bits 12-23: Z region (direct, 0-4095)
                    # Bits 24-31: Y region (direct, 0-255)
                    # Bits 32-39: (padding/unused)
                    # Bits 40-51: SolarSystemIndex (12 bits)
                    # Bits 52-55: PlanetIndex + 1 (4 bits, stored as planet+1)
                    # Bits 56-63: Galaxy index (8 bits)

                    x_region = universe_addr & 0xFFF
                    z_region = (universe_addr >> 12) & 0xFFF
                    y_region = (universe_addr >> 24) & 0xFF
                    system_idx = (universe_addr >> 40) & 0xFFF
                    planet_idx_raw = (universe_addr >> 52) & 0xF
                    planet_idx = max(0, planet_idx_raw - 1)  # Stored as planet+1
                    galaxy_idx = (universe_addr >> 56) & 0xFF

                    # DEBUG: Log raw packed address decode
                    logger.info(f"  [DEBUG] mUniverseAddress packed decode (Method 2) - v10.1.0 CORRECT layout:")
                    logger.info(f"    Raw addr: 0x{universe_addr:016X}")
                    logger.info(f"    x_region={x_region} (0x{x_region:03X}), y_region={y_region} (0x{y_region:02X}), z_region={z_region} (0x{z_region:03X})")
                    logger.info(f"    system_idx={system_idx} (0x{system_idx:03X}), planet_idx={planet_idx}, galaxy_idx={galaxy_idx}")

                    # Sanity check - region coords must be in valid range
                    if (0 <= x_region <= 4095 and 0 <= y_region <= 255 and 0 <= z_region <= 4095 and
                        0 <= system_idx <= 4095 and 0 <= galaxy_idx <= 255):

                        galaxy_name = galaxy_names.get(galaxy_idx, f"Galaxy_{galaxy_idx}")

                        # Construct glyph DIRECTLY from region coords (no conversion needed!)
                        # Format: P-SSS-YY-ZZZ-XXX
                        glyph_code = f"{planet_idx:01X}{system_idx:03X}{y_region:02X}{z_region:03X}{x_region:03X}".upper()

                        # Convert to signed voxel coords using SIGNED HEX formula (must match glyph_decoder.py!)
                        # X/Z: 0x000-0x7FF = 0 to +2047, 0x800-0xFFF = -2048 to -1
                        # Y:   0x00-0x7F = 0 to +127, 0x80-0xFF = -128 to -1
                        voxel_x = x_region if x_region <= 0x7FF else x_region - 0x1000
                        voxel_y = y_region if y_region <= 0x7F else y_region - 0x100
                        voxel_z = z_region if z_region <= 0x7FF else z_region - 0x1000

                        # Get actual system name from mGameState
                        system_name = self._get_actual_system_name()
                        if not system_name:
                            system_name = f"System_{glyph_code}"
                        region_name = f"Region_{glyph_code[:4]}"
                        self._current_system_coords = {
                            "system_name": system_name,
                            "region_name": region_name,
                            "glyph_code": glyph_code,
                            "galaxy_name": galaxy_name,
                            "galaxy_index": galaxy_idx,
                            "voxel_x": voxel_x,
                            "voxel_y": voxel_y,
                            "voxel_z": voxel_z,
                            "region_x": x_region,
                            "region_y": y_region,
                            "region_z": z_region,
                            "solar_system_index": system_idx,
                        }
                        logger.info(f"  [SUCCESS via Method 2] System: '{system_name}' @ {glyph_code} ({galaxy_name})")
                        logger.info(f"    Voxel coords (signed): [{voxel_x}, {voxel_y}, {voxel_z}]")
                        logger.info(f"    Region coords (raw): [{x_region}, {y_region}, {z_region}]")
                    else:
                        logger.info(f"  [DEBUG] Method 2 failed sanity check: x_region={x_region}, y_region={y_region}, z_region={z_region}")
                except Exception as e:
                    # "Uninitialized mUniverseAddress" is expected - skip quietly
                    if "Uninitialized" not in str(e):
                        logger.debug(f"  mUniverseAddress decode failed: {e}")

            if self._current_system_coords is None:
                logger.info("  [DEBUG] No coordinates yet - will try again during planet capture")

            # =====================================================
            # v8.1.0: Clear captured planets for new system
            # =====================================================
            self._captured_planets.clear()
            self._capture_enabled = True
            self._system_saved_to_batch = False  # v8.2.2: Reset save flag for new system
            logger.info("  [v8.1.0] Captured planet data cleared for new system")
            logger.info("  [v8.1.0] Capture ENABLED - GenerateCreatureRoles hook active")

            logger.info("")
            logger.info("=" * 60)
            logger.info(">>> NEW SYSTEM - Planet data will be captured automatically <<<")
            logger.info(f">>> Systems in batch: {len(self._batch_systems)} <<<")
            logger.info(">>> System saves on next warp or Export Batch <<<")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"Failed to cache solar system: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # =========================================================================
    # CRITICAL v8.1.0: GenerateCreatureRoles HOOK - Captures Flora/Fauna/Sentinels
    # This hook fires for EVERY planet as the game generates creature roles.
    # The lPlanetData parameter contains the actual planet data we need!
    # =========================================================================

    @nms.cGcPlanetGenerator.GenerateCreatureRoles.after
    def on_creature_roles_generate(self, this, lPlanetData, lUA):
        """
        Captures planet data when GenerateCreatureRoles is called.

        This hook fires for EACH planet in the system, receiving the full
        cGcPlanetData structure with Flora, Fauna, Sentinels, Weather, etc.

        This is the CRITICAL hook that was working in v7.9.6!

        IMPORTANT: We limit capture to 6 planets max because the hook also
        fires for nearby systems during galaxy discovery. Only the first 6
        belong to the current system.
        """
        # v10.0.3: lUA parameter is unreliable - gives garbage values when dereferenced
        # v10.1.0: Use mUniverseAddress from planet discovery data instead (PROVEN CORRECT)

        if not self._capture_enabled:
            return

        # v10.1.0: Extract coordinates from planet discovery data mUniverseAddress
        # This is the ONLY reliable source - diagnostic proved it contains correct region coords
        if self._current_system_coords is None and len(self._captured_planets) == 0:
            try:
                if self._cached_solar_system is not None:
                    # Access first planet's discovery data
                    planets = self._cached_solar_system.maPlanets
                    first_planet = planets[0]
                    discovery_data = first_planet.mPlanetDiscoveryData
                    universe_addr = self._safe_int(discovery_data.mUniverseAddress)

                    # Skip if uninitialized
                    if universe_addr != 0 and universe_addr != 0xFFFFFFFFFFFFFFFF:
                        # v10.1.0: CORRECT bit layout for mUniverseAddress
                        # Bits 0-11:  X region (direct, 0-4095)
                        # Bits 12-23: Z region (direct, 0-4095)
                        # Bits 24-31: Y region (direct, 0-255)
                        # Bits 40-51: SolarSystemIndex (12 bits)
                        # Bits 52-55: PlanetIndex + 1 (stored as planet+1)
                        # Bits 56-63: Galaxy index (8 bits)

                        x_region = universe_addr & 0xFFF
                        z_region = (universe_addr >> 12) & 0xFFF
                        y_region = (universe_addr >> 24) & 0xFF
                        system_idx = (universe_addr >> 40) & 0xFFF
                        planet_idx_raw = (universe_addr >> 52) & 0xF
                        planet_idx = max(0, planet_idx_raw - 1)
                        galaxy_idx = (universe_addr >> 56) & 0xFF

                        logger.info(f"  [DEBUG] GenerateCreatureRoles mUniverseAddress decode (v10.1.0):")
                        logger.info(f"    Raw addr: 0x{universe_addr:016X}")
                        logger.info(f"    x_region={x_region}, y_region={y_region}, z_region={z_region}")
                        logger.info(f"    system_idx={system_idx}, planet_idx={planet_idx}, galaxy_idx={galaxy_idx}")

                        # Sanity check
                        if (0 <= x_region <= 4095 and 0 <= y_region <= 255 and 0 <= z_region <= 4095 and
                            0 <= system_idx <= 4095 and 0 <= galaxy_idx <= 255):

                            galaxy_names = {
                                0: "Euclid", 1: "Hilbert Dimension", 2: "Calypso",
                                3: "Hesperius Dimension", 4: "Hyades", 5: "Ickjamatew",
                                6: "Budullangr", 7: "Kikolgallr", 8: "Eltiensleen",
                                9: "Eissentam", 10: "Elkupalos",
                            }
                            galaxy_name = galaxy_names.get(galaxy_idx, f"Galaxy_{galaxy_idx}")

                            # Construct glyph DIRECTLY from region coords
                            glyph_code = f"{planet_idx:01X}{system_idx:03X}{y_region:02X}{z_region:03X}{x_region:03X}".upper()

                            # Convert to signed voxel coords using SIGNED HEX formula (must match glyph_decoder.py!)
                            # X/Z: 0x000-0x7FF = 0 to +2047, 0x800-0xFFF = -2048 to -1
                            # Y:   0x00-0x7F = 0 to +127, 0x80-0xFF = -128 to -1
                            voxel_x = x_region if x_region <= 0x7FF else x_region - 0x1000
                            voxel_y = y_region if y_region <= 0x7F else y_region - 0x100
                            voxel_z = z_region if z_region <= 0x7FF else z_region - 0x1000

                            # Get actual system name
                            system_name = self._get_actual_system_name()
                            if not system_name:
                                system_name = f"System_{glyph_code}"
                            region_name = f"Region_{glyph_code[:4]}"

                            self._current_system_coords = {
                                "system_name": system_name,
                                "region_name": region_name,
                                "glyph_code": glyph_code,
                                "galaxy_name": galaxy_name,
                                "galaxy_index": galaxy_idx,
                                "voxel_x": voxel_x,
                                "voxel_y": voxel_y,
                                "voxel_z": voxel_z,
                                "region_x": x_region,
                                "region_y": y_region,
                                "region_z": z_region,
                                "solar_system_index": system_idx,
                            }
                            logger.info(f"  [SUCCESS via GenerateCreatureRoles] System: '{system_name}' @ {glyph_code} ({galaxy_name})")
                            logger.info(f"    Voxel coords (signed): [{voxel_x}, {voxel_y}, {voxel_z}]")
                            logger.info(f"    Region coords (raw): [{x_region}, {y_region}, {z_region}]")
                        else:
                            logger.debug(f"  [DEBUG] GenerateCreatureRoles sanity failed: region=[{x_region},{y_region},{z_region}]")
            except Exception as e:
                logger.debug(f"  [DEBUG] GenerateCreatureRoles coord extraction failed: {e}")

        # CRITICAL: Limit to 6 planets max (NMS max planets per system)
        # After APPVIEW, the hook fires for nearby systems - ignore those!
        if len(self._captured_planets) >= 6:
            return

        try:
            # Get the planet data pointer
            planet_data_addr = get_addressof(lPlanetData)
            if planet_data_addr == 0:
                logger.debug("GenerateCreatureRoles: lPlanetData is NULL")
                return

            # Map to cGcPlanetData structure (using global imports)
            planet_data = map_struct(planet_data_addr, nmse.cGcPlanetData)

            # Determine planet index - use length of captured dict
            planet_index = len(self._captured_planets)

            # Extract Flora (Life field at offset 0x3458)
            flora_raw = 0
            flora_name = "Unknown"
            try:
                if hasattr(planet_data, 'Life'):
                    life_val = planet_data.Life
                    if hasattr(life_val, 'value'):
                        flora_raw = life_val.value
                    else:
                        flora_raw = int(life_val) if life_val is not None else 0
                    flora_name = self.FLORA_LEVELS.get(flora_raw, f"Unknown({flora_raw})")
            except Exception as e:
                logger.debug(f"Flora extraction failed: {e}")

            # Extract Fauna (CreatureLife field at offset 0x344C)
            fauna_raw = 0
            fauna_name = "Unknown"
            try:
                if hasattr(planet_data, 'CreatureLife'):
                    creature_val = planet_data.CreatureLife
                    if hasattr(creature_val, 'value'):
                        fauna_raw = creature_val.value
                    else:
                        fauna_raw = int(creature_val) if creature_val is not None else 0
                    fauna_name = self.FAUNA_LEVELS.get(fauna_raw, f"Unknown({fauna_raw})")
            except Exception as e:
                logger.debug(f"Fauna extraction failed: {e}")

            # Extract Sentinels (from GroundCombatDataPerDifficulty[0].SentinelLevel)
            # GroundCombatDataPerDifficulty is an array with 4 entries (one per difficulty)
            # We use index 0 for normal difficulty
            sentinel_raw = 0
            sentinel_name = "Unknown"
            try:
                if hasattr(planet_data, 'GroundCombatDataPerDifficulty'):
                    combat_data_array = planet_data.GroundCombatDataPerDifficulty
                    # Access the first element (normal difficulty)
                    if hasattr(combat_data_array, '__getitem__'):
                        combat_data = combat_data_array[0]
                        if hasattr(combat_data, 'SentinelLevel'):
                            sentinel_val = combat_data.SentinelLevel
                            if hasattr(sentinel_val, 'value'):
                                sentinel_raw = sentinel_val.value
                            else:
                                sentinel_raw = int(sentinel_val) if sentinel_val is not None else 0
                            sentinel_name = self.SENTINEL_LEVELS.get(sentinel_raw, f"Unknown({sentinel_raw})")
                    elif hasattr(combat_data_array, 'SentinelLevel'):
                        # Fallback: maybe it's not an array after all
                        sentinel_val = combat_data_array.SentinelLevel
                        if hasattr(sentinel_val, 'value'):
                            sentinel_raw = sentinel_val.value
                        else:
                            sentinel_raw = int(sentinel_val) if sentinel_val is not None else 0
                        sentinel_name = self.SENTINEL_LEVELS.get(sentinel_raw, f"Unknown({sentinel_raw})")
            except Exception as e:
                logger.debug(f"Sentinel extraction failed: {e}")

            # CRITICAL v8.1.6: Extract Biome, BiomeSubType, and Size from GenerationData
            # cGcPlanetData.GenerationData contains cGcPlanetGenerationIntermediateData
            # which has Biome at offset 0x138, BiomeSubType at 0x13C, and Size at 0x144
            biome_raw = -1
            biome_name = "Unknown"
            biome_subtype_raw = -1
            biome_subtype_name = "Unknown"
            planet_size_raw = -1
            planet_size_name = "Unknown"
            is_moon = False
            try:
                if hasattr(planet_data, 'GenerationData'):
                    gen_data = planet_data.GenerationData
                    # Extract Biome
                    if hasattr(gen_data, 'Biome'):
                        biome_val = gen_data.Biome
                        if hasattr(biome_val, 'value'):
                            biome_raw = biome_val.value
                        else:
                            biome_raw = int(biome_val) if biome_val is not None else -1
                        biome_name = BIOME_TYPES.get(biome_raw, f"Unknown({biome_raw})")
                    # Extract BiomeSubType
                    if hasattr(gen_data, 'BiomeSubType'):
                        subtype_val = gen_data.BiomeSubType
                        if hasattr(subtype_val, 'value'):
                            biome_subtype_raw = subtype_val.value
                        else:
                            biome_subtype_raw = int(subtype_val) if subtype_val is not None else -1
                        biome_subtype_name = BIOME_SUBTYPES.get(biome_subtype_raw, f"Unknown({biome_subtype_raw})")
                    # CRITICAL v8.1.9: Extract Size from GenerationData (offset 0x144)
                    # This is the RELIABLE source for planet_size - direct memory read gives garbage
                    if hasattr(gen_data, 'Size'):
                        size_val = gen_data.Size
                        if hasattr(size_val, 'value'):
                            planet_size_raw = size_val.value
                        else:
                            planet_size_raw = int(size_val) if size_val is not None else -1
                        planet_size_name = PLANET_SIZES.get(planet_size_raw, f"Unknown({planet_size_raw})")
                        is_moon = (planet_size_raw == 3)  # Moon = 3
                    logger.debug(f"    Biome={biome_name}, SubType={biome_subtype_name}, Size={planet_size_name}")
            except Exception as e:
                logger.debug(f"Biome extraction from GenerationData failed: {e}")

            # Extract resources - clean to remove garbage characters
            common_resource = ""
            uncommon_resource = ""
            rare_resource = ""
            try:
                if hasattr(planet_data, 'CommonSubstanceID'):
                    val = str(planet_data.CommonSubstanceID) or ""
                    # Only keep printable ASCII
                    common_resource = ''.join(c for c in val if c.isprintable() and ord(c) < 128)
                    if common_resource and (len(common_resource) < 2 or not common_resource[0].isalpha()):
                        common_resource = ""
                if hasattr(planet_data, 'UncommonSubstanceID'):
                    val = str(planet_data.UncommonSubstanceID) or ""
                    uncommon_resource = ''.join(c for c in val if c.isprintable() and ord(c) < 128)
                    if uncommon_resource and (len(uncommon_resource) < 2 or not uncommon_resource[0].isalpha()):
                        uncommon_resource = ""
                if hasattr(planet_data, 'RareSubstanceID'):
                    val = str(planet_data.RareSubstanceID) or ""
                    rare_resource = ''.join(c for c in val if c.isprintable() and ord(c) < 128)
                    if rare_resource and (len(rare_resource) < 2 or not rare_resource[0].isalpha()):
                        rare_resource = ""
            except Exception as e:
                logger.debug(f"Resource extraction failed: {e}")

            # CRITICAL v8.1.8: Extract weather from cGcPlanetData.Weather.WeatherType
            # This uses the actual Weather structure (offset 0x1C00) with enum values
            # Works for ALL planets, not just visited ones like PlanetInfo.Weather
            weather = ""
            weather_raw = -1
            storm_frequency = ""
            storm_raw = -1  # v10.2.0: Store raw value for contextual weather lookup
            try:
                if hasattr(planet_data, 'Weather'):
                    weather_data = planet_data.Weather
                    # Get WeatherType enum
                    if hasattr(weather_data, 'WeatherType'):
                        weather_val = weather_data.WeatherType
                        if hasattr(weather_val, 'value'):
                            weather_raw = weather_val.value
                        else:
                            weather_raw = int(weather_val) if weather_val is not None else -1
                        weather = WEATHER_OPTIONS.get(weather_raw, f"Unknown({weather_raw})")
                        logger.debug(f"    Weather: {weather}")
                    # Also get storm frequency
                    if hasattr(weather_data, 'StormFrequency'):
                        storm_val = weather_data.StormFrequency
                        if hasattr(storm_val, 'value'):
                            storm_raw = storm_val.value
                        else:
                            storm_raw = int(storm_val) if storm_val is not None else -1
                        storm_frequency = STORM_FREQUENCY.get(storm_raw, f"Unknown({storm_raw})")
            except Exception as e:
                logger.debug(f"Weather extraction from Weather struct failed: {e}")

            # Fallback: Try PlanetInfo.Weather display string if Weather struct failed
            if not weather or weather == "Unknown(-1)":
                try:
                    if hasattr(planet_data, 'PlanetInfo'):
                        info = planet_data.PlanetInfo
                        if hasattr(info, 'Weather'):
                            val = str(info.Weather) or ""
                            fallback_weather = ''.join(c for c in val if c.isprintable() and ord(c) < 128)
                            if fallback_weather and len(fallback_weather) >= 2 and fallback_weather != "None":
                                # Clean up raw weather strings like "weather_glitch 6"
                                weather = clean_weather_string(fallback_weather)
                                logger.debug(f"    Weather (fallback): {weather}")
                except Exception as e:
                    logger.debug(f"Weather fallback extraction failed: {e}")

            # CRITICAL v8.1.7: Extract planet Name from cGcPlanetData.Name (offset 0x396E)
            # This is a cTkFixedString0x80 (128 char fixed string)
            planet_name = ""
            try:
                if hasattr(planet_data, 'Name'):
                    name_val = planet_data.Name
                    if name_val is not None:
                        name_str = str(name_val) or ""
                        # Clean to printable ASCII only
                        planet_name = ''.join(c for c in name_str if c.isprintable() and ord(c) < 128)
                        # Validate it looks like a real name
                        if planet_name and (len(planet_name) < 2 or planet_name == "None"):
                            planet_name = ""
                        if planet_name:
                            logger.info(f"  Planet: '{planet_name}'")
            except Exception as e:
                logger.debug(f"Planet name extraction failed: {e}")

            # Store captured planet data
            self._captured_planets[planet_index] = {
                'flora_raw': flora_raw,
                'flora': flora_name,
                'fauna_raw': fauna_raw,
                'fauna': fauna_name,
                'sentinel_raw': sentinel_raw,
                'sentinel': sentinel_name,
                'biome_raw': biome_raw,
                'biome': biome_name,
                'biome_subtype_raw': biome_subtype_raw,
                'biome_subtype': biome_subtype_name,
                'planet_size_raw': planet_size_raw,
                'planet_size': planet_size_name,
                'is_moon': is_moon,
                'common_resource': common_resource,
                'uncommon_resource': uncommon_resource,
                'rare_resource': rare_resource,
                'weather': weather,
                'weather_raw': weather_raw,
                'storm_frequency': storm_frequency,
                'storm_raw': storm_raw,  # v10.2.0: Raw value for contextual weather lookup
                'planet_name': planet_name,
            }

            logger.info("")
            logger.info("*" * 60)
            logger.info(f">>> CAPTURED PLANET {planet_index} DATA! <<<")
            logger.info(f"    Name: {planet_name or '(not set)'}")
            logger.info(f"    Biome: {biome_name} ({biome_raw})")
            logger.info(f"    BiomeSubType: {biome_subtype_name} ({biome_subtype_raw})")
            logger.info(f"    Size: {planet_size_name} ({planet_size_raw}) [is_moon={is_moon}]")
            logger.info(f"    Flora: {flora_name} ({flora_raw})")
            logger.info(f"    Fauna: {fauna_name} ({fauna_raw})")
            logger.info(f"    Sentinels: {sentinel_name} ({sentinel_raw})")
            logger.info(f"    Weather: {weather} (raw: {weather_raw}, storms: {storm_frequency})")
            logger.info(f"    Resources: {common_resource}, {uncommon_resource}, {rare_resource}")
            logger.info(f"    Total captured: {len(self._captured_planets)} planets")
            logger.info("*" * 60)
            logger.info("")

            # =====================================================
            # v10.0.2: Cache coordinates after first planet capture
            # player_state is often None during on_system_generate but
            # should be available by the time planets are generating
            # =====================================================
            if self._current_system_coords is None:
                logger.info(f"    [DEBUG] Attempting planet capture fallback for coordinates...")
                try:
                    player_state = gameData.player_state
                    logger.info(f"    [DEBUG] player_state = {player_state}")
                    if player_state:
                        location = player_state.mLocation
                        galactic_addr = location.GalacticAddress

                        voxel_x = self._safe_int(galactic_addr.VoxelX)
                        voxel_y = self._safe_int(galactic_addr.VoxelY)
                        voxel_z = self._safe_int(galactic_addr.VoxelZ)
                        system_idx = self._safe_int(galactic_addr.SolarSystemIndex)
                        planet_idx_coord = self._safe_int(galactic_addr.PlanetIndex)
                        galaxy_idx = self._safe_int(location.RealityIndex)

                        # DEBUG: Log raw values from GalacticAddress struct (planet capture fallback)
                        logger.info(f"    [DEBUG] GalacticAddress struct (planet capture fallback):")
                        logger.info(f"      VoxelX={voxel_x}, VoxelY={voxel_y}, VoxelZ={voxel_z}")
                        logger.info(f"      SolarSystemIndex={system_idx}, PlanetIndex={planet_idx_coord}, Galaxy={galaxy_idx}")
                        dbg_px = (voxel_x + 2047) & 0xFFF
                        dbg_py = (voxel_y + 127) & 0xFF
                        dbg_pz = (voxel_z + 2047) & 0xFFF
                        logger.info(f"      -> Region coords: [{dbg_px}, {dbg_py}, {dbg_pz}]")

                        # Sanity check galaxy index
                        if galaxy_idx < 0 or galaxy_idx > 255:
                            logger.warning(f"    [v10.0.2] Invalid galaxy_idx {galaxy_idx}, defaulting to 0 (Euclid)")
                            galaxy_idx = 0

                        galaxy_names = {
                            0: "Euclid", 1: "Hilbert Dimension", 2: "Calypso",
                            3: "Hesperius Dimension", 4: "Hyades", 5: "Ickjamatew",
                            6: "Budullangr", 7: "Kikolgallr", 8: "Eltiensleen",
                            9: "Eissentam", 10: "Elkupalos",
                        }
                        galaxy_name = galaxy_names.get(galaxy_idx, f"Galaxy_{galaxy_idx}")

                        glyph_code = self._coords_to_glyphs(planet_idx_coord, system_idx, voxel_x, voxel_y, voxel_z)

                        # Get actual system name from mGameState
                        system_name = self._get_actual_system_name()
                        if not system_name:
                            system_name = f"System_{glyph_code}"
                        region_name = f"Region_{glyph_code[:4]}"

                        self._current_system_coords = {
                            "system_name": system_name,
                            "region_name": region_name,
                            "glyph_code": glyph_code,
                            "galaxy_name": galaxy_name,
                            "galaxy_index": galaxy_idx,
                            "voxel_x": voxel_x,
                            "voxel_y": voxel_y,
                            "voxel_z": voxel_z,
                            "solar_system_index": system_idx,
                        }
                        logger.info(f"    [SUCCESS via Planet Capture Fallback] Cached coords: '{system_name}' in '{region_name}' @ {glyph_code} ({galaxy_name})")
                    else:
                        logger.info("    [DEBUG] player_state is None during planet capture")
                except Exception as e:
                    logger.info(f"    [DEBUG] Planet capture fallback failed: {e}")

        except Exception as e:
            logger.error(f"GenerateCreatureRoles capture failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # =========================================================================
    # APPVIEW - Marks system ready for extraction
    # =========================================================================

    @on_state_change("APPVIEW")
    def on_appview(self):
        """
        Fires when entering game view - player_state is now available.
        Auto-saves system to batch when this fires.

        Note: This only fires if nmspy internal mods are loaded.
        If not, systems save on next warp or Export Batch click.
        """
        if not self._pending_extraction:
            return

        self._pending_extraction = False

        logger.info("=" * 40)
        logger.info("=== APPVIEW STATE - SYSTEM READY ===")
        logger.info("=" * 40)

        # v10.0.13: Extract coordinates from player_state NOW since it's available
        if self._current_system_coords is None:
            logger.info("[APPVIEW] Getting coordinates from player_state...")
            try:
                player_state = gameData.player_state
                logger.info(f"[APPVIEW] player_state = {player_state}")
                if player_state:
                    location = player_state.mLocation
                    galactic_addr = location.GalacticAddress

                    voxel_x = self._safe_int(galactic_addr.VoxelX)
                    voxel_y = self._safe_int(galactic_addr.VoxelY)
                    voxel_z = self._safe_int(galactic_addr.VoxelZ)
                    system_idx = self._safe_int(galactic_addr.SolarSystemIndex)
                    planet_idx = self._safe_int(galactic_addr.PlanetIndex)
                    galaxy_idx = self._safe_int(location.RealityIndex)

                    # DEBUG: Log values
                    logger.info(f"[APPVIEW] GalacticAddress fields:")
                    logger.info(f"  VoxelX={voxel_x}, VoxelY={voxel_y}, VoxelZ={voxel_z}")
                    logger.info(f"  SolarSystemIndex={system_idx}, PlanetIndex={planet_idx}, Galaxy={galaxy_idx}")
                    dbg_px = (voxel_x + 2047) & 0xFFF
                    dbg_py = (voxel_y + 127) & 0xFF
                    dbg_pz = (voxel_z + 2047) & 0xFFF
                    logger.info(f"  -> Region coords: [{dbg_px}, {dbg_py}, {dbg_pz}]")

                    # Sanity check galaxy index
                    if galaxy_idx < 0 or galaxy_idx > 255:
                        logger.warning(f"[APPVIEW] Invalid galaxy_idx {galaxy_idx}, defaulting to 0")
                        galaxy_idx = 0

                    galaxy_names = {
                        0: "Euclid", 1: "Hilbert Dimension", 2: "Calypso",
                        3: "Hesperius Dimension", 4: "Hyades", 5: "Ickjamatew",
                        6: "Budullangr", 7: "Kikolgallr", 8: "Eltiensleen",
                        9: "Eissentam", 10: "Elkupalos",
                    }
                    galaxy_name = galaxy_names.get(galaxy_idx, f"Galaxy_{galaxy_idx}")

                    glyph_code = self._coords_to_glyphs(planet_idx, system_idx, voxel_x, voxel_y, voxel_z)

                    # Get actual system name
                    system_name = self._get_actual_system_name()
                    if not system_name:
                        system_name = f"System_{glyph_code}"
                    region_name = f"Region_{glyph_code[:4]}"

                    self._current_system_coords = {
                        "system_name": system_name,
                        "region_name": region_name,
                        "glyph_code": glyph_code,
                        "galaxy_name": galaxy_name,
                        "galaxy_index": galaxy_idx,
                        "voxel_x": voxel_x,
                        "voxel_y": voxel_y,
                        "voxel_z": voxel_z,
                        "solar_system_index": system_idx,
                    }
                    logger.info(f"[APPVIEW SUCCESS] Coords: '{system_name}' @ {glyph_code} in {region_name} ({galaxy_name})")
                else:
                    logger.warning("[APPVIEW] player_state is still None!")
            except Exception as e:
                logger.error(f"[APPVIEW] Failed to get coordinates: {e}")

        # Auto-save to batch when APPVIEW fires (if not already saved)
        if self._batch_mode_enabled and self._captured_planets and not self._system_saved_to_batch:
            logger.info("[BATCH] Auto-saving system to batch...")
            self._save_current_system_to_batch()
            self._system_saved_to_batch = True
            logger.info(f"[BATCH] Systems in batch: {len(self._batch_systems)}")
        elif self._system_saved_to_batch:
            logger.info("[BATCH] System already saved")
            logger.info(f"[BATCH] Systems in batch: {len(self._batch_systems)}")

        logger.info(">>> Click 'Export Batch' to save all systems <<<")
        logger.info("=" * 40)

    # =========================================================================
    # GUI BUTTONS
    # =========================================================================

    @gui_button("Get Coordinates")
    def get_coordinates_button(self):
        """
        Diagnostic: Dump ALL possible coordinate sources.
        For Sea of Gidzenuf: region [4009, 1, 2365] = [0xFA9, 0x01, 0x93D]
        """
        import ctypes

        logger.info("")
        logger.info("=" * 70)
        logger.info(">>> COORDINATE SOURCE DIAGNOSTIC <<<")
        logger.info(">>> Sea of Gidzenuf target: [4009, 1, 2365] = [0xFA9, 0x01, 0x93D] <<<")
        logger.info("=" * 70)

        planet_count = len(self._captured_planets)
        logger.info(f"Captured planet count: {planet_count}")

        # =====================================================
        # SOURCE 1: player_state.mLocation.GalacticAddress
        # =====================================================
        logger.info("")
        logger.info("--- SOURCE 1: player_state.mLocation.GalacticAddress ---")
        try:
            player_state = gameData.player_state
            if player_state:
                location = player_state.mLocation
                galactic_addr = location.GalacticAddress
                logger.info(f"  VoxelX = {self._safe_int(galactic_addr.VoxelX)}")
                logger.info(f"  VoxelY = {self._safe_int(galactic_addr.VoxelY)}")
                logger.info(f"  VoxelZ = {self._safe_int(galactic_addr.VoxelZ)}")
                logger.info(f"  SolarSystemIndex = {self._safe_int(galactic_addr.SolarSystemIndex)}")
                logger.info(f"  PlanetIndex = {self._safe_int(galactic_addr.PlanetIndex)}")
                logger.info(f"  RealityIndex = {self._safe_int(location.RealityIndex)}")
            else:
                logger.info("  player_state is None")
        except Exception as e:
            logger.info(f"  Failed: {e}")

        # =====================================================
        # SOURCE 2: Solar System mSolarSystemData.Seed
        # =====================================================
        logger.info("")
        logger.info("--- SOURCE 2: Solar System Seed ---")
        try:
            solar_system = self._cached_solar_system
            if solar_system:
                solar_data = solar_system.mSolarSystemData
                if hasattr(solar_data, 'Seed'):
                    seed = self._safe_int(solar_data.Seed)
                    logger.info(f"  Seed = {seed} (0x{seed:016X})")
                    # Try decoding seed as coordinates
                    logger.info(f"    Low 12 bits (X?): {seed & 0xFFF}")
                    logger.info(f"    Bits 12-19 (Y?): {(seed >> 12) & 0xFF}")
                    logger.info(f"    Bits 20-31 (Z?): {(seed >> 20) & 0xFFF}")
                    logger.info(f"    Bits 32-43 (Sys?): {(seed >> 32) & 0xFFF}")
        except Exception as e:
            logger.info(f"  Failed: {e}")

        # =====================================================
        # SOURCE 3: Planet mUniverseAddress raw values
        # v10.1.0: Using CORRECT bit layout (verified working!)
        # =====================================================
        logger.info("")
        logger.info("--- SOURCE 3: Planet Discovery mUniverseAddress (v10.1.0 CORRECT decode) ---")
        try:
            if self._cached_solar_system:
                planets = self._cached_solar_system.maPlanets
                for i in range(min(2, 6)):  # Just check first 2
                    try:
                        planet = planets[i]
                        if planet:
                            discovery = planet.mPlanetDiscoveryData
                            addr = self._safe_int(discovery.mUniverseAddress)
                            if addr != 0:
                                logger.info(f"  Planet {i} mUniverseAddress = 0x{addr:016X}")
                                # v10.1.0: CORRECT bit layout
                                x_region = addr & 0xFFF
                                z_region = (addr >> 12) & 0xFFF
                                y_region = (addr >> 24) & 0xFF
                                system_idx = (addr >> 40) & 0xFFF
                                planet_idx_raw = (addr >> 52) & 0xF
                                planet_idx = max(0, planet_idx_raw - 1)
                                galaxy_idx = (addr >> 56) & 0xFF
                                glyph = f"{planet_idx:01X}{system_idx:03X}{y_region:02X}{z_region:03X}{x_region:03X}".upper()
                                logger.info(f"    X region: {x_region} (0x{x_region:03X})")
                                logger.info(f"    Y region: {y_region} (0x{y_region:02X})")
                                logger.info(f"    Z region: {z_region} (0x{z_region:03X})")
                                logger.info(f"    System index: {system_idx} (0x{system_idx:03X})")
                                logger.info(f"    Planet index: {planet_idx}")
                                logger.info(f"    Galaxy: {galaxy_idx}")
                                logger.info(f"    => GLYPH: {glyph}")
                                logger.info(f"    => Region coords: [{x_region}, {y_region}, {z_region}]")
                    except:
                        pass
        except Exception as e:
            logger.info(f"  Failed: {e}")

        # =====================================================
        # SOURCE 4: Raw memory scan of solar system struct
        # =====================================================
        logger.info("")
        logger.info("--- SOURCE 4: Raw Memory Scan (looking for 0xFA9, 0x93D) ---")
        try:
            if self._cached_solar_system:
                base = get_addressof(self._cached_solar_system)
                logger.info(f"  Solar system base: 0x{base:X}")

                # Scan for values that might be our coords
                # Looking for 4009 (0xFA9), 1 (0x01), 2365 (0x93D)
                for offset in range(0, 0x100, 4):
                    try:
                        val32 = ctypes.c_uint32.from_address(base + offset).value
                        val16 = ctypes.c_uint16.from_address(base + offset).value

                        # Check if this looks like our target coords
                        if val16 == 4009 or val16 == 2365 or val32 == 4009 or val32 == 2365:
                            logger.info(f"    Offset 0x{offset:04X}: u32={val32}, u16={val16} ** POTENTIAL MATCH **")
                        elif val16 in range(4000, 4020) or val16 in range(2360, 2370):
                            logger.info(f"    Offset 0x{offset:04X}: u32={val32}, u16={val16} (close)")
                    except:
                        pass

                # Also check specific known offsets in cGcSolarSystemData
                logger.info("  Checking specific offsets:")
                for offset, name in [(0x0, "start"), (0x8, "+8"), (0x10, "+16"),
                                      (0x2270, "Name area"), (0x2280, "+2280")]:
                    try:
                        val64 = ctypes.c_uint64.from_address(base + offset).value
                        logger.info(f"    0x{offset:04X} ({name}): 0x{val64:016X}")
                    except:
                        pass
        except Exception as e:
            logger.info(f"  Failed: {e}")

        # =====================================================
        # SOURCE 5: Check if there's a region name string
        # =====================================================
        logger.info("")
        logger.info("--- SOURCE 5: Region/System Name from memory ---")
        try:
            system_name = self._get_actual_system_name()
            logger.info(f"  System name: {system_name or '(not found)'}")
        except Exception as e:
            logger.info(f"  Failed: {e}")

        logger.info("")
        logger.info("=" * 70)
        logger.info(">>> Look for values matching: 4009, 2365, 0xFA9, 0x93D <<<")
        logger.info("=" * 70)

    @gui_button("Check System Data")
    def check_system_data(self):
        """
        Check planet data status - shows both mPlanetData AND captured hook data.
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info(">>> PLANET DATA STATUS <<<")
        logger.info(f">>> Captured planets via hook: {len(self._captured_planets)} <<<")
        logger.info("=" * 60)

        # First, show captured hook data summary
        if self._captured_planets:
            logger.info("")
            logger.info("=== CAPTURED HOOK DATA SUMMARY ===")
            for idx, captured in sorted(self._captured_planets.items()):
                moon_tag = " [MOON]" if captured.get('is_moon') else ""
                name = captured.get('planet_name') or f"Planet_{idx+1}"
                logger.info(f"  Planet {idx}: {name}{moon_tag}")
                logger.info(f"    Biome: {captured.get('biome')}, SubType: {captured.get('biome_subtype')}, Size: {captured.get('planet_size')}")
                logger.info(f"    Weather: {captured.get('weather')}, Flora: {captured.get('flora')}, Fauna: {captured.get('fauna')}, Sentinels: {captured.get('sentinel')}")
        else:
            logger.info("  No captured data yet - warp to a system first")

        logger.info("")
        logger.info("=== DETAILED PLANET STATUS ===")

        # Get solar system
        solar_system = self._cached_solar_system
        if not solar_system:
            simulation = gameData.simulation
            if simulation and simulation.mpSolarSystem:
                addr = get_addressof(simulation.mpSolarSystem)
                if addr != 0:
                    solar_system = map_struct(addr, nms.cGcSolarSystem)

        if not solar_system:
            logger.warning("No solar system available")
            return

        try:
            planets_array = solar_system.maPlanets
            sys_data = solar_system.mSolarSystemData
            planet_count = self._safe_int(sys_data.Planets) if hasattr(sys_data, 'Planets') else 6

            for i in range(min(planet_count, 6)):
                planet = planets_array[i]
                if planet is None:
                    continue

                planet_addr = get_addressof(planet)
                if planet_addr == 0:
                    continue

                # v8.1.9: Use CAPTURED data from hook (reliable) instead of direct memory (garbage)
                biome = "NOT_READ"
                biome_subtype = "NOT_READ"
                planet_size = "NOT_READ"
                is_moon = False
                weather = "NOT_READ"

                # First check if we have captured data from hook (RELIABLE source)
                if i in self._captured_planets:
                    cap = self._captured_planets[i]
                    biome = cap.get('biome', 'Unknown')
                    biome_subtype = cap.get('biome_subtype', 'Unknown')
                    planet_size = cap.get('planet_size', 'Unknown')
                    is_moon = cap.get('is_moon', False)
                    weather = cap.get('weather', 'Unknown')
                else:
                    # Fallback to direct memory read (often gives garbage for planets 1-5)
                    try:
                        sys_data_addr = get_addressof(sys_data)
                        if sys_data_addr != 0:
                            direct_data = self._read_planet_gen_input_direct(sys_data_addr, i)
                            biome = direct_data.get("biome", "Unknown")
                            planet_size = direct_data.get("planet_size", "Unknown")
                            is_moon = direct_data.get("is_moon", False)
                    except Exception as e:
                        logger.debug(f"Direct read failed for {i}: {e}")

                # v8.1.9: Use captured data from hook for name/flora/fauna/sentinel if available
                name = f"Planet_{i+1}"
                sentinels = "NOT_READ"
                flora = "NOT_READ"
                fauna = "NOT_READ"

                # Use captured data from hook (RELIABLE source)
                if i in self._captured_planets:
                    cap = self._captured_planets[i]
                    if cap.get('planet_name'):
                        name = cap.get('planet_name')
                    flora = cap.get('flora', 'Unknown')
                    fauna = cap.get('fauna', 'Unknown')
                    sentinels = cap.get('sentinel', 'Unknown')
                else:
                    # Fallback: Try mPlanetData (only works for visited/populated planets)
                    try:
                        if hasattr(planet, 'mPlanetData'):
                            pd = planet.mPlanetData
                            if hasattr(pd, 'Name'):
                                n = str(pd.Name)
                                if n and n != "None" and len(n) > 0:
                                    name = n
                            if hasattr(pd, 'PlanetInfo'):
                                info = pd.PlanetInfo
                                if weather == "NOT_READ" and hasattr(info, 'Weather'):
                                    w = str(info.Weather)
                                    if w and w != "None":
                                        weather = clean_weather_string(w)
                                # NOTE: SentinelsPerDifficulty, Flora, Fauna are array types
                                # Use captured data from hook instead (these would show object refs)
                    except Exception as e:
                        logger.debug(f"Error checking planet {i}: {e}")

                # Log status - v8.1.9: Shows captured data from hook (reliable)
                has_captured = i in self._captured_planets
                status = "CAPTURED" if has_captured else "NO_HOOK_DATA"
                moon_str = " [MOON]" if is_moon else ""
                logger.info(f"  Planet {i} [{status}]: {name}{moon_str}")
                logger.info(f"    Biome: {biome}, SubType: {biome_subtype}")
                logger.info(f"    Size: {planet_size}, is_moon: {is_moon}")
                logger.info(f"    Weather: {weather}")
                logger.info(f"    Flora: {flora}, Fauna: {fauna}, Sentinels: {sentinels}")

        except Exception as e:
            logger.error(f"Check planet data failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        logger.info("=" * 60)

    def _read_bytes(self, base_addr: int, offset: int, size: int) -> bytes:
        """Read raw bytes from memory."""
        try:
            import ctypes
            addr = base_addr + offset
            buffer = (ctypes.c_char * size)()
            ctypes.memmove(buffer, addr, size)
            return bytes(buffer)
        except Exception:
            return None

    def _read_uint64(self, base_addr: int, offset: int) -> int:
        """Read uint64 from memory."""
        try:
            import ctypes
            addr = base_addr + offset
            return ctypes.cast(addr, ctypes.POINTER(ctypes.c_uint64)).contents.value
        except Exception:
            return 0

    def _read_uint32(self, base_addr: int, offset: int) -> int:
        """Read uint32 from memory."""
        try:
            import ctypes
            addr = base_addr + offset
            return ctypes.cast(addr, ctypes.POINTER(ctypes.c_uint32)).contents.value
        except Exception:
            return 0

    def _read_string(self, base_addr: int, offset: int, max_len: int = 128) -> str:
        """Read null-terminated string from memory."""
        try:
            raw = self._read_bytes(base_addr, offset, max_len)
            if raw:
                null_pos = raw.find(b'\x00')
                if null_pos > 0:
                    return raw[:null_pos].decode('utf-8', errors='ignore')
            return ""
        except Exception:
            return ""

    # =========================================================================
    # v10.0.0: STREAMLINED GUI BUTTONS
    # =========================================================================

    @gui_button("Check Batch Data")
    def check_batch_data(self):
        """
        Show current batch status - how many systems are stored.
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info(">>> BATCH DATA STATUS (v10.0.0) <<<")
        logger.info("=" * 60)

        logger.info(f"  Systems in batch: {len(self._batch_systems)}")

        if self._batch_systems:
            total_planets = sum(sys.get('planet_count', 0) for sys in self._batch_systems)
            logger.info(f"  Total planets stored: {total_planets}")
            logger.info("")
            logger.info("  Systems in batch:")
            for i, sys in enumerate(self._batch_systems):
                glyph = sys.get('glyph_code', 'Unknown')
                galaxy = sys.get('galaxy_name', 'Unknown')
                planets = sys.get('planet_count', 0)
                logger.info(f"    {i+1}. [{glyph}] in {galaxy} - {planets} planets")
        else:
            logger.info("")
            logger.info("  Batch is empty - warp to systems to collect data")

        # Also show current system info
        logger.info("")
        logger.info("  Current system:")
        logger.info(f"    Captured planets: {len(self._captured_planets)}")
        if self._captured_planets:
            logger.info("    (Will be added to batch on Export)")

        logger.info("")
        logger.info("  User config:")
        logger.info(f"    Discord: {USER_DISCORD_USERNAME}")
        logger.info(f"    Community: {USER_DISCORD_TAG}")
        logger.info(f"    Reality: {USER_REALITY}")

        logger.info("=" * 60)
        logger.info("")

    @gui_button("Show Config Status")
    def show_config_status(self):
        """
        v10.0.0: Display current configuration in log.
        Config fields are editable in the GUI above (Discord Username, Discord ID, dropdowns).
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info(">>> CURRENT CONFIGURATION <<<")
        logger.info("=" * 60)
        logger.info(f"  Discord Username: {self._discord_username or '(not set)'}")
        logger.info(f"  Community Tag:    {self._discord_tag}")
        logger.info(f"  Reality Mode:     {self._reality}")
        logger.info("=" * 60)
        if not self._discord_username:
            logger.warning("[CONFIG] Discord Username is required for export!")
            logger.info("[CONFIG] Enter your Discord username in the text field above.")
        else:
            logger.info("[CONFIG] Configuration is complete. Ready to export!")
        logger.info("")

    @gui_button("Export to Haven UI")
    def export_to_haven_ui(self):
        """
        v10.0.0: Export systems directly to Haven UI with duplicate checking.
        Uploads all collected systems in batch with progress logging.
        """
        logger.info("")
        logger.info("=" * 60)
        logger.info(">>> EXPORT TO HAVEN UI (v10.0.0) <<<")
        logger.info("=" * 60)

        # Check if config is complete
        if not self._discord_username:
            logger.error("[EXPORT] Configuration incomplete!")
            logger.error("[EXPORT] Please enter your Discord Username in the text field above.")
            logger.info("[EXPORT] Use the 'Show Config Status' button to verify your settings.")
            return

        # First, save current system to batch if there's data
        if self._captured_planets:
            logger.info("[EXPORT] Saving current system to batch...")
            self._save_current_system_to_batch()

        if not self._batch_systems:
            logger.warning("[EXPORT] No systems to export!")
            logger.info("[EXPORT] Visit some systems first, then click 'Export to Haven UI'")
            return

        total = len(self._batch_systems)
        logger.info(f"[EXPORT] Preparing to export {total} system(s)...")

        # Run export in a thread to avoid blocking the game
        def run_export():
            try:
                self._run_export_flow()
            except Exception as e:
                logger.error(f"Export failed: {e}")
                import traceback
                logger.error(traceback.format_exc())

        thread = threading.Thread(target=run_export, daemon=True)
        thread.start()

    def _run_export_flow(self):
        """
        Run the full export flow with log-based progress.
        No tkinter dialogs - all output goes to the pymhf log window.
        """
        systems_to_export = self._batch_systems.copy()
        total_systems = len(systems_to_export)

        if total_systems == 0:
            logger.warning("[EXPORT] No systems to export!")
            return

        logger.info(f"[EXPORT] Starting export of {total_systems} system(s)...")
        logger.info("")

        # Step 1: Pre-flight duplicate check
        logger.info("[EXPORT] Running pre-flight duplicate check...")
        glyph_codes = [sys.get('glyph_code') for sys in systems_to_export if sys.get('glyph_code')]

        check_result = self._check_duplicates(glyph_codes)
        if not check_result:
            logger.warning("[EXPORT] Could not verify duplicates with Haven UI")
            logger.info("[EXPORT] Proceeding with export anyway...")
            check_result = {"results": {}, "summary": {"available": len(glyph_codes), "already_charted": 0, "pending_review": 0}}

        summary = check_result.get("summary", {})
        results = check_result.get("results", {})

        available_count = summary.get("available", 0)
        charted_count = summary.get("already_charted", 0)
        pending_count = summary.get("pending_review", 0)

        logger.info("")
        logger.info("--- DUPLICATE CHECK RESULTS ---")
        logger.info(f"  Ready to submit: {available_count}")
        logger.info(f"  Already charted: {charted_count}")
        logger.info(f"  Pending review:  {pending_count}")
        logger.info("")

        # Show details for duplicates
        if charted_count > 0 or pending_count > 0:
            for glyph, info in results.items():
                status = info.get('status', 'unknown')
                if status == 'already_charted':
                    name = info.get('system_name', 'Unknown')
                    logger.info(f"  [CHARTED] {glyph} - \"{name}\"")
                elif status == 'pending_review':
                    by = info.get('submitted_by', 'Unknown')
                    logger.info(f"  [PENDING] {glyph} - by {by}")
            logger.info("")

        # Step 2: Filter out only already_charted systems (approved duplicates)
        # Pending systems are allowed through - server will update them
        if charted_count > 0:
            systems_to_export = [
                sys for sys in systems_to_export
                if results.get(sys.get('glyph_code'), {}).get('status') != 'already_charted'
            ]
            logger.info(f"[EXPORT] Exporting {len(systems_to_export)} systems (skipping {charted_count} already charted)")
        else:
            logger.info(f"[EXPORT] Exporting all {len(systems_to_export)} systems")

        if pending_count > 0:
            logger.info(f"[EXPORT] Note: {pending_count} pending system(s) will be updated with new data")

        # Step 3: Upload systems
        if not systems_to_export:
            logger.info("[EXPORT] No new systems to export after filtering duplicates")
            return

        self._upload_systems_to_api_log(systems_to_export)

    def _check_duplicates(self, glyph_codes: list) -> dict:
        """Check which systems already exist in Haven."""
        try:
            url = f"{API_BASE_URL}/api/check_glyph_codes"
            payload = json.dumps({"glyph_codes": glyph_codes}).encode('utf-8')

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(url, data=payload, headers={
                'Content-Type': 'application/json',
                'X-API-Key': HAVEN_EXTRACTOR_API_KEY,
                'User-Agent': 'HavenExtractor/10.0.0',
            })

            with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                return json.loads(response.read().decode('utf-8'))

        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return None

    def _upload_systems_to_api_log(self, systems: list):
        """Upload systems to Haven UI API with log-based progress (no tkinter)."""
        total = len(systems)
        results = {"submitted": 0, "skipped": 0, "failed": 0, "errors": []}

        logger.info("")
        logger.info("--- UPLOADING TO HAVEN UI ---")
        logger.info("")

        for i, system in enumerate(systems):
            glyph = system.get('glyph_code', 'Unknown')
            logger.info(f"[{i+1}/{total}] Uploading {glyph}...")

            try:
                # Add user config to system data
                system['discord_username'] = self._discord_username
                system['personal_id'] = self._personal_id
                system['discord_tag'] = self._discord_tag
                system['reality'] = self._reality

                result = self._send_single_system_to_api(system)
                if result.get('status') == 'ok':
                    logger.info(f"  [OK] {glyph} - submitted")
                    results["submitted"] += 1
                elif result.get('status') == 'updated':
                    logger.info(f"  [OK] {glyph} - updated")
                    results["submitted"] += 1
                elif result.get('status') == 'already_charted':
                    logger.info(f"  [SKIP] {glyph} - already charted")
                    results["skipped"] += 1
                else:
                    error_msg = result.get('message', 'unknown error')
                    logger.warning(f"  [FAIL] {glyph} - {error_msg}")
                    results["failed"] += 1
                    results["errors"].append(f"{glyph}: {error_msg}")

            except Exception as e:
                logger.error(f"  [FAIL] {glyph} - {str(e)}")
                results["failed"] += 1
                results["errors"].append(f"{glyph}: {str(e)}")

        # Show final results
        logger.info("")
        logger.info("=" * 60)
        logger.info(">>> EXPORT COMPLETE <<<")
        logger.info("=" * 60)
        logger.info(f"  Submitted: {results['submitted']}")
        logger.info(f"  Skipped:   {results['skipped']}")
        logger.info(f"  Failed:    {results['failed']}")
        logger.info("=" * 60)

        # Clear batch after successful export
        if results["submitted"] > 0:
            self._batch_systems.clear()
            logger.info("[EXPORT] Batch cleared after successful export")
            logger.info("[EXPORT] Your submissions are now pending admin review!")
        logger.info("")

    def _send_single_system_to_api(self, system: dict) -> dict:
        """Send a single system to the Haven UI API."""
        try:
            url = f"{API_BASE_URL}/api/extraction"
            payload = json.dumps(system, default=str).encode('utf-8')

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(url, data=payload, headers={
                'Content-Type': 'application/json',
                'X-API-Key': HAVEN_EXTRACTOR_API_KEY,
                'User-Agent': 'HavenExtractor/10.0.0',
            })

            with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                return json.loads(response.read().decode('utf-8'))

        except urllib.error.HTTPError as e:
            try:
                error_body = json.loads(e.read().decode('utf-8'))
                return error_body
            except:
                return {"status": "error", "message": f"HTTP {e.code}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # =========================================================================
    # EXTRACTION LOGIC
    # =========================================================================

    def _do_extraction(self, force: bool = False, trigger: str = "unknown"):
        """Perform the actual extraction using cached or live solar system."""
        # Update extraction timestamp
        self._last_extraction_time = time.time()

        # Try cached solar system first
        solar_system = self._cached_solar_system
        if not solar_system:
            logger.info("No cached solar system - getting from gameData")
            simulation = gameData.simulation
            if not simulation:
                logger.warning("No simulation available")
                return

            ptr = simulation.mpSolarSystem
            if not ptr:
                logger.warning("No solar system pointer")
                return

            addr = get_addressof(ptr)
            if addr == 0:
                logger.warning("Solar system pointer is NULL")
                return

            solar_system = map_struct(addr, nms.cGcSolarSystem)

        logger.info(f"Solar system: {solar_system}")

        # Get system data
        sys_data = solar_system.mSolarSystemData
        logger.info(f"System data: {sys_data}")

        # CRITICAL: Cache the sys_data address for direct memory reads
        try:
            self._cached_sys_data_addr = get_addressof(sys_data)
            logger.info(f"  Cached sys_data address: 0x{self._cached_sys_data_addr:X}")
        except Exception as e:
            logger.warning(f"  Could not get sys_data address: {e}")
            self._cached_sys_data_addr = None

        # Check if we already extracted this system (skip if force=True)
        if not force:
            try:
                current_seed = self._safe_int(sys_data.Seed.Seed) if hasattr(sys_data, 'Seed') else 0
                if current_seed == self._last_extracted_seed and current_seed != 0:
                    logger.info(f"Already extracted system with seed {current_seed}")
                    return
                self._last_extracted_seed = current_seed
                logger.info(f"New system seed: {current_seed}")
            except Exception as e:
                logger.debug(f"Seed check failed: {e}")
        else:
            logger.info("Force extraction - skipping seed check")
            try:
                current_seed = self._safe_int(sys_data.Seed.Seed) if hasattr(sys_data, 'Seed') else 0
                self._last_extracted_seed = current_seed
            except Exception:
                pass

        # Get player coordinates
        coords = self._get_current_coordinates()
        if not coords:
            logger.warning("Could not get player coordinates")
            return

        # Cache coordinates for batch mode
        self._current_system_coords = coords
        logger.info(f"Coordinates cached: {coords.get('glyph_code')} in {coords.get('galaxy_name')}")

        # Determine data source based on whether we have captured data
        data_source = "captured_hook" if len(self._captured_planets) > 0 else "memory_read"

        extraction = {
            "extraction_time": datetime.now().isoformat(),
            "extractor_version": "10.0.0",
            "trigger": trigger,
            "source": "live_extraction",
            "data_source": data_source,
            "captured_planet_count": len(self._captured_planets),
            "discoverer_name": "HavenExtractor",
            "discovery_timestamp": int(datetime.now().timestamp()),
            **coords,
            **self._extract_system_properties(sys_data),
            "planets": self._extract_planets(solar_system),
        }

        extraction["planet_count"] = len(extraction["planets"])
        self._write_extraction(extraction)

        logger.info(f"Extraction complete: {extraction['glyph_code']} - {extraction['planet_count']} planets")

        # Clear cache after extraction
        self._cached_solar_system = None

    def _get_current_coordinates(self) -> Optional[dict]:
        """Get current galactic coordinates from player state or solar system."""
        # All 256 NMS galaxies (first 10 are well-known, rest are procedural)
        galaxy_names = {
            0: "Euclid", 1: "Hilbert Dimension", 2: "Calypso",
            3: "Hesperius Dimension", 4: "Hyades", 5: "Ickjamatew",
            6: "Budullangr", 7: "Kikolgallr", 8: "Eltiensleen",
            9: "Eissentam", 10: "Elkupalos", 11: "Aptarkaba",
            12: "Ontiniangp", 13: "Odiwagiri", 14: "Ogtialabi",
            15: "Muhacksonto", 16: "Hitonskyer", 17: "Reaboranxu",
            18: "Isdoraijung", 19: "Doctilusda", 20: "Loychazinq",
        }

        # Method 1: Try player_state (most reliable when available)
        logger.info("  Checking coordinate sources...")
        try:
            player_state = gameData.player_state
            logger.info(f"  Method 1 - player_state: {player_state}")
            if player_state:
                location = player_state.mLocation
                galactic_addr = location.GalacticAddress

                voxel_x = self._safe_int(galactic_addr.VoxelX)
                voxel_y = self._safe_int(galactic_addr.VoxelY)
                voxel_z = self._safe_int(galactic_addr.VoxelZ)
                system_idx = self._safe_int(galactic_addr.SolarSystemIndex)
                planet_idx = self._safe_int(galactic_addr.PlanetIndex)

                # Debug log the raw reality index
                raw_reality = location.RealityIndex
                logger.info(f"  [player_state] Raw RealityIndex: {raw_reality}, type: {type(raw_reality)}")
                galaxy_idx = self._safe_int(raw_reality)

                # Sanity check: galaxy index should be 0-255
                if galaxy_idx < 0 or galaxy_idx > 255:
                    logger.warning(f"  [player_state] Invalid galaxy_idx {galaxy_idx}, defaulting to 0 (Euclid)")
                    galaxy_idx = 0

                logger.info(f"  [player_state] SUCCESS: X={voxel_x}, Y={voxel_y}, Z={voxel_z}, Sys={system_idx}, Galaxy={galaxy_idx}")

                glyph_code = self._coords_to_glyphs(
                    planet_idx, system_idx, voxel_x, voxel_y, voxel_z
                )

                # Get actual system name from mGameState
                system_name = self._get_actual_system_name()
                if not system_name:
                    system_name = f"System_{glyph_code}"
                region_name = f"Region_{glyph_code[:4]}"

                return {
                    "system_name": system_name,
                    "region_name": region_name,
                    "glyph_code": glyph_code,
                    "galaxy_name": galaxy_names.get(galaxy_idx, f"Galaxy_{galaxy_idx}"),
                    "galaxy_index": galaxy_idx,
                    "voxel_x": voxel_x,
                    "voxel_y": voxel_y,
                    "voxel_z": voxel_z,
                    "solar_system_index": system_idx,
                }
        except Exception as e:
            logger.info(f"  [player_state] EXCEPTION: {e}")

        # Method 2: Check if we have cached coordinates from on_system_generate
        # v10.0.1: This is the primary fallback - coords are cached when system generates
        logger.info(f"  Method 2 - cached coords: {self._current_system_coords}")
        if self._current_system_coords:
            cached_glyph = self._current_system_coords.get('glyph_code', 'Unknown')
            cached_name = self._current_system_coords.get('system_name', 'Unknown')
            logger.warning(f"  [cached] WARNING: Using CACHED coords (player_state was None)")
            logger.warning(f"  [cached] Cached system: '{cached_name}' @ {cached_glyph}")
            logger.warning(f"  [cached] If this is wrong, try warping to a system and waiting before export")
            return self._current_system_coords

        logger.warning("  All coordinate methods failed - are you in a star system?")
        return None

    def _extract_system_properties(self, sys_data) -> dict:
        """Extract system-level properties from game memory."""
        result = {
            "system_name": "",
            "star_color": "Unknown",
            "economy_type": "Unknown",
            "economy_strength": "Unknown",
            "conflict_level": "Unknown",
            "dominant_lifeform": "Unknown",
            "system_seed": 0,
        }

        # =====================================================
        # Get system name from mGameState notification string
        # The game stores "In the {system_name} system" at offset 0x38
        # =====================================================
        try:
            game_state = gameData.game_state
            if game_state:
                game_state_addr = get_addressof(game_state)
                if game_state_addr and game_state_addr != 0:
                    notification_str = self._read_string(game_state_addr, 0x38, max_len=256)
                    if notification_str:
                        match = re.match(r"In the (.+) system", notification_str)
                        if match:
                            extracted_name = match.group(1).strip()
                            if extracted_name:
                                result["system_name"] = extracted_name
                                logger.info(f"  System name: '{extracted_name}'")
        except Exception as e:
            logger.debug(f"System name extraction failed: {e}")

        # Star color mapping (enum names to clean values)
        STAR_COLOR_MAP = {
            'Yellow': 'Yellow', 'Yellow_': 'Yellow', 'yellow': 'Yellow', '0': 'Yellow',
            'Red': 'Red', 'Red_': 'Red', 'red': 'Red', '1': 'Red',
            'Green': 'Green', 'Green_': 'Green', 'green': 'Green', '2': 'Green',
            'Blue': 'Blue', 'Blue_': 'Blue', 'blue': 'Blue', '3': 'Blue',
            'Default': 'Yellow', 'Default_': 'Yellow',  # Default is Yellow
        }

        # Dominant lifeform mapping (enum names to clean values)
        LIFEFORM_MAP = {
            'Traders': 'Gek', 'Traders_': 'Gek', 'Gek': 'Gek', '0': 'Gek',
            'Warriors': "Vy'keen", 'Warriors_': "Vy'keen", "Vy'keen": "Vy'keen", 'Vykeen': "Vy'keen", '1': "Vy'keen",
            'Explorers': 'Korvax', 'Explorers_': 'Korvax', 'Korvax': 'Korvax', '2': 'Korvax',
            'Robots': 'None', 'Robots_': 'None', '3': 'None',
            'Atlas': 'None', 'Atlas_': 'None', '4': 'None',
            'Diplomats': 'None', 'Diplomats_': 'None', '5': 'None',
            'None': 'None', 'None_': 'None', '6': 'None',
        }

        # Get other properties from NMS.py struct access
        try:
            if result["star_color"] == "Unknown" and hasattr(sys_data, 'Class'):
                raw_star = self._safe_enum(sys_data.Class)
                result["star_color"] = STAR_COLOR_MAP.get(raw_star, STAR_COLOR_MAP.get(raw_star.rstrip('_'), 'Yellow'))
                logger.debug(f"  Star color: raw='{raw_star}' -> '{result['star_color']}'")
        except Exception:
            pass

        try:
            if hasattr(sys_data, 'TradingData'):
                trading = sys_data.TradingData
                if result["economy_type"] == "Unknown" and hasattr(trading, 'TradingClass'):
                    result["economy_type"] = self._safe_enum(trading.TradingClass)
                if result["economy_strength"] == "Unknown" and hasattr(trading, 'WealthClass'):
                    result["economy_strength"] = self._safe_enum(trading.WealthClass)
                if result["conflict_level"] == "Unknown" and hasattr(trading, 'ConflictLevel'):
                    result["conflict_level"] = self._safe_enum(trading.ConflictLevel)
        except Exception:
            pass

        try:
            if result["conflict_level"] == "Unknown" and hasattr(sys_data, 'ConflictData'):
                result["conflict_level"] = self._safe_enum(sys_data.ConflictData)
        except Exception:
            pass

        try:
            if hasattr(sys_data, 'InhabitingRace') and result["dominant_lifeform"] == "Unknown":
                raw_race = self._safe_enum(sys_data.InhabitingRace)
                result["dominant_lifeform"] = LIFEFORM_MAP.get(raw_race, LIFEFORM_MAP.get(raw_race.rstrip('_'), 'None'))
                logger.debug(f"  Dominant lifeform: raw='{raw_race}' -> '{result['dominant_lifeform']}'")
        except Exception:
            pass

        try:
            if hasattr(sys_data, 'Seed') and hasattr(sys_data.Seed, 'Seed'):
                result["system_seed"] = self._safe_int(sys_data.Seed.Seed)
        except Exception:
            pass

        return result

    def _extract_planets(self, solar_system) -> list:
        """Extract planet data - ONLY valid slots based on Planets count."""
        planets = []

        logger.info("=" * 30)
        logger.info("EXTRACTING PLANETS")
        logger.info("=" * 30)

        # Get actual planet count from system data - THIS IS CRITICAL
        # maPlanets is always a 6-slot array, but only first N have valid data
        actual_planet_count = 6  # Default max
        prime_planet_count = 0
        try:
            sys_data = solar_system.mSolarSystemData
            logger.info(f"  sys_data object: {sys_data}")

            if hasattr(sys_data, 'Planets'):
                planets_raw = sys_data.Planets
                actual_planet_count = self._safe_int(planets_raw)
                logger.info(f"  *** VALID PLANET COUNT: {actual_planet_count} (raw: {planets_raw}, type: {type(planets_raw).__name__})")

            if hasattr(sys_data, 'PrimePlanets'):
                prime_raw = sys_data.PrimePlanets
                prime_planet_count = self._safe_int(prime_raw)
                logger.info(f"  *** PRIME PLANETS: {prime_planet_count} (raw: {prime_raw}, type: {type(prime_raw).__name__})")
            else:
                logger.warning(f"  *** PrimePlanets attribute not found!")
        except Exception as e:
            logger.warning(f"  Could not get planet count: {e}")
            import traceback
            logger.warning(traceback.format_exc())

        # Calculate expected moons: total - prime = moons
        expected_moons = actual_planet_count - prime_planet_count
        logger.info(f"  *** EXPECTED MOONS: {expected_moons}")

        try:
            planets_array = solar_system.maPlanets
            logger.info(f"  planets_array object: {planets_array}")

            # CRITICAL FIX: Only iterate through VALID planet slots
            # Remaining slots (N to 5) contain default/empty data
            for i in range(min(actual_planet_count, 6)):
                try:
                    planet = planets_array[i]
                    logger.info(f"  --- Processing slot {i} ---")

                    if planet is None:
                        logger.warning(f"  Slot {i}: None (unexpected for valid slot)")
                        continue

                    planet_addr = get_addressof(planet)
                    if planet_addr == 0:
                        logger.warning(f"  Slot {i}: NULL pointer (unexpected for valid slot)")
                        continue

                    logger.info(f"  Slot {i}: address 0x{planet_addr:X}")

                    planet_data = self._extract_single_planet(planet, i)
                    if planet_data:
                        planets.append(planet_data)
                        body_type = "MOON" if planet_data.get('is_moon', False) else "PLANET"
                        logger.info(f"  Slot {i}: [{body_type}] {planet_data.get('planet_name', 'Unknown')} - {planet_data.get('biome', 'Unknown')}")
                    else:
                        logger.warning(f"  Slot {i}: Failed to extract data")

                except Exception as e:
                    logger.error(f"  Slot {i} extraction failed: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    continue

        except Exception as e:
            logger.error(f"Planet array access failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        # Count results
        moon_count = sum(1 for p in planets if p.get('is_moon', False))
        planet_count = len(planets) - moon_count
        logger.info("=" * 30)
        logger.info(f"EXTRACTION COMPLETE: {planet_count} planets + {moon_count} moons = {len(planets)} total")
        logger.info(f"Expected: {prime_planet_count} planets + {expected_moons} moons = {actual_planet_count} total")
        logger.info("=" * 30)
        return planets

    def _extract_single_planet(self, planet, index: int) -> Optional[dict]:
        """Extract data from a single planet using DIRECT MEMORY READ as primary source."""
        try:
            result = {
                "planet_index": index,
                "planet_name": f"Planet_{index + 1}",
                "biome": "Unknown",
                "biome_subtype": "Unknown",
                "weather": "Unknown",
                "sentinel_level": "Unknown",
                "flora_level": "Unknown",
                "fauna_level": "Unknown",
                "common_resource": "Unknown",
                "uncommon_resource": "Unknown",
                "rare_resource": "Unknown",
                "is_moon": False,
                "planet_size": "Unknown",
            }

            # =====================================================
            # CRITICAL v8.1.1: DIRECT MEMORY READ as PRIMARY SOURCE
            # Read from SolarSystemData + 0x1EA0 (planet gen input array)
            # Each planet entry is 0x53 bytes (83 bytes)
            # This is the CORRECT memory location - struct mapping was unreliable!
            # =====================================================
            if self._cached_sys_data_addr:
                logger.info(f"    [DIRECT] Using direct memory read for planet {index}")
                direct_data = self._read_planet_gen_input_direct(self._cached_sys_data_addr, index)

                # Apply direct-read biome (CRITICAL - this is the fix!)
                raw_biome = direct_data.get("biome_raw", -1)
                if raw_biome >= 0:
                    result["biome"] = direct_data["biome"]
                    logger.info(f"    [DIRECT] Biome = {result['biome']} (raw: {raw_biome})")

                # Apply direct-read planet_size (CRITICAL - this is the fix!)
                raw_size = direct_data.get("planet_size_raw", -1)
                if raw_size >= 0:
                    result["planet_size"] = direct_data["planet_size"]
                    result["is_moon"] = direct_data.get("is_moon", False)
                    logger.info(f"    [DIRECT] PlanetSize = {result['planet_size']} (raw: {raw_size}, is_moon: {result['is_moon']})")

                # Apply direct-read biome_subtype
                raw_subtype = direct_data.get("biome_subtype_raw", -1)
                if raw_subtype >= 0:
                    result["biome_subtype"] = direct_data["biome_subtype"]
                    logger.info(f"    [DIRECT] BiomeSubType = {result['biome_subtype']} (raw: {raw_subtype})")

                # Apply direct-read resources
                if direct_data.get("common_resource"):
                    result["common_resource"] = direct_data["common_resource"]
                if direct_data.get("rare_resource"):
                    result["rare_resource"] = direct_data["rare_resource"]
            else:
                logger.warning(f"    [DIRECT] No cached sys_data_addr - cannot use direct memory read!")

            # =====================================================
            # CAPTURED DATA: Use GenerateCreatureRoles hook data
            # v8.1.6: NOW INCLUDES BIOME from GenerationData - this is RELIABLE!
            # =====================================================
            if index in self._captured_planets:
                captured = self._captured_planets[index]
                logger.info(f"    [CAPTURED] Using captured data for planet {index}")

                # CRITICAL v8.1.6: Apply captured BIOME data (from GenerationData - reliable!)
                # This overrides the unreliable direct memory read
                if captured.get('biome_raw', -1) >= 0:
                    result["biome"] = captured.get('biome', result["biome"])
                    logger.info(f"    [CAPTURED] Biome = {result['biome']} (raw: {captured.get('biome_raw')})")
                if captured.get('biome_subtype_raw', -1) >= 0:
                    result["biome_subtype"] = captured.get('biome_subtype', result["biome_subtype"])
                    logger.info(f"    [CAPTURED] BiomeSubType = {result['biome_subtype']} (raw: {captured.get('biome_subtype_raw')})")

                # CRITICAL v8.1.9: Apply captured PLANET SIZE data (from GenerationData.Size - reliable!)
                # This overrides the GARBAGE values from direct memory read (was showing 256, 33554432, etc)
                if captured.get('planet_size_raw', -1) >= 0:
                    result["planet_size"] = captured.get('planet_size', result["planet_size"])
                    result["is_moon"] = captured.get('is_moon', False)
                    logger.info(f"    [CAPTURED] PlanetSize = {result['planet_size']} (raw: {captured.get('planet_size_raw')}, is_moon: {result['is_moon']})")

                # Apply captured flora/fauna/sentinel data with CONTEXTUAL adjectives
                # v10.2.0: Use biome-specific mappings for variety
                biome_key = result["biome"]  # Already determined above

                # Flora - use biome-specific mapping if available
                flora_raw = captured.get('flora_raw', -1)
                if flora_raw >= 0 and biome_key in self.FLORA_BY_BIOME:
                    result["flora_level"] = self.FLORA_BY_BIOME[biome_key].get(flora_raw, captured.get('flora', 'Unknown'))
                else:
                    result["flora_level"] = captured.get('flora', 'Unknown')

                # Fauna - use biome-specific mapping if available
                fauna_raw = captured.get('fauna_raw', -1)
                if fauna_raw >= 0 and biome_key in self.FAUNA_BY_BIOME:
                    result["fauna_level"] = self.FAUNA_BY_BIOME[biome_key].get(fauna_raw, captured.get('fauna', 'Unknown'))
                else:
                    result["fauna_level"] = captured.get('fauna', 'Unknown')

                # Sentinel - use biome-specific mapping if available
                sentinel_raw = captured.get('sentinel_raw', -1)
                if sentinel_raw >= 0 and biome_key in self.SENTINEL_BY_BIOME:
                    result["sentinel_level"] = self.SENTINEL_BY_BIOME[biome_key].get(sentinel_raw, captured.get('sentinel', 'Unknown'))
                else:
                    result["sentinel_level"] = captured.get('sentinel', 'Unknown')

                # Apply captured resources if not already set from direct read (translate to readable names)
                if result["common_resource"] == "Unknown" and captured.get('common_resource'):
                    result["common_resource"] = translate_resource(captured['common_resource'])
                if captured.get('uncommon_resource'):
                    result["uncommon_resource"] = translate_resource(captured['uncommon_resource'])
                if result["rare_resource"] == "Unknown" and captured.get('rare_resource'):
                    result["rare_resource"] = translate_resource(captured['rare_resource'])

                # v10.2.0: Apply captured weather with CONTEXTUAL adjectives
                # Uses biome + weather_raw + storm_raw for variety
                if captured.get('weather') and captured.get('weather_raw', -1) >= 0:
                    weather_raw = captured.get('weather_raw', -1)
                    storm_raw = captured.get('storm_raw', 0)
                    storm_info = captured.get('storm_frequency', '')

                    # Try contextual weather lookup: (biome, weather_enum, storm_frequency)
                    weather_key = (biome_key, weather_raw, storm_raw)
                    contextual_weather = self.WEATHER_CONTEXTUAL.get(weather_key)

                    if contextual_weather:
                        result["weather"] = contextual_weather
                        logger.info(f"    [CAPTURED] Weather = {result['weather']} (contextual: biome={biome_key}, weather={weather_raw}, storm={storm_raw})")
                    else:
                        # v10.2.0: Convert internal weather name to user-friendly adjective
                        raw_weather_name = captured['weather']
                        result["weather"] = self.WEATHER_FALLBACK.get(raw_weather_name, raw_weather_name)
                        if storm_info:
                            logger.info(f"    [CAPTURED] Weather = {result['weather']} (from {raw_weather_name}, storms: {storm_info})")
                        else:
                            logger.info(f"    [CAPTURED] Weather = {result['weather']}")
                elif result["weather"] == "Unknown" and captured.get('weather'):
                    # Fallback to any weather value if raw not available
                    # v10.2.0: Still convert to user-friendly adjective
                    raw_weather_name = captured['weather']
                    result["weather"] = self.WEATHER_FALLBACK.get(raw_weather_name, raw_weather_name)
                    logger.info(f"    [CAPTURED] Weather = {result['weather']} (fallback from {raw_weather_name})")

                # v8.1.7: Apply captured planet name from cGcPlanetData.Name
                # This is the RELIABLE source - captures all planet names when hook fires
                if captured.get('planet_name'):
                    result["planet_name"] = captured['planet_name']
                    logger.info(f"    [CAPTURED] PlanetName = {result['planet_name']}")

                logger.info(f"    [CAPTURED] Applied: flora={result['flora_level']}, fauna={result['fauna_level']}, sentinel={result['sentinel_level']}")
            else:
                # Planet not in captured data - hook didn't fire for this planet
                logger.warning(f"    [NOCAPTURE] Planet {index} not in captured data - hook may not have fired")

            # NOTE: miPlanetIndex often returns garbage values - we use array index instead
            try:
                if hasattr(planet, 'miPlanetIndex'):
                    mi_idx = self._safe_int(planet.miPlanetIndex)
                    logger.debug(f"    [DEBUG] miPlanetIndex = {mi_idx} (ignoring, using array index {index})")
            except Exception as e:
                logger.debug(f"    miPlanetIndex access failed: {e}")

            # FALLBACK: NMS.py struct mapping (only if direct read failed)
            # This is unreliable but kept as a last resort
            if result["biome"] == "Unknown" or result["planet_size"] == "Unknown":
                logger.info(f"    [FALLBACK] Direct read incomplete, trying NMS.py struct mapping...")
                try:
                    if hasattr(planet, 'mPlanetGenerationInputData'):
                        gen_input = planet.mPlanetGenerationInputData

                        # PlanetSize - only if not already set
                        if result["planet_size"] == "Unknown" and hasattr(gen_input, 'PlanetSize'):
                            size_val = gen_input.PlanetSize
                            raw_size = None
                            try:
                                if hasattr(size_val, 'value'):
                                    raw_size = size_val.value
                                else:
                                    raw_size = int(size_val)
                            except:
                                pass

                            if raw_size is not None and 0 <= raw_size <= 4:
                                size_name = self._safe_enum(size_val)
                                result["planet_size"] = size_name
                                result["is_moon"] = (raw_size == 3)
                                logger.info(f"    [FALLBACK] PlanetSize = {size_name} (raw: {raw_size})")

                        # Biome - only if not already set
                        if result["biome"] == "Unknown" and hasattr(gen_input, 'Biome'):
                            biome_val = gen_input.Biome
                            raw_biome = None
                            try:
                                if hasattr(biome_val, 'value'):
                                    raw_biome = biome_val.value
                                else:
                                    raw_biome = int(biome_val)
                            except:
                                pass

                            if raw_biome is not None and 0 <= raw_biome <= 16:
                                result["biome"] = self._validate_biome(biome_val, raw_biome)
                                logger.info(f"    [FALLBACK] Biome = {result['biome']} (raw: {raw_biome})")

                        # BiomeSubType
                        if result["biome_subtype"] == "Unknown" and hasattr(gen_input, 'BiomeSubType'):
                            result["biome_subtype"] = self._safe_enum(gen_input.BiomeSubType)
                            logger.info(f"    [FALLBACK] BiomeSubType = {result['biome_subtype']}")

                except Exception as e:
                    logger.warning(f"    [FALLBACK] NMS.py struct mapping failed: {e}")

            # SECONDARY SOURCE: mPlanetData (has name, weather, sentinels, etc.)
            planet_data = None
            try:
                if hasattr(planet, 'mPlanetData'):
                    planet_data = planet.mPlanetData
            except Exception:
                pass

            if planet_data is not None:
                # Planet name
                try:
                    if hasattr(planet_data, 'Name'):
                        name = str(planet_data.Name)
                        if name and len(name) > 0 and name != "None":
                            result["planet_name"] = name
                except Exception:
                    pass

                # PlanetInfo - display strings
                try:
                    if hasattr(planet_data, 'PlanetInfo'):
                        info = planet_data.PlanetInfo

                        # If biome still unknown, try PlanetType string
                        if result["biome"] == "Unknown" and hasattr(info, 'PlanetType'):
                            pt = str(info.PlanetType)
                            if pt and pt != "None" and len(pt) > 0:
                                result["biome"] = pt

                        if hasattr(info, 'Weather'):
                            val = str(info.Weather)
                            if val and val != "None":
                                result["weather"] = clean_weather_string(val)

                        # NOTE: SentinelsPerDifficulty, Flora, Fauna are array types
                        # We already get these from the GenerateCreatureRoles hook
                        # Skip these fallbacks to avoid overwriting good data with object references
                except Exception:
                    pass

                # Resources from PlanetData if not already set - clean and translate to readable names
                try:
                    if result["common_resource"] == "Unknown" and hasattr(planet_data, 'CommonSubstanceID'):
                        val = self._clean_resource_string(str(planet_data.CommonSubstanceID))
                        if val:
                            result["common_resource"] = translate_resource(val)

                    if hasattr(planet_data, 'UncommonSubstanceID'):
                        val = self._clean_resource_string(str(planet_data.UncommonSubstanceID))
                        if val:
                            result["uncommon_resource"] = translate_resource(val)

                    if result["rare_resource"] == "Unknown" and hasattr(planet_data, 'RareSubstanceID'):
                        val = self._clean_resource_string(str(planet_data.RareSubstanceID))
                        if val:
                            result["rare_resource"] = translate_resource(val)
                except Exception:
                    pass

            return result

        except Exception as e:
            logger.debug(f"Planet {index} data extraction failed: {e}")
            return None

    def _safe_enum(self, val, default: str = "Unknown") -> str:
        """Safely convert enum to string, with normalization."""
        try:
            if val is None:
                return default
            if hasattr(val, 'name'):
                name = val.name
            elif hasattr(val, 'value'):
                name = str(val.value)
            else:
                name = str(val)
            # Normalize: strip trailing underscores (None_ -> None)
            return name.rstrip('_') if name else default
        except Exception:
            return default

    def _safe_int(self, val, default: int = 0) -> int:
        """Safely convert value to int."""
        try:
            if val is None:
                return default
            if hasattr(val, 'value'):
                return int(val.value)
            return int(val)
        except Exception:
            return default

    def _clean_resource_string(self, val: str) -> str:
        """Clean a resource string, removing garbage characters."""
        if not val or val == "None":
            return ""
        # Only keep printable ASCII characters
        cleaned = ''.join(c for c in str(val) if c.isprintable() and ord(c) < 128)
        # Validate it looks like a valid resource ID
        if cleaned and len(cleaned) >= 2 and cleaned[0].isalpha():
            return cleaned
        return ""

    def _validate_biome(self, biome_val, raw_val) -> str:
        """Validate biome value, returning 'Unknown' for garbage."""
        biome_name = self._safe_enum(biome_val)
        # Check if raw value is a valid biome index (0-16)
        if raw_val is not None:
            if isinstance(raw_val, int) and 0 <= raw_val <= 16:
                return biome_name
            # Invalid raw value
            return "Unknown"
        return biome_name

    def _coords_to_glyphs(self, planet: int, system: int, x: int, y: int, z: int) -> str:
        """Convert coordinates to portal glyph code."""
        try:
            portal_x = (x + 2047) & 0xFFF
            portal_y = (y + 127) & 0xFF
            portal_z = (z + 2047) & 0xFFF
            portal_sys = system & 0x1FF
            portal_planet = planet & 0xF
            glyph = f"{portal_planet:01X}{portal_sys:03X}{portal_y:02X}{portal_z:03X}{portal_x:03X}"
            return glyph.upper()
        except Exception:
            return "000000000000"

    def _glyph_to_portal_code(self, glyph: str) -> int:
        """Convert glyph string (e.g., '00940F34B00A') to portal code integer."""
        try:
            return int(glyph, 16)
        except (ValueError, TypeError):
            return 0

    def _coords_to_portal_code(self, system_idx: int, x: int, y: int, z: int, planet: int = 0) -> int:
        """Convert coordinates to full 48-bit portal code for name generation.

        IMPORTANT: Uses full 12-bit system index, not 9-bit glyph version.
        Standard portal glyphs only encode 9 bits (max 511), but NMS uses
        full 12-bit system indices (max 4095) for name generation.
        """
        portal_x = (x + 2047) & 0xFFF      # 12 bits
        portal_y = (y + 127) & 0xFF        # 8 bits
        portal_z = (z + 2047) & 0xFFF      # 12 bits
        portal_sys = system_idx & 0xFFF    # 12 bits (FULL, not 9-bit truncated!)
        portal_planet = planet & 0xF       # 4 bits

        # Build 48-bit portal code: PSSS YYZZ ZXXX (but with 12-bit system)
        portal_code = (portal_planet << 44) | (portal_sys << 32) | (portal_y << 24) | (portal_z << 12) | portal_x
        return portal_code

    def _get_actual_system_name(self) -> str:
        """Get the actual in-game system name from solar system data.

        Reads directly from cGcSolarSystemData.Name at offset 0x2274.
        Note: This field may be empty during planet generation and
        only gets populated later. Call this during export, not capture.

        Returns:
            System name string, or empty string if not found
        """
        # Try reading from cached solar system's Name field
        if self._cached_solar_system:
            try:
                solar_sys_addr = get_addressof(self._cached_solar_system)
                # Name is at offset 0x2274 from solar system start
                name_addr = solar_sys_addr + 0x2274

                # Read 128 bytes (cTkFixedString<0x80>)
                buffer = (ctypes.c_char * 128)()
                ctypes.memmove(buffer, name_addr, 128)
                raw = bytes(buffer)

                # Find null terminator
                null_idx = raw.find(b'\x00')
                if null_idx > 0:
                    name = raw[:null_idx].decode('utf-8', errors='ignore').strip()
                    if name:
                        logger.info(f"  [SYSNAME] Got: '{name}'")
                        return name

            except Exception as e:
                logger.debug(f"  [SYSNAME] Read failed: {e}")

        return ""

    def _generate_system_name(self, glyph_code: str, galaxy_idx: int = 0,
                               system_idx: int = None, x: int = None, y: int = None, z: int = None) -> str:
        """Generate procedural system name using NMS algorithm.

        Args:
            glyph_code: 12-character hex glyph string (fallback identifier)
            galaxy_idx: Galaxy index (0 = Euclid, 1 = Hilbert, etc.)
            system_idx: Full 12-bit system index (if available)
            x, y, z: Voxel coordinates (if available)

        Returns:
            Procedurally generated system name, or fallback if generation fails
        """
        if not NMS_NAMEGEN_AVAILABLE:
            return f"System_{glyph_code}"

        try:
            # Use full coordinates if provided (preferred - uses 12-bit system index)
            if system_idx is not None and x is not None and y is not None and z is not None:
                portal_code = self._coords_to_portal_code(system_idx, x, y, z)
            else:
                # Fallback to glyph code (only 9-bit system index)
                portal_code = self._glyph_to_portal_code(glyph_code)

            if portal_code == 0:
                return f"System_{glyph_code}"

            name = nms_system_name(portal_code, galaxy_idx)
            logger.debug(f"  [v10.1.1] Generated system name: '{name}' (sys_idx={system_idx})")
            return name
        except Exception as e:
            logger.debug(f"  [v10.1.1] System name generation failed: {e}")
            return f"System_{glyph_code}"

    def _generate_region_name(self, glyph_code: str, galaxy_idx: int = 0,
                               system_idx: int = None, x: int = None, y: int = None, z: int = None) -> str:
        """Generate procedural region name using NMS algorithm.

        Args:
            glyph_code: 12-character hex glyph string (fallback identifier)
            galaxy_idx: Galaxy index (0 = Euclid, 1 = Hilbert, etc.)
            system_idx: Full 12-bit system index (if available)
            x, y, z: Voxel coordinates (if available)

        Returns:
            Procedurally generated region name, or fallback if generation fails
        """
        if not NMS_NAMEGEN_AVAILABLE:
            return f"Region_{glyph_code[:8]}"

        try:
            # Use full coordinates if provided (preferred - uses 12-bit system index)
            if system_idx is not None and x is not None and y is not None and z is not None:
                portal_code = self._coords_to_portal_code(system_idx, x, y, z)
            else:
                # Fallback to glyph code (only 9-bit system index)
                portal_code = self._glyph_to_portal_code(glyph_code)

            if portal_code == 0:
                return f"Region_{glyph_code[:8]}"

            name = nms_region_name(portal_code, galaxy_idx)
            logger.debug(f"  [v10.1.1] Generated region name: '{name}' (sys_idx={system_idx})")
            return name
        except Exception as e:
            logger.debug(f"  [v10.1.1] Region name generation failed: {e}")
            return f"Region_{glyph_code[:8]}"

    def _write_extraction(self, data: dict):
        """Save extraction data locally (NO auto-send to API - use Save Watcher for manual upload)."""
        # Save local backup
        try:
            latest = self._output_dir / "latest.json"
            with open(latest, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            timestamped = self._output_dir / f"extraction_{ts}.json"
            with open(timestamped, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"=" * 50)
            logger.info(f">>> EXTRACTION SAVED <<<")
            logger.info(f"  Latest: {latest}")
            logger.info(f"  Backup: {timestamped}")
            logger.info(f"")
            logger.info(f">>> Use Save Watcher to manually upload to Haven UI <<<")
            logger.info(f"=" * 50)

        except Exception as e:
            logger.error(f"Local save failed: {e}")

    def _write_batch_extraction(self, data: dict):
        """
        Save BATCH extraction data locally.
        v8.2.0: Saves all systems in batch to separate files.
        """
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            system_count = data.get('total_systems', 0)

            # Save batch file with all systems
            batch_file = self._output_dir / f"batch_{system_count}systems_{ts}.json"
            with open(batch_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

            # Also update latest.json with the batch data
            latest = self._output_dir / "latest.json"
            with open(latest, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f"=" * 50)
            logger.info(f">>> BATCH EXTRACTION SAVED <<<")
            logger.info(f"  Batch file: {batch_file}")
            logger.info(f"  Latest: {latest}")
            logger.info(f"  Systems: {system_count}")
            logger.info(f"  Planets: {data.get('total_planets', 0)}")
            logger.info(f"")
            logger.info(f">>> Use Save Watcher to manually upload to Haven UI <<<")
            logger.info(f"=" * 50)

        except Exception as e:
            logger.error(f"Batch save failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _send_to_api(self, data: dict):
        """Send extraction data to Haven UI via HTTP POST."""
        api_url = f"{API_BASE_URL.rstrip('/')}/api/extraction"

        try:
            # Prepare JSON payload
            json_data = json.dumps(data, default=str).encode('utf-8')

            # Create request
            req = urllib.request.Request(
                api_url,
                data=json_data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': f'HavenExtractor/{self.__version__}',
                }
            )

            # Add API key if configured
            if API_KEY:
                req.add_header('X-API-Key', API_KEY)

            # Create SSL context that doesn't verify certificates (for ngrok)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # Send request
            logger.info(f"Sending extraction to: {api_url}")
            with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                response_data = json.loads(response.read().decode('utf-8'))

                if response.status in (200, 201):
                    logger.info("=" * 50)
                    logger.info(">>> EXTRACTION SENT TO HAVEN UI <<<")
                    logger.info(f"  Status: {response_data.get('status', 'ok')}")
                    logger.info(f"  Message: {response_data.get('message', '')}")
                    logger.info(f"  Submission ID: {response_data.get('submission_id', 'N/A')}")
                    logger.info(f"  Planets: {response_data.get('planet_count', 0)}")
                    logger.info(f"  Moons: {response_data.get('moon_count', 0)}")
                    logger.info("=" * 50)
                else:
                    logger.warning(f"API returned status {response.status}: {response_data}")

        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode('utf-8')
            except:
                pass
            logger.error(f"API request failed (HTTP {e.code}): {error_body}")
            logger.error("Data saved locally - you can manually submit later")

        except urllib.error.URLError as e:
            logger.error(f"Cannot connect to API: {e.reason}")
            logger.error(f"Check that API_BASE_URL is correct: {API_BASE_URL}")
            logger.error("Data saved locally - you can manually submit later")

        except Exception as e:
            logger.error(f"API send failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            logger.error("Data saved locally - you can manually submit later")
