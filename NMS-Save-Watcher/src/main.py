"""
Main entry point for Haven Watcher.
Monitors live extraction data from Haven Extractor game mod.
"""

import sys
import logging
import threading
import signal
from pathlib import Path

from .config import load_config, validate_config
from .watcher import LiveExtractionWatcher
from .api_client import SubmissionResult, SubmissionStatus
from .notifications import create_notifier
from .dashboard import run_dashboard, set_watcher


def setup_logging(config: dict):
    """Configure logging based on settings."""
    debug_config = config.get('debug', {})

    level = getattr(logging, debug_config.get('log_level', 'INFO').upper())

    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File logging if enabled
    if debug_config.get('enabled', False):
        log_file = Path(__file__).parent.parent / debug_config.get('log_file', 'watcher.log')
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logging.getLogger().addHandler(file_handler)


def main():
    """Main entry point."""
    print("=" * 50)
    print("  Haven Watcher v2.1.0")
    print("  Live Extraction Mode (Smart Deduplication)")
    print("  Companion App for Voyagers Haven")
    print("=" * 50)
    print()
    print("  Changes in v2.1.0:")
    print("    - Smart deduplication: 1 system = 1 queue entry")
    print("    - Only queues NEW systems or planet count increases")
    print("    - Clearer logging distinguishes new vs updated")
    print()

    # Load configuration
    print("[*] Loading configuration...")
    config = load_config()

    # Setup logging
    setup_logging(config)
    logger = logging.getLogger('nms_watcher.main')

    # Validate configuration
    is_valid, errors = validate_config(config)
    if not is_valid:
        print("[!] Configuration issues:")
        for error in errors:
            print(f"    - {error}")
        print()
        print("[!] Please configure via the dashboard or edit config.json")
        print("[*] Starting dashboard anyway for configuration...")

    # Create notifier
    notifier = create_notifier(config)

    # Callback for submission results
    def on_submission(result: SubmissionResult):
        if result.status == SubmissionStatus.SUCCESS:
            notifier.notify_success(result.system_name, result.glyph_code)
            logger.info(f"SUCCESS: {result.system_name} [{result.glyph_code}]")
        elif result.status == SubmissionStatus.DUPLICATE:
            notifier.notify_duplicate(result.system_name, result.glyph_code)
            logger.info(f"DUPLICATE: {result.system_name} [{result.glyph_code}]")
        elif result.status == SubmissionStatus.QUEUED:
            notifier.notify_queued(result.system_name)
            logger.info(f"QUEUED: {result.system_name} [{result.glyph_code}]")
        else:
            notifier.notify_error(f"{result.system_name}: {result.message}")
            logger.error(f"ERROR: {result.system_name} - {result.message}")

    # Callback for errors
    def on_error(message: str):
        notifier.notify_error(message)
        logger.error(message)

    # Create watcher (now LiveExtractionWatcher)
    watcher = LiveExtractionWatcher(
        config,
        on_submission=on_submission,
        on_error=on_error
    )

    # Get extraction output directory
    extraction_config = config.get('live_extraction', {})
    output_dir = extraction_config.get('output_dir')
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = Path.home() / "Documents" / "Haven-Extractor"

    # Start watcher if enabled
    if extraction_config.get('enabled', True):
        print(f"[*] Starting live extraction watcher...")
        print(f"    Monitoring: {output_path}")
        print(f"    Poll interval: {extraction_config.get('poll_interval', 2.0)}s")
        print()
        print("[*] How it works:")
        print("    1. Launch NMS via NMS.py with Haven Extractor mod")
        print("    2. Warp to a new system in-game")
        print("    3. Haven Extractor captures system data")
        print("    4. This watcher submits to Haven Control Room")
        print()
        startup_delay = extraction_config.get('startup_delay', 60.0)
        print(f"[*] LEARNING MODE: Watcher will ignore all data for {startup_delay}s")
        print("    Start the game during this time - then only NEW discoveries are collected.")
        print()

        if watcher.start():
            notifier.notify_watcher_started(str(output_path))
            print("[+] Watcher started successfully")
        else:
            print("[!] Failed to start watcher")
    else:
        print("[*] Watcher disabled in config")

    # Start dashboard in separate thread
    dashboard_host = config.get('dashboard', {}).get('host', '127.0.0.1')
    dashboard_port = config.get('dashboard', {}).get('port', 8006)

    print()
    print(f"[*] Starting dashboard at http://{dashboard_host}:{dashboard_port}")
    print()
    print("-" * 50)
    print("  Dashboard: http://{}:{}".format(dashboard_host, dashboard_port))
    print("  Press Ctrl+C to stop")
    print("-" * 50)
    print()

    # Handle shutdown
    shutdown_event = threading.Event()

    def signal_handler(signum, frame):
        print()
        print("[*] Shutting down...")
        watcher.stop()
        notifier.notify_watcher_stopped()
        shutdown_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run dashboard (this blocks)
    try:
        run_dashboard(config, watcher)
    except KeyboardInterrupt:
        pass
    finally:
        watcher.stop()
        print("[*] Shutdown complete")


if __name__ == '__main__':
    main()
