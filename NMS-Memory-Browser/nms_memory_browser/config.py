"""Configuration management for NMS Memory Browser."""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BrowserConfig:
    """Configuration settings for the memory browser."""

    # Export settings
    export_dir: Path = field(default_factory=lambda: Path.home() / "Documents" / "NMS-Memory-Browser")
    include_hex_dumps: bool = True
    include_unknown_regions: bool = True
    max_hex_dump_size: int = 4096  # Max bytes to include in hex dumps

    # UI settings
    tree_panel_width: int = 350
    detail_panel_width: int = 650
    window_width: int = 1200
    window_height: int = 800

    # Memory scanning settings
    max_array_elements: int = 100  # Max elements to read from arrays
    pointer_valid_range: tuple = (0x7FF000000000, 0x7FFFFFFFFFFF)  # Windows x64 user space

    # Type inference settings
    string_min_length: int = 3
    string_max_length: int = 256
    float_reasonable_range: tuple = (-1e6, 1e6)

    def __post_init__(self):
        """Ensure export directory exists."""
        self.export_dir.mkdir(parents=True, exist_ok=True)


def load_config(config_path: Optional[Path] = None) -> BrowserConfig:
    """Load configuration from file or use defaults."""
    config = BrowserConfig()

    # Try loading from various locations
    config_locations = [
        config_path,
        Path(__file__).parent.parent / "browser_config.json",
        Path.home() / "Documents" / "NMS-Memory-Browser" / "config.json",
    ]

    for path in config_locations:
        if path and path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Update config with loaded values
                if 'export_dir' in data:
                    config.export_dir = Path(data['export_dir'])
                if 'include_hex_dumps' in data:
                    config.include_hex_dumps = data['include_hex_dumps']
                if 'include_unknown_regions' in data:
                    config.include_unknown_regions = data['include_unknown_regions']
                if 'max_hex_dump_size' in data:
                    config.max_hex_dump_size = data['max_hex_dump_size']
                if 'max_array_elements' in data:
                    config.max_array_elements = data['max_array_elements']

                logger.info(f"Loaded config from: {path}")
                break
            except Exception as e:
                logger.warning(f"Could not load config from {path}: {e}")

    return config


def save_config(config: BrowserConfig, config_path: Optional[Path] = None) -> bool:
    """Save configuration to file."""
    if config_path is None:
        config_path = Path.home() / "Documents" / "NMS-Memory-Browser" / "config.json"

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            'export_dir': str(config.export_dir),
            'include_hex_dumps': config.include_hex_dumps,
            'include_unknown_regions': config.include_unknown_regions,
            'max_hex_dump_size': config.max_hex_dump_size,
            'max_array_elements': config.max_array_elements,
            'tree_panel_width': config.tree_panel_width,
            'window_width': config.window_width,
            'window_height': config.window_height,
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved config to: {config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False
