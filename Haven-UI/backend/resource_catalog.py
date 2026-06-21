"""Canonical NMS resource catalog + materials-string normalizer.

The planets.materials column is a comma-joined free-text list of resources
(e.g. "Salt, Gold, Copper"). In practice it accumulated a lot of noise:
  - case variants:  "Copper" / "copper" / "COPPER"
  - typos / non-English: "Cooper", "kupfer", "uramium", "doixit", "Phsphorus"
  - bad separators: "Salt. Gold. Copper", "Copper and uranium"
That made the resource FILTER (which matched the near-empty dedicated
common/uncommon/rare_resource columns) effectively useless, and any dropdown
built from the raw values a 170-entry mess.

This module is the single source of truth for normalizing those values:
`normalize_materials()` re-splits a raw cell, maps each token to its canonical
resource name where we can recognize it, and PRESERVES anything it can't map
(no information is dropped). `CANONICAL_RESOURCES` mirrors the curated
front-end list in Haven-UI/src/data/adjectives.js (`resourcesList`) — keep the
two in sync.
"""

# Curated canonical resource / collectible names. Mirror of `resourcesList`
# in Haven-UI/src/data/adjectives.js (the authoritative manual-upload list).
CANONICAL_RESOURCES = [
    # Raw Materials
    "Activated Cadmium", "Activated Copper", "Activated Emeril",
    "Activated Indium", "Activated Quartzite", "Ammonia", "Ancestral Memories",
    "Atlantideum", "Basalt", "Cactus Flesh", "Cadmium", "Carbon", "Chlorine",
    "Chromatic Metal", "Cobalt", "Condensed Carbon", "Copper",
    "Crystallised Helium", "Cursed Dust", "Cyto-Phosphate", "Deuterium",
    "Di-hydrogen", "Dioxite", "Emeril", "Faecium", "Ferrite Dust",
    "Fragmented Qualia", "Frost Crystal", "Fungal Mould", "Gamma Root", "Gold",
    "Hexite", "Indium", "Ionised Cobalt", "Kelp Sac", "Liquid Sun", "Lithium",
    "Living Slime", "Magnetised Ferrite", "Marrow Bulb", "Methane", "Mordite",
    "Nitrogen", "Oxygen", "Paraffinium", "Phosphorus", "Platinum",
    "Polished Stone", "Pugneum", "Pure Ferrite", "Pyrite", "Quartzite", "Radon",
    "Residual Goop", "Runaway Mould", "Rusted Metal", "Salt", "Shattered Qualia",
    "Silicate Powder", "Silver", "Sodium", "Sodium Nitrate", "Solanium",
    "Somnal Dust", "Star Bulb", "Sulphurine", "Tainted Metal", "Tritium",
    "Uranium", "Viscous Fluids", "Void Mote",
    # Special Harvestables
    "Ancient Bones", "Buried Technology", "Salvageable Scrap", "Storm Crystals",
    "Vile Brood Detected", "Whispering Eggs",
    # Cave & Underground Collectibles
    "Albumen Pearl", "Vortex Cube", "Submerged Relic",
    # Hazardous Flora Collectibles
    "Gravitino Ball", "Sac Venom", "Larval Core",
    # Underwater Collectibles
    "Living Pearl", "Crystal Sulphide", "Hadal Core", "Hypnotic Eye",
    # Exotic Planet Glitch Collectibles
    "Bubble Cluster", "Cable Pod", "Calcishroom", "Capillary Shell",
    "Electric Cube", "Glitching Separator", "Hexplate Bush", "Light Fissure",
    "Ossified Star", "Rattle Spine", "Terbium Growth",
    # Sentinel Drops
    "Quad Servo", "Walker Brain", "Hyaline Brain",
    # Other Miscellaneous
    "Salvaged Data", "Geode", "Gold Nugget", "Crystal Fragment", "Echo Seed",
    "Tritium Hypercluster",
]

# lower-cased canonical name -> canonical casing
_CANON_BY_LOWER = {r.lower(): r for r in CANONICAL_RESOURCES}

# Known messy variants -> canonical. Keys are lower-cased. Derived from the
# live data audit (case folding is handled separately, so these are only the
# non-trivial typos / misspellings / alternate spellings).
RESOURCE_ALIASES = {
    # Copper family
    "cooper": "Copper", "coppee": "Copper", "coppeer": "Copper",
    "coppee": "Copper", "coppe": "Copper", "kupfer": "Copper",
    "coopee": "Copper", "copeer": "Copper", "coppeee": "Copper",
    "activated cooper": "Activated Copper",
    # Cobalt
    "kobalt": "Cobalt", "cobal": "Cobalt",
    # Uranium
    "uramium": "Uranium",
    # Dioxite
    "doixit": "Dioxite", "dioxide": "Dioxite",
    # Phosphorus
    "phsphorus": "Phosphorus", "phophorus": "Phosphorus", "phosphor": "Phosphorus",
    # Paraffinium
    "parafinnium": "Paraffinium", "parafifnium": "Paraffinium",
    "paraaffinium": "Paraffinium", "parrafinium": "Paraffinium",
    "parafinium": "Paraffinium", "paraffin": "Paraffinium",
    # Magnetised Ferrite (US spelling / typos)
    "magnetized ferrite": "Magnetised Ferrite", "magnatised ferrite": "Magnetised Ferrite",
    "magnetic ferrite": "Magnetised Ferrite",
    # Fungal Mould (US spelling / typos)
    "fungal mold": "Fungal Mould", "fungal mount": "Fungal Mould",
    "mould": "Fungal Mould", "mold": "Fungal Mould",
    # Star Bulb
    "starbulb": "Star Bulb", "star bulbs": "Star Bulb",
    # Gamma Root
    "gamme root": "Gamma Root",
    # Faecium
    "feacium": "Faecium",
    # Cactus Flesh
    "cactus flrsh": "Cactus Flesh", "cactus": "Cactus Flesh",
    # Ancient Bones
    "acient bones": "Ancient Bones", "ancient bone": "Ancient Bones",
    "bones": "Ancient Bones",
    # Salvageable Scrap
    "salvagable scrap": "Salvageable Scrap", "salvage scrap": "Salvageable Scrap",
    "salvageable": "Salvageable Scrap", "scrap": "Salvageable Scrap",
    # Vile Brood (canonical is "Vile Brood Detected")
    "vile brood": "Vile Brood Detected", "vile brood detected": "Vile Brood Detected",
    # Sulphurine
    "suphurine": "Sulphurine", "sulphurite": "Sulphurine",
    # Ammonia
    "ammonium": "Ammonia",
    # Frost Crystal
    "frosst crystal": "Frost Crystal", "frostcrystal": "Frost Crystal",
    "frost crystals": "Frost Crystal",
    # Cadmium
    "cadium": "Cadmium",
}


def normalize_resource_token(token):
    """Map a single raw token to its canonical resource name.

    Returns the canonical name, or None if the token isn't a recognized
    resource (caller decides whether to preserve it verbatim).
    """
    if not token:
        return None
    t = " ".join(str(token).split()).strip(" .,:;-")  # collapse ws, strip edge punct
    if not t:
        return None
    low = t.lower()
    if low in _CANON_BY_LOWER:
        return _CANON_BY_LOWER[low]
    if low in RESOURCE_ALIASES:
        return RESOURCE_ALIASES[low]
    # Conservative single-edit fallback for obvious 1-char typos against the
    # canonical set (catches e.g. "cobal"->"cobalt"); skipped for very short
    # tokens where a 1-edit distance is too ambiguous.
    if len(low) >= 5:
        for cl, canon in _CANON_BY_LOWER.items():
            if abs(len(cl) - len(low)) <= 1 and _within_one_edit(low, cl):
                return canon
    return None


def _within_one_edit(a, b):
    """True if strings a, b are within Levenshtein distance 1 (cheap check)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    # Find first differing index
    i = 0
    while i < min(la, lb) and a[i] == b[i]:
        i += 1
    if la == lb:
        # substitution: rest must match after skipping one char
        return a[i + 1:] == b[i + 1:]
    # insertion/deletion: align the longer one by skipping one char
    if la > lb:
        return a[i + 1:] == b[i:]
    return a[i:] == b[i + 1:]


# Separators that have shown up between resources in the raw data.
import re as _re
_SPLIT_RE = _re.compile(r"\s*(?:,|\.|;|:|/| and |&|\n)\s*")


def normalize_materials(raw):
    """Normalize a raw `materials` cell into a clean canonical list.

    Re-splits on the various separators seen in the data, maps each token to a
    canonical resource where recognized, and PRESERVES unrecognized tokens
    verbatim (no information dropped). De-dupes case-insensitively while keeping
    first-seen order. Returns a ", "-joined string (or '' for empty input).
    """
    if not raw or not str(raw).strip():
        return ""
    out = []
    seen = set()
    for part in _SPLIT_RE.split(str(raw)):
        tok = part.strip()
        if not tok:
            continue
        canon = normalize_resource_token(tok)
        value = canon if canon else tok
        key = value.lower()
        if key not in seen:
            seen.add(key)
            out.append(value)
    return ", ".join(out)
