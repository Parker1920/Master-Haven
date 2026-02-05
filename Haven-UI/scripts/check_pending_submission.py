"""Check pending submission data"""
import sqlite3
import json
from pathlib import Path

db_path = Path('Haven-UI/data/haven_ui.db')
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

cursor.execute('SELECT id, system_name, system_data, status FROM pending_systems WHERE id = 1')
row = cursor.fetchone()

print(f'Pending Submission #{row[0]}: {row[1]}')
print(f'Status: {row[3]}')

data = json.loads(row[2])
print(f'\nSystem data:')
print(f'  Name: {data.get("name")}')
print(f'  Coords: ({data.get("x")}, {data.get("y")}, {data.get("z")})')
print(f'  Planets: {len(data.get("planets", []))}')

for i, p in enumerate(data.get('planets', [])):
    print(f'\n  Planet {i+1}: {p.get("name")}')
    print(f'    Coords: ({p.get("x")}, {p.get("y")}, {p.get("z")})')
    print(f'    Climate: {p.get("climate")}')
    print(f'    Moons: {len(p.get("moons", []))}')
    for m in p.get('moons', []):
        print(f'      - {m.get("name")}')

conn.close()
