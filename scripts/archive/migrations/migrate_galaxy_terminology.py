"""
Database migration script to fix Galaxy/Region terminology.

Changes:
1. Rename 'region' column to 'galaxy' (what we were incorrectly calling "region")
2. Add proper region coordinates (region_x, region_y, region_z) for NMS regions
3. Add glyph-related columns (glyph_code, glyph_planet, glyph_solar_system)
4. Add spatial indexing for performance
5. Migrate existing data
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / 'Haven-UI' / 'data' / 'haven_ui.db'


def migrate_database():
    """Perform the database migration."""
    print("=" * 60)
    print("DATABASE MIGRATION: Galaxy/Region Terminology Fix")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    # Connect with a timeout to handle locked database
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    cursor = conn.cursor()

    try:
        # First, try to close any existing WAL connections
        print("\nAttempting to close existing database connections...")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        # Step 1: Check current schema
        print("\n[1/7] Checking current schema...")
        cursor.execute("PRAGMA table_info(systems)")
        columns = {row[1]: row for row in cursor.fetchall()}
        print(f"  Found {len(columns)} columns in systems table")

        # Step 2: Create new systems table with correct schema
        print("\n[2/7] Creating new systems table with updated schema...")
        cursor.execute("""
            CREATE TABLE systems_new (
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
        print("  ✓ New table created")

        # Step 3: Copy existing data
        print("\n[3/7] Migrating existing data...")
        cursor.execute("SELECT COUNT(*) FROM systems")
        count = cursor.fetchone()[0]
        print(f"  Found {count} systems to migrate")

        if count > 0:
            # Copy data, renaming 'region' to 'galaxy'
            cursor.execute("""
                INSERT INTO systems_new (
                    id, name, x, y, z, galaxy, fauna, flora, sentinel,
                    materials, base_location, photo, attributes, created_at, modified_at
                )
                SELECT
                    id, name, x, y, z,
                    COALESCE(region, 'Euclid') as galaxy,
                    fauna, flora, sentinel, materials, base_location, photo,
                    attributes, created_at, modified_at
                FROM systems
            """)
            print(f"  ✓ Migrated {count} systems")

        # Step 4: Drop old table and rename new one
        print("\n[4/7] Replacing old table...")
        cursor.execute("DROP TABLE systems")
        cursor.execute("ALTER TABLE systems_new RENAME TO systems")
        print("  ✓ Table replaced")

        # Step 5: Create indices for performance
        print("\n[5/7] Creating indices for spatial queries...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_coords ON systems(x, y, z)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_glyph ON systems(glyph_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_galaxy ON systems(galaxy)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_region ON systems(region_x, region_y, region_z)")
        print("  ✓ Indices created")

        # Step 6: Update any pending_systems table if it exists
        print("\n[6/7] Checking for pending_systems table...")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='pending_systems'
        """)

        if cursor.fetchone():
            print("  Found pending_systems table, migrating...")

            # Check if it has the region column
            cursor.execute("PRAGMA table_info(pending_systems)")
            pending_columns = {row[1]: row for row in cursor.fetchall()}

            if 'region' in pending_columns and 'galaxy' not in pending_columns:
                # Create new pending_systems table
                cursor.execute("""
                    CREATE TABLE pending_systems_new (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        x REAL NOT NULL,
                        y REAL NOT NULL,
                        z REAL NOT NULL,
                        galaxy TEXT NOT NULL DEFAULT 'Euclid',
                        region_x INTEGER,
                        region_y INTEGER,
                        region_z INTEGER,
                        glyph_code TEXT,
                        glyph_planet INTEGER DEFAULT 0,
                        glyph_solar_system INTEGER DEFAULT 1,
                        fauna TEXT,
                        flora TEXT,
                        sentinel TEXT,
                        materials TEXT,
                        base_location TEXT,
                        photo TEXT,
                        attributes TEXT,
                        submitted_by TEXT,
                        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending'
                    )
                """)

                # Copy data
                cursor.execute("""
                    INSERT INTO pending_systems_new
                    SELECT
                        id, name, x, y, z,
                        COALESCE(region, 'Euclid') as galaxy,
                        NULL, NULL, NULL, NULL, 0, 1,
                        fauna, flora, sentinel, materials, base_location, photo,
                        attributes, submitted_by, submitted_at, status
                    FROM pending_systems
                """)

                cursor.execute("DROP TABLE pending_systems")
                cursor.execute("ALTER TABLE pending_systems_new RENAME TO pending_systems")
                print("  ✓ pending_systems table migrated")
            else:
                print("  pending_systems already has correct schema")
        else:
            print("  No pending_systems table found (OK)")

        # Step 7: Commit changes
        print("\n[7/7] Committing changes...")
        conn.commit()
        print("  ✓ Migration completed successfully!")

        # Verify migration
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)
        cursor.execute("SELECT COUNT(*) FROM systems")
        final_count = cursor.fetchone()[0]
        print(f"Systems table: {final_count} records")

        cursor.execute("PRAGMA table_info(systems)")
        columns = cursor.fetchall()
        print(f"Columns: {', '.join([col[1] for col in columns])}")

        # Check for 'galaxy' column
        has_galaxy = any(col[1] == 'galaxy' for col in columns)
        has_region = any(col[1] == 'region' for col in columns)

        if has_galaxy and not has_region:
            print("\nSUCCESS: 'region' renamed to 'galaxy'")
        else:
            print("\nERROR: Migration may have failed")
            if not has_galaxy:
                print("  - 'galaxy' column not found")
            if has_region:
                print("  - 'region' column still exists")

        has_glyph = any(col[1] == 'glyph_code' for col in columns)
        has_region_coords = any(col[1] == 'region_x' for col in columns)

        if has_glyph:
            print("Glyph columns added")
        if has_region_coords:
            print("Region coordinate columns added")

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update API code to use 'galaxy' instead of 'region'")
        print("2. Update frontend components to use correct terminology")
        print("3. Test all system submission and query endpoints")

    except Exception as e:
        print(f"\nERROR during migration: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    migrate_database()
