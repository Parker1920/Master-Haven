"""Export dialog for saving memory snapshots.

Provides options for exporting memory data to JSON.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QGroupBox, QFileDialog, QSpinBox
)
from PyQt6.QtCore import Qt

from ...config import BrowserConfig

logger = logging.getLogger(__name__)


class ExportDialog(QDialog):
    """Dialog for configuring export options."""

    def __init__(self, config: BrowserConfig, parent=None):
        super().__init__(parent)

        self._config = config
        self._options: Dict[str, Any] = {}

        self.setWindowTitle("Export Memory Snapshot")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # File path section
        file_group = QGroupBox("Output File")
        file_layout = QVBoxLayout(file_group)

        path_layout = QHBoxLayout()
        self._path_edit = QLineEdit()

        # Default path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = self._config.export_dir / f"memory_snapshot_{timestamp}.json"
        self._path_edit.setText(str(default_path))

        path_layout.addWidget(self._path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._on_browse)
        path_layout.addWidget(browse_btn)

        file_layout.addLayout(path_layout)
        layout.addWidget(file_group)

        # Content options
        content_group = QGroupBox("Content Options")
        content_layout = QVBoxLayout(content_group)

        self._include_player = QCheckBox("Include Player Data")
        self._include_player.setChecked(True)
        content_layout.addWidget(self._include_player)

        self._include_system = QCheckBox("Include Solar System Data")
        self._include_system.setChecked(True)
        content_layout.addWidget(self._include_system)

        self._include_mp = QCheckBox("Include Multiplayer Data")
        self._include_mp.setChecked(True)
        content_layout.addWidget(self._include_mp)

        self._include_unknown = QCheckBox("Include Unknown Regions")
        self._include_unknown.setChecked(self._config.include_unknown_regions)
        content_layout.addWidget(self._include_unknown)

        self._include_hex = QCheckBox("Include Hex Dumps")
        self._include_hex.setChecked(self._config.include_hex_dumps)
        content_layout.addWidget(self._include_hex)

        layout.addWidget(content_group)

        # Hex dump options
        hex_group = QGroupBox("Hex Dump Options")
        hex_layout = QHBoxLayout(hex_group)

        hex_layout.addWidget(QLabel("Max hex dump size (bytes):"))
        self._max_hex_size = QSpinBox()
        self._max_hex_size.setRange(256, 65536)
        self._max_hex_size.setSingleStep(256)
        self._max_hex_size.setValue(self._config.max_hex_dump_size)
        hex_layout.addWidget(self._max_hex_size)
        hex_layout.addStretch()

        layout.addWidget(hex_group)

        # Format options
        format_group = QGroupBox("Format Options")
        format_layout = QVBoxLayout(format_group)

        self._pretty_print = QCheckBox("Pretty print JSON (indented)")
        self._pretty_print.setChecked(True)
        format_layout.addWidget(self._pretty_print)

        layout.addWidget(format_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        export_btn = QPushButton("Export")
        export_btn.setDefault(True)
        export_btn.clicked.connect(self._on_export)
        button_layout.addWidget(export_btn)

        layout.addLayout(button_layout)

    def _on_browse(self):
        """Handle browse button click."""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Snapshot",
            str(self._config.export_dir),
            "JSON Files (*.json);;All Files (*)"
        )

        if filepath:
            self._path_edit.setText(filepath)

    def _on_export(self):
        """Handle export button click."""
        filepath = self._path_edit.text().strip()

        if not filepath:
            return

        # Ensure .json extension
        if not filepath.lower().endswith('.json'):
            filepath += '.json'

        self._options = {
            'filepath': Path(filepath),
            'include_player': self._include_player.isChecked(),
            'include_system': self._include_system.isChecked(),
            'include_multiplayer': self._include_mp.isChecked(),
            'include_unknown': self._include_unknown.isChecked(),
            'include_hex_dumps': self._include_hex.isChecked(),
            'max_hex_dump_size': self._max_hex_size.value(),
            'pretty_print': self._pretty_print.isChecked(),
        }

        self.accept()

    def get_options(self) -> Dict[str, Any]:
        """Get the selected export options.

        Returns:
            Dictionary of export options
        """
        return self._options
