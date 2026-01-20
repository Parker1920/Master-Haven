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
