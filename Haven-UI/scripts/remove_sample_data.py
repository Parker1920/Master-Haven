#!/usr/bin/env python3
"""Remove sample data I added"""
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).parent.parent / 'data' / 'haven_ui.db'

conn = sqlite3.connect(str(DB_FILE))
cursor = conn.cursor()

# Remove the sample data
cursor.execute('''
    UPDATE planets
    SET flora=NULL, fauna=NULL, materials=NULL, base_location=NULL, notes=NULL
    WHERE name IN ("Voyager's Haven", "New Oculs", "Erren")
''')
conn.commit()
print(f"Removed sample data from {cursor.rowcount} planets")
conn.close()
