# Keeper → Haven: Create-Tab & Map API Reference

Everything the Keeper needs to build a friendly "add a system" / "look up a system"
flow that mirrors Haven's web **Create** tab and 3D **Map** — auto-naming, the
curated dropdown lists, region naming, glyph tools, and map deep-links.

All of these are **backend-owned**: Haven does the decoding, naming, dedup, and
URL-building. Keeper calls one endpoint per feature and renders the result.

---

## 0. Conventions (read once)

**Two base URLs — you already have both in `.env`:**

| Var | Value (prod) | Use for |
|---|---|---|
| `HAVEN_API` | `http://haven:8005` (internal docker) | **API calls** (this doc) |
| `HAVEN_PUBLIC_URL` | `https://havenmap.online` | **user-facing links** you put in embeds |

> ⚠️ **Never put `HAVEN_API` in a link you send to Discord** — `http://haven:8005`
> isn't routable from a user's browser and Discord rejects the embed with
> `400 Not a well formed URL`. Any endpoint below that returns a `*_url` field
> returns it **relative** (`/map/system/…`); prefix it with `HAVEN_PUBLIC_URL`.
> You already do this in `voyager.py`.

**Auth.** Everything in this doc is **public / read-only except submission**.
Sending your existing `X-API-Key` header on read calls is harmless. It's
**required** only for `/api/extraction` (submit) and `/api/check_duplicate`.

**Reality / galaxy.** `reality` accepts `Normal` / `Permadeath` (default `Normal`).
`galaxy` is the display name, e.g. `Euclid` (default `Euclid`). Both are optional
on read endpoints; pass them when the user isn't in the default.

**HTTP shape.** `400` = bad input (e.g. glyph not 12 hex chars), `409` = duplicate
pending, `503` = a helper (namegen lib / DB) is temporarily unavailable.

---

## 1. Auto-naming (system + region names)

NMS system and region names are **procedurally generated** from the portal glyph +
galaxy. Haven vendors the exact algorithm the game uses, so you never have to make
the user type a name.

### 1a. `GET /api/glyph/preview` — the one-call "Create tab" primer ⭐ recommended

Give it a glyph, get back **decoded coords + procedural system name + procedural
region name + whether that region is already named on Haven** — everything the web
Create tab shows after you paste a glyph, in a single round-trip. Replaces calling
`decode_glyph` + `namegen` + `regions/…` separately.

```
GET {HAVEN_API}/api/glyph/preview?glyph=<12-hex>&galaxy=Euclid&reality=Normal
```

**Response:**
```json
{
  "glyph": "20720193DFA9",
  "galaxy": "Euclid",
  "reality": "Normal",
  "decoded": { "planet": 2, "ssi": 114, "region_x": 4091, "region_y": 5, "region_z": 4 },
  "system_name": "Oculi",
  "region_name": "Muxali Terminus",
  "region_status": {
    "named": true,
    "custom_name": "Muxali Terminus",
    "pending": false,
    "system_count": 3
  }
}
```

- `system_name` / `region_name` are the **procedural suggestions** (may be `null`
  if the namegen library is down — degrade gracefully, don't hard-fail).
- `region_status.named` → a community has already named this region on Haven
  (`custom_name`). `pending` → a name is already awaiting approval. `system_count`
  → how many catalogued systems share this region.

**Use it to:** prefill the name field, show "this region is already called **X**",
and skip prompting for a region name when one exists.

### 1b. `GET /api/namegen` — just the two names

If you only want the names and nothing else:

```
GET {HAVEN_API}/api/namegen?glyph=<12-hex>&galaxy=Euclid
→ { "system_name": "Oculi", "region_name": "Muxali Terminus" }
```

`400` if the glyph isn't 12 hex chars; `503` if the name library is unavailable.

> **You don't have to name systems client-side at all.** On submit (`/api/extraction`),
> Haven runs a **name safety net**: if you send a blank name, `System_<glyph>`, or
> the old `[TAG] X#-XXXX` placeholder, the backend fills the real procedural name
> automatically. Real/custom names are left untouched. So auto-naming in the UI is a
> nicety for the user, not a correctness requirement.

---

## 2. The dropdown fields (biomes, weather, resources, enums…)

### `GET /api/option-catalog`

The **single source of truth** for every curated list the web Create tab's dropdowns
use. Served straight from the same file the wizard reads, so your slash-command
autocomplete can never drift from the website. Public, cached, small.

```
GET {HAVEN_API}/api/option-catalog
```

**Top-level keys:**

| Key | Type | What it is |
|---|---|---|
| `biomes` | `string[]` | ~223 planet biome adjectives (Lush, Toxic, Paradise, …) |
| `weather` | `string[]` | ~368 weather adjectives |
| `sentinel` | `string[]` | Sentinel-level adjectives |
| `flora` | `string[]` | Flora-level adjectives |
| `fauna` | `string[]` | Fauna-level adjectives |
| `resources` | `string[]` | Canonical resource/material names |
| `exotic_trophies` | `string[]` | Exotic-biome collectible names |
| `planet_sizes` | `string[]` | e.g. Large / Medium / Small |
| `realities` | `string[]` | `Normal`, `Permadeath` |
| `star_types` | `string[]` | Yellow / Red / Green / Blue / Purple |
| `economy_types` | `string[]` | Trading, Mining, Technology, … |
| `economy_levels` | `string[]` | Economy tier labels |
| `conflict_levels` | `string[]` | None / Low / … / Pirate |
| `dominant_lifeforms` | `string[]` | Gek, Vy'keen, Korvax, … |
| `game_modes` | `string[]` | Normal / Survival / Permadeath / Creative / Relaxed / Custom |
| `planet_attributes` | `{key,label,icon}[]` | Boolean toggles (see below) |

**`planet_attributes`** are the checkbox-style flags. Each item is
`{ "key": "has_rings", "label": "Has Rings", "icon": "🪐" }`. The `key` is exactly
the field name to send in a planet object on submit (§5). Full set: `has_rings`,
`is_dissonant`, `is_infested`, `extreme_weather`, `water_world`, `vile_brood`,
`ancient_bones`, `salvageable_scrap`, `storm_crystals`, `gravitino_balls`,
`is_bubble`, `is_floating_islands`, `swarm_debris`, `trash_debris`,
`high_sentinel_activity`, `aggressive_sentinel_activity`, `is_gas_giant`.

**Recommended pattern:** fetch once on cog load, cache in memory, and drive
`app_commands.autocomplete` from the arrays. All lists are already sorted A→Z.

---

## 3. Region names

If a region has no name yet, let the user propose one (goes to Haven's approval
queue, exactly like the web Create tab).

### 3a. `GET /api/regions/{rx}/{ry}/{rz}` — is it already named?

```
GET {HAVEN_API}/api/regions/4091/5/4?reality=Normal&galaxy=Euclid
→ {
  "region_x": 4091, "region_y": 5, "region_z": 4,
  "reality": "Normal", "galaxy": "Euclid",
  "custom_name": "Muxali Terminus",   // null if unnamed
  "system_count": 3,
  "pending_name": { "proposed_name": "...", "submitted_by": "...", "submission_date": "..." } | null
}
```

Get `rx/ry/rz` from `decoded` in `/api/glyph/preview` (§1a), or from `decode_glyph`
(§4b). `/api/glyph/preview`'s `region_status` already folds this in — prefer that
if you've called it.

### 3b. `POST /api/regions/{rx}/{ry}/{rz}/submit` — propose a name

```
POST {HAVEN_API}/api/regions/4091/5/4/submit
Body: {
  "proposed_name": "Muxali Terminus",   // required, ≤ 50 chars
  "reality": "Normal",
  "galaxy": "Euclid",
  "discord_tag": "Haven",               // optional community tag
  "personal_discord_username": "turpitzz",   // optional, for attribution
  "submitted_by": "turpitzz"            // optional display name
}
→ { "status": "submitted", "proposed_name": "Muxali Terminus", ... }
```

- `409` if a name is **already pending** for that voxel (one pending per region).
- Names may repeat across galaxies — a name being used elsewhere is **not** rejected.
- Send `X-API-Key` so the proposal is attributed to `keeper_bot` in the review queue
  (anonymous otherwise).

> **Shortcut:** you can skip this endpoint entirely and pass `proposed_region_name`
> **inside the system submission** (§5) — Haven queues the region name alongside the
> system. If you omit it, `/api/extraction` auto-proposes the **procedural** region
> name for you.

---

## 4. Glyph tools (validate / decode / encode)

### 4a. `POST /api/validate_glyph` — you already use this

```
POST {HAVEN_API}/api/validate_glyph   Body: { "glyph": "20720193DFA9" }
→ { "valid": true, "warning": null }          // or { "valid": true, "warning": "phantom star…" }
→ { "valid": false, "error": "…" }
```

Good pre-check before any other glyph call. `warning` is non-fatal (phantom star /
core void notes).

### 4b. `POST /api/decode_glyph` — glyph → coordinates

```
POST {HAVEN_API}/api/decode_glyph   Body: { "glyph": "20720193DFA9" }
→ { "x": …, "y": …, "z": …, "planet": 2, "region_x": 4091, "region_y": 5, "region_z": 4, … }
```

### 4c. `POST /api/encode_glyph` — coordinates → glyph

```
POST {HAVEN_API}/api/encode_glyph
Body: { "x": 500, "y": -50, "z": -1200, "planet": 0, "solar_system": 1 }
→ { "glyph": "0-001-4E-350-9F4", "glyph_raw": "00014E3509F4" }
```

---

## 5. Submitting a system (the actual "Create")

The Keeper already POSTs to **`/api/extraction`** with `X-API-Key` (see
`Haven_upload.py`). That's the right endpoint — this section just documents the
full field contract so you can surface more of the Create tab.

```
POST {HAVEN_API}/api/extraction
Headers: { "X-API-Key": HAVEN_API_KEY }
```

**System-level fields** (only `glyph_code` is strictly required):

```jsonc
{
  "glyph_code": "20720193DFA9",       // REQUIRED, 12 hex chars
  "system_name": "Oculi",             // optional — blank/placeholder → auto procedural name
  "galaxy_name": "Euclid",
  "reality": "Normal",
  "game_mode": "Normal",              // from option-catalog.game_modes
  "star_type": "Yellow",              // (star_color also accepted) from star_types
  "economy_type": "Trading",          // from economy_types
  "economy_strength": "Wealthy",      // → economy_level
  "conflict_level": "Low",            // from conflict_levels
  "dominant_lifeform": "Gek",         // from dominant_lifeforms
  "no_trade_data": false,             // true → economy/conflict/lifeform stored NULL (abandoned)
  "discord_tag": "Haven",             // community (from /api/discord_tags), or "personal"
  "discord_username": "turpitzz",     // submitter, for attribution + leaderboards
  "proposed_region_name": "Muxali Terminus",  // optional — queues region name too (else auto)
  "event_id": 12,                     // optional — enter an active event (from /api/events/active)
  "planets": [ /* see below */ ]
}
```

**Planet objects** (each entry in `planets[]`; set `"is_moon": true` for moons):

```jsonc
{
  "planet_index": 0,
  "planet_name": "Oculi Prime",
  "biome": "Lush",                    // from option-catalog.biomes
  "biome_subtype": "Standard",
  "weather": "Pleasant",              // from weather
  "sentinel_level": "Low",            // from sentinel
  "flora_level": "High",              // from flora
  "fauna_level": "Medium",            // from fauna
  "planet_size": "Large",             // from planet_sizes
  "common_resource": "Copper",        // from resources
  "uncommon_resource": "Carbon",
  "rare_resource": "Gold",
  "is_moon": false,
  // boolean attributes — send any of the option-catalog.planet_attributes keys:
  "has_rings": true, "water_world": false, "is_gas_giant": false,
  "vile_brood": false, "ancient_bones": false, "extreme_weather": false
  // …etc (full key list in §2)
}
```

Notes:
- Submissions land in the **pending queue** for admin approval (same as every path).
- Coordinates/region are derived server-side from `glyph_code` — you don't compute them.
- `no_trade_data: true` is for abandoned systems with no economy/conflict/lifeform.
- Fields you omit fall through to sensible defaults; the whitelist above is what
  Haven persists, so anything outside it is ignored.

**Before submitting, dedup with `GET /api/check_duplicate`** (you already call this):

```
GET {HAVEN_API}/api/check_duplicate?glyph_code=<12hex>&galaxy=Euclid&reality=Normal
Headers: { "X-API-Key": HAVEN_API_KEY }
→ { "exists": true, "location": "approved"|"pending", "system_id"/"submission_id", "system_name" }
→ { "exists": false }
```

Matching tolerates the leading planet-index digit (last-11 + galaxy + reality), so a
glyph read from a different planet of the same system still matches.

---

## 6. Context lists for the picker

### `GET /api/discord_tags` — community tag dropdown

```
GET {HAVEN_API}/api/discord_tags
→ { "tags": [ { "tag": "Personal", "name": "Personal (Not affiliated)" },
              { "tag": "Haven", "name": "Voyager's Haven" }, … ] }
```

Send the `tag` value as `discord_tag` on submit. (`/api/communities` returns the
same civ list without the "Personal" row — either works.)

### `GET /api/events/active` — event picker (opt-in competitions)

```
GET {HAVEN_API}/api/events/active?kind=submission
→ { "events": [ { "id": 12, "name": "…", "discord_tag": "Haven",
                  "start_date": "…", "end_date": "…", "event_type": "submissions", "description": "…" } ] }
```

`kind=submission` filters to events that score system uploads. Anyone can enter any
active event; pass the chosen `id` as `event_id` on submit (§5).

---

## 7. Map-like lookups (make Keeper feel like havenmap.online)

### 7a. `GET /api/glyph/system` — glyph → 3D map deep-link

Paste a glyph, get a link that opens that system in Haven's 3D cartography view,
plus name/grade/region for a clean embed. **Fully documented in
[`HAVEN_GLYPH_MAP_SPEC.md`](./HAVEN_GLYPH_MAP_SPEC.md)** — this is the endpoint
behind a `/glyphmap` command (or bolt it onto `/hexkey`).

```
GET {HAVEN_API}/api/glyph/system?glyph=<12hex>&galaxy=Euclid&reality=Normal
→ status: "approved"  → { name, completeness_grade, region_name, map_url, detail_url, cartographer_url }
→ status: "pending"   → submitted, awaiting approval (no map link yet)
→ status: "not_found" → { region_name, submit_url }   // "/create?glyph=…" — a ready-made Create link
```

Prefix `map_url` / `submit_url` with `HAVEN_PUBLIC_URL`.

### 7b. `GET /api/glyph/resolve` — system NAME → glyph (the reverse)

User knows a system by name and wants the portal glyphs to travel there.

```
GET {HAVEN_API}/api/glyph/resolve?name=Oculi&galaxy=Euclid&reality=Normal
→ {
  "query": "Oculi", "confidence": "high", "count": 1,
  "candidates": [ { "id", "name", "glyph_code": "20720193DFA9",
                    "galaxy", "reality", "region_name", "ssi", "planet",
                    "star_type", "completeness_grade", "discovered_by" } ],
  "suggestions": []   // fuzzy near-name matches, only when count == 0
}
```

- `confidence`: `high` (1 match) / `medium` (2–5) / `low` (>5) / `none` (0). NMS
  procgen names repeat, so show all candidates with `galaxy` + `region_name` to
  disambiguate. Pass `galaxy`/`reality` to narrow.
- Needs `name` ≥ 2 chars. Only returns systems already catalogued on Haven.

---

## Suggested Keeper features (mapping to the above)

| Command idea | Endpoints |
|---|---|
| `/addsystem <glyph>` — prefill name/region, dropdown autocomplete, submit | `glyph/preview` → `option-catalog` → `check_duplicate` → `extraction` |
| `/glyphmap <glyph>` — link into the 3D map | `glyph/system` (see glyph-map spec) |
| `/findglyph <name>` — name → portal code | `glyph/resolve` |
| `/nameregion <glyph> <name>` — propose a region name | `glyph/preview` → `regions/{}/submit` |
| Slash-command field autocomplete | `option-catalog` (cache on cog load) |
| Event entry on upload | `events/active` → `event_id` on submit |

## Minimal example (aiohttp, matches your `HavenAPI` style)

```python
import aiohttp, os

HAVEN_API = os.getenv("HAVEN_API", "https://havenmap.online")
HAVEN_PUBLIC_URL = os.getenv("HAVEN_PUBLIC_URL", "https://havenmap.online")
HEADERS = {"X-API-Key": os.getenv("HAVEN_API_KEY", "")}

async def _get(path, params=None):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{HAVEN_API}{path}", params=params, headers=HEADERS) as r:
            return await r.json()

async def preview(glyph, galaxy="Euclid", reality="Normal"):
    """Decoded coords + procedural names + region status — one call."""
    return await _get("/api/glyph/preview",
                      {"glyph": glyph, "galaxy": galaxy, "reality": reality})

# cache once on cog load:
async def load_catalog():
    return await _get("/api/option-catalog")   # {biomes, weather, resources, ...}
```

---

*Backend-owned. If a field/enum you need isn't here, it's likely already in
`/api/option-catalog` or derivable from `/api/glyph/preview` — ping Parker before
re-implementing any decode/name/dedup logic client-side.*
