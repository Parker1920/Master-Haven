import sqlite3
import json

conn = sqlite3.connect(r"c:\Master-Haven\Haven-UI\data\haven_ui.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== Checking pending system submissions ===\n")
cur.execute("SELECT id, system_name, system_data FROM pending_systems ORDER BY id DESC LIMIT 2")
rows = cur.fetchall()

for r in rows:
    print(f"ID: {r['id']}")
    print(f"System Name: {r['system_name']}")
    print(f"Raw system_data:")
    try:
        data = json.loads(r['system_data'])
        print(json.dumps(data, indent=2))
    except:
        print(r['system_data'])
    print("\n" + "="*50 + "\n")

conn.close()
