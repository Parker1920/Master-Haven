# NMS-Haven-Extractor - In-Game Mod

PyMHF-based mod that extracts system and planet data from No Man's Sky in real-time.

> **Version**: 1.3.8 | **Updated**: 2026-01-27
>
> **After making changes to this component:**
> 1. Bump `__version__` in `dist/HavenExtractor/mod/haven_extractor.py` (PATCH: bug fix, MINOR: feature, MAJOR: breaking)
> 2. Update `pyproject.toml` version to match
> 3. Update `/CLAUDE.md` → "Current Versions" table
> 4. Add changelog entry in `/CLAUDE.md`

## Quick Reference

- **Framework**: PyMHF (Python Modding Hook Framework) + NMS.py
- **Version**: 1.3.8
- **Python**: 3.11-3.12 (NOT 3.14, NOT Windows Store)
- **Output**: `~/Documents/Haven-Extractor/`

## Key Files

| File | Purpose |
|------|---------|
| `dist/HavenExtractor/mod/haven_extractor.py` | Main mod (1,175 lines) |
| `structs.py` | Data structures and enum mappings |
| `extraction_watcher.py` | File watcher for extraction outputs |
| `haven_config.json.example` | Configuration template |
| `pymhf.toml` | PyMHF mod configuration |

## Architecture

```
┌────────────────────────────────────────────────────┐
│              No Man's Sky Process                   │
│  ┌──────────────────────────────────────────────┐  │
│  │           PyMHF Injection                     │  │
│  │  ┌────────────────────────────────────────┐  │  │
│  │  │        Haven Extractor Mod              │  │  │
│  │  │  ┌──────────┐  ┌──────────────────┐   │  │  │
│  │  │  │  Hooks   │  │  Direct Memory   │   │  │  │
│  │  │  │ Generate │  │  Offset Reads    │   │  │  │
│  │  │  │ScanEvent │  │  (ctypes)        │   │  │  │
│  │  │  └────┬─────┘  └────────┬─────────┘   │  │  │
│  │  │       │                 │              │  │  │
│  │  │       └────────┬────────┘              │  │  │
│  │  │                ▼                       │  │  │
│  │  │         Extraction Data                │  │  │
│  │  └────────────────┬───────────────────────┘  │  │
│  └───────────────────┼──────────────────────────┘  │
└──────────────────────┼─────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌───────────────────┐    ┌────────────────────────┐
│   Local Files     │    │    Haven API           │
│ ~/Documents/      │    │ POST /api/extraction   │
│ Haven-Extractor/  │    │ (if configured)        │
│ - latest.json     │    │                        │
│ - extraction_*.json│    │                        │
└───────────────────┘    └────────────────────────┘
```

## Game Hooks

### @nms.cGcSolarSystem.Generate.after
- **Trigger**: After warping to new system
- **Action**: Caches solar system struct pointer, resets scan counter
- **Location**: Line 383

### @nms.cGcScanEvent.Construct.after
- **Trigger**: When scan events fire (e.g., freighter scanner room)
- **Action**: Logs events, increments counter
- **Filter**: `leTable == 3` (scanner room events)
- **Location**: Line 421

### @on_state_change("APPVIEW")
- **Trigger**: Player enters game view
- **Action**: Marks system ready
- **Location**: Line 442

## GUI Buttons

| Button | Action |
|--------|--------|
| "Check Planet Data" | Diagnostic - shows data population status |
| "Extract Now" | Manual trigger after scanner room use |

## Data Extracted

### System Level
```json
{
  "system_name": "System_XXXX",
  "glyph_code": "XXXXXXXXXXXX",
  "galaxy_name": "Euclid",
  "galaxy_index": 0,
  "star_type": "Yellow|Red|Green|Blue",
  "economy_type": "Mining|HighTech|Trading|...",
  "economy_strength": "Poor|Average|Wealthy|Pirate",
  "conflict_level": "Low|Default|High|Pirate",
  "dominant_lifeform": "Gek|Vy'keen|Korvax|...",
  "system_seed": 12345,
  "planet_count": 6,
  "voxel_x": -123, "voxel_y": 45, "voxel_z": 678,
  "solar_system_index": 114
}
```

### Per Planet
```json
{
  "planet_index": 0,
  "planet_name": "Planet 1",
  "biome": "Lush|Toxic|Scorched|...",
  "biome_subtype": "Unknown|...",
  "weather": "Humid|Radioactive Storms|...",
  "sentinel_level": "Low|Standard|High|Aggressive",
  "flora_level": "None|Sparse|Low|Average|...",
  "fauna_level": "None|Sparse|Low|Average|...",
  "common_resource": "Ferrite Dust|Carbon|...",
  "uncommon_resource": "Sodium|Phosphorus|...",
  "rare_resource": "Gold|Silver|...",
  "is_moon": false,
  "planet_size": "Large|Medium|Small|Moon|Giant"
}
```

## Memory Offset System

Based on NMS 4.13 PDB symbols from Fractal413 debug version:

```python
class SolarSystemDataOffsets:
    PLANETS_COUNT = 0x2264
    PRIME_PLANETS = 0x2268
    STAR_CLASS = 0x224C
    STAR_TYPE = 0x2270
    TRADING_DATA = 0x2240
    CONFLICT_DATA = 0x2250
    INHABITING_RACE = 0x2254
    SEED = 0x21A0
    PLANET_GEN_INPUTS = 0x1EA0

class PlanetGenInputOffsets:
    STRUCT_SIZE = 0x53  # 83 bytes per planet
    BIOME = 0x30
    PLANET_SIZE = 0x40
    COMMON_SUBSTANCE = 0x00
    RARE_SUBSTANCE = 0x10
```

### Hybrid Extraction
1. **Primary**: Direct memory offset reads via ctypes
2. **Fallback**: NMS.py struct access if direct reads fail

## Configuration

### haven_config.json
```json
{
  "api_url": "https://havenmap.online",
  "api_key": "vh_live_..."
}
```

### Config Search Order
1. `haven_config.json` in mod directory
2. `%USERPROFILE%\Documents\Haven-Extractor\config.json`
3. Hardcoded defaults

## API Communication

### Endpoint
`POST {api_url}/api/extraction`

### Headers
```
Content-Type: application/json
User-Agent: HavenExtractor/8.0.0
X-API-Key: {api_key}  # If configured
```

### SSL
Disabled verification for compatibility:
```python
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
```

### Timeout
30 seconds

### Response Format
```json
{
  "status": "ok",
  "message": "Extraction submitted",
  "submission_id": "...",
  "planet_count": 4,
  "moon_count": 1
}
```

## Output Files

Location: `~/Documents/Haven-Extractor/`

| File | Purpose |
|------|---------|
| `latest.json` | Most recent extraction |
| `extraction_YYYYMMDD_HHMMSS.json` | Timestamped backups |
| `batch_YYYYMMDD_HHMMSS.json` | Batch extractions |

## Development Tools

### Offset Discovery
```
RUN_SCANNER.bat     → Installs offset_scanner.py
ANALYZE_DUMP.bat    → Offline dump analysis
verify_offsets.py   → Compares direct vs struct
```

### Build Distribution
```
build_distributable.py  → Creates standalone package
                         → Bundles Python 3.11 embedded
                         → Includes all dependencies
```

## Enum Mappings

### Biome Types (17)
Lush, Toxic, Scorched, Radioactive, Frozen, Barren, Dead, Weird, Swamp, Lava, Waterworld, GasGiant, etc.

### Planet Sizes (5)
Large, Medium, Small, Moon, Giant

### Star Types (4)
Yellow, Red, Green, Blue

### Alien Races (7)
Traders (Gek), Warriors (Vy'keen), Explorers (Korvax), Robots, Atlas, Diplomats, None

## Extraction Flow

1. Player warps to system → `Generate` hook caches pointer
2. Player uses freighter scanner room → `ScanEvent` logs events
3. Player clicks "Check Planet Data" → Verify population
4. Player clicks "Extract Now" → Trigger extraction
5. System extracts via direct offsets + NMS.py fallback
6. Each planet extracted with all properties
7. JSON saved locally + sent to API (if configured)
8. API returns submission ID

## Dependencies

```toml
[project]
requires-python = ">=3.11,<3.14"
dependencies = [
    "nmspy>=0.1.0",     # NMS.py framework
    "requests>=2.28.0", # HTTP (optional, using urllib)
]
```

## Common Issues

### Offsets Shifted
After NMS update, offsets may change:
1. Run offset scanner mod
2. Analyze dump files
3. Update offset constants in `haven_extractor.py`

### API Connection Failed
- Check API URL is current (havenmap.online)
- Verify API key is valid
- Check Haven server is running

### Data Not Populated
- Use freighter scanner room first
- Check "Check Planet Data" button
- Some fields only populate after scanner room

## File Structure

```
NMS-Haven-Extractor/
├── dist/HavenExtractor/
│   └── mod/
│       └── haven_extractor.py   # Main distributable mod
├── structs.py                   # Data structures
├── extraction_watcher.py        # File monitoring
├── test_extractor.py            # Unit tests
├── verify_offsets.py            # Offset verification
├── analyze_dump.py              # Dump analyzer
├── offset_scanner.py            # Memory scanner mod
├── build_distributable.py       # Package builder
├── haven_config.json.example    # Config template
├── pymhf.toml                   # Mod config
├── pyproject.toml               # Python project
└── README.md                    # Documentation
```
