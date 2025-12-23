"""Struct mapper for reading NMS.py structures from memory.

Maps memory addresses to typed struct instances and extracts
field values for display.
"""

import ctypes
import logging
from typing import Optional, Dict, Any, List, Type
from dataclasses import dataclass, field

from .memory_reader import MemoryReader
from .struct_registry import StructRegistry, StructInfo, FieldInfo

logger = logging.getLogger(__name__)


@dataclass
class MappedField:
    """A field value read from memory."""
    name: str
    offset: int
    size: int
    type_name: str
    raw_bytes: bytes
    raw_value: Any
    formatted_value: str
    is_pointer: bool = False
    is_array: bool = False
    is_struct: bool = False
    nested_struct: Optional['MappedStruct'] = None


@dataclass
class MappedStruct:
    """A struct mapped from memory."""
    struct_type: str
    address: int
    size: int
    fields: List[MappedField] = field(default_factory=list)
    raw_bytes: Optional[bytes] = None
    valid: bool = True
    error: str = ""


class StructMapper:
    """Maps NMS.py structs to memory addresses and extracts field values."""

    def __init__(self, reader: MemoryReader, registry: StructRegistry):
        """Initialize the struct mapper.

        Args:
            reader: Memory reader instance
            registry: Struct registry with type definitions
        """
        self.reader = reader
        self.registry = registry

    def map_struct(self, address: int, struct_name: str, depth: int = 0, max_depth: int = 3) -> MappedStruct:
        """Map a struct from memory.

        Args:
            address: Memory address of struct
            struct_name: Name of struct type
            depth: Current recursion depth
            max_depth: Maximum recursion depth for nested structs

        Returns:
            MappedStruct with field values
        """
        result = MappedStruct(
            struct_type=struct_name,
            address=address,
            size=0,
        )

        if address == 0:
            result.valid = False
            result.error = "NULL address"
            return result

        # Get struct info from registry
        struct_info = self.registry.get_struct(struct_name)
        if struct_info is None:
            result.valid = False
            result.error = f"Unknown struct type: {struct_name}"
            return result

        result.size = struct_info.size

        # Read raw bytes for the entire struct
        if struct_info.size > 0:
            result.raw_bytes = self.reader.read_bytes(address, struct_info.size)
            if result.raw_bytes is None:
                result.valid = False
                result.error = f"Failed to read {struct_info.size} bytes at 0x{address:X}"
                return result

        # Try to use NMS.py's map_struct for typed access
        try:
            from pymhf.core.memutils import map_struct as pymhf_map_struct
            struct_class = self.registry.get_struct_class(struct_name)

            if struct_class:
                mapped_instance = pymhf_map_struct(address, struct_class)
                result.fields = self._extract_fields_from_instance(
                    mapped_instance, struct_info, address, depth, max_depth
                )
                return result
        except Exception as e:
            logger.debug(f"pymhf map_struct failed for {struct_name}: {e}")

        # Fallback: Read fields manually using offsets
        result.fields = self._extract_fields_manually(
            struct_info, address, depth, max_depth
        )

        return result

    def _extract_fields_from_instance(
        self,
        instance: Any,
        struct_info: StructInfo,
        base_address: int,
        depth: int,
        max_depth: int
    ) -> List[MappedField]:
        """Extract field values from a mapped struct instance."""
        fields = []

        for field_info in struct_info.fields:
            try:
                mapped_field = self._read_field_from_instance(
                    instance, field_info, base_address, depth, max_depth
                )
                if mapped_field:
                    fields.append(mapped_field)
            except Exception as e:
                logger.debug(f"Failed to read field {field_info.name}: {e}")
                # Add placeholder for failed field
                fields.append(MappedField(
                    name=field_info.name,
                    offset=field_info.offset,
                    size=field_info.size,
                    type_name=field_info.type_name,
                    raw_bytes=b'',
                    raw_value=None,
                    formatted_value=f"<error: {e}>",
                ))

        return fields

    def _read_field_from_instance(
        self,
        instance: Any,
        field_info: FieldInfo,
        base_address: int,
        depth: int,
        max_depth: int
    ) -> Optional[MappedField]:
        """Read a single field from a mapped instance."""
        try:
            raw_value = getattr(instance, field_info.name)
        except:
            raw_value = None

        # Read raw bytes for this field
        field_address = base_address + field_info.offset
        raw_bytes = self.reader.read_bytes(field_address, field_info.size) or b''

        # Format the value
        formatted_value = self._format_value(raw_value, field_info)

        mapped_field = MappedField(
            name=field_info.name,
            offset=field_info.offset,
            size=field_info.size,
            type_name=field_info.type_name,
            raw_bytes=raw_bytes,
            raw_value=raw_value,
            formatted_value=formatted_value,
            is_pointer=field_info.is_pointer,
            is_array=field_info.is_array,
            is_struct=field_info.is_struct,
        )

        # Recursively map nested structs
        if field_info.is_struct and depth < max_depth:
            try:
                nested = self.map_struct(
                    field_address,
                    field_info.type_name,
                    depth + 1,
                    max_depth
                )
                if nested.valid:
                    mapped_field.nested_struct = nested
            except:
                pass

        return mapped_field

    def _extract_fields_manually(
        self,
        struct_info: StructInfo,
        base_address: int,
        depth: int,
        max_depth: int
    ) -> List[MappedField]:
        """Extract field values using direct memory reads."""
        fields = []

        for field_info in struct_info.fields:
            field_address = base_address + field_info.offset

            # Read raw bytes
            raw_bytes = self.reader.read_bytes(field_address, field_info.size) or b''

            # Try to interpret the value based on type
            raw_value = self._read_typed_value(field_address, field_info)
            formatted_value = self._format_value(raw_value, field_info)

            mapped_field = MappedField(
                name=field_info.name,
                offset=field_info.offset,
                size=field_info.size,
                type_name=field_info.type_name,
                raw_bytes=raw_bytes,
                raw_value=raw_value,
                formatted_value=formatted_value,
                is_pointer=field_info.is_pointer,
                is_array=field_info.is_array,
                is_struct=field_info.is_struct,
            )

            # Recursively map nested structs
            if field_info.is_struct and depth < max_depth:
                try:
                    nested = self.map_struct(
                        field_address,
                        field_info.type_name,
                        depth + 1,
                        max_depth
                    )
                    if nested.valid:
                        mapped_field.nested_struct = nested
                except:
                    pass

            fields.append(mapped_field)

        return fields

    def _read_typed_value(self, address: int, field_info: FieldInfo) -> Any:
        """Read a value based on its type."""
        type_name = field_info.type_name.lower()

        if field_info.is_pointer:
            return self.reader.read_pointer(address)

        if field_info.size == 1:
            return self.reader.read_uint8(address)
        elif field_info.size == 2:
            return self.reader.read_uint16(address)
        elif field_info.size == 4:
            if 'float' in type_name:
                return self.reader.read_float(address)
            return self.reader.read_uint32(address)
        elif field_info.size == 8:
            if 'double' in type_name:
                return self.reader.read_double(address)
            return self.reader.read_uint64(address)

        # For larger types, return raw bytes
        return self.reader.read_bytes(address, field_info.size)

    def _format_value(self, value: Any, field_info: FieldInfo) -> str:
        """Format a value for display."""
        if value is None:
            return "<null>"

        # Check for enum
        if field_info.is_enum:
            enum_name = self.registry.get_enum_value_name(field_info.type_name, value)
            return f"{enum_name} ({value})"

        # Format pointer
        if field_info.is_pointer:
            if value == 0:
                return "NULL"
            return f"0x{value:X}"

        # Format based on type name hints
        type_lower = field_info.type_name.lower()

        if 'float' in type_lower or 'double' in type_lower:
            if isinstance(value, float):
                return f"{value:.4f}"

        if 'bool' in type_lower:
            return "True" if value else "False"

        if 'string' in type_lower:
            if isinstance(value, bytes):
                try:
                    return value.rstrip(b'\x00').decode('utf-8', errors='ignore')
                except:
                    pass
            return str(value)

        if isinstance(value, bytes):
            if len(value) <= 16:
                return value.hex()
            return f"{value[:16].hex()}... ({len(value)} bytes)"

        if isinstance(value, int):
            # Show both decimal and hex for integers
            if value > 0xFFFF:
                return f"{value} (0x{value:X})"
            return str(value)

        return str(value)

    # =========================================================================
    # Convenience Methods
    # =========================================================================

    def get_field_value(
        self,
        base_address: int,
        struct_name: str,
        field_name: str
    ) -> Optional[Any]:
        """Get a specific field value from a struct.

        Args:
            base_address: Address of struct
            struct_name: Struct type name
            field_name: Field name to read

        Returns:
            Field value or None
        """
        struct_info = self.registry.get_struct(struct_name)
        if struct_info is None:
            return None

        for field in struct_info.fields:
            if field.name == field_name:
                return self._read_typed_value(
                    base_address + field.offset,
                    field
                )

        return None

    def map_array(
        self,
        base_address: int,
        struct_name: str,
        count: int,
        max_count: int = 100
    ) -> List[MappedStruct]:
        """Map an array of structs.

        Args:
            base_address: Address of first element
            struct_name: Struct type name
            count: Number of elements
            max_count: Maximum elements to read

        Returns:
            List of mapped structs
        """
        struct_info = self.registry.get_struct(struct_name)
        if struct_info is None or struct_info.size == 0:
            return []

        count = min(count, max_count)
        results = []

        for i in range(count):
            element_addr = base_address + (i * struct_info.size)
            mapped = self.map_struct(element_addr, struct_name, depth=1)
            results.append(mapped)

        return results
