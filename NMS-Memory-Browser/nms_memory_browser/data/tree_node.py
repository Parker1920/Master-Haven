"""Tree node model for hierarchical data display.

Provides the data model for the tree browser UI component.
"""

from enum import Enum, auto
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field


class NodeType(Enum):
    """Types of nodes in the tree hierarchy."""
    ROOT = auto()
    CATEGORY = auto()      # Top-level category (Player, System, Multiplayer)
    STRUCT = auto()        # A struct type
    FIELD = auto()         # A field within a struct
    ARRAY = auto()         # An array container
    ARRAY_ELEMENT = auto() # An element in an array
    UNKNOWN_REGION = auto() # Unknown memory region
    VALUE = auto()         # A simple value (leaf node)


@dataclass
class TreeNode:
    """A node in the memory browser tree.

    Represents a hierarchical item that can be displayed
    in the tree browser and selected to show details.
    """
    # Display properties
    name: str
    node_type: NodeType
    display_text: str = ""
    icon: str = ""

    # Data properties
    struct_type: str = ""
    address: int = 0
    size: int = 0
    value: Any = None
    formatted_value: str = ""
    offset: int = 0  # Offset within parent struct

    # Hierarchy
    parent: Optional['TreeNode'] = None
    children: List['TreeNode'] = field(default_factory=list)

    # State
    expanded: bool = False
    loaded: bool = False  # For lazy loading

    # Loader function for lazy loading children
    _loader: Optional[Callable[['TreeNode'], List['TreeNode']]] = field(
        default=None, repr=False
    )

    def __post_init__(self):
        if not self.display_text:
            self.display_text = self.name

    @property
    def has_children(self) -> bool:
        """Check if node has or can have children."""
        if self.children:
            return True
        if self._loader is not None and not self.loaded:
            return True
        return self.node_type in (
            NodeType.ROOT, NodeType.CATEGORY, NodeType.STRUCT,
            NodeType.ARRAY, NodeType.ARRAY_ELEMENT
        )

    @property
    def address_hex(self) -> str:
        """Get address as hex string."""
        if self.address:
            return f"0x{self.address:X}"
        return ""

    @property
    def path(self) -> str:
        """Get full path from root to this node."""
        parts = []
        node = self
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return '/'.join(reversed(parts))

    def add_child(self, child: 'TreeNode') -> 'TreeNode':
        """Add a child node.

        Args:
            child: Node to add

        Returns:
            The added child node
        """
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child: 'TreeNode') -> bool:
        """Remove a child node.

        Args:
            child: Node to remove

        Returns:
            True if removed
        """
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            return True
        return False

    def clear_children(self):
        """Remove all children."""
        for child in self.children:
            child.parent = None
        self.children.clear()
        self.loaded = False

    def load_children(self) -> List['TreeNode']:
        """Load children using the loader function.

        Returns:
            List of loaded children
        """
        if self._loader is not None and not self.loaded:
            new_children = self._loader(self)
            for child in new_children:
                child.parent = self
            self.children.extend(new_children)
            self.loaded = True
        return self.children

    def find_child(self, name: str) -> Optional['TreeNode']:
        """Find a child by name.

        Args:
            name: Child name to find

        Returns:
            Child node or None
        """
        for child in self.children:
            if child.name == name:
                return child
        return None

    def find_by_path(self, path: str) -> Optional['TreeNode']:
        """Find a node by path.

        Args:
            path: Slash-separated path

        Returns:
            Node at path or None
        """
        parts = path.strip('/').split('/')
        node = self

        for part in parts:
            if not part:
                continue
            if node.name == part:
                continue
            child = node.find_child(part)
            if child is None:
                return None
            node = child

        return node

    def get_root(self) -> 'TreeNode':
        """Get the root node of this tree."""
        node = self
        while node.parent is not None:
            node = node.parent
        return node

    def get_depth(self) -> int:
        """Get depth of this node from root."""
        depth = 0
        node = self.parent
        while node is not None:
            depth += 1
            node = node.parent
        return depth

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary."""
        return {
            'name': self.name,
            'type': self.node_type.name,
            'display_text': self.display_text,
            'struct_type': self.struct_type,
            'address': self.address_hex,
            'size': self.size,
            'value': self.formatted_value or str(self.value) if self.value is not None else None,
            'offset': f"0x{self.offset:X}" if self.offset else None,
            'children_count': len(self.children),
        }


# =========================================================================
# Factory Functions
# =========================================================================

def create_root_node() -> TreeNode:
    """Create the root node of the tree."""
    return TreeNode(
        name="NMS Memory",
        node_type=NodeType.ROOT,
        display_text="No Man's Sky Memory",
        icon="memory",
    )


def create_category_node(name: str, description: str = "") -> TreeNode:
    """Create a category node.

    Args:
        name: Category name
        description: Optional description
    """
    icons = {
        'Player': 'person',
        'Solar System': 'star',
        'Multiplayer': 'people',
        'Simulation': 'cpu',
        'Unknown Structures': 'question',
    }

    return TreeNode(
        name=name,
        node_type=NodeType.CATEGORY,
        display_text=description or name,
        icon=icons.get(name, 'folder'),
    )


def create_struct_node(
    name: str,
    struct_type: str,
    address: int,
    size: int = 0
) -> TreeNode:
    """Create a struct node.

    Args:
        name: Display name
        struct_type: Type name
        address: Memory address
        size: Struct size
    """
    return TreeNode(
        name=name,
        node_type=NodeType.STRUCT,
        display_text=f"{name} ({struct_type})",
        struct_type=struct_type,
        address=address,
        size=size,
        icon='struct',
    )


def create_field_node(
    name: str,
    value: Any,
    formatted_value: str,
    offset: int,
    size: int,
    type_name: str = ""
) -> TreeNode:
    """Create a field node.

    Args:
        name: Field name
        value: Raw value
        formatted_value: Display value
        offset: Offset in parent struct
        size: Field size
        type_name: Type name
    """
    return TreeNode(
        name=name,
        node_type=NodeType.FIELD,
        display_text=f"{name}: {formatted_value}",
        value=value,
        formatted_value=formatted_value,
        offset=offset,
        size=size,
        struct_type=type_name,
        icon='field',
    )


def create_array_node(
    name: str,
    element_type: str,
    address: int,
    count: int
) -> TreeNode:
    """Create an array container node.

    Args:
        name: Array name
        element_type: Type of elements
        address: Base address
        count: Number of elements
    """
    return TreeNode(
        name=name,
        node_type=NodeType.ARRAY,
        display_text=f"{name}[{count}]",
        struct_type=element_type,
        address=address,
        size=count,
        icon='array',
    )


def create_unknown_region_node(
    address: int,
    size: int,
    context: str = ""
) -> TreeNode:
    """Create an unknown region node.

    Args:
        address: Memory address
        size: Region size
        context: Optional context description
    """
    display = context if context else f"Region at 0x{address:X}"
    return TreeNode(
        name=f"0x{address:X}",
        node_type=NodeType.UNKNOWN_REGION,
        display_text=f"{display} ({size} bytes)",
        address=address,
        size=size,
        icon='unknown',
    )
