"""JSON exporter for memory snapshots.

Exports memory snapshots to JSON files with configurable options.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from ..data.snapshot import Snapshot
from .schema import SNAPSHOT_SCHEMA

logger = logging.getLogger(__name__)


class JSONExporter:
    """Exports memory snapshots to JSON format."""

    def __init__(self, snapshot: Snapshot):
        """Initialize the exporter.

        Args:
            snapshot: Snapshot to export
        """
        self._snapshot = snapshot

    def export(self, filepath: Path, options: Optional[Dict[str, Any]] = None) -> bool:
        """Export the snapshot to a JSON file.

        Args:
            filepath: Path to save the JSON file
            options: Export options (include_hex_dumps, pretty_print, etc.)

        Returns:
            True if export succeeded
        """
        options = options or {}

        try:
            # Build export data
            data = self._build_export_data(options)

            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Write JSON
            indent = 2 if options.get('pretty_print', True) else None

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, default=self._json_serializer)

            logger.info(f"Exported snapshot to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False

    def _build_export_data(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Build the export data structure."""
        data = {
            'version': SNAPSHOT_SCHEMA['version'],
            'metadata': self._export_metadata(),
        }

        # Known structures
        known = {}

        if options.get('include_player', True):
            known['player'] = self._export_section(self._snapshot.player, options)

        if options.get('include_system', True):
            known['solar_system'] = self._export_section(self._snapshot.solar_system, options)

        if options.get('include_multiplayer', True):
            known['multiplayer'] = self._export_multiplayer(options)

        data['known_structures'] = known

        # Unknown regions
        if options.get('include_unknown', True):
            data['unknown_regions'] = self._export_unknown_regions(options)

        # Stats
        data['stats'] = self._snapshot.stats

        return data

    def _export_metadata(self) -> Dict[str, Any]:
        """Export metadata section."""
        meta = self._snapshot.metadata
        return {
            'timestamp': meta.timestamp,
            'game_version': meta.game_version,
            'extractor_version': meta.extractor_version,
            'galaxy_name': meta.galaxy_name,
            'glyph_code': meta.glyph_code,
            'player_name': meta.player_name,
            'system_name': meta.system_name,
            'connected': meta.connected,
        }

    def _export_section(self, section: Dict, options: Dict[str, Any]) -> Dict[str, Any]:
        """Export a section of struct snapshots."""
        result = {}

        for name, struct_snapshot in section.items():
            if hasattr(struct_snapshot, '__dataclass_fields__'):
                # It's a dataclass
                struct_data = {
                    'name': struct_snapshot.name,
                    '__type__': struct_snapshot.struct_type,
                    '__address__': struct_snapshot.address,
                    '__size__': struct_snapshot.size,
                    'category': struct_snapshot.category,
                    'fields': struct_snapshot.fields,
                    'valid': struct_snapshot.valid,
                }

                if struct_snapshot.error:
                    struct_data['error'] = struct_snapshot.error

                # Include hex if requested
                if options.get('include_hex_dumps', True) and struct_snapshot.raw_hex:
                    max_size = options.get('max_hex_dump_size', 4096)
                    hex_str = struct_snapshot.raw_hex
                    if len(hex_str) > max_size * 2:  # Hex string is 2x bytes
                        hex_str = hex_str[:max_size * 2] + '...'
                    struct_data['raw_hex'] = hex_str

                result[name] = struct_data
            else:
                # Plain dict
                result[name] = struct_snapshot

        return result

    def _export_multiplayer(self, options: Dict[str, Any]) -> Dict[str, Any]:
        """Export multiplayer section."""
        mp = self._snapshot.multiplayer
        return {
            'session_info': mp.get('session_info', {}),
            'other_players': mp.get('other_players', []),
            'player_bases': mp.get('player_bases', []),
            'settlements': mp.get('settlements', []),
            'comm_stations': mp.get('comm_stations', []),
        }

    def _export_unknown_regions(self, options: Dict[str, Any]) -> list:
        """Export unknown regions."""
        result = []

        for region in self._snapshot.unknown_regions:
            region_data = {
                'address': region.address,
                'size': region.size,
                'context': region.context,
                'inferred_types': region.inferred_types,
            }

            # Include hex dump if requested
            if options.get('include_hex_dumps', True) and region.hex_dump:
                max_size = options.get('max_hex_dump_size', 4096)
                hex_str = region.hex_dump
                if len(hex_str) > max_size:
                    hex_str = hex_str[:max_size] + '...'
                region_data['hex_dump'] = hex_str

            result.append(region_data)

        return result

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if hasattr(obj, '__dataclass_fields__'):
            # Dataclass
            from dataclasses import asdict
            return asdict(obj)
        elif isinstance(obj, bytes):
            return obj.hex()
        elif isinstance(obj, Path):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return str(obj)

    def to_string(self, options: Optional[Dict[str, Any]] = None) -> str:
        """Export the snapshot to a JSON string.

        Args:
            options: Export options

        Returns:
            JSON string
        """
        options = options or {}
        data = self._build_export_data(options)
        indent = 2 if options.get('pretty_print', True) else None
        return json.dumps(data, indent=indent, default=self._json_serializer)
