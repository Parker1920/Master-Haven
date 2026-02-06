"""
Database Migration: Add Star Position Columns

This migration adds star_x, star_y, star_z columns to the systems table.
These columns store the calculated 3D position of each star within its region,
allowing proper visualization without overlapping stars in the same region.

The original x, y, z columns remain as "region coordinates" (from glyph YY-ZZZ-XXX).
The new star_x, star_y, star_z columns store the actual star position for 3D rendering.

This is a NON-DESTRUCTIVE migration - it only adds new columns, does not modify existing data.
Existing systems will have NULL star positions until the backfill script is run.
"""

import sqlite3
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Database path — resolved relative to this script's location
DB_PATH = Path(__file__).parent.parent / 'data' / 'haven_ui.db'

def find_database():
    """Find the database file."""
    if DB_PATH.exists():
        return DB_PATH
    return None

def backup_database(db_path: Path) -> Path:
    """Create a backup of the database before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_star_positions_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    print(f"[OK] Database backed up to: {backup_path}")
    return backup_path

def check_columns_exist(cursor) -> dict:
    """Check which star position columns already exist."""
    cursor.execute("PRAGMA table_info(systems)")
    columns = {row[1] for row in cursor.fetchall()}

    return {
        'star_x': 'star_x' in columns,
        'star_y': 'star_y' in columns,
        'star_z': 'star_z' in columns,
    }

def add_star_position_columns(db_path: Path) -> bool:
    """Add star_x, star_y, star_z columns to systems table."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check what already exists
        existing = check_columns_exist(cursor)

        print("\n=== Checking Current Schema ===")
        for col, exists in existing.items():
            status = "EXISTS" if exists else "MISSING"
            print(f"  {col}: {status}")

        if all(existing.values()):
            print("\n[INFO] All star position columns already exist. No migration needed.")
            return True

        print("\n=== Adding Star Position Columns ===")

        # Add star_x column (REAL for floating point precision)
        if not existing['star_x']:
            print("  Adding star_x column...")
            cursor.execute("ALTER TABLE systems ADD COLUMN star_x REAL")
            print("  [OK] star_x added")

        # Add star_y column
        if not existing['star_y']:
            print("  Adding star_y column...")
            cursor.execute("ALTER TABLE systems ADD COLUMN star_y REAL")
            print("  [OK] star_y added")

        # Add star_z column
        if not existing['star_z']:
            print("  Adding star_z column...")
            cursor.execute("ALTER TABLE systems ADD COLUMN star_z REAL")
            print("  [OK] star_z added")

        # Create index for star position queries (spatial lookups)
        print("\n=== Adding Spatial Index ===")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_systems_star_coords
                ON systems(star_x, star_y, star_z)
            """)
            print("  [OK] Index idx_systems_star_coords created")
        except sqlite3.OperationalError as e:
            print(f"  [WARN] Could not create index: {e}")

        conn.commit()
        print("\n[OK] Migration completed successfully!")

        # Verify the changes
        print("\n=== Verifying Schema ===")
        final_check = check_columns_exist(cursor)
        for col, exists in final_check.items():
            status = "OK" if exists else "FAILED"
            print(f"  {col}: {status}")

        if not all(final_check.values()):
            print("\n[ERROR] Some columns were not added correctly!")
            return False

        return True

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    print("=" * 60)
    print("Master-Haven: Star Position Migration")
    print("=" * 60)

    # Find database
    db_path = find_database()
    if not db_path:
        print("\n[ERROR] Database not found!")
        print("Searched paths:")
        for p in DB_PATHS:
            print(f"  - {p}")
        sys.exit(1)

    print(f"\nDatabase: {db_path}")
    print(f"Exists: {db_path.exists()}")

    # Confirm with user
    print("\nThis migration will:")
    print("  1. Backup the database")
    print("  2. Add star_x, star_y, star_z columns to systems table")
    print("  3. Create spatial index for performance")
    print("\nExisting data will NOT be modified.")
    print("Star positions for existing systems will be NULL until backfill.\n")

    response = input("Continue? (y/n): ").strip().lower()
    if response != 'y':
        print("Migration cancelled.")
        sys.exit(0)

    # Backup
    print("\n=== Creating Backup ===")
    backup_path = backup_database(db_path)

    # Migrate
    success = add_star_position_columns(db_path)

    if success:
        print("\n" + "=" * 60)
        print("Migration Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Run the backfill script to calculate star positions for existing systems")
        print("     python scripts/backfill_star_positions.py")
        print("  2. Restart the web server")
        print(f"\nBackup location: {backup_path}")
    else:
        print("\n" + "=" * 60)
        print("Migration Failed!")
        print("=" * 60)
        print(f"\nYou can restore from backup: {backup_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()
