"""Unknown memory region collector.

Scans for and analyzes memory regions that aren't covered by
known struct definitions.
"""

import logging
from typing import Optional, Dict, Any, List

from ..core.memory_reader import MemoryReader
from ..core.struct_mapper import StructMapper
from ..core.struct_registry import StructRegistry
from ..core.type_inference import TypeInferenceEngine, InferredType
from ..core.pointer_scanner import PointerScanner
from ..data.tree_node import (
    TreeNode, NodeType, create_field_node,
    create_category_node, create_unknown_region_node
)
from ..data.snapshot import UnknownRegion

logger = logging.getLogger(__name__)


class UnknownCollector:
    """Collects and analyzes unknown memory regions.

    This collector:
    1. Identifies gaps between known struct fields
    2. Scans regions not covered by known structs
    3. Applies type inference to unknown data
    """

    # Maximum size of region to analyze
    MAX_REGION_SIZE = 4096

    # Minimum gap size to report
    MIN_GAP_SIZE = 8

    def __init__(
        self,
        reader: MemoryReader,
        mapper: StructMapper,
        registry: StructRegistry,
        scanner: PointerScanner
    ):
        """Initialize the unknown collector.

        Args:
            reader: Memory reader instance
            mapper: Struct mapper instance
            registry: Struct registry instance
            scanner: Pointer scanner instance
        """
        self.reader = reader
        self.mapper = mapper
        self.registry = registry
        self.scanner = scanner
        self.inference = TypeInferenceEngine()

    def collect(self) -> Dict[str, Any]:
        """Collect unknown memory regions.

        Returns:
            Dictionary with unknown regions and their analysis
        """
        result = {
            'struct_gaps': [],
            'unmapped_regions': [],
            'total_unknown_bytes': 0,
        }

        # Scan gaps in known structs
        result['struct_gaps'] = self._scan_struct_gaps()

        # Count total unknown bytes
        for gap in result['struct_gaps']:
            result['total_unknown_bytes'] += gap.get('size', 0)

        return result

    def _scan_struct_gaps(self) -> List[Dict[str, Any]]:
        """Scan for gaps in known struct field layouts."""
        gaps = []

        # Scan gaps in major root pointers
        pointers_to_scan = ['player_state', 'solar_system', 'game_state']

        for ptr_name in pointers_to_scan:
            pointer = self.scanner.get_pointer(ptr_name)
            if not pointer or not pointer.valid:
                continue

            struct_info = self.registry.get_struct(pointer.struct_type)
            if not struct_info:
                continue

            # Find gaps between fields
            struct_gaps = self._find_field_gaps(
                pointer.address,
                struct_info,
                f"{ptr_name} ({pointer.struct_type})"
            )
            gaps.extend(struct_gaps)

        return gaps

    def _find_field_gaps(
        self,
        base_addr: int,
        struct_info: Any,
        context: str
    ) -> List[Dict[str, Any]]:
        """Find gaps between struct fields."""
        gaps = []

        if not struct_info.fields:
            return gaps

        # Sort fields by offset
        sorted_fields = sorted(struct_info.fields, key=lambda f: f.offset)

        # Check for gap at start
        if sorted_fields[0].offset > 0:
            gap_size = sorted_fields[0].offset
            if gap_size >= self.MIN_GAP_SIZE:
                gaps.append(self._analyze_gap(
                    base_addr,
                    gap_size,
                    f"{context}: Gap at start (before {sorted_fields[0].name})"
                ))

        # Check gaps between fields
        for i in range(len(sorted_fields) - 1):
            current = sorted_fields[i]
            next_field = sorted_fields[i + 1]

            expected_end = current.offset + current.size
            actual_next = next_field.offset

            if actual_next > expected_end:
                gap_size = actual_next - expected_end
                if gap_size >= self.MIN_GAP_SIZE:
                    gaps.append(self._analyze_gap(
                        base_addr + expected_end,
                        gap_size,
                        f"{context}: Gap between {current.name} and {next_field.name}"
                    ))

        # Check for gap at end (if we know total struct size)
        if struct_info.size > 0 and sorted_fields:
            last = sorted_fields[-1]
            expected_end = last.offset + last.size
            if struct_info.size > expected_end:
                gap_size = struct_info.size - expected_end
                if gap_size >= self.MIN_GAP_SIZE:
                    gaps.append(self._analyze_gap(
                        base_addr + expected_end,
                        min(gap_size, self.MAX_REGION_SIZE),
                        f"{context}: Gap at end (after {last.name})"
                    ))

        return gaps

    def _analyze_gap(self, address: int, size: int, context: str) -> Dict[str, Any]:
        """Analyze a gap in memory."""
        size = min(size, self.MAX_REGION_SIZE)

        result = {
            'address': address,
            'address_hex': f"0x{address:X}",
            'size': size,
            'context': context,
            'inferred_types': [],
            'hex_preview': '',
            'is_all_zeros': False,
        }

        # Read the data
        data = self.reader.read_bytes(address, size)
        if data is None:
            result['error'] = 'Failed to read memory'
            return result

        # Check if all zeros
        if all(b == 0 for b in data):
            result['is_all_zeros'] = True
            result['inferred_types'] = [{'type': 'padding', 'confidence': 0.95}]
            return result

        # Hex preview (first 64 bytes)
        preview_size = min(64, len(data))
        result['hex_preview'] = ' '.join(f'{b:02X}' for b in data[:preview_size])
        if len(data) > preview_size:
            result['hex_preview'] += ' ...'

        # Run type inference
        analysis = self.inference.analyze_region(data, context)
        result['inferred_types'] = analysis.get('inferences', [])[:10]  # Limit to first 10
        result['likely_struct'] = analysis.get('summary', {}).get('likely_struct', False)

        return result

    def analyze_region(self, address: int, size: int) -> Dict[str, Any]:
        """Analyze a specific memory region.

        Args:
            address: Memory address
            size: Size to analyze

        Returns:
            Analysis results
        """
        return self._analyze_gap(address, size, "Manual analysis")

    # =========================================================================
    # Tree Node Generation
    # =========================================================================

    def build_tree_nodes(self) -> TreeNode:
        """Build tree nodes for unknown memory regions.

        Returns:
            Unknown Structures category node with children
        """
        category = create_category_node('Unknown Structures', 'Unmapped Memory Regions')

        # Collect data
        data = self.collect()

        # Add summary node
        summary_node = TreeNode(
            name='Summary',
            node_type=NodeType.STRUCT,
            display_text=f"Total Unknown: {data['total_unknown_bytes']} bytes",
            icon='info',
        )

        summary_node.add_child(create_field_node(
            name='total_gaps',
            value=len(data['struct_gaps']),
            formatted_value=str(len(data['struct_gaps'])),
            offset=0,
            size=0,
        ))

        summary_node.add_child(create_field_node(
            name='total_bytes',
            value=data['total_unknown_bytes'],
            formatted_value=f"{data['total_unknown_bytes']} bytes",
            offset=0,
            size=0,
        ))

        category.add_child(summary_node)

        # Add struct gaps
        gaps_node = TreeNode(
            name='Struct Gaps',
            node_type=NodeType.ARRAY,
            display_text=f"Gaps in Known Structs ({len(data['struct_gaps'])})",
            icon='gap',
        )

        for i, gap in enumerate(data['struct_gaps']):
            gap_node = create_unknown_region_node(
                address=gap['address'],
                size=gap['size'],
                context=gap['context'],
            )

            # Add inferred types as children
            for inf in gap.get('inferred_types', [])[:5]:
                inf_node = create_field_node(
                    name=f"offset_{inf.get('offset', 0)}",
                    value=inf.get('value'),
                    formatted_value=f"{inf.get('type', '?')}: {inf.get('value', '?')} ({inf.get('confidence', 0):.0%})",
                    offset=inf.get('offset', 0),
                    size=inf.get('size', 4),
                    type_name=inf.get('type', 'unknown'),
                )
                gap_node.add_child(inf_node)

            # Add hex preview
            if gap.get('hex_preview'):
                hex_node = TreeNode(
                    name='hex_preview',
                    node_type=NodeType.VALUE,
                    display_text=gap['hex_preview'][:80],
                    value=gap['hex_preview'],
                    icon='hex',
                )
                gap_node.add_child(hex_node)

            gaps_node.add_child(gap_node)

        category.add_child(gaps_node)

        return category

    def to_snapshot_regions(self, data: Dict[str, Any]) -> List[UnknownRegion]:
        """Convert collected data to UnknownRegion objects."""
        regions = []

        for gap in data.get('struct_gaps', []):
            region = UnknownRegion(
                address=gap['address_hex'],
                size=gap['size'],
                context=gap['context'],
                inferred_types=gap.get('inferred_types', []),
                hex_dump=gap.get('hex_preview', ''),
            )
            regions.append(region)

        return regions
