"""
Complete the database migration by replacing files.
Run this after closing all applications that might be using the database.
"""

import os
import time
from pathlib import Path

DB_DIR = Path(__file__).parent / 'Haven-UI' / 'data'
OLD_DB = DB_DIR / 'haven_ui.db'
NEW_DB = DB_DIR / 'haven_ui_new.db'
WAL_FILE = DB_DIR / 'haven_ui.db-wal'
SHM_FILE = DB_DIR / 'haven_ui.db-shm'

print("=" * 70)
print("DATABASE MIGRATION - FINAL STEP")
print("=" * 70)
print("\nThis will replace the old database with the new one.")
print("Make sure:")
print("  1. The API server is stopped")
print("  2. No database browsers are open")
print("  3. No other Python scripts are accessing the database")
print("\nPress Ctrl+C to cancel, or press Enter to continue...")
input()

def try_remove(filepath, retries=5):
    """Try to remove a file with retries."""
    for i in range(retries):
        try:
            if filepath.exists():
                filepath.unlink()
                print(f"  Removed {filepath.name}")
                return True
        except PermissionError as e:
            if i < retries - 1:
                print(f"  File locked, waiting... (attempt {i+1}/{retries})")
                time.sleep(1)
            else:
                print(f"  ERROR: Cannot remove {filepath.name} - {e}")
                return False
    return True

print("\n[1/4] Removing WAL files...")
try_remove(WAL_FILE)
try_remove(SHM_FILE)

print("\n[2/4] Removing old database...")
if try_remove(OLD_DB):
    print("\n[3/4] Renaming new database...")
    try:
        NEW_DB.rename(OLD_DB)
        print(f"  Renamed {NEW_DB.name} to {OLD_DB.name}")

        print("\n[4/4] Verifying...")
        import sqlite3
        conn = sqlite3.connect(OLD_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM systems")
        count = cursor.fetchone()[0]
        cursor.execute("PRAGMA table_info(systems)")
        columns = [col[1] for col in cursor.fetchall()]
        conn.close()

        has_galaxy = 'galaxy' in columns
        has_glyph = 'glyph_code' in columns
        has_region_coords = 'region_x' in columns

        print("\n" + "=" * 70)
        print("MIGRATION COMPLETE!")
        print("=" * 70)
        print(f"Systems: {count}")
        print(f"Galaxy column: {'YES' if has_galaxy else 'NO'}")
        print(f"Glyph columns: {'YES' if has_glyph else 'NO'}")
        print(f"Region coordinates: {'YES' if has_region_coords else 'NO'}")
        print(f"\nAll columns: {', '.join(columns)}")

    except Exception as e:
        print(f"\nERROR: {e}")
        print("Manual steps required:")
        print(f"  1. Delete: {OLD_DB}")
        print(f"  2. Rename: {NEW_DB} to {OLD_DB.name}")
else:
    print("\nERROR: Could not remove old database.")
    print("Please close all applications using the database and try again.")
