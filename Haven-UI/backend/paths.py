"""
Master Haven - Centralized Path Configuration
Handles path resolution for different deployment environments.
Eliminates hardcoded paths throughout the codebase.
"""

import os
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger('master_haven.paths')

class HavenPaths:
    """
    Centralized path configuration for Master Haven.

    Automatically detects deployment environment and finds resources
    without requiring hardcoded paths in the codebase.
    """

    def __init__(self):
        """Initialize path configuration with intelligent detection."""
        # Detect directory structure
        # This file is now at Haven-UI/backend/paths.py
        self.backend_dir = Path(__file__).resolve().parent
        self.haven_ui_dir_default = self.backend_dir.parent  # Haven-UI/
        self.root = self.haven_ui_dir_default.parent  # Master-Haven/

        logger.info(f"Master Haven root directory: {self.root}")

        # Environment-based overrides (highest priority)
        self.haven_ui_dir = self._resolve_haven_ui_dir()
        self.haven_db = self._resolve_haven_db()

    def _resolve_haven_ui_dir(self) -> Path:
        """Resolve Haven UI directory."""
        # 1. Check environment variable
        env_path = os.getenv('HAVEN_UI_DIR')
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.info(f"Haven UI directory from env: {path}")
                return path

        # 2. Use the default (we're already inside Haven-UI)
        if self.haven_ui_dir_default.exists() and self.haven_ui_dir_default.is_dir():
            logger.info(f"Haven UI directory found: {self.haven_ui_dir_default}")
            return self.haven_ui_dir_default

        # 3. Check relative to project root (fallback)
        candidates = [
            self.root / 'Haven-UI',
        ]

        for path in candidates:
            if path.exists() and path.is_dir():
                logger.info(f"Haven UI directory found: {path}")
                return path

        # 4. Default to expected location
        logger.warning(f"Haven UI directory not found, using default: {self.haven_ui_dir_default}")
        return self.haven_ui_dir_default

    def _resolve_haven_db(self) -> Optional[Path]:
        """Resolve Haven database path."""
        # 1. Check environment variable (highest priority)
        env_path = os.getenv('HAVEN_DB_PATH')
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.info(f"Haven database from env: {path}")
                return path

        # 2. Search common locations
        search_paths = [
            # Project structure paths
            self.haven_ui_dir / 'data' / 'haven_ui.db',
            self.root / 'Haven-UI' / 'data' / 'haven_ui.db',
            self.root.parent / 'Haven-UI' / 'data' / 'haven_ui.db',
            # Legacy paths
            self.root / 'Haven-UI' / 'data' / 'VH-Database.db',
            # Current working directory
            Path.cwd() / 'Haven-UI' / 'data' / 'haven_ui.db',
        ]

        for path in search_paths:
            if path.exists() and path.is_file():
                logger.info(f"Haven database found: {path}")
                return path

        logger.warning("Haven database not found in expected locations")
        return None

    def find_database(self, preferred_name: str = 'haven_ui.db') -> Optional[Path]:
        """
        Search for a database file in common locations.

        Args:
            preferred_name: Name of the database file to find

        Returns:
            Path to database if found, None otherwise
        """
        search_locations = [
            # Haven UI data directory
            self.haven_ui_dir / 'data' / preferred_name,
            # Project root data directory
            self.root / 'data' / preferred_name,
            # Current working directory
            Path.cwd() / preferred_name,
            Path.cwd() / 'data' / preferred_name,
        ]

        for path in search_locations:
            if path.exists() and path.is_file():
                logger.debug(f"Found database '{preferred_name}' at: {path}")
                return path

        logger.warning(f"Database '{preferred_name}' not found in expected locations")
        return None

    def find_data_file(self, filename: str, subdirs: Optional[List[str]] = None) -> Optional[Path]:
        """
        Search for a data file in common data directories.

        Args:
            filename: Name of the file to find
            subdirs: Optional list of subdirectories to check within data dirs

        Returns:
            Path to file if found, None otherwise
        """
        if subdirs is None:
            subdirs = ['']

        search_bases = [
            self.haven_ui_dir / 'data',
            self.root / 'data',
            Path.cwd() / 'data',
        ]

        for base in search_bases:
            for subdir in subdirs:
                if subdir:
                    search_path = base / subdir / filename
                else:
                    search_path = base / filename

                if search_path.exists() and search_path.is_file():
                    logger.debug(f"Found data file '{filename}' at: {search_path}")
                    return search_path

        logger.warning(f"Data file '{filename}' not found")
        return None

    def get_backup_dir(self) -> Path:
        """Get the backup directory path, creating it if needed."""
        backup_dir = self.haven_ui_dir / 'data' / 'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    def get_logs_dir(self, component: str = 'main') -> Path:
        """Get logs directory for a specific component, creating it if needed."""
        if component == 'haven-ui':
            logs_dir = self.haven_ui_dir / 'logs'
        else:
            logs_dir = self.root / 'logs'

        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    def get_data_dir(self, component: str = 'main') -> Path:
        """Get data directory for a specific component, creating it if needed."""
        if component == 'haven-ui':
            data_dir = self.haven_ui_dir / 'data'
        else:
            data_dir = self.root / 'data'

        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def __repr__(self) -> str:
        """String representation showing key paths."""
        return (
            f"HavenPaths(\n"
            f"  root={self.root},\n"
            f"  haven_ui_dir={self.haven_ui_dir},\n"
            f"  haven_db={self.haven_db}\n"
            f")"
        )


# Global instance for easy import
haven_paths = HavenPaths()


def get_haven_paths() -> HavenPaths:
    """
    Get the global HavenPaths instance.

    Returns:
        Global HavenPaths singleton
    """
    return haven_paths


# Convenience functions for common operations
def get_haven_database() -> Optional[Path]:
    """Get the Haven database path."""
    return haven_paths.haven_db


def get_project_root() -> Path:
    """Get the Master Haven project root directory."""
    return haven_paths.root


if __name__ == '__main__':
    # Test/debug output when run directly
    logging.basicConfig(level=logging.INFO)
    print("Master Haven Path Configuration")
    print("=" * 60)
    print(haven_paths)
    print("\nEnvironment Variables:")
    print(f"  HAVEN_UI_DIR: {os.getenv('HAVEN_UI_DIR', '(not set)')}")
    print(f"  HAVEN_DB_PATH: {os.getenv('HAVEN_DB_PATH', '(not set)')}")
    print("\nDatabase Search:")
    print(f"  Haven DB: {get_haven_database()}")
