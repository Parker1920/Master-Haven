"""Detail panel for displaying selected node information.

Shows formatted field view and hex dump for selected tree nodes.
Enhanced with address calculation for child nodes and better value formatting.
Includes live value reading with auto-refresh capability.
"""

import struct
import logging
from typing import Optional, Dict, Any, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QPushButton, QFrame, QScrollArea, QGridLayout, QCheckBox,
    QSpinBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from ..data.tree_node import TreeNode, NodeType
from .hex_viewer import HexViewerPanel

logger = logging.getLogger(__name__)


def read_live_value(memory_reader, address: int, type_name: str, size: int) -> Tuple[Any, str]:
    """Read a live value from memory at the given address.

    Args:
        memory_reader: MemoryReader instance
        address: Memory address to read from
        type_name: The type name to interpret as
        size: Size in bytes to read

    Returns:
        Tuple of (raw_value, formatted_string)
    """
    if not memory_reader or not address or address == 0:
        return None, "N/A"

    try:
        # Read the bytes
        data = memory_reader.read_bytes(address, max(size, 8))
        if not data:
            return None, "Read failed"

        type_lower = type_name.lower() if type_name else ""

        # Boolean types
        if type_lower in ('bool', 'boolean') or size == 1 and 'bool' in type_lower:
            val = data[0]
            return val, "True" if val else "False"

        # Integer types
        if size == 1:
            val = struct.unpack('b', data[:1])[0]
            return val, f"{val} (0x{data[0]:02X})"
        elif size == 2:
            val = struct.unpack('<h', data[:2])[0]
            uval = struct.unpack('<H', data[:2])[0]
            return val, f"{val} (0x{uval:04X})"
        elif size == 4:
            # Check if float
            if 'float' in type_lower or type_lower == 'f32':
                fval = struct.unpack('<f', data[:4])[0]
                return fval, f"{fval:.6g}"
            else:
                val = struct.unpack('<i', data[:4])[0]
                uval = struct.unpack('<I', data[:4])[0]
                return val, f"{val} (0x{uval:08X})"
        elif size == 8:
            # Check if double
            if 'double' in type_lower or type_lower == 'f64':
                dval = struct.unpack('<d', data[:8])[0]
                return dval, f"{dval:.10g}"
            # Check if pointer
            elif 'ptr' in type_lower or type_lower.startswith('p') or '*' in type_name:
                ptr = struct.unpack('<Q', data[:8])[0]
                if ptr == 0:
                    return ptr, "NULL"
                elif 0x10000 <= ptr <= 0x7FFFFFFFFFFF:
                    return ptr, f"0x{ptr:X} (valid)"
                else:
                    return ptr, f"0x{ptr:X}"
            else:
                val = struct.unpack('<q', data[:8])[0]
                uval = struct.unpack('<Q', data[:8])[0]
                return val, f"{val} (0x{uval:016X})"

        # Default: show as hex bytes
        hex_str = " ".join(f"{b:02X}" for b in data[:min(size, 16)])
        return data[:size], hex_str

    except Exception as e:
        logger.debug(f"Failed to read live value at 0x{address:X}: {e}")
        return None, f"Error: {str(e)[:20]}"


# Common NMS enum mappings for human-readable display
NMS_ENUM_MAPPINGS = {
    # Biome types
    'eBiome': {
        0: 'Lush', 1: 'Toxic', 2: 'Scorched', 3: 'Radioactive', 4: 'Frozen',
        5: 'Barren', 6: 'Dead', 7: 'Weird', 8: 'Red', 9: 'Green', 10: 'Blue',
    },
    # Weather
    'eWeather': {
        0: 'Clear', 1: 'Dust', 2: 'Humid', 3: 'Snow', 4: 'Toxic',
        5: 'Scorched', 6: 'Radioactive', 7: 'RedWeather', 8: 'GreenWeather',
    },
    # Life levels
    'eLifeLevel': {0: 'Dead', 1: 'Low', 2: 'Mid', 3: 'Full'},
    # Sentinel levels
    'eSentinelLevel': {0: 'Low', 1: 'Default', 2: 'High', 3: 'Aggressive'},
    # Galaxy types
    'eGalaxyType': {0: 'Euclid', 1: 'Hilbert', 2: 'Calypso', 3: 'Hesperius'},
    # Boolean-like
    'bool': {0: 'False', 1: 'True'},
}


def format_value_for_display(value: Any, type_name: str = "", field_name: str = "") -> str:
    """Format a value for human-readable display.

    Args:
        value: The raw value
        type_name: The type name (for enum lookup)
        field_name: The field name (for context-based formatting)

    Returns:
        Human-readable string representation
    """
    if value is None:
        return "N/A"

    # Check for enum mapping
    if type_name in NMS_ENUM_MAPPINGS:
        try:
            int_val = int(value)
            if int_val in NMS_ENUM_MAPPINGS[type_name]:
                return f"{NMS_ENUM_MAPPINGS[type_name][int_val]} ({int_val})"
        except (ValueError, TypeError):
            pass

    # Boolean fields
    if type_name.lower() in ('bool', 'boolean') or field_name.lower().startswith('mb'):
        try:
            return "True" if bool(value) else "False"
        except:
            pass

    # Pointer fields (64-bit addresses)
    if type_name.lower() in ('pointer', 'ptr') or field_name.lower().startswith('mp'):
        try:
            addr = int(value)
            if addr == 0:
                return "NULL"
            elif 0x10000 <= addr <= 0x7FFFFFFFFFFF:
                return f"0x{addr:X} (valid ptr)"
            else:
                return f"0x{addr:X}"
        except:
            pass

    # Integer with hex display
    if isinstance(value, int):
        if abs(value) > 1000000:  # Large numbers show hex too
            return f"{value} (0x{value:X})"
        elif value < 0:
            return f"{value} (0x{value & 0xFFFFFFFF:X})"
        else:
            return str(value)

    # Float formatting
    if isinstance(value, float):
        if abs(value) < 0.0001 and value != 0:
            return f"{value:.6e}"
        elif abs(value) > 1000000:
            return f"{value:.2e}"
        else:
            return f"{value:.4f}".rstrip('0').rstrip('.')

    return str(value)


def get_effective_address(node: TreeNode) -> int:
    """Calculate the effective memory address for a node.

    For child nodes, calculates parent.address + offset.
    Walks up the tree until it finds a node with an address.

    Args:
        node: The tree node

    Returns:
        Calculated memory address, or 0 if not calculable
    """
    # If node has direct address, use it
    if node.address:
        return node.address

    # If node has offset and parent has address (or calculable address)
    if node.offset is not None and node.parent:
        parent_addr = get_effective_address(node.parent)
        if parent_addr:
            return parent_addr + node.offset

    return 0


class FormattedView(QWidget):
    """Widget showing formatted struct/field information with live value reading."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._memory_reader = None
        self._current_node: Optional[TreeNode] = None
        self._auto_refresh = False
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_auto_refresh)
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Refresh controls bar
        refresh_bar = QHBoxLayout()

        self._refresh_btn = QPushButton("⟳ Refresh Values")
        self._refresh_btn.setToolTip("Read live values from game memory")
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        self._refresh_btn.setStyleSheet("font-weight: bold;")
        refresh_bar.addWidget(self._refresh_btn)

        self._auto_refresh_cb = QCheckBox("Auto-refresh")
        self._auto_refresh_cb.setToolTip("Automatically refresh values at interval")
        self._auto_refresh_cb.stateChanged.connect(self._on_auto_refresh_changed)
        refresh_bar.addWidget(self._auto_refresh_cb)

        refresh_bar.addWidget(QLabel("Interval:"))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(100, 5000)
        self._interval_spin.setValue(500)
        self._interval_spin.setSuffix(" ms")
        self._interval_spin.setToolTip("Refresh interval in milliseconds")
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        refresh_bar.addWidget(self._interval_spin)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #888; font-style: italic;")
        refresh_bar.addWidget(self._status_label)

        refresh_bar.addStretch()
        layout.addLayout(refresh_bar)

        # Header info section
        self._header = QFrame()
        self._header.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QGridLayout(self._header)
        header_layout.setContentsMargins(8, 8, 8, 8)

        # Type
        header_layout.addWidget(QLabel("Type:"), 0, 0)
        self._type_label = QLabel("N/A")
        self._type_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._type_label.setStyleSheet("font-weight: bold; color: #569CD6;")
        header_layout.addWidget(self._type_label, 0, 1)

        # Address (now shows calculated address)
        header_layout.addWidget(QLabel("Address:"), 1, 0)
        self._addr_label = QLabel("N/A")
        self._addr_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._addr_label.setStyleSheet("font-family: Consolas, monospace; color: #9CDCFE;")
        header_layout.addWidget(self._addr_label, 1, 1)

        # Size
        header_layout.addWidget(QLabel("Size:"), 2, 0)
        self._size_label = QLabel("N/A")
        self._size_label.setStyleSheet("font-family: Consolas, monospace;")
        header_layout.addWidget(self._size_label, 2, 1)

        # Offset (for fields)
        header_layout.addWidget(QLabel("Offset:"), 3, 0)
        self._offset_label = QLabel("N/A")
        self._offset_label.setStyleSheet("font-family: Consolas, monospace;")
        header_layout.addWidget(self._offset_label, 3, 1)

        header_layout.setColumnStretch(1, 1)
        layout.addWidget(self._header)

        # Fields table
        self._table = QTableWidget()
        self._table.setColumnCount(5)  # Added Address column
        self._table.setHorizontalHeaderLabels(["Field", "Value", "Address", "Offset", "Type"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)

        # Better styling
        self._table.setStyleSheet("""
            QTableWidget {
                font-family: Consolas, monospace;
                font-size: 10pt;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #d4d4d4;
                padding: 4px;
                font-weight: bold;
            }
        """)

        layout.addWidget(self._table)

    def set_memory_reader(self, reader):
        """Set the memory reader for live value reading.

        Args:
            reader: MemoryReader instance
        """
        self._memory_reader = reader

    def _on_refresh_clicked(self):
        """Handle manual refresh button click."""
        self._refresh_live_values()

    def _on_auto_refresh_changed(self, state):
        """Handle auto-refresh checkbox change."""
        self._auto_refresh = bool(state)
        if self._auto_refresh:
            self._refresh_timer.start(self._interval_spin.value())
            self._status_label.setText("Auto-refreshing...")
        else:
            self._refresh_timer.stop()
            self._status_label.setText("")

    def _on_interval_changed(self, value):
        """Handle interval spinbox change."""
        if self._auto_refresh:
            self._refresh_timer.setInterval(value)

    def _on_auto_refresh(self):
        """Handle auto-refresh timer tick."""
        self._refresh_live_values()

    def _refresh_live_values(self):
        """Refresh all displayed values by reading from memory."""
        if not self._current_node or not self._memory_reader:
            self._status_label.setText("No memory reader")
            return

        effective_addr = get_effective_address(self._current_node)
        if not effective_addr:
            self._status_label.setText("No address")
            return

        # Update each row in the table with live values
        updated = 0
        for row in range(self._table.rowCount()):
            addr_item = self._table.item(row, 2)  # Address column
            type_item = self._table.item(row, 4)  # Type column

            if addr_item and addr_item.text():
                try:
                    # Parse the address
                    addr_text = addr_item.text().replace("0x", "").replace("(calculated)", "").strip()
                    addr = int(addr_text, 16)

                    # Determine size from type
                    type_name = type_item.text() if type_item else ""
                    size = self._get_type_size(type_name)

                    # Read live value
                    raw_val, formatted = read_live_value(self._memory_reader, addr, type_name, size)

                    # Apply enum mapping if available
                    if type_name in NMS_ENUM_MAPPINGS and raw_val is not None:
                        try:
                            int_val = int(raw_val)
                            if int_val in NMS_ENUM_MAPPINGS[type_name]:
                                formatted = f"{NMS_ENUM_MAPPINGS[type_name][int_val]} ({int_val})"
                        except:
                            pass

                    # Update value cell
                    value_item = self._table.item(row, 1)
                    if value_item:
                        value_item.setText(formatted)
                        # Highlight changed values
                        value_item.setForeground(QColor("#4FC3F7"))
                        updated += 1
                except Exception as e:
                    logger.debug(f"Error refreshing row {row}: {e}")

        self._status_label.setText(f"Updated {updated} values")

    def _get_type_size(self, type_name: str) -> int:
        """Get the size in bytes for a type name."""
        type_lower = type_name.lower() if type_name else ""

        # Exact size matches
        if type_lower in ('bool', 'boolean', 'char', 'int8', 'uint8', 'byte'):
            return 1
        elif type_lower in ('short', 'int16', 'uint16', 'word'):
            return 2
        elif type_lower in ('int', 'int32', 'uint32', 'dword', 'float', 'f32'):
            return 4
        elif type_lower in ('long', 'int64', 'uint64', 'qword', 'double', 'f64', 'pointer', 'ptr'):
            return 8

        # Pattern matches
        if 'float' in type_lower:
            return 4
        if 'double' in type_lower:
            return 8
        if 'ptr' in type_lower or '*' in type_name:
            return 8
        if '64' in type_lower:
            return 8
        if '32' in type_lower:
            return 4
        if '16' in type_lower:
            return 2
        if '8' in type_lower:
            return 1

        # Default to 4 bytes
        return 4

    def set_node(self, node: TreeNode):
        """Display information for a tree node.

        Args:
            node: The node to display
        """
        self._current_node = node

        # Calculate effective address
        effective_addr = get_effective_address(node)

        # Update header
        self._type_label.setText(node.struct_type or node.node_type.name)

        if effective_addr:
            addr_text = f"0x{effective_addr:X}"
            if not node.address and node.offset is not None:
                addr_text += " (calculated)"
            self._addr_label.setText(addr_text)
        else:
            self._addr_label.setText("N/A")

        self._size_label.setText(
            f"{node.size} bytes (0x{node.size:X})" if node.size is not None and node.size > 0 else "N/A"
        )
        self._offset_label.setText(
            f"0x{node.offset:X} ({node.offset})" if node.offset is not None else "N/A"
        )

        # Update table with children (fields)
        self._table.setRowCount(0)

        if node.children:
            # Filter out internal nodes like "Details" that are just for tree expansion
            display_children = [c for c in node.children if not c.name.endswith('_details')]

            # If all children were filtered out but node has its own value, show the node's value
            if not display_children and (node.value is not None or node.formatted_value):
                self._show_single_node_row(node, effective_addr)
            elif display_children:
                self._table.setRowCount(len(display_children))

                # Calculate parent address for children
                parent_addr = effective_addr

                for i, child in enumerate(display_children):
                    # Field name
                    name_item = QTableWidgetItem(child.name)
                    name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self._table.setItem(i, 0, name_item)

                    # Value - format for readability
                    value = ""
                    if child.formatted_value:
                        value = child.formatted_value
                    elif child.value is not None:
                        value = format_value_for_display(
                            child.value,
                            child.struct_type or "",
                            child.name
                        )
                    value_item = QTableWidgetItem(value)
                    value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self._table.setItem(i, 1, value_item)

                    # Address - calculate from parent + offset
                    child_addr = ""
                    if parent_addr and child.offset is not None:
                        calc_addr = parent_addr + child.offset
                        child_addr = f"0x{calc_addr:X}"
                    elif child.address:
                        child_addr = f"0x{child.address:X}"
                    addr_item = QTableWidgetItem(child_addr)
                    addr_item.setFlags(addr_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    addr_item.setForeground(QColor("#9CDCFE"))
                    self._table.setItem(i, 2, addr_item)

                    # Offset - handle zero offset properly
                    offset_str = f"0x{child.offset:X}" if child.offset is not None else ""
                    offset_item = QTableWidgetItem(offset_str)
                    offset_item.setFlags(offset_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self._table.setItem(i, 3, offset_item)

                    # Type
                    type_item = QTableWidgetItem(child.struct_type or "")
                    type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    type_item.setForeground(QColor("#4EC9B0"))
                    self._table.setItem(i, 4, type_item)

        # If this is a simple value node (no children), show it in a single row
        elif node.value is not None or node.formatted_value:
            self._show_single_node_row(node, effective_addr)

    def _show_single_node_row(self, node: TreeNode, effective_addr: int = 0):
        """Display a single node's value in the table.

        Args:
            node: The node to display
            effective_addr: Calculated memory address
        """
        self._table.setRowCount(1)

        name_item = QTableWidgetItem(node.name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(0, 0, name_item)

        # Format value for readability
        if node.formatted_value:
            value = node.formatted_value
        elif node.value is not None:
            value = format_value_for_display(node.value, node.struct_type or "", node.name)
        else:
            value = ""
        value_item = QTableWidgetItem(value)
        value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(0, 1, value_item)

        # Address
        addr_str = f"0x{effective_addr:X}" if effective_addr else ""
        addr_item = QTableWidgetItem(addr_str)
        addr_item.setFlags(addr_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        addr_item.setForeground(QColor("#9CDCFE"))
        self._table.setItem(0, 2, addr_item)

        offset_str = f"0x{node.offset:X}" if node.offset is not None else ""
        offset_item = QTableWidgetItem(offset_str)
        offset_item.setFlags(offset_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(0, 3, offset_item)

        type_item = QTableWidgetItem(node.struct_type or "")
        type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        type_item.setForeground(QColor("#4EC9B0"))
        self._table.setItem(0, 4, type_item)

    def clear(self):
        """Clear the display."""
        self._current_node = None
        self._type_label.setText("N/A")
        self._addr_label.setText("N/A")
        self._size_label.setText("N/A")
        self._offset_label.setText("N/A")
        self._table.setRowCount(0)
        self._status_label.setText("")

        # Stop auto-refresh
        if self._auto_refresh:
            self._refresh_timer.stop()
            self._auto_refresh_cb.setChecked(False)
            self._auto_refresh = False


class DetailPanel(QWidget):
    """Panel showing details for the selected tree node.

    Contains tabs for formatted view and hex dump.
    Enhanced with address calculation for child nodes.
    Supports live value reading with auto-refresh.
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
        """Set the memory reader for hex view and live value reading.

        Args:
            reader: MemoryReader instance
        """
        self._memory_reader = reader
        # Also set on formatted view for live value reading
        self._formatted.set_memory_reader(reader)
        # And on hex panel for refresh
        self._hex_panel.set_memory_reader(reader)

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

        # Calculate effective address (walks up tree if needed)
        effective_addr = get_effective_address(node)

        # Update hex view if we have address and reader
        if effective_addr and self._memory_reader:
            # Determine size - use node size or default
            if node.size and node.size > 0:
                size = node.size
            elif node.struct_type:
                # Try to get size from struct type if available
                size = 256  # Default
            else:
                size = 256  # Default to 256 bytes

            size = min(size, 4096)  # Limit to 4KB

            data = self._memory_reader.read_bytes(effective_addr, size)
            if data:
                # Pass size for refresh capability
                self._hex_panel.set_data(data, effective_addr, size)
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
