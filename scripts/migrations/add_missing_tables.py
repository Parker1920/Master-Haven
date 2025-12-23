"""
Database Migration Script - Add Missing Tables
===============================================

This script adds the missing systems, planets, moons, and space_stations tables
to existing Haven UI databases.

Created: November 25, 2025
Purpose: Fix database schema after refactoring
"""

import sqlite3
import sys
from pathlib import Path

# Add Master-Haven root to path
master_haven_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(master_haven_root))

try:
    from config.paths import haven_paths
except ImportError:
    haven_paths = None


def get_database_path():
    """Get the Haven database path using centralized config."""
    if haven_paths and haven_paths.haven_db:
        return haven_paths.haven_db
    # Fallback
    return master_haven_root / 'Haven-UI' / 'data' / 'haven_ui.db'


def check_table_exists(cursor, table_name):
    """Check if a table exists in the database."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name=?
    """, (table_name,))
    return cursor.fetchone() is not None


def add_missing_tables(db_path):
    """Add missing tables to the database."""
    print(f"Migrating database: {db_path}")

    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return False

    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    cursor = conn.cursor()

    tables_to_add = {
        'systems': '''
            CREATE TABLE IF NOT EXISTS systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                galaxy TEXT DEFAULT 'Euclid',
                x INTEGER,
                y INTEGER,
                z INTEGER,
                description TEXT,
                glyph_code TEXT,
                glyph_planet INTEGER DEFAULT 0,
                glyph_solar_system INTEGER DEFAULT 1,
                region_x INTEGER,
                region_y INTEGER,
                region_z INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',
        'planets': '''
            CREATE TABLE IF NOT EXISTS planets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                x REAL DEFAULT 0,
                y REAL DEFAULT 0,
                z REAL DEFAULT 0,
                climate TEXT,
                sentinel TEXT DEFAULT 'None',
                fauna_count INTEGER DEFAULT 0,
                flora_count INTEGER DEFAULT 0,
                has_water INTEGER DEFAULT 0,
                description TEXT,
                FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE
            )
        ''',
        'moons': '''
            CREATE TABLE IF NOT EXISTS moons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                planet_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                orbit_radius REAL DEFAULT 0.5,
                climate TEXT,
                sentinel TEXT DEFAULT 'None',
                description TEXT,
                FOREIGN KEY (planet_id) REFERENCES planets(id) ON DELETE CASCADE
            )
        ''',
        'space_stations': '''
            CREATE TABLE IF NOT EXISTS space_stations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                race TEXT DEFAULT 'Gek',
                x REAL DEFAULT 0,
                y REAL DEFAULT 0,
                z REAL DEFAULT 0,
                sell_percent INTEGER DEFAULT 80,
                buy_percent INTEGER DEFAULT 50,
                FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE
            )
        '''
    }

    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_planets_system_id ON planets(system_id)',
        'CREATE INDEX IF NOT EXISTS idx_moons_planet_id ON moons(planet_id)',
        'CREATE INDEX IF NOT EXISTS idx_space_stations_system_id ON space_stations(system_id)',
        'CREATE INDEX IF NOT EXISTS idx_discoveries_system_id ON discoveries(system_id)',
        'CREATE INDEX IF NOT EXISTS idx_discoveries_planet_id ON discoveries(planet_id)',
        'CREATE INDEX IF NOT EXISTS idx_pending_systems_status ON pending_systems(status)'
    ]

    # Check existing tables
    print("\nChecking existing tables:")
    for table_name in tables_to_add.keys():
        exists = check_table_exists(cursor, table_name)
        status = "EXISTS" if exists else "MISSING"
        print(f"  - {table_name}: {status}")

    # Add missing tables
    print("\nAdding missing tables:")
    for table_name, create_sql in tables_to_add.items():
        if not check_table_exists(cursor, table_name):
            print(f"  - Creating table: {table_name}")
            cursor.execute(create_sql)
        else:
            print(f"  - Skipping (already exists): {table_name}")

    # Add indexes
    print("\nAdding indexes:")
    for index_sql in indexes:
        print(f"  - {index_sql.split('idx_')[1].split(' ON')[0] if 'idx_' in index_sql else 'index'}")
        cursor.execute(index_sql)

    # Commit changes
    conn.commit()

    # Verify tables were created
    print("\nVerifying migration:")
    all_tables_exist = True
    for table_name in tables_to_add.keys():
        exists = check_table_exists(cursor, table_name)
        status = "OK" if exists else "FAIL"
        print(f"  [{status}] {table_name}")
        if not exists:
            all_tables_exist = False

    conn.close()

    if all_tables_exist:
        print("\n[SUCCESS] Migration completed successfully!")
        return True
    else:
        print("\n[FAILED] Migration failed - some tables were not created")
        return False


if __name__ == '__main__':
    db_path = get_database_path()
    print("=" * 60)
    print("Haven Database Migration - Add Missing Tables")
    print("=" * 60)

    success = add_missing_tables(db_path)

    sys.exit(0 if success else 1)
