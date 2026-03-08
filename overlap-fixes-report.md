# Overlap Fixes Report
**Date:** 2026-03-08

## Task 1: CLAUDE.md Update
- Status: Complete
- Changes made:
  - Removed Round Table AI section (4 endpoints + WS /ws/rtai)
  - Removed `/api/migrate_hub_tags` from Audit & Admin Tools
  - Removed `POST /api/generate_map` from Map section
  - Removed `WS /ws/rtai` from WebSocket section
  - Updated endpoint count from "210+ across /api/*, plus 2 WebSocket" to "200+ across /api/*, plus 1 WebSocket"
  - Added "Post-Cleanup State (March 8, 2026)" section at bottom

## Task 2: Repo Tree Fix
- Status: Complete
- Line changed: "Docker Compose is available but the Pi currently runs the app directly via systemd" → "Haven runs in Docker Compose on the Pi, served by uvicorn inside the container on port 8005. The container is managed by Docker, not systemd."

## Task 3: Overlap Fixes

### Fix A: Tag Colors
- Status: Complete
- API response shape: `{ colors: { tag: { color: '#hex', name: 'display_name' } } }`
- Files modified:
  - `Haven-UI/src/utils/tagColors.js` — Added `_apiColors` cache, `setApiTagColors()`, `getTagColorFromAPI()`, `hexToTagStyle()`. Updated `getTagColorStyle()` to check API cache. Kept all hardcoded values as fallbacks.
  - `Haven-UI/src/components/ThemeProvider.jsx` — Added fetch of `/api/discord_tag_colors` on startup, calls `setApiTagColors()`
  - `Haven-UI/src/components/DiscordTagBadge.jsx` — Switched from `tagColors[tag]` Tailwind class to `getTagColorFromAPI(tag)` with inline style
  - `Haven-UI/src/components/SystemsList.jsx` — Same: Tailwind class → `getTagColorFromAPI()` inline style
  - `Haven-UI/src/components/LeaderboardTable.jsx` — Same: `getTagColor()` → `getTagColorFromAPI()` inline style (2 locations)
  - `Haven-UI/src/pages/CommunityDetail.jsx` — No change needed (uses `getTagColorStyle()` which now checks API cache)
  - `Haven-UI/src/pages/CommunityStats.jsx` — No change needed (same reason)

### Fix B: Backend Discovery Colors
- Status: Complete
- Lines removed: 12 color fields removed from DISCOVERY_TYPE_INFO dict entries
- Comment added above constant explaining colors are frontend-only
- File: `Haven-UI/backend/control_room_api.py`

### Fix C: DiscoverySubmitModal
- Status: Complete
- Files modified: `Haven-UI/src/components/DiscoverySubmitModal.jsx`
- Removed hardcoded 13-entry DISCOVERY_TYPES array (lines 8-22)
- Added import from `../data/discoveryTypes` (TYPE_INFO)
- DISCOVERY_TYPES now built dynamically: `Object.values(TYPE_INFO).map()`
- TYPE_FIELDS kept as-is with explanatory comment added
- "Select type..." placeholder option preserved

### Fix D: Extractor Community List
- Status: Complete
- What changed:
  - Removed `_DEFAULT_COMMUNITY_TAGS` constant (25-entry hardcoded list)
  - Added `_community_fetch_error` global for error state tracking
  - When both API fetch and cache fail: sets error message, returns `["personal"]` (minimum for enum to load), logs warning
  - Export button (`export_to_haven_ui`) now checks `_community_fetch_error` and blocks submission with visible error message
  - Comment added explaining why no hardcoded fallback exists
- File: `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py`

## Verified Working
- Backend compiles: Yes
- Frontend builds: Yes
- Errors: None
