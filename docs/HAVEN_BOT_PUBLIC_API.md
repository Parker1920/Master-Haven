# Haven Public API Reference (Discord Bot Edition)

**Base URL:** `https://havenmap.online`

This guide documents the **public, no-auth endpoints** that power the Community Stats page, plus the discovery submission endpoint. Everything here is safe to call from a Discord bot without an API key.

The only endpoint requiring auth is `/api/submit_discovery` — it accepts public submissions but expects identifying fields in the payload.

---

## Table of Contents

1. [Global Stats](#1-global-stats)
2. [Communities List](#2-communities-list)
3. [Community Overview](#3-community-overview)
4. [Contributors Leaderboard](#4-contributors-leaderboard)
5. [Activity Timeline](#5-activity-timeline)
6. [Discovery Type Breakdown](#6-discovery-type-breakdown)
7. [Community Regions](#7-community-regions)
8. [Submit Discovery](#8-submit-discovery)
9. [Bot Command Examples](#9-bot-command-examples)

---

## 1. Global Stats

Total counts across the entire Haven database.

### Request

```http
GET /api/db_stats
```

No auth, no parameters.

### Response (Public)

```json
{
  "user_type": "public",
  "stats": {
    "systems": 5678,
    "star_systems": 5678,
    "planets": 12450,
    "moons": 3201,
    "regions": 42,
    "populated_regions": 89,
    "planet_pois": 156,
    "discoveries": 678
  }
}
```

### Field Reference

| Field | Meaning |
|-------|---------|
| `systems` / `star_systems` | Total approved star systems |
| `planets` | Total planets across all systems |
| `moons` | Total moons across all planets |
| `regions` | **Named regions** — every row has a `custom_name` |
| `populated_regions` | Distinct region coords with ≥1 system (named *or* unnamed) |
| `planet_pois` | Points of Interest on planet surfaces |
| `discoveries` | Approved scientific discoveries |

---

## 2. Communities List

All registered partner communities. Use this to validate community names before passing them to other endpoints.

### Request

```http
GET /api/communities
```

### Response

```json
{
  "communities": [
    {
      "discord_tag": "HAVEN",
      "display_name": "Haven",
      "color": "#00d4ff"
    },
    {
      "discord_tag": "IEA",
      "display_name": "Intergalactic Exploration Agency",
      "color": "#ff8800"
    }
  ]
}
```

---

## 3. Community Overview

Per-community totals + grand totals. The exact data behind the Community Stats overview cards.

### Request

```http
GET /api/public/community-overview
```

### Response

```json
{
  "communities": [
    {
      "discord_tag": "HAVEN",
      "display_name": "Haven",
      "total_systems": 1234,
      "total_discoveries": 67,
      "unique_contributors": 42,
      "manual_systems": 800,
      "extractor_systems": 434
    }
  ],
  "totals": {
    "total_systems": 5678,
    "total_discoveries": 123,
    "total_communities": 8,
    "total_contributors": 156
  }
}
```

### Field Reference

| Field | Meaning |
|-------|---------|
| `discord_tag` | Community tag — used as filter parameter elsewhere |
| `display_name` | Human-readable community name |
| `total_systems` | Approved systems tagged to this community |
| `total_discoveries` | Discoveries tagged to this community |
| `unique_contributors` | Distinct submitters who contributed to this community |
| `manual_systems` | Systems submitted via web form |
| `extractor_systems` | Systems submitted via Haven Extractor mod |

---

## 4. Contributors Leaderboard

Ranked list of contributors, optionally filtered by community.

### Request

```http
GET /api/public/contributors
GET /api/public/contributors?community=HAVEN
GET /api/public/contributors?community=HAVEN&limit=10
```

### Query Parameters

| Param | Type | Default | Meaning |
|-------|------|---------|---------|
| `community` | string | `null` | Filter to one community's contributors |
| `limit` | int | `50` | Max contributors to return |

### Response

```json
{
  "contributors": [
    {
      "rank": 1,
      "username": "Parker1920",
      "discord_tags": "HAVEN,IEA",
      "total_systems": 234,
      "manual_count": 100,
      "extractor_count": 134,
      "total_discoveries": 12,
      "last_activity": "2026-04-13T14:22:18"
    }
  ],
  "total_contributors": 156
}
```

### Field Reference

| Field | Meaning |
|-------|---------|
| `rank` | Ranking by `total_systems` (desc) |
| `username` | Display name (Discord discriminator stripped) |
| `discord_tags` | Comma-joined list of communities they've submitted to |
| `total_systems` | Approved system submissions |
| `manual_count` | Of those, submitted via web form |
| `extractor_count` | Of those, submitted via Haven Extractor mod |
| `total_discoveries` | Approved discovery submissions |
| `last_activity` | ISO timestamp of most recent submission |

---

## 5. Activity Timeline

Time-series data combining manual systems, extractor systems, and discoveries.

### Request

```http
GET /api/public/activity-timeline
GET /api/public/activity-timeline?granularity=week&months=6
```

### Query Parameters

| Param | Type | Default | Allowed Values |
|-------|------|---------|----------------|
| `granularity` | string | `week` | `day`, `week`, `month` |
| `months` | int | `6` | How far back to query |

### Response

```json
{
  "timeline": [
    {"date": "2026-W14", "manual": 12, "extractor": 8, "discoveries": 3},
    {"date": "2026-W15", "manual": 9,  "extractor": 14, "discoveries": 5}
  ],
  "granularity": "week"
}
```

### Date Format by Granularity

| Granularity | Date Format Example |
|-------------|--------------------|
| `day` | `2026-04-13` |
| `week` | `2026-W15` (ISO week) |
| `month` | `2026-04` |

---

## 6. Discovery Type Breakdown

Discovery counts grouped by type, with percentages.

### Request

```http
GET /api/public/discovery-breakdown
```

### Response

```json
{
  "breakdown": [
    {"type_slug": "fauna",    "discovery_type": "Fauna",    "count": 45, "percentage": 36.6},
    {"type_slug": "flora",    "discovery_type": "Flora",    "count": 28, "percentage": 22.8},
    {"type_slug": "ancient",  "discovery_type": "Ancient",  "count": 19, "percentage": 15.4},
    {"type_slug": "mineral",  "discovery_type": "Mineral",  "count": 14, "percentage": 11.4},
    {"type_slug": "starship", "discovery_type": "Starship", "count": 8,  "percentage": 6.5}
  ],
  "total": 123
}
```

### Discovery Type Slugs

`fauna`, `flora`, `mineral`, `ancient`, `history`, `bones`, `alien`, `starship`, `multitool`, `lore`, `base`, `other`

---

## 7. Community Regions

All regions (named + unnamed) where a community has submitted systems, with system lists.

### Request

```http
GET /api/public/community-regions?community=HAVEN
```

### Query Parameters

| Param | Type | Required | Meaning |
|-------|------|----------|---------|
| `community` | string | yes | Discord tag of the community |

### Response

```json
{
  "regions": [
    {
      "region_name": "Haven Sector",
      "region_x": 5,
      "region_y": -3,
      "region_z": 12,
      "system_count": 23,
      "systems": [
        {
          "id": "abc-123-uuid",
          "name": "Haven Prime",
          "star_type": "Yellow",
          "grade": "S"
        }
      ]
    },
    {
      "region_name": null,
      "region_x": 7,
      "region_y": -2,
      "region_z": 8,
      "system_count": 4,
      "systems": [...]
    }
  ],
  "total_regions": 8
}
```

### Sort Order

Named regions first (by `system_count` descending), then unnamed regions (by `system_count` descending).

### Field Reference

| Field | Meaning |
|-------|---------|
| `region_name` | Custom name, or `null` if unnamed |
| `region_x` / `region_y` / `region_z` | Signed region coordinates |
| `system_count` | Number of systems this community has in this region |
| `systems[].grade` | Completeness grade: `S` / `A` / `B` / `C` |
| `systems[].star_type` | `Yellow`, `Red`, `Green`, `Blue`, `Purple` |

---

## 8. Submit Discovery

Submit a discovery for approval. Goes into the `pending_discoveries` queue.

### Request

```http
POST /api/submit_discovery
Content-Type: application/json
```

### Required Fields

| Field | Type | Meaning |
|-------|------|---------|
| `discovery_name` | string | Name of the discovery |
| `system_id` | string | UUID of the linked system |
| `discord_username` | string | Submitter's Discord username |
| `discord_tag` | string | Community tag (e.g. `HAVEN`) |
| `discovery_type` | string | One of: `fauna`, `flora`, `mineral`, `ancient`, `history`, `bones`, `alien`, `starship`, `multitool`, `lore`, `base`, `other` |

### Optional Fields

| Field | Type | Meaning |
|-------|------|---------|
| `location_type` | string | `planet`, `moon`, or `space` (default: `space`) |
| `planet_id` | int | Planet ID if `location_type=planet` |
| `moon_id` | int | Moon ID if `location_type=moon` |
| `photo_url` | string | URL or filename of uploaded photo |
| `type_metadata` | object | Type-specific subfields (see below) |

### `type_metadata` Subfields by Type

| Discovery Type | Metadata Fields |
|----------------|-----------------|
| `fauna` | `species_name`, `behavior` |
| `flora` | `species_name`, `biome` |
| `mineral` | `resource_type`, `deposit_richness` |
| `ancient` | `age_era`, `associated_race` |
| `history` | `language_status`, `author_origin` |
| `bones` | `species_type`, `estimated_age` |
| `alien` | `structure_type`, `operational_status` |
| `starship` | `ship_type`, `ship_class` |
| `multitool` | `tool_type`, `tool_class` |
| `lore` | `story_type` |
| `base` | `base_type` |
| `other` | *(none)* |

### Example Payload

```json
{
  "discovery_name": "Crystalline Manatee",
  "discovery_type": "fauna",
  "system_id": "abc-123-uuid",
  "planet_id": 4567,
  "location_type": "planet",
  "discord_username": "Parker1920",
  "discord_tag": "HAVEN",
  "photo_url": "https://example.com/photo.jpg",
  "type_metadata": {
    "species_name": "Crystallus aquaticus",
    "behavior": "Docile filter-feeder"
  }
}
```

### Response

```json
{
  "status": "pending",
  "message": "Discovery submitted for approval!",
  "submission_id": 142
}
```

### Errors

| Status | Reason |
|--------|--------|
| 400 | Missing required field |
| 500 | Server error |

---

## 9. Bot Command Examples

Reference implementations using `requests` / `aiohttp`. Drop into a `discord.py` cog.

### `!haven` — Global Snapshot

```python
import requests

BASE = 'https://havenmap.online'

def haven_global():
    db = requests.get(f'{BASE}/api/db_stats').json()['stats']
    o  = requests.get(f'{BASE}/api/public/community-overview').json()['totals']

    return (
        f"🌌 **Haven Global Stats**\n"
        f"Systems: {db['systems']:,}\n"
        f"Planets: {db['planets']:,}\n"
        f"Moons: {db['moons']:,}\n"
        f"Named Regions: {db['regions']:,}\n"
        f"Discoveries: {db['discoveries']:,}\n"
        f"Communities: {o['total_communities']}\n"
        f"Contributors: {o['total_contributors']:,}"
    )
```

### `!community <tag>` — Community Snapshot

```python
def community_stats(tag):
    overview = requests.get(f'{BASE}/api/public/community-overview').json()
    match = next((c for c in overview['communities'] if c['discord_tag'] == tag), None)
    if not match:
        return f"Community `{tag}` not found."

    regions = requests.get(
        f'{BASE}/api/public/community-regions',
        params={'community': tag}
    ).json()

    named = sum(1 for r in regions['regions'] if r['region_name'])

    return (
        f"🏛️ **{match['display_name']}**\n"
        f"Systems: {match['total_systems']:,} "
        f"({match['manual_systems']} manual / {match['extractor_systems']} extractor)\n"
        f"Discoveries: {match['total_discoveries']}\n"
        f"Contributors: {match['unique_contributors']}\n"
        f"Regions: {regions['total_regions']} ({named} named)"
    )
```

### `!leaderboard [community]` — Top 10 Contributors

```python
def leaderboard(community=None):
    params = {'limit': 10}
    if community:
        params['community'] = community

    data = requests.get(
        f'{BASE}/api/public/contributors',
        params=params
    ).json()

    lines = ["🏆 **Top Contributors**"]
    for c in data['contributors']:
        lines.append(
            f"{c['rank']}. **{c['username']}** — "
            f"{c['total_systems']} systems, {c['total_discoveries']} discoveries"
        )
    return "\n".join(lines)
```

### `!discoveries` — Type Breakdown

```python
def discovery_breakdown():
    data = requests.get(f'{BASE}/api/public/discovery-breakdown').json()

    lines = [f"🔬 **Discoveries** (total: {data['total']})"]
    for item in data['breakdown']:
        lines.append(
            f"• **{item['discovery_type']}** — "
            f"{item['count']} ({item['percentage']}%)"
        )
    return "\n".join(lines)
```

### `!activity` — Last 4 Weeks

```python
def recent_activity():
    data = requests.get(
        f'{BASE}/api/public/activity-timeline',
        params={'granularity': 'week', 'months': 1}
    ).json()

    lines = ["📈 **Recent Activity (weekly)**"]
    for entry in data['timeline'][-4:]:
        total = entry['manual'] + entry['extractor']
        lines.append(
            f"`{entry['date']}` — "
            f"{total} systems ({entry['manual']}m / {entry['extractor']}x), "
            f"{entry['discoveries']} discoveries"
        )
    return "\n".join(lines)
```

### `!regions <community>` — Community Region Map

```python
def community_regions(tag):
    data = requests.get(
        f'{BASE}/api/public/community-regions',
        params={'community': tag}
    ).json()

    lines = [f"🗺️ **{tag} Regions** ({data['total_regions']} total)"]
    for r in data['regions'][:10]:
        name = r['region_name'] or f"_(unnamed {r['region_x']},{r['region_y']},{r['region_z']})_"
        lines.append(f"• **{name}** — {r['system_count']} systems")
    return "\n".join(lines)
```

### Submit a Discovery from Discord

```python
def submit_fauna(system_id, planet_id, name, species, behavior, user, tag):
    payload = {
        'discovery_name': name,
        'discovery_type': 'fauna',
        'system_id': system_id,
        'planet_id': planet_id,
        'location_type': 'planet',
        'discord_username': user,
        'discord_tag': tag,
        'type_metadata': {
            'species_name': species,
            'behavior': behavior,
        }
    }
    r = requests.post(f'{BASE}/api/submit_discovery', json=payload)
    r.raise_for_status()
    return r.json()['submission_id']
```

---

## Summary Table

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/db_stats` | GET | none | Global counts |
| `/api/communities` | GET | none | Community list |
| `/api/public/community-overview` | GET | none | Per-community + grand totals |
| `/api/public/contributors` | GET | none | Contributor leaderboard |
| `/api/public/activity-timeline` | GET | none | Time-series activity |
| `/api/public/discovery-breakdown` | GET | none | Discoveries by type |
| `/api/public/community-regions` | GET | none | Regions for a community |
| `/api/submit_discovery` | POST | none\* | Submit new discovery |

\* No auth required, but submission identifies via `discord_username` + `discord_tag` in payload.

---

## Notes

- All endpoints return JSON and use standard HTTP status codes
- No rate limiting on public read endpoints
- All timestamps are ISO 8601 UTC
- `discord_tag` values are case-sensitive — fetch them from `/api/communities` to be safe
- For private/per-community admin data (rejection rates, audit trails, pending queues), an authenticated session or API key is required — see `HAVEN_API_GUIDE.md`
