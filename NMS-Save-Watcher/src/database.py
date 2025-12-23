"""
Local SQLite Database for NMS Save Watcher.
Tracks processed discoveries to prevent duplicate submissions.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from contextlib import contextmanager
from dataclasses import dataclass

from .extractor import SystemData

logger = logging.getLogger('nms_watcher.database')


@dataclass
class ProcessedSystem:
    """Record of a processed system."""
    id: int
    glyph_code: str
    galaxy: str
    system_name: str
    submitted: bool
    submitted_at: Optional[str]
    submission_status: str
    first_seen: str
    last_seen: str


class LocalDatabase:
    """Local SQLite database for tracking processed discoveries."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the database.

        Args:
            db_path: Path to the database file (default: data/watcher.db)
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'watcher.db'

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Processed systems table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_systems (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    glyph_code TEXT NOT NULL,
                    galaxy TEXT NOT NULL,
                    system_name TEXT,
                    submitted INTEGER DEFAULT 0,
                    submitted_at TEXT,
                    submission_status TEXT DEFAULT 'pending',
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    UNIQUE(glyph_code, galaxy)
                )
            ''')

            # Processed planets table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processed_planets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_id INTEGER NOT NULL,
                    planet_name TEXT NOT NULL,
                    biome TEXT,
                    first_seen TEXT NOT NULL,
                    FOREIGN KEY (system_id) REFERENCES processed_systems(id)
                )
            ''')

            # Submission history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS submission_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    glyph_code TEXT NOT NULL,
                    galaxy TEXT NOT NULL,
                    system_name TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    timestamp TEXT NOT NULL
                )
            ''')

            # Queued extractions table (stores full extraction data for manual upload)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS queued_extractions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    glyph_code TEXT NOT NULL,
                    galaxy TEXT NOT NULL,
                    system_name TEXT,
                    planet_count INTEGER DEFAULT 0,
                    extraction_data TEXT NOT NULL,
                    queued_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    UNIQUE(glyph_code, galaxy)
                )
            ''')

            # Statistics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_glyph ON processed_systems(glyph_code)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_systems_galaxy ON processed_systems(galaxy)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_timestamp ON submission_history(timestamp)')

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Get a database connection with context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def is_processed(self, glyph_code: str, galaxy: str) -> bool:
        """
        Check if a system has already been processed.

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name

        Returns:
            True if system was already processed
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM processed_systems
                WHERE glyph_code = ? AND galaxy = ?
            ''', (glyph_code, galaxy))
            return cursor.fetchone() is not None

    def mark_processed(self, system: SystemData, submitted: bool = False,
                      status: str = 'pending', message: str = '') -> int:
        """
        Mark a system as processed.

        Args:
            system: SystemData that was processed
            submitted: Whether it was submitted to API
            status: Submission status
            message: Status message

        Returns:
            Database ID of the record
        """
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Try to insert or update
            cursor.execute('''
                INSERT INTO processed_systems
                (glyph_code, galaxy, system_name, submitted, submitted_at, submission_status, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(glyph_code, galaxy) DO UPDATE SET
                    system_name = excluded.system_name,
                    submitted = excluded.submitted,
                    submitted_at = CASE WHEN excluded.submitted = 1 THEN excluded.submitted_at ELSE submitted_at END,
                    submission_status = excluded.submission_status,
                    last_seen = excluded.last_seen
            ''', (
                system.glyph_code,
                system.galaxy,
                system.name,
                1 if submitted else 0,
                now if submitted else None,
                status,
                now,
                now
            ))

            system_id = cursor.lastrowid

            # Add planets
            for planet in system.planets:
                cursor.execute('''
                    INSERT OR IGNORE INTO processed_planets
                    (system_id, planet_name, biome, first_seen)
                    VALUES (?, ?, ?, ?)
                ''', (system_id, planet.name, planet.biome, now))

            # Record in history
            if submitted:
                cursor.execute('''
                    INSERT INTO submission_history
                    (glyph_code, galaxy, system_name, status, message, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (system.glyph_code, system.galaxy, system.name, status, message, now))

            conn.commit()

            # Update stats
            self._update_stats(conn)

            return system_id

    def update_submission_status(self, glyph_code: str, galaxy: str,
                                 status: str, message: str = ''):
        """Update the submission status of a processed system."""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE processed_systems
                SET submission_status = ?, submitted = 1, submitted_at = ?
                WHERE glyph_code = ? AND galaxy = ?
            ''', (status, now, glyph_code, galaxy))

            # Record in history
            cursor.execute('''
                INSERT INTO submission_history
                (glyph_code, galaxy, system_name, status, message, timestamp)
                SELECT glyph_code, galaxy, system_name, ?, ?, ?
                FROM processed_systems
                WHERE glyph_code = ? AND galaxy = ?
            ''', (status, message, now, glyph_code, galaxy))

            conn.commit()

    def get_processed_system(self, glyph_code: str, galaxy: str) -> Optional[ProcessedSystem]:
        """Get a processed system record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM processed_systems
                WHERE glyph_code = ? AND galaxy = ?
            ''', (glyph_code, galaxy))

            row = cursor.fetchone()
            if row:
                return ProcessedSystem(
                    id=row['id'],
                    glyph_code=row['glyph_code'],
                    galaxy=row['galaxy'],
                    system_name=row['system_name'],
                    submitted=bool(row['submitted']),
                    submitted_at=row['submitted_at'],
                    submission_status=row['submission_status'],
                    first_seen=row['first_seen'],
                    last_seen=row['last_seen']
                )
            return None

    def get_recent_submissions(self, limit: int = 50) -> list[dict]:
        """Get recent submission history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM submission_history
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Total processed
            cursor.execute('SELECT COUNT(*) FROM processed_systems')
            stats['total_processed'] = cursor.fetchone()[0]

            # Total submitted
            cursor.execute('SELECT COUNT(*) FROM processed_systems WHERE submitted = 1')
            stats['total_submitted'] = cursor.fetchone()[0]

            # By status
            cursor.execute('''
                SELECT submission_status, COUNT(*) as count
                FROM processed_systems
                GROUP BY submission_status
            ''')
            stats['by_status'] = {row['submission_status']: row['count'] for row in cursor.fetchall()}

            # By galaxy
            cursor.execute('''
                SELECT galaxy, COUNT(*) as count
                FROM processed_systems
                GROUP BY galaxy
                ORDER BY count DESC
                LIMIT 10
            ''')
            stats['by_galaxy'] = {row['galaxy']: row['count'] for row in cursor.fetchall()}

            # Total planets
            cursor.execute('SELECT COUNT(*) FROM processed_planets')
            stats['total_planets'] = cursor.fetchone()[0]

            # Recent activity
            cursor.execute('''
                SELECT COUNT(*) FROM submission_history
                WHERE timestamp > datetime('now', '-1 hour')
            ''')
            stats['submissions_last_hour'] = cursor.fetchone()[0]

            cursor.execute('''
                SELECT COUNT(*) FROM submission_history
                WHERE timestamp > datetime('now', '-24 hours')
            ''')
            stats['submissions_last_24h'] = cursor.fetchone()[0]

            return stats

    def _update_stats(self, conn: sqlite3.Connection):
        """Update cached statistics."""
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO stats (key, value)
            VALUES ('last_updated', ?)
        ''', (now,))

    def get_unsubmitted_systems(self, limit: int = 100) -> list[dict]:
        """Get systems that haven't been submitted yet."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM processed_systems
                WHERE submitted = 0
                ORDER BY first_seen DESC
                LIMIT ?
            ''', (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def clear_old_history(self, days: int = 30):
        """Clear submission history older than specified days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM submission_history
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            ''', (days,))
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {deleted} old history records")
            return deleted

    def reset_failed_for_retry(self, glyph_code: str, galaxy: str) -> bool:
        """
        Reset a failed submission so it can be retried.

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name

        Returns:
            True if system was reset
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM processed_systems
                WHERE glyph_code = ? AND galaxy = ?
                AND submission_status IN ('error', 'pending')
            ''', (glyph_code, galaxy))
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.info(f"Reset {glyph_code} in {galaxy} for retry")
            return deleted > 0

    def reset_all_failed_for_retry(self) -> int:
        """
        Reset all failed submissions so they can be retried.

        Returns:
            Number of systems reset
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM processed_systems
                WHERE submission_status = 'error'
            ''')
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Reset {deleted} failed systems for retry")
            return deleted

    def save_live_extraction(self, extraction_data: dict) -> int:
        """
        Save a live extraction from the Haven Extractor game mod.

        Args:
            extraction_data: Raw extraction data from Haven Extractor

        Returns:
            Database ID of the record
        """
        now = datetime.now().isoformat()

        # Extract key fields
        system_name = extraction_data.get('system_name', 'Unknown')
        glyph_code = extraction_data.get('glyph_code', '')
        galaxy = extraction_data.get('galaxy_name', 'Euclid')

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert or update system record
            cursor.execute('''
                INSERT INTO processed_systems
                (glyph_code, galaxy, system_name, submitted, submission_status, first_seen, last_seen)
                VALUES (?, ?, ?, 0, 'live_extraction', ?, ?)
                ON CONFLICT(glyph_code, galaxy) DO UPDATE SET
                    system_name = excluded.system_name,
                    last_seen = excluded.last_seen
            ''', (glyph_code, galaxy, system_name, now, now))

            system_id = cursor.lastrowid

            # Add planets from extraction
            for planet in extraction_data.get('planets', []):
                planet_name = planet.get('planet_name', f"Planet {planet.get('planet_index', 0) + 1}")
                biome = planet.get('biome', 'Unknown')
                cursor.execute('''
                    INSERT OR IGNORE INTO processed_planets
                    (system_id, planet_name, biome, first_seen)
                    VALUES (?, ?, ?, ?)
                ''', (system_id, planet_name, biome, now))

            # Record in history
            cursor.execute('''
                INSERT INTO submission_history
                (glyph_code, galaxy, system_name, status, message, timestamp)
                VALUES (?, ?, ?, 'live_extraction', 'From Haven Extractor mod', ?)
            ''', (glyph_code, galaxy, system_name, now))

            conn.commit()
            self._update_stats(conn)

            logger.info(f"Saved live extraction: {system_name} [{glyph_code}]")
            return system_id

    def save_live_extraction_status(self, glyph_code: str, galaxy: str,
                                     status: str, message: str = '') -> None:
        """
        Update the status of a live extraction submission.

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name
            status: Submission status (submitted, duplicate, queued, error)
            message: Optional status message
        """
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Update system status
            cursor.execute('''
                UPDATE processed_systems
                SET submission_status = ?,
                    submitted = CASE WHEN ? = 'submitted' THEN 1 ELSE submitted END,
                    submitted_at = CASE WHEN ? = 'submitted' THEN ? ELSE submitted_at END,
                    last_seen = ?
                WHERE glyph_code = ? AND galaxy = ?
            ''', (status, status, status, now, now, glyph_code, galaxy))

            # Record in history
            cursor.execute('''
                INSERT INTO submission_history
                (glyph_code, galaxy, system_name, status, message, timestamp)
                SELECT glyph_code, galaxy, system_name, ?, ?, ?
                FROM processed_systems
                WHERE glyph_code = ? AND galaxy = ?
            ''', (status, message or f'Live extraction: {status}', now, glyph_code, galaxy))

            conn.commit()
            logger.debug(f"Updated extraction status: {glyph_code} -> {status}")

    # =========================================================================
    # Queued Extraction Methods (for manual upload)
    # =========================================================================

    def queue_extraction(self, extraction_data: dict) -> int:
        """
        Queue an extraction for manual upload later.

        If the same system is queued again (e.g., after scanning more planets),
        it will update the existing queue entry with the new data.

        Args:
            extraction_data: Raw extraction data from Haven Extractor

        Returns:
            Database ID of the queued record
        """
        import json as json_module
        now = datetime.now().isoformat()

        system_name = extraction_data.get('system_name', 'Unknown')
        glyph_code = extraction_data.get('glyph_code', '')
        galaxy = extraction_data.get('galaxy_name', 'Euclid')
        planet_count = extraction_data.get('planet_count', 0)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Serialize full extraction data as JSON
            extraction_json = json_module.dumps(extraction_data)

            # Insert or update (upsert) - update if more planets
            cursor.execute('''
                INSERT INTO queued_extractions
                (glyph_code, galaxy, system_name, planet_count, extraction_data, queued_at, updated_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
                ON CONFLICT(glyph_code, galaxy) DO UPDATE SET
                    system_name = excluded.system_name,
                    planet_count = CASE
                        WHEN excluded.planet_count > planet_count THEN excluded.planet_count
                        ELSE planet_count
                    END,
                    extraction_data = CASE
                        WHEN excluded.planet_count > planet_count THEN excluded.extraction_data
                        ELSE extraction_data
                    END,
                    updated_at = excluded.updated_at
            ''', (glyph_code, galaxy, system_name, planet_count, extraction_json, now, now))

            queue_id = cursor.lastrowid
            conn.commit()

            logger.info(f"Queued extraction: {system_name} [{glyph_code}] ({planet_count} planets)")
            return queue_id

    def get_queued_extractions(self, status: str = 'pending') -> list[dict]:
        """
        Get all queued extractions with specified status.

        Args:
            status: Filter by status ('pending', 'uploaded', 'error', or 'all')

        Returns:
            List of queued extraction records
        """
        import json as json_module

        with self._get_connection() as conn:
            cursor = conn.cursor()

            if status == 'all':
                cursor.execute('''
                    SELECT * FROM queued_extractions
                    ORDER BY updated_at DESC
                ''')
            else:
                cursor.execute('''
                    SELECT * FROM queued_extractions
                    WHERE status = ?
                    ORDER BY updated_at DESC
                ''', (status,))

            results = []
            for row in cursor.fetchall():
                record = dict(row)
                # Parse the JSON extraction data
                try:
                    record['extraction_data'] = json_module.loads(record['extraction_data'])
                except:
                    pass
                results.append(record)

            return results

    def get_queued_extraction(self, glyph_code: str, galaxy: str) -> Optional[dict]:
        """
        Get a specific queued extraction.

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name

        Returns:
            Queued extraction record or None
        """
        import json as json_module

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM queued_extractions
                WHERE glyph_code = ? AND galaxy = ?
            ''', (glyph_code, galaxy))

            row = cursor.fetchone()
            if row:
                record = dict(row)
                try:
                    record['extraction_data'] = json_module.loads(record['extraction_data'])
                except:
                    pass
                return record
            return None

    def update_queued_status(self, glyph_code: str, galaxy: str, status: str) -> bool:
        """
        Update the status of a queued extraction.

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name
            status: New status ('uploaded', 'error', 'pending')

        Returns:
            True if updated successfully
        """
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE queued_extractions
                SET status = ?, updated_at = ?
                WHERE glyph_code = ? AND galaxy = ?
            ''', (status, now, glyph_code, galaxy))

            updated = cursor.rowcount > 0
            conn.commit()
            return updated

    def remove_queued_extraction(self, glyph_code: str, galaxy: str) -> bool:
        """
        Remove a queued extraction (after successful upload).

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name

        Returns:
            True if removed successfully
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM queued_extractions
                WHERE glyph_code = ? AND galaxy = ?
            ''', (glyph_code, galaxy))

            removed = cursor.rowcount > 0
            conn.commit()
            if removed:
                logger.info(f"Removed queued extraction: {glyph_code} in {galaxy}")
            return removed

    def get_queue_count(self) -> dict:
        """
        Get counts of queued extractions by status.

        Returns:
            Dict with counts by status
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM queued_extractions
                GROUP BY status
            ''')

            counts = {'total': 0, 'pending': 0, 'uploaded': 0, 'error': 0}
            for row in cursor.fetchall():
                counts[row['status']] = row['count']
                counts['total'] += row['count']

            return counts

    def clear_uploaded_queue(self) -> int:
        """
        Clear all successfully uploaded extractions from queue.

        Returns:
            Number of records removed
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM queued_extractions
                WHERE status = 'uploaded'
            ''')

            removed = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {removed} uploaded extractions from queue")
            return removed
