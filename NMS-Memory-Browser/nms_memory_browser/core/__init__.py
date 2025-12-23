"""Core memory access and struct mapping modules."""

from .memory_reader import MemoryReader
from .struct_registry import StructRegistry
from .struct_mapper import StructMapper
from .type_inference import TypeInferenceEngine
from .pointer_scanner import PointerScanner

__all__ = [
    'MemoryReader',
    'StructRegistry',
    'StructMapper',
    'TypeInferenceEngine',
    'PointerScanner',
]
