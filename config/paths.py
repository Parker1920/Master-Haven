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
        # Detect project root (where config/ directory is located)
        self.config_dir = Path(__file__).resolve().parent
        self.root = self.config_dir.parent

        logger.info(f"Master Haven root directory: {self.root}")

        # Environment-based overrides (highest priority)
        self.haven_ui_dir = self._resolve_haven_ui_dir()
        self.haven_db = self._resolve_haven_db()
        self.keeper_bot_dir = self._resolve_keeper_bot_dir()
        self.keeper_db = self._resolve_keeper_db()

    def _resolve_haven_ui_dir(self) -> Path:
        """Resolve Haven UI directory."""
        # 1. Check environment variable
        env_path = os.getenv('HAVEN_UI_DIR')
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.info(f"Haven UI directory from env: {path}")
                return path

        # 2. Check relative to project root
        candidates = [
            self.root / 'Haven-UI',
            self.root.parent / 'Haven-UI',
        ]

        for path in candidates:
            if path.exists() and path.is_dir():
                logger.info(f"Haven UI directory found: {path}")
                return path

        # 3. Default to expected location
        default_path = self.root / 'Haven-UI'
        logger.warning(f"Haven UI directory not found, using default: {default_path}")
        return default_path

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

    def _resolve_keeper_bot_dir(self) -> Path:
        """Resolve Keeper bot directory."""
        candidates = [
            self.root / 'keeper-discord-bot-main',
            self.root.parent / 'keeper-discord-bot-main',
        ]

        for path in candidates:
            if path.exists() and path.is_dir():
                logger.info(f"Keeper bot directory found: {path}")
                return path

        # Default
        default_path = self.root / 'keeper-discord-bot-main'
        logger.warning(f"Keeper bot directory not found, using default: {default_path}")
        return default_path

    def _resolve_keeper_db(self) -> Optional[Path]:
        """Resolve Keeper database path."""
        # 1. Check environment variable
        env_path = os.getenv('KEEPER_DB_PATH')
        if env_path:
            path = Path(env_path)
            if path.exists():
                logger.info(f"Keeper database from env: {path}")
                return path

        # 2. Check relative to keeper bot directory
        candidates = [
            self.keeper_bot_dir / 'data' / 'keeper.db',
            self.root / 'keeper-discord-bot-main' / 'data' / 'keeper.db',
        ]

        for path in candidates:
            if path.exists() and path.is_file():
                logger.info(f"Keeper database found: {path}")
                return path

        # Default (may not exist yet)
        default_path = self.keeper_bot_dir / 'data' / 'keeper.db'
        return default_path

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
            # Keeper bot data directory
            self.keeper_bot_dir / 'data' / preferred_name,
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
            self.keeper_bot_dir / 'data',
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
        if component == 'keeper':
            logs_dir = self.keeper_bot_dir / 'logs'
        elif component == 'haven-ui':
            logs_dir = self.haven_ui_dir / 'logs'
        else:
            logs_dir = self.root / 'logs'

        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir

    def get_data_dir(self, component: str = 'main') -> Path:
        """Get data directory for a specific component, creating it if needed."""
        if component == 'keeper':
            data_dir = self.keeper_bot_dir / 'data'
        elif component == 'haven-ui':
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
            f"  haven_db={self.haven_db},\n"
            f"  keeper_bot_dir={self.keeper_bot_dir},\n"
            f"  keeper_db={self.keeper_db}\n"
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


def get_keeper_database() -> Optional[Path]:
    """Get the Keeper database path."""
    return haven_paths.keeper_db


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
    print(f"  KEEPER_DB_PATH: {os.getenv('KEEPER_DB_PATH', '(not set)')}")
    print("\nDatabase Search:")
    print(f"  Haven DB: {get_haven_database()}")
    print(f"  Keeper DB: {get_keeper_database()}")
