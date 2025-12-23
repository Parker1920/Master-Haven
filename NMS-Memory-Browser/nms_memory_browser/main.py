"""NMS Memory Browser - Main entry point.

This is a pyMHF mod that provides a GUI for browsing game memory.
Launch with: pymhf run c:\\Master-Haven\\NMS-Memory-Browser
"""

# /// script
# [tool.pymhf]
# exe = "NMS.exe"
# steam_gameid = 275850
# start_exe = true
# ///

import sys
import logging
import traceback
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add the parent directory to sys.path so we can import our package
_this_dir = Path(__file__).parent
_parent_dir = _this_dir.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from pymhf import Mod
from pymhf.gui.decorators import gui_button

# Configure file-based logging for debugging crashes
_log_dir = _parent_dir / "logs"
_log_dir.mkdir(exist_ok=True)
_log_file = _log_dir / f"memory_browser_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create a file handler that flushes immediately
_file_handler = logging.FileHandler(_log_file, encoding='utf-8')
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Set up both console and file logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        _file_handler,
        logging.StreamHandler(sys.stdout)
    ]
)
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


log_flush(f"=== NMS Memory Browser Starting - Log: {_log_file} ===")


class GUIThread(threading.Thread):
    """Thread that runs the Qt event loop."""

    def __init__(self, game_data_provider=None):
        super().__init__(daemon=True)
        self._app = None
        self._window = None
        self._ready = threading.Event()
        self._stop_requested = False
        self._game_data_provider = game_data_provider  # Callback to get data from main thread

    def run(self):
        """Run the Qt event loop in this thread."""
        try:
            log_flush("GUIThread: Starting Qt event loop thread...")

            from PyQt6.QtWidgets import QApplication
            log_flush("GUIThread: PyQt6 imported")

            # Create QApplication in this thread
            self._app = QApplication([])
            log_flush("GUIThread: QApplication created")

            # Import and create main window with data provider
            from nms_memory_browser.ui.main_window import MainWindow
            log_flush("GUIThread: MainWindow imported")

            self._window = MainWindow(game_data_provider=self._game_data_provider)
            log_flush("GUIThread: MainWindow created")

            self._window.show()
            self._window.raise_()
            self._window.activateWindow()
            log_flush("GUIThread: Window shown")

            # Signal that we're ready
            self._ready.set()
            log_flush("GUIThread: Ready, starting event loop...")

            # Run the event loop
            self._app.exec()
            log_flush("GUIThread: Event loop ended")

        except Exception as e:
            log_flush(f"GUIThread: FAILED - {e}", "error")
            log_flush(f"GUIThread: Traceback:\n{traceback.format_exc()}", "error")
            self._ready.set()  # Unblock waiting threads even on error

    def stop(self):
        """Request the thread to stop."""
        if self._app:
            self._app.quit()


class NMSMemoryBrowser(Mod):
    """NMS Memory Browser mod.

    Provides a PyQt6 GUI for browsing game memory structures.
    """

    __author__ = "Master Haven"
    __version__ = "1.0.0"
    __description__ = "Live memory browser for No Man's Sky"

    def __init__(self):
        super().__init__()
        self._gui_thread: Optional[GUIThread] = None
        self._cached_game_data = {}  # Cache data collected from main thread
        self._data_lock = threading.Lock()
        logger.info("NMS Memory Browser initialized")

    def _collect_game_data(self) -> dict:
        """Collect game data from nmspy - MUST be called from pyMHF thread.

        This runs in the main pyMHF thread where gameData is properly accessible.
        """
        log_flush("=== _collect_game_data: Collecting from pyMHF thread ===")
        result = {
            'player_state': None,
            'game_state': None,
            'simulation': None,
            'solar_system': None,
            'player': None,
            'environment': None,
            'raw_data': {},
        }

        try:
            from nmspy.common import gameData
            log_flush(f"gameData type: {type(gameData)}")

            # Log available attributes first
            attrs = [a for a in dir(gameData) if not a.startswith('_')]
            log_flush(f"gameData available attrs: {attrs}")

            # Try to access each attribute and log what we get
            for attr_name in ['player_state', 'game_state', 'simulation', 'player', 'environment']:
                try:
                    log_flush(f"Trying to access gameData.{attr_name}...")
                    attr_val = getattr(gameData, attr_name, None)
                    log_flush(f"  gameData.{attr_name} = {type(attr_val) if attr_val else 'None'}")

                    if attr_val is not None:
                        result[attr_name] = attr_val

                        # If it's player_state, extract the data
                        if attr_name == 'player_state':
                            log_flush(f"  Extracting player data from player_state...")
                            try:
                                # Log what attributes player_state has
                                ps_attrs = [a for a in dir(attr_val) if not a.startswith('_')][:20]
                                log_flush(f"  player_state attrs (first 20): {ps_attrs}")

                                result['raw_data']['player'] = {
                                    'health': getattr(attr_val, 'miHealth', None),
                                    'shield': getattr(attr_val, 'miShield', None),
                                    'units': getattr(attr_val, 'muUnits', None),
                                    'nanites': getattr(attr_val, 'muNanites', None),
                                }
                                log_flush(f"  Player data extracted: {result['raw_data']['player']}")
                            except Exception as e:
                                log_flush(f"  Error extracting player data: {e}", "warning")
                except Exception as e:
                    log_flush(f"  Error accessing {attr_name}: {e}", "warning")

        except Exception as e:
            log_flush(f"Error collecting game data: {e}", "error")
            log_flush(traceback.format_exc(), "error")

        # Cache the data thread-safely
        with self._data_lock:
            self._cached_game_data = result

        log_flush(f"=== _collect_game_data: Done, cached {len(result['raw_data'])} items ===")
        return result

    def get_cached_data(self) -> dict:
        """Get cached game data (thread-safe for GUI access)."""
        with self._data_lock:
            return self._cached_game_data.copy()

    @gui_button("Open Memory Browser")
    def open_browser(self):
        """Open the memory browser window."""
        log_flush("=== Open Memory Browser button clicked ===")
        try:
            # Collect data in the pyMHF thread FIRST
            self._collect_game_data()

            self._launch_gui()
        except Exception as e:
            log_flush(f"Failed to open browser: {e}", "error")
            log_flush(f"Traceback:\n{traceback.format_exc()}", "error")

    def _launch_gui(self):
        """Launch the PyQt6 GUI in a separate thread."""
        # Check if thread already running
        if self._gui_thread and self._gui_thread.is_alive():
            log_flush("GUI thread already running, bringing window to front...")
            if self._gui_thread._window:
                # Can't directly call Qt methods from another thread
                # The window should already be visible
                log_flush("Window should already be visible")
            return

        log_flush("Starting new GUI thread...")
        # Pass the data provider callback
        self._gui_thread = GUIThread(game_data_provider=self.get_cached_data)
        self._gui_thread.start()

        # Wait for window to be ready (with timeout)
        if self._gui_thread._ready.wait(timeout=10.0):
            log_flush("=== GUI thread started successfully ===")
        else:
            log_flush("GUI thread start timeout!", "error")

    @gui_button("Refresh Data")
    def refresh_data(self):
        """Refresh the browser data."""
        log_flush("=== Refresh Data button clicked ===")

        # Collect fresh data in the pyMHF thread
        self._collect_game_data()

        if self._gui_thread and self._gui_thread._window:
            log_flush("Signaling GUI to refresh...")
            try:
                # The window will use get_cached_data() to get the fresh data
                self._gui_thread._window._on_refresh()
                log_flush("Data refreshed")
            except Exception as e:
                log_flush(f"Refresh failed: {e}", "error")
        else:
            log_flush("Browser window not open", "warning")

    @gui_button("Export Snapshot")
    def export_snapshot(self):
        """Export a memory snapshot."""
        if self._gui_thread and self._gui_thread._window:
            try:
                self._gui_thread._window._on_export()
            except Exception as e:
                log_flush(f"Export failed: {e}", "error")
        else:
            log_flush("Browser window not open - opening first", "warning")
            self._launch_gui()


# Alternative standalone launcher (without pyMHF)
def main():
    """Standalone entry point for testing UI without game."""
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("NMS Memory Browser")

    from nms_memory_browser.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
