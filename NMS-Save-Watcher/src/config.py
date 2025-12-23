"""
Configuration management for NMS Save Watcher.
Handles loading/saving settings and auto-detection of paths.
"""

import os
import json
import re
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger('nms_watcher.config')

# Default configuration
DEFAULT_CONFIG = {
    "api": {
        "base_url": "http://localhost:8005",
        "key": ""
    },
    "watcher": {
        "save_path": "auto",  # "auto" for auto-detection or explicit path
        "save_slot": 1,
        "debounce_seconds": 2,
        "enabled": True
    },
    "notifications": {
        "enabled": True,
        "on_success": True,
        "on_duplicate": False,
        "on_error": True,
        "on_offline_queue": True
    },
    "dashboard": {
        "port": 8006,
        "host": "127.0.0.1"
    },
    "debug": {
        "enabled": False,
        "log_file": "watcher.log",
        "log_level": "INFO"
    }
}

# Save slot to filename mapping
SAVE_SLOTS = {
    1: "save.hg",      # Auto-save slot 1
    2: "save2.hg",     # Manual save slot 1
    3: "save3.hg",     # Auto-save slot 2
    4: "save4.hg",     # Manual save slot 2
    5: "save5.hg",     # Auto-save slot 3
    6: "save6.hg",     # Manual save slot 3
    7: "save7.hg",     # Auto-save slot 4
    8: "save8.hg",     # Manual save slot 4
    9: "save9.hg",     # Auto-save slot 5
    10: "save10.hg",   # Manual save slot 5
}


def get_app_dir() -> Path:
    """Get the application directory (where the exe/script is located)."""
    # When running as a script
    return Path(__file__).resolve().parent.parent


def get_config_path() -> Path:
    """Get the path to the configuration file."""
    return get_app_dir() / "config.json"


def get_data_dir() -> Path:
    """Get the data directory for local database and cache."""
    data_dir = get_app_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def find_nms_save_path() -> Optional[Path]:
    """
    Auto-detect the NMS Steam save folder.
    Returns the path to the save folder or None if not found.
    """
    appdata = os.environ.get('APPDATA')
    if not appdata:
        logger.warning("APPDATA environment variable not found")
        return None

    nms_base = Path(appdata) / 'HelloGames' / 'NMS'

    if not nms_base.exists():
        logger.warning(f"NMS save folder not found at {nms_base}")
        return None

    # Find st_* folder (Steam ID folder)
    steam_folders = []
    for folder in nms_base.iterdir():
        if folder.is_dir() and re.match(r'^st_\d+$', folder.name):
            steam_folders.append(folder)

    if not steam_folders:
        logger.warning("No Steam save folders (st_*) found")
        return None

    # If multiple Steam accounts, use the most recently modified
    if len(steam_folders) > 1:
        steam_folders.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        logger.info(f"Multiple Steam folders found, using most recent: {steam_folders[0].name}")

    save_folder = steam_folders[0]

    # Verify save files exist
    if not (save_folder / 'save.hg').exists():
        logger.warning(f"No save.hg found in {save_folder}")
        return None

    logger.info(f"Found NMS save folder: {save_folder}")
    return save_folder


def get_save_file_path(config: dict) -> Optional[Path]:
    """
    Get the full path to the save file based on config.
    Returns None if not found.
    """
    save_path = config.get('watcher', {}).get('save_path', 'auto')
    save_slot = config.get('watcher', {}).get('save_slot', 1)

    if save_path == 'auto':
        base_path = find_nms_save_path()
        if not base_path:
            return None
    else:
        base_path = Path(save_path)
        if not base_path.exists():
            logger.warning(f"Configured save path does not exist: {base_path}")
            return None

    # Get save filename for slot
    save_filename = SAVE_SLOTS.get(save_slot, 'save.hg')
    save_file = base_path / save_filename

    if not save_file.exists():
        logger.warning(f"Save file not found: {save_file}")
        return None

    return save_file


def load_config() -> dict:
    """Load configuration from file or create default."""
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Merge with defaults to ensure all keys exist
            merged = _deep_merge(DEFAULT_CONFIG.copy(), config)
            return merged
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        # Create default config file
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Save configuration to file."""
    config_path = get_config_path()

    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration saved to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def validate_config(config: dict) -> tuple[bool, list[str]]:
    """
    Validate configuration.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    # Check API key
    api_key = config.get('api', {}).get('key', '')
    if not api_key:
        errors.append("API key is not configured")
    elif not api_key.startswith('vh_live_'):
        errors.append("API key format is invalid (should start with 'vh_live_')")

    # Check API URL
    api_url = config.get('api', {}).get('base_url', '')
    if not api_url:
        errors.append("API base URL is not configured")

    # Check save path
    save_path = config.get('watcher', {}).get('save_path', 'auto')
    if save_path != 'auto':
        if not Path(save_path).exists():
            errors.append(f"Save path does not exist: {save_path}")
    else:
        if not find_nms_save_path():
            errors.append("Could not auto-detect NMS save folder")

    # Check save slot
    save_slot = config.get('watcher', {}).get('save_slot', 1)
    if save_slot not in SAVE_SLOTS:
        errors.append(f"Invalid save slot: {save_slot} (must be 1-10)")

    return (len(errors) == 0, errors)
