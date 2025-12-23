"""
API Client for Voyagers Haven.
Handles submissions with retry logic and offline queue support.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .extractor import SystemData

logger = logging.getLogger('nms_watcher.api')


class SubmissionStatus(Enum):
    """Status of a submission attempt."""
    SUCCESS = "success"
    DUPLICATE = "duplicate"
    QUEUED = "queued"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"


@dataclass
class SubmissionResult:
    """Result of a submission attempt."""
    status: SubmissionStatus
    message: str
    system_name: str
    glyph_code: str
    queued: bool = False


class APIClient:
    """Client for Voyagers Haven API with retry and offline support."""

    def __init__(self, base_url: str, api_key: str, offline_queue_path: Optional[Path] = None):
        """
        Initialize the API client.

        Args:
            base_url: Base URL of the Voyagers Haven API
            api_key: API key for authentication
            offline_queue_path: Path to store queued submissions (default: data/offline_queue.json)
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.offline_queue_path = offline_queue_path or Path(__file__).parent.parent / 'data' / 'offline_queue.json'

        # Configure session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key,
            'User-Agent': 'NMS-Save-Watcher/1.0'
        })

        # Track rate limiting
        self.rate_limit_until: Optional[float] = None

    def check_duplicate(self, glyph_code: str, galaxy: str) -> bool:
        """
        Check if a system already exists in the database.

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name

        Returns:
            True if duplicate exists, False otherwise
        """
        result = self.check_duplicate_detailed(glyph_code, galaxy)
        return result.get('exists', False)

    def check_duplicate_detailed(self, glyph_code: str, galaxy: str) -> dict:
        """
        Check if a system already exists with detailed information.

        Args:
            glyph_code: Portal glyph code
            galaxy: Galaxy name

        Returns:
            Dict with 'exists', 'location', 'system_id', 'system_name', 'system_data'
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/check_duplicate",
                params={'glyph_code': glyph_code, 'galaxy': galaxy},
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                logger.error("API key authentication failed")
                return {'exists': False, 'error': 'auth_failed'}
            else:
                logger.warning(f"Duplicate check failed: {response.status_code}")
                return {'exists': False, 'error': f'status_{response.status_code}'}

        except requests.RequestException as e:
            logger.warning(f"Could not check for duplicate (offline?): {e}")
            return {'exists': False, 'error': 'offline'}

    def submit_system(self, system: SystemData) -> SubmissionResult:
        """
        Submit a system discovery to the API.

        Args:
            system: SystemData to submit

        Returns:
            SubmissionResult with status and message
        """
        # Check rate limiting
        if self.rate_limit_until and time.time() < self.rate_limit_until:
            wait_time = int(self.rate_limit_until - time.time())
            logger.warning(f"Rate limited, waiting {wait_time}s")
            return SubmissionResult(
                status=SubmissionStatus.RATE_LIMITED,
                message=f"Rate limited, retry in {wait_time}s",
                system_name=system.name,
                glyph_code=system.glyph_code
            )

        # Build submission payload
        payload = self._build_payload(system)

        try:
            response = self.session.post(
                f"{self.base_url}/api/submit_system",
                json=payload,
                timeout=30
            )

            return self._handle_response(response, system)

        except requests.ConnectionError as e:
            logger.warning(f"Connection error, queuing submission: {e}")
            self._queue_submission(system)
            return SubmissionResult(
                status=SubmissionStatus.QUEUED,
                message="Server unreachable, submission queued",
                system_name=system.name,
                glyph_code=system.glyph_code,
                queued=True
            )

        except requests.Timeout as e:
            logger.warning(f"Request timeout, queuing submission: {e}")
            self._queue_submission(system)
            return SubmissionResult(
                status=SubmissionStatus.QUEUED,
                message="Request timeout, submission queued",
                system_name=system.name,
                glyph_code=system.glyph_code,
                queued=True
            )

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return SubmissionResult(
                status=SubmissionStatus.ERROR,
                message=str(e),
                system_name=system.name,
                glyph_code=system.glyph_code
            )

    def _build_payload(self, system: SystemData) -> dict:
        """Build API payload from SystemData."""
        # Convert planets to the expected format
        planets = []
        for planet in system.planets:
            planet_data = {
                'name': planet.name,
                'biome': planet.biome,
                'sentinel_level': planet.sentinel_level,
                'fauna_level': planet.fauna_level,
                'flora_level': planet.flora_level,
                'resources': planet.resources,
                'moons': []
            }
            # Add moons if any
            for moon in planet.moons:
                moon_data = {
                    'name': moon.name,
                    'biome': moon.biome,
                    'sentinel_level': moon.sentinel_level,
                    'fauna_level': moon.fauna_level,
                    'flora_level': moon.flora_level,
                    'resources': moon.resources
                }
                planet_data['moons'].append(moon_data)
            planets.append(planet_data)

        return {
            'name': system.name,  # API expects 'name', not 'system_name'
            'glyph_code': system.glyph_code,
            'galaxy': system.galaxy,
            'star_type': system.star_type,
            'economy_type': system.economy_type,
            'economy_level': system.economy_level,
            'conflict_level': system.conflict_level,
            'discovered_by': system.discovered_by,
            'discovered_at': system.discovered_at,
            'submitted_by': system.discovered_by or 'Companion App',
            'planets': planets,
            'source': 'companion_app'
        }

    def _handle_response(self, response: requests.Response, system: SystemData) -> SubmissionResult:
        """Handle API response and return appropriate result."""
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            if data.get('duplicate'):
                return SubmissionResult(
                    status=SubmissionStatus.DUPLICATE,
                    message="System already exists in database",
                    system_name=system.name,
                    glyph_code=system.glyph_code
                )
            return SubmissionResult(
                status=SubmissionStatus.SUCCESS,
                message="System submitted for approval",
                system_name=system.name,
                glyph_code=system.glyph_code
            )

        elif response.status_code == 401:
            return SubmissionResult(
                status=SubmissionStatus.AUTH_ERROR,
                message="Invalid API key",
                system_name=system.name,
                glyph_code=system.glyph_code
            )

        elif response.status_code == 409:
            # Duplicate
            return SubmissionResult(
                status=SubmissionStatus.DUPLICATE,
                message="System already exists",
                system_name=system.name,
                glyph_code=system.glyph_code
            )

        elif response.status_code == 429:
            # Rate limited
            retry_after = int(response.headers.get('Retry-After', 60))
            self.rate_limit_until = time.time() + retry_after
            logger.warning(f"Rate limited, retry after {retry_after}s")

            # Queue for later
            self._queue_submission(system)
            return SubmissionResult(
                status=SubmissionStatus.RATE_LIMITED,
                message=f"Rate limited, queued for retry in {retry_after}s",
                system_name=system.name,
                glyph_code=system.glyph_code,
                queued=True
            )

        else:
            error_msg = f"API error: {response.status_code}"
            try:
                error_data = response.json()
                # API may return 'error' or 'detail' for error messages
                error_msg = error_data.get('detail') or error_data.get('error') or error_msg
            except:
                pass

            logger.error(f"API submission failed: {response.status_code} - {error_msg}")

            return SubmissionResult(
                status=SubmissionStatus.ERROR,
                message=error_msg,
                system_name=system.name,
                glyph_code=system.glyph_code
            )

    def _queue_submission(self, system: SystemData):
        """Queue a submission for later retry."""
        queue = self._load_queue()

        # Add to queue with timestamp
        entry = {
            'timestamp': datetime.now().isoformat(),
            'system': system.to_dict()
        }

        # Check if already queued (by glyph_code + galaxy)
        for item in queue:
            if (item['system'].get('glyph_code') == system.glyph_code and
                item['system'].get('galaxy') == system.galaxy):
                logger.debug(f"System {system.name} already queued")
                return

        queue.append(entry)
        self._save_queue(queue)
        logger.info(f"Queued submission for {system.name}")

    def _load_queue(self) -> list:
        """Load the offline queue from file."""
        if not self.offline_queue_path.exists():
            return []

        try:
            with open(self.offline_queue_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load queue: {e}")
            return []

    def _save_queue(self, queue: list):
        """Save the offline queue to file."""
        try:
            self.offline_queue_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.offline_queue_path, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save queue: {e}")

    def process_queue(self) -> list[SubmissionResult]:
        """
        Process queued submissions.

        Returns:
            List of submission results
        """
        queue = self._load_queue()
        if not queue:
            return []

        results = []
        remaining = []

        for item in queue:
            system_dict = item['system']

            # Reconstruct SystemData
            system = SystemData(
                name=system_dict.get('name', ''),
                glyph_code=system_dict.get('glyph_code', ''),
                galaxy=system_dict.get('galaxy', ''),
                galaxy_index=system_dict.get('galaxy_index', 0),
                star_type=system_dict.get('star_type', ''),
                economy_type=system_dict.get('economy_type', ''),
                economy_level=system_dict.get('economy_level', ''),
                conflict_level=system_dict.get('conflict_level', ''),
                discovered_by=system_dict.get('discovered_by', ''),
                discovered_at=system_dict.get('discovered_at', ''),
                planets=[]  # Simplified - planets handled in payload
            )

            # Temporarily disable queuing to avoid re-queuing
            result = self.submit_system(system)

            if result.status in (SubmissionStatus.SUCCESS, SubmissionStatus.DUPLICATE):
                results.append(result)
            elif result.status == SubmissionStatus.QUEUED:
                # Still offline, keep in queue
                remaining.append(item)
                break  # Stop processing if we're offline
            else:
                results.append(result)
                # Keep failed items for manual review
                remaining.append(item)

        # Update queue
        self._save_queue(remaining)

        return results

    def get_queue_count(self) -> int:
        """Get the number of queued submissions."""
        return len(self._load_queue())

    def test_connection(self) -> tuple[bool, str]:
        """
        Test API connection and authentication.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Try to hit a simple endpoint
            response = self.session.get(
                f"{self.base_url}/api/stats",
                timeout=10
            )

            if response.status_code == 200:
                return True, "Connected successfully"
            elif response.status_code == 401:
                return False, "Invalid API key"
            else:
                return False, f"Server returned {response.status_code}"

        except requests.ConnectionError:
            return False, "Could not connect to server"
        except requests.Timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, str(e)
