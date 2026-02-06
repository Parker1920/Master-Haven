"""
Clean Broken Test Submissions
==============================
Removes broken test systems and resets their pending submissions to "pending" status
so they can be re-approved with the fixed code.
"""

import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / 'data' / 'haven_ui.db'
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=" * 60)
print("Cleaning Broken Test Submissions")
print("=" * 60)

# Find test systems
cursor.execute('SELECT id, name FROM systems WHERE name IN ("test", "tesetes")')
test_systems = cursor.fetchall()

print(f"\nFound {len(test_systems)} test systems:")
for sys_id, sys_name in test_systems:
    # Check for planets
    cursor.execute('SELECT COUNT(*) FROM planets WHERE system_id = ?', (sys_id,))
    planet_count = cursor.fetchone()[0]
    print(f"  - {sys_name} (id={sys_id}): {planet_count} planets")

# Delete test systems
print("\nDeleting test systems...")
cursor.execute('DELETE FROM systems WHERE name IN ("test", "tesetes")')
deleted = cursor.rowcount
print(f"  [OK] Deleted {deleted} systems")

# Reset pending submissions to "pending" status
print("\nResetting pending submissions...")
cursor.execute('''
    UPDATE pending_systems
    SET status = 'pending', reviewed_by = NULL, review_date = NULL
    WHERE system_name IN ("test", "tesetes")
''')
reset_count = cursor.rowcount
print(f"  [OK] Reset {reset_count} submissions to pending")

# Commit changes
conn.commit()
conn.close()

print("\n[SUCCESS] Cleanup complete!")
print("\nNext steps:")
print("  1. Restart Haven UI server")
print("  2. Re-approve the submissions through the UI")
print("  3. Verify planets and moons are created correctly")
print("=" * 60)
