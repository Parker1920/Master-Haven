"""Detail panel for displaying selected node information.

Shows formatted field view and hex dump for selected tree nodes.
"""

import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QPushButton, QFrame, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..data.tree_node import TreeNode, NodeType
from .hex_viewer import HexViewerPanel

logger = logging.getLogger(__name__)


class FormattedView(QWidget):
    """Widget showing formatted struct/field information."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Header info section
        self._header = QFrame()
        self._header.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QGridLayout(self._header)
        header_layout.setContentsMargins(8, 8, 8, 8)

        # Type
        header_layout.addWidget(QLabel("Type:"), 0, 0)
        self._type_label = QLabel("N/A")
        self._type_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(self._type_label, 0, 1)

        # Address
        header_layout.addWidget(QLabel("Address:"), 1, 0)
        self._addr_label = QLabel("N/A")
        self._addr_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        header_layout.addWidget(self._addr_label, 1, 1)

        # Size
        header_layout.addWidget(QLabel("Size:"), 2, 0)
        self._size_label = QLabel("N/A")
        header_layout.addWidget(self._size_label, 2, 1)

        # Offset (for fields)
        header_layout.addWidget(QLabel("Offset:"), 3, 0)
        self._offset_label = QLabel("N/A")
        header_layout.addWidget(self._offset_label, 3, 1)

        header_layout.setColumnStretch(1, 1)
        layout.addWidget(self._header)

        # Fields table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Field", "Value", "Offset", "Type"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)

        layout.addWidget(self._table)

    def set_node(self, node: TreeNode):
        """Display information for a tree node.

        Args:
            node: The node to display
        """
        # Update header
        self._type_label.setText(node.struct_type or node.node_type.name)
        self._addr_label.setText(node.address_hex if node.address else "N/A")
        self._size_label.setText(f"{node.size} bytes" if node.size else "N/A")
        self._offset_label.setText(f"0x{node.offset:X}" if node.offset else "N/A")

        # Update table with children (fields)
        self._table.setRowCount(0)

        if node.children:
            self._table.setRowCount(len(node.children))

            for i, child in enumerate(node.children):
                # Field name
                name_item = QTableWidgetItem(child.name)
                name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(i, 0, name_item)

                # Value
                value = child.formatted_value or str(child.value) if child.value is not None else ""
                value_item = QTableWidgetItem(value)
                value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(i, 1, value_item)

                # Offset
                offset_str = f"0x{child.offset:X}" if child.offset else ""
                offset_item = QTableWidgetItem(offset_str)
                offset_item.setFlags(offset_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(i, 2, offset_item)

                # Type
                type_item = QTableWidgetItem(child.struct_type or "")
                type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(i, 3, type_item)

        # If this is a simple value node, show it in a single row
        elif node.value is not None:
            self._table.setRowCount(1)

            name_item = QTableWidgetItem(node.name)
            self._table.setItem(0, 0, name_item)

            value_item = QTableWidgetItem(node.formatted_value or str(node.value))
            self._table.setItem(0, 1, value_item)

            offset_item = QTableWidgetItem(f"0x{node.offset:X}" if node.offset else "")
            self._table.setItem(0, 2, offset_item)

            type_item = QTableWidgetItem(node.struct_type or "")
            self._table.setItem(0, 3, type_item)

    def clear(self):
        """Clear the display."""
        self._type_label.setText("N/A")
        self._addr_label.setText("N/A")
        self._size_label.setText("N/A")
        self._offset_label.setText("N/A")
        self._table.setRowCount(0)


class DetailPanel(QWidget):
    """Panel showing details for the selected tree node.

    Contains tabs for formatted view and hex dump.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._current_node: Optional[TreeNode] = None
        self._memory_reader = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title bar
        title_bar = QHBoxLayout()
        self._title = QLabel("Select an item")
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self._title.setFont(font)
        title_bar.addWidget(self._title)

        title_bar.addStretch()

        # Copy button
        self._copy_btn = QPushButton("Copy Path")
        self._copy_btn.clicked.connect(self._on_copy_path)
        title_bar.addWidget(self._copy_btn)

        layout.addLayout(title_bar)

        # Tab widget
        self._tabs = QTabWidget()

        # Formatted view tab
        self._formatted = FormattedView()
        self._tabs.addTab(self._formatted, "Formatted")

        # Hex view tab
        self._hex_panel = HexViewerPanel()
        self._tabs.addTab(self._hex_panel, "Raw Hex")

        layout.addWidget(self._tabs)

    def set_memory_reader(self, reader):
        """Set the memory reader for hex view.

        Args:
            reader: MemoryReader instance
        """
        self._memory_reader = reader

    def set_node(self, node: TreeNode):
        """Display information for a tree node.

        Args:
            node: The node to display
        """
        self._current_node = node

        # Update title
        self._title.setText(node.display_text)

        # Update formatted view
        self._formatted.set_node(node)

        # Update hex view if we have address and reader
        if node.address and self._memory_reader:
            size = node.size if node.size > 0 else 256  # Default to 256 bytes
            size = min(size, 4096)  # Limit to 4KB

            data = self._memory_reader.read_bytes(node.address, size)
            if data:
                self._hex_panel.set_data(data, node.address)
            else:
                self._hex_panel.clear()
        else:
            self._hex_panel.clear()

    def clear(self):
        """Clear the display."""
        self._current_node = None
        self._title.setText("Select an item")
        self._formatted.clear()
        self._hex_panel.clear()

    def _on_copy_path(self):
        """Copy the current node path to clipboard."""
        if self._current_node:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self._current_node.path)

    def get_current_node(self) -> Optional[TreeNode]:
        """Get the currently displayed node."""
        return self._current_node
