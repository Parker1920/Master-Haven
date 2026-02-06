"""
Test System Approval Workflow
==============================
Quick test to verify the approve_system endpoint works with the new schema.
"""

import sqlite3
import json
from pathlib import Path

# Get database path — relative to this script (scripts/ -> Haven-UI/data/)
db_path = Path(__file__).parent.parent / 'data' / 'haven_ui.db'

# Connect to database
conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get pending submission
cursor.execute('SELECT * FROM pending_systems WHERE status = "pending" LIMIT 1')
row = cursor.fetchone()

if not row:
    print("No pending submissions found")
    exit(0)

submission = dict(row)
print(f"Found pending submission #{submission['id']}:")
print(f"  Name: {submission['system_name']}")
print(f"  Submitted by: {submission['submitted_by']}")

# Parse system data
system_data = json.loads(submission['system_data'])

print(f"\nSystem data:")
print(f"  Name: {system_data.get('name')}")
print(f"  Galaxy: {system_data.get('galaxy', 'Euclid')}")
print(f"  Planets: {len(system_data.get('planets', []))}")

# Test INSERT statement (same as in approve_system)
try:
    print(f"\nTesting system INSERT...")
    cursor.execute('''
        INSERT INTO systems (name, galaxy, x, y, z, description, glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        system_data.get('name') + ' (TEST)',
        system_data.get('galaxy', 'Euclid'),
        system_data.get('x', 0),
        system_data.get('y', 0),
        system_data.get('z', 0),
        system_data.get('description', ''),
        system_data.get('glyph_code'),
        system_data.get('glyph_planet', 0),
        system_data.get('glyph_solar_system', 1),
        system_data.get('region_x'),
        system_data.get('region_y'),
        system_data.get('region_z')
    ))
    system_id = cursor.lastrowid
    print(f"  SUCCESS - System ID: {system_id}")

    # Test planet INSERT
    print(f"\nTesting planet INSERT...")
    for i, planet in enumerate(system_data.get('planets', [])):
        cursor.execute('''
            INSERT INTO planets (system_id, name, x, y, z, climate, sentinel, fauna_count, flora_count, has_water, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            system_id,
            planet.get('name'),
            planet.get('x', 0),
            planet.get('y', 0),
            planet.get('z', 0),
            planet.get('climate'),
            planet.get('sentinel', 'None'),
            planet.get('fauna_count', 0),
            planet.get('flora_count', 0),
            planet.get('has_water', 0),
            planet.get('description', '')
        ))
        planet_id = cursor.lastrowid
        print(f"  Planet {i+1}: {planet.get('name')} - ID: {planet_id}")

        # Test moon INSERT
        for moon in planet.get('moons', []):
            cursor.execute('''
                INSERT INTO moons (planet_id, name, orbit_radius, climate, sentinel, description)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                planet_id,
                moon.get('name'),
                moon.get('orbit_radius', 0.5),
                moon.get('climate'),
                moon.get('sentinel', 'None'),
                moon.get('description', '')
            ))
            print(f"    Moon: {moon.get('name')}")

    print(f"\n[SUCCESS] All INSERT statements work correctly!")
    print(f"\nRolling back test transaction (no changes saved)...")
    conn.rollback()

except Exception as e:
    print(f"\n[ERROR] Insert failed: {e}")
    conn.rollback()
    exit(1)

finally:
    conn.close()

print("\n[PASS] System approval workflow is functional!")
