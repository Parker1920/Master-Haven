"""Memory snapshot data model.

Represents a point-in-time capture of game memory state.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class SnapshotMetadata:
    """Metadata for a memory snapshot."""
    timestamp: str = ""
    game_version: str = "Unknown"
    extractor_version: str = "1.0.0"
    galaxy_name: str = "Unknown"
    glyph_code: str = ""
    player_name: str = "Unknown"
    system_name: str = "Unknown"
    connected: bool = False

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class StructSnapshot:
    """Snapshot of a single struct."""
    name: str
    struct_type: str
    address: str  # Hex string
    size: int
    category: str = ""
    fields: Dict[str, Any] = field(default_factory=dict)
    raw_hex: str = ""
    valid: bool = True
    error: str = ""


@dataclass
class UnknownRegion:
    """Snapshot of an unknown memory region."""
    address: str  # Hex string
    size: int
    context: str = ""
    inferred_types: List[Dict[str, Any]] = field(default_factory=list)
    hex_dump: str = ""


@dataclass
class Snapshot:
    """Complete memory snapshot."""
    metadata: SnapshotMetadata = field(default_factory=SnapshotMetadata)

    # Known structures organized by category
    player: Dict[str, StructSnapshot] = field(default_factory=dict)
    solar_system: Dict[str, StructSnapshot] = field(default_factory=dict)
    multiplayer: Dict[str, Any] = field(default_factory=dict)
    simulation: Dict[str, StructSnapshot] = field(default_factory=dict)

    # Unknown/unmapped regions
    unknown_regions: List[UnknownRegion] = field(default_factory=list)

    # Statistics
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for JSON export."""
        return {
            'version': '1.0.0',
            'metadata': asdict(self.metadata),
            'known_structures': {
                'player': {k: asdict(v) for k, v in self.player.items()},
                'solar_system': {k: asdict(v) for k, v in self.solar_system.items()},
                'multiplayer': self._serialize_multiplayer(),
                'simulation': {k: asdict(v) for k, v in self.simulation.items()},
            },
            'unknown_regions': [asdict(r) for r in self.unknown_regions],
            'stats': self.stats,
        }

    def _serialize_multiplayer(self) -> Dict[str, Any]:
        """Serialize multiplayer data."""
        result = {}
        for key, value in self.multiplayer.items():
            if isinstance(value, list):
                result[key] = [
                    asdict(item) if hasattr(item, '__dataclass_fields__') else item
                    for item in value
                ]
            elif hasattr(value, '__dataclass_fields__'):
                result[key] = asdict(value)
            else:
                result[key] = value
        return result

    def save(self, filepath: Path) -> bool:
        """Save snapshot to JSON file.

        Args:
            filepath: Path to save to

        Returns:
            True if saved successfully
        """
        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, default=str)

            logger.info(f"Saved snapshot to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
            return False

    @classmethod
    def load(cls, filepath: Path) -> Optional['Snapshot']:
        """Load snapshot from JSON file.

        Args:
            filepath: Path to load from

        Returns:
            Snapshot instance or None
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            snapshot = cls()

            # Load metadata
            if 'metadata' in data:
                snapshot.metadata = SnapshotMetadata(**data['metadata'])

            # Load known structures
            if 'known_structures' in data:
                ks = data['known_structures']

                if 'player' in ks:
                    for name, struct_data in ks['player'].items():
                        snapshot.player[name] = StructSnapshot(**struct_data)

                if 'solar_system' in ks:
                    for name, struct_data in ks['solar_system'].items():
                        snapshot.solar_system[name] = StructSnapshot(**struct_data)

                if 'multiplayer' in ks:
                    snapshot.multiplayer = ks['multiplayer']

                if 'simulation' in ks:
                    for name, struct_data in ks['simulation'].items():
                        snapshot.simulation[name] = StructSnapshot(**struct_data)

            # Load unknown regions
            if 'unknown_regions' in data:
                snapshot.unknown_regions = [
                    UnknownRegion(**r) for r in data['unknown_regions']
                ]

            # Load stats
            if 'stats' in data:
                snapshot.stats = data['stats']

            logger.info(f"Loaded snapshot from {filepath}")
            return snapshot

        except Exception as e:
            logger.error(f"Failed to load snapshot: {e}")
            return None

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the snapshot contents."""
        return {
            'timestamp': self.metadata.timestamp,
            'galaxy': self.metadata.galaxy_name,
            'system': self.metadata.system_name,
            'player_structs': len(self.player),
            'system_structs': len(self.solar_system),
            'multiplayer_items': sum(
                len(v) if isinstance(v, list) else 1
                for v in self.multiplayer.values()
            ),
            'unknown_regions': len(self.unknown_regions),
            'connected': self.metadata.connected,
        }
