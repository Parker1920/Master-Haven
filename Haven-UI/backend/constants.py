"""
Centralized constants for the Haven Control Room API.

All magic numbers, thresholds, and configuration values live here.
Import from this module instead of hardcoding values in route files.
"""

from pathlib import Path
import json
import hashlib
import logging

logger = logging.getLogger('control.room')

# ============================================================================
# Path Setup
# ============================================================================

BACKEND_DIR = Path(__file__).resolve().parent
HAVEN_UI_DIR = BACKEND_DIR.parent
MASTER_HAVEN_ROOT = HAVEN_UI_DIR.parent

# ============================================================================
# Pagination & Limits
# ============================================================================

DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 500
ACTIVITY_LOG_MAX = 500  # Keep only the last N activity logs

# ============================================================================
# Session & Auth
# ============================================================================

SESSION_TIMEOUT_MINUTES = 20

# Super admin credentials
# NOTE: INTENTIONAL DESIGN - 'Haven' is Parker's personal login, not a generic default
SUPER_ADMIN_USERNAME = "Haven"
# NOTE: INTENTIONAL DESIGN - default password, changed on first login in production
DEFAULT_SUPER_ADMIN_PASSWORD_HASH = hashlib.sha256("WhrStrsG".encode()).hexdigest()

# Default personal submission color (fuchsia)
DEFAULT_PERSONAL_COLOR = '#c026d3'

# ============================================================================
# Completeness Grading
# ============================================================================

GRADE_THRESHOLDS = {'S': (85, 100), 'A': (65, 84), 'B': (40, 64), 'C': (0, 39)}


def score_to_grade(score: int) -> str:
    """Convert a completeness score (0-100) to a letter grade."""
    if score >= 85:
        return 'S'
    elif score >= 65:
        return 'A'
    elif score >= 40:
        return 'B'
    return 'C'


# Biomes where fauna/flora are not expected (Dead, Gas Giant categories)
NO_LIFE_BIOMES = frozenset({
    'Dead', 'Lifeless', 'Life-Incompatible', 'Airless', 'Low Atmosphere',
    'Gas Giant', 'Empty',
})

# ============================================================================
# User Profile Tiers
# ============================================================================

TIER_SUPER_ADMIN = 1
TIER_PARTNER = 2
TIER_SUB_ADMIN = 3
TIER_MEMBER = 4
TIER_MEMBER_READONLY = 5

TIER_TO_USER_TYPE = {
    TIER_SUPER_ADMIN: 'super_admin',
    TIER_PARTNER: 'partner',
    TIER_SUB_ADMIN: 'sub_admin',
    TIER_MEMBER: 'member',
    TIER_MEMBER_READONLY: 'member_readonly',
}

# ============================================================================
# Submission Source Attribution
# ============================================================================
#
# Every pending/approved row carries a `source` enum so the UI can render
# distinct badges and analytics can split by upload path. Values:
#
#   'manual'          - web wizard, no API key on the request
#   'haven_extractor' - any extractor-style API key submission (per-user
#                       Extractor keys, the legacy 'Haven Extractor' system
#                       key, or the prototype 'Haven' admin key from Dec 2025)
#   'keeper_bot'      - the dedicated Keeper Discord bot keys
#                       ('Keeper 2.0' and the dormant 'Keeper Bot' v1)
#
# Historical 'companion_app' rows were folded into 'haven_extractor' in
# migration 1.69.0 - they were prototype extractor traffic before the
# dedicated extractor key was created.

SOURCE_MANUAL = 'manual'
SOURCE_EXTRACTOR = 'haven_extractor'
SOURCE_KEEPER_BOT = 'keeper_bot'

# API key names that map to the Keeper bot bucket. Match exactly on
# api_keys.name; key_type='admin' is too broad (shared with internal admin
# keys like 'Haven' and 'AP Cartography Bot' that aren't bot integrations).
KEEPER_API_KEY_NAMES = frozenset({'Keeper 2.0', 'Keeper Bot'})


def resolve_source(api_key_name):
    """Map an api_key_name (or None) to the canonical source enum.

    Anonymous requests (no API key) are 'manual'. Keeper bot keys get their
    own bucket. Everything else authenticated is bucketed as the extractor
    family.
    """
    if not api_key_name:
        return SOURCE_MANUAL
    if api_key_name in KEEPER_API_KEY_NAMES:
        return SOURCE_KEEPER_BOT
    return SOURCE_EXTRACTOR


# ============================================================================
# Discovery Constants
# ============================================================================

# Discovery type emoji-to-slug mapping for URL routing
DISCOVERY_EMOJI_TO_SLUG = {
    '\U0001f997': 'fauna',      # cricket
    '\U0001f33f': 'flora',      # herb
    '\U0001f48e': 'mineral',    # gem
    '\U0001f3db\ufe0f': 'ancient',  # classical building
    '\U0001f4dc': 'history',    # scroll
    '\U0001f9b4': 'bones',      # bone
    '\U0001f47d': 'alien',      # alien
    '\U0001f680': 'starship',   # rocket
    '\u2699\ufe0f': 'multitool',    # gear
    '\U0001f4d6': 'lore',       # open book
    '\U0001f3e0': 'base',       # house
    '\U0001f195': 'other',      # NEW button
}

# Reverse mapping: slug to emoji
DISCOVERY_SLUG_TO_EMOJI = {v: k for k, v in DISCOVERY_EMOJI_TO_SLUG.items()}

# All valid discovery type slugs
DISCOVERY_TYPE_SLUGS = list(DISCOVERY_SLUG_TO_EMOJI.keys())

# Discovery type display info
DISCOVERY_TYPE_INFO = {
    'fauna': {'emoji': '\U0001f997', 'label': 'Fauna'},
    'flora': {'emoji': '\U0001f33f', 'label': 'Flora'},
    'mineral': {'emoji': '\U0001f48e', 'label': 'Mineral'},
    'ancient': {'emoji': '\U0001f3db\ufe0f', 'label': 'Ancient'},
    'history': {'emoji': '\U0001f4dc', 'label': 'History'},
    'bones': {'emoji': '\U0001f9b4', 'label': 'Bones'},
    'alien': {'emoji': '\U0001f47d', 'label': 'Alien'},
    'starship': {'emoji': '\U0001f680', 'label': 'Starship'},
    'multitool': {'emoji': '\u2699\ufe0f', 'label': 'Multi-tool'},
    'lore': {'emoji': '\U0001f4d6', 'label': 'Lore'},
    'base': {'emoji': '\U0001f3e0', 'label': 'Custom Base'},
    'other': {'emoji': '\U0001f195', 'label': 'Other'},
}

# Simplified type-specific fields for discovery submissions (2-3 per type)
DISCOVERY_TYPE_FIELDS = {
    'fauna':    ['species_name', 'behavior'],
    'flora':    ['species_name', 'biome'],
    'mineral':  ['resource_type', 'deposit_richness'],
    'ancient':  ['age_era', 'associated_race'],
    'history':  ['language_status', 'author_origin'],
    'bones':    ['species_type', 'estimated_age'],
    'alien':    ['structure_type', 'operational_status'],
    'starship': ['ship_type', 'ship_class'],
    'multitool':['tool_type', 'tool_class'],
    'lore':     ['story_type'],
    'base':     ['base_type'],
    'other':    [],
}

# ============================================================================
# Data Restriction Field Groups
# ============================================================================

# Maps field group names to the specific columns they redact when restricted
RESTRICTABLE_FIELDS = {
    'coordinates': ['x', 'y', 'z', 'region_x', 'region_y', 'region_z'],
    'glyph_code': ['glyph_code', 'glyph_planet', 'glyph_solar_system'],
    'discovered_by': ['discovered_by', 'discovered_at', 'personal_discord_username'],
    'base_location': [],  # Applied to planets
    'description': ['description'],
    'star_type': ['star_type', 'economy_type', 'economy_level', 'conflict_level'],
    'planets': [],  # Special handling - hides planet details
}

# ============================================================================
# Galaxy Reference Data
# ============================================================================

GALAXIES_JSON_PATH = BACKEND_DIR / 'data' / 'galaxies.json'


def load_galaxies() -> dict:
    """Load galaxy reference data (all 256 NMS galaxies)."""
    try:
        if GALAXIES_JSON_PATH.exists():
            with open(GALAXIES_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load galaxies.json: {e}")
    return {"0": "Euclid"}


GALAXIES_DATA = load_galaxies()
GALAXY_NAMES = set(GALAXIES_DATA.values())
GALAXY_BY_INDEX = {int(k): v for k, v in GALAXIES_DATA.items()}
GALAXY_BY_NAME = {v: int(k) for k, v in GALAXIES_DATA.items()}


def validate_galaxy(galaxy: str) -> bool:
    """Validate galaxy name against known NMS galaxies."""
    return galaxy in GALAXY_NAMES


def validate_reality(reality: str) -> bool:
    """Validate reality value (Normal or Permadeath)."""
    return reality in ('Normal', 'Permadeath')


def get_discovery_type_slug(discovery_type: str) -> str:
    """Convert discovery type emoji or text to URL-friendly slug."""
    if not discovery_type:
        return 'other'
    if discovery_type.lower() in DISCOVERY_TYPE_SLUGS:
        return discovery_type.lower()
    if discovery_type in DISCOVERY_EMOJI_TO_SLUG:
        return DISCOVERY_EMOJI_TO_SLUG[discovery_type]
    text_lower = discovery_type.lower()
    text_mappings = {
        'fauna': 'fauna', 'flora': 'flora', 'mineral': 'mineral',
        'ancient': 'ancient', 'history': 'history', 'bones': 'bones',
        'alien': 'alien', 'starship': 'starship', 'ship': 'starship',
        'multi-tool': 'multitool', 'multitool': 'multitool', 'tool': 'multitool',
        'lore': 'lore', 'custom base': 'base', 'base': 'base',
        'other': 'other', 'unknown': 'other',
    }
    return text_mappings.get(text_lower, 'other')


def normalize_discord_username(username: str) -> str:
    """
    Normalize a Discord username for comparison by:
    1. Converting to lowercase
    2. Stripping the #XXXX discriminator suffix if present
    """
    if not username:
        return ''
    normalized = username.lower().strip()
    if '#' in normalized:
        normalized = normalized.split('#')[0]
    return normalized
