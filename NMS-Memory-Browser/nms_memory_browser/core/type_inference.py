"""Type inference engine for unknown memory regions.

Attempts to detect and classify data types in unmapped memory
based on heuristics and pattern analysis.
"""

import struct
import math
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class InferredType(Enum):
    """Types that can be inferred from raw memory."""
    UNKNOWN = "unknown"
    INT8 = "int8"
    UINT8 = "uint8"
    INT16 = "int16"
    UINT16 = "uint16"
    INT32 = "int32"
    UINT32 = "uint32"
    INT64 = "int64"
    UINT64 = "uint64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    POINTER = "pointer"
    STRING = "string"
    WSTRING = "wstring"
    BOOL = "bool"
    PADDING = "padding"
    STRUCT = "struct"


@dataclass
class TypeInference:
    """Result of type inference on a memory region."""
    inferred_type: InferredType
    value: Any
    confidence: float  # 0.0 to 1.0
    offset: int = 0
    size: int = 0
    alternatives: List[Tuple[InferredType, Any, float]] = None

    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class TypeInferenceEngine:
    """Engine for detecting types in unknown memory regions.

    Uses various heuristics to determine the most likely type
    of data at a given memory location.
    """

    # Windows x64 user space pointer range
    POINTER_RANGE = (0x7FF000000000, 0x7FFFFFFFFFFF)

    # Reasonable float ranges for game data
    FLOAT_REASONABLE_RANGE = (-1e6, 1e6)
    FLOAT_COMMON_RANGE = (-10000, 10000)

    # String detection settings
    STRING_MIN_LENGTH = 3
    STRING_MAX_LENGTH = 256

    def __init__(self):
        """Initialize the type inference engine."""
        pass

    def infer_type(self, data: bytes, offset: int = 0) -> TypeInference:
        """Infer the most likely type for a memory region.

        Args:
            data: Raw bytes to analyze
            offset: Offset within parent structure (for context)

        Returns:
            TypeInference with best guess and alternatives
        """
        if not data or len(data) == 0:
            return TypeInference(
                inferred_type=InferredType.UNKNOWN,
                value=None,
                confidence=0.0,
                offset=offset,
                size=0,
            )

        results = []

        # Check for padding (all zeros)
        if self._is_padding(data):
            results.append((InferredType.PADDING, None, 0.9))

        # Try string detection first (consumes variable length)
        string_result = self._detect_string(data)
        if string_result:
            results.append(string_result)

        # Try wide string
        wstring_result = self._detect_wstring(data)
        if wstring_result:
            results.append(wstring_result)

        # 8-byte interpretations
        if len(data) >= 8:
            # Pointer
            ptr_result = self._score_pointer(data[:8])
            if ptr_result:
                results.append(ptr_result)

            # Int64/Uint64
            int64_result = self._score_int64(data[:8])
            if int64_result:
                results.append(int64_result)

            # Double
            double_result = self._score_double(data[:8])
            if double_result:
                results.append(double_result)

        # 4-byte interpretations
        if len(data) >= 4:
            # Float
            float_result = self._score_float(data[:4])
            if float_result:
                results.append(float_result)

            # Int32/Uint32
            int32_result = self._score_int32(data[:4])
            if int32_result:
                results.append(int32_result)

            # Bool (if value is 0 or 1)
            bool_result = self._score_bool(data[:4])
            if bool_result:
                results.append(bool_result)

        # 2-byte interpretations
        if len(data) >= 2:
            int16_result = self._score_int16(data[:2])
            if int16_result:
                results.append(int16_result)

        # 1-byte interpretation
        if len(data) >= 1:
            int8_result = self._score_int8(data[:1])
            if int8_result:
                results.append(int8_result)

        # Sort by confidence
        results.sort(key=lambda x: x[2], reverse=True)

        if not results:
            return TypeInference(
                inferred_type=InferredType.UNKNOWN,
                value=data.hex(),
                confidence=0.0,
                offset=offset,
                size=len(data),
            )

        best = results[0]
        return TypeInference(
            inferred_type=best[0],
            value=best[1],
            confidence=best[2],
            offset=offset,
            size=self._get_type_size(best[0], best[1]),
            alternatives=results[1:4] if len(results) > 1 else [],
        )

    def infer_sequence(self, data: bytes, alignment: int = 4) -> List[TypeInference]:
        """Infer types for a sequence of memory locations.

        Args:
            data: Raw bytes to analyze
            alignment: Assumed data alignment

        Returns:
            List of TypeInferences covering the data
        """
        results = []
        offset = 0

        while offset < len(data):
            remaining = data[offset:]
            inference = self.infer_type(remaining, offset)

            if inference.size > 0:
                results.append(inference)
                offset += inference.size
            else:
                # Move by alignment if we couldn't determine type
                results.append(TypeInference(
                    inferred_type=InferredType.UNKNOWN,
                    value=remaining[:alignment].hex() if len(remaining) >= alignment else remaining.hex(),
                    confidence=0.0,
                    offset=offset,
                    size=min(alignment, len(remaining)),
                ))
                offset += alignment

        return results

    # =========================================================================
    # Detection Helpers
    # =========================================================================

    def _is_padding(self, data: bytes) -> bool:
        """Check if data is all zeros (likely padding)."""
        return all(b == 0 for b in data)

    def _detect_string(self, data: bytes) -> Optional[Tuple[InferredType, str, float]]:
        """Detect if data contains a printable ASCII string."""
        if len(data) < self.STRING_MIN_LENGTH:
            return None

        # Look for printable ASCII followed by null
        string_bytes = []
        for i, b in enumerate(data):
            if b == 0:
                # Found null terminator
                if len(string_bytes) >= self.STRING_MIN_LENGTH:
                    try:
                        s = bytes(string_bytes).decode('utf-8')
                        if s.isprintable() and not s.isspace():
                            # Higher confidence for longer strings
                            confidence = min(0.95, 0.6 + len(s) * 0.02)
                            return (InferredType.STRING, s, confidence)
                    except:
                        pass
                break
            elif 32 <= b < 127:
                string_bytes.append(b)
            else:
                # Non-printable character
                break

        return None

    def _detect_wstring(self, data: bytes) -> Optional[Tuple[InferredType, str, float]]:
        """Detect if data contains a UTF-16 wide string."""
        if len(data) < self.STRING_MIN_LENGTH * 2:
            return None

        # Look for UTF-16 LE pattern (ASCII chars with 0x00 between)
        chars = []
        for i in range(0, len(data) - 1, 2):
            low = data[i]
            high = data[i + 1]

            if low == 0 and high == 0:
                # Null terminator
                if len(chars) >= self.STRING_MIN_LENGTH:
                    s = ''.join(chars)
                    if s.isprintable() and not s.isspace():
                        confidence = min(0.9, 0.5 + len(s) * 0.02)
                        return (InferredType.WSTRING, s, confidence)
                break
            elif high == 0 and 32 <= low < 127:
                # ASCII character in UTF-16
                chars.append(chr(low))
            else:
                # Not a simple wide string
                break

        return None

    def _score_pointer(self, data: bytes) -> Optional[Tuple[InferredType, str, float]]:
        """Score likelihood that data is a pointer."""
        try:
            value = struct.unpack('<Q', data)[0]

            if value == 0:
                # NULL pointer - possible but low confidence
                return (InferredType.POINTER, "NULL", 0.3)

            if self.POINTER_RANGE[0] <= value <= self.POINTER_RANGE[1]:
                # Looks like valid user-space pointer
                confidence = 0.85
                # Higher confidence if 8-byte aligned
                if value % 8 == 0:
                    confidence = 0.92
                return (InferredType.POINTER, f"0x{value:X}", confidence)

        except:
            pass
        return None

    def _score_float(self, data: bytes) -> Optional[Tuple[InferredType, float, float]]:
        """Score likelihood that data is a float."""
        try:
            value = struct.unpack('<f', data)[0]

            if math.isnan(value) or math.isinf(value):
                return None

            # Score based on how "reasonable" the float looks
            if self.FLOAT_COMMON_RANGE[0] <= value <= self.FLOAT_COMMON_RANGE[1]:
                # Very common game float range
                confidence = 0.7

                # Boost for values that look like coordinates, percentages, etc.
                if -1 <= value <= 1:
                    confidence = 0.75  # Normalized values
                elif 0 <= value <= 100:
                    confidence = 0.72  # Percentages
                elif abs(value) < 1:
                    confidence = 0.68  # Small decimals

                return (InferredType.FLOAT32, value, confidence)

            elif self.FLOAT_REASONABLE_RANGE[0] <= value <= self.FLOAT_REASONABLE_RANGE[1]:
                return (InferredType.FLOAT32, value, 0.5)

        except:
            pass
        return None

    def _score_double(self, data: bytes) -> Optional[Tuple[InferredType, float, float]]:
        """Score likelihood that data is a double."""
        try:
            value = struct.unpack('<d', data)[0]

            if math.isnan(value) or math.isinf(value):
                return None

            if self.FLOAT_REASONABLE_RANGE[0] <= value <= self.FLOAT_REASONABLE_RANGE[1]:
                return (InferredType.FLOAT64, value, 0.4)  # Lower than float32

        except:
            pass
        return None

    def _score_int32(self, data: bytes) -> Optional[Tuple[InferredType, int, float]]:
        """Score likelihood that data is a 32-bit integer."""
        try:
            signed = struct.unpack('<i', data)[0]
            unsigned = struct.unpack('<I', data)[0]

            # Prefer signed for negative or small values
            if -1000000 <= signed <= 1000000:
                confidence = 0.5
                # Boost for common value patterns
                if 0 <= signed <= 100:
                    confidence = 0.6  # Counts, levels, etc.
                elif signed < 0:
                    confidence = 0.55
                return (InferredType.INT32, signed, confidence)

            # Use unsigned for larger values
            if unsigned <= 0xFFFFFF:
                return (InferredType.UINT32, unsigned, 0.45)

        except:
            pass
        return None

    def _score_int64(self, data: bytes) -> Optional[Tuple[InferredType, int, float]]:
        """Score likelihood that data is a 64-bit integer."""
        try:
            value = struct.unpack('<q', data)[0]

            # Only suggest int64 if it doesn't look like a pointer
            if not (self.POINTER_RANGE[0] <= value <= self.POINTER_RANGE[1]):
                if -1000000000 <= value <= 1000000000:
                    return (InferredType.INT64, value, 0.35)

        except:
            pass
        return None

    def _score_int16(self, data: bytes) -> Optional[Tuple[InferredType, int, float]]:
        """Score likelihood that data is a 16-bit integer."""
        try:
            value = struct.unpack('<h', data)[0]
            if -32768 <= value <= 32767:
                return (InferredType.INT16, value, 0.4)
        except:
            pass
        return None

    def _score_int8(self, data: bytes) -> Optional[Tuple[InferredType, int, float]]:
        """Score likelihood that data is an 8-bit integer."""
        try:
            value = struct.unpack('<b', data)[0]
            return (InferredType.INT8, value, 0.3)
        except:
            pass
        return None

    def _score_bool(self, data: bytes) -> Optional[Tuple[InferredType, bool, float]]:
        """Score likelihood that data is a boolean."""
        try:
            value = struct.unpack('<I', data)[0]
            if value == 0:
                return (InferredType.BOOL, False, 0.5)
            elif value == 1:
                return (InferredType.BOOL, True, 0.6)
        except:
            pass
        return None

    def _get_type_size(self, inferred_type: InferredType, value: Any) -> int:
        """Get the size in bytes for an inferred type."""
        sizes = {
            InferredType.UNKNOWN: 4,
            InferredType.INT8: 1,
            InferredType.UINT8: 1,
            InferredType.INT16: 2,
            InferredType.UINT16: 2,
            InferredType.INT32: 4,
            InferredType.UINT32: 4,
            InferredType.INT64: 8,
            InferredType.UINT64: 8,
            InferredType.FLOAT32: 4,
            InferredType.FLOAT64: 8,
            InferredType.POINTER: 8,
            InferredType.BOOL: 4,
            InferredType.PADDING: 4,
            InferredType.STRUCT: 0,
        }

        if inferred_type == InferredType.STRING and isinstance(value, str):
            return len(value) + 1  # Include null terminator

        if inferred_type == InferredType.WSTRING and isinstance(value, str):
            return (len(value) + 1) * 2  # UTF-16 with null terminator

        return sizes.get(inferred_type, 4)

    # =========================================================================
    # High-level Analysis
    # =========================================================================

    def analyze_region(self, data: bytes, context: str = "") -> Dict[str, Any]:
        """Perform comprehensive analysis on a memory region.

        Args:
            data: Raw bytes to analyze
            context: Optional context string for logging

        Returns:
            Dictionary with analysis results
        """
        result = {
            'size': len(data),
            'context': context,
            'is_all_zeros': self._is_padding(data),
            'inferences': [],
            'summary': {},
        }

        if result['is_all_zeros']:
            result['summary']['type'] = 'padding'
            return result

        # Analyze the data
        inferences = self.infer_sequence(data)
        result['inferences'] = [
            {
                'offset': inf.offset,
                'type': inf.inferred_type.value,
                'value': inf.value,
                'confidence': inf.confidence,
                'size': inf.size,
            }
            for inf in inferences
        ]

        # Summarize type distribution
        type_counts = {}
        for inf in inferences:
            t = inf.inferred_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        result['summary']['type_distribution'] = type_counts

        # Identify if region looks like a struct
        if len(inferences) > 3:
            unique_types = len(set(inf.inferred_type for inf in inferences))
            if unique_types > 2:
                result['summary']['likely_struct'] = True

        return result
