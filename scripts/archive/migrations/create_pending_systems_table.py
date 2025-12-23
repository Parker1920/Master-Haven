#!/usr/bin/env python3
"""
Create pending_systems table for System Approvals Queue
Run this script to add the new table to haven_ui.db
"""

import sqlite3
from pathlib import Path

# Database path
db_path = Path(__file__).parent / 'Haven-UI' / 'data' / 'haven_ui.db'

print(f"Database: {db_path}")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create pending_systems table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_systems (
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
        )
    ''')

    # Create index for status lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_pending_systems_status
        ON pending_systems(status)
    ''')

    # Create index for IP-based rate limiting
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_pending_systems_ip_date
        ON pending_systems(submitted_by_ip, submission_date)
    ''')

    conn.commit()

    # Verify table was created
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_systems'")
    result = cursor.fetchone()

    if result:
        print("[SUCCESS] pending_systems table created successfully!")

        # Show table schema
        cursor.execute("PRAGMA table_info(pending_systems)")
        columns = cursor.fetchall()
        print("\nTable Schema:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")

        # Show existing count
        cursor.execute("SELECT COUNT(*) FROM pending_systems")
        count = cursor.fetchone()[0]
        print(f"\nCurrent pending submissions: {count}")
    else:
        print("[ERROR] Failed to create table")

    conn.close()
    print("\n[SUCCESS] Database initialization complete!")

except sqlite3.Error as e:
    print(f"\n[ERROR] Database error: {e}")
    exit(1)
