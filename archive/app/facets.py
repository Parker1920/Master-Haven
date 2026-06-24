"""
Per-section facet schema — the single source of truth for the catalogue's
custom filters/categories.

Each authored namespace maps to an ordered list of facets. A facet is:
    {"key": str, "label": str, "control": "single"|"multi"|"boolean", "options": [str, ...]}

- single   → pick one value (radio / select)
- multi    → pick any number (checkboxes); stored as multiple article_facet rows
- boolean  → a flag; stored as a single value "true" when set

The frontend fetches this via GET /api/v1/articles/facets/{namespace} and
renders BOTH the create/edit form controls and the Browse filter rail from
it, so the categories stay single-sourced.

Derived from docs/wiki-filters.md. Synced namespaces (system/planet/item via
the live atlas) and the civ special page are not article-facet driven and
are absent here. Shared enums are defined once at the top and reused.
"""

from __future__ import annotations

# --- shared enums (define once, reuse) -------------------------------
CLASS = ["C", "B", "A", "S"]
STAR_TYPE = ["Yellow", "Red", "Green", "Blue", "Purple"]
BIOME = [
    "Lush", "Barren", "Dead", "Scorched", "Frozen", "Toxic", "Irradiated",
    "Marsh", "Volcanic", "Exotic", "Mega Exotic", "Gas Giant", "Waterworld",
]
RARITY = ["Common", "Uncommon", "Rare"]
PLATFORM = [
    "PC (Steam)", "PC (GOG)", "PC (MS Store)", "PlayStation", "Xbox",
    "Switch", "Mac", "Cross-platform",
]
GAME_MODE = ["Normal", "Creative", "Relaxed", "Survival", "Permadeath", "Custom"]
ERA = [
    "Genesis (2016)", "NEXT (2018)", "Beyond/Synthesis (2019-20)",
    "Origins-Frontiers (2020-21)", "Sentinel-Endurance (2021-22)",
    "Fractal-Echoes (2023)", "Worlds I-II (2024-25)", "Voyagers/Modern (2025-26)",
]
GALAXY_SHORT = [
    "Euclid", "Hilbert Dimension", "Calypso", "Hesperius Dimension", "Hyades",
    "Ickjamatew", "Budullangr", "Kikolgallr", "Eltiensleen", "Eissentam",
    "Multi-galaxy", "Other",
]


def _f(key, label, control, options=None):
    return {"key": key, "label": label, "control": control, "options": options or []}


FACET_SCHEMAS: dict[str, list[dict]] = {
    # ---- people ----------------------------------------------------
    "traveler": [
        _f("role", "Primary role", "single", [
            "Cartographer", "Diplomat", "Builder", "Hunter", "Trader", "Lore-keeper",
            "Historian", "Leader", "Photographer", "Racer", "Event Organizer",
            "Tool-maker", "Recruiter",
        ]),
        _f("status", "Status", "single", ["Active", "Occasional", "Retired", "Memorial"]),
        _f("specialty", "Specialty", "multi", [
            "Exploration", "Diplomacy", "Base-building", "PvP", "Trading", "Lore",
            "History", "Leadership", "Photography", "Racing", "Tool development",
            "Community management", "Region naming", "Expedition running",
        ]),
        _f("platform", "Platform", "multi", PLATFORM),
        _f("era", "Contribution era", "single", ERA),
    ],
    # ---- biology / geology ----------------------------------------
    "creature": [
        _f("genus", "Genus", "multi", [
            "Bos", "Felidae", "Felihex", "Osteofelidae", "Procavya", "Tetraceris",
            "Reococcyx", "Ungulatis", "Hexungulatis", "Anastomus", "Mogara", "Theroma",
            "Rangifae", "Tyranocae", "Talpidae", "Lok", "Conokinis", "Bosoptera",
            "Floradae", "Shaihuluda", "Arthropodae", "Agnelis", "Cycromys", "Rhopalocera",
            "Oxyacta", "Protocaeli", "Ictaloris", "Prionace", "Chrysaora", "Bosaquatica",
            "Crustacea", "Hippocampus", "Mobula", "Krakenidae", "Procavaquatica",
            "Mechanoceris", "Structurae", "Spiralis", "Prionterrae", "Prototerrae", "Anomalous",
        ]),
        _f("ecosystem", "Ecosystem", "multi", ["Ground", "Flying", "Underwater", "Underground"]),
        _f("temperament", "Temperament", "single", ["Predator", "Player Predator", "Prey", "Passive"]),
        _f("diet", "Diet", "single", ["Herbivore", "Carnivore", "Omnivore", "Pica", "Predatory", "Non-predatory"]),
        _f("rarity", "Rarity", "single", RARITY),
        _f("gender", "Gender", "multi", [
            "Male", "Female", "Exotic", "Indeterminate", "Asymmetric", "Non-uniform",
            "Symmetric", "Rational", "Vectorised", "Prime", "Alpha", "Radical",
            "Asymptotic", "Orthogonal", "None",
        ]),
        _f("activity", "Activity", "single", ["Always Active", "Diurnal", "Nocturnal", "Mostly Diurnal", "Mostly Nocturnal"]),
        _f("biome", "Biome", "multi", BIOME),
        _f("rideable", "Rideable", "boolean"),
        _f("predator", "Predator", "boolean"),
        _f("megafauna", "Megafauna", "boolean"),
    ],
    "flora": [
        _f("biome", "Biome", "multi", BIOME),
        _f("resource_yielded", "Resource yielded", "multi", [
            "Carbon", "Star Bulb", "Cactus Flesh", "Solanium", "Frost Crystal",
            "Fungal Mould", "Gamma Root", "Faecium", "Mordite", "Kelp Sac",
            "Marrow Bulb", "NipNip Buds", "Fireberry", "Frostwort", "Echinocactus",
        ]),
        _f("form", "Form", "multi", [
            "Ground cover", "Shrub", "Tree", "Cactus", "Coral", "Fern", "Flower",
            "Mushroom", "Seaweed", "Spire", "Weird/Exotic",
        ]),
        _f("hazardous", "Hazardous", "boolean"),
        _f("rarity", "Rarity", "single", RARITY),
        _f("harvestable", "Harvestable", "boolean"),
    ],
    "mineral": [
        _f("resource", "Resource", "multi", [
            "Copper", "Cadmium", "Emeril", "Indium", "Quartzite", "Activated Copper",
            "Activated Cadmium", "Activated Emeril", "Activated Indium", "Activated Quartzite",
            "Cobalt", "Magnetised Ferrite", "Salt", "Silver", "Sodium", "Paraffinium",
            "Pyrite", "Phosphorus", "Dioxite", "Ammonia", "Uranium", "Rusted Metal",
            "Mordite", "Basalt", "Crystallised Helium", "Lithium", "Gold",
        ]),
        _f("richness", "Richness (class)", "single", CLASS),
        _f("deposit_type", "Deposit type", "multi", ["Resource Deposit", "Deep-Level (Hotspot)", "Buried Formation", "Crystalline"]),
        _f("biome", "Biome", "multi", BIOME),
        _f("star_gating", "Star-type gating", "multi", STAR_TYPE),
    ],
    # ---- ships & equipment ----------------------------------------
    "ship": [
        _f("archetype", "Archetype", "single", [
            "Shuttle", "Fighter", "Hauler", "Explorer", "Exotic", "Solar",
            "Sentinel Interceptor", "Living Ship", "Corvette",
        ]),
        _f("class", "Class", "single", CLASS),
        _f("bonus", "Type bonus", "single", [
            "Damage", "Hyperdrive range", "Shield + Inventory", "Balanced",
            "All-round", "Pulse drive", "Combat",
        ]),
        _f("procurement", "Procurement", "single", ["Procedural", "Unique", "Built"]),
        _f("where_found", "Where found", "multi", [
            "Space station", "Crashed ship", "Derelict freighter", "NPC gift",
            "Expedition", "Quicksilver", "Dissonant planet", "Corvette Workshop",
        ]),
    ],
    "freighter": [
        _f("design", "Design", "single", ["Sentinel/Dreadnought", "Venator/Resurgent", "Normal", "Capital"]),
        _f("class", "Class", "single", CLASS),
        _f("frigate_type", "Frigate type (fleet)", "multi", ["Support", "Exploration", "Combat", "Trade", "Industrial"]),
        _f("where_found", "Where found", "multi", ["Space-battle rescue", "Bought from station", "Derelict", "Expedition"]),
    ],
    "exocraft": [
        _f("type", "Type", "single", ["Roamer", "Nomad", "Pilgrim", "Colossus", "Minotaur", "Nautilon"]),
        _f("terrain", "Terrain", "multi", ["Land", "Sea", "Air-hover", "Mech"]),
        _f("use", "Use", "multi", ["Mining", "Exploration", "Cargo", "Combat", "Racing", "Underwater"]),
    ],
    "tool": [
        _f("type", "Type", "single", [
            "Pistol", "Rifle", "Experimental", "Alien", "Royal", "Sentinel",
            "Atlantid", "Voltaic Staff",
        ]),
        _f("class", "Class", "single", CLASS),
        _f("bonus", "Type bonus", "single", ["Mining", "Damage", "Scanning"]),
        _f("handedness", "Handedness", "single", ["One-handed", "Two-handed"]),
        _f("where_found", "Where found", "multi", [
            "Cabinet", "Minor Settlement", "Station merchant", "NPC gift", "Monolith",
            "Crashed ship", "Sentinel Pillar", "Korvax monolith", "Autophage terminal", "Expedition",
        ]),
    ],
    # ---- community -------------------------------------------------
    "base": [
        _f("build_type", "Build type / purpose", "multi", [
            "Home", "Farm", "Racetrack", "Gallery/Museum", "Settlement", "Freighter Base",
            "Capital", "Puzzle", "Art", "Logic/Tech", "Trading Post", "Monument",
            "Landing Hub", "Roleplay", "Underwater", "Cave",
        ]),
        _f("biome", "Biome", "multi", BIOME + ["N/A (Freighter/Space)"]),
        _f("location_type", "Location", "single", ["Planet", "Moon", "Underwater", "Cave", "Freighter", "Space"]),
        _f("glyph_available", "Glyph published", "boolean"),
        _f("galaxy", "Galaxy", "single", GALAXY_SHORT),
        _f("platform", "Platform", "multi", PLATFORM),
        _f("game_mode", "Game mode", "multi", GAME_MODE),
        _f("size", "Size", "single", ["Micro", "Small", "Medium", "Large", "Massive", "Limit-busting"]),
        _f("featured_tech", "Featured tech", "multi", [
            "Power/Wiring", "Logic", "Auto-doors", "Hydroponics", "Teleporter",
            "Landing Pads", "Trade Terminal", "Glitch-building", "Terrain edits",
            "Byte Beat", "POI integration",
        ]),
    ],
    "event": [
        _f("date", "Date", "date"),
        _f("type", "Type", "single", [
            "Expedition", "Festival", "Community", "War", "Gathering", "Census",
            "Competition", "Exhibition", "Race", "Charity", "Anniversary",
        ]),
        _f("expedition", "Official expedition", "single", [
            "Pioneers", "Beachhead", "Cartographers", "Emergence", "Exobiology",
            "The Blighted", "Leviathan", "Polestar", "Utopia", "Singularity", "Voyagers",
            "Omega", "Adrift", "Liquidators", "Aquarius", "The Cursed", "Titan",
            "Relics", "Corvette", "Breach", "Remnant", "The Swarm",
        ]),
        _f("status", "Status", "single", ["Upcoming", "Active", "Past", "Cancelled", "Postponed"]),
        _f("recurrence", "Recurrence", "single", ["One-off", "Annual", "Seasonal", "Monthly", "Weekly"]),
        _f("scale", "Scale", "single", ["Civ-internal", "Inter-civ", "Galaxy-wide", "Universe-wide"]),
    ],
    # ---- knowledge -------------------------------------------------
    "lore": [
        _f("topic", "Topic", "multi", [
            "Gek", "Vy'keen", "Korvax", "Travellers", "Sentinels", "Autophage",
            "First Spawn", "Forgotten Colonies", "Atlas", "Telamon", "The Anomaly",
            "Boundary Failures", "Awakenings", "Atlas Path", "Artemis Arc", "The Purge",
            "Artemis", "Apollo", "Nada", "Polo", "Glyphs & Portals", "Convergence",
        ]),
        _f("canonicity", "Canonicity", "single", [
            "In-game canon", "Dev intent/ARG", "Community interpretation",
            "Headcanon/fan-fiction", "Disputed",
        ]),
        _f("lifeform_scope", "Lifeform scope", "multi", [
            "Gek", "Vy'keen", "Korvax", "Traveller", "Autophage", "Sentinel", "Mixed",
        ]),
        _f("source_type", "Source type", "multi", [
            "Story-mission", "Lore stone/monolith", "Plaque/Ruins", "Korvax Encyclopedia",
            "Boundary log", "NPC dialogue", "ARG", "Community-authored",
        ]),
        _f("arc_stage", "Story-arc stage", "single", [
            "Pre-Awakening", "Awakenings", "Atlas Path", "Artemis Path", "The Purge",
            "Post-game", "Standalone",
        ]),
    ],
    "guide": [
        _f("topic_area", "Topic area", "multi", [
            "Exploration", "Economy", "Combat", "Base-building", "Multi-tool", "Starship",
            "Farming", "Fishing", "Settlements", "Expeditions", "Freighters", "Photography",
            "Crafting", "Navigation", "Companions", "Living Ships", "Modding", "Multiplayer",
            "Getting Started",
        ]),
        _f("difficulty", "Difficulty", "single", ["Beginner", "Intermediate", "Advanced", "Expert/Min-max", "Reference"]),
        _f("patch_relevance", "Patch relevance", "single", ["Current", "Recent", "Legacy (pre-Worlds)", "Outdated", "Version-agnostic"]),
        _f("game_mode", "Game mode", "multi", GAME_MODE),
        _f("format", "Format", "single", ["Walkthrough", "Reference", "Tips", "Video", "Checklist", "Tutorial", "Tier list"]),
    ],
    "mechanic": [
        _f("category", "Category", "single", [
            "Economy", "Combat", "Crafting", "Exploration", "Base-building", "Multiplayer",
            "Technology", "Progression", "Survival", "Navigation", "Inventory", "Reputation",
            "Customization", "Automation",
        ]),
        _f("subsystem", "Subsystem", "multi", [
            "Exosuit", "Multi-tool", "Starship", "Freighter", "Exocraft", "Companion",
            "Settlement", "Base", "Refiner", "Trade", "Nexus/Anomaly", "Portals",
            "Sentinels", "Weather",
        ]),
        _f("activity", "Player activity", "multi", [
            "Mining", "Scanning", "Fighting", "Trading", "Building", "Farming", "Fishing",
            "Cooking", "Refining", "Piloting", "Diplomacy", "Exploring",
        ]),
        _f("introduced", "Introduced in", "single", ERA),
        _f("status", "Status", "single", ["Current", "Reworked", "Deprecated", "Legacy"]),
    ],
    "item": [
        _f("category", "Category", "single", [
            "Element/Raw", "Product", "Component", "Technology", "Tradeable",
            "Trade Commodity", "Curiosity", "Consumable", "Crafted", "Artifact",
        ]),
        _f("element_division", "Element division", "multi", [
            "Catalyst", "Earth", "Exotic", "Flora", "Fuel", "Metal", "Special", "Stellar",
        ]),
        _f("rarity", "Rarity / value", "single", ["Common", "Rare", "Extraordinary"]),
        _f("where_sourced", "Where sourced", "multi", [
            "Mining", "Cave", "Underwater", "Asteroid", "Flora", "Fauna", "Atmosphere",
            "Storm-only", "Refined", "Trade Terminal", "NPC/Mission", "Derelict",
            "Sentinel drop", "Stellar",
        ]),
        _f("star_gating", "Star-type gating", "multi", STAR_TYPE),
        _f("class", "Class", "single", CLASS + ["X"]),
    ],
}


def get_facets(namespace: str) -> list[dict]:
    """Return the ordered facet schema for a namespace (empty if none)."""
    return FACET_SCHEMAS.get(namespace, [])


def facet_keys(namespace: str) -> set[str]:
    return {f["key"] for f in FACET_SCHEMAS.get(namespace, [])}
