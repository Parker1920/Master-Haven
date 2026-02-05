"""Quick test system generator - systems only, no planets"""
import sqlite3
import sys
import random
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, r'C:\Master-Haven\src')
from glyph_decoder import encode_coords_to_glyph, get_region_name

DB_PATH = r'C:\Master-Haven\Haven-UI\data\haven_ui.db'

NAMES = ["Drogradur", "Iousongsat XVI", "Elkupalos", "Hicanpamar", "Odyalax",
         "Givingston", "Aaseamru", "Enleystein", "Uschukulm", "Orsangtry VIII",
         "Toarunn", "Lakenswood", "Hageakron-Zet", "Duikirk", "Ewilukino",
         "Nisobucha", "Letonfield XIX", "Zuhilok", "Ogatown", "Bihangir",
         "Idahawa VI", "Norutokk-Mor", "Gelofield", "Onihamrv", "Aarungawa-Zet",
         "Shotopoint XXII", "Itopamar", "Gosakagawa XIV", "Gulusanct", "Ibsenpamar"]

def gen_coord(min_val, max_val, spread=0.3):
    if random.random() < 0.8:
        center = (max_val + min_val) / 2
        range_size = (max_val - min_val) * spread
        return int(center + random.uniform(-range_size/2, range_size/2))
    return random.randint(min_val, max_val)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Generating 30 test systems...")
used_names = set()
for i in range(30):
    name = random.choice(NAMES)
    while name in used_names:
        name = random.choice(NAMES) + f" {random.choice(['VII', 'XIV', 'XXI', 'Prime'])}"
    used_names.add(name)
    x = gen_coord(-2048, 2047)
    y = gen_coord(-128, 127, 0.4)
    z = gen_coord(-2048, 2047)
    planet = 0
    solar_system = random.randint(1, 767)

    glyph = encode_coords_to_glyph(x, y, z, planet, solar_system)
    region_x = (x + 2048) // 128
    region_y = (y + 128) // 128
    region_z = (z + 2048) // 128

    cursor.execute("""
        INSERT INTO systems (id, name, x, y, z, galaxy, glyph_code, glyph_planet, glyph_solar_system,
                            region_x, region_y, region_z, discovered_by, discovered_at, approved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), name, x, y, z, 'Euclid', glyph, planet, solar_system,
          region_x, region_y, region_z, 'Test Explorer',
          (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat(), 1))

    print(f"  {i+1}. {name}: {glyph} at ({x}, {y}, {z})")

conn.commit()
print(f"\n✓ Created 30 systems!")
cursor.execute("SELECT COUNT(*) FROM systems")
print(f"Total in database: {cursor.fetchone()[0]}")
conn.close()
