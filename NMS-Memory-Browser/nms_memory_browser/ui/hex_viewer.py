"""Hex viewer widget for raw memory display.

Displays memory contents in traditional hex dump format.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QLabel, QSpinBox, QPushButton, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCharFormat, QColor

logger = logging.getLogger(__name__)


class HexViewer(QWidget):
    """Widget for displaying raw memory in hex format."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._data: bytes = b''
        self._base_address: int = 0
        self._bytes_per_line: int = 16

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

        # Hex display
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        # Use monospace font
        font = QFont("Consolas", 10)
        if not font.exactMatch():
            font = QFont("Courier New", 10)
        if not font.exactMatch():
            font.setFamily("monospace")
        self._text.setFont(font)

        # Style
        self._text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                selection-background-color: #264f78;
            }
        """)

        layout.addWidget(self._text)

    def _on_bpl_changed(self, text: str):
        """Handle bytes per line change."""
        try:
            self._bytes_per_line = int(text)
            self._update_display()
        except:
            pass

    def set_data(self, data: bytes, base_address: int = 0):
        """Set the data to display.

        Args:
            data: Raw bytes to display
            base_address: Base address for offset display
        """
        self._data = data
        self._base_address = base_address

        self._addr_label.setText(f"Address: 0x{base_address:X}" if base_address else "Address: N/A")
        self._size_label.setText(f"Size: {len(data)} bytes")

        self._update_display()

    def clear(self):
        """Clear the display."""
        self._data = b''
        self._base_address = 0
        self._text.clear()
        self._addr_label.setText("Address: N/A")
        self._size_label.setText("Size: 0 bytes")

    def _update_display(self):
        """Update the hex dump display."""
        if not self._data:
            self._text.clear()
            return

        lines = []
        bpl = self._bytes_per_line

        for i in range(0, len(self._data), bpl):
            chunk = self._data[i:i + bpl]

            # Offset
            offset = self._base_address + i if self._base_address else i
            offset_str = f"{offset:08X}"

            # Hex bytes
            hex_parts = []
            for j, b in enumerate(chunk):
                hex_parts.append(f"{b:02X}")
                # Add extra space every 8 bytes for readability
                if (j + 1) % 8 == 0 and j < len(chunk) - 1:
                    hex_parts.append("")

            hex_str = " ".join(hex_parts)

            # Pad hex string to consistent width
            expected_width = (bpl * 3) - 1 + (bpl // 8 - 1)
            hex_str = hex_str.ljust(expected_width)

            # ASCII representation
            ascii_parts = []
            for b in chunk:
                if 32 <= b < 127:
                    ascii_parts.append(chr(b))
                else:
                    ascii_parts.append(".")

            ascii_str = "".join(ascii_parts)

            # Combine
            lines.append(f"{offset_str}  {hex_str}  |{ascii_str}|")

        self._text.setPlainText("\n".join(lines))

    def get_hex_dump(self) -> str:
        """Get the current hex dump as text."""
        return self._text.toPlainText()

    def copy_to_clipboard(self):
        """Copy the hex dump to clipboard."""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.get_hex_dump())


class HexViewerPanel(QWidget):
    """Panel containing hex viewer with copy button."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with title and copy button
        header = QHBoxLayout()
        header.addWidget(QLabel("Raw Hex View"))
        header.addStretch()

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.clicked.connect(self._on_copy)
        header.addWidget(self._copy_btn)

        layout.addLayout(header)

        # Hex viewer
        self._viewer = HexViewer()
        layout.addWidget(self._viewer)

    def _on_copy(self):
        """Handle copy button click."""
        self._viewer.copy_to_clipboard()

    def set_data(self, data: bytes, base_address: int = 0):
        """Set the data to display."""
        self._viewer.set_data(data, base_address)

    def clear(self):
        """Clear the display."""
        self._viewer.clear()
