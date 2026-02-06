"""
Database Cleanup Script - Delete Systems in Galactic Core Void

This script finds and deletes all star systems that exist within the galactic core void
(ellipsoidal zone: 450 units X/Z radius, 28 units Y radius). Run this once after
implementing core void validation to clean up existing data.

Usage:
    python delete_core_void_systems.py
"""

import sqlite3
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from glyph_decoder import is_in_core_void, CORE_VOID_RADIUS_XZ, CORE_VOID_RADIUS_Y

# Database path — resolved relative to this script's location
DB_PATH = str(Path(__file__).parent.parent / 'data' / 'haven_ui.db')


def main():
    print("=" * 60)
    print("Galactic Core Void - Database Cleanup Script")
    print("=" * 60)
    print(f"Core void radius: X/Z={CORE_VOID_RADIUS_XZ}, Y={CORE_VOID_RADIUS_Y} coordinate units (ellipsoid)")
    print(f"Database: {DB_PATH}")
    print()

    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Find systems in core void
        print("Scanning database for systems in galactic core void...")
        cursor.execute(
            "SELECT id, name, x, y, z FROM systems WHERE x IS NOT NULL AND y IS NOT NULL AND z IS NOT NULL"
        )

        violations = []
        for row in cursor.fetchall():
            sys_id, name, x, y, z = row
            if is_in_core_void(x, y, z):
                violations.append((sys_id, name, x, y, z))

        if not violations:
            print("[OK] No systems found in galactic core void - database is clean!")
            conn.close()
            return

        # Display violations
        print(f"\n[WARNING] Found {len(violations)} system(s) in galactic core void:\n")
        for sys_id, name, x, y, z in violations:
            print(f"  • ID {sys_id}: '{name}'")
            print(f"    Coordinates: ({x}, {y}, {z})")
            print()

        # Confirm deletion
        response = input(f"Delete these {len(violations)} system(s)? (yes/no): ").strip().lower()

        if response != 'yes':
            print("\n[CANCELLED] Deletion cancelled. No changes made to database.")
            conn.close()
            return

        # Delete systems
        print("\nDeleting systems...")
        violation_ids = [v[0] for v in violations]

        # Note: CASCADE DELETE should handle related planets, discoveries, etc.
        placeholders = ','.join('?' * len(violation_ids))
        cursor.execute(f"DELETE FROM systems WHERE id IN ({placeholders})", violation_ids)

        deleted_count = cursor.rowcount
        conn.commit()

        print(f"\n[SUCCESS] Deleted {deleted_count} system(s) from galactic core void")
        print("\nDatabase cleanup complete!")

        # Verify
        cursor.execute(
            "SELECT COUNT(*) FROM systems WHERE x IS NOT NULL AND y IS NOT NULL AND z IS NOT NULL"
        )
        remaining_systems = cursor.fetchone()[0]
        print(f"Remaining systems in database: {remaining_systems}")

        conn.close()

    except sqlite3.Error as e:
        print(f"\n[ERROR] Database error: {e}")
        return
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return


if __name__ == '__main__':
    main()
