#!/usr/bin/env python3
"""
Test Space Station Random Placement
Tests the placement algorithm with existing Aurora and Serenity systems
"""

import sqlite3
from pathlib import Path
import json

# Database path
db_path = Path(__file__).parent / 'Haven-UI' / 'data' / 'haven_ui.db'

print("=" * 70)
print("SPACE STATION RANDOM PLACEMENT TEST")
print("=" * 70)

if not db_path.exists():
    print(f"\n❌ ERROR: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Test with Aurora system
print("\n1. TESTING: Aurora System")
print("-" * 70)

cursor.execute('SELECT * FROM systems WHERE name LIKE "%Aurora%"')
aurora_system = dict(cursor.fetchone())
print(f"System: {aurora_system['name']} (ID: {aurora_system['id']})")
print(f"Position: ({aurora_system['x']}, {aurora_system['y']}, {aurora_system['z']})")

# Get planets
cursor.execute('SELECT * FROM planets WHERE system_id = ?', (aurora_system['id'],))
aurora_planets = [dict(row) for row in cursor.fetchall()]
print(f"\nPlanets: {len(aurora_planets)}")
for planet in aurora_planets:
    print(f"  - {planet['name']}: ({planet['x']}, {planet['y']}, {planet['z']})")

    # Get moons
    cursor.execute('SELECT * FROM moons WHERE planet_id = ?', (planet['id'],))
    moons = cursor.fetchall()
    if moons:
        print(f"    Moons: {len(moons)}")
        for moon in moons:
            orbit = moon['orbit_radius'] if moon['orbit_radius'] else 0.5
            print(f"      - {moon['name']}: orbit radius {orbit}")

# Get existing station
cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (aurora_system['id'],))
aurora_station = cursor.fetchone()
if aurora_station:
    aurora_station = dict(aurora_station)
    print(f"\nExisting Station: {aurora_station['name']}")
    print(f"  Position: ({aurora_station['x']}, {aurora_station['y']}, {aurora_station['z']})")
    print(f"  Race: {aurora_station['race']}")

    # Calculate distances
    from math import sqrt

    # Distance to sun
    dist_to_sun = sqrt(aurora_station['x']**2 + aurora_station['y']**2 + aurora_station['z']**2)
    print(f"  Distance to sun: {dist_to_sun:.2f} units")

    # Distance to planets
    for planet in aurora_planets:
        dist = sqrt(
            (aurora_station['x'] - planet['x'])**2 +
            (aurora_station['y'] - planet['y'])**2 +
            (aurora_station['z'] - planet['z'])**2
        )
        print(f"  Distance to {planet['name']}: {dist:.2f} units")

    # Check if valid
    if dist_to_sun < 1.5:
        print(f"  ⚠️ WARNING: Too close to sun! (< 1.5 units)")
    else:
        print(f"  ✓ Safe distance from sun")

    min_planet_dist = min([
        sqrt(
            (aurora_station['x'] - p['x'])**2 +
            (aurora_station['y'] - p['y'])**2 +
            (aurora_station['z'] - p['z'])**2
        ) for p in aurora_planets
    ]) if aurora_planets else 999

    if min_planet_dist < 2.0:
        print(f"  ⚠️ WARNING: Too close to planet! ({min_planet_dist:.2f} < 2.0 units)")
    else:
        print(f"  ✓ Safe distance from planets")

# Test with Serenity system
print("\n\n2. TESTING: Serenity System")
print("-" * 70)

cursor.execute('SELECT * FROM systems WHERE name LIKE "%Serenity%"')
serenity_system = dict(cursor.fetchone())
print(f"System: {serenity_system['name']} (ID: {serenity_system['id']})")
print(f"Position: ({serenity_system['x']}, {serenity_system['y']}, {serenity_system['z']})")

# Get planets
cursor.execute('SELECT * FROM planets WHERE system_id = ?', (serenity_system['id'],))
serenity_planets = [dict(row) for row in cursor.fetchall()]
print(f"\nPlanets: {len(serenity_planets)}")
for planet in serenity_planets:
    print(f"  - {planet['name']}: ({planet['x']}, {planet['y']}, {planet['z']})")

    # Get moons
    cursor.execute('SELECT * FROM moons WHERE planet_id = ?', (planet['id'],))
    moons = cursor.fetchall()
    if moons:
        print(f"    Moons: {len(moons)}")
        for moon in moons:
            orbit = moon['orbit_radius'] if moon['orbit_radius'] else 0.5
            print(f"      - {moon['name']}: orbit radius {orbit}")

# Get existing station
cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (serenity_system['id'],))
serenity_station = cursor.fetchone()
if serenity_station:
    serenity_station = dict(serenity_station)
    print(f"\nExisting Station: {serenity_station['name']}")
    print(f"  Position: ({serenity_station['x']}, {serenity_station['y']}, {serenity_station['z']})")
    print(f"  Race: {serenity_station['race']}")

    # Calculate distances
    dist_to_sun = sqrt(serenity_station['x']**2 + serenity_station['y']**2 + serenity_station['z']**2)
    print(f"  Distance to sun: {dist_to_sun:.2f} units")

    # Distance to planets
    for planet in serenity_planets:
        dist = sqrt(
            (serenity_station['x'] - planet['x'])**2 +
            (serenity_station['y'] - planet['y'])**2 +
            (serenity_station['z'] - planet['z'])**2
        )
        print(f"  Distance to {planet['name']}: {dist:.2f} units")

    # Check if valid
    if dist_to_sun < 1.5:
        print(f"  ⚠️ WARNING: Too close to sun! (< 1.5 units)")
    else:
        print(f"  ✓ Safe distance from sun")

    if serenity_planets:
        min_planet_dist = min([
            sqrt(
                (serenity_station['x'] - p['x'])**2 +
                (serenity_station['y'] - p['y'])**2 +
                (serenity_station['z'] - p['z'])**2
            ) for p in serenity_planets
        ])

        if min_planet_dist < 2.0:
            print(f"  ⚠️ WARNING: Too close to planet! ({min_planet_dist:.2f} < 2.0 units)")
        else:
            print(f"  ✓ Safe distance from planets")

# Summary
print("\n\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"\nAurora System:")
print(f"  Planets: {len(aurora_planets)}")
print(f"  Station: {'✓ Yes' if aurora_station else '✗ No'}")

print(f"\nSerenity System:")
print(f"  Planets: {len(serenity_planets)}")
print(f"  Station: {'✓ Yes' if serenity_station else '✗ No'}")

print("\n✅ Database query test complete!")
print("\nTo regenerate station positions with the new algorithm:")
print("  1. Open the Control Room web interface")
print("  2. Edit Aurora or Serenity system")
print("  3. Toggle space station checkbox")
print("  4. Click 'Regenerate Random Position' button")
print("  5. Save the system")

conn.close()
