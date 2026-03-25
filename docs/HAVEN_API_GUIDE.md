# Haven API Integration Guide

**For Discord Bot Developers** | Base URL: `https://havenmap.online`

---

## Authentication

All authenticated requests use the `X-API-Key` header:

```
X-API-Key: vh_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

Your API key has permissions for `submit` and `check_duplicate`. Public/read endpoints don't need a key at all.

### Getting an API Key

Register a personal key (one-time, returns key only once):

```
POST /api/extractor/register
Content-Type: application/json

{
    "discord_username": "StarBot"
}
```

**Response:**
```json
{
    "status": "registered",
    "key": "vh_live_xxxxxxxxxxxxxxxxxxxxxxxx",
    "key_prefix": "vh_live_xxxxxxxx",
    "discord_username": "StarBot",
    "profile_id": 42,
    "rate_limit": 100,
    "message": "Save this key now — it cannot be retrieved later!"
}
```

> Save the `key` immediately. It cannot be retrieved again. If lost, contact an admin.

---

## Read Endpoints (No Auth Required)

These are all public. Great for bot lookup commands.

### Quick Stats

```
GET /api/stats
```

Returns total systems, planets, moons, discoveries, pending counts, etc.

---

### Search Systems

```
GET /api/systems/search?q=Paradise&limit=10
```

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `q` | string | **Required.** Searches system name, glyph code, galaxy, description |
| `limit` | int | Max results (default 20, max 50) |

**Response:**
```json
{
    "results": [
        {
            "id": "abc-123",
            "name": "Paradise Found",
            "glyph_code": "0123456789AB",
            "galaxy": "Euclid",
            "reality": "Normal",
            "star_type": "Yellow",
            "economy_type": "Trading",
            "conflict_level": "Low",
            "dominant_lifeform": "Gek",
            "planet_count": 4,
            "completeness_score": 87,
            "completeness_grade": "S",
            "region_name": "Galactic Hub",
            "discord_tag": "Haven"
        }
    ],
    "total": 1,
    "query": "Paradise"
}
```

---

### List Systems (Paginated, Filterable)

```
GET /api/systems?galaxy=Euclid&reality=Normal&page=1&limit=50
```

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `reality` | string | `Normal` or `Permadeath` |
| `galaxy` | string | Galaxy name (e.g., `Euclid`, `Hilbert Dimension`) |
| `discord_tag` | string | Community tag (e.g., `Haven`, `IEA`, `personal`) |
| `page` | int | Page number, 1-indexed (default 1) |
| `limit` | int | Per page (default 50, max 500) |
| `include_planets` | bool | Include nested planet data (default false) |
| `star_type` | string | `Yellow`, `Red`, `Green`, `Blue`, `Purple` |
| `economy_type` | string | `Trading`, `Mining`, `Technology`, etc. |
| `conflict_level` | string | `Low`, `Medium`, `High`, `Pirate` |
| `dominant_lifeform` | string | `Gek`, `Korvax`, `Vy'keen` |
| `biome` | string | Planet biome filter (e.g., `Lush`, `Toxic`) |
| `weather` | string | Planet weather filter |
| `sentinel_level` | string | Planet sentinel filter |
| `resource` | string | Planet resource filter |
| `has_moons` | bool | Only systems with moons |
| `min_planets` | int | Minimum planet count |
| `max_planets` | int | Maximum planet count |

**Response:**
```json
{
    "systems": [ ... ],
    "pagination": {
        "page": 1,
        "limit": 50,
        "total": 312,
        "pages": 7
    },
    "filters": { ... }
}
```

---

### Get System Detail

```
GET /api/systems/{system_id}
```

Returns full system with nested planets, moons, space station, completeness breakdown, region info, and contributors.

---

### Recent Systems

```
GET /api/systems/recent?limit=10
```

Returns the most recently added/modified systems.

---

### Browse Discoveries

```
GET /api/discoveries/browse?type=fauna&q=&sort=newest&page=0&limit=24
```

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `type` | string | Type slug: `fauna`, `flora`, `mineral`, `starship`, `multi-tool`, `freighter`, `frigate`, `base`, `settlement`, `bones`, `ruins` |
| `q` | string | Search name/description |
| `sort` | string | `newest`, `oldest`, `name`, `views` |
| `discoverer` | string | Filter by discoverer name |
| `page` | int | 0-indexed page |
| `limit` | int | Per page (max 100) |

---

### Community Stats (Public)

```
GET /api/public/community-overview     # Per-community stats with totals
GET /api/public/contributors           # Ranked contributors (optional ?community=Haven)
GET /api/public/activity-timeline      # Systems + discoveries over time
GET /api/public/discovery-breakdown    # Discovery counts by type
GET /api/public/community-regions?discord_tag=Haven  # Regions for a community
```

---

### Galaxy & Region Data

```
GET /api/galaxies/summary              # All galaxies with system counts + grade distribution
GET /api/realities/summary             # Normal vs Permadeath breakdown
GET /api/regions/grouped?reality=Normal&galaxy=Euclid&page=1&limit=50
GET /api/regions/{rx}/{ry}/{rz}?reality=Normal&galaxy=Euclid
GET /api/communities                   # List of partner communities
```

---

## Glyph Utilities (No Auth Required)

### Decode Glyph to Coordinates

```
POST /api/decode_glyph
Content-Type: application/json

{"glyph": "0123456789AB"}
```

**Response:**
```json
{
    "x": ...,
    "y": ...,
    "z": ...,
    "planet": 0,
    "solar_system": ...,
    "region_x": ...,
    "region_y": ...,
    "region_z": ...
}
```

### Encode Coordinates to Glyph

```
POST /api/encode_glyph
Content-Type: application/json

{"x": 500, "y": -50, "z": -1200, "planet": 0, "solar_system": 1}
```

**Response:**
```json
{
    "glyph": "0-001-4E-350-9F4",
    "glyph_raw": "00014E3509F4"
}
```

### Validate Glyph Code

```
POST /api/validate_glyph
Content-Type: application/json

{"glyph": "0123456789AB"}
```

**Response:**
```json
{"valid": true, "warning": null}
```

---

## Write Endpoints (API Key Required)

### Check if a System Already Exists

```
GET /api/check_duplicate?glyph_code=0123456789AB&galaxy=Euclid&reality=Normal
X-API-Key: vh_live_xxx
```

**Response:**
```json
{"exists": false}
```
or
```json
{
    "exists": true,
    "location": "approved",
    "system_id": "abc-123",
    "system_name": "Paradise Found"
}
```

### Batch Duplicate Check

```
POST /api/check_glyph_codes
Content-Type: application/json
X-API-Key: vh_live_xxx

{
    "glyph_codes": ["0123456789AB", "111111111111", "222222222222"],
    "galaxy": "Euclid",
    "reality": "Normal"
}
```

**Response:**
```json
{
    "results": {
        "0123456789AB": {"status": "available", "exists": false},
        "111111111111": {"status": "already_charted", "exists": true, "location": "approved", "system_id": "...", "system_name": "..."},
        "222222222222": {"status": "pending_review", "exists": true, "location": "pending", "submission_id": 5, "system_name": "..."}
    },
    "summary": {"available": 1, "already_charted": 1, "pending_review": 1, "total": 3}
}
```

---

### Submit a System (Goes to Approval Queue)

This does NOT create a system directly. It lands in the pending queue for an admin/partner to review and approve.

```
POST /api/extraction
Content-Type: application/json
X-API-Key: vh_live_xxx

{
    "glyph_code": "0123456789AB",
    "system_name": "Paradise Found",
    "galaxy_name": "Euclid",
    "reality": "Normal",
    "star_type": "Yellow",
    "economy_type": "Trading",
    "economy_strength": "Wealthy",
    "conflict_level": "Low",
    "dominant_lifeform": "Gek",
    "discord_username": "SubmitterName",
    "discord_tag": "Haven",
    "voxel_x": 100,
    "voxel_y": 50,
    "voxel_z": -200,
    "solar_system_index": 123,
    "planets": [
        {
            "planet_index": 0,
            "planet_name": "Green Paradise",
            "biome": "Lush",
            "weather": "Pleasant",
            "sentinel_level": "Low",
            "flora_level": "High",
            "fauna_level": "Medium",
            "planet_size": "Large",
            "common_resource": "Copper",
            "uncommon_resource": "Star Bulb",
            "rare_resource": "Gold",
            "is_moon": false
        },
        {
            "planet_index": 1,
            "planet_name": "Tiny Moon",
            "biome": "Barren",
            "weather": "Clear",
            "sentinel_level": "Low",
            "flora_level": "None",
            "fauna_level": "None",
            "planet_size": "Small",
            "is_moon": true
        }
    ]
}
```

**Key fields:**
| Field | Required | Notes |
|-------|----------|-------|
| `glyph_code` | Yes | 12 hex chars (portal address) |
| `system_name` | Yes | Falls back to `System_{glyph_code}` |
| `galaxy_name` | No | Default: `Euclid` |
| `reality` | No | Default: `Normal` |
| `discord_username` | Yes | Who submitted it |
| `discord_tag` | Yes | Community tag (e.g., `Haven`, `IEA`, or `personal`) |
| `star_type` | No | `Yellow`, `Red`, `Green`, `Blue`, `Purple` |
| `economy_type` | No | `Trading`, `Mining`, `Technology`, etc. |
| `economy_strength` | No | `Low`, `Medium`, `High` (economy tier) |
| `conflict_level` | No | `Low`, `Medium`, `High`, `Pirate` |
| `dominant_lifeform` | No | `Gek`, `Korvax`, `Vy'keen` |
| `planets` | No | Array of planet objects |

**Planet fields:**
| Field | Notes |
|-------|-------|
| `planet_index` | 0-based index |
| `planet_name` | Planet/moon name |
| `biome` | `Lush`, `Toxic`, `Scorched`, `Frozen`, `Barren`, `Dead`, `Exotic`, `Marsh`, `Volcanic`, etc. |
| `weather` | Weather adjective |
| `sentinel_level` | Sentinel adjective |
| `flora_level` | Flora adjective |
| `fauna_level` | Fauna adjective |
| `common_resource` | e.g., `Copper`, `Paraffinium` |
| `uncommon_resource` | e.g., `Star Bulb`, `Frost Crystal` |
| `rare_resource` | e.g., `Gold`, `Emeril` |
| `is_moon` | `true` if moon, `false` if planet |

---

### Submit a Discovery (Goes to Approval Queue)

No API key needed, but `discord_username` and `discord_tag` are required.

```
POST /api/submit_discovery
Content-Type: application/json

{
    "discovery_name": "Giant Beetle",
    "discovery_type": "Fauna",
    "system_id": "abc-123",
    "planet_id": 5,
    "location_type": "Planet",
    "discord_username": "SubmitterName",
    "discord_tag": "Haven",
    "description": "A massive beetle found near the coast",
    "type_metadata": {
        "species": "Beetle",
        "biome": "Lush",
        "behavior": "Passive"
    }
}
```

**Required fields:** `discovery_name`, `system_id`, `discord_username`, `discord_tag`

**Discovery types:** `Fauna`, `Flora`, `Mineral`, `Starship`, `Multi-Tool`, `Freighter`, `Frigate`, `Base`, `Settlement`, `Bones`, `Ruins`

---

### Submit a Region Name

```
POST /api/regions/{rx}/{ry}/{rz}/submit
Content-Type: application/json

{
    "proposed_name": "The Frontier",
    "submitted_by": "SubmitterName",
    "personal_discord_username": "SubmitterName",
    "reality": "Normal",
    "galaxy": "Euclid"
}
```

---

## Python Examples (aiohttp)

### Basic Lookup Command

```python
import aiohttp

BASE_URL = "https://havenmap.online"
API_KEY = "vh_live_xxxxxxxxxxxxxxxxxxxxxxxx"

async def search_system(query: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BASE_URL}/api/systems/search",
            params={"q": query, "limit": 5}
        ) as resp:
            data = await resp.json()
            return data["results"]

async def get_system_detail(system_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/systems/{system_id}") as resp:
            return await resp.json()

async def check_duplicate(glyph_code: str, galaxy="Euclid", reality="Normal"):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BASE_URL}/api/check_duplicate",
            params={"glyph_code": glyph_code, "galaxy": galaxy, "reality": reality},
            headers={"X-API-Key": API_KEY}
        ) as resp:
            return await resp.json()

async def decode_glyph(glyph_code: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/decode_glyph",
            json={"glyph": glyph_code}
        ) as resp:
            return await resp.json()

async def get_community_stats():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/public/community-overview") as resp:
            return await resp.json()
```

### Submit a System via Bot

```python
async def submit_system(system_data: dict):
    """Submit system to Haven. Goes to approval queue."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/extraction",
            json=system_data,
            headers={"X-API-Key": API_KEY}
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            else:
                error = await resp.json()
                raise Exception(f"Submit failed: {error.get('detail', resp.status)}")
```

### discord.py Slash Command Example

```python
import discord
from discord import app_commands

@app_commands.command(name="lookup", description="Look up a system in Haven")
@app_commands.describe(query="System name or glyph code")
async def lookup(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    results = await search_system(query)

    if not results:
        await interaction.followup.send(f"No systems found for **{query}**")
        return

    system = results[0]
    embed = discord.Embed(
        title=system["name"],
        color=0x00ffcc
    )
    embed.add_field(name="Galaxy", value=system.get("galaxy", "Unknown"), inline=True)
    embed.add_field(name="Star Type", value=system.get("star_type", "Unknown"), inline=True)
    embed.add_field(name="Economy", value=system.get("economy_type", "Unknown"), inline=True)
    embed.add_field(name="Conflict", value=system.get("conflict_level", "Unknown"), inline=True)
    embed.add_field(name="Lifeform", value=system.get("dominant_lifeform", "Unknown"), inline=True)
    embed.add_field(name="Grade", value=system.get("completeness_grade", "?"), inline=True)

    if system.get("glyph_code"):
        embed.add_field(name="Glyphs", value=f"`{system['glyph_code']}`", inline=False)
    if system.get("region_name"):
        embed.add_field(name="Region", value=system["region_name"], inline=True)
    if system.get("discord_tag"):
        embed.add_field(name="Community", value=system["discord_tag"], inline=True)

    embed.set_footer(text=f"Planets: {system.get('planet_count', '?')} | Score: {system.get('completeness_score', '?')}%")

    await interaction.followup.send(embed=embed)
```

---

## Bot Command Ideas

| Command | Endpoint | Description |
|---------|----------|-------------|
| `/lookup <name>` | `GET /api/systems/search` | Search systems by name or glyphs |
| `/system <id>` | `GET /api/systems/{id}` | Full system detail |
| `/glyphs <code>` | `POST /api/decode_glyph` | Decode portal glyphs to coordinates |
| `/encode <x> <y> <z>` | `POST /api/encode_glyph` | Encode coordinates to glyphs |
| `/check <glyphs>` | `GET /api/check_duplicate` | Check if glyphs are already charted |
| `/stats` | `GET /api/stats` | Database totals |
| `/community` | `GET /api/public/community-overview` | Community leaderboard |
| `/leaderboard` | `GET /api/public/contributors` | Top contributors |
| `/recent` | `GET /api/systems/recent` | Latest systems added |
| `/discoveries <type>` | `GET /api/discoveries/browse` | Browse discoveries |
| `/submit` | `POST /api/extraction` | Submit a system (needs API key) |

---

## Important Notes

1. **Submissions go to a queue.** Nothing submitted via API is immediately visible. A community admin must approve it first.
2. **Rate limit is 100 requests/hour** per API key (configurable by admin).
3. **No auth needed for reads.** All browse/search/stats endpoints are fully public.
4. **API key is for writes only:** duplicate checks and system submissions.
5. **Glyph codes are 12 hex characters** (e.g., `0123456789AB`). The first character is the planet index.
6. **`discord_tag`** identifies which community the submission belongs to. Use the exact tag string (e.g., `Haven`, `IEA`, `B.E.S`). Get the list from `GET /api/communities`.
7. **Responses are JSON.** Errors return `{"detail": "error message"}` with appropriate HTTP status codes (400, 401, 403, 404, 500).

---

## Error Codes

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad request (missing/invalid fields) |
| 401 | API key missing or invalid |
| 403 | API key lacks required permission, or account suspended |
| 404 | Resource not found |
| 409 | Conflict (duplicate glyph code) |
| 500 | Server error |

---

*Haven API v1.47.0 | Last updated: 2026-03-22*
