"""Solar system data collector.

Collects solar system and planet data from game memory.
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


# Enum mappings from haven_extractor.py
BIOME_TYPES = {
    0: "Lush", 1: "Toxic", 2: "Scorched", 3: "Radioactive", 4: "Frozen",
    5: "Barren", 6: "Dead", 7: "Weird", 8: "Red", 9: "Green", 10: "Blue",
    11: "Test", 12: "Swamp", 13: "Lava", 14: "Waterworld", 15: "GasGiant", 16: "All"
}

STAR_TYPES = {0: "Yellow", 1: "Red", 2: "Green", 3: "Blue"}

TRADING_CLASSES = {
    0: "Mining", 1: "HighTech", 2: "Trading", 3: "Manufacturing",
    4: "Fusion", 5: "Scientific", 6: "PowerGeneration"
}

WEALTH_CLASSES = {0: "Poor", 1: "Average", 2: "Wealthy", 3: "Pirate"}

PLANET_SIZES = {0: "Large", 1: "Medium", 2: "Small", 3: "Moon", 4: "Giant"}

ALIEN_RACES = {
    0: "Traders", 1: "Warriors", 2: "Explorers", 3: "Robots",
    4: "Atlas", 5: "Diplomats", 6: "None"
}


class SystemCollector:
    """Collects solar system data."""

    # Memory offsets from haven_extractor.py
    class Offsets:
        PLANETS_COUNT = 0x2264
        PRIME_PLANETS = 0x2268
        STAR_CLASS = 0x224C
        STAR_TYPE = 0x2270
        TRADING_DATA = 0x2240
        CONFLICT_DATA = 0x2250
        INHABITING_RACE = 0x2254
        SEED = 0x21A0
        PLANET_GEN_INPUTS = 0x1EA0

    def __init__(
        self,
        reader: MemoryReader,
        mapper: StructMapper,
        scanner: PointerScanner
    ):
        """Initialize the system collector.

        Args:
            reader: Memory reader instance
            mapper: Struct mapper instance
            scanner: Pointer scanner instance
        """
        self.reader = reader
        self.mapper = mapper
        self.scanner = scanner

    def collect(self) -> Dict[str, Any]:
        """Collect solar system data.

        Returns:
            Dictionary of system data
        """
        result = {
            'system_info': {},
            'planets': [],
            'structs': {},
        }

        # Get solar system pointer
        pointer = self.scanner.get_pointer('solar_system')
        if not pointer or not pointer.valid:
            logger.warning("Could not access solar system")
            return result

        sys_addr = pointer.address

        # Extract system info using direct memory reads
        result['system_info'] = self._extract_system_info(sys_addr)

        # Extract planet count
        planet_count = self.reader.read_int32(sys_addr + self.Offsets.PLANETS_COUNT)
        if planet_count and 0 < planet_count <= 6:
            result['system_info']['planet_count'] = planet_count

            # Extract planets
            for i in range(planet_count):
                planet_data = self._extract_planet_data(sys_addr, i)
                if planet_data:
                    result['planets'].append(planet_data)

        # Map the struct
        mapped = self.mapper.map_struct(sys_addr, 'cGcSolarSystem', max_depth=1)
        result['structs']['solar_system'] = self._mapped_struct_to_snapshot(
            'solar_system', mapped
        )

        return result

    def _extract_system_info(self, sys_addr: int) -> Dict[str, Any]:
        """Extract system-level information."""
        info = {}

        try:
            # Star type
            star_type = self.reader.read_uint32(sys_addr + self.Offsets.STAR_TYPE)
            if star_type is not None:
                info['star_type_raw'] = star_type
                info['star_type'] = STAR_TYPES.get(star_type, f"Unknown({star_type})")

            # Economy (trading data)
            trading_addr = sys_addr + self.Offsets.TRADING_DATA
            trading_class = self.reader.read_uint32(trading_addr)
            wealth_class = self.reader.read_uint32(trading_addr + 4)
            if trading_class is not None:
                info['economy_type_raw'] = trading_class
                info['economy_type'] = TRADING_CLASSES.get(trading_class, f"Unknown({trading_class})")
            if wealth_class is not None:
                info['economy_strength_raw'] = wealth_class
                info['economy_strength'] = WEALTH_CLASSES.get(wealth_class, f"Unknown({wealth_class})")

            # Conflict
            conflict_level = self.reader.read_uint32(sys_addr + self.Offsets.CONFLICT_DATA)
            if conflict_level is not None:
                info['conflict_level'] = conflict_level

            # Dominant race
            race = self.reader.read_uint32(sys_addr + self.Offsets.INHABITING_RACE)
            if race is not None:
                info['dominant_race_raw'] = race
                info['dominant_race'] = ALIEN_RACES.get(race, f"Unknown({race})")

            # Planet count
            planet_count = self.reader.read_int32(sys_addr + self.Offsets.PLANETS_COUNT)
            prime_planets = self.reader.read_int32(sys_addr + self.Offsets.PRIME_PLANETS)
            if planet_count is not None:
                info['total_planets'] = planet_count
            if prime_planets is not None:
                info['main_planets'] = prime_planets
                if planet_count:
                    info['moons'] = planet_count - prime_planets

        except Exception as e:
            logger.debug(f"Error extracting system info: {e}")

        return info

    def _extract_planet_data(self, sys_addr: int, planet_index: int) -> Optional[Dict[str, Any]]:
        """Extract data for a single planet."""
        try:
            # Planet gen input data
            # Each entry is 0x53 bytes (83 bytes)
            PLANET_GEN_SIZE = 0x53
            planet_addr = sys_addr + self.Offsets.PLANET_GEN_INPUTS + (planet_index * PLANET_GEN_SIZE)

            data = {
                'index': planet_index,
            }

            # Common substance (offset 0x00, 16-byte string)
            common = self.reader.read_string(planet_addr, max_len=16)
            if common:
                data['common_resource'] = common

            # Rare substance (offset 0x10, 16-byte string)
            rare = self.reader.read_string(planet_addr + 0x10, max_len=16)
            if rare:
                data['rare_resource'] = rare

            # Biome (offset 0x30)
            biome = self.reader.read_uint32(planet_addr + 0x30)
            if biome is not None:
                data['biome_raw'] = biome
                data['biome'] = BIOME_TYPES.get(biome, f"Unknown({biome})")

            # Biome subtype (offset 0x34)
            subtype = self.reader.read_uint32(planet_addr + 0x34)
            if subtype is not None:
                data['biome_subtype'] = subtype

            # Planet size (offset 0x40)
            size = self.reader.read_uint32(planet_addr + 0x40)
            if size is not None:
                data['size_raw'] = size
                data['size'] = PLANET_SIZES.get(size, f"Unknown({size})")
                data['is_moon'] = size == 3

            return data

        except Exception as e:
            logger.debug(f"Error extracting planet {planet_index}: {e}")
            return None

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
            category='Solar System',
            fields=fields,
            raw_hex=mapped.raw_bytes.hex() if mapped.raw_bytes else '',
            valid=mapped.valid,
            error=mapped.error,
        )

    # =========================================================================
    # Tree Node Generation
    # =========================================================================

    def build_tree_nodes(self) -> TreeNode:
        """Build tree nodes for solar system data.

        Returns:
            Solar System category node with children
        """
        category = create_category_node('Solar System', 'Current System')

        # Collect data
        data = self.collect()

        # Add System Info node
        info_node = TreeNode(
            name='System Info',
            node_type=NodeType.STRUCT,
            display_text='System Properties',
            icon='info',
        )

        for key, value in data['system_info'].items():
            info_node.add_child(create_field_node(
                name=key,
                value=value,
                formatted_value=str(value),
                offset=0,
                size=4,
            ))

        category.add_child(info_node)

        # Add Planets array
        if data['planets']:
            planets_node = create_array_node(
                name='Planets',
                element_type='PlanetData',
                address=0,
                count=len(data['planets']),
            )

            for planet in data['planets']:
                planet_node = TreeNode(
                    name=f"Planet {planet['index']}",
                    node_type=NodeType.ARRAY_ELEMENT,
                    display_text=f"Planet {planet['index']} - {planet.get('biome', 'Unknown')}",
                    icon='planet',
                )

                for key, value in planet.items():
                    planet_node.add_child(create_field_node(
                        name=key,
                        value=value,
                        formatted_value=str(value),
                        offset=0,
                        size=4,
                    ))

                planets_node.add_child(planet_node)

            category.add_child(planets_node)

        # Add raw struct node with lazy loading
        pointer = self.scanner.get_pointer('solar_system')
        if pointer and pointer.valid:
            struct_node = create_struct_node(
                name='SolarSystem (Raw)',
                struct_type='cGcSolarSystem',
                address=pointer.address,
                size=data['structs'].get('solar_system', StructSnapshot('', '', '', 0)).size,
            )
            struct_node._loader = lambda n: self._load_struct_fields(n)
            category.add_child(struct_node)

        return category

    def _load_struct_fields(self, node: TreeNode) -> List[TreeNode]:
        """Lazy loader for struct fields."""
        children = []

        pointer = self.scanner.get_pointer('solar_system')
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
