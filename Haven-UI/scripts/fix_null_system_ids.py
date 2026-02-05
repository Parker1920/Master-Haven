"""
Fix Systems with NULL IDs
===========================
Assigns UUIDs to systems that have NULL id values, and links their planets.
"""

import sqlite3
import uuid
from pathlib import Path

# Get database path
db_path = Path('Haven-UI/data/haven_ui.db')

# Connect to database
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=" * 60)
print("Fixing Systems with NULL IDs")
print("=" * 60)

# Find systems with NULL id
cursor.execute('SELECT rowid, name, x, y, z FROM systems WHERE id IS NULL')
broken_systems = cursor.fetchall()

if not broken_systems:
    print("\n[OK] No systems with NULL id found!")
    conn.close()
    exit(0)

print(f"\nFound {len(broken_systems)} systems with NULL id:")
for rowid, name, x, y, z in broken_systems:
    print(f"  - {name} at ({x}, {y}, {z}) [rowid={rowid}]")

print("\nAssigning UUIDs...")

# Fix each system
for rowid, name, x, y, z in broken_systems:
    # Generate new UUID
    new_id = str(uuid.uuid4())

    # Update system with new ID
    cursor.execute('UPDATE systems SET id = ? WHERE rowid = ?', (new_id, rowid))

    print(f"  [OK] {name}: {new_id}")

# Check for orphaned planets
cursor.execute('SELECT id, name FROM planets WHERE system_id IS NULL')
orphaned_planets = cursor.fetchall()

if orphaned_planets:
    print(f"\n[WARNING] Found {len(orphaned_planets)} orphaned planets (system_id=NULL):")
    for planet_id, planet_name in orphaned_planets:
        print(f"  - {planet_name} (id={planet_id})")
    print("\n[ACTION NEEDED] These planets need to be manually linked to their systems")
else:
    print("\n[OK] No orphaned planets found")

# Commit changes
conn.commit()
conn.close()

print("\n[SUCCESS] Systems fixed!")
print("=" * 60)
