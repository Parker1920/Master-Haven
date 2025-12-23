# System Approvals Queue - Implementation Complete

## Overview
Non-admin users can now submit star systems for approval instead of being blocked. Admins can review, approve, or reject submissions through a dedicated dashboard.

---

## What Was Implemented

### 1. Database Schema
- **New Table**: `pending_systems`
  - Stores submission data as JSON
  - Tracks status (pending/approved/rejected)
  - Records submitter IP for rate limiting
  - Includes review metadata (reviewer, date, rejection reason)

### 2. Backend API Endpoints (control_room_api.py)

#### Public Endpoints:
- `POST /api/submit_system` - Submit system for approval (non-admin)
  - Rate limited: 5 submissions per hour per IP
  - Validates system data
  - Prevents duplicate submissions

- `GET /api/pending_systems/count` - Get count of pending submissions (for badge)

#### Admin-Only Endpoints:
- `GET /api/pending_systems` - List all submissions
- `GET /api/pending_systems/{id}` - View submission details
- `POST /api/approve_system/{id}` - Approve and add to database
- `POST /api/reject_system/{id}` - Reject with reason

#### Modified Endpoint:
- `POST /api/save_system` - Now requires admin authentication

### 3. Frontend Components

#### Modified Files:
- **Wizard.jsx** - System creation form
  - Detects admin vs non-admin status
  - Shows "Save System" button for admins
  - Shows "Submit for Approval" button for non-admins
  - Displays yellow notice for non-admins
  - Routes to appropriate API endpoint

- **Navbar.jsx** - Navigation bar
  - Added "Approvals" link (admin-only)
  - Badge shows pending submission count
  - Auto-refreshes count every 30 seconds

- **App.jsx** - Routing
  - Added `/pending-approvals` route (admin-only)

#### New Files:
- **PendingApprovals.jsx** - Admin dashboard
  - Lists pending submissions
  - Shows recently reviewed submissions
  - Detailed review modal with full system data
  - Approve/reject actions with confirmation
  - Rejection reason input

### 4. Security Features
- Rate limiting: 5 submissions per hour per IP
- Input validation and sanitization
- Duplicate prevention (same name + pending status)
- Session-based admin authentication
- SQL injection protection (parameterized queries)

---

## File Changes Summary

### New Files Created:
1. `create_pending_systems_table.py` - Database initialization script
2. `Haven-UI/src/pages/PendingApprovals.jsx` - Admin dashboard component

### Modified Files:
1. `src/control_room_api.py` - Added 6 new API endpoints + rate limiting
2. `Haven-UI/src/pages/Wizard.jsx` - Admin detection + dual submission modes
3. `Haven-UI/src/components/Navbar.jsx` - Approvals link + badge count
4. `Haven-UI/src/App.jsx` - Added route for PendingApprovals

---

## Testing Instructions

### Step 1: Initialize Database Table
Run the database initialization script:
```
python C:\Users\parke\OneDrive\Desktop\Master-Haven\create_pending_systems_table.py
```

Expected output:
```
[SUCCESS] pending_systems table created successfully!
Table Schema:
  id (INTEGER)
  submitted_by (TEXT)
  ...
Current pending submissions: 0
```

### Step 2: Start the Control Room Server
```
python C:\Users\parke\OneDrive\Desktop\Master-Haven\src\control_room_api.py
```

Expected output:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Test Non-Admin Submission Flow

1. Open browser to: `http://localhost:8000/haven-ui/`
2. Navigate to **Create** (Wizard page)
3. **DO NOT** log in as admin
4. Create a test system:
   - Name: "Test Submission System"
   - Region: "Test Region"
   - Add 1-2 planets
5. Click **"Submit for Approval"**
6. Should see success message with submission ID

### Step 4: Test Admin Review Flow

1. Click **"Unlock"** button in navbar
2. Enter admin password (default: "Haven")
3. Click **"Approvals"** link in navbar
4. Should see notification badge with "1"
5. View pending submission:
   - Click **"Review"** button
   - Verify all system details are visible
   - Check planets, moons, space station data

### Step 5: Test Approval

1. In review modal, click **"Approve System"**
2. Confirm approval
3. System should be added to database
4. Should redirect/refresh and show in "Recently Reviewed"
5. Navigate to **"Systems"** page
6. Verify "Test Submission System" appears in list

### Step 6: Test Rejection

1. Create another test submission (as non-admin)
2. Login as admin and navigate to Approvals
3. Click **"Review"** on the new submission
4. Click **"Reject System"**
5. Enter rejection reason: "Test rejection - duplicate system"
6. Click **"Confirm Rejection"**
7. Verify submission moves to "Recently Reviewed" with rejected status

### Step 7: Test Rate Limiting

1. Logout from admin
2. Try to submit 6 systems in a row
3. 6th submission should fail with:
   ```
   Rate limit exceeded. Maximum 5 submissions per hour.
   ```

### Step 8: Test Admin-Only Save

1. Login as admin
2. Go to **Create** page
3. Should see **"Save System"** button (not "Submit for Approval")
4. Create a system and click Save
5. Should save directly without going through approvals queue

---

## API Endpoint Reference

### Submit System (Non-Admin)
```bash
POST /api/submit_system
Content-Type: application/json

{
  "name": "New System",
  "region": "Euclid",
  "x": 10, "y": 20, "z": 30,
  "description": "A test system",
  "planets": [...]
}

Response:
{
  "status": "ok",
  "message": "System submitted for approval",
  "submission_id": 1,
  "system_name": "New System"
}
```

### Get Pending Count
```bash
GET /api/pending_systems/count

Response:
{
  "count": 3
}
```

### Approve System (Admin Only)
```bash
POST /api/approve_system/1
Cookie: session=<admin_session>

Response:
{
  "status": "ok",
  "message": "System approved and added to database",
  "system_id": 15,
  "system_name": "New System"
}
```

### Reject System (Admin Only)
```bash
POST /api/reject_system/1
Cookie: session=<admin_session>
Content-Type: application/json

{
  "reason": "Duplicate system already exists"
}

Response:
{
  "status": "ok",
  "message": "System submission rejected",
  "submission_id": 1
}
```

---

## Database Schema

```sql
CREATE TABLE pending_systems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_by TEXT,
    submitted_by_ip TEXT,
    submission_date TEXT NOT NULL,
    system_data TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    reviewed_by TEXT,
    review_date TEXT,
    rejection_reason TEXT,
    system_name TEXT,
    system_region TEXT
);

CREATE INDEX idx_pending_systems_status ON pending_systems(status);
CREATE INDEX idx_pending_systems_ip_date ON pending_systems(submitted_by_ip, submission_date);
```

---

## Future Enhancements (Not Implemented)

1. **Email Notifications**
   - Notify submitter when system is approved/rejected
   - Requires email collection in submission form

2. **Edit Submission Before Approval**
   - Allow admins to modify system data before approving
   - Useful for fixing typos or adjusting coordinates

3. **Submission History for Users**
   - `GET /api/my_submissions` endpoint
   - Track submissions by IP or optional username

4. **Bulk Actions**
   - Approve/reject multiple submissions at once
   - Useful for managing large queues

5. **Auto-Approval Rules**
   - Whitelist trusted submitters
   - Auto-approve systems with certain criteria

6. **Submission Comments**
   - Allow admins to add notes to submissions
   - Thread-based discussion for complex reviews

---

## Troubleshooting

### Issue: "Admin authentication required" on save
**Solution**: Make sure you're logged in as admin before saving systems

### Issue: Badge count not updating
**Solution**: Wait 30 seconds (auto-refresh interval) or refresh the page

### Issue: Rate limit blocking submissions
**Solution**: Wait 1 hour or clear rate limit in server restart

### Issue: Database table not found
**Solution**: Run `create_pending_systems_table.py` script first

### Issue: Submissions not appearing in admin dashboard
**Solution**:
1. Check database: `SELECT * FROM pending_systems;`
2. Verify API endpoint returns data: `GET /api/pending_systems`
3. Check browser console for JavaScript errors

---

## Implementation Statistics

- **Backend Code**: ~400 lines (6 endpoints + validation + rate limiting)
- **Frontend Code**: ~350 lines (PendingApprovals component)
- **Database**: 1 new table, 2 indexes
- **Modified Files**: 4
- **New Files**: 2
- **Total Development Time**: ~2 hours

---

## Completion Checklist

- [x] Create pending_systems database table
- [x] Implement POST /api/submit_system endpoint
- [x] Implement GET /api/pending_systems endpoint
- [x] Implement POST /api/approve_system/{id} endpoint
- [x] Implement POST /api/reject_system/{id} endpoint
- [x] Implement GET /api/pending_systems/count endpoint
- [x] Add rate limiting (5 per hour per IP)
- [x] Add input validation and sanitization
- [x] Modify /api/save_system to require admin auth
- [x] Update Wizard.jsx for admin detection
- [x] Create PendingApprovals.jsx dashboard
- [x] Add Approvals link to Navbar with badge
- [x] Add route to App.jsx
- [ ] End-to-end testing (ready for user)

---

## Next Steps

1. **Test the implementation** following the Testing Instructions above
2. **Report any issues** or unexpected behavior
3. **Consider future enhancements** based on usage patterns
4. **Monitor submission quality** to identify common rejection reasons

---

*Implementation completed: 2025-11-18*
*Status: Ready for testing*
