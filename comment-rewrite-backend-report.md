# Comment Rewrite — Backend Report
**Date:** 2026-03-08

## Files Completed
| File | Status | Approx comments added | Notes |
|------|--------|----------------------|-------|
| control_room_api.py | Complete | ~60 | Docstrings, section headers, NOTE comments across all 10 endpoint groups |
| migrations.py | Complete | ~50 | One-line comment above each of 47 migrations, plus framework function docs |
| glyph_decoder.py | Already documented | 0 | File already had comprehensive docstrings, Args/Returns, and inline comments |
| paths.py | Already documented | 0 | File already had class/method docstrings and detection logic comments |
| image_processor.py | Already documented | 0 | File already had file-level docstring, function docstring with Args/Returns |

## Notable Design Decisions Documented

### # NOTE: INTENTIONAL DESIGN comments added:

1. **Super admin username "Haven"** (control_room_api.py ~line 1905)
   - "Parker's personal login, not a generic default"

2. **Default password hash** (control_room_api.py ~line 1907)
   - "Default password, changed on first login in production"

3. **Partner direct save vs pending queue** (control_room_api.py, save_system)
   - Partners with SYSTEM_CREATE bypass the pending queue and save directly (trusted partners; SYSTEM_CREATE flag controls this, not security)
   - Public submissions go to pending_systems queue for review (open by design)

4. **Extraction endpoint auth model** (control_room_api.py, /api/extraction)
   - Uses API key auth, not session auth
   - Routes to pending_systems queue (same as public submissions), not direct save
   - Deduplicates by updating existing pending rows

5. **Self-approval prevention** (control_room_api.py, approve_system/approve_discovery)
   - Super admin and partners exempt, sub-admins blocked
   - Matching by account_id first, then normalized username fallback

6. **Data restrictions model** (control_room_api.py ~line 2084)
   - Per-system visibility controls, field group redaction, map visibility modes
   - Super admin and owning partner bypass restrictions

7. **Source filter COALESCE pattern** (control_room_api.py, analytics endpoints)
   - NULL/legacy rows treated as 'manual' because source column was added later

8. **Save system delete-and-reinsert** (control_room_api.py, save_system)
   - Planets deleted and re-inserted rather than diffed — simpler than tracking adds/removes/updates

9. **Pending edits don't auto-apply** (control_room_api.py, pending_edits)
   - Approval marks as approved but does NOT auto-apply the changes

10. **Stub system idempotent** (control_room_api.py, create_system_stub)
    - Returns existing system if name/glyph matches instead of creating duplicate

## Verified
- All files compile: Yes
- Errors: None
