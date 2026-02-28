# NMS Debug Enabler

**Version:** 1.0.0
**Part of the [Master Haven](https://github.com/Parker1920/Master-Haven) project**

A standalone PyMHF mod for No Man's Sky that unlocks all 260+ debug flags in the release build by flipping the master gate: `DisableDebugControls = False`.

## What It Does

NMS ships with a full debug options struct (`gGcDebugOptions`) compiled into the release binary, but the master flag `DisableDebugControls` is set to `True`, locking out all 260+ toggles. This mod hooks into the game at boot, flips that flag, and provides a GUI panel for controlling individual flags and presets.

### Debug Features Unlocked

- **Gameplay** - God mode, infinite stamina, everything free, super kill guns, warp without fuel/drive
- **Display** - FPS counter, GPU memory/render time, position debug, universe address, memory pool overlay
- **World Gen** - Force biome, star type, terrain type, extreme weather, water, creature life levels
- **Building** - Disable build limits, disable power requirements
- **Dev Tools** - Terrain editor beam, model/creature/effect viewers, ImGui overlays, debug camera, Proto2 DevKit
- **System** - Skip intro/logos, disable hazards/storms/NPCs, toggle pirate/sentinel/ship spawning
- **Unlocks** - All words, titles, stories, season rewards

### Presets

| Preset | What It Enables |
|--------|----------------|
| God Mode | Invincible, infinite stamina, everything free, super weapons |
| Explorer | Free warping, all words unlocked, position display, skip intro |
| Builder | No build limits, no power needed, everything free |
| Performance Debug | FPS graph, GPU stats, memory overlays |
| Modder Tools | DevKit, texture debugger, scene info, creature details |
| World Override | Force biome/star/terrain/weather/water/creatures |
| Safe Online | QoL only (skip intro, FPS display) with cheats explicitly off |

## Requirements

- No Man's Sky (Steam, Windows)
- [PyMHF](https://github.com/monkeyman192/pyMHF) mod framework
- [NMS.py](https://github.com/monkeyman192/NMS.py) (nmspy)

## Usage

1. Place `mod/nms_debug_enabler.py` in your PyMHF mod directory
2. Launch NMS via PyMHF
3. Debug controls auto-enable on boot
4. Use the PyMHF GUI panel to toggle individual features or activate presets
5. Click "RESET ALL TO DEFAULTS" to restore vanilla behavior

This mod runs independently alongside Haven Extractor - both can be loaded simultaneously.

## Project Structure

```
NMS-Debug-Enabler/
  mod/
    nms_debug_enabler.py   # The mod (single file)
  analysis/
    scripts/                # Binary analysis tools for finding debug offsets
```
