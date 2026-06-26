# Haven ⇄ Keeper Integration Spec

**For:** Stars (The_Keeper maintainer)
**From:** Parker / Haven backend
**Date:** 2026-06-26
**Status:** Backend is live-ready (Haven backend `1.82.0`). This doc is the Keeper-side wiring guide. Nothing in `The_Keeper/` has been changed — that's yours.

---

## TL;DR

Two asks, both already supported by new Haven endpoints — the Keeper just needs to call them:

1. **Auto system + region names** (parity with the in-game extractor and the web wizard). The Keeper currently uploads systems with a placeholder name like `[HAVEN] F4-ABCD` and no region info. Haven can now hand you the real procedural NMS system name **and** region name from just the glyph, in **one HTTP call**.
2. **Searchable field entry.** Haven now serves the exact curated dropdown lists the web wizard uses (biomes, weather, flora, fauna, sentinel, resources, plus the star/economy/conflict/lifeform enums) so you can drive Discord slash-command autocomplete instead of free-text.

Base URL + auth are unchanged from what the Keeper already uses:

```python
BASE_URL = os.getenv("HAVEN_API", "https://havenmap.online")
HEADERS  = {"X-API-Key": os.getenv("HAVEN_API_KEY")}   # only needed for writes
```

All the **GET** endpoints below are **public (no key required)**. The key is only needed for the existing submit calls.

---

## Ask 1 — Auto system & region naming

### The one call: `GET /api/glyph/preview`

After the user finishes entering the 12-glyph code, call this. It returns everything you need to show a confirmation embed and to submit, in a single round-trip.

**Request**
```
GET /api/glyph/preview?glyph=<12-hex>&galaxy=<GalaxyName>&reality=<Normal|Permadeath>
```
- `glyph` — required, 12 hex chars (the code the keypad already builds).
- `galaxy` — optional, defaults `Euclid`. Use the galaxy the user selected.
- `reality` — optional, defaults `Normal`.

**Response 200**
```json
{
  "glyph": "0FFF615E0CC5",
  "galaxy": "Euclid",
  "reality": "Normal",
  "decoded": { "planet": 0, "ssi": 4095, "region_x": 3269, "region_y": 97, "region_z": 1504 },
  "system_name": "Pazuzumok XVII",
  "region_name": "Imniarab Mass",
  "region_status": {
    "named": false,            // is the region already named on Haven?
    "custom_name": null,       // the existing name, if named
    "pending": false,          // is a region name already awaiting approval?
    "system_count": 12         // systems Haven has in this region
  }
}
```
- `system_name` / `region_name` are the **real procedural NMS names** (deterministic — same glyph+galaxy always gives the same names; they match the wizard and the in-game extractor exactly).
- They can be `null` only if the name library is unavailable (rare); fall back to letting the user type a name.
- `400` if the glyph isn't 12 hex chars.

**Decoded coords matter:** `region_x/y/z` are what you pass to the region endpoints below.

### Wiring it into the upload flow

Replace the Keeper's `generate_system_name()` placeholder (`[HAVEN] F4-ABCD`) with the previewed `system_name`:

1. User finishes the glyph → call `/api/glyph/preview`.
2. Pre-fill the system-name field with `data["system_name"]` (user can still override in the modal).
3. In the confirmation embed, show the region:
   - `region_status.named == true` → "Region: **{custom_name}** (already named)".
   - `region_status.pending == true` → "Region: **{region_name}** (name pending approval)".
   - else → "Region: **{region_name}** — I'll submit this name for approval."

### Submitting the system

**Keep using `POST /api/extraction`** exactly as today — just send the real name (or send nothing and let Haven fill it; see the safety net below). New: you can also pass a region name to propose.

```python
payload = {
    "glyph_code": glyph,
    "system_name": preview["system_name"],   # real procedural name (or omit/blank — see note)
    "galaxy_name": galaxy,
    "reality": reality,
    "discord_tag": community_tag,
    "discord_username": interaction.user.name,
    # ... your existing economy/conflict/lifeform/star fields, planets[], etc. ...

    # NEW (optional): propose the region name in the same call.
    # Only meaningful when region_status.named and region_status.pending are both false.
    "proposed_region_name": preview["region_name"],
}
# POST {BASE_URL}/api/extraction  with X-API-Key
```

**Region naming — you have two equivalent options, pick one:**
- **(A) Inline (recommended, simplest):** add `proposed_region_name` to the `/api/extraction` payload (above). Haven queues it for approval if the region is unnamed and has no pending name.
- **(B) Separate call** (what the in-game extractor does): `POST /api/regions/{rx}/{ry}/{rz}/submit` with `{ "proposed_name": ..., "galaxy": ..., "reality": ..., "submitted_by": ..., "discord_tag": ... }`. Use `rx/ry/rz` from `preview["decoded"]`.

Either way, the "one pending submission per voxel" rule keeps it from creating duplicates.

### Safety net (already live — you get this even before wiring)

Haven's `/api/extraction` now **auto-fixes placeholder names server-side**: if you submit a blank name, `System_<glyph>`, or the Keeper's `[TAG] X#-XXXX` pattern, Haven replaces it with the real procedural name and auto-proposes the procedural region name. So the moment this backend deploys, existing Keeper uploads stop landing as `[HAVEN] F4-ABCD`. Wiring `/api/glyph/preview` is still better (the user sees/confirms the name), but you're covered immediately.

> The placeholder detector is deliberately tight — it will **not** touch civ-tag-prefixed real names like `[RES]Boulde`. Only blank / `System_*` / the exact `[TAG] Letter+Digit-Hex4` shape are treated as placeholders.

### `aiohttp` helper (matches your existing `HavenAPI` style)

```python
async def glyph_preview(self, glyph: str, galaxy: str = "Euclid", reality: str = "Normal"):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{self.base}/api/glyph/preview",
            params={"glyph": glyph, "galaxy": galaxy, "reality": reality},
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return None
```

---

## Ask 2 — Searchable (type-to-filter) field entry

### The constraint you need to know

Discord **modals only support plain text inputs** — no autocomplete, no dropdowns. The only way to get "type a few letters → it searches the list" is **slash-command options with `@app_commands.autocomplete`** (the same mechanism you already use for `/atlas`'s galaxy field). So the planet-entry portion needs to move from the modal to a slash-command flow (e.g. `/addplanet biome:<autocomplete> weather:<autocomplete> ...`). The small system-level fields (star/economy/conflict/lifeform) are fine as they are (select menus), or can become autocomplete too for consistency.

### The data: `GET /api/option-catalog`

Fetch this **once on startup**, cache it in memory, and filter it locally for autocomplete. Public, no auth. It's the *exact* curated list the web wizard uses (single source of truth — they can't drift).

**Response 200** (abridged)
```json
{
  "version": 1,
  "biomes":   ["[REDACTED]", "Abandoned", "Acidic", "...223 total..."],
  "weather":  ["Acid Rain", "...368 total..."],
  "sentinel": ["Absent", "Aggressive", "...43 total..."],
  "flora":    ["Absent", "Abundant", "...54 total..."],
  "fauna":    ["Absent", "Abundant", "...54 total..."],
  "resources":["Activated Cadmium", "...104 total..."],
  "exotic_trophies": ["Bubble Cluster", "...11 total..."],
  "planet_sizes": ["Small", "Medium", "Large"],
  "realities": [{"value":"Normal","label":"Normal"}, {"value":"Permadeath","label":"Permadeath"}],
  "star_types":         [{"value":"Yellow","label":"☀ Yellow"}, "..."],
  "economy_types":      [{"value":"Trading","label":"⚖️ Trading"}, "...11 total..."],
  "economy_levels":     [{"value":"T1","label":"★ (Low)"}, "...5 total..."],
  "conflict_levels":    [{"value":"Low","label":"🔥 Low"}, "...5 total..."],
  "dominant_lifeforms": [{"value":"Gek","label":"🐸 Gek"}, "...5 total..."],
  "game_modes":         [{"value":"Normal","label":"Normal"}, "...6 total..."],
  "planet_attributes":  [{"key":"has_rings","label":"Has Rings","icon":"🪐"}, "...17 total..."]
}
```

- The **adjective/resource lists** are plain string arrays → autocomplete `name == value == the string`.
- The **enums** are `{value, label}` → use `value` when submitting, `label` (with emoji) for display.
- `planet_attributes` are the boolean toggles (`key` is the payload field, `label`/`icon` for display).

### Autocomplete pattern (reuse your `/atlas` pattern)

```python
# at startup
self.catalog = await fetch_option_catalog()   # GET /api/option-catalog, cache it

def _ac(field_key):
    """Build an autocomplete callback over a cached list. Discord caps at 25."""
    async def inner(interaction: discord.Interaction, current: str):
        cur = (current or "").lower()
        items = self.catalog[field_key]
        # plain-string list (biomes/weather/...) vs {value,label} enum list
        names = [x if isinstance(x, str) else x["value"] for x in items]
        matches = [n for n in names if cur in n.lower()][:25]
        return [app_commands.Choice(name=n, value=n) for n in matches]
    return inner

@app_commands.command(name="addplanet", description="Add a planet to the system you're logging")
@app_commands.autocomplete(biome=_ac("biomes"), weather=_ac("weather"),
                           flora=_ac("flora"), fauna=_ac("fauna"),
                           sentinel=_ac("sentinel"), resource=_ac("resources"))
async def addplanet(self, interaction, biome: str, weather: str,
                    flora: str = "", fauna: str = "", sentinel: str = "",
                    resource: str = ""):
    ...
```

(Discord allows ≤25 autocomplete choices, which is why you filter by `current` first — even the 368-entry weather list works because the user has typed a few letters by the time choices are shown.)

### Field → catalog key map

| Keeper field | Catalog key | Shape |
|---|---|---|
| biome | `biomes` | string[] |
| weather | `weather` | string[] |
| sentinel | `sentinel` | string[] |
| flora | `flora` | string[] |
| fauna | `fauna` | string[] |
| resources / materials | `resources` | string[] |
| exotic trophy | `exotic_trophies` | string[] |
| planet size | `planet_sizes` | string[] |
| star type | `star_types` | {value,label}[] |
| economy type | `economy_types` | {value,label}[] |
| economy tier | `economy_levels` | {value,label}[] |
| conflict level | `conflict_levels` | {value,label}[] |
| dominant lifeform | `dominant_lifeforms` | {value,label}[] |
| game mode | `game_modes` | {value,label}[] |
| reality | `realities` | {value,label}[] |
| planet/moon toggles | `planet_attributes` | {key,label,icon}[] |

---

## Endpoint reference

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/glyph/preview?glyph=&galaxy=&reality=` | none | decoded coords + procedural system/region names + region status (**use this for Ask 1**) |
| GET | `/api/option-catalog` | none | curated option lists (**use this for Ask 2**) |
| GET | `/api/namegen?glyph=&galaxy=` | none | just `{system_name, region_name}` (subset of preview) |
| POST | `/api/decode_glyph` `{glyph}` | none | full coord decode if you ever need more than preview gives |
| GET | `/api/regions/{rx}/{ry}/{rz}?reality=&galaxy=` | none | region naming status (preview already includes this) |
| POST | `/api/regions/{rx}/{ry}/{rz}/submit` | optional key | propose a region name (option B) |
| POST | `/api/extraction` | X-API-Key | submit the system to the pending queue (**unchanged; now accepts `proposed_region_name`**) |

---

## Notes / gotchas

- **Names are deterministic.** Same glyph + galaxy → same system & region name, every time, matching the wizard and the in-game extractor. No need to store them; re-derive any time.
- **503 on the name endpoints** means the name library is momentarily unavailable — degrade gracefully (let the user type a name); don't hard-fail the upload.
- **You don't have to do Ask 1 and Ask 2 in the same release.** Ask 1 (one preview call + use the names) is small. Ask 2 (slash-command autocomplete) is the bigger change because of the modal→slash move.
- **Galaxy name vs index:** pass the galaxy **display name** (e.g. `Euclid`, `Hyades`) to all these endpoints — they resolve the index internally.
- **No backend changes are needed from you** — everything here is live on Haven once `1.82.0` deploys. Reach out to Parker if any field shape needs adjusting.

---

### Suggested home for this file
Once you've reviewed it, this can live at `The_Keeper/HAVEN_INTEGRATION_SPEC.md` (or wherever you keep notes). It was left out of the Keeper repo on purpose so Parker isn't editing your project.
