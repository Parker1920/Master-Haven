"""Hex viewer widget for raw memory display.

Enhanced hex viewer with:
- Color coding for different byte types (null, ASCII, high bytes)
- Value interpretation panel (int8/16/32/64, float, double, pointer, string)
- Click-to-select bytes and see their interpretation
- Improved readability and formatting
"""

import struct
import logging
from typing import Optional, List, Tuple

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLabel, QSpinBox, QPushButton, QComboBox, QFrame,
    QGridLayout, QGroupBox, QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCharFormat, QColor, QTextCursor, QMouseEvent

logger = logging.getLogger(__name__)


class ValueInterpreter(QGroupBox):
    """Panel showing interpretation of selected bytes as various data types."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__("Value Interpretation", parent)
        self._setup_ui()
        self._data: bytes = b''
        self._offset: int = 0

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QGridLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        # Create labels for each interpretation
        self._labels = {}

        interpretations = [
            ('offset', 'Offset:'),
            ('int8', 'Int8:'),
            ('uint8', 'UInt8:'),
            ('int16_le', 'Int16 (LE):'),
            ('uint16_le', 'UInt16 (LE):'),
            ('int32_le', 'Int32 (LE):'),
            ('uint32_le', 'UInt32 (LE):'),
            ('int64_le', 'Int64 (LE):'),
            ('uint64_le', 'UInt64 (LE):'),
            ('float_le', 'Float (LE):'),
            ('double_le', 'Double (LE):'),
            ('pointer', 'Pointer:'),
            ('hex_bytes', 'Hex Bytes:'),
            ('ascii', 'ASCII:'),
            ('utf16', 'UTF-16:'),
        ]

        row = 0
        col = 0
        for key, label_text in interpretations:
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold; color: #888;")
            layout.addWidget(label, row, col * 2)

            value = QLabel("--")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setStyleSheet("font-family: Consolas, monospace;")
            self._labels[key] = value
            layout.addWidget(value, row, col * 2 + 1)

            row += 1
            if row >= 8:
                row = 0
                col += 1

        # Set column stretch
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)

    def set_selection(self, data: bytes, offset: int, base_address: int = 0):
        """Update interpretation for selected bytes.

        Args:
            data: The full data buffer
            offset: Offset within the buffer of selection
            base_address: Base memory address
        """
        self._data = data
        self._offset = offset

        if not data or offset >= len(data):
            self._clear()
            return

        # Get bytes from offset (up to 8 for full interpretation)
        remaining = len(data) - offset
        sel_bytes = data[offset:offset + min(8, remaining)]

        if not sel_bytes:
            self._clear()
            return

        # Offset/Address
        addr = base_address + offset if base_address else offset
        self._labels['offset'].setText(f"0x{addr:X} (offset: 0x{offset:X})")

        # Single byte interpretations
        b0 = sel_bytes[0]
        self._labels['int8'].setText(f"{struct.unpack('b', bytes([b0]))[0]}")
        self._labels['uint8'].setText(f"{b0} (0x{b0:02X})")

        # 2-byte interpretations
        if len(sel_bytes) >= 2:
            self._labels['int16_le'].setText(f"{struct.unpack('<h', sel_bytes[:2])[0]}")
            self._labels['uint16_le'].setText(f"{struct.unpack('<H', sel_bytes[:2])[0]}")
        else:
            self._labels['int16_le'].setText("--")
            self._labels['uint16_le'].setText("--")

        # 4-byte interpretations
        if len(sel_bytes) >= 4:
            i32 = struct.unpack('<i', sel_bytes[:4])[0]
            u32 = struct.unpack('<I', sel_bytes[:4])[0]
            f32 = struct.unpack('<f', sel_bytes[:4])[0]
            self._labels['int32_le'].setText(f"{i32} (0x{u32:08X})")
            self._labels['uint32_le'].setText(f"{u32} (0x{u32:08X})")
            self._labels['float_le'].setText(f"{f32:.6g}")
        else:
            self._labels['int32_le'].setText("--")
            self._labels['uint32_le'].setText("--")
            self._labels['float_le'].setText("--")

        # 8-byte interpretations
        if len(sel_bytes) >= 8:
            i64 = struct.unpack('<q', sel_bytes[:8])[0]
            u64 = struct.unpack('<Q', sel_bytes[:8])[0]
            f64 = struct.unpack('<d', sel_bytes[:8])[0]
            self._labels['int64_le'].setText(f"{i64}")
            self._labels['uint64_le'].setText(f"{u64} (0x{u64:016X})")
            self._labels['double_le'].setText(f"{f64:.10g}")

            # Pointer interpretation (check if valid range)
            if 0x10000 <= u64 <= 0x7FFFFFFFFFFF:
                self._labels['pointer'].setText(f"0x{u64:X} (valid)")
            elif u64 == 0:
                self._labels['pointer'].setText("NULL")
            else:
                self._labels['pointer'].setText(f"0x{u64:X} (invalid?)")
        else:
            self._labels['int64_le'].setText("--")
            self._labels['uint64_le'].setText("--")
            self._labels['double_le'].setText("--")
            self._labels['pointer'].setText("--")

        # Hex bytes (up to 16)
        hex_display = " ".join(f"{b:02X}" for b in sel_bytes[:16])
        if remaining > 16:
            hex_display += " ..."
        self._labels['hex_bytes'].setText(hex_display)

        # ASCII interpretation (read until null or 32 chars)
        ascii_chars = []
        for i in range(min(32, remaining)):
            b = data[offset + i]
            if b == 0:
                break
            if 32 <= b < 127:
                ascii_chars.append(chr(b))
            else:
                ascii_chars.append('.')
        self._labels['ascii'].setText("".join(ascii_chars) if ascii_chars else "(non-printable)")

        # UTF-16 interpretation (read until null or 16 chars)
        try:
            utf16_bytes = data[offset:offset + 64]
            # Find null terminator
            null_pos = len(utf16_bytes)
            for i in range(0, len(utf16_bytes) - 1, 2):
                if utf16_bytes[i] == 0 and utf16_bytes[i + 1] == 0:
                    null_pos = i
                    break
            if null_pos > 0:
                utf16_str = utf16_bytes[:null_pos].decode('utf-16-le', errors='replace')[:32]
                self._labels['utf16'].setText(utf16_str if utf16_str else "(empty)")
            else:
                self._labels['utf16'].setText("(empty)")
        except:
            self._labels['utf16'].setText("(decode error)")

    def _clear(self):
        """Clear all interpretations."""
        for label in self._labels.values():
            label.setText("--")


class EnhancedHexViewer(QWidget):
    """Enhanced hex viewer with color coding and click-to-select."""

    # Signal emitted when user clicks on a byte
    byteSelected = pyqtSignal(int)  # offset within buffer

    # Color scheme
    COLOR_NULL = "#555555"       # Null bytes (0x00)
    COLOR_PRINTABLE = "#9CDCFE"  # Printable ASCII (0x20-0x7E)
    COLOR_WHITESPACE = "#6A9955" # Whitespace (0x09, 0x0A, 0x0D)
    COLOR_HIGH = "#CE9178"       # High bytes (0x80-0xFF)
    COLOR_LOW = "#DCDCAA"        # Low control (0x01-0x1F)
    COLOR_FF = "#F44747"         # 0xFF bytes (often padding/uninitialized)
    COLOR_ADDR = "#569CD6"       # Address column
    COLOR_ASCII = "#D4D4D4"      # ASCII column

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._data: bytes = b''
        self._base_address: int = 0
        self._bytes_per_line: int = 16
        self._selected_offset: int = -1

        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Controls bar
        controls = QHBoxLayout()

        # Address label
        self._addr_label = QLabel("Address: N/A")
        self._addr_label.setStyleSheet("font-weight: bold;")
        controls.addWidget(self._addr_label)

        # Size label
        self._size_label = QLabel("Size: 0 bytes")
        controls.addWidget(self._size_label)

        controls.addStretch()

        # Bytes per line selector
        controls.addWidget(QLabel("Bytes/line:"))
        self._bpl_combo = QComboBox()
        self._bpl_combo.addItems(["8", "16", "32"])
        self._bpl_combo.setCurrentText("16")
        self._bpl_combo.currentTextChanged.connect(self._on_bpl_changed)
        controls.addWidget(self._bpl_combo)

        layout.addLayout(controls)

        # Color legend
        legend = QHBoxLayout()
        legend.addWidget(self._make_legend_item("Null", self.COLOR_NULL))
        legend.addWidget(self._make_legend_item("ASCII", self.COLOR_PRINTABLE))
        legend.addWidget(self._make_legend_item("Space", self.COLOR_WHITESPACE))
        legend.addWidget(self._make_legend_item("High", self.COLOR_HIGH))
        legend.addWidget(self._make_legend_item("Ctrl", self.COLOR_LOW))
        legend.addWidget(self._make_legend_item("0xFF", self.COLOR_FF))
        legend.addStretch()
        layout.addLayout(legend)

        # Hex display using QTextEdit for rich text
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        # Use monospace font
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        if not font.exactMatch():
            font.setFamily("monospace")
        self._text.setFont(font)

        # Style
        self._text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                selection-background-color: #264f78;
                border: 1px solid #3c3c3c;
            }
        """)

        # Connect mouse click
        self._text.mousePressEvent = self._on_mouse_press

        layout.addWidget(self._text)

    def _make_legend_item(self, text: str, color: str) -> QLabel:
        """Create a legend item."""
        label = QLabel(f"<span style='color:{color};'>■</span> {text}")
        label.setStyleSheet("font-size: 9px;")
        return label

    def _on_bpl_changed(self, text: str):
        """Handle bytes per line change."""
        try:
            self._bytes_per_line = int(text)
            self._update_display()
        except:
            pass

    def _on_mouse_press(self, event: QMouseEvent):
        """Handle mouse click to select byte."""
        # Call parent implementation first
        QTextEdit.mousePressEvent(self._text, event)

        if not self._data:
            return

        # Get cursor position
        cursor = self._text.cursorForPosition(event.pos())
        pos = cursor.positionInBlock()
        block = cursor.blockNumber()

        # Calculate which byte was clicked (rough approximation)
        # Format: "XXXXXXXX  XX XX XX XX XX XX XX XX  XX XX XX XX XX XX XX XX  |................|"
        # Offset column: 8 chars + 2 spaces = 10
        # Hex section starts at position 10

        if pos >= 10:
            hex_pos = pos - 10

            # Account for extra space every 8 bytes
            # Each byte takes 3 chars (XX + space), extra space after 8th byte
            bpl = self._bytes_per_line
            bytes_before_gap = min(8, bpl)
            first_section_width = bytes_before_gap * 3

            if hex_pos < first_section_width:
                byte_in_line = hex_pos // 3
            else:
                # In second section
                hex_pos_adjusted = hex_pos - first_section_width - 1  # -1 for extra space
                if hex_pos_adjusted >= 0:
                    byte_in_line = 8 + (hex_pos_adjusted // 3)
                else:
                    byte_in_line = 7  # Edge case

            byte_in_line = min(byte_in_line, bpl - 1)

            offset = block * bpl + byte_in_line
            if offset < len(self._data):
                self._selected_offset = offset
                self.byteSelected.emit(offset)

    def set_data(self, data: bytes, base_address: int = 0):
        """Set the data to display.

        Args:
            data: Raw bytes to display
            base_address: Base address for offset display
        """
        self._data = data
        self._base_address = base_address
        self._selected_offset = -1

        self._addr_label.setText(f"Address: 0x{base_address:X}" if base_address else "Address: N/A")
        self._size_label.setText(f"Size: {len(data)} bytes")

        self._update_display()

    def clear(self):
        """Clear the display."""
        self._data = b''
        self._base_address = 0
        self._selected_offset = -1
        self._text.clear()
        self._addr_label.setText("Address: N/A")
        self._size_label.setText("Size: 0 bytes")

    def _get_byte_color(self, b: int) -> str:
        """Get the color for a byte value."""
        if b == 0x00:
            return self.COLOR_NULL
        elif b == 0xFF:
            return self.COLOR_FF
        elif b in (0x09, 0x0A, 0x0D, 0x20):  # Tab, LF, CR, Space
            return self.COLOR_WHITESPACE
        elif 0x21 <= b <= 0x7E:  # Printable ASCII (excluding space)
            return self.COLOR_PRINTABLE
        elif b < 0x20:
            return self.COLOR_LOW
        else:  # 0x80-0xFE
            return self.COLOR_HIGH

    def _update_display(self):
        """Update the hex dump display with color coding."""
        if not self._data:
            self._text.clear()
            return

        html_lines = []
        bpl = self._bytes_per_line

        # Header
        html_lines.append(f"<pre style='margin:0; font-family:Consolas,monospace; font-size:10pt;'>")

        # Column headers
        header = f"<span style='color:{self.COLOR_ADDR};'>{'Offset':8}</span>  "
        for i in range(bpl):
            header += f"<span style='color:#888;'>{i:02X}</span> "
            if (i + 1) % 8 == 0 and i < bpl - 1:
                header += " "
        header += f" <span style='color:#888;'>ASCII</span>"
        html_lines.append(header)
        html_lines.append("<span style='color:#444;'>" + "─" * (10 + bpl * 3 + (bpl // 8) + 20) + "</span>")

        for i in range(0, len(self._data), bpl):
            chunk = self._data[i:i + bpl]

            # Offset/Address
            offset = self._base_address + i if self._base_address else i
            line = f"<span style='color:{self.COLOR_ADDR};'>{offset:08X}</span>  "

            # Hex bytes with colors
            hex_parts = []
            for j, b in enumerate(chunk):
                color = self._get_byte_color(b)
                hex_parts.append(f"<span style='color:{color};'>{b:02X}</span>")
                if (j + 1) % 8 == 0 and j < len(chunk) - 1:
                    hex_parts.append(" ")

            hex_str = " ".join(hex_parts)

            # Pad hex string if needed
            padding_bytes = bpl - len(chunk)
            if padding_bytes > 0:
                hex_str += "   " * padding_bytes
                # Account for gap spaces
                if len(chunk) <= 8 and bpl > 8:
                    hex_str += " "

            # ASCII representation with colors
            ascii_parts = []
            for b in chunk:
                if 32 <= b < 127:
                    # Escape HTML special chars
                    c = chr(b)
                    if c == '<':
                        c = '&lt;'
                    elif c == '>':
                        c = '&gt;'
                    elif c == '&':
                        c = '&amp;'
                    ascii_parts.append(f"<span style='color:{self.COLOR_PRINTABLE};'>{c}</span>")
                elif b == 0:
                    ascii_parts.append(f"<span style='color:{self.COLOR_NULL};'>.</span>")
                else:
                    ascii_parts.append(f"<span style='color:{self.COLOR_HIGH};'>.</span>")

            ascii_str = "".join(ascii_parts)

            line += f"{hex_str}  <span style='color:#666;'>|</span>{ascii_str}<span style='color:#666;'>|</span>"
            html_lines.append(line)

        html_lines.append("</pre>")

        self._text.setHtml("\n".join(html_lines))

    def get_hex_dump(self) -> str:
        """Get the current hex dump as plain text."""
        return self._text.toPlainText()

    def get_selected_offset(self) -> int:
        """Get the currently selected byte offset."""
        return self._selected_offset


class HexViewerPanel(QWidget):
    """Panel containing enhanced hex viewer with interpretation panel and live refresh."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._memory_reader = None
        self._current_address: int = 0
        self._current_size: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header with title and controls
        header = QHBoxLayout()
        title = QLabel("Raw Hex View")
        title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        header.addWidget(title)

        # Refresh button for hex
        self._refresh_btn = QPushButton("⟳ Refresh")
        self._refresh_btn.setToolTip("Refresh hex dump from memory")
        self._refresh_btn.clicked.connect(self._on_refresh)
        header.addWidget(self._refresh_btn)

        header.addStretch()

        self._copy_btn = QPushButton("Copy Hex")
        self._copy_btn.clicked.connect(self._on_copy)
        header.addWidget(self._copy_btn)

        layout.addLayout(header)

        # Splitter for hex viewer and interpretation panel
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Hex viewer
        self._viewer = EnhancedHexViewer()
        self._viewer.byteSelected.connect(self._on_byte_selected)
        splitter.addWidget(self._viewer)

        # Value interpretation panel
        self._interpreter = ValueInterpreter()
        splitter.addWidget(self._interpreter)

        # Set initial sizes (70% hex, 30% interpretation)
        splitter.setSizes([300, 130])

        layout.addWidget(splitter)

        # Store data for interpretation
        self._data: bytes = b''
        self._base_address: int = 0

    def _on_copy(self):
        """Handle copy button click."""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self._viewer.get_hex_dump())

    def _on_byte_selected(self, offset: int):
        """Handle byte selection in hex viewer."""
        self._interpreter.set_selection(self._data, offset, self._base_address)

    def _on_refresh(self):
        """Handle refresh button click - re-read memory."""
        if self._memory_reader and self._current_address and self._current_size:
            data = self._memory_reader.read_bytes(self._current_address, self._current_size)
            if data:
                self._data = data
                self._viewer.set_data(data, self._current_address)
                # Refresh interpretation at current selection
                offset = self._viewer.get_selected_offset()
                if offset >= 0:
                    self._interpreter.set_selection(data, offset, self._current_address)
                else:
                    self._interpreter.set_selection(data, 0, self._current_address)

    def set_memory_reader(self, reader):
        """Set the memory reader for live refresh.

        Args:
            reader: MemoryReader instance
        """
        self._memory_reader = reader

    def set_data(self, data: bytes, base_address: int = 0, size: int = 0):
        """Set the data to display.

        Args:
            data: Raw bytes to display
            base_address: Base memory address
            size: Size to read on refresh (if different from len(data))
        """
        self._data = data
        self._base_address = base_address
        self._current_address = base_address
        self._current_size = size if size else len(data)
        self._viewer.set_data(data, base_address)

        # Show interpretation of first byte by default
        if data:
            self._interpreter.set_selection(data, 0, base_address)

    def clear(self):
        """Clear the display."""
        self._data = b''
        self._base_address = 0
        self._current_address = 0
        self._current_size = 0
        self._viewer.clear()
        self._interpreter.set_selection(b'', 0, 0)


# Keep old class names for backward compatibility
HexViewer = EnhancedHexViewer
