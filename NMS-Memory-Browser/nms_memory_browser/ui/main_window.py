"""Main application window for NMS Memory Browser.

Provides the main UI with tree browser, detail panel, and toolbar.
"""

import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QStatusBar, QLabel, QMessageBox, QFileDialog,
    QPushButton, QProgressDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from ..config import BrowserConfig, load_config
from ..core.memory_reader import MemoryReader
from ..core.struct_registry import StructRegistry
from ..core.struct_mapper import StructMapper
from ..core.pointer_scanner import PointerScanner
from ..collectors.player_collector import PlayerCollector
from ..collectors.system_collector import SystemCollector
from ..collectors.multiplayer_collector import MultiplayerCollector
from ..collectors.unknown_collector import UnknownCollector
from ..data.tree_node import TreeNode, NodeType, create_root_node, create_category_node, create_field_node
from ..data.snapshot import Snapshot, SnapshotMetadata
from ..export.json_exporter import JSONExporter
from .tree_browser import TreeBrowser
from .detail_panel import DetailPanel
from .dialogs.export_dialog import ExportDialog

logger = logging.getLogger(__name__)


def log_flush(msg: str, level: str = "info"):
    """Log a message and immediately flush to disk."""
    if level == "info":
        logger.info(msg)
    elif level == "error":
        logger.error(msg)
    elif level == "warning":
        logger.warning(msg)
    elif level == "debug":
        logger.debug(msg)
    # Force flush all handlers
    for handler in logging.root.handlers:
        handler.flush()


def safe_collect(collector, name: str) -> Optional[TreeNode]:
    """Safely collect data from a collector with error handling.

    Args:
        collector: The collector instance
        name: Name of the collector for logging

    Returns:
        TreeNode or None if collection failed
    """
    if collector is None:
        log_flush(f"{name}: Collector is None, skipping", "debug")
        return None

    try:
        log_flush(f"{name}: Starting collection...")
        node = collector.build_tree_nodes()
        log_flush(f"{name}: Collection successful")
        return node
    except Exception as e:
        log_flush(f"{name}: Collection FAILED - {e}", "error")
        log_flush(f"{name}: Traceback:\n{traceback.format_exc()}", "error")
        return None


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, parent: Optional[QWidget] = None, game_data_provider=None):
        super().__init__(parent)

        self._config = load_config()
        self._connected = False
        self._game_data_provider = game_data_provider  # Callback to get data from main thread

        # Core components (initialized on connect)
        self._reader: Optional[MemoryReader] = None
        self._registry: Optional[StructRegistry] = None
        self._mapper: Optional[StructMapper] = None
        self._scanner: Optional[PointerScanner] = None

        # Collectors
        self._player_collector: Optional[PlayerCollector] = None
        self._system_collector: Optional[SystemCollector] = None
        self._mp_collector: Optional[MultiplayerCollector] = None
        self._unknown_collector: Optional[UnknownCollector] = None

        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()

        # Try to connect on startup - call directly since QTimer doesn't work in pyMHF context
        log_flush("MainWindow.__init__: About to call _try_connect directly...")
        try:
            self._try_connect()
        except Exception as e:
            log_flush(f"MainWindow.__init__: _try_connect FAILED - {e}", "error")
            log_flush(f"Traceback:\n{traceback.format_exc()}", "error")

    def _setup_ui(self):
        """Set up the main UI layout."""
        self.setWindowTitle("NMS Memory Browser")
        self.setMinimumSize(800, 600)
        self.resize(self._config.window_width, self._config.window_height)

        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        # Main splitter
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Tree browser
        self._tree = TreeBrowser()
        self._tree.nodeSelected.connect(self._on_node_selected)
        self._splitter.addWidget(self._tree)

        # Right panel: Detail panel
        self._detail = DetailPanel()
        self._splitter.addWidget(self._detail)

        # Set splitter sizes
        self._splitter.setSizes([
            self._config.tree_panel_width,
            self._config.detail_panel_width
        ])

        layout.addWidget(self._splitter)

    def _setup_toolbar(self):
        """Set up the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Connect button (manual fallback)
        self._connect_action = QAction("Connect", self)
        self._connect_action.triggered.connect(self._on_manual_connect)
        toolbar.addAction(self._connect_action)

        # Refresh button
        self._refresh_action = QAction("Refresh", self)
        self._refresh_action.setShortcut("F5")
        self._refresh_action.triggered.connect(self._on_refresh)
        toolbar.addAction(self._refresh_action)

        toolbar.addSeparator()

        # Export button
        self._export_action = QAction("Export JSON", self)
        self._export_action.setShortcut("Ctrl+S")
        self._export_action.triggered.connect(self._on_export)
        toolbar.addAction(self._export_action)

        toolbar.addSeparator()

        # Expand/Collapse
        expand_action = QAction("Expand All", self)
        expand_action.triggered.connect(self._tree.expand_all)
        toolbar.addAction(expand_action)

        collapse_action = QAction("Collapse All", self)
        collapse_action.triggered.connect(self._tree.collapse_all)
        toolbar.addAction(collapse_action)

    def _setup_statusbar(self):
        """Set up the status bar."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        # Connection status
        self._connection_label = QLabel("Disconnected")
        self._statusbar.addWidget(self._connection_label)

        # Spacer
        self._statusbar.addWidget(QLabel(" | "))

        # Stats
        self._stats_label = QLabel("Structs: 0")
        self._statusbar.addWidget(self._stats_label)

        # Memory stats
        self._memory_label = QLabel("")
        self._statusbar.addPermanentWidget(self._memory_label)

    def _try_connect(self):
        """Try to connect to the game."""
        log_flush("=== _try_connect: Starting connection sequence ===")
        try:
            # Initialize core components
            log_flush("Connect Step 1: Creating MemoryReader...")
            self._reader = MemoryReader()
            log_flush("Connect Step 1: MemoryReader created")

            log_flush("Connect Step 2: Creating StructRegistry...")
            self._registry = StructRegistry()
            log_flush("Connect Step 2: StructRegistry created")

            log_flush("Connect Step 3: Creating PointerScanner...")
            self._scanner = PointerScanner()
            log_flush("Connect Step 3: PointerScanner created")

            # Load registry
            log_flush("Connect Step 4: Loading struct registry...")
            if not self._registry.load():
                log_flush("Could not load struct registry - running without NMS.py", "warning")
            else:
                log_flush("Connect Step 4: Registry loaded successfully")

            # Connect scanner
            log_flush("Connect Step 5: Connecting scanner to game...")
            if not self._scanner.connect():
                log_flush("Connect Step 5: Scanner failed to connect", "warning")
                self._update_status("Game not connected", False)
                return
            log_flush("Connect Step 5: Scanner connected successfully")

            # Initialize mapper
            log_flush("Connect Step 6: Creating StructMapper...")
            self._mapper = StructMapper(self._reader, self._registry)
            log_flush("Connect Step 6: StructMapper created")

            # Initialize collectors (but don't collect data yet)
            log_flush("Connect Step 7: Creating collectors...")
            try:
                self._player_collector = PlayerCollector(self._reader, self._mapper, self._scanner)
                log_flush("Connect Step 7a: PlayerCollector created")
            except Exception as e:
                log_flush(f"Connect Step 7a: PlayerCollector FAILED - {e}", "error")
                self._player_collector = None

            try:
                self._system_collector = SystemCollector(self._reader, self._mapper, self._scanner)
                log_flush("Connect Step 7b: SystemCollector created")
            except Exception as e:
                log_flush(f"Connect Step 7b: SystemCollector FAILED - {e}", "error")
                self._system_collector = None

            try:
                self._mp_collector = MultiplayerCollector(self._reader, self._mapper, self._scanner)
                log_flush("Connect Step 7c: MultiplayerCollector created")
            except Exception as e:
                log_flush(f"Connect Step 7c: MultiplayerCollector FAILED - {e}", "error")
                self._mp_collector = None

            try:
                self._unknown_collector = UnknownCollector(
                    self._reader, self._mapper, self._registry, self._scanner
                )
                log_flush("Connect Step 7d: UnknownCollector created")
            except Exception as e:
                log_flush(f"Connect Step 7d: UnknownCollector FAILED - {e}", "error")
                self._unknown_collector = None

            # Set up detail panel
            log_flush("Connect Step 8: Setting up detail panel...")
            self._detail.set_memory_reader(self._reader)
            log_flush("Connect Step 8: Detail panel ready")

            self._connected = True
            self._update_status("Connected to NMS", True)
            log_flush("=== _try_connect: Connection successful ===")

            # Load initial data - call directly since QTimer doesn't work in pyMHF context
            log_flush("Calling initial data refresh directly...")
            self._safe_initial_refresh()

        except Exception as e:
            log_flush(f"_try_connect FAILED: {e}", "error")
            log_flush(f"Traceback:\n{traceback.format_exc()}", "error")
            self._update_status(f"Connection failed: {e}", False)

    def _safe_initial_refresh(self):
        """Safely perform initial data refresh with error handling."""
        log_flush("=== _safe_initial_refresh: Starting initial data load ===")
        try:
            self._refresh_tree()
            log_flush("=== _safe_initial_refresh: Completed successfully ===")
        except Exception as e:
            log_flush(f"_safe_initial_refresh FAILED: {e}", "error")
            log_flush(f"Traceback:\n{traceback.format_exc()}", "error")
            self._update_status(f"Initial load failed: {e}", True)

    def _update_status(self, message: str, connected: bool):
        """Update the status bar."""
        self._connected = connected

        if connected:
            self._connection_label.setText(f"Connected: {message}")
            self._connection_label.setStyleSheet("color: green;")
        else:
            self._connection_label.setText(f"Disconnected: {message}")
            self._connection_label.setStyleSheet("color: red;")

        # Update stats
        struct_count = len(self._registry.structs) if self._registry else 0
        self._stats_label.setText(f"Structs: {struct_count}")

    def _refresh_tree(self):
        """Refresh the tree with current game data."""
        log_flush("=== _refresh_tree: Starting refresh ===")

        if not self._connected:
            log_flush("_refresh_tree: Not connected, aborting", "warning")
            QMessageBox.warning(
                self,
                "Not Connected",
                "Not connected to the game. Make sure NMS is running with pyMHF."
            )
            return

        try:
            # Create new root
            log_flush("Refresh Step 1: Creating root node...")
            root = create_root_node()
            log_flush("Refresh Step 1: Root node created")

            # Get cached data from the pyMHF thread
            cached_data = {}
            if self._game_data_provider:
                log_flush("Refresh Step 1.5: Getting cached data from provider...")
                cached_data = self._game_data_provider()
                log_flush(f"Refresh Step 1.5: Got cached data: {list(cached_data.keys())}")
                if 'raw_data' in cached_data:
                    log_flush(f"Refresh Step 1.5: raw_data: {cached_data['raw_data']}")

            # Build tree from cached data
            log_flush("Refresh Step 2: Building Player node from cached data...")
            player_node = self._build_player_node(cached_data)
            if player_node:
                root.add_child(player_node)
                log_flush("Refresh Step 2: Player node added")
            else:
                log_flush("Refresh Step 2: No player data available", "warning")

            # Add Solar System category (placeholder for now)
            log_flush("Refresh Step 3: Building SolarSystem node...")
            system_node = self._build_system_node(cached_data)
            if system_node:
                root.add_child(system_node)
                log_flush("Refresh Step 3: SolarSystem node added")

            # Add placeholder nodes for other categories
            log_flush("Refresh Step 4: Adding placeholder nodes...")

            # Update tree
            log_flush("Refresh Step 5: Updating tree view...")
            self._tree.set_root(root)
            log_flush("Refresh Step 5: Tree view updated")

            # Update memory stats
            if self._reader:
                stats = self._reader.stats
                self._memory_label.setText(
                    f"Reads: {stats['read_count']} | Errors: {stats['error_count']}"
                )
                log_flush(f"Memory stats - Reads: {stats['read_count']}, Errors: {stats['error_count']}")

            self._statusbar.showMessage("Refresh complete", 3000)
            log_flush("=== _refresh_tree: Completed successfully ===")

        except Exception as e:
            log_flush(f"_refresh_tree FAILED: {e}", "error")
            log_flush(f"Traceback:\n{traceback.format_exc()}", "error")
            QMessageBox.critical(self, "Error", f"Failed to refresh: {e}")

    def _build_player_node(self, cached_data: dict) -> Optional[TreeNode]:
        """Build player tree node from cached data."""
        category = create_category_node('Player', 'Player Data')

        # Check if we have player data
        raw_data = cached_data.get('raw_data', {})
        player_data = raw_data.get('player', {})

        if not player_data:
            log_flush("_build_player_node: No player data in cache", "warning")
            # Add placeholder node
            stats_node = TreeNode(
                name='Stats',
                node_type=NodeType.STRUCT,
                display_text='Player Stats (No Data)',
                icon='chart',
            )
            stats_node.add_child(create_field_node(
                name='status',
                value='No data available',
                formatted_value='Click "Refresh Data" in pyMHF to update',
                offset=0,
                size=0,
            ))
            category.add_child(stats_node)
            return category

        # Add Stats node with actual data
        stats_node = TreeNode(
            name='Stats',
            node_type=NodeType.STRUCT,
            display_text='Player Stats',
            icon='chart',
        )

        for stat_name, stat_value in player_data.items():
            if stat_value is not None:
                stats_node.add_child(create_field_node(
                    name=stat_name,
                    value=stat_value,
                    formatted_value=str(stat_value),
                    offset=0,
                    size=4,
                ))

        category.add_child(stats_node)
        return category

    def _build_system_node(self, cached_data: dict) -> Optional[TreeNode]:
        """Build solar system tree node from cached data."""
        category = create_category_node('Solar System', 'Solar System Data')

        # Placeholder for now
        info_node = TreeNode(
            name='Info',
            node_type=NodeType.STRUCT,
            display_text='System Info',
            icon='planet',
        )
        info_node.add_child(create_field_node(
            name='status',
            value='Pending implementation',
            formatted_value='Solar system data collection coming soon',
            offset=0,
            size=0,
        ))
        category.add_child(info_node)

        return category

    def _on_refresh(self):
        """Handle refresh button click."""
        self._refresh_tree()

    def _on_manual_connect(self):
        """Handle manual connect button click."""
        log_flush("=== Manual Connect button clicked ===")
        try:
            self._try_connect()
        except Exception as e:
            log_flush(f"Manual connect FAILED: {e}", "error")
            log_flush(f"Traceback:\n{traceback.format_exc()}", "error")
            QMessageBox.critical(self, "Connect Failed", f"Failed to connect: {e}")

    def _on_node_selected(self, node: TreeNode):
        """Handle tree node selection."""
        self._detail.set_node(node)

    def _on_export(self):
        """Handle export button click."""
        if not self._connected:
            QMessageBox.warning(
                self,
                "Not Connected",
                "Not connected to the game. Cannot export."
            )
            return

        # Show export dialog
        dialog = ExportDialog(self._config, self)
        if dialog.exec():
            options = dialog.get_options()
            self._do_export(options)

    def _do_export(self, options: dict):
        """Perform the export."""
        try:
            # Collect data
            snapshot = Snapshot()

            # Metadata
            snapshot.metadata = SnapshotMetadata(
                timestamp=datetime.now().isoformat(),
                extractor_version="1.0.0",
                connected=self._connected,
            )

            # Get player location for metadata
            if self._player_collector:
                player_data = self._player_collector.collect()
                location = player_data.get('location', {})
                snapshot.metadata.glyph_code = location.get('glyph_code', '')

            # Collect each category
            if self._player_collector:
                data = self._player_collector.collect()
                snapshot.player = data.get('structs', {})

            if self._system_collector:
                data = self._system_collector.collect()
                snapshot.solar_system = data.get('structs', {})

            if self._mp_collector:
                data = self._mp_collector.collect()
                snapshot.multiplayer = {
                    'session_info': data.get('session_info', {}),
                    'other_players': data.get('other_players', []),
                    'player_bases': data.get('player_bases', []),
                    'settlements': data.get('settlements', []),
                    'comm_stations': data.get('comm_stations', []),
                }

            if options.get('include_unknown', True) and self._unknown_collector:
                data = self._unknown_collector.collect()
                snapshot.unknown_regions = self._unknown_collector.to_snapshot_regions(data)

            # Export
            filepath = options.get('filepath')
            if not filepath:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = self._config.export_dir / f"memory_snapshot_{timestamp}.json"

            exporter = JSONExporter(snapshot)
            exporter.export(Path(filepath), options)

            QMessageBox.information(
                self,
                "Export Complete",
                f"Snapshot saved to:\n{filepath}"
            )

        except Exception as e:
            logger.error(f"Export failed: {e}")
            QMessageBox.critical(self, "Export Failed", str(e))

    def closeEvent(self, event):
        """Handle window close."""
        # Save window geometry to config
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        sizes = self._splitter.sizes()
        if len(sizes) >= 2:
            self._config.tree_panel_width = sizes[0]
            self._config.detail_panel_width = sizes[1]

        event.accept()
