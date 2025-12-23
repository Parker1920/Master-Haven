"""Low-level memory reading utilities using ctypes.

Based on patterns from haven_extractor.py - uses ctypes.memmove() for direct memory access.
"""

import ctypes
import logging
import struct
import traceback
from typing import Optional, List, Tuple, Any

logger = logging.getLogger(__name__)


class MemoryReader:
    """Low-level memory reading utilities for game memory access.

    Uses ctypes.memmove() pattern from haven_extractor.py for direct
    memory access within the injected process space.
    """

    # Windows x64 user space pointer range (expanded for game memory)
    # Game memory can be in lower ranges too
    POINTER_RANGE = (0x10000, 0x7FFFFFFFFFFF)

    # Minimum valid address (skip NULL and low memory that would crash)
    MIN_VALID_ADDRESS = 0x10000

    # Maximum read size to prevent excessive memory access
    MAX_READ_SIZE = 1024 * 1024  # 1MB max

    def __init__(self):
        """Initialize the memory reader."""
        self._read_count = 0
        self._error_count = 0
        self._last_error = None
        self._crash_addresses = set()  # Track addresses that caused issues
        logger.info("MemoryReader initialized")

    def _is_safe_address(self, address: int, size: int = 1) -> bool:
        """Check if an address is safe to read from.

        Args:
            address: Memory address to check
            size: Number of bytes to read

        Returns:
            True if address appears safe to access
        """
        if address is None or address == 0:
            return False
        if address < self.MIN_VALID_ADDRESS:
            logger.debug(f"Address 0x{address:X} below minimum (0x{self.MIN_VALID_ADDRESS:X})")
            return False
        if address > self.POINTER_RANGE[1]:
            logger.debug(f"Address 0x{address:X} above maximum (0x{self.POINTER_RANGE[1]:X})")
            return False
        if size <= 0 or size > self.MAX_READ_SIZE:
            logger.debug(f"Invalid read size: {size}")
            return False
        if address in self._crash_addresses:
            logger.debug(f"Address 0x{address:X} previously caused issues, skipping")
            return False
        return True

    def _safe_memmove(self, dest, src: int, size: int) -> bool:
        """Safely perform memmove with error handling.

        Args:
            dest: Destination buffer (ctypes)
            src: Source address (int)
            size: Number of bytes

        Returns:
            True if successful, False otherwise
        """
        try:
            ctypes.memmove(dest, src, size)
            return True
        except OSError as e:
            # Access violation or similar
            self._crash_addresses.add(src)
            self._last_error = f"OSError at 0x{src:X}: {e}"
            logger.warning(f"Memory access error at 0x{src:X}: {e}")
            return False
        except Exception as e:
            self._crash_addresses.add(src)
            self._last_error = f"Error at 0x{src:X}: {e}"
            logger.warning(f"Unexpected error reading 0x{src:X}: {e}")
            return False

    @property
    def stats(self) -> dict:
        """Get read statistics."""
        return {
            'read_count': self._read_count,
            'error_count': self._error_count,
        }

    def reset_stats(self):
        """Reset read statistics."""
        self._read_count = 0
        self._error_count = 0

    # =========================================================================
    # Basic Type Reads
    # =========================================================================

    def read_bytes(self, address: int, size: int) -> Optional[bytes]:
        """Read raw bytes from memory.

        Args:
            address: Memory address to read from
            size: Number of bytes to read

        Returns:
            Bytes read, or None on error
        """
        # Validate address before attempting read
        if not self._is_safe_address(address, size):
            self._error_count += 1
            return None

        try:
            buffer = ctypes.create_string_buffer(size)
            if self._safe_memmove(buffer, address, size):
                self._read_count += 1
                return buffer.raw
            else:
                self._error_count += 1
                return None
        except Exception as e:
            self._error_count += 1
            self._crash_addresses.add(address)
            logger.warning(f"Failed to read {size} bytes at 0x{address:X}: {e}")
            return None

    def read_int8(self, address: int) -> Optional[int]:
        """Read a signed 8-bit integer."""
        if not self._is_safe_address(address, 1):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_int8()
            if self._safe_memmove(ctypes.addressof(value), address, 1):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read int8 at 0x{address:X}: {e}")
            return None

    def read_uint8(self, address: int) -> Optional[int]:
        """Read an unsigned 8-bit integer."""
        if not self._is_safe_address(address, 1):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_uint8()
            if self._safe_memmove(ctypes.addressof(value), address, 1):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read uint8 at 0x{address:X}: {e}")
            return None

    def read_int16(self, address: int) -> Optional[int]:
        """Read a signed 16-bit integer."""
        if not self._is_safe_address(address, 2):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_int16()
            if self._safe_memmove(ctypes.addressof(value), address, 2):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read int16 at 0x{address:X}: {e}")
            return None

    def read_uint16(self, address: int) -> Optional[int]:
        """Read an unsigned 16-bit integer."""
        if not self._is_safe_address(address, 2):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_uint16()
            if self._safe_memmove(ctypes.addressof(value), address, 2):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read uint16 at 0x{address:X}: {e}")
            return None

    def read_int32(self, address: int) -> Optional[int]:
        """Read a signed 32-bit integer."""
        if not self._is_safe_address(address, 4):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_int32()
            if self._safe_memmove(ctypes.addressof(value), address, 4):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read int32 at 0x{address:X}: {e}")
            return None

    def read_uint32(self, address: int) -> Optional[int]:
        """Read an unsigned 32-bit integer."""
        if not self._is_safe_address(address, 4):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_uint32()
            if self._safe_memmove(ctypes.addressof(value), address, 4):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read uint32 at 0x{address:X}: {e}")
            return None

    def read_int64(self, address: int) -> Optional[int]:
        """Read a signed 64-bit integer."""
        if not self._is_safe_address(address, 8):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_int64()
            if self._safe_memmove(ctypes.addressof(value), address, 8):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read int64 at 0x{address:X}: {e}")
            return None

    def read_uint64(self, address: int) -> Optional[int]:
        """Read an unsigned 64-bit integer."""
        if not self._is_safe_address(address, 8):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_uint64()
            if self._safe_memmove(ctypes.addressof(value), address, 8):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read uint64 at 0x{address:X}: {e}")
            return None

    def read_float(self, address: int) -> Optional[float]:
        """Read a 32-bit float."""
        if not self._is_safe_address(address, 4):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_float()
            if self._safe_memmove(ctypes.addressof(value), address, 4):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read float at 0x{address:X}: {e}")
            return None

    def read_double(self, address: int) -> Optional[float]:
        """Read a 64-bit double."""
        if not self._is_safe_address(address, 8):
            self._error_count += 1
            return None
        try:
            value = ctypes.c_double()
            if self._safe_memmove(ctypes.addressof(value), address, 8):
                self._read_count += 1
                return value.value
            self._error_count += 1
            return None
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read double at 0x{address:X}: {e}")
            return None

    def read_bool(self, address: int) -> Optional[bool]:
        """Read a boolean (1 byte)."""
        val = self.read_uint8(address)
        return bool(val) if val is not None else None

    # =========================================================================
    # Pointer Operations
    # =========================================================================

    def read_pointer(self, address: int) -> Optional[int]:
        """Read a 64-bit pointer value.

        Returns:
            Pointer value, or None on error
        """
        return self.read_uint64(address)

    def is_valid_pointer(self, value: int) -> bool:
        """Check if a value looks like a valid pointer.

        Args:
            value: Value to check

        Returns:
            True if value falls within typical Windows x64 user space
        """
        if value == 0:
            return False
        return self.POINTER_RANGE[0] <= value <= self.POINTER_RANGE[1]

    def dereference_pointer(self, address: int) -> Optional[int]:
        """Read a pointer and return what it points to.

        Args:
            address: Address containing the pointer

        Returns:
            The dereferenced address, or None if invalid
        """
        ptr = self.read_pointer(address)
        if ptr is not None and self.is_valid_pointer(ptr):
            return ptr
        return None

    def follow_pointer_chain(self, base: int, offsets: List[int]) -> Optional[int]:
        """Follow a chain of pointer offsets.

        Args:
            base: Starting address
            offsets: List of offsets to follow

        Returns:
            Final address after following all offsets, or None if chain breaks
        """
        addr = base
        for i, offset in enumerate(offsets):
            if i < len(offsets) - 1:
                # Not the last offset, dereference
                addr = self.dereference_pointer(addr + offset)
                if addr is None:
                    logger.debug(f"Pointer chain broke at offset {i} (0x{offset:X})")
                    return None
            else:
                # Last offset, just add
                addr = addr + offset
        return addr

    # =========================================================================
    # String Operations
    # =========================================================================

    def read_string(self, address: int, max_len: int = 256, encoding: str = 'utf-8') -> Optional[str]:
        """Read a null-terminated string from memory.

        Args:
            address: Memory address to read from
            max_len: Maximum string length to read
            encoding: String encoding (default utf-8)

        Returns:
            Decoded string, or None on error
        """
        if not self._is_safe_address(address, max_len):
            self._error_count += 1
            return None
        try:
            buffer = ctypes.create_string_buffer(max_len)
            if not self._safe_memmove(buffer, address, max_len):
                self._error_count += 1
                return None
            raw = buffer.raw

            # Find null terminator
            null_pos = raw.find(b'\x00')
            if null_pos >= 0:
                raw = raw[:null_pos]

            self._read_count += 1
            return raw.decode(encoding, errors='ignore')
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read string at 0x{address:X}: {e}")
            return None

    def read_wstring(self, address: int, max_len: int = 256) -> Optional[str]:
        """Read a null-terminated wide string (UTF-16) from memory.

        Args:
            address: Memory address to read from
            max_len: Maximum number of characters to read

        Returns:
            Decoded string, or None on error
        """
        byte_len = max_len * 2
        if not self._is_safe_address(address, byte_len):
            self._error_count += 1
            return None
        try:
            # Wide strings are 2 bytes per character
            buffer = ctypes.create_string_buffer(byte_len)
            if not self._safe_memmove(buffer, address, byte_len):
                self._error_count += 1
                return None
            raw = buffer.raw

            # Find null terminator (2 zero bytes)
            for i in range(0, len(raw) - 1, 2):
                if raw[i] == 0 and raw[i + 1] == 0:
                    raw = raw[:i]
                    break

            self._read_count += 1
            return raw.decode('utf-16-le', errors='ignore')
        except Exception as e:
            self._error_count += 1
            logger.debug(f"Failed to read wstring at 0x{address:X}: {e}")
            return None

    def read_fixed_string(self, address: int, length: int, encoding: str = 'utf-8') -> Optional[str]:
        """Read a fixed-length string (not null-terminated).

        Args:
            address: Memory address to read from
            length: Exact number of bytes to read
            encoding: String encoding

        Returns:
            Decoded string, or None on error
        """
        data = self.read_bytes(address, length)
        if data is None:
            return None
        # Strip trailing nulls
        data = data.rstrip(b'\x00')
        return data.decode(encoding, errors='ignore')

    # =========================================================================
    # Vector/Array Operations
    # =========================================================================

    def read_vector3(self, address: int) -> Optional[Tuple[float, float, float]]:
        """Read a 3D vector (3 floats)."""
        data = self.read_bytes(address, 12)
        if data is None:
            return None
        try:
            x, y, z = struct.unpack('<fff', data)
            return (x, y, z)
        except:
            return None

    def read_vector4(self, address: int) -> Optional[Tuple[float, float, float, float]]:
        """Read a 4D vector (4 floats)."""
        data = self.read_bytes(address, 16)
        if data is None:
            return None
        try:
            x, y, z, w = struct.unpack('<ffff', data)
            return (x, y, z, w)
        except:
            return None

    def read_array(self, address: int, element_size: int, count: int) -> Optional[List[bytes]]:
        """Read an array of fixed-size elements.

        Args:
            address: Base address of array
            element_size: Size of each element in bytes
            count: Number of elements to read

        Returns:
            List of raw bytes for each element, or None on error
        """
        if count <= 0 or element_size <= 0:
            return []

        total_size = element_size * count
        data = self.read_bytes(address, total_size)
        if data is None:
            return None

        elements = []
        for i in range(count):
            start = i * element_size
            end = start + element_size
            elements.append(data[start:end])

        return elements

    # =========================================================================
    # Offset-based Operations
    # =========================================================================

    def read_at_offset(self, base: int, offset: int, read_type: str) -> Optional[Any]:
        """Read a value at base + offset using the specified type.

        Args:
            base: Base address
            offset: Offset from base
            read_type: Type string ('int8', 'uint8', 'int16', 'uint16',
                      'int32', 'uint32', 'int64', 'uint64', 'float',
                      'double', 'pointer', 'bool')

        Returns:
            Value read, or None on error
        """
        addr = base + offset

        read_funcs = {
            'int8': self.read_int8,
            'uint8': self.read_uint8,
            'int16': self.read_int16,
            'uint16': self.read_uint16,
            'int32': self.read_int32,
            'uint32': self.read_uint32,
            'int64': self.read_int64,
            'uint64': self.read_uint64,
            'float': self.read_float,
            'double': self.read_double,
            'pointer': self.read_pointer,
            'bool': self.read_bool,
        }

        func = read_funcs.get(read_type)
        if func is None:
            logger.warning(f"Unknown read type: {read_type}")
            return None

        return func(addr)

    # =========================================================================
    # Utility Functions
    # =========================================================================

    def hex_dump(self, address: int, size: int, bytes_per_line: int = 16) -> str:
        """Generate a hex dump string of memory.

        Args:
            address: Starting address
            size: Number of bytes to dump
            bytes_per_line: Bytes per line in output

        Returns:
            Formatted hex dump string
        """
        data = self.read_bytes(address, size)
        if data is None:
            return f"Failed to read {size} bytes at 0x{address:X}"

        lines = []
        for i in range(0, len(data), bytes_per_line):
            chunk = data[i:i + bytes_per_line]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            # Pad hex part to consistent width
            hex_part = hex_part.ljust(bytes_per_line * 3 - 1)

            # ASCII representation
            ascii_part = ''.join(
                chr(b) if 32 <= b < 127 else '.'
                for b in chunk
            )

            offset = i
            lines.append(f"0x{offset:04X}: {hex_part}  {ascii_part}")

        return '\n'.join(lines)
