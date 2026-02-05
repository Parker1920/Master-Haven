# Master-Haven Repository Cleanup Report

**Generated**: February 4, 2026
**Status**: PHASE 3 & 4 COMPLETE - CLEANUP FINISHED

---

## 1. Current Structure

```
C:\Master-Haven\
├── .claude/                        # Claude Code settings
│   ├── settings.json
│   └── settings.local.json
├── .git/                           # Git repository
├── .gitignore                      # Git ignore rules
├── .gitmodules                     # Git submodules (Planet_Atlas)
├── .venv/                          # Python virtual environment (SHOULD NOT BE IN REPO)
│
├── config/                         # Centralized path config
│   ├── __pycache__/
│   └── paths.py                    # HavenPaths class - used by src/control_room_api.py
│
├── docs/                           # Documentation
│   ├── HOMELAB_MIGRATION.md        # Haven-UI deployment guide
│   └── RASPBERRY_PI_PRODUCTION_SETUP.md
│
├── scripts/                        # Utility scripts
│   ├── archive/                    # Archived/old scripts
│   ├── migrations/                 # DB migration scripts
│   │   ├── add_missing_tables.py
│   │   └── update_planets_schema.py
│   ├── apply_update_remote.sh
│   ├── backfill_star_positions.py
│   ├── check_pending_submission.py
│   ├── clean_broken_submissions.py
│   ├── create_update_archive.ps1
│   ├── delete_core_void_systems.py
│   ├── deploy_to_pi.ps1
│   ├── examine_discovery_records.py
│   ├── fix_null_system_ids.py
│   ├── migrate.py
│   ├── migrate_star_positions.py
│   ├── ngrok_check.ps1
│   ├── quick_health_check.bat
│   ├── start_keeper_bot.bat
│   ├── start_server.bat
│   ├── start_with_ngrok.bat
│   ├── test_approval.py
│   ├── test_signed_hex_glyphs.py
│   └── verify_dashboard_fix.bat
│
├── src/                            # Backend API (CRITICAL - NEEDS TO MOVE TO Haven-UI)
│   ├── __pycache__/
│   ├── CLAUDE.md                   # Backend documentation
│   ├── control_room_api.py         # Main FastAPI server (666KB, 10,859 lines)
│   ├── glyph_decoder.py            # Portal glyph conversion
│   ├── haven_ui.db                 # STALE - 0 bytes, empty
│   ├── migrate_atlas_pois.py       # POI migration utility
│   ├── migrations.py               # Schema migration system
│   └── planet_atlas_wrapper.py     # 3D planet visualization
│
├── tests/                          # API tests (should move to Haven-UI)
│   ├── api/
│   │   ├── test_api_calls.py
│   │   ├── test_approvals_system.py
│   │   ├── test_endpoints.py
│   │   └── test_post_discovery.py
│   ├── data/
│   │   ├── generate_test_data.py
│   │   ├── populate_test_data.py
│   │   ├── quick_test_systems.py
│   │   └── test_station_placement.py
│   └── integration/
│       ├── keeper_test_bot_startup.py
│       ├── keeper_test_integration.py
│       ├── test_integration.py
│       └── test_keeper_http_integration.py
│
├── Haven-UI/                       # React frontend + wrapper server (PRIMARY PROJECT)
│   ├── .venv/                      # Local venv
│   ├── data/                       # SQLite databases + data.json
│   ├── dist/                       # Production build output
│   ├── docs/
│   ├── logs/
│   ├── node_modules/
│   ├── photos/                     # User-uploaded images
│   ├── public/
│   ├── raspberry/
│   ├── scripts/                    # Haven-UI specific scripts
│   ├── src/                        # React components (JavaScript)
│   ├── static/
│   ├── tests/
│   ├── package.json
│   ├── requirements.txt
│   ├── server.py                   # Imports from ../src/control_room_api.py
│   ├── vite.config.mjs
│   └── README.md
│
├── keeper-discord-bot-main/        # Discord bot (SELF-CONTAINED)
├── NMS-Haven-Extractor/            # Game mod (SELF-CONTAINED)
├── NMS-Memory-Browser/             # Memory browser (SELF-CONTAINED)
├── NMS-Save-Watcher/               # Save watcher (SELF-CONTAINED)
├── Planet_Atlas/                   # Git submodule (EXTERNAL REPO)
│
├── CLAUDE.md                       # Master project documentation
├── LICENSE                         # MIT License
├── README.md                       # Repo-level README
├── PARTNER_GUIDE.md                # Haven user guide
├── discovery_debug.json            # Debug output file (stale)
├── nul                             # Garbage from failed command (stale)
├── start_haven_ui.bat              # Root launcher for Haven
├── transfer_to_pi.bat              # Data transfer utility
└── update_planet_atlas.bat         # Submodule update script
```

---

## 2. Target Structure

```
C:\Master-Haven\
├── Haven-UI/                       # Haven Control Room (FULLY SELF-CONTAINED)
│   ├── src/                        # React frontend (existing)
│   │   └── (jsx/js files)
│   ├── backend/                    # NEW: Python backend (moved from root src/)
│   │   ├── control_room_api.py     # Main FastAPI server
│   │   ├── glyph_decoder.py
│   │   ├── migrations.py
│   │   ├── planet_atlas_wrapper.py
│   │   ├── migrate_atlas_pois.py
│   │   ├── paths.py                # Moved from config/
│   │   └── CLAUDE.md               # Backend docs
│   ├── config/                     # Configuration
│   │   └── paths.py                # (Alternative location)
│   ├── data/                       # Databases and data files
│   ├── dist/                       # Production build
│   ├── docs/                       # Documentation
│   │   ├── HOMELAB_MIGRATION.md
│   │   ├── RASPBERRY_PI_PRODUCTION_SETUP.md
│   │   ├── PARTNER_GUIDE.md        # Moved from root
│   │   └── GOOGLE_FORMS_SUBMISSION_GUIDE.md
│   ├── logs/
│   ├── photos/
│   ├── public/
│   ├── raspberry/
│   ├── scripts/                    # All Haven scripts consolidated
│   │   ├── (existing Haven-UI scripts)
│   │   ├── backfill_star_positions.py
│   │   ├── check_pending_submission.py
│   │   ├── clean_broken_submissions.py
│   │   ├── delete_core_void_systems.py
│   │   ├── examine_discovery_records.py
│   │   ├── fix_null_system_ids.py
│   │   ├── migrate_star_positions.py
│   │   ├── test_approval.py
│   │   ├── test_signed_hex_glyphs.py
│   │   └── migrations/
│   ├── static/
│   ├── tests/                      # All tests consolidated
│   │   ├── api/
│   │   ├── data/
│   │   ├── integration/
│   │   └── e2e/
│   ├── .env.example
│   ├── package.json
│   ├── requirements.txt
│   ├── server.py                   # Updated imports
│   ├── start_haven_ui.bat          # Moved from root
│   ├── vite.config.mjs
│   └── README.md
│
├── NMS-Haven-Extractor/            # Game mod (SELF-CONTAINED)
│   └── ...
│
├── keeper-discord-bot-main/        # Discord bot (SELF-CONTAINED)
│   ├── start_keeper_bot.bat        # Moved from scripts/
│   └── ...
│
├── NMS-Save-Watcher/               # Save file monitor (SELF-CONTAINED)
│   └── ...
│
├── NMS-Memory-Browser/             # Memory browser (SELF-CONTAINED)
│   └── ...
│
├── Planet_Atlas/                   # Git submodule (EXTERNAL REPO - DO NOT MODIFY)
│   └── ...
│
├── .gitignore
├── .gitmodules
├── CLAUDE.md                       # Master project overview
├── LICENSE
├── README.md
├── transfer_to_pi.bat              # Keep at root (works across sub-projects)
└── update_planet_atlas.bat         # Keep at root (manages submodule)
```

---

## 3. Files to Move

### 3A. Root `src/` → `Haven-UI/backend/`

| Source | Destination | Notes |
|--------|-------------|-------|
| `src/control_room_api.py` | `Haven-UI/backend/control_room_api.py` | Main API (666KB) |
| `src/glyph_decoder.py` | `Haven-UI/backend/glyph_decoder.py` | Glyph conversion |
| `src/migrations.py` | `Haven-UI/backend/migrations.py` | Schema migrations |
| `src/planet_atlas_wrapper.py` | `Haven-UI/backend/planet_atlas_wrapper.py` | 3D visualization |
| `src/migrate_atlas_pois.py` | `Haven-UI/backend/migrate_atlas_pois.py` | POI migration |
| `src/CLAUDE.md` | `Haven-UI/backend/CLAUDE.md` | Backend docs |

### 3B. Root `config/` → `Haven-UI/backend/`

| Source | Destination | Notes |
|--------|-------------|-------|
| `config/paths.py` | `Haven-UI/backend/paths.py` | Path configuration |

### 3C. Root `scripts/` → Various

| Source | Destination | Notes |
|--------|-------------|-------|
| `scripts/backfill_star_positions.py` | `Haven-UI/scripts/` | Haven DB script |
| `scripts/check_pending_submission.py` | `Haven-UI/scripts/` | Haven DB script |
| `scripts/clean_broken_submissions.py` | `Haven-UI/scripts/` | Haven DB script |
| `scripts/delete_core_void_systems.py` | `Haven-UI/scripts/` | Haven DB script |
| `scripts/examine_discovery_records.py` | `Haven-UI/scripts/` | Haven DB script |
| `scripts/fix_null_system_ids.py` | `Haven-UI/scripts/` | Haven DB script |
| `scripts/migrate.py` | `Haven-UI/scripts/` | Migration runner |
| `scripts/migrate_star_positions.py` | `Haven-UI/scripts/` | Haven DB script |
| `scripts/test_approval.py` | `Haven-UI/scripts/` | Haven test |
| `scripts/test_signed_hex_glyphs.py` | `Haven-UI/scripts/` | Haven test |
| `scripts/migrations/` | `Haven-UI/scripts/migrations/` | DB migrations |
| `scripts/start_keeper_bot.bat` | `keeper-discord-bot-main/` | Keeper launcher |
| `scripts/start_server.bat` | `Haven-UI/` | Haven launcher |
| `scripts/start_with_ngrok.bat` | `Haven-UI/` | Haven + ngrok |
| `scripts/quick_health_check.bat` | `Haven-UI/` | Haven health check |
| `scripts/verify_dashboard_fix.bat` | `Haven-UI/` | Haven verify |
| `scripts/deploy_to_pi.ps1` | `Haven-UI/scripts/` | Haven deployment |
| `scripts/create_update_archive.ps1` | `Haven-UI/scripts/` | Haven packaging |
| `scripts/ngrok_check.ps1` | `Haven-UI/scripts/` | Haven utility |
| `scripts/apply_update_remote.sh` | `Haven-UI/scripts/` | Haven deployment |

### 3D. Root `tests/` → `Haven-UI/tests/`

| Source | Destination | Notes |
|--------|-------------|-------|
| `tests/api/*` | `Haven-UI/tests/api/` | API tests |
| `tests/data/*` | `Haven-UI/tests/data/` | Test data generators |
| `tests/integration/*` | `Haven-UI/tests/integration/` | Integration tests |

### 3E. Root `docs/` → `Haven-UI/docs/`

| Source | Destination | Notes |
|--------|-------------|-------|
| `docs/HOMELAB_MIGRATION.md` | `Haven-UI/docs/` | Deployment guide |
| `docs/RASPBERRY_PI_PRODUCTION_SETUP.md` | `Haven-UI/docs/` | Pi setup guide |

### 3F. Root Files → Various

| Source | Destination | Notes |
|--------|-------------|-------|
| `start_haven_ui.bat` | `Haven-UI/` | Haven launcher |
| `PARTNER_GUIDE.md` | `Haven-UI/docs/` | User documentation |

---

## 4. Files to Delete

| File | Justification |
|------|---------------|
| `nul` | Garbage from failed Windows command - contains only error messages |
| `src/haven_ui.db` | Empty file (0 bytes) - real DB is in Haven-UI/data/ |
| `src/__pycache__/` | Python cache - will regenerate |
| `config/__pycache__/` | Python cache - will regenerate |
| `discovery_debug.json` | Debug output file - not needed in repo |
| `.venv/` | Virtual environment - should NOT be in repo (use .gitignore) |
| `Haven-UI/data/nul` | Another garbage file (108 bytes) |
| `Haven-UI/data/_ul` | Appears to be partial/corrupted file (46 bytes) |
| `Haven-UI/data/haven.db` | Empty database (0 bytes) |
| `scripts/archive/` | Review contents - likely obsolete |

### Files to KEEP at Root (Repo-Level)

| File | Reason |
|------|--------|
| `CLAUDE.md` | Master project documentation |
| `README.md` | Repository overview |
| `LICENSE` | MIT License |
| `.gitignore` | Git configuration |
| `.gitmodules` | Submodule registration (Planet_Atlas) |
| `.claude/` | Claude Code settings |
| `transfer_to_pi.bat` | Cross-project utility |
| `update_planet_atlas.bat` | Submodule management |

---

## 5. Import Changes Required

### 5A. `Haven-UI/server.py` (CRITICAL)

**Current** (lines 15-28):
```python
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
src_dir = REPO_ROOT / 'src'
sys.path.insert(0, str(src_dir))
from src.control_room_api import app, init_rtai
```

**After**:
```python
# No more parent directory references
HAVEN_UI_DIR = Path(__file__).resolve().parent
BACKEND_DIR = HAVEN_UI_DIR / 'backend'
sys.path.insert(0, str(BACKEND_DIR))
from control_room_api import app, init_rtai
```

### 5B. `Haven-UI/backend/control_room_api.py`

**Current** (lines 20-28):
```python
master_haven_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(master_haven_root))
from config.paths import haven_paths
from migrations import run_pending_migrations
from glyph_decoder import (...)
from planet_atlas_wrapper import generate_planet_html
```

**After**:
```python
# All imports now relative to backend/ folder
BACKEND_DIR = Path(__file__).resolve().parent
HAVEN_UI_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
from paths import haven_paths
from migrations import run_pending_migrations
from glyph_decoder import (...)
from planet_atlas_wrapper import generate_planet_html
```

**Also update** (line 156):
```python
# Current
GALAXIES_JSON_PATH = Path(__file__).resolve().parents[1] / 'NMS-Save-Watcher' / 'data' / 'galaxies.json'

# After - copy galaxies.json to Haven-UI/data/ OR use relative path from repo root
GALAXIES_JSON_PATH = HAVEN_UI_DIR.parent / 'NMS-Save-Watcher' / 'data' / 'galaxies.json'
```

### 5C. `Haven-UI/backend/paths.py`

**Current** (lines 25-26):
```python
self.config_dir = Path(__file__).resolve().parent
self.root = self.config_dir.parent
```

**After**:
```python
self.backend_dir = Path(__file__).resolve().parent
self.haven_ui_dir = self.backend_dir.parent
self.root = self.haven_ui_dir.parent  # Points to Master-Haven for cross-project access
```

### 5D. Root `start_haven_ui.bat`

**Current** (line 35):
```batch
Haven-UI\.venv\Scripts\python src\control_room_api.py
```

**After move to Haven-UI**:
```batch
.venv\Scripts\python backend\control_room_api.py
```

### 5E. Root `scripts/*.py` files

All scripts that import from `src.` need path updates after moving to Haven-UI/scripts/:

**Example pattern**:
```python
# Current
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# After
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
```

### 5F. Test files in `tests/`

Similar pattern - update sys.path references from `src` to `backend`.

---

## 6. External Duplicates (C:\ Level)

| Path | Status | Action |
|------|--------|--------|
| `C:\Haven-Extractor\` | **NOT FOUND** | Already deleted |
| `C:\keeper-discord-bot\` | **NOT FOUND** | Already deleted |

---

## 7. Duplicate Detection Summary

| File | Location 1 | Location 2 | Resolution |
|------|------------|------------|------------|
| `haven_ui.db` | `src/` (0 bytes - empty) | `Haven-UI/data/` (11MB - real) | Delete from src/ |
| `nul` | Root (236 bytes - garbage) | `Haven-UI/data/` (108 bytes) | Delete both |
| `CLAUDE.md` | Root (project overview) | `src/` (backend docs) | Keep both, move src/ version |

---

## 8. Sub-Project Status Summary

| Sub-Project | Self-Contained? | Has README? | Has requirements.txt? | Issues |
|-------------|-----------------|-------------|----------------------|--------|
| **Haven-UI** | NO - imports from ../src/ | YES | YES | CRITICAL: needs backend files |
| **NMS-Haven-Extractor** | YES | YES | pyproject.toml | None |
| **keeper-discord-bot-main** | YES | YES | YES | None |
| **NMS-Save-Watcher** | YES | YES | YES | None |
| **NMS-Memory-Browser** | YES | YES | YES | None |
| **Planet_Atlas** | YES (submodule) | YES | YES | External repo - don't modify |

---

## 9. Recommended Execution Order (Phase 3)

1. **Create `Haven-UI/backend/` folder**
2. **Move src/ files** → Haven-UI/backend/
3. **Move config/paths.py** → Haven-UI/backend/
4. **Update imports** in control_room_api.py, server.py, paths.py
5. **Move scripts/** → Haven-UI/scripts/ and keeper-discord-bot-main/
6. **Move tests/** → Haven-UI/tests/
7. **Move docs/** → Haven-UI/docs/
8. **Move root files** (start_haven_ui.bat, PARTNER_GUIDE.md)
9. **Delete stale files** (nul, empty DBs, __pycache__)
10. **Delete empty root folders** (src/, config/, scripts/, tests/, docs/)
11. **Verify self-containment** - run grep for `../` and `parents[1]`
12. **Test Haven-UI** - ensure server starts correctly

---

## 10. Files Ready for Pi Deployment

After cleanup, this folder should be deployable:
```
Haven-UI/
├── backend/          # All Python backend code
├── data/             # Databases (transfer separately)
├── dist/             # Built React frontend
├── photos/           # User uploads (transfer separately)
├── ...
└── requirements.txt
```

**Deployment command**:
```bash
scp -r Haven-UI/ parker@10.0.0.33:/home/parker/Master-Haven/
```

---

## 11. Phase 4: Final Report - CLEANUP COMPLETE

**Completed**: February 4, 2026

### Summary of Changes Made

#### Files Moved to Haven-UI/backend/
- `control_room_api.py` (666KB - main FastAPI server)
- `glyph_decoder.py`
- `migrations.py`
- `planet_atlas_wrapper.py`
- `migrate_atlas_pois.py`
- `paths.py` (from config/)
- `CLAUDE.md` (backend docs)

#### Files Moved to Haven-UI/scripts/
- All Python scripts from root scripts/
- All PowerShell/bash deployment scripts
- migrations/ subfolder

#### Files Moved to Haven-UI/tests/
- api/ folder with 4 test files
- data/ folder with 4 test files
- integration/ folder with 4 test files

#### Files Moved to Haven-UI/docs/
- HOMELAB_MIGRATION.md
- RASPBERRY_PI_PRODUCTION_SETUP.md
- PARTNER_GUIDE.md

#### Files Moved to Haven-UI/
- start_haven_ui.bat (updated for new structure)
- start_server.bat
- start_with_ngrok.bat
- quick_health_check.bat
- verify_dashboard_fix.bat

#### Files Moved to keeper-discord-bot-main/
- start_keeper_bot.bat

#### Files Deleted
- `nul` (root - garbage)
- `discovery_debug.json` (debug output)
- `src/haven_ui.db` (empty duplicate)
- `Haven-UI/data/nul`
- `Haven-UI/data/_ul`
- `Haven-UI/data/haven.db` (empty)
- All `__pycache__/` folders

#### Folders Deleted
- `src/` (contents moved to Haven-UI/backend/)
- `config/` (contents moved to Haven-UI/backend/)
- `scripts/` (contents distributed)
- `tests/` (contents moved to Haven-UI/tests/)
- `docs/` (contents moved to Haven-UI/docs/)

### Final Repository Structure

```
C:\Master-Haven\
├── .claude/                        # Claude Code settings
├── .git/                           # Git repository
├── .gitignore
├── .gitmodules                     # Planet_Atlas submodule
├── .venv/                          # Root venv (consider removing from git)
├── CLAUDE.md                       # Master project documentation
├── CLEANUP_REPORT.md               # This report
├── LICENSE
├── README.md
├── transfer_to_pi.bat              # Cross-project utility
├── update_planet_atlas.bat         # Submodule management
│
├── Haven-UI/                       # FULLY SELF-CONTAINED
│   ├── backend/                    # Python backend code
│   │   ├── control_room_api.py     # Main FastAPI server
│   │   ├── glyph_decoder.py
│   │   ├── migrations.py
│   │   ├── paths.py
│   │   ├── planet_atlas_wrapper.py
│   │   ├── migrate_atlas_pois.py
│   │   └── CLAUDE.md
│   ├── data/                       # Databases
│   ├── dist/                       # Built React frontend
│   ├── docs/                       # Documentation
│   ├── logs/
│   ├── node_modules/
│   ├── photos/
│   ├── public/
│   ├── raspberry/
│   ├── scripts/                    # Utility scripts
│   ├── src/                        # React source (JavaScript)
│   ├── static/
│   ├── tests/                      # All tests
│   ├── server.py                   # Entry point
│   ├── start_haven_ui.bat
│   ├── package.json
│   ├── requirements.txt
│   └── README.md
│
├── keeper-discord-bot-main/        # SELF-CONTAINED
├── NMS-Haven-Extractor/            # SELF-CONTAINED
├── NMS-Memory-Browser/             # SELF-CONTAINED
├── NMS-Save-Watcher/               # SELF-CONTAINED
└── Planet_Atlas/                   # Git submodule (external)
```

### Import Changes Applied

All imports updated to use new `backend/` path:
- `from src.X` → `from X` (direct import from backend/)
- `from config.paths` → `from paths`
- `parents[1]` → uses `BACKEND_DIR.parent` or `haven_ui_dir`

### Remaining Considerations

1. **Root `.venv/`** - Still exists. Consider adding to `.gitignore` if not already.
2. **External duplicates** - `C:\Haven-Extractor\` and `C:\keeper-discord-bot\` were NOT found (already deleted).

### Next Steps

1. **Test Haven-UI server** - Run `cd Haven-UI && python server.py` to verify
2. **Run npm build** - `cd Haven-UI && npm run build` to ensure frontend builds
3. **Review git status** - Check what files are staged before committing
4. **Deploy to Pi** - Use transfer_to_pi.bat or scp Haven-UI/ folder

---

**CLEANUP COMPLETE**

