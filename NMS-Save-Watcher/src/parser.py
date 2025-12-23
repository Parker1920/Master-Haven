"""
NMS Save File Parser.
Handles LZ4 decompression and JSON key deobfuscation.
"""

import json
import lz4.frame
import lz4.block
import logging
from pathlib import Path
from typing import Optional, Any
import struct

logger = logging.getLogger('nms_watcher.parser')


class KeyMapper:
    """Handles obfuscated key deobfuscation for NMS save files."""

    def __init__(self, mappings_path: Optional[Path] = None):
        """
        Initialize the key mapper.

        Args:
            mappings_path: Path to mapping.json file. If None, uses bundled mappings.
        """
        self.mappings: dict[str, str] = {}
        self.reverse_mappings: dict[str, str] = {}
        self.unknown_keys: set[str] = set()

        if mappings_path is None:
            # Use bundled mappings from data directory
            mappings_path = Path(__file__).parent.parent / 'data' / 'mapping.json'

        self._load_mappings(mappings_path)

    def _load_mappings(self, path: Path):
        """Load key mappings from JSON file."""
        if not path.exists():
            logger.warning(f"Mappings file not found: {path}")
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle both formats: array of {Key, Value} or direct dict
            if isinstance(data, dict) and 'Mapping' in data:
                # MBINCompiler format: {"libMBIN_version": "...", "Mapping": [{Key, Value}, ...]}
                for item in data['Mapping']:
                    key = item.get('Key', '')
                    value = item.get('Value', '')
                    if key and value:
                        self.mappings[key] = value
                        self.reverse_mappings[value] = key
            elif isinstance(data, dict):
                # Simple dict format: {"obfuscated": "real", ...}
                self.mappings = data
                self.reverse_mappings = {v: k for k, v in data.items()}
            elif isinstance(data, list):
                # Array format: [{Key, Value}, ...]
                for item in data:
                    key = item.get('Key', '')
                    value = item.get('Value', '')
                    if key and value:
                        self.mappings[key] = value
                        self.reverse_mappings[value] = key

            logger.info(f"Loaded {len(self.mappings)} key mappings from {path}")

        except Exception as e:
            logger.error(f"Failed to load mappings: {e}")

    def deobfuscate(self, obj: Any) -> Any:
        """
        Recursively deobfuscate JSON keys.

        Args:
            obj: JSON object (dict, list, or primitive)

        Returns:
            Object with deobfuscated keys
        """
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                # Try to deobfuscate the key
                if key in self.mappings:
                    new_key = self.mappings[key]
                else:
                    new_key = key
                    # Track unknown keys that look obfuscated
                    # Obfuscated keys are typically 3 characters with special chars
                    if len(key) == 3 and any(c in key for c in '@><=:?;'):
                        self.unknown_keys.add(key)
                    elif len(key) <= 4 and not key.isalpha():
                        self.unknown_keys.add(key)

                result[new_key] = self.deobfuscate(value)
            return result
        elif isinstance(obj, list):
            return [self.deobfuscate(item) for item in obj]
        else:
            return obj

    def obfuscate(self, obj: Any) -> Any:
        """
        Recursively obfuscate JSON keys (reverse of deobfuscate).

        Args:
            obj: JSON object with real key names

        Returns:
            Object with obfuscated keys
        """
        if isinstance(obj, dict):
            result = {}
            for key, value in obj.items():
                if key in self.reverse_mappings:
                    new_key = self.reverse_mappings[key]
                else:
                    new_key = key
                result[new_key] = self.obfuscate(value)
            return result
        elif isinstance(obj, list):
            return [self.obfuscate(item) for item in obj]
        else:
            return obj

    def get_unknown_keys(self) -> list[str]:
        """Return list of unknown obfuscated keys encountered."""
        return list(self.unknown_keys)

    def clear_unknown_keys(self):
        """Clear the list of unknown keys."""
        self.unknown_keys.clear()


class SaveParser:
    """Parser for NMS save files (.hg format)."""

    def __init__(self, key_mapper: Optional[KeyMapper] = None):
        """
        Initialize the save parser.

        Args:
            key_mapper: KeyMapper instance for deobfuscation. Creates one if None.
        """
        self.key_mapper = key_mapper or KeyMapper()

    def decompress_save(self, file_path: Path) -> bytes:
        """
        Decompress/extract an NMS .hg save file.

        NMS save files use chunked LZ4 compression:
        - Each chunk has 16-byte header: magic(4) + compressed_size(4) + decompressed_size(4) + reserved(4)
        - Magic number: 0xFEEDA1E5
        - Chunks are typically 512KB decompressed
        - Multiple chunks are concatenated

        Args:
            file_path: Path to the .hg file

        Returns:
            Extracted/decompressed data as bytes

        Raises:
            ValueError: If extraction fails
        """
        # Ensure file_path is a Path object
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Save file not found: {file_path}")

        with open(file_path, 'rb') as f:
            data = f.read()

        NMS_MAGIC = 0xFEEDA1E5

        # Strategy 1: NMS chunked LZ4 format (current format)
        # Check if file starts with NMS magic
        if len(data) >= 16:
            magic = struct.unpack('<I', data[0:4])[0]
            if magic == NMS_MAGIC:
                try:
                    result = self._decompress_chunked(data)
                    logger.debug(f"Decompressed chunked NMS format: {len(data)} -> {len(result)} bytes")
                    return result
                except Exception as e:
                    logger.debug(f"Chunked decompression failed: {e}, trying other formats...")

        # Strategy 2: Look for raw JSON (uncompressed saves)
        for offset in [0, 4, 8, 12, 16, 18, 20, 24, 32]:
            if offset < len(data) and data[offset:offset+1] == b'{':
                sample = data[offset:offset+50]
                if b':' in sample and b'"' in sample:
                    logger.debug(f"Found raw JSON at offset {offset}")
                    return data[offset:]

        # Strategy 3: Standard LZ4 frame (legacy saves)
        try:
            decompressed = lz4.frame.decompress(data)
            logger.debug(f"Decompressed using LZ4 frame: {len(data)} -> {len(decompressed)} bytes")
            return decompressed
        except Exception as e:
            logger.debug(f"LZ4 frame decompress failed: {e}")

        # Strategy 4: Single LZ4 block with header
        for header_size in [8, 12, 16, 20]:
            if len(data) <= header_size:
                continue
            try:
                decompressed_size = struct.unpack('<I', data[header_size-8:header_size-4])[0]
                if 1000 < decompressed_size < 500_000_000:
                    compressed_data = data[header_size:]
                    try:
                        decompressed = lz4.block.decompress(compressed_data, uncompressed_size=decompressed_size)
                        if decompressed[:1] == b'{':
                            logger.debug(f"Decompressed using {header_size}-byte header")
                            return decompressed
                    except:
                        pass
            except:
                continue

        raise ValueError(f"Failed to extract save file - unknown format. File size: {len(data)} bytes")

    def _decompress_chunked(self, data: bytes) -> bytes:
        """
        Decompress NMS chunked LZ4 format.

        Each chunk has 16-byte header:
        - Bytes 0-3: Magic (0xFEEDA1E5)
        - Bytes 4-7: Compressed size
        - Bytes 8-11: Decompressed size (typically 524288 = 512KB)
        - Bytes 12-15: Reserved (0)
        - Bytes 16+: LZ4 compressed data

        Args:
            data: Raw file data

        Returns:
            Decompressed data
        """
        NMS_MAGIC = 0xFEEDA1E5
        result = b''
        offset = 0
        chunk_count = 0

        while offset + 16 <= len(data):
            # Read chunk header
            magic = struct.unpack('<I', data[offset:offset+4])[0]
            if magic != NMS_MAGIC:
                if chunk_count == 0:
                    raise ValueError(f"Invalid magic number: 0x{magic:08X}")
                # End of chunks (might be trailing data)
                break

            compressed_size = struct.unpack('<I', data[offset+4:offset+8])[0]
            decompressed_size = struct.unpack('<I', data[offset+8:offset+12])[0]

            # Sanity checks
            if compressed_size == 0 or decompressed_size == 0:
                break
            if offset + 16 + compressed_size > len(data):
                logger.warning(f"Chunk {chunk_count+1} extends beyond file, truncating")
                compressed_size = len(data) - offset - 16

            # Decompress chunk
            chunk_data = data[offset+16:offset+16+compressed_size]
            try:
                decompressed = lz4.block.decompress(chunk_data, uncompressed_size=decompressed_size)
                result += decompressed
                chunk_count += 1
                logger.debug(f"Chunk {chunk_count}: {compressed_size} -> {len(decompressed)} bytes")
            except Exception as e:
                if chunk_count == 0:
                    raise ValueError(f"Failed to decompress first chunk: {e}")
                logger.warning(f"Chunk {chunk_count+1} decompression failed, stopping: {e}")
                break

            offset += 16 + compressed_size

        if chunk_count == 0:
            raise ValueError("No valid chunks found")

        logger.info(f"Decompressed {chunk_count} chunks, total {len(result)} bytes")
        return result

    def parse_save(self, file_path: Path, deobfuscate: bool = True) -> dict:
        """
        Parse an NMS save file and return the JSON data.

        Args:
            file_path: Path to the .hg file (can be str or Path)
            deobfuscate: Whether to deobfuscate keys (default True)

        Returns:
            Parsed save data as dict

        Raises:
            ValueError: If parsing fails
        """
        # Ensure file_path is a Path object
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # Decompress/extract
        decompressed = self.decompress_save(file_path)

        # Parse JSON
        try:
            # Handle BOM if present, and use errors='replace' for any stray bytes
            text = decompressed.decode('utf-8-sig', errors='replace')

            # Try to parse the JSON
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                # NMS saves may have trailing garbage after the JSON
                # Try to find the actual end of the JSON object
                if 'Extra data' in str(e) or 'Expecting' in str(e):
                    # Find the last valid closing brace
                    for i in range(len(text) - 1, max(0, len(text) - 1000), -1):
                        if text[i] == '}':
                            try:
                                data = json.loads(text[:i+1])
                                logger.debug(f"Parsed JSON after truncating at position {i+1}")
                                break
                            except json.JSONDecodeError:
                                continue
                    else:
                        raise ValueError(f"Failed to parse JSON: {e}")
                else:
                    raise ValueError(f"Failed to parse JSON: {e}")
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode save file: {e}")

        # Deobfuscate keys
        if deobfuscate:
            data = self.key_mapper.deobfuscate(data)

        return data

    def get_unknown_keys(self) -> list[str]:
        """Return unknown obfuscated keys found during parsing."""
        return self.key_mapper.get_unknown_keys()


def parse_nms_save(file_path: Path, mappings_path: Optional[Path] = None) -> tuple[dict, list[str]]:
    """
    Convenience function to parse an NMS save file.

    Args:
        file_path: Path to the .hg save file
        mappings_path: Optional path to key mappings file

    Returns:
        Tuple of (parsed_data, unknown_keys)
    """
    key_mapper = KeyMapper(mappings_path)
    parser = SaveParser(key_mapper)
    data = parser.parse_save(file_path)
    unknown_keys = parser.get_unknown_keys()

    return data, unknown_keys
