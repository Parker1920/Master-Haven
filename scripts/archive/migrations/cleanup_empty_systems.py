#!/usr/bin/env python3
"""
Clean up empty test systems from haven_ui.db
Run this when the Control Room server is NOT running.
"""

import sqlite3
from pathlib import Path

# Database path
db_path = Path(__file__).parent / 'Haven-UI' / 'data' / 'haven_ui.db'

# Systems to remove (those with 0 planets)
empty_systems = ['Frr', 'Test System X', 'TestX-CLI']

print(f"Database: {db_path}")
print(f"Systems to delete: {empty_systems}\n")

if not db_path.exists():
    print(f"ERROR: Database not found at {db_path}")
    exit(1)

try:
    conn = sqlite3.connect(str(db_path), timeout=1.0)
    c = conn.cursor()

    # Show current system count
    c.execute('SELECT COUNT(*) FROM systems')
    before_count = c.fetchone()[0]
    print(f"Systems before cleanup: {before_count}")

    # Delete empty systems
    deleted = 0
    for sys_name in empty_systems:
        c.execute('DELETE FROM systems WHERE name = ?', (sys_name,))
        if c.rowcount > 0:
            print(f"  ✓ Deleted: {sys_name}")
            deleted += 1
        else:
            print(f"  - Not found: {sys_name}")

    conn.commit()

    # Show final count
    c.execute('SELECT COUNT(*) FROM systems')
    after_count = c.fetchone()[0]
    print(f"\nSystems after cleanup: {after_count}")
    print(f"Total deleted: {deleted}")

    # List remaining systems
    print("\nRemaining systems:")
    c.execute('SELECT name, region FROM systems ORDER BY name')
    for row in c.fetchall():
        print(f"  - {row[0]} ({row[1]})")

    conn.close()
    print("\n✅ Cleanup complete!")

except sqlite3.OperationalError as e:
    print(f"\n❌ ERROR: {e}")
    print("\nThe database may be locked. Please:")
    print("1. Stop the Control Room server")
    print("2. Run this script again")
    print("3. Restart the Control Room server")
    exit(1)
