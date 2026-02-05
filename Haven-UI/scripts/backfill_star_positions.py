"""
Backfill Star Positions for Existing Systems

This script calculates and updates star_x, star_y, star_z for all systems
that have a glyph_code but no star position yet.

The star position is deterministically calculated from:
- Region coordinates (from glyph YY-ZZZ-XXX)
- Solar System Index (from glyph SSS)

This ensures:
1. Each system gets a unique position within its region
2. The position is consistent (same glyph always produces same position)
3. Systems in the same region don't overlap on the 3D map
"""

import sqlite3
import sys
from pathlib import Path

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_dir))

from glyph_decoder import decode_glyph_to_coords

# Database paths
DB_PATHS = [
    Path(r"C:\Master-Haven\Haven-UI\data\haven_ui.db"),
    Path(r"c:\Master-Haven\Haven-UI\data\haven_ui.db"),
]

def find_database():
    """Find the database file."""
    for db_path in DB_PATHS:
        if db_path.exists():
            return db_path
    return None

def backfill_star_positions(db_path: Path, dry_run: bool = False) -> dict:
    """
    Calculate and update star positions for all systems.

    Args:
        db_path: Path to the database
        dry_run: If True, don't actually update the database

    Returns:
        Dictionary with statistics
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    stats = {
        'total': 0,
        'updated': 0,
        'skipped_no_glyph': 0,
        'skipped_has_position': 0,
        'errors': 0,
    }

    try:
        # Get all systems
        cursor.execute("""
            SELECT id, name, glyph_code, star_x, star_y, star_z,
                   region_x, region_y, region_z, glyph_solar_system
            FROM systems
        """)
        systems = cursor.fetchall()

        stats['total'] = len(systems)
        print(f"\nProcessing {stats['total']} systems...")

        for system in systems:
            system_id = system['id']
            name = system['name'] or f"System {system_id}"
            glyph_code = system['glyph_code']

            # Skip if no glyph code
            if not glyph_code:
                stats['skipped_no_glyph'] += 1
                continue

            # Skip if already has star position (optional - uncomment to force recalculate)
            # if system['star_x'] is not None:
            #     stats['skipped_has_position'] += 1
            #     continue

            try:
                # Decode glyph to get star position
                decoded = decode_glyph_to_coords(glyph_code)

                star_x = decoded['star_x']
                star_y = decoded['star_y']
                star_z = decoded['star_z']

                if dry_run:
                    print(f"  [DRY RUN] Would update '{name}': star=({star_x:.2f}, {star_y:.2f}, {star_z:.2f})")
                else:
                    # Update the system with calculated star position
                    cursor.execute("""
                        UPDATE systems
                        SET star_x = ?, star_y = ?, star_z = ?
                        WHERE id = ?
                    """, (star_x, star_y, star_z, system_id))

                    print(f"  [OK] Updated '{name}': star=({star_x:.2f}, {star_y:.2f}, {star_z:.2f})")

                stats['updated'] += 1

            except Exception as e:
                print(f"  [ERROR] Failed to process '{name}' (glyph: {glyph_code}): {e}")
                stats['errors'] += 1

        if not dry_run:
            conn.commit()

        return stats

    except Exception as e:
        print(f"\n[ERROR] Backfill failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def verify_star_positions(db_path: Path):
    """Verify that star positions were calculated correctly."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Check systems with star positions
        cursor.execute("""
            SELECT COUNT(*) as count FROM systems
            WHERE star_x IS NOT NULL AND star_y IS NOT NULL AND star_z IS NOT NULL
        """)
        with_position = cursor.fetchone()['count']

        cursor.execute("""
            SELECT COUNT(*) as count FROM systems
            WHERE glyph_code IS NOT NULL
        """)
        with_glyph = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM systems")
        total = cursor.fetchone()['count']

        print(f"\n=== Verification ===")
        print(f"  Total systems: {total}")
        print(f"  Systems with glyph code: {with_glyph}")
        print(f"  Systems with star position: {with_position}")

        if with_glyph > 0:
            coverage = (with_position / with_glyph) * 100
            print(f"  Coverage: {coverage:.1f}%")

        # Show a few examples
        cursor.execute("""
            SELECT name, glyph_code, x, y, z, star_x, star_y, star_z
            FROM systems
            WHERE star_x IS NOT NULL
            LIMIT 5
        """)
        examples = cursor.fetchall()

        if examples:
            print(f"\n=== Sample Systems ===")
            for sys in examples:
                print(f"  {sys['name']}:")
                print(f"    Glyph: {sys['glyph_code']}")
                print(f"    Region: ({sys['x']}, {sys['y']}, {sys['z']})")
                print(f"    Star:   ({sys['star_x']:.2f}, {sys['star_y']:.2f}, {sys['star_z']:.2f})")

    finally:
        conn.close()

def main():
    print("=" * 60)
    print("Master-Haven: Backfill Star Positions")
    print("=" * 60)

    # Find database
    db_path = find_database()
    if not db_path:
        print("\n[ERROR] Database not found!")
        sys.exit(1)

    print(f"\nDatabase: {db_path}")

    # Check for dry run argument
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("\n[DRY RUN MODE] No changes will be made to the database.")

    print("\nThis script will:")
    print("  1. Find all systems with glyph codes")
    print("  2. Calculate star_x, star_y, star_z from glyph + region + SSS")
    print("  3. Update the database with calculated positions")

    if not dry_run:
        response = input("\nContinue? (y/n): ").strip().lower()
        if response != 'y':
            print("Backfill cancelled.")
            sys.exit(0)

    # Run backfill
    print("\n=== Running Backfill ===")
    stats = backfill_star_positions(db_path, dry_run=dry_run)

    # Print stats
    print(f"\n=== Statistics ===")
    print(f"  Total systems: {stats['total']}")
    print(f"  Updated: {stats['updated']}")
    print(f"  Skipped (no glyph): {stats['skipped_no_glyph']}")
    print(f"  Skipped (has position): {stats['skipped_has_position']}")
    print(f"  Errors: {stats['errors']}")

    # Verify
    if not dry_run:
        verify_star_positions(db_path)

    print("\n" + "=" * 60)
    print("Backfill Complete!" if not dry_run else "Dry Run Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
