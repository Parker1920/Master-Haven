"""
namegen_adapter.py
==================

THE ONLY INTEGRATION POINT for the reverse glyph resolver.

The resolver can recover glyphs three ways (see resolver.py). Two of them
need NOTHING from your namegen — they use Haven's catalog. The third tier,
for systems that are NOT in the catalog and live in a region with no
catalogued neighbours, needs to GENERATE a procedural system name for a
candidate (galaxy, region, SSI) and compare it to the target name.

That generation is the one thing this file cannot know on its own, because
the real No Man's Sky procedural names come from datamined word tables +
the game's seed function. Wire your local namegen here and Tier 3 lights up.
Leave it unimplemented and the resolver still does Tiers 1 and 2 fully.

================================================================
HOW TO WIRE IT
================================================================
Replace the body of `system_name()` with a call into your namegen, e.g.:

    from my_namegen import generate_system_name        # your module
    def system_name(galaxy, region_x, region_y, region_z, ssi):
        return generate_system_name(galaxy, region_x, region_y, region_z, ssi)

CONTRACT
- Inputs: galaxy (str name, e.g. "Euclid"), region_x/y/z (int, raw Haven
  region coords 0..4095 / 0..255 — NOT signed voxel coords), ssi (int 0..4095).
- Output: the system's *default procedural* name as the game would display it
  (str), or None if your namegen can't produce one for that slot.
- Must be DETERMINISTIC and must match the game's real names. If it returns
  plausible-but-different names, Tier 3 results are meaningless — see the
  calibration note at the bottom.
"""

# Flip to True only after you have wired and calibrated a real namegen.
NAMEGEN_AVAILABLE = False


def system_name(galaxy: str, region_x: int, region_y: int, region_z: int, ssi: int):
    """Return the procedural system name for a (galaxy, region, SSI) slot.

    Stub: returns None so the resolver cleanly reports 'namegen unavailable'
    for Tier 3 instead of guessing. Wire your namegen per the header.
    """
    if not NAMEGEN_AVAILABLE:
        return None
    raise NotImplementedError(
        "Set NAMEGEN_AVAILABLE = True and call your namegen here."
    )


def region_name(galaxy: str, region_x: int, region_y: int, region_z: int):
    """Optional: procedural region name for a coordinate.

    Only needed for the (rare) fully-blind case where you have a region name
    but no coords AND the region isn't in Haven's catalog. The resolver does
    not depend on this for normal use.
    """
    if not NAMEGEN_AVAILABLE:
        return None
    raise NotImplementedError("Wire region-name generation here if needed.")


# ================================================================
# CALIBRATION (run once after wiring, before trusting Tier 3)
# ================================================================
# Regions cannot be renamed in-game, so Haven's region coords are a clean
# truth set. Pull ~50 regions from /api/regions for ONE galaxy, feed each
# region_x/y/z into region_name(), and diff against custom_name. If they
# don't match, your namegen is a convention generator, not the real engine,
# and Tier 3 must stay off. resolver.py has a `calibrate_regions()` helper.
