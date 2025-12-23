#!/usr/bin/env python3
"""Check Oculi system data in database"""
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent.parent / 'data' / 'haven_ui.db'

conn = sqlite3.connect(str(DB_FILE))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get Oculi system
cursor.execute('SELECT * FROM systems WHERE name = ?', ('Oculi',))
system = cursor.fetchone()
if system:
    print(f"System: {dict(system)}")
    sys_id = system['id']

    # Get planets
    cursor.execute('SELECT * FROM planets WHERE system_id = ?', (sys_id,))
    planets = cursor.fetchall()
    print(f"\nPlanets ({len(planets)}):")
    for p in planets:
        print(f"  {p['name']}: flora={p['flora']}, fauna={p['fauna']}, materials={p['materials']}, sentinel={p['sentinel']}")
else:
    print("Oculi system not found!")

conn.close()
