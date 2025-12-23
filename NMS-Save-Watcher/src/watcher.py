"""
Live Extraction Watcher for NMS Haven Extractor.
Monitors for live extraction data from the Haven Extractor game mod.

Extractions are QUEUED for manual upload rather than auto-submitted.
This allows reviewing data after scanning all planets before submitting.
"""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, List

from .config import get_save_file_path
from .extraction_watcher import ExtractionWatcher, convert_extraction_to_haven_payload
from .api_client import APIClient, SubmissionResult, SubmissionStatus
from .database import LocalDatabase

logger = logging.getLogger('nms_watcher.watcher')


class LiveExtractionWatcher:
    """
    Watches for live extraction data from Haven Extractor game mod.

    Extractions are queued for manual upload - they are NOT auto-submitted.
    Use upload_queued() or upload_all_pending() to manually upload.
    """

    def __init__(self, config: dict,
                 on_extraction: Optional[Callable[[dict], None]] = None,
                 on_submission: Optional[Callable[[SubmissionResult], None]] = None,
                 on_error: Optional[Callable[[str], None]] = None):
        """
        Initialize the live extraction watcher.

        Args:
            config: Configuration dictionary
            on_extraction: Callback when new extraction is queued (not submitted)
            on_submission: Callback for manual submission results
            on_error: Callback for errors
        """
        self.config = config
        self.on_extraction = on_extraction
        self.on_submission = on_submission
        self.on_error = on_error

        # Initialize components
        self.database = LocalDatabase()

        # API client - may be None if no key configured
        api_config = config.get('api', {})
        if api_config.get('key'):
            self.api_client = APIClient(
                base_url=api_config.get('base_url', 'http://localhost:8005'),
                api_key=api_config['key']
            )
        else:
            self.api_client = None
            logger.warning("No API key configured - submissions disabled")

        # Watcher state
        self._extraction_watcher: Optional[ExtractionWatcher] = None
        self._running = False
        self._stats = {
            'start_time': None,
            'live_extractions': 0,
            'submissions_success': 0,
            'submissions_duplicate': 0,
            'submissions_error': 0
        }

        # Live extraction config
        extraction_config = config.get('live_extraction', {})
        self._output_dir = extraction_config.get('output_dir')
        self._poll_interval = extraction_config.get('poll_interval', 2.0)
        self._startup_delay = extraction_config.get('startup_delay', 60.0)  # Default 60 seconds

    def start(self) -> bool:
        """
        Start watching for live extraction data.

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Watcher already running")
            return True

        try:
            # Get output directory
            output_dir = Path(self._output_dir) if self._output_dir else None

            self._extraction_watcher = ExtractionWatcher(
                output_dir=output_dir,
                callback=self._on_live_extraction,
                poll_interval=self._poll_interval,
                startup_delay=self._startup_delay
            )
            self._extraction_watcher.start()

            self._running = True
            self._stats['start_time'] = time.time()

            logger.info(f"Live extraction watcher started (QUEUE MODE)")
            logger.info(f"Monitoring: {self._extraction_watcher.output_dir}")
            if self._startup_delay > 0:
                logger.info(f"Learning mode: {self._startup_delay}s delay before collecting")
            logger.info(f"Extractions will be QUEUED for manual upload")

            return True

        except Exception as e:
            error = f"Failed to start extraction watcher: {e}"
            logger.error(error)
            if self.on_error:
                self.on_error(error)
            return False

    def _on_live_extraction(self, extraction_data: dict):
        """
        Handle new extraction from Haven Extractor game mod.

        Queues the extraction for manual upload instead of auto-submitting.

        Note: This callback only fires when ExtractionWatcher detects:
        - A NEW system (different glyph_code)
        - OR more planets than before (scanner room used)
        Duplicate updates are filtered out at the ExtractionWatcher level.
        """
        self._stats['live_extractions'] += 1

        try:
            system_name = extraction_data.get('system_name', 'Unknown')
            glyph_code = extraction_data.get('glyph_code', '')
            galaxy = extraction_data.get('galaxy_name', 'Euclid')
            planet_count = extraction_data.get('planet_count', 0)

            # Check if this is an update to existing queued system
            existing = self.database.get_queued_extraction(glyph_code, galaxy)
            is_update = existing is not None

            logger.info(f"=" * 50)
            if is_update:
                old_count = existing.get('planet_count', 0)
                logger.info(f"EXTRACTION UPDATED: {system_name}")
                logger.info(f"  Planets: {old_count} -> {planet_count}")
            else:
                logger.info(f"NEW SYSTEM QUEUED: {system_name}")
                logger.info(f"  Glyph Code: {glyph_code}")
                logger.info(f"  Galaxy: {galaxy}")
                logger.info(f"  Star: {extraction_data.get('star_type', 'Unknown')}")
                logger.info(f"  Economy: {extraction_data.get('economy_type', 'Unknown')}")
                logger.info(f"  Planets: {planet_count}")

                for planet in extraction_data.get('planets', []):
                    logger.info(f"    - {planet.get('planet_name', 'Unknown')}: {planet.get('biome', 'Unknown')}")

            # Queue the extraction (will update if same system with more planets)
            self.database.queue_extraction(extraction_data)

            # Get updated queue count
            queue_counts = self.database.get_queue_count()
            logger.info(f"  >> Queue status: {queue_counts['pending']} pending")
            logger.info(f"  >> Use upload command to submit to Haven Control Room")
            logger.info(f"=" * 50)

            # Notify callback
            if self.on_extraction:
                self.on_extraction(extraction_data)

        except Exception as e:
            logger.error(f"Error queueing extraction: {e}", exc_info=True)
            if self.on_error:
                self.on_error(f"Queue error: {e}")

    # =========================================================================
    # Manual Upload Methods
    # =========================================================================

    def get_pending_queue(self) -> List[dict]:
        """Get all pending extractions in the queue."""
        return self.database.get_queued_extractions(status='pending')

    def get_queue_count(self) -> dict:
        """Get counts of queued extractions by status."""
        return self.database.get_queue_count()

    def upload_queued(self, glyph_code: str, galaxy: str = 'Euclid') -> SubmissionResult:
        """
        Manually upload a specific queued extraction.

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name

        Returns:
            SubmissionResult with status
        """
        if not self.api_client:
            return SubmissionResult(
                status=SubmissionStatus.ERROR,
                message="No API key configured",
                glyph_code=glyph_code
            )

        # Get the queued extraction
        queued = self.database.get_queued_extraction(glyph_code, galaxy)
        if not queued:
            return SubmissionResult(
                status=SubmissionStatus.ERROR,
                message="System not found in queue",
                glyph_code=glyph_code
            )

        extraction_data = queued.get('extraction_data', {})
        if isinstance(extraction_data, str):
            import json
            extraction_data = json.loads(extraction_data)

        # Convert and submit
        payload = convert_extraction_to_haven_payload(extraction_data)
        result = self._submit_extraction(payload)

        # Update queue status based on result
        if result.status == SubmissionStatus.SUCCESS:
            self.database.update_queued_status(glyph_code, galaxy, 'uploaded')
        elif result.status == SubmissionStatus.DUPLICATE:
            self.database.update_queued_status(glyph_code, galaxy, 'uploaded')  # Still mark as done
        else:
            self.database.update_queued_status(glyph_code, galaxy, 'error')

        # Notify callback
        if self.on_submission:
            self.on_submission(result)

        return result

    def upload_all_pending(self) -> List[SubmissionResult]:
        """
        Upload all pending extractions in the queue.

        Returns:
            List of SubmissionResult for each upload attempt
        """
        results = []
        pending = self.get_pending_queue()

        if not pending:
            logger.info("No pending extractions to upload")
            return results

        logger.info(f"Uploading {len(pending)} pending extractions...")

        for queued in pending:
            glyph_code = queued.get('glyph_code', '')
            galaxy = queued.get('galaxy', 'Euclid')
            system_name = queued.get('system_name', 'Unknown')

            logger.info(f"Uploading: {system_name} [{glyph_code}]")

            result = self.upload_queued(glyph_code, galaxy)
            results.append(result)

            logger.info(f"  Result: {result.status.value} - {result.message}")

            # Small delay between submissions to avoid rate limiting
            time.sleep(0.5)

        # Summary
        success = sum(1 for r in results if r.status == SubmissionStatus.SUCCESS)
        duplicate = sum(1 for r in results if r.status == SubmissionStatus.DUPLICATE)
        errors = sum(1 for r in results if r.status == SubmissionStatus.ERROR)

        logger.info(f"Upload complete: {success} success, {duplicate} duplicate, {errors} errors")

        return results

    def clear_uploaded(self) -> int:
        """Clear successfully uploaded extractions from queue."""
        return self.database.clear_uploaded_queue()

    def remove_from_queue(self, glyph_code: str, galaxy: str = 'Euclid') -> bool:
        """Remove a specific extraction from the queue without uploading."""
        return self.database.remove_queued_extraction(glyph_code, galaxy)

    def _submit_extraction(self, payload: dict) -> SubmissionResult:
        """Submit a live extraction to the Haven Control Room API."""
        system_name = payload.get('name', 'Unknown')
        glyph_code = payload.get('glyph_code', '')
        galaxy = payload.get('galaxy', 'Euclid')

        try:
            # Check for duplicate on server first
            try:
                is_duplicate = self.api_client.check_duplicate(glyph_code, galaxy)
                if is_duplicate:
                    self._stats['submissions_duplicate'] += 1
                    return SubmissionResult(
                        status=SubmissionStatus.DUPLICATE,
                        message="System already exists on server",
                        system_name=system_name,
                        glyph_code=glyph_code
                    )
            except Exception as e:
                logger.warning(f"Could not check for duplicate: {e}")

            # Build submission payload - include ALL fields from Haven Extractor v7.9.6+
            submission = {
                'name': system_name,
                'glyph_code': glyph_code,
                'galaxy': galaxy,
                'star_type': payload.get('star_type', 'Unknown'),
                'economy_type': payload.get('economy_type', 'Unknown'),
                'economy_level': payload.get('economy_level', 'Unknown'),
                'conflict_level': payload.get('conflict_level', 'Unknown'),
                'dominant_lifeform': payload.get('dominant_lifeform', 'Unknown'),
                'x': payload.get('x', 0),
                'y': payload.get('y', 0),
                'z': payload.get('z', 0),
                'planets': payload.get('planets', []),  # Full planet data with all new fields
                'planet_count': payload.get('planet_count', 0),
                'submitted_by': 'Haven Extractor',
                'source': 'live_extraction'
            }

            # Submit to API
            response = self.api_client.session.post(
                f"{self.api_client.base_url}/api/submit_system",
                json=submission,
                timeout=30
            )

            if response.status_code in (200, 201):
                data = response.json()
                if data.get('duplicate'):
                    self._stats['submissions_duplicate'] += 1
                    return SubmissionResult(
                        status=SubmissionStatus.DUPLICATE,
                        message="System already exists",
                        system_name=system_name,
                        glyph_code=glyph_code
                    )

                self._stats['submissions_success'] += 1
                return SubmissionResult(
                    status=SubmissionStatus.SUCCESS,
                    message="System submitted for admin approval",
                    system_name=system_name,
                    glyph_code=glyph_code
                )

            elif response.status_code == 409:
                self._stats['submissions_duplicate'] += 1
                return SubmissionResult(
                    status=SubmissionStatus.DUPLICATE,
                    message="System already exists",
                    system_name=system_name,
                    glyph_code=glyph_code
                )

            else:
                error_msg = f"API error: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get('detail') or error_data.get('error') or error_msg
                except:
                    pass

                self._stats['submissions_error'] += 1
                return SubmissionResult(
                    status=SubmissionStatus.ERROR,
                    message=error_msg,
                    system_name=system_name,
                    glyph_code=glyph_code
                )

        except Exception as e:
            self._stats['submissions_error'] += 1
            return SubmissionResult(
                status=SubmissionStatus.ERROR,
                message=str(e),
                system_name=system_name,
                glyph_code=glyph_code
            )

    def stop(self):
        """Stop the extraction watcher."""
        if self._extraction_watcher:
            self._extraction_watcher.stop()
            self._extraction_watcher = None

        self._running = False
        logger.info("Live extraction watcher stopped")

    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running

    def get_stats(self) -> dict:
        """Get watcher statistics."""
        stats = self._stats.copy()
        if stats['start_time']:
            stats['uptime_seconds'] = int(time.time() - stats['start_time'])

        # Add queue counts
        queue_counts = self.database.get_queue_count()
        stats['queue_pending'] = queue_counts.get('pending', 0)
        stats['queue_uploaded'] = queue_counts.get('uploaded', 0)
        stats['queue_total'] = queue_counts.get('total', 0)

        stats.update(self.database.get_stats())

        # Get extraction watcher info
        if self._extraction_watcher:
            stats['output_dir'] = str(self._extraction_watcher.output_dir)
            stats['poll_interval'] = self._poll_interval

        return stats

    def get_latest_extraction(self) -> Optional[dict]:
        """Get the most recent extraction data."""
        if self._extraction_watcher:
            return self._extraction_watcher.get_latest_extraction()
        return None

    def reset_deduplication(self):
        """
        Reset the deduplication tracking state.

        Call this to force the watcher to re-process the current extraction
        (useful for testing or when user wants to re-queue a system).
        """
        if self._extraction_watcher:
            self._extraction_watcher.reset_deduplication()

    def get_tracking_state(self) -> dict:
        """
        Get current deduplication tracking state (for debugging).

        Returns:
            Dict with current tracking info
        """
        if self._extraction_watcher:
            return self._extraction_watcher.get_tracking_state()
        return {}


# Alias for backward compatibility
SaveWatcher = LiveExtractionWatcher
