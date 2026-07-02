# Keeper → Haven: Glyph to Map Link

**Purpose:** a user pastes a 12-glyph portal code to Keeper and gets a link that
opens that system directly in Haven's 3D cartography view — plus the system name,
grade, and region for a nice embed. If the system isn't catalogued yet, Haven
returns the decoded region + a "submit it" link instead.

This is backend-owned: Haven builds the resolution and the URL paths. Keeper just
calls one endpoint and renders the result. No new Keeper→Haven auth is required.

---

## Endpoint

```
GET {HAVEN_API}/api/glyph/system?glyph=<12-hex>&galaxy=Euclid&reality=Normal
```

- **Public, no API key required** (systems and the `/map/system` page are already
  public). Sending your existing `X-API-Key` is harmless if that's easier in your
  http helper.
- `galaxy` defaults to `Euclid`, `reality` to `Normal`. Omit them for the common
  case; pass them when the user is elsewhere. `reality` accepts `Normal` /
  `Permadeath`.
- Matching tolerates the **leading planet-index digit** of the glyph (it changes
  every time a player portals in), so the user does **not** have to be standing on
  the exact planet the system was catalogued from. Match rule = last-11 glyph
  chars + galaxy + reality.

## Responses

**Found — live/approved system** (the happy path):
```json
{
  "status": "approved",
  "system_id": "63bd03ab-f575-4eaf-8e5c-4ea77f7cde8a",
  "name": "Oculi",
  "completeness_grade": "S",
  "galaxy": "Euclid",
  "reality": "Normal",
  "region_name": "Muxali Terminus",
  "decoded": { "planet": 2, "ssi": 114, "region_x": 4091, "region_y": 5, "region_z": 4 },
  "map_url": "/map/system/63bd03ab-f575-4eaf-8e5c-4ea77f7cde8a",
  "detail_url": "/systems/63bd03ab-f575-4eaf-8e5c-4ea77f7cde8a",
  "cartographer_url": "/map/latest?focus=system:63bd03ab-f575-4eaf-8e5c-4ea77f7cde8a"
}
```
> `map_url` is the primary link (3D system view). `detail_url` (info page) and
> `cartographer_url` (galaxy map focused on the system) are provided too if you'd
> rather link one of those.

**Found — submitted but still awaiting approval** (not on the live map yet):
```json
{
  "status": "pending",
  "submission_id": 812,
  "name": "Oculi",
  "galaxy": "Euclid",
  "reality": "Normal",
  "region_name": null,
  "decoded": { "planet": 2, "ssi": 114, "region_x": 4091, "region_y": 5, "region_z": 4 }
}
```
> No `map_url` here on purpose — it isn't on the live map until approved. Show a
> "submitted, pending review" note.

**Not catalogued yet:**
```json
{
  "status": "not_found",
  "galaxy": "Euclid",
  "reality": "Normal",
  "region_name": "Muxali Terminus",
  "region_system_count": 0,
  "decoded": { "planet": 2, "ssi": 114, "region_x": 4091, "region_y": 5, "region_z": 4 },
  "submit_url": "/create?glyph=20720193DFA9&galaxy=Euclid&reality=Normal"
}
```

**Bad input:** `400` for a glyph that isn't 12 hex chars.

## Building the link (important)

The URLs come back **relative**. Prefix them with **`HAVEN_PUBLIC_URL`**
(`https://havenmap.online`) — **not** `HAVEN_API` (the internal `http://haven:8005`),
or Discord rejects the embed with a 400 "Not a well formed URL". Same rule you
already use in `voyager.py`.

```python
url = HAVEN_PUBLIC_URL + data["map_url"]   # https://havenmap.online/map/system/<id>
```

## Suggested command

```
/glyphmap <glyph> [galaxy] [reality]
```

- `approved` → reply with `{HAVEN_PUBLIC_URL}{map_url}`, embed title = `name`,
  fields = `completeness_grade`, `region_name`.
- `pending` → "This system is submitted but awaiting approval — it'll be on the
  map once reviewed."
- `not_found` → "Not on Haven yet. Region: **{region_name}**. Add it:
  `{HAVEN_PUBLIC_URL}{submit_url}`."

You can also just bolt this onto the existing `/hexkey` flow — it already calls
`/api/check_duplicate` with the glyph; swap/append this call and add the link when
a match comes back.

## Minimal example

```python
import aiohttp, os

HAVEN_API = os.getenv("HAVEN_API", "https://havenmap.online")
HAVEN_PUBLIC_URL = os.getenv("HAVEN_PUBLIC_URL", "https://havenmap.online")

async def glyph_to_map_link(glyph, galaxy="Euclid", reality="Normal"):
    params = {"glyph": glyph, "galaxy": galaxy, "reality": reality}
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{HAVEN_API}/api/glyph/system", params=params) as r:
            data = await r.json()
    if data["status"] == "approved":
        return f"{HAVEN_PUBLIC_URL}{data['map_url']}"   # link to the 3D system view
    if data["status"] == "pending":
        return None                                     # submitted, awaiting approval
    return f"{HAVEN_PUBLIC_URL}{data['submit_url']}"    # not_found → submit link
```
