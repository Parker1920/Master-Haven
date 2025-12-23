"""
Force migration by creating a new database with correct schema.
This script will:
1. Create a backup of the old database
2. Create a new database with updated schema
3. Copy all data from old to new
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / 'Haven-UI' / 'data' / 'haven_ui.db'
BACKUP_PATH = Path(__file__).parent / 'Haven-UI' / 'data' / 'backups' / f'haven_ui_pre_glyph_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'


def force_migrate():
    print("=" * 70)
    print("FORCE MIGRATION: Creating new database with updated schema")
    print("=" * 70)

    # Ensure backup directory exists
    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Copy current database to backup
    print("\n[1/5] Creating backup...")
    try:
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"  Backup created: {BACKUP_PATH.name}")
    except Exception as e:
        print(f"  WARNING: Could not create backup: {e}")
        response = input("  Continue without backup? (yes/no): ")
        if response.lower() != 'yes':
            print("Migration cancelled.")
            return

    # Step 2: Read all data from old database (read-only connection)
    print("\n[2/5] Reading data from current database...")
    try:
        # Open in read-only mode
        old_conn = sqlite3.connect(f'file:{DB_PATH}?mode=ro', uri=True, timeout=1.0)
        old_cursor = old_conn.cursor()

        # Read systems
        old_cursor.execute("SELECT * FROM systems")
        systems_data = old_cursor.fetchall()

        old_cursor.execute("PRAGMA table_info(systems)")
        systems_columns = [col[1] for col in old_cursor.fetchall()]

        print(f"  Found {len(systems_data)} systems")
        print(f"  Columns: {', '.join(systems_columns)}")

        old_conn.close()

    except Exception as e:
        print(f"  ERROR reading data: {e}")
        return

    # Step 3: Create new temporary database
    print("\n[3/5] Creating new database with updated schema...")
    NEW_DB_PATH = DB_PATH.parent / 'haven_ui_new.db'

    if NEW_DB_PATH.exists():
        NEW_DB_PATH.unlink()

    new_conn = sqlite3.connect(NEW_DB_PATH)
    new_cursor = new_conn.cursor()

    # Create new systems table
    new_cursor.execute("""
        CREATE TABLE systems (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            x REAL NOT NULL,
            y REAL NOT NULL,
            z REAL NOT NULL,
            galaxy TEXT NOT NULL DEFAULT 'Euclid',
            region_x INTEGER,
            region_y INTEGER,
            region_z INTEGER,
            glyph_code TEXT UNIQUE,
            glyph_planet INTEGER DEFAULT 0,
            glyph_solar_system INTEGER DEFAULT 1,
            fauna TEXT,
            flora TEXT,
            sentinel TEXT,
            materials TEXT,
            base_location TEXT,
            photo TEXT,
            attributes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create indices
    new_cursor.execute("CREATE INDEX idx_systems_coords ON systems(x, y, z)")
    new_cursor.execute("CREATE INDEX idx_systems_glyph ON systems(glyph_code)")
    new_cursor.execute("CREATE INDEX idx_systems_galaxy ON systems(galaxy)")
    new_cursor.execute("CREATE INDEX idx_systems_region ON systems(region_x, region_y, region_z)")

    print("  New schema created")

    # Step 4: Insert data into new database
    print("\n[4/5] Migrating data...")
    if systems_data:
        # Map old columns to new
        col_map = {}
        for idx, col in enumerate(systems_columns):
            if col == 'region':
                col_map['galaxy'] = idx
            else:
                col_map[col] = idx

        for row in systems_data:
            values = {
                'id': row[col_map['id']],
                'name': row[col_map['name']],
                'x': row[col_map['x']],
                'y': row[col_map['y']],
                'z': row[col_map['z']],
                'galaxy': row[col_map.get('galaxy', col_map.get('region', 0))] or 'Euclid',
                'fauna': row[col_map.get('fauna', None)] if 'fauna' in col_map else None,
                'flora': row[col_map.get('flora', None)] if 'flora' in col_map else None,
                'sentinel': row[col_map.get('sentinel', None)] if 'sentinel' in col_map else None,
                'materials': row[col_map.get('materials', None)] if 'materials' in col_map else None,
                'base_location': row[col_map.get('base_location', None)] if 'base_location' in col_map else None,
                'photo': row[col_map.get('photo', None)] if 'photo' in col_map else None,
                'attributes': row[col_map.get('attributes', None)] if 'attributes' in col_map else None,
                'created_at': row[col_map.get('created_at', None)] if 'created_at' in col_map else None,
                'modified_at': row[col_map.get('modified_at', None)] if 'modified_at' in col_map else None,
            }

            new_cursor.execute("""
                INSERT INTO systems (
                    id, name, x, y, z, galaxy,
                    fauna, flora, sentinel, materials, base_location,
                    photo, attributes, created_at, modified_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                values['id'], values['name'], values['x'], values['y'], values['z'],
                values['galaxy'], values['fauna'], values['flora'], values['sentinel'],
                values['materials'], values['base_location'], values['photo'],
                values['attributes'], values['created_at'], values['modified_at']
            ))

        new_conn.commit()
        print(f"  Migrated {len(systems_data)} systems")

    new_conn.close()

    # Step 5: Replace old database with new
    print("\n[5/5] Replacing old database...")
    print("  Please close all applications using the database and press Enter...")
    input()

    try:
        # Delete WAL files
        wal_file = DB_PATH.with_suffix('.db-wal')
        shm_file = DB_PATH.with_suffix('.db-shm')

        if wal_file.exists():
            wal_file.unlink()
            print("  Removed WAL file")

        if shm_file.exists():
            shm_file.unlink()
            print("  Removed SHM file")

        # Replace database
        DB_PATH.unlink()
        shutil.move(NEW_DB_PATH, DB_PATH)
        print("  Database replaced successfully!")

        # Verify
        verify_conn = sqlite3.connect(DB_PATH)
        verify_cursor = verify_conn.cursor()
        verify_cursor.execute("SELECT COUNT(*) FROM systems")
        count = verify_cursor.fetchone()[0]
        verify_cursor.execute("PRAGMA table_info(systems)")
        columns = [col[1] for col in verify_cursor.fetchall()]
        verify_conn.close()

        print("\n" + "=" * 70)
        print("MIGRATION COMPLETE!")
        print("=" * 70)
        print(f"Systems migrated: {count}")
        print(f"New columns: {', '.join(columns)}")
        print(f"Backup location: {BACKUP_PATH}")

    except Exception as e:
        print(f"\nERROR replacing database: {e}")
        print(f"New database available at: {NEW_DB_PATH}")
        print(f"Old database backed up at: {BACKUP_PATH}")
        print("Please manually replace the database file.")


if __name__ == '__main__':
    force_migrate()
