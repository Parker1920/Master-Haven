"""
One-time migration script to import POIs from Planet_Atlas CSV into Haven database.

Usage:
    python src/migrate_atlas_pois.py

This script will:
1. Read Planet_Atlas/atlas_data.csv
2. Filter for POINT records only
3. Look up matching systems and planets in Haven database
4. Insert POIs into planet_pois table
5. Skip duplicates and report results
"""

import csv
import sqlite3
from pathlib import Path

# Color name to hex mapping
COLOR_MAP = {
    'purple': '#BA55D3',
    'cyan': '#00FFFF',
    'brown': '#8B4513',
    'blue': '#1E90FF',
    'red': '#FC422D',
    'orange': '#FF8C00',
    'gray': '#A6A6A6',
    'grey': '#A6A6A6',
    'green': '#32CD32',
    'yellow': '#FFD700',
    'pink': '#FF9AC7',
    'white': '#FFFFFF',
    'black': '#000000',
}

def normalize_color(color_value):
    """Convert color name to hex if needed."""
    if not color_value:
        return '#00C2B3'  # Default cyan

    color_value = color_value.strip().lower()

    # Already a hex color
    if color_value.startswith('#'):
        return color_value.upper()

    # Look up color name
    return COLOR_MAP.get(color_value, '#00C2B3')


def main():
    # Paths
    project_root = Path(__file__).parent.parent
    csv_path = project_root / 'Planet_Atlas' / 'atlas_data.csv'
    db_path = project_root / 'Haven-UI' / 'data' / 'haven_ui.db'

    print("=" * 60)
    print("Planet Atlas POI Migration")
    print("=" * 60)
    print(f"CSV Source: {csv_path}")
    print(f"Database:   {db_path}")
    print()

    # Verify files exist
    if not csv_path.exists():
        print(f"ERROR: CSV file not found: {csv_path}")
        return

    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        return

    # Read CSV
    print("Reading CSV file...")
    points = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('type') == 'POINT':
                points.append(row)

    print(f"Found {len(points)} POINT records in CSV")
    print()

    # Connect to database
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build lookup caches
    print("Building system/planet lookup caches...")

    # Systems by name (case-insensitive)
    cursor.execute('SELECT id, name FROM systems')
    systems = {row['name'].lower(): row['id'] for row in cursor.fetchall()}
    print(f"  Found {len(systems)} systems in database")

    # Planets by (system_id, planet_name) - case-insensitive
    cursor.execute('SELECT id, system_id, name FROM planets')
    planets = {}
    for row in cursor.fetchall():
        key = (row['system_id'], row['name'].lower())
        planets[key] = row['id']
    print(f"  Found {len(planets)} planets in database")
    print()

    # Process POIs
    imported = 0
    skipped_no_system = 0
    skipped_no_planet = 0
    skipped_duplicate = 0
    skipped_other = 0

    skipped_details = []

    print("Importing POIs...")
    for point in points:
        poi_name = point.get('name', '').strip()
        parent_system = point.get('parent_system', '').strip()
        parent_planet = point.get('parent_planet', '').strip()

        # Skip if missing required data
        if not poi_name or not parent_system or not parent_planet:
            skipped_other += 1
            continue

        # Look up system
        system_id = systems.get(parent_system.lower())
        if not system_id:
            skipped_no_system += 1
            if parent_system not in [d.get('system') for d in skipped_details]:
                skipped_details.append({'type': 'system', 'system': parent_system})
            continue

        # Look up planet
        planet_key = (system_id, parent_planet.lower())
        planet_id = planets.get(planet_key)
        if not planet_id:
            skipped_no_planet += 1
            skipped_details.append({'type': 'planet', 'system': parent_system, 'planet': parent_planet})
            continue

        # Parse coordinates
        try:
            latitude = float(point.get('lat', 0))
            longitude = float(point.get('lon', 0))
        except (ValueError, TypeError):
            latitude = 0.0
            longitude = 0.0

        # Normalize color
        color = normalize_color(point.get('color', ''))

        # Get other fields
        symbol = point.get('symbol', 'circle') or 'circle'
        category = point.get('category', '-') or '-'

        # Check for duplicates (same name, lat, lon on same planet)
        cursor.execute('''
            SELECT id FROM planet_pois
            WHERE planet_id = ? AND name = ? AND latitude = ? AND longitude = ?
        ''', (planet_id, poi_name, latitude, longitude))

        if cursor.fetchone():
            skipped_duplicate += 1
            continue

        # Insert POI
        try:
            cursor.execute('''
                INSERT INTO planet_pois (planet_id, name, latitude, longitude, color, symbol, category, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (planet_id, poi_name, latitude, longitude, color, symbol, category, 'atlas_migration'))
            imported += 1
        except Exception as e:
            print(f"  Error inserting POI '{poi_name}': {e}")
            skipped_other += 1

    # Commit changes
    conn.commit()
    conn.close()

    # Print summary
    print()
    print("=" * 60)
    print("Migration Complete")
    print("=" * 60)
    print(f"  Imported:              {imported}")
    print(f"  Skipped (no system):   {skipped_no_system}")
    print(f"  Skipped (no planet):   {skipped_no_planet}")
    print(f"  Skipped (duplicate):   {skipped_duplicate}")
    print(f"  Skipped (other):       {skipped_other}")
    print()

    # Show which systems/planets were not found
    if skipped_details:
        print("Missing systems/planets (not in Haven database):")
        seen_systems = set()
        for detail in skipped_details:
            if detail['type'] == 'system' and detail['system'] not in seen_systems:
                print(f"  - System: {detail['system']}")
                seen_systems.add(detail['system'])

        seen_planets = set()
        for detail in skipped_details:
            if detail['type'] == 'planet':
                key = (detail['system'], detail['planet'])
                if key not in seen_planets:
                    print(f"  - Planet: {detail['planet']} (in system: {detail['system']})")
                    seen_planets.add(key)


if __name__ == '__main__':
    main()
