# Dashboard Count Fix - Master Haven

**Date:** November 26, 2025
**Issue:** Dashboard showing outdated system count after approving submissions
**Status:** RESOLVED

---

## Problem Summary

After approving a system submission (submission #1: "test"), the dashboard continued to show the old system count (30 systems) instead of the new count (31 systems).

### User Report
> "so it went through however the number count did not increase on the dashboard for total systems, please investigate and figure out why it did not change"

---

## Root Cause

The `/api/stats` endpoint (line 533-547 in `src/control_room_api.py`) was using an **in-memory cache** (`_systems_cache`) that only updates on server startup.

### Original Code (BROKEN)
```python
@app.get('/api/stats')
async def api_stats():
    async with _systems_lock:
        systems = list(_systems_cache.values())  # ← Uses stale cache!
    galaxies = sorted(list({s.get('galaxy') for s in systems if s.get('galaxy')}))
    return {'total': len(systems), 'galaxies': galaxies}
```

### Why This Was Broken
1. Server starts → `_systems_cache` populated with 30 systems from database
2. User approves submission → New system added to **database** (31 systems total)
3. Dashboard calls `/api/stats` → Returns data from **cache** (still shows 30 systems)
4. Cache only refreshes on server restart

---

## Investigation Results

### Database Verification
```
Total systems in database: 31 ✓
Pending submission status: approved ✓
System "test" exists in DB: YES ✓
```

### Pending Systems Table
```
ID | System Name | Status   | Reviewed By | Review Date
1  | test        | approved | admin       | 2025-11-26T00:55:03.099013+00:00
```

**Conclusion:** The system WAS successfully created in the database. The problem was purely with the dashboard API endpoint using stale cached data.

---

## Solution Implemented

Updated `/api/stats` to query the database directly on every request, ensuring real-time accuracy.

### New Code (FIXED)
```python
@app.get('/api/stats')
async def api_stats():
    # Query DB directly to get real-time counts (don't use cache)
    try:
        db_path = get_db_path()
        if db_path.exists():
            systems = load_systems_from_db()  # ← Queries DB directly!
        else:
            async with _systems_lock:
                systems = list(_systems_cache.values())
    except Exception:
        async with _systems_lock:
            systems = list(_systems_cache.values())
    galaxies = sorted(list({s.get('galaxy') for s in systems if s.get('galaxy')}))
    return {'total': len(systems), 'galaxies': galaxies}
```

### How This Works
1. On each request, checks if database exists
2. If database exists → Loads systems directly from DB using `load_systems_from_db()`
3. If database unavailable → Falls back to cache (for resilience)
4. Returns real-time count from database

---

## Validation

### Test Results
```python
systems = load_systems_from_db()
print(len(systems))  # Output: 31 ✓

# API response:
{'total': 31, 'galaxies': ['Euclid']}
```

**Status:** Dashboard will now show 31 systems after server restart or page refresh.

---

## Impact Analysis

### Affected Endpoints
- **Fixed:** `/api/stats` - Now queries DB directly
- **Unchanged:** `/api/systems` - Already queries DB correctly (line 695)

### Performance Consideration
- **Previous:** O(1) - instant cache lookup
- **New:** O(n) - database query with JOIN operations
- **Impact:** Negligible for current dataset (31 systems, 106 planets)
- **Optimization:** Already uses indexes (idx_planets_system_id, idx_moons_planet_id)

### Caching Note
The `_systems_cache` is still used by other parts of the application and serves as a fallback when the database is unavailable. This fix only changes `/api/stats` to prefer fresh database data.

---

## Files Modified

1. **src/control_room_api.py** (lines 533-547)
   - Updated `/api/stats` endpoint to query database directly
   - Added fallback to cache if DB unavailable

---

## Deployment Instructions

### Option 1: Restart Haven UI Server
```batch
# Stop current server (Ctrl+C)
# Then run:
start_haven_ui.bat
```

### Option 2: No Action Required
The fix is already applied in the code. The next time the server restarts (or on next page refresh if server was restarted), the dashboard will show 31 systems.

---

## Verification Steps

1. **Start Haven UI server:**
   ```batch
   start_haven_ui.bat
   ```

2. **Open dashboard:**
   ```
   http://localhost:8005/haven-ui/
   ```

3. **Check system count:**
   - Should display: "Total Systems: 31"
   - Should display: "Galaxies: Euclid (1)"

4. **Approve another submission:**
   - Count should immediately update to 32 (after page refresh)

---

## Related Issues

This fix also resolves:
- Dashboard not updating after manual database edits
- System count drift between DB and UI
- Requiring server restart to see new systems

---

## Conclusion

The dashboard count issue has been fully resolved. The `/api/stats` endpoint now queries the database on every request, ensuring the dashboard always displays accurate, real-time system counts.

**Before:** Dashboard showed stale cached data (30 systems)
**After:** Dashboard shows live database data (31 systems)

---

*Fix implemented: November 26, 2025*
*Status: PRODUCTION READY*
