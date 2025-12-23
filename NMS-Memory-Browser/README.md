# NMS Memory Browser

A standalone PyQt6-based GUI tool for browsing live game memory from No Man's Sky. Part of the Master Haven mod toolkit.

## Features

- **Browse All Memory Data** - View all accessible game structures organized by category
- **Known Structures** - Uses NMS.py struct definitions for typed access
- **Unknown Regions** - Scans gaps in known structs with type inference
- **Dual View** - See both formatted field values AND raw hex dumps
- **Multiplayer Focus** - Browse other players, bases, settlements, comm stations
- **JSON Export** - Save snapshots for offline analysis

## Requirements

- No Man's Sky (Steam)
- Python 3.10+
- PyQt6
- nmspy (includes pyMHF)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or install manually
pip install PyQt6 nmspy
```

## Usage

### With pyMHF (Recommended)

Launch as a pyMHF mod that injects into No Man's Sky:

```bash
# From the NMS-Memory-Browser folder
pymhf run .

# Or from anywhere
pymhf run path\to\Master-Haven\NMS-Memory-Browser
```

Once NMS is running, click "Open Memory Browser" in the pyMHF GUI panel.

### Standalone (UI Testing)

Run the GUI without game connection:

```bash
python -m nms_memory_browser.main
```

## UI Overview

```
+------------------------------------------------------------------+
|  [Refresh] [Export JSON] [Expand All] [Collapse All]             |
+------------------------------------------------------------------+
|  TREE BROWSER            |  DETAIL PANEL                         |
|                          |  +-----------------------------------+|
|  - Player                |  | FORMATTED VIEW                    ||
|    - Stats               |  | Type: cGcPlayerState              ||
|    - Location            |  | Address: 0x7FF123456              ||
|  - Solar System          |  | Size: 50000 bytes                 ||
|    + System Info         |  |                                   ||
|    + Planets[]           |  | Fields:                           ||
|  - Multiplayer           |  |   miShield: 100 (0x1B0)           ||
|    + Other Players[]     |  |   miHealth: 75 (0x1B4)            ||
|    + Player Bases[]      |  +-----------------------------------+|
|    + Settlements[]       |  | RAW HEX VIEW                      ||
|  - Unknown Structures    |  | 0x000: 00 00 64 00 4B 00 00 00    ||
|                          |  +-----------------------------------+|
+------------------------------------------------------------------+
|  Connected: NMS | Structs: 847 | Reads: 1234                     |
+------------------------------------------------------------------+
```

## Tree Hierarchy

- **Player** - Player state, stats, location, inventory
- **Solar System** - Current system info, planets array
- **Multiplayer** - Session info, other players, bases, settlements
- **Unknown Structures** - Gaps in known structs with type inference

## Export Format

Snapshots are saved as JSON with the following structure:

```json
{
  "version": "1.0.0",
  "metadata": {
    "timestamp": "2025-12-22T12:00:00",
    "galaxy_name": "Euclid",
    "glyph_code": "0123456789AB"
  },
  "known_structures": {
    "player": {...},
    "solar_system": {...},
    "multiplayer": {...}
  },
  "unknown_regions": [...]
}
```

## Development

### Project Structure

```
NMS-Memory-Browser/
├── nms_memory_browser/
│   ├── core/              # Memory reading, struct mapping
│   ├── collectors/        # Data collectors (player, system, MP)
│   ├── data/              # Data models (snapshot, tree nodes)
│   ├── ui/                # PyQt6 UI components
│   └── export/            # JSON export
├── pymhf.toml             # pyMHF configuration
└── requirements.txt
```

### Key Files

- `core/memory_reader.py` - Low-level ctypes memory access
- `core/struct_registry.py` - Enumerates NMS.py structs
- `core/type_inference.py` - Detects types in unknown memory
- `collectors/*_collector.py` - Category-specific data extraction
- `ui/main_window.py` - Main application window
- `ui/tree_browser.py` - Tree navigation widget
- `ui/detail_panel.py` - Formatted + hex view

## Credits

- Uses [NMS.py](https://github.com/monkeyman192/NMS.py) for game struct definitions
- Uses [pyMHF](https://github.com/monkeyman192/pyMHF) for game injection
- Part of the Master Haven mod toolkit

## License

MIT License - See LICENSE file
