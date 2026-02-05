#!/usr/bin/env python3
"""
Test System Approvals Queue Implementation
Verifies database table and basic functionality
"""

import sqlite3
from pathlib import Path
import json

# Database path
db_path = Path(__file__).parent / 'Haven-UI' / 'data' / 'haven_ui.db'

print("=" * 70)
print("SYSTEM APPROVALS QUEUE - VERIFICATION TEST")
print("=" * 70)

if not db_path.exists():
    print(f"\n[ERROR] Database not found at {db_path}")
    exit(1)

try:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Test 1: Verify table exists
    print("\n1. CHECKING DATABASE TABLE")
    print("-" * 70)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_systems'")
    result = cursor.fetchone()

    if result:
        print("[PASS] pending_systems table exists")

        # Show schema
        cursor.execute("PRAGMA table_info(pending_systems)")
        columns = cursor.fetchall()
        print("\nTable Schema:")
        for col in columns:
            print(f"  {col['name']:20} {col['type']:10} {'(PRIMARY KEY)' if col['pk'] else ''}")
    else:
        print("[FAIL] pending_systems table NOT found")
        print("\nRun this command first:")
        print("  python create_pending_systems_table.py")
        conn.close()
        exit(1)

    # Test 2: Verify indexes
    print("\n2. CHECKING INDEXES")
    print("-" * 70)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='pending_systems'")
    indexes = cursor.fetchall()

    expected_indexes = ['idx_pending_systems_status', 'idx_pending_systems_ip_date']
    found_indexes = [idx['name'] for idx in indexes if not idx['name'].startswith('sqlite_')]

    for expected in expected_indexes:
        if expected in found_indexes:
            print(f"[PASS] Index {expected} exists")
        else:
            print(f"[WARN] Index {expected} missing")

    # Test 3: Count existing submissions
    print("\n3. CHECKING EXISTING SUBMISSIONS")
    print("-" * 70)
    cursor.execute("SELECT COUNT(*) as count FROM pending_systems")
    total = cursor.fetchone()['count']
    print(f"Total submissions: {total}")

    cursor.execute("SELECT COUNT(*) as count FROM pending_systems WHERE status='pending'")
    pending = cursor.fetchone()['count']
    print(f"  Pending:  {pending}")

    cursor.execute("SELECT COUNT(*) as count FROM pending_systems WHERE status='approved'")
    approved = cursor.fetchone()['count']
    print(f"  Approved: {approved}")

    cursor.execute("SELECT COUNT(*) as count FROM pending_systems WHERE status='rejected'")
    rejected = cursor.fetchone()['count']
    print(f"  Rejected: {rejected}")

    # Test 4: Show recent submissions (if any)
    if total > 0:
        print("\n4. RECENT SUBMISSIONS")
        print("-" * 70)
        cursor.execute("""
            SELECT id, system_name, status, submitted_by, submission_date
            FROM pending_systems
            ORDER BY submission_date DESC
            LIMIT 5
        """)
        rows = cursor.fetchall()

        for row in rows:
            status_icon = {
                'pending': '[PENDING]',
                'approved': '[APPROVED]',
                'rejected': '[REJECTED]'
            }.get(row['status'], '[UNKNOWN]')

            print(f"{status_icon:12} ID:{row['id']:3} {row['system_name']:30} by {row['submitted_by'] or 'Anonymous':15} on {row['submission_date'][:10]}")

    # Test 5: Verify other required tables
    print("\n5. CHECKING RELATED TABLES")
    print("-" * 70)
    required_tables = ['systems', 'planets', 'moons', 'space_stations']
    for table in required_tables:
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cursor.fetchone():
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"[PASS] {table:20} ({count} records)")
        else:
            print(f"[WARN] {table:20} NOT FOUND")

    conn.close()

    # Summary
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    print("\n[SUCCESS] System Approvals Queue is ready!")
    print("\nNext steps:")
    print("  1. Start the Control Room server:")
    print("     python src\\control_room_api.py")
    print()
    print("  2. Open browser to http://localhost:8000/haven-ui/")
    print()
    print("  3. Test non-admin submission:")
    print("     - Go to 'Create' page (do NOT login)")
    print("     - Create a test system")
    print("     - Click 'Submit for Approval'")
    print()
    print("  4. Test admin review:")
    print("     - Click 'Unlock' and login")
    print("     - Click 'Approvals' in navbar")
    print("     - Review and approve/reject submission")
    print()

except sqlite3.Error as e:
    print(f"\n[ERROR] Database error: {e}")
    exit(1)
