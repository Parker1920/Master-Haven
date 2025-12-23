"""
Database Migration Script: Add Glyph System Support

This script migrates the Master-Haven database to support the NMS portal glyph coordinate system.

Changes:
1. Add glyph-related columns to systems table
2. Rename 'region' to 'galaxy' (terminology fix)
3. Add proper NMS region coordinates
4. Add spatial indexing for performance
5. Clear test data
"""

import sqlite3
import os
import sys

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'Haven-UI', 'data', 'haven_ui.db')

def backup_database():
    """Create a backup of the database before migration."""
    backup_path = DB_PATH + '.backup'
    if os.path.exists(DB_PATH):
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"[OK] Database backed up to: {backup_path}")
        return True
    return False

def migrate_database():
    """Execute database migration."""
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return False

    backup_database()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("\n=== Starting Database Migration ===\n")

        # Step 1: Get current schema
        print("Step 1: Checking current schema...")
        cursor.execute("PRAGMA table_info(systems)")
        current_columns = {row[1]: row[2] for row in cursor.fetchall()}
        print(f"  Current columns: {list(current_columns.keys())}")

        # Step 2: Rename 'region' column to 'galaxy' if it exists
        if 'region' in current_columns and 'galaxy' not in current_columns:
            print("\nStep 2: Renaming 'region' column to 'galaxy'...")
            # SQLite doesn't support column rename directly, need to recreate table
            cursor.execute("""
                CREATE TABLE systems_new (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    x REAL NOT NULL,
                    y REAL NOT NULL,
                    z REAL NOT NULL,
                    galaxy TEXT DEFAULT 'Euclid',
                    description TEXT,
                    economy TEXT,
                    conflict TEXT,
                    discovered_by TEXT,
                    discovered_at TIMESTAMP,
                    submitter_id TEXT,
                    approved INTEGER DEFAULT 1
                )
            """)

            # Copy data with column rename
            cursor.execute("""
                INSERT INTO systems_new (id, name, x, y, z, galaxy, description, economy, conflict, discovered_by, discovered_at, submitter_id, approved)
                SELECT id, name, x, y, z, region, description, economy, conflict, discovered_by, discovered_at, submitter_id, approved
                FROM systems
            """)

            cursor.execute("DROP TABLE systems")
            cursor.execute("ALTER TABLE systems_new RENAME TO systems")
            print("  [OK] 'region' renamed to 'galaxy'")
        else:
            print("\nStep 2: Skipped (no 'region' column or 'galaxy' already exists)")

        # Step 3: Add glyph columns if they don't exist
        print("\nStep 3: Adding glyph columns...")
        columns_to_add = {
            'glyph_code': 'TEXT UNIQUE',
            'glyph_planet': 'INTEGER DEFAULT 0',
            'glyph_solar_system': 'INTEGER DEFAULT 1',
            'region_x': 'INTEGER',
            'region_y': 'INTEGER',
            'region_z': 'INTEGER'
        }

        cursor.execute("PRAGMA table_info(systems)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE systems ADD COLUMN {col_name} {col_type}")
                print(f"  [OK] Added column: {col_name}")
            else:
                print(f"  - Column already exists: {col_name}")

        # Step 4: Add spatial indexing
        print("\nStep 4: Adding spatial indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_coords ON systems(x, y, z)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_glyph ON systems(glyph_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_galaxy ON systems(galaxy)")
        print("  [OK] Spatial indexes created")

        # Step 5: Clear test data
        print("\nStep 5: Clearing old test data...")
        cursor.execute("SELECT COUNT(*) FROM systems")
        old_systems_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM planets")
        old_planets_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM discoveries")
        old_discoveries_count = cursor.fetchone()[0]

        if old_systems_count > 0 or old_planets_count > 0 or old_discoveries_count > 0:
            response = input(f"\n  Found {old_systems_count} systems, {old_planets_count} planets, {old_discoveries_count} discoveries.\n  Clear all test data? (yes/no): ")
            if response.lower() == 'yes':
                cursor.execute("DELETE FROM discoveries")
                cursor.execute("DELETE FROM space_stations")
                cursor.execute("DELETE FROM moons")
                cursor.execute("DELETE FROM planets")
                cursor.execute("DELETE FROM systems")
                print(f"  [OK] Cleared {old_systems_count} systems, {old_planets_count} planets, {old_discoveries_count} discoveries")
            else:
                print("  - Skipped clearing test data")
        else:
            print("  - No test data to clear")

        # Step 6: Update pending_systems table if it exists
        print("\nStep 6: Updating pending_systems table...")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pending_systems'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(pending_systems)")
            pending_columns = [row[1] for row in cursor.fetchall()]

            for col_name, col_type in columns_to_add.items():
                if col_name not in pending_columns:
                    cursor.execute(f"ALTER TABLE pending_systems ADD COLUMN {col_name} {col_type}")
                    print(f"  [OK] Added column to pending_systems: {col_name}")
        else:
            print("  - pending_systems table not found, skipping")

        conn.commit()
        print("\n[OK] Migration completed successfully!")

        # Show final schema
        print("\n=== Final Schema ===")
        cursor.execute("PRAGMA table_info(systems)")
        for row in cursor.fetchall():
            print(f"  {row[1]}: {row[2]}")

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        print(f"  Database backup available at: {DB_PATH}.backup")
        return False

    finally:
        conn.close()

if __name__ == '__main__':
    print("="*60)
    print("Master-Haven Glyph System Migration")
    print("="*60)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Exists: {os.path.exists(DB_PATH)}\n")

    if migrate_database():
        print("\n" + "="*60)
        print("Migration completed! You can now:")
        print("1. Run the test data generator")
        print("2. Start using the glyph coordinate system")
        print("="*60)
        sys.exit(0)
    else:
        sys.exit(1)
