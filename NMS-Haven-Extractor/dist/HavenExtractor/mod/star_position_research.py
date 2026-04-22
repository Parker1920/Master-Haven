# /// script
# [tool.pymhf]
# exe = "NMS.exe"
# steam_gameid = 275850
# start_exe = false
# ///
"""
Star Position Research Tool

Hooks cGcSolarSystemGenerator.GenerateQueryInfo to capture the GenerationData
struct output. This tells us where NMS places each star in the galaxy map.

Run alongside the Haven Extractor (or standalone) to collect ground truth data
for reverse engineering the star placement algorithm.

Output: ~/Documents/Haven-Extractor/star_position_data.jsonl
Each line is one system's data: seed, universe address, raw struct bytes, and
any Vector3f fields found via pattern scanning.
"""

import json
import logging
import struct
import ctypes
from datetime import datetime
from pathlib import Path
from ctypes import c_uint64, c_float

from pymhf import Mod
from pymhf.core.memutils import map_struct, get_addressof
from pymhf.gui.decorators import gui_button
import nmspy.data.types as nms
import nmspy.data.basic_types as basic
from nmspy.common import gameData

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path.home() / "Documents" / "Haven-Extractor"
OUTPUT_FILE = OUTPUT_DIR / "star_position_data.jsonl"


class StarPositionResearch(Mod):
    """Research mod to capture star position generation data from NMS."""

    __version__ = "0.1.0"

    def __init__(self):
        super().__init__()
        self._captures = []
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Star Position Research Tool loaded")
        logger.info(f"Output: {OUTPUT_FILE}")

    @nms.cGcSolarSystem.Generate.after
    def on_system_generate(self, this, lbUseSettingsFile, lSeed):
        """After a solar system generates, read its data for position research."""
        try:
            addr = get_addressof(this)
            if addr == 0:
                return

            solar_system = map_struct(addr, nms.cGcSolarSystem)
            sys_data = solar_system.mSolarSystemData

            # Read the system seed
            sys_data_addr = get_addressof(sys_data)
            if not sys_data_addr or sys_data_addr < 0x10000:
                return

            # Read seed from offset 0x21A0 (GcSeed)
            seed_bytes = (ctypes.c_ubyte * 8).from_address(sys_data_addr + 0x21A0)
            system_seed = int.from_bytes(bytes(seed_bytes), 'little')

            # Read the universe address from first planet's discovery data
            planets = solar_system.maPlanets
            discovery_data = planets[0].mPlanetDiscoveryData
            universe_addr = int(discovery_data.mUniverseAddress)

            # Now the key part: scan the SolarSystemData struct for position data.
            # The struct is ~0x2300 bytes. We know some fields (seed at 0x21A0,
            # star type at 0x2270, etc). The position is likely stored as a Vector3f
            # (3 floats, 12 bytes) somewhere in the struct.
            #
            # Strategy: dump candidate float triplets and compare across systems
            # to find which ones change in a way consistent with position.

            # Read a large chunk of the struct for analysis
            struct_size = 0x2400
            raw_bytes = (ctypes.c_ubyte * struct_size).from_address(sys_data_addr)
            raw_data = bytes(raw_bytes)

            # Scan for Vector3f candidates: look for float triplets where
            # each value is in a reasonable galaxy coordinate range (-2048 to +2048)
            candidates = []
            for offset in range(0, struct_size - 12, 4):
                try:
                    fx, fy, fz = struct.unpack_from('<fff', raw_data, offset)
                    # Galaxy coordinates range: roughly -2048 to +2048
                    if (-3000 < fx < 3000 and -500 < fy < 500 and -3000 < fz < 3000
                            and not (fx == 0 and fy == 0 and fz == 0)
                            and abs(fx) > 0.001 and abs(fz) > 0.001):
                        candidates.append({
                            "offset": hex(offset),
                            "x": round(fx, 6),
                            "y": round(fy, 6),
                            "z": round(fz, 6),
                        })
                except struct.error:
                    pass

            # Get system name for reference
            system_name = ""
            try:
                name_bytes = (ctypes.c_ubyte * 128).from_address(sys_data_addr + 0x2274)
                raw = bytes(name_bytes)
                null_pos = raw.find(0)
                if null_pos >= 0:
                    raw = raw[:null_pos]
                system_name = raw.decode('utf-8', errors='ignore').strip()
            except Exception:
                pass

            # Decode universe address for reference coords
            x_region = universe_addr & 0xFFF
            z_region = (universe_addr >> 12) & 0xFFF
            y_region = (universe_addr >> 24) & 0xFF
            system_idx = (universe_addr >> 40) & 0xFFF

            voxel_x = x_region if x_region <= 0x7FF else x_region - 0x1000
            voxel_y = y_region if y_region <= 0x7F else y_region - 0x100
            voxel_z = z_region if z_region <= 0x7FF else z_region - 0x1000

            capture = {
                "timestamp": datetime.now().isoformat(),
                "system_name": system_name,
                "universe_addr": hex(universe_addr),
                "system_seed": hex(system_seed),
                "system_idx": system_idx,
                "region": [x_region, y_region, z_region],
                "voxel": [voxel_x, voxel_y, voxel_z],
                "vector3f_candidates": candidates,
            }

            self._captures.append(capture)

            # Append to file
            with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(capture, default=str) + '\n')

            logger.info(f"[STAR-POS] Captured: '{system_name}' seed={hex(system_seed)} "
                        f"voxel=[{voxel_x},{voxel_y},{voxel_z}] sys={system_idx} "
                        f"candidates={len(candidates)}")

        except Exception as e:
            logger.error(f"[STAR-POS] Capture failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

    @gui_button("Star Position Status")
    def show_status(self):
        """Show how many systems have been captured."""
        logger.info(f"[STAR-POS] Captured {len(self._captures)} systems")
        logger.info(f"[STAR-POS] Output: {OUTPUT_FILE}")

        if self._captures:
            # Find offsets that appear in ALL captures — those are the stable position fields
            all_offsets = None
            for cap in self._captures:
                offsets = {c["offset"] for c in cap["vector3f_candidates"]}
                if all_offsets is None:
                    all_offsets = offsets
                else:
                    all_offsets &= offsets

            if all_offsets:
                logger.info(f"[STAR-POS] Offsets present in ALL captures: {sorted(all_offsets)}")

                # For each stable offset, show the values across captures
                for offset in sorted(all_offsets)[:5]:
                    vals = []
                    for cap in self._captures:
                        for c in cap["vector3f_candidates"]:
                            if c["offset"] == offset:
                                vals.append(f"({c['x']:.1f}, {c['y']:.1f}, {c['z']:.1f})")
                                break
                    logger.info(f"  {offset}: {' | '.join(vals[:5])}")

    @gui_button("Analyze Positions")
    def analyze(self):
        """Analyze captured data to find the position field."""
        if len(self._captures) < 2:
            logger.info("[STAR-POS] Need at least 2 captures to analyze. Warp to more systems.")
            return

        logger.info(f"[STAR-POS] Analyzing {len(self._captures)} captures...")

        # For each candidate offset, check if the values correlate with voxel coords
        # The star position should be CLOSE to the voxel coordinates but with a sub-region offset
        offset_scores = {}
        for offset_hex in {c["offset"] for cap in self._captures for c in cap["vector3f_candidates"]}:
            matches = 0
            diffs = []
            for cap in self._captures:
                vx, vy, vz = cap["voxel"]
                for c in cap["vector3f_candidates"]:
                    if c["offset"] == offset_hex:
                        dx = abs(c["x"] - vx)
                        dy = abs(c["y"] - vy)
                        dz = abs(c["z"] - vz)
                        # Position should be within ~1 unit of voxel coords (same region)
                        if dx < 100 and dy < 100 and dz < 100:
                            matches += 1
                            diffs.append((dx, dy, dz))
                        break

            if matches == len(self._captures):
                avg_diff = tuple(sum(d[i] for d in diffs) / len(diffs) for i in range(3))
                offset_scores[offset_hex] = {
                    "matches": matches,
                    "avg_diff": avg_diff,
                    "score": sum(avg_diff),  # Lower = better match
                }

        if offset_scores:
            logger.info("[STAR-POS] === CANDIDATE POSITION OFFSETS ===")
            for offset, data in sorted(offset_scores.items(), key=lambda x: x[1]["score"]):
                logger.info(f"  {offset}: avg_diff=({data['avg_diff'][0]:.2f}, "
                            f"{data['avg_diff'][1]:.2f}, {data['avg_diff'][2]:.2f}) "
                            f"score={data['score']:.2f}")
            best = min(offset_scores.items(), key=lambda x: x[1]["score"])
            logger.info(f"[STAR-POS] BEST CANDIDATE: offset {best[0]} (score {best[1]['score']:.2f})")
        else:
            logger.info("[STAR-POS] No offsets correlate with voxel coords across all captures.")
            logger.info("[STAR-POS] Position might be in a different coordinate space. Need more data.")
