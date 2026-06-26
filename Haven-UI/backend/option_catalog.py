"""Loader for the canonical NMS system-submission option catalog.

The actual lists live in `src/data/optionCatalog.json` — the SINGLE SOURCE OF
TRUTH that the web wizard also reads (`src/data/adjectives.js` re-exports the
adjective/resource arrays from that same JSON). This module loads the file so
the backend can serve it at `GET /api/option-catalog`, which the Keeper Discord
bot fetches for slash-command autocomplete.

Why the JSON lives under `src/` rather than `backend/data/`: the Dockerfile's
frontend build stage only copies `src/`, so a file the *frontend build* must
import has to live there. The backend runtime stage does `COPY . .`, so `src/`
is present at runtime too (same reachability `data/galaxies.json` relies on).
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger('control.room')

# backend/ -> Haven-UI/ -> src/data/optionCatalog.json
_CATALOG_PATH = Path(__file__).parent.parent / 'src' / 'data' / 'optionCatalog.json'

_catalog_cache = None


def get_option_catalog():
    """Return the full option catalog dict (cached in-process).

    Returns an empty dict if the file can't be read; callers should treat an
    empty catalog as "unavailable" rather than crashing.
    """
    global _catalog_cache
    if _catalog_cache is None:
        try:
            with open(_CATALOG_PATH, encoding='utf-8') as f:
                _catalog_cache = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load option catalog from {_CATALOG_PATH}: {e}")
            _catalog_cache = {}
    return _catalog_cache
