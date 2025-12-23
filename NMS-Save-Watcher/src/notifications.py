"""
Windows Notifications for NMS Save Watcher.
Uses win10toast for toast notifications.
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger('nms_watcher.notifications')

# Try to import Windows toast notification library
try:
    from win10toast import ToastNotifier
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False
    logger.warning("win10toast not available - notifications disabled")


class NotificationManager:
    """Manages Windows toast notifications."""

    def __init__(self, config: dict):
        """
        Initialize the notification manager.

        Args:
            config: Notification configuration dict
        """
        self.config = config.get('notifications', {})
        self.enabled = self.config.get('enabled', True) and TOAST_AVAILABLE

        if self.enabled:
            self._toaster = ToastNotifier()
        else:
            self._toaster = None

        self._app_name = "NMS Save Watcher"

    def _show_notification(self, title: str, message: str, duration: int = 5):
        """
        Show a toast notification (runs in background thread).

        Args:
            title: Notification title
            message: Notification body
            duration: Display duration in seconds
        """
        if not self.enabled or not self._toaster:
            return

        def _notify():
            try:
                self._toaster.show_toast(
                    title=title,
                    msg=message,
                    duration=duration,
                    threaded=False
                )
            except Exception as e:
                logger.error(f"Failed to show notification: {e}")

        # Run in background thread to avoid blocking
        thread = threading.Thread(target=_notify, daemon=True)
        thread.start()

    def notify_success(self, system_name: str, glyph_code: str):
        """Notify successful submission."""
        if not self.config.get('on_success', True):
            return

        self._show_notification(
            f"System Submitted",
            f"{system_name}\n{glyph_code}\nSubmitted for approval"
        )

    def notify_duplicate(self, system_name: str, glyph_code: str):
        """Notify duplicate detection."""
        if not self.config.get('on_duplicate', False):
            return

        self._show_notification(
            "Duplicate System",
            f"{system_name}\n{glyph_code}\nAlready in database"
        )

    def notify_error(self, message: str):
        """Notify error."""
        if not self.config.get('on_error', True):
            return

        self._show_notification(
            "Error",
            message,
            duration=10
        )

    def notify_queued(self, system_name: str, count: int = 1):
        """Notify submission queued for offline."""
        if not self.config.get('on_offline_queue', True):
            return

        if count == 1:
            self._show_notification(
                "Submission Queued",
                f"{system_name}\nWill be submitted when online"
            )
        else:
            self._show_notification(
                "Submissions Queued",
                f"{count} systems queued\nWill be submitted when online"
            )

    def notify_queue_processed(self, success_count: int, total: int):
        """Notify queued items processed."""
        if success_count > 0:
            self._show_notification(
                "Queue Processed",
                f"{success_count}/{total} submissions completed"
            )

    def notify_watcher_started(self, save_path: str):
        """Notify watcher started."""
        if not self.enabled:
            return

        self._show_notification(
            "Watcher Started",
            f"Monitoring: {save_path}"
        )

    def notify_watcher_stopped(self):
        """Notify watcher stopped."""
        if not self.enabled:
            return

        self._show_notification(
            "Watcher Stopped",
            "No longer monitoring save files"
        )


# Console-based fallback notifier for when toast is unavailable
class ConsoleNotifier:
    """Fallback console-based notifications."""

    def __init__(self, config: dict):
        self.config = config.get('notifications', {})
        self.enabled = self.config.get('enabled', True)

    def _print(self, level: str, message: str):
        """Print notification to console."""
        if not self.enabled:
            return

        colors = {
            'success': '\033[92m',  # Green
            'warning': '\033[93m',  # Yellow
            'error': '\033[91m',    # Red
            'info': '\033[94m',     # Blue
            'reset': '\033[0m'
        }

        color = colors.get(level, colors['info'])
        print(f"{color}[{level.upper()}]{colors['reset']} {message}")

    def notify_success(self, system_name: str, glyph_code: str):
        if self.config.get('on_success', True):
            self._print('success', f"Submitted: {system_name} [{glyph_code}]")

    def notify_duplicate(self, system_name: str, glyph_code: str):
        if self.config.get('on_duplicate', False):
            self._print('warning', f"Duplicate: {system_name} [{glyph_code}]")

    def notify_error(self, message: str):
        if self.config.get('on_error', True):
            self._print('error', message)

    def notify_queued(self, system_name: str, count: int = 1):
        if self.config.get('on_offline_queue', True):
            self._print('info', f"Queued: {system_name} ({count} total)")

    def notify_queue_processed(self, success_count: int, total: int):
        self._print('success', f"Queue processed: {success_count}/{total} completed")

    def notify_watcher_started(self, save_path: str):
        self._print('info', f"Watcher started: {save_path}")

    def notify_watcher_stopped(self):
        self._print('info', "Watcher stopped")


def create_notifier(config: dict) -> NotificationManager:
    """
    Create appropriate notifier based on availability.

    Args:
        config: Configuration dict

    Returns:
        NotificationManager or ConsoleNotifier
    """
    if TOAST_AVAILABLE:
        return NotificationManager(config)
    else:
        logger.info("Using console notifications (win10toast not available)")
        return ConsoleNotifier(config)
