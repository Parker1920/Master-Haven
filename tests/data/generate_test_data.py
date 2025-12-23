"""
Test Data Generator for Master-Haven Glyph System

Generates realistic test systems with proper glyph codes, planets, moons, space stations, and discoveries.
"""

import sqlite3
import os
import sys
import random
import uuid
from datetime import datetime, timedelta

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from glyph_decoder import encode_coords_to_glyph, validate_glyph_code, calculate_region_name, is_in_core_void

DB_PATH = r'C:\Master-Haven\Haven-UI\data\haven_ui.db'

# Test system names (NMS-themed)
SYSTEM_NAMES = [
    "Drogradur",
    "Iousongsat XVI",
    "Elkupalos",
    "Hicanpamar",
    "Odyalax",
    "Givingston",
    "Aaseamru",
    "Enleystein",
    "Uschukulm",
    "Orsangtry VIII",
    "Toarunn",
    "Ibsenpamar",
    "Lakenswood",
    "Gosakagawa XIV",
    "Hageakron-Zet",
    "Duikirk",
    "Ewilukino",
    "Nisobucha",
    "Itopamar",
    "Letonfield XIX",
    "Zuhilok",
    "Ogatown",
    "Bihangir",
    "Idahawa VI",
    "Norutokk-Mor",
    "Gelofield",
    "Onihamrv",
    "Gulusanct",
    "Aarungawa-Zet",
    "Shotopoint XXII"
]

PLANET_PREFIXES = [
    "Ket", "Ora", "Una", "Mel", "Vin", "Til", "Nar", "Kas", "Rud", "Gek",
    "Kor", "Vex", "Hir", "Zet", "Lok", "Nim", "Tal", "Wex", "Yar", "Zen"
]

PLANET_SUFFIXES = [
    "Prime", "Secundus", "Alpha", "Beta", "Gamma", "Major", "Minor", "Tertius"
]

MON_PREFIXES = [
    "Lu", "Sel", "Tit", "Cal", "Gan", "Eur", "Tri", "Pho", "Dei", "Cha"
]

DISCOVERY_FLORA = [
    "Humming Sac", "Gravitino Host", "Albumen Pearl Plant", "Star Bulb", "Solanium",
    "Frost Crystal", "Gamma Root", "Cactus Flesh", "Marrow Bulb", "Kelp Sac"
]

DISCOVERY_FAUNA = [
    "Diplo Descendant", "Quadrupedal Mammal", "Flying Serpent", "Protoplanar Beetle",
    "Bipedal Predator", "Hexapod Herbivore", "Grazing Ruminant", "Aquatic Swarmer"
]

DISCOVERY_MINERALS = [
    "Copper Deposit", "Paraffinium", "Uranium Node", "Activated Copper", "Gold Deposit",
    "Emeril", "Cadmium", "Indium", "Ancient Bones", "Salvageable Scrap"
]

RACES = ["Gek", "Korvax", "Vy'keen"]
ECONOMIES = ["Trading", "Mining", "Manufacturing", "Technology", "Scientific", "Power Generation", "Mercantile"]
CONFLICTS = ["Peaceful", "Tranquil", "Booming", "Promising", "Declining", "At War", "Under Attack"]
SENTINELS = ["None", "Low", "Standard", "Aggressive", "High Security"]

def generate_coordinate(min_val, max_val, spread=0.3):
    """Generate coordinates clustered in central region with some outliers."""
    if random.random() < 0.8:
        # 80% clustered in central region
        center = (max_val + min_val) / 2
        range_size = (max_val - min_val) * spread
        return int(center + random.uniform(-range_size/2, range_size/2))
    else:
        # 20% spread out
        return random.randint(min_val, max_val)

def generate_systems(count=30):
    """Generate test star systems with proper glyph codes."""
    systems = []
    used_names = set()
    used_glyphs = set()

    for i in range(count):
        # Generate unique name
        name = random.choice(SYSTEM_NAMES)
        while name in used_names:
            name = random.choice(SYSTEM_NAMES) + f" {random.choice(['VII', 'XIV', 'XXI', 'Prime'])}"
        used_names.add(name)

        # Generate coordinates (clustered around center with some spread)
        # Ensure coordinates are NOT in the galactic core void
        max_attempts = 100
        for _ in range(max_attempts):
            x = generate_coordinate(-2048, 2047)
            y = generate_coordinate(-128, 127, spread=0.4)  # Vertical is narrower
            z = generate_coordinate(-2048, 2047)

            # Check if coordinates are outside core void
            if not is_in_core_void(x, y, z):
                break
        else:
            # Failed to find valid coordinates after max_attempts
            print(f"Warning: Could not generate coordinates outside core void for {name}")
            continue

        solar_system = random.randint(1, 767)
        planet = 0  # System-level glyph

        # Encode to glyph
        try:
            glyph = encode_coords_to_glyph(x, y, z, planet, solar_system)

            # Ensure unique glyph (while avoiding core void)
            attempt_count = 0
            while glyph in used_glyphs and attempt_count < 50:
                x += random.randint(-10, 10)
                z += random.randint(-10, 10)
                x = max(-2048, min(2047, x))
                z = max(-2048, min(2047, z))

                # Skip if in core void
                if is_in_core_void(x, y, z):
                    attempt_count += 1
                    continue

                glyph = encode_coords_to_glyph(x, y, z, planet, solar_system)
                attempt_count += 1

            used_glyphs.add(glyph)
        except ValueError as e:
            print(f"Warning: Failed to generate glyph for {name}: {e}")
            continue

        # Calculate region coordinates
        region_x = (x + 2048) // 128
        region_y = (y + 128) // 128
        region_z = (z + 2048) // 128

        system = {
            'id': str(uuid.uuid4()),
            'name': name,
            'x': x,
            'y': y,
            'z': z,
            'galaxy': 'Euclid',
            'glyph_code': glyph,
            'glyph_planet': planet,
            'glyph_solar_system': solar_system,
            'region_x': region_x,
            'region_y': region_y,
            'region_z': region_z,
            'description': f"A {random.choice(CONFLICTS).lower()} star system in the {calculate_region_name(region_x, region_y, region_z)} region.",
            'economy': random.choice(ECONOMIES),
            'conflict': random.choice(CONFLICTS),
            'discovered_by': random.choice(['Traveller Atlas', 'Explorer Polo', 'Scientist Nada', 'Merchant Helios']),
            'discovered_at': (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(),
            'approved': 1
        }
        systems.append(system)
        print(f"Generated system: {name} at ({x}, {y}, {z}) - Glyph: {glyph}")

    return systems

def generate_planets_for_system(system_id, system_name, num_planets=None):
    """Generate planets and moons for a system."""
    if num_planets is None:
        num_planets = random.randint(2, 6)

    planets = []
    for i in range(num_planets):
        prefix = random.choice(PLANET_PREFIXES)
        suffix = random.choice(PLANET_SUFFIXES) if random.random() > 0.5 else ""
        name = f"{prefix} {suffix}" if suffix else prefix

        planet = {
            'id': str(uuid.uuid4()),
            'system_id': system_id,
            'name': name,
            'climate': random.choice(["Frozen", "Scorched", "Toxic", "Radioactive", "Lush", "Barren", "Temperate"]),
            'sentinel': random.choice(SENTINELS),
            'fauna_count': random.randint(0, 12),
            'flora_count': random.randint(5, 20),
            'has_water': random.choice([0, 1])
        }
        planets.append(planet)

        # Generate 0-2 moons for planet
        num_moons = random.choices([0, 1, 2], weights=[0.5, 0.3, 0.2])[0]
        for j in range(num_moons):
            moon_name = f"{random.choice(MON_PREFIXES)}-{i+1}-{j+1}"
            moon = {
                'id': str(uuid.uuid4()),
                'planet_id': planet['id'],
                'name': moon_name,
                'climate': random.choice(["Airless", "Frozen", "Dead", "Lifeless"]),
                'sentinel': random.choice(["None", "Low"]),
                'resources': random.choice(["Copper", "Cobalt", "Silver", "Gold"])
            }
            planets.append((planet, moon))

    print(f"  Generated {num_planets} planets for {system_name}")
    return planets

def generate_space_station(system_id, system_name):
    """Generate a space station for a system."""
    station = {
        'id': str(uuid.uuid4()),
        'system_id': system_id,
        'name': f"{system_name} Station",
        'race': random.choice(RACES),
        'sell_percent': random.randint(70, 90),
        'buy_percent': random.randint(40, 60),
        'x': round(random.uniform(-20, 20), 2),
        'y': round(random.uniform(-15, 15), 2),
        'z': round(random.uniform(-20, 20), 2)
    }
    return station

def generate_discoveries(planet_id, planet_name, count=None):
    """Generate discoveries for a planet/moon."""
    if count is None:
        count = random.randint(2, 6)

    discoveries = []
    for i in range(count):
        discovery_type = random.choice(['flora', 'fauna', 'mineral'])

        if discovery_type == 'flora':
            name = random.choice(DISCOVERY_FLORA)
        elif discovery_type == 'fauna':
            name = random.choice(DISCOVERY_FAUNA)
        else:
            name = random.choice(DISCOVERY_MINERALS)

        discovery = {
            'id': str(uuid.uuid4()),
            'planet_id': planet_id,
            'name': name,
            'discovery_type': discovery_type,
            'discovered_by': random.choice(['Traveller Atlas', 'Explorer Polo', 'Scientist Nada']),
            'discovered_at': (datetime.now() - timedelta(days=random.randint(1, 180))).isoformat(),
            'description': f"Discovered on {planet_name}"
        }
        discoveries.append(discovery)

    return discoveries

def insert_test_data():
    """Insert all test data into database."""
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("\n=== Generating Test Data ===\n")

        # Generate systems
        print("Generating star systems...")
        systems = generate_systems(30)

        # Insert systems
        for system in systems:
            cursor.execute("""
                INSERT INTO systems (id, name, x, y, z, galaxy, glyph_code, glyph_planet, glyph_solar_system,
                                    region_x, region_y, region_z, description, economy, conflict,
                                    discovered_by, discovered_at, approved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (system['id'], system['name'], system['x'], system['y'], system['z'], system['galaxy'],
                  system['glyph_code'], system['glyph_planet'], system['glyph_solar_system'],
                  system['region_x'], system['region_y'], system['region_z'], system['description'],
                  system['economy'], system['conflict'], system['discovered_by'], system['discovered_at'],
                  system['approved']))

        print(f"\n[OK] Inserted {len(systems)} systems")

        # Generate planets, moons, stations, discoveries
        total_planets = 0
        total_moons = 0
        total_stations = 0
        total_discoveries = 0

        for system in systems:
            # Planets and moons
            planets_data = generate_planets_for_system(system['id'], system['name'])
            for planet_info in planets_data:
                if isinstance(planet_info, tuple):
                    planet, moon = planet_info
                    # Insert planet
                    cursor.execute("""
                        INSERT INTO planets (id, system_id, name, climate, sentinel, fauna_count, flora_count, has_water)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (planet['id'], planet['system_id'], planet['name'], planet['climate'], planet['sentinel'],
                          planet['fauna_count'], planet['flora_count'], planet['has_water']))
                    total_planets += 1

                    # Insert moon
                    cursor.execute("""
                        INSERT INTO moons (id, planet_id, name, climate, sentinel, resources)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (moon['id'], moon['planet_id'], moon['name'], moon['climate'], moon['sentinel'], moon['resources']))
                    total_moons += 1

                    # Generate discoveries for planet
                    planet_discoveries = generate_discoveries(planet['id'], planet['name'])
                    for disc in planet_discoveries:
                        cursor.execute("""
                            INSERT INTO discoveries (id, planet_id, discovery_name, discovery_type, discovered_by, submission_timestamp, description)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (disc['id'], disc['planet_id'], disc['name'], disc['discovery_type'],
                              disc['discovered_by'], disc['discovered_at'], disc['description']))
                        total_discoveries += 1

                    # Generate discoveries for moon
                    moon_discoveries = generate_discoveries(moon['id'], moon['name'], count=random.randint(1, 3))
                    for disc in moon_discoveries:
                        cursor.execute("""
                            INSERT INTO discoveries (id, planet_id, discovery_name, discovery_type, discovered_by, submission_timestamp, description)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (disc['id'], disc['planet_id'], disc['name'], disc['discovery_type'],
                              disc['discovered_by'], disc['discovered_at'], disc['description']))
                        total_discoveries += 1
                else:
                    planet = planet_info
                    # Insert planet
                    cursor.execute("""
                        INSERT INTO planets (id, system_id, name, climate, sentinel, fauna_count, flora_count, has_water)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (planet['id'], planet['system_id'], planet['name'], planet['climate'], planet['sentinel'],
                          planet['fauna_count'], planet['flora_count'], planet['has_water']))
                    total_planets += 1

                    # Generate discoveries for planet
                    planet_discoveries = generate_discoveries(planet['id'], planet['name'])
                    for disc in planet_discoveries:
                        cursor.execute("""
                            INSERT INTO discoveries (id, planet_id, discovery_name, discovery_type, discovered_by, submission_timestamp, description)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (disc['id'], disc['planet_id'], disc['name'], disc['discovery_type'],
                              disc['discovered_by'], disc['discovered_at'], disc['description']))
                        total_discoveries += 1

            # Space station (80% chance)
            if random.random() < 0.8:
                station = generate_space_station(system['id'], system['name'])
                cursor.execute("""
                    INSERT INTO space_stations (id, system_id, name, race, sell_percent, buy_percent, x, y, z)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (station['id'], station['system_id'], station['name'], station['race'],
                      station['sell_percent'], station['buy_percent'], station['x'], station['y'], station['z']))
                total_stations += 1

        conn.commit()

        print(f"\n=== Test Data Summary ===")
        print(f"Systems: {len(systems)}")
        print(f"Planets: {total_planets}")
        print(f"Moons: {total_moons}")
        print(f"Space Stations: {total_stations}")
        print(f"Discoveries: {total_discoveries}")
        print(f"\n[OK] Test data generation complete!")

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Test data generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()

if __name__ == '__main__':
    print("="*60)
    print("Master-Haven Test Data Generator")
    print("="*60)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Exists: {os.path.exists(DB_PATH)}\n")

    if insert_test_data():
        print("\n" + "="*60)
        print("Test data inserted successfully!")
        print("You can now start the web server and test the glyph system.")
        print("="*60)
        sys.exit(0)
    else:
        sys.exit(1)
