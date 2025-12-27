"""NMS Memory Browser - Main entry point.

This is a pyMHF mod that provides a GUI for browsing game memory.
Launch with: pymhf run c:\\Master-Haven\\NMS-Memory-Browser

v3.8.4 - DEEP Base Search (game_state + BaseBuildingManager)
- NEW: Probes game_state in ADDITION to player_state for base arrays
- NEW: Explores mBaseBuildingManager structure for base data
- NEW: Searches memory for known base names from HUD markers
- FIX: Previous probe only found inventory data, now searches correct locations
- Logs all potential base array locations for modification research

v3.8.3 - WIDE Offset Probing for Base Discovery
- ENHANCED: Comprehensive offset scanning (5000+ offsets instead of 20)
- Probes 0x0-0x1000 every 8 bytes, 0x1000-0x10000 every 24 bytes
- Probes 0x10000-0x80000 every 256 bytes
- Expanded name detection (30+ offsets within each entry)
- Logs discovered arrays with name offset for base modification research

v3.8.2 - Offset Probing for Base Discovery
- NEW: Automatic offset probing to find PersistentPlayerBases across game versions
- Scans multiple potential offsets (0x7CC18, 0x7CD00, 0x80000, etc.)
- Validates arrays by checking for readable name strings
- Logs discovered offsets for analysis and future base modification

v3.8.1 - CRASH FIX: Safe Memory Access
- FIX: Added SafeMemoryReader with VirtualQuery validation to prevent crashes
- FIX: Experimental features disabled by default (ENABLE_EXPERIMENTAL_BASE_SCAN, ENABLE_EXPERIMENTAL_NETWORK_SCAN)
- All raw memory access now validates memory regions before reading
- Graceful fallback when memory is not accessible

v3.8.0 - ACTUAL Base & Network Player State Data
- NEW: Scans ACTUAL persistent player bases from cGcPlayerStateData (not just HUD markers)
- NEW: Extracts real base data with glyph codes and galactic addresses
- NEW: Attempts to read network player state data from network manager
- Keeps HUD marker scanning as visual fallback
- Dual data sources: Visual (HUD markers) + Actual (PlayerStateData)
- Base modification research: Shows memory addresses for potential edits

v3.7.1 - Network Players & Player Bases Detection
- Detects network players by "<IMG>MODE<>" pattern in marker names
- Detects player bases by name patterns (Base, Outpost, Colony, Haven, etc.)
- Shows "Nearby Player Bases" section with position coordinates
- Bases sorted by distance from current position
- Position extraction from raw memory (x, y, z coordinates)

v3.6.4 - Performance Timing Diagnostics
- Comprehensive timing diagnostics to identify startup bottlenecks
- [PERF] markers show time taken for each operation
- Timing summary printed when GUI is ready
- Tracks: module imports, struct enumeration, player data extraction,
  multiplayer detection, HUD marker scanning, and GUI launch

v3.6.3 - Enhanced Network Player Tracking
- Dual detection: marker hooks + direct HUD marker array scanning
- Scans 128 HUD markers for network player building classes
- Detects: NetworkPlayer, NetworkPlayerShip, NetworkPlayerVehicle, Fireteam

v3.6.1 - Enhanced Multiplayer Detection
- Multiple detection methods for multiplayer session status
- Scans for mbMultiplayerActive via attribute and raw memory offsets
- Detects Anomaly/Nexus location as multiplayer indicator
- Debug info panel shows detection attempts for troubleshooting
- Improved logging for multiplayer state debugging
- Browse ALL available game structures from nmspy
- Shows ALL FIELDS with offsets, sizes, and types for every struct
- Explore any gameData entry point dynamically
- View raw memory at any address
- Follow pointer chains to explore nested structures
- Identifies pointers, arrays, and nested structs
- Also includes planet data capture for convenience
"""

# /// script
# [tool.pymhf]
# exe = "NMS.exe"
# steam_gameid = 275850
# start_exe = true
# ///

import sys
import logging
import traceback
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Add the parent directory to sys.path so we can import our package
_this_dir = Path(__file__).parent
_parent_dir = _this_dir.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from pymhf import Mod
from pymhf.core.memutils import map_struct, get_addressof
from pymhf.gui.decorators import gui_button
from pymhf.core.hooking import one_shot
from nmspy.decorators import on_state_change
from nmspy.common import gameData
import nmspy.data.types as nms

# =============================================================================
# ENUM VALUE MAPPINGS (from MBINCompiler - same as haven_extractor)
# =============================================================================

BIOME_TYPES = {
    0: "Lush", 1: "Toxic", 2: "Scorched", 3: "Radioactive", 4: "Frozen",
    5: "Barren", 6: "Dead", 7: "Weird", 8: "Red", 9: "Green", 10: "Blue",
    11: "Test", 12: "Swamp", 13: "Lava", 14: "Waterworld", 15: "GasGiant", 16: "All"
}

BIOME_SUBTYPES = {
    0: "None", 1: "Standard", 2: "HighQuality", 3: "Structure", 4: "Beam",
    5: "Hexagon", 6: "FractCube", 7: "Bubble", 8: "Shards", 9: "Contour",
    10: "Shell", 11: "BoneSpire", 12: "WireCell", 13: "HydroGarden", 14: "HugePlant",
    15: "HugeLush", 16: "HugeRing", 17: "HugeRock", 18: "HugeScorch", 19: "HugeToxic",
    20: "Variant_A", 21: "Variant_B", 22: "Variant_C", 23: "Variant_D",
    24: "Infested", 25: "Swamp", 26: "Lava", 27: "Worlds",
    28: "Remix_A", 29: "Remix_B", 30: "Remix_C", 31: "Remix_D",
}

PLANET_SIZES = {0: "Large", 1: "Medium", 2: "Small", 3: "Moon", 4: "Giant"}

WEATHER_OPTIONS = {
    0: "Clear", 1: "Dust", 2: "Humid", 3: "Snow", 4: "Toxic",
    5: "Scorched", 6: "Radioactive", 7: "RedWeather", 8: "GreenWeather",
    9: "BlueWeather", 10: "Swamp", 11: "Lava", 12: "Bubble", 13: "Weird",
    14: "Fire", 15: "ClearCold", 16: "GasGiant",
}

STORM_FREQUENCY = {0: "None", 1: "Low", 2: "High", 3: "Always"}

LIFE_LEVELS = {0: "Dead", 1: "Low", 2: "Mid", 3: "Full"}
SENTINEL_LEVELS = {0: "Low", 1: "Default", 2: "High", 3: "Aggressive"}

GALAXY_NAMES = {
    0: "Euclid", 1: "Hilbert Dimension", 2: "Calypso",
    3: "Hesperius Dimension", 4: "Hyades", 5: "Ickjamatew",
    6: "Budullangr", 7: "Kikolgallr", 8: "Eltiensleen",
    9: "Eissentam", 10: "Elkupalos"
}

# =============================================================================
# EXPERIMENTAL FEATURE FLAGS
# These features use raw memory access and may cause crashes in some game states
# Set to True to enable experimental features (at your own risk)
# =============================================================================
ENABLE_EXPERIMENTAL_BASE_SCAN = True  # Scan PersistentPlayerBases from PlayerStateData
ENABLE_EXPERIMENTAL_NETWORK_SCAN = False  # Scan network player state data

# =============================================================================
# SAFE MEMORY ACCESS UTILITIES
# Uses Windows VirtualQuery to validate memory before reading
# =============================================================================
import ctypes
import ctypes.wintypes

class SafeMemoryReader:
    """Safe memory reader that validates addresses before access.

    Uses Windows VirtualQuery API to check if memory is readable before
    attempting to read it. This prevents crashes from accessing invalid memory.
    """

    # Memory protection constants
    PAGE_NOACCESS = 0x01
    PAGE_GUARD = 0x100
    PAGE_NOCACHE = 0x200

    # Memory state constants
    MEM_COMMIT = 0x1000

    # MEMORY_BASIC_INFORMATION structure
    class MEMORY_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_void_p),
            ("AllocationBase", ctypes.c_void_p),
            ("AllocationProtect", ctypes.wintypes.DWORD),
            ("RegionSize", ctypes.c_size_t),
            ("State", ctypes.wintypes.DWORD),
            ("Protect", ctypes.wintypes.DWORD),
            ("Type", ctypes.wintypes.DWORD),
        ]

    def __init__(self):
        """Initialize the safe memory reader."""
        self._kernel32 = ctypes.windll.kernel32
        self._VirtualQuery = self._kernel32.VirtualQuery
        self._VirtualQuery.argtypes = [ctypes.c_void_p, ctypes.POINTER(self.MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
        self._VirtualQuery.restype = ctypes.c_size_t

    def is_readable(self, address: int, size: int = 1) -> bool:
        """Check if memory at address is readable.

        Args:
            address: Memory address to check
            size: Number of bytes we want to read

        Returns:
            True if the memory region is readable, False otherwise
        """
        if address == 0 or address < 0x10000:  # NULL or low memory
            return False

        try:
            mbi = self.MEMORY_BASIC_INFORMATION()
            result = self._VirtualQuery(
                ctypes.c_void_p(address),
                ctypes.byref(mbi),
                ctypes.sizeof(mbi)
            )

            if result == 0:
                return False

            # Check if memory is committed and readable
            if mbi.State != self.MEM_COMMIT:
                return False

            # Check protection flags - must not be NOACCESS or GUARD
            if mbi.Protect & (self.PAGE_NOACCESS | self.PAGE_GUARD):
                return False

            # Check if the entire requested region fits in this block
            offset_in_region = address - mbi.BaseAddress
            if offset_in_region + size > mbi.RegionSize:
                # Need to check the next region too
                return self.is_readable(mbi.BaseAddress + mbi.RegionSize, size - (mbi.RegionSize - offset_in_region))

            return True

        except Exception:
            return False

    def read_uint64(self, address: int, default: int = 0) -> int:
        """Safely read a uint64 from memory."""
        if not self.is_readable(address, 8):
            return default
        try:
            return ctypes.c_uint64.from_address(address).value
        except Exception:
            return default

    def read_uint32(self, address: int, default: int = 0) -> int:
        """Safely read a uint32 from memory."""
        if not self.is_readable(address, 4):
            return default
        try:
            return ctypes.c_uint32.from_address(address).value
        except Exception:
            return default

    def read_int16(self, address: int, default: int = 0) -> int:
        """Safely read an int16 from memory."""
        if not self.is_readable(address, 2):
            return default
        try:
            return ctypes.c_int16.from_address(address).value
        except Exception:
            return default

    def read_uint16(self, address: int, default: int = 0) -> int:
        """Safely read a uint16 from memory."""
        if not self.is_readable(address, 2):
            return default
        try:
            return ctypes.c_uint16.from_address(address).value
        except Exception:
            return default

    def read_float(self, address: int, default: float = 0.0) -> float:
        """Safely read a float from memory."""
        if not self.is_readable(address, 4):
            return default
        try:
            return ctypes.c_float.from_address(address).value
        except Exception:
            return default

    def read_string(self, address: int, max_length: int = 64, default: str = "") -> str:
        """Safely read a null-terminated string from memory."""
        if not self.is_readable(address, min(max_length, 8)):  # At least check first 8 bytes
            return default
        try:
            # Read byte by byte up to max_length or until we can't read anymore
            result = []
            for i in range(max_length):
                if not self.is_readable(address + i, 1):
                    break
                byte = ctypes.c_ubyte.from_address(address + i).value
                if byte == 0:  # Null terminator
                    break
                if 32 <= byte < 127:  # Printable ASCII
                    result.append(chr(byte))
                elif byte >= 128:  # Could be UTF-8, try to include
                    result.append(chr(byte))
            return ''.join(result)
        except Exception:
            return default

    def read_bytes(self, address: int, size: int) -> bytes:
        """Safely read bytes from memory."""
        if not self.is_readable(address, size):
            return b''
        try:
            return ctypes.string_at(address, size)
        except Exception:
            return b''

# Global safe memory reader instance
_safe_reader = None

def get_safe_reader() -> SafeMemoryReader:
    """Get or create the global safe memory reader."""
    global _safe_reader
    if _safe_reader is None:
        _safe_reader = SafeMemoryReader()
    return _safe_reader

# Configure file-based logging for debugging crashes
_log_dir = _parent_dir / "logs"
_log_dir.mkdir(exist_ok=True)
_log_file = _log_dir / f"memory_browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create a file handler that flushes immediately
_file_handler = logging.FileHandler(_log_file, encoding='utf-8')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Set up both console and file logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        _file_handler,
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def log_flush(msg: str, level: str = "info"):
    """Log a message and immediately flush to disk."""
    if level == "info":
        logger.info(msg)
    elif level == "error":
        logger.error(msg)
    elif level == "warning":
        logger.warning(msg)
    elif level == "debug":
        logger.debug(msg)
    # Force flush all handlers
    for handler in logging.root.handlers:
        handler.flush()


# =============================================================================
# TIMING DIAGNOSTICS - Track startup performance
# =============================================================================
import time

_startup_time = time.time()
_last_timing_mark = _startup_time
_timing_marks = {}

def timing_mark(label: str, show_delta: bool = True):
    """Record a timing mark for performance diagnostics.

    Args:
        label: Description of what just completed
        show_delta: If True, shows time since last mark. If False, shows total time.
    """
    global _last_timing_mark
    now = time.time()
    total_elapsed = now - _startup_time
    delta = now - _last_timing_mark
    _timing_marks[label] = {'total': total_elapsed, 'delta': delta}
    _last_timing_mark = now

    if show_delta:
        log_flush(f"[TIMING] {label}: +{delta:.3f}s (total: {total_elapsed:.2f}s)")
    else:
        log_flush(f"[TIMING] {label}: {total_elapsed:.2f}s total")

def print_timing_summary():
    """Print a summary of all timing marks."""
    log_flush("=" * 60)
    log_flush("TIMING SUMMARY (Startup Performance)")
    log_flush("=" * 60)
    sorted_marks = sorted(_timing_marks.items(), key=lambda x: x[1]['total'])
    for label, times in sorted_marks:
        log_flush(f"  {times['delta']:6.3f}s  {label}")
    total = time.time() - _startup_time
    log_flush("-" * 60)
    log_flush(f"  TOTAL: {total:.2f}s")
    log_flush("=" * 60)


timing_mark("Module imports started")
log_flush(f"=== NMS Memory Browser Starting - Log: {_log_file} ===")


class GUIThread(threading.Thread):
    """Thread that runs the Qt event loop."""

    def __init__(self, game_data_provider=None):
        super().__init__(daemon=True)
        self._app = None
        self._window = None
        self._ready = threading.Event()
        self._stop_requested = False
        self._game_data_provider = game_data_provider  # Callback to get data from main thread

    def run(self):
        """Run the Qt event loop in this thread."""
        try:
            timing_mark("GUIThread: Starting")
            log_flush("GUIThread: Starting Qt event loop thread...")

            timing_mark("GUIThread: Importing PyQt6...")
            from PyQt6.QtWidgets import QApplication
            timing_mark("GUIThread: PyQt6 imported")

            # Create QApplication in this thread
            self._app = QApplication([])
            timing_mark("GUIThread: QApplication created")

            # Import and create main window with data provider
            timing_mark("GUIThread: Importing MainWindow...")
            from nms_memory_browser.ui.main_window import MainWindow
            timing_mark("GUIThread: MainWindow imported")

            timing_mark("GUIThread: Creating MainWindow...")
            self._window = MainWindow(game_data_provider=self._game_data_provider)
            timing_mark("GUIThread: MainWindow created")

            self._window.show()
            self._window.raise_()
            self._window.activateWindow()
            timing_mark("GUIThread: Window shown")

            # Signal that we're ready
            self._ready.set()
            log_flush("GUIThread: Ready, starting event loop...")
            print_timing_summary()  # Print summary when GUI is ready

            # Run the event loop
            self._app.exec()
            log_flush("GUIThread: Event loop ended")

        except Exception as e:
            log_flush(f"GUIThread: FAILED - {e}", "error")
            log_flush(f"GUIThread: Traceback:\n{traceback.format_exc()}", "error")
            self._ready.set()  # Unblock waiting threads even on error

    def stop(self):
        """Request the thread to stop."""
        if self._app:
            self._app.quit()


class NMSMemoryBrowser(Mod):
    """NMS Memory Browser mod.

    Provides a PyQt6 GUI for browsing ALL game memory structures.
    General-purpose browser for exploring any nmspy struct type.
    Also captures planet data via hooks for convenience.
    """

    __author__ = "Master Haven"
    __version__ = "3.8.4"
    __description__ = "General-purpose live memory browser for No Man's Sky with WIDE offset probing"

    # Flag to ensure GcApplication is only set once
    _gc_application_set = False

    def __init__(self):
        timing_mark("NMSMemoryBrowser.__init__ starting")
        super().__init__()
        self._gui_thread: Optional[GUIThread] = None
        self._cached_game_data = {}  # Cache data collected from main thread
        self._data_lock = threading.Lock()
        self._data_ready = False  # Set True when APPVIEW fires
        self._cached_solar_system = None  # Direct memory mapped solar system

        # =====================================================
        # CRITICAL v2.0: Captured planet data from GenerateCreatureRoles hook
        # This dictionary stores Flora, Fauna, Sentinels, Weather, etc. per planet
        # Key: planet_index, Value: dict with captured data
        # =====================================================
        self._captured_planets: Dict[int, Dict[str, Any]] = {}
        self._capture_enabled = False  # Only capture after system generates

        # =====================================================
        # v3.6.2: Network player tracking via marker hooks
        # Detects other players via marker system (building class 0x39)
        # Key: player_name, Value: dict with player data (position, join time)
        # =====================================================
        self._network_players: Dict[str, Dict[str, Any]] = {}
        self._markers_added = 0
        self._markers_removed = 0
        self._discovered_bases = []  # Player bases discovered via marker scan

        timing_mark("NMSMemoryBrowser.__init__ completed")
        logger.info("=" * 60)
        logger.info("NMS Memory Browser v3.8.4 - DEEP Base Search")
        logger.info("  ENHANCED: Scanning 5000+ offsets to find base arrays")
        logger.info("  Safe memory access with VirtualQuery validation")
        logger.info(f"  ENABLE_EXPERIMENTAL_BASE_SCAN = {ENABLE_EXPERIMENTAL_BASE_SCAN}")
        logger.info(f"  ENABLE_EXPERIMENTAL_NETWORK_SCAN = {ENABLE_EXPERIMENTAL_NETWORK_SCAN}")
        logger.info("  Detects network players by <IMG>MODE<> pattern")
        logger.info("  Detects player bases by name patterns (visual fallback)")
        logger.info("  Browse ALL available nmspy struct types")
        logger.info("  View ALL FIELDS with offsets, sizes, and types")
        logger.info("  Comprehensive player data: stats, currencies, ships, character state")
        logger.info("  Multiplayer session status, game mode, and lobby info")
        logger.info("  Freighter, base building, and multitool detection")
        logger.info("  Live value reading with auto-refresh")
        logger.info("  View raw memory and follow pointer chains")
        logger.info("  Planet data capture included for convenience")
        logger.info("=" * 60)

    # =========================================================================
    # CRITICAL: GcApplication Singleton Hook
    # nmspy's internal singletons mod isn't loading, so we capture GcApplication ourselves
    # This is needed for gameData.player_state, gameData.simulation, etc. to work
    # =========================================================================

    @one_shot
    @nms.cTkFSM.StateChange.after
    def capture_gc_application(self, this, *args):
        """One-shot hook to capture the GcApplication singleton.

        This fires early when the game's FSM changes state. The cGcApplication
        object is derived from cTkFSM, so the first FSM state change gives us
        the application pointer.

        Without this, gameData.player_state will always be None!
        """
        if NMSMemoryBrowser._gc_application_set:
            return

        log_flush("=" * 50)
        log_flush("=== CRITICAL HOOK: cTkFSM.StateChange.after ===")
        log_flush("  Capturing GcApplication singleton...")

        try:
            addr = get_addressof(this)
            log_flush(f"  FSM this pointer: 0x{addr:X}")

            if addr != 0:
                gameData.GcApplication = map_struct(addr, nms.cGcApplication)
                NMSMemoryBrowser._gc_application_set = True
                log_flush(f"  SUCCESS: gameData.GcApplication = {gameData.GcApplication}")
                log_flush("  gameData.player_state should now work!")

                # Verify it worked
                try:
                    ps = gameData.player_state
                    log_flush(f"  Verification: gameData.player_state = {ps}")
                    if ps is not None:
                        log_flush("  PLAYER STATE IS NOW AVAILABLE!")
                except Exception as e:
                    log_flush(f"  Verification failed: {e}", "warning")
            else:
                log_flush("  WARNING: FSM this pointer is NULL", "warning")
        except Exception as e:
            log_flush(f"  Failed to capture GcApplication: {e}", "error")
            log_flush(traceback.format_exc(), "error")

    # =========================================================================
    # Function Hooks - These hook directly into game functions (like haven_extractor)
    # =========================================================================

    @nms.cGcSolarSystem.Generate.after
    def on_system_generate(self, this, lbUseSettingsFile, lSeed):
        """Fires AFTER solar system generation - cache the solar system pointer."""
        log_flush("=" * 50)
        log_flush("=== FUNCTION HOOK: cGcSolarSystem.Generate.after ===")
        log_flush(f"  this pointer: {this}, seed: {lSeed}")

        addr = get_addressof(this)
        if addr == 0:
            log_flush("  WARNING: this pointer is NULL", "warning")
            return

        log_flush(f"  this address: 0x{addr:X}")

        try:
            self._cached_solar_system = map_struct(addr, nms.cGcSolarSystem)
            self._data_ready = True

            # =====================================================
            # v2.0: Clear captured planets for new system
            # =====================================================
            self._captured_planets.clear()
            self._capture_enabled = True
            log_flush("  [v2.0] Captured planet data cleared for new system")
            log_flush("  [v2.0] Capture ENABLED - GenerateCreatureRoles hook active")

            log_flush(f"  Cached solar system: {self._cached_solar_system}")
            log_flush("  DATA IS NOW READY - Planet data will be captured automatically")
        except Exception as e:
            log_flush(f"  Failed to cache solar system: {e}", "error")

    # =========================================================================
    # CRITICAL v2.0: GenerateCreatureRoles HOOK - Captures ALL planet data
    # This hook fires for EVERY planet as the game generates creature roles.
    # The lPlanetData parameter contains Flora, Fauna, Sentinels, Weather, etc.
    # =========================================================================

    @nms.cGcPlanetGenerator.GenerateCreatureRoles.after
    def on_creature_roles_generate(self, this, lPlanetData, lUA):
        """
        Captures planet data when GenerateCreatureRoles is called.

        This hook fires for EACH planet in the system, receiving the full
        cGcPlanetData structure with Flora, Fauna, Sentinels, Weather, etc.

        IMPORTANT: We limit capture to 6 planets max because the hook also
        fires for nearby systems during galaxy discovery.
        """
        if not self._capture_enabled:
            return

        # CRITICAL: Limit to 6 planets max (NMS max planets per system)
        if len(self._captured_planets) >= 6:
            return

        try:
            # Get the planet data pointer
            planet_data_addr = get_addressof(lPlanetData)
            if planet_data_addr == 0:
                log_flush("GenerateCreatureRoles: lPlanetData is NULL", "debug")
                return

            # Map to cGcPlanetData structure
            import nmspy.data.exported_types as nmse
            planet_data = map_struct(planet_data_addr, nmse.cGcPlanetData)

            # Determine planet index
            planet_index = len(self._captured_planets)

            # Extract Flora (Life field)
            flora_raw = 0
            flora_name = "Unknown"
            try:
                if hasattr(planet_data, 'Life'):
                    life_val = planet_data.Life
                    if hasattr(life_val, 'value'):
                        flora_raw = life_val.value
                    else:
                        flora_raw = int(life_val) if life_val is not None else 0
                    flora_name = LIFE_LEVELS.get(flora_raw, f"Unknown({flora_raw})")
            except Exception as e:
                log_flush(f"Flora extraction failed: {e}", "debug")

            # Extract Fauna (CreatureLife field)
            fauna_raw = 0
            fauna_name = "Unknown"
            try:
                if hasattr(planet_data, 'CreatureLife'):
                    creature_val = planet_data.CreatureLife
                    if hasattr(creature_val, 'value'):
                        fauna_raw = creature_val.value
                    else:
                        fauna_raw = int(creature_val) if creature_val is not None else 0
                    fauna_name = LIFE_LEVELS.get(fauna_raw, f"Unknown({fauna_raw})")
            except Exception as e:
                log_flush(f"Fauna extraction failed: {e}", "debug")

            # Extract Sentinels
            sentinel_raw = 0
            sentinel_name = "Unknown"
            try:
                if hasattr(planet_data, 'GroundCombatDataPerDifficulty'):
                    combat_data = planet_data.GroundCombatDataPerDifficulty
                    if hasattr(combat_data, 'SentinelLevel'):
                        sentinel_val = combat_data.SentinelLevel
                        if hasattr(sentinel_val, 'value'):
                            sentinel_raw = sentinel_val.value
                        else:
                            sentinel_raw = int(sentinel_val) if sentinel_val is not None else 0
                        sentinel_name = SENTINEL_LEVELS.get(sentinel_raw, f"Unknown({sentinel_raw})")
            except Exception as e:
                log_flush(f"Sentinel extraction failed: {e}", "debug")

            # Extract Biome, BiomeSubType, and Size from GenerationData
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
                    # Extract Size
                    if hasattr(gen_data, 'Size'):
                        size_val = gen_data.Size
                        if hasattr(size_val, 'value'):
                            planet_size_raw = size_val.value
                        else:
                            planet_size_raw = int(size_val) if size_val is not None else -1
                        planet_size_name = PLANET_SIZES.get(planet_size_raw, f"Unknown({planet_size_raw})")
                        is_moon = (planet_size_raw == 3)  # Moon = 3
            except Exception as e:
                log_flush(f"Biome extraction from GenerationData failed: {e}", "debug")

            # Extract resources - clean to remove garbage characters
            common_resource = ""
            uncommon_resource = ""
            rare_resource = ""
            try:
                if hasattr(planet_data, 'CommonSubstanceID'):
                    val = str(planet_data.CommonSubstanceID) or ""
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
                log_flush(f"Resource extraction failed: {e}", "debug")

            # Extract weather from cGcPlanetData.Weather.WeatherType
            weather = ""
            weather_raw = -1
            storm_frequency = ""
            try:
                if hasattr(planet_data, 'Weather'):
                    weather_data = planet_data.Weather
                    if hasattr(weather_data, 'WeatherType'):
                        weather_val = weather_data.WeatherType
                        if hasattr(weather_val, 'value'):
                            weather_raw = weather_val.value
                        else:
                            weather_raw = int(weather_val) if weather_val is not None else -1
                        weather = WEATHER_OPTIONS.get(weather_raw, f"Unknown({weather_raw})")
                    if hasattr(weather_data, 'StormFrequency'):
                        storm_val = weather_data.StormFrequency
                        if hasattr(storm_val, 'value'):
                            storm_raw = storm_val.value
                        else:
                            storm_raw = int(storm_val) if storm_val is not None else -1
                        storm_frequency = STORM_FREQUENCY.get(storm_raw, f"Unknown({storm_raw})")
            except Exception as e:
                log_flush(f"Weather extraction failed: {e}", "debug")

            # Fallback: Try PlanetInfo.Weather display string if Weather struct failed
            if not weather or weather == "Unknown(-1)":
                try:
                    if hasattr(planet_data, 'PlanetInfo'):
                        info = planet_data.PlanetInfo
                        if hasattr(info, 'Weather'):
                            val = str(info.Weather) or ""
                            fallback_weather = ''.join(c for c in val if c.isprintable() and ord(c) < 128)
                            if fallback_weather and len(fallback_weather) >= 2 and fallback_weather != "None":
                                weather = fallback_weather
                except Exception as e:
                    log_flush(f"Weather fallback extraction failed: {e}", "debug")

            # Extract planet Name from cGcPlanetData.Name
            planet_name = ""
            try:
                if hasattr(planet_data, 'Name'):
                    name_val = planet_data.Name
                    if name_val is not None:
                        name_str = str(name_val) or ""
                        planet_name = ''.join(c for c in name_str if c.isprintable() and ord(c) < 128)
                        if planet_name and (len(planet_name) < 2 or planet_name == "None"):
                            planet_name = ""
            except Exception as e:
                log_flush(f"Planet name extraction failed: {e}", "debug")

            # Store captured data
            self._captured_planets[planet_index] = {
                'planet_index': planet_index,
                'planet_name': planet_name,
                'biome': biome_name,
                'biome_raw': biome_raw,
                'biome_subtype': biome_subtype_name,
                'biome_subtype_raw': biome_subtype_raw,
                'planet_size': planet_size_name,
                'planet_size_raw': planet_size_raw,
                'is_moon': is_moon,
                'flora': flora_name,
                'flora_raw': flora_raw,
                'fauna': fauna_name,
                'fauna_raw': fauna_raw,
                'sentinel': sentinel_name,
                'sentinel_raw': sentinel_raw,
                'weather': weather,
                'weather_raw': weather_raw,
                'storm_frequency': storm_frequency,
                'common_resource': common_resource,
                'uncommon_resource': uncommon_resource,
                'rare_resource': rare_resource,
            }

            log_flush("")
            log_flush("*" * 60)
            log_flush(f">>> CAPTURED PLANET {planet_index} DATA! <<<")
            log_flush(f"    Name: {planet_name or '(not set)'}")
            log_flush(f"    Biome: {biome_name} | SubType: {biome_subtype_name}")
            log_flush(f"    Size: {planet_size_name} [is_moon={is_moon}]")
            log_flush(f"    Flora: {flora_name} | Fauna: {fauna_name} | Sentinels: {sentinel_name}")
            log_flush(f"    Weather: {weather} (storms: {storm_frequency})")
            log_flush(f"    Resources: {common_resource}, {uncommon_resource}, {rare_resource}")
            log_flush(f"    Total captured: {len(self._captured_planets)} planets")
            log_flush("*" * 60)
            log_flush("")

        except Exception as e:
            log_flush(f"GenerateCreatureRoles capture failed: {e}", "error")
            log_flush(traceback.format_exc(), "error")

    # =========================================================================
    # v3.6.2: Network Player Tracking via Marker Hooks
    # Markers with building class 0x39 (NetworkPlayer) are other players
    # =========================================================================

    # Building class value for network players
    NETWORK_PLAYER_CLASS = 0x39  # 57 decimal

    @nms.cGcMarkerList.TryAddMarker.after
    def on_marker_added(self, this, lPoint, lbUpdateTime):
        """Hook called when a marker is added - detect network players."""
        self._markers_added += 1

        if not lPoint:
            return

        try:
            marker = lPoint.contents
            name = ""
            subtitle = ""
            position = None
            building_class = None

            # Extract marker data
            try:
                name = str(marker.mCustomName)
            except:
                pass

            try:
                subtitle = str(marker.mCustomSubtitle)
            except:
                pass

            try:
                pos = marker.mPosition
                position = {
                    'x': float(pos.x) if hasattr(pos, 'x') else 0,
                    'y': float(pos.y) if hasattr(pos, 'y') else 0,
                    'z': float(pos.z) if hasattr(pos, 'z') else 0,
                }
            except:
                pass

            try:
                building_class = int(marker.meBuildingClass)
            except:
                pass

            # Check if this is a network player (building class 0x39)
            if building_class == self.NETWORK_PLAYER_CLASS:
                from datetime import datetime
                log_flush(f"*** NETWORK PLAYER DETECTED: {name} ***")
                log_flush(f"    Subtitle: {subtitle}")
                log_flush(f"    Position: {position}")

                # Store in network players dictionary
                if name:
                    self._network_players[name] = {
                        'name': name,
                        'subtitle': subtitle,
                        'position': position,
                        'building_class': building_class,
                        'detected_at': datetime.now().isoformat(),
                        'status': 'active',
                    }
                    log_flush(f"    Network players now: {list(self._network_players.keys())}")

        except Exception as e:
            log_flush(f"Error processing marker addition: {e}", "debug")

    @nms.cGcMarkerList.RemoveMarker.after
    def on_marker_removed(self, this, lExampleMarker):
        """Hook called when a marker is removed - track player departures."""
        self._markers_removed += 1

        if not lExampleMarker:
            return

        try:
            marker = lExampleMarker.contents
            name = ""

            try:
                name = str(marker.mCustomName)
            except:
                pass

            # If this was a tracked network player, update their status
            if name and name in self._network_players:
                log_flush(f"*** NETWORK PLAYER MARKER REMOVED: {name} ***")
                self._network_players[name]['status'] = 'left'
                from datetime import datetime
                self._network_players[name]['left_at'] = datetime.now().isoformat()

        except Exception as e:
            log_flush(f"Error processing marker removal: {e}", "debug")

    # =========================================================================
    # State Change Hooks - These may or may not fire depending on nmspy config
    # =========================================================================

    @on_state_change("APPVIEW")
    def on_appview(self):
        """Fires when entering game view - player_state is now available."""
        log_flush("=== STATE HOOK: APPVIEW - Game data now available ===")
        self._data_ready = True
        self._try_auto_collect()

    def _try_auto_collect(self):
        """Try to auto-collect data when a state hook fires."""
        try:
            self._collect_game_data()
            log_flush("Data auto-collected on state change")
        except Exception as e:
            log_flush(f"Auto-collect failed: {e}", "warning")

    def _coords_to_glyphs(self, planet: int, system: int, x: int, y: int, z: int) -> str:
        """Convert coordinates to portal glyph code."""
        portal_x = (x + 2047) & 0xFFF
        portal_y = (y + 127) & 0xFF
        portal_z = (z + 2047) & 0xFFF
        portal_sys = system & 0x1FF
        portal_planet = planet & 0xF
        return f"{portal_planet:01X}{portal_sys:03X}{portal_y:02X}{portal_z:03X}{portal_x:03X}"

    def _safe_int(self, val) -> int:
        """Safely convert a value to int."""
        if val is None:
            return 0
        if hasattr(val, 'value'):
            return int(val.value)
        try:
            return int(val)
        except:
            return 0

    def _safe_float(self, val) -> float:
        """Safely convert a value to float."""
        if val is None:
            return 0.0
        if hasattr(val, 'value'):
            return float(val.value)
        try:
            return float(val)
        except:
            return 0.0

    def _scan_hud_markers_for_players(self) -> list:
        """
        Directly scan the HUD markers array to find network players.

        This reads the cGcPlayerHUD.maMarkers array (128 entries) and looks for
        markers that have a custom name set (which indicates a network player).

        HUD Marker structure:
        - maMarkers is at offset 0x20F50 in cGcPlayerHUD
        - Each cGcHUDMarker is 0x1610 bytes
        - cGcMarkerPoint (mData) is at offset 0x10 within cGcHUDMarker
        - mCustomName is at offset 0x38 within cGcMarkerPoint
        - meBuildingClass is at offset 0x118 within cGcMarkerPoint

        Scanner Icon Types for network players (from cGcScannerIconTypesEnum):
        - NetworkPlayerFireTeam = 0x1B (27) - Fireteam member on foot
        - NetworkPlayerFireTeamShip = 0x1C (28) - Fireteam member in ship
        - NetworkPlayer = 0x1D (29) - Non-fireteam player on foot
        - NetworkPlayerShip = 0x1E (30) - Non-fireteam player in ship
        - NetworkPlayerVehicle = 0x1F (31) - Player in vehicle

        Returns:
            List of dictionaries with network player info
        """
        import ctypes
        from datetime import datetime

        network_players = []
        scan_start = time.time()

        try:
            log_flush("  _scan_hud_markers: Starting HUD marker scan...")

            app = gameData.GcApplication
            log_flush(f"  _scan_hud_markers: GcApplication = {app}")
            if not app or not hasattr(app, 'mpData') or not app.mpData:
                log_flush("  _scan_hud_markers: EARLY EXIT - No app data available")
                return network_players

            log_flush(f"  _scan_hud_markers: app.mpData = {app.mpData}")
            app_data = app.mpData.contents
            log_flush(f"  _scan_hud_markers: app_data type = {type(app_data).__name__}")

            if not hasattr(app_data, 'mHUDManager'):
                log_flush("  _scan_hud_markers: EARLY EXIT - No mHUDManager attribute")
                return network_players

            hud_mgr = app_data.mHUDManager
            log_flush(f"  _scan_hud_markers: mHUDManager = {type(hud_mgr).__name__}")

            # List ALL available attributes on mHUDManager to find marker access
            hud_mgr_attrs = [a for a in dir(hud_mgr) if not a.startswith('_')]
            log_flush(f"  _scan_hud_markers: mHUDManager has {len(hud_mgr_attrs)} attrs: {hud_mgr_attrs[:30]}")

            # Try multiple paths to find markers
            markers = None
            markers_source = None

            # Path 1: mHUDManager.mMarkerList (cGcMarkerList)
            if hasattr(hud_mgr, 'mMarkerList'):
                marker_list = hud_mgr.mMarkerList
                log_flush(f"  _scan_hud_markers: Found mMarkerList = {type(marker_list).__name__}")
                ml_attrs = [a for a in dir(marker_list) if not a.startswith('_')]
                log_flush(f"  _scan_hud_markers: mMarkerList attrs: {ml_attrs[:25]}")
                if hasattr(marker_list, 'maMarkerPoints'):
                    markers = marker_list.maMarkerPoints
                    markers_source = "mMarkerList.maMarkerPoints"
                elif hasattr(marker_list, 'maMarkers'):
                    markers = marker_list.maMarkers
                    markers_source = "mMarkerList.maMarkers"
                elif hasattr(marker_list, 'mMarkers'):
                    markers = marker_list.mMarkers
                    markers_source = "mMarkerList.mMarkers"

            # Path 2: mHUDManager.maMarkers directly
            if markers is None and hasattr(hud_mgr, 'maMarkers'):
                markers = hud_mgr.maMarkers
                markers_source = "mHUDManager.maMarkers"

            # Path 3: Try mPlayerHUD.maMarkers (original path)
            if markers is None and hasattr(hud_mgr, 'mPlayerHUD'):
                player_hud = hud_mgr.mPlayerHUD
                log_flush(f"  _scan_hud_markers: mPlayerHUD = {type(player_hud).__name__}")
                phud_attrs = [a for a in dir(player_hud) if not a.startswith('_')]
                log_flush(f"  _scan_hud_markers: mPlayerHUD attrs: {phud_attrs[:25]}")
                if hasattr(player_hud, 'maMarkers'):
                    markers = player_hud.maMarkers
                    markers_source = "mPlayerHUD.maMarkers"

            # Path 4: Check for any attribute containing 'marker' (case insensitive)
            if markers is None:
                for attr in hud_mgr_attrs:
                    if 'marker' in attr.lower():
                        log_flush(f"  _scan_hud_markers: Found marker-related attr: {attr}")
                        try:
                            potential = getattr(hud_mgr, attr)
                            log_flush(f"  _scan_hud_markers: {attr} = {type(potential).__name__}")
                            pot_attrs = [a for a in dir(potential) if not a.startswith('_')]
                            log_flush(f"  _scan_hud_markers: {attr} has: {pot_attrs[:20]}")
                        except Exception as e:
                            log_flush(f"  _scan_hud_markers: Error accessing {attr}: {e}")

            # Path 5: RAW MEMORY ACCESS - nmspy bindings are incomplete
            # Use ctypes to read markers directly from memory at known offsets
            if markers is None:
                log_flush("  _scan_hud_markers: nmspy bindings incomplete, trying RAW MEMORY access...")
                try:
                    from pymhf.core.memutils import get_addressof

                    # Get mPlayerHUD address
                    player_hud = hud_mgr.mPlayerHUD
                    player_hud_addr = get_addressof(player_hud)
                    log_flush(f"  _scan_hud_markers: mPlayerHUD address = 0x{player_hud_addr:X}")

                    # Known structure offsets (from game analysis):
                    # maMarkers array is at various possible offsets in cGcPlayerHUD
                    # cGcHUDMarker size is typically 0x1610 bytes
                    # mCustomName (cTkFixedString<127>) is at offset 0x48 within cGcMarkerPoint (mData)
                    # meBuildingClass is at offset 0x118 within cGcMarkerPoint
                    # mData (cGcMarkerPoint) is at offset 0x10 within cGcHUDMarker

                    MARKER_COUNT = 128
                    MARKER_SIZE = 0x1610  # Size of each cGcHUDMarker
                    MARKER_DATA_OFFSET = 0x10  # mData within cGcHUDMarker
                    CUSTOM_NAME_OFFSET = 0x38  # mCustomName within cGcMarkerPoint
                    BUILDING_CLASS_OFFSET = 0x118  # meBuildingClass within cGcMarkerPoint
                    POSITION_OFFSET = 0x0  # mPosition (cTkPhysRelVec3) within cGcMarkerPoint

                    # Try different offsets for maMarkers array within cGcPlayerHUD
                    possible_marker_offsets = [0x20F50, 0x20000, 0x21000, 0x1F000, 0x22000, 0x18000, 0x10000]
                    markers_with_names = 0
                    player_bases = []  # Track discovered player bases

                    for marker_array_offset in possible_marker_offsets:
                        markers_base = player_hud_addr + marker_array_offset
                        log_flush(f"  _scan_hud_markers: Trying markers at offset 0x{marker_array_offset:X} (addr 0x{markers_base:X})")

                        found_named_markers = 0
                        for i in range(min(5, MARKER_COUNT)):  # Check first 5 markers as sample
                            try:
                                marker_addr = markers_base + (i * MARKER_SIZE)
                                marker_data_addr = marker_addr + MARKER_DATA_OFFSET
                                name_addr = marker_data_addr + CUSTOM_NAME_OFFSET
                                building_class_addr = marker_data_addr + BUILDING_CLASS_OFFSET

                                # Read custom name (first 32 chars)
                                name_bytes = ctypes.string_at(name_addr, 32)
                                name = name_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
                                name = ''.join(c for c in name if c.isprintable())

                                # Read building class
                                building_class = ctypes.c_uint32.from_address(building_class_addr).value

                                if name and len(name) >= 2 and building_class < 0x1000:  # Sanity check
                                    found_named_markers += 1
                                    log_flush(f"    [RAW SAMPLE {i}] Name='{name[:20]}' Class=0x{building_class:X}")

                            except Exception as me:
                                break  # Memory access error - wrong offset

                        if found_named_markers > 0:
                            log_flush(f"  _scan_hud_markers: Found markers at offset 0x{marker_array_offset:X}! Scanning all...")
                            markers_source = f"RAW@0x{marker_array_offset:X}"

                            # Full scan with this offset
                            for i in range(MARKER_COUNT):
                                try:
                                    marker_addr = markers_base + (i * MARKER_SIZE)
                                    marker_data_addr = marker_addr + MARKER_DATA_OFFSET
                                    name_addr = marker_data_addr + CUSTOM_NAME_OFFSET
                                    building_class_addr = marker_data_addr + BUILDING_CLASS_OFFSET

                                    name_bytes = ctypes.string_at(name_addr, 64)
                                    name = name_bytes.split(b'\x00')[0].decode('utf-8', errors='ignore').strip()
                                    name = ''.join(c for c in name if c.isprintable())

                                    if not name or len(name) < 2:
                                        continue

                                    building_class = ctypes.c_uint32.from_address(building_class_addr).value
                                    if building_class > 0x1000:  # Sanity check
                                        continue

                                    # Extract position (x, y, z floats)
                                    pos_addr = marker_data_addr + POSITION_OFFSET
                                    try:
                                        pos_x = ctypes.c_float.from_address(pos_addr).value
                                        pos_y = ctypes.c_float.from_address(pos_addr + 4).value
                                        pos_z = ctypes.c_float.from_address(pos_addr + 8).value
                                    except:
                                        pos_x, pos_y, pos_z = 0.0, 0.0, 0.0

                                    markers_with_names += 1
                                    log_flush(f"    [RAW {i}] Name='{name}' Class=0x{building_class:X} Pos=({pos_x:.0f}, {pos_y:.0f}, {pos_z:.0f})")

                                    # Check for network players by:
                                    # 1. Building class (0x1B-0x1F, 0x39, 0x3C)
                                    # 2. Name pattern: "<IMG>MODE<>" where MODE is CREATIVE, NORMAL, SURVIVAL, PERMADEATH
                                    is_network_player = False
                                    player_type = "unknown"
                                    display_name = name

                                    # Method 1: Check building class
                                    network_player_classes = [0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x39, 0x3C]
                                    class_names = {
                                        0x1B: "fireteam_onfoot", 0x1C: "fireteam_ship",
                                        0x1D: "player_onfoot", 0x1E: "player_ship",
                                        0x1F: "player_vehicle", 0x39: "network_player",
                                        0x3C: "marker_player",
                                    }

                                    # Method 2: Check for <IMG>MODE<> pattern (most reliable!)
                                    # Player names have format: "PlayerName, Title <IMG>CREATIVE<>"
                                    game_modes = ['CREATIVE', 'NORMAL', 'SURVIVAL', 'PERMADEATH', 'RELAXED']
                                    detected_mode = None
                                    for mode in game_modes:
                                        mode_tag = f'<IMG>{mode}<>'
                                        if mode_tag in name:
                                            is_network_player = True
                                            detected_mode = mode
                                            player_type = f"network_player_{mode.lower()}"
                                            # Extract clean player name (before the <IMG> tag)
                                            display_name = name.split('<IMG>')[0].strip()
                                            # Remove trailing comma if present
                                            if display_name.endswith(','):
                                                display_name = display_name[:-1].strip()
                                            log_flush(f"    *** NETWORK PLAYER DETECTED: '{display_name}' ({mode}) ***")
                                            break

                                    # Only add if detected as network player
                                    if is_network_player:
                                        player_info = {
                                            'name': display_name,
                                            'full_marker_name': name,
                                            'building_class': building_class,
                                            'player_type': player_type,
                                            'game_mode': detected_mode,
                                            'marker_index': i,
                                            'position': {'x': pos_x, 'y': pos_y, 'z': pos_z},
                                            'detected_at': datetime.now().isoformat(),
                                            'status': 'active',
                                            'detection_source': f'raw_memory_0x{marker_array_offset:X}',
                                        }
                                        network_players.append(player_info)

                                    # Check for player bases by name patterns
                                    # Bases typically have names like "XXX Base", "XXX Outpost", "XXX Colony", etc.
                                    # Also check for custom names that don't look like system-generated names
                                    base_keywords = ['Base', 'Outpost', 'Colony', 'Haven', 'Station', 'Hub', 'Camp', 'Home', 'Fort', 'Tower', 'Depot', 'Shelter']
                                    is_player_base = False

                                    # Skip UI markers and system markers
                                    skip_prefixes = ['UI_', 'FOOD_', 'PROD_', 'Silver ', 'Gold ', 'Copper ', 'Paraffinium', 'Pyrite', 'Dioxite', 'Phosphorus', 'Ammonia', 'Uranium']
                                    is_system_marker = any(name.startswith(prefix) for prefix in skip_prefixes)

                                    if not is_system_marker and not is_network_player:
                                        # Check if name contains base keywords
                                        for keyword in base_keywords:
                                            if keyword.lower() in name.lower():
                                                is_player_base = True
                                                break

                                        # Also detect bases with custom names (no spaces = likely procedural, spaces = likely player-named)
                                        # But exclude short names and compass directions
                                        if not is_player_base and ' ' in name and len(name) > 5:
                                            # Likely a player-named location
                                            compass_markers = ['NORTH', 'SOUTH', 'EAST', 'WEST']
                                            if not any(cm in name.upper() for cm in compass_markers):
                                                is_player_base = True

                                    if is_player_base:
                                        base_info = {
                                            'name': name,
                                            'building_class': building_class,
                                            'marker_index': i,
                                            'position': {'x': pos_x, 'y': pos_y, 'z': pos_z},
                                            'distance': (pos_x**2 + pos_y**2 + pos_z**2)**0.5,  # Distance from origin
                                            'detected_at': datetime.now().isoformat(),
                                        }
                                        player_bases.append(base_info)
                                        log_flush(f"    *** PLAYER BASE: '{name}' at ({pos_x:.0f}, {pos_y:.0f}, {pos_z:.0f}) ***")

                                except Exception:
                                    continue
                            break  # Found working offset

                    scan_time = time.time() - scan_start
                    log_flush(f"  _scan_hud_markers: RAW scan - {markers_with_names} markers, {len(network_players)} players, {len(player_bases)} bases ({scan_time:.3f}s)")

                    # Store bases in instance variable for UI access
                    self._discovered_bases = player_bases

                    return network_players

                except Exception as raw_err:
                    log_flush(f"  _scan_hud_markers: RAW MEMORY failed: {raw_err}")
                    return network_players

            log_flush(f"  _scan_hud_markers: Got markers via {markers_source}, type={type(markers).__name__}")
            markers_checked = 0
            markers_with_names = 0

            log_flush(f"  _scan_hud_markers: Scanning {len(markers)} HUD markers...")

            # Log first marker's structure to understand available fields (INFO level for visibility)
            if len(markers) > 0:
                try:
                    first_marker = markers[0]
                    first_data = first_marker.mData if hasattr(first_marker, 'mData') else None
                    if first_data:
                        marker_fields = [f for f in dir(first_data) if not f.startswith('_')]
                        log_flush(f"  [STRUCT] cGcMarkerPoint has {len(marker_fields)} fields: {marker_fields[:15]}...")
                    else:
                        log_flush(f"  [STRUCT] WARNING: first_marker.mData is None!")
                except Exception as fe:
                    log_flush(f"  [STRUCT] ERROR inspecting marker: {fe}")

            # Log first 5 markers (sample) to see what data is available
            sample_logged = 0

            for i, hud_marker in enumerate(markers):
                try:
                    # Each cGcHUDMarker has mData (cGcMarkerPoint) at offset 0x10
                    marker_data = hud_marker.mData

                    # Extract building class FIRST - try multiple potential field names
                    building_class = 0
                    building_class_source = "none"
                    try:
                        if hasattr(marker_data, 'meBuildingClass'):
                            building_class = int(marker_data.meBuildingClass)
                            building_class_source = "meBuildingClass"
                        elif hasattr(marker_data, 'meScannerIconType'):
                            building_class = int(marker_data.meScannerIconType)
                            building_class_source = "meScannerIconType"
                        elif hasattr(marker_data, 'meIcon'):
                            building_class = int(marker_data.meIcon)
                            building_class_source = "meIcon"
                    except Exception as bc_err:
                        building_class_source = f"error:{bc_err}"

                    # Extract custom name (network players have their username here)
                    name = ""
                    try:
                        name_val = marker_data.mCustomName
                        if name_val:
                            name = str(name_val).strip()
                            # Clean the name - remove null terminators and garbage
                            name = name.split('\x00')[0].strip()
                            # Filter out non-printable characters
                            name = ''.join(c for c in name if c.isprintable())
                    except:
                        pass

                    # Log sample of markers (first 5 with non-zero building class)
                    if sample_logged < 5 and building_class != 0:
                        log_flush(f"    [SAMPLE MARKER {i}] Class=0x{building_class:X} Name='{name[:30] if name else '(empty)'}' via {building_class_source}")
                        sample_logged += 1

                    # Skip empty markers
                    if not name or len(name) < 2:
                        continue

                    markers_with_names += 1

                    # Log ALL markers with names (INFO level so it always shows)
                    log_flush(f"    [MARKER {i}] Name='{name}' Class=0x{building_class:X} ({building_class}) via {building_class_source}")

                    # Extract subtitle
                    subtitle = ""
                    try:
                        sub_val = marker_data.mCustomSubtitle
                        if sub_val:
                            subtitle = str(sub_val).strip()
                            subtitle = subtitle.split('\x00')[0].strip()
                            subtitle = ''.join(c for c in subtitle if c.isprintable())
                    except:
                        pass

                    # Extract position
                    position = {'x': 0.0, 'y': 0.0, 'z': 0.0}
                    try:
                        pos = marker_data.mPosition
                        if hasattr(pos, 'x'):
                            position['x'] = float(pos.x)
                        if hasattr(pos, 'y'):
                            position['y'] = float(pos.y)
                        if hasattr(pos, 'z'):
                            position['z'] = float(pos.z)
                    except:
                        pass

                    # Check if this looks like a network player marker
                    # Network player markers have custom names and certain building classes
                    # We also check for markers that have player-like names
                    is_network_player = False
                    player_type = "unknown"

                    # Check building class values that indicate network players
                    # From cGcScannerIconTypesEnum:
                    # 0x1B = NetworkPlayerFireTeam, 0x1C = NetworkPlayerFireTeamShip
                    # 0x1D = NetworkPlayer, 0x1E = NetworkPlayerShip, 0x1F = NetworkPlayerVehicle
                    network_player_classes = [0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x39]

                    if building_class in network_player_classes:
                        is_network_player = True
                        class_names = {
                            0x1B: "fireteam_onfoot",
                            0x1C: "fireteam_ship",
                            0x1D: "player_onfoot",
                            0x1E: "player_ship",
                            0x1F: "player_vehicle",
                            0x39: "network_player",
                        }
                        player_type = class_names.get(building_class, f"class_{building_class}")

                    # Also check if marker has a name that looks like a player username
                    # (has no spaces at start, reasonable length, alphanumeric-ish)
                    if not is_network_player and name:
                        # Heuristic: player names are typically 3-20 chars, mostly alphanumeric
                        if 3 <= len(name) <= 25:
                            # Check if it looks like a username rather than a location name
                            # Location names often have spaces, player names typically don't
                            alpha_ratio = sum(c.isalnum() for c in name) / len(name)
                            if alpha_ratio > 0.7 and not name.startswith("Signal") and not name.startswith("Base"):
                                # This might be a player - mark it for review
                                is_network_player = True
                                player_type = f"possible_player_class_{building_class}"

                    if is_network_player:
                        player_info = {
                            'name': name,
                            'subtitle': subtitle,
                            'position': position,
                            'building_class': building_class,
                            'player_type': player_type,
                            'marker_index': i,
                            'detected_at': datetime.now().isoformat(),
                            'status': 'active',
                            'detection_source': 'hud_marker_scan',
                        }
                        network_players.append(player_info)
                        log_flush(f"  Found network player: {name} (class={building_class}, type={player_type})")

                    markers_checked += 1

                except Exception as e:
                    continue

            scan_time = time.time() - scan_start
            log_flush(f"  _scan_hud_markers: Checked {markers_checked} markers, found {markers_with_names} with names, {len(network_players)} network players ({scan_time:.3f}s)")

        except Exception as e:
            log_flush(f"  _scan_hud_markers failed: {e}", "error")
            log_flush(f"  Traceback: {traceback.format_exc()}", "debug")

        return network_players

    def _probe_base_array_offsets(self, player_state_addr: int, safe_mem) -> list:
        """
        Probe different offsets in cGcPlayerStateData to find PersistentPlayerBases.

        The offset 0x7CC18 may vary by game version. This function scans through
        likely offset ranges looking for structures that look like base arrays.

        A valid base array should have:
        - A data pointer (non-zero, readable)
        - A size field (1-100 typical for player bases)
        - Base entries with readable name strings

        Returns:
            List of potential offsets with their details
        """
        potential_offsets = []

        # Offsets to try - COMPREHENSIVE SCAN for any game version
        # Build a list of offsets to probe across the entire structure
        OFFSETS_TO_TRY = []

        # Priority 1: First 4KB very thoroughly (every 8 bytes)
        # Common place for important arrays
        for offset in range(0x0, 0x1000, 0x8):
            OFFSETS_TO_TRY.append(offset)

        # Priority 2: 4KB-64KB (every 24 bytes)
        for offset in range(0x1000, 0x10000, 0x18):
            OFFSETS_TO_TRY.append(offset)

        # Priority 3: 64KB-512KB sparse (every 256 bytes)
        for offset in range(0x10000, 0x80000, 0x100):
            OFFSETS_TO_TRY.append(offset)

        # Priority 4: Original research areas (very thorough)
        for offset in range(0x7C000, 0x82000, 0x8):
            OFFSETS_TO_TRY.append(offset)

        # Priority 5: Areas around common offsets
        for base in [0x100, 0x200, 0x400, 0x800, 0x1000, 0x2000, 0x4000, 0x8000]:
            for delta in range(-0x20, 0x28, 0x8):
                OFFSETS_TO_TRY.append(base + delta)

        # Remove duplicates and sort
        OFFSETS_TO_TRY = sorted(set(OFFSETS_TO_TRY))

        log_flush(f"  _probe_base_array: WIDE SCAN - Probing {len(OFFSETS_TO_TRY)} offsets for base array...")

        for offset in OFFSETS_TO_TRY:
            try:
                array_addr = player_state_addr + offset

                # Check if readable
                if not safe_mem.is_readable(array_addr, 16):
                    continue

                # Read as dynamic array structure (ptr at 0x0, size at 0x8)
                data_ptr = safe_mem.read_uint64(array_addr, 0)
                array_size = safe_mem.read_uint32(array_addr + 0x8, 0)

                # Filter: must have valid pointer and reasonable size
                if data_ptr == 0 or data_ptr < 0x10000:
                    continue
                if array_size == 0 or array_size > 500:
                    continue

                # Check if data pointer is readable
                if not safe_mem.is_readable(data_ptr, 0x100):
                    continue

                # Try to read first entry's name field (at various offsets)
                # Base name could be at many places - scan comprehensively
                name_found = False
                name_value = ""
                name_offset_found = 0

                # Try many offsets where a base name might be stored
                NAME_OFFSETS_TO_TRY = [
                    0x0, 0x8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40,
                    0x48, 0x50, 0x58, 0x60, 0x68, 0x70, 0x78, 0x80,
                    0x100, 0x108, 0x110, 0x118, 0x120,
                    0x200, 0x208, 0x210, 0x218, 0x220,
                    0x300, 0x308, 0x400, 0x408, 0x500, 0x508,
                ]
                for name_offset in NAME_OFFSETS_TO_TRY:
                    test_name = safe_mem.read_string(data_ptr + name_offset, 40, "")
                    # Look for base-like names (contain common words)
                    if test_name and len(test_name) >= 3:
                        # Filter out obvious non-names
                        if not test_name.startswith('UI_') and not test_name.startswith('PROD_'):
                            name_found = True
                            name_value = test_name
                            name_offset_found = name_offset
                            break

                # Log this potential match
                log_flush(f"    [PROBE] Offset 0x{offset:X}: ptr=0x{data_ptr:X}, size={array_size}, name@0x{name_offset_found:X}='{name_value[:30] if name_value else 'N/A'}'")

                potential_offsets.append({
                    'offset': offset,
                    'data_ptr': data_ptr,
                    'array_size': array_size,
                    'name_found': name_found,
                    'sample_name': name_value,
                    'name_offset': name_offset_found,
                })

            except Exception as e:
                continue

        log_flush(f"  _probe_base_array: Found {len(potential_offsets)} potential offsets")
        return potential_offsets

    def _probe_game_state_for_bases(self, safe_mem) -> list:
        """
        Probe game_state (cGcGameState) for base arrays.

        The actual persistent bases may be stored in game_state rather than
        player_state. This function scans game_state for arrays containing
        base-like structures.

        Returns:
            List of potential base array locations in game_state
        """
        potential_offsets = []

        try:
            game_state = gameData.game_state
            if not game_state:
                log_flush("  _probe_game_state: No game_state available")
                return potential_offsets

            game_state_addr = get_addressof(game_state)
            log_flush(f"  _probe_game_state: game_state @ 0x{game_state_addr:X}")

            if not safe_mem.is_readable(game_state_addr, 8):
                log_flush("  _probe_game_state: game_state address not readable")
                return potential_offsets

            # Build comprehensive offset list for game_state
            OFFSETS_TO_TRY = []

            # Priority 1: First 8KB every 8 bytes
            for offset in range(0x0, 0x2000, 0x8):
                OFFSETS_TO_TRY.append(offset)

            # Priority 2: 8KB-128KB every 24 bytes
            for offset in range(0x2000, 0x20000, 0x18):
                OFFSETS_TO_TRY.append(offset)

            # Priority 3: 128KB-1MB sparse (every 256 bytes)
            for offset in range(0x20000, 0x100000, 0x100):
                OFFSETS_TO_TRY.append(offset)

            # Remove duplicates and sort
            OFFSETS_TO_TRY = sorted(set(OFFSETS_TO_TRY))

            log_flush(f"  _probe_game_state: Probing {len(OFFSETS_TO_TRY)} offsets in game_state...")

            for offset in OFFSETS_TO_TRY:
                try:
                    array_addr = game_state_addr + offset

                    if not safe_mem.is_readable(array_addr, 16):
                        continue

                    # Read as dynamic array structure
                    data_ptr = safe_mem.read_uint64(array_addr, 0)
                    array_size = safe_mem.read_uint32(array_addr + 0x8, 0)

                    # Filter: valid pointer and reasonable size for bases
                    if data_ptr == 0 or data_ptr < 0x10000:
                        continue
                    if array_size == 0 or array_size > 200:
                        continue

                    if not safe_mem.is_readable(data_ptr, 0x200):
                        continue

                    # Look for base-like structure signatures
                    # Bases have names, positions, and galactic addresses
                    name_found = False
                    name_value = ""
                    name_offset_found = 0

                    # Base names are typically at offset 0x208 or similar
                    NAME_OFFSETS = [
                        0x0, 0x8, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40,
                        0x100, 0x108, 0x200, 0x208, 0x210, 0x300, 0x400, 0x500
                    ]

                    for name_offset in NAME_OFFSETS:
                        test_name = safe_mem.read_string(data_ptr + name_offset, 50, "")
                        # Look for base-like names (contain words like Haven, Base, Outpost, etc.)
                        if test_name and len(test_name) >= 4:
                            # Filter out obvious non-base names
                            lower_name = test_name.lower()
                            if any(kw in lower_name for kw in ['base', 'haven', 'outpost', 'colony', 'pit', 'showcase']):
                                name_found = True
                                name_value = test_name
                                name_offset_found = name_offset
                                break
                            # Also accept if it doesn't start with common game prefixes
                            if not any(test_name.startswith(p) for p in ['UI_', 'PROD_', 'FUEL', 'ENERGY', 'SHIP_', 'MODELS/']):
                                name_found = True
                                name_value = test_name
                                name_offset_found = name_offset

                    if name_found:
                        log_flush(f"    [GAME_STATE PROBE] Offset 0x{offset:X}: ptr=0x{data_ptr:X}, size={array_size}, name@0x{name_offset_found:X}='{name_value[:40]}'")
                        potential_offsets.append({
                            'source': 'game_state',
                            'offset': offset,
                            'data_ptr': data_ptr,
                            'array_size': array_size,
                            'name_found': name_found,
                            'sample_name': name_value,
                            'name_offset': name_offset_found,
                        })

                except Exception:
                    continue

            log_flush(f"  _probe_game_state: Found {len(potential_offsets)} potential base arrays in game_state")

        except Exception as e:
            log_flush(f"  _probe_game_state failed: {e}", "error")

        return potential_offsets

    def _explore_base_building_manager(self, safe_mem) -> list:
        """
        Explore mBaseBuildingManager for base data.

        The BaseBuildingManager may contain references to all built bases
        in the current session.

        Returns:
            List of base locations found in BaseBuildingManager
        """
        potential_bases = []

        try:
            app = gameData.GcApplication
            if not app or not hasattr(app, 'mpData') or not app.mpData:
                log_flush("  _explore_bbm: No GcApplication.mpData available")
                return potential_bases

            data = app.mpData.contents

            if not hasattr(data, 'mBaseBuildingManager'):
                log_flush("  _explore_bbm: No mBaseBuildingManager attribute")
                return potential_bases

            bbm = data.mBaseBuildingManager
            if not bbm:
                log_flush("  _explore_bbm: mBaseBuildingManager is None")
                return potential_bases

            bbm_addr = get_addressof(bbm)
            log_flush(f"  _explore_bbm: mBaseBuildingManager @ 0x{bbm_addr:X}")

            if not safe_mem.is_readable(bbm_addr, 8):
                log_flush("  _explore_bbm: BaseBuildingManager not readable")
                return potential_bases

            # List all attributes of BaseBuildingManager
            bbm_attrs = [a for a in dir(bbm) if not a.startswith('_')]
            log_flush(f"  _explore_bbm: BaseBuildingManager has {len(bbm_attrs)} attrs")

            # Look for base-related attributes
            base_attrs = [a for a in bbm_attrs if any(kw in a.lower() for kw in
                         ['base', 'persistent', 'building', 'object', 'array', 'list', 'player'])]
            log_flush(f"  _explore_bbm: Base-related attrs: {base_attrs[:20]}")

            # Probe memory around BaseBuildingManager for arrays
            OFFSETS_TO_TRY = list(range(0x0, 0x1000, 0x8))

            for offset in OFFSETS_TO_TRY:
                try:
                    addr = bbm_addr + offset
                    if not safe_mem.is_readable(addr, 16):
                        continue

                    data_ptr = safe_mem.read_uint64(addr, 0)
                    array_size = safe_mem.read_uint32(addr + 0x8, 0)

                    if data_ptr == 0 or data_ptr < 0x10000:
                        continue
                    if array_size == 0 or array_size > 200:
                        continue

                    if not safe_mem.is_readable(data_ptr, 0x100):
                        continue

                    # Look for base names
                    for name_offset in [0x0, 0x8, 0x10, 0x100, 0x200, 0x208]:
                        test_name = safe_mem.read_string(data_ptr + name_offset, 50, "")
                        if test_name and len(test_name) >= 4:
                            lower_name = test_name.lower()
                            if any(kw in lower_name for kw in ['base', 'haven', 'outpost', 'colony']):
                                log_flush(f"    [BBM PROBE] Offset 0x{offset:X}: ptr=0x{data_ptr:X}, size={array_size}, name='{test_name[:40]}'")
                                potential_bases.append({
                                    'source': 'base_building_manager',
                                    'offset': offset,
                                    'data_ptr': data_ptr,
                                    'array_size': array_size,
                                    'sample_name': test_name,
                                })
                                break

                except Exception:
                    continue

            log_flush(f"  _explore_bbm: Found {len(potential_bases)} potential base refs in BaseBuildingManager")

        except Exception as e:
            log_flush(f"  _explore_bbm failed: {e}", "error")

        return potential_bases

    def _search_for_known_base_names(self, known_base_names: list, safe_mem) -> list:
        """
        Search memory for specific base names found by HUD markers.

        This helps locate the actual base storage by finding where known
        base name strings are stored in memory.

        Args:
            known_base_names: List of base names from HUD marker scan
            safe_mem: SafeMemoryReader instance

        Returns:
            List of memory locations containing base names
        """
        found_locations = []

        if not known_base_names:
            log_flush("  _search_base_names: No known base names to search for")
            return found_locations

        log_flush(f"  _search_base_names: Searching for {len(known_base_names)} known base names...")

        # Get key memory regions to search
        search_regions = []

        try:
            player_state = gameData.player_state
            if player_state:
                ps_addr = get_addressof(player_state)
                search_regions.append(('player_state', ps_addr, 0x100000))

            game_state = gameData.game_state
            if game_state:
                gs_addr = get_addressof(game_state)
                search_regions.append(('game_state', gs_addr, 0x100000))

            app = gameData.GcApplication
            if app and hasattr(app, 'mpData') and app.mpData:
                data = app.mpData.contents
                if hasattr(data, 'mBaseBuildingManager'):
                    bbm = data.mBaseBuildingManager
                    if bbm:
                        bbm_addr = get_addressof(bbm)
                        search_regions.append(('base_building_manager', bbm_addr, 0x10000))

        except Exception as e:
            log_flush(f"  _search_base_names: Error getting regions: {e}", "error")

        # Search for each known base name
        for base_name in known_base_names[:5]:  # Limit to first 5 to avoid taking too long
            if len(base_name) < 5:
                continue

            log_flush(f"  _search_base_names: Looking for '{base_name[:30]}'...")

            for region_name, base_addr, size in search_regions:
                # Sample every 8 bytes in the region
                for offset in range(0, min(size, 0x50000), 0x8):
                    addr = base_addr + offset
                    try:
                        if not safe_mem.is_readable(addr, len(base_name)):
                            continue

                        test_str = safe_mem.read_string(addr, len(base_name) + 1, "")
                        if test_str == base_name:
                            log_flush(f"    [FOUND] '{base_name[:30]}' at {region_name} + 0x{offset:X} (addr 0x{addr:X})")
                            found_locations.append({
                                'name': base_name,
                                'region': region_name,
                                'offset': offset,
                                'address': addr,
                            })
                            break  # Found in this region, move to next

                    except Exception:
                        continue

        log_flush(f"  _search_base_names: Found {len(found_locations)} base name locations")
        return found_locations

    def _scan_persistent_player_bases(self) -> list:
        """
        Scan the ACTUAL persistent player bases from cGcPlayerStateData.

        This reads the real base data stored in the game, not just the HUD markers.
        HUD markers are visual only - this accesses the actual base structures.

        Uses SafeMemoryReader to validate memory before access (prevents crashes).
        Now includes offset probing to find the correct location across game versions.

        Structure offsets (from game analysis):
        - PersistentPlayerBases array: offset varies by version (probed at runtime)
        - Each cGcPersistentBase is approximately 0x800 bytes
        - Key fields in cGcPersistentBase:
            - mPosition: offset 0x10 (cTkPhysRelVec3 - 3 floats)
            - mGalacticAddress: offset 0x50 (cGcUniverseAddressData)
            - mName: offset 0x208 (cTkFixedString0x40 - 64 char string)
            - mObjects: offset 0x40 (array of base building objects)

        Returns:
            List of dictionaries with actual base data
        """
        from datetime import datetime

        bases = []
        scan_start = time.time()

        # Get safe memory reader
        safe_mem = get_safe_reader()

        try:
            log_flush("  _scan_persistent_bases: Starting DEEP base scan (v3.8.4)...")

            # Collect all potential base array offsets from multiple sources
            all_potential_offsets = []

            # ========================================
            # SOURCE 1: Probe player_state
            # ========================================
            player_state = gameData.player_state
            if player_state:
                player_state_addr = get_addressof(player_state)
                log_flush(f"  _scan_persistent_bases: player_state @ 0x{player_state_addr:X}")

                if safe_mem.is_readable(player_state_addr, 8):
                    player_state_offsets = self._probe_base_array_offsets(player_state_addr, safe_mem)
                    for po in player_state_offsets:
                        po['source'] = 'player_state'
                    all_potential_offsets.extend(player_state_offsets)
                    log_flush(f"  _scan_persistent_bases: player_state probe found {len(player_state_offsets)} candidates")
            else:
                log_flush("  _scan_persistent_bases: No player_state available")

            # ========================================
            # SOURCE 2: Probe game_state (NEW in v3.8.4)
            # ========================================
            game_state_offsets = self._probe_game_state_for_bases(safe_mem)
            all_potential_offsets.extend(game_state_offsets)
            log_flush(f"  _scan_persistent_bases: game_state probe found {len(game_state_offsets)} candidates")

            # ========================================
            # SOURCE 3: Explore BaseBuildingManager (NEW in v3.8.4)
            # ========================================
            bbm_bases = self._explore_base_building_manager(safe_mem)
            all_potential_offsets.extend(bbm_bases)
            log_flush(f"  _scan_persistent_bases: BaseBuildingManager probe found {len(bbm_bases)} candidates")

            # ========================================
            # SOURCE 4: Search for known base names (NEW in v3.8.4)
            # ========================================
            known_base_names = [b.get('name', '') for b in self._discovered_bases if b.get('name')]
            if known_base_names:
                name_locations = self._search_for_known_base_names(known_base_names, safe_mem)
                log_flush(f"  _scan_persistent_bases: Base name search found {len(name_locations)} locations")

            log_flush(f"  _scan_persistent_bases: TOTAL candidates from all sources: {len(all_potential_offsets)}")

            # Use all_potential_offsets instead of just player_state
            potential_offsets = all_potential_offsets

            # Use the best match - prioritize by quality
            # Priority 1: game_state or BBM with base-like names
            # Priority 2: Any source with base-like names
            # Priority 3: Any match with any name
            # Priority 4: Fallback to first match

            best_match = None

            # Priority 1: game_state or base_building_manager with base-like names
            for match in potential_offsets:
                if match.get('source') in ['game_state', 'base_building_manager']:
                    sample = match.get('sample_name', '').lower()
                    if any(kw in sample for kw in ['base', 'haven', 'outpost', 'colony', 'pit', 'showcase']):
                        best_match = match
                        log_flush(f"  _scan_persistent_bases: BEST MATCH from {match.get('source')} with base name '{match.get('sample_name', '')[:30]}'")
                        break

            # Priority 2: Any source with base-like names
            if not best_match:
                for match in potential_offsets:
                    sample = match.get('sample_name', '').lower()
                    if any(kw in sample for kw in ['base', 'haven', 'outpost', 'colony', 'pit', 'showcase']):
                        best_match = match
                        log_flush(f"  _scan_persistent_bases: Found base-like name from {match.get('source', 'unknown')}: '{match.get('sample_name', '')[:30]}'")
                        break

            # Priority 3: Any match with a name (not inventory)
            if not best_match:
                for match in potential_offsets:
                    if match.get('name_found'):
                        sample = match.get('sample_name', '')
                        # Skip obvious inventory items
                        if not any(sample.startswith(p) for p in ['FUEL', 'ENERGY', 'SHIP_', 'STRONGLASER', 'ASTEROID', 'HYPERDRIVE', 'LAUNCHER']):
                            best_match = match
                            log_flush(f"  _scan_persistent_bases: Using match with name: '{sample[:30]}'")
                            break

            # Priority 4: Fallback to first match
            if not best_match and potential_offsets:
                best_match = potential_offsets[0]
                log_flush(f"  _scan_persistent_bases: Fallback to first match (may be inventory data)")

            if not best_match:
                log_flush("  _scan_persistent_bases: No valid base array offset found in any source")
                return bases

            best_offset = best_match['offset']
            log_flush(f"  _scan_persistent_bases: Using {best_match.get('source', 'unknown')} offset 0x{best_offset:X} (size={best_match['array_size']})")

            # Now scan using the discovered offset
            BASE_STRUCT_SIZE = 0x800  # Approximate size of each base entry
            MAX_BASES = 50  # Max bases to scan

            # Fields within cGcPersistentBase - use discovered offsets if available
            POSITION_OFFSET = 0x10  # mPosition (cTkPhysRelVec3)
            GALACTIC_ADDR_OFFSET = 0x50  # mGalacticAddress
            # Use discovered name offset if available, otherwise default to 0x208
            NAME_OFFSET = best_match.get('name_offset', 0x208)
            log_flush(f"  _scan_persistent_bases: Using name offset 0x{NAME_OFFSET:X}")

            data_ptr = best_match['data_ptr']
            array_size = best_match['array_size']

            if data_ptr == 0 or array_size == 0 or array_size > 1000:  # Sanity check
                log_flush("  _scan_persistent_bases: Empty, null, or invalid array")
                return bases

            # Validate data pointer is readable
            if not safe_mem.is_readable(data_ptr, BASE_STRUCT_SIZE):
                log_flush("  _scan_persistent_bases: Array data pointer not readable")
                return bases

            # Log the source and data pointer for debugging/modification research
            log_flush(f"  _scan_persistent_bases: SOURCE={best_match.get('source', 'unknown')}")
            log_flush(f"  _scan_persistent_bases: DATA_PTR=0x{data_ptr:X}")
            log_flush(f"  _scan_persistent_bases: ARRAY_SIZE={array_size}")

            # Limit to reasonable number
            count_to_scan = min(array_size, MAX_BASES)
            log_flush(f"  _scan_persistent_bases: Scanning {count_to_scan} bases safely...")

            for i in range(count_to_scan):
                try:
                    base_addr = data_ptr + (i * BASE_STRUCT_SIZE)

                    # Validate this base entry is readable
                    if not safe_mem.is_readable(base_addr, 0x220):
                        log_flush(f"    [BASE {i}] Not readable - skipping", "debug")
                        continue

                    # Read position (3 floats) safely
                    pos_addr = base_addr + POSITION_OFFSET
                    pos_x = safe_mem.read_float(pos_addr, 0.0)
                    pos_y = safe_mem.read_float(pos_addr + 4, 0.0)
                    pos_z = safe_mem.read_float(pos_addr + 8, 0.0)

                    # Skip empty bases (position at origin)
                    if abs(pos_x) < 0.1 and abs(pos_y) < 0.1 and abs(pos_z) < 0.1:
                        continue

                    # Read name - try discovered offset first, then try multiple offsets
                    name = ""
                    name_addr = base_addr + NAME_OFFSET
                    name = safe_mem.read_string(name_addr, 64, "")

                    # If no name found at expected offset, try scanning for it
                    if not name or name.startswith('UI_') or name.startswith('PROD_'):
                        for try_offset in [0x0, 0x8, 0x10, 0x100, 0x200, 0x208, 0x210, 0x300]:
                            test_name = safe_mem.read_string(base_addr + try_offset, 64, "")
                            if test_name and len(test_name) >= 3:
                                if not test_name.startswith('UI_') and not test_name.startswith('PROD_'):
                                    name = test_name
                                    break

                    if not name:
                        name = f"Base {i}"

                    # Read galactic address safely
                    ga_addr = base_addr + GALACTIC_ADDR_OFFSET
                    voxel_x = safe_mem.read_int16(ga_addr, 0)
                    voxel_y = safe_mem.read_int16(ga_addr + 2, 0)
                    voxel_z = safe_mem.read_int16(ga_addr + 4, 0)
                    system_idx = safe_mem.read_uint16(ga_addr + 6, 0)
                    planet_idx = safe_mem.read_uint16(ga_addr + 8, 0)

                    # Calculate glyph code
                    glyph_code = self._coords_to_glyphs(planet_idx, system_idx, voxel_x, voxel_y, voxel_z)

                    base_info = {
                        'index': i,
                        'name': name,
                        'address': f"0x{base_addr:X}",
                        'position': {'x': pos_x, 'y': pos_y, 'z': pos_z},
                        'galactic_address': {
                            'voxel_x': voxel_x,
                            'voxel_y': voxel_y,
                            'voxel_z': voxel_z,
                            'system_index': system_idx,
                            'planet_index': planet_idx,
                        },
                        'glyph_code': glyph_code,
                        'detected_at': datetime.now().isoformat(),
                        'source': best_match.get('source', 'persistent_base_data'),
                        'data_source_offset': f"0x{best_offset:X}",
                    }
                    bases.append(base_info)
                    log_flush(f"    [ACTUAL BASE {i}] '{name}' @ ({pos_x:.0f}, {pos_y:.0f}, {pos_z:.0f}) Glyphs: {glyph_code} [src={best_match.get('source', 'unknown')}]")

                except Exception as base_err:
                    log_flush(f"    [BASE {i}] Error: {base_err}", "debug")
                    continue

            scan_time = time.time() - scan_start
            log_flush(f"  _scan_persistent_bases: Found {len(bases)} actual bases ({scan_time:.3f}s)")

        except Exception as e:
            log_flush(f"  _scan_persistent_bases failed: {e}", "error")
            import traceback
            log_flush(f"  Traceback: {traceback.format_exc()}", "debug")

        return bases

    def _scan_network_player_state(self) -> list:
        """
        Scan for network player state data from the multiplayer/network manager.

        Network players have their state stored in various locations:
        1. cGcNetworkManager - manages all network connections
        2. cGcLobbyManager - lobby and session info
        3. Network player array in app data

        Uses SafeMemoryReader to validate memory before access (prevents crashes).

        This function attempts to access the actual player state data for
        other players in the session, not just HUD markers.

        Returns:
            List of dictionaries with network player state data
        """
        from datetime import datetime

        players = []
        scan_start = time.time()

        # Get safe memory reader
        safe_mem = get_safe_reader()

        try:
            log_flush("  _scan_network_player_state: Starting SAFE network player state scan...")

            app = gameData.GcApplication
            if not app:
                log_flush("  _scan_network_player_state: No GcApplication available")
                return players

            app_addr = get_addressof(app)
            log_flush(f"  _scan_network_player_state: GcApplication @ 0x{app_addr:X}")

            # Validate app address
            if not safe_mem.is_readable(app_addr, 8):
                log_flush("  _scan_network_player_state: GcApplication address not readable")
                return players

            # Check for mpData which contains various managers
            if not hasattr(app, 'mpData') or not app.mpData:
                log_flush("  _scan_network_player_state: No mpData available")
                return players

            try:
                app_data = app.mpData.contents
                log_flush(f"  _scan_network_player_state: mpData type = {type(app_data).__name__}")
            except Exception as e:
                log_flush(f"  _scan_network_player_state: Error accessing mpData.contents: {e}")
                return players

            # List available attributes to find network-related managers
            try:
                data_attrs = [a for a in dir(app_data) if not a.startswith('_')]
                network_attrs = [a for a in data_attrs if 'network' in a.lower() or 'lobby' in a.lower() or 'player' in a.lower() or 'multi' in a.lower()]
                log_flush(f"  _scan_network_player_state: Network-related attrs: {network_attrs}")
            except Exception as e:
                log_flush(f"  _scan_network_player_state: Error listing attrs: {e}")
                return players

            # Try to access network manager
            network_mgr = None
            network_mgr_addr = 0

            for attr_name in ['mNetworkManager', 'mpNetworkManager', 'mNetwork', 'mLobbyManager', 'mpLobbyManager']:
                if hasattr(app_data, attr_name):
                    try:
                        mgr = getattr(app_data, attr_name)
                        if mgr:
                            network_mgr = mgr
                            network_mgr_addr = get_addressof(mgr)
                            if safe_mem.is_readable(network_mgr_addr, 8):
                                log_flush(f"  _scan_network_player_state: Found {attr_name} @ 0x{network_mgr_addr:X}")
                                break
                            else:
                                log_flush(f"  _scan_network_player_state: {attr_name} not readable")
                                network_mgr = None
                    except Exception as e:
                        log_flush(f"  _scan_network_player_state: Error accessing {attr_name}: {e}")

            if network_mgr:
                # List network manager attributes
                try:
                    mgr_attrs = [a for a in dir(network_mgr) if not a.startswith('_')]
                    log_flush(f"  _scan_network_player_state: Manager attrs: {mgr_attrs[:30]}")
                except Exception as e:
                    log_flush(f"  _scan_network_player_state: Error listing manager attrs: {e}")
                    mgr_attrs = []

                # Look for player arrays or lists
                for attr_name in mgr_attrs:
                    if 'player' in attr_name.lower() or 'member' in attr_name.lower() or 'client' in attr_name.lower():
                        try:
                            player_data = getattr(network_mgr, attr_name)
                            log_flush(f"    Checking {attr_name}: {type(player_data).__name__}")

                            if hasattr(player_data, '__iter__') and not isinstance(player_data, (str, bytes)):
                                for idx, p in enumerate(player_data):
                                    if idx >= 16:  # Limit
                                        break
                                    player_info = self._extract_network_player_info(p, idx)
                                    if player_info:
                                        players.append(player_info)
                            elif player_data:
                                player_info = self._extract_network_player_info(player_data, 0)
                                if player_info:
                                    players.append(player_info)

                        except Exception as e:
                            log_flush(f"    Error reading {attr_name}: {e}", "debug")

            # Also try SAFE raw memory scan for network player array
            # Known offsets may vary by game version
            if not players:
                log_flush("  _scan_network_player_state: Trying SAFE raw memory scan for player array...")
                try:
                    # Try scanning at known experimental offsets in GcApplicationData
                    app_data_addr = get_addressof(app_data)

                    # Validate app_data_addr is readable
                    if not safe_mem.is_readable(app_data_addr, 0x100):
                        log_flush("  _scan_network_player_state: app_data address not readable")
                    else:
                        # Experimental offsets where network player array might be
                        NETWORK_PLAYER_OFFSETS = [0x1F0, 0x200, 0x210, 0x220, 0x1000, 0x1100]
                        PLAYER_STRUCT_SIZE = 0x1A0  # Approximate size of network player struct

                        for offset in NETWORK_PLAYER_OFFSETS:
                            try:
                                array_addr = app_data_addr + offset

                                # Validate array header is readable
                                if not safe_mem.is_readable(array_addr, 16):
                                    continue

                                # Read array header safely
                                data_ptr = safe_mem.read_uint64(array_addr, 0)
                                array_size = safe_mem.read_uint32(array_addr + 8, 0)

                                if 0 < array_size < 100 and data_ptr > 0x10000:
                                    # Validate data pointer
                                    if not safe_mem.is_readable(data_ptr, PLAYER_STRUCT_SIZE):
                                        continue

                                    log_flush(f"    Potential player array at offset 0x{offset:X}: ptr=0x{data_ptr:X}, size={array_size}")

                                    for i in range(min(array_size, 16)):
                                        player_addr = data_ptr + (i * PLAYER_STRUCT_SIZE)

                                        # Validate player entry is readable
                                        if not safe_mem.is_readable(player_addr, 64):
                                            continue

                                        # Read player name safely
                                        name = safe_mem.read_string(player_addr + 0x10, 32, "")

                                        if name and len(name) >= 2:
                                            player_info = {
                                                'index': i,
                                                'name': name,
                                                'address': f"0x{player_addr:X}",
                                                'detected_at': datetime.now().isoformat(),
                                                'source': f'raw_memory_0x{offset:X}',
                                            }
                                            players.append(player_info)
                                            log_flush(f"    [NETWORK PLAYER {i}] '{name}' @ 0x{player_addr:X}")

                            except Exception:
                                continue

                except Exception as raw_err:
                    log_flush(f"  _scan_network_player_state: Raw scan error: {raw_err}", "debug")

            scan_time = time.time() - scan_start
            log_flush(f"  _scan_network_player_state: Found {len(players)} network players ({scan_time:.3f}s)")

        except Exception as e:
            log_flush(f"  _scan_network_player_state failed: {e}", "error")
            import traceback
            log_flush(f"  Traceback: {traceback.format_exc()}", "debug")

        return players

    def _extract_network_player_info(self, player_obj, index: int) -> dict:
        """Extract information from a network player object."""
        try:
            info = {
                'index': index,
                'source': 'network_manager',
            }

            # Try common field names
            field_mappings = [
                ('name', ['mName', 'sName', 'Username', 'mUsername', 'PlayerName']),
                ('platform', ['mPlatform', 'ePlatform', 'Platform']),
                ('status', ['mStatus', 'eStatus', 'State', 'mState']),
                ('lobby_id', ['mLobbyId', 'LobbyId', 'SessionId']),
            ]

            for target_field, possible_names in field_mappings:
                for field_name in possible_names:
                    if hasattr(player_obj, field_name):
                        try:
                            val = getattr(player_obj, field_name)
                            if val is not None:
                                if isinstance(val, (int, float, bool)):
                                    info[target_field] = val
                                else:
                                    info[target_field] = str(val).strip()
                                break
                        except:
                            pass

            # Get address
            try:
                info['address'] = f"0x{get_addressof(player_obj):X}"
            except:
                pass

            # Add timestamp
            from datetime import datetime
            info['detected_at'] = datetime.now().isoformat()

            # Only return if we got a name
            if 'name' in info and info['name']:
                return info

        except Exception as e:
            log_flush(f"  _extract_network_player_info error: {e}", "debug")

        return None

    def _get_ctypes_type_name(self, field_type) -> str:
        """Get a human-readable type name for a ctypes field type.

        Args:
            field_type: The ctypes type class

        Returns:
            Human-readable type name string
        """
        import ctypes

        # Check for common ctypes primitives
        primitive_names = {
            ctypes.c_int8: 'int8',
            ctypes.c_uint8: 'uint8',
            ctypes.c_int16: 'int16',
            ctypes.c_uint16: 'uint16',
            ctypes.c_int32: 'int32',
            ctypes.c_uint32: 'uint32',
            ctypes.c_int64: 'int64',
            ctypes.c_uint64: 'uint64',
            ctypes.c_float: 'float',
            ctypes.c_double: 'double',
            ctypes.c_bool: 'bool',
            ctypes.c_char: 'char',
            ctypes.c_wchar: 'wchar',
            ctypes.c_byte: 'byte',
            ctypes.c_ubyte: 'ubyte',
            ctypes.c_short: 'short',
            ctypes.c_ushort: 'ushort',
            ctypes.c_int: 'int',
            ctypes.c_uint: 'uint',
            ctypes.c_long: 'long',
            ctypes.c_ulong: 'ulong',
            ctypes.c_longlong: 'int64',
            ctypes.c_ulonglong: 'uint64',
            ctypes.c_void_p: 'void*',
            ctypes.c_char_p: 'char*',
            ctypes.c_wchar_p: 'wchar*',
        }

        # Direct match
        if field_type in primitive_names:
            return primitive_names[field_type]

        # Check if it's an array
        if hasattr(field_type, '_length_'):
            element_type = field_type._type_
            element_name = self._get_ctypes_type_name(element_type)
            return f'{element_name}[{field_type._length_}]'

        # Check if it's a pointer
        if hasattr(field_type, '_type_') and hasattr(field_type, 'contents'):
            pointed_type = field_type._type_
            if pointed_type == ctypes.c_char:
                return 'char*'
            pointed_name = self._get_ctypes_type_name(pointed_type)
            return f'{pointed_name}*'

        # Check class name
        if hasattr(field_type, '__name__'):
            name = field_type.__name__

            # Clean up pointer names
            if name.startswith('LP_'):
                return name[3:] + '*'
            if name.startswith('c_'):
                return name[2:]

            return name

        # Fallback to string representation
        return str(field_type)

    def _collect_game_data(self) -> dict:
        """Collect ALL available game data from nmspy - MUST be called from pyMHF thread.

        v3.0: General-purpose collection that enumerates ALL gameData attributes
        dynamically instead of hardcoding specific ones. This enables the browser
        to explore any game structure that nmspy exposes.
        """
        collect_start = time.time()
        log_flush("=== _collect_game_data: Collecting ALL gameData (v3.0) ===")
        log_flush(f"  _data_ready flag (before): {self._data_ready}")
        log_flush(f"  captured_planets count: {len(self._captured_planets)}")

        result = {
            'data_ready': False,
            'raw_data': {},
            'captured_planets': {},
            # v3.0: New fields for general-purpose browsing
            'game_objects': {},  # ALL gameData attributes with addresses
            'struct_types': [],  # ALL available nmspy struct types
        }

        try:
            from nmspy.common import gameData
            log_flush(f"gameData type: {type(gameData)}")

            # =====================================================
            # v3.0: Enumerate ALL gameData attributes dynamically
            # =====================================================
            all_attrs = [a for a in dir(gameData) if not a.startswith('_')]
            log_flush(f"gameData has {len(all_attrs)} public attributes: {all_attrs}")

            for attr_name in all_attrs:
                try:
                    attr_val = getattr(gameData, attr_name, None)
                    if attr_val is None:
                        continue

                    # Get type info
                    type_name = type(attr_val).__name__

                    # Try to get memory address
                    addr = 0
                    try:
                        addr = get_addressof(attr_val)
                    except:
                        pass

                    # Store info for browsing
                    result['game_objects'][attr_name] = {
                        'name': attr_name,
                        'type': type_name,
                        'address': addr,
                        'address_hex': f"0x{addr:X}" if addr else "N/A",
                        'has_data': attr_val is not None,
                    }

                    # Extract nested attributes for key objects
                    if attr_val is not None:
                        nested_attrs = [a for a in dir(attr_val) if not a.startswith('_')][:50]
                        result['game_objects'][attr_name]['attributes'] = nested_attrs

                    log_flush(f"  {attr_name}: {type_name} @ {result['game_objects'][attr_name]['address_hex']}")

                except Exception as e:
                    log_flush(f"  Error accessing {attr_name}: {e}", "debug")

            # =====================================================
            # v3.0: Enumerate ALL available struct types from nmspy
            # v3.1: Now includes FULL FIELD INFO with offsets and sizes
            # =====================================================
            struct_enum_start = time.time()
            log_flush("  [PERF] Starting struct type enumeration...")
            try:
                import nmspy.data.types as nms_types
                import nmspy.data.exported_types as nms_exported
                import ctypes
                import inspect

                struct_count = 0
                field_count = 0

                for module_name, module in [('types', nms_types), ('exported_types', nms_exported)]:
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, ctypes.Structure) and obj is not ctypes.Structure:
                            try:
                                size = ctypes.sizeof(obj)

                                # Extract all fields with offsets
                                fields = []
                                if hasattr(obj, '_fields_'):
                                    for field_name, field_type in obj._fields_:
                                        try:
                                            # Get field descriptor for offset/size
                                            field_desc = getattr(obj, field_name)
                                            field_offset = field_desc.offset
                                            field_size = field_desc.size

                                            # Determine field type info
                                            type_name = self._get_ctypes_type_name(field_type)
                                            is_pointer = 'POINTER' in type_name or type_name.startswith('LP_')
                                            is_array = hasattr(field_type, '_length_')
                                            array_len = getattr(field_type, '_length_', 0) if is_array else 0
                                            is_struct = False
                                            try:
                                                is_struct = issubclass(field_type, ctypes.Structure)
                                            except:
                                                pass

                                            fields.append({
                                                'name': field_name,
                                                'offset': field_offset,
                                                'offset_hex': f"0x{field_offset:X}",
                                                'size': field_size,
                                                'size_hex': f"0x{field_size:X}",
                                                'type': type_name,
                                                'is_pointer': is_pointer,
                                                'is_array': is_array,
                                                'array_length': array_len,
                                                'is_struct': is_struct,
                                            })
                                            field_count += 1
                                        except Exception as fe:
                                            # Still add field even if we can't get all info
                                            fields.append({
                                                'name': field_name,
                                                'offset': 0,
                                                'offset_hex': '?',
                                                'size': 0,
                                                'size_hex': '?',
                                                'type': str(field_type),
                                                'error': str(fe),
                                            })

                                result['struct_types'].append({
                                    'name': name,
                                    'module': module_name,
                                    'size': size,
                                    'size_hex': f"0x{size:X}",
                                    'field_count': len(fields),
                                    'fields': fields,
                                })
                                struct_count += 1
                            except Exception as se:
                                # Log but continue
                                pass

                struct_enum_time = time.time() - struct_enum_start
                log_flush(f"  [PERF] Struct enumeration took {struct_enum_time:.3f}s ({struct_count} types, {field_count} fields)")
            except Exception as e:
                log_flush(f"  Error enumerating struct types: {e}", "warning")

            # =====================================================
            # Legacy: Extract specific data for backward compatibility
            # =====================================================
            player_data_start = time.time()
            log_flush("  [PERF] Starting player data extraction...")

            # Player state (commonly used)
            log_flush("  --- PLAYER STATE DEBUG ---")
            player_state = gameData.player_state
            log_flush(f"  gameData.player_state = {player_state}")
            log_flush(f"  player_state type = {type(player_state)}")

            if player_state is None:
                log_flush("  WARNING: player_state is None!", "warning")
                log_flush("  This usually means:")
                log_flush("    1. Game not fully loaded (wait for APPVIEW)")
                log_flush("    2. Not in-game (still on menu)")
                log_flush("    3. nmspy.common.gameData not properly initialized")
            else:
                try:
                    # Log what attributes are available
                    player_attrs = [a for a in dir(player_state) if not a.startswith('_')]
                    log_flush(f"  player_state has {len(player_attrs)} attributes")
                    log_flush(f"  First 20 attrs: {player_attrs[:20]}")

                    # Try to get address
                    try:
                        addr = get_addressof(player_state)
                        log_flush(f"  player_state address: 0x{addr:X}")
                    except Exception as ae:
                        log_flush(f"  Could not get player_state address: {ae}", "debug")

                    # Extract stats with detailed logging
                    # Basic stats
                    health = getattr(player_state, 'miHealth', None)
                    shield = getattr(player_state, 'miShield', None)
                    ship_health = getattr(player_state, 'miShipHealth', None)
                    energy = getattr(player_state, 'mfEnergy', None)

                    # Currencies
                    units = getattr(player_state, 'muUnits', None)
                    nanites = getattr(player_state, 'muNanites', None)
                    quicksilver = getattr(player_state, 'muSpecials', None)

                    # Indices
                    primary_ship = getattr(player_state, 'miPrimaryShip', None)
                    primary_weapon = getattr(player_state, 'miPrimaryWeapon', None)

                    log_flush(f"  miHealth raw = {health} (type: {type(health)})")
                    log_flush(f"  miShield raw = {shield} (type: {type(shield)})")
                    log_flush(f"  miShipHealth raw = {ship_health} (type: {type(ship_health)})")
                    log_flush(f"  muUnits raw = {units} (type: {type(units)})")
                    log_flush(f"  muNanites raw = {nanites} (type: {type(nanites)})")
                    log_flush(f"  muSpecials (quicksilver) raw = {quicksilver}")
                    log_flush(f"  miPrimaryShip raw = {primary_ship}")

                    result['raw_data']['player'] = {
                        'health': self._safe_int(health),
                        'shield': self._safe_int(shield),
                        'ship_health': self._safe_int(ship_health),
                        'energy': self._safe_float(energy) if energy else 0.0,
                        'units': self._safe_int(units),
                        'nanites': self._safe_int(nanites),
                        'quicksilver': self._safe_int(quicksilver),
                        'primary_ship_index': self._safe_int(primary_ship),
                        'primary_multitool_index': self._safe_int(primary_weapon),
                    }
                    log_flush(f"  Player data extracted: {result['raw_data']['player']}")

                    # Location
                    log_flush("  --- LOCATION DEBUG ---")
                    if hasattr(player_state, 'mLocation'):
                        loc = player_state.mLocation
                        log_flush(f"  mLocation = {loc}")
                        if hasattr(loc, 'GalacticAddress'):
                            ga = loc.GalacticAddress
                            log_flush(f"  GalacticAddress = {ga}")
                            voxel_x = self._safe_int(getattr(ga, 'VoxelX', 0))
                            voxel_y = self._safe_int(getattr(ga, 'VoxelY', 0))
                            voxel_z = self._safe_int(getattr(ga, 'VoxelZ', 0))
                            system_idx = self._safe_int(getattr(ga, 'SolarSystemIndex', 0))
                            planet_idx = self._safe_int(getattr(ga, 'PlanetIndex', 0))
                            galaxy_idx = self._safe_int(getattr(loc, 'RealityIndex', 0))

                            log_flush(f"  VoxelX={voxel_x}, VoxelY={voxel_y}, VoxelZ={voxel_z}")
                            log_flush(f"  SystemIdx={system_idx}, PlanetIdx={planet_idx}, GalaxyIdx={galaxy_idx}")

                            glyph_code = self._coords_to_glyphs(
                                planet_idx, system_idx, voxel_x, voxel_y, voxel_z
                            )

                            result['raw_data']['location'] = {
                                'voxel_x': voxel_x,
                                'voxel_y': voxel_y,
                                'voxel_z': voxel_z,
                                'system_index': system_idx,
                                'planet_index': planet_idx,
                                'galaxy_index': galaxy_idx,
                                'galaxy_name': GALAXY_NAMES.get(galaxy_idx, f"Galaxy_{galaxy_idx}"),
                                'glyph_code': glyph_code,
                            }
                            log_flush(f"  Location extracted: Glyph={glyph_code}")
                        else:
                            log_flush("  WARNING: mLocation has no GalacticAddress!", "warning")
                    else:
                        log_flush("  WARNING: player_state has no mLocation!", "warning")
                except Exception as e:
                    log_flush(f"  Error extracting player data: {e}", "warning")
                    log_flush(f"  Traceback: {traceback.format_exc()}", "debug")

            # =====================================================
            # Character State (jetpack, stamina, etc.) from simulation.mPlayer
            # =====================================================
            log_flush("  --- CHARACTER STATE ---")
            simulation = gameData.simulation
            if simulation and hasattr(simulation, 'mPlayer'):
                try:
                    player = simulation.mPlayer
                    result['raw_data']['character'] = {}

                    # Jetpack fuel
                    if hasattr(player, 'mfJetpackTank'):
                        result['raw_data']['character']['jetpack_fuel'] = self._safe_float(player.mfJetpackTank)
                    # Stamina
                    if hasattr(player, 'mfStamina'):
                        result['raw_data']['character']['stamina'] = self._safe_float(player.mfStamina)
                    # Air timer
                    if hasattr(player, 'mfAirTimer'):
                        result['raw_data']['character']['air_timer'] = self._safe_float(player.mfAirTimer)
                    # State flags
                    if hasattr(player, 'mbSpawned'):
                        result['raw_data']['character']['spawned'] = bool(player.mbSpawned)
                    if hasattr(player, 'mbIsRunning'):
                        result['raw_data']['character']['is_running'] = bool(player.mbIsRunning)
                    if hasattr(player, 'mbIsDying'):
                        result['raw_data']['character']['is_dying'] = bool(player.mbIsDying)

                    log_flush(f"  Character data extracted: {result['raw_data']['character']}")
                except Exception as e:
                    log_flush(f"  Error extracting character state: {e}", "debug")

            player_data_time = time.time() - player_data_start
            log_flush(f"  [PERF] Player/location/character extraction took {player_data_time:.3f}s")

            # =====================================================
            # Freighter Data
            # The freighter data is stored at known offsets in the game state
            # We try to read freighter matrix position as indicator of freighter ownership
            # =====================================================
            freighter_start = time.time()
            log_flush("  --- FREIGHTER DATA ---")
            try:
                game_state = gameData.game_state
                if game_state:
                    game_state_addr = get_addressof(game_state)
                    log_flush(f"  game_state address: 0x{game_state_addr:X}")

                    # The freighter data is embedded in the player state data structure
                    # We'll try to detect if player has a freighter by checking if freighter spawn time is set
                    # FreighterFleet in cGcPlayerStateData has:
                    #   - HomeSystemSeed at offset 0x4C8 within cGcFreighterSaveData
                    #   - LastSpawnTime at offset 0x4D8 within cGcFreighterSaveData
                    #   - Dismissed flag at offset 0x4F8

                    # For now, just mark that freighter data detection is available
                    result['raw_data']['freighter'] = {
                        'status': 'detection_available',
                        'note': 'Freighter data requires save file parsing for full details',
                        'has_freighter': False,  # Default to false, update below if detected
                    }

                    # Try to access mPlayerFreighterOwnership if it exists
                    if hasattr(game_state, 'mPlayerFreighterOwnership'):
                        freighter_ownership = game_state.mPlayerFreighterOwnership
                        if freighter_ownership:
                            result['raw_data']['freighter']['has_freighter'] = True
                            log_flush("  Freighter ownership detected!")

                    log_flush(f"  Freighter data: {result['raw_data']['freighter']}")
            except Exception as e:
                log_flush(f"  Error extracting freighter data: {e}", "debug")
                result['raw_data']['freighter'] = {
                    'status': 'error',
                    'error': str(e),
                }

            # =====================================================
            # Base Building Data
            # PersistentPlayerBases is a dynamic array in the player state data
            # This is complex to read from live memory, so we provide status info
            # =====================================================
            log_flush("  --- BASE BUILDING DATA ---")
            try:
                result['raw_data']['bases'] = {
                    'status': 'detection_available',
                    'note': 'Base data stored in save file structure',
                    'base_count': 0,  # Default
                    'bases': [],
                }

                # Try to access base building manager if available
                app = gameData.GcApplication
                if app and hasattr(app, 'mpData') and app.mpData:
                    data = app.mpData.contents
                    if hasattr(data, 'mBaseBuildingManager'):
                        log_flush("  BaseBuildingManager found in GcApplication.mpData")
                        result['raw_data']['bases']['status'] = 'manager_accessible'

                log_flush(f"  Base data: {result['raw_data']['bases']}")
            except Exception as e:
                log_flush(f"  Error extracting base data: {e}", "debug")
                result['raw_data']['bases'] = {
                    'status': 'error',
                    'error': str(e),
                }

            # =====================================================
            # Multitool Data
            # =====================================================
            log_flush("  --- MULTITOOL DATA ---")
            try:
                result['raw_data']['multitools'] = {
                    'primary_index': player_data.get('primary_multitool_index', 0) if player_data else 0,
                    'note': 'Multitool inventory data in save file structure',
                }
                log_flush(f"  Multitool data: {result['raw_data']['multitools']}")
            except Exception as e:
                log_flush(f"  Error extracting multitool data: {e}", "debug")

            freighter_base_time = time.time() - freighter_start
            log_flush(f"  [PERF] Freighter/base/multitool extraction took {freighter_base_time:.3f}s")

            # =====================================================
            # Multiplayer Data - Enhanced Detection v2
            # Multiple detection methods to catch all MP scenarios:
            # 1. mbMultiplayerActive attribute (may only work for host)
            # 2. Raw memory scan around offset 0xB508
            # 3. Scan nearby offsets for offset changes in game updates
            # 4. HUDManager marker detection for NetworkPlayer (0x39)
            # 5. Check multiplayer-related fields in player state
            # =====================================================
            multiplayer_start = time.time()
            log_flush("  --- MULTIPLAYER DATA (Enhanced Detection v2) ---")
            try:
                import ctypes
                result['raw_data']['multiplayer'] = {
                    'multiplayer_active': False,
                    'session_type': 'single_player',
                    'network_players_detected': 0,
                    'network_player_names': [],
                    'lobby_id': 0,
                    'in_anomaly': False,
                    'detection_method': 'none',
                    'debug_info': {},
                }

                app = gameData.GcApplication
                app_addr = 0
                detection_methods_tried = []

                # Method 1: Check mbMultiplayerActive via struct attribute
                if app and hasattr(app, 'mbMultiplayerActive'):
                    try:
                        mp_active = bool(app.mbMultiplayerActive)
                        detection_methods_tried.append(f"attribute={mp_active}")
                        if mp_active:
                            result['raw_data']['multiplayer']['multiplayer_active'] = True
                            result['raw_data']['multiplayer']['session_type'] = 'multiplayer_host'
                            result['raw_data']['multiplayer']['detection_method'] = 'attribute'
                        log_flush(f"  Method 1 - mbMultiplayerActive (attribute): {mp_active}")
                    except Exception as e:
                        log_flush(f"  Method 1 failed: {e}", "debug")

                # Method 2: Scan multiple offsets around 0xB508
                # Game updates may shift offsets slightly
                if app:
                    try:
                        app_addr = get_addressof(app)
                        log_flush(f"  cGcApplication address: 0x{app_addr:X}")
                        result['raw_data']['multiplayer']['debug_info']['app_address'] = f"0x{app_addr:X}"

                        # Scan a range of offsets around 0xB508
                        mp_offsets_to_check = [0xB508, 0xB509, 0xB50A, 0xB507, 0xB506,
                                               0xB510, 0xB500, 0xB518, 0xB520]
                        for offset in mp_offsets_to_check:
                            try:
                                addr = app_addr + offset
                                val = ctypes.c_bool.from_address(addr).value
                                if val:
                                    detection_methods_tried.append(f"raw_0x{offset:X}=True")
                                    log_flush(f"  Method 2 - Found TRUE at offset 0x{offset:X}")
                                    if not result['raw_data']['multiplayer']['multiplayer_active']:
                                        result['raw_data']['multiplayer']['multiplayer_active'] = True
                                        result['raw_data']['multiplayer']['session_type'] = 'multiplayer_detected'
                                        result['raw_data']['multiplayer']['detection_method'] = f'raw_0x{offset:X}'
                            except:
                                pass

                        # Read mbPaused at 0xB505
                        try:
                            paused = ctypes.c_bool.from_address(app_addr + 0xB505).value
                            result['raw_data']['multiplayer']['game_paused'] = paused
                        except:
                            pass

                    except Exception as e:
                        log_flush(f"  Method 2 failed: {e}", "debug")

                # Method 3: Check for network players via HUDManager marker system
                # NetworkPlayer building class = 0x39 (57 decimal)
                if app and hasattr(app, 'mpData') and app.mpData:
                    try:
                        app_data = app.mpData.contents
                        if hasattr(app_data, 'mHUDManager'):
                            hud_mgr = app_data.mHUDManager
                            log_flush(f"  Method 3 - Checking HUDManager for network player markers...")
                            # Note: Direct marker iteration requires hooking TryAddMarker
                            # We can check if HUDManager is accessible
                            result['raw_data']['multiplayer']['debug_info']['hud_manager_available'] = True
                    except Exception as e:
                        log_flush(f"  Method 3 (HUDManager check) failed: {e}", "debug")

                # Method 4: Check player environment for Nexus/Anomaly (always multiplayer)
                if simulation and hasattr(simulation, 'mEnvironment'):
                    try:
                        env = simulation.mEnvironment
                        if hasattr(env, 'mPlayerEnvironment'):
                            player_env = env.mPlayerEnvironment
                            if hasattr(player_env, 'meLocation'):
                                loc_type = self._safe_int(player_env.meLocation)
                                # Location types for multiplayer areas:
                                # 0x1B = InNexus, 0x1C = InNexusOnFoot
                                in_nexus = loc_type in [0x1B, 0x1C]
                                result['raw_data']['multiplayer']['in_anomaly'] = in_nexus
                                result['raw_data']['multiplayer']['location_type'] = loc_type
                                log_flush(f"  Method 4 - Location type: {loc_type}, In Anomaly: {in_nexus}")
                                if in_nexus:
                                    result['raw_data']['multiplayer']['multiplayer_active'] = True
                                    result['raw_data']['multiplayer']['session_type'] = 'anomaly_session'
                                    if result['raw_data']['multiplayer']['detection_method'] == 'none':
                                        result['raw_data']['multiplayer']['detection_method'] = 'anomaly_location'
                    except Exception as e:
                        log_flush(f"  Method 4 failed: {e}", "debug")

                # Method 5: Check game state for multiplayer-related data
                game_state = gameData.game_state
                if game_state:
                    try:
                        game_state_addr = get_addressof(game_state)
                        log_flush(f"  Method 5 - cGcGameState address: 0x{game_state_addr:X}")
                        result['raw_data']['multiplayer']['debug_info']['game_state_address'] = f"0x{game_state_addr:X}"

                        # Try to read player state for multiplayer fields
                        if hasattr(game_state, 'mPlayerState'):
                            player_state = game_state.mPlayerState
                            ps_addr = get_addressof(player_state)
                            result['raw_data']['multiplayer']['debug_info']['player_state_address'] = f"0x{ps_addr:X}"

                            # Check for any network-related fields we can access
                            # FireteamSessionCount is at a known offset in save data
                            # Try reading some experimental offsets
                            try:
                                # These are heuristic checks for multiplayer indicators
                                for field_name in dir(player_state):
                                    if 'network' in field_name.lower() or 'multi' in field_name.lower() or 'fireteam' in field_name.lower():
                                        try:
                                            val = getattr(player_state, field_name)
                                            log_flush(f"    Found field: {field_name} = {val}")
                                        except:
                                            pass
                            except:
                                pass

                    except Exception as e:
                        log_flush(f"  Method 5 failed: {e}", "debug")

                # Method 6: Try reading from mpData offsets that might indicate network state
                if app and app_addr:
                    try:
                        # Check for connected players count or session flags
                        # These are experimental offsets based on structure analysis
                        experimental_offsets = [
                            (0xB510, 'c_uint32', 'player_count_check'),
                            (0xB514, 'c_uint32', 'session_id_low'),
                            (0xB518, 'c_uint32', 'session_id_high'),
                        ]
                        for offset, ctype, name in experimental_offsets:
                            try:
                                if ctype == 'c_uint32':
                                    val = ctypes.c_uint32.from_address(app_addr + offset).value
                                else:
                                    val = ctypes.c_uint8.from_address(app_addr + offset).value
                                if val > 0 and val < 1000000:  # Sanity check
                                    result['raw_data']['multiplayer']['debug_info'][name] = val
                                    log_flush(f"  Method 6 - {name} at 0x{offset:X}: {val}")
                            except:
                                pass
                    except Exception as e:
                        log_flush(f"  Method 6 failed: {e}", "debug")

                # Get save slot and game mode
                if app:
                    try:
                        if hasattr(app, 'muPlayerSaveSlot'):
                            result['raw_data']['multiplayer']['save_slot'] = self._safe_int(app.muPlayerSaveSlot)

                        if hasattr(app, 'meGameMode'):
                            game_mode = self._safe_int(app.meGameMode)
                            game_mode_names = {
                                0: "Normal", 1: "Creative", 2: "Survival", 3: "Permadeath",
                                4: "Ambient", 5: "Seasonal"
                            }
                            result['raw_data']['multiplayer']['game_mode'] = game_mode
                            result['raw_data']['multiplayer']['game_mode_name'] = game_mode_names.get(game_mode, f"Mode {game_mode}")
                    except Exception as e:
                        log_flush(f"  Error getting app properties: {e}", "debug")

                # Store all detection attempts for debugging
                result['raw_data']['multiplayer']['debug_info']['methods_tried'] = detection_methods_tried

                multiplayer_detection_time = time.time() - multiplayer_start
                log_flush(f"  [PERF] Multiplayer detection methods took {multiplayer_detection_time:.3f}s")

                # =====================================================
                # v3.6.3: ENHANCED Network Player Detection
                # Combines two approaches:
                # 1. Marker hooks (dynamic tracking when markers are added/removed)
                # 2. Direct HUD marker scanning (reads current state on demand)
                # =====================================================
                network_scan_start = time.time()
                log_flush("  --- NETWORK PLAYER SCAN ---")

                # First, collect players from marker hooks
                hook_players = {p.get('name'): p for p in self._network_players.values() if p.get('status') == 'active'}
                log_flush(f"  Players from hooks: {list(hook_players.keys())}")

                # Second, perform direct HUD marker scan
                hud_players = self._scan_hud_markers_for_players()
                log_flush(f"  Players from HUD scan: {[p.get('name') for p in hud_players]}")

                # Merge players (prefer HUD scan data as it's more current)
                all_players = {}
                for p in hook_players.values():
                    name = p.get('name')
                    if name:
                        all_players[name] = p

                for p in hud_players:
                    name = p.get('name')
                    if name:
                        # HUD scan data is fresher, update if exists
                        if name in all_players:
                            all_players[name].update(p)
                        else:
                            all_players[name] = p

                active_players = [p for p in all_players.values() if p.get('status') == 'active']

                result['raw_data']['multiplayer']['network_players_detected'] = len(active_players)
                result['raw_data']['multiplayer']['network_player_names'] = [p.get('name', '') for p in active_players]
                result['raw_data']['multiplayer']['network_players'] = list(all_players.values())

                # Add discovered player bases
                result['raw_data']['multiplayer']['player_bases'] = self._discovered_bases
                result['raw_data']['multiplayer']['player_bases_count'] = len(self._discovered_bases)
                log_flush(f"  Discovered bases: {len(self._discovered_bases)}")
                for base in self._discovered_bases[:5]:  # Log first 5
                    pos = base.get('position', {})
                    log_flush(f"    - {base.get('name')} at ({pos.get('x', 0):.0f}, {pos.get('y', 0):.0f}, {pos.get('z', 0):.0f})")

                result['raw_data']['multiplayer']['debug_info']['markers_added'] = self._markers_added
                result['raw_data']['multiplayer']['debug_info']['markers_removed'] = self._markers_removed
                result['raw_data']['multiplayer']['debug_info']['total_players_seen'] = len(self._network_players)
                result['raw_data']['multiplayer']['debug_info']['hud_scan_players'] = len(hud_players)
                result['raw_data']['multiplayer']['debug_info']['hook_players'] = len(hook_players)
                result['raw_data']['multiplayer']['debug_info']['discovered_bases'] = len(self._discovered_bases)

                # If we detected network players, mark as multiplayer active
                if len(active_players) > 0:
                    result['raw_data']['multiplayer']['multiplayer_active'] = True
                    if result['raw_data']['multiplayer']['session_type'] == 'single_player':
                        result['raw_data']['multiplayer']['session_type'] = 'multiplayer_with_players'
                    if result['raw_data']['multiplayer']['detection_method'] == 'none':
                        result['raw_data']['multiplayer']['detection_method'] = 'hud_marker_scan'

                log_flush(f"  Network players (active): {len(active_players)}")
                log_flush(f"  Network player names: {result['raw_data']['multiplayer']['network_player_names']}")
                log_flush(f"  Final multiplayer status: {result['raw_data']['multiplayer']['session_type']}")
                log_flush(f"  Detection method: {result['raw_data']['multiplayer']['detection_method']}")
                log_flush(f"  Debug info: {result['raw_data']['multiplayer']['debug_info']}")

                network_scan_time = time.time() - network_scan_start
                log_flush(f"  [PERF] Network player scan took {network_scan_time:.3f}s")

                # =====================================================
                # v3.8.0: ACTUAL BASE DATA (Not just HUD markers)
                # Scans PersistentPlayerBases from cGcPlayerStateData
                # This gives us real base info with glyph codes
                # GUARDED BY EXPERIMENTAL FLAG - Disabled by default
                # =====================================================
                actual_bases_start = time.time()
                log_flush("  --- ACTUAL PERSISTENT BASES ---")

                if ENABLE_EXPERIMENTAL_BASE_SCAN:
                    log_flush("  [EXPERIMENTAL] Base scanning ENABLED - using safe memory access")
                    actual_bases = self._scan_persistent_player_bases()
                else:
                    log_flush("  [EXPERIMENTAL] Base scanning DISABLED - set ENABLE_EXPERIMENTAL_BASE_SCAN=True to enable")
                    actual_bases = []

                result['raw_data']['multiplayer']['actual_bases'] = actual_bases
                result['raw_data']['multiplayer']['actual_bases_count'] = len(actual_bases)
                result['raw_data']['multiplayer']['experimental_base_scan_enabled'] = ENABLE_EXPERIMENTAL_BASE_SCAN

                log_flush(f"  Actual bases from PlayerStateData: {len(actual_bases)}")
                for base in actual_bases[:5]:  # Log first 5
                    pos = base.get('position', {})
                    log_flush(f"    - {base.get('name')} [{base.get('glyph_code')}] @ ({pos.get('x', 0):.0f}, {pos.get('y', 0):.0f}, {pos.get('z', 0):.0f})")

                actual_bases_time = time.time() - actual_bases_start
                log_flush(f"  [PERF] Actual bases scan took {actual_bases_time:.3f}s")

                # =====================================================
                # v3.8.0: NETWORK PLAYER STATE DATA
                # Attempts to access actual player state for network players
                # GUARDED BY EXPERIMENTAL FLAG - Disabled by default
                # =====================================================
                net_state_start = time.time()
                log_flush("  --- NETWORK PLAYER STATE DATA ---")

                if ENABLE_EXPERIMENTAL_NETWORK_SCAN:
                    log_flush("  [EXPERIMENTAL] Network state scanning ENABLED - using safe memory access")
                    network_state_players = self._scan_network_player_state()
                else:
                    log_flush("  [EXPERIMENTAL] Network state scanning DISABLED - set ENABLE_EXPERIMENTAL_NETWORK_SCAN=True to enable")
                    network_state_players = []

                result['raw_data']['multiplayer']['network_player_state'] = network_state_players
                result['raw_data']['multiplayer']['network_state_count'] = len(network_state_players)
                result['raw_data']['multiplayer']['experimental_network_scan_enabled'] = ENABLE_EXPERIMENTAL_NETWORK_SCAN

                log_flush(f"  Network player state entries: {len(network_state_players)}")
                for nsp in network_state_players[:5]:  # Log first 5
                    log_flush(f"    - {nsp.get('name')} (source: {nsp.get('source')})")

                # Update debug info
                result['raw_data']['multiplayer']['debug_info']['actual_bases_count'] = len(actual_bases)
                result['raw_data']['multiplayer']['debug_info']['network_state_count'] = len(network_state_players)
                result['raw_data']['multiplayer']['debug_info']['experimental_base_scan'] = ENABLE_EXPERIMENTAL_BASE_SCAN
                result['raw_data']['multiplayer']['debug_info']['experimental_network_scan'] = ENABLE_EXPERIMENTAL_NETWORK_SCAN

                net_state_time = time.time() - net_state_start
                log_flush(f"  [PERF] Network player state scan took {net_state_time:.3f}s")

            except Exception as e:
                log_flush(f"  Error extracting multiplayer data: {e}", "debug")
                import traceback
                log_flush(f"  Traceback: {traceback.format_exc()}", "debug")
                result['raw_data']['multiplayer'] = {
                    'status': 'error',
                    'error': str(e),
                }

            # =====================================================
            # Ship Fleet Data from game_state.mPlayerShipOwnership
            # =====================================================
            ships_start = time.time()
            log_flush("  --- SHIP FLEET ---")
            game_state = gameData.game_state
            if game_state and hasattr(game_state, 'mPlayerShipOwnership'):
                try:
                    ship_ownership = game_state.mPlayerShipOwnership
                    result['raw_data']['ships'] = []

                    if hasattr(ship_ownership, 'mShips'):
                        ships_array = ship_ownership.mShips
                        log_flush(f"  Found ship array: {type(ships_array)}")

                        for i in range(12):  # Max 12 ships
                            try:
                                ship = ships_array[i] if hasattr(ships_array, '__getitem__') else None
                                if ship:
                                    ship_info = {'slot': i}

                                    # Extract seed
                                    if hasattr(ship, 'mPlayerShipSeed'):
                                        seed_obj = ship.mPlayerShipSeed
                                        seed_val = self._safe_int(getattr(seed_obj, 'Seed', 0) if hasattr(seed_obj, 'Seed') else seed_obj)
                                        ship_info['seed'] = seed_val
                                        ship_info['empty'] = (seed_val == 0)

                                    # Ship class
                                    if hasattr(ship, 'meShipClass'):
                                        ship_info['class_id'] = self._safe_int(ship.meShipClass)

                                    result['raw_data']['ships'].append(ship_info)
                            except Exception as se:
                                log_flush(f"  Error reading ship {i}: {se}", "debug")

                    log_flush(f"  Ships extracted: {len(result['raw_data'].get('ships', []))} slots")
                except Exception as e:
                    log_flush(f"  Error extracting ship data: {e}", "debug")

            # Solar system (commonly used)
            if simulation and hasattr(simulation, 'mpSolarSystem') and simulation.mpSolarSystem:
                try:
                    addr = get_addressof(simulation.mpSolarSystem)
                    if addr != 0:
                        self._cached_solar_system = map_struct(addr, nms.cGcSolarSystem)
                        if hasattr(self._cached_solar_system, 'mSolarSystemData'):
                            sys_data = self._cached_solar_system.mSolarSystemData
                            result['raw_data']['system'] = {
                                'planet_count': getattr(sys_data, 'Planets', 0),
                            }
                except Exception as e:
                    log_flush(f"  Error extracting system data: {e}", "warning")

            # Fallback: Use cached solar system from function hook
            if self._cached_solar_system and 'system' not in result['raw_data']:
                try:
                    if hasattr(self._cached_solar_system, 'mSolarSystemData'):
                        sys_data = self._cached_solar_system.mSolarSystemData
                        result['raw_data']['system'] = {
                            'planet_count': getattr(sys_data, 'Planets', 0),
                        }
                except:
                    pass

        except Exception as e:
            log_flush(f"Error collecting game data: {e}", "error")
            log_flush(traceback.format_exc(), "error")

        # =====================================================
        # Include captured planet data from hooks
        # =====================================================
        if self._captured_planets:
            result['captured_planets'] = dict(self._captured_planets)
            result['raw_data']['planets'] = []
            for idx in sorted(self._captured_planets.keys()):
                planet = self._captured_planets[idx]
                result['raw_data']['planets'].append(planet)

        # Determine data readiness
        has_data = (len(result['game_objects']) > 0 or
                    len(result['raw_data']) > 0 or
                    len(self._captured_planets) > 0)

        if has_data:
            self._data_ready = True
            result['data_ready'] = True
            log_flush(f"=== Data ready: {len(result['game_objects'])} game objects, {len(result['struct_types'])} struct types ===")
        else:
            result['data_ready'] = self._data_ready
            if not self._data_ready:
                log_flush("No data found - load into game and click Refresh Data", "warning")

        # Cache thread-safely
        with self._data_lock:
            self._cached_game_data = result

        # Final timing summary
        total_collect_time = time.time() - collect_start
        log_flush("=" * 60)
        log_flush(f"[PERF] _collect_game_data TOTAL: {total_collect_time:.3f}s")
        log_flush("=" * 60)
        log_flush(f"=== _collect_game_data: Done, {len(result['game_objects'])} objects, {len(result['struct_types'])} types ===")
        return result

    def get_cached_data(self) -> dict:
        """Get cached game data (thread-safe for GUI access)."""
        with self._data_lock:
            return self._cached_game_data.copy()

    def explore_object(self, object_path: str, max_depth: int = 2) -> dict:
        """Explore a game object's attributes at the given path.

        v3.0: Allows dynamic exploration of any game object by path.
        Path format: "simulation.mpSolarSystem.mSolarSystemData"

        Args:
            object_path: Dot-separated path from gameData
            max_depth: How deep to explore nested objects

        Returns:
            Dictionary with explored fields and values
        """
        log_flush(f"=== explore_object: {object_path} (depth={max_depth}) ===")
        result = {
            'path': object_path,
            'success': False,
            'error': None,
            'type': None,
            'address': None,
            'fields': {},
        }

        try:
            from nmspy.common import gameData

            # Navigate to the object
            parts = object_path.split('.')
            obj = gameData

            for part in parts:
                if obj is None:
                    result['error'] = f"NULL at '{part}'"
                    return result
                obj = getattr(obj, part, None)

            if obj is None:
                result['error'] = "Object is NULL"
                return result

            # Get basic info
            result['type'] = type(obj).__name__
            try:
                result['address'] = f"0x{get_addressof(obj):X}"
            except:
                result['address'] = "N/A"

            # Get all attributes
            attrs = [a for a in dir(obj) if not a.startswith('_')]

            for attr_name in attrs:
                try:
                    attr_val = getattr(obj, attr_name, None)

                    field_info = {
                        'name': attr_name,
                        'type': type(attr_val).__name__ if attr_val is not None else 'NoneType',
                        'value': None,
                        'address': None,
                        'is_expandable': False,
                    }

                    # Try to get address
                    try:
                        addr = get_addressof(attr_val)
                        field_info['address'] = f"0x{addr:X}" if addr else "N/A"
                    except:
                        field_info['address'] = "N/A"

                    # Get value based on type
                    if attr_val is None:
                        field_info['value'] = "NULL"
                    elif isinstance(attr_val, (int, float, bool, str)):
                        field_info['value'] = str(attr_val)
                    elif isinstance(attr_val, bytes):
                        field_info['value'] = attr_val[:32].hex() + ('...' if len(attr_val) > 32 else '')
                    elif hasattr(attr_val, '__iter__') and not isinstance(attr_val, str):
                        try:
                            length = len(attr_val)
                            field_info['value'] = f"[array of {length}]"
                            field_info['is_expandable'] = True
                        except:
                            field_info['value'] = "[iterable]"
                            field_info['is_expandable'] = True
                    else:
                        # Complex object - mark as expandable
                        field_info['value'] = f"<{type(attr_val).__name__}>"
                        field_info['is_expandable'] = True

                        # If shallow enough, recurse
                        if max_depth > 0:
                            nested_attrs = [a for a in dir(attr_val) if not a.startswith('_')][:20]
                            field_info['nested_preview'] = nested_attrs

                    result['fields'][attr_name] = field_info

                except Exception as e:
                    result['fields'][attr_name] = {
                        'name': attr_name,
                        'error': str(e),
                    }

            result['success'] = True
            log_flush(f"  Explored {len(result['fields'])} fields")

        except Exception as e:
            result['error'] = str(e)
            log_flush(f"  explore_object failed: {e}", "error")

        return result

    def read_memory_at(self, address: int, size: int = 256) -> dict:
        """Read raw memory at an arbitrary address.

        v3.0: Allows viewing raw memory bytes at any address.

        Args:
            address: Memory address to read
            size: Number of bytes to read (max 4096)

        Returns:
            Dictionary with hex dump and info
        """
        log_flush(f"=== read_memory_at: 0x{address:X} (size={size}) ===")
        result = {
            'address': f"0x{address:X}",
            'size': min(size, 4096),
            'success': False,
            'error': None,
            'hex_dump': '',
            'ascii_preview': '',
        }

        try:
            import ctypes

            # Read the memory
            buffer = (ctypes.c_ubyte * result['size'])()
            bytes_read = ctypes.c_size_t()

            # Get current process handle
            import ctypes.wintypes
            kernel32 = ctypes.windll.kernel32
            GetCurrentProcess = kernel32.GetCurrentProcess
            GetCurrentProcess.restype = ctypes.wintypes.HANDLE
            ReadProcessMemory = kernel32.ReadProcessMemory

            handle = GetCurrentProcess()
            success = ReadProcessMemory(
                handle,
                ctypes.c_void_p(address),
                buffer,
                result['size'],
                ctypes.byref(bytes_read)
            )

            if success:
                data = bytes(buffer[:bytes_read.value])
                result['hex_dump'] = data.hex()
                result['ascii_preview'] = ''.join(
                    chr(b) if 32 <= b < 127 else '.'
                    for b in data[:64]
                )
                result['success'] = True
                result['bytes_read'] = bytes_read.value
                log_flush(f"  Read {bytes_read.value} bytes")
            else:
                result['error'] = f"ReadProcessMemory failed: {ctypes.GetLastError()}"
                log_flush(f"  {result['error']}", "error")

        except Exception as e:
            result['error'] = str(e)
            log_flush(f"  read_memory_at failed: {e}", "error")

        return result

    @gui_button("Open Memory Browser")
    def open_browser(self):
        """Open the memory browser window."""
        timing_mark("Open Memory Browser: Button clicked")
        log_flush("=== Open Memory Browser button clicked ===")
        log_flush(f"  _data_ready: {self._data_ready}")

        if not self._data_ready:
            log_flush("WARNING: APPVIEW hook hasn't fired yet - data may not be available")
            log_flush("  Make sure you're fully loaded into the game (on a planet or in space)")

        try:
            # Collect data in the pyMHF thread FIRST
            timing_mark("Open Memory Browser: Starting data collection...")
            self._collect_game_data()
            timing_mark("Open Memory Browser: Data collection complete")

            timing_mark("Open Memory Browser: Launching GUI...")
            self._launch_gui()
            timing_mark("Open Memory Browser: GUI launched")
        except Exception as e:
            log_flush(f"Failed to open browser: {e}", "error")
            log_flush(f"Traceback:\n{traceback.format_exc()}", "error")

    def _launch_gui(self):
        """Launch the PyQt6 GUI in a separate thread."""
        launch_start = time.time()

        # Check if thread already running
        if self._gui_thread and self._gui_thread.is_alive():
            log_flush("GUI thread already running, bringing window to front...")
            if self._gui_thread._window:
                # Can't directly call Qt methods from another thread
                # The window should already be visible
                log_flush("Window should already be visible")
            return

        log_flush("[PERF] Starting new GUI thread...")
        thread_start = time.time()

        # Pass the data provider callback
        self._gui_thread = GUIThread(game_data_provider=self.get_cached_data)
        self._gui_thread.start()

        thread_create_time = time.time() - thread_start
        log_flush(f"[PERF] Thread created in {thread_create_time:.3f}s, waiting for window...")

        # Wait for window to be ready (with timeout)
        wait_start = time.time()
        if self._gui_thread._ready.wait(timeout=10.0):
            wait_time = time.time() - wait_start
            total_time = time.time() - launch_start
            log_flush(f"[PERF] GUI ready after wait: {wait_time:.3f}s (total: {total_time:.3f}s)")
            log_flush("=== GUI thread started successfully ===")
        else:
            log_flush("GUI thread start timeout!", "error")

    @gui_button("Refresh Data")
    def refresh_data(self):
        """Refresh the browser data."""
        log_flush("=== Refresh Data button clicked ===")

        # Collect fresh data in the pyMHF thread
        self._collect_game_data()

        if self._gui_thread and self._gui_thread._window:
            log_flush("Signaling GUI to refresh...")
            try:
                # The window will use get_cached_data() to get the fresh data
                self._gui_thread._window._on_refresh()
                log_flush("Data refreshed")
            except Exception as e:
                log_flush(f"Refresh failed: {e}", "error")
        else:
            log_flush("Browser window not open", "warning")

    @gui_button("Export Snapshot")
    def export_snapshot(self):
        """Export a memory snapshot."""
        if self._gui_thread and self._gui_thread._window:
            try:
                self._gui_thread._window._on_export()
            except Exception as e:
                log_flush(f"Export failed: {e}", "error")
        else:
            log_flush("Browser window not open - opening first", "warning")
            self._launch_gui()

    @gui_button("Force Ready (if hooks fail)")
    def force_ready(self):
        """Force data ready state - use if state hooks don't fire."""
        log_flush("=== Force Ready button clicked ===")
        log_flush("  Forcing _data_ready = True and collecting data...")

        self._data_ready = True
        self._collect_game_data()

        if self._gui_thread and self._gui_thread._window:
            try:
                self._gui_thread._window._on_refresh()
                log_flush("Force ready complete - GUI refreshed")
            except Exception as e:
                log_flush(f"Force ready refresh failed: {e}", "error")
        else:
            log_flush("Force ready complete - open browser to see data")

    @gui_button("Explore: simulation")
    def explore_simulation(self):
        """Explore the simulation object and all its attributes."""
        log_flush("=== Exploring simulation object ===")
        result = self.explore_object("simulation", max_depth=1)

        if result['success']:
            log_flush(f"  Type: {result['type']}")
            log_flush(f"  Address: {result['address']}")
            log_flush(f"  Fields ({len(result['fields'])}):")
            for name, info in sorted(result['fields'].items()):
                value = info.get('value', 'N/A')
                addr = info.get('address', 'N/A')
                log_flush(f"    {name}: {value} @ {addr}")
        else:
            log_flush(f"  Error: {result['error']}", "error")

    @gui_button("Explore: player_state")
    def explore_player_state(self):
        """Explore the player_state object and all its attributes."""
        log_flush("=== Exploring player_state object ===")
        result = self.explore_object("player_state", max_depth=1)

        if result['success']:
            log_flush(f"  Type: {result['type']}")
            log_flush(f"  Address: {result['address']}")
            log_flush(f"  Fields ({len(result['fields'])}):")
            for name, info in sorted(result['fields'].items()):
                value = info.get('value', 'N/A')
                addr = info.get('address', 'N/A')
                log_flush(f"    {name}: {value} @ {addr}")
        else:
            log_flush(f"  Error: {result['error']}", "error")

    @gui_button("DEBUG: Player Data")
    def debug_player_data(self):
        """Debug button to check player state access and log all details."""
        log_flush("")
        log_flush("=" * 60)
        log_flush("=== DEBUG: Player Data Access Test ===")
        log_flush("=" * 60)

        try:
            from nmspy.common import gameData

            # Check gameData
            log_flush(f"gameData object: {gameData}")
            log_flush(f"gameData type: {type(gameData)}")

            # List all attributes
            all_attrs = [a for a in dir(gameData) if not a.startswith('_')]
            log_flush(f"gameData attributes: {all_attrs}")

            # Check player_state specifically
            log_flush("")
            log_flush("--- player_state check ---")
            player_state = gameData.player_state
            log_flush(f"player_state = {player_state}")
            log_flush(f"player_state type = {type(player_state)}")
            log_flush(f"player_state is None? {player_state is None}")

            if player_state is not None:
                # Try to get address
                try:
                    addr = get_addressof(player_state)
                    log_flush(f"player_state address: 0x{addr:X}")
                except Exception as e:
                    log_flush(f"Could not get address: {e}")

                # List player_state attributes
                ps_attrs = [a for a in dir(player_state) if not a.startswith('_')]
                log_flush(f"player_state has {len(ps_attrs)} attributes")

                # Log first 50 attributes
                log_flush("First 50 attributes:")
                for attr in ps_attrs[:50]:
                    try:
                        val = getattr(player_state, attr, None)
                        log_flush(f"  {attr} = {val} ({type(val).__name__})")
                    except Exception as e:
                        log_flush(f"  {attr} = ERROR: {e}")

                # Try specific fields we expect
                log_flush("")
                log_flush("--- Expected player fields ---")
                expected_fields = [
                    'miHealth', 'miShield', 'muUnits', 'muNanites',
                    'mfEnergy', 'mLocation', 'mPlayerTitleData',
                    'mSaveData', 'miShipIndex', 'mInventory'
                ]
                for field in expected_fields:
                    try:
                        val = getattr(player_state, field, 'NOT_FOUND')
                        log_flush(f"  {field} = {val}")
                    except Exception as e:
                        log_flush(f"  {field} = ERROR: {e}")
            else:
                log_flush("player_state is None!")
                log_flush("This means the game hasn't fully loaded player data yet.")
                log_flush("Try:")
                log_flush("  1. Make sure you're fully loaded into a save (on a planet)")
                log_flush("  2. Wait a few seconds after loading")
                log_flush("  3. Click 'Force Ready' then 'Refresh Data'")

        except Exception as e:
            log_flush(f"Debug failed: {e}", "error")
            log_flush(traceback.format_exc(), "error")

        log_flush("=" * 60)
        log_flush("=== END DEBUG ===")
        log_flush("=" * 60)


# Alternative standalone launcher (without pyMHF)
def main():
    """Standalone entry point for testing UI without game."""
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("NMS Memory Browser")

    from nms_memory_browser.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
