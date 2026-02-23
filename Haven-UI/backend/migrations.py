"""
Schema Migration System for Master-Haven

Migrations are Python functions registered with version numbers.
They are executed in order on startup if not already applied.

Usage:
    from migrations import run_pending_migrations

    # In init_database():
    run_pending_migrations(db_path)

Version Scheme: MAJOR.MINOR.PATCH
    - MAJOR: Breaking changes requiring data transformation
    - MINOR: New tables, columns, or indexes (backward compatible)
    - PATCH: Small fixes, default changes
"""

import sqlite3
import logging
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger('master_haven.migrations')


@dataclass
class Migration:
    """Represents a single schema migration."""
    version: str
    name: str
    up: Callable[[sqlite3.Connection], None]
    down: Optional[Callable[[sqlite3.Connection], None]] = None


# Global migration registry
_migrations: List[Migration] = []


def register_migration(version: str, name: str, down: Optional[Callable] = None):
    """
    Decorator to register a migration function.

    Args:
        version: Semantic version string (e.g., "1.0.0", "1.1.0")
        name: Human-readable migration name
        down: Optional rollback function

    Example:
        @register_migration("1.2.0", "Add new_column to systems")
        def migration_1_2_0(conn: sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute("ALTER TABLE systems ADD COLUMN new_column TEXT")
    """
    def decorator(up_func: Callable[[sqlite3.Connection], None]):
        _migrations.append(Migration(
            version=version,
            name=name,
            up=up_func,
            down=down
        ))
        # Keep migrations sorted by version
        _migrations.sort(key=lambda m: _version_tuple(m.version))
        return up_func
    return decorator


def _version_tuple(version: str) -> Tuple[int, ...]:
    """Convert version string to tuple for comparison."""
    return tuple(int(x) for x in version.split('.'))


def get_migrations() -> List[Migration]:
    """Return all registered migrations in version order."""
    return _migrations.copy()


def get_current_version(conn: sqlite3.Connection) -> Optional[str]:
    """Get the current schema version from the database."""
    cursor = conn.cursor()

    # Check if schema_migrations table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='schema_migrations'
    """)
    if not cursor.fetchone():
        return None

    # Get highest successfully applied version
    cursor.execute("""
        SELECT version FROM schema_migrations
        WHERE success = 1
        ORDER BY id DESC LIMIT 1
    """)
    row = cursor.fetchone()
    return row[0] if row else None


def create_migrations_table(conn: sqlite3.Connection):
    """Create the schema_migrations tracking table."""
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            migration_name TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            execution_time_ms INTEGER,
            success INTEGER DEFAULT 1
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_schema_migrations_version
        ON schema_migrations(version)
    ''')
    conn.commit()


def backup_database(db_path: Path) -> Path:
    """
    Create a timestamped backup before migration.

    Args:
        db_path: Path to the database file

    Returns:
        Path to the backup file
    """
    backup_dir = db_path.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f'pre_migration_{timestamp}.db'

    shutil.copy2(db_path, backup_path)
    logger.info(f"Created pre-migration backup: {backup_path}")
    return backup_path


def run_pending_migrations(db_path: Path) -> Tuple[int, List[str]]:
    """
    Run all pending migrations in order.

    Args:
        db_path: Path to the database file

    Returns:
        Tuple of (count of applied migrations, list of version strings)
    """
    if isinstance(db_path, str):
        db_path = Path(db_path)

    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')

    try:
        # Ensure migrations table exists
        create_migrations_table(conn)

        current_version = get_current_version(conn)
        migrations = get_migrations()

        # Filter to pending migrations
        pending = []
        for m in migrations:
            if current_version is None:
                pending.append(m)
            else:
                # Compare versions numerically
                current_parts = _version_tuple(current_version)
                migration_parts = _version_tuple(m.version)
                if migration_parts > current_parts:
                    pending.append(m)

        if not pending:
            logger.info("Database schema is up to date")
            return 0, []

        # Create backup before any migrations
        if db_path.exists():
            backup_path = backup_database(db_path)

        logger.info(f"Running {len(pending)} pending migration(s)")

        applied = []
        for migration in pending:
            start_time = datetime.now()
            logger.info(f"Applying migration {migration.version}: {migration.name}")

            try:
                # Execute the migration
                migration.up(conn)
                conn.commit()

                # Record success (use INSERT OR REPLACE to handle retry scenarios)
                elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO schema_migrations
                    (version, migration_name, applied_at, execution_time_ms, success)
                    VALUES (?, ?, ?, ?, 1)
                ''', (migration.version, migration.name,
                      datetime.now().isoformat(), elapsed_ms))
                conn.commit()

                applied.append(migration.version)
                logger.info(f"Migration {migration.version} completed in {elapsed_ms}ms")

            except Exception as e:
                conn.rollback()
                logger.error(f"Migration {migration.version} failed: {e}")

                # Record failure
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO schema_migrations
                    (version, migration_name, applied_at, success)
                    VALUES (?, ?, ?, 0)
                ''', (migration.version, migration.name, datetime.now().isoformat()))
                conn.commit()

                if db_path.exists():
                    logger.error(f"Backup available at: {backup_path}")
                raise RuntimeError(f"Migration {migration.version} failed: {e}")

        return len(applied), applied

    finally:
        conn.close()


# =============================================================================
# MIGRATIONS
# =============================================================================
#
# Historical migrations are registered here. Since the schema changes were
# already applied before the versioning system existed, these migrations
# are no-ops that document what changed at each version.
#
# Future migrations should include actual schema modification code.
# =============================================================================

@register_migration("1.0.0", "Initial schema - 8 tables, basic systems")
def migration_1_0_0_baseline(conn: sqlite3.Connection):
    """
    Nov 16, 2025 - Initial database schema.

    Tables: _metadata, discoveries, moons, pending_systems, planets,
            space_stations, sqlite_sequence, systems
    Systems table: 15 columns (id, name, x, y, z, region, fauna, flora,
                   sentinel, materials, base_location, photo, attributes,
                   created_at, modified_at)
    """
    logger.info("Marking v1.0.0 baseline - initial schema")


@register_migration("1.1.0", "Glyph system - portal coordinates")
def migration_1_1_0_glyph(conn: sqlite3.Connection):
    """
    Nov 19, 2025 - Glyph System Implementation.

    Added to systems table:
    - glyph_code, glyph_planet, glyph_solar_system
    - region_x, region_y, region_z
    - Renamed 'region' to 'galaxy'
    - description, economy, conflict
    - discovered_by, discovered_at, submitter_id, approved

    Systems table: 15 -> 28 columns
    """
    logger.info("Marking v1.1.0 - glyph system implementation")


@register_migration("1.2.0", "System approvals workflow")
def migration_1_2_0_approvals(conn: sqlite3.Connection):
    """
    Nov 19, 2025 - System Approvals Implementation.

    Enhanced pending_systems table for approval workflow.
    """
    logger.info("Marking v1.2.0 - system approvals workflow")


@register_migration("1.3.0", "Schema fix - planets table, UUID IDs")
def migration_1_3_0_schema_fix(conn: sqlite3.Connection):
    """
    Nov 25, 2025 - Critical Schema Fix.

    - Fixed planets table columns for approval workflow
    - Changed system IDs to UUIDs
    - Fixed approve_system() INSERT statements
    """
    logger.info("Marking v1.3.0 - schema fix")


@register_migration("1.4.0", "Regions table - custom region names")
def migration_1_4_0_regions(conn: sqlite3.Connection):
    """
    Nov 25, 2025 - Regions System.

    Added tables:
    - regions (custom region names)
    - pending_region_names (region name approval queue)
    """
    logger.info("Marking v1.4.0 - regions table")


@register_migration("1.5.0", "Signed hex coordinates")
def migration_1_5_0_signed_hex(conn: sqlite3.Connection):
    """
    Nov 27, 2025 - Signed Hex Implementation.

    Coordinate system updates for proper NMS coordinate handling.
    """
    logger.info("Marking v1.5.0 - signed hex coordinates")


@register_migration("1.6.0", "API keys table")
def migration_1_6_0_api_keys(conn: sqlite3.Connection):
    """
    Dec 2025 - API Key Authentication.

    Added table:
    - api_keys (API authentication with rate limiting)
    """
    logger.info("Marking v1.6.0 - API keys table")


@register_migration("1.7.0", "Activity logs table")
def migration_1_7_0_activity_logs(conn: sqlite3.Connection):
    """
    Dec 2025 - Activity Logging.

    Added table:
    - activity_logs (system event tracking)
    """
    logger.info("Marking v1.7.0 - activity logs table")


@register_migration("1.8.0", "Partner accounts system")
def migration_1_8_0_partner_accounts(conn: sqlite3.Connection):
    """
    Dec 2025 - Partner Login System.

    Added tables:
    - partner_accounts (multi-tenant partner login)
    - pending_edit_requests (partner edit approval workflow)
    """
    logger.info("Marking v1.8.0 - partner accounts system")


@register_migration("1.9.0", "Data restrictions and admin settings")
def migration_1_9_0_data_restrictions(conn: sqlite3.Connection):
    """
    Dec 2025 - Data Visibility Controls.

    Added tables:
    - data_restrictions (partner data visibility controls)
    - super_admin_settings (changeable admin password)
    """
    logger.info("Marking v1.9.0 - data restrictions")


@register_migration("1.10.0", "Sub-admin system")
def migration_1_10_0_sub_admin(conn: sqlite3.Connection):
    """
    Dec 2025 - Sub-Administrator System.

    Added tables:
    - sub_admin_accounts (partner sub-administrators)
    - approval_audit_log (approval/rejection tracking)
    """
    logger.info("Marking v1.10.0 - sub-admin system")


@register_migration("1.11.0", "Planet data tables")
def migration_1_11_0_planet_data(conn: sqlite3.Connection):
    """
    Dec 2025 - Extended Planet Data.

    Added tables:
    - terrain_data (planet terrain information)
    - planet_colors (planet color data)
    """
    logger.info("Marking v1.11.0 - planet data tables")


@register_migration("1.12.0", "Multi-reality and extractor columns")
def migration_1_12_0_multi_reality(conn: sqlite3.Connection):
    """
    Dec 2025 - Multi-Reality Support & Extractor Integration.

    Added to systems table:
    - reality (Permadeath vs Normal tracking)
    - star_x, star_y, star_z, star_type
    - economy_type, economy_level, conflict_level
    - dominant_lifeform
    - discord_tag, personal_discord_username
    - data_source, visit_date, is_complete

    Systems table: 28 -> 42 columns
    """
    logger.info("Marking v1.12.0 - multi-reality and extractor columns")


@register_migration("1.13.0", "Schema versioning system")
def migration_1_13_0_versioning(conn: sqlite3.Connection):
    """
    Jan 5, 2026 - Schema Versioning System.

    Added table:
    - schema_migrations (migration tracking)

    Updates _metadata.version to reflect current schema state.
    """
    cursor = conn.cursor()

    # Update _metadata table version if it exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)

    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.13.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.13.0")


@register_migration("1.14.0", "Haven sub-admins and planet POIs")
def migration_1_14_0_haven_sub_admins(conn: sqlite3.Connection):
    """
    Jan 2026 - Haven Sub-Admins & Planet POIs.

    Changes:
    - Recreate sub_admin_accounts to allow NULL parent_partner_id (for Haven sub-admins)
    - Add planet_pois table for 3D planet POI markers
    """
    cursor = conn.cursor()

    # Check if sub_admin_accounts table has the NOT NULL constraint issue
    cursor.execute("PRAGMA table_info(sub_admin_accounts)")
    columns = cursor.fetchall()

    needs_rebuild = False
    for col in columns:
        # col format: (cid, name, type, notnull, default, pk)
        if col[1] == 'parent_partner_id' and col[3] == 1:  # notnull = 1 means NOT NULL
            needs_rebuild = True
            break

    if needs_rebuild:
        logger.info("Rebuilding sub_admin_accounts to allow NULL parent_partner_id...")

        # Create new table with correct schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sub_admin_accounts_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_partner_id INTEGER,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                enabled_features TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP,
                created_by TEXT,
                FOREIGN KEY (parent_partner_id) REFERENCES partner_accounts(id) ON DELETE CASCADE
            )
        ''')

        # Copy existing data
        cursor.execute('''
            INSERT INTO sub_admin_accounts_new
            SELECT * FROM sub_admin_accounts
        ''')

        # Drop old table and rename new one
        cursor.execute('DROP TABLE sub_admin_accounts')
        cursor.execute('ALTER TABLE sub_admin_accounts_new RENAME TO sub_admin_accounts')

        # Recreate indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sub_admin_parent ON sub_admin_accounts(parent_partner_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sub_admin_username ON sub_admin_accounts(username)')

        logger.info("sub_admin_accounts table rebuilt successfully")
    else:
        logger.info("sub_admin_accounts already allows NULL parent_partner_id")

    # Add planet_pois table if it doesn't exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='planet_pois'
    """)
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE planet_pois (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                planet_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                poi_type TEXT DEFAULT 'custom',
                color TEXT DEFAULT '#00C2B3',
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (planet_id) REFERENCES planets(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_planet_pois_planet_id ON planet_pois(planet_id)')
        logger.info("Created planet_pois table")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.14.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.14.0")


@register_migration("1.15.0", "Haven sub-admin discord tag visibility")
def migration_1_15_0_sub_admin_discord_tags(conn: sqlite3.Connection):
    """
    Jan 2026 - Haven Sub-Admin Discord Tag Visibility.

    Changes:
    - Add additional_discord_tags column to sub_admin_accounts
      (JSON array of discord tags that Haven sub-admins can see/approve beyond "Haven")
    """
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(sub_admin_accounts)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'additional_discord_tags' not in columns:
        cursor.execute('''
            ALTER TABLE sub_admin_accounts
            ADD COLUMN additional_discord_tags TEXT DEFAULT '[]'
        ''')
        logger.info("Added additional_discord_tags column to sub_admin_accounts")
    else:
        logger.info("additional_discord_tags column already exists")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.15.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.15.0")


@register_migration("1.16.0", "Haven sub-admin personal uploads permission")
def migration_1_16_0_personal_uploads(conn: sqlite3.Connection):
    """
    Jan 2026 - Haven Sub-Admin Personal Uploads Permission.

    Changes:
    - Add can_approve_personal_uploads column to sub_admin_accounts
      (allows Haven sub-admins to approve personal uploads without seeing discord info)
    """
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(sub_admin_accounts)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'can_approve_personal_uploads' not in columns:
        cursor.execute('''
            ALTER TABLE sub_admin_accounts
            ADD COLUMN can_approve_personal_uploads INTEGER DEFAULT 0
        ''')
        logger.info("Added can_approve_personal_uploads column to sub_admin_accounts")
    else:
        logger.info("can_approve_personal_uploads column already exists")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.16.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.16.0")


@register_migration("1.17.0", "Submission events tracking system")
def migration_1_17_0_events(conn: sqlite3.Connection):
    """
    Jan 2026 - Submission Events Tracking System.

    Adds:
    - events table for tracking Discord submission events/competitions
    - Enables time-boxed leaderboards and event-specific analytics
    """
    cursor = conn.cursor()

    # Check if events table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='events'
    """)
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                discord_tag TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                description TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                is_active INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('CREATE INDEX idx_events_discord_tag ON events(discord_tag)')
        cursor.execute('CREATE INDEX idx_events_dates ON events(start_date, end_date)')
        cursor.execute('CREATE INDEX idx_events_active ON events(is_active)')
        logger.info("Created events table with indexes")
    else:
        logger.info("events table already exists")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.17.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.17.0")


@register_migration("1.18.0", "Space station trade goods")
def migration_1_18_0_station_trade_goods(conn: sqlite3.Connection):
    """
    Add trade_goods column to space_stations table.
    This stores a JSON array of trade good IDs that the station sells.
    The sell_percent and buy_percent columns are deprecated but kept for backwards compatibility.
    """
    cursor = conn.cursor()

    # Check if trade_goods column exists
    cursor.execute("PRAGMA table_info(space_stations)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'trade_goods' not in columns:
        cursor.execute('ALTER TABLE space_stations ADD COLUMN trade_goods TEXT DEFAULT "[]"')
        logger.info("Added trade_goods column to space_stations table")
    else:
        logger.info("trade_goods column already exists in space_stations")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.18.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.18.0")


@register_migration("1.19.0", "Backfill anonymous submissions with IP-matched usernames")
def migration_1_19_0_backfill_anonymous_usernames(conn: sqlite3.Connection):
    """
    Jan 2026 - Backfill Anonymous Submission Usernames.

    Identifies anonymous submissions that can be attributed to known users
    based on IP address matching. Updates personal_discord_username field
    for submissions where:
    - submitted_by is NULL, 'Anonymous', or empty
    - personal_discord_username is NULL or empty
    - Same IP has other submissions with a known username
    """
    cursor = conn.cursor()

    # Find IP addresses that have both anonymous and identified submissions
    cursor.execute('''
        SELECT DISTINCT submitted_by_ip
        FROM pending_systems
        WHERE submitted_by_ip IS NOT NULL
          AND submitted_by_ip != ''
          AND (submitted_by IS NULL OR submitted_by = 'Anonymous' OR submitted_by = 'anonymous' OR submitted_by = '')
          AND (personal_discord_username IS NULL OR personal_discord_username = '')
    ''')
    anonymous_ips = [row[0] for row in cursor.fetchall()]

    total_updated = 0
    ip_username_map = {}

    for ip in anonymous_ips:
        # Find if this IP has any identified submissions
        cursor.execute('''
            SELECT personal_discord_username, submitted_by, COUNT(*) as cnt
            FROM pending_systems
            WHERE submitted_by_ip = ?
              AND (
                (personal_discord_username IS NOT NULL AND personal_discord_username != '' AND personal_discord_username NOT IN ('None', 'null'))
                OR (submitted_by IS NOT NULL AND submitted_by != '' AND submitted_by NOT IN ('Anonymous', 'anonymous', 'None', 'null', ''))
              )
            GROUP BY personal_discord_username, submitted_by
            ORDER BY cnt DESC
            LIMIT 1
        ''', (ip,))

        match = cursor.fetchone()
        if match:
            # Prefer personal_discord_username, fallback to submitted_by
            username = match[0] if match[0] and match[0] not in ('None', 'null', '') else match[1]
            if username and username not in ('Anonymous', 'anonymous', 'None', 'null', ''):
                ip_username_map[ip] = username

    # Update anonymous submissions with matched usernames
    for ip, username in ip_username_map.items():
        cursor.execute('''
            UPDATE pending_systems
            SET personal_discord_username = ?
            WHERE submitted_by_ip = ?
              AND (submitted_by IS NULL OR submitted_by = 'Anonymous' OR submitted_by = 'anonymous' OR submitted_by = '')
              AND (personal_discord_username IS NULL OR personal_discord_username = '' OR personal_discord_username = 'None')
        ''', (username, ip))

        updated = cursor.rowcount
        if updated > 0:
            total_updated += updated
            logger.info(f"Updated {updated} anonymous submissions from IP {ip[:20]}... to username '{username}'")

    logger.info(f"Backfill complete: Updated {total_updated} anonymous submissions with IP-matched usernames")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.19.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.19.0")


@register_migration("1.20.0", "Haven Extractor API integration - personal_id field and API key")
def migration_1_20_0_haven_extractor_integration(conn: sqlite3.Connection):
    """
    Jan 2026 - Haven Extractor API Integration.

    Adds personal_id field for Discord snowflake ID tracking and creates
    the Haven Extractor API key for direct mod-to-API communication.

    Changes:
    - Add personal_id column to pending_systems (Discord snowflake ID)
    - Add personal_id column to systems (for approved systems)
    - Create 'Haven Extractor' API key with submit + check_duplicate permissions
    """
    import hashlib

    cursor = conn.cursor()

    # Add personal_id to pending_systems (Discord snowflake ID - 18 digit string)
    cursor.execute("PRAGMA table_info(pending_systems)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'personal_id' not in columns:
        cursor.execute("ALTER TABLE pending_systems ADD COLUMN personal_id TEXT")
        logger.info("Added personal_id column to pending_systems")

    # Add personal_id to systems table (for approved systems)
    cursor.execute("PRAGMA table_info(systems)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'personal_id' not in columns:
        cursor.execute("ALTER TABLE systems ADD COLUMN personal_id TEXT")
        logger.info("Added personal_id column to systems")

    # Create Haven Extractor API key
    api_key = "vh_live_HvnXtr8k9Lm2NpQ4rStUvWxYz1A3bC5dE7fG"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    key_prefix = api_key[:24]  # "vh_live_HvnXtr8k9Lm2NpQ4"

    # Check if key already exists (by name or hash)
    cursor.execute("SELECT id FROM api_keys WHERE name = 'Haven Extractor' OR key_hash = ?", (key_hash,))
    existing_key = cursor.fetchone()

    if not existing_key:
        cursor.execute('''
            INSERT INTO api_keys (key_hash, key_prefix, name, created_at, permissions, rate_limit, is_active, created_by, discord_tag)
            VALUES (?, ?, ?, ?, ?, ?, 1, 'system', NULL)
        ''', (key_hash, key_prefix, 'Haven Extractor', datetime.now().isoformat(), '["submit", "check_duplicate"]', 1000))
        logger.info("Created 'Haven Extractor' API key with rate_limit=1000")
    else:
        logger.info("Haven Extractor API key already exists, skipping creation")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.20.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.20.0")


@register_migration("1.21.0", "Haven Extractor - pending_systems schema fix")
def migration_1_21_0_pending_systems_schema(conn: sqlite3.Connection):
    """
    Jan 19, 2026 - Fix pending_systems table schema for Haven Extractor.

    The API code expects many columns that were never added to the table.
    This migration adds all missing columns required for the extraction API.

    Changes:
    - Add glyph_code column (required for duplicate checking)
    - Add galaxy column
    - Add coordinate columns (x, y, z, region_x, region_y, region_z)
    - Add submitter_name, submission_timestamp columns
    - Add source column (tracks where submission came from)
    - Add raw_json column (original JSON payload)
    - Add discord_tag, personal_discord_username columns
    - Add api_key_name column (for API key tracking)
    """
    cursor = conn.cursor()

    # Get current columns in pending_systems
    cursor.execute("PRAGMA table_info(pending_systems)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    # Define all columns that should exist with their SQL types
    required_columns = {
        'glyph_code': 'TEXT',
        'galaxy': 'TEXT',
        'x': 'INTEGER',
        'y': 'INTEGER',
        'z': 'INTEGER',
        'region_x': 'INTEGER',
        'region_y': 'INTEGER',
        'region_z': 'INTEGER',
        'submitter_name': 'TEXT',
        'submission_timestamp': 'TEXT',
        'source': 'TEXT',
        'raw_json': 'TEXT',
        'discord_tag': 'TEXT',
        'personal_discord_username': 'TEXT',
        'api_key_name': 'TEXT',
    }

    # Add missing columns
    for column, col_type in required_columns.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE pending_systems ADD COLUMN {column} {col_type}")
            logger.info(f"Added {column} column to pending_systems")

    # Create index on glyph_code for faster duplicate checking
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_systems_glyph_code
        ON pending_systems(glyph_code)
    """)
    logger.info("Created index on pending_systems.glyph_code")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.21.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.21.0")


@register_migration("1.22.0", "Clean up weather and biome_subtype display values")
def migration_1_22_0_clean_weather_biome_subtype(conn: sqlite3.Connection):
    """
    Jan 19, 2026 - Clean Up Weather and Biome Subtype Display Values.

    Updates existing planet/moon records with cleaner display values:
    - Climate/Weather: Maps raw values like "Weather Lush" to proper adjectives like "Pleasant"
    - Biome Subtype: Maps raw enum names like "HugePlant" to user-friendly names like "Mega Flora"

    This matches the new formatting in Haven Extractor v10.1.4.

    Note: Only updates columns that exist in each table.
    """
    cursor = conn.cursor()

    # Helper to get columns in a table
    def get_table_columns(table: str) -> set:
        cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}

    # Weather value mappings (raw -> EXACT weatherAdjectives from adjectives.js)
    # Values like "Superheated", "Dusty", "Toxic", "Volatile" are NOT in weatherAdjectives
    weather_mappings = {
        # Lush planet weather -> Pleasant
        "Weather Lush": "Pleasant",
        "weather_lush": "Pleasant",
        "weather lush": "Pleasant",
        "Lush": "Pleasant",
        # Toxic planet weather -> Toxic Rain (not just "Toxic")
        "Weather Toxic": "Toxic Rain",
        "weather_toxic": "Toxic Rain",
        "Toxic": "Toxic Rain",
        # Scorched/Hot planet weather -> Extreme Heat
        "Weather Scorched": "Extreme Heat",
        "weather_scorched": "Extreme Heat",
        "Scorched": "Extreme Heat",
        "Weather Hot": "Extreme Heat",
        "weather_hot": "Extreme Heat",
        "Superheated": "Extreme Heat",
        # Fire -> Inferno
        "Weather Fire": "Inferno",
        "weather_fire": "Inferno",
        # Radioactive -> Radioactive (exists in list)
        "Weather Radioactive": "Radioactive",
        "weather_radioactive": "Radioactive",
        # Frozen/Cold -> Frozen or Freezing
        "Weather Frozen": "Frozen",
        "weather_frozen": "Frozen",
        "Weather Cold": "Freezing",
        "weather_cold": "Freezing",
        "Weather Snow": "Frozen",
        "weather_snow": "Frozen",
        "Weather Blizzard": "Freezing",
        "weather_blizzard": "Freezing",
        # Barren/Dust -> Arid (not "Dusty")
        "Weather Barren": "Arid",
        "weather_barren": "Arid",
        "Weather Dust": "Arid",
        "weather_dust": "Arid",
        "Dusty": "Arid",
        # Dead -> Airless
        "Weather Dead": "Airless",
        "weather_dead": "Airless",
        # Weird/Exotic -> Anomalous
        "Weather Weird": "Anomalous",
        "weather_weird": "Anomalous",
        "Weather Glitch": "Anomalous",
        "weather_glitch": "Anomalous",
        "Weather Bubble": "Anomalous",
        "weather_bubble": "Anomalous",
        # Swamp/Humid -> Humid
        "Weather Swamp": "Humid",
        "weather_swamp": "Humid",
        "Weather Humid": "Humid",
        "weather_humid": "Humid",
        # Lava -> Inferno
        "Weather Lava": "Inferno",
        "weather_lava": "Inferno",
        # Clear/Normal
        "Weather Clear": "Clear",
        "weather_clear": "Clear",
        "Weather Normal": "Temperate",
        "weather_normal": "Temperate",
        # Extreme
        "Weather Extreme": "Extreme Heat",
        "weather_extreme": "Extreme Heat",
        # Invalid values we created earlier - fix them
        "Volatile": "Temperate",
        # Color-based weather (exotic planets)
        "RedWeather": "Anomalous",
        "GreenWeather": "Anomalous",
        "BlueWeather": "Anomalous",
    }

    # Biome subtype mappings (raw enum name -> display)
    biome_subtype_mappings = {
        # None/Standard variants
        "None_": "Standard",
        "None": "Standard",
        "HighQuality": "High Quality",
        # Exotic planet subtypes
        "Structure": "Exotic",
        "Beam": "Exotic",
        "Hexagon": "Exotic",
        "FractCube": "Exotic",
        "Bubble": "Exotic",
        "Shards": "Exotic",
        "Contour": "Exotic",
        "Shell": "Exotic",
        "BoneSpire": "Exotic",
        "WireCell": "Exotic",
        "HydroGarden": "Exotic",
        # Mega/Huge variants
        "HugePlant": "Mega Flora",
        "HugeLush": "Mega Flora",
        "HugeRing": "Mega Fauna",
        "HugeRock": "Mega Terrain",
        "HugeScorch": "Mega Terrain",
        "HugeToxic": "Mega Toxic",
        # Variants with underscores
        "Variant_A": "Variant A",
        "Variant_B": "Variant B",
        "Variant_C": "Variant C",
        "Variant_D": "Variant D",
        "Remix_A": "Remix A",
        "Remix_B": "Remix B",
        "Remix_C": "Remix C",
        "Remix_D": "Remix D",
    }

    # Get columns for each table
    planets_columns = get_table_columns('planets')
    moons_columns = get_table_columns('moons')

    logger.info(f"Planets columns: {planets_columns}")
    logger.info(f"Moons columns: {moons_columns}")

    # Update planets table - climate (always exists)
    planets_climate_updated = 0
    if 'climate' in planets_columns:
        for old_val, new_val in weather_mappings.items():
            cursor.execute("UPDATE planets SET climate = ? WHERE climate = ?", (new_val, old_val))
            planets_climate_updated += cursor.rowcount
        logger.info(f"Updated {planets_climate_updated} climate values in planets table")

    # Update planets table - weather (may not exist)
    planets_weather_updated = 0
    if 'weather' in planets_columns:
        for old_val, new_val in weather_mappings.items():
            cursor.execute("UPDATE planets SET weather = ? WHERE weather = ?", (new_val, old_val))
            planets_weather_updated += cursor.rowcount
        logger.info(f"Updated {planets_weather_updated} weather values in planets table")
    else:
        logger.info("planets.weather column does not exist, skipping")

    # Update planets table - biome_subtype (may not exist)
    planets_subtype_updated = 0
    if 'biome_subtype' in planets_columns:
        for old_val, new_val in biome_subtype_mappings.items():
            cursor.execute("UPDATE planets SET biome_subtype = ? WHERE biome_subtype = ?", (new_val, old_val))
            planets_subtype_updated += cursor.rowcount
        logger.info(f"Updated {planets_subtype_updated} biome_subtype values in planets table")
    else:
        logger.info("planets.biome_subtype column does not exist, skipping")

    # Update moons table - climate (always exists)
    moons_climate_updated = 0
    if 'climate' in moons_columns:
        for old_val, new_val in weather_mappings.items():
            cursor.execute("UPDATE moons SET climate = ? WHERE climate = ?", (new_val, old_val))
            moons_climate_updated += cursor.rowcount
        logger.info(f"Updated {moons_climate_updated} climate values in moons table")

    # Update moons table - weather (may not exist)
    moons_weather_updated = 0
    if 'weather' in moons_columns:
        for old_val, new_val in weather_mappings.items():
            cursor.execute("UPDATE moons SET weather = ? WHERE weather = ?", (new_val, old_val))
            moons_weather_updated += cursor.rowcount
        logger.info(f"Updated {moons_weather_updated} weather values in moons table")
    else:
        logger.info("moons.weather column does not exist, skipping")

    # Update moons table - biome_subtype (may not exist)
    moons_subtype_updated = 0
    if 'biome_subtype' in moons_columns:
        for old_val, new_val in biome_subtype_mappings.items():
            cursor.execute("UPDATE moons SET biome_subtype = ? WHERE biome_subtype = ?", (new_val, old_val))
            moons_subtype_updated += cursor.rowcount
        logger.info(f"Updated {moons_subtype_updated} biome_subtype values in moons table")
    else:
        logger.info("moons.biome_subtype column does not exist, skipping")

    total_updated = (planets_climate_updated + planets_weather_updated + planets_subtype_updated +
                     moons_climate_updated + moons_weather_updated + moons_subtype_updated)
    logger.info(f"Total display value updates: {total_updated}")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.22.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.22.0")


@register_migration("1.23.0", "Hierarchy indexes for containerized queries")
def migration_1_23_0_hierarchy_indexes(conn: sqlite3.Connection):
    """
    Jan 2026 - Database Optimization for Containerized Systems Page.

    Part 2 of the Systems Page overhaul. Adds indexes to support the new
    hierarchical lazy-loading pattern (Reality → Galaxy → Region → System).

    Indexes added:
    - idx_systems_hierarchy: Compound index for containerized queries
    - idx_systems_reality_galaxy: For galaxy summary queries
    - idx_pending_ip_date: For submission rate limiting
    - idx_systems_discord_created: For partner filtering with date ordering

    These indexes dramatically improve query performance for:
    - /api/realities/summary
    - /api/galaxies/summary
    - /api/regions/grouped
    - /api/systems (with hierarchy filters)
    """
    cursor = conn.cursor()

    # Index 1: Primary hierarchy index for containerized navigation
    # Covers: SELECT ... WHERE reality=? AND galaxy=? AND region_x=? AND region_y=? AND region_z=?
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_systems_hierarchy
        ON systems(reality, galaxy, region_x, region_y, region_z)
    """)
    logger.info("Created idx_systems_hierarchy compound index")

    # Index 2: Reality-Galaxy index for summary queries
    # Covers: SELECT galaxy, COUNT(*) FROM systems WHERE reality=? GROUP BY galaxy
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_systems_reality_galaxy
        ON systems(reality, galaxy)
    """)
    logger.info("Created idx_systems_reality_galaxy index")

    # Index 3: Rate limiting index for pending submissions
    # Covers: SELECT COUNT(*) FROM pending_systems WHERE submitted_by_ip=? AND submission_date > ?
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pending_ip_date
        ON pending_systems(submitted_by_ip, submission_date)
    """)
    logger.info("Created idx_pending_ip_date index")

    # Index 4: Discord tag with date ordering for partner filtering
    # Covers: SELECT * FROM systems WHERE discord_tag=? ORDER BY created_at DESC
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_systems_discord_created
        ON systems(discord_tag, created_at DESC)
    """)
    logger.info("Created idx_systems_discord_created index")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.23.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.23.0")


@register_migration("1.24.0", "Stellar classification field for systems")
def migration_1_24_0_stellar_classification(conn: sqlite3.Connection):
    """
    Jan 2026 - Add stellar classification field to systems.

    Stellar classification follows the Harvard spectral classification system
    used in No Man's Sky: O, B, A, F, G, K, M, E (exotic).

    Changes:
    - Add stellar_classification column to systems table
    - Add stellar_classification column to pending_systems table
    """
    cursor = conn.cursor()

    # Add to systems table
    cursor.execute("PRAGMA table_info(systems)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'stellar_classification' not in columns:
        cursor.execute('''
            ALTER TABLE systems ADD COLUMN stellar_classification TEXT
        ''')
        logger.info("Added stellar_classification column to systems table")
    else:
        logger.info("stellar_classification column already exists in systems")

    # Add to pending_systems table (stores system_data as JSON but we track it separately for filtering)
    cursor.execute("PRAGMA table_info(pending_systems)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'stellar_classification' not in columns:
        cursor.execute('''
            ALTER TABLE pending_systems ADD COLUMN stellar_classification TEXT
        ''')
        logger.info("Added stellar_classification column to pending_systems table")
    else:
        logger.info("stellar_classification column already exists in pending_systems")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.24.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.24.0")


@register_migration("1.25.0", "War Room feature - territorial conflict tracking system")
def migration_1_25_0_war_room(conn: sqlite3.Connection):
    """
    Jan 2026 - War Room Feature.

    A military command center-style feature for tracking territorial conflicts
    between enrolled No Man's Sky civilizations. Includes territory claims,
    conflict declarations, live feeds, statistics, and news system.

    Tables added:
    - war_room_enrollment: Civs enrolled in War Room
    - territorial_claims: System ownership claims
    - conflicts: Attack declarations and resolutions
    - conflict_events: Timeline of conflict actions
    - war_news: Correspondent articles
    - war_correspondents: Users who can post news
    - current_debrief: Mission objectives (single row)
    - war_statistics: Cached calculated stats
    - war_notifications: Pending in-app notifications
    - discord_webhooks: Per-civ webhook URLs for notifications
    """
    cursor = conn.cursor()

    # Table 1: war_room_enrollment - Civs enrolled in War Room
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS war_room_enrollment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER NOT NULL UNIQUE,
            enrolled_at TEXT DEFAULT (datetime('now')),
            enrolled_by TEXT,
            is_active INTEGER DEFAULT 1,
            notification_settings TEXT DEFAULT '{}',
            FOREIGN KEY (partner_id) REFERENCES partner_accounts(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_enrollment_partner ON war_room_enrollment(partner_id)')
    logger.info("Created war_room_enrollment table")

    # Table 2: territorial_claims - System ownership
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS territorial_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id TEXT NOT NULL,
            claimant_partner_id INTEGER NOT NULL,
            claimed_at TEXT DEFAULT (datetime('now')),
            claim_type TEXT DEFAULT 'controlled',
            region_x INTEGER,
            region_y INTEGER,
            region_z INTEGER,
            galaxy TEXT DEFAULT 'Euclid',
            reality TEXT DEFAULT 'Normal',
            notes TEXT,
            FOREIGN KEY (claimant_partner_id) REFERENCES partner_accounts(id),
            UNIQUE(system_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_territorial_claims_partner ON territorial_claims(claimant_partner_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_territorial_claims_region ON territorial_claims(region_x, region_y, region_z)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_territorial_claims_system ON territorial_claims(system_id)')
    logger.info("Created territorial_claims table")

    # Table 3: conflicts - Attack declarations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conflicts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_system_id TEXT NOT NULL,
            target_system_name TEXT,
            attacker_partner_id INTEGER NOT NULL,
            defender_partner_id INTEGER NOT NULL,
            declared_at TEXT DEFAULT (datetime('now')),
            declared_by TEXT,
            acknowledged_at TEXT,
            acknowledged_by TEXT,
            resolved_at TEXT,
            resolved_by TEXT,
            status TEXT DEFAULT 'pending',
            resolution TEXT,
            victor_partner_id INTEGER,
            notes TEXT,
            FOREIGN KEY (attacker_partner_id) REFERENCES partner_accounts(id),
            FOREIGN KEY (defender_partner_id) REFERENCES partner_accounts(id),
            FOREIGN KEY (victor_partner_id) REFERENCES partner_accounts(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflicts_status ON conflicts(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflicts_attacker ON conflicts(attacker_partner_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflicts_defender ON conflicts(defender_partner_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflicts_declared ON conflicts(declared_at DESC)')
    logger.info("Created conflicts table")

    # Table 4: conflict_events - Timeline of conflict actions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conflict_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conflict_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_at TEXT DEFAULT (datetime('now')),
            actor_partner_id INTEGER,
            actor_username TEXT,
            details TEXT,
            FOREIGN KEY (conflict_id) REFERENCES conflicts(id) ON DELETE CASCADE,
            FOREIGN KEY (actor_partner_id) REFERENCES partner_accounts(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflict_events_conflict ON conflict_events(conflict_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflict_events_time ON conflict_events(event_at DESC)')
    logger.info("Created conflict_events table")

    # Table 5: war_news - Correspondent articles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS war_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT NOT NULL,
            body TEXT NOT NULL,
            author_id INTEGER,
            author_username TEXT NOT NULL,
            author_type TEXT NOT NULL,
            related_conflict_id INTEGER,
            published_at TEXT DEFAULT (datetime('now')),
            is_pinned INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (related_conflict_id) REFERENCES conflicts(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_news_published ON war_news(published_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_news_pinned ON war_news(is_pinned, published_at DESC)')
    logger.info("Created war_news table")

    # Table 6: war_correspondents - Users who can post news
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS war_correspondents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            created_by TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_correspondents_username ON war_correspondents(username)')
    logger.info("Created war_correspondents table")

    # Table 7: current_debrief - Mission objectives (single row)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS current_debrief (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            objectives TEXT DEFAULT '[]',
            updated_at TEXT DEFAULT (datetime('now')),
            updated_by TEXT
        )
    ''')
    cursor.execute('INSERT OR IGNORE INTO current_debrief (id, objectives) VALUES (1, "[]")')
    logger.info("Created current_debrief table with initial row")

    # Table 8: war_statistics - Cached calculated stats
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS war_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_type TEXT NOT NULL UNIQUE,
            partner_id INTEGER,
            partner_display_name TEXT,
            value INTEGER,
            value_unit TEXT,
            details TEXT,
            calculated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (partner_id) REFERENCES partner_accounts(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_statistics_type ON war_statistics(stat_type)')
    logger.info("Created war_statistics table")

    # Table 9: war_notifications - Pending in-app notifications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS war_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_partner_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            related_conflict_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            read_at TEXT,
            dismissed_at TEXT,
            FOREIGN KEY (recipient_partner_id) REFERENCES partner_accounts(id) ON DELETE CASCADE,
            FOREIGN KEY (related_conflict_id) REFERENCES conflicts(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_notifications_recipient ON war_notifications(recipient_partner_id, read_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_notifications_created ON war_notifications(created_at DESC)')
    logger.info("Created war_notifications table")

    # Table 10: discord_webhooks - Per-civ webhook URLs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discord_webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner_id INTEGER NOT NULL UNIQUE,
            webhook_url TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            last_triggered_at TEXT,
            FOREIGN KEY (partner_id) REFERENCES partner_accounts(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discord_webhooks_partner ON discord_webhooks(partner_id)')
    logger.info("Created discord_webhooks table")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.25.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.25.0")


@register_migration("1.26.0", "War Room - add home region tracking for enrolled civilizations")
def migration_1_26_0_home_regions(conn: sqlite3.Connection):
    """
    Jan 2026 - Add home region tracking for War Room.

    Adds home region fields to war_room_enrollment so each civilization
    can have a designated home region displayed differently on the war map.
    """
    cursor = conn.cursor()

    # Add home region fields to war_room_enrollment
    try:
        cursor.execute('ALTER TABLE war_room_enrollment ADD COLUMN home_region_x INTEGER')
        cursor.execute('ALTER TABLE war_room_enrollment ADD COLUMN home_region_y INTEGER')
        cursor.execute('ALTER TABLE war_room_enrollment ADD COLUMN home_region_z INTEGER')
        cursor.execute('ALTER TABLE war_room_enrollment ADD COLUMN home_region_name TEXT')
        cursor.execute('ALTER TABLE war_room_enrollment ADD COLUMN home_galaxy TEXT DEFAULT "Euclid"')
        logger.info("Added home region columns to war_room_enrollment")
    except sqlite3.OperationalError as e:
        if 'duplicate column name' in str(e).lower():
            logger.info("Home region columns already exist in war_room_enrollment")
        else:
            raise

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.26.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.26.0")


@register_migration("1.27.0", "War Room v2 - Multi-party conflicts, activity feed, media, and reporting organizations")
def migration_1_27_0_war_room_v2(conn: sqlite3.Connection):
    """
    Jan 2026 - War Room v2 Major Update.

    Adds support for:
    - Multi-party conflicts (alliances, multiple civs per side)
    - Public activity feed for all war events
    - Media uploads (war pictures, screenshots)
    - Reporting organizations (Discord-based news teams)
    - Expanded news system with full articles and battle reports
    - Mutual agreement conflict resolution

    Tables added:
    - conflict_parties: Tracks which civs are on which side of a conflict
    - war_activity_feed: Public log of all war events
    - war_media: Stores images/screenshots
    - reporting_organizations: News organizations that can post
    - reporting_org_members: Members of reporting organizations

    Tables modified:
    - conflicts: Add conflict_type, resolution fields
    - war_news: Add article_type, featured_image_id
    """
    cursor = conn.cursor()

    # Table 1: conflict_parties - Multi-party support
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conflict_parties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conflict_id INTEGER NOT NULL,
            partner_id INTEGER NOT NULL,
            side TEXT NOT NULL CHECK (side IN ('attacker', 'defender')),
            joined_at TEXT DEFAULT (datetime('now')),
            joined_by TEXT,
            is_primary INTEGER DEFAULT 0,
            resolution_agreed INTEGER DEFAULT 0,
            resolution_agreed_at TEXT,
            FOREIGN KEY (conflict_id) REFERENCES conflicts(id) ON DELETE CASCADE,
            FOREIGN KEY (partner_id) REFERENCES partner_accounts(id),
            UNIQUE(conflict_id, partner_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflict_parties_conflict ON conflict_parties(conflict_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_conflict_parties_partner ON conflict_parties(partner_id)')
    logger.info("Created conflict_parties table")

    # Table 2: war_activity_feed - Public activity log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS war_activity_feed (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            event_at TEXT DEFAULT (datetime('now')),
            actor_partner_id INTEGER,
            actor_name TEXT,
            target_partner_id INTEGER,
            target_name TEXT,
            conflict_id INTEGER,
            system_id TEXT,
            system_name TEXT,
            region_name TEXT,
            headline TEXT NOT NULL,
            details TEXT,
            is_public INTEGER DEFAULT 1,
            FOREIGN KEY (actor_partner_id) REFERENCES partner_accounts(id),
            FOREIGN KEY (target_partner_id) REFERENCES partner_accounts(id),
            FOREIGN KEY (conflict_id) REFERENCES conflicts(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_feed_time ON war_activity_feed(event_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_feed_type ON war_activity_feed(event_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_feed_conflict ON war_activity_feed(conflict_id)')
    logger.info("Created war_activity_feed table")

    # Table 3: war_media - Images and screenshots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS war_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            original_filename TEXT,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            mime_type TEXT,
            uploaded_by_id INTEGER,
            uploaded_by_username TEXT,
            uploaded_by_type TEXT,
            uploaded_at TEXT DEFAULT (datetime('now')),
            caption TEXT,
            related_conflict_id INTEGER,
            related_news_id INTEGER,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (uploaded_by_id) REFERENCES partner_accounts(id),
            FOREIGN KEY (related_conflict_id) REFERENCES conflicts(id) ON DELETE SET NULL,
            FOREIGN KEY (related_news_id) REFERENCES war_news(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_media_uploaded ON war_media(uploaded_at DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_media_conflict ON war_media(related_conflict_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_war_media_news ON war_media(related_news_id)')
    logger.info("Created war_media table")

    # Table 4: reporting_organizations - News organizations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reporting_organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            discord_server_id TEXT,
            discord_server_name TEXT,
            logo_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            created_by TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reporting_orgs_name ON reporting_organizations(name)')
    logger.info("Created reporting_organizations table")

    # Table 5: reporting_org_members - Members of reporting orgs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reporting_org_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            role TEXT DEFAULT 'reporter',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            created_by TEXT,
            last_login_at TEXT,
            FOREIGN KEY (org_id) REFERENCES reporting_organizations(id) ON DELETE CASCADE,
            UNIQUE(org_id, username)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reporting_members_org ON reporting_org_members(org_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reporting_members_username ON reporting_org_members(username)')
    logger.info("Created reporting_org_members table")

    # Modify conflicts table - add new columns
    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN conflict_type TEXT DEFAULT "invasion"')
        logger.info("Added conflict_type to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN conflict_name TEXT')
        logger.info("Added conflict_name to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN resolution_proposed_by INTEGER')
        logger.info("Added resolution_proposed_by to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN resolution_proposed_at TEXT')
        logger.info("Added resolution_proposed_at to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN resolution_summary TEXT')
        logger.info("Added resolution_summary to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Modify war_news table - add article type and media
    try:
        cursor.execute('ALTER TABLE war_news ADD COLUMN article_type TEXT DEFAULT "headline"')
        logger.info("Added article_type to war_news")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE war_news ADD COLUMN featured_image_id INTEGER REFERENCES war_media(id)')
        logger.info("Added featured_image_id to war_news")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE war_news ADD COLUMN reporting_org_id INTEGER REFERENCES reporting_organizations(id)')
        logger.info("Added reporting_org_id to war_news")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE war_news ADD COLUMN view_count INTEGER DEFAULT 0')
        logger.info("Added view_count to war_news")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.27.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.27.0")


@register_migration("1.28.0", "War Room v3 - Peace treaty system, territory integration with systems.discord_tag")
def migration_1_28_0_peace_treaties(conn: sqlite3.Connection):
    """
    Jan 2026 - War Room v3: Peace Treaty System.

    Implements Civ6-style peace negotiations:
    - Peace proposals with demands (systems/regions)
    - Counter-offer system (2 max per civ)
    - Walk-away option to continue fighting
    - Auto-news generation for war events
    - Territory based on systems.discord_tag
    - HQ protection mechanics

    Tables added:
    - peace_proposals: Treaty proposals between warring parties
    - proposal_items: Systems/regions being offered or demanded
    - auto_news_events: Tracks which events have auto-generated news

    Tables modified:
    - conflicts: Add negotiation state tracking
    - war_room_enrollment: Add is_hq flag for home region protection
    """
    cursor = conn.cursor()

    # Table 1: peace_proposals - Treaty proposals
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS peace_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conflict_id INTEGER NOT NULL,
            proposer_partner_id INTEGER NOT NULL,
            recipient_partner_id INTEGER NOT NULL,
            proposal_type TEXT NOT NULL CHECK (proposal_type IN ('initial', 'counter')),
            counter_number INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'expired', 'superseded')),
            proposed_at TEXT DEFAULT (datetime('now')),
            responded_at TEXT,
            response_by TEXT,
            message TEXT,
            FOREIGN KEY (conflict_id) REFERENCES conflicts(id) ON DELETE CASCADE,
            FOREIGN KEY (proposer_partner_id) REFERENCES partner_accounts(id),
            FOREIGN KEY (recipient_partner_id) REFERENCES partner_accounts(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_peace_proposals_conflict ON peace_proposals(conflict_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_peace_proposals_status ON peace_proposals(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_peace_proposals_recipient ON peace_proposals(recipient_partner_id, status)')
    logger.info("Created peace_proposals table")

    # Table 2: proposal_items - Items in a peace proposal
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proposal_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER NOT NULL,
            item_type TEXT NOT NULL CHECK (item_type IN ('system', 'region')),
            direction TEXT NOT NULL CHECK (direction IN ('give', 'receive')),
            system_id TEXT,
            system_name TEXT,
            region_x INTEGER,
            region_y INTEGER,
            region_z INTEGER,
            region_name TEXT,
            galaxy TEXT DEFAULT 'Euclid',
            from_partner_id INTEGER NOT NULL,
            to_partner_id INTEGER NOT NULL,
            FOREIGN KEY (proposal_id) REFERENCES peace_proposals(id) ON DELETE CASCADE,
            FOREIGN KEY (from_partner_id) REFERENCES partner_accounts(id),
            FOREIGN KEY (to_partner_id) REFERENCES partner_accounts(id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_proposal_items_proposal ON proposal_items(proposal_id)')
    logger.info("Created proposal_items table")

    # Table 3: auto_news_events - Tracks auto-generated news
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS auto_news_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            reference_id INTEGER,
            reference_type TEXT,
            news_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (news_id) REFERENCES war_news(id) ON DELETE SET NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_auto_news_ref ON auto_news_events(reference_type, reference_id)')
    logger.info("Created auto_news_events table")

    # Add negotiation columns to conflicts table
    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN negotiation_status TEXT DEFAULT NULL')
        logger.info("Added negotiation_status to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN attacker_counter_count INTEGER DEFAULT 0')
        logger.info("Added attacker_counter_count to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN defender_counter_count INTEGER DEFAULT 0')
        logger.info("Added defender_counter_count to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN negotiation_started_at TEXT')
        logger.info("Added negotiation_started_at to conflicts")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Add is_hq flag to war_room_enrollment for HQ protection
    try:
        cursor.execute('ALTER TABLE war_room_enrollment ADD COLUMN is_hq_protected INTEGER DEFAULT 1')
        logger.info("Added is_hq_protected to war_room_enrollment")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.28.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.28.0")


@register_migration("1.29.0", "System update tracking - last_updated_by, last_updated_at, contributors")
def migration_1_29_0_system_update_tracking(conn: sqlite3.Connection):
    """
    Jan 2026 - System Update Tracking.

    Adds fields to track who has contributed updates to systems:
    - last_updated_by: Username of the last person to update the system
    - last_updated_at: Timestamp of the last update
    - contributors: JSON array of all usernames who have contributed to this system

    This preserves credit for the original discoverer (discovered_by) while
    tracking subsequent editors for attribution.
    """
    cursor = conn.cursor()

    # Add last_updated_by to systems table
    try:
        cursor.execute('ALTER TABLE systems ADD COLUMN last_updated_by TEXT')
        logger.info("Added last_updated_by to systems")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Add last_updated_at to systems table
    try:
        cursor.execute('ALTER TABLE systems ADD COLUMN last_updated_at TEXT')
        logger.info("Added last_updated_at to systems")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Add contributors JSON array to systems table
    try:
        cursor.execute("ALTER TABLE systems ADD COLUMN contributors TEXT DEFAULT '[]'")
        logger.info("Added contributors to systems")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.29.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.29.0")


@register_migration("1.30.0", "War Room - Practice mode for conflict testing")
def migration_1_30_0_war_room_practice_mode(conn: sqlite3.Connection):
    """
    Jan 2026 - War Room Practice Mode.

    Adds is_practice column to conflicts table to support practice/training
    conflicts that don't affect real statistics or territory.

    Practice conflicts:
    - Don't send notifications
    - Don't appear in activity feed
    - Don't affect leaderboard statistics
    - Are filtered from active conflicts display by default
    - Allow civs to test the war system safely
    """
    cursor = conn.cursor()

    # Add is_practice column to conflicts table
    try:
        cursor.execute('ALTER TABLE conflicts ADD COLUMN is_practice INTEGER DEFAULT 0')
        logger.info("Added is_practice column to conflicts table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.30.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.30.0")


@register_migration("1.31.0", "Discoveries showcase - featured, view tracking, and type slugs")
def migration_1_31_0_discoveries_showcase(conn: sqlite3.Connection):
    """
    Jan 2026 - Discoveries Page Showcase Overhaul.

    Adds columns to support the new showcase-style discoveries page:
    - is_featured: Allows admins/partners to feature specific discoveries
    - view_count: Tracks popularity for sorting
    - type_slug: Normalized type identifier for URL routing

    Also adds indexes for efficient filtering and sorting.
    """
    cursor = conn.cursor()

    # Add is_featured column
    try:
        cursor.execute('ALTER TABLE discoveries ADD COLUMN is_featured INTEGER DEFAULT 0')
        logger.info("Added is_featured column to discoveries table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Add view_count column
    try:
        cursor.execute('ALTER TABLE discoveries ADD COLUMN view_count INTEGER DEFAULT 0')
        logger.info("Added view_count column to discoveries table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Add type_slug column (normalized type for URL routing)
    try:
        cursor.execute('ALTER TABLE discoveries ADD COLUMN type_slug TEXT')
        logger.info("Added type_slug column to discoveries table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Create indexes for efficient queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discoveries_type_slug ON discoveries(type_slug)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discoveries_featured ON discoveries(is_featured)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discoveries_timestamp ON discoveries(submission_timestamp DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discoveries_views ON discoveries(view_count DESC)')
    logger.info("Created indexes for discoveries table")

    # Backfill type_slug based on existing discovery_type emoji values
    emoji_to_slug = {
        '🦗': 'fauna',
        '🌿': 'flora',
        '💎': 'mineral',
        '🏛️': 'ancient',
        '📜': 'history',
        '🦴': 'bones',
        '👽': 'alien',
        '🚀': 'starship',
        '⚙️': 'multitool',
        '📖': 'lore',
        '🏠': 'base',
        '🆕': 'other',
    }

    for emoji, slug in emoji_to_slug.items():
        cursor.execute(
            'UPDATE discoveries SET type_slug = ? WHERE discovery_type = ? AND type_slug IS NULL',
            (slug, emoji)
        )
        updated = cursor.rowcount
        if updated > 0:
            logger.info(f"Set type_slug='{slug}' for {updated} discoveries with type={emoji}")

    # Handle any discoveries with text-based types (fallback)
    text_to_slug = {
        'Fauna': 'fauna', 'fauna': 'fauna',
        'Flora': 'flora', 'flora': 'flora',
        'Mineral': 'mineral', 'mineral': 'mineral',
        'Ancient': 'ancient', 'ancient': 'ancient',
        'History': 'history', 'history': 'history',
        'Bones': 'bones', 'bones': 'bones',
        'Alien': 'alien', 'alien': 'alien',
        'Starship': 'starship', 'starship': 'starship',
        'Multi-tool': 'multitool', 'Multitool': 'multitool', 'multitool': 'multitool',
        'Lore': 'lore', 'lore': 'lore',
        'Custom Base': 'base', 'Base': 'base', 'base': 'base',
        'Other': 'other', 'other': 'other',
    }

    for text, slug in text_to_slug.items():
        cursor.execute(
            'UPDATE discoveries SET type_slug = ? WHERE discovery_type = ? AND type_slug IS NULL',
            (slug, text)
        )

    # Set remaining NULL type_slugs to 'other'
    cursor.execute("UPDATE discoveries SET type_slug = 'other' WHERE type_slug IS NULL")
    logger.info("Set type_slug='other' for remaining discoveries without type")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.31.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.31.0")


@register_migration("1.32.0", "Advanced filter performance indexes")
def migration_1_32_0_filter_indexes(conn: sqlite3.Connection):
    """
    Feb 2026 - Advanced Filter System.

    Adds indexes to support the new advanced filtering on the Systems and
    Galaxy pages. These indexes dramatically speed up filtering by star type,
    economy, conflict level, lifeform, and planet-level attributes.
    """
    cursor = conn.cursor()

    # System-level filter indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_star_type ON systems(star_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_economy_type ON systems(economy_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_conflict_level ON systems(conflict_level)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_dominant_lifeform ON systems(dominant_lifeform)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_stellar_classification ON systems(stellar_classification)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_is_complete ON systems(is_complete)')
    logger.info("Created system-level filter indexes")

    # Planet-level filter indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planets_system_id ON planets(system_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planets_biome ON planets(biome)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planets_sentinel_level ON planets(sentinel_level)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planets_weather ON planets(weather)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_planets_is_moon ON planets(is_moon)')
    logger.info("Created planet-level filter indexes")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.32.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.32.0")


@register_migration("1.33.0", "Discovery community tagging and event types")
def migration_1_33_0_discovery_tags_event_types(conn: sqlite3.Connection):
    """
    Feb 2026 - Discovery Events + Partner Analytics.

    Adds discord_tag to discoveries table for community-scoped analytics
    and discovery event tracking. Backfills from linked systems.

    Adds event_type to events table to support discovery-only and
    combined (submissions + discoveries) events.
    """
    cursor = conn.cursor()

    # Add discord_tag to discoveries table
    try:
        cursor.execute('ALTER TABLE discoveries ADD COLUMN discord_tag TEXT')
        logger.info("Added discord_tag column to discoveries table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Backfill discord_tag from linked systems
    cursor.execute('''
        UPDATE discoveries
        SET discord_tag = (
            SELECT systems.discord_tag
            FROM systems
            WHERE systems.id = discoveries.system_id
        )
        WHERE discord_tag IS NULL AND system_id IS NOT NULL
    ''')
    backfilled = cursor.rowcount
    if backfilled > 0:
        logger.info(f"Backfilled discord_tag for {backfilled} discoveries from linked systems")

    # Index for community-scoped discovery queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discoveries_discord_tag ON discoveries(discord_tag)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_discoveries_discord_tag_timestamp ON discoveries(discord_tag, submission_timestamp DESC)')

    # Add event_type to events table (submissions, discoveries, both)
    try:
        cursor.execute("ALTER TABLE events ADD COLUMN event_type TEXT DEFAULT 'submissions'")
        logger.info("Added event_type column to events table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.33.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.33.0")


@register_migration("1.34.0", "Discovery system linking, stub systems, pending discoveries approval")
def migration_1_34_0_discovery_system_linking(conn: sqlite3.Connection):
    """
    Feb 2026 - Discovery System Linking & Approval Workflow.

    Adds:
    - is_stub column to systems table for minimal placeholder systems
    - type_metadata column to discoveries table for type-specific fields (JSON)
    - pending_discoveries table for discovery approval workflow
      (mirrors pending_systems pattern with discord_tag scoping)

    Stub systems are created inline during discovery submission when
    the system doesn't exist yet. They have is_stub=1 and display a
    public badge indicating they need full data.

    Pending discoveries follow the same approval rules as systems:
    - Partners approve their own community's discoveries
    - Super admin approves Haven + personal submissions
    - Self-approval prevention
    """
    cursor = conn.cursor()

    # Add is_stub to systems table
    try:
        cursor.execute('ALTER TABLE systems ADD COLUMN is_stub INTEGER DEFAULT 0')
        logger.info("Added is_stub column to systems table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Add type_metadata to discoveries table (JSON string for type-specific fields)
    try:
        cursor.execute('ALTER TABLE discoveries ADD COLUMN type_metadata TEXT')
        logger.info("Added type_metadata column to discoveries table")
    except sqlite3.OperationalError as e:
        if 'duplicate column' not in str(e).lower():
            raise

    # Index on is_stub for filtering
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_is_stub ON systems(is_stub)')
    logger.info("Created idx_systems_is_stub index")

    # Create pending_discoveries table
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='pending_discoveries'
    """)
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE pending_discoveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discovery_data TEXT,
                discovery_name TEXT,
                discovery_type TEXT,
                type_slug TEXT,
                system_id INTEGER,
                system_name TEXT,
                planet_name TEXT,
                moon_name TEXT,
                location_type TEXT,
                discord_tag TEXT,
                submitted_by TEXT,
                submitted_by_ip TEXT,
                submitter_account_id INTEGER,
                submitter_account_type TEXT,
                submission_date TEXT,
                photo_url TEXT,
                status TEXT DEFAULT 'pending',
                reviewed_by TEXT,
                review_date TEXT,
                rejection_reason TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_disc_status ON pending_discoveries(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_disc_discord_tag ON pending_discoveries(discord_tag)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pending_disc_submission_date ON pending_discoveries(submission_date DESC)')
        logger.info("Created pending_discoveries table with indexes")
    else:
        logger.info("pending_discoveries table already exists")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.34.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.34.0")


@register_migration("1.35.0", "Backfill completeness scores for all systems")
def migrate_1_35_0(conn):
    """Repurpose is_complete from boolean (0/1) to score (0-100) and backfill all systems.

    The is_complete column now stores a completeness percentage (0-100).
    Grade thresholds: S (85-100), A (65-84), B (40-64), C (0-39).
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all system IDs
    cursor.execute('SELECT id FROM systems')
    system_ids = [row[0] for row in cursor.fetchall()]
    logger.info(f"Backfilling completeness scores for {len(system_ids)} systems...")

    # Import the helper from the API module
    import importlib
    import sys as _sys
    api_module_path = Path(__file__).parent / 'control_room_api.py'

    # Inline scoring logic to avoid circular import
    def _calc_score(cursor, system_id):
        cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
        system = cursor.fetchone()
        if not system:
            return 0
        system = dict(system)

        cursor.execute('SELECT * FROM planets WHERE system_id = ?', (system_id,))
        planets = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (system_id,))
        station_row = cursor.fetchone()
        station = dict(station_row) if station_row else None

        # System Core (30 pts)
        sys_core_fields = ['star_type', 'economy_type', 'economy_level', 'conflict_level', 'dominant_lifeform', 'stellar_classification']
        sys_core_filled = sum(1 for f in sys_core_fields if system.get(f))
        sys_core_score = round((sys_core_filled / len(sys_core_fields)) * 30)

        # System Extra (10 pts)
        sys_extra_fields = ['glyph_code', 'description']
        sys_extra_filled = sum(1 for f in sys_extra_fields if system.get(f))
        sys_extra_score = round((sys_extra_filled / len(sys_extra_fields)) * 10)

        # Planet Coverage (10 pts)
        planet_coverage_score = 10 if planets else 0

        # Planet scores
        planet_env_score = 0
        planet_life_score = 0
        planet_detail_score = 0

        if planets:
            env_fields = ['biome', 'weather', 'sentinel', 'storm_frequency', 'building_density']
            life_fields = ['fauna', 'flora', 'common_resource', 'uncommon_resource', 'rare_resource']
            detail_fields = ['photo', 'description']

            env_totals = []
            life_totals = []
            detail_totals = []

            for p in planets:
                env_filled = sum(1 for f in env_fields if p.get(f) and str(p.get(f)).strip() and p.get(f) not in ('None', 'N/A'))
                env_totals.append(env_filled / len(env_fields))

                life_filled = 0
                for f in life_fields:
                    val = p.get(f)
                    if f in ('fauna', 'flora'):
                        if val and str(val).strip() and val not in ('N/A', 'None'):
                            life_filled += 1
                    else:
                        if val and str(val).strip():
                            life_filled += 1
                life_totals.append(life_filled / len(life_fields))

                detail_filled = sum(1 for f in detail_fields if p.get(f) and str(p.get(f)).strip())
                has_hazard = any(p.get(h, 0) != 0 for h in ['hazard_temperature', 'hazard_radiation', 'hazard_toxicity'])
                if has_hazard:
                    detail_filled += 1
                detail_totals.append(detail_filled / (len(detail_fields) + 1))

            planet_env_score = round((sum(env_totals) / len(env_totals)) * 20)
            planet_life_score = round((sum(life_totals) / len(life_totals)) * 15)
            planet_detail_score = round((sum(detail_totals) / len(detail_totals)) * 10)

        # Space Station (5 pts)
        station_score = 0
        if station:
            station_score += 3
            trade_goods = station.get('trade_goods', '[]')
            if trade_goods and trade_goods != '[]':
                station_score += 2

        return min(sys_core_score + sys_extra_score + planet_coverage_score + planet_env_score + planet_life_score + planet_detail_score + station_score, 100)

    updated = 0
    for sys_id in system_ids:
        score = _calc_score(cursor, sys_id)
        cursor.execute('UPDATE systems SET is_complete = ? WHERE id = ?', (score, sys_id))
        updated += 1

    logger.info(f"Backfilled completeness scores for {updated} systems")

    # Create index for grade-based filtering
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_completeness ON systems(is_complete)')
    logger.info("Created idx_systems_completeness index")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.35.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.35.0")


@register_migration("1.36.0", "Re-score completeness with corrected criteria")
def migrate_1_36_0(conn):
    """Re-backfill completeness scores with fairer scoring criteria.

    Changes from v1.35.0 scoring:
    - System Core now 35pts (5 fields, removed stellar_classification)
    - stellar_classification moved to System Extra (10pts, 3 fields)
    - Planet Environment now 25pts (biome, weather, sentinel only)
    - sentinel='None' now counts as filled (valid game value = no sentinels)
    - fauna/flora _text display fields used as fallback
    - Removed Planet Detail category (photo/description/hazards are aspirational)
    - Hazards all-zero is no longer penalized (peaceful planets are valid)
    - Removed storm_frequency, building_density from scoring (rarely captured)
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM systems')
    system_ids = [row[0] for row in cursor.fetchall()]
    logger.info(f"Re-scoring completeness for {len(system_ids)} systems with corrected criteria...")

    def _is_filled(val, allow_none=False):
        if val is None:
            return False
        s = str(val).strip()
        if not s:
            return False
        if s == 'N/A':
            return False
        if s == 'None' and not allow_none:
            return False
        return True

    def _calc_score_v2(cursor, system_id):
        cursor.execute('SELECT * FROM systems WHERE id = ?', (system_id,))
        system = cursor.fetchone()
        if not system:
            return 0
        system = dict(system)

        cursor.execute('SELECT * FROM planets WHERE system_id = ?', (system_id,))
        planets = [dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM space_stations WHERE system_id = ?', (system_id,))
        station_row = cursor.fetchone()
        station = dict(station_row) if station_row else None

        # System Core (35 pts) - 5 essential fields
        sys_core_fields = ['star_type', 'economy_type', 'economy_level', 'conflict_level', 'dominant_lifeform']
        sys_core_filled = sum(1 for f in sys_core_fields if _is_filled(system.get(f)))
        sys_core_score = round((sys_core_filled / len(sys_core_fields)) * 35)

        # System Extra (10 pts) - bonus fields
        sys_extra_fields = ['glyph_code', 'stellar_classification', 'description']
        sys_extra_filled = sum(1 for f in sys_extra_fields if _is_filled(system.get(f)))
        sys_extra_score = round((sys_extra_filled / len(sys_extra_fields)) * 10)

        # Planet Coverage (10 pts)
        planet_coverage_score = 10 if planets else 0

        # Planet Environment avg (25 pts) - biome, weather, sentinel
        planet_env_score = 0
        planet_life_score = 0

        if planets:
            env_totals = []
            life_totals = []

            for p in planets:
                env_filled = 0
                if _is_filled(p.get('biome')):
                    env_filled += 1
                # Weather: check main field and display text fallback
                if _is_filled(p.get('weather')) or _is_filled(p.get('weather_text')):
                    env_filled += 1
                # Sentinel: 'None' is valid (means no sentinels on planet)
                if _is_filled(p.get('sentinel'), allow_none=True) or _is_filled(p.get('sentinels_text')):
                    env_filled += 1
                env_totals.append(min(env_filled / 3, 1.0))

                # Life (15 pts) - fauna, flora, resources
                life_filled = 0
                # Fauna: check main field and display text
                if _is_filled(p.get('fauna')) or _is_filled(p.get('fauna_text')):
                    life_filled += 1
                # Flora: check main field and display text
                if _is_filled(p.get('flora')) or _is_filled(p.get('flora_text')):
                    life_filled += 1
                # Resources
                for f in ['common_resource', 'uncommon_resource', 'rare_resource']:
                    if _is_filled(p.get(f)):
                        life_filled += 1
                life_totals.append(life_filled / 5)

            planet_env_score = round((sum(env_totals) / len(env_totals)) * 25)
            planet_life_score = round((sum(life_totals) / len(life_totals)) * 15)

        # Space Station (5 pts)
        station_score = 0
        if station:
            station_score += 3
            trade_goods = station.get('trade_goods', '[]')
            if trade_goods and trade_goods != '[]':
                station_score += 2

        return min(sys_core_score + sys_extra_score + planet_coverage_score + planet_env_score + planet_life_score + station_score, 100)

    updated = 0
    for sys_id in system_ids:
        score = _calc_score_v2(cursor, sys_id)
        cursor.execute('UPDATE systems SET is_complete = ? WHERE id = ?', (score, sys_id))
        updated += 1

    logger.info(f"Re-scored completeness for {updated} systems with corrected criteria")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.36.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.36.0")


@register_migration("1.37.0", "Backfill NULL contributors from discovered_by")
def migrate_1_37_0(conn):
    """Fix systems with NULL contributors by populating from discovered_by field."""
    cursor = conn.cursor()

    # Find all systems with NULL or empty contributors
    cursor.execute("""
        SELECT id, discovered_by FROM systems
        WHERE contributors IS NULL OR contributors = '' OR contributors = '[]'
    """)
    rows = cursor.fetchall()

    updated = 0
    for sys_id, discovered_by in rows:
        if discovered_by and discovered_by != 'Unknown':
            cursor.execute(
                'UPDATE systems SET contributors = ? WHERE id = ?',
                (json.dumps([discovered_by]), sys_id)
            )
        else:
            cursor.execute(
                "UPDATE systems SET contributors = '[]' WHERE id = ?",
                (sys_id,)
            )
        updated += 1

    logger.info(f"Backfilled contributors for {updated} systems")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.37.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.37.0")


@register_migration("1.38.0", "Backfill contributors from pending_systems discord username")
def migrate_1_38_0(conn):
    """Fix systems still missing contributors by looking up the original submitter's
    discord username from pending_systems.personal_discord_username."""
    cursor = conn.cursor()

    # Find systems still missing real contributors
    cursor.execute("""
        SELECT s.id, s.discovered_by, ps.personal_discord_username, ps.submitted_by
        FROM systems s
        LEFT JOIN pending_systems ps ON (
            ps.system_name = s.name OR ps.edit_system_id = s.id
        )
        WHERE s.contributors IS NULL OR s.contributors = '' OR s.contributors = '[]'
        GROUP BY s.id
    """)
    rows = cursor.fetchall()

    updated = 0
    for sys_id, discovered_by, personal_discord, submitted_by in rows:
        # Priority: personal_discord_username (the actual form field) > submitted_by > discovered_by
        username = personal_discord or submitted_by or discovered_by
        if username and username != 'Unknown' and username != 'HavenExtractor':
            cursor.execute(
                'UPDATE systems SET contributors = ? WHERE id = ?',
                (json.dumps([username]), sys_id)
            )
        else:
            cursor.execute(
                "UPDATE systems SET contributors = '[]' WHERE id = ?",
                (sys_id,)
            )
        updated += 1

    logger.info(f"Backfilled contributors from pending_systems for {updated} systems")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.38.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.38.0")
