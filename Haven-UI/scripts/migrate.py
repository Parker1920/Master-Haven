#!/usr/bin/env python3
"""
Schema Migration CLI Tool for Master-Haven

Usage:
    python scripts/migrate.py status     # Show current version and pending migrations
    python scripts/migrate.py run        # Run all pending migrations
    python scripts/migrate.py history    # Show migration history
    python scripts/migrate.py backup     # Create a manual backup
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add Haven-UI and backend to path
haven_ui_dir = Path(__file__).resolve().parents[1]
backend_dir = haven_ui_dir / 'backend'
sys.path.insert(0, str(haven_ui_dir))
sys.path.insert(0, str(backend_dir))

from migrations import (
    run_pending_migrations,
    get_current_version,
    get_migrations,
    backup_database,
    create_migrations_table,
    _version_tuple
)

import sqlite3


def get_db_path() -> Path:
    """Get the database path."""
    # Try to use the paths config
    try:
        from paths import haven_paths
        if haven_paths and haven_paths.haven_db:
            return Path(haven_paths.haven_db)
    except ImportError:
        pass

    # Fallback to standard location
    return haven_ui_dir / 'data' / 'haven_ui.db'


def cmd_status():
    """Show current schema version and pending migrations."""
    db_path = get_db_path()

    print("=" * 60)
    print("Schema Migration Status")
    print("=" * 60)
    print(f"\nDatabase: {db_path}")
    print(f"Exists: {db_path.exists()}")

    if not db_path.exists():
        print("\nNo database found. It will be created on first run.")
        return

    conn = sqlite3.connect(str(db_path), timeout=30.0)

    try:
        current = get_current_version(conn)
        all_migrations = get_migrations()

        print(f"\nCurrent Version: {current or 'Not initialized'}")
        print(f"Total Migrations: {len(all_migrations)}")

        # Find pending migrations
        pending = []
        for m in all_migrations:
            if current is None:
                pending.append(m)
            elif _version_tuple(m.version) > _version_tuple(current):
                pending.append(m)

        print(f"Pending: {len(pending)}")

        if pending:
            print("\nPending Migrations:")
            for m in pending:
                print(f"  {m.version}: {m.name}")
        else:
            print("\nDatabase schema is up to date!")

        # Show _metadata version if it exists
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='_metadata'
        """)
        if cursor.fetchone():
            cursor.execute("SELECT key, value, updated_at FROM _metadata WHERE key = 'version'")
            row = cursor.fetchone()
            if row:
                print(f"\n_metadata version: {row[1]} (updated: {row[2]})")

    finally:
        conn.close()


def cmd_run():
    """Run pending migrations."""
    db_path = get_db_path()

    print("=" * 60)
    print("Running Schema Migrations")
    print("=" * 60)
    print(f"\nDatabase: {db_path}")

    if not db_path.exists():
        print("\nNo database found. Run the server to create it.")
        return

    try:
        count, versions = run_pending_migrations(db_path)

        if count > 0:
            print(f"\nSuccessfully applied {count} migration(s):")
            for v in versions:
                print(f"  - {v}")
        else:
            print("\nNo pending migrations. Schema is up to date!")

    except Exception as e:
        print(f"\nMigration failed: {e}")
        print("Check logs and backups for recovery options.")
        sys.exit(1)


def cmd_history():
    """Show migration history from database."""
    db_path = get_db_path()

    print("=" * 60)
    print("Migration History")
    print("=" * 60)
    print(f"\nDatabase: {db_path}")

    if not db_path.exists():
        print("\nNo database found.")
        return

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        # Check if schema_migrations table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_migrations'
        """)
        if not cursor.fetchone():
            print("\nNo migration history (schema_migrations table not found).")
            print("Run migrations to initialize the versioning system.")
            return

        cursor.execute("""
            SELECT version, migration_name, applied_at, execution_time_ms, success
            FROM schema_migrations
            ORDER BY id ASC
        """)
        rows = cursor.fetchall()

        if not rows:
            print("\nNo migrations have been applied yet.")
            return

        print(f"\nApplied Migrations ({len(rows)}):\n")
        print(f"{'Version':<10} {'Status':<10} {'Time (ms)':<10} {'Applied At':<25} Name")
        print("-" * 80)

        for row in rows:
            status = "OK" if row['success'] else "FAILED"
            time_ms = row['execution_time_ms'] or 0
            applied = row['applied_at'][:19] if row['applied_at'] else 'N/A'
            print(f"{row['version']:<10} {status:<10} {time_ms:<10} {applied:<25} {row['migration_name']}")

    finally:
        conn.close()


def cmd_backup():
    """Create a manual backup."""
    db_path = get_db_path()

    print("=" * 60)
    print("Creating Database Backup")
    print("=" * 60)
    print(f"\nDatabase: {db_path}")

    if not db_path.exists():
        print("\nNo database found to backup.")
        return

    backup_path = backup_database(db_path)
    print(f"\nBackup created: {backup_path}")
    print(f"Size: {backup_path.stat().st_size:,} bytes")


def main():
    parser = argparse.ArgumentParser(
        description='Schema Migration Tool for Master-Haven',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/migrate.py status   # Check current schema version
    python scripts/migrate.py run      # Apply pending migrations
    python scripts/migrate.py history  # View applied migrations
    python scripts/migrate.py backup   # Create a backup
        """
    )
    parser.add_argument(
        'command',
        choices=['status', 'run', 'history', 'backup'],
        help='Command to execute'
    )
    args = parser.parse_args()

    commands = {
        'status': cmd_status,
        'run': cmd_run,
        'history': cmd_history,
        'backup': cmd_backup
    }

    commands[args.command]()


if __name__ == '__main__':
    main()
