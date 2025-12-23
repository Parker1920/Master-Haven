"""Player data collector.

Collects player-related data from game memory including
location, stats, inventory, and ship information.
"""

import logging
from typing import Optional, Dict, Any, List

from ..core.memory_reader import MemoryReader
from ..core.struct_mapper import StructMapper, MappedStruct
from ..core.pointer_scanner import PointerScanner
from ..data.tree_node import (
    TreeNode, NodeType, create_struct_node, create_field_node,
    create_category_node, create_array_node
)
from ..data.snapshot import StructSnapshot

logger = logging.getLogger(__name__)


class PlayerCollector:
    """Collects player-related game data."""

    # Player-related struct types to collect
    PLAYER_STRUCTS = [
        ('player_state', 'cGcPlayerState', 'Player State'),
        ('location', 'cGcUniverseAddressData', 'Location'),
    ]

    # Key fields to extract from player state
    PLAYER_STATE_FIELDS = [
        'miShield',
        'miHealth',
        'muUnits',
        'muNanites',
        'mfEnergy',
        'mLocation',
    ]

    def __init__(
        self,
        reader: MemoryReader,
        mapper: StructMapper,
        scanner: PointerScanner
    ):
        """Initialize the player collector.

        Args:
            reader: Memory reader instance
            mapper: Struct mapper instance
            scanner: Pointer scanner instance
        """
        self.reader = reader
        self.mapper = mapper
        self.scanner = scanner

    def collect(self) -> Dict[str, Any]:
        """Collect all player data.

        Returns:
            Dictionary of player data
        """
        result = {
            'stats': {},
            'location': {},
            'inventory': {},
            'structs': {},
        }

        # Get player state
        player_state = self.scanner.get_game_object('player_state')
        if player_state is None:
            logger.warning("Could not access player state")
            return result

        # Extract stats
        result['stats'] = self._extract_stats(player_state)

        # Extract location
        result['location'] = self._extract_location(player_state)

        # Get player state struct
        pointer = self.scanner.get_pointer('player_state')
        if pointer and pointer.valid:
            mapped = self.mapper.map_struct(pointer.address, 'cGcPlayerState', max_depth=1)
            result['structs']['player_state'] = self._mapped_struct_to_snapshot(
                'player_state', mapped
            )

        return result

    def _extract_stats(self, player_state: Any) -> Dict[str, Any]:
        """Extract player stats."""
        stats = {}

        try:
            if hasattr(player_state, 'miShield'):
                stats['shield'] = player_state.miShield
            if hasattr(player_state, 'miHealth'):
                stats['health'] = player_state.miHealth
            if hasattr(player_state, 'muUnits'):
                stats['units'] = player_state.muUnits
            if hasattr(player_state, 'muNanites'):
                stats['nanites'] = player_state.muNanites
            if hasattr(player_state, 'mfEnergy'):
                stats['energy'] = player_state.mfEnergy
        except Exception as e:
            logger.debug(f"Error extracting player stats: {e}")

        return stats

    def _extract_location(self, player_state: Any) -> Dict[str, Any]:
        """Extract player location."""
        location = {}

        try:
            if hasattr(player_state, 'mLocation'):
                loc = player_state.mLocation
                if hasattr(loc, 'GalacticAddress'):
                    ga = loc.GalacticAddress
                    location['voxel_x'] = getattr(ga, 'VoxelX', 0)
                    location['voxel_y'] = getattr(ga, 'VoxelY', 0)
                    location['voxel_z'] = getattr(ga, 'VoxelZ', 0)
                    location['system_index'] = getattr(ga, 'SolarSystemIndex', 0)
                    location['planet_index'] = getattr(ga, 'PlanetIndex', 0)
                if hasattr(loc, 'RealityIndex'):
                    location['galaxy_index'] = loc.RealityIndex

                # Calculate glyph code
                if all(k in location for k in ['voxel_x', 'voxel_y', 'voxel_z', 'system_index', 'planet_index']):
                    location['glyph_code'] = self._coords_to_glyphs(
                        location['planet_index'],
                        location['system_index'],
                        location['voxel_x'],
                        location['voxel_y'],
                        location['voxel_z']
                    )
        except Exception as e:
            logger.debug(f"Error extracting location: {e}")

        return location

    def _coords_to_glyphs(self, planet: int, system: int, x: int, y: int, z: int) -> str:
        """Convert coordinates to portal glyph code."""
        portal_x = (x + 2047) & 0xFFF
        portal_y = (y + 127) & 0xFF
        portal_z = (z + 2047) & 0xFFF
        portal_sys = system & 0x1FF
        portal_planet = planet & 0xF
        return f"{portal_planet:01X}{portal_sys:03X}{portal_y:02X}{portal_z:03X}{portal_x:03X}"

    def _mapped_struct_to_snapshot(self, name: str, mapped: MappedStruct) -> StructSnapshot:
        """Convert a MappedStruct to a StructSnapshot."""
        fields = {}
        for f in mapped.fields:
            fields[f.name] = {
                'offset': f"0x{f.offset:X}",
                'size': f.size,
                'type': f.type_name,
                'value': f.formatted_value,
                'raw': f.raw_bytes.hex() if f.raw_bytes else '',
            }

        return StructSnapshot(
            name=name,
            struct_type=mapped.struct_type,
            address=f"0x{mapped.address:X}",
            size=mapped.size,
            category='Player',
            fields=fields,
            raw_hex=mapped.raw_bytes.hex() if mapped.raw_bytes else '',
            valid=mapped.valid,
            error=mapped.error,
        )

    # =========================================================================
    # Tree Node Generation
    # =========================================================================

    def build_tree_nodes(self) -> TreeNode:
        """Build tree nodes for player data.

        Returns:
            Player category node with children
        """
        category = create_category_node('Player', 'Player Data')

        # Collect data
        data = self.collect()

        # Add Stats node
        stats_node = TreeNode(
            name='Stats',
            node_type=NodeType.STRUCT,
            display_text='Player Stats',
            icon='chart',
        )

        for stat_name, stat_value in data['stats'].items():
            stats_node.add_child(create_field_node(
                name=stat_name,
                value=stat_value,
                formatted_value=str(stat_value),
                offset=0,
                size=4,
            ))

        category.add_child(stats_node)

        # Add Location node
        location_node = TreeNode(
            name='Location',
            node_type=NodeType.STRUCT,
            display_text='Current Location',
            icon='location',
        )

        for loc_name, loc_value in data['location'].items():
            location_node.add_child(create_field_node(
                name=loc_name,
                value=loc_value,
                formatted_value=str(loc_value),
                offset=0,
                size=4,
            ))

        category.add_child(location_node)

        # Add raw struct nodes
        if 'player_state' in data['structs']:
            ps = data['structs']['player_state']
            pointer = self.scanner.get_pointer('player_state')
            addr = pointer.address if pointer and pointer.valid else 0

            struct_node = create_struct_node(
                name='PlayerState (Raw)',
                struct_type='cGcPlayerState',
                address=addr,
                size=ps.size,
            )
            struct_node._loader = lambda n: self._load_struct_fields(n, 'player_state')
            category.add_child(struct_node)

        return category

    def _load_struct_fields(self, node: TreeNode, struct_name: str) -> List[TreeNode]:
        """Lazy loader for struct fields."""
        children = []

        pointer = self.scanner.get_pointer(struct_name)
        if not pointer or not pointer.valid:
            return children

        mapped = self.mapper.map_struct(pointer.address, pointer.struct_type, max_depth=1)

        for field in mapped.fields:
            child = create_field_node(
                name=field.name,
                value=field.raw_value,
                formatted_value=field.formatted_value,
                offset=field.offset,
                size=field.size,
                type_name=field.type_name,
            )
            children.append(child)

        return children
