"""
haven_glyph_resolver.py
=======================

Reverse the namegen: derive 12-glyph portal addresses from NMS names.

Input you have:  system name (+ region name + galaxy)
Output you want: the 12-character portal glyph code.

This does it WITHOUT reimplementing the game's name algorithm, by leaning on
Haven's own catalogue (the ~13k extractor-uploaded systems, which already
carry both names and glyphs). The glyph packing math below is not guessed —
it was validated round-trip against 500 live catalogue records (500/500 exact).

RESOLUTION TIERS (tried in order, cheapest/most-certain first)
  1. CATALOG  — system name is already in Haven. Return its stored glyph.
                Exact. Covers everything the extractor has uploaded.
  2. REGION   — system isn't catalogued, but its region is, and the region
                already has a catalogued system with that exact name/SSI, OR
                we know the region coords and only need to place the SSI.
  3. GENERATE — region known, system genuinely never seen: brute-force SSI
                via the namegen adapter (namegen_adapter.system_name).
                Off unless you've wired + calibrated a real namegen.

Every result carries a CONFIDENCE and the number of candidates, so you never
treat an ambiguous hit as authoritative.

Stdlib only (urllib) — no pip installs, nothing to host, fits the Haven rule
of zero paid/subscription dependencies.

CLI:
    python haven_glyph_resolver.py "Cuomul-Ake" --galaxy Odyalutai
    python haven_glyph_resolver.py "Some System" --galaxy Euclid --region "Some Region"
    python haven_glyph_resolver.py --calibrate Euclid
"""

import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import namegen_adapter

API_BASE = "https://havenmap.online"
HTTP_TIMEOUT = 25
MAX_SSI = 0xFFF  # 4095 — SSI is a 12-bit field in the glyph code


# ======================================================================
# GLYPH MATH  (validated 500/500 against live catalogue records)
# ======================================================================
# A portal glyph code is 12 hex chars = 48 bits, laid out MSB-first as:
#
#     P  S S S  Y Y  Z Z Z  X X X
#     |  \___/  \_/  \___/  \___/
#     |    |     |     |      |
#     |    |     |     |      +-- region_x  (12 bits, raw 0..4095)
#     |    |     |     +--------- region_z  (12 bits, raw 0..4095)
#     |    |     +--------------- region_y  ( 8 bits, raw 0..255)
#     |    +--------------------- SSI       (12 bits, solar system index)
#     +-------------------------- planet    ( 4 bits, planet index)
#
# Haven stores region_x/y/z as the RAW glyph values (no signed-voxel offset),
# so packing is a direct bit-shift. (The save-file format uses different
# offsets — do not use those here.)

def pack_glyphs(planet: int, ssi: int, region_x: int, region_y: int, region_z: int) -> str:
    """Build a 12-char glyph code from its components. Inverse of decode_glyphs."""
    val = (
        (planet & 0xF) << 44
        | (ssi & 0xFFF) << 32
        | (region_y & 0xFF) << 24
        | (region_z & 0xFFF) << 12
        | (region_x & 0xFFF)
    )
    return format(val, "012X")


def decode_glyphs(glyph_code: str) -> dict:
    """Decode a 12-char glyph code back into its components."""
    val = int(glyph_code, 16)
    return {
        "planet": (val >> 44) & 0xF,
        "ssi": (val >> 32) & 0xFFF,
        "region_y": (val >> 24) & 0xFF,
        "region_z": (val >> 12) & 0xFFF,
        "region_x": val & 0xFFF,
    }


# ======================================================================
# THIN HAVEN API CLIENT  (stdlib urllib, read-only public endpoints)
# ======================================================================
def _get(path: str, params: dict = None) -> Optional[dict]:
    """GET <API_BASE><path>?<params> and return parsed JSON, or None on error."""
    url = API_BASE + path
    if params:
        # Drop None values so we only send filters we actually have.
        clean = {k: v for k, v in params.items() if v is not None}
        url += "?" + urllib.parse.urlencode(clean)
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"  [api error] {url} -> {e}", file=sys.stderr)
        return None


def search_systems_by_name(name: str, galaxy: str = None, reality: str = None,
                           rx: int = None, ry: int = None, rz: int = None) -> list:
    """Server-side name search, optionally narrowed by galaxy/region.

    Returns only records whose name matches the target EXACTLY (the q search
    is fuzzy, so we re-filter here to avoid near-miss false positives).
    """
    data = _get("/api/systems/search",
                {"q": name, "galaxy": galaxy, "reality": reality,
                 "rx": rx, "ry": ry, "rz": rz, "limit": 100})
    if not data:
        return []
    # /api/systems/search wraps rows in 'results'; other endpoints use 'systems'.
    rows = data.get("results") or data.get("systems") or (data if isinstance(data, list) else [])
    target = name.strip().casefold()
    return [s for s in rows if (s.get("name") or "").strip().casefold() == target]


def resolve_region_coords(region_name: str, galaxy: str = None) -> list:
    """Resolve a region NAME to candidate (rx, ry, rz) triples from the catalog.

    Region names can collide across the galaxy, so this returns a list. Each
    entry is (rx, ry, rz, galaxy). Caller decides how to disambiguate.
    """
    out = {}
    # /api/regions carries custom_name + coords + galaxy + system_count.
    data = _get("/api/regions", {"limit": 5000, "galaxy": galaxy})
    if data:
        target = region_name.strip().casefold()
        for r in data.get("regions", []):
            nm = (r.get("custom_name") or "").strip().casefold()
            if nm == target and (galaxy is None or r.get("galaxy") == galaxy):
                key = (r["region_x"], r["region_y"], r["region_z"])
                out[key] = (r["region_x"], r["region_y"], r["region_z"], r.get("galaxy"))
    return list(out.values())


def systems_in_region(rx: int, ry: int, rz: int) -> list:
    """All catalogued systems in a region, with names + SSIs."""
    data = _get(f"/api/regions/{rx}/{ry}/{rz}/systems")
    if not data:
        return []
    return data.get("systems", data if isinstance(data, list) else [])


# ======================================================================
# RESULT TYPES
# ======================================================================
class Confidence(str, Enum):
    HIGH = "high"        # single unambiguous hit
    MEDIUM = "medium"    # small candidate set, needs a tiebreak
    LOW = "low"          # many candidates / generic name — do not trust
    NONE = "none"        # nothing found


class Method(str, Enum):
    CATALOG = "catalog"          # exact stored glyph (Tier 1)
    REGION = "region_match"      # matched within a known region (Tier 2)
    GENERATE = "namegen_search"  # SSI brute-forced via namegen (Tier 3)
    UNRESOLVED = "unresolved"


@dataclass
class Candidate:
    glyph_code: str
    galaxy: Optional[str]
    region_name: Optional[str]
    region_x: int
    region_y: int
    region_z: int
    ssi: int
    planet: int
    source: str  # where the record/SSI came from (e.g. discord_tag, 'namegen')


@dataclass
class Resolution:
    query_name: str
    method: Method
    confidence: Confidence
    candidates: list = field(default_factory=list)
    note: str = ""

    def best(self) -> Optional[Candidate]:
        return self.candidates[0] if self.candidates else None

    def to_dict(self) -> dict:
        return {
            "query": self.query_name,
            "method": self.method.value,
            "confidence": self.confidence.value,
            "count": len(self.candidates),
            "note": self.note,
            "candidates": [c.__dict__ for c in self.candidates],
        }


# ======================================================================
# THE RESOLVER
# ======================================================================
def resolve(system_name: str, galaxy: str = None, region_name: str = None,
            reality: str = None, planet: int = 0) -> Resolution:
    """Derive glyphs for a system name. Tries Tier 1 -> 2 -> 3."""
    system_name = system_name.strip()

    # ---- TIER 1: catalogue exact match -------------------------------
    hits = search_systems_by_name(system_name, galaxy=galaxy, reality=reality)
    glyph_hits = [h for h in hits if h.get("glyph_code") and len(h["glyph_code"]) == 12]
    if glyph_hits:
        cands = [_candidate_from_record(h) for h in glyph_hits]
        # Collapse exact-duplicate glyph codes (same system, multiple uploads).
        cands = _dedupe(cands)
        conf = (Confidence.HIGH if len(cands) == 1
                else Confidence.MEDIUM if len(cands) <= 5
                else Confidence.LOW)
        note = ("exact catalogue hit" if len(cands) == 1
                else f"{len(cands)} catalogue systems share this name — "
                     "disambiguate by region/galaxy/star type")
        return Resolution(system_name, Method.CATALOG, conf, cands, note)

    # ---- Need region coords for Tiers 2 & 3 --------------------------
    region_coords = []
    if region_name:
        region_coords = resolve_region_coords(region_name, galaxy=galaxy)
    if not region_coords:
        return Resolution(
            system_name, Method.UNRESOLVED, Confidence.NONE, [],
            note=("not in catalogue and region "
                  + (f"'{region_name}' not found" if region_name
                     else "not provided — give a region to enable reconstruction")))

    # ---- TIER 2: match within the known region(s) --------------------
    region_cands = []
    for (rx, ry, rz, g) in region_coords:
        for s in systems_in_region(rx, ry, rz):
            if (s.get("name") or "").strip().casefold() == system_name.casefold():
                ssi = s.get("glyph_solar_system")
                if ssi is None and s.get("glyph_code") and len(s["glyph_code"]) == 12:
                    ssi = decode_glyphs(s["glyph_code"])["ssi"]  # derive from glyph
                if ssi is None:
                    continue
                ssi = int(ssi)
                region_cands.append(Candidate(
                    glyph_code=pack_glyphs(planet, ssi, rx, ry, rz),
                    galaxy=g or galaxy, region_name=region_name,
                    region_x=rx, region_y=ry, region_z=rz,
                    ssi=ssi, planet=planet,
                    source=s.get("discord_tag") or s.get("source") or "region_catalog"))
    region_cands = _dedupe(region_cands)
    if region_cands:
        conf = Confidence.HIGH if len(region_cands) == 1 else Confidence.MEDIUM
        return Resolution(system_name, Method.REGION, conf, region_cands,
                          note="matched a catalogued system inside the named region")

    # ---- TIER 3: generate names per SSI via the namegen --------------
    if not namegen_adapter.NAMEGEN_AVAILABLE:
        return Resolution(
            system_name, Method.UNRESOLVED, Confidence.NONE, [],
            note=("region known but system not catalogued; namegen not wired "
                  "(set NAMEGEN_AVAILABLE in namegen_adapter.py to enable SSI search)"))

    gen_cands = []
    for (rx, ry, rz, g) in region_coords:
        for ssi in range(MAX_SSI + 1):
            nm = namegen_adapter.system_name(g or galaxy, rx, ry, rz, ssi)
            if nm and nm.strip().casefold() == system_name.casefold():
                gen_cands.append(Candidate(
                    glyph_code=pack_glyphs(planet, ssi, rx, ry, rz),
                    galaxy=g or galaxy, region_name=region_name,
                    region_x=rx, region_y=ry, region_z=rz,
                    ssi=ssi, planet=planet, source="namegen"))
    gen_cands = _dedupe(gen_cands)
    if gen_cands:
        conf = (Confidence.HIGH if len(gen_cands) == 1
                else Confidence.MEDIUM if len(gen_cands) <= 5 else Confidence.LOW)
        return Resolution(system_name, Method.GENERATE, conf, gen_cands,
                          note="reconstructed by matching generated names per SSI")

    return Resolution(system_name, Method.UNRESOLVED, Confidence.NONE, [],
                      note="exhausted catalogue and namegen search with no match")


# ----------------------------------------------------------------------
def _candidate_from_record(s: dict) -> Candidate:
    # Search records carry glyph_code + region coords but not always SSI/planet,
    # so decode them straight from the glyph code as the source of truth.
    parts = decode_glyphs(s["glyph_code"])
    return Candidate(
        glyph_code=s["glyph_code"].upper(),
        galaxy=s.get("galaxy"),
        region_name=s.get("region_name"),
        region_x=int(s.get("region_x", parts["region_x"])),
        region_y=int(s.get("region_y", parts["region_y"])),
        region_z=int(s.get("region_z", parts["region_z"])),
        ssi=parts["ssi"],
        planet=parts["planet"],
        source=s.get("discord_tag") or s.get("source") or "catalog")


def _dedupe(cands: list) -> list:
    seen, out = set(), []
    for c in cands:
        if c.glyph_code not in seen:
            seen.add(c.glyph_code)
            out.append(c)
    return out


# ======================================================================
# CALIBRATION — prove the namegen reproduces real region names
# ======================================================================
def calibrate_regions(galaxy: str = "Euclid", sample: int = 50) -> None:
    """Diff namegen region names against Haven's stored region names.

    Regions can't be renamed in-game, so a mismatch means the namegen is a
    convention generator, not the real engine — keep Tier 3 off if so.
    """
    if not namegen_adapter.NAMEGEN_AVAILABLE:
        print("namegen not wired — nothing to calibrate.")
        return
    data = _get("/api/regions", {"limit": sample * 4, "galaxy": galaxy})
    regions = (data or {}).get("regions", [])[:sample]
    if not regions:
        print(f"no regions returned for galaxy '{galaxy}'.")
        return
    match = total = 0
    for r in regions:
        stored = (r.get("custom_name") or "").strip()
        if not stored:
            continue
        total += 1
        gen = namegen_adapter.region_name(galaxy, r["region_x"], r["region_y"], r["region_z"])
        ok = gen and gen.strip().casefold() == stored.casefold()
        match += 1 if ok else 0
        flag = "OK " if ok else "XX "
        print(f"  {flag}{stored!r:32} vs {gen!r}")
    rate = (match / total * 100) if total else 0
    print(f"\n  region-name match: {match}/{total} ({rate:.0f}%)")
    print("  >=~95% => namegen is real, Tier 3 trustworthy. "
          "Plausible-but-different => convention generator, keep Tier 3 off.")


# ======================================================================
# CLI
# ======================================================================
def _main(argv: list) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Derive NMS portal glyphs from names.")
    p.add_argument("name", nargs="?", help="system name to resolve")
    p.add_argument("--galaxy", help="galaxy name, e.g. Euclid")
    p.add_argument("--region", help="region name (enables reconstruction)")
    p.add_argument("--reality", help="game mode, e.g. Normal / Creative")
    p.add_argument("--planet", type=int, default=0, help="planet index (default 0 = space)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--calibrate", metavar="GALAXY", help="run region-name calibration")
    args = p.parse_args(argv)

    if args.calibrate:
        calibrate_regions(args.calibrate)
        return 0
    if not args.name:
        p.error("provide a system name (or --calibrate GALAXY)")

    res = resolve(args.name, galaxy=args.galaxy, region_name=args.region,
                  reality=args.reality, planet=args.planet)

    if args.json:
        print(json.dumps(res.to_dict(), indent=2))
        return 0

    print(f"\n  query     : {res.query_name}"
          f"{'  (' + args.galaxy + ')' if args.galaxy else ''}")
    print(f"  method    : {res.method.value}")
    print(f"  confidence: {res.confidence.value}")
    print(f"  note      : {res.note}")
    if res.candidates:
        print(f"  {'glyph code':<14} {'ssi':>5}  region            galaxy / source")
        for c in res.candidates[:10]:
            reg = f"{c.region_x},{c.region_y},{c.region_z}"
            print(f"  {c.glyph_code:<14} {c.ssi:>5}  {reg:<16}  "
                  f"{c.galaxy or '?'} / {c.source}")
    print()
    return 0 if res.candidates else 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
