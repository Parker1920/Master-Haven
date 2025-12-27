"""
Extraction Watcher - Monitor for Haven Extractor output.

This module provides functionality to watch the Haven Extractor output
directory and process new extractions as they appear.

This can be integrated into the main NMS-Save-Watcher or run standalone.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Dict, Any
from threading import Thread, Event

logger = logging.getLogger(__name__)


# =============================================================================
# NMS Game Value Translation Maps
# =============================================================================
# These translate raw NMS internal IDs/enums to human-readable values
# that the Haven Control Room expects.

# Load resource mappings from resources.json if available
def _load_resource_map() -> Dict[str, str]:
    """Load resource ID to name mappings from resources.json."""
    resource_map = {}

    # Try to load from data/resources.json
    for base_path in [Path(__file__).parent.parent, Path.cwd()]:
        json_path = base_path / "data" / "resources.json"
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    resource_map.update(data.get("elements", {}))
                    resource_map.update(data.get("special", {}))
                    break
            except Exception as e:
                logger.warning(f"Failed to load resources.json: {e}")

    # Add fallback mappings for common resources
    fallback = {
        # Stellar metals (common deposits on planets)
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
        # Plants/Flora resources
        "PLANT_POOP": "Mordite",
        "PLANT_TOXIC": "Fungal Mould",
        "PLANT_SNOW": "Frost Crystal",
        "PLANT_HOT": "Solanium",
        "PLANT_RADIO": "Gamma Root",
        "PLANT_DUST": "Cactus Flesh",
        "PLANT_LUSH": "Star Bulb",
        "PLANT_CAVE": "Marrow Bulb",
        "PLANT_WATER": "Kelp Sac",
        # Space gunk
        "SPACEGUNK1": "Residual Goop",
        "SPACEGUNK2": "Runaway Mould",
        "SPACEGUNK3": "Living Slime",
        "SPACEGUNK4": "Viscous Fluids",
        "SPACEGUNK5": "Tainted Metal",
    }

    # Merge fallback with loaded (loaded takes precedence)
    for key, value in fallback.items():
        if key not in resource_map:
            resource_map[key] = value

    return resource_map

RESOURCE_MAP = _load_resource_map()


def translate_resource(resource_id: str) -> str:
    """Translate a resource ID to human-readable name."""
    if not resource_id or resource_id == "Unknown":
        return "Unknown"

    # Direct lookup
    if resource_id in RESOURCE_MAP:
        return RESOURCE_MAP[resource_id]

    # Try uppercase
    if resource_id.upper() in RESOURCE_MAP:
        return RESOURCE_MAP[resource_id.upper()]

    # Return cleaned up version
    cleaned = resource_id.replace("_", " ").title()
    import re
    cleaned = re.sub(r'\d+$', '', cleaned).strip()
    return cleaned if cleaned else resource_id

# Biome translations (NMS internal -> Human readable)
BIOME_MAP = {
    # Lush biomes
    "LUSH": "Lush",
    "LUSH1": "Lush",
    "LUSH2": "Lush",
    "LUSH3": "Lush",
    "LUSHBUBBLE": "Lush (Bubble)",
    "LUSHHQ": "Lush (Paradise)",
    "LUSHROOM": "Lush (Fungal)",

    # Barren biomes
    "BARREN": "Barren",
    "BARREN1": "Barren",
    "BARREN2": "Barren",
    "BARREN3": "Barren",
    "BARRENHQ": "Barren (Dead)",

    # Scorched biomes
    "SCORCHED": "Scorched",
    "SCORCHED1": "Scorched",
    "SCORCHED2": "Scorched",
    "SCORCHED3": "Scorched",
    "SCORCHEDHQ": "Scorched (Volcanic)",

    # Frozen biomes
    "FROZEN": "Frozen",
    "FROZEN1": "Frozen",
    "FROZEN2": "Frozen",
    "FROZEN3": "Frozen",
    "FROZENHQ": "Frozen (Glacial)",

    # Toxic biomes
    "TOXIC": "Toxic",
    "TOXIC1": "Toxic",
    "TOXIC2": "Toxic",
    "TOXIC3": "Toxic",
    "TOXICHQ": "Toxic (Caustic)",

    # Radioactive biomes
    "RADIOACTIVE": "Radioactive",
    "RADIOACTIVE1": "Radioactive",
    "RADIOACTIVE2": "Radioactive",
    "RADIOACTIVE3": "Radioactive",
    "RADIOACTIVEHQ": "Radioactive (Nuclear)",

    # Swamp biomes
    "SWAMP": "Swamp",
    "SWAMP1": "Swamp",
    "SWAMP2": "Swamp",
    "SWAMPHQ": "Swamp (Marsh)",

    # Exotic/Anomalous biomes
    "WEIRD": "Exotic",
    "WEIRD1": "Exotic (Hexagonal)",
    "WEIRD2": "Exotic (Pillars)",
    "WEIRD3": "Exotic (Bubble)",
    "WEIRD4": "Exotic (Contour)",
    "WEIRD5": "Exotic (Shattered)",
    "WEIRD6": "Exotic (Beam)",
    "WEIRD7": "Exotic (Wire)",

    # Dead/Airless
    "DEAD": "Dead",
    "DEAD1": "Dead",
    "DEAD2": "Dead",
    "DEAD3": "Dead",
    "AIRLESS": "Airless",

    # Lava/Volcanic biomes
    "LAVA": "Lava",
    "LAVA1": "Lava",
    "LAVA2": "Lava",
    "LAVA3": "Lava",
    "VOLCANIC": "Volcanic",
    "Lava": "Lava",

    # Water worlds
    "WATERWORLD": "Ocean",

    # Infested biomes
    "INFESTED": "Infested",
    "INFESTEDLUSH": "Infested (Lush)",
    "INFESTEDTOXIC": "Infested (Toxic)",
    "INFESTEDRADIOACTIVE": "Infested (Radioactive)",
    "INFESTEDFROZEN": "Infested (Frozen)",
    "INFESTEDSCORCHED": "Infested (Scorched)",
    "INFESTEDBARREN": "Infested (Barren)",
}

# Weather translations
# Includes numbered variants (WEATHER_COLD10, WEATHER_HEAT5, etc.)
WEATHER_MAP = {
    # Calm/Clear
    "WEATHER_CLEAR": "Clear",
    "WEATHER_FINE": "Fine",
    "WEATHER_CALM": "Calm",
    "WEATHER_PLEASANT": "Pleasant",
    "WEATHER_BLISSFUL": "Blissful",
    "WEATHER_MILD": "Mild",
    "WEATHER_MODERATE": "Moderate",

    # Hot weather (numbered variants)
    "WEATHER_HOT": "Hot",
    "WEATHER_SCORCHING": "Scorching",
    "WEATHER_BURNING": "Burning",
    "WEATHER_EXTREME_HOT": "Extreme Heat",
    "WEATHER_FIRESTORM": "Firestorm",
    "WEATHER_SUPERHEATED": "Superheated",
    "WEATHER_HEAT": "Hot",
    "WEATHER_HEAT1": "Hot",
    "WEATHER_HEAT2": "Hot",
    "WEATHER_HEAT3": "Hot",
    "WEATHER_HEAT4": "Hot",
    "WEATHER_HEAT5": "Hot",
    "WEATHER_HEAT6": "Hot",
    "WEATHER_HEATEXTREME": "Extreme Heat",
    "WEATHER_HEATEXTREME1": "Extreme Heat",
    "WEATHER_HEATEXTREME2": "Extreme Heat",
    "WEATHER_HEATEXTREME3": "Extreme Heat",
    "WEATHER_HEATEXTREME4": "Extreme Heat",
    "WEATHER_HEATEXTREME5": "Extreme Heat",
    "Scorched": "Scorching",

    # Cold weather (numbered variants)
    "WEATHER_COLD": "Cold",
    "WEATHER_FREEZING": "Freezing",
    "WEATHER_BLIZZARD": "Blizzard",
    "WEATHER_EXTREME_COLD": "Extreme Cold",
    "WEATHER_ICESTORM": "Ice Storm",
    "WEATHER_SNOWFALL": "Snowfall",
    "WEATHER_COLD1": "Cold",
    "WEATHER_COLD2": "Cold",
    "WEATHER_COLD3": "Cold",
    "WEATHER_COLD4": "Freezing",
    "WEATHER_COLD5": "Freezing",
    "WEATHER_COLD6": "Freezing",
    "WEATHER_COLD7": "Icy",
    "WEATHER_COLD8": "Icy",
    "WEATHER_COLD9": "Frigid",
    "WEATHER_COLD10": "Frigid",
    "WEATHER_COLD_CLEAR": "Cold and Clear",
    "WEATHER_COLD_CLEAR1": "Cold and Clear",
    "WEATHER_COLD_CLEAR2": "Cold and Clear",
    "WEATHER_COLD_CLEAR3": "Cold and Clear",

    # Toxic weather (numbered variants)
    "WEATHER_TOXIC": "Toxic",
    "WEATHER_POISON": "Poison",
    "WEATHER_NOXIOUS": "Noxious",
    "WEATHER_CORROSIVE": "Corrosive",
    "WEATHER_ACIDRAIN": "Acid Rain",
    "WEATHER_CHOKING": "Choking Clouds",
    "WEATHER_TOXIC1": "Toxic",
    "WEATHER_TOXIC2": "Toxic",
    "WEATHER_TOXIC3": "Noxious",
    "WEATHER_TOXIC4": "Noxious",
    "WEATHER_TOXIC5": "Corrosive",
    # Toxic clear variants (low toxicity)
    "WEATHER_TOXIC_CLEAR": "Mild Toxicity",
    "WEATHER_TOXIC_CLEAR1": "Mild Toxicity",
    "WEATHER_TOXIC_CLEAR2": "Mild Toxicity",
    "WEATHER_TOXIC_CLEAR3": "Mild Toxicity",
    "WEATHER_TOXIC_CLEAR4": "Mild Toxicity",
    "WEATHER_TOXIC_CLEAR5": "Mild Toxicity",
    "WEATHER_TOXIC_CLEAR6": "Mild Toxicity",
    "WEATHER_TOXIC_CLEAR7": "Mild Toxicity",

    # Radioactive weather (numbered variants)
    "WEATHER_RADIATION": "Radiation",
    "WEATHER_IRRADIATED": "Irradiated",
    "WEATHER_NUCLEARSTORM": "Nuclear Storm",
    "WEATHER_EXTREME_RADIATION": "Extreme Radiation",
    "WEATHER_RADIO": "Irradiated",
    "WEATHER_RADIO1": "Irradiated",
    "WEATHER_RADIO2": "Irradiated",
    "WEATHER_RADIO3": "Radioactive",
    "WEATHER_RADIO4": "Radioactive",
    "WEATHER_RADIO5": "High Radiation",
    "WEATHER_RADIO_CLEAR": "Irradiated Clear",
    "WEATHER_RADIO_CLEAR1": "Irradiated Clear",
    "WEATHER_RADIO_CLEAR2": "Irradiated Clear",
    "WEATHER_RADIO_CLEAR3": "Irradiated Clear",
    "WEATHER_RADIO_CLEAR4": "Irradiated Clear",
    "WEATHER_RADIO_CLEAR5": "Irradiated Clear",
    "WEATHER_RADIO_CLEAR6": "Irradiated Clear",
    "WEATHER_RADIO_CLEAR7": "Irradiated Clear",

    # Storm types
    "WEATHER_STORM": "Stormy",
    "WEATHER_RAINSTORM": "Rainstorm",
    "WEATHER_THUNDERSTORM": "Thunderstorm",
    "WEATHER_WINDSTORM": "Windstorm",
    "WEATHER_DUST": "Dusty",
    "WEATHER_DUSTSTORM": "Dust Storm",
    "WEATHER_SANDSTORM": "Sandstorm",
    "WEATHER_BOILING": "Boiling",
    "WEATHER_SUPERSTORM": "Superstorm",
    "WEATHER_LAVA": "Volcanic",
    "Dust": "Dusty",
    "Humid": "Humid",
    "Lava": "Volcanic",
    "Toxic": "Toxic",

    # Barren weather patterns
    "WEATHER_BARREN": "Barren",
    "WEATHER_BARREN1": "Arid",
    "WEATHER_BARREN2": "Dusty",
    "WEATHER_BARREN3": "Desert",
    "WEATHER_BARREN4": "Dry",
    "WEATHER_BARREN5": "Parched",
    "WEATHER_BARREN6": "Desolate",
    "WEATHER_BARREN7": "Baked",
    "WEATHER_BARREN8": "Dusty",

    # Lush weather patterns
    "WEATHER_LUSH": "Temperate",
    "WEATHER_LUSH1": "Humid",
    "WEATHER_LUSH2": "Tropical",
    "WEATHER_LUSH3": "Rainy",
    "WEATHER_LUSH4": "Misty",
    "WEATHER_LUSH5": "Foggy",

    # Blue/Exotic star weather (numbered variants)
    "WEATHER_BLUE": "Anomalous",
    "WEATHER_BLUE1": "Anomalous",
    "WEATHER_BLUE2": "Anomalous",
    "WEATHER_BLUE3": "Anomalous",
    "WEATHER_BLUE4": "Anomalous",
    "WEATHER_BLUE5": "Anomalous",
    "WEATHER_BLUE6": "Anomalous",
    "WEATHER_BLUE7": "Anomalous",

    # Exotic weather
    "WEATHER_WEIRD": "Anomalous",
    "WEATHER_EXOTIC": "Exotic",
}

# Star type translations
STAR_TYPE_MAP = {
    "Yellow": "Yellow",
    "Red": "Red",
    "Green": "Green",
    "Blue": "Blue",
    "YELLOW": "Yellow",
    "RED": "Red",
    "GREEN": "Green",
    "BLUE": "Blue",
    "Yellow_Star": "Yellow",
    "Red_Star": "Red",
    "Green_Star": "Green",
    "Blue_Star": "Blue",
}

# Economy/Trading class translations
ECONOMY_TYPE_MAP = {
    # Trading classes
    "TradingClass_None": "None",
    "TradingClass_Mining": "Mining",
    "TradingClass_Manufacturing": "Manufacturing",
    "TradingClass_Scientific": "Scientific",
    "TradingClass_Trading": "Trading",
    "TradingClass_Advanced": "Advanced Materials",
    "TradingClass_Power": "Power Generation",
    "TradingClass_Technology": "High Tech",
    "TradingClass_Industrial": "Industrial",
    "TradingClass_Commercial": "Commercial",
    "TradingClass_Mercantile": "Mercantile",

    # Simplified versions
    "Mining": "Mining",
    "Manufacturing": "Manufacturing",
    "Scientific": "Scientific",
    "Trading": "Trading",
    "Advanced": "Advanced Materials",
    "Power": "Power Generation",
    "Technology": "High Tech",
    "Industrial": "Industrial",
    "Commercial": "Commercial",
    "Mercantile": "Mercantile",
}

# Economy strength/wealth translations
ECONOMY_STRENGTH_MAP = {
    "WealthClass_Low": "Low",
    "WealthClass_Medium": "Medium",
    "WealthClass_High": "High",
    "WealthClass_None": "None",
    "Low": "Low",
    "Medium": "Medium",
    "High": "High",
    "None": "None",
    "Declining": "Low",
    "Struggling": "Low",
    "Developing": "Low",
    "Comfortable": "Medium",
    "Satisfactory": "Medium",
    "Adequate": "Medium",
    "Flourishing": "High",
    "Prosperous": "High",
    "Wealthy": "High",
    "Opulent": "High",
    "Booming": "High",
}

# Conflict level translations
CONFLICT_LEVEL_MAP = {
    "ConflictLevel_None": "None",
    "ConflictLevel_Low": "Low",
    "ConflictLevel_Medium": "Medium",
    "ConflictLevel_High": "High",
    "None": "None",
    "Low": "Low",
    "Medium": "Medium",
    "High": "High",
    "Peaceful": "Low",
    "Unthreatening": "Low",
    "Relaxed": "Low",
    "Rowdy": "Medium",
    "Boisterous": "Medium",
    "Unruly": "Medium",
    "Aggressive": "High",
    "Dangerous": "High",
    "Lawless": "High",
    "Perilous": "High",
}

# Sentinel level translations
# SENTINEL_RARE<N> = Low (rare sentinels = few = low activity)
# SENTINEL_MID<N> = Normal
# SENTINEL_HIGH<N> = High/Aggressive
SENTINEL_LEVEL_MAP = {
    "None": "None",
    "Low": "Low",
    "Normal": "Normal",
    "Medium": "Normal",
    "High": "High",
    "Aggressive": "Aggressive",
    "Hostile": "Hostile",
    "Frenzied": "Frenzied",
    "SENTINELS_NONE": "None",
    "SENTINELS_LOW": "Low",
    "SENTINELS_NORMAL": "Normal",
    "SENTINELS_HIGH": "High",
    "SENTINELS_AGGRESSIVE": "Aggressive",
    "SENTINELS_HOSTILE": "Hostile",
    "SENTINELS_FRENZIED": "Frenzied",
    # SENTINEL_RARE<N> patterns (rare activity = low)
    "SENTINEL_RARE": "Low",
    "SENTINEL_RARE1": "Low",
    "SENTINEL_RARE2": "Low",
    "SENTINEL_RARE3": "Low",
    "SENTINEL_RARE4": "Low",
    "SENTINEL_RARE5": "Low",
    "SENTINEL_RARE6": "Low",
    "SENTINEL_RARE7": "Low",
    "SENTINEL_RARE8": "Low",
    "SENTINEL_RARE9": "Low",
    "SENTINEL_RARE10": "Low",
    "SENTINEL_RARE11": "Low",
    "SENTINEL_RARE12": "Low",
    # SENTINEL_MID<N> patterns (medium = normal)
    "SENTINEL_MID": "Normal",
    "SENTINEL_MID1": "Normal",
    "SENTINEL_MID2": "Normal",
    "SENTINEL_MID3": "Normal",
    "SENTINEL_MID4": "Normal",
    "SENTINEL_MID5": "Normal",
    # SENTINEL_HIGH<N> patterns (high activity)
    "SENTINEL_HIGH": "High",
    "SENTINEL_HIGH1": "High",
    "SENTINEL_HIGH2": "High",
    "SENTINEL_HIGH3": "High",
    "SENTINEL_HIGH4": "High",
    "SENTINEL_HIGH5": "High",
    # Text descriptions
    "Reduced": "Low",
    "Standard": "Normal",
    "Regular": "Normal",
    "Infrequent": "Low",
    "Limited": "Low",
    "Minimal": "Low",
    "Spread Thin": "Low",
    "Average": "Normal",
    "Typical": "Normal",
    "Threatening": "High",
    "High Security": "High",
    "Corrupt": "Frenzied",
}

# Flora/Fauna level translations
# RARITY_HIGH<N> = Rich/Abundant (high rarity of fauna/flora = lots of them)
# RARITY_MID<N> = Average/Common
# Low, Sparse, Occasional = Sparse
FLORA_FAUNA_MAP = {
    "None": "None",
    "Absent": "None",
    "Nonexistent": "None",
    "Empty": "None",
    "Deficient": "Sparse",
    "Devoid": "None",
    "Lacking": "Sparse",
    "Scarce": "Sparse",
    "Low": "Sparse",
    "Sparse": "Sparse",
    "Occasional": "Sparse",
    "Infrequent": "Sparse",
    "Limited": "Sparse",
    "Uncommon": "Sparse",
    "Rare": "Sparse",
    "Average": "Average",
    "Common": "Average",
    "Typical": "Average",
    "Regular": "Average",
    "Normal": "Average",
    "Fair": "Average",
    "Moderate": "Average",
    "Ordinary": "Average",
    "Mid": "Average",
    "Ample": "Rich",
    "Abundant": "Rich",
    "Bountiful": "Rich",
    "Copious": "Rich",
    "Full": "Rich",
    "High": "Rich",
    "Generous": "Rich",
    "Rich": "Rich",
    "Teeming": "Rich",
    "Frequent": "Rich",
    "Flourishing": "Rich",
    "Full": "Rich",
    "Mid": "Average",
    # RARITY_HIGH<N> patterns (high = abundant = rich)
    "RARITY_HIGH": "Rich",
    "RARITY_HIGH1": "Rich",
    "RARITY_HIGH2": "Rich",
    "RARITY_HIGH3": "Rich",
    "RARITY_HIGH4": "Rich",
    "RARITY_HIGH5": "Rich",
    "RARITY_HIGH6": "Rich",
    "RARITY_HIGH7": "Rich",
    "RARITY_HIGH8": "Rich",
    "RARITY_HIGH9": "Rich",
    "RARITY_HIGH10": "Rich",
    # RARITY_MID<N> patterns (medium = average)
    "RARITY_MID": "Average",
    "RARITY_MID1": "Average",
    "RARITY_MID2": "Average",
    "RARITY_MID3": "Average",
    "RARITY_MID4": "Average",
    "RARITY_MID5": "Average",
    "RARITY_MID6": "Average",
    "RARITY_MID7": "Average",
    # RARITY_LOW<N> patterns (low = sparse)
    "RARITY_LOW": "Sparse",
    "RARITY_LOW1": "Sparse",
    "RARITY_LOW2": "Sparse",
    "RARITY_LOW3": "Sparse",
}

# Dominant lifeform translations
LIFEFORM_MAP = {
    "GekPrime": "Gek",
    "Gek": "Gek",
    "Korvax": "Korvax",
    "VyKeen": "Vy'keen",
    "Vykeen": "Vy'keen",
    "Traveller": "Traveller",
    "None": "None",
    "Uncharted": "None",
}


def translate_nms_value(value: str, translation_map: dict, default: str = "Unknown") -> str:
    """
    Translate an NMS internal value to a human-readable value.

    Handles case variations and partial matches.
    """
    if not value or value == "Unknown":
        return default

    # Try exact match first
    if value in translation_map:
        return translation_map[value]

    # Try uppercase
    if value.upper() in translation_map:
        return translation_map[value.upper()]

    # Try with common prefixes stripped
    for prefix in ["WEATHER_", "BIOME_", "SENTINEL_", "TRADING_", "CONFLICT_"]:
        stripped = value.replace(prefix, "")
        if stripped in translation_map:
            return translation_map[stripped]

    # Try partial match (for values like "BARREN2" -> match "BARREN")
    for key, mapped_value in translation_map.items():
        if value.upper().startswith(key.upper()):
            return mapped_value

    # Return cleaned up version of original value
    # Remove numeric suffixes and underscores, title case
    cleaned = value.replace("_", " ").title()
    # Remove trailing numbers
    import re
    cleaned = re.sub(r'\d+$', '', cleaned).strip()
    return cleaned if cleaned else default


class ExtractionWatcher:
    """
    Watches for new extraction files from Haven Extractor.

    Usage:
        watcher = ExtractionWatcher(
            output_dir=Path.home() / "Documents" / "Haven-Extractor",
            callback=lambda data: print(f"New system: {data['system_name']}")
        )
        watcher.start()
        # ... later ...
        watcher.stop()

    Deduplication:
        Only fires callback when:
        - A new system is detected (different glyph_code)
        - OR the planet count has increased (more planets scanned)
        This prevents duplicate callbacks when Haven Extractor updates
        the same file multiple times during planet scanning.
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        poll_interval: float = 2.0,
        startup_delay: float = 0.0
    ):
        """
        Initialize the extraction watcher.

        Args:
            output_dir: Directory where Haven Extractor writes JSON files.
                       Defaults to ~/Documents/Haven-Extractor
            callback: Function to call when new extraction is found.
                     Receives the extracted system data as a dict.
            poll_interval: Seconds between directory polls.
            startup_delay: Seconds to wait before processing any data.
                          During this time, all incoming systems are tracked
                          but NOT processed. Use this to let the game fully
                          load before collecting new discoveries.
        """
        self.output_dir = output_dir or Path(os.environ.get(
            "HAVEN_EXTRACTOR_OUTPUT",
            Path.home() / "Documents" / "Haven-Extractor"
        ))
        self.callback = callback
        self.poll_interval = poll_interval
        self.startup_delay = startup_delay

        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._start_time: float = 0
        self._last_extraction_time: float = 0
        self._processed_files: set = set()

        # Deduplication tracking - prevents multiple callbacks for same system
        self._last_glyph_code: str = ""
        self._last_galaxy: str = ""
        self._last_planet_count: int = 0

        # Track ALL known glyph codes seen during startup delay
        self._known_glyph_codes: set = set()
        self._in_learning_mode: bool = False

    def start(self):
        """Start watching for new extractions."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Watcher already running")
            return

        self._start_time = time.time()
        self._known_glyph_codes.clear()

        # Mark ALL existing batch files as already processed
        # Only files created AFTER watcher starts will be picked up
        if self.output_dir.exists():
            existing_batch_files = list(self.output_dir.glob("batch_*.json"))
            for bf in existing_batch_files:
                self._processed_files.add(str(bf))
            if existing_batch_files:
                logger.info(f"Ignoring {len(existing_batch_files)} existing batch files - only new files will be processed")

        # Enter learning mode if startup_delay > 0
        if self.startup_delay > 0:
            self._in_learning_mode = True
            logger.info(f"LEARNING MODE: Ignoring all data for {self.startup_delay} seconds")
            logger.info("  Start your game now - watcher will begin collecting after delay")
        else:
            self._in_learning_mode = False

        self._stop_event.clear()
        self._thread = Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"Extraction watcher started. Monitoring: {self.output_dir}")

    def stop(self):
        """Stop watching."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info("Extraction watcher stopped")

    def is_running(self) -> bool:
        """Check if watcher is currently running."""
        return self._thread is not None and self._thread.is_alive()

    def check_once(self) -> Optional[Dict[str, Any]]:
        """
        Check for new extractions once (non-blocking).

        Returns the latest extraction if available, or None.
        """
        return self._check_for_new_extraction()

    def _watch_loop(self):
        """Main watch loop (runs in background thread)."""
        while not self._stop_event.is_set():
            try:
                # Check for batch files first (batch_*.json)
                batch_files = self.check_for_batch_files()
                for batch_file in batch_files:
                    logger.info(f"Found batch file: {batch_file.name}")
                    systems = self.process_batch_file(batch_file)
                    if systems and self.callback:
                        # Display batch summary
                        converted_systems = []
                        for system_data in systems:
                            payload = convert_extraction_to_haven_payload(system_data)
                            converted_systems.append(payload)

                        if converted_systems:
                            logger.info(display_batch_summary(converted_systems))

                        # Process each system in the batch
                        for system_data in systems:
                            try:
                                self.callback(system_data)
                            except Exception as e:
                                logger.error(f"Callback error for batch system: {e}")

                # Then check for single extraction files (latest.json, extraction_*.json)
                extraction = self._check_for_new_extraction()
                if extraction and self.callback:
                    try:
                        self.callback(extraction)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
            except Exception as e:
                logger.error(f"Watch loop error: {e}")

            self._stop_event.wait(self.poll_interval)

    def _check_for_new_extraction(self) -> Optional[Dict[str, Any]]:
        """
        Check for new extraction files.

        Returns the newest unprocessed extraction, or None.

        Deduplication logic:
        - Only returns data if it's a NEW system (different glyph_code)
        - OR if the same system now has MORE planets (scanner room used)
        - Prevents duplicate callbacks when Haven Extractor updates file repeatedly
        """
        if not self.output_dir.exists():
            return None

        # Check if we're still in learning mode
        if self._in_learning_mode:
            elapsed = time.time() - self._start_time
            if elapsed >= self.startup_delay:
                # Exit learning mode
                self._in_learning_mode = False
                logger.info(f"LEARNING MODE COMPLETE: Now tracking {len(self._known_glyph_codes)} known systems")
                logger.info("Ready to collect NEW discoveries!")

        # Look for the "latest.json" file first
        latest_file = self.output_dir / "latest.json"
        if latest_file.exists():
            mtime = latest_file.stat().st_mtime
            if mtime > self._last_extraction_time:
                self._last_extraction_time = mtime
                try:
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # Content-based deduplication
                    glyph_code = data.get('glyph_code', '')
                    galaxy = data.get('galaxy_name', 'Euclid')
                    planet_count = data.get('planet_count', 0)
                    glyph_key = f"{galaxy}:{glyph_code}"

                    # During learning mode, just track glyph codes without processing
                    if self._in_learning_mode:
                        self._known_glyph_codes.add(glyph_key)
                        self._last_glyph_code = glyph_code
                        self._last_galaxy = galaxy
                        self._last_planet_count = planet_count
                        return None

                    # Skip if this is a known system from learning mode
                    if glyph_key in self._known_glyph_codes:
                        # Update tracking but don't process
                        self._last_glyph_code = glyph_code
                        self._last_galaxy = galaxy
                        self._last_planet_count = planet_count
                        return None

                    # Check if this is truly new data worth processing
                    is_new_system = (glyph_code != self._last_glyph_code or
                                    galaxy != self._last_galaxy)
                    has_more_planets = (glyph_code == self._last_glyph_code and
                                       galaxy == self._last_galaxy and
                                       planet_count > self._last_planet_count)

                    if is_new_system or has_more_planets:
                        # Update tracking
                        self._last_glyph_code = glyph_code
                        self._last_galaxy = galaxy
                        self._last_planet_count = planet_count

                        # Add to known codes so we don't reprocess if it cycles back
                        self._known_glyph_codes.add(glyph_key)

                        if is_new_system:
                            logger.info(f"New system detected: {data.get('system_name', 'Unknown')} [{glyph_code}]")
                        else:
                            logger.info(f"System updated with more planets: {planet_count} (was {self._last_planet_count})")

                        return data
                    else:
                        # Same system, same planet count - skip
                        logger.debug(f"Skipping duplicate: {glyph_code} ({planet_count} planets, unchanged)")
                        return None

                except Exception as e:
                    logger.error(f"Failed to read {latest_file}: {e}")

        # Also check for individual extraction files (fallback)
        extraction_files = sorted(
            self.output_dir.glob("extraction_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for filepath in extraction_files:
            if str(filepath) in self._processed_files:
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Apply same deduplication logic
                glyph_code = data.get('glyph_code', '')
                galaxy = data.get('galaxy_name', 'Euclid')
                planet_count = data.get('planet_count', 0)
                glyph_key = f"{galaxy}:{glyph_code}"

                self._processed_files.add(str(filepath))

                # During learning mode, just track glyph codes
                if self._in_learning_mode:
                    self._known_glyph_codes.add(glyph_key)
                    continue

                # Skip if this is a known system
                if glyph_key in self._known_glyph_codes:
                    continue

                is_new_system = (glyph_code != self._last_glyph_code or
                                galaxy != self._last_galaxy)
                has_more_planets = (glyph_code == self._last_glyph_code and
                                   galaxy == self._last_galaxy and
                                   planet_count > self._last_planet_count)

                if is_new_system or has_more_planets:
                    self._last_glyph_code = glyph_code
                    self._last_galaxy = galaxy
                    self._last_planet_count = planet_count
                    self._known_glyph_codes.add(glyph_key)
                    return data

            except Exception as e:
                logger.error(f"Failed to read {filepath}: {e}")
                self._processed_files.add(str(filepath))  # Skip bad files

        return None

    def get_latest_extraction(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest extraction without marking it as processed.

        Useful for displaying current state.
        """
        latest_file = self.output_dir / "latest.json"
        if latest_file.exists():
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def reset_deduplication(self, clear_known: bool = True):
        """
        Reset the deduplication tracking state.

        Call this to force the watcher to re-process the current extraction
        (useful for testing or when user wants to re-queue a system).

        Args:
            clear_known: If True, also clears the known glyph codes set,
                        allowing ALL systems to be re-processed.
        """
        self._last_glyph_code = ""
        self._last_galaxy = ""
        self._last_planet_count = 0
        self._last_extraction_time = 0
        if clear_known:
            self._known_glyph_codes.clear()
            logger.info("Deduplication state fully reset - all systems can be re-processed")
        else:
            logger.info("Deduplication state reset - next extraction will be processed")

    def get_tracking_state(self) -> Dict[str, Any]:
        """
        Get current deduplication tracking state (for debugging).

        Returns:
            Dict with current tracking info
        """
        state = {
            "last_glyph_code": self._last_glyph_code,
            "last_galaxy": self._last_galaxy,
            "last_planet_count": self._last_planet_count,
            "last_extraction_time": self._last_extraction_time,
            "processed_files_count": len(self._processed_files),
            "known_systems_count": len(self._known_glyph_codes),
            "in_learning_mode": self._in_learning_mode,
            "startup_delay": self.startup_delay
        }
        if self._in_learning_mode and self._start_time > 0:
            remaining = self.startup_delay - (time.time() - self._start_time)
            state["learning_mode_remaining"] = max(0, remaining)
        return state

    def check_for_batch_files(self) -> list:
        """
        Check for batch extraction files (batch_*.json).

        Returns a list of unprocessed batch files.
        """
        if not self.output_dir.exists():
            return []

        batch_files = sorted(
            self.output_dir.glob("batch_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True  # Newest first
        )

        unprocessed = []
        for filepath in batch_files:
            if str(filepath) not in self._processed_files:
                unprocessed.append(filepath)

        return unprocessed

    def process_batch_file(self, batch_file: Path) -> list:
        """
        Process a batch extraction file.

        Reads the batch file and returns a list of individual system extractions.
        Each system is ready to be converted and submitted via API.

        Args:
            batch_file: Path to the batch JSON file

        Returns:
            List of system dictionaries, each ready for convert_extraction_to_haven_payload()
        """
        systems = []

        try:
            with open(batch_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check if this is a batch file
            if not data.get("batch_mode", False):
                logger.warning(f"{batch_file} does not appear to be a batch file")
                return []

            batch_systems = data.get("systems", [])
            logger.info(f"Processing batch file with {len(batch_systems)} systems")

            for i, system_data in enumerate(batch_systems):
                # Skip if we've already processed this system
                glyph_code = system_data.get('glyph_code', '')
                galaxy = system_data.get('galaxy_name', 'Euclid')
                glyph_key = f"{galaxy}:{glyph_code}"

                if glyph_key in self._known_glyph_codes:
                    logger.debug(f"Skipping already-known system: {system_data.get('system_name', 'Unknown')}")
                    continue

                # Add to known codes
                self._known_glyph_codes.add(glyph_key)

                # Add metadata about batch processing
                system_data['_batch_source'] = str(batch_file)
                system_data['_batch_index'] = i
                system_data['_batch_total'] = len(batch_systems)

                systems.append(system_data)
                logger.info(f"  System {i+1}/{len(batch_systems)}: {system_data.get('system_name', 'Unknown')} ({len(system_data.get('planets', []))} planets)")

            # Mark the batch file as processed
            self._processed_files.add(str(batch_file))

        except Exception as e:
            logger.error(f"Failed to process batch file {batch_file}: {e}")

        return systems


def convert_extraction_to_haven_payload(extraction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Haven Extractor output to Haven Control Room API payload format.

    This maps the extraction format to match what the Control Room API expects,
    including translating NMS internal values to human-readable format.

    Field Mapping:
    - Haven Extractor "system_name" -> Control Room "name"
    - Haven Extractor "galaxy_name" -> Control Room "galaxy"
    - Haven Extractor "voxel_x/y/z" -> Control Room "x/y/z"
    - Haven Extractor planet "biome" -> Control Room planet "climate"
    - Haven Extractor planet "sentinel_level" -> Control Room planet "sentinel"
    - Haven Extractor planet "flora_level" -> Control Room planet "flora"
    - Haven Extractor planet "fauna_level" -> Control Room planet "fauna"
    - Haven Extractor planet resources -> Control Room planet "materials"
    """
    # Translate system-level values
    star_type = translate_nms_value(
        extraction.get("star_type", "Unknown"),
        STAR_TYPE_MAP,
        "Yellow"
    )

    economy_type = translate_nms_value(
        extraction.get("economy_type", "Unknown"),
        ECONOMY_TYPE_MAP,
        "Unknown"
    )

    economy_strength = translate_nms_value(
        extraction.get("economy_strength", "Unknown"),
        ECONOMY_STRENGTH_MAP,
        "Unknown"
    )

    conflict_level = translate_nms_value(
        extraction.get("conflict_level", "Unknown"),
        CONFLICT_LEVEL_MAP,
        "Unknown"
    )

    dominant_lifeform = translate_nms_value(
        extraction.get("dominant_lifeform", "Unknown"),
        LIFEFORM_MAP,
        "Unknown"
    )

    payload = {
        # System identification - map to Control Room expected fields
        "name": extraction.get("system_name", "Unknown System"),
        "glyph_code": extraction.get("glyph_code", ""),
        "galaxy": extraction.get("galaxy_name", "Euclid"),

        # System properties - translated to human-readable values
        "star_type": star_type,
        "economy_type": economy_type,
        "economy_level": economy_strength,  # Control Room uses "economy_level"
        "conflict_level": conflict_level,
        "dominant_lifeform": dominant_lifeform,

        # Coordinates - map voxel_* to x/y/z for Control Room
        "x": extraction.get("voxel_x", 0),
        "y": extraction.get("voxel_y", 0),
        "z": extraction.get("voxel_z", 0),
        "glyph_solar_system": extraction.get("solar_system_index", 0),

        # Also include original voxel names for compatibility
        "voxel_x": extraction.get("voxel_x"),
        "voxel_y": extraction.get("voxel_y"),
        "voxel_z": extraction.get("voxel_z"),
        "solar_system_index": extraction.get("solar_system_index"),

        # Planet count
        "planet_count": extraction.get("planet_count", 0),

        # Planets will be populated below
        "planets": []
    }

    # Convert planet data with proper field mapping for Control Room
    for planet in extraction.get("planets", []):
        # Translate planet-level values
        biome = translate_nms_value(
            planet.get("biome", "Unknown"),
            BIOME_MAP,
            "Unknown"
        )

        weather = translate_nms_value(
            planet.get("weather", "Unknown"),
            WEATHER_MAP,
            "Unknown"
        )

        sentinel = translate_nms_value(
            planet.get("sentinel_level", "Unknown"),
            SENTINEL_LEVEL_MAP,
            "Normal"
        )

        flora = translate_nms_value(
            planet.get("flora_level", "Unknown"),
            FLORA_FAUNA_MAP,
            "Unknown"
        )

        fauna = translate_nms_value(
            planet.get("fauna_level", "Unknown"),
            FLORA_FAUNA_MAP,
            "Unknown"
        )

        # Build materials string from resources (translated to human-readable names)
        resources = []
        common_res_raw = planet.get("common_resource", "")
        uncommon_res_raw = planet.get("uncommon_resource", "")
        rare_res_raw = planet.get("rare_resource", "")

        # Translate each resource ID to human-readable name
        common_res = translate_resource(common_res_raw) if common_res_raw and common_res_raw != "Unknown" else ""
        uncommon_res = translate_resource(uncommon_res_raw) if uncommon_res_raw and uncommon_res_raw != "Unknown" else ""
        rare_res = translate_resource(rare_res_raw) if rare_res_raw and rare_res_raw != "Unknown" else ""

        if common_res:
            resources.append(common_res)
        if uncommon_res:
            resources.append(uncommon_res)
        if rare_res:
            resources.append(rare_res)
        materials = ", ".join(resources) if resources else None

        # Get planet name - use planet_name from extractor, fallback to Planet_N
        planet_name = planet.get("planet_name", "")
        if not planet_name or planet_name == "Unknown":
            planet_name = f"Planet {planet.get('planet_index', 0) + 1}"

        planet_payload = {
            # Control Room expected fields
            "name": planet_name,
            "climate": biome,  # Control Room uses "climate" for biome/environment type
            "sentinel": sentinel,  # Control Room uses "sentinel" not "sentinel_level"
            "fauna": fauna,  # Control Room uses "fauna" not "fauna_level"
            "flora": flora,  # Control Room uses "flora" not "flora_level"
            "materials": materials,  # Control Room expects comma-separated materials string

            # Additional fields the Control Room may use
            "weather": weather,
            "description": f"{biome} planet with {weather.lower()} weather",

            # Original extraction data for reference
            "index": planet.get("planet_index", 0),
            "planet_index": planet.get("planet_index", 0),
            "biome": biome,  # Also include as biome for compatibility
            "sentinel_level": sentinel,
            "flora_level": flora,
            "fauna_level": fauna,

            # ====================================================================
            # Haven Extractor v7.9.6+ Extended Planet Data
            # ====================================================================

            # Biome details
            "biome_subtype": planet.get("biome_subtype", ""),

            # Planet characteristics
            "planet_size": planet.get("planet_size", ""),
            "is_moon": planet.get("is_moon", False),

            # Weather details
            "storm_frequency": planet.get("storm_frequency", ""),
            "weather_intensity": planet.get("weather_intensity", ""),
            "weather_text": planet.get("weather_text", ""),

            # Building/sentinels
            "building_density": planet.get("building_density", ""),
            "sentinels_text": planet.get("sentinels_text", ""),

            # Hazards
            "hazard_temperature": planet.get("hazard_temperature", 0.0),
            "hazard_radiation": planet.get("hazard_radiation", 0.0),
            "hazard_toxicity": planet.get("hazard_toxicity", 0.0),

            # Resources (translated to human-readable names)
            "common_resource": common_res,
            "uncommon_resource": uncommon_res,
            "rare_resource": rare_res,

            # Raw resource IDs (for debugging/reference)
            "common_resource_raw": common_res_raw,
            "uncommon_resource_raw": uncommon_res_raw,
            "rare_resource_raw": rare_res_raw,

            # Text descriptions from extractor
            "flora_text": planet.get("flora_text", ""),
            "fauna_text": planet.get("fauna_text", ""),

            # Resources in structured format (for APIs that want it)
            "resources": {
                "common": common_res,
                "uncommon": uncommon_res,
                "rare": rare_res
            }
        }
        payload["planets"].append(planet_payload)

    return payload


def get_translation_summary(extraction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a summary of how values were translated for debugging/logging.

    Returns a dict showing original -> translated values.
    """
    summary = {
        "system": {
            "star_type": {
                "original": extraction.get("star_type", "Unknown"),
                "translated": translate_nms_value(extraction.get("star_type", "Unknown"), STAR_TYPE_MAP, "Yellow")
            },
            "economy_type": {
                "original": extraction.get("economy_type", "Unknown"),
                "translated": translate_nms_value(extraction.get("economy_type", "Unknown"), ECONOMY_TYPE_MAP, "Unknown")
            },
            "economy_strength": {
                "original": extraction.get("economy_strength", "Unknown"),
                "translated": translate_nms_value(extraction.get("economy_strength", "Unknown"), ECONOMY_STRENGTH_MAP, "Unknown")
            },
            "conflict_level": {
                "original": extraction.get("conflict_level", "Unknown"),
                "translated": translate_nms_value(extraction.get("conflict_level", "Unknown"), CONFLICT_LEVEL_MAP, "Unknown")
            },
        },
        "planets": []
    }

    for planet in extraction.get("planets", []):
        planet_summary = {
            "index": planet.get("planet_index", 0),
            "biome": {
                "original": planet.get("biome", "Unknown"),
                "translated": translate_nms_value(planet.get("biome", "Unknown"), BIOME_MAP, "Unknown")
            },
            "weather": {
                "original": planet.get("weather", "Unknown"),
                "translated": translate_nms_value(planet.get("weather", "Unknown"), WEATHER_MAP, "Unknown")
            },
            "sentinel": {
                "original": planet.get("sentinel_level", "Unknown"),
                "translated": translate_nms_value(planet.get("sentinel_level", "Unknown"), SENTINEL_LEVEL_MAP, "Normal")
            },
        }
        summary["planets"].append(planet_summary)

    return summary


# =============================================================================
# Terminal UI Display Functions
# =============================================================================

def display_system_data(payload: Dict[str, Any], show_raw: bool = False) -> str:
    """
    Format system data for terminal display.

    Args:
        payload: The Haven payload (after convert_extraction_to_haven_payload)
        show_raw: If True, also show raw resource IDs

    Returns:
        Formatted string for terminal display
    """
    lines = []
    width = 60

    # Header
    lines.append("=" * width)
    lines.append(f"  STAR SYSTEM: {payload.get('name', 'Unknown')}")
    lines.append("=" * width)

    # System Info
    lines.append("")
    lines.append("  SYSTEM INFO")
    lines.append("  " + "-" * (width - 4))
    lines.append(f"  Galaxy:       {payload.get('galaxy', 'Euclid')}")
    lines.append(f"  Glyph Code:   {payload.get('glyph_code', 'Unknown')}")
    lines.append(f"  Star Type:    {payload.get('star_type', 'Unknown')}")
    lines.append(f"  Economy:      {payload.get('economy_type', 'Unknown')} ({payload.get('economy_level', 'Unknown')})")
    lines.append(f"  Conflict:     {payload.get('conflict_level', 'Unknown')}")
    lines.append(f"  Lifeform:     {payload.get('dominant_lifeform', 'Unknown')}")
    lines.append(f"  Coordinates:  ({payload.get('x', 0)}, {payload.get('y', 0)}, {payload.get('z', 0)})")

    # Planets
    planets = payload.get('planets', [])
    lines.append("")
    lines.append(f"  PLANETS ({len(planets)})")
    lines.append("  " + "-" * (width - 4))

    for i, planet in enumerate(planets):
        lines.append("")
        moon_marker = " [Moon]" if planet.get('is_moon', False) else ""
        lines.append(f"  [{i+1}] {planet.get('name', 'Unknown')}{moon_marker}")
        lines.append(f"      Climate:    {planet.get('climate', 'Unknown')}")
        lines.append(f"      Weather:    {planet.get('weather', 'Unknown')}")
        lines.append(f"      Sentinels:  {planet.get('sentinel', 'Unknown')}")
        lines.append(f"      Flora:      {planet.get('flora', 'Unknown')}")
        lines.append(f"      Fauna:      {planet.get('fauna', 'Unknown')}")

        # Resources
        resources = planet.get('resources', {})
        common = resources.get('common', '')
        uncommon = resources.get('uncommon', '')
        rare = resources.get('rare', '')
        resource_str = ", ".join(filter(None, [common, uncommon, rare]))
        lines.append(f"      Resources:  {resource_str or 'None'}")

        # Show raw IDs if requested
        if show_raw:
            raw_common = planet.get('common_resource_raw', '')
            raw_uncommon = planet.get('uncommon_resource_raw', '')
            raw_rare = planet.get('rare_resource_raw', '')
            if any([raw_common, raw_uncommon, raw_rare]):
                raw_str = ", ".join(filter(None, [raw_common, raw_uncommon, raw_rare]))
                lines.append(f"      (Raw IDs:   {raw_str})")

        # Hazards if present
        temp = planet.get('hazard_temperature', 0)
        rad = planet.get('hazard_radiation', 0)
        tox = planet.get('hazard_toxicity', 0)
        if temp != 0 or rad != 0 or tox != 0:
            lines.append(f"      Hazards:    Temp={temp}°, Rad={rad}, Tox={tox}")

    lines.append("")
    lines.append("=" * width)

    return "\n".join(lines)


def display_batch_summary(systems: list) -> str:
    """
    Format a summary of batch systems for terminal display.

    Args:
        systems: List of system payloads

    Returns:
        Formatted string for terminal display
    """
    lines = []
    width = 60

    lines.append("=" * width)
    lines.append(f"  BATCH SUMMARY: {len(systems)} Systems")
    lines.append("=" * width)

    total_planets = 0
    for i, system in enumerate(systems):
        planet_count = len(system.get('planets', []))
        total_planets += planet_count
        lines.append(f"  [{i+1}] {system.get('name', 'Unknown'):<30} ({planet_count} planets)")

    lines.append("-" * width)
    lines.append(f"  TOTAL: {len(systems)} systems, {total_planets} planets")
    lines.append("=" * width)

    return "\n".join(lines)


# ============================================================================
# Standalone testing
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def on_extraction(data):
        print(f"\n{'='*60}")
        print(f"New Extraction: {data.get('system_name', 'Unknown')}")
        print(f"Star Type: {data.get('star_type', 'Unknown')}")
        print(f"Planets: {data.get('planet_count', 0)}")
        for planet in data.get('planets', []):
            print(f"  - {planet.get('planet_name', 'Unknown')}: {planet.get('biome', 'Unknown')}")
        print(f"{'='*60}\n")

        # Show Haven payload format
        payload = convert_extraction_to_haven_payload(data)
        print("Haven Payload:")
        print(json.dumps(payload, indent=2))

    watcher = ExtractionWatcher(callback=on_extraction)
    watcher.start()

    print("Watching for extractions... Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        print("Stopped.")
