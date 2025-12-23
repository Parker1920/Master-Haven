#!/usr/bin/env python3
"""Add sample materials/flora/fauna to Oculi planets for testing"""
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent.parent / 'data' / 'haven_ui.db'

conn = sqlite3.connect(str(DB_FILE))
cursor = conn.cursor()

# Update Voyager's Haven planet with sample data
cursor.execute('''
    UPDATE planets
    SET flora = 'Abundant',
        fauna = 'Rich',
        materials = 'Copper, Sodium, Carbon, Paraffinium',
        base_location = 'Main Base - coordinates +45.2, -12.8',
        notes = 'Great planet for farming resources. Has beautiful sunsets.'
    WHERE name = "Voyager's Haven"
''')

# Update New Oculs with sample data
cursor.execute('''
    UPDATE planets
    SET flora = 'Moderate',
        fauna = 'Low',
        materials = 'Salt, Cobalt, Di-hydrogen',
        notes = 'Ocean planet, good for underwater exploration'
    WHERE name = "New Oculs"
''')

# Update Erren with sample data
cursor.execute('''
    UPDATE planets
    SET flora = 'Sparse',
        fauna = 'None',
        materials = 'Ferrite Dust, Magnetised Ferrite, Pure Ferrite',
        notes = 'Barren world but rich in ferrite'
    WHERE name = "Erren"
''')

conn.commit()
print(f"Updated {cursor.rowcount} planets with sample data")

# Verify
cursor.execute('SELECT name, flora, fauna, materials, notes FROM planets WHERE materials IS NOT NULL')
for row in cursor.fetchall():
    print(f"  {row[0]}: flora={row[1]}, fauna={row[2]}, materials={row[3][:30]}...")

conn.close()
print("\nDone! Restart the server to see changes in the 3D map.")
