"""Player data collector.

Collects comprehensive player-related data from game memory including:
- Player stats (health, shield, currencies)
- Current location and coordinates
- Ship ownership (all 12 ships)
- Base building data
- Freighter information
- Player character state (jetpack, stamina)
- Multitool data
"""

import logging
import ctypes
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


# Galaxy name mapping
GALAXY_NAMES = {
    0: "Euclid", 1: "Hilbert Dimension", 2: "Calypso", 3: "Hesperius Dimension",
    4: "Hyades", 5: "Ickjamatew", 6: "Budullangr", 7: "Kikolgallr",
    8: "Eltiensleen", 9: "Eissentam", 10: "Elkupalos", 11: "Aptarkaba",
    12: "Ontiniangp", 13: "Odiwagiri", 14: "Ogtialabi", 15: "Muhacksonto",
    16: "Hitonskyer", 17: "Rerasmutul", 18: "Isdoraijung", 19: "Doctinawyra",
    20: "Loychazinq", 21: "Zukasizawa", 22: "Ekwathore", 23: "Yeberhahne",
    24: "Twerbetek", 25: "Sivarates", 26: "Eaaborom", 27: "Ssjsjsksksksk",
    28: "Pivsjsksk", 29: "Axsjjsj", 30: "Hajsjskx", 254: "Odyalutai", 255: "Isdoraijung",
}

# Ship class names
SHIP_CLASSES = {
    0: "Shuttle", 1: "Fighter", 2: "Scientific", 3: "Dropship/Hauler",
    4: "Royal/Exotic", 5: "Freighter", 6: "Capital Freighter", 7: "Living Ship",
    8: "Solar Ship", 9: "Robot Ship",
}


class PlayerCollector:
    """Collects comprehensive player-related game data."""

    # Player-related struct types to collect
    PLAYER_STRUCTS = [
        ('player_state', 'cGcPlayerState', 'Player State'),
        ('location', 'cGcUniverseAddressData', 'Location'),
        ('player', 'cGcPlayer', 'Player Character'),
        ('ship_ownership', 'cGcPlayerShipOwnership', 'Ship Ownership'),
    ]

    # Key fields to extract from player state
    PLAYER_STATE_FIELDS = [
        'miShield',
        'miHealth',
        'miShipHealth',
        'muUnits',
        'muNanites',
        'muSpecials',  # Quicksilver
        'mfEnergy',
        'mLocation',
        'miPrimaryShip',
        'miPrimaryWeapon',  # Multitool index
    ]

    # Fields for player character (cGcPlayer)
    PLAYER_CHARACTER_FIELDS = [
        'mfJetpackTank',
        'mfStamina',
        'mfAirTimer',
        'mbSpawned',
        'mbIsRunning',
        'mbIsAutoWalking',
        'mbIsDying',
    ]

    # Ship data structure offsets (from cGcPlayerShipOwnership)
    SHIP_ARRAY_OFFSET = 0x58  # mShips array
    SHIP_DATA_SIZE = 0xE08  # Size of each ship entry (sGcShipData)
    MAX_SHIPS = 12

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
            Dictionary of comprehensive player data
        """
        result = {
            'stats': {},
            'location': {},
            'currencies': {},
            'ships': [],
            'character': {},
            'inventory': {},
            'structs': {},
            'bases': [],
            'freighter': {},
        }

        # Get player state
        player_state = self.scanner.get_game_object('player_state')
        if player_state is None:
            logger.warning("Could not access player state")
            return result

        # Extract stats (health, shield, ship health)
        result['stats'] = self._extract_stats(player_state)

        # Extract currencies separately for clarity
        result['currencies'] = self._extract_currencies(player_state)

        # Extract location
        result['location'] = self._extract_location(player_state)

        # Extract ship ownership data
        result['ships'] = self._extract_ships(player_state)

        # Extract player character state (jetpack, stamina, etc.)
        result['character'] = self._extract_character_state()

        # Get player state struct
        pointer = self.scanner.get_pointer('player_state')
        if pointer and pointer.valid:
            mapped = self.mapper.map_struct(pointer.address, 'cGcPlayerState', max_depth=1)
            result['structs']['player_state'] = self._mapped_struct_to_snapshot(
                'player_state', mapped
            )

        return result

    def _extract_currencies(self, player_state: Any) -> Dict[str, Any]:
        """Extract player currencies."""
        currencies = {}

        try:
            if hasattr(player_state, 'muUnits'):
                currencies['units'] = self._safe_int(player_state.muUnits)
            if hasattr(player_state, 'muNanites'):
                currencies['nanites'] = self._safe_int(player_state.muNanites)
            if hasattr(player_state, 'muSpecials'):
                currencies['quicksilver'] = self._safe_int(player_state.muSpecials)
        except Exception as e:
            logger.debug(f"Error extracting currencies: {e}")

        return currencies

    def _safe_int(self, value: Any) -> int:
        """Safely convert a value to int."""
        try:
            if hasattr(value, 'value'):
                return int(value.value)
            return int(value)
        except:
            return 0

    def _safe_float(self, value: Any) -> float:
        """Safely convert a value to float."""
        try:
            if hasattr(value, 'value'):
                return float(value.value)
            return float(value)
        except:
            return 0.0

    def _safe_bool(self, value: Any) -> bool:
        """Safely convert a value to bool."""
        try:
            if hasattr(value, 'value'):
                return bool(value.value)
            return bool(value)
        except:
            return False

    def _safe_str(self, value: Any) -> str:
        """Safely convert a value to string."""
        try:
            if value is None:
                return ""
            if hasattr(value, 'value'):
                return str(value.value)
            return str(value)
        except:
            return ""

    def _extract_stats(self, player_state: Any) -> Dict[str, Any]:
        """Extract player stats (health, shield, ship health)."""
        stats = {}

        try:
            if hasattr(player_state, 'miShield'):
                stats['shield'] = self._safe_int(player_state.miShield)
            if hasattr(player_state, 'miHealth'):
                stats['health'] = self._safe_int(player_state.miHealth)
            if hasattr(player_state, 'miShipHealth'):
                stats['ship_health'] = self._safe_int(player_state.miShipHealth)
            if hasattr(player_state, 'mfEnergy'):
                stats['energy'] = self._safe_float(player_state.mfEnergy)

            # Primary ship/weapon indices
            if hasattr(player_state, 'miPrimaryShip'):
                stats['primary_ship_index'] = self._safe_int(player_state.miPrimaryShip)
            if hasattr(player_state, 'miPrimaryWeapon'):
                stats['primary_multitool_index'] = self._safe_int(player_state.miPrimaryWeapon)
        except Exception as e:
            logger.debug(f"Error extracting player stats: {e}")

        return stats

    def _extract_ships(self, player_state: Any) -> List[Dict[str, Any]]:
        """Extract ship ownership data for all 12 ship slots."""
        ships = []

        try:
            # Try to access ship ownership from game state
            game_state = self.scanner.get_game_object('game_state')
            if game_state and hasattr(game_state, 'mPlayerShipOwnership'):
                ship_ownership = game_state.mPlayerShipOwnership

                if hasattr(ship_ownership, 'mShips'):
                    ship_array = ship_ownership.mShips

                    # Iterate through ship slots
                    for i in range(min(self.MAX_SHIPS, len(ship_array) if hasattr(ship_array, '__len__') else self.MAX_SHIPS)):
                        try:
                            ship_data = self._extract_single_ship(ship_array, i)
                            if ship_data:
                                ships.append(ship_data)
                        except Exception as e:
                            logger.debug(f"Error extracting ship {i}: {e}")
                            ships.append({'slot': i, 'error': str(e)})
        except Exception as e:
            logger.debug(f"Error extracting ships: {e}")

        # If we couldn't get ship data from game state, try player state
        if not ships and player_state:
            try:
                primary_idx = self._safe_int(getattr(player_state, 'miPrimaryShip', 0))
                ships.append({
                    'slot': primary_idx,
                    'name': 'Primary Ship',
                    'is_primary': True,
                    'note': 'Ship details require deeper struct access'
                })
            except:
                pass

        return ships

    def _extract_single_ship(self, ship_array: Any, index: int) -> Optional[Dict[str, Any]]:
        """Extract data for a single ship slot."""
        ship_data = {
            'slot': index,
            'is_primary': False,
        }

        try:
            # Access ship at index
            if hasattr(ship_array, '__getitem__'):
                ship = ship_array[index]
            else:
                return ship_data

            # Extract seed (unique identifier)
            if hasattr(ship, 'mPlayerShipSeed'):
                seed = ship.mPlayerShipSeed
                if hasattr(seed, 'Seed'):
                    ship_data['seed'] = self._safe_int(seed.Seed)
                elif hasattr(seed, 'value'):
                    ship_data['seed'] = self._safe_int(seed.value)

            # Extract ship name if available
            if hasattr(ship, 'mCustomName'):
                ship_data['custom_name'] = self._safe_str(ship.mCustomName)

            # Extract ship class/type
            if hasattr(ship, 'meShipClass'):
                class_val = self._safe_int(ship.meShipClass)
                ship_data['class_id'] = class_val
                ship_data['class_name'] = SHIP_CLASSES.get(class_val, f"Unknown ({class_val})")

            # Extract inventory size info
            if hasattr(ship, 'miInventoryWidth'):
                ship_data['inventory_width'] = self._safe_int(ship.miInventoryWidth)
            if hasattr(ship, 'miInventoryHeight'):
                ship_data['inventory_height'] = self._safe_int(ship.miInventoryHeight)

            # Check if this slot is empty
            seed_val = ship_data.get('seed', 0)
            if seed_val == 0:
                ship_data['empty'] = True

        except Exception as e:
            ship_data['error'] = str(e)

        return ship_data

    def _extract_character_state(self) -> Dict[str, Any]:
        """Extract player character state (jetpack, stamina, etc.)."""
        character = {}

        try:
            # Try to get player character from simulation
            simulation = self.scanner.get_game_object('simulation')
            if simulation and hasattr(simulation, 'mPlayer'):
                player = simulation.mPlayer

                # Jetpack fuel
                if hasattr(player, 'mfJetpackTank'):
                    character['jetpack_fuel'] = self._safe_float(player.mfJetpackTank)

                # Stamina
                if hasattr(player, 'mfStamina'):
                    character['stamina'] = self._safe_float(player.mfStamina)

                # Air timer (for falling/underwater)
                if hasattr(player, 'mfAirTimer'):
                    character['air_timer'] = self._safe_float(player.mfAirTimer)

                # State flags
                if hasattr(player, 'mbSpawned'):
                    character['spawned'] = self._safe_bool(player.mbSpawned)
                if hasattr(player, 'mbIsRunning'):
                    character['is_running'] = self._safe_bool(player.mbIsRunning)
                if hasattr(player, 'mbIsAutoWalking'):
                    character['is_auto_walking'] = self._safe_bool(player.mbIsAutoWalking)
                if hasattr(player, 'mbIsDying'):
                    character['is_dying'] = self._safe_bool(player.mbIsDying)

            # Also try player environment for location type
            if simulation and hasattr(simulation, 'mEnvironment'):
                env = simulation.mEnvironment
                if hasattr(env, 'mPlayerEnvironment'):
                    player_env = env.mPlayerEnvironment

                    if hasattr(player_env, 'meLocation'):
                        character['location_type'] = self._safe_int(player_env.meLocation)
                    if hasattr(player_env, 'mfDistanceFromPlanet'):
                        character['distance_from_planet'] = self._safe_float(player_env.mfDistanceFromPlanet)
                    if hasattr(player_env, 'mbInsidePlanetAtmosphere'):
                        character['in_atmosphere'] = self._safe_bool(player_env.mbInsidePlanetAtmosphere)

        except Exception as e:
            logger.debug(f"Error extracting character state: {e}")

        return character

    def _extract_location(self, player_state: Any) -> Dict[str, Any]:
        """Extract player location with full details."""
        location = {}

        try:
            if hasattr(player_state, 'mLocation'):
                loc = player_state.mLocation
                if hasattr(loc, 'GalacticAddress'):
                    ga = loc.GalacticAddress
                    location['voxel_x'] = self._safe_int(getattr(ga, 'VoxelX', 0))
                    location['voxel_y'] = self._safe_int(getattr(ga, 'VoxelY', 0))
                    location['voxel_z'] = self._safe_int(getattr(ga, 'VoxelZ', 0))
                    location['system_index'] = self._safe_int(getattr(ga, 'SolarSystemIndex', 0))
                    location['planet_index'] = self._safe_int(getattr(ga, 'PlanetIndex', 0))

                if hasattr(loc, 'RealityIndex'):
                    galaxy_idx = self._safe_int(loc.RealityIndex)
                    location['galaxy_index'] = galaxy_idx
                    location['galaxy_name'] = GALAXY_NAMES.get(galaxy_idx, f"Galaxy {galaxy_idx}")

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
        """Build comprehensive tree nodes for player data.

        Returns:
            Player category node with children
        """
        category = create_category_node('Player', 'Player Data (Comprehensive)')

        # Collect data
        data = self.collect()

        # Add Stats node (Health, Shield, Energy)
        stats_node = TreeNode(
            name='Stats',
            node_type=NodeType.STRUCT,
            display_text='Health & Stats',
            icon='chart',
        )
        for stat_name, stat_value in data['stats'].items():
            stats_node.add_child(create_field_node(
                name=stat_name,
                value=stat_value,
                formatted_value=self._format_stat_value(stat_name, stat_value),
                offset=0,
                size=4,
            ))
        category.add_child(stats_node)

        # Add Currencies node
        currencies_node = TreeNode(
            name='Currencies',
            node_type=NodeType.STRUCT,
            display_text='Currencies',
            icon='money',
        )
        for curr_name, curr_value in data['currencies'].items():
            currencies_node.add_child(create_field_node(
                name=curr_name,
                value=curr_value,
                formatted_value=f"{curr_value:,}" if isinstance(curr_value, int) else str(curr_value),
                offset=0,
                size=4,
            ))
        category.add_child(currencies_node)

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

        # Add Character State node (Jetpack, Stamina, etc.)
        if data['character']:
            character_node = TreeNode(
                name='Character',
                node_type=NodeType.STRUCT,
                display_text='Character State',
                icon='player',
            )
            for char_name, char_value in data['character'].items():
                formatted = self._format_character_value(char_name, char_value)
                character_node.add_child(create_field_node(
                    name=char_name,
                    value=char_value,
                    formatted_value=formatted,
                    offset=0,
                    size=4,
                ))
            category.add_child(character_node)

        # Add Ships node (Fleet of 12 ships)
        ships_node = TreeNode(
            name='Ships',
            node_type=NodeType.ARRAY,
            display_text=f'Ships ({len(data["ships"])} slots)',
            icon='ship',
        )
        for ship_data in data['ships']:
            ship_node = self._build_ship_node(ship_data, data['stats'].get('primary_ship_index', 0))
            ships_node.add_child(ship_node)
        category.add_child(ships_node)

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

    def _format_stat_value(self, name: str, value: Any) -> str:
        """Format a stat value for display."""
        if 'health' in name.lower() or 'shield' in name.lower():
            return f"{value} HP" if isinstance(value, int) else str(value)
        elif 'energy' in name.lower():
            return f"{value:.1f}%" if isinstance(value, float) else str(value)
        elif 'index' in name.lower():
            return f"Slot {value}" if isinstance(value, int) else str(value)
        return str(value)

    def _format_character_value(self, name: str, value: Any) -> str:
        """Format a character state value for display."""
        if 'fuel' in name.lower() or 'stamina' in name.lower():
            return f"{value:.1f}%" if isinstance(value, float) else str(value)
        elif 'distance' in name.lower():
            return f"{value:.0f}u" if isinstance(value, float) else str(value)
        elif isinstance(value, bool):
            return "Yes" if value else "No"
        return str(value)

    def _build_ship_node(self, ship_data: Dict, primary_idx: int) -> TreeNode:
        """Build a tree node for a single ship."""
        slot = ship_data.get('slot', 0)
        is_primary = slot == primary_idx
        is_empty = ship_data.get('empty', False)

        if is_empty:
            name = f"Ship Slot {slot} (Empty)"
            display = f"Slot {slot}: Empty"
        else:
            ship_class = ship_data.get('class_name', 'Unknown')
            custom_name = ship_data.get('custom_name', '')
            if custom_name:
                name = f"Ship {slot}: {custom_name}"
                display = f"Slot {slot}: {custom_name} ({ship_class})"
            else:
                name = f"Ship Slot {slot}"
                display = f"Slot {slot}: {ship_class}"

        if is_primary:
            display += " [PRIMARY]"

        ship_node = TreeNode(
            name=name,
            node_type=NodeType.STRUCT,
            display_text=display,
            icon='ship',
        )

        # Add ship fields
        for field_name, field_value in ship_data.items():
            if field_name not in ('slot', 'empty'):
                ship_node.add_child(create_field_node(
                    name=field_name,
                    value=field_value,
                    formatted_value=str(field_value),
                    offset=0,
                    size=4,
                ))

        return ship_node

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
