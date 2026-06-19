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

# Session lifetime. The cookie + server-side store BOTH slide forward on every
# authenticated request via the SessionCookieRefreshMiddleware in
# control_room_api.py — so this is effectively an *idle* timeout, not a hard
# wall-clock cap. An active user is logged in indefinitely; an idle user is
# kicked out after this many minutes of inactivity.
#
# CRITICAL: SESSION_COOKIE_SECONDS must equal SESSION_TIMEOUT_MINUTES * 60.
# Historically these two drifted apart (cookie was hard-coded to 600s while
# the server-side window was 20 min), which is why "the backend kicks me off
# after exactly 10 minutes" was the canonical symptom — the cookie expired
# before the server-side sliding window had a chance to matter. Derive one
# from the other so they cannot drift again.
SESSION_TIMEOUT_MINUTES = 60
SESSION_COOKIE_SECONDS = SESSION_TIMEOUT_MINUTES * 60

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

# Score ranges for the four letter grades. S+ is intentionally absent here:
# it is NOT a score band. S+ ("fully charted") is a checklist that sits ON TOP
# of an S-grade score (>=85) — a system is S+ only when, in addition to scoring
# S, it has a discovery on every body, wonder notes on every planet, a base,
# and a recorded station (when applicable). That checklist lives in
# services/completeness.check_splus_eligible() and is materialized into the
# systems.is_fully_charted column by update_completeness_score().
GRADE_THRESHOLDS = {'S': (85, 100), 'A': (65, 84), 'B': (40, 64), 'C': (0, 39)}

# S-grade baseline a system must clear before the S+ checklist is even run.
SPLUS_MIN_SCORE = 85
GRADE_SPLUS = 'S+'


def score_to_grade(score: int, is_fully_charted: bool = False) -> str:
    """Convert a completeness score (0-100) to a letter grade.

    S+ ("fully charted") is NOT a score threshold — it's a checklist that sits
    on top of the S grade (see services/completeness.check_splus_eligible).
    Callers that already know the system's fully-charted flag (e.g. read it from
    systems.is_fully_charted) pass is_fully_charted=True to surface S+; the
    default keeps the pure score→letter behavior for the many callers that only
    have a number.
    """
    if score >= SPLUS_MIN_SCORE:
        return GRADE_SPLUS if is_fully_charted else 'S'
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
# Civilization Role -> Feature Grants
# ============================================================================
#
# A civilization leader / co-leader is full-power within their civ ("'leader'
# and 'co_leader' are functionally identical per Parker's spec" — migration
# 1.80.0). Their access must NOT depend on whoever remembered to tick the
# civ's `enabled_features_default` checkboxes at founding time — that grid is
# framed for sub-admins and is usually left empty, which is exactly how a
# brand-new partner ended up tier=2 with `enabled_features=[]` and no access
# to Approvals. So leaders are granted this full feature set BY ROLE in
# `_recompute_profile_features`, regardless of the civ default or any
# per-member override. Sub-admins keep the per-member-override-else-civ-default
# behavior so their access stays delegable/restrictable.
#
# This mirrors the FEATURE_DEFAULTS list in CivilizationManagement.jsx (the
# partner-grade granular features). Super-admin-only flags (api_keys,
# backup_restore, partner_management) are intentionally excluded — those
# routes gate on user_type == 'super_admin' / RequireSuperAdmin, not on the
# features list, and a civ leader is not a site super admin.
LEADER_FEATURES = frozenset({
    'system_create',
    'system_edit',
    'approvals',
    'batch_approvals',
    'stats',
    'settings',
    'csv_import',
    'war_room',
})

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

def normalize_discovery_coords(latitude, longitude):
    """Validate and coerce a discovery's surface lat/long pair.

    Returns (lat_or_None, lng_or_None). Either value is coerced to float and
    range-checked: latitude must be in [-90, 90], longitude in [-180, 180].
    Anything non-numeric or out of range becomes None (the pair is independent
    — one bad value doesn't void the other). Used by every discovery INSERT
    path so a malformed coordinate can never land in the DB.
    """
    def _one(value, limit):
        if value is None or value == '':
            return None
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if f != f or f < -limit or f > limit:  # f != f rejects NaN
            return None
        return f
    return _one(latitude, 90.0), _one(longitude, 180.0)


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


def normalize_reality(reality) -> str:
    """Defensive scrub for the `reality` field on submission intake.

    Older Haven Extractor versions (≤1.9.7) can persist and send the Python
    enum repr (e.g. "RealityMode.Normal") instead of the bare value ("Normal")
    when pymhf's DearPyGUI round-trips the field as a string. This stripped
    out the "RealityMode." class prefix at every backend intake site so the
    bad value cannot reach `systems.reality` / `pending_systems.reality` /
    `regions.reality` even from a stale client. See 2026-05-12 incident.
    """
    if reality is None:
        return 'Normal'
    s = str(reality).strip()
    if '.' in s:
        s = s.split('.', 1)[1]
    return s if s in ('Normal', 'Permadeath') else 'Normal'


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
