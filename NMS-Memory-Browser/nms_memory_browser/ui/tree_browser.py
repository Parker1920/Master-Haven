"""Tree browser widget for hierarchical memory navigation.

Provides a tree view for navigating through game memory structures.
"""

import logging
from typing import Optional, List, Any, Callable

from PyQt6.QtWidgets import (
    QTreeView, QWidget, QVBoxLayout, QLineEdit,
    QAbstractItemView, QHeaderView
)
from PyQt6.QtCore import (
    Qt, QAbstractItemModel, QModelIndex, pyqtSignal,
    QSortFilterProxyModel
)
from PyQt6.QtGui import QFont

from ..data.tree_node import TreeNode, NodeType

logger = logging.getLogger(__name__)


class TreeNodeModel(QAbstractItemModel):
    """Qt model for TreeNode hierarchy."""

    def __init__(self, root: TreeNode, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._root = root

    @property
    def root(self) -> TreeNode:
        return self._root

    def set_root(self, root: TreeNode):
        """Replace the root node."""
        self.beginResetModel()
        self._root = root
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            return len(self._root.children)

        node = parent.internalPointer()
        if node is None:
            return 0

        # Lazy load children if needed
        if node._loader and not node.loaded:
            node.load_children()

        return len(node.children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 3  # Name, Value, Address

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        node = index.internalPointer()
        if node is None:
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            if col == 0:
                return node.display_text
            elif col == 1:
                return node.formatted_value or ""
            elif col == 2:
                return node.address_hex if node.address else ""

        elif role == Qt.ItemDataRole.ToolTipRole:
            parts = [f"Type: {node.struct_type}"] if node.struct_type else []
            if node.address:
                parts.append(f"Address: {node.address_hex}")
            if node.size:
                parts.append(f"Size: {node.size} bytes")
            if node.offset:
                parts.append(f"Offset: 0x{node.offset:X}")
            return "\n".join(parts) if parts else None

        elif role == Qt.ItemDataRole.FontRole:
            if node.node_type in (NodeType.CATEGORY, NodeType.ROOT):
                font = QFont()
                font.setBold(True)
                return font

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            headers = ["Name", "Value", "Address"]
            if section < len(headers):
                return headers[section]
        return None

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_node = self._root
        else:
            parent_node = parent.internalPointer()

        if parent_node is None:
            return QModelIndex()

        # Lazy load if needed
        if parent_node._loader and not parent_node.loaded:
            parent_node.load_children()

        if row < len(parent_node.children):
            child = parent_node.children[row]
            return self.createIndex(row, column, child)

        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        node = index.internalPointer()
        if node is None or node.parent is None or node.parent is self._root:
            return QModelIndex()

        parent = node.parent
        grandparent = parent.parent

        if grandparent is None:
            grandparent = self._root

        row = grandparent.children.index(parent) if parent in grandparent.children else 0
        return self.createIndex(row, 0, parent)

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:
        if not parent.isValid():
            return len(self._root.children) > 0

        node = parent.internalPointer()
        if node is None:
            return False

        return node.has_children

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


class TreeFilterProxy(QSortFilterProxyModel):
    """Filter proxy for tree search."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setRecursiveFilteringEnabled(True)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        # Get the source model index
        source_model = self.sourceModel()
        if source_model is None:
            return True

        index = source_model.index(source_row, 0, source_parent)
        if not index.isValid():
            return True

        # Get the display text
        text = source_model.data(index, Qt.ItemDataRole.DisplayRole)
        if text is None:
            text = ""

        # Check if matches filter
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True

        return pattern.lower() in text.lower()


class TreeBrowser(QWidget):
    """Tree browser widget for memory hierarchy navigation."""

    # Signal emitted when a node is selected
    nodeSelected = pyqtSignal(object)  # TreeNode

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._root = TreeNode(
            name="Memory",
            node_type=NodeType.ROOT,
            display_text="No Man's Sky Memory"
        )
        self._model = TreeNodeModel(self._root)
        self._proxy = TreeFilterProxy()
        self._proxy.setSourceModel(self._model)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Search box
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search...")
        self._search.textChanged.connect(self._on_search)
        layout.addWidget(self._search)

        # Tree view
        self._tree = QTreeView()
        self._tree.setModel(self._proxy)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setUniformRowHeights(True)
        self._tree.setAnimated(True)
        self._tree.setExpandsOnDoubleClick(True)

        # Column sizing
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        # Connect selection
        self._tree.selectionModel().currentChanged.connect(self._on_selection_changed)

        layout.addWidget(self._tree)

    def _on_search(self, text: str):
        """Handle search text changes."""
        self._proxy.setFilterFixedString(text)

        # Expand all if searching
        if text:
            self._tree.expandAll()

    def _on_selection_changed(self, current: QModelIndex, previous: QModelIndex):
        """Handle selection changes."""
        if not current.isValid():
            return

        # Get source index through proxy
        source_index = self._proxy.mapToSource(current)
        if not source_index.isValid():
            return

        node = source_index.internalPointer()
        if node is not None:
            self.nodeSelected.emit(node)

    def set_root(self, root: TreeNode):
        """Set the root node of the tree.

        Args:
            root: New root node
        """
        self._root = root
        self._model.set_root(root)

        # Expand top-level items
        for i in range(self._model.rowCount()):
            index = self._model.index(i, 0)
            proxy_index = self._proxy.mapFromSource(index)
            self._tree.expand(proxy_index)

    def add_category(self, category: TreeNode):
        """Add a category to the root.

        Args:
            category: Category node to add
        """
        self._model.beginInsertRows(
            QModelIndex(),
            len(self._root.children),
            len(self._root.children)
        )
        self._root.add_child(category)
        self._model.endInsertRows()

    def refresh(self):
        """Refresh the tree view."""
        self._model.beginResetModel()
        self._model.endResetModel()

    def expand_all(self):
        """Expand all nodes."""
        self._tree.expandAll()

    def collapse_all(self):
        """Collapse all nodes."""
        self._tree.collapseAll()

    def get_selected_node(self) -> Optional[TreeNode]:
        """Get the currently selected node."""
        indexes = self._tree.selectionModel().selectedIndexes()
        if not indexes:
            return None

        source_index = self._proxy.mapToSource(indexes[0])
        if source_index.isValid():
            return source_index.internalPointer()

        return None
