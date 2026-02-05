"""
Populate Haven UI Database with Test Data
==========================================
Creates 5 star systems with planets, moons, and discoveries for testing
"""

import sqlite3
from datetime import datetime
import random

# Database path
DB_PATH = r"C:\Users\parke\OneDrive\Desktop\Master-Haven\Haven-UI\data\haven_ui.db"

# Test data definitions
TEST_SYSTEMS = [
    {
        'id': 'SYS_NEXARA_PRIME',
        'name': 'Nexara Prime',
        'region': 'Outer Rim',
        'x': -245.8, 'y': 112.4, 'z': 89.2,
        'fauna': 'Abundant', 'flora': 'Lush', 'sentinel': 'Low',
        'materials': 'Copper, Carbon, Sodium',
        'planets': [
            {'name': 'Nexara I', 'sentinel': 'None', 'fauna': 'Rich', 'flora': 'Moderate', 'materials': 'Copper, Oxygen'},
            {'name': 'Nexara II', 'sentinel': 'Low', 'fauna': 'Sparse', 'flora': 'Abundant', 'materials': 'Silver, Carbon'},
            {'name': 'Nexara III', 'sentinel': 'Aggressive', 'fauna': 'None', 'flora': 'None', 'materials': 'Gold, Platinum'},
            {'name': 'Nexara IV', 'sentinel': 'None', 'fauna': 'Moderate', 'flora': 'Rich', 'materials': 'Emeril, Indium'},
        ]
    },
    {
        'id': 'SYS_CORVAX_CLUSTER',
        'name': 'Corvax Cluster',
        'region': 'Core Worlds',
        'x': 12.5, 'y': -89.3, 'z': 156.7,
        'fauna': 'Moderate', 'flora': 'Sparse', 'sentinel': 'High',
        'materials': 'Gold, Emeril, Platinum',
        'planets': [
            {'name': 'Corvax Alpha', 'sentinel': 'High', 'fauna': 'Dangerous', 'flora': 'None', 'materials': 'Activated Copper'},
            {'name': 'Corvax Beta', 'sentinel': 'Moderate', 'fauna': 'Rich', 'flora': 'Moderate', 'materials': 'Cadmium, Emeril'},
            {'name': 'Corvax Gamma', 'sentinel': 'Low', 'fauna': 'Abundant', 'flora': 'Lush', 'materials': 'Carbon, Oxygen'},
            {'name': 'Corvax Delta', 'sentinel': 'None', 'fauna': 'Sparse', 'flora': 'Sparse', 'materials': 'Silver, Gold'},
            {'name': 'Corvax Epsilon', 'sentinel': 'Aggressive', 'fauna': 'None', 'flora': 'None', 'materials': 'Platinum, Indium'},
            {'name': 'Corvax Zeta', 'sentinel': 'Low', 'fauna': 'Moderate', 'flora': 'Rich', 'materials': 'Ammonia, Nitrogen'},
        ]
    },
    {
        'id': 'SYS_HELIOS_TERMINUS',
        'name': 'Helios Terminus',
        'region': 'Edge Sector',
        'x': 334.2, 'y': 67.8, 'z': -123.4,
        'fauna': 'Rare', 'flora': 'Moderate', 'sentinel': 'Moderate',
        'materials': 'Emeril, Cadmium, Uranium',
        'planets': [
            {'name': 'Helios Prime', 'sentinel': 'Moderate', 'fauna': 'Rich', 'flora': 'Abundant', 'materials': 'Emeril, Gold'},
            {'name': 'Helios Minor', 'sentinel': 'Low', 'fauna': 'Sparse', 'flora': 'Moderate', 'materials': 'Cadmium, Silver'},
            {'name': 'Helios Tertius', 'sentinel': 'None', 'fauna': 'None', 'flora': 'None', 'materials': 'Uranium, Platinum'},
        ]
    },
    {
        'id': 'SYS_VOIDWATCH',
        'name': 'Voidwatch Station',
        'region': 'Deep Space',
        'x': -412.7, 'y': -245.1, 'z': 298.5,
        'fauna': 'Abundant', 'flora': 'Rich', 'sentinel': 'None',
        'materials': 'Carbon, Oxygen, Sodium, Di-hydrogen',
        'planets': [
            {'name': 'Voidwatch I', 'sentinel': 'None', 'fauna': 'Abundant', 'flora': 'Lush', 'materials': 'Carbon, Oxygen'},
            {'name': 'Voidwatch II', 'sentinel': 'Low', 'fauna': 'Rich', 'flora': 'Moderate', 'materials': 'Copper, Sodium'},
            {'name': 'Voidwatch III', 'sentinel': 'None', 'fauna': 'Moderate', 'flora': 'Sparse', 'materials': 'Silver, Gold'},
            {'name': 'Voidwatch IV', 'sentinel': 'Moderate', 'fauna': 'Sparse', 'flora': 'None', 'materials': 'Emeril, Cadmium'},
            {'name': 'Voidwatch V', 'sentinel': 'None', 'fauna': 'None', 'flora': 'Rich', 'materials': 'Platinum, Indium'},
        ]
    },
    {
        'id': 'SYS_CELESTIS_EXPANSE',
        'name': 'Celestis Expanse',
        'region': 'Frontier',
        'x': 178.9, 'y': 223.6, 'z': -67.3,
        'fauna': 'Rich', 'flora': 'Abundant', 'sentinel': 'Low',
        'materials': 'Carbon, Ferrite, Phosphorus',
        'planets': [
            {'name': 'Celestis Major', 'sentinel': 'Low', 'fauna': 'Abundant', 'flora': 'Lush', 'materials': 'Carbon, Ferrite'},
            {'name': 'Celestis Minor', 'sentinel': 'None', 'fauna': 'Rich', 'flora': 'Rich', 'materials': 'Phosphorus, Sodium'},
            {'name': 'Celestis Tertia', 'sentinel': 'Moderate', 'fauna': 'Moderate', 'flora': 'Moderate', 'materials': 'Copper, Silver'},
            {'name': 'Celestis Quarta', 'sentinel': 'None', 'fauna': 'Sparse', 'flora': 'Abundant', 'materials': 'Gold, Emeril'},
        ]
    }
]

# Moon names for each system's planets
MOON_TEMPLATES = [
    '{planet} Alpha', '{planet} Beta', '{planet} Gamma', '{planet} I', '{planet} II',
    '{planet} III', '{planet}-A', '{planet}-B', '{planet}-C'
]

# Discovery templates
DISCOVERY_TEMPLATES = [
    {'type': 'artifact', 'name': 'Ancient Monolith', 'desc': 'A towering monolith covered in indecipherable glyphs', 'tier': 3},
    {'type': 'structure', 'name': 'Abandoned Outpost', 'desc': 'A derelict structure showing signs of recent habitation', 'tier': 2},
    {'type': 'crashed_ship', 'name': 'Crashed Freighter', 'desc': 'Massive ship wreckage scattered across the landscape', 'tier': 4},
    {'type': 'resource', 'name': 'Rich Mineral Deposit', 'desc': 'Unusually concentrated ore deposits detected', 'tier': 1},
    {'type': 'anomaly', 'name': 'Gravity Anomaly', 'desc': 'Localized distortion in gravitational field', 'tier': 5},
    {'type': 'artifact', 'name': 'Alien Artifact', 'desc': 'Mysterious device of unknown origin and purpose', 'tier': 4},
    {'type': 'structure', 'name': 'Ancient Ruins', 'desc': 'Weathered ruins of an advanced civilization', 'tier': 3},
    {'type': 'crashed_ship', 'name': 'Downed Explorer', 'desc': 'Small explorer craft in surprisingly good condition', 'tier': 2},
    {'type': 'resource', 'name': 'Exotic Flora', 'desc': 'Rare plant species with unusual properties', 'tier': 2},
    {'type': 'anomaly', 'name': 'Energy Nexus', 'desc': 'Point of concentrated electromagnetic energy', 'tier': 4},
    {'type': 'artifact', 'name': 'Data Terminal', 'desc': 'Functional terminal containing encrypted data', 'tier': 3},
    {'type': 'structure', 'name': 'Trading Post', 'desc': 'Automated trading facility still operational', 'tier': 1},
    {'type': 'resource', 'name': 'Salvageable Technology', 'desc': 'Scattered components of advanced technology', 'tier': 3},
    {'type': 'anomaly', 'name': 'Temporal Rift', 'desc': 'Localized time distortion effect observed', 'tier': 5},
    {'type': 'artifact', 'name': 'Sentinel Hive', 'desc': 'Dormant sentinel manufacturing facility', 'tier': 4},
]

def insert_test_data():
    """Insert test data into the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Populating Haven UI Database with Test Data...")
    print("=" * 60)

    # Get next available IDs
    cursor.execute('SELECT MAX(id) FROM planets')
    next_planet_id = (cursor.fetchone()[0] or 0) + 1
    cursor.execute('SELECT MAX(id) FROM moons')
    next_moon_id = (cursor.fetchone()[0] or 0) + 1
    cursor.execute('SELECT MAX(id) FROM discoveries')
    next_discovery_id = (cursor.fetchone()[0] or 0) + 1

    planet_id_counter = next_planet_id
    moon_id_counter = next_moon_id
    discovery_id_counter = next_discovery_id

    all_planets = []  # Store planet IDs for moon assignment
    all_locations = []  # Store all locations for discovery assignment

    # Insert systems
    for system in TEST_SYSTEMS:
        print(f"\nInserting system: {system['name']}")

        cursor.execute('''
            INSERT INTO systems (id, name, x, y, z, region, fauna, flora, sentinel, materials, created_at, modified_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            system['id'], system['name'],
            system['x'], system['y'], system['z'],
            system['region'], system['fauna'], system['flora'],
            system['sentinel'], system['materials'],
            datetime.now(), datetime.now()
        ))

        # Insert planets for this system
        system_planets = []
        for planet in system['planets']:
            cursor.execute('''
                INSERT INTO planets (id, system_id, name, sentinel, fauna, flora, materials)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                planet_id_counter, system['id'], planet['name'],
                planet['sentinel'], planet['fauna'], planet['flora'],
                planet['materials']
            ))

            system_planets.append((planet_id_counter, planet['name'], system['id']))
            all_locations.append({
                'type': 'planet',
                'id': planet_id_counter,
                'name': planet['name'],
                'system_id': system['id']
            })

            print(f"  + Planet: {planet['name']} (ID: {planet_id_counter})")
            planet_id_counter += 1

        # Insert moons for each planet (1-2 moons per planet randomly)
        for planet_id, planet_name, sys_id in system_planets:
            num_moons = random.randint(1, 2)
            for i in range(num_moons):
                moon_name = MOON_TEMPLATES[i % len(MOON_TEMPLATES)].format(planet=planet_name)

                cursor.execute('''
                    INSERT INTO moons (id, planet_id, name, sentinel, fauna, flora, materials, orbit_radius, orbit_speed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    moon_id_counter, planet_id, moon_name,
                    random.choice(['None', 'Low', 'Moderate']),
                    random.choice(['None', 'Sparse', 'Moderate']),
                    random.choice(['None', 'Sparse', 'Moderate']),
                    random.choice(['Copper', 'Silver', 'Gold', 'Carbon']),
                    random.uniform(100, 500),  # orbit radius
                    random.uniform(0.5, 2.0)   # orbit speed
                ))

                all_locations.append({
                    'type': 'moon',
                    'id': moon_id_counter,
                    'name': moon_name,
                    'planet_id': planet_id,
                    'system_id': sys_id
                })

                print(f"    - Moon: {moon_name} (ID: {moon_id_counter})")
                moon_id_counter += 1

    print(f"\n{'=' * 60}")
    print("Inserting discoveries...")
    print("=" * 60)

    # Insert discoveries (15-20 discoveries across all locations)
    num_discoveries = random.randint(15, 20)

    for i in range(num_discoveries):
        template = random.choice(DISCOVERY_TEMPLATES)
        location = random.choice(all_locations)

        # Determine location fields based on type
        planet_id = None
        moon_id = None
        location_type = location['type']

        if location['type'] == 'planet':
            planet_id = location['id']
        elif location['type'] == 'moon':
            moon_id = location['id']
            planet_id = location['planet_id']

        cursor.execute('''
            INSERT INTO discoveries (
                id, discovery_type, discovery_name, system_id, planet_id, moon_id,
                location_type, location_name, description, significance,
                discovered_by, submission_timestamp, mystery_tier, analysis_status,
                pattern_matches
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            discovery_id_counter,
            template['type'],
            template['name'],
            location['system_id'],
            planet_id,
            moon_id,
            location_type,
            location['name'],
            template['desc'],
            random.choice(['Minor', 'Notable', 'Significant', 'Major']),
            random.choice(['Explorer_7', 'Wanderer', 'Pathfinder', 'Voyager', 'Discoverer']),
            datetime.now(),
            template['tier'],
            random.choice(['pending', 'analyzed', 'pattern_detected']),
            random.randint(0, 5)
        ))

        print(f"  Discovery #{discovery_id_counter}: {template['name']} @ {location['name']} ({location_type})")
        discovery_id_counter += 1

    # Commit all changes
    conn.commit()
    conn.close()

    print(f"\n{'=' * 60}")
    print("Test data inserted successfully!")
    print(f"  Systems: 5")
    print(f"  Planets: {planet_id_counter - next_planet_id}")
    print(f"  Moons: {moon_id_counter - next_moon_id}")
    print(f"  Discoveries: {discovery_id_counter - next_discovery_id}")
    print("=" * 60)

if __name__ == '__main__':
    insert_test_data()
