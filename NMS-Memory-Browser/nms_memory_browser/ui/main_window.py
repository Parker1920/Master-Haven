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
        self.setWindowTitle("NMS Memory Browser v3.8.4 - DEEP Base Search")
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
        """Refresh the tree with current game data.

        v3.0: Now shows ALL available game objects and struct types for
        general-purpose memory browsing.
        """
        log_flush("=== _refresh_tree: Starting refresh (v3.0) ===")

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
            root = create_root_node()

            # Get cached data from the pyMHF thread
            cached_data = {}
            if self._game_data_provider:
                cached_data = self._game_data_provider()
                log_flush(f"Got cached data keys: {list(cached_data.keys())}")

            # Check if data is ready
            data_ready = cached_data.get('data_ready', False)

            if not data_ready:
                waiting_node = create_category_node('Status', 'Waiting for Game Data')
                info_node = TreeNode(
                    name='waiting',
                    node_type=NodeType.STRUCT,
                    display_text='Waiting for game...',
                    icon='warning',
                )
                info_node.add_child(create_field_node(
                    name='message',
                    value='Game data not ready',
                    formatted_value='Load into the game fully, then click Refresh Data in pyMHF.',
                    offset=0,
                    size=0,
                ))
                waiting_node.add_child(info_node)
                root.add_child(waiting_node)
                self._tree.set_root(root)
                self._statusbar.showMessage("Waiting for game data", 5000)
                return

            # =====================================================
            # v3.0: Add Game Objects category (ALL gameData entries)
            # =====================================================
            game_objects = cached_data.get('game_objects', {})
            if game_objects:
                objects_node = self._build_game_objects_node(game_objects)
                root.add_child(objects_node)
                log_flush(f"Added Game Objects node with {len(game_objects)} entries")

            # =====================================================
            # v3.0: Add Struct Types category (ALL nmspy structs)
            # =====================================================
            struct_types = cached_data.get('struct_types', [])
            if struct_types:
                types_node = self._build_struct_types_node(struct_types)
                root.add_child(types_node)
                log_flush(f"Added Struct Types node with {len(struct_types)} types")

            # =====================================================
            # Legacy: Player and System nodes for convenience
            # =====================================================
            player_node = self._build_player_node(cached_data)
            if player_node:
                root.add_child(player_node)

            system_node = self._build_system_node(cached_data)
            if system_node:
                root.add_child(system_node)

            # Update tree
            self._tree.set_root(root)

            # Update memory stats
            if self._reader:
                stats = self._reader.stats
                self._memory_label.setText(
                    f"Reads: {stats['read_count']} | Errors: {stats['error_count']}"
                )

            # Update status with counts including field count
            obj_count = len(game_objects)
            type_count = len(struct_types)
            field_count = sum(s.get('field_count', 0) for s in struct_types)
            self._statusbar.showMessage(
                f"Loaded: {obj_count} game objects, {type_count} structs, {field_count} fields", 5000
            )
            log_flush(f"=== _refresh_tree: Done - {obj_count} objects, {type_count} structs, {field_count} fields ===")

        except Exception as e:
            log_flush(f"_refresh_tree FAILED: {e}", "error")
            log_flush(f"Traceback:\n{traceback.format_exc()}", "error")
            QMessageBox.critical(self, "Error", f"Failed to refresh: {e}")

    def _build_player_node(self, cached_data: dict) -> Optional[TreeNode]:
        """Build player tree node from cached data."""
        category = create_category_node('Player', 'Player Data')

        # Debug: Log what we receive
        log_flush("=== _build_player_node: Building player node ===")
        raw_data = cached_data.get('raw_data', {})
        log_flush(f"  raw_data keys: {list(raw_data.keys())}")
        player_data = raw_data.get('player', {})
        location_data = raw_data.get('location', {})
        log_flush(f"  player_data: {player_data}")
        log_flush(f"  location_data: {location_data}")

        if not player_data:
            log_flush("_build_player_node: No player data in cache", "warning")
            log_flush("  Possible causes:")
            log_flush("    1. gameData.player_state is None (check main log)")
            log_flush("    2. Game not fully loaded yet (wait for APPVIEW)")
            log_flush("    3. Click 'Refresh Data' in pyMHF to update")
            # Add placeholder node
            stats_node = TreeNode(
                name='Stats',
                node_type=NodeType.STRUCT,
                display_text='Player Stats (No Data)',
                icon='chart',
                formatted_value='No data available',
                struct_type='PlayerStats',
            )
            stats_node.add_child(create_field_node(
                name='status',
                value='No data available',
                formatted_value='Click "Refresh Data" in pyMHF to update',
                offset=0,
                size=0,
                type_name='status',
            ))
            category.add_child(stats_node)
            return category

        # Get additional data sections
        character_data = raw_data.get('character', {})
        ships_data = raw_data.get('ships', [])

        # Build summary of player stats
        health = player_data.get('health', '?')
        shield = player_data.get('shield', '?')
        units = player_data.get('units', 0)

        # Add Stats node (health, shield, energy)
        stats_node = TreeNode(
            name='Stats',
            node_type=NodeType.STRUCT,
            display_text='Health & Stats',
            icon='chart',
            formatted_value=f'Health: {health} | Shield: {shield}',
            struct_type='cGcPlayerState',
        )
        stat_fields = ['health', 'shield', 'ship_health', 'energy', 'primary_ship_index', 'primary_multitool_index']
        for stat_name in stat_fields:
            stat_value = player_data.get(stat_name)
            if stat_value is not None:
                formatted = f"{stat_value} HP" if 'health' in stat_name else str(stat_value)
                stats_node.add_child(create_field_node(
                    name=stat_name,
                    value=stat_value,
                    formatted_value=formatted,
                    offset=0,
                    size=4,
                    type_name='int32' if isinstance(stat_value, int) else 'float',
                ))
        category.add_child(stats_node)

        # Add Currencies node
        currencies_node = TreeNode(
            name='Currencies',
            node_type=NodeType.STRUCT,
            display_text='Currencies',
            icon='money',
            formatted_value=f'Units: {units:,}' if isinstance(units, int) else f'Units: {units}',
            struct_type='Currencies',
        )
        for curr_name in ['units', 'nanites', 'quicksilver']:
            curr_value = player_data.get(curr_name)
            if curr_value is not None:
                currencies_node.add_child(create_field_node(
                    name=curr_name,
                    value=curr_value,
                    formatted_value=f'{curr_value:,}' if isinstance(curr_value, int) else str(curr_value),
                    offset=0,
                    size=4,
                    type_name='uint32',
                ))
        category.add_child(currencies_node)

        # Add Location node
        if location_data:
            galaxy_name = location_data.get('galaxy_name', 'Unknown')
            glyph_code = location_data.get('glyph_code', 'N/A')
            loc_node = TreeNode(
                name='Location',
                node_type=NodeType.STRUCT,
                display_text='Current Location',
                icon='location',
                formatted_value=f'{galaxy_name} | {glyph_code}',
                struct_type='cGcUniverseAddressData',
            )
            for loc_name, loc_value in location_data.items():
                if loc_value is not None:
                    loc_node.add_child(create_field_node(
                        name=loc_name,
                        value=loc_value,
                        formatted_value=str(loc_value),
                        offset=0,
                        size=4,
                        type_name='int32' if isinstance(loc_value, int) else 'string',
                    ))
            category.add_child(loc_node)

        # Add Character State node (jetpack, stamina, etc.)
        if character_data:
            char_node = TreeNode(
                name='Character',
                node_type=NodeType.STRUCT,
                display_text='Character State',
                icon='player',
                formatted_value='Jetpack, stamina, running state',
                struct_type='cGcPlayer',
            )
            for char_name, char_value in character_data.items():
                if char_value is not None:
                    if isinstance(char_value, bool):
                        formatted = 'Yes' if char_value else 'No'
                    elif isinstance(char_value, float):
                        formatted = f'{char_value:.1f}%'
                    else:
                        formatted = str(char_value)
                    char_node.add_child(create_field_node(
                        name=char_name,
                        value=char_value,
                        formatted_value=formatted,
                        offset=0,
                        size=4,
                        type_name='float' if isinstance(char_value, float) else 'bool' if isinstance(char_value, bool) else 'int32',
                    ))
            category.add_child(char_node)

        # Add Ships node (fleet of up to 12 ships)
        if ships_data:
            primary_idx = player_data.get('primary_ship_index', 0)
            owned_count = sum(1 for s in ships_data if not s.get('empty', True))
            ships_node = TreeNode(
                name='Ships',
                node_type=NodeType.ARRAY,
                display_text=f'Ship Fleet ({owned_count} owned)',
                icon='ship',
                formatted_value=f'{owned_count} ships, Primary: Slot {primary_idx}',
                struct_type='cGcPlayerShipOwnership',
            )
            for ship_info in ships_data:
                slot = ship_info.get('slot', 0)
                is_empty = ship_info.get('empty', True)
                is_primary = (slot == primary_idx)

                if is_empty:
                    ship_display = f'Slot {slot}: Empty'
                else:
                    class_id = ship_info.get('class_id', 0)
                    class_names = {0: "Shuttle", 1: "Fighter", 2: "Scientific", 3: "Hauler",
                                   4: "Exotic", 5: "Freighter", 6: "Capital", 7: "Living", 8: "Solar", 9: "Robot"}
                    class_name = class_names.get(class_id, f"Class {class_id}")
                    ship_display = f'Slot {slot}: {class_name}'
                    if is_primary:
                        ship_display += ' [PRIMARY]'

                ship_node = TreeNode(
                    name=f'Ship_{slot}',
                    node_type=NodeType.STRUCT,
                    display_text=ship_display,
                    icon='ship',
                    struct_type='sGcShipData',
                )
                for field_name, field_value in ship_info.items():
                    if field_name != 'slot' and field_value is not None:
                        ship_node.add_child(create_field_node(
                            name=field_name,
                            value=field_value,
                            formatted_value=str(field_value),
                            offset=0,
                            size=4,
                            type_name='int32',
                        ))
                ships_node.add_child(ship_node)
            category.add_child(ships_node)

        # Add Freighter node
        freighter_data = raw_data.get('freighter', {})
        if freighter_data:
            has_freighter = freighter_data.get('has_freighter', False)
            status = freighter_data.get('status', 'unknown')
            freighter_node = TreeNode(
                name='Freighter',
                node_type=NodeType.STRUCT,
                display_text='Freighter',
                icon='freighter',
                formatted_value='Owned' if has_freighter else 'None detected',
                struct_type='cGcFreighterSaveData',
            )
            freighter_node.add_child(create_field_node(
                name='has_freighter',
                value=has_freighter,
                formatted_value='Yes' if has_freighter else 'No',
                offset=0,
                size=1,
                type_name='bool',
            ))
            freighter_node.add_child(create_field_node(
                name='status',
                value=status,
                formatted_value=status,
                offset=0,
                size=0,
                type_name='string',
            ))
            note = freighter_data.get('note', '')
            if note:
                freighter_node.add_child(create_field_node(
                    name='note',
                    value=note,
                    formatted_value=note,
                    offset=0,
                    size=0,
                    type_name='string',
                ))
            category.add_child(freighter_node)

        # Add Bases node
        bases_data = raw_data.get('bases', {})
        if bases_data:
            base_count = bases_data.get('base_count', 0)
            status = bases_data.get('status', 'unknown')
            bases_node = TreeNode(
                name='Bases',
                node_type=NodeType.STRUCT,
                display_text='Player Bases',
                icon='base',
                formatted_value=f'{base_count} bases' if base_count > 0 else 'Data in save file',
                struct_type='cGcPersistentBase',
            )
            bases_node.add_child(create_field_node(
                name='base_count',
                value=base_count,
                formatted_value=str(base_count),
                offset=0,
                size=4,
                type_name='int32',
            ))
            bases_node.add_child(create_field_node(
                name='status',
                value=status,
                formatted_value=status,
                offset=0,
                size=0,
                type_name='string',
            ))
            note = bases_data.get('note', '')
            if note:
                bases_node.add_child(create_field_node(
                    name='note',
                    value=note,
                    formatted_value=note,
                    offset=0,
                    size=0,
                    type_name='string',
                ))
            category.add_child(bases_node)

        # Add Multitools node
        multitools_data = raw_data.get('multitools', {})
        if multitools_data:
            primary_mt = multitools_data.get('primary_index', 0)
            mt_node = TreeNode(
                name='Multitools',
                node_type=NodeType.STRUCT,
                display_text='Multitools',
                icon='multitool',
                formatted_value=f'Primary: Slot {primary_mt}',
                struct_type='cGcMultitoolData',
            )
            mt_node.add_child(create_field_node(
                name='primary_index',
                value=primary_mt,
                formatted_value=f'Slot {primary_mt}',
                offset=0,
                size=4,
                type_name='int32',
            ))
            note = multitools_data.get('note', '')
            if note:
                mt_node.add_child(create_field_node(
                    name='note',
                    value=note,
                    formatted_value=note,
                    offset=0,
                    size=0,
                    type_name='string',
                ))
            category.add_child(mt_node)

        # Add Multiplayer node (Enhanced v2)
        multiplayer_data = raw_data.get('multiplayer', {})
        if multiplayer_data:
            mp_active = multiplayer_data.get('multiplayer_active', False)
            session_type = multiplayer_data.get('session_type', 'unknown')
            detection_method = multiplayer_data.get('detection_method', 'none')
            game_mode = multiplayer_data.get('game_mode_name', 'Unknown')

            # Format session type for display
            session_display = {
                'single_player': 'Solo Session',
                'multiplayer_host': 'Hosting Multiplayer',
                'multiplayer_detected': 'In Multiplayer Session',
                'multiplayer_with_players': 'Multiplayer (Players Detected)',
                'anomaly_session': 'In Anomaly (MP Hub)',
            }.get(session_type, session_type)

            mp_node = TreeNode(
                name='Multiplayer',
                node_type=NodeType.STRUCT,
                display_text='Multiplayer & Session',
                icon='network',
                formatted_value=session_display,
                struct_type='cGcMultiplayerSession',
            )

            # Session status (primary indicator)
            mp_node.add_child(create_field_node(
                name='session_type',
                value=session_type,
                formatted_value=session_display,
                offset=0,
                size=0,
                type_name='string',
            ))

            # Multiplayer active status
            mp_node.add_child(create_field_node(
                name='multiplayer_active',
                value=mp_active,
                formatted_value='Yes - Online' if mp_active else 'No - Solo',
                offset=0,
                size=1,
                type_name='bool',
            ))

            # Detection method (for debugging)
            mp_node.add_child(create_field_node(
                name='detection_method',
                value=detection_method,
                formatted_value=detection_method if detection_method != 'none' else 'No MP detected',
                offset=0,
                size=0,
                type_name='string',
            ))

            # Game mode
            if 'game_mode' in multiplayer_data:
                mode_id = multiplayer_data.get('game_mode', 0)
                mp_node.add_child(create_field_node(
                    name='game_mode',
                    value=mode_id,
                    formatted_value=f'{game_mode} (ID: {mode_id})',
                    offset=0,
                    size=4,
                    type_name='int32',
                ))

            # Save slot
            if 'save_slot' in multiplayer_data:
                slot = multiplayer_data.get('save_slot', 0)
                mp_node.add_child(create_field_node(
                    name='save_slot',
                    value=slot,
                    formatted_value=f'Slot {slot + 1}' if slot >= 0 else 'Unknown',
                    offset=0,
                    size=4,
                    type_name='int32',
                ))

            # Game paused
            if 'game_paused' in multiplayer_data:
                paused = multiplayer_data.get('game_paused', False)
                mp_node.add_child(create_field_node(
                    name='game_paused',
                    value=paused,
                    formatted_value='Yes' if paused else 'No',
                    offset=0,
                    size=1,
                    type_name='bool',
                ))

            # Location type
            if 'location_type' in multiplayer_data:
                loc_type = multiplayer_data.get('location_type', 0)
                mp_node.add_child(create_field_node(
                    name='location_type',
                    value=loc_type,
                    formatted_value=f'0x{loc_type:X} ({loc_type})',
                    offset=0,
                    size=4,
                    type_name='int32',
                ))

            # In Anomaly (Nexus)
            if 'in_anomaly' in multiplayer_data:
                in_anomaly = multiplayer_data.get('in_anomaly', False)
                mp_node.add_child(create_field_node(
                    name='in_anomaly',
                    value=in_anomaly,
                    formatted_value='Yes - In Nexus' if in_anomaly else 'No',
                    offset=0,
                    size=1,
                    type_name='bool',
                ))

            # Network players detected
            if 'network_players_detected' in multiplayer_data:
                np_count = multiplayer_data.get('network_players_detected', 0)
                if np_count > 0:
                    mp_node.add_child(create_field_node(
                        name='network_players_detected',
                        value=np_count,
                        formatted_value=f'{np_count} players detected',
                        offset=0,
                        size=4,
                        type_name='int32',
                    ))

            # Network player names (if any)
            player_names = multiplayer_data.get('network_player_names', [])
            if player_names:
                names_str = ', '.join(player_names[:5])  # Limit to first 5
                if len(player_names) > 5:
                    names_str += f' (+{len(player_names) - 5} more)'
                mp_node.add_child(create_field_node(
                    name='network_player_names',
                    value=player_names,
                    formatted_value=names_str,
                    offset=0,
                    size=0,
                    type_name='string[]',
                ))

            # Network players list (full details)
            network_players = multiplayer_data.get('network_players', [])
            if network_players:
                players_node = TreeNode(
                    name='network_players',
                    node_type=NodeType.ARRAY,
                    display_text='Network Players',
                    icon='players',
                    formatted_value=f'{len(network_players)} player(s)',
                    struct_type='NetworkPlayerArray',
                )
                for player in network_players:
                    player_name = player.get('name', 'Unknown')
                    player_status = player.get('status', 'unknown')
                    status_icon = 'active' if player_status == 'active' else 'inactive'

                    player_node = TreeNode(
                        name=player_name,
                        node_type=NodeType.STRUCT,
                        display_text=f'{player_name} ({player_status})',
                        icon=status_icon,
                        formatted_value=player_status,
                        struct_type='NetworkPlayer',
                    )

                    # Add player name
                    player_node.add_child(create_field_node(
                        name='name',
                        value=player_name,
                        formatted_value=player_name,
                        offset=0,
                        size=0,
                        type_name='string',
                    ))

                    # Add status
                    player_node.add_child(create_field_node(
                        name='status',
                        value=player_status,
                        formatted_value=player_status,
                        offset=0,
                        size=0,
                        type_name='string',
                    ))

                    # Add player type (v3.6.3)
                    player_type = player.get('player_type', '')
                    if player_type:
                        player_node.add_child(create_field_node(
                            name='player_type',
                            value=player_type,
                            formatted_value=player_type,
                            offset=0,
                            size=0,
                            type_name='string',
                        ))

                    # Add building class (v3.6.3)
                    building_class = player.get('building_class', 0)
                    if building_class:
                        player_node.add_child(create_field_node(
                            name='building_class',
                            value=building_class,
                            formatted_value=f'0x{building_class:X} ({building_class})',
                            offset=0,
                            size=4,
                            type_name='int32',
                        ))

                    # Add detection source (v3.6.3)
                    detection_source = player.get('detection_source', '')
                    if detection_source:
                        player_node.add_child(create_field_node(
                            name='detection_source',
                            value=detection_source,
                            formatted_value=detection_source,
                            offset=0,
                            size=0,
                            type_name='string',
                        ))

                    # Add subtitle if present
                    subtitle = player.get('subtitle', '')
                    if subtitle:
                        player_node.add_child(create_field_node(
                            name='subtitle',
                            value=subtitle,
                            formatted_value=subtitle,
                            offset=0,
                            size=0,
                            type_name='string',
                        ))

                    # Add position if present
                    position = player.get('position', {})
                    if position:
                        pos_str = f"({position.get('x', 0):.1f}, {position.get('y', 0):.1f}, {position.get('z', 0):.1f})"
                        pos_node = TreeNode(
                            name='position',
                            node_type=NodeType.STRUCT,
                            display_text='Position',
                            icon='location',
                            formatted_value=pos_str,
                            struct_type='Vector3f',
                        )
                        for coord_name in ['x', 'y', 'z']:
                            coord_val = position.get(coord_name, 0)
                            pos_node.add_child(create_field_node(
                                name=coord_name,
                                value=coord_val,
                                formatted_value=f'{coord_val:.3f}',
                                offset=0,
                                size=4,
                                type_name='float',
                            ))
                        player_node.add_child(pos_node)

                    # Add timestamps
                    detected_at = player.get('detected_at', '')
                    if detected_at:
                        player_node.add_child(create_field_node(
                            name='detected_at',
                            value=detected_at,
                            formatted_value=detected_at,
                            offset=0,
                            size=0,
                            type_name='string',
                        ))

                    left_at = player.get('left_at', '')
                    if left_at:
                        player_node.add_child(create_field_node(
                            name='left_at',
                            value=left_at,
                            formatted_value=left_at,
                            offset=0,
                            size=0,
                            type_name='string',
                        ))

                    players_node.add_child(player_node)

                mp_node.add_child(players_node)

            # Player bases list (v3.7.0)
            player_bases = multiplayer_data.get('player_bases', [])
            if player_bases:
                bases_node = TreeNode(
                    name='player_bases',
                    node_type=NodeType.ARRAY,
                    display_text='Nearby Player Bases',
                    icon='base',
                    formatted_value=f'{len(player_bases)} base(s)',
                    struct_type='PlayerBaseArray',
                )

                # Sort bases by distance (closest first)
                sorted_bases = sorted(player_bases, key=lambda b: b.get('distance', float('inf')))

                for base in sorted_bases:
                    base_name = base.get('name', 'Unknown Base')
                    position = base.get('position', {})
                    distance = base.get('distance', 0)

                    # Format position for display
                    pos_str = f"({position.get('x', 0):.0f}, {position.get('y', 0):.0f}, {position.get('z', 0):.0f})"

                    base_node = TreeNode(
                        name=base_name,
                        node_type=NodeType.STRUCT,
                        display_text=base_name,
                        icon='base',
                        formatted_value=pos_str,
                        struct_type='PlayerBase',
                    )

                    # Add base name
                    base_node.add_child(create_field_node(
                        name='name',
                        value=base_name,
                        formatted_value=base_name,
                        offset=0,
                        size=0,
                        type_name='string',
                    ))

                    # Add position
                    if position:
                        pos_node = TreeNode(
                            name='position',
                            node_type=NodeType.STRUCT,
                            display_text='Position',
                            icon='location',
                            formatted_value=pos_str,
                            struct_type='Vector3f',
                        )
                        for coord_name in ['x', 'y', 'z']:
                            coord_val = position.get(coord_name, 0)
                            pos_node.add_child(create_field_node(
                                name=coord_name,
                                value=coord_val,
                                formatted_value=f'{coord_val:.1f}',
                                offset=0,
                                size=4,
                                type_name='float',
                            ))
                        base_node.add_child(pos_node)

                    # Add distance
                    base_node.add_child(create_field_node(
                        name='distance',
                        value=distance,
                        formatted_value=f'{distance:.0f}u',
                        offset=0,
                        size=4,
                        type_name='float',
                    ))

                    # Add building class
                    building_class = base.get('building_class', 0)
                    base_node.add_child(create_field_node(
                        name='building_class',
                        value=building_class,
                        formatted_value=f'0x{building_class:X}',
                        offset=0,
                        size=4,
                        type_name='int32',
                    ))

                    bases_node.add_child(base_node)

                mp_node.add_child(bases_node)

            # ACTUAL Persistent Bases (v3.8.0 - from PlayerStateData, not HUD markers)
            actual_bases = multiplayer_data.get('actual_bases', [])
            if actual_bases:
                actual_bases_node = TreeNode(
                    name='actual_bases',
                    node_type=NodeType.ARRAY,
                    display_text='Actual Persistent Bases (PlayerStateData)',
                    icon='base',
                    formatted_value=f'{len(actual_bases)} base(s) with glyphs',
                    struct_type='PersistentBaseArray',
                )

                for base in actual_bases:
                    base_name = base.get('name', 'Unknown Base')
                    glyph_code = base.get('glyph_code', 'N/A')
                    position = base.get('position', {})
                    address = base.get('address', 'N/A')

                    # Format position for display
                    pos_str = f"({position.get('x', 0):.0f}, {position.get('y', 0):.0f}, {position.get('z', 0):.0f})"

                    actual_base_node = TreeNode(
                        name=base_name,
                        node_type=NodeType.STRUCT,
                        display_text=f'{base_name} [{glyph_code}]',
                        icon='base',
                        formatted_value=pos_str,
                        struct_type='cGcPersistentBase',
                    )

                    # Add base name
                    actual_base_node.add_child(create_field_node(
                        name='name',
                        value=base_name,
                        formatted_value=base_name,
                        offset=0x208,
                        size=64,
                        type_name='cTkFixedString0x40',
                    ))

                    # Add glyph code
                    actual_base_node.add_child(create_field_node(
                        name='glyph_code',
                        value=glyph_code,
                        formatted_value=glyph_code,
                        offset=0,
                        size=0,
                        type_name='computed',
                    ))

                    # Add memory address (for potential modification)
                    actual_base_node.add_child(create_field_node(
                        name='memory_address',
                        value=address,
                        formatted_value=address,
                        offset=0,
                        size=8,
                        type_name='pointer',
                    ))

                    # Add position
                    if position:
                        pos_node = TreeNode(
                            name='position',
                            node_type=NodeType.STRUCT,
                            display_text='Position',
                            icon='location',
                            formatted_value=pos_str,
                            struct_type='cTkPhysRelVec3',
                        )
                        for coord_name in ['x', 'y', 'z']:
                            coord_val = position.get(coord_name, 0)
                            pos_node.add_child(create_field_node(
                                name=coord_name,
                                value=coord_val,
                                formatted_value=f'{coord_val:.1f}',
                                offset=0x10 + ['x', 'y', 'z'].index(coord_name) * 4,
                                size=4,
                                type_name='float',
                            ))
                        actual_base_node.add_child(pos_node)

                    # Add galactic address
                    ga = base.get('galactic_address', {})
                    if ga:
                        ga_node = TreeNode(
                            name='galactic_address',
                            node_type=NodeType.STRUCT,
                            display_text='Galactic Address',
                            icon='location',
                            formatted_value=glyph_code,
                            struct_type='cGcUniverseAddressData',
                        )
                        for ga_field in ['voxel_x', 'voxel_y', 'voxel_z', 'system_index', 'planet_index']:
                            ga_val = ga.get(ga_field, 0)
                            ga_node.add_child(create_field_node(
                                name=ga_field,
                                value=ga_val,
                                formatted_value=str(ga_val),
                                offset=0x50,
                                size=2,
                                type_name='int16',
                            ))
                        actual_base_node.add_child(ga_node)

                    actual_bases_node.add_child(actual_base_node)

                mp_node.add_child(actual_bases_node)

            # Network Player State Data (v3.8.0 - actual player state, not just markers)
            network_state = multiplayer_data.get('network_player_state', [])
            if network_state:
                net_state_node = TreeNode(
                    name='network_player_state',
                    node_type=NodeType.ARRAY,
                    display_text='Network Player State Data',
                    icon='person',
                    formatted_value=f'{len(network_state)} player(s)',
                    struct_type='NetworkPlayerStateArray',
                )

                for player in network_state:
                    player_name = player.get('name', 'Unknown')
                    source = player.get('source', 'unknown')
                    address = player.get('address', 'N/A')

                    player_state_node = TreeNode(
                        name=player_name,
                        node_type=NodeType.STRUCT,
                        display_text=f'{player_name} (state data)',
                        icon='person',
                        formatted_value=f'source: {source}',
                        struct_type='NetworkPlayerState',
                    )

                    for key, value in player.items():
                        player_state_node.add_child(create_field_node(
                            name=key,
                            value=value,
                            formatted_value=str(value),
                            offset=0,
                            size=0,
                            type_name='auto',
                        ))

                    net_state_node.add_child(player_state_node)

                mp_node.add_child(net_state_node)

            # Debug info (collapsible sub-node)
            debug_info = multiplayer_data.get('debug_info', {})
            if debug_info:
                debug_node = TreeNode(
                    name='debug_info',
                    node_type=NodeType.STRUCT,
                    display_text='Debug Info',
                    icon='debug',
                    formatted_value=f'{len(debug_info)} fields',
                    struct_type='DebugData',
                )
                for key, value in debug_info.items():
                    if isinstance(value, list):
                        value_str = ', '.join(str(v) for v in value[:5])
                        if len(value) > 5:
                            value_str += f' (+{len(value) - 5} more)'
                    else:
                        value_str = str(value)
                    debug_node.add_child(create_field_node(
                        name=key,
                        value=value,
                        formatted_value=value_str,
                        offset=0,
                        size=0,
                        type_name='debug',
                    ))
                mp_node.add_child(debug_node)

            category.add_child(mp_node)

        return category

    def _build_system_node(self, cached_data: dict) -> Optional[TreeNode]:
        """Build solar system tree node from cached data."""
        category = create_category_node('Solar System', 'Solar System Data')

        # Check for system data
        raw_data = cached_data.get('raw_data', {})
        system_data = raw_data.get('system', {})
        location_data = raw_data.get('location', {})
        planets_data = raw_data.get('planets', [])

        # Add Location node
        if location_data:
            galaxy_name = location_data.get('galaxy_name', 'Unknown')
            glyph_code = location_data.get('glyph_code', 'N/A')
            loc_node = TreeNode(
                name='Location',
                node_type=NodeType.STRUCT,
                display_text='Current Location',
                icon='location',
                formatted_value=f'{galaxy_name} | Glyphs: {glyph_code}',
                struct_type='cGcUniverseAddressData',
            )
            for loc_name, loc_value in location_data.items():
                if loc_value is not None:
                    loc_node.add_child(create_field_node(
                        name=loc_name,
                        value=loc_value,
                        formatted_value=str(loc_value),
                        offset=0,
                        size=4,
                        type_name='int32' if isinstance(loc_value, int) else 'string',
                    ))
            category.add_child(loc_node)

        # Add System Info node
        planet_count = system_data.get('planet_count', 0) if system_data else 0
        info_node = TreeNode(
            name='Info',
            node_type=NodeType.STRUCT,
            display_text='System Info',
            icon='planet',
            formatted_value=f'{planet_count} planets' if system_data else 'No data',
            struct_type='cGcSolarSystemData',
        )

        if system_data:
            for sys_name, sys_value in system_data.items():
                if sys_value is not None:
                    info_node.add_child(create_field_node(
                        name=sys_name,
                        value=sys_value,
                        formatted_value=str(sys_value),
                        offset=0,
                        size=4,
                        type_name='int32',
                    ))
        else:
            info_node.add_child(create_field_node(
                name='status',
                value='No system data',
                formatted_value='System data not available - click Refresh Data',
                offset=0,
                size=0,
                type_name='status',
            ))

        category.add_child(info_node)

        # =====================================================
        # v2.0: Add captured planet nodes with full data
        # =====================================================
        if planets_data:
            planets_node = TreeNode(
                name='Planets',
                node_type=NodeType.STRUCT,
                display_text=f'Planets ({len(planets_data)})',
                icon='planet',
                formatted_value=f'{len(planets_data)} planets captured',
                struct_type='PlanetArray',
            )

            for planet in planets_data:
                planet_idx = planet.get('planet_index', 0)
                planet_name = planet.get('planet_name', '') or f"Planet {planet_idx}"
                is_moon = planet.get('is_moon', False)
                biome = planet.get('biome', 'Unknown')
                weather = planet.get('weather', 'Unknown')
                flora = planet.get('flora', 'Unknown')
                fauna = planet.get('fauna', 'Unknown')

                # Create planet node with summary info
                planet_node = TreeNode(
                    name=f'planet_{planet_idx}',
                    node_type=NodeType.STRUCT,
                    display_text=f"{'[Moon] ' if is_moon else ''}{planet_name} - {biome}",
                    icon='moon' if is_moon else 'planet',
                    formatted_value=f'{biome} | {weather} | Flora: {flora} | Fauna: {fauna}',
                    struct_type='Moon' if is_moon else 'Planet',
                )

                # Add biome info
                biome_subtype = planet.get('biome_subtype', 'Unknown')
                biome_node = TreeNode(
                    name='Biome',
                    node_type=NodeType.STRUCT,
                    display_text='Biome Info',
                    icon='terrain',
                    formatted_value=f'{biome} ({biome_subtype})',
                    struct_type='BiomeInfo',
                )
                biome_node.add_child(create_field_node(
                    name='biome', value=biome,
                    formatted_value=biome, offset=0, size=4, type_name='string',
                ))
                biome_node.add_child(create_field_node(
                    name='biome_subtype', value=biome_subtype,
                    formatted_value=biome_subtype, offset=0, size=4, type_name='string',
                ))
                biome_node.add_child(create_field_node(
                    name='planet_size', value=planet.get('planet_size', 'Unknown'),
                    formatted_value=planet.get('planet_size', 'Unknown'), offset=0, size=4, type_name='string',
                ))
                biome_node.add_child(create_field_node(
                    name='is_moon', value=is_moon,
                    formatted_value=str(is_moon), offset=0, size=1, type_name='bool',
                ))
                planet_node.add_child(biome_node)

                # Add weather info
                storm_freq = planet.get('storm_frequency', 'Unknown')
                weather_node = TreeNode(
                    name='Weather',
                    node_type=NodeType.STRUCT,
                    display_text='Weather',
                    icon='weather',
                    formatted_value=f'{weather} (Storms: {storm_freq})',
                    struct_type='WeatherInfo',
                )
                weather_node.add_child(create_field_node(
                    name='weather', value=weather,
                    formatted_value=weather, offset=0, size=4, type_name='string',
                ))
                weather_node.add_child(create_field_node(
                    name='storm_frequency', value=storm_freq,
                    formatted_value=storm_freq, offset=0, size=4, type_name='string',
                ))
                planet_node.add_child(weather_node)

                # Add life info (Flora, Fauna, Sentinels)
                sentinel = planet.get('sentinel', 'Unknown')
                life_node = TreeNode(
                    name='Life',
                    node_type=NodeType.STRUCT,
                    display_text='Flora / Fauna / Sentinels',
                    icon='life',
                    formatted_value=f'Flora: {flora} | Fauna: {fauna} | Sentinels: {sentinel}',
                    struct_type='LifeInfo',
                )
                life_node.add_child(create_field_node(
                    name='flora', value=flora,
                    formatted_value=flora, offset=0, size=4, type_name='string',
                ))
                life_node.add_child(create_field_node(
                    name='fauna', value=fauna,
                    formatted_value=fauna, offset=0, size=4, type_name='string',
                ))
                life_node.add_child(create_field_node(
                    name='sentinels', value=sentinel,
                    formatted_value=sentinel, offset=0, size=4, type_name='string',
                ))
                planet_node.add_child(life_node)

                # Add resources info
                common = planet.get('common_resource', '') or 'N/A'
                uncommon = planet.get('uncommon_resource', '') or 'N/A'
                rare = planet.get('rare_resource', '') or 'N/A'
                resources_node = TreeNode(
                    name='Resources',
                    node_type=NodeType.STRUCT,
                    display_text='Resources',
                    icon='resource',
                    formatted_value=f'Common: {common} | Uncommon: {uncommon} | Rare: {rare}',
                    struct_type='ResourceInfo',
                )
                resources_node.add_child(create_field_node(
                    name='common', value=common,
                    formatted_value=common, offset=0, size=4, type_name='string',
                ))
                resources_node.add_child(create_field_node(
                    name='uncommon', value=uncommon,
                    formatted_value=uncommon, offset=0, size=4, type_name='string',
                ))
                resources_node.add_child(create_field_node(
                    name='rare', value=rare,
                    formatted_value=rare, offset=0, size=4, type_name='string',
                ))
                planet_node.add_child(resources_node)

                planets_node.add_child(planet_node)

            category.add_child(planets_node)
            log_flush(f"_build_system_node: Added {len(planets_data)} planets to tree")
        else:
            # No planets captured yet
            no_planets_node = TreeNode(
                name='Planets',
                node_type=NodeType.STRUCT,
                display_text='Planets (Warp to capture)',
                icon='planet',
                formatted_value='No planets captured yet',
                struct_type='PlanetArray',
            )
            no_planets_node.add_child(create_field_node(
                name='status',
                value='No planets captured',
                formatted_value='Warp to a new system to capture planet data',
                offset=0,
                size=0,
                type_name='status',
            ))
            category.add_child(no_planets_node)

        return category

    # =========================================================================
    # v3.0: General Purpose Browser Node Builders
    # =========================================================================

    def _build_game_objects_node(self, game_objects: dict) -> TreeNode:
        """Build tree node showing ALL available gameData entry points.

        This is the core of the general-purpose browser - it shows every
        object available from nmspy's gameData singleton.
        """
        category = create_category_node('Game Objects', f'All Game Objects ({len(game_objects)})')

        # Sort by name for easier navigation
        sorted_objects = sorted(game_objects.items(), key=lambda x: x[0])

        for obj_name, obj_info in sorted_objects:
            obj_type = obj_info.get('type', 'Unknown')
            obj_addr = obj_info.get('address_hex', 'N/A')
            has_data = obj_info.get('has_data', False)
            attributes = obj_info.get('attributes', [])

            # Create object node with proper values for detail panel
            obj_node = TreeNode(
                name=obj_name,
                node_type=NodeType.STRUCT,
                display_text=f"{obj_name} ({obj_type})",
                icon='struct' if has_data else 'null',
                struct_type=obj_type,
                address=obj_info.get('address', 0),
                formatted_value=f'{obj_type} @ {obj_addr}',
            )

            # Add address info
            obj_node.add_child(create_field_node(
                name='address',
                value=obj_info.get('address', 0),
                formatted_value=obj_addr,
                offset=0,
                size=8,
                type_name='pointer',
            ))

            obj_node.add_child(create_field_node(
                name='type',
                value=obj_type,
                formatted_value=obj_type,
                offset=0,
                size=0,
            ))

            # Add available attributes as children
            if attributes:
                attrs_node = TreeNode(
                    name='attributes',
                    node_type=NodeType.STRUCT,
                    display_text=f'Attributes ({len(attributes)})',
                    icon='list',
                    formatted_value=f'{len(attributes)} available attributes',
                    struct_type='attributes_list',
                )

                for attr_name in attributes[:100]:  # Limit to first 100
                    attrs_node.add_child(create_field_node(
                        name=attr_name,
                        value=attr_name,
                        formatted_value='(expandable attribute)',
                        offset=0,
                        size=0,
                        type_name='attribute',
                    ))

                obj_node.add_child(attrs_node)

            category.add_child(obj_node)

        return category

    def _build_struct_types_node(self, struct_types: list) -> TreeNode:
        """Build tree node showing ALL available nmspy struct types.

        v3.1: Now includes FULL FIELD INFORMATION with offsets, sizes, and types.
        This lets users browse what struct definitions are available
        for memory mapping - useful for mod development.
        """
        # Count total fields
        total_fields = sum(s.get('field_count', 0) for s in struct_types)
        category = create_category_node(
            'Struct Types',
            f'All Struct Types ({len(struct_types)} structs, {total_fields} fields)'
        )

        # Group by module
        types_module = {}
        exported_module = {}

        for struct in struct_types:
            name = struct.get('name', '')
            module = struct.get('module', '')
            if module == 'types':
                types_module[name] = struct
            else:
                exported_module[name] = struct

        # Add types module
        if types_module:
            types_fields = sum(s.get('field_count', 0) for s in types_module.values())
            types_node = TreeNode(
                name='nmspy.data.types',
                node_type=NodeType.CATEGORY,
                display_text=f'nmspy.data.types ({len(types_module)} structs, {types_fields} fields)',
                icon='folder',
                formatted_value=f'{len(types_module)} structs, {types_fields} total fields',
                struct_type='module',
            )

            for name in sorted(types_module.keys()):
                struct_node = self._build_single_struct_node(types_module[name])
                types_node.add_child(struct_node)

            category.add_child(types_node)

        # Add exported_types module
        if exported_module:
            exported_fields = sum(s.get('field_count', 0) for s in exported_module.values())
            exported_node = TreeNode(
                name='nmspy.data.exported_types',
                node_type=NodeType.CATEGORY,
                display_text=f'nmspy.data.exported_types ({len(exported_module)} structs, {exported_fields} fields)',
                icon='folder',
                formatted_value=f'{len(exported_module)} structs, {exported_fields} total fields',
                struct_type='module',
            )

            for name in sorted(exported_module.keys()):
                struct_node = self._build_single_struct_node(exported_module[name])
                exported_node.add_child(struct_node)

            category.add_child(exported_node)

        return category

    def _build_single_struct_node(self, struct: dict) -> TreeNode:
        """Build a tree node for a single struct with all its fields.

        Args:
            struct: Dictionary with struct info including 'fields' list

        Returns:
            TreeNode representing the struct with all field children
        """
        name = struct.get('name', 'Unknown')
        size = struct.get('size', 0)
        size_hex = struct.get('size_hex', '0x0')
        field_count = struct.get('field_count', 0)
        fields = struct.get('fields', [])

        # Create struct node with field count in display
        # IMPORTANT: Set all properties so detail panel can display them properly
        struct_node = TreeNode(
            name=name,
            node_type=NodeType.STRUCT,
            display_text=f'{name} [{size_hex}, {field_count} fields]',
            icon='struct',
            struct_type=name,  # Set struct type for detail panel Type column
            size=size,  # Set size for detail panel Size display
            formatted_value=f'{size} bytes ({size_hex}), {field_count} fields',  # For Value column
        )

        # Add struct size as first child
        struct_node.add_child(create_field_node(
            name='_struct_size',
            value=size,
            formatted_value=f'{size} bytes ({size_hex})',
            offset=0,
            size=4,
            type_name='meta',
        ))

        # Add all fields with full details
        for field in fields:
            field_name = field.get('name', '?')
            field_offset = field.get('offset', 0)
            field_offset_hex = field.get('offset_hex', '?')
            field_size = field.get('size', 0)
            field_size_hex = field.get('size_hex', '?')
            field_type = field.get('type', '?')
            is_pointer = field.get('is_pointer', False)
            is_array = field.get('is_array', False)
            array_len = field.get('array_length', 0)
            is_struct = field.get('is_struct', False)

            # Build display text with all info
            # Format: name @ offset [size] : type
            display_parts = [f'{field_name}']

            # Add type indicator icons
            type_indicators = []
            if is_pointer:
                type_indicators.append('PTR')
            if is_array:
                type_indicators.append(f'ARR[{array_len}]')
            if is_struct:
                type_indicators.append('STRUCT')

            if type_indicators:
                display_parts.append(f" ({', '.join(type_indicators)})")

            # Choose icon based on field type
            if is_pointer:
                icon = 'pointer'
            elif is_array:
                icon = 'array'
            elif is_struct:
                icon = 'struct'
            else:
                icon = 'field'

            # Create the field node
            field_node = create_field_node(
                name=field_name,
                value=f'{field_type}',
                formatted_value=f'@ {field_offset_hex} [{field_size_hex}] : {field_type}',
                offset=field_offset,
                size=field_size,
                type_name=field_type,
            )

            # Add detailed info as children of the field
            details_node = TreeNode(
                name=f'{field_name}_details',
                node_type=NodeType.STRUCT,
                display_text=f'Details',
                icon='info',
            )

            details_node.add_child(create_field_node(
                name='offset',
                value=field_offset,
                formatted_value=f'{field_offset} ({field_offset_hex})',
                offset=0,
                size=4,
            ))

            details_node.add_child(create_field_node(
                name='size',
                value=field_size,
                formatted_value=f'{field_size} bytes ({field_size_hex})',
                offset=0,
                size=4,
            ))

            details_node.add_child(create_field_node(
                name='type',
                value=field_type,
                formatted_value=field_type,
                offset=0,
                size=0,
            ))

            if is_pointer:
                details_node.add_child(create_field_node(
                    name='is_pointer',
                    value=True,
                    formatted_value='Yes - dereference to follow',
                    offset=0,
                    size=0,
                ))

            if is_array:
                details_node.add_child(create_field_node(
                    name='array_length',
                    value=array_len,
                    formatted_value=f'{array_len} elements',
                    offset=0,
                    size=0,
                ))

            if is_struct:
                details_node.add_child(create_field_node(
                    name='is_nested_struct',
                    value=True,
                    formatted_value=f'Yes - expand to see {field_type} fields',
                    offset=0,
                    size=0,
                ))

            field_node.add_child(details_node)
            struct_node.add_child(field_node)

        return struct_node

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
