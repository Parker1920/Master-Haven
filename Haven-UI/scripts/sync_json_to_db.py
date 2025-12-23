#!/usr/bin/env python3
"""
Sync data from data.json to haven_ui.db, including all planet/moon fields.

This script:
1. Reads systems from data.json
2. For each system, updates or inserts into the database
3. Preserves all fields: flora, fauna, materials, base_location, notes, photo, etc.
"""

import json
import sqlite3
import uuid
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / 'data'
JSON_FILE = DATA_DIR / 'data.json'
DB_FILE = DATA_DIR / 'haven_ui.db'


def get_db_connection():
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def sync_system(cursor, system):
    """Sync a single system and its planets/moons to the database."""
    sys_id = system.get('id') or str(uuid.uuid4())
    name = system.get('name')

    if not name:
        print(f"  Skipping system without name")
        return False

    # Check if system exists by name
    cursor.execute('SELECT id FROM systems WHERE name = ?', (name,))
    existing = cursor.fetchone()

    if existing:
        sys_id = existing['id']
        print(f"  Updating existing system: {name} (ID: {sys_id})")

        # Update system
        cursor.execute('''
            UPDATE systems SET
                galaxy = ?, x = ?, y = ?, z = ?, description = ?,
                glyph_code = ?, glyph_planet = ?, glyph_solar_system = ?,
                region_x = ?, region_y = ?, region_z = ?
            WHERE id = ?
        ''', (
            system.get('galaxy', 'Euclid'),
            system.get('x', 0),
            system.get('y', 0),
            system.get('z', 0),
            system.get('description', ''),
            system.get('glyph_code'),
            system.get('glyph_planet', 0),
            system.get('glyph_solar_system', 1),
            system.get('region_x'),
            system.get('region_y'),
            system.get('region_z'),
            sys_id
        ))

        # Delete existing planets (will cascade to moons)
        cursor.execute('DELETE FROM planets WHERE system_id = ?', (sys_id,))
    else:
        print(f"  Inserting new system: {name} (ID: {sys_id})")

        # Insert new system
        cursor.execute('''
            INSERT INTO systems (id, name, galaxy, x, y, z, description, glyph_code, glyph_planet, glyph_solar_system, region_x, region_y, region_z)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sys_id,
            name,
            system.get('galaxy', 'Euclid'),
            system.get('x', 0),
            system.get('y', 0),
            system.get('z', 0),
            system.get('description', ''),
            system.get('glyph_code'),
            system.get('glyph_planet', 0),
            system.get('glyph_solar_system', 1),
            system.get('region_x'),
            system.get('region_y'),
            system.get('region_z')
        ))

    # Insert planets with ALL fields
    for planet in system.get('planets', []):
        cursor.execute('''
            INSERT INTO planets (system_id, name, x, y, z, climate, sentinel, fauna, flora, fauna_count, flora_count, has_water, materials, base_location, photo, notes, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sys_id,
            planet.get('name', 'Unknown'),
            planet.get('x', 0),
            planet.get('y', 0),
            planet.get('z', 0),
            planet.get('climate'),
            planet.get('sentinel', 'None'),
            planet.get('fauna', 'N/A'),
            planet.get('flora', 'N/A'),
            planet.get('fauna_count', 0),
            planet.get('flora_count', 0),
            planet.get('has_water', 0),
            planet.get('materials'),
            planet.get('base_location'),
            planet.get('photo'),
            planet.get('notes'),
            planet.get('description', '')
        ))
        planet_id = cursor.lastrowid

        # Insert moons with ALL fields
        for moon in planet.get('moons', []):
            cursor.execute('''
                INSERT INTO moons (planet_id, name, orbit_radius, orbit_speed, climate, sentinel, fauna, flora, materials, notes, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                planet_id,
                moon.get('name', 'Unknown'),
                moon.get('orbit_radius', 0.5),
                moon.get('orbit_speed', 0),
                moon.get('climate'),
                moon.get('sentinel', 'None'),
                moon.get('fauna', 'N/A'),
                moon.get('flora', 'N/A'),
                moon.get('materials'),
                moon.get('notes'),
                moon.get('description', '')
            ))

        print(f"    Added planet: {planet.get('name')} with {len(planet.get('moons', []))} moons")

    # Handle space station
    if system.get('space_station'):
        station = system['space_station']
        # Delete existing station for this system
        cursor.execute('DELETE FROM space_stations WHERE system_id = ?', (sys_id,))

        cursor.execute('''
            INSERT INTO space_stations (system_id, name, race, x, y, z, sell_percent, buy_percent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sys_id,
            station.get('name', f"{name} Station"),
            station.get('race', 'Gek'),
            station.get('x', 0),
            station.get('y', 0),
            station.get('z', 0),
            station.get('sell_percent', 80),
            station.get('buy_percent', 50)
        ))
        print(f"    Added space station: {station.get('name')}")

    return True


def main():
    print("=" * 60)
    print("Syncing data.json to haven_ui.db")
    print("=" * 60)

    if not JSON_FILE.exists():
        print(f"ERROR: {JSON_FILE} not found!")
        return

    if not DB_FILE.exists():
        print(f"ERROR: {DB_FILE} not found!")
        return

    # Load JSON data
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    systems = data.get('systems', [])
    print(f"Found {len(systems)} systems in data.json")

    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure new columns exist (run migrations)
    def add_column_if_missing(table, column, coltype):
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cursor.fetchall()]
        if column not in columns:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            print(f"  Added column {column} to {table}")

    print("\nChecking database schema...")
    add_column_if_missing('planets', 'fauna', "TEXT DEFAULT 'N/A'")
    add_column_if_missing('planets', 'flora', "TEXT DEFAULT 'N/A'")
    add_column_if_missing('planets', 'materials', 'TEXT')
    add_column_if_missing('planets', 'base_location', 'TEXT')
    add_column_if_missing('planets', 'photo', 'TEXT')
    add_column_if_missing('planets', 'notes', 'TEXT')
    add_column_if_missing('moons', 'orbit_speed', 'REAL DEFAULT 0')
    add_column_if_missing('moons', 'fauna', "TEXT DEFAULT 'N/A'")
    add_column_if_missing('moons', 'flora', "TEXT DEFAULT 'N/A'")
    add_column_if_missing('moons', 'materials', 'TEXT')
    add_column_if_missing('moons', 'notes', 'TEXT')

    print("\nSyncing systems...")
    success_count = 0
    for system in systems:
        try:
            if sync_system(cursor, system):
                success_count += 1
        except Exception as e:
            print(f"  ERROR syncing system {system.get('name')}: {e}")

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print(f"Sync complete! {success_count}/{len(systems)} systems synced.")
    print("=" * 60)


if __name__ == '__main__':
    main()
