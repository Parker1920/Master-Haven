# /// script
# [tool.pymhf]
# exe = "NMS.exe"
# steam_gameid = 275850
# start_exe = true
# ///
"""
NMS Debug Enabler v1.0.0

Standalone PyMHF mod that unlocks all 260+ debug flags in the current NMS
release build by flipping the master gate: DisableDebugControls = False.

Provides GUI toggle panel with presets and individual controls.
Completely independent from Haven Extractor - both mods run side by side.

DEBUG FEATURES UNLOCKED:
- Terrain editor beam
- Model/creature/effect viewers (NGui windows)
- ImGui debug overlays
- Debug camera (free cam)
- God mode, infinite stamina, everything free
- Force biome/star type/terrain type
- Force weather (storm/tornado/lightning)
- Performance overlays (FPS, GPU, memory)
- Position debug, universe address display
- Skip intro/logos/tutorial
- Disable base building limits/power
- Warp without fuel/drive requirements
- And 200+ more toggles

USAGE:
1. Place this file in NMS GAMEDATA/MODS/ alongside haven_extractor.py
2. Launch NMS via PyMHF
3. Debug controls auto-enable on boot
4. Use the PyMHF GUI panel to toggle features and presets
"""

import logging
from pymhf import Mod
from pymhf.gui.decorators import gui_button
from nmspy.decorators import on_fully_booted
import nmspy.globals as nms_globals

logger = logging.getLogger(__name__)


class NMSDebugEnabler(Mod):
    __author__ = "Haven Dev"
    __version__ = "1.0.0"
    __description__ = "Debug mode enabler with 260+ toggle flags"

    _opts = None

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    @on_fully_booted
    def _on_boot(self):
        """Map the debug options global once game is fully loaded."""
        try:
            self._opts = nms_globals.gGcDebugOptions
            if self._opts is not None:
                logger.info(
                    f"[DebugEnabler] Mapped gGcDebugOptions successfully. "
                    f"DisableDebugControls = {self._opts.DisableDebugControls}"
                )
                # Auto-enable debug controls on boot
                self._opts.DisableDebugControls = False
                logger.info("[DebugEnabler] DEBUG CONTROLS ENABLED")
            else:
                logger.error("[DebugEnabler] Failed to map gGcDebugOptions!")
        except Exception as e:
            logger.error(f"[DebugEnabler] Error during boot: {e}")

    def _ensure_mapped(self):
        """Try to map debug options if not already mapped."""
        if self._opts is not None:
            return True
        try:
            self._opts = nms_globals.gGcDebugOptions
            if self._opts is not None:
                logger.info("[DebugEnabler] Lazy-mapped gGcDebugOptions successfully")
                return True
            else:
                logger.warning("[DebugEnabler] gGcDebugOptions is None (not found in binary)")
                return False
        except Exception as e:
            logger.error(f"[DebugEnabler] Error mapping debug options: {e}")
            return False

    def _safe_set(self, attr, value):
        """Safely set a debug option attribute."""
        if not self._ensure_mapped():
            return False
        try:
            setattr(self._opts, attr, value)
            return True
        except Exception as e:
            logger.error(f"[DebugEnabler] Failed to set {attr}: {e}")
            return False

    # =========================================================================
    # MASTER CONTROLS
    # =========================================================================

    @gui_button(">>> ENABLE DEBUG CONTROLS <<<")
    def enable_debug(self):
        if self._safe_set("DisableDebugControls", False):
            logger.info("[DebugEnabler] Debug controls ENABLED")

    @gui_button("--- Disable Debug Controls ---")
    def disable_debug(self):
        if self._safe_set("DisableDebugControls", True):
            logger.info("[DebugEnabler] Debug controls DISABLED")

    # =========================================================================
    # PRESETS
    # =========================================================================

    @gui_button("Preset: God Mode")
    def preset_god_mode(self):
        if not self._ensure_mapped():
            return
        self._opts.DisableDebugControls = False
        self._opts.GodMode = True
        self._opts.TakeNoDamage = True
        self._opts.InfiniteStamina = True
        self._opts.EverythingIsFree = True
        self._opts.SuperKillGuns = True
        self._opts.InfiniteInteractions = True
        logger.info("[DebugEnabler] Preset: God Mode ON")

    @gui_button("Preset: Explorer")
    def preset_explorer(self):
        if not self._ensure_mapped():
            return
        self._opts.DisableDebugControls = False
        self._opts.MapWarpCheckIgnoreDrive = True
        self._opts.MapWarpCheckIgnoreFuel = True
        self._opts.UnlockAllWords = True
        self._opts.ShowPositionDebug = True
        self._opts.ShowFramerate = True
        self._opts.ShowFireteamMembersUA = True
        self._opts.SkipIntro = True
        self._opts.SkipLogos = True
        logger.info("[DebugEnabler] Preset: Explorer ON")

    @gui_button("Preset: Builder")
    def preset_builder(self):
        if not self._ensure_mapped():
            return
        self._opts.DisableDebugControls = False
        self._opts.DisableBaseBuildingLimits = True
        self._opts.DisableBasePowerRequirements = True
        self._opts.DisableLimits = True
        self._opts.EverythingIsFree = True
        self._opts.ShowEditorPlacementPreview = True
        logger.info("[DebugEnabler] Preset: Builder ON")

    @gui_button("Preset: Performance Debug")
    def preset_performance(self):
        if not self._ensure_mapped():
            return
        self._opts.DisableDebugControls = False
        self._opts.ShowFramerate = True
        self._opts.ShowGPUMemory = True
        self._opts.ShowGPURenderTime = True
        self._opts.ShowMempoolOverlay = True
        self._opts.GraphFPS = True
        self._opts.PrintAvgFrameTimes = True
        self._opts.ShowGraphs = True
        logger.info("[DebugEnabler] Preset: Performance Debug ON")

    @gui_button("Preset: Modder Tools")
    def preset_modder(self):
        if not self._ensure_mapped():
            return
        self._opts.DisableDebugControls = False
        self._opts.Proto2DevKit = True
        self._opts.UseProcTextureDebugger = True
        self._opts.UseSceneInfoWindow = True
        self._opts.ShowDebugMessages = True
        self._opts.ShowEditorPlacementPreview = True
        self._opts.RenderCreatureDetails = True
        self._opts.DebugBuildingSpawns = True
        self._opts.ShowPositionDebug = True
        self._opts.ShowFramerate = True
        logger.info("[DebugEnabler] Preset: Modder Tools ON")

    @gui_button("Preset: World Override")
    def preset_world_override(self):
        if not self._ensure_mapped():
            return
        self._opts.DisableDebugControls = False
        self._opts.ForceBiome = True
        self._opts.ForceStarType = True
        self._opts.ForceTerrainType = True
        self._opts.ForceExtremeWeather = True
        self._opts.ForcePlanetsToHaveWater = True
        self._opts.ForceCreatureLifeLevel = True
        logger.info("[DebugEnabler] Preset: World Override ON")

    @gui_button("Preset: Safe Online")
    def preset_safe_online(self):
        if not self._ensure_mapped():
            return
        self._opts.DisableDebugControls = False
        self._opts.SkipIntro = True
        self._opts.SkipLogos = True
        self._opts.ShowFramerate = True
        self._opts.ShowPositionDebug = True
        # Explicitly disable cheats for safe online play
        self._opts.GodMode = False
        self._opts.TakeNoDamage = False
        self._opts.EverythingIsFree = False
        self._opts.SuperKillGuns = False
        logger.info("[DebugEnabler] Preset: Safe Online ON")

    # =========================================================================
    # RESET
    # =========================================================================

    @gui_button("!!! RESET ALL TO DEFAULTS !!!")
    def reset_all(self):
        if not self._ensure_mapped():
            return
        # Gameplay cheats off
        self._opts.GodMode = False
        self._opts.TakeNoDamage = False
        self._opts.InfiniteStamina = False
        self._opts.EverythingIsFree = False
        self._opts.EverythingIsKnown = False
        self._opts.SuperKillGuns = False
        self._opts.InfiniteInteractions = False
        self._opts.SpecialsShop = False
        self._opts.MapWarpCheckIgnoreDrive = False
        self._opts.MapWarpCheckIgnoreFuel = False
        # World gen off
        self._opts.ForceBiome = False
        self._opts.ForceStarType = False
        self._opts.ForceTerrainType = False
        self._opts.ForceExtremeWeather = False
        self._opts.ForceExtremeSentinels = False
        self._opts.ForcePirateSystem = False
        self._opts.ForcePlanetsToHaveWater = False
        self._opts.ForcePlanetsToHaveNoWater = False
        self._opts.ForcePlanetsToHaveNoCaves = False
        self._opts.ForceCreatureLifeLevel = False
        self._opts.ForceGasGiantSystem = False
        self._opts.ForceBinaryStar = False
        # Building off
        self._opts.DisableBaseBuildingLimits = False
        self._opts.DisableBasePowerRequirements = False
        self._opts.DisableLimits = False
        # Overlays off
        self._opts.ShowFramerate = False
        self._opts.ShowGPUMemory = False
        self._opts.ShowGPURenderTime = False
        self._opts.ShowPositionDebug = False
        self._opts.ShowMempoolOverlay = False
        self._opts.ShowDebugMessages = False
        self._opts.ShowGraphs = False
        self._opts.ShowDynamicResScale = False
        self._opts.ShowFireteamMembersUA = False
        self._opts.GraphFPS = False
        self._opts.PrintAvgFrameTimes = False
        # System toggles off
        self._opts.DisableHazards = False
        self._opts.DisableStorms = False
        self._opts.DisableNPCs = False
        self._opts.DisableSettlements = False
        self._opts.DisableSaving = False
        self._opts.DisableProfanityFilter = False
        # Dev tools off
        self._opts.ScreenshotMode = False
        self._opts.VideoCaptureMode = False
        self._opts.Proto2DevKit = False
        self._opts.UseProcTextureDebugger = False
        self._opts.UseSceneInfoWindow = False
        self._opts.ShowEditorPlacementPreview = False
        self._opts.RenderCreatureDetails = False
        self._opts.DebugBuildingSpawns = False
        # Unlocks off
        self._opts.UnlockAllWords = False
        self._opts.UnlockAllTitles = False
        self._opts.UnlockAllStories = False
        self._opts.UnlockAllSeasonRewards = False
        self._opts.UnlockAllPlatformRewards = False
        self._opts.UnlockAllTwitchRewards = False
        # Spawning defaults
        self._opts.SpawnPirates = True
        self._opts.SpawnRobots = True
        self._opts.SpawnShips = True
        self._opts.SpawnPulseEncounters = True
        # Keep essential systems on
        self._opts.RenderHud = True
        self._opts.UseTerrain = True
        self._opts.UseBuildings = True
        self._opts.UseCreatures = True
        self._opts.UseInstances = True
        self._opts.UseClouds = True
        self._opts.UseParticles = True
        self._opts.UseObjects = True
        self._opts.LoadMissions = True
        self._opts.DoAlienLanguage = True
        self._opts.EnableDayNightCycle = True
        self._opts.EnableCloudAnimation = True
        # Re-lock debug controls
        self._opts.DisableDebugControls = True
        logger.info("[DebugEnabler] ALL flags reset to defaults")

    # =========================================================================
    # INDIVIDUAL TOGGLES - GAMEPLAY
    # =========================================================================

    @gui_button("Toggle: God Mode")
    def toggle_god_mode(self):
        if self._ensure_mapped():
            self._opts.GodMode = not self._opts.GodMode
            logger.info(f"[DebugEnabler] GodMode = {self._opts.GodMode}")

    @gui_button("Toggle: Take No Damage")
    def toggle_no_damage(self):
        if self._ensure_mapped():
            self._opts.TakeNoDamage = not self._opts.TakeNoDamage
            logger.info(f"[DebugEnabler] TakeNoDamage = {self._opts.TakeNoDamage}")

    @gui_button("Toggle: Infinite Stamina")
    def toggle_inf_stamina(self):
        if self._ensure_mapped():
            self._opts.InfiniteStamina = not self._opts.InfiniteStamina
            logger.info(f"[DebugEnabler] InfiniteStamina = {self._opts.InfiniteStamina}")

    @gui_button("Toggle: Everything Free")
    def toggle_everything_free(self):
        if self._ensure_mapped():
            self._opts.EverythingIsFree = not self._opts.EverythingIsFree
            logger.info(f"[DebugEnabler] EverythingIsFree = {self._opts.EverythingIsFree}")

    @gui_button("Toggle: Super Kill Guns")
    def toggle_super_kill(self):
        if self._ensure_mapped():
            self._opts.SuperKillGuns = not self._opts.SuperKillGuns
            logger.info(f"[DebugEnabler] SuperKillGuns = {self._opts.SuperKillGuns}")

    @gui_button("Toggle: Warp Ignore Drive")
    def toggle_warp_drive(self):
        if self._ensure_mapped():
            self._opts.MapWarpCheckIgnoreDrive = not self._opts.MapWarpCheckIgnoreDrive
            logger.info(f"[DebugEnabler] MapWarpCheckIgnoreDrive = {self._opts.MapWarpCheckIgnoreDrive}")

    @gui_button("Toggle: Warp Ignore Fuel")
    def toggle_warp_fuel(self):
        if self._ensure_mapped():
            self._opts.MapWarpCheckIgnoreFuel = not self._opts.MapWarpCheckIgnoreFuel
            logger.info(f"[DebugEnabler] MapWarpCheckIgnoreFuel = {self._opts.MapWarpCheckIgnoreFuel}")

    # =========================================================================
    # INDIVIDUAL TOGGLES - DISPLAY / OVERLAYS
    # =========================================================================

    @gui_button("Toggle: Show Framerate")
    def toggle_fps(self):
        if self._ensure_mapped():
            self._opts.ShowFramerate = not self._opts.ShowFramerate
            logger.info(f"[DebugEnabler] ShowFramerate = {self._opts.ShowFramerate}")

    @gui_button("Toggle: Show Position Debug")
    def toggle_position(self):
        if self._ensure_mapped():
            self._opts.ShowPositionDebug = not self._opts.ShowPositionDebug
            logger.info(f"[DebugEnabler] ShowPositionDebug = {self._opts.ShowPositionDebug}")

    @gui_button("Toggle: Show GPU Memory")
    def toggle_gpu_mem(self):
        if self._ensure_mapped():
            self._opts.ShowGPUMemory = not self._opts.ShowGPUMemory
            logger.info(f"[DebugEnabler] ShowGPUMemory = {self._opts.ShowGPUMemory}")

    @gui_button("Toggle: Show GPU Render Time")
    def toggle_gpu_render(self):
        if self._ensure_mapped():
            self._opts.ShowGPURenderTime = not self._opts.ShowGPURenderTime
            logger.info(f"[DebugEnabler] ShowGPURenderTime = {self._opts.ShowGPURenderTime}")

    @gui_button("Toggle: Show Debug Messages")
    def toggle_debug_msgs(self):
        if self._ensure_mapped():
            self._opts.ShowDebugMessages = not self._opts.ShowDebugMessages
            logger.info(f"[DebugEnabler] ShowDebugMessages = {self._opts.ShowDebugMessages}")

    @gui_button("Toggle: Show Fireteam UA")
    def toggle_fireteam_ua(self):
        if self._ensure_mapped():
            self._opts.ShowFireteamMembersUA = not self._opts.ShowFireteamMembersUA
            logger.info(f"[DebugEnabler] ShowFireteamMembersUA = {self._opts.ShowFireteamMembersUA}")

    @gui_button("Toggle: Show Memory Pool")
    def toggle_mempool(self):
        if self._ensure_mapped():
            self._opts.ShowMempoolOverlay = not self._opts.ShowMempoolOverlay
            logger.info(f"[DebugEnabler] ShowMempoolOverlay = {self._opts.ShowMempoolOverlay}")

    @gui_button("Toggle: Graph FPS")
    def toggle_graph_fps(self):
        if self._ensure_mapped():
            self._opts.GraphFPS = not self._opts.GraphFPS
            logger.info(f"[DebugEnabler] GraphFPS = {self._opts.GraphFPS}")

    # =========================================================================
    # INDIVIDUAL TOGGLES - WORLD GENERATION
    # =========================================================================

    @gui_button("Toggle: Force Biome")
    def toggle_force_biome(self):
        if self._ensure_mapped():
            self._opts.ForceBiome = not self._opts.ForceBiome
            logger.info(f"[DebugEnabler] ForceBiome = {self._opts.ForceBiome}")

    @gui_button("Toggle: Force Star Type")
    def toggle_force_star(self):
        if self._ensure_mapped():
            self._opts.ForceStarType = not self._opts.ForceStarType
            logger.info(f"[DebugEnabler] ForceStarType = {self._opts.ForceStarType}")

    @gui_button("Toggle: Force Terrain Type")
    def toggle_force_terrain(self):
        if self._ensure_mapped():
            self._opts.ForceTerrainType = not self._opts.ForceTerrainType
            logger.info(f"[DebugEnabler] ForceTerrainType = {self._opts.ForceTerrainType}")

    @gui_button("Toggle: Force Extreme Weather")
    def toggle_extreme_weather(self):
        if self._ensure_mapped():
            self._opts.ForceExtremeWeather = not self._opts.ForceExtremeWeather
            logger.info(f"[DebugEnabler] ForceExtremeWeather = {self._opts.ForceExtremeWeather}")

    @gui_button("Toggle: Force Water")
    def toggle_force_water(self):
        if self._ensure_mapped():
            self._opts.ForcePlanetsToHaveWater = not self._opts.ForcePlanetsToHaveWater
            logger.info(f"[DebugEnabler] ForcePlanetsToHaveWater = {self._opts.ForcePlanetsToHaveWater}")

    # =========================================================================
    # INDIVIDUAL TOGGLES - BUILDING
    # =========================================================================

    @gui_button("Toggle: No Build Limits")
    def toggle_no_build_limits(self):
        if self._ensure_mapped():
            self._opts.DisableBaseBuildingLimits = not self._opts.DisableBaseBuildingLimits
            logger.info(f"[DebugEnabler] DisableBaseBuildingLimits = {self._opts.DisableBaseBuildingLimits}")

    @gui_button("Toggle: No Power Required")
    def toggle_no_power(self):
        if self._ensure_mapped():
            self._opts.DisableBasePowerRequirements = not self._opts.DisableBasePowerRequirements
            logger.info(f"[DebugEnabler] DisableBasePowerRequirements = {self._opts.DisableBasePowerRequirements}")

    # =========================================================================
    # INDIVIDUAL TOGGLES - SYSTEM
    # =========================================================================

    @gui_button("Toggle: Disable Hazards")
    def toggle_hazards(self):
        if self._ensure_mapped():
            self._opts.DisableHazards = not self._opts.DisableHazards
            logger.info(f"[DebugEnabler] DisableHazards = {self._opts.DisableHazards}")

    @gui_button("Toggle: Disable Storms")
    def toggle_storms(self):
        if self._ensure_mapped():
            self._opts.DisableStorms = not self._opts.DisableStorms
            logger.info(f"[DebugEnabler] DisableStorms = {self._opts.DisableStorms}")

    @gui_button("Toggle: Disable NPCs")
    def toggle_npcs(self):
        if self._ensure_mapped():
            self._opts.DisableNPCs = not self._opts.DisableNPCs
            logger.info(f"[DebugEnabler] DisableNPCs = {self._opts.DisableNPCs}")

    @gui_button("Toggle: Disable Saving")
    def toggle_saving(self):
        if self._ensure_mapped():
            self._opts.DisableSaving = not self._opts.DisableSaving
            logger.info(f"[DebugEnabler] DisableSaving = {self._opts.DisableSaving}")

    # =========================================================================
    # INDIVIDUAL TOGGLES - DEV TOOLS
    # =========================================================================

    @gui_button("Toggle: Skip Intro")
    def toggle_skip_intro(self):
        if self._ensure_mapped():
            self._opts.SkipIntro = not self._opts.SkipIntro
            logger.info(f"[DebugEnabler] SkipIntro = {self._opts.SkipIntro}")

    @gui_button("Toggle: Skip Logos")
    def toggle_skip_logos(self):
        if self._ensure_mapped():
            self._opts.SkipLogos = not self._opts.SkipLogos
            logger.info(f"[DebugEnabler] SkipLogos = {self._opts.SkipLogos}")

    @gui_button("Toggle: Screenshot Mode")
    def toggle_screenshot(self):
        if self._ensure_mapped():
            self._opts.ScreenshotMode = not self._opts.ScreenshotMode
            logger.info(f"[DebugEnabler] ScreenshotMode = {self._opts.ScreenshotMode}")

    @gui_button("Toggle: Proto2 DevKit")
    def toggle_devkit(self):
        if self._ensure_mapped():
            self._opts.Proto2DevKit = not self._opts.Proto2DevKit
            logger.info(f"[DebugEnabler] Proto2DevKit = {self._opts.Proto2DevKit}")

    @gui_button("Toggle: Proc Texture Debugger")
    def toggle_proc_tex(self):
        if self._ensure_mapped():
            self._opts.UseProcTextureDebugger = not self._opts.UseProcTextureDebugger
            logger.info(f"[DebugEnabler] UseProcTextureDebugger = {self._opts.UseProcTextureDebugger}")

    @gui_button("Toggle: Scene Info Window")
    def toggle_scene_info(self):
        if self._ensure_mapped():
            self._opts.UseSceneInfoWindow = not self._opts.UseSceneInfoWindow
            logger.info(f"[DebugEnabler] UseSceneInfoWindow = {self._opts.UseSceneInfoWindow}")

    @gui_button("Toggle: Boot Into Last Save")
    def toggle_boot_save(self):
        if self._ensure_mapped():
            self._opts.BootDirectlyIntoLastSave = not self._opts.BootDirectlyIntoLastSave
            logger.info(f"[DebugEnabler] BootDirectlyIntoLastSave = {self._opts.BootDirectlyIntoLastSave}")

    # =========================================================================
    # INDIVIDUAL TOGGLES - UNLOCKS
    # =========================================================================

    @gui_button("Unlock All Words")
    def unlock_words(self):
        if self._ensure_mapped():
            self._opts.UnlockAllWords = True
            logger.info("[DebugEnabler] UnlockAllWords = True")

    @gui_button("Unlock All Titles")
    def unlock_titles(self):
        if self._ensure_mapped():
            self._opts.UnlockAllTitles = True
            logger.info("[DebugEnabler] UnlockAllTitles = True")

    @gui_button("Unlock All Stories")
    def unlock_stories(self):
        if self._ensure_mapped():
            self._opts.UnlockAllStories = True
            logger.info("[DebugEnabler] UnlockAllStories = True")

    @gui_button("Unlock All Season Rewards")
    def unlock_season(self):
        if self._ensure_mapped():
            self._opts.UnlockAllSeasonRewards = True
            logger.info("[DebugEnabler] UnlockAllSeasonRewards = True")

    # =========================================================================
    # INDIVIDUAL TOGGLES - SPAWNING
    # =========================================================================

    @gui_button("Toggle: Spawn Pirates")
    def toggle_pirates(self):
        if self._ensure_mapped():
            self._opts.SpawnPirates = not self._opts.SpawnPirates
            logger.info(f"[DebugEnabler] SpawnPirates = {self._opts.SpawnPirates}")

    @gui_button("Toggle: Spawn Sentinels")
    def toggle_sentinels(self):
        if self._ensure_mapped():
            self._opts.SpawnRobots = not self._opts.SpawnRobots
            logger.info(f"[DebugEnabler] SpawnRobots = {self._opts.SpawnRobots}")

    @gui_button("Toggle: Spawn Ships")
    def toggle_ships(self):
        if self._ensure_mapped():
            self._opts.SpawnShips = not self._opts.SpawnShips
            logger.info(f"[DebugEnabler] SpawnShips = {self._opts.SpawnShips}")

    # =========================================================================
    # STATUS
    # =========================================================================

    @gui_button("Print Current Debug Status")
    def print_status(self):
        if self._opts is None:
            logger.info("[DebugEnabler] Debug options not mapped")
            return
        logger.info("=" * 60)
        logger.info("[DebugEnabler] CURRENT DEBUG STATUS")
        logger.info("=" * 60)
        logger.info(f"  DisableDebugControls = {self._opts.DisableDebugControls}")
        logger.info(f"  GodMode = {self._opts.GodMode}")
        logger.info(f"  TakeNoDamage = {self._opts.TakeNoDamage}")
        logger.info(f"  InfiniteStamina = {self._opts.InfiniteStamina}")
        logger.info(f"  EverythingIsFree = {self._opts.EverythingIsFree}")
        logger.info(f"  SuperKillGuns = {self._opts.SuperKillGuns}")
        logger.info(f"  ShowFramerate = {self._opts.ShowFramerate}")
        logger.info(f"  ShowPositionDebug = {self._opts.ShowPositionDebug}")
        logger.info(f"  ShowGPUMemory = {self._opts.ShowGPUMemory}")
        logger.info(f"  ShowGPURenderTime = {self._opts.ShowGPURenderTime}")
        logger.info(f"  ForceBiome = {self._opts.ForceBiome}")
        logger.info(f"  ForceStarType = {self._opts.ForceStarType}")
        logger.info(f"  ForceTerrainType = {self._opts.ForceTerrainType}")
        logger.info(f"  DisableBaseBuildingLimits = {self._opts.DisableBaseBuildingLimits}")
        logger.info(f"  DisableBasePowerRequirements = {self._opts.DisableBasePowerRequirements}")
        logger.info(f"  DisableHazards = {self._opts.DisableHazards}")
        logger.info(f"  DisableStorms = {self._opts.DisableStorms}")
        logger.info(f"  MapWarpCheckIgnoreDrive = {self._opts.MapWarpCheckIgnoreDrive}")
        logger.info(f"  MapWarpCheckIgnoreFuel = {self._opts.MapWarpCheckIgnoreFuel}")
        logger.info(f"  Proto2DevKit = {self._opts.Proto2DevKit}")
        logger.info(f"  SkipIntro = {self._opts.SkipIntro}")
        logger.info(f"  SkipLogos = {self._opts.SkipLogos}")
        logger.info(f"  SpawnPirates = {self._opts.SpawnPirates}")
        logger.info(f"  SpawnRobots = {self._opts.SpawnRobots}")
        logger.info(f"  SpawnShips = {self._opts.SpawnShips}")
        logger.info("=" * 60)
