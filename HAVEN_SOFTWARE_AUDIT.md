# Haven Software Audit - Post-Cleanup Report

**Date:** 2026-02-27
**Performed by:** Claude Code (post-cleanup verification)
**Previous audit:** 2026-02-27 (pre-cleanup)

---

## Summary

A comprehensive cleanup was performed on the Master Haven repository based on findings from the initial software audit. All issues have been resolved across 8 commits.

### Cleanup Commits
| Commit | Description |
|--------|-------------|
| `2a89ef4` | fix: update OpenGraph meta tags to havenmap.online |
| `5a136d5` | fix: replace all ngrok URLs with havenmap.online |
| `87fe258` | fix: update port references from 8000 to 8005 |
| `fdaa1e7` | cleanup: remove dead scripts, stale databases, superseded static files, empty dirs |
| `491f0d0` | fix: update stale version strings in launcher scripts |
| `26e583f` | fix: exclude unnecessary sub-projects from Docker build context |
| `f9494f1` | docs: add README for NMS-Debug-Enabler |
| `b2b4bce` | docs: regenerate CLAUDE.md with current metrics and paths |

### Git Maintenance
- `.git/` size reduced from **636 MB → 340 MB** (46% reduction) via `git gc --aggressive --prune=now`

---

## Verification Results

### 1. Ngrok References — RESOLVED

**Active user-facing files:** Zero ngrok URLs remain.

**Remaining intentional references (not actionable):**
| Location | Count | Reason |
|----------|-------|--------|
| `NMS-Haven-Extractor/old_versions/` | 11 | Historical archive — old extractor versions |
| `Haven-UI/docs/HOMELAB_MIGRATION.md` | 6 | Migration narrative — past tense, describes completed migration |
| `Haven-UI/docs/RASPBERRY_PI_PRODUCTION_SETUP.md` | 2 | Historical cost comparison ("Previous ngrok cost: $20/month") |
| `NMS-Haven-Extractor/dist/.../haven_extractor.py` | 1 | SSL comment in dist — do NOT touch (intentional embedded Python) |

**Total remaining:** 20 references, all in historical/archived files. None are user-facing or functional.

### 2. Port References (8000 → 8005) — RESOLVED

All 5 files updated:
- [x] `Haven-UI/README.md`
- [x] `Haven-UI/start_server.bat`
- [x] `Haven-UI/run_server.ps1`
- [x] `Haven-UI/tests/api/test_approvals_system.py`
- [x] `NMS-Save-Watcher/config.example.json`

**Verification:** Zero files contain `localhost:8000` (excluding this audit file).

### 3. Dead Files — REMOVED

**Deleted scripts:**
- [x] `Haven-UI/start_with_ngrok.bat`
- [x] `Haven-UI/scripts/ngrok_check.ps1`
- [x] `Haven-UI/verify_dashboard_fix.bat`
- [x] `Haven-UI/run_haven_ui.bat`
- [x] `NMS-Haven-Extractor/utility_scripts/INSTALL_EXTRACTOR.bat`
- [x] `NMS-Haven-Extractor/utility_scripts/RUN_DEBUG_TEST.bat`

**Deleted stale databases (from disk, were gitignored):**
- [x] `Haven-UI/data/haven_data.db` (7.7 MB legacy)
- [x] `Haven-UI/data/haven_ui_new.db` (36 KB empty test)
- [x] `Haven-UI/data/uploaded.db` (1.3 MB old upload)
- [x] `Haven-UI/data/haven_ui_backup_star_positions_*.db` (228 KB backup)
- **NOT deleted:** `haven_ui.db` (active database, 12.5 MB)

**Deleted empty directories:**
- [x] `Haven-UI/Haven-UI/` (empty nested folder)
- [x] `files/` (empty root directory)

**Deleted superseded static files:**
- [x] `Haven-UI/static/` (entire directory — old pre-React vanilla HTML SPA)
  - index.html, systems.html, wizard.html, logs.html, rtai.html, settings.html, tests.html
  - spa.js, sw.js, manifest.webmanifest

### 4. CLAUDE.md Metrics — UPDATED

| Field | Old Value | New Value |
|-------|-----------|-----------|
| Table count | 19 | 37 |
| Endpoint count | 70+ | 235 |
| control_room_api.py lines | 10,859 | 18,752 |
| control_room_api.py path | `src/control_room_api.py` | `Haven-UI/backend/control_room_api.py` |
| Page count | 15+ | 23 |
| Component count | 27+ | 37 |
| Schema version | v1.31.0 | v1.45.0 |

Additional CLAUDE.md changes:
- [x] Removed Roundtable AI from architecture diagram and sub-project table
- [x] Added NMS-Debug-Enabler to Quick Reference and Game Integration sections
- [x] War Room noted as WIP (18 tables, 73 endpoints)
- [x] Keeper bot noted as community-maintained
- [x] All file paths updated to `Haven-UI/backend/`
- [x] Public access section updated from ngrok to `havenmap.online`

### 5. .dockerignore — UPDATED

Added exclusions:
- [x] `NMS-Haven-Extractor/dist/` (contains embedded Python 3.11 runtime)
- [x] `NMS-Debug-Enabler/` (game mod, not needed in Docker)
- [x] `Planet_Atlas/` (separate Dash app, not part of Haven container)

### 6. Version Strings — UPDATED

| File | Old Version | New Version |
|------|-------------|-------------|
| `Haven-UI/start_haven_ui.bat` | v1.14.0 | v1.38.1 |
| `NMS-Haven-Extractor/dist/.../RUN_HAVEN_EXTRACTOR.bat` | v9.0.0 | v1.5.1 |
| `NMS-Haven-Extractor/dist/.../FIRST_TIME_SETUP.bat` | v9.0.0 | v1.5.1 |

### 7. OpenGraph Meta Tags — FIXED

Both files updated with `https://havenmap.online` URLs:
- [x] `Haven-UI/index.html` — og:image, og:url, twitter:image
- [x] `Haven-UI/public/VH-Map-ThreeJS.html` — og:image, og:url, twitter:image

### 8. NMS-Debug-Enabler Documentation — ADDED

- [x] `NMS-Debug-Enabler/README.md` created with:
  - Project description and version (1.0.0)
  - Feature list (260+ debug flags, 7 presets)
  - Requirements and usage instructions
  - Project structure

---

## Current Repository State

### Metrics
| Metric | Value |
|--------|-------|
| Backend API lines | 18,752 |
| API endpoints | 235 (132 GET, 66 POST, 22 PUT, 15 DELETE) |
| Database tables | 37 |
| Schema version | v1.45.0 |
| Frontend pages | 23 |
| Frontend components | 37 |
| Sub-projects | 7 (Haven-UI, Extractor, Debug-Enabler, Memory Browser, Save Watcher, Keeper Bot, Planet Atlas) |
| `.git/` size | 340 MB (down from 636 MB) |

### Architecture Notes
- **War Room**: WIP — 18 tables, 73 endpoints, partially populated. Keep as-is.
- **Roundtable AI**: Removed from documentation. Dead endpoints still in code but not advertised.
- **Keeper Bot**: Being maintained by a community member. HTTP-only direction confirmed.
- **Extractor dist**: Contains embedded Python 3.11 — intentional for standalone distribution. Do not modify.
- **Hosting**: Self-hosted at `https://havenmap.online` on Raspberry Pi 5 8GB (10.0.0.229). ngrok fully retired.

---

## Final Checklist

- [x] OpenGraph meta tags point to havenmap.online
- [x] Zero ngrok URLs in user-facing files
- [x] Port 8005 everywhere (not 8000)
- [x] No dead scripts, stale DBs, or empty dirs
- [x] Version strings are current
- [x] .dockerignore excludes unnecessary sub-projects
- [x] NMS-Debug-Enabler has a README
- [x] CLAUDE.md reflects real metrics and paths
- [x] `git gc` has been run (636 MB → 340 MB)
- [ ] All changes pushed to remote (pending user action)
