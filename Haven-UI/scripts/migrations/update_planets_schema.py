"""
Database Migration - Update Planets Table Schema
=================================================

This script updates the planets table to add missing coordinate and game property columns.

Created: November 25, 2025
Purpose: Add x, y, z, climate, fauna_count, flora_count, has_water, description columns
"""

import sqlite3
import sys
from pathlib import Path

# Add Haven-UI backend to path
haven_ui_dir = Path(__file__).resolve().parents[2]
backend_dir = haven_ui_dir / 'backend'
sys.path.insert(0, str(backend_dir))

try:
    from paths import haven_paths
except ImportError:
    haven_paths = None


def get_database_path():
    """Get the Haven database path using centralized config."""
    if haven_paths and haven_paths.haven_db:
        return haven_paths.haven_db
    return haven_ui_dir / 'data' / 'haven_ui.db'


def backup_database(db_path):
    """Create a backup of the database before migration."""
    import shutil
    from datetime import datetime

    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f'pre_schema_update_{timestamp}.db'

    shutil.copy2(db_path, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path


def migrate_planets_table(db_path):
    """Add missing columns to planets table."""
    print(f"\nMigrating database: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    cursor = conn.cursor()

    # Check current schema
    cursor.execute("PRAGMA table_info(planets)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    print(f"\nExisting columns in planets table:")
    for col in sorted(existing_columns):
        print(f"  - {col}")

    # Define columns to add
    columns_to_add = {
        'x': ('REAL', 0),
        'y': ('REAL', 0),
        'z': ('REAL', 0),
        'climate': ('TEXT', None),
        'sentinel_level': ('TEXT', 'None'),  # Different name to avoid conflict
        'fauna_count': ('INTEGER', 0),
        'flora_count': ('INTEGER', 0),
        'has_water': ('INTEGER', 0),
        'description': ('TEXT', None)
    }

    # Add missing columns
    print(f"\nAdding missing columns:")
    for column_name, (column_type, default_value) in columns_to_add.items():
        if column_name not in existing_columns:
            default_clause = f"DEFAULT {default_value}" if default_value is not None else ""
            if default_value is None:
                alter_sql = f"ALTER TABLE planets ADD COLUMN {column_name} {column_type}"
            elif isinstance(default_value, str):
                alter_sql = f"ALTER TABLE planets ADD COLUMN {column_name} {column_type} DEFAULT '{default_value}'"
            else:
                alter_sql = f"ALTER TABLE planets ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"

            print(f"  - Adding column: {column_name} ({column_type})")
            try:
                cursor.execute(alter_sql)
            except Exception as e:
                print(f"    WARNING: {e}")
        else:
            print(f"  - Skipping (exists): {column_name}")

    # Similarly update moons table
    print(f"\nUpdating moons table:")
    cursor.execute("PRAGMA table_info(moons)")
    existing_moon_columns = {row[1] for row in cursor.fetchall()}

    moon_columns_to_add = {
        'climate': ('TEXT', None),
        'description': ('TEXT', None)
    }

    for column_name, (column_type, default_value) in moon_columns_to_add.items():
        if column_name not in existing_moon_columns:
            if default_value is None:
                alter_sql = f"ALTER TABLE moons ADD COLUMN {column_name} {column_type}"
            else:
                alter_sql = f"ALTER TABLE moons ADD COLUMN {column_name} {column_type} DEFAULT '{default_value}'"

            print(f"  - Adding column: {column_name} ({column_type})")
            try:
                cursor.execute(alter_sql)
            except Exception as e:
                print(f"    WARNING: {e}")
        else:
            print(f"  - Skipping (exists): {column_name}")

    conn.commit()

    # Verify final schema
    cursor.execute("PRAGMA table_info(planets)")
    final_columns = [row[1] for row in cursor.fetchall()]

    print(f"\nFinal planets table schema ({len(final_columns)} columns):")
    for col in final_columns:
        print(f"  - {col}")

    # Show row counts
    cursor.execute("SELECT COUNT(*) FROM systems")
    systems_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM planets")
    planets_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM discoveries")
    discoveries_count = cursor.fetchone()[0]

    print(f"\nData preserved:")
    print(f"  - Systems: {systems_count}")
    print(f"  - Planets: {planets_count}")
    print(f"  - Discoveries: {discoveries_count}")

    conn.close()

    print("\n[SUCCESS] Schema migration completed!")
    return True


if __name__ == '__main__':
    db_path = get_database_path()
    print("=" * 70)
    print("Haven Database Migration - Update Planets Schema")
    print("=" * 70)

    # Create backup first
    backup_path = backup_database(db_path)

    # Run migration
    success = migrate_planets_table(db_path)

    if success:
        print(f"\nBackup saved at: {backup_path}")
        print("You can restore from backup if needed.")

    sys.exit(0 if success else 1)
