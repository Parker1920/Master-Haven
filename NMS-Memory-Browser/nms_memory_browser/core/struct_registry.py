"""Registry of all known NMS.py struct definitions.

Dynamically enumerates ctypes.Structure subclasses from NMS.py modules
to provide a complete map of known game structures.
"""

import ctypes
import inspect
import logging
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)


@dataclass
class FieldInfo:
    """Information about a struct field."""
    name: str
    offset: int
    size: int
    type_name: str
    is_pointer: bool = False
    is_array: bool = False
    array_length: int = 0
    is_struct: bool = False
    is_enum: bool = False


@dataclass
class StructInfo:
    """Information about a struct type."""
    name: str
    size: int
    fields: List[FieldInfo] = field(default_factory=list)
    source_module: str = ""
    category: str = "Unknown"  # Player, System, Multiplayer, etc.


class StructRegistry:
    """Registry of all known NMS.py struct types.

    Dynamically loads and catalogs struct definitions from NMS.py,
    organizing them by category for the tree browser.
    """

    # Categories for organizing structs in the tree
    CATEGORIES = {
        'Player': [
            'cGcPlayerState', 'cGcInventoryStore', 'cGcInventoryElement',
            'cGcPlayerShipOwnership', 'cGcPlayerFreighterOwnership',
            'cGcUniverseAddressData', 'cGcPlayerWeapon', 'cGcPlayerExosuit',
        ],
        'Solar System': [
            'cGcSolarSystem', 'cGcSolarSystemData', 'cGcPlanet', 'cGcPlanetData',
            'cGcPlanetGenerationInputData', 'cGcSpaceStationNode',
            'cGcSolarSystemClass', 'cGcGalaxyStarTypes',
        ],
        'Multiplayer': [
            'cGcMultiplayerGlobals', 'cGcPersistentBaseEntry', 'cGcBaseBuildingEntry',
            'cGcSettlementState', 'cGcSettlementLocalSaveData',
            'cGcPlayerBasePersistentBuffer', 'cGcNetworkPlayer',
        ],
        'Simulation': [
            'cGcSimulation', 'cGcEnvironment', 'cGcGameState',
            'cGcRealityManager', 'cGcApplication',
        ],
        'Resources': [
            'cGcProductData', 'cGcSubstanceData', 'cGcTechnology',
            'cGcTechnologyTableEntry', 'cGcRecipeElement',
        ],
    }

    def __init__(self):
        """Initialize the struct registry."""
        self.structs: Dict[str, StructInfo] = {}
        self.enums: Dict[str, Dict[str, int]] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load struct definitions from NMS.py modules.

        Returns:
            True if loaded successfully
        """
        if self._loaded:
            return True

        try:
            self._load_structs_from_nmspy()
            self._load_enums_from_nmspy()
            self._loaded = True
            logger.info(f"Loaded {len(self.structs)} structs and {len(self.enums)} enums")
            return True
        except Exception as e:
            logger.error(f"Failed to load NMS.py definitions: {e}")
            return False

    def _load_structs_from_nmspy(self):
        """Load struct definitions from nmspy.data.types and exported_types."""
        modules_to_scan = []

        try:
            import nmspy.data.types as nms_types
            modules_to_scan.append(('nmspy.data.types', nms_types))
        except ImportError:
            logger.warning("Could not import nmspy.data.types")

        try:
            import nmspy.data.exported_types as nms_exported
            modules_to_scan.append(('nmspy.data.exported_types', nms_exported))
        except ImportError:
            logger.warning("Could not import nmspy.data.exported_types")

        for module_name, module in modules_to_scan:
            for name, obj in inspect.getmembers(module):
                if self._is_struct_class(obj):
                    struct_info = self._extract_struct_info(name, obj, module_name)
                    if struct_info:
                        self.structs[name] = struct_info

    def _is_struct_class(self, obj: Any) -> bool:
        """Check if object is a ctypes Structure class."""
        try:
            return (
                inspect.isclass(obj) and
                issubclass(obj, ctypes.Structure) and
                obj is not ctypes.Structure
            )
        except:
            return False

    def _extract_struct_info(self, name: str, struct_class: Type, module_name: str) -> Optional[StructInfo]:
        """Extract information about a struct class."""
        try:
            # Get size
            try:
                size = ctypes.sizeof(struct_class)
            except:
                size = 0

            # Get fields
            fields = []
            if hasattr(struct_class, '_fields_'):
                for field_name, field_type in struct_class._fields_:
                    try:
                        field_descriptor = getattr(struct_class, field_name)
                        field_info = FieldInfo(
                            name=field_name,
                            offset=field_descriptor.offset,
                            size=field_descriptor.size,
                            type_name=self._get_type_name(field_type),
                            is_pointer=self._is_pointer_type(field_type),
                            is_array=self._is_array_type(field_type),
                            array_length=self._get_array_length(field_type),
                            is_struct=self._is_struct_type(field_type),
                            is_enum=self._is_enum_type(field_type),
                        )
                        fields.append(field_info)
                    except Exception as e:
                        logger.debug(f"Could not extract field {field_name} from {name}: {e}")

            # Determine category
            category = self._categorize_struct(name)

            return StructInfo(
                name=name,
                size=size,
                fields=fields,
                source_module=module_name,
                category=category,
            )
        except Exception as e:
            logger.debug(f"Could not extract struct info for {name}: {e}")
            return None

    def _get_type_name(self, field_type: Any) -> str:
        """Get a human-readable name for a field type."""
        if hasattr(field_type, '__name__'):
            return field_type.__name__
        return str(field_type)

    def _is_pointer_type(self, field_type: Any) -> bool:
        """Check if field type is a pointer."""
        type_name = self._get_type_name(field_type)
        return 'POINTER' in type_name or type_name.startswith('LP_')

    def _is_array_type(self, field_type: Any) -> bool:
        """Check if field type is an array."""
        return hasattr(field_type, '_length_')

    def _get_array_length(self, field_type: Any) -> int:
        """Get array length if type is an array."""
        if hasattr(field_type, '_length_'):
            return field_type._length_
        return 0

    def _is_struct_type(self, field_type: Any) -> bool:
        """Check if field type is another struct."""
        try:
            return issubclass(field_type, ctypes.Structure)
        except:
            return False

    def _is_enum_type(self, field_type: Any) -> bool:
        """Check if field type is an enum."""
        try:
            return issubclass(field_type, IntEnum)
        except:
            return False

    def _categorize_struct(self, name: str) -> str:
        """Determine category for a struct based on name."""
        for category, struct_names in self.CATEGORIES.items():
            if name in struct_names:
                return category

        # Try to guess based on name patterns
        name_lower = name.lower()
        if 'player' in name_lower:
            return 'Player'
        elif 'solar' in name_lower or 'planet' in name_lower:
            return 'Solar System'
        elif 'multiplayer' in name_lower or 'base' in name_lower or 'settlement' in name_lower:
            return 'Multiplayer'
        elif 'simulation' in name_lower or 'game' in name_lower:
            return 'Simulation'
        elif 'inventory' in name_lower or 'resource' in name_lower:
            return 'Resources'

        return 'Other'

    def _load_enums_from_nmspy(self):
        """Load enum definitions from nmspy."""
        try:
            import nmspy.data.enums as nms_enums
            for name, obj in inspect.getmembers(nms_enums):
                if inspect.isclass(obj) and issubclass(obj, IntEnum) and obj is not IntEnum:
                    self.enums[name] = {member.name: member.value for member in obj}
        except ImportError:
            logger.warning("Could not import nmspy.data.enums")

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_struct(self, name: str) -> Optional[StructInfo]:
        """Get struct info by name."""
        return self.structs.get(name)

    def get_struct_class(self, name: str) -> Optional[Type]:
        """Get the actual ctypes class for a struct."""
        try:
            import nmspy.data.types as nms_types
            if hasattr(nms_types, name):
                return getattr(nms_types, name)

            import nmspy.data.exported_types as nms_exported
            if hasattr(nms_exported, name):
                return getattr(nms_exported, name)
        except:
            pass
        return None

    def get_structs_by_category(self, category: str) -> List[StructInfo]:
        """Get all structs in a category."""
        return [s for s in self.structs.values() if s.category == category]

    def get_categories(self) -> List[str]:
        """Get list of all categories with structs."""
        categories = set(s.category for s in self.structs.values())
        # Order by predefined categories first
        ordered = [c for c in self.CATEGORIES.keys() if c in categories]
        # Add any other categories
        for c in sorted(categories):
            if c not in ordered:
                ordered.append(c)
        return ordered

    def search_structs(self, query: str) -> List[StructInfo]:
        """Search structs by name or field name."""
        query_lower = query.lower()
        results = []

        for struct in self.structs.values():
            # Match struct name
            if query_lower in struct.name.lower():
                results.append(struct)
                continue

            # Match field names
            for field in struct.fields:
                if query_lower in field.name.lower():
                    results.append(struct)
                    break

        return results

    def get_enum_value_name(self, enum_name: str, value: int) -> str:
        """Get the name for an enum value."""
        if enum_name in self.enums:
            for name, val in self.enums[enum_name].items():
                if val == value:
                    return name
        return f"Unknown({value})"

    def format_field_value(self, field: FieldInfo, raw_value: Any) -> str:
        """Format a field value for display."""
        if field.is_enum and field.type_name in self.enums:
            return self.get_enum_value_name(field.type_name, raw_value)

        if field.is_pointer:
            if raw_value == 0:
                return "NULL"
            return f"0x{raw_value:X}"

        if isinstance(raw_value, float):
            return f"{raw_value:.4f}"

        if isinstance(raw_value, bool):
            return "True" if raw_value else "False"

        return str(raw_value)
