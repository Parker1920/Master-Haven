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

import json
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
        # Guard against duplicate version numbers. The runner records applied
        # versions in schema_migrations.version (UNIQUE) and only runs a
        # migration whose version is GREATER than the highest already applied —
        # so a second migration sharing an existing version would silently NEVER
        # run on any DB that already applied the first one (e.g. prod). That's a
        # data-integrity landmine when two branches independently grab the same
        # number, so fail loudly at import instead. Bump to the next free number.
        existing = next((m for m in _migrations if m.version == version), None)
        if existing is not None:
            highest = _migrations[-1].version if _migrations else 'none'
            raise ValueError(
                f"Duplicate migration version {version!r} "
                f"(new: {name!r}; existing: {existing.name!r}). "
                f"Each migration needs a unique version — bump to the next free "
                f"number (current highest is {highest}). A duplicate would be "
                f"silently skipped on any DB that already applied the first one."
            )
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

    # Numerically-highest successfully applied REAL migration. Excludes the
    # underscore-prefixed bridge marker, and sorts by version tuple in Python
    # (string ORDER BY mis-ranks 1.9.0 vs 1.10.0, and a backfilled row's id is
    # not its version order).
    cursor.execute(r"""
        SELECT version FROM schema_migrations
        WHERE success = 1 AND version NOT LIKE '\_%' ESCAPE '\'
    """)
    versions = [r[0] for r in cursor.fetchall()]
    if not versions:
        return None
    try:
        return max(versions, key=_version_tuple)
    except (ValueError, TypeError):
        return versions[-1]


# Sentinel row recorded once when a legacy DB is bridged from the old
# high-water-mark runner to per-migration tracking, so the backfill never repeats.
_BACKFILL_MARKER = '_per_migration_backfill'


def _get_applied_versions(conn: sqlite3.Connection) -> set:
    """Set of migration version strings already applied successfully."""
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_migrations WHERE success = 1")
    return {row[0] for row in cursor.fetchall()}


def _backfill_applied_versions_once(conn: sqlite3.Connection, migrations) -> None:
    """One-time bridge from the legacy high-water-mark model to per-migration
    tracking.

    The OLD runner stored only "the last applied version" and ran everything
    numbered above it. So migrations from before the tracking table existed (and
    anything ever skipped for being <= the watermark) have NO success row. If we
    switched straight to "run anything not recorded", all of those would re-run.

    To prevent that, the FIRST time the new runner sees a legacy DB we record
    every registered migration at-or-below the current watermark as
    already-applied (faithfully capturing what the old logic assumed), then drop
    a marker so this never runs again. Migrations ABOVE the watermark — and any
    migration added later at any number — are intentionally NOT backfilled, so
    they run. Idempotent; a fresh DB just gets the marker (nothing to bridge).
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ? AND success = 1",
        (_BACKFILL_MARKER,))
    if cursor.fetchone():
        return  # already bridged

    watermark = get_current_version(conn)  # legacy: last-applied version (None on fresh DB)
    now = datetime.now().isoformat()
    backfilled = 0
    if watermark is not None:
        wm = _version_tuple(watermark)
        already = _get_applied_versions(conn)
        for m in migrations:
            if m.version not in already and _version_tuple(m.version) <= wm:
                cursor.execute('''
                    INSERT OR IGNORE INTO schema_migrations
                    (version, migration_name, applied_at, success)
                    VALUES (?, ?, ?, 1)
                ''', (m.version, m.name + ' (backfilled)', now))
                backfilled += 1
    cursor.execute('''
        INSERT OR IGNORE INTO schema_migrations
        (version, migration_name, applied_at, success)
        VALUES (?, ?, ?, 1)
    ''', (_BACKFILL_MARKER, 'per-migration tracking bridge', now))
    conn.commit()
    if watermark is not None:
        logger.info(
            "Migration runner: bridged to per-migration tracking "
            f"(watermark was {watermark}; backfilled {backfilled} prior versions)")


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

        migrations = get_migrations()  # sorted ascending by version

        # Bridge legacy high-water-mark DBs to per-migration tracking (once),
        # then run any migration NOT yet recorded as applied — independent of how
        # its number compares to others. This removes the old landmine where a
        # migration numbered at-or-below the last-applied version silently never
        # ran (a duplicate version, or a lower number added by a parallel branch).
        _backfill_applied_versions_once(conn, migrations)
        applied_versions = _get_applied_versions(conn)
        pending = [m for m in migrations if m.version not in applied_versions]

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
    # Column renamed sentinel_level → sentinel in v1.45.2; check before
    # indexing so fresh-init DBs (where init_database created the new schema)
    # don't fail when applying this historical migration.
    cursor.execute("PRAGMA table_info(planets)")
    planet_cols = {row[1] for row in cursor.fetchall()}
    if 'sentinel_level' in planet_cols:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_planets_sentinel_level ON planets(sentinel_level)')
    elif 'sentinel' in planet_cols:
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_planets_sentinel ON planets(sentinel)')
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


# Add discord_tag to discoveries (backfilled from systems) and event_type to events.
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


# Add is_stub to systems, type_metadata to discoveries, create pending_discoveries table.
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


# Repurpose is_complete from boolean to 0-100 score; backfill all systems with v1 scoring.
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


# Re-score all systems with v2 scoring: fairer weights, sentinel='None' valid, no detail penalty.
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


# Data fix: populate empty contributors arrays from the discovered_by field.
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


# Data fix: fill remaining empty contributors by looking up original submitter in pending_systems.
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


# Data fix: fix discovered_by from pending_systems; convert contributors from ["name"] to [{name, action, date}].
@register_migration("1.39.0", "Fix discovered_by and convert contributors to object format")
def migrate_1_39_0(conn):
    """Fix discovered_by from pending_systems.personal_discord_username and convert
    contributors from old string array to new object format with action and date."""
    cursor = conn.cursor()

    # Step 1: Fix discovered_by for ALL systems using pending_systems.personal_discord_username
    # This is the Discord name entered on the Create form - the actual uploader
    cursor.execute("""
        SELECT s.id, s.discovered_by, s.discovered_at, s.created_at,
               ps.personal_discord_username, ps.submitted_by, ps.submission_timestamp,
               ps.edit_system_id
        FROM systems s
        LEFT JOIN pending_systems ps ON (
            (ps.edit_system_id IS NULL AND ps.system_name = s.name)
            OR ps.edit_system_id = s.id
        )
        GROUP BY s.id
    """)
    all_systems = cursor.fetchall()

    discovered_fixed = 0
    for row in all_systems:
        sys_id = row[0]
        current_discovered_by = row[1]
        current_discovered_at = row[2]
        created_at = row[3]
        personal_discord = row[4]
        submitted_by = row[5]
        submission_ts = row[6]
        edit_system_id = row[7]

        # Only fix discovered_by if it's missing/Unknown AND this was a first upload (not an edit)
        if (not current_discovered_by or current_discovered_by in ('Unknown', 'HavenExtractor')) and not edit_system_id:
            username = personal_discord or submitted_by
            if username and username not in ('Unknown', 'HavenExtractor'):
                upload_date = submission_ts or current_discovered_at or created_at or datetime.now().isoformat()
                cursor.execute(
                    'UPDATE systems SET discovered_by = ?, discovered_at = COALESCE(discovered_at, ?) WHERE id = ?',
                    (username, upload_date, sys_id)
                )
                discovered_fixed += 1

    logger.info(f"Fixed discovered_by for {discovered_fixed} systems")

    # Step 2: Convert ALL contributors from old string format to new object format
    cursor.execute("SELECT id, contributors, discovered_by, discovered_at, created_at FROM systems")
    all_for_contrib = cursor.fetchall()

    contrib_converted = 0
    for row in all_for_contrib:
        sys_id = row[0]
        raw_contributors = row[1]
        discovered_by = row[2]
        discovered_at = row[3]
        created_at = row[4]

        try:
            parsed = json.loads(raw_contributors) if raw_contributors else []
        except (json.JSONDecodeError, TypeError):
            parsed = []

        # Check if already in new format (list of dicts)
        if parsed and isinstance(parsed[0], dict):
            continue  # Already converted

        # Convert old format: first entry is uploader, rest are editors
        new_contributors = []
        upload_date = discovered_at or created_at or datetime.now().isoformat()

        if parsed:
            # Old format: ["name1", "name2", ...]
            for i, name in enumerate(parsed):
                if isinstance(name, str):
                    new_contributors.append({
                        "name": name,
                        "action": "upload" if i == 0 else "edit",
                        "date": upload_date if i == 0 else None
                    })
        elif discovered_by and discovered_by not in ('Unknown', 'HavenExtractor'):
            # No contributors but has discovered_by - create upload entry
            new_contributors.append({
                "name": discovered_by,
                "action": "upload",
                "date": upload_date
            })

        if new_contributors:
            cursor.execute(
                'UPDATE systems SET contributors = ? WHERE id = ?',
                (json.dumps(new_contributors), sys_id)
            )
            contrib_converted += 1

    logger.info(f"Converted contributors format for {contrib_converted} systems")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.39.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.39.0")


# Add 13 planet columns (rings, dissonant, bones, etc.); re-score with v3 (abandoned + dynamic life).
@register_migration("1.40.0", "Planet attributes, valuable resources, dynamic scoring with materials fix")
def migrate_1_40_0(conn):
    """Add planet attribute and valuable resource columns, re-score with fixed logic.

    Schema changes:
    - Planet specials: has_rings, is_dissonant, is_infested, extreme_weather, water_world, vile_brood
    - Valuable resources: ancient_bones, salvageable_scrap, storm_crystals, gravitino_balls
    - Exotic trophy text field
    - (Also adds old column names as no-ops if they exist from a partial run)

    Scoring improvements (v3):
    - Abandoned systems get full credit for economy/conflict/station fields
    - Planet Life uses biome-aware dynamic denominator for fauna/flora
    - Resources checked via `materials` field first (where Wizard saves),
      falls back to common/uncommon/rare columns (Extractor data)
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- Schema: Add planet attribute and resource columns ---
    new_columns = [
        # Planet specials (attributes of the planet itself)
        ('has_rings', 'INTEGER DEFAULT 0'),
        ('is_dissonant', 'INTEGER DEFAULT 0'),
        ('is_infested', 'INTEGER DEFAULT 0'),
        ('extreme_weather', 'INTEGER DEFAULT 0'),
        ('water_world', 'INTEGER DEFAULT 0'),
        ('vile_brood', 'INTEGER DEFAULT 0'),
        # Valuable resources (surface harvestables)
        ('ancient_bones', 'INTEGER DEFAULT 0'),
        ('salvageable_scrap', 'INTEGER DEFAULT 0'),
        ('storm_crystals', 'INTEGER DEFAULT 0'),
        ('gravitino_balls', 'INTEGER DEFAULT 0'),
        # Exotic trophy
        ('exotic_trophy', 'TEXT'),
        # Legacy column names (no-op if already exist from partial run)
        ('dissonance', 'INTEGER DEFAULT 0'),
        ('infested', 'INTEGER DEFAULT 0'),
    ]
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f'ALTER TABLE planets ADD COLUMN {col_name} {col_type}')
            logger.info(f"Added column planets.{col_name}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # --- Re-score completeness for all systems ---
    cursor.execute('SELECT id FROM systems')
    system_ids = [row[0] for row in cursor.fetchall()]
    logger.info(f"Re-scoring completeness for {len(system_ids)} systems (v3: materials fix + dynamic life)...")

    NO_LIFE_BIOMES = {'Dead', 'Lifeless', 'Life-Incompatible', 'Airless', 'Low Atmosphere', 'Gas Giant', 'Empty'}

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

    def _life_descriptor_filled(val, val_text):
        for v in [val, val_text]:
            if v is not None:
                s = str(v).strip()
                if s:
                    return True
        return False

    def _calc_score_v3(cursor, system_id):
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

        is_abandoned = system.get('economy_type') in ('None', 'Abandoned')

        # System Core (35 pts)
        sys_core_fields = ['star_type', 'economy_type', 'economy_level', 'conflict_level', 'dominant_lifeform']
        sys_core_filled = 0
        for f in sys_core_fields:
            val = system.get(f)
            if f in ('economy_type', 'economy_level', 'conflict_level') and is_abandoned:
                sys_core_filled += 1
            elif _is_filled(val):
                sys_core_filled += 1
        sys_core_score = round((sys_core_filled / len(sys_core_fields)) * 35)

        # System Extra (10 pts)
        sys_extra_fields = ['glyph_code', 'stellar_classification', 'description']
        sys_extra_filled = sum(1 for f in sys_extra_fields if _is_filled(system.get(f)))
        sys_extra_score = round((sys_extra_filled / len(sys_extra_fields)) * 10)

        # Planet Coverage (10 pts)
        planet_coverage_score = 10 if planets else 0

        # Planet Environment (25 pts) + Planet Life (15 pts)
        planet_env_score = 0
        planet_life_score = 0

        if planets:
            env_totals = []
            life_totals = []

            for p in planets:
                env_filled = 0
                if _is_filled(p.get('biome')):
                    env_filled += 1
                if _is_filled(p.get('weather')) or _is_filled(p.get('weather_text')):
                    env_filled += 1
                if _is_filled(p.get('sentinel'), allow_none=True) or _is_filled(p.get('sentinels_text')):
                    env_filled += 1
                env_totals.append(min(env_filled / 3, 1.0))

                # Life - dynamic denominator, materials-based resource check
                life_filled = 0
                life_applicable = 0
                biome_val = (p.get('biome') or '').strip()
                is_dead_biome = biome_val in NO_LIFE_BIOMES

                if _life_descriptor_filled(p.get('fauna'), p.get('fauna_text')):
                    life_filled += 1
                    life_applicable += 1
                elif not is_dead_biome:
                    life_applicable += 1

                if _life_descriptor_filled(p.get('flora'), p.get('flora_text')):
                    life_filled += 1
                    life_applicable += 1
                elif not is_dead_biome:
                    life_applicable += 1

                # Resources: check materials first, fall back to individual columns
                materials_val = (p.get('materials') or '').strip()
                has_materials = bool(materials_val) and materials_val not in ('N/A', 'None')
                if has_materials:
                    life_applicable += 1
                    life_filled += 1
                else:
                    res_filled = sum(1 for f in ['common_resource', 'uncommon_resource', 'rare_resource'] if _is_filled(p.get(f)))
                    life_applicable += 1
                    if res_filled > 0:
                        life_filled += 1

                life_totals.append(life_filled / max(life_applicable, 1))

            planet_env_score = round((sum(env_totals) / len(env_totals)) * 25)
            planet_life_score = round((sum(life_totals) / len(life_totals)) * 15)

        # Space Station (5 pts)
        station_score = 0
        if is_abandoned:
            station_score = 5
        elif station:
            station_score += 3
            trade_goods = station.get('trade_goods', '[]')
            if trade_goods and trade_goods != '[]':
                station_score += 2

        return min(sys_core_score + sys_extra_score + planet_coverage_score + planet_env_score + planet_life_score + station_score, 100)

    updated = 0
    for sys_id in system_ids:
        score = _calc_score_v3(cursor, sys_id)
        cursor.execute('UPDATE systems SET is_complete = ? WHERE id = ?', (score, sys_id))
        updated += 1

    logger.info(f"Re-scored completeness for {updated} systems (v3)")

    # Update _metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.40.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.40.0")


# Fix for partial v1.40.0: ensure all planet/moon attribute columns exist after schema rename.
@register_migration("1.41.0", "Ensure planet attribute columns exist and re-score")
def migrate_1_41_0(conn):
    """Fix for v1.40.0 rewrite: ensure all planet/moon attribute columns exist.

    v1.40.0 was rewritten after initial deploy to rename columns. If v1.40.0
    already ran with the old schema, the new columns (has_rings, is_dissonant,
    extreme_weather, water_world) were never created. This migration ensures
    they all exist on both planets and moons tables, and re-scores completeness.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Attribute columns shared by planets and moons
    attr_columns = [
        ('has_rings', 'INTEGER DEFAULT 0'),
        ('is_dissonant', 'INTEGER DEFAULT 0'),
        ('is_infested', 'INTEGER DEFAULT 0'),
        ('extreme_weather', 'INTEGER DEFAULT 0'),
        ('water_world', 'INTEGER DEFAULT 0'),
        ('vile_brood', 'INTEGER DEFAULT 0'),
        ('exotic_trophy', 'TEXT'),
    ]

    # Planet-only columns (valuable resources + legacy)
    planet_extra_columns = [
        ('ancient_bones', 'INTEGER DEFAULT 0'),
        ('salvageable_scrap', 'INTEGER DEFAULT 0'),
        ('storm_crystals', 'INTEGER DEFAULT 0'),
        ('gravitino_balls', 'INTEGER DEFAULT 0'),
        # Legacy names from original v1.40.0
        ('dissonance', 'INTEGER DEFAULT 0'),
        ('infested', 'INTEGER DEFAULT 0'),
    ]

    # Add attribute columns to planets table
    added = 0
    for col_name, col_type in attr_columns + planet_extra_columns:
        try:
            cursor.execute(f'ALTER TABLE planets ADD COLUMN {col_name} {col_type}')
            logger.info(f"Added missing column planets.{col_name}")
            added += 1
        except sqlite3.OperationalError:
            pass  # Already exists

    if added > 0:
        logger.info(f"Added {added} missing planet attribute columns")
    else:
        logger.info("All planet attribute columns already present")

    # Add attribute columns to moons table
    moon_added = 0
    for col_name, col_type in attr_columns:
        try:
            cursor.execute(f'ALTER TABLE moons ADD COLUMN {col_name} {col_type}')
            logger.info(f"Added column moons.{col_name}")
            moon_added += 1
        except sqlite3.OperationalError:
            pass  # Already exists

    if moon_added > 0:
        logger.info(f"Added {moon_added} moon attribute columns")
    else:
        logger.info("All moon attribute columns already present")

    # Re-score completeness with materials fix
    NO_LIFE_BIOMES = {'Dead', 'Lifeless', 'Life-Incompatible', 'Airless', 'Low Atmosphere', 'Gas Giant', 'Empty'}

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

    def _life_descriptor_filled(val, val_text):
        for v in [val, val_text]:
            if v is not None:
                s = str(v).strip()
                if s:
                    return True
        return False

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

        is_abandoned = system.get('economy_type') in ('None', 'Abandoned')

        # System Core (35 pts)
        sys_core_fields = ['star_type', 'economy_type', 'economy_level', 'conflict_level', 'dominant_lifeform']
        sys_core_filled = 0
        for f in sys_core_fields:
            val = system.get(f)
            if f in ('economy_type', 'economy_level', 'conflict_level') and is_abandoned:
                sys_core_filled += 1
            elif _is_filled(val):
                sys_core_filled += 1
        sys_core_score = round((sys_core_filled / len(sys_core_fields)) * 35)

        # System Extra (10 pts)
        sys_extra_fields = ['glyph_code', 'stellar_classification', 'description']
        sys_extra_filled = sum(1 for f in sys_extra_fields if _is_filled(system.get(f)))
        sys_extra_score = round((sys_extra_filled / len(sys_extra_fields)) * 10)

        # Planet Coverage (10 pts)
        planet_coverage_score = 10 if planets else 0

        # Planet Environment (25 pts) + Planet Life (15 pts)
        planet_env_score = 0
        planet_life_score = 0
        if planets:
            env_totals = []
            life_totals = []
            for p in planets:
                env_filled = 0
                if _is_filled(p.get('biome')):
                    env_filled += 1
                if _is_filled(p.get('weather')) or _is_filled(p.get('weather_text')):
                    env_filled += 1
                if _is_filled(p.get('sentinel'), allow_none=True) or _is_filled(p.get('sentinels_text')):
                    env_filled += 1
                env_totals.append(min(env_filled / 3, 1.0))

                life_filled = 0
                life_applicable = 0
                biome_val = (p.get('biome') or '').strip()
                is_dead_biome = biome_val in NO_LIFE_BIOMES

                if _life_descriptor_filled(p.get('fauna'), p.get('fauna_text')):
                    life_filled += 1
                    life_applicable += 1
                elif not is_dead_biome:
                    life_applicable += 1

                if _life_descriptor_filled(p.get('flora'), p.get('flora_text')):
                    life_filled += 1
                    life_applicable += 1
                elif not is_dead_biome:
                    life_applicable += 1

                materials_val = (p.get('materials') or '').strip()
                has_materials = bool(materials_val) and materials_val not in ('N/A', 'None')
                if has_materials:
                    life_applicable += 1
                    life_filled += 1
                else:
                    res_filled = sum(1 for f in ['common_resource', 'uncommon_resource', 'rare_resource'] if _is_filled(p.get(f)))
                    life_applicable += 1
                    if res_filled > 0:
                        life_filled += 1

                life_totals.append(life_filled / max(life_applicable, 1))

            planet_env_score = round((sum(env_totals) / len(env_totals)) * 25)
            planet_life_score = round((sum(life_totals) / len(life_totals)) * 15)

        # Space Station (5 pts)
        station_score = 0
        if is_abandoned:
            station_score = 5
        elif station:
            station_score += 3
            trade_goods = station.get('trade_goods', '[]')
            if trade_goods and trade_goods != '[]':
                station_score += 2

        return min(sys_core_score + sys_extra_score + planet_coverage_score + planet_env_score + planet_life_score + station_score, 100)

    cursor.execute('SELECT id FROM systems')
    system_ids = [row[0] for row in cursor.fetchall()]
    logger.info(f"Re-scoring completeness for {len(system_ids)} systems...")

    for sys_id in system_ids:
        score = _calc_score(cursor, sys_id)
        cursor.execute('UPDATE systems SET is_complete = ? WHERE id = ?', (score, sys_id))

    logger.info(f"Re-scored {len(system_ids)} systems")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.41.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.41.0")


# Data fix: recover star_type from pending_systems JSON where star_color/star_type mismatch lost it.
@register_migration("1.42.0", "Backfill star_type from extractor pending_systems JSON")
def migrate_1_42_0(conn):
    """Backfill star_type for approved systems where it was lost due to field name mismatch.

    The extractor sends 'star_color' but the approval code was reading 'star_type'.
    This reads the original JSON from pending_systems and fills in the missing values.
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find approved systems with NULL/empty star_type
    cursor.execute("""
        SELECT s.id, s.name, s.glyph_code
        FROM systems s
        WHERE (s.star_type IS NULL OR s.star_type = '' OR s.star_type = 'Unknown')
    """)
    missing_systems = cursor.fetchall()

    if not missing_systems:
        logger.info("No systems with missing star_type found")
        return

    logger.info(f"Found {len(missing_systems)} systems with missing star_type")
    updated = 0

    for system in missing_systems:
        system_id = system['id']
        glyph_code = system['glyph_code']

        if not glyph_code:
            continue

        # Try to find the original submission in pending_systems
        cursor.execute("""
            SELECT system_data, raw_json FROM pending_systems
            WHERE glyph_code = ?
            ORDER BY id DESC LIMIT 1
        """, (glyph_code,))
        pending = cursor.fetchone()

        if not pending:
            continue

        # Try system_data first, then raw_json
        star_color = None
        for json_field in ['system_data', 'raw_json']:
            json_str = pending[json_field]
            if not json_str:
                continue
            try:
                data = json.loads(json_str)
                star_color = data.get('star_color') or data.get('star_type')
                if star_color and star_color != 'Unknown':
                    break
            except (json.JSONDecodeError, TypeError):
                continue

        if star_color and star_color != 'Unknown':
            cursor.execute("UPDATE systems SET star_type = ? WHERE id = ?", (star_color, system_id))
            updated += 1
            logger.info(f"  Backfilled star_type='{star_color}' for system '{system['name']}' ({glyph_code})")

    conn.commit()
    logger.info(f"Backfilled star_type for {updated}/{len(missing_systems)} systems")

    # Update metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.42.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.42.0")


# Add key_type, discord_username, submission stats to api_keys for per-user extractor tracking.
@register_migration("1.43.0", "Per-user extractor API keys with self-service registration")
def migrate_1_43_0(conn):
    """Per-user API keys for Haven Extractor.

    Adds columns to api_keys table for user tracking and classification:
    - key_type: 'extractor' (per-user), 'admin' (manual), 'system' (shared legacy)
    - discord_username: tied to extractor key owner
    - total_submissions: cached count for quick display
    - last_submission_at: timestamp of most recent submission

    Backfills stats from pending_systems and marks existing keys.
    """
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(api_keys)")
    columns = [col[1] for col in cursor.fetchall()]

    # Add key_type column
    if 'key_type' not in columns:
        cursor.execute("ALTER TABLE api_keys ADD COLUMN key_type TEXT DEFAULT 'admin'")
        logger.info("Added key_type column to api_keys")

    # Add discord_username column
    if 'discord_username' not in columns:
        cursor.execute("ALTER TABLE api_keys ADD COLUMN discord_username TEXT")
        logger.info("Added discord_username column to api_keys")

    # Add total_submissions cached count
    if 'total_submissions' not in columns:
        cursor.execute("ALTER TABLE api_keys ADD COLUMN total_submissions INTEGER DEFAULT 0")
        logger.info("Added total_submissions column to api_keys")

    # Add last_submission_at timestamp
    if 'last_submission_at' not in columns:
        cursor.execute("ALTER TABLE api_keys ADD COLUMN last_submission_at TEXT")
        logger.info("Added last_submission_at column to api_keys")

    # Mark the existing shared "Haven Extractor" key as system type
    cursor.execute("UPDATE api_keys SET key_type = 'system' WHERE name = 'Haven Extractor'")
    logger.info("Marked 'Haven Extractor' shared key as key_type='system'")

    # Mark any other keys without a type as admin
    cursor.execute("UPDATE api_keys SET key_type = 'admin' WHERE key_type IS NULL OR key_type = ''")

    # Create indexes for fast lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_discord_username ON api_keys(discord_username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_type ON api_keys(key_type)")
    logger.info("Created indexes on api_keys(discord_username, key_type)")

    # Backfill total_submissions from pending_systems
    cursor.execute("""
        UPDATE api_keys SET total_submissions = (
            SELECT COUNT(*) FROM pending_systems ps
            WHERE ps.api_key_name = api_keys.name
        )
    """)
    logger.info("Backfilled total_submissions from pending_systems")

    # Backfill last_submission_at from pending_systems
    cursor.execute("""
        UPDATE api_keys SET last_submission_at = (
            SELECT MAX(submission_date) FROM pending_systems ps
            WHERE ps.api_key_name = api_keys.name
        )
    """)
    logger.info("Backfilled last_submission_at from pending_systems")

    conn.commit()

    # Update metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.43.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.43.0")


# Data fix: replace 0-indexed Galaxy_N fallback names with proper NMS galaxy names from embedded lookup.
@register_migration("1.44.0", "Fix Galaxy_N naming - merge into proper galaxy names")
def migrate_1_44_0(conn):
    """Fix galaxy names from extractor off-by-one bug.

    The extractor sent 0-indexed galaxy IDs as fallback names (Galaxy_255, Galaxy_149)
    instead of 1-indexed (Galaxy_256, Galaxy_150) or proper names (Odyalutai, Zavainlani).
    This migration:
    1. Finds all Galaxy_N entries in systems and pending_systems tables
    2. Looks up the correct name from galaxies.json (N is 0-indexed game ID)
    3. Updates the galaxy column and system_data JSON where applicable
    """
    import re

    cursor = conn.cursor()

    # All 256 NMS galaxies: 0-indexed game ID -> proper name
    # Embedded directly so migration works regardless of file structure
    galaxies_data = {
        "0": "Euclid", "1": "Hilbert Dimension", "2": "Calypso", "3": "Hesperius Dimension",
        "4": "Hyades", "5": "Ickjamatew", "6": "Budullangr", "7": "Kikolgallr",
        "8": "Eltiensleen", "9": "Eissentam", "10": "Elkupalos", "11": "Aptarkaba",
        "12": "Ontiniangp", "13": "Odiwagiri", "14": "Ogtialabi", "15": "Muhacksonto",
        "16": "Hitonskyer", "17": "Rerasmutul", "18": "Isdoraijung", "19": "Doctinawyra",
        "20": "Loychazinq", "21": "Zukasizawa", "22": "Ekwathore", "23": "Yeberhahne",
        "24": "Twerbetek", "25": "Sivarates", "26": "Eajerandal", "27": "Aldukesci",
        "28": "Wotyarogii", "29": "Sudzerbal", "30": "Maupenzhay", "31": "Sugueziume",
        "32": "Brogoweldian", "33": "Ehbogdenbu", "34": "Ijsenufryos", "35": "Nipikulha",
        "36": "Autsurabin", "37": "Lusontrygiamh", "38": "Rewmanawa", "39": "Ethiophodhe",
        "40": "Urastrykle", "41": "Xobeurindj", "42": "Oniijialdu", "43": "Wucetosucc",
        "44": "Ebyeloof", "45": "Odyavanta", "46": "Milekistri", "47": "Waferganh",
        "48": "Agnusopwit", "49": "Teyaypilny", "50": "Zalienkosm", "51": "Ladgudiraf",
        "52": "Mushonponte", "53": "Amsentisz", "54": "Fladiselm", "55": "Laanawemb",
        "56": "Ilkerloor", "57": "Davanossi", "58": "Ploehrliou", "59": "Corpinyaya",
        "60": "Leckandmeram", "61": "Quulngais", "62": "Nokokipsechl", "63": "Rinblodesa",
        "64": "Loydporpen", "65": "Ibtrevskip", "66": "Elkowaldb", "67": "Heholhofsko",
        "68": "Yebrilowisod", "69": "Husalvangewi", "70": "Ovna'uesed", "71": "Bahibusey",
        "72": "Nuybeliaure", "73": "Doshawchuc", "74": "Ruckinarkh", "75": "Thorettac",
        "76": "Nuponoparau", "77": "Moglaschil", "78": "Uiweupose", "79": "Nasmilete",
        "80": "Ekdaluskin", "81": "Hakapanasy", "82": "Dimonimba", "83": "Cajaccari",
        "84": "Olonerovo", "85": "Umlanswick", "86": "Henayliszm", "87": "Utzenmate",
        "88": "Umirpaiya", "89": "Paholiang", "90": "Iaereznika", "91": "Yudukagath",
        "92": "Boealalosnj", "93": "Yaevarcko", "94": "Coellosipp", "95": "Wayndohalou",
        "96": "Smoduraykl", "97": "Apmaneessu", "98": "Hicanpaav", "99": "Akvasanta",
        "100": "Tuychelisaor", "101": "Rivskimbe", "102": "Daksanquix", "103": "Kissonlin",
        "104": "Aediabiel", "105": "Ulosaginyik", "106": "Roclaytonycar", "107": "Kichiaroa",
        "108": "Irceauffey", "109": "Nudquathsenfe", "110": "Getaizakaal", "111": "Hansolmien",
        "112": "Bloytisagra", "113": "Ladsenlay", "114": "Luyugoslasr", "115": "Ubredhatk",
        "116": "Cidoniana", "117": "Jasinessa", "118": "Torweierf", "119": "Saffneckm",
        "120": "Thnistner", "121": "Dotusingg", "122": "Luleukous", "123": "Jelmandan",
        "124": "Otimanaso", "125": "Enjaxusanto", "126": "Sezviktorew", "127": "Zikehpm",
        "128": "Bephembah", "129": "Broomerrai", "130": "Meximicka", "131": "Venessika",
        "132": "Gaiteseling", "133": "Zosakasiro", "134": "Drajayanes", "135": "Ooibekuar",
        "136": "Urckiansi", "137": "Dozivadido", "138": "Emiekereks", "139": "Meykinunukur",
        "140": "Kimycuristh", "141": "Roansfien", "142": "Isgarmeso", "143": "Daitibeli",
        "144": "Gucuttarik", "145": "Enlaythie", "146": "Drewweste", "147": "Akbulkabi",
        "148": "Homskiw", "149": "Zavainlani", "150": "Jewijkmas", "151": "Itlhotagra",
        "152": "Podalicess", "153": "Hiviusauer", "154": "Halsebenk", "155": "Puikitoac",
        "156": "Gaybakuaria", "157": "Grbodubhe", "158": "Rycempler", "159": "Indjalala",
        "160": "Fontenikk", "161": "Pasycihelwhee", "162": "Ikbaksmit", "163": "Telicianses",
        "164": "Oyleyzhan", "165": "Uagerosat", "166": "Impoxectin", "167": "Twoodmand",
        "168": "Hilfsesorbs", "169": "Ezdaranit", "170": "Wiensanshe", "171": "Ewheelonc",
        "172": "Litzmantufa", "173": "Emarmatosi", "174": "Mufimbomacvi", "175": "Wongquarum",
        "176": "Hapirajua", "177": "Igbinduina", "178": "Wepaitvas", "179": "Sthatigudi",
        "180": "Yekathsebehn", "181": "Ebedeagurst", "182": "Nolisonia", "183": "Ulexovitab",
        "184": "Iodhinxois", "185": "Irroswitzs", "186": "Bifredait", "187": "Beiraghedwe",
        "188": "Yeonatlak", "189": "Cugnatachh", "190": "Nozoryenki", "191": "Ebralduri",
        "192": "Evcickcandj", "193": "Ziybosswin", "194": "Heperclait", "195": "Sugiuniam",
        "196": "Aaseertush", "197": "Uglyestemaa", "198": "Horeroedsh", "199": "Drundemiso",
        "200": "Ityanianat", "201": "Purneyrine", "202": "Dokiessmat", "203": "Nupiacheh",
        "204": "Dihewsonj", "205": "Rudrailhik", "206": "Tweretnort", "207": "Snatreetze",
        "208": "Iwundaracos", "209": "Digarlewena", "210": "Erquagsta", "211": "Logovoloin",
        "212": "Boyaghosganh", "213": "Kuolungau", "214": "Pehneldept", "215": "Yevettiiqidcon",
        "216": "Sahliacabru", "217": "Noggalterpor", "218": "Chmageaki", "219": "Veticueca",
        "220": "Vittesbursul", "221": "Nootanore", "222": "Innebdjerah", "223": "Kisvarcini",
        "224": "Cuzcogipper", "225": "Pamanhermonsu", "226": "Brotoghek", "227": "Mibittara",
        "228": "Huruahili", "229": "Raldwicarn", "230": "Ezdartlic", "231": "Badesclema",
        "232": "Isenkeyan", "233": "Iadoitesu", "234": "Yagrovoisi", "235": "Ewcomechio",
        "236": "Inunnunnoda", "237": "Dischiutun", "238": "Yuwarugha", "239": "Ialmendra",
        "240": "Reponudrle", "241": "Rinjanagrbo", "242": "Zeziceloh", "243": "Oeileutasc",
        "244": "Zicniijinis", "245": "Dugnowarilda", "246": "Neuxoisan", "247": "Ilmenhorn",
        "248": "Rukwatsuku", "249": "Nepitzaspru", "250": "Chcehoemig", "251": "Haffneyrin",
        "252": "Uliciawai", "253": "Tuhgrespod", "254": "Iousongola", "255": "Odyalutai",
    }

    # Find all Galaxy_N entries in systems table
    cursor.execute("SELECT DISTINCT galaxy FROM systems WHERE galaxy LIKE 'Galaxy_%'")
    bad_system_galaxies = [row[0] for row in cursor.fetchall()]

    total_fixed = 0
    for bad_name in bad_system_galaxies:
        match = re.match(r'^Galaxy_(\d+)$', bad_name)
        if not match:
            continue
        idx = match.group(1)
        correct_name = galaxies_data.get(idx)
        if not correct_name:
            logger.warning(f"No galaxy name found for index {idx}, skipping {bad_name}")
            continue

        cursor.execute("UPDATE systems SET galaxy = ? WHERE galaxy = ?", (correct_name, bad_name))
        count = cursor.rowcount
        total_fixed += count
        logger.info(f"Systems: {bad_name} -> {correct_name} ({count} rows)")

    if total_fixed:
        logger.info(f"Fixed {total_fixed} systems with incorrect galaxy names")

    # Find all Galaxy_N entries in pending_systems table
    cursor.execute("SELECT DISTINCT galaxy FROM pending_systems WHERE galaxy LIKE 'Galaxy_%'")
    bad_pending_galaxies = [row[0] for row in cursor.fetchall()]

    pending_fixed = 0
    for bad_name in bad_pending_galaxies:
        match = re.match(r'^Galaxy_(\d+)$', bad_name)
        if not match:
            continue
        idx = match.group(1)
        correct_name = galaxies_data.get(idx)
        if not correct_name:
            logger.warning(f"No galaxy name found for index {idx}, skipping {bad_name}")
            continue

        # Update galaxy column
        cursor.execute("UPDATE pending_systems SET galaxy = ? WHERE galaxy = ?", (correct_name, bad_name))
        count = cursor.rowcount
        pending_fixed += count
        logger.info(f"Pending: {bad_name} -> {correct_name} ({count} rows)")

        # Also fix system_data JSON where galaxy is stored
        cursor.execute(
            "SELECT id, system_data FROM pending_systems WHERE galaxy = ? AND system_data IS NOT NULL",
            (correct_name,)
        )
        for row in cursor.fetchall():
            try:
                data = json.loads(row[1])
                if data.get('galaxy') == bad_name:
                    data['galaxy'] = correct_name
                    cursor.execute(
                        "UPDATE pending_systems SET system_data = ? WHERE id = ?",
                        (json.dumps(data), row[0])
                    )
            except (json.JSONDecodeError, TypeError):
                pass

    if pending_fixed:
        logger.info(f"Fixed {pending_fixed} pending_systems with incorrect galaxy names")

    if not total_fixed and not pending_fixed:
        logger.info("No Galaxy_N entries found - no fixes needed")

    conn.commit()

    # Update metadata version
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.44.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.44.0")


# Retry of v1.44.0 galaxy fix: v1.44.0 failed on production due to wrong file path for galaxies.json.
@register_migration("1.45.0", "Fix Galaxy_N naming - retry with embedded data")
def migrate_1_45_0(conn):
    """Re-run galaxy name fix with embedded lookup data.

    Migration 1.44.0 failed on production because it tried to load galaxies.json
    from a wrong file path. This migration has the full galaxy mapping embedded
    directly so it works regardless of file structure.
    """
    import re

    cursor = conn.cursor()

    # All 256 NMS galaxies: 0-indexed game ID (as string) -> proper name
    galaxies_data = {
        "0": "Euclid", "1": "Hilbert Dimension", "2": "Calypso", "3": "Hesperius Dimension",
        "4": "Hyades", "5": "Ickjamatew", "6": "Budullangr", "7": "Kikolgallr",
        "8": "Eltiensleen", "9": "Eissentam", "10": "Elkupalos", "11": "Aptarkaba",
        "12": "Ontiniangp", "13": "Odiwagiri", "14": "Ogtialabi", "15": "Muhacksonto",
        "16": "Hitonskyer", "17": "Rerasmutul", "18": "Isdoraijung", "19": "Doctinawyra",
        "20": "Loychazinq", "21": "Zukasizawa", "22": "Ekwathore", "23": "Yeberhahne",
        "24": "Twerbetek", "25": "Sivarates", "26": "Eajerandal", "27": "Aldukesci",
        "28": "Wotyarogii", "29": "Sudzerbal", "30": "Maupenzhay", "31": "Sugueziume",
        "32": "Brogoweldian", "33": "Ehbogdenbu", "34": "Ijsenufryos", "35": "Nipikulha",
        "36": "Autsurabin", "37": "Lusontrygiamh", "38": "Rewmanawa", "39": "Ethiophodhe",
        "40": "Urastrykle", "41": "Xobeurindj", "42": "Oniijialdu", "43": "Wucetosucc",
        "44": "Ebyeloof", "45": "Odyavanta", "46": "Milekistri", "47": "Waferganh",
        "48": "Agnusopwit", "49": "Teyaypilny", "50": "Zalienkosm", "51": "Ladgudiraf",
        "52": "Mushonponte", "53": "Amsentisz", "54": "Fladiselm", "55": "Laanawemb",
        "56": "Ilkerloor", "57": "Davanossi", "58": "Ploehrliou", "59": "Corpinyaya",
        "60": "Leckandmeram", "61": "Quulngais", "62": "Nokokipsechl", "63": "Rinblodesa",
        "64": "Loydporpen", "65": "Ibtrevskip", "66": "Elkowaldb", "67": "Heholhofsko",
        "68": "Yebrilowisod", "69": "Husalvangewi", "70": "Ovna'uesed", "71": "Bahibusey",
        "72": "Nuybeliaure", "73": "Doshawchuc", "74": "Ruckinarkh", "75": "Thorettac",
        "76": "Nuponoparau", "77": "Moglaschil", "78": "Uiweupose", "79": "Nasmilete",
        "80": "Ekdaluskin", "81": "Hakapanasy", "82": "Dimonimba", "83": "Cajaccari",
        "84": "Olonerovo", "85": "Umlanswick", "86": "Henayliszm", "87": "Utzenmate",
        "88": "Umirpaiya", "89": "Paholiang", "90": "Iaereznika", "91": "Yudukagath",
        "92": "Boealalosnj", "93": "Yaevarcko", "94": "Coellosipp", "95": "Wayndohalou",
        "96": "Smoduraykl", "97": "Apmaneessu", "98": "Hicanpaav", "99": "Akvasanta",
        "100": "Tuychelisaor", "101": "Rivskimbe", "102": "Daksanquix", "103": "Kissonlin",
        "104": "Aediabiel", "105": "Ulosaginyik", "106": "Roclaytonycar", "107": "Kichiaroa",
        "108": "Irceauffey", "109": "Nudquathsenfe", "110": "Getaizakaal", "111": "Hansolmien",
        "112": "Bloytisagra", "113": "Ladsenlay", "114": "Luyugoslasr", "115": "Ubredhatk",
        "116": "Cidoniana", "117": "Jasinessa", "118": "Torweierf", "119": "Saffneckm",
        "120": "Thnistner", "121": "Dotusingg", "122": "Luleukous", "123": "Jelmandan",
        "124": "Otimanaso", "125": "Enjaxusanto", "126": "Sezviktorew", "127": "Zikehpm",
        "128": "Bephembah", "129": "Broomerrai", "130": "Meximicka", "131": "Venessika",
        "132": "Gaiteseling", "133": "Zosakasiro", "134": "Drajayanes", "135": "Ooibekuar",
        "136": "Urckiansi", "137": "Dozivadido", "138": "Emiekereks", "139": "Meykinunukur",
        "140": "Kimycuristh", "141": "Roansfien", "142": "Isgarmeso", "143": "Daitibeli",
        "144": "Gucuttarik", "145": "Enlaythie", "146": "Drewweste", "147": "Akbulkabi",
        "148": "Homskiw", "149": "Zavainlani", "150": "Jewijkmas", "151": "Itlhotagra",
        "152": "Podalicess", "153": "Hiviusauer", "154": "Halsebenk", "155": "Puikitoac",
        "156": "Gaybakuaria", "157": "Grbodubhe", "158": "Rycempler", "159": "Indjalala",
        "160": "Fontenikk", "161": "Pasycihelwhee", "162": "Ikbaksmit", "163": "Telicianses",
        "164": "Oyleyzhan", "165": "Uagerosat", "166": "Impoxectin", "167": "Twoodmand",
        "168": "Hilfsesorbs", "169": "Ezdaranit", "170": "Wiensanshe", "171": "Ewheelonc",
        "172": "Litzmantufa", "173": "Emarmatosi", "174": "Mufimbomacvi", "175": "Wongquarum",
        "176": "Hapirajua", "177": "Igbinduina", "178": "Wepaitvas", "179": "Sthatigudi",
        "180": "Yekathsebehn", "181": "Ebedeagurst", "182": "Nolisonia", "183": "Ulexovitab",
        "184": "Iodhinxois", "185": "Irroswitzs", "186": "Bifredait", "187": "Beiraghedwe",
        "188": "Yeonatlak", "189": "Cugnatachh", "190": "Nozoryenki", "191": "Ebralduri",
        "192": "Evcickcandj", "193": "Ziybosswin", "194": "Heperclait", "195": "Sugiuniam",
        "196": "Aaseertush", "197": "Uglyestemaa", "198": "Horeroedsh", "199": "Drundemiso",
        "200": "Ityanianat", "201": "Purneyrine", "202": "Dokiessmat", "203": "Nupiacheh",
        "204": "Dihewsonj", "205": "Rudrailhik", "206": "Tweretnort", "207": "Snatreetze",
        "208": "Iwundaracos", "209": "Digarlewena", "210": "Erquagsta", "211": "Logovoloin",
        "212": "Boyaghosganh", "213": "Kuolungau", "214": "Pehneldept", "215": "Yevettiiqidcon",
        "216": "Sahliacabru", "217": "Noggalterpor", "218": "Chmageaki", "219": "Veticueca",
        "220": "Vittesbursul", "221": "Nootanore", "222": "Innebdjerah", "223": "Kisvarcini",
        "224": "Cuzcogipper", "225": "Pamanhermonsu", "226": "Brotoghek", "227": "Mibittara",
        "228": "Huruahili", "229": "Raldwicarn", "230": "Ezdartlic", "231": "Badesclema",
        "232": "Isenkeyan", "233": "Iadoitesu", "234": "Yagrovoisi", "235": "Ewcomechio",
        "236": "Inunnunnoda", "237": "Dischiutun", "238": "Yuwarugha", "239": "Ialmendra",
        "240": "Reponudrle", "241": "Rinjanagrbo", "242": "Zeziceloh", "243": "Oeileutasc",
        "244": "Zicniijinis", "245": "Dugnowarilda", "246": "Neuxoisan", "247": "Ilmenhorn",
        "248": "Rukwatsuku", "249": "Nepitzaspru", "250": "Chcehoemig", "251": "Haffneyrin",
        "252": "Uliciawai", "253": "Tuhgrespod", "254": "Iousongola", "255": "Odyalutai",
    }

    # Fix systems table
    cursor.execute("SELECT DISTINCT galaxy FROM systems WHERE galaxy LIKE 'Galaxy_%'")
    bad_system_galaxies = [row[0] for row in cursor.fetchall()]

    total_fixed = 0
    for bad_name in bad_system_galaxies:
        match = re.match(r'^Galaxy_(\d+)$', bad_name)
        if not match:
            continue
        idx = match.group(1)
        correct_name = galaxies_data.get(idx)
        if not correct_name:
            logger.warning(f"No galaxy name found for index {idx}, skipping {bad_name}")
            continue

        cursor.execute("UPDATE systems SET galaxy = ? WHERE galaxy = ?", (correct_name, bad_name))
        count = cursor.rowcount
        total_fixed += count
        logger.info(f"Systems: {bad_name} -> {correct_name} ({count} rows)")

    if total_fixed:
        logger.info(f"Fixed {total_fixed} systems with incorrect galaxy names")

    # Fix pending_systems table
    cursor.execute("SELECT DISTINCT galaxy FROM pending_systems WHERE galaxy LIKE 'Galaxy_%'")
    bad_pending_galaxies = [row[0] for row in cursor.fetchall()]

    pending_fixed = 0
    for bad_name in bad_pending_galaxies:
        match = re.match(r'^Galaxy_(\d+)$', bad_name)
        if not match:
            continue
        idx = match.group(1)
        correct_name = galaxies_data.get(idx)
        if not correct_name:
            continue

        cursor.execute("UPDATE pending_systems SET galaxy = ? WHERE galaxy = ?", (correct_name, bad_name))
        count = cursor.rowcount
        pending_fixed += count
        logger.info(f"Pending: {bad_name} -> {correct_name} ({count} rows)")

        # Also fix system_data JSON
        cursor.execute(
            "SELECT id, system_data FROM pending_systems WHERE galaxy = ? AND system_data IS NOT NULL",
            (correct_name,)
        )
        for row in cursor.fetchall():
            try:
                data = json.loads(row[1])
                if data.get('galaxy') == bad_name:
                    data['galaxy'] = correct_name
                    cursor.execute(
                        "UPDATE pending_systems SET system_data = ? WHERE id = ?",
                        (json.dumps(data), row[0])
                    )
            except (json.JSONDecodeError, TypeError):
                pass

    if pending_fixed:
        logger.info(f"Fixed {pending_fixed} pending_systems with incorrect galaxy names")

    if not total_fixed and not pending_fixed:
        logger.info("No Galaxy_N entries found - already clean")

    conn.commit()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.45.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.45.0")


# Data fix: resolve "Unknown(N)" star_type values caused by wrong STAR_TYPES enum ordering.
@register_migration("1.47.0", "Fix Unknown(N) star colors from wrong STAR_TYPES enum mapping")
def migrate_1_46_0(conn):
    """Fix star_type values corrupted by the wrong STAR_TYPES enum mapping.

    The extractor's STAR_TYPES dict had incorrect ordering (1=Red, 2=Green, 3=Blue)
    instead of matching the game's cGcGalaxyStarTypes enum (1=Green, 2=Blue, 3=Red, 4=Purple).
    This caused:
      - "Unknown(4)" for Purple stars (value 4 was missing entirely)
      - Potentially swapped Red/Green/Blue for values 1-3

    This migration cleans up:
      1. "Unknown(N)" pattern values in systems.star_type → correct color name
      2. Same pattern in pending_systems system_data JSON (star_color and star_type fields)
    """
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    import re

    # cGcGalaxyStarTypes enum (authoritative from NMS.py)
    ENUM_TO_COLOR = {
        0: "Yellow", 1: "Green", 2: "Blue", 3: "Red", 4: "Purple"
    }

    # --- Fix systems table ---
    cursor.execute("""
        SELECT id, name, star_type FROM systems
        WHERE star_type LIKE 'Unknown(%'
    """)
    systems = cursor.fetchall()
    sys_fixed = 0

    for system in systems:
        match = re.match(r'Unknown\((\d+)\)', system['star_type'] or '')
        if match:
            raw_val = int(match.group(1))
            correct_color = ENUM_TO_COLOR.get(raw_val)
            if correct_color:
                cursor.execute("UPDATE systems SET star_type = ? WHERE id = ?",
                               (correct_color, system['id']))
                sys_fixed += 1
                logger.info(f"  Fixed system '{system['name']}': '{system['star_type']}' -> '{correct_color}'")

    if sys_fixed:
        conn.commit()
        logger.info(f"Fixed {sys_fixed} systems with Unknown(N) star_type")
    else:
        logger.info("No systems with Unknown(N) star_type found")

    # --- Fix pending_systems JSON ---
    cursor.execute("""
        SELECT id, system_data FROM pending_systems
        WHERE system_data IS NOT NULL AND system_data != ''
    """)
    pending_rows = cursor.fetchall()
    pending_fixed = 0

    for row in pending_rows:
        try:
            data = json.loads(row['system_data'])
            changed = False

            for field in ('star_color', 'star_type'):
                val = data.get(field, '')
                match = re.match(r'Unknown\((\d+)\)', val or '')
                if match:
                    raw_val = int(match.group(1))
                    correct_color = ENUM_TO_COLOR.get(raw_val)
                    if correct_color:
                        data[field] = correct_color
                        changed = True

            if changed:
                cursor.execute(
                    "UPDATE pending_systems SET system_data = ? WHERE id = ?",
                    (json.dumps(data), row['id'])
                )
                pending_fixed += 1
        except (json.JSONDecodeError, TypeError):
            continue

    if pending_fixed:
        conn.commit()
        logger.info(f"Fixed {pending_fixed} pending_systems with Unknown(N) star colors")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.47.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.47.0")


@register_migration("1.48.0", "Add thumbnail column to war_media for WebP thumbnail persistence")
def migration_1_48_0(conn):
    cursor = conn.cursor()

    # Add thumbnail column
    cursor.execute("PRAGMA table_info(war_media)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'thumbnail' not in columns:
        cursor.execute("ALTER TABLE war_media ADD COLUMN thumbnail TEXT")
        logger.info("Added thumbnail column to war_media")

    # Backfill: any existing .webp entries should have a _thumb.webp on disk
    cursor.execute("SELECT id, filename FROM war_media WHERE filename LIKE '%.webp' AND thumbnail IS NULL")
    rows = cursor.fetchall()
    updated = 0
    for row in rows:
        stem = row[1].replace('.webp', '')
        thumb = f"{stem}_thumb.webp"
        cursor.execute("UPDATE war_media SET thumbnail = ? WHERE id = ?", (thumb, row[0]))
        updated += 1
    if updated:
        conn.commit()
        logger.info(f"Backfilled thumbnail for {updated} existing war_media entries")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.48.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.48.0")


@register_migration("1.49.0", "Rebuild regions UNIQUE constraint to include reality+galaxy for multi-dimension scoping")
def migration_1_49_0(conn):
    """
    The regions table had UNIQUE(region_x, region_y, region_z) which doesn't account
    for different realities/galaxies sharing the same XYZ coordinates. Rebuild to
    UNIQUE(reality, galaxy, region_x, region_y, region_z).

    Also add a unique partial index on pending_region_names to prevent duplicate
    pending submissions per reality+galaxy+region combo.
    """
    cursor = conn.cursor()

    # --- Rebuild regions table with new UNIQUE constraint ---
    # SQLite doesn't support ALTER CONSTRAINT, so we rebuild the table
    logger.info("Rebuilding regions table with reality+galaxy in UNIQUE constraint...")

    # Clean up any leftover regions_new from a previous failed attempt
    cursor.execute("DROP TABLE IF EXISTS regions_new")

    # 1. Create new table with correct constraint
    # Dynamically detect columns to handle both local dev and production Pi schemas
    cursor.execute("PRAGMA table_info(regions)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_x INTEGER NOT NULL,
            region_y INTEGER NOT NULL,
            region_z INTEGER NOT NULL,
            custom_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            discord_tag TEXT,
            reality TEXT DEFAULT 'Normal',
            galaxy TEXT DEFAULT 'Euclid',
            UNIQUE(reality, galaxy, region_x, region_y, region_z),
            UNIQUE(custom_name)
        )
    ''')

    # 2. Copy data from old table (only columns that exist in both tables)
    copy_cols = ['id', 'region_x', 'region_y', 'region_z', 'custom_name',
                 'created_at', 'updated_at', 'discord_tag']
    select_exprs = list(copy_cols)
    # reality and galaxy may have NULL defaults, coalesce them
    if 'reality' in existing_cols:
        copy_cols.append('reality')
        select_exprs.append("COALESCE(reality, 'Normal')")
    else:
        copy_cols.append('reality')
        select_exprs.append("'Normal'")
    if 'galaxy' in existing_cols:
        copy_cols.append('galaxy')
        select_exprs.append("COALESCE(galaxy, 'Euclid')")
    else:
        copy_cols.append('galaxy')
        select_exprs.append("'Euclid'")

    cols_str = ', '.join(copy_cols)
    select_str = ', '.join(select_exprs)
    cursor.execute(f'''
        INSERT OR IGNORE INTO regions_new ({cols_str})
        SELECT {select_str} FROM regions
    ''')
    cursor.execute('SELECT COUNT(*) FROM regions_new')
    count = cursor.fetchone()[0]
    logger.info(f"Copied {count} regions to new table")

    # 3. Drop old table and rename
    cursor.execute('DROP TABLE regions')
    cursor.execute('ALTER TABLE regions_new RENAME TO regions')
    logger.info("Rebuilt regions table with UNIQUE(reality, galaxy, region_x, region_y, region_z)")

    # --- Add index on pending_region_names for reality+galaxy scoped lookups ---
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_pending_region_names_scoped
        ON pending_region_names(region_x, region_y, region_z, reality, galaxy, status)
    ''')
    logger.info("Added scoped index on pending_region_names")

    # --- Add index on regions for fast lookups ---
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_regions_coords_scoped
        ON regions(region_x, region_y, region_z, reality, galaxy)
    ''')
    logger.info("Added scoped index on regions")

    conn.commit()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.49.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.49.0")


@register_migration("1.50.0", "Add is_gas_giant column to planets and moons tables")
def migration_1_50_0(conn):
    """
    Add is_gas_giant INTEGER column (0/1) to planets and moons tables.
    Gas Giant is a special planet attribute like has_rings or is_dissonant.
    """
    cursor = conn.cursor()

    # Add to planets
    cursor.execute("PRAGMA table_info(planets)")
    planet_cols = {row[1] for row in cursor.fetchall()}
    if 'is_gas_giant' not in planet_cols:
        cursor.execute("ALTER TABLE planets ADD COLUMN is_gas_giant INTEGER DEFAULT 0")
        logger.info("Added is_gas_giant column to planets table")
    else:
        logger.info("is_gas_giant already exists on planets table")

    # Add to moons
    cursor.execute("PRAGMA table_info(moons)")
    moon_cols = {row[1] for row in cursor.fetchall()}
    if 'is_gas_giant' not in moon_cols:
        cursor.execute("ALTER TABLE moons ADD COLUMN is_gas_giant INTEGER DEFAULT 0")
        logger.info("Added is_gas_giant column to moons table")
    else:
        logger.info("is_gas_giant already exists on moons table")

    conn.commit()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.50.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.50.0")


@register_migration("1.51.0", "Backfill created_at on systems for Travelers Collective incremental sync")
def migration_1_51_0(conn):
    """
    The Collective's sync uses updated_since which filters on created_at/last_updated_at.
    Most systems have NULL created_at because the approve_system INSERT never set it explicitly
    and the DEFAULT CURRENT_TIMESTAMP was lost during table rebuilds.

    Backfill using: discovered_at (most accurate) → submission_date from audit log → NOW().
    """
    cursor = conn.cursor()

    # Count how many need backfill
    cursor.execute("SELECT COUNT(*) FROM systems WHERE created_at IS NULL")
    null_count = cursor.fetchone()[0]
    logger.info(f"Systems with NULL created_at: {null_count}")

    if null_count == 0:
        logger.info("No systems need created_at backfill — skipping")
    else:
        # Layer 1: Use discovered_at where available
        cursor.execute("""
            UPDATE systems SET created_at = discovered_at
            WHERE created_at IS NULL AND discovered_at IS NOT NULL
        """)
        layer1 = cursor.rowcount
        logger.info(f"Backfilled {layer1} systems from discovered_at")

        # Layer 2: Use approval_audit_log timestamp for remaining
        cursor.execute("""
            UPDATE systems SET created_at = (
                SELECT MIN(a.timestamp)
                FROM approval_audit_log a
                WHERE CAST(a.submission_id AS TEXT) = CAST(systems.id AS TEXT)
                  AND a.action IN ('approve_system', 'approved')
            )
            WHERE created_at IS NULL AND EXISTS (
                SELECT 1 FROM approval_audit_log a
                WHERE CAST(a.submission_id AS TEXT) = CAST(systems.id AS TEXT)
                  AND a.action IN ('approve_system', 'approved')
            )
        """)
        layer2 = cursor.rowcount
        logger.info(f"Backfilled {layer2} systems from approval_audit_log")

        # Layer 3: Fallback to NOW() for any remaining
        cursor.execute("""
            UPDATE systems SET created_at = ?
            WHERE created_at IS NULL
        """, (datetime.now().isoformat(),))
        layer3 = cursor.rowcount
        logger.info(f"Backfilled {layer3} systems with current timestamp (fallback)")

        conn.commit()
        logger.info(f"Total backfilled: {layer1 + layer2 + layer3} systems")

    # Also add index on created_at for efficient updated_since queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_created_at ON systems(created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_last_updated_at ON systems(last_updated_at DESC)")
    logger.info("Ensured indexes on systems.created_at and systems.last_updated_at")

    conn.commit()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.51.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.51.0")


# =============================================================================
# v1.52.0 - Add game_mode column to track difficulty preset for adjective context
# =============================================================================
@register_migration("1.52.0", "Add game_mode column to systems and pending_systems for difficulty tracking")
def migration_1_52_0(conn):
    """
    Track which game mode (Normal, Creative, Relaxed, Survival, Permadeath, Custom)
    produced the adjective data (biome, weather, sentinel). Sentinel adjectives
    change per difficulty, and the game writes different values into biome/weather
    fields depending on the active mode.
    """
    cursor = conn.cursor()

    # Add game_mode to systems table
    try:
        cursor.execute("ALTER TABLE systems ADD COLUMN game_mode TEXT DEFAULT 'Normal'")
        logger.info("Added game_mode column to systems table")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            logger.info("game_mode column already exists in systems")
        else:
            raise

    # Add game_mode to pending_systems table
    try:
        cursor.execute("ALTER TABLE pending_systems ADD COLUMN game_mode TEXT DEFAULT 'Normal'")
        logger.info("Added game_mode column to pending_systems table")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            logger.info("game_mode column already exists in pending_systems")
        else:
            raise

    conn.commit()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.52.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.52.0")


@register_migration("1.53.0", "Clean garbage resource values from planets and moons tables")
def migration_1_53_0(conn):
    """
    Extractor submissions could store raw memory bytes in common_resource,
    uncommon_resource, rare_resource columns because the extraction endpoint
    only checked len >= 2 but not that the value was alphabetic. This migration
    NULLs out any resource values that start with a non-alpha character.
    """
    cursor = conn.cursor()

    cleaned = 0
    for table in ['planets', 'moons']:
        for col in ['common_resource', 'uncommon_resource', 'rare_resource']:
            try:
                cursor.execute(f"""
                    UPDATE {table} SET {col} = NULL
                    WHERE {col} IS NOT NULL
                    AND (LENGTH({col}) < 2 OR SUBSTR({col}, 1, 1) NOT GLOB '[A-Za-z]')
                """)
                count = cursor.rowcount
                if count > 0:
                    cleaned += count
                    logger.info(f"Cleaned {count} garbage {col} values from {table}")
            except Exception as e:
                logger.warning(f"Could not clean {col} in {table}: {e}")

    if cleaned > 0:
        logger.info(f"Total garbage resource values cleaned: {cleaned}")
    else:
        logger.info("No garbage resource values found")

    conn.commit()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.53.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.53.0")


@register_migration("1.54.0", "Remove UNIQUE constraint on systems.name, replace glyph UNIQUE with canonical dedup index")
def migration_1_54_0(conn):
    """
    The systems table was created with `name TEXT NOT NULL UNIQUE` which prevents
    same-named systems in different galaxies/realities — a legitimate NMS scenario.

    System identity is now based on canonical glyph dedup:
    last 11 glyph chars + galaxy + reality (not name, not exact glyph).

    This migration:
    1. Rebuilds systems table without UNIQUE on name
    2. Drops the old exact glyph_code UNIQUE index
    3. Adds a new canonical dedup index on (SUBSTR(glyph_code, -11), galaxy, reality)
    """
    cursor = conn.cursor()

    logger.info("Rebuilding systems table to remove UNIQUE constraint on name...")

    # Get current column list dynamically
    cursor.execute("PRAGMA table_info(systems)")
    columns = [row[1] for row in cursor.fetchall()]
    logger.info(f"Systems table has {len(columns)} columns")

    # Drop any leftover temp table
    cursor.execute("DROP TABLE IF EXISTS systems_new")

    # Build CREATE TABLE without UNIQUE on name
    # We need to get the full schema and modify it
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='systems'")
    original_sql = cursor.fetchone()[0]

    # Replace "name TEXT NOT NULL UNIQUE" with "name TEXT NOT NULL"
    new_sql = original_sql.replace(
        'name TEXT NOT NULL UNIQUE',
        'name TEXT NOT NULL'
    )
    # Change table name to systems_new
    new_sql = new_sql.replace('CREATE TABLE "systems"', 'CREATE TABLE "systems_new"', 1)
    if 'systems_new' not in new_sql:
        new_sql = new_sql.replace('CREATE TABLE systems', 'CREATE TABLE systems_new', 1)

    logger.info("Creating systems_new without UNIQUE on name...")
    cursor.execute(new_sql)

    # Copy all data
    cols_str = ', '.join(columns)
    cursor.execute(f'INSERT INTO systems_new ({cols_str}) SELECT {cols_str} FROM systems')
    cursor.execute('SELECT COUNT(*) FROM systems_new')
    count = cursor.fetchone()[0]
    logger.info(f"Copied {count} systems to new table")

    # Drop old table and rename
    cursor.execute('DROP TABLE systems')
    cursor.execute('ALTER TABLE systems_new RENAME TO systems')
    logger.info("Rebuilt systems table without UNIQUE on name")

    # Drop old exact glyph_code UNIQUE index (no longer correct for dedup)
    cursor.execute("DROP INDEX IF EXISTS idx_systems_glyph")
    logger.info("Dropped old idx_systems_glyph UNIQUE index")

    # Recreate all needed indexes (they were dropped with the table)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_systems_name ON systems(name)",
        "CREATE INDEX IF NOT EXISTS idx_systems_coords ON systems(x, y, z)",
        "CREATE INDEX IF NOT EXISTS idx_systems_galaxy ON systems(galaxy)",
        "CREATE INDEX IF NOT EXISTS idx_systems_star_coords ON systems(star_x, star_y, star_z)",
        "CREATE INDEX IF NOT EXISTS idx_systems_discord_tag ON systems(discord_tag)",
        "CREATE INDEX IF NOT EXISTS idx_systems_region ON systems(region_x, region_y, region_z)",
        "CREATE INDEX IF NOT EXISTS idx_systems_glyph_code ON systems(glyph_code)",
        "CREATE INDEX IF NOT EXISTS idx_systems_created_at ON systems(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_systems_reality ON systems(reality)",
        "CREATE INDEX IF NOT EXISTS idx_systems_hierarchy ON systems(reality, galaxy, region_x, region_y, region_z)",
        "CREATE INDEX IF NOT EXISTS idx_systems_reality_galaxy ON systems(reality, galaxy)",
        "CREATE INDEX IF NOT EXISTS idx_systems_discord_created ON systems(discord_tag, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_systems_star_type ON systems(star_type)",
        "CREATE INDEX IF NOT EXISTS idx_systems_economy_type ON systems(economy_type)",
        "CREATE INDEX IF NOT EXISTS idx_systems_conflict_level ON systems(conflict_level)",
        "CREATE INDEX IF NOT EXISTS idx_systems_dominant_lifeform ON systems(dominant_lifeform)",
        "CREATE INDEX IF NOT EXISTS idx_systems_stellar_classification ON systems(stellar_classification)",
        "CREATE INDEX IF NOT EXISTS idx_systems_is_complete ON systems(is_complete)",
        "CREATE INDEX IF NOT EXISTS idx_systems_is_stub ON systems(is_stub)",
        "CREATE INDEX IF NOT EXISTS idx_systems_completeness ON systems(is_complete)",
    ]
    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")

    logger.info("Recreated all system indexes")

    conn.commit()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='_metadata'
    """)
    if cursor.fetchone():
        cursor.execute("""
            UPDATE _metadata SET value = '1.54.0', updated_at = ?
            WHERE key = 'version'
        """, (datetime.now().isoformat(),))
        logger.info("Updated _metadata version to 1.54.0")


@register_migration("1.55.0", "Unified user profiles table - single identity source for all users")
def migration_1_55_0(conn):
    """
    Creates the user_profiles table as the single source of truth for all user identity.
    Replaces the fragmented identity system (partner_accounts, sub_admin_accounts,
    super_admin_settings, api_keys.discord_username, anonymous submitted_by fields).

    Tier system:
      1 = Super Admin
      2 = Partner (community leader)
      3 = Sub-Admin (delegated by partner)
      4 = Member (has password, can edit profile)
      5 = Member readonly (no password, view-only)
    """
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            username_normalized TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            display_name TEXT,
            default_civ_tag TEXT,
            discord_snowflake_id TEXT,
            tier INTEGER NOT NULL DEFAULT 5,
            partner_discord_tag TEXT UNIQUE,
            enabled_features TEXT DEFAULT '[]',
            theme_settings TEXT DEFAULT '{}',
            region_color TEXT DEFAULT '#00C2B3',
            parent_profile_id INTEGER,
            additional_discord_tags TEXT DEFAULT '[]',
            can_approve_personal_uploads INTEGER DEFAULT 0,
            default_reality TEXT,
            default_galaxy TEXT,
            api_key_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY (parent_profile_id) REFERENCES user_profiles(id) ON DELETE SET NULL
        )
    ''')
    logger.info("Created user_profiles table")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_profiles_username_norm ON user_profiles(username_normalized)",
        "CREATE INDEX IF NOT EXISTS idx_profiles_tier ON user_profiles(tier)",
        "CREATE INDEX IF NOT EXISTS idx_profiles_partner_tag ON user_profiles(partner_discord_tag)",
        "CREATE INDEX IF NOT EXISTS idx_profiles_parent ON user_profiles(parent_profile_id)",
        "CREATE INDEX IF NOT EXISTS idx_profiles_discord_snowflake ON user_profiles(discord_snowflake_id)",
        "CREATE INDEX IF NOT EXISTS idx_profiles_default_civ ON user_profiles(default_civ_tag)",
        "CREATE INDEX IF NOT EXISTS idx_profiles_active ON user_profiles(is_active)",
    ]
    for idx_sql in indexes:
        cursor.execute(idx_sql)
    logger.info("Created user_profiles indexes")

    conn.commit()


@register_migration("1.56.0", "Add profile_id foreign key columns to existing tables")
def migration_1_56_0(conn):
    """
    Adds nullable profile_id columns to all tables that track user identity.
    These will be backfilled in migration 1.57.0 after profiles are created.
    """
    cursor = conn.cursor()

    def add_col(table, column, coltype="INTEGER"):
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cursor.fetchall()]
        if column not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
            logger.info(f"Added {column} to {table}")

    # Systems - who submitted/created
    add_col('systems', 'profile_id')

    # Pending systems - who submitted for approval
    add_col('pending_systems', 'submitter_profile_id')

    # Discoveries - who discovered
    add_col('discoveries', 'profile_id')

    # Pending discoveries - who submitted
    add_col('pending_discoveries', 'submitter_profile_id')

    # Pending region names - who proposed
    add_col('pending_region_names', 'submitter_profile_id')

    # Audit log - who approved and who submitted
    add_col('approval_audit_log', 'approver_profile_id')
    add_col('approval_audit_log', 'submitter_profile_id')

    # API keys - link to profile
    add_col('api_keys', 'profile_id')

    # Create indexes for profile_id lookups
    index_pairs = [
        ('idx_systems_profile', 'systems', 'profile_id'),
        ('idx_pending_systems_profile', 'pending_systems', 'submitter_profile_id'),
        ('idx_discoveries_profile', 'discoveries', 'profile_id'),
        ('idx_pending_discoveries_profile', 'pending_discoveries', 'submitter_profile_id'),
        ('idx_pending_regions_profile', 'pending_region_names', 'submitter_profile_id'),
        ('idx_audit_approver_profile', 'approval_audit_log', 'approver_profile_id'),
        ('idx_audit_submitter_profile', 'approval_audit_log', 'submitter_profile_id'),
        ('idx_api_keys_profile', 'api_keys', 'profile_id'),
    ]
    for idx_name, table, col in index_pairs:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({col})")
        except Exception as e:
            logger.warning(f"Index {idx_name} warning: {e}")

    logger.info("Added profile_id columns and indexes to 8 tables")
    conn.commit()


@register_migration("1.57.0", "Backfill user profiles from existing accounts and submissions")
def migration_1_57_0(conn):
    """
    Populates user_profiles from all existing identity sources:
    1. Super admin -> tier 1
    2. partner_accounts -> tier 2
    3. sub_admin_accounts -> tier 3
    4. api_keys (extractor) -> tier 5
    5. Anonymous submitters from all tables -> tier 5
    """
    import sqlite3
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    def normalize_for_dedup(username):
        """Normalize username for dedup: lowercase, strip whitespace/#/trailing 4-digit discriminator."""
        if not username:
            return ''
        n = username.strip().lower().replace('#', '')
        if len(n) > 4 and n[-4:].isdigit():
            prefix = n[:-4]
            if prefix and not prefix[-1].isdigit():
                n = prefix
        return n

    def insert_profile(username, normalized, password_hash, display_name, tier,
                        partner_discord_tag=None, enabled_features='[]',
                        theme_settings='{}', region_color='#00C2B3',
                        parent_profile_id=None, additional_discord_tags='[]',
                        can_approve_personal=0, created_by=None,
                        is_active=1, last_login_at=None, api_key_id=None):
        """Insert a profile, skipping if normalized username already exists."""
        cursor.execute("SELECT id FROM user_profiles WHERE username_normalized = ?", (normalized,))
        if cursor.fetchone():
            return None  # Already exists
        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO user_profiles (
                username, username_normalized, password_hash, display_name, tier,
                partner_discord_tag, enabled_features, theme_settings, region_color,
                parent_profile_id, additional_discord_tags, can_approve_personal_uploads,
                is_active, created_at, updated_at, last_login_at, created_by, api_key_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            username, normalized, password_hash, display_name, tier,
            partner_discord_tag, enabled_features, theme_settings, region_color,
            parent_profile_id, additional_discord_tags, can_approve_personal,
            is_active, now, now, last_login_at, created_by, api_key_id
        ))
        return cursor.lastrowid

    # Track old ID -> new profile ID mappings
    partner_id_map = {}
    created_count = 0

    # Step 1: Super admin
    cursor.execute("SELECT value FROM super_admin_settings WHERE key = 'password_hash'")
    sa_row = cursor.fetchone()
    sa_hash = sa_row['value'] if sa_row else None
    pid = insert_profile('Haven', 'haven', sa_hash, 'Super Admin', 1,
                          enabled_features='["all"]', created_by='migration')
    if pid:
        created_count += 1
        logger.info(f"Created super admin profile (id={pid})")

    # Step 2: Partner accounts -> tier 2
    cursor.execute('''
        SELECT id, username, password_hash, discord_tag, display_name, enabled_features,
               theme_settings, region_color, is_active, last_login_at, created_by
        FROM partner_accounts
    ''')
    for row in cursor.fetchall():
        row = dict(row)
        normalized = normalize_for_dedup(row['username'])
        if not normalized:
            continue
        pid = insert_profile(
            row['username'], normalized, row['password_hash'],
            row['display_name'], 2,
            partner_discord_tag=row['discord_tag'],
            enabled_features=row['enabled_features'] or '[]',
            theme_settings=row['theme_settings'] or '{}',
            region_color=row['region_color'] or '#00C2B3',
            is_active=row['is_active'] or 1,
            last_login_at=row['last_login_at'],
            created_by=row.get('created_by') or 'migration'
        )
        if pid:
            partner_id_map[row['id']] = pid
            created_count += 1
        else:
            # Profile already existed (e.g. username collision with super admin)
            cursor.execute("SELECT id FROM user_profiles WHERE username_normalized = ?", (normalized,))
            existing = cursor.fetchone()
            if existing:
                partner_id_map[row['id']] = existing['id']

    logger.info(f"Migrated {len(partner_id_map)} partner accounts to profiles")

    # Step 3: Sub-admin accounts -> tier 3
    sub_count = 0
    cursor.execute('''
        SELECT id, parent_partner_id, username, password_hash, display_name,
               enabled_features, is_active, last_login_at, created_by,
               additional_discord_tags, can_approve_personal_uploads
        FROM sub_admin_accounts
    ''')
    for row in cursor.fetchall():
        row = dict(row)
        normalized = normalize_for_dedup(row['username'])
        if not normalized:
            continue
        parent_pid = partner_id_map.get(row['parent_partner_id'])
        pid = insert_profile(
            row['username'], normalized, row['password_hash'],
            row['display_name'], 3,
            parent_profile_id=parent_pid,
            enabled_features=row['enabled_features'] or '[]',
            additional_discord_tags=row.get('additional_discord_tags') or '[]',
            can_approve_personal=row.get('can_approve_personal_uploads') or 0,
            is_active=row['is_active'] or 1,
            last_login_at=row['last_login_at'],
            created_by=row.get('created_by') or 'migration'
        )
        if pid:
            sub_count += 1
            created_count += 1

    logger.info(f"Migrated {sub_count} sub-admin accounts to profiles")

    # Step 4: Extractor API keys -> tier 5
    ext_count = 0
    cursor.execute('''
        SELECT id, discord_username
        FROM api_keys
        WHERE key_type = 'extractor' AND discord_username IS NOT NULL AND discord_username != ''
    ''')
    for row in cursor.fetchall():
        row = dict(row)
        normalized = normalize_for_dedup(row['discord_username'])
        if not normalized:
            continue
        pid = insert_profile(
            row['discord_username'], normalized, None,
            row['discord_username'], 5,
            created_by='extractor_migration',
            api_key_id=row['id']
        )
        if pid:
            cursor.execute("UPDATE api_keys SET profile_id = ? WHERE id = ?", (pid, row['id']))
            ext_count += 1
            created_count += 1
        else:
            # Profile existed, link api key to it
            cursor.execute("SELECT id FROM user_profiles WHERE username_normalized = ?", (normalized,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE api_keys SET profile_id = ? WHERE id = ?", (existing['id'], row['id']))

    logger.info(f"Migrated {ext_count} extractor users to profiles, linked API keys")

    # Step 5: Scan all anonymous submitter usernames across tables
    anon_count = 0
    username_sources = []

    # Gather distinct usernames from all relevant tables
    for query in [
        "SELECT DISTINCT personal_discord_username AS u FROM pending_systems WHERE personal_discord_username IS NOT NULL AND personal_discord_username != ''",
        "SELECT DISTINCT submitted_by AS u FROM pending_systems WHERE submitted_by IS NOT NULL AND submitted_by != '' AND submitted_by != 'Anonymous' AND submitted_by != 'anonymous'",
        "SELECT DISTINCT personal_discord_username AS u FROM systems WHERE personal_discord_username IS NOT NULL AND personal_discord_username != ''",
        "SELECT DISTINCT discovered_by AS u FROM systems WHERE discovered_by IS NOT NULL AND discovered_by != '' AND discovered_by != 'Anonymous' AND discovered_by != 'anonymous'",
        "SELECT DISTINCT submitted_by AS u FROM pending_region_names WHERE submitted_by IS NOT NULL AND submitted_by != '' AND submitted_by != 'Anonymous' AND submitted_by != 'anonymous'",
        "SELECT DISTINCT personal_discord_username AS u FROM pending_region_names WHERE personal_discord_username IS NOT NULL AND personal_discord_username != ''",
        "SELECT DISTINCT discovered_by AS u FROM discoveries WHERE discovered_by IS NOT NULL AND discovered_by != '' AND discovered_by != 'Anonymous' AND discovered_by != 'anonymous'",
        "SELECT DISTINCT submitted_by AS u FROM pending_discoveries WHERE submitted_by IS NOT NULL AND submitted_by != '' AND submitted_by != 'Anonymous' AND submitted_by != 'anonymous'",
    ]:
        try:
            cursor.execute(query)
            for r in cursor.fetchall():
                if r['u']:
                    username_sources.append(r['u'])
        except Exception as e:
            logger.warning(f"Skipping username source query: {e}")

    # Deduplicate by normalized form
    seen_normalized = set()
    cursor.execute("SELECT username_normalized FROM user_profiles")
    for r in cursor.fetchall():
        seen_normalized.add(r['username_normalized'])

    for raw_username in username_sources:
        normalized = normalize_for_dedup(raw_username)
        if not normalized or normalized in seen_normalized:
            continue
        seen_normalized.add(normalized)
        pid = insert_profile(
            raw_username, normalized, None,
            raw_username, 5,
            created_by='submission_migration'
        )
        if pid:
            anon_count += 1
            created_count += 1

    logger.info(f"Created {anon_count} profiles from anonymous submitter usernames")
    logger.info(f"Total profiles created: {created_count}")

    conn.commit()


@register_migration("1.58.0", "Backfill profile_id on systems, pending_systems, discoveries, and other tables")
def migration_1_58_0(conn):
    """
    Links existing rows in systems, pending_systems, discoveries, etc. to their
    user_profiles by matching normalized usernames. Uses the same COALESCE chain
    as the analytics leaderboard queries.
    """
    import sqlite3
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    def normalize_for_dedup(username):
        if not username:
            return ''
        n = username.strip().lower().replace('#', '')
        if len(n) > 4 and n[-4:].isdigit():
            prefix = n[:-4]
            if prefix and not prefix[-1].isdigit():
                n = prefix
        return n

    # Build a lookup dict: normalized_username -> profile_id
    cursor.execute("SELECT id, username_normalized FROM user_profiles")
    profile_lookup = {row['username_normalized']: row['id'] for row in cursor.fetchall()}

    def find_profile(username):
        if not username:
            return None
        n = normalize_for_dedup(username)
        return profile_lookup.get(n)

    total_updated = 0

    # 1. systems.profile_id from personal_discord_username or discovered_by
    cursor.execute("""
        SELECT id, personal_discord_username, discovered_by
        FROM systems WHERE profile_id IS NULL
    """)
    for row in cursor.fetchall():
        pid = find_profile(row['personal_discord_username']) or find_profile(row['discovered_by'])
        if pid:
            cursor.execute("UPDATE systems SET profile_id = ? WHERE id = ?", (pid, row['id']))
            total_updated += 1
    logger.info(f"Backfilled profile_id on {total_updated} systems rows")

    # 2. pending_systems.submitter_profile_id
    count = 0
    cursor.execute("""
        SELECT id, personal_discord_username, submitted_by, system_data
        FROM pending_systems WHERE submitter_profile_id IS NULL
    """)
    for row in cursor.fetchall():
        row = dict(row)
        pid = find_profile(row['personal_discord_username']) or find_profile(row['submitted_by'])
        if not pid and row.get('system_data'):
            try:
                sd = json.loads(row['system_data'])
                pid = find_profile(sd.get('discovered_by'))
            except Exception:
                pass
        if pid:
            cursor.execute("UPDATE pending_systems SET submitter_profile_id = ? WHERE id = ?", (pid, row['id']))
            count += 1
    total_updated += count
    logger.info(f"Backfilled submitter_profile_id on {count} pending_systems rows")

    # 3. discoveries.profile_id
    count = 0
    cursor.execute("""
        SELECT id, discovered_by FROM discoveries WHERE profile_id IS NULL
    """)
    for row in cursor.fetchall():
        pid = find_profile(row['discovered_by'])
        if pid:
            cursor.execute("UPDATE discoveries SET profile_id = ? WHERE id = ?", (pid, row['id']))
            count += 1
    total_updated += count
    logger.info(f"Backfilled profile_id on {count} discoveries rows")

    # 4. pending_discoveries.submitter_profile_id
    count = 0
    try:
        cursor.execute("""
            SELECT id, submitted_by FROM pending_discoveries WHERE submitter_profile_id IS NULL
        """)
        for row in cursor.fetchall():
            pid = find_profile(row['submitted_by'])
            if pid:
                cursor.execute("UPDATE pending_discoveries SET submitter_profile_id = ? WHERE id = ?", (pid, row['id']))
                count += 1
        total_updated += count
        logger.info(f"Backfilled submitter_profile_id on {count} pending_discoveries rows")
    except Exception as e:
        logger.warning(f"Skipping pending_discoveries backfill: {e}")

    # 5. pending_region_names.submitter_profile_id
    count = 0
    try:
        cursor.execute("""
            SELECT id, submitted_by, personal_discord_username
            FROM pending_region_names WHERE submitter_profile_id IS NULL
        """)
        for row in cursor.fetchall():
            pid = find_profile(row['personal_discord_username']) or find_profile(row['submitted_by'])
            if pid:
                cursor.execute("UPDATE pending_region_names SET submitter_profile_id = ? WHERE id = ?", (pid, row['id']))
                count += 1
        total_updated += count
        logger.info(f"Backfilled submitter_profile_id on {count} pending_region_names rows")
    except Exception as e:
        logger.warning(f"Skipping pending_region_names backfill: {e}")

    # 6. approval_audit_log - approver and submitter profile IDs
    count = 0
    try:
        cursor.execute("""
            SELECT id, approver_username, submitter_username
            FROM approval_audit_log
            WHERE approver_profile_id IS NULL OR submitter_profile_id IS NULL
        """)
        for row in cursor.fetchall():
            approver_pid = find_profile(row['approver_username'])
            submitter_pid = find_profile(row['submitter_username'])
            if approver_pid or submitter_pid:
                cursor.execute("""
                    UPDATE approval_audit_log
                    SET approver_profile_id = COALESCE(approver_profile_id, ?),
                        submitter_profile_id = COALESCE(submitter_profile_id, ?)
                    WHERE id = ?
                """, (approver_pid, submitter_pid, row['id']))
                count += 1
        total_updated += count
        logger.info(f"Backfilled profile IDs on {count} audit log rows")
    except Exception as e:
        logger.warning(f"Skipping audit log backfill: {e}")

    logger.info(f"Total rows updated with profile_id: {total_updated}")
    conn.commit()


@register_migration("1.59.0", "Add source column to systems table, backfill from pending_systems")
def migration_1_59_0(conn):
    """
    Add upload source tracking to approved systems so the Profile page
    can split submissions by manual vs extractor.
    """
    cursor = conn.cursor()

    # Add source column to systems table
    try:
        cursor.execute("ALTER TABLE systems ADD COLUMN source TEXT DEFAULT 'manual'")
        logger.info("Added source column to systems table")
    except Exception:
        logger.info("source column already exists on systems")

    # Backfill from pending_systems where we have a match
    cursor.execute("""
        UPDATE systems SET source = (
            SELECT COALESCE(ps.source, 'manual')
            FROM pending_systems ps
            WHERE (
                ps.status = 'approved'
                AND (
                    (ps.system_name IS NOT NULL AND ps.system_name = systems.name AND ps.galaxy = systems.galaxy)
                    OR (ps.submitter_profile_id IS NOT NULL AND ps.submitter_profile_id = systems.profile_id
                        AND ps.system_name = systems.name)
                )
            )
            ORDER BY ps.id DESC LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM pending_systems ps
            WHERE ps.status = 'approved'
            AND (
                (ps.system_name IS NOT NULL AND ps.system_name = systems.name AND ps.galaxy = systems.galaxy)
                OR (ps.submitter_profile_id IS NOT NULL AND ps.submitter_profile_id = systems.profile_id
                    AND ps.system_name = systems.name)
            )
        )
    """)
    backfilled = cursor.rowcount
    logger.info(f"Backfilled source on {backfilled} systems from pending_systems")
    conn.commit()


@register_migration("1.60.0", "Backfill submitted_by from personal_discord_username where NULL or anonymous")
def migration_1_60_0(conn):
    """
    Fix 'Anonymous' display on pending submissions and region names by copying
    personal_discord_username to submitted_by where it's missing.
    """
    cursor = conn.cursor()

    # Fix pending_systems
    cursor.execute("""
        UPDATE pending_systems
        SET submitted_by = personal_discord_username
        WHERE personal_discord_username IS NOT NULL
          AND personal_discord_username != ''
          AND (submitted_by IS NULL OR submitted_by = '' OR submitted_by = 'Anonymous' OR submitted_by = 'anonymous')
    """)
    ps_count = cursor.rowcount
    logger.info(f"Backfilled submitted_by on {ps_count} pending_systems rows")

    # Fix pending_region_names
    cursor.execute("""
        UPDATE pending_region_names
        SET submitted_by = personal_discord_username
        WHERE personal_discord_username IS NOT NULL
          AND personal_discord_username != ''
          AND (submitted_by IS NULL OR submitted_by = '' OR submitted_by = 'Anonymous' OR submitted_by = 'anonymous')
    """)
    rn_count = cursor.rowcount
    logger.info(f"Backfilled submitted_by on {rn_count} pending_region_names rows")

    conn.commit()


@register_migration("1.61.0", "Add source column to approval_audit_log for submission method tracking")
def migration_1_61_0(conn):
    """Add source column to track whether audit entries came from manual, extractor, or companion_app."""
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE approval_audit_log ADD COLUMN source TEXT")
        logger.info("Added source column to approval_audit_log")
    except Exception:
        logger.info("source column already exists on approval_audit_log")
    conn.commit()


# =============================================================================
# v1.62.0 - Add is_bubble and is_floating_islands columns to planets and moons
# =============================================================================
@register_migration("1.62.0", "Add is_bubble and is_floating_islands columns to planets and moons")
def migration_1_62_0(conn):
    """
    Track Bubble Planet and Floating Islands planetary attributes.
    These are rare biome features added in NMS Worlds Part updates.
    """
    cursor = conn.cursor()

    for table in ['planets', 'moons']:
        for col in ['is_bubble', 'is_floating_islands']:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER DEFAULT 0")
                logger.info(f"Added {col} column to {table} table")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    logger.info(f"{col} column already exists in {table}")
                else:
                    raise

    conn.commit()


# =============================================================================
# v1.63.0 - Add submitter_profile_id to pending_region_names for profile tracking
# =============================================================================
@register_migration("1.63.0", "Add submitter_profile_id to pending_region_names for profile tracking")
def migration_1_63_0(conn):
    """
    Track which user_profile submitted region name proposals.
    Backfill from personal_discord_username where possible.
    """
    cursor = conn.cursor()

    # Add submitter_profile_id column
    try:
        cursor.execute("ALTER TABLE pending_region_names ADD COLUMN submitter_profile_id INTEGER")
        logger.info("Added submitter_profile_id column to pending_region_names")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            logger.info("submitter_profile_id column already exists in pending_region_names")
        else:
            raise

    # Backfill from user_profiles where personal_discord_username matches
    try:
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='user_profiles'
        """)
        if cursor.fetchone():
            cursor.execute("""
                UPDATE pending_region_names
                SET submitter_profile_id = (
                    SELECT up.id FROM user_profiles up
                    WHERE LOWER(REPLACE(up.username, '#', '')) = LOWER(REPLACE(pending_region_names.personal_discord_username, '#', ''))
                    LIMIT 1
                )
                WHERE personal_discord_username IS NOT NULL
                  AND personal_discord_username != ''
                  AND submitter_profile_id IS NULL
            """)
            backfilled = cursor.rowcount
            logger.info(f"Backfilled submitter_profile_id on {backfilled} pending_region_names rows")
    except Exception as e:
        logger.warning(f"Could not backfill submitter_profile_id: {e}")

    conn.commit()


@register_migration("1.64.0", "Re-normalize username_normalized to strip spaces, underscores, dashes, unicode accents and merge duplicate profiles")
def migration_1_64_0(conn):
    """
    Tighten username normalization: strip spaces, underscores, dashes, and unicode accents.
    Merge profiles that collide under the new normalization (keep lower ID / higher tier).
    Re-backfill profile_id on systems, pending_systems, discoveries.
    """
    import unicodedata
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    def normalize(username):
        if not username:
            return ''
        n = unicodedata.normalize('NFKD', username)
        n = ''.join(ch for ch in n if not unicodedata.combining(ch))
        n = n.strip().lower().replace('#', '').replace(' ', '').replace('_', '').replace('-', '')
        if len(n) > 4 and n[-4:].isdigit():
            prefix = n[:-4]
            if prefix and not prefix[-1].isdigit():
                n = prefix
        return n

    # Find collisions under new normalization
    cursor.execute('SELECT id, username, tier FROM user_profiles ORDER BY tier ASC, id ASC')
    all_profiles = cursor.fetchall()
    norm_map = {}
    merges = []

    for row in all_profiles:
        nn = normalize(row['username'])
        if nn in norm_map:
            keep_id = norm_map[nn][0]
            merges.append((keep_id, row['id']))
        else:
            norm_map[nn] = (row['id'], row['username'], row['tier'])

    # Merge duplicates
    for keep_id, merge_id in merges:
        logger.info(f"Merging profile {merge_id} -> {keep_id}")
        for tbl, col in [('systems', 'profile_id'), ('pending_systems', 'submitter_profile_id'),
                         ('discoveries', 'profile_id'), ('api_keys', 'profile_id'),
                         ('approval_audit_log', 'approver_profile_id'),
                         ('approval_audit_log', 'submitter_profile_id'),
                         ('pending_region_names', 'submitter_profile_id')]:
            try:
                cursor.execute(f'UPDATE {tbl} SET {col} = ? WHERE {col} = ?', (keep_id, merge_id))
            except Exception:
                pass
        cursor.execute('DELETE FROM user_profiles WHERE id = ?', (merge_id,))

    logger.info(f"Merged {len(merges)} duplicate profiles")

    # Update all username_normalized with tighter normalization
    cursor.execute('SELECT id, username FROM user_profiles')
    for row in cursor.fetchall():
        nn = normalize(row['username'])
        cursor.execute('UPDATE user_profiles SET username_normalized = ? WHERE id = ?', (nn, row['id']))

    logger.info("Updated all username_normalized values")

    # Re-backfill profile_id on systems, pending_systems, discoveries
    cursor.execute('SELECT id, username, username_normalized FROM user_profiles')
    profile_lookup = {}
    for row in cursor.fetchall():
        profile_lookup[row['username_normalized']] = row['id']
        profile_lookup[row['username'].lower().strip()] = row['id']

    def find_profile(username):
        if not username:
            return None
        low = username.lower().strip()
        if low in profile_lookup:
            return profile_lookup[low]
        return profile_lookup.get(normalize(username))

    # Systems
    cursor.execute('SELECT id, personal_discord_username, discovered_by FROM systems WHERE profile_id IS NULL')
    sys_count = 0
    for row in cursor.fetchall():
        pid = find_profile(row['personal_discord_username']) or find_profile(row['discovered_by'])
        if pid:
            cursor.execute('UPDATE systems SET profile_id = ? WHERE id = ?', (pid, row['id']))
            sys_count += 1

    # Pending systems
    cursor.execute('SELECT id, personal_discord_username, submitted_by FROM pending_systems WHERE submitter_profile_id IS NULL')
    pend_count = 0
    for row in cursor.fetchall():
        pid = find_profile(row['personal_discord_username']) or find_profile(row['submitted_by'])
        if pid:
            cursor.execute('UPDATE pending_systems SET submitter_profile_id = ? WHERE id = ?', (pid, row['id']))
            pend_count += 1

    # Discoveries
    cursor.execute('SELECT id, discovered_by FROM discoveries WHERE profile_id IS NULL')
    disc_count = 0
    for row in cursor.fetchall():
        pid = find_profile(row['discovered_by'])
        if pid:
            cursor.execute('UPDATE discoveries SET profile_id = ? WHERE id = ?', (pid, row['id']))
            disc_count += 1

    logger.info(f"Backfilled profile_id: {sys_count} systems, {pend_count} pending, {disc_count} discoveries")
    conn.commit()


# =============================================================================
# v1.65.0 - Add missing moon columns and backfill from pending_systems JSON
# =============================================================================
@register_migration("1.65.0", "Add missing moon columns (biome, weather, resources) and backfill from pending_systems JSON")
def migration_1_65_0(conn):
    """
    The moons table was missing biome, weather, and resource columns that planets have had
    since v1.36.0. Moon data was submitted correctly (stored in pending_systems.system_data JSON)
    but silently dropped during approval because the INSERT statements didn't include these columns.

    This migration:
    1. Adds the missing columns to the moons table
    2. Backfills moon data from pending_systems JSON by matching system name → planet → moon name
    """
    import sqlite3 as _sqlite3
    conn.row_factory = _sqlite3.Row
    cursor = conn.cursor()

    # Step 1: Add missing columns
    new_columns = [
        ('biome', 'TEXT'),
        ('biome_subtype', 'TEXT'),
        ('weather', 'TEXT'),
        ('planet_size', 'TEXT'),
        ('common_resource', 'TEXT'),
        ('uncommon_resource', 'TEXT'),
        ('rare_resource', 'TEXT'),
        ('weather_text', 'TEXT'),
        ('sentinels_text', 'TEXT'),
        ('flora_text', 'TEXT'),
        ('fauna_text', 'TEXT'),
        ('plant_resource', 'TEXT'),
        ('dissonance', 'INTEGER DEFAULT 0'),
    ]

    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE moons ADD COLUMN {col_name} {col_type}")
            logger.info(f"Added {col_name} column to moons table")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                pass  # Already exists from init_database
            else:
                raise

    conn.commit()

    # Step 2: Build a lookup of moon data from pending_systems JSON
    # For each approved system, find its pending_systems row and extract moon data
    logger.info("Backfilling moon data from pending_systems JSON...")

    # Get all systems with their names and IDs
    cursor.execute("SELECT id, name, glyph_code FROM systems")
    systems = {row['name']: {'id': row['id'], 'glyph': row['glyph_code']} for row in cursor.fetchall()}

    # Get all pending_systems with their JSON data (approved ones have the data we need)
    cursor.execute("SELECT system_name, system_data FROM pending_systems WHERE system_data IS NOT NULL")
    pending_rows = cursor.fetchall()

    # Build moon data lookup: { (system_name, moon_name_lower): moon_dict }
    moon_data_lookup = {}
    for row in pending_rows:
        try:
            data = json.loads(row['system_data'])
            sys_name = data.get('name') or row['system_name']
            if not sys_name:
                continue

            # Moons nested under planets
            for planet in data.get('planets', []):
                for moon in planet.get('moons', []):
                    moon_name = (moon.get('name') or '').strip()
                    if moon_name:
                        key = (sys_name, moon_name.lower())
                        # Keep the most data-rich version
                        existing = moon_data_lookup.get(key)
                        if not existing or (moon.get('biome') and not existing.get('biome')):
                            moon_data_lookup[key] = moon

            # Root-level moons (from extractor)
            for moon in data.get('moons', []):
                moon_name = (moon.get('name') or '').strip()
                if moon_name:
                    key = (sys_name, moon_name.lower())
                    existing = moon_data_lookup.get(key)
                    if not existing or (moon.get('biome') and not existing.get('biome')):
                        moon_data_lookup[key] = moon
        except (json.JSONDecodeError, TypeError):
            continue

    logger.info(f"Found {len(moon_data_lookup)} moon data entries in pending_systems JSON")

    # Step 3: Update each moon in the moons table
    cursor.execute("""
        SELECT m.id, m.name, p.name as planet_name, s.name as system_name
        FROM moons m
        JOIN planets p ON m.planet_id = p.id
        JOIN systems s ON p.system_id = s.id
    """)
    moon_rows = cursor.fetchall()

    updated = 0
    for moon_row in moon_rows:
        moon_name = (moon_row['name'] or '').strip()
        sys_name = moon_row['system_name']
        if not moon_name or not sys_name:
            continue

        key = (sys_name, moon_name.lower())
        source = moon_data_lookup.get(key)
        if not source:
            continue

        # Only update fields that are currently NULL/empty in the DB
        updates = []
        values = []

        field_map = {
            'biome': 'biome',
            'biome_subtype': 'biome_subtype',
            'weather': 'weather',
            'planet_size': 'planet_size',
            'common_resource': 'common_resource',
            'uncommon_resource': 'uncommon_resource',
            'rare_resource': 'rare_resource',
            'plant_resource': 'plant_resource',
            'weather_text': 'weather_text',
            'sentinels_text': 'sentinels_text',
            'flora_text': 'flora_text',
            'fauna_text': 'fauna_text',
        }

        for db_col, json_key in field_map.items():
            val = source.get(json_key)
            if val and str(val).strip():
                updates.append(f"{db_col} = ?")
                values.append(str(val).strip())

        # Also backfill sentinel/flora/fauna if they're still at defaults
        for field, default in [('sentinel', 'None'), ('flora', 'N/A'), ('fauna', 'N/A')]:
            src_val = source.get(field)
            if src_val and str(src_val).strip() and str(src_val).strip() not in ('N/A', 'None', ''):
                updates.append(f"{field} = CASE WHEN {field} IS NULL OR {field} = '{default}' OR {field} = '' THEN ? ELSE {field} END")
                values.append(str(src_val).strip())

        # Backfill climate from weather if climate is empty
        weather_val = source.get('weather') or source.get('climate')
        if weather_val and str(weather_val).strip():
            updates.append("climate = CASE WHEN climate IS NULL OR climate = '' THEN ? ELSE climate END")
            values.append(str(weather_val).strip())

        if updates:
            values.append(moon_row['id'])
            sql = f"UPDATE moons SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, values)
            updated += 1

    logger.info(f"Backfilled data for {updated} of {len(moon_rows)} moons from pending_systems JSON")
    conn.commit()


@register_migration("1.66.0", "Backfill profile_id, personal_discord_username, source on systems from discovered_by")
def migration_1_66_0(conn):
    """
    The save_system endpoint (used by admins/partners for direct system creation) was
    not setting profile_id, personal_discord_username, or source. This caused the
    My Profile submissions count to undercount direct-created systems.

    This migration:
    1. Backfills profile_id on systems where NULL by matching discovered_by/personal_discord_username
       against user_profiles.username_normalized (via same normalization as the runtime helper).
    2. Defaults source to 'manual' where NULL (only for systems that aren't 'haven_extractor' or
       'companion_app').
    """
    import unicodedata
    cursor = conn.cursor()

    def _normalize(u: str) -> str:
        if not u:
            return ''
        n = unicodedata.normalize('NFKD', u)
        n = ''.join(ch for ch in n if not unicodedata.combining(ch))
        n = n.strip().lower().replace('#', '').replace(' ', '').replace('_', '').replace('-', '')
        if len(n) > 4 and n[-4:].isdigit():
            prefix = n[:-4]
            if prefix and not prefix[-1].isdigit():
                n = prefix
        return n

    # Build a username_normalized -> profile_id lookup
    cursor.execute("SELECT id, username_normalized FROM user_profiles WHERE username_normalized IS NOT NULL")
    profile_lookup = {row[1]: row[0] for row in cursor.fetchall() if row[1]}

    # Find systems missing profile_id
    cursor.execute("""
        SELECT id, discovered_by, personal_discord_username
        FROM systems WHERE profile_id IS NULL
    """)
    rows = cursor.fetchall()

    matched = 0
    for sys_id, discovered_by, pdu in rows:
        candidate = pdu or discovered_by
        if not candidate:
            continue
        key = _normalize(candidate)
        pid = profile_lookup.get(key)
        if pid:
            cursor.execute('UPDATE systems SET profile_id = ? WHERE id = ?', (pid, sys_id))
            matched += 1

    logger.info(f"Backfilled profile_id on {matched} of {len(rows)} systems without profile_id")

    # Default source to 'manual' where NULL
    cursor.execute("""
        UPDATE systems SET source = 'manual'
        WHERE source IS NULL
    """)
    logger.info(f"Set source='manual' on {cursor.rowcount} systems where source was NULL")

    conn.commit()


@register_migration("1.67.0", "Backfill pending_systems.galaxy from system_data JSON so approval list shows correct galaxy")
def migration_1_67_0(conn):
    """
    Pre-1.66.0 the submit_system INSERT never populated the galaxy column on pending_systems
    (galaxy value was stored in system_region instead). This caused the approval tab to show
    "Euclid" for every non-Euclid submission. 1.66.0 fixed the INSERT going forward; this
    migration backfills historical rows by reading galaxy from the system_data JSON blob.
    """
    import json as _json
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, system_data FROM pending_systems
        WHERE galaxy IS NULL AND system_data IS NOT NULL
    """)
    rows = cursor.fetchall()
    backfilled = 0
    for row_id, sys_data_json in rows:
        try:
            sd = _json.loads(sys_data_json) if sys_data_json else {}
            g = sd.get('galaxy')
            if g:
                cursor.execute("UPDATE pending_systems SET galaxy = ? WHERE id = ?", (g, row_id))
                backfilled += 1
        except (ValueError, TypeError):
            continue

    logger.info(f"Backfilled galaxy on {backfilled} of {len(rows)} pending_systems rows")
    conn.commit()


@register_migration("1.68.0", "Backfill procedural system names and create missing region entries via nms_namegen")
def migration_1_68_0(conn):
    """
    Uses the vendored nms_namegen library to:
    1. Replace System_XXXX placeholder names on approved systems with procedural names
    2. Replace System_XXXX placeholder names on non-rejected pending systems
    3. Create regions table entries (with procedural names) for regions that have systems
       but no entry in the regions table
    4. Clean up 'RealityMode.Normal' → 'Normal' in reality columns
    """
    import json as _json
    from pathlib import Path as _Path

    cursor = conn.cursor()

    # Load galaxy name → index lookup
    galaxies_path = _Path(__file__).parent / 'data' / 'galaxies.json'
    try:
        with open(galaxies_path) as f:
            _galaxies = _json.load(f)
        galaxy_to_idx = {v: int(k) for k, v in _galaxies.items()}
    except Exception as e:
        logger.error(f"Could not load galaxies.json: {e}")
        return

    # Import nms_namegen (vendored in backend directory)
    try:
        from nms_namegen.system import systemName as _systemName
        from nms_namegen.region import regionName as _regionName
    except ImportError as e:
        logger.error(f"nms_namegen not available for migration: {e}")
        return

    def _galaxy_idx(name):
        return galaxy_to_idx.get(name, 0)

    def _glyph_to_portal(glyph):
        try:
            return int(glyph, 16)
        except (ValueError, TypeError):
            return 0

    def _region_portal(rx, ry, rz):
        """Build portal code from region coords for regionName(). Only lower 32 bits matter."""
        return (ry << 24) | (rz << 12) | rx

    # --- Step 1: Fix RealityMode.Normal → Normal ---
    cursor.execute("UPDATE systems SET reality = 'Normal' WHERE reality = 'RealityMode.Normal'")
    reality_fixed = cursor.rowcount
    cursor.execute("UPDATE pending_systems SET reality = 'Normal' WHERE reality = 'RealityMode.Normal'")
    reality_fixed += cursor.rowcount
    cursor.execute("UPDATE regions SET reality = 'Normal' WHERE reality = 'RealityMode.Normal'")
    reality_fixed += cursor.rowcount
    if reality_fixed:
        logger.info(f"Fixed {reality_fixed} 'RealityMode.Normal' → 'Normal' across tables")

    # --- Step 2: Backfill approved system placeholder names ---
    cursor.execute("""
        SELECT id, name, glyph_code, galaxy FROM systems
        WHERE name = 'System_' || glyph_code
          AND glyph_code IS NOT NULL AND length(glyph_code) = 12
    """)
    systems = cursor.fetchall()
    sys_updated = 0
    for sys_id, old_name, glyph, galaxy in systems:
        portal = _glyph_to_portal(glyph)
        if portal == 0:
            continue
        try:
            new_name = _systemName(portal, _galaxy_idx(galaxy))
            cursor.execute("UPDATE systems SET name = ? WHERE id = ?", (new_name, sys_id))
            logger.info(f"  System '{old_name}' → '{new_name}' (galaxy={galaxy})")
            sys_updated += 1
        except Exception as e:
            logger.warning(f"  System {sys_id} name gen failed: {e}")
    logger.info(f"Backfilled {sys_updated} of {len(systems)} system placeholder names")

    # --- Step 3: Backfill pending system placeholder names ---
    cursor.execute("""
        SELECT id, system_name, glyph_code, galaxy, system_data FROM pending_systems
        WHERE system_name LIKE 'System_%'
          AND glyph_code IS NOT NULL AND length(glyph_code) = 12
          AND status != 'rejected'
    """)
    pending = cursor.fetchall()
    pend_updated = 0
    for pend_id, old_name, glyph, galaxy, sys_data_json in pending:
        # Skip if the name doesn't look like a hex placeholder
        suffix = old_name[7:] if old_name.startswith('System_') else ''
        if not all(c in '0123456789ABCDEFabcdef' for c in suffix):
            continue
        portal = _glyph_to_portal(glyph)
        if portal == 0:
            continue
        try:
            new_name = _systemName(portal, _galaxy_idx(galaxy or 'Euclid'))
            cursor.execute("UPDATE pending_systems SET system_name = ? WHERE id = ?", (new_name, pend_id))
            # Also update system_data JSON if present
            if sys_data_json:
                try:
                    sd = _json.loads(sys_data_json)
                    sd['name'] = new_name
                    cursor.execute("UPDATE pending_systems SET system_data = ? WHERE id = ?",
                                   (_json.dumps(sd), pend_id))
                except (ValueError, TypeError):
                    pass
            pend_updated += 1
        except Exception as e:
            logger.warning(f"  Pending {pend_id} name gen failed: {e}")
    logger.info(f"Backfilled {pend_updated} of {len(pending)} pending system placeholder names")

    # --- Step 4: Create missing region entries with procedural names ---
    cursor.execute("""
        SELECT DISTINCT s.region_x, s.region_y, s.region_z,
               COALESCE(s.galaxy, 'Euclid') as galaxy,
               COALESCE(s.reality, 'Normal') as reality
        FROM systems s
        LEFT JOIN regions r ON s.region_x = r.region_x AND s.region_y = r.region_y AND s.region_z = r.region_z
                               AND COALESCE(s.galaxy, 'Euclid') = COALESCE(r.galaxy, 'Euclid')
                               AND COALESCE(s.reality, 'Normal') = COALESCE(r.reality, 'Normal')
        WHERE r.region_x IS NULL
          AND s.region_x IS NOT NULL
    """)
    missing_regions = cursor.fetchall()
    regions_created = 0
    for rx, ry, rz, galaxy, reality in missing_regions:
        portal = _region_portal(rx, ry, rz)
        try:
            name = _regionName(portal, _galaxy_idx(galaxy))
            cursor.execute("""
                INSERT OR IGNORE INTO regions (region_x, region_y, region_z, custom_name, reality, galaxy)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rx, ry, rz, name, reality, galaxy))
            if cursor.rowcount > 0:
                regions_created += 1
        except Exception as e:
            logger.warning(f"  Region [{rx},{ry},{rz}] name gen failed: {e}")
    logger.info(f"Created {regions_created} of {len(missing_regions)} missing region entries with procedural names")

    conn.commit()


@register_migration("1.69.0", "Unify submission source attribution: split keeper_bot from haven_extractor, fold companion_app, add source column to pending_discoveries / discoveries / pending_region_names / regions")
def migration_1_69_0(conn):
    """
    Unifies the `source` enum across every pending and approved table so the
    UI can render consistent badges and analytics can split by upload path.

    Final source values:
      - 'manual'          web wizard, no API key
      - 'haven_extractor' any extractor-style API key (per-user keys,
                          legacy 'Haven Extractor' system key, prototype
                          'Haven' admin key from Dec 2025)
      - 'keeper_bot'      dedicated Keeper Discord bot keys

    Steps:
      1. Add `source TEXT NOT NULL DEFAULT 'manual'` to pending_discoveries,
         discoveries, pending_region_names, regions if missing.
      2. Backfill all existing pending_discoveries and discoveries rows as
         'keeper_bot' (only ingest path that has ever existed for those rows
         is the Keeper Discord bot - confirmed against Pi snapshot).
      3. Split keeper_bot off haven_extractor in pending_systems and systems
         by api_key_name match against KEEPER_API_KEY_NAMES.
      4. Fold the small 'companion_app' bucket (30 pending + 1 approved) into
         haven_extractor - those rows are early extractor prototype data from
         before the dedicated extractor key existed (verified by name pattern
         and timeline against api_keys.created_at).
    """
    cursor = conn.cursor()

    keeper_names = ('Keeper 2.0', 'Keeper Bot')

    # --- Step 1: Add `source` column where missing ----------------------

    def _has_column(table, col):
        cursor.execute(f"PRAGMA table_info({table})")
        return col in [row[1] for row in cursor.fetchall()]

    if not _has_column('pending_discoveries', 'source'):
        cursor.execute("ALTER TABLE pending_discoveries ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
        logger.info("Added source column to pending_discoveries")

    if not _has_column('discoveries', 'source'):
        cursor.execute("ALTER TABLE discoveries ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
        logger.info("Added source column to discoveries")

    if not _has_column('pending_region_names', 'source'):
        cursor.execute("ALTER TABLE pending_region_names ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
        logger.info("Added source column to pending_region_names")

    if not _has_column('regions', 'source'):
        cursor.execute("ALTER TABLE regions ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
        logger.info("Added source column to regions")

    # --- Step 2: Backfill discoveries as keeper_bot ---------------------
    # Every existing row in pending_discoveries / discoveries came in via the
    # Keeper bot - the web /api/submit_discovery path is recent and produces
    # rows we'll start tagging 'manual' going forward via the route handler.
    # We mark all _existing_ rows keeper_bot since that is their actual origin.
    cursor.execute("UPDATE pending_discoveries SET source = 'keeper_bot' WHERE source = 'manual'")
    pd_backfill = cursor.rowcount
    cursor.execute("UPDATE discoveries SET source = 'keeper_bot' WHERE source = 'manual'")
    d_backfill = cursor.rowcount
    logger.info(f"Backfilled {pd_backfill} pending_discoveries and {d_backfill} discoveries as 'keeper_bot'")

    # --- Step 3: Split keeper_bot off haven_extractor in pending_systems -
    cursor.execute(
        "UPDATE pending_systems SET source = 'keeper_bot' "
        "WHERE api_key_name IN (?, ?)",
        keeper_names,
    )
    ps_keeper = cursor.rowcount

    # Fold prototype 'companion_app' into haven_extractor
    cursor.execute(
        "UPDATE pending_systems SET source = 'haven_extractor' "
        "WHERE source = 'companion_app'"
    )
    ps_legacy = cursor.rowcount

    logger.info(f"pending_systems: {ps_keeper} -> keeper_bot, {ps_legacy} companion_app -> haven_extractor")

    # --- Step 4: Same split on the approved systems table ---------------
    # Trace approved Keeper systems through pending_systems by glyph + galaxy.
    cursor.execute("""
        UPDATE systems
        SET source = 'keeper_bot'
        WHERE id IN (
            SELECT s.id FROM systems s
            JOIN pending_systems ps
              ON ps.glyph_code = s.glyph_code
             AND COALESCE(ps.galaxy, 'Euclid') = COALESCE(s.galaxy, 'Euclid')
            WHERE ps.api_key_name IN (?, ?)
              AND ps.status = 'approved'
        )
    """, keeper_names)
    sys_keeper = cursor.rowcount

    cursor.execute(
        "UPDATE systems SET source = 'haven_extractor' WHERE source = 'companion_app'"
    )
    sys_legacy = cursor.rowcount

    logger.info(f"systems: {sys_keeper} -> keeper_bot, {sys_legacy} companion_app -> haven_extractor")

    # --- Sanity: log the final distribution -----------------------------
    cursor.execute("SELECT source, COUNT(*) FROM pending_systems GROUP BY source")
    logger.info(f"pending_systems final distribution: {dict(cursor.fetchall())}")
    cursor.execute("SELECT source, COUNT(*) FROM systems GROUP BY source")
    logger.info(f"systems final distribution: {dict(cursor.fetchall())}")
    cursor.execute("SELECT source, COUNT(*) FROM pending_discoveries GROUP BY source")
    logger.info(f"pending_discoveries final distribution: {dict(cursor.fetchall())}")
    cursor.execute("SELECT source, COUNT(*) FROM discoveries GROUP BY source")
    logger.info(f"discoveries final distribution: {dict(cursor.fetchall())}")

    conn.commit()


@register_migration("1.70.0", "Poster service: add poster_public flag to user_profiles + create poster_cache table")
def migration_1_70_0(conn):
    """
    Foundation for the Voyager Card / Galaxy Atlas poster service.

    - Adds `poster_public INTEGER DEFAULT 1` to user_profiles. Default opt-in
      so the personal voyager card is publicly accessible at /voyager/:username
      unless the user explicitly toggles it off.
    - Creates `poster_cache` table tracking generated poster artifacts. Used by
      the future Playwright-based PNG renderer to skip re-screenshotting when
      the underlying data hasn't changed.
    """
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(user_profiles)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'poster_public' not in cols:
        cursor.execute("ALTER TABLE user_profiles ADD COLUMN poster_public INTEGER DEFAULT 1")
        logger.info("Added poster_public column to user_profiles (default 1 / opt-in)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS poster_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poster_type TEXT NOT NULL,
            cache_key TEXT NOT NULL,
            template_version INTEGER NOT NULL DEFAULT 1,
            generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            data_hash TEXT,
            file_path TEXT,
            render_ms INTEGER,
            UNIQUE(poster_type, cache_key)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_poster_cache_type_key ON poster_cache(poster_type, cache_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_poster_cache_generated_at ON poster_cache(generated_at)")

    conn.commit()
    logger.info("Created poster_cache table + indexes")


@register_migration("1.71.0", "Hot-path indexes: activity_logs.timestamp, approval_audit_log filter columns, pending_systems queue columns")
def migration_1_71_0(conn):
    """
    Pi freeze mitigation (Stage 1).

    activity_logs has zero indexes. The trim query in db.add_activity_log runs on every
    write and previously did `DELETE ... WHERE id NOT IN (... ORDER BY timestamp DESC LIMIT N)`,
    which without an index on timestamp is a full scan + in-memory sort while holding the
    write lock. Index on timestamp DESC lets the rewritten trim use a fast cutoff lookup.

    approval_audit_log already has indexes on timestamp / approver_username / discord_tag.
    Filters on submitter_username, action, submission_type, and source are unindexed and
    grow with the audit log. These get added so partner audit-log queries don't fall back
    to full scans of an ever-growing table.

    pending_systems only has an index on glyph_code. The pending-queue listing endpoints
    filter by status (always 'pending') and order by submission_date DESC, and partner-
    scoped views additionally filter by discord_tag. These are the hot paths admins hit
    on every approval-page load.
    """
    cursor = conn.cursor()

    # activity_logs - the single most impactful index per the diagnosis
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp ON activity_logs(timestamp DESC)")

    # approval_audit_log - additions to existing timestamp/approver/discord_tag indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_submitter ON approval_audit_log(submitter_username)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON approval_audit_log(action)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_submission_type ON approval_audit_log(submission_type)")
    # source column was added in v1.61.0; guard in case older DBs pre-migration
    cursor.execute("PRAGMA table_info(approval_audit_log)")
    audit_cols = {row[1] for row in cursor.fetchall()}
    if 'source' in audit_cols:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_source ON approval_audit_log(source)")

    # pending_systems - composite indexes matching the actual queue queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_systems_status_date ON pending_systems(status, submission_date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_systems_discord_status ON pending_systems(discord_tag, status)")

    conn.commit()
    logger.info("Created hot-path indexes for activity_logs, approval_audit_log, and pending_systems")


@register_migration("1.72.0", "Indexable username_normalized column on pending_systems for analytics leaderboard")
def migration_1_72_0(conn):
    """
    Adds an indexable, denormalized `username_normalized` column to pending_systems
    so the analytics leaderboard can GROUP BY a real column instead of the
    LOWER(TRIM(CASE WHEN SUBSTR(...) GLOB ... ELSE ... END)) expression that
    forces a full table scan on every request.

    Backfill uses the canonical Python helper services.auth_service.normalize_username_for_dedup
    rather than re-implementing the rule in SQL — the normalization rule has changed
    twice (v1.55.0, v1.64.0) and a generated/computed column would lock it. New
    INSERT sites populate the column at write time using the same helper.

    The raw input mirrors the existing raw_username COALESCE chain in
    routes/analytics.py so the leaderboard's grouping behavior stays identical:
      submitted_by (excluding 'Anonymous'/'anonymous') → personal_discord_username
      → JSON-extract discovered_by → 'Unknown'
    """
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(pending_systems)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'username_normalized' not in cols:
        cursor.execute("ALTER TABLE pending_systems ADD COLUMN username_normalized TEXT")
        logger.info("Added username_normalized column to pending_systems")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_systems_username_normalized ON pending_systems(username_normalized)")

    # Backfill using the canonical Python normalizer. Import lazily so this
    # module remains importable even if services.auth_service has a circular dep
    # at startup (it doesn't today, but we cross the import via a local import
    # to be safe).
    try:
        import sys
        from pathlib import Path as _P
        backend_dir = _P(__file__).parent
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))
        from services.auth_service import normalize_username_for_dedup
    except Exception as e:
        logger.warning(f"Could not import normalize_username_for_dedup for backfill: {e}")
        conn.commit()
        return

    cursor.execute("""
        SELECT id, submitted_by, personal_discord_username, system_data
        FROM pending_systems
        WHERE username_normalized IS NULL
    """)
    rows = cursor.fetchall()
    updated = 0
    for row in rows:
        sid, submitted_by, personal, system_data_json = row[0], row[1], row[2], row[3]
        raw = None
        if submitted_by and submitted_by not in ('Anonymous', 'anonymous'):
            raw = submitted_by
        elif personal:
            raw = personal
        else:
            try:
                if system_data_json:
                    sd = json.loads(system_data_json)
                    raw = sd.get('discovered_by')
            except (json.JSONDecodeError, TypeError):
                pass
        if not raw:
            raw = 'Unknown'
        normalized = normalize_username_for_dedup(raw)
        cursor.execute("UPDATE pending_systems SET username_normalized = ? WHERE id = ?", (normalized, sid))
        updated += 1

    conn.commit()
    logger.info(f"Backfilled username_normalized for {updated} pending_systems rows")


@register_migration("1.73.0", "Indexable glyph_code_suffix on systems and pending_systems via auto-maintained triggers")
def migration_1_73_0(conn):
    """
    The glyph-coordinate dedup query in db.find_matching_system() does
    `WHERE SUBSTR(glyph_code, -11) = ?`, which defeats idx_systems_glyph_code
    because the LHS is an expression. Calling that function inside the approval
    transaction and on every extractor upload makes it a hot path.

    Solution: maintain a `glyph_code_suffix` column (last 11 chars) populated
    by SQLite triggers so the rule lives in one place and is auto-maintained.
    The "last 11 chars" rule is structurally stable (it encodes the planet+system
    portion of the 12-char NMS portal address) so trigger-based maintenance is
    safe — unlike the username normalization rules.

    Adds the column + index + INSERT/UPDATE triggers on both `systems` and
    `pending_systems`. Backfills existing rows.
    """
    cursor = conn.cursor()

    for table in ('systems', 'pending_systems'):
        cursor.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in cursor.fetchall()}
        if 'glyph_code_suffix' not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN glyph_code_suffix TEXT")
            logger.info(f"Added glyph_code_suffix column to {table}")

        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table}_glyph_code_suffix
            ON {table}(glyph_code_suffix)
        """)

        cursor.execute(f"DROP TRIGGER IF EXISTS trg_{table}_glyph_suffix_insert")
        cursor.execute(f"""
            CREATE TRIGGER trg_{table}_glyph_suffix_insert
            AFTER INSERT ON {table}
            FOR EACH ROW
            WHEN NEW.glyph_code IS NOT NULL AND LENGTH(NEW.glyph_code) >= 11
            BEGIN
                UPDATE {table}
                SET glyph_code_suffix = UPPER(SUBSTR(NEW.glyph_code, -11))
                WHERE rowid = NEW.rowid;
            END
        """)

        cursor.execute(f"DROP TRIGGER IF EXISTS trg_{table}_glyph_suffix_update")
        cursor.execute(f"""
            CREATE TRIGGER trg_{table}_glyph_suffix_update
            AFTER UPDATE OF glyph_code ON {table}
            FOR EACH ROW
            WHEN NEW.glyph_code IS NOT NULL AND LENGTH(NEW.glyph_code) >= 11
            BEGIN
                UPDATE {table}
                SET glyph_code_suffix = UPPER(SUBSTR(NEW.glyph_code, -11))
                WHERE rowid = NEW.rowid;
            END
        """)

        # Backfill rows whose suffix is NULL but whose glyph is populated.
        cursor.execute(f"""
            UPDATE {table}
            SET glyph_code_suffix = UPPER(SUBSTR(glyph_code, -11))
            WHERE glyph_code IS NOT NULL
              AND LENGTH(glyph_code) >= 11
              AND glyph_code_suffix IS NULL
        """)
        logger.info(f"Backfilled glyph_code_suffix on {table} ({cursor.rowcount} rows)")

    conn.commit()
    logger.info("glyph_code_suffix triggers + index installed on systems and pending_systems")


@register_migration("1.74.0", "Async batch-approval job tracking")
def migration_1_74_0(conn):
    """
    Backing table for the async batch-approval job queue (Phase 4 of the
    May 2026 latency fix dispatch).

    The /api/approve_systems/batch endpoint used to process every submission
    inline within one HTTP request, which exceeded Nginx Proxy Manager's
    60-second timeout for batches of ~100. The endpoint now returns 202 +
    job_id immediately and runs the work in a background task. The frontend
    polls /api/batch_jobs/{job_id} for progress.

    No FK constraint on submission ids — failures get logged into the JSON
    `failures` column rather than relying on referential integrity, since
    pending submissions can legitimately disappear (be approved or rejected
    out from under us by another admin) between job submission and
    processing.
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS batch_jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            total_systems INTEGER NOT NULL,
            processed_systems INTEGER NOT NULL DEFAULT 0,
            failed_systems INTEGER NOT NULL DEFAULT 0,
            failures TEXT,
            submitted_by_username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_jobs_created_at ON batch_jobs(created_at DESC)")
    conn.commit()
    logger.info("Created batch_jobs table for async batch-approval tracking")


@register_migration("1.75.0", "Wizard v1 rebuild: game_version, submitter_notes, expedition_id, expeditions table, system_coauthors table")
def migration_1_75_0(conn):
    """
    Schema additions for the Wizard v1 rebuild (May 2026).

    New columns:
    - systems.game_version              TEXT  — NMS engine version (e.g. "6.18", "Worlds Part 2")
    - pending_systems.game_version      TEXT  — same, on pending row for round-trip
    - pending_systems.submitter_notes   TEXT  — admin-only review context. NOT copied to systems on approve
    - systems.expedition_id             INTEGER  — link to expeditions(id)
    - pending_systems.expedition_id     INTEGER  — same, on pending row

    New tables:
    - expeditions          — community-scoped charting campaigns
    - system_coauthors     — many-to-many credit table; co-author counts are tracked
                             SEPARATELY from primary submission counts in analytics
    """
    cursor = conn.cursor()

    # --- Column additions (idempotent) ---
    def _add_col(table: str, name: str, type_def: str):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {type_def}")
            logger.info(f"Added {table}.{name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' not in str(e).lower():
                raise

    _add_col('systems', 'game_version', 'TEXT')
    _add_col('pending_systems', 'game_version', 'TEXT')
    _add_col('pending_systems', 'submitter_notes', 'TEXT')
    _add_col('systems', 'expedition_id', 'INTEGER')
    _add_col('pending_systems', 'expedition_id', 'INTEGER')

    # --- expeditions table ---
    # status: 'active' | 'completed' | 'archived'. discord_tag scopes visibility
    # to a community (per Parker: "whole community can see expeditions").
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expeditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            owner_profile_id INTEGER,
            owner_username TEXT,
            discord_tag TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            description TEXT,
            started_at TEXT,
            ended_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT,
            UNIQUE(slug)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expeditions_status ON expeditions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expeditions_discord_tag ON expeditions(discord_tag, status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expeditions_owner ON expeditions(owner_profile_id)")
    logger.info("Created expeditions table")

    # --- system_coauthors table ---
    # Composite PK avoids dupes; profile_id may be NULL for legacy/anon coauthors so
    # username_normalized is the dedup field. credited_at is the approval timestamp.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_coauthors (
            system_id TEXT NOT NULL,
            profile_id INTEGER,
            username TEXT NOT NULL,
            username_normalized TEXT NOT NULL,
            credited_at TEXT NOT NULL,
            PRIMARY KEY (system_id, username_normalized)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coauthors_profile ON system_coauthors(profile_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coauthors_username ON system_coauthors(username_normalized)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coauthors_system ON system_coauthors(system_id)")
    logger.info("Created system_coauthors table")

    # --- expedition_id index on systems for leaderboard queries ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_systems_expedition ON systems(expedition_id)")

    conn.commit()
    logger.info("Migration 1.75.0 complete")


@register_migration("1.76.0", "Wonders Page Notes: estimated_age, core_element, lore_notes, root_structure, nutrient_source on planets + moons")
def migration_1_76_0(conn):
    """
    Preserve the procedurally-generated narrative text NMS surfaces on a
    planet/moon's Log Exploration Guide page (visible in the Wonders
    Catalogue after upload). All five are free-form text — no record math.

    Columns added to both planets and moons:
    - estimated_age      TEXT  — e.g. "approximately 6.04 billion years"
    - core_element       TEXT  — e.g. "Gold", "Cadmium", "Water"
    - lore_notes         TEXT  — multi-paragraph procgen origin/history blurb
    - root_structure     TEXT  — lush/exotic biome flora-system description
    - nutrient_source    TEXT  — how local life feeds
    """
    cursor = conn.cursor()

    def _add_col(table: str, name: str, type_def: str):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {type_def}")
            logger.info(f"Added {table}.{name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' not in str(e).lower():
                raise

    for table in ('planets', 'moons'):
        _add_col(table, 'estimated_age', 'TEXT')
        _add_col(table, 'core_element', 'TEXT')
        _add_col(table, 'lore_notes', 'TEXT')
        _add_col(table, 'root_structure', 'TEXT')
        _add_col(table, 'nutrient_source', 'TEXT')

    conn.commit()
    logger.info("Migration 1.76.0 complete")


@register_migration("1.77.0", "Systems Tab v2.0: user_saved_searches table for named filter sets")
def migration_1_77_0(conn):
    """
    Per-user named filter sets that follow a user across devices.

    Owned by the Systems Tab v2.0 redesign (spec section 3.5). The Saved
    Searches dropdown sits next to the search bar and lets a user persist
    full filter snapshots ("T3 Wealthy Tech w/ Moons", "Paradise Hunting",
    etc.). State is profile-scoped, not device-local — recently-viewed
    history stays in localStorage; saved searches live here.

    Schema choices to call out:
    - INTEGER PK to match the rest of Haven's schema (user_profiles.id,
      systems.id, etc.). The dispatch's example SQL used TEXT ids — that
      was a copy-paste shape from the mockup, not a real constraint.
    - filters_json stores the full filter snapshot serialized; the
      shape is owned by the frontend and validated at write time in
      routes/user.py (we just check it parses as JSON).
    - 50-row hard cap enforced in the route handler, not at the DB
      layer, so we can return a friendly 400 instead of a constraint
      violation.
    - Cascade delete on profile removal so we don't leak saved searches
      when a profile is deleted.
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            filters_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_saved_searches_user
        ON user_saved_searches(user_id, created_at DESC)
    """)
    conn.commit()
    logger.info("Created user_saved_searches table for Systems Tab v2.0 saved filter sets")


@register_migration("1.78.0", "Poster cache: system_count_at_render column for region_thumb threshold refresh")
def migration_1_78_0(conn):
    """
    Adds `system_count_at_render` to `poster_cache` so region_thumb knows
    when to invalidate.

    Parker 2026-05-11: region posters refresh after the region grows by
    >= 10 systems OR >= 10% since the cached render. We persist the
    `system_count_at_render` value at render time and compare on each new
    system approval. See routes/approvals.py:_should_refresh_region_thumb.

    All other poster types ignore this column; it defaults to NULL on the
    existing rows.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(poster_cache)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'system_count_at_render' not in cols:
        cursor.execute("ALTER TABLE poster_cache ADD COLUMN system_count_at_render INTEGER")
        logger.info("Added poster_cache.system_count_at_render")
    conn.commit()


@register_migration("1.79.0", "Backfill planet/moon biome/weather/sentinel/fauna/flora from the notes field where the upload parked them")
def migration_1_79_0(conn):
    """
    Recover planet and moon detail data that legacy uploaders crammed into
    the `notes` column instead of the dedicated biome/weather/sentinel/
    fauna/flora columns.

    Findings from investigation (Parker 2026-05-11):
      - 898 planets have empty biome but populated notes
      - Of those, 420 use the canonical `Biome: X, Weather: Y, Sentinels: Z,
        Flora: W, Fauna: V` 5-part comma format (Wonders Guide format)
      - 116 use a 4-part variant (usually missing flora or sentinel)
      - 269 are real free-form user notes that should NOT be touched
      - 174 moons have the same problem (some use space-separated labels)

    This migration:
      - Adds `notes_legacy` TEXT column on both `planets` and `moons` so the
        original notes text is preserved for audit/rollback
      - Walks rows where biome is empty/NULL AND notes contains the
        `Biome:` label
      - Parses labeled chunks tolerant to comma OR whitespace separators
      - Backfills empty/N/A columns only — never clobbers data
      - Strips trailing " planet" / " moon" from biome values
      - Fixes the common 'Copius' → 'Copious' typo
      - On successful parse, moves notes → notes_legacy and clears notes
      - On free-form notes, leaves the row untouched

    Safety:
      - Idempotent (re-running is a no-op since notes is cleared post-parse)
      - Never destructive — original text retained in notes_legacy
      - Only fills columns that were empty; existing data is sacred
    """
    import re
    cursor = conn.cursor()

    # 1. Add notes_legacy columns (idempotent)
    for table in ('planets', 'moons'):
        cursor.execute(f"PRAGMA table_info({table})")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if 'notes_legacy' not in existing_cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN notes_legacy TEXT")
            logger.info(f"Added {table}.notes_legacy")

    # 2. Compile regexes for parsing
    # Match `Label: value` where value runs until the next label or end-of-string.
    # The look-ahead handles both `,` separators and whitespace separators.
    LABEL_PATTERN = re.compile(
        r'\b(Biome|Weather|Sentinels?|Flora|Fauna)\s*:\s*'
        r'(.+?)'
        r'(?=\s*[,;.]?\s*\b(?:Biome|Weather|Sentinels?|Flora|Fauna)\s*:|$)',
        re.IGNORECASE | re.DOTALL,
    )

    def _is_empty(v):
        """Return True if a column value should be considered empty."""
        if v is None:
            return True
        if not isinstance(v, str):
            return False
        s = v.strip()
        return s == '' or s.upper() in ('N/A', 'NONE')

    def _normalize_value(field, raw):
        s = raw.strip()
        # Strip trailing punctuation
        s = s.rstrip('.;, \t')
        # Strip trailing " planet" / " moon" from biome
        if field == 'biome':
            for suffix in (' planet', ' Planet', ' moon', ' Moon'):
                if s.endswith(suffix):
                    s = s[: -len(suffix)].rstrip()
                    break
        # Common typo fixes
        if s == 'Copius':
            s = 'Copious'
        # Capitalize first letter for biome / weather / sentinel
        if s and s[0].islower() and field in ('biome', 'weather', 'sentinel'):
            s = s[0].upper() + s[1:]
        return s

    def _strip_field_suffix(text, suffixes):
        """Strip a trailing suffix word (case-insensitive). 'rich Flora' -> 'rich'."""
        s = text.strip()
        for suffix in suffixes:
            if s.lower().endswith(' ' + suffix.lower()):
                return s[: -(len(suffix) + 1)].strip()
        return s

    def _parse_notes(notes):
        """Return dict of {biome, weather, sentinel, fauna, flora} parsed from
        the notes string, or None if nothing parses.

        Handles two formats observed in production:
          1. Labeled: 'Biome: X, Weather: Y, Sentinels: Z, Flora: W, Fauna: V'
          2. Positional 5-part: 'biome, weather, X sentinels, X Flora, X fauna'
             (used in 302 of the 612 affected rows — strip the suffix word
             off positions 3/4/5 to get the actual value)
        """
        if not notes:
            return None
        out = {}

        # Path 1: labeled format
        for m in LABEL_PATTERN.finditer(notes):
            label = m.group(1).lower()
            col = 'sentinel' if label.startswith('sentinel') else label
            if col in ('biome', 'weather', 'sentinel', 'fauna', 'flora'):
                value = _normalize_value(col, m.group(2))
                if value:
                    out.setdefault(col, value)
        if out:
            return out

        # Path 2: positional 5-part split (no colons, comma-separated).
        # Reject anything that looks even slightly free-form by requiring
        # the trailing "sentinels"/"flora"/"fauna" suffix words on parts 3/4/5.
        if ':' in notes:
            return None  # Labeled format that path 1 couldn't parse — leave alone
        parts = [p.strip() for p in notes.split(',')]
        if len(parts) != 5:
            return None  # 4-part is ambiguous; skip
        p_biome, p_weather, p_sent, p_flora, p_fauna = parts
        # Sentinels suffix is mandatory; flora/fauna labels are usually
        # present but tolerated absent for safety.
        sent_lc = p_sent.lower()
        if not (sent_lc.endswith(' sentinels') or sent_lc.endswith(' sentinel')):
            return None  # Doesn't match expected positional shape
        out['biome']   = _normalize_value('biome',   p_biome)
        out['weather'] = _normalize_value('weather', p_weather)
        out['sentinel'] = _normalize_value('sentinel', _strip_field_suffix(p_sent, ['sentinels', 'sentinel']))
        out['flora']   = _normalize_value('flora',   _strip_field_suffix(p_flora, ['Flora', 'flora']))
        out['fauna']   = _normalize_value('fauna',   _strip_field_suffix(p_fauna, ['Fauna', 'fauna']))
        # Drop any empty values that ended up as ''
        out = {k: v for k, v in out.items() if v}
        return out if out else None

    def _backfill_table(table):
        cursor.execute(f"""
            SELECT id, notes, biome, weather, sentinel, fauna, flora
            FROM {table}
            WHERE notes IS NOT NULL AND notes != ''
              AND (biome IS NULL OR biome = '')
        """)
        rows = cursor.fetchall()
        parsed = 0
        skipped = 0
        for row in rows:
            row_id, notes, biome, weather, sentinel, fauna, flora = row
            fields = _parse_notes(notes)
            # Fallback for bare positional rows: if the planet's fauna/flora
            # are still the bogus default 'N/A' AND sentinel is 'None' AND
            # notes has exactly 5 comma parts, this is almost certainly a
            # misfile. Accept without requiring suffix labels.
            if not fields and ':' not in (notes or ''):
                parts = [p.strip() for p in (notes or '').split(',')]
                if (len(parts) == 5
                        and _is_empty(fauna) and _is_empty(flora)
                        and (_is_empty(sentinel) or (sentinel or '').strip().lower() in ('none', 'n/a'))
                        and all(len(p) < 80 for p in parts)):
                    p_biome, p_weather, p_sent, p_flora, p_fauna = parts
                    candidate = {
                        'biome': _normalize_value('biome', p_biome),
                        'weather': _normalize_value('weather', p_weather),
                        'sentinel': _normalize_value('sentinel', _strip_field_suffix(p_sent, ['sentinels', 'sentinel'])),
                        'flora': _normalize_value('flora', _strip_field_suffix(p_flora, ['Flora', 'flora'])),
                        'fauna': _normalize_value('fauna', _strip_field_suffix(p_fauna, ['Fauna', 'fauna'])),
                    }
                    fields = {k: v for k, v in candidate.items() if v}
            if not fields:
                skipped += 1
                continue
            # Only update columns that are currently empty
            updates = {}
            if 'biome' in fields and _is_empty(biome):
                updates['biome'] = fields['biome']
            if 'weather' in fields and _is_empty(weather):
                updates['weather'] = fields['weather']
            if 'sentinel' in fields and _is_empty(sentinel):
                updates['sentinel'] = fields['sentinel']
            # sentinel_level is the older "amount" enum (Low/Standard/etc.);
            # if it's also empty/None mirror sentinel into it for back-compat
            # — only when sentinel value clearly fits the canonical set.
            if 'fauna' in fields and _is_empty(fauna):
                updates['fauna'] = fields['fauna']
            if 'flora' in fields and _is_empty(flora):
                updates['flora'] = fields['flora']

            if not updates:
                skipped += 1
                continue

            # Move original notes → notes_legacy, clear notes
            set_clauses = [f"{k} = ?" for k in updates] + ['notes_legacy = ?', 'notes = NULL']
            params = list(updates.values()) + [notes, row_id]
            cursor.execute(
                f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )
            parsed += 1
        logger.info(f"  {table}: parsed {parsed}, skipped {skipped} (no fields matched)")
        return parsed

    # 3. Run backfill on both tables
    logger.info("Migration 1.79.0: backfilling planet+moon detail columns from notes…")
    planets_updated = _backfill_table('planets')
    moons_updated = _backfill_table('moons')
    conn.commit()
    logger.info(f"Migration 1.79.0 complete: {planets_updated} planets, {moons_updated} moons backfilled")


@register_migration("1.80.0", "Civilizations as first-class entities — N:M membership replacing 1:1 partner ownership")
def migration_1_80_0(conn):
    """
    Civilizations refactor (Option B).

    Reframes a "civ" from "the discord_tag string on a single tier-2 user_profiles
    row" into a real entity with N:M membership. After this migration:
      - A civilization can have multiple leaders / co-leaders.
      - A member can belong to multiple civilizations with a role per membership.
      - Civ-level brand fields (display_name, region_color, theme_settings,
        enabled_features_default) live on the civilization row, not on a profile.
      - War room enrollment moves from partner_id → civ_id, retiring the legacy
        partner_accounts JOIN entirely.
      - Audit logs gain `acting_civ_tag` so we record which civ a member was
        acting on behalf of (matters once "acting as" UX lands).

    The migration is idempotent: every CREATE/ALTER is guarded, and the backfill
    is keyed by (tag) / (civ_id, profile_id) so re-running is a no-op.

    Legacy `user_profiles.partner_discord_tag`, `parent_profile_id`,
    `additional_discord_tags` columns are kept in place as deprecated reads —
    nothing in this migration drops them. The session builder + scoping queries
    will be rewired to consume `civilization_members` directly in the same
    release; the old columns survive only so an emergency rollback to the prior
    server code path is possible without restoring a backup.
    """
    # Migration connections don't set row_factory by default; we need column-
    # name access on a few of the backfill SELECTs below, so set it locally.
    # Save and restore so we don't leak state into later migrations.
    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    def _add_col(table: str, name: str, type_def: str):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {name} {type_def}")
            logger.info(f"Added {table}.{name}")
        except sqlite3.OperationalError as e:
            if 'duplicate column' not in str(e).lower():
                raise

    # ----- 1. civilizations table -----
    # `tag` is the immutable civ key (the same string that's been on systems
    # forever, e.g. 'Haven', 'GHUB'). Display_name / region_color /
    # theme_settings used to live on user_profiles and have moved here so
    # they're authoritative across all members.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS civilizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            region_color TEXT,
            theme_settings TEXT,
            enabled_features_default TEXT,
            default_reality TEXT,
            default_galaxy TEXT,
            founder_profile_id INTEGER,
            founded_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_civilizations_tag ON civilizations(tag)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_civilizations_active ON civilizations(is_active)")

    # ----- 2. civilization_members table -----
    # Composite PK: a profile can only be on a civ once. `role` controls
    # capability ('leader' and 'co_leader' are functionally identical per
    # Parker's spec; 'sub_admin' is delegated). `enabled_features` here is
    # an OPTIONAL per-member override of the civ's default set — when NULL
    # the member inherits civilizations.enabled_features_default.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS civilization_members (
            civ_id INTEGER NOT NULL,
            profile_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            enabled_features TEXT,
            can_approve_personal_uploads INTEGER NOT NULL DEFAULT 0,
            joined_at TEXT NOT NULL,
            joined_via TEXT,
            PRIMARY KEY (civ_id, profile_id),
            FOREIGN KEY (civ_id) REFERENCES civilizations(id),
            FOREIGN KEY (profile_id) REFERENCES user_profiles(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_civ_members_profile ON civilization_members(profile_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_civ_members_civ_role ON civilization_members(civ_id, role)")

    # ----- 3. home_civ_id on user_profiles -----
    # "Acting as" UX defaults to this civ at login when the user has >1
    # membership. NULL is fine — UX falls back to "first membership" or
    # prompts the user to pick.
    _add_col('user_profiles', 'home_civ_id', 'INTEGER')

    # ----- 4. civ_id on war_room_enrollment -----
    # Phase-2-of-Option-B kills the partner_accounts JOIN: enrollment is
    # now keyed by civilization, and any member of that civ can act on its
    # behalf in the war room. partner_id stays in place for one release as
    # a fallback / debug aid; nothing should read it after this migration.
    _add_col('war_room_enrollment', 'civ_id', 'INTEGER')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_war_room_enrollment_civ ON war_room_enrollment(civ_id, is_active)")

    # ----- 5. acting_civ_tag audit context -----
    # When a member of multiple civs takes an action, record which civ
    # context they were acting in. NULL on rows that pre-date this column
    # — analytics can fall back to discord_tag-on-system for those.
    _add_col('approval_audit_log', 'acting_civ_tag', 'TEXT')
    _add_col('pending_systems', 'acting_civ_tag', 'TEXT')

    conn.commit()

    # ============================================================================
    # Backfill
    # ============================================================================

    # Pull the unicode-aware username normalizer used by other identity
    # backfills; falls back to a no-op lambda if the import fails so the
    # rest of the migration still runs and we don't hard-fail on a fresh DB.
    try:
        from services.auth_service import normalize_username_for_dedup as _norm
    except Exception as e:
        logger.warning(f"Migration 1.80.0: could not import normalize_username_for_dedup ({e}); using passthrough")
        _norm = lambda u: (u or '').strip().lower()

    now_iso = "datetime('now')"  # SQLite-side timestamp for backfilled rows

    # ----- 5a. civilizations from existing tier-2 partner profiles -----
    # One civilization per partner_discord_tag found on a tier-2 row. Brand
    # fields (display_name, region_color, theme_settings, default_reality,
    # default_galaxy) snapshotted from the partner profile that owns it
    # today. ON CONFLICT DO NOTHING keeps the migration idempotent on
    # re-run and protects existing rows from a destructive re-snapshot.
    cursor.execute(f"""
        INSERT INTO civilizations
            (tag, display_name, region_color, theme_settings,
             enabled_features_default, default_reality, default_galaxy,
             founder_profile_id, founded_at, is_active, created_at)
        SELECT
            partner_discord_tag,
            COALESCE(display_name, partner_discord_tag),
            region_color,
            theme_settings,
            enabled_features,
            default_reality,
            default_galaxy,
            id,
            created_at,
            is_active,
            {now_iso}
        FROM user_profiles
        WHERE tier = 2 AND partner_discord_tag IS NOT NULL AND partner_discord_tag != ''
        ON CONFLICT(tag) DO NOTHING
    """)
    civs_created = cursor.rowcount
    logger.info(f"Migration 1.80.0: created {civs_created} civilization rows")

    # Build a tag → civ_id lookup for the membership inserts below
    cursor.execute("SELECT id, tag FROM civilizations")
    civ_id_by_tag = {row['tag']: row['id'] for row in cursor.fetchall()}

    # ----- 5b. leader memberships for tier-2 profiles -----
    cursor.execute("""
        SELECT id AS profile_id, partner_discord_tag, enabled_features, can_approve_personal_uploads
        FROM user_profiles
        WHERE tier = 2 AND partner_discord_tag IS NOT NULL AND partner_discord_tag != ''
    """)
    leader_rows = cursor.fetchall()
    leaders_inserted = 0
    for row in leader_rows:
        civ_id = civ_id_by_tag.get(row['partner_discord_tag'])
        if not civ_id:
            continue
        cursor.execute(f"""
            INSERT INTO civilization_members
                (civ_id, profile_id, role, enabled_features, can_approve_personal_uploads,
                 joined_at, joined_via)
            VALUES (?, ?, 'leader', NULL, ?, {now_iso}, 'founder')
            ON CONFLICT(civ_id, profile_id) DO NOTHING
        """, (civ_id, row['profile_id'], row['can_approve_personal_uploads'] or 0))
        leaders_inserted += cursor.rowcount
    logger.info(f"Migration 1.80.0: inserted {leaders_inserted} leader memberships")

    # ----- 5c. sub-admin memberships -----
    # Two source patterns to migrate:
    #   (i)  tier-3 with parent_profile_id set → sub_admin under that parent's civ
    #   (ii) tier-3 with parent_profile_id IS NULL but additional_discord_tags
    #        populated (the "Haven sub-admin" legacy pattern) → one sub_admin
    #        membership row per tag in the list
    cursor.execute("""
        SELECT id AS profile_id, parent_profile_id, additional_discord_tags,
               enabled_features, can_approve_personal_uploads
        FROM user_profiles
        WHERE tier = 3
    """)
    sub_admins_inserted = 0
    for row in cursor.fetchall():
        per_member_features = row['enabled_features']  # carried as override
        cap = row['can_approve_personal_uploads'] or 0

        if row['parent_profile_id']:
            # Pattern (i): single civ — the parent leader's civ
            cursor.execute("""
                SELECT partner_discord_tag FROM user_profiles WHERE id = ?
            """, (row['parent_profile_id'],))
            parent = cursor.fetchone()
            parent_tag = parent['partner_discord_tag'] if parent else None
            target_tags = [parent_tag] if parent_tag else []
        else:
            # Pattern (ii): Haven sub-admin — fan out across all civs they cover
            try:
                target_tags = json.loads(row['additional_discord_tags'] or '[]')
            except Exception:
                target_tags = []
            if not target_tags:
                # legacy Haven sub-admin with no extras → default to Haven civ
                target_tags = ['Haven']

        for tag in target_tags:
            civ_id = civ_id_by_tag.get(tag)
            if not civ_id:
                logger.warning(f"Migration 1.80.0: sub_admin profile={row['profile_id']} references civ '{tag}' which doesn't exist; skipping")
                continue
            cursor.execute(f"""
                INSERT INTO civilization_members
                    (civ_id, profile_id, role, enabled_features, can_approve_personal_uploads,
                     joined_at, joined_via)
                VALUES (?, ?, 'sub_admin', ?, ?, {now_iso}, 'legacy_migration')
                ON CONFLICT(civ_id, profile_id) DO NOTHING
            """, (civ_id, row['profile_id'], per_member_features, cap))
            sub_admins_inserted += cursor.rowcount
    logger.info(f"Migration 1.80.0: inserted {sub_admins_inserted} sub_admin memberships")

    # ----- 5d. war_room_enrollment.civ_id backfill -----
    # Each enrollment row has a partner_id pointing at the legacy
    # partner_accounts table. Join through that → discord_tag → civilizations
    # to get the new civ_id. Rows whose partner_id doesn't resolve get
    # logged + left at NULL; the war_room routes will treat NULL civ_id as
    # an unenrolled / orphaned row.
    cursor.execute("""
        UPDATE war_room_enrollment
        SET civ_id = (
            SELECT civilizations.id
            FROM partner_accounts
            JOIN civilizations ON civilizations.tag = partner_accounts.discord_tag
            WHERE partner_accounts.id = war_room_enrollment.partner_id
        )
        WHERE civ_id IS NULL
    """)
    war_rows_filled = cursor.rowcount
    cursor.execute("SELECT COUNT(*) FROM war_room_enrollment WHERE civ_id IS NULL")
    war_rows_orphan = cursor.fetchone()[0]
    if war_rows_orphan:
        logger.warning(f"Migration 1.80.0: {war_rows_orphan} war_room_enrollment rows have no resolvable civ_id (partner_id points to a missing or untagged partner_accounts row)")
    logger.info(f"Migration 1.80.0: backfilled civ_id on {war_rows_filled} war_room_enrollment rows")

    # ----- 5e. user_profiles.home_civ_id default -----
    # For existing partners, default home_civ_id to their own civ — so
    # logging in pre-selects their familiar civ in the new "acting as"
    # selector. Sub-admins default to NULL (first membership wins at runtime).
    cursor.execute("""
        UPDATE user_profiles
        SET home_civ_id = (
            SELECT id FROM civilizations WHERE tag = user_profiles.partner_discord_tag
        )
        WHERE tier = 2 AND home_civ_id IS NULL
          AND partner_discord_tag IS NOT NULL AND partner_discord_tag != ''
    """)
    home_civ_set = cursor.rowcount
    logger.info(f"Migration 1.80.0: set home_civ_id on {home_civ_set} partner profiles")

    conn.commit()

    # ----- 6. Sanity check -----
    cursor.execute("SELECT COUNT(*) FROM civilizations")
    total_civs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM civilization_members")
    total_members = cursor.fetchone()[0]
    cursor.execute("SELECT role, COUNT(*) FROM civilization_members GROUP BY role")
    role_counts = {r[0]: r[1] for r in cursor.fetchall()}
    logger.info(
        f"Migration 1.80.0 complete: {total_civs} civilizations, {total_members} memberships ({role_counts})"
    )

    # Restore the connection's prior row_factory so later migrations and the
    # rest of startup see the same shape they had before this migration ran.
    conn.row_factory = prev_factory


@register_migration("1.81.0", "Re-scrub 'RealityMode.Normal' → 'Normal' rows that arrived after migration 1.79.0")
def migration_1_81_0(conn):
    """Stale Haven Extractor builds (≤1.9.7) still persist and submit the
    Python enum repr `RealityMode.Normal` as the literal `reality` string.
    Migration 1.79.0 cleaned the existing rows, but ran only once — new
    submissions from unfixed extractor installs keep poisoning the column
    (50 rows visible on prod as of 2026-05-12, surfacing as a phantom
    "RealityMode.Normal" reality card in the Systems Browser).

    Layer 2 defense (`constants.normalize_reality`) is now applied at every
    backend intake site so no new rows can land. This migration scrubs the
    rows that landed between 1.79.0 running and the intake guard shipping.
    Same UPDATEs as 1.79.0 — idempotent, no-op once clean.
    """
    cursor = conn.cursor()
    cursor.execute("UPDATE systems SET reality = 'Normal' WHERE reality = 'RealityMode.Normal'")
    fixed = cursor.rowcount
    cursor.execute("UPDATE pending_systems SET reality = 'Normal' WHERE reality = 'RealityMode.Normal'")
    fixed += cursor.rowcount
    cursor.execute("UPDATE regions SET reality = 'Normal' WHERE reality = 'RealityMode.Normal'")
    fixed += cursor.rowcount
    if fixed:
        logger.info(f"Migration 1.81.0: re-scrubbed {fixed} 'RealityMode.Normal' rows")


@register_migration("1.82.0", "Add pending_systems.discoveries_draft column for co-submitted discoveries")
def migration_1_82_0(conn):
    """Wizard public submit path can now co-submit discoveries with the
    system. Draft discoveries ride along on the pending_systems row as a JSON
    array; on approval the helper resolves planet/moon names to IDs against
    the just-inserted planets/moons and inserts directly into `discoveries`
    with status='approved' — they inherit the system's review decision.

    Idempotent: column-presence guarded. Nullable, no default, no backfill.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(pending_systems)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'discoveries_draft' not in cols:
        cursor.execute("ALTER TABLE pending_systems ADD COLUMN discoveries_draft TEXT")
        logger.info("Migration 1.82.0: added pending_systems.discoveries_draft column")
    else:
        logger.info("Migration 1.82.0: discoveries_draft column already present")


@register_migration("1.83.0", "Backfill user_profiles.enabled_features from civilization_members so existing leaders get permissions")
def migration_1_83_0(conn):
    """Closes the "elevated to leader but has no permissions" gap for
    users who were added to civilizations before _recompute_profile_features
    existed. The session reads user_profiles.enabled_features at login;
    until this migration, that column was only populated by the legacy
    PUT /api/admin/profiles/{id}/tier path. Members promoted via the new
    POST /api/civilizations/{id}/members flow had tier=2 in their profile
    but features=[], so route guards refused them.

    For each profile with at least one ACTIVE civ membership, computes
    the union of effective features (per-member override if set, else
    civ default) and writes it back to user_profiles.enabled_features.
    Mirrors the runtime _recompute_profile_features helper exactly.

    Super admins (tier 1) skipped — their permission comes from user_type
    check, not the features list. Idempotent — re-running produces the
    same result and overwrites stale data.
    """
    import json as _json
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT cm.profile_id
        FROM civilization_members cm
        JOIN civilizations c ON c.id = cm.civ_id
        JOIN user_profiles up ON up.id = cm.profile_id
        WHERE c.is_active = 1 AND up.tier != 1
    """)
    profile_ids = [r[0] for r in cursor.fetchall()]

    updated = 0
    for profile_id in profile_ids:
        cursor.execute("""
            SELECT cm.enabled_features, c.enabled_features_default
            FROM civilization_members cm
            JOIN civilizations c ON c.id = cm.civ_id
            WHERE cm.profile_id = ? AND c.is_active = 1
        """, (profile_id,))
        union = set()
        for row in cursor.fetchall():
            per_member_raw, default_raw = row[0], row[1]
            try:
                per_member = _json.loads(per_member_raw) if per_member_raw else None
            except (TypeError, ValueError):
                per_member = None
            try:
                default = _json.loads(default_raw) if default_raw else []
            except (TypeError, ValueError):
                default = []
            effective = per_member if per_member is not None else default
            if isinstance(effective, list):
                union.update(effective)

        cursor.execute(
            "UPDATE user_profiles SET enabled_features = ? WHERE id = ?",
            (_json.dumps(sorted(union)), profile_id),
        )
        updated += 1

    logger.info(f"Migration 1.83.0: backfilled enabled_features for {updated} profiles with active civ memberships")


@register_migration("1.84.0", "Role-aware feature backfill: civ leaders/co-leaders get the full leader feature set")
def migration_1_84_0(conn):
    """Fixes the deeper gap that v1.83.0 couldn't: a leader's features were
    still sourced from civilizations.enabled_features_default (or a per-member
    override the UI never sent). Civs founded via the new "Found new
    civilization" modal start with an EMPTY default — the feature grid is
    framed for sub-admins and is usually left unticked — so v1.83.0 faithfully
    backfilled those leaders with [] (union of empty == empty). Result: brand
    new partners still showed tier=2 / "Partner" with zero feature access and
    couldn't see Approvals.

    From now on leader / co_leader access is granted BY ROLE in the runtime
    helper _recompute_profile_features. This migration re-runs that role-aware
    union for every profile with at least one ACTIVE civ membership so existing
    (and freshly-broken) leaders are repaired on deploy without waiting for the
    next civ event.

    The leader feature set is inlined here on purpose — a migration is a frozen
    historical record. It mirrors constants.LEADER_FEATURES as of 1.84.0; if
    that constant later changes, a new migration handles the re-sync.

    Super admins (tier 1) skipped. Idempotent — re-running produces the same
    result and overwrites stale data.
    """
    import json as _json
    cursor = conn.cursor()

    # Mirrors constants.LEADER_FEATURES at the time of this migration.
    leader_features = {
        'system_create', 'system_edit', 'approvals', 'batch_approvals',
        'stats', 'settings', 'csv_import', 'war_room',
    }

    cursor.execute("""
        SELECT DISTINCT cm.profile_id
        FROM civilization_members cm
        JOIN civilizations c ON c.id = cm.civ_id
        JOIN user_profiles up ON up.id = cm.profile_id
        WHERE c.is_active = 1 AND up.tier != 1
    """)
    profile_ids = [r[0] for r in cursor.fetchall()]

    updated = 0
    for profile_id in profile_ids:
        cursor.execute("""
            SELECT cm.role, cm.enabled_features, c.enabled_features_default
            FROM civilization_members cm
            JOIN civilizations c ON c.id = cm.civ_id
            WHERE cm.profile_id = ? AND c.is_active = 1
        """, (profile_id,))
        union = set()
        for row in cursor.fetchall():
            role, per_member_raw, default_raw = row[0], row[1], row[2]
            if role in ('leader', 'co_leader'):
                union.update(leader_features)
                continue
            try:
                per_member = _json.loads(per_member_raw) if per_member_raw else None
            except (TypeError, ValueError):
                per_member = None
            try:
                default = _json.loads(default_raw) if default_raw else []
            except (TypeError, ValueError):
                default = []
            effective = per_member if per_member is not None else default
            if isinstance(effective, list):
                union.update(effective)

        cursor.execute(
            "UPDATE user_profiles SET enabled_features = ? WHERE id = ?",
            (_json.dumps(sorted(union)), profile_id),
        )
        updated += 1

    logger.info(f"Migration 1.84.0: role-aware re-sync of enabled_features for {updated} profiles with active civ memberships")


@register_migration("1.85.0", "Add latitude/longitude columns to discoveries + pending_discoveries")
def migration_1_85_0(conn):
    """Discoveries can now carry a precise surface coordinate (the lat/long
    NMS shows in the analysis visor) in addition to the existing free-text
    location_name and the planet/moon FK links.

    Two nullable REAL columns on each of the live `discoveries` table and the
    `pending_discoveries` queue. Only meaningful for planet/moon discoveries
    (space discoveries leave them NULL). No backfill — existing rows stay NULL.

    Idempotent: each ADD COLUMN is column-presence guarded.
    """
    cursor = conn.cursor()
    for table in ('discoveries', 'pending_discoveries'):
        cursor.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in cursor.fetchall()}
        for col in ('latitude', 'longitude'):
            if col not in cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} REAL")
                logger.info(f"Migration 1.85.0: added {table}.{col} column")
            else:
                logger.info(f"Migration 1.85.0: {table}.{col} already present")


# Data fix: the pre-1.10 Haven Extractor "always Euclid" bug. MidGenXGamer's extractor
# uploads were all stamped Euclid (galaxy + procedural system/region names) when he was
# actually galaxy-hopping. He confirmed the galaxy for THREE upload sessions (times in
# EDT, which is how the UTC submission_date maps to "his" day):
#   * 2026-05-18 session  -> Hyades       (idx 4)   [128 systems]
#   * 2026-05-19 session  -> Ickjamatew   (idx 5)   [44 systems]  EXCEPT the last system
#                            of that session, where he crossed the Ickjamatew core into
#                            Budullangr (idx 6) [1 system]
#   * 2026-05-24 session  -> Budullangr   (idx 6)   [36 systems]
# Two further sessions (2026-05-23 = 10 systems, 2026-05-25 = 53 systems) have NO
# confirmed galaxy and are intentionally LEFT as Euclid for a follow-up migration.
@register_migration("1.86.0", "Backfill MidGenX extractor 'always Euclid' systems (3 confirmed sessions) + region names")
def migration_1_86_0(conn):
    """Fix galaxy + galaxy-dependent procedural names for MidGenXGamer's three
    galaxy-confirmed extractor upload sessions (209 pending systems + their regions).

    Per-row safe and idempotent:
      * System galaxy is rewritten in BOTH the `galaxy` column and the system_data
        JSON blob's `galaxy` key (approval reads the blob; the column drives the UI).
      * The system NAME is regenerated for the correct galaxy ONLY when the stored
        name exactly equals the Euclid procgen name for that glyph — proof it was the
        buggy Euclid fallback, not a real/custom name the player set. (At authoring
        time all 209 matched; the guard keeps re-runs and any edge row safe.)
      * For each affected voxel, the live `regions` row and the already-approved
        `pending_region_names` record are moved to the correct galaxy with a
        regenerated region name. A phantom Euclid region (no other live system at that
        voxel) is moved in place; a voxel still shared by another live Euclid system
        gets a NEW correct-galaxy row while the Euclid row is left intact. A custom
        (non-procgen) region name is preserved across the move.
      * Scoped to source='haven_extractor', galaxy='Euclid', submitter LIKE 'MidGenX%',
        and the three confirmed session days — so manual rows, other contributors, and
        the two unconfirmed sessions are never touched. Once a row leaves galaxy='Euclid'
        it no longer matches, so a second run is a no-op.

    Requires nms_namegen (vendored under backend/nms_namegen/, deployed with this code).
    """
    import json as _json
    from nms_namegen.system import systemName
    from nms_namegen.region import regionName

    cur = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    DAY_GAL = {'2026-05-18': 4, '2026-05-19': 5, '2026-05-24': 6}
    GAL_NAME = {4: 'Hyades', 5: 'Ickjamatew', 6: 'Budullangr'}
    CONFIRMED_DAYS = tuple(DAY_GAL.keys())

    rows = cur.execute(
        """SELECT id, submission_date, system_data, glyph_code,
                  region_x, region_y, region_z, COALESCE(reality,'Normal')
           FROM pending_systems
           WHERE status='pending' AND source='haven_extractor' AND galaxy='Euclid'
             AND COALESCE(personal_discord_username, submitted_by) LIKE 'MidGenX%'
             AND substr(submission_date,1,10) IN (?,?,?)""",
        CONFIRMED_DAYS,
    ).fetchall()

    if not rows:
        logger.info("Migration 1.86.0: no matching Euclid MidGenX pending systems — nothing to do")
        return

    # The single last system of the 2026-05-19 session crossed the core into Budullangr.
    s19 = [r for r in rows if r[1][:10] == '2026-05-19']
    s19_last_id = max(s19, key=lambda r: r[1])[0] if s19 else None

    voxel_gal = {}  # (reality, rx, ry, rz) -> galaxy_idx  (unambiguous: verified at authoring)
    sys_fixed = name_regen = 0
    for rid, sdate, sdata, glyph, rx, ry, rz, reality in rows:
        gidx = DAY_GAL[sdate[:10]]
        if rid == s19_last_id:
            gidx = 6  # Budullangr
        gname = GAL_NAME[gidx]
        try:
            blob = _json.loads(sdata)
        except Exception:
            logger.warning(f"Migration 1.86.0: pending system {rid} has unparseable system_data — skipped")
            continue
        blob['galaxy'] = gname
        new_name = None
        try:
            pc = int(glyph, 16)
            if blob.get('name') == systemName(pc, 0):
                new_name = systemName(pc, gidx)
                blob['name'] = new_name
        except Exception as e:
            logger.warning(f"Migration 1.86.0: name regen skipped for system {rid} (glyph={glyph}): {e}")
        cur.execute(
            "UPDATE pending_systems SET galaxy=?, system_data=?, "
            "system_name=COALESCE(?, system_name) WHERE id=?",
            (gname, _json.dumps(blob), new_name, rid),
        )
        sys_fixed += 1
        if new_name:
            name_regen += 1
        voxel_gal[(reality, rx, ry, rz)] = gidx

    logger.info(
        f"Migration 1.86.0: fixed {sys_fixed} pending systems "
        f"({name_regen} names regenerated) across {len(voxel_gal)} voxels"
    )

    reg_moved = reg_inserted = reg_skipped = prn_fixed = name_collisions = 0
    for (reality, rx, ry, rz), gidx in voxel_gal.items():
        gname = GAL_NAME[gidx]
        coords_pc = (ry << 24) | (rz << 12) | rx
        euc_region_name = regionName(coords_pc, 0)
        new_region_name = regionName(coords_pc, gidx)

        # Correct-galaxy region already exists at this voxel — don't duplicate it.
        if cur.execute(
            "SELECT 1 FROM regions WHERE reality=? AND galaxy=? "
            "AND region_x=? AND region_y=? AND region_z=?",
            (reality, gname, rx, ry, rz),
        ).fetchone():
            reg_skipped += 1
            continue

        euc = cur.execute(
            "SELECT id, custom_name, discord_tag, source FROM regions "
            "WHERE reality=? AND galaxy='Euclid' AND region_x=? AND region_y=? AND region_z=?",
            (reality, rx, ry, rz),
        ).fetchone()
        euc_id = euc[0] if euc else None
        euc_custom = euc[1] if euc else None
        # A player-set custom region name (not the Euclid procgen) is preserved verbatim;
        # otherwise the name is regenerated for the correct galaxy.
        keep_custom = bool(euc_custom) and euc_custom != euc_region_name
        desired = euc_custom if keep_custom else new_region_name

        # regions enforces UNIQUE(custom_name). If the regenerated name is already taken
        # by a DIFFERENT region (NMS region names repeat across the universe), leave this
        # voxel untouched and flag it — the system itself is still correctly re-galaxied.
        if not keep_custom:
            taken = cur.execute("SELECT id FROM regions WHERE custom_name=?", (desired,)).fetchone()
            if taken and (euc_id is None or taken[0] != euc_id):
                name_collisions += 1
                logger.warning(
                    f"Migration 1.86.0: region-name collision at ({reality},{gname},{rx},{ry},{rz}) "
                    f"-> '{desired}' already used by region id {taken[0]}; region left as-is for manual fix"
                )
                continue

        other_live = cur.execute(
            "SELECT COUNT(*) FROM systems WHERE COALESCE(reality,'Normal')=? "
            "AND COALESCE(galaxy,'Euclid')='Euclid' AND region_x=? AND region_y=? AND region_z=?",
            (reality, rx, ry, rz),
        ).fetchone()[0]

        if euc and other_live == 0:
            # Phantom Euclid region (only this batch referenced it) — move it in place.
            cur.execute(
                "UPDATE regions SET galaxy=?, custom_name=?, updated_at=? WHERE id=?",
                (gname, desired, now, euc_id),
            )
            reg_moved += 1
        else:
            # Voxel still shared by another live Euclid system (or no Euclid row): add a
            # fresh correct-galaxy row and leave any Euclid row intact.
            cur.execute(
                "INSERT INTO regions (region_x,region_y,region_z,custom_name,created_at,"
                "updated_at,discord_tag,reality,galaxy,source) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (rx, ry, rz, desired, now, now,
                 (euc[2] if euc else None), reality, gname, (euc[3] if euc else None) or 'haven_extractor'),
            )
            reg_inserted += 1

        for pid, pname in cur.execute(
            "SELECT id, proposed_name FROM pending_region_names "
            "WHERE status='approved' AND galaxy='Euclid' AND COALESCE(reality,'Normal')=? "
            "AND region_x=? AND region_y=? AND region_z=? "
            "AND COALESCE(personal_discord_username, submitted_by) LIKE 'MidGenX%'",
            (reality, rx, ry, rz),
        ).fetchall():
            pnew = pname if (pname and pname != euc_region_name) else desired
            cur.execute(
                "UPDATE pending_region_names SET galaxy=?, proposed_name=? WHERE id=?",
                (gname, pnew, pid),
            )
            prn_fixed += 1

    logger.info(
        f"Migration 1.86.0: regions moved={reg_moved} inserted={reg_inserted} "
        f"skipped_existing={reg_skipped} name_collisions_deferred={name_collisions}; "
        f"region-name records fixed={prn_fixed}"
    )


@register_migration("1.87.0", "Add pending_discoveries.edit_discovery_id for discovery edits through the approval queue")
def migration_1_87_0(conn):
    """Discoveries can now be EDITED through the approval queue, mirroring the
    system edit flow (pending_systems.edit_system_id).

    A nullable `edit_discovery_id` on `pending_discoveries`: when set, the
    submission is an EDIT of the live `discoveries` row with that id, and
    `approve_discovery` UPDATEs that row in place instead of INSERTing a new
    one. NULL = a brand-new discovery submission (unchanged behavior).

    Idempotent: column-presence guarded.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(pending_discoveries)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'edit_discovery_id' not in cols:
        cursor.execute("ALTER TABLE pending_discoveries ADD COLUMN edit_discovery_id INTEGER")
        logger.info("Migration 1.87.0: added pending_discoveries.edit_discovery_id column")
    else:
        logger.info("Migration 1.87.0: pending_discoveries.edit_discovery_id already present")


@register_migration("1.88.0", "Drop global UNIQUE(custom_name) on regions — NMS region names legitimately repeat across galaxies")
def migration_1_88_0(conn):
    """Region names are NOT globally unique.

    NMS region names repeat across the universe (the same procgen region name
    appears in different galaxies, and even at the same voxel in different
    galaxies — e.g. "Muxali Terminus" exists in both Euclid and Odyalutai).
    The legacy `regions` schema carried an inline `UNIQUE(custom_name)` that
    forbade this, so approving a region name already used anywhere else failed
    with `sqlite3.IntegrityError: UNIQUE constraint failed: regions.custom_name`
    and 500'd. The only real uniqueness rule is one row per voxel, enforced by
    UNIQUE(reality, galaxy, region_x, region_y, region_z), which we keep.

    SQLite can't DROP a constraint (the UNIQUE(custom_name) created an
    auto-index that DROP INDEX can't remove), so we rebuild the table without
    it. Column set + indexes are detected/recreated dynamically so this works
    against both local dev and the production Pi schema (which has `source`).

    Idempotent: if the live table's DDL no longer contains 'UNIQUE (custom_name)'
    the rebuild is skipped.
    """
    cursor = conn.cursor()

    # Idempotency: inspect the current table DDL. SQLite normalises the inline
    # constraint to "UNIQUE (custom_name)" (with a space) in sqlite_master.sql.
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='regions'")
    row = cursor.fetchone()
    table_sql = (row[0] if row else '') or ''
    normalised = table_sql.replace(' ', '').lower()
    if 'unique(custom_name)' not in normalised:
        logger.info("Migration 1.88.0: regions already has no UNIQUE(custom_name) — skipping rebuild")
        return

    logger.info("Rebuilding regions table to drop the global UNIQUE(custom_name) constraint...")

    cursor.execute("DROP TABLE IF EXISTS regions_new")

    # Detect existing columns so we carry `source` (and anything else) through.
    cursor.execute("PRAGMA table_info(regions)")
    existing_cols = {r[1] for r in cursor.fetchall()}
    has_source = 'source' in existing_cols

    # New table: SAME shape as current, MINUS UNIQUE(custom_name).
    cursor.execute(f'''
        CREATE TABLE regions_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_x INTEGER NOT NULL,
            region_y INTEGER NOT NULL,
            region_z INTEGER NOT NULL,
            custom_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            discord_tag TEXT,
            reality TEXT DEFAULT 'Normal',
            galaxy TEXT DEFAULT 'Euclid',
            {"source TEXT NOT NULL DEFAULT 'manual'," if has_source else ""}
            UNIQUE(reality, galaxy, region_x, region_y, region_z)
        )
    ''')

    copy_cols = ['id', 'region_x', 'region_y', 'region_z', 'custom_name',
                 'created_at', 'updated_at', 'discord_tag']
    select_exprs = list(copy_cols)
    copy_cols.append('reality')
    select_exprs.append("COALESCE(reality, 'Normal')" if 'reality' in existing_cols else "'Normal'")
    copy_cols.append('galaxy')
    select_exprs.append("COALESCE(galaxy, 'Euclid')" if 'galaxy' in existing_cols else "'Euclid'")
    if has_source:
        copy_cols.append('source')
        select_exprs.append("COALESCE(source, 'manual')")

    cols_str = ', '.join(copy_cols)
    select_str = ', '.join(select_exprs)
    # Plain INSERT (not OR IGNORE): the composite key is already satisfied by
    # the live data, and we want a loud failure if that assumption is ever wrong.
    cursor.execute(f"INSERT INTO regions_new ({cols_str}) SELECT {select_str} FROM regions")
    cursor.execute("SELECT COUNT(*) FROM regions_new")
    copied = cursor.fetchone()[0]

    cursor.execute("DROP TABLE regions")
    cursor.execute("ALTER TABLE regions_new RENAME TO regions")
    logger.info(f"Migration 1.88.0: rebuilt regions ({copied} rows) without UNIQUE(custom_name)")

    # Recreate the non-constraint indexes (dropped with the old table). The
    # composite UNIQUE is already enforced by the inline constraint above; the
    # explicit UNIQUE index is recreated to match the prior prod schema exactly.
    cursor.execute('''CREATE UNIQUE INDEX IF NOT EXISTS idx_regions_reality_galaxy_coords
                      ON regions(reality, galaxy, region_x, region_y, region_z)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_regions_coords_scoped
                      ON regions(region_x, region_y, region_z, reality, galaxy)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_regions_coords
                      ON regions(region_x, region_y, region_z)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_regions_discord_tag
                      ON regions(discord_tag)''')
    logger.info("Migration 1.88.0: recreated regions indexes")


@register_migration("1.89.0", "Add event_id to pending_systems/systems/pending_discoveries/discoveries for real event participation")
def migration_1_89_0(conn):
    """Events become real, opt-in competitions.

    Previously an "event" was just a (name, discord_tag, start, end) window and
    the leaderboard sliced the entire pending_systems / discoveries firehose by
    tag + date. There was no link between a submission and an event, so events
    couldn't overlap, nobody opted in, and rejected/pending rows inflated the
    standings.

    This adds a nullable `event_id` to the two submission tables and the two
    live tables. A submission is tagged with the event the submitter picked at
    upload time (mirrors the existing `expedition_id` pattern); on approval the
    id is carried to the live `systems` / `discoveries` row so the leaderboard
    counts APPROVED rows only, grouped by event_id.

    Four nullable INTEGER columns. No backfill — existing rows stay NULL (i.e.
    not part of any event). Idempotent: each ADD COLUMN is column-presence
    guarded. Indexes added for the per-event leaderboard scans.
    """
    cursor = conn.cursor()
    for table in ('pending_systems', 'systems', 'pending_discoveries', 'discoveries'):
        cursor.execute(f"PRAGMA table_info({table})")
        cols = {row[1] for row in cursor.fetchall()}
        if 'event_id' not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN event_id INTEGER")
            logger.info(f"Migration 1.89.0: added {table}.event_id column")
        else:
            logger.info(f"Migration 1.89.0: {table}.event_id already present")
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_event_id ON {table}(event_id)"
        )


@register_migration("1.90.0", "Add systems.is_fully_charted (S+ flag) + re-score all systems with description dropped from scoring")
def migration_1_90_0(conn):
    """S+ grade flag + scoring-formula refresh.

    Two coupled changes ship together:

      1. Adds `is_fully_charted INTEGER DEFAULT 0` to `systems`. S+ ("fully
         charted") is a checklist that sits ON TOP of the S grade — a discovery
         on every planet AND moon, wonder notes on every planet, a documented
         base, and a recorded station (when the system has one). It can't be
         derived from the score alone, so SQL grade ladders read this column.

      2. Re-scores EVERY system with the current formula. The 2026-06-19 change
         dropped `description` from the System Extra category (free-text prose,
         repurposed to stash the procgen name — never a real completeness
         signal), so stored scores shift and must be recomputed. The same pass
         runs the S+ checklist and sets is_fully_charted.

    Reuses services.completeness.update_completeness_score so the migration
    applies exactly the live formula (single source of truth) and writes both
    is_complete and is_fully_charted per system. Idempotent: the ADD COLUMN is
    presence-guarded; a re-run recomputes to the same values.
    """
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(systems)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'is_fully_charted' not in cols:
        cursor.execute("ALTER TABLE systems ADD COLUMN is_fully_charted INTEGER DEFAULT 0")
        logger.info("Migration 1.90.0: added systems.is_fully_charted column")
    else:
        logger.info("Migration 1.90.0: systems.is_fully_charted already present")

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_systems_is_fully_charted ON systems(is_fully_charted)"
    )

    # services.completeness reads rows as dicts → it needs sqlite3.Row. Migration
    # connections don't set a row_factory by default, so set it for the rescore
    # pass and restore it afterwards (mirrors the 1.80.0 pattern at line ~6073).
    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        from services.completeness import update_completeness_score
        id_cursor = conn.cursor()
        id_cursor.execute("SELECT id FROM systems")
        system_ids = [row[0] for row in id_cursor.fetchall()]
        score_cursor = conn.cursor()
        logger.info(
            f"Migration 1.90.0: re-scoring {len(system_ids)} systems "
            f"(description dropped from System Extra) + running S+ checklist..."
        )
        splus = 0
        for sys_id in system_ids:
            result = update_completeness_score(score_cursor, sys_id)
            if result.get('is_fully_charted'):
                splus += 1
        logger.info(
            f"Migration 1.90.0: re-scored {len(system_ids)} systems; "
            f"{splus} qualify as S+ (fully charted)"
        )
    finally:
        conn.row_factory = prev_factory


@register_migration("1.91.0", "Re-score systems to repair stale is_fully_charted (S+) drift from one-off discovery relinks + late discovery promotion")
def migration_1_91_0(conn):
    """Repair the cached S+ flag (`systems.is_fully_charted`) for systems whose
    completeness inputs changed AFTER their last score was computed.

    Why this is needed even though 1.90.0 already re-scored everything: that pass
    ran while several showcase systems still had their discoveries ORPHANED
    (planet_id pointing at planet rows that had been deleted-and-reinserted with
    new ids — the recurring "Mabaya planet tags wiped" bug). Those discoveries
    were re-pointed by a one-off prod data script (Master Haven 1.79.0) that
    fixed `discoveries.planet_id` but did NOT re-run update_completeness_score,
    so the systems are stuck at `is_fully_charted = 0` even though they now pass
    the S+ checklist live. The system detail page recomputes live and shows S+,
    but the systems list / map / search / posters read this cached column and
    show plain S — they disagree. (Going forward, approve_discovery now recomputes
    the parent system, and both planet-rebuild paths already recompute after
    relinking, so this drift can't recur from the code paths.)

    Re-scoring every system is the same proven, idempotent repair 1.90.0 used:
    it applies the live formula via services.completeness.update_completeness_score
    (single source of truth) and rewrites is_complete + is_fully_charted. A re-run
    converges to the same values.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(systems)")
    cols = {row[1] for row in cursor.fetchall()}
    if 'is_fully_charted' not in cols:
        # 1.90.0 should have added it; guard so this migration is order-safe.
        cursor.execute("ALTER TABLE systems ADD COLUMN is_fully_charted INTEGER DEFAULT 0")
        logger.info("Migration 1.91.0: added missing systems.is_fully_charted column")

    # update_completeness_score reads rows as dicts → needs sqlite3.Row (mirrors 1.90.0).
    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        from services.completeness import update_completeness_score
        id_cursor = conn.cursor()
        id_cursor.execute("SELECT id FROM systems")
        system_ids = [row[0] for row in id_cursor.fetchall()]
        score_cursor = conn.cursor()
        logger.info(f"Migration 1.91.0: re-scoring {len(system_ids)} systems to repair S+ drift...")
        splus = 0
        for sys_id in system_ids:
            result = update_completeness_score(score_cursor, sys_id)
            if result.get('is_fully_charted'):
                splus += 1
        logger.info(
            f"Migration 1.91.0: re-scored {len(system_ids)} systems; "
            f"{splus} now qualify as S+ (fully charted)"
        )
    finally:
        conn.row_factory = prev_factory


@register_migration("1.92.0", "Backfill tracking mirror rows for historical direct-saved systems")
def migration_1_92_0(conn):
    """Make past trusted DIRECT saves visible to analytics/events retroactively.

    Direct admin/partner saves (POST /api/save_system) bypassed the pending
    queue, so they never created a pending_systems row. The analytics layer
    (submission leaderboard, community-stats, submissions-timeline, partner
    overview) and the public contributors list / activity timeline all derive
    from pending_systems, and the events leaderboards key off systems.event_id —
    so a direct-saved system was effectively untracked everywhere except the
    raw systems table and the approval audit log. As of Master Haven 1.84.0 a
    direct save writes a pre-approved pending_systems "mirror" row going forward;
    this migration creates one such row per historical direct-saved system so
    older trusted contributions are counted too.

    Source of truth for "which systems were direct-saved" is approval_audit_log:
    save_system has recorded every direct save as action 'direct_add'/'direct_edit'
    with the target system_id embedded in its notes ("...(system_id: <uuid>)").
    Using the audit log is precise — it cannot mistake a queue-approved system
    (which has no audit row of those actions) for a direct save, so there is no
    risk of double-counting normal submissions. ONE mirror row per system (the
    creation credit), attributed from the live systems row; forward parity
    (one row per save) applies only to new saves, not retroactive edits.

    Idempotent: skips any system that already has a mirror row
    (api_key_name='direct_save'), and skips audit rows whose system no longer
    exists.
    """
    import re as _re
    from datetime import timezone as _tz

    # Username normalizer — reuse the canonical helper; fall back to an inline
    # copy of the documented rule (strip @, strip #discriminator, lowercase) if
    # the import isn't available during early init.
    try:
        from services.auth_service import normalize_username_for_dedup as _norm
    except Exception:
        def _norm(u):
            if not u:
                return 'unknown'
            s = str(u).lstrip('@').strip()
            s = _re.sub(r'#\d{4}$', '', s)
            if '#' in s:
                s = s.split('#')[0]
            return s.strip().lower() or 'unknown'

    cursor = conn.cursor()

    # approval_audit_log may not exist on a brand-new DB.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='approval_audit_log'")
    if not cursor.fetchone():
        logger.info("Migration 1.92.0: no approval_audit_log table; nothing to backfill")
        return

    cursor.execute("""
        SELECT notes FROM approval_audit_log
        WHERE action IN ('direct_add', 'direct_edit')
          AND submission_type = 'system'
        ORDER BY timestamp ASC
    """)
    pat = _re.compile(r'system_id:\s*([0-9a-fA-F-]{6,})')
    sys_ids = []
    seen = set()
    for row in cursor.fetchall():
        m = pat.search(row[0] or '')
        if not m:
            continue
        sid = m.group(1)
        if sid not in seen:
            seen.add(sid)
            sys_ids.append(sid)  # earliest audit row first → creation credit

    if not sys_ids:
        logger.info("Migration 1.92.0: no direct-saved systems found in audit log")
        return

    prev_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        read_cur = conn.cursor()
        write_cur = conn.cursor()
        created = 0
        skipped = 0
        for sid in sys_ids:
            read_cur.execute("SELECT * FROM systems WHERE id = ?", (sid,))
            srow = read_cur.fetchone()
            if not srow:
                skipped += 1
                continue
            s = dict(srow)

            # Idempotency: one mirror row per system.
            read_cur.execute(
                "SELECT 1 FROM pending_systems WHERE edit_system_id = ? AND api_key_name = 'direct_save' LIMIT 1",
                (sid,),
            )
            if read_cur.fetchone():
                skipped += 1
                continue

            raw_name = s.get('discovered_by') or s.get('personal_discord_username') or 'Unknown'
            norm = _norm(raw_name)
            sub_date = s.get('discovered_at') or s.get('created_at') or datetime.now(_tz.utc).isoformat()
            galaxy = s.get('galaxy') or 'Euclid'
            reality = s.get('reality') or 'Normal'
            blob = json.dumps({
                'id': sid,
                'name': s.get('name'),
                'galaxy': galaxy,
                'reality': reality,
                'glyph_code': s.get('glyph_code'),
                'discovered_by': s.get('discovered_by'),
                'discord_tag': s.get('discord_tag'),
            })
            write_cur.execute('''
                INSERT INTO pending_systems
                (submitted_by, submission_date, system_data, status,
                 reviewed_by, review_date,
                 system_name, system_region, galaxy, reality,
                 glyph_code, glyph_planet, glyph_solar_system,
                 region_x, region_y, region_z, game_mode,
                 source, api_key_name, discord_tag, personal_discord_username,
                 edit_system_id, username_normalized,
                 game_version, expedition_id, event_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                raw_name,
                sub_date,
                blob,
                'approved',
                raw_name,
                sub_date,
                s.get('name'),
                galaxy,
                galaxy,
                reality,
                s.get('glyph_code'),
                s.get('glyph_planet') or 0,
                s.get('glyph_solar_system') or 1,
                s.get('region_x'),
                s.get('region_y'),
                s.get('region_z'),
                s.get('game_mode') or 'Normal',
                'manual',
                'direct_save',
                s.get('discord_tag'),
                s.get('personal_discord_username'),
                sid,
                norm,
                s.get('game_version'),
                s.get('expedition_id'),
                s.get('event_id'),
            ))
            created += 1
        logger.info(
            f"Migration 1.92.0: created {created} tracking mirror rows for historical "
            f"direct-saved systems ({skipped} skipped: missing system or already mirrored)"
        )
    finally:
        conn.row_factory = prev_factory


@register_migration("1.93.0", "Normalize planets/moons materials into canonical resource names (typo/case/separator cleanup; no resource data dropped)")
def migration_1_93_0(conn):
    """Clean up the free-text `materials` resource lists in place.

    The materials column accumulated case variants ("Copper"/"copper"), typos
    ("Cooper", "kupfer", "uramium"), and bad separators ("Salt. Gold. Copper",
    "Copper and uranium"). That made the resource filter — which now matches
    against materials — noisy, and any dropdown built from it a 170-entry mess.

    resource_catalog.normalize_materials() re-splits each cell, maps every token
    we can recognize to its canonical resource name, and PRESERVES anything it
    can't (genuine non-resources like "Dissonance" / "High Sentinel Activity"),
    so no information is lost. Idempotent: a second run normalizes to the same
    string and changes nothing. The migration runner snapshots the DB first.
    """
    from resource_catalog import normalize_materials
    cursor = conn.cursor()
    total_changed = 0
    for table in ("planets", "moons"):
        cursor.execute("PRAGMA table_info(%s)" % table)
        cols = {row[1] for row in cursor.fetchall()}
        if 'materials' not in cols:
            continue
        cursor.execute(
            f"SELECT id, materials FROM {table} "
            f"WHERE materials IS NOT NULL AND TRIM(materials) != ''")
        rows = cursor.fetchall()
        upd = conn.cursor()
        changed = 0
        for row in rows:
            pid, mats = row[0], row[1]
            norm = normalize_materials(mats)
            if norm != (mats or '').strip():
                upd.execute(f"UPDATE {table} SET materials = ? WHERE id = ?", (norm, pid))
                changed += 1
        total_changed += changed
        logger.info(f"Migration 1.93.0: normalized materials on {changed}/{len(rows)} {table}")
    logger.info(f"Migration 1.93.0: total {total_changed} rows normalized")


@register_migration("1.94.0", "War Room is civ-scoped: drop war_room from the by-role leader grant; re-sync enabled_features so only members of civs that enabled War Room keep it")
def migration_1_94_0(conn):
    """Repairs the over-grant that migration 1.84.0 baked in: it wrote
    'war_room' onto EVERY civ leader/co_leader by role, so any civ leader saw
    the War Room tab regardless of whether their civ was ever given the feature
    (e.g. IEA's leader had 'war_room' while the IEA civ default did not).

    War Room is now CIV-SCOPED: a member sees it only if one of their ACTIVE
    civs has 'war_room' in civilizations.enabled_features_default. It is no
    longer part of the by-role LEADER_FEATURES set (constants.py).

    Re-runs the role-aware union (mirroring _recompute_profile_features as of
    1.94.0) for every profile with at least one active civ membership:
      - leader / co_leader -> LEADER_FEATURES   (which NO LONGER includes war_room)
      - sub_admin          -> per-member override else civ default
      - any role           -> + 'war_room' iff that civ's default contains it

    Scope is intentionally limited to profiles WITH active civ memberships
    (matching 1.83.0 / 1.84.0): legacy Haven sub-admins with no civ_members row
    keep their directly-assigned features and are not touched. Super admins
    (tier 1) skipped — their access comes from user_type, not the features list.
    The leader feature set is inlined because a migration is a frozen historical
    record. Idempotent — re-running produces the same result.
    """
    import json as _json
    cursor = conn.cursor()

    # Mirrors constants.LEADER_FEATURES as of 1.94.0 — note: NO 'war_room'.
    leader_features = {
        'system_create', 'system_edit', 'approvals', 'batch_approvals',
        'stats', 'settings', 'csv_import',
    }

    # Belt-and-suspenders: any civ with an ACTIVE war_room_enrollment must keep
    # War Room. Ensure 'war_room' is in its enabled_features_default so the
    # member re-sync below grants it. (On current prod every enrolled civ already
    # has it via the 1.80.0 partner_accounts->civ backfill; this only guards an
    # enrolled civ whose default was later edited to drop war_room.)
    cursor.execute("""
        SELECT DISTINCT c.id, c.enabled_features_default
        FROM war_room_enrollment wre
        JOIN civilizations c ON c.id = wre.civ_id
        WHERE wre.is_active = 1
    """)
    for civ_id, def_raw in cursor.fetchall():
        try:
            feats = _json.loads(def_raw) if def_raw else []
        except (TypeError, ValueError):
            feats = []
        if not isinstance(feats, list):
            feats = []
        if 'war_room' not in feats:
            feats.append('war_room')
            cursor.execute(
                "UPDATE civilizations SET enabled_features_default = ? WHERE id = ?",
                (_json.dumps(feats), civ_id),
            )

    cursor.execute("""
        SELECT DISTINCT cm.profile_id
        FROM civilization_members cm
        JOIN civilizations c ON c.id = cm.civ_id
        JOIN user_profiles up ON up.id = cm.profile_id
        WHERE c.is_active = 1 AND up.tier != 1
    """)
    profile_ids = [r[0] for r in cursor.fetchall()]

    updated = 0
    for profile_id in profile_ids:
        cursor.execute("""
            SELECT cm.role, cm.enabled_features, c.enabled_features_default
            FROM civilization_members cm
            JOIN civilizations c ON c.id = cm.civ_id
            WHERE cm.profile_id = ? AND c.is_active = 1
        """, (profile_id,))
        union = set()
        for row in cursor.fetchall():
            role, per_member_raw, default_raw = row[0], row[1], row[2]
            try:
                default = _json.loads(default_raw) if default_raw else []
            except (TypeError, ValueError):
                default = []
            if not isinstance(default, list):
                default = []
            if 'war_room' in default:
                union.add('war_room')
            if role in ('leader', 'co_leader'):
                union.update(leader_features)
                continue
            try:
                per_member = _json.loads(per_member_raw) if per_member_raw else None
            except (TypeError, ValueError):
                per_member = None
            effective = per_member if per_member is not None else default
            if isinstance(effective, list):
                union.update(effective)

        cursor.execute(
            "UPDATE user_profiles SET enabled_features = ? WHERE id = ?",
            (_json.dumps(sorted(union)), profile_id),
        )
        updated += 1

    logger.info(f"Migration 1.94.0: civ-scoped War Room re-sync of enabled_features for {updated} profiles")


@register_migration("1.95.0", "Sub-admins start at zero permissions: convert NULL (civ-default-inheriting) sub_admin overrides to an explicit empty set, then re-sync enabled_features")
def migration_1_95_0(conn):
    """Enforce 'a sub-admin has no permissions until a leader explicitly grants
    them'.

    Before this, a sub_admin whose civilization_members.enabled_features was
    NULL silently inherited the civ's enabled_features_default — so the moment
    someone was added as a sub-admin they could already approve / create / edit
    (whatever the civ default happened to seed), with nobody having granted it.
    That implicit grant is the "permissions feel broken" complaint.

    add_member (routes/civilizations.py) now seeds new sub-admins with an empty
    override ([]). This migration brings EXISTING sub-admins in line: every
    sub_admin membership with a NULL override is set to '[]' (explicit zero).
    The civ default is preserved and stays available as a one-click "Reset to
    civ default" opt-in in the UI, so a leader can restore the standard set
    deliberately.

    Sub-admins who already had an EXPLICIT override (an array, even empty) are
    untouched — someone chose those. Leaders / co_leaders are untouched (their
    override is NULL by design; they're full-power by role). After flipping the
    memberships, every affected profile's materialized
    user_profiles.enabled_features is recomputed (mirrors
    _recompute_profile_features as of 1.95.0: leader -> LEADER_FEATURES;
    sub_admin -> override-else-civ-default with war_room stripped from the
    override; + war_room iff the civ default has it).

    Idempotent: a re-run finds no NULL sub_admin overrides (already '[]') and
    no-ops. Operational note: on deploy, existing sub-admins drop to zero access
    until their leader re-grants (or clicks "Reset to civ default").
    """
    import json as _json
    cursor = conn.cursor()

    # Mirrors constants.LEADER_FEATURES as of 1.95.0 (no 'war_room' — civ-scoped).
    leader_features = {
        'system_create', 'system_edit', 'approvals', 'batch_approvals',
        'stats', 'settings', 'csv_import',
    }

    # 1. Flip every IMPLICIT (NULL-override) sub_admin grant to an explicit
    #    empty set so the "no permissions until granted" rule applies to
    #    existing sub-admins. Explicit overrides (arrays) are someone's choice
    #    and are left alone.
    cursor.execute("""
        UPDATE civilization_members
        SET enabled_features = '[]'
        WHERE role = 'sub_admin' AND enabled_features IS NULL
    """)
    flipped = cursor.rowcount

    # 2. Re-sync the materialized feature list for EVERY profile with an active
    #    civ membership (matching the sweep scope of 1.94.0), not just the
    #    flipped ones. This also retroactively strips any war_room that an old
    #    buggy UI leaked into a sub-admin's explicit override (1.94.0 re-synced
    #    but did NOT strip war_room from sub_admin overrides). Idempotent.
    cursor.execute("""
        SELECT DISTINCT cm.profile_id
        FROM civilization_members cm
        JOIN civilizations c ON c.id = cm.civ_id
        JOIN user_profiles up ON up.id = cm.profile_id
        WHERE c.is_active = 1 AND up.tier != 1
    """)
    affected_profiles = [r[0] for r in cursor.fetchall()]

    resynced = 0
    for profile_id in affected_profiles:
        cursor.execute("""
            SELECT cm.role, cm.enabled_features, c.enabled_features_default
            FROM civilization_members cm
            JOIN civilizations c ON c.id = cm.civ_id
            WHERE cm.profile_id = ? AND c.is_active = 1
        """, (profile_id,))
        union = set()
        for row in cursor.fetchall():
            role, per_member_raw, default_raw = row[0], row[1], row[2]
            try:
                default = _json.loads(default_raw) if default_raw else []
            except (TypeError, ValueError):
                default = []
            if not isinstance(default, list):
                default = []
            if 'war_room' in default:
                union.add('war_room')
            if role in ('leader', 'co_leader'):
                union.update(leader_features)
                continue
            try:
                per_member = _json.loads(per_member_raw) if per_member_raw else None
            except (TypeError, ValueError):
                per_member = None
            effective = per_member if per_member is not None else default
            if isinstance(effective, list):
                # war_room never granted via a sub-admin override (civ-scoped only).
                union.update(f for f in effective if f != 'war_room')

        cursor.execute(
            "UPDATE user_profiles SET enabled_features = ? WHERE id = ? AND tier != 1",
            (_json.dumps(sorted(union)), profile_id),
        )
        resynced += 1

    logger.info(
        f"Migration 1.95.0: zeroed {flipped} implicit sub_admin override(s); "
        f"re-synced enabled_features for {resynced} profile(s)"
    )
