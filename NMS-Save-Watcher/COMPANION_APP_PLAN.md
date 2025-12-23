# NMS Save Watcher Companion App - Complete Implementation Plan

## Project Overview

A Python companion application that watches No Man's Sky save files and automatically uploads discovered system/planet data to the Voyagers Haven web application as pending approval submissions.

---

## Table of Contents

1. [Project Goals](#project-goals)
2. [Technical Stack](#technical-stack)
3. [Architecture Overview](#architecture-overview)
4. [Backend Modifications](#backend-modifications)
5. [Companion App Components](#companion-app-components)
6. [Data Structures](#data-structures)
7. [NMS Save File Parsing](#nms-save-file-parsing)
8. [Web Dashboard](#web-dashboard)
9. [Duplicate Detection Strategy](#duplicate-detection-strategy)
10. [Error Handling](#error-handling)
11. [File Structure](#file-structure)
12. [Implementation Phases](#implementation-phases)
13. [Resource Mappings](#resource-mappings)
14. [API Endpoints](#api-endpoints)
15. [Configuration](#configuration)
16. [Testing Strategy](#testing-strategy)

---

## 1. Project Goals

### Primary Objectives
- Watch NMS save files for changes in real-time
- Parse LZ4 compressed save files with obfuscated JSON keys
- Extract system and planet discovery data when stellar scanner is used
- Submit discoveries to Voyagers Haven API as pending approval
- Prevent duplicates using galactic coordinates (glyph_code + galaxy)
- Track upload history locally to avoid re-uploading
- Provide a web dashboard matching Haven-UI theme

### Key Features
- Auto-detect Steam save file location
- Process save slot #1 (configurable)
- Support all 256 galaxies (stored for future multi-galaxy maps)
- Include other players' discoveries with original discoverer credited
- Queue uploads when server is offline, retry when available
- Windows notifications on successful uploads
- Flag unknown obfuscated keys for mod updates

### User Experience
- Manual start via `start.bat`
- Web dashboard on port 8006
- Console logging + Windows toast notifications
- Standalone `.exe` for easy distribution

---

## 2. Technical Stack

### Companion App
- **Language**: Python 3.11+
- **File Watching**: `watchdog` library
- **LZ4 Decompression**: `lz4` library
- **HTTP Client**: `httpx` (async support, retry logic)
- **Local Database**: SQLite3
- **Web Dashboard**: FastAPI + Jinja2 templates
- **Notifications**: `win10toast` or `plyer`
- **Packaging**: PyInstaller (standalone .exe)

### Backend Additions (Voyagers Haven)
- API key authentication system
- Schema migrations for new fields
- Source tracking for submissions

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NMS Save Watcher Companion App                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐       │
│  │   File Watcher   │───▶│   Save Parser    │───▶│  Data Extractor  │       │
│  │    (watchdog)    │    │  (LZ4 + deobf)   │    │   (discoveries)  │       │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘       │
│           │                                               │                  │
│           │ monitors                                      │ extracts         │
│           ▼                                               ▼                  │
│  ┌──────────────────┐                           ┌──────────────────┐        │
│  │  %APPDATA%/      │                           │  System + Planet │        │
│  │  HelloGames/NMS/ │                           │  Discovery Data  │        │
│  │  st_<steamid>/   │                           └──────────────────┘        │
│  │  save.hg         │                                    │                  │
│  └──────────────────┘                                    ▼                  │
│                                                 ┌──────────────────┐        │
│                                                 │ Duplicate Check  │        │
│                                                 │ (glyph + galaxy) │        │
│                                                 └──────────────────┘        │
│                                                          │                  │
│                         ┌────────────────────────────────┼──────────┐       │
│                         │                                │          │       │
│                         ▼                                ▼          ▼       │
│                ┌──────────────────┐           ┌─────────────┐ ┌──────────┐ │
│                │   Local SQLite   │           │  API Client │ │  Upload  │ │
│                │  (upload history │◀─────────▶│  (httpx)    │ │  Queue   │ │
│                │   + state)       │           └─────────────┘ │ (offline)│ │
│                └──────────────────┘                   │       └──────────┘ │
│                         │                             │                     │
│                         │                             ▼                     │
│                         │                    ┌──────────────────┐           │
│                         │                    │  Voyagers Haven  │           │
│                         │                    │      API         │           │
│                         │                    │ /api/submit_system│          │
│                         │                    └──────────────────┘           │
│                         │                                                   │
│                         ▼                                                   │
│                ┌──────────────────────────────────────────────────┐        │
│                │              Web Dashboard (FastAPI)              │        │
│                │                  Port 8006                        │        │
│                │  ┌────────────┬────────────┬────────────────┐    │        │
│                │  │   Status   │   Upload   │   Settings     │    │        │
│                │  │  Monitor   │   History  │   & Config     │    │        │
│                │  └────────────┴────────────┴────────────────┘    │        │
│                └──────────────────────────────────────────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Backend Modifications (Voyagers Haven)

### 4.1 New Database Table: `api_keys`

```sql
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,          -- SHA256 hash of the API key
    key_prefix TEXT NOT NULL,               -- First 8 chars for identification
    name TEXT NOT NULL,                     -- Friendly name (e.g., "Parker's Companion App")
    created_at TEXT NOT NULL,               -- ISO timestamp
    last_used_at TEXT,                      -- Last API call timestamp
    permissions TEXT DEFAULT '["submit"]',  -- JSON array of allowed actions
    rate_limit INTEGER DEFAULT 200,         -- Requests per hour (null = unlimited)
    is_active INTEGER DEFAULT 1,            -- 0 = disabled, 1 = active
    created_by TEXT                         -- Admin who created the key
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
```

### 4.2 Schema Migrations: `systems` Table

Add these columns to the existing `systems` table:

```sql
-- Star classification
ALTER TABLE systems ADD COLUMN star_type TEXT;
-- Values: 'Yellow', 'Red', 'Green', 'Blue', 'Purple'

-- Economy information
ALTER TABLE systems ADD COLUMN economy_type TEXT;
-- Values: 'Mining', 'Manufacturing', 'Technology', 'Trading',
--         'Advanced Materials', 'Scientific', 'Power Generation',
--         'Mass Production', 'Ore Processing', 'High Tech',
--         'Construction', 'Research', 'Metal Processing',
--         'Experimental', 'Nano-construction', 'Commercial',
--         'Mathematical', 'Energy Supply'

ALTER TABLE systems ADD COLUMN economy_level TEXT;
-- Values: 'Low', 'Medium', 'High' (displayed as stars in-game)

-- Conflict information
ALTER TABLE systems ADD COLUMN conflict_level TEXT;
-- Values: 'Low', 'Medium', 'High'

-- Discovery metadata
ALTER TABLE systems ADD COLUMN discovered_by TEXT;
-- Original discoverer's NMS username

ALTER TABLE systems ADD COLUMN discovered_at TEXT;
-- ISO timestamp of discovery (from save file if available)
```

### 4.3 Schema Migrations: `pending_systems` Table

Add source tracking:

```sql
ALTER TABLE pending_systems ADD COLUMN source TEXT DEFAULT 'manual';
-- Values: 'manual' (web UI), 'companion_app', 'api'

ALTER TABLE pending_systems ADD COLUMN api_key_name TEXT;
-- Name of API key used (null for manual/session submissions)
```

### 4.4 New API Endpoints

#### `POST /api/keys` (Admin only)
Create a new API key.

**Request:**
```json
{
    "name": "Parker's Companion App",
    "rate_limit": 200,
    "permissions": ["submit", "check_duplicate"]
}
```

**Response:**
```json
{
    "id": 1,
    "name": "Parker's Companion App",
    "key": "vh_live_a1b2c3d4e5f6g7h8i9j0...",  // Only shown once!
    "key_prefix": "vh_live_a1",
    "created_at": "2024-12-03T18:00:00Z"
}
```

#### `GET /api/keys` (Admin only)
List all API keys (without the actual key values).

#### `DELETE /api/keys/{id}` (Admin only)
Revoke an API key.

#### `GET /api/check_duplicate` (API key required)
Check if a system already exists before uploading.

**Request Headers:**
```
X-API-Key: vh_live_a1b2c3d4e5f6g7h8i9j0...
```

**Query Parameters:**
```
?glyph_code=60720193DFA9&galaxy=Euclid
```

**Response:**
```json
{
    "exists": true,
    "location": "approved",  // or "pending"
    "system_id": "63bd03ab-f575-4eaf-8e5c-4ea77f7cde8a",
    "system_name": "Oculi"
}
```
or
```json
{
    "exists": false
}
```

### 4.5 Modified Endpoints

#### `POST /api/submit_system`
Add API key authentication support alongside existing session auth.

**New Headers Accepted:**
```
X-API-Key: vh_live_a1b2c3d4e5f6g7h8i9j0...
```

**Modified Behavior:**
- If `X-API-Key` header present, validate against `api_keys` table
- Set `source = 'companion_app'` and `api_key_name` in pending_systems
- Apply API key's rate limit (200/hour) instead of IP-based limit
- Still creates pending submission (no auto-approve)

**New Fields in Request Body:**
```json
{
    "name": "System Name",
    "galaxy": "Euclid",
    "star_type": "Yellow",
    "economy_type": "Trading",
    "economy_level": "High",
    "conflict_level": "Low",
    "discovered_by": "OriginalDiscoverer",
    "discovered_at": "2024-12-01T15:30:00Z",
    // ... existing fields ...
}
```

### 4.6 Authentication Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Companion App  │     │   Haven API     │     │    Database     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │  POST /api/submit_system                      │
         │  X-API-Key: vh_live_...                       │
         │──────────────────────▶│                       │
         │                       │                       │
         │                       │  SHA256(key)          │
         │                       │──────────────────────▶│
         │                       │                       │
         │                       │  SELECT * FROM api_keys
         │                       │  WHERE key_hash = ?   │
         │                       │◀──────────────────────│
         │                       │                       │
         │                       │  Check: is_active,    │
         │                       │  rate_limit, perms    │
         │                       │                       │
         │                       │  UPDATE last_used_at  │
         │                       │──────────────────────▶│
         │                       │                       │
         │                       │  INSERT pending_system│
         │                       │  source='companion_app'
         │                       │──────────────────────▶│
         │                       │                       │
         │  200 OK               │                       │
         │  {submission_id: 123} │                       │
         │◀──────────────────────│                       │
         │                       │                       │
```

---

## 5. Companion App Components

### 5.1 File Watcher (`watcher.py`)

**Responsibilities:**
- Auto-detect NMS save folder: `%APPDATA%\HelloGames\NMS\st_*\`
- Watch for changes to `save.hg` (save slot 1)
- Debounce rapid save events (wait 2 seconds after last change)
- Trigger parser when save file stabilizes

**Implementation:**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import os

class SaveFileHandler(FileSystemEventHandler):
    def __init__(self, callback, debounce_seconds=2):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.last_modified = 0
        self.pending_process = False

    def on_modified(self, event):
        if event.src_path.endswith('save.hg'):
            self.last_modified = time.time()
            if not self.pending_process:
                self.pending_process = True
                # Schedule processing after debounce period
                threading.Timer(self.debounce_seconds, self._process).start()

    def _process(self):
        if time.time() - self.last_modified >= self.debounce_seconds:
            self.pending_process = False
            self.callback()
        else:
            # More changes came in, wait longer
            threading.Timer(self.debounce_seconds, self._process).start()
```

**Save Path Detection:**
```python
def find_nms_save_path():
    """Auto-detect NMS Steam save folder."""
    appdata = os.environ.get('APPDATA')
    nms_base = os.path.join(appdata, 'HelloGames', 'NMS')

    if not os.path.exists(nms_base):
        raise FileNotFoundError("NMS save folder not found")

    # Find st_* folder (Steam ID folder)
    for folder in os.listdir(nms_base):
        if folder.startswith('st_'):
            save_path = os.path.join(nms_base, folder)
            if os.path.exists(os.path.join(save_path, 'save.hg')):
                return save_path

    raise FileNotFoundError("No Steam save folder found")
```

### 5.2 Save Parser (`parser.py`)

**Responsibilities:**
- Decompress LZ4-compressed .hg files
- Parse JSON with obfuscated keys
- Deobfuscate keys using mapping table
- Flag unknown keys for investigation

**LZ4 Decompression:**
```python
import lz4.frame
import json

def decompress_save(file_path):
    """Decompress NMS .hg save file."""
    with open(file_path, 'rb') as f:
        # Skip header bytes (format-specific)
        header = f.read(4)
        compressed_data = f.read()

    try:
        decompressed = lz4.frame.decompress(compressed_data)
        return decompressed.decode('utf-8')
    except Exception as e:
        raise ValueError(f"Failed to decompress save: {e}")
```

**Key Deobfuscation:**
```python
class KeyMapper:
    def __init__(self, mappings_path):
        with open(mappings_path) as f:
            self.mappings = json.load(f)
        self.reverse_mappings = {v: k for k, v in self.mappings.items()}
        self.unknown_keys = set()

    def deobfuscate(self, obj):
        """Recursively deobfuscate JSON keys."""
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key in self.mappings:
                    new_key = self.mappings[key]
                else:
                    new_key = key
                    if key.startswith('@') or len(key) == 3:
                        # Likely obfuscated, flag it
                        self.unknown_keys.add(key)
                result[new_key] = self.deobfuscate(value)
            return result
        elif isinstance(obj, list):
            return [self.deobfuscate(item) for item in obj]
        else:
            return obj

    def get_unknown_keys(self):
        """Return keys that couldn't be mapped."""
        return list(self.unknown_keys)
```

### 5.3 Data Extractor (`extractor.py`)

**Responsibilities:**
- Navigate parsed save structure to find discovery data
- Extract system information (name, star type, economy, conflict)
- Extract planet information (biome, sentinels, fauna, flora, resources)
- Extract moon information
- Extract base locations
- Get original discoverer username
- Convert coordinates to glyph format using API

**Key Save File Paths:**

```python
# Player's current location
save_data['PlayerStateData']['UniverseAddress']['GalacticAddress']
# Contains: VoxelX, VoxelY, VoxelZ, SolarSystemIndex, PlanetIndex

# Galaxy index (0 = Euclid, 1 = Hilbert, etc.)
save_data['PlayerStateData']['UniverseAddress']['RealityIndex']

# Discovery data
save_data['DiscoveryManagerData']['DiscoveryData-v1']
# Array of all discoveries

# Each discovery contains:
# - DD (DiscoveryData): Name, type, timestamp
# - DM (DiscoveryMetadata): Coordinates, discoverer info
# - OWS (OwnershipState): Who discovered it
```

**System Extraction:**
```python
def extract_system_data(discovery):
    """Extract system data from a discovery record."""
    return {
        'name': discovery.get('Name', 'Unknown'),
        'star_type': map_star_type(discovery.get('StarType')),
        'economy_type': map_economy_type(discovery.get('Economy')),
        'economy_level': map_economy_level(discovery.get('Wealth')),
        'conflict_level': map_conflict_level(discovery.get('Conflict')),
        'discovered_by': discovery.get('Discoverer', 'Unknown'),
        'discovered_at': parse_nms_timestamp(discovery.get('Timestamp')),
        'galaxy_index': discovery.get('RealityIndex', 0),
        'voxel_x': discovery.get('GalacticAddress', {}).get('VoxelX'),
        'voxel_y': discovery.get('GalacticAddress', {}).get('VoxelY'),
        'voxel_z': discovery.get('GalacticAddress', {}).get('VoxelZ'),
        'solar_system_index': discovery.get('GalacticAddress', {}).get('SolarSystemIndex'),
    }
```

**Planet Extraction:**
```python
def extract_planet_data(discovery):
    """Extract planet data from a discovery record."""
    return {
        'name': discovery.get('Name', 'Unknown'),
        'biome': discovery.get('Biome'),  # Raw biome type
        'climate': discovery.get('Weather'),  # Weather description
        'sentinel': map_sentinel_level(discovery.get('Sentinels')),
        'fauna': map_fauna_level(discovery.get('Fauna')),
        'flora': map_flora_level(discovery.get('Flora')),
        'has_water': discovery.get('HasWater', False),
        'resources': extract_resources(discovery.get('Resources', [])),
        'base_location': extract_base_location(discovery),
    }
```

### 5.4 Glyph Converter (`glyph.py`)

**Responsibilities:**
- Call Haven API `/api/decode_glyph` for coordinate conversion
- Cache results locally to reduce API calls
- Handle offline scenarios

```python
import httpx

class GlyphConverter:
    def __init__(self, api_base_url, api_key):
        self.api_base = api_base_url
        self.api_key = api_key
        self.cache = {}

    async def coordinates_to_glyph(self, voxel_x, voxel_y, voxel_z,
                                    solar_system_index, planet_index=0):
        """Convert NMS coordinates to 12-digit glyph code."""
        cache_key = (voxel_x, voxel_y, voxel_z, solar_system_index, planet_index)

        if cache_key in self.cache:
            return self.cache[cache_key]

        # Call the Haven API encode endpoint
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/api/encode_glyph",
                json={
                    'x': voxel_x,
                    'y': voxel_y,
                    'z': voxel_z,
                    'solar_system': solar_system_index,
                    'planet': planet_index
                },
                headers={'X-API-Key': self.api_key}
            )

            if response.status_code == 200:
                result = response.json()
                self.cache[cache_key] = result
                return result
            else:
                raise Exception(f"Glyph encoding failed: {response.text}")
```

### 5.5 API Client (`api_client.py`)

**Responsibilities:**
- Submit systems to Haven API
- Check for duplicates before submission
- Handle authentication with API key
- Implement retry logic with exponential backoff
- Queue requests when offline

```python
import httpx
import asyncio
from datetime import datetime

class HavenAPIClient:
    def __init__(self, base_url, api_key, local_db):
        self.base_url = base_url
        self.api_key = api_key
        self.local_db = local_db
        self.offline_queue = []
        self.max_retries = 3
        self.retry_delay = 5  # seconds

    async def check_duplicate(self, glyph_code, galaxy):
        """Check if system already exists in Haven database."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.base_url}/api/check_duplicate",
                    params={'glyph_code': glyph_code, 'galaxy': galaxy},
                    headers={'X-API-Key': self.api_key}
                )

                if response.status_code == 200:
                    return response.json()
                return {'exists': False}
        except httpx.RequestError:
            # Offline - check local database only
            return self.local_db.check_local_duplicate(glyph_code, galaxy)

    async def submit_system(self, system_data):
        """Submit a system to Haven for approval."""
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"{self.base_url}/api/submit_system",
                        json=system_data,
                        headers={'X-API-Key': self.api_key}
                    )

                    if response.status_code == 200:
                        result = response.json()
                        self.local_db.record_upload(
                            glyph_code=system_data['glyph_code'],
                            galaxy=system_data['galaxy'],
                            submission_id=result['submission_id']
                        )
                        return {'success': True, 'submission_id': result['submission_id']}

                    elif response.status_code == 409:
                        # Duplicate - already exists
                        return {'success': False, 'reason': 'duplicate'}

                    else:
                        return {'success': False, 'reason': response.text}

            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    # Queue for later
                    self.queue_offline(system_data)
                    return {'success': False, 'reason': 'offline', 'queued': True}

    def queue_offline(self, system_data):
        """Add to offline queue for later retry."""
        self.offline_queue.append({
            'data': system_data,
            'queued_at': datetime.utcnow().isoformat()
        })
        self.local_db.save_offline_queue(self.offline_queue)

    async def process_offline_queue(self):
        """Try to submit queued items."""
        if not self.offline_queue:
            return

        successful = []
        for item in self.offline_queue:
            result = await self.submit_system(item['data'])
            if result['success'] or result.get('reason') == 'duplicate':
                successful.append(item)

        # Remove successful items from queue
        for item in successful:
            self.offline_queue.remove(item)

        self.local_db.save_offline_queue(self.offline_queue)
```

### 5.6 Local Database (`local_db.py`)

**Responsibilities:**
- Track which discoveries have been uploaded
- Store offline upload queue
- Cache API responses
- Store configuration

**Schema:**
```sql
-- Track uploaded discoveries
CREATE TABLE uploaded_discoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    glyph_code TEXT NOT NULL,
    galaxy TEXT NOT NULL,
    system_name TEXT,
    submission_id INTEGER,
    uploaded_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    UNIQUE(glyph_code, galaxy)
);

-- Offline upload queue
CREATE TABLE offline_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_data TEXT NOT NULL,  -- JSON
    queued_at TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_error TEXT
);

-- Unknown obfuscated keys (for mod updates)
CREATE TABLE unknown_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name TEXT UNIQUE NOT NULL,
    first_seen TEXT NOT NULL,
    context TEXT  -- Where in the save structure it was found
);

-- Configuration
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- API response cache
CREATE TABLE api_cache (
    cache_key TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    cached_at TEXT NOT NULL,
    expires_at TEXT
);
```

### 5.7 Resource Mapper (`resources.py`)

**Responsibilities:**
- Map NMS internal resource IDs to human-readable names
- Match exactly what appears in-game

```python
RESOURCE_MAPPINGS = {
    # Common Elements
    'FUEL1': 'Carbon',
    'FUEL2': 'Condensed Carbon',
    'LAND1': 'Ferrite Dust',
    'LAND2': 'Pure Ferrite',
    'LAND3': 'Magnetised Ferrite',
    'OXYGEN': 'Oxygen',
    'WATER1': 'Salt',
    'ASTEROID1': 'Silver',
    'ASTEROID2': 'Gold',
    'ASTEROID3': 'Platinum',
    'LAUNCHSUB': 'Di-hydrogen',
    'ROCKITE': 'Cobalt',
    'CAVE1': 'Cobalt',
    'CAVE2': 'Ionised Cobalt',

    # Stellar Metals
    'YELLOW': 'Copper',
    'RED': 'Cadmium',
    'GREEN': 'Emeril',
    'BLUE': 'Indium',

    # Trade Commodities
    'TRADEABLE1': 'Sodium',
    'TRADEABLE2': 'Sodium Nitrate',

    # Organic
    'PLANT_POOP': 'Mordite',
    'CREATURE1': 'Mordite',
    'PLANT_TOXIC': 'Fungal Mould',
    'PLANT_SNOW': 'Frost Crystal',
    'PLANT_HOT': 'Solanium',
    'PLANT_RADIO': 'Gamma Root',
    'PLANT_DUST': 'Cactus Flesh',
    'PLANT_LUSH': 'Star Bulb',
    'PLANT_CAVE': 'Marrow Bulb',
    'PLANT_WATER': 'Kelp Sac',

    # Rare
    'DUSTY1': 'Pyrite',
    'LUSH1': 'Paraffinium',
    'TOXIC1': 'Ammonia',
    'RADIO1': 'Uranium',
    'SNOW1': 'Dioxite',
    'HOT1': 'Phosphorus',

    # Ancient
    'FOSSIL1': 'Ancient Bones',
    'TECH_COMP': 'Salvaged Data',

    # ... more mappings to be added
}

def map_resource(internal_id):
    """Convert NMS internal resource ID to display name."""
    return RESOURCE_MAPPINGS.get(internal_id, internal_id)
```

### 5.8 Level Mappers

```python
# Sentinel levels
SENTINEL_MAPPINGS = {
    'None': 'None',
    'Low': 'Low',
    'LowSecurity': 'Low',
    'Normal': 'Medium',
    'NormalSecurity': 'Medium',
    'High': 'High',
    'HighSecurity': 'High',
    'Aggressive': 'Aggressive',
    'Hostile': 'Aggressive',
}

# Fauna/Flora levels (as shown in discovery tab)
LIFE_LEVEL_MAPPINGS = {
    'None': 'None',
    'NotPresent': 'None',
    'Empty': 'None',
    'Low': 'Low',
    'Sparse': 'Sparse',
    'Few': 'Sparse',
    'Fair': 'Average',
    'Average': 'Average',
    'Common': 'Common',
    'Frequent': 'Common',
    'High': 'Abundant',
    'Ample': 'Abundant',
    'Abundant': 'Abundant',
    'Full': 'Abundant',
    'Copious': 'Bountiful',
    'Rich': 'Bountiful',
    'Generous': 'Bountiful',
}

# Economy levels
ECONOMY_LEVEL_MAPPINGS = {
    1: 'Low',      # One star
    2: 'Medium',   # Two stars
    3: 'High',     # Three stars
}

# Conflict levels
CONFLICT_LEVEL_MAPPINGS = {
    1: 'Low',
    2: 'Medium',
    3: 'High',
}

# Star types
STAR_TYPE_MAPPINGS = {
    'Yellow': 'Yellow',
    'Red': 'Red',
    'Green': 'Green',
    'Blue': 'Blue',
    'Purple': 'Purple',  # Exotic
}

# Galaxy names
GALAXY_NAMES = {
    0: 'Euclid',
    1: 'Hilbert Dimension',
    2: 'Calypso',
    3: 'Hesperius Dimension',
    4: 'Hyades',
    5: 'Ickjamatew',
    # ... all 256 galaxies
}
```

### 5.9 Notifications (`notifications.py`)

```python
from win10toast import ToastNotifier
import logging

class NotificationManager:
    def __init__(self):
        self.toaster = ToastNotifier()
        self.logger = logging.getLogger('companion')

    def notify_upload_success(self, system_name, planet_count):
        """Show notification for successful upload."""
        message = f"Uploaded {system_name} with {planet_count} planet(s)"
        self.logger.info(message)
        self.toaster.show_toast(
            "Voyagers Haven - Upload Success",
            message,
            icon_path="assets/icon.ico",
            duration=5
        )

    def notify_duplicate(self, system_name):
        """Show notification for duplicate detection."""
        message = f"{system_name} already exists in database"
        self.logger.info(message)
        self.toaster.show_toast(
            "Voyagers Haven - Duplicate Skipped",
            message,
            icon_path="assets/icon.ico",
            duration=3
        )

    def notify_error(self, error_message):
        """Show notification for errors."""
        self.logger.error(error_message)
        self.toaster.show_toast(
            "Voyagers Haven - Error",
            error_message,
            icon_path="assets/icon.ico",
            duration=5
        )

    def notify_offline_queued(self, system_name):
        """Show notification when queued for offline."""
        message = f"{system_name} queued - will upload when online"
        self.logger.warning(message)
        self.toaster.show_toast(
            "Voyagers Haven - Offline",
            message,
            icon_path="assets/icon.ico",
            duration=3
        )

    def notify_unknown_keys(self, key_count):
        """Alert about unknown obfuscated keys."""
        message = f"Found {key_count} unknown save file keys - mod may need update"
        self.logger.warning(message)
        self.toaster.show_toast(
            "Voyagers Haven - Update May Be Needed",
            message,
            icon_path="assets/icon.ico",
            duration=10
        )
```

---

## 6. Data Structures

### 6.1 System Submission Payload

The companion app will submit systems in this format:

```json
{
    "name": "Oculi",
    "galaxy": "Euclid",
    "star_type": "Yellow",
    "economy_type": "Trading",
    "economy_level": "High",
    "conflict_level": "Low",
    "discovered_by": "OriginalExplorer",
    "discovered_at": "2024-12-01T15:30:00Z",
    "glyph_code": "60720193DFA9",
    "glyph_planet": 6,
    "glyph_solar_system": 114,
    "x": -87,
    "y": 1,
    "z": -1731,
    "region_x": 4009,
    "region_y": 1,
    "region_z": 2365,
    "description": "Auto-discovered by NMS Save Watcher",
    "planets": [
        {
            "name": "Voyager's Haven",
            "climate": "Temperate",
            "sentinel": "Low",
            "fauna": "Abundant",
            "flora": "Bountiful",
            "has_water": 1,
            "materials": "Copper, Cobalt, Star Bulb",
            "base_location": "+42.15, -118.32",
            "moons": [
                {
                    "name": "Haven's Shadow",
                    "climate": "Dusty",
                    "sentinel": "None",
                    "fauna": "Sparse",
                    "flora": "None"
                }
            ]
        }
    ],
    "space_station": null
}
```

### 6.2 Local Discovery Record

```python
@dataclass
class LocalDiscovery:
    glyph_code: str
    galaxy: str
    system_name: str
    planet_count: int
    moon_count: int
    discovered_by: str
    discovered_at: datetime
    uploaded_at: datetime = None
    submission_id: int = None
    status: str = 'pending'  # pending, approved, rejected, failed
    is_edit: bool = False    # True if updating existing system
    original_system_id: str = None  # If edit, the ID being updated
```

### 6.3 Upload Queue Item

```python
@dataclass
class QueuedUpload:
    id: int
    system_data: dict
    queued_at: datetime
    retry_count: int = 0
    last_error: str = None
    is_edit: bool = False
```

---

## 7. NMS Save File Parsing

### 7.1 Save File Structure

NMS save files (`.hg`) have this structure:

```
[4 bytes: header/magic number]
[LZ4 compressed JSON data]
```

After decompression, the JSON has obfuscated keys that need mapping.

### 7.2 Key Discovery Paths in Save

```
Root
├── PlayerStateData
│   ├── UniverseAddress
│   │   ├── RealityIndex (galaxy: 0=Euclid, 1=Hilbert, etc.)
│   │   └── GalacticAddress
│   │       ├── VoxelX
│   │       ├── VoxelY
│   │       ├── VoxelZ
│   │       ├── SolarSystemIndex
│   │       └── PlanetIndex
│   └── PlayerName
│
├── DiscoveryManagerData
│   └── DiscoveryData-v1 (array of discoveries)
│       └── [each discovery]
│           ├── DD (DiscoveryData)
│           │   ├── VP (Name/title)
│           │   ├── DT (Discovery type: system, planet, etc.)
│           │   ├── TS (Timestamp)
│           │   └── ...
│           ├── DM (DiscoveryMetadata)
│           │   ├── UA (Universe address)
│           │   │   ├── RI (Reality Index / Galaxy)
│           │   │   └── GA (Galactic Address)
│           │   │       ├── VX (Voxel X)
│           │   │       ├── VY (Voxel Y)
│           │   │       ├── VZ (Voxel Z)
│           │   │       └── SI (Solar System Index)
│           │   └── PT (Planet type/biome)
│           └── OWS (Ownership/discoverer info)
│               ├── USN (Username)
│               └── UID (User ID)
```

### 7.3 Discovery Types

```python
DISCOVERY_TYPES = {
    'Unknown': 0,
    'SolarSystem': 1,
    'Planet': 2,
    'Moon': 3,         # Treated as planet in data
    'Creature': 4,
    'Flora': 5,
    'Mineral': 6,
    'Waypoint': 7,     # Points of interest
    'Sector': 8,       # Region
}
```

### 7.4 Obfuscated Key Mapping Source

The key mappings will be extracted from the MBINCompiler project or NMSSaveEditor:
- https://github.com/goatfungus/NMSSaveEditor/tree/master/NMSSaveEditor/App_Data

Key mapping file structure:
```json
{
    "F2P": "PlayerStateData",
    "8pG": "UniverseAddress",
    "osr": "RealityIndex",
    "yhJ": "GalacticAddress",
    "dZj": "VoxelX",
    "IyE": "VoxelY",
    "uXE": "VoxelZ",
    "vby": "SolarSystemIndex",
    "jsw": "PlanetIndex",
    "fEQ": "DiscoveryManagerData",
    "ETO": "DiscoveryData-v1",
    // ... hundreds more mappings
}
```

---

## 8. Web Dashboard

### 8.1 Dashboard Features

The web dashboard will run on `http://localhost:8006` with these pages:

#### Home / Status Page
- Current watcher status (Running/Stopped/Error)
- Save file being monitored
- API connection status
- Last save file change detected
- Last successful upload

#### Upload History
- Table of all uploaded systems
- Columns: System Name, Galaxy, Planets, Uploaded At, Status
- Status badges: Pending (yellow), Approved (green), Rejected (red)
- Filter by status
- Search by name

#### Pending Queue
- Items waiting to upload (offline queue)
- Retry button for failed items
- Clear queue button

#### Save File Stats
- Total systems in save file
- Total planets discovered
- Total moons discovered
- Systems by galaxy breakdown
- Your discoveries vs others' discoveries

#### Settings
- API endpoint URL
- API key (masked with reveal button)
- Save file path (auto-detected, can override)
- Notification preferences
- Debug mode toggle

#### Unknown Keys Log
- List of unrecognized obfuscated keys
- Context where they were found
- Export button for bug reports

### 8.2 Dashboard Theme

Will match Haven-UI theme:
- Dark background (#0f172a or similar)
- Cyan/teal accent colors
- Space/star map aesthetic
- Same fonts and styling patterns

### 8.3 Dashboard Routes

```python
# FastAPI routes
GET  /                     # Home/status page
GET  /history              # Upload history
GET  /queue                # Offline queue
GET  /stats                # Save file statistics
GET  /settings             # Configuration
GET  /keys                 # Unknown keys log

# API endpoints for dashboard
GET  /api/status           # Watcher status
GET  /api/history          # Uploaded discoveries list
GET  /api/queue            # Offline queue items
POST /api/queue/{id}/retry # Retry specific item
DELETE /api/queue/{id}     # Remove from queue
GET  /api/stats            # Save file stats
GET  /api/config           # Current configuration
POST /api/config           # Update configuration
POST /api/watcher/start    # Start file watcher
POST /api/watcher/stop     # Stop file watcher
```

---

## 9. Duplicate Detection Strategy

### 9.1 Multi-Layer Duplicate Checking

```
┌─────────────────────────────────────────────────────────────┐
│                   Duplicate Detection Flow                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  New Discovery Detected                                      │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                       │
│  │ Local DB Check   │◀── Check uploaded_discoveries table   │
│  │ (glyph + galaxy) │                                       │
│  └────────┬─────────┘                                       │
│           │                                                  │
│           ├─── FOUND ──▶ Skip (already uploaded)            │
│           │                                                  │
│           ▼ NOT FOUND                                       │
│  ┌──────────────────┐                                       │
│  │ API Check        │◀── GET /api/check_duplicate           │
│  │ (glyph + galaxy) │                                       │
│  └────────┬─────────┘                                       │
│           │                                                  │
│           ├─── EXISTS in 'approved' ──▶ Check for edits     │
│           │         │                                        │
│           │         ▼                                        │
│           │    ┌──────────────────┐                         │
│           │    │ Compare Data     │                         │
│           │    │ (name changed?)  │                         │
│           │    └────────┬─────────┘                         │
│           │             │                                    │
│           │             ├─── SAME ──▶ Skip                  │
│           │             │                                    │
│           │             └─── DIFFERENT ──▶ Submit as Edit   │
│           │                                                  │
│           ├─── EXISTS in 'pending' ──▶ Skip (already queued)│
│           │                                                  │
│           └─── NOT EXISTS ──▶ Submit as New                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Unique Identifier

**Primary Key:** `glyph_code + galaxy`

- Glyph code encodes: region coordinates + solar system index + planet index
- Same glyph in different galaxies = different systems
- System names can change but coordinates never do

### 9.3 Edit Detection

When a system exists but data has changed:
```python
def check_for_edits(existing_system, new_data):
    """Detect if new scan has different data than existing."""
    changes = {}

    # Check system-level changes
    if existing_system['name'] != new_data['name']:
        changes['name'] = {
            'old': existing_system['name'],
            'new': new_data['name']
        }

    # Check for new planets
    existing_planets = {p['name'] for p in existing_system.get('planets', [])}
    new_planets = {p['name'] for p in new_data.get('planets', [])}

    if new_planets - existing_planets:
        changes['new_planets'] = list(new_planets - existing_planets)

    return changes if changes else None
```

---

## 10. Error Handling

### 10.1 Error Categories

| Category | Handling | User Notification |
|----------|----------|-------------------|
| Save file not found | Retry detection every 30s | Dashboard warning |
| LZ4 decompression failed | Log error, skip this save | Toast + dashboard error |
| Malformed JSON | Log error, skip this save | Toast + dashboard error |
| Unknown obfuscated keys | Continue with known keys | Dashboard alert |
| Network offline | Queue uploads | Toast notification |
| API rate limit exceeded | Wait and retry | Dashboard status |
| API authentication failed | Stop uploads, alert user | Toast + dashboard error |
| Duplicate submission (409) | Skip, mark as known | Log only (not error) |

### 10.2 Retry Logic

```python
class RetryConfig:
    max_retries = 3
    base_delay = 5  # seconds
    max_delay = 300  # 5 minutes
    exponential_base = 2

    @classmethod
    def get_delay(cls, attempt):
        """Exponential backoff with max cap."""
        delay = cls.base_delay * (cls.exponential_base ** attempt)
        return min(delay, cls.max_delay)
```

### 10.3 Offline Queue Processing

```python
async def process_offline_queue():
    """Periodically try to submit queued items."""
    while True:
        await asyncio.sleep(60)  # Check every minute

        if not await check_api_available():
            continue

        queue_items = local_db.get_offline_queue()
        for item in queue_items:
            result = await api_client.submit_system(item.system_data)

            if result['success']:
                local_db.remove_from_queue(item.id)
                notify.notify_upload_success(item.system_data['name'])
            elif result.get('reason') == 'duplicate':
                local_db.remove_from_queue(item.id)
            else:
                local_db.increment_retry_count(item.id, result.get('reason'))
```

---

## 11. File Structure

```
NMS-Save-Watcher/
│
├── src/
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── watcher.py              # File system watcher
│   ├── parser.py               # LZ4 decompression + JSON parsing
│   ├── extractor.py            # Discovery data extraction
│   ├── glyph.py                # Coordinate/glyph conversion (uses API)
│   ├── api_client.py           # Haven API integration
│   ├── local_db.py             # SQLite database management
│   ├── resources.py            # Resource ID mappings
│   ├── mappings.py             # Level/type mappings
│   ├── notifications.py        # Windows toast notifications
│   └── config.py               # Configuration management
│
├── web/
│   ├── __init__.py
│   ├── app.py                  # FastAPI dashboard server
│   ├── routes.py               # Dashboard API routes
│   ├── static/
│   │   ├── css/
│   │   │   └── dashboard.css   # Haven-UI theme styling
│   │   ├── js/
│   │   │   └── dashboard.js    # Frontend JavaScript
│   │   └── img/
│   │       └── icon.ico        # App icon
│   └── templates/
│       ├── base.html           # Base template
│       ├── index.html          # Home/status page
│       ├── history.html        # Upload history
│       ├── queue.html          # Offline queue
│       ├── stats.html          # Save statistics
│       ├── settings.html       # Configuration
│       └── keys.html           # Unknown keys log
│
├── data/
│   ├── key_mappings.json       # Obfuscated key → real key mappings
│   ├── resources.json          # Resource ID → human name
│   ├── galaxies.json           # Galaxy index → name
│   ├── biomes.json             # Biome type mappings
│   └── watcher.db              # Local SQLite database
│
├── assets/
│   └── icon.ico                # Application icon
│
├── config.json                 # User configuration
├── start.bat                   # Windows launcher
├── requirements.txt            # Python dependencies
├── build.py                    # PyInstaller build script
└── README.md                   # User documentation
```

---

## 12. Implementation Phases

### Phase 1: Backend Modifications (Voyagers Haven)
**Estimated scope: ~200-300 lines of code changes**

1. Create `api_keys` table migration
2. Add new columns to `systems` table (star_type, economy_type, etc.)
3. Add `source` and `api_key_name` columns to `pending_systems`
4. Implement API key authentication middleware
5. Create `/api/keys` endpoints (create, list, revoke)
6. Create `/api/check_duplicate` endpoint
7. Modify `/api/submit_system` to accept new fields and API key auth
8. Update rate limiting to use API key limits
9. Test all new endpoints

### Phase 2: Core Companion App
**Estimated scope: ~500-700 lines of code**

1. Set up project structure and dependencies
2. Implement save path auto-detection
3. Implement file watcher with debouncing
4. Research and implement LZ4 decompression
5. Obtain/create key mapping file
6. Implement JSON deobfuscation
7. Implement discovery extraction logic
8. Create local SQLite database schema
9. Implement API client with retry logic
10. Implement offline queue
11. Test parsing with real save files

### Phase 3: Data Processing
**Estimated scope: ~300-400 lines of code**

1. Create resource ID mapping table
2. Create level mapping tables (sentinel, fauna, flora, economy, conflict)
3. Create galaxy name mapping
4. Implement base location extraction
5. Implement glyph conversion via API
6. Implement duplicate detection logic
7. Implement edit detection
8. Test data extraction accuracy

### Phase 4: Web Dashboard
**Estimated scope: ~400-500 lines of code (Python) + ~300 lines HTML/CSS/JS**

1. Set up FastAPI dashboard server
2. Create base template with Haven-UI theme
3. Implement home/status page
4. Implement upload history page
5. Implement offline queue page
6. Implement save statistics page
7. Implement settings page
8. Implement unknown keys log page
9. Create dashboard API endpoints
10. Add real-time status updates (polling or WebSocket)

### Phase 5: Notifications & Polish
**Estimated scope: ~100-150 lines of code**

1. Implement Windows toast notifications
2. Create application icon
3. Create `start.bat` launcher
4. Add comprehensive logging
5. Add configuration validation
6. Handle edge cases and error scenarios

### Phase 6: Packaging & Documentation
1. Create PyInstaller build script
2. Build standalone .exe
3. Write user documentation (README)
4. Create configuration guide
5. Test on clean Windows install

---

## 13. Resource Mappings

### 13.1 Complete Resource ID → Name Mapping

This will be stored in `data/resources.json`:

```json
{
    "elements": {
        "FUEL1": "Carbon",
        "FUEL2": "Condensed Carbon",
        "LAND1": "Ferrite Dust",
        "LAND2": "Pure Ferrite",
        "LAND3": "Magnetised Ferrite",
        "OXYGEN": "Oxygen",
        "CATALYST1": "Sodium",
        "CATALYST2": "Sodium Nitrate",
        "LAUNCHSUB": "Di-hydrogen",
        "LAUNCHSUB2": "Di-hydrogen Jelly",
        "ROCKITE": "Cobalt",
        "CAVE1": "Cobalt",
        "CAVE2": "Ionised Cobalt",
        "WATER1": "Salt",
        "WATER2": "Chlorine",
        "ASTEROID1": "Silver",
        "ASTEROID2": "Gold",
        "ASTEROID3": "Platinum",
        "YELLOW": "Copper",
        "YELLOW2": "Chromatic Metal",
        "RED": "Cadmium",
        "GREEN": "Emeril",
        "BLUE": "Indium",
        "DUSTY1": "Pyrite",
        "LUSH1": "Paraffinium",
        "TOXIC1": "Ammonia",
        "RADIO1": "Uranium",
        "SNOW1": "Dioxite",
        "HOT1": "Phosphorus",
        "PLANT_POOP": "Mordite",
        "CREATURE1": "Mordite",
        "PLANT_TOXIC": "Fungal Mould",
        "PLANT_SNOW": "Frost Crystal",
        "PLANT_HOT": "Solanium",
        "PLANT_RADIO": "Gamma Root",
        "PLANT_DUST": "Cactus Flesh",
        "PLANT_LUSH": "Star Bulb",
        "PLANT_CAVE": "Marrow Bulb",
        "PLANT_WATER": "Kelp Sac",
        "FOSSIL1": "Ancient Bones",
        "ALLOY1": "Herox",
        "ALLOY2": "Aronium",
        "ALLOY3": "Lemmium",
        "ALLOY4": "Dirty Bronze",
        "ALLOY5": "Grantine",
        "ALLOY6": "Magno-Gold"
    },
    "special": {
        "SALVAGE1": "Salvaged Data",
        "TECH_COMP": "Salvaged Data",
        "NANITES": "Nanite Cluster",
        "QUICKSILVER": "Quicksilver",
        "UNITS": "Units",
        "STORM_CRYSTAL": "Storm Crystals",
        "LARVAL_CORE": "Larval Core"
    }
}
```

### 13.2 Complete Galaxy Index → Name Mapping

This will be stored in `data/galaxies.json`:

```json
{
    "0": "Euclid",
    "1": "Hilbert Dimension",
    "2": "Calypso",
    "3": "Hesperius Dimension",
    "4": "Hyades",
    "5": "Ickjamatew",
    "6": "Budullangr",
    "7": "Kikolgallr",
    "8": "Eltiensleen",
    "9": "Eissentam",
    "10": "Elkupalos"
    // ... continues to 255
}
```

Full list available at: https://nomanssky.fandom.com/wiki/Galaxy

---

## 14. API Endpoints Summary

### 14.1 New Backend Endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| POST | `/api/keys` | Admin session | Create new API key |
| GET | `/api/keys` | Admin session | List all API keys |
| DELETE | `/api/keys/{id}` | Admin session | Revoke API key |
| GET | `/api/check_duplicate` | API key | Check if system exists |

### 14.2 Modified Backend Endpoints

| Method | Endpoint | Change |
|--------|----------|--------|
| POST | `/api/submit_system` | Accept API key auth, new fields, source tracking |

### 14.3 Companion App Dashboard Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Home/status page |
| GET | `/history` | Upload history page |
| GET | `/queue` | Offline queue page |
| GET | `/stats` | Save statistics page |
| GET | `/settings` | Configuration page |
| GET | `/keys` | Unknown keys log page |
| GET | `/api/status` | Get watcher status |
| GET | `/api/history` | Get upload history |
| GET | `/api/queue` | Get offline queue |
| POST | `/api/queue/{id}/retry` | Retry queued item |
| DELETE | `/api/queue/{id}` | Remove from queue |
| GET | `/api/stats` | Get save statistics |
| GET | `/api/config` | Get configuration |
| POST | `/api/config` | Update configuration |
| POST | `/api/watcher/start` | Start file watcher |
| POST | `/api/watcher/stop` | Stop file watcher |

---

## 15. Configuration

### 15.1 config.json Structure

```json
{
    "api": {
        "base_url": "http://localhost:8005",
        "key": "vh_live_xxxxxxxxxxxxxxxx"
    },
    "watcher": {
        "save_path": "auto",
        "save_slot": 1,
        "debounce_seconds": 2,
        "enabled": true
    },
    "notifications": {
        "enabled": true,
        "on_success": true,
        "on_duplicate": false,
        "on_error": true,
        "on_offline_queue": true
    },
    "dashboard": {
        "port": 8006,
        "host": "127.0.0.1"
    },
    "debug": {
        "enabled": false,
        "log_file": "watcher.log",
        "log_level": "INFO"
    }
}
```

### 15.2 Environment Variables (Optional Overrides)

```bash
HAVEN_API_URL=http://localhost:8005
HAVEN_API_KEY=vh_live_xxxxxxxx
NMS_SAVE_PATH=C:\Users\...\HelloGames\NMS\st_xxxxx
WATCHER_DEBUG=true
```

---

## 16. Testing Strategy

### 16.1 Backend Tests

1. **API Key Tests**
   - Create key and verify hash stored correctly
   - Authenticate with valid key
   - Reject invalid key
   - Reject expired/disabled key
   - Rate limiting per key

2. **Duplicate Check Tests**
   - Return exists=true for known glyph
   - Return exists=false for unknown glyph
   - Correctly identify pending vs approved
   - Handle different galaxies correctly

3. **Submission Tests**
   - Accept new fields (star_type, economy_type, etc.)
   - Track source correctly
   - Track API key name correctly

### 16.2 Companion App Tests

1. **Parser Tests**
   - Decompress valid .hg file
   - Handle corrupted file gracefully
   - Deobfuscate known keys correctly
   - Flag unknown keys

2. **Extractor Tests**
   - Extract system data correctly
   - Extract planet data correctly
   - Extract moon data correctly
   - Map resources correctly
   - Map levels correctly

3. **Integration Tests**
   - End-to-end: save file → API submission
   - Duplicate detection flow
   - Offline queue and retry
   - Edit detection

### 16.3 Test Data

Create mock save file data for testing without needing actual NMS:
- Sample compressed save file
- Sample decompressed JSON
- Known key mappings
- Expected output

---

## Appendix A: NMS Save Editor References

### Useful Repositories

1. **NMSSaveEditor** (Java)
   - https://github.com/goatfungus/NMSSaveEditor
   - Key mappings: `/App_Data/mapping.json`
   - Save format documentation

2. **NomNom** (C#)
   - https://github.com/zencq/NomNom
   - Comprehensive save editor
   - libNOM library for save parsing

3. **NMS-Base-File-Editor** (Python)
   - https://github.com/NightCodeOfficial/NMS-Base-File-Editor
   - Python LZ4 decompression example

4. **MBINCompiler**
   - https://github.com/monkeyman192/MBINCompiler
   - MBIN → JSON conversion
   - Game file extraction

### Save File Format Notes

- Header is 4 bytes (may vary by version)
- LZ4 frame format (not block format)
- JSON uses Unicode encoding
- Timestamps are NMS-specific format
- Some values are bitfields/flags

---

## Appendix B: Implementation Notes

### Steam ID Detection

```python
def find_steam_id_folder():
    """Find the st_xxxxx folder containing saves."""
    import os
    import re

    appdata = os.environ.get('APPDATA')
    nms_path = os.path.join(appdata, 'HelloGames', 'NMS')

    if not os.path.exists(nms_path):
        return None

    for folder in os.listdir(nms_path):
        if re.match(r'^st_\d+$', folder):
            full_path = os.path.join(nms_path, folder)
            if os.path.isdir(full_path):
                # Verify save files exist
                if os.path.exists(os.path.join(full_path, 'save.hg')):
                    return full_path

    return None
```

### Save Slot Mapping

```python
SAVE_SLOTS = {
    1: 'save.hg',      # Auto-save slot 1
    2: 'save2.hg',     # Manual save slot 1
    3: 'save3.hg',     # Auto-save slot 2
    4: 'save4.hg',     # Manual save slot 2
    5: 'save5.hg',     # Auto-save slot 3
    # ... etc
}
```

### PyInstaller Spec

```python
# build.spec
a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('data/*.json', 'data'),
        ('web/templates/*.html', 'web/templates'),
        ('web/static/*', 'web/static'),
        ('assets/*', 'assets'),
    ],
    hiddenimports=['uvicorn', 'fastapi', 'jinja2'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='NMS-Save-Watcher',
    debug=False,
    strip=False,
    upx=True,
    console=True,  # Show console for logging
    icon='assets/icon.ico',
)
```

---

## Summary

This companion app will:

1. **Watch** NMS save files for stellar scanner discoveries
2. **Parse** LZ4 compressed saves with obfuscated JSON
3. **Extract** system, planet, moon, and base data
4. **Check** for duplicates using glyph + galaxy coordinates
5. **Submit** to Voyagers Haven API as pending approval
6. **Queue** uploads when offline, retry automatically
7. **Notify** via console and Windows toasts
8. **Dashboard** on port 8006 matching Haven-UI theme
9. **Package** as standalone .exe for distribution

The backend will be enhanced with:
- API key authentication system
- New schema fields for star type, economy, conflict
- Source tracking for submissions
- Duplicate checking endpoint

Total estimated code:
- Backend modifications: ~300 lines
- Companion app core: ~1500 lines
- Web dashboard: ~500 lines (Python) + ~400 lines (HTML/CSS/JS)
- Configuration/data files: ~500 lines

Ready to proceed with implementation in phases.
