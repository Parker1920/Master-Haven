# Haven Extractor API Integration Plan

## Overview
Connect the Haven Extractor mod directly to the Haven UI API for automatic system uploads, with session configuration for user identification and community routing.

---

## Changes Required

### 1. Database Migration (New Fields + API Key)
**File**: `src/migrations.py`

Add new migration to add `personal_id` field and create API key:
```python
@register_migration("1.20.0", "Add personal_id field and Haven Extractor API key")
def migration_1_20_0(conn):
    cursor = conn.cursor()

    # Add personal_id to pending_systems (Discord snowflake ID)
    cursor.execute("ALTER TABLE pending_systems ADD COLUMN personal_id TEXT")

    # Add personal_id to systems table for approved systems
    cursor.execute("ALTER TABLE systems ADD COLUMN personal_id TEXT")

    # Create Haven Extractor API key
    import hashlib
    api_key = "vh_live_HvnXtr8k9Lm2NpQ4rStUvWxYz1A3bC5dE7fG"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_prefix = api_key[:24]  # "vh_live_HvnXtr8k9Lm2NpQ4"

    cursor.execute('''
        INSERT INTO api_keys (key_hash, key_prefix, name, created_at, permissions, rate_limit, is_active, created_by, discord_tag)
        VALUES (?, ?, ?, datetime('now'), ?, ?, 1, 'system', NULL)
    ''', (key_hash, key_prefix, 'Haven Extractor', '["submit", "check_duplicate"]', 1000))
```

---

### 2. API Endpoint Update
**File**: `src/control_room_api.py`

Update `/api/extraction` endpoint to:
- Accept new fields: `discord_username`, `personal_id`, `discord_tag`, `reality`
- Store them in `pending_systems` table
- Use the hardcoded "Haven Extractor" API key

**New payload format from extractor**:
```json
{
  "extraction_time": "2024-01-15T12:00:00",
  "extractor_version": "10.0.0",
  "glyph_code": "0123456789AB",
  "galaxy_name": "Euclid",
  "voxel_x": 100,
  "voxel_y": 50,
  "voxel_z": -200,
  "solar_system_index": 123,
  "system_name": "System Name",
  "star_type": "Yellow",
  "economy_type": "Trading",
  "economy_strength": "Wealthy",
  "conflict_level": "Low",
  "dominant_lifeform": "Gek",
  "reality": "Normal",

  "discord_username": "TurpitZz",
  "personal_id": "123456789012345678",
  "discord_tag": "Haven",

  "planets": [...]
}
```

**Updated INSERT statement** to include:
- `discord_tag`
- `personal_discord_username` (from `discord_username`)
- `personal_id`
- `reality` (stored in system_data JSON)

**Server-side duplicate validation** (double-check even after pre-flight):
```python
# Check if system already exists in approved systems
cursor.execute('SELECT id, name FROM systems WHERE glyph_code = ?', (glyph_code,))
existing_approved = cursor.fetchone()
if existing_approved:
    return JSONResponse({
        'status': 'already_charted',
        'message': f'System already exists as "{existing_approved[1]}"',
        'existing_system_id': existing_approved[0],
        'glyph_code': glyph_code
    }, status_code=409)  # Conflict
```

---

### 3. Create Haven Extractor API Key
**Method**: Database insert via migration

Create API key entry:
- **Name**: "Haven Extractor"
- **Key**: `vh_live_HvnXtr8k9Lm2NpQ4rStUvWxYz1A3bC5dE7fG`
- **Rate Limit**: 1000 (high limit for official mod)
- **Permissions**: `["submit", "check_duplicate"]`
- **Discord Tag**: NULL (user selects per session)
- **Is Active**: 1

The key will be visible in Haven UI's API Keys management page for future editing.

**Hardcode in extractor dist version**:
```python
HAVEN_EXTRACTOR_API_KEY = "vh_live_HvnXtr8k9Lm2NpQ4rStUvWxYz1A3bC5dE7fG"
```

---

### 4. New Duplicate Check Endpoint
**File**: `src/control_room_api.py`

Add new endpoint `POST /api/check_glyph_codes`:

**Request**:
```json
{
  "glyph_codes": ["ABC123DEF456", "111111111111", "222222222222"]
}
```

**Response**:
```json
{
  "results": {
    "ABC123DEF456": {
      "status": "available",
      "exists": false
    },
    "111111111111": {
      "status": "already_charted",
      "exists": true,
      "location": "approved",
      "system_name": "Voyager's Rest",
      "galaxy": "Euclid",
      "submitted_by": "TurpitZz",
      "approved_date": "2024-01-15"
    },
    "222222222222": {
      "status": "pending_review",
      "exists": true,
      "location": "pending",
      "submitted_by": "OtherUser",
      "submission_date": "2024-01-18"
    }
  },
  "summary": {
    "available": 1,
    "already_charted": 1,
    "pending_review": 1,
    "total": 3
  }
}
```

**Logic**:
```python
@app.post('/api/check_glyph_codes')
async def check_glyph_codes(payload: dict, x_api_key: str = Header(None)):
    # Validate API key has "check_duplicate" permission
    glyph_codes = payload.get('glyph_codes', [])

    results = {}
    for glyph in glyph_codes:
        # Check approved systems table first
        cursor.execute('SELECT name, galaxy, discovered_by, created_at FROM systems WHERE glyph_code = ?', (glyph,))
        approved = cursor.fetchone()
        if approved:
            results[glyph] = {
                "status": "already_charted",
                "exists": True,
                "location": "approved",
                "system_name": approved[0],
                "galaxy": approved[1],
                "submitted_by": approved[2],
                "approved_date": approved[3]
            }
            continue

        # Check pending systems
        cursor.execute('SELECT system_name, submitted_by, submission_date FROM pending_systems WHERE glyph_code = ? AND status = "pending"', (glyph,))
        pending = cursor.fetchone()
        if pending:
            results[glyph] = {
                "status": "pending_review",
                "exists": True,
                "location": "pending",
                "system_name": pending[0],
                "submitted_by": pending[1],
                "submission_date": pending[2]
            }
            continue

        # Not found anywhere
        results[glyph] = {"status": "available", "exists": False}

    return {"results": results, "summary": {...}}
```

---

### 4. Extractor Mod Updates
**File**: `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py`

#### A. Startup Config GUI
On first launch (or if config incomplete), show a tkinter dialog:

```
┌─────────────────────────────────────────┐
│     Haven Extractor Configuration       │
├─────────────────────────────────────────┤
│                                         │
│  Discord Username: [________________]   │
│                                         │
│  Discord ID:       [________________]   │
│                                         │
│  Community:        [▼ Select Tag    ]   │
│                    - Personal           │
│                    - Haven              │
│                    - IEA                │
│                    - (other partners)   │
│                                         │
│  Reality:          [▼ Normal        ]   │
│                    - Normal             │
│                    - Permadeath         │
│                                         │
│         [Save & Start Extractor]        │
│                                         │
└─────────────────────────────────────────┘
```

#### B. Config Storage
Save to `haven_config.json`:
```json
{
  "api_url": "https://voyagers-haven-3dmap.ngrok.io",
  "api_key": "vh_live_xxxxx...",
  "discord_username": "TurpitZz",
  "personal_id": "123456789012345678",
  "discord_tag": "Haven",
  "reality": "Normal"
}
```

#### C. GUI Buttons (PyMHF)
Replace current buttons with only:
1. **Check System Data** - Shows current system info in log
2. **Check Batch Data** - Shows batch collection status in log
3. **Export to Haven UI** - Opens export dialog (see below)

#### D. Export Dialog Flow
When user clicks "Export to Haven UI":

**Step 1: Choose Export Type**
```
┌─────────────────────────────────────────┐
│         Export to Haven UI              │
├─────────────────────────────────────────┤
│                                         │
│  What would you like to export?         │
│                                         │
│  [Export Current System]                │
│                                         │
│  [Export All Batch (X systems)]         │
│                                         │
│  [Cancel]                               │
│                                         │
└─────────────────────────────────────────┘
```

**Step 2: Pre-flight Duplicate Check**
Calls `/api/check_glyph_codes` with selected glyph codes.

**Step 3: Show Results Summary**
```
┌─────────────────────────────────────────┐
│         Export Summary                  │
├─────────────────────────────────────────┤
│                                         │
│  Ready to submit:     5 systems    [✓]  │
│  Already charted:     2 systems    [!]  │
│  Pending review:      1 system     [~]  │
│                                         │
│  ─────────────────────────────────────  │
│  Already Charted:                       │
│  • 0A1B2C3D4E5F - "Voyager's Rest"      │
│  • 112233445566 - "Explorer Hub"        │
│                                         │
│  Pending Review:                        │
│  • AABBCCDDEEFF - submitted by OtherUser│
│                                         │
├─────────────────────────────────────────┤
│  [Export New Only (5)]                  │
│  [Export All (8)]                       │
│  [Cancel]                               │
└─────────────────────────────────────────┘
```

**Step 4: Upload with Progress**
```
┌─────────────────────────────────────────┐
│         Uploading to Haven UI...        │
├─────────────────────────────────────────┤
│                                         │
│  [████████████░░░░░░░░] 3/5 systems     │
│                                         │
│  ✓ 0A1B2C3D4E5F - submitted             │
│  ✓ 112233445566 - submitted             │
│  ✓ AABBCCDDEEFF - submitted             │
│  ○ 123456789ABC - uploading...          │
│  ○ FEDCBA987654 - waiting...            │
│                                         │
└─────────────────────────────────────────┘
```

**Step 5: Final Results**
```
┌─────────────────────────────────────────┐
│         Export Complete!                │
├─────────────────────────────────────────┤
│                                         │
│  Successfully submitted: 5 systems      │
│  Skipped (duplicate):    2 systems      │
│  Failed:                 0 systems      │
│                                         │
│  Your submissions are now pending       │
│  admin review in the Haven UI.          │
│                                         │
│  [OK]                                   │
│                                         │
└─────────────────────────────────────────┘
```

#### E. Fetch Tags from API
On startup, fetch from `/api/discord_tags`:
```python
def fetch_community_tags():
    url = f"{API_BASE_URL}/api/discord_tags"
    response = urllib.request.urlopen(url)
    data = json.loads(response.read())
    return [{"tag": "personal", "name": "Personal"}] + data.get("tags", [])
```

#### F. Updated Send Function
Include all session config in API payload:
```python
def _send_to_api(self, data: dict):
    # Add session config to payload
    data["discord_username"] = self._config.get("discord_username", "")
    data["personal_id"] = self._config.get("personal_id", "")
    data["discord_tag"] = self._config.get("discord_tag", "personal")
    data["reality"] = self._config.get("reality", "Normal")

    # Send to API with hardcoded key
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': HAVEN_EXTRACTOR_API_KEY,
    }
    # ... rest of send logic
```

#### G. Duplicate Check Function
Pre-flight check before export:
```python
def _check_duplicates(self, glyph_codes: list) -> dict:
    """Check which systems already exist in Haven."""
    url = f"{API_BASE_URL}/api/check_glyph_codes"
    payload = json.dumps({"glyph_codes": glyph_codes}).encode('utf-8')

    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'X-API-Key': HAVEN_EXTRACTOR_API_KEY,
    })

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())
```

---

### 5. Haven UI Updates
**File**: `Haven-UI/src/pages/PendingApprovals.jsx`

Update the submission review modal to display extractor-specific fields:

#### System Info Section (add):
- Star Type
- Economy Type / Strength
- Conflict Level
- Dominant Lifeform
- Reality (Normal/Permadeath)

#### Planet Display (update):
- Biome + Biome Subtype
- Weather
- Planet Size (Large/Medium/Small/Moon)
- Resources (Common, Uncommon, Rare)
- Is Moon indicator

#### Submitter Info (add):
- Personal ID (Discord snowflake)

---

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `src/migrations.py` | ADD | New migration 1.20.0 for `personal_id` field + API key |
| `src/control_room_api.py` | EDIT | Update `/api/extraction`, add `/api/check_glyph_codes` |
| `Haven-UI/src/pages/PendingApprovals.jsx` | EDIT | Display all extractor fields in review modal |
| `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py` | REWRITE | Config GUI, 3 buttons, export dialogs, duplicate check, direct API |

---

## New Data Flow

```
[User Launches Extractor]
         │
         ▼
[Config GUI Popup]
- Fetches tags from /api/discord_tags
- User enters: Discord Username, Discord ID
- User selects: Community Tag, Reality
- Saves to haven_config.json
         │
         ▼
[Mod Starts - Hooks into NMS]
         │
         ▼
[User Warps to Systems]
- Data captured automatically via hooks
- Stored in batch memory
         │
         ▼
[User Clicks "Export to Haven UI"]
         │
         ▼
[Export Type Dialog]
- "Export Current System" or "Export All Batch"
         │
         ▼
[POST /api/check_glyph_codes]  ◄── Pre-flight duplicate check
- Checks against: approved systems + pending submissions
- Returns: available / already_charted / pending_review
         │
         ▼
[Export Summary Dialog]
- Shows counts: X ready, Y charted, Z pending
- User chooses: "Export New Only" or "Export All"
         │
         ▼
[POST /api/extraction] (for each system)
- Server validates again (double-check)
- If duplicate → returns 409 Conflict
- If new → inserts into pending_systems
- API key: "Haven Extractor" (hardcoded)
         │
         ▼
[Upload Progress + Final Results]
- Shows: submitted / skipped / failed counts
         │
         ▼
[Haven UI - pending_systems table]
- discord_tag set for admin routing
- personal_discord_username for contact
- personal_id for tracking
- reality stored in system_data
         │
         ▼
[Admin Reviews in PendingApprovals]
- Sees all system details
- Sees all planet details (biome, resources, etc.)
- Sees submitter info (Discord username + ID)
- Routes based on discord_tag
```

---

## Testing Checklist

- [ ] Migration runs without errors
- [ ] API key "Haven Extractor" created and visible in Haven UI
- [ ] Extractor config GUI appears on first launch
- [ ] Tags fetched successfully from API (includes all partners)
- [ ] Config saves to haven_config.json
- [ ] "Check System Data" button shows current system info
- [ ] "Check Batch Data" button shows batch status
- [ ] "Export to Haven UI" shows export type choice
- [ ] Pre-flight duplicate check works (`/api/check_glyph_codes`)
- [ ] Export summary shows correct counts (available/charted/pending)
- [ ] "Export New Only" skips duplicates
- [ ] "Export All" submits everything
- [ ] Upload progress shows correctly
- [ ] Final results summary is accurate
- [ ] Submission appears in PendingApprovals
- [ ] All system fields display (star type, economy, conflict, lifeform, reality)
- [ ] All planet fields display (biome, subtype, weather, size, resources)
- [ ] Discord tag routing works (Haven admins see Haven, etc.)
- [ ] Personal submissions show Discord username + ID
- [ ] Server rejects already-charted systems with 409 status

---

## API Key Details

**For dist version**, hardcode:
- API URL: `https://voyagers-haven-3dmap.ngrok.io`
- API Key: Will be generated and embedded

**Key visible in Haven UI** at `/api-keys` page for future management.
