"""
Poster service — registry, render queue, Playwright lifecycle, cache I/O.

Single source of truth for every dynamically-rendered visual artifact in Haven
(Voyager Cards, Galaxy Atlases, Open Graph cards). Adding a new poster type =
one row in REGISTRY + one React component in src/posters/. Nothing else.

Design invariants (poster-system-plan.md):
  1. Adding a new poster type must be: registry entry + React component.
  2. Every poster component must set window.__POSTER_READY = true.
  3. The PNG endpoint is the single share-source for all consumers.
  4. Cache invalidation is event-driven first, TTL second.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from db import get_db_connection, get_db_path

logger = logging.getLogger('control.room')

# ============================================================================
# Configuration
# ============================================================================

# How long the headless browser will wait for window.__POSTER_READY
POSTER_READY_TIMEOUT_MS = 12000

# Hard ceiling on a single render (page load + screenshot)
RENDER_TIMEOUT_S = 18

# Concurrent render budget — protects Pi from being overwhelmed
RENDER_CONCURRENCY = 2

# How long to wait before dropping cache rows that haven't been read
CACHE_PRUNE_AFTER_DAYS = 90

# Where rendered PNGs live on disk
def get_posters_dir() -> Path:
    """Resolve the poster cache directory under Haven-UI/data/posters/."""
    db_path = get_db_path()
    posters_dir = db_path.parent / 'posters'
    posters_dir.mkdir(parents=True, exist_ok=True)
    return posters_dir


# Where Playwright opens the SPA. In production this is the same backend that
# serves /api/posters/, so 127.0.0.1 + the port we're listening on works.
def get_render_base_url() -> str:
    return os.getenv('POSTER_RENDER_BASE', 'http://127.0.0.1:8005')


# ============================================================================
# Registry
# ============================================================================

@dataclass
class PosterTemplate:
    """Defines one renderable poster type.

    Adding a new poster type = add a row here + create the React component
    referenced by spa_route. The React component must self-fetch its data and
    set window.__POSTER_READY = true after first paint.
    """
    type: str                                # 'voyager', 'atlas', 'og_site', etc.
    version: int                             # Bump to invalidate all caches for this type
    width: int                               # Viewport width Playwright opens at
    height: int                              # Viewport height
    spa_route: str                           # SPA path Playwright loads, with {key} placeholder
    ttl_hours: int                           # Cache lifetime before automatic re-render
    public: bool = True                      # Whether the PNG endpoint is publicly fetchable
    requires_opt_in_check: bool = False      # If True, check user_profiles.poster_public for the key
    description: str = ''                    # Human-readable description for admin UI


REGISTRY: dict[str, PosterTemplate] = {
    'voyager': PosterTemplate(
        type='voyager',
        version=1,
        width=680,
        height=1040,
        spa_route='/poster/voyager/{key}',
        ttl_hours=24,
        requires_opt_in_check=True,
        description='Personal Voyager Card — 680x1040 stat-rich poster',
    ),
    'voyager_og': PosterTemplate(
        type='voyager_og',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/voyager_og/{key}',
        ttl_hours=24,
        requires_opt_in_check=True,
        description='Voyager Card OG variant — 1200x630 condensed for Discord/Twitter embeds',
    ),
    'atlas': PosterTemplate(
        type='atlas',
        version=1,
        width=680,
        height=920,
        spa_route='/poster/atlas/{key}',
        ttl_hours=24,
        description='Galaxy Atlas — 680x920 political map of one galaxy',
    ),
    'atlas_thumb': PosterTemplate(
        type='atlas_thumb',
        version=1,
        width=400,
        height=400,
        spa_route='/poster/atlas_thumb/{key}',
        ttl_hours=24,
        description='Galaxy Atlas thumbnail — 400x400 for Systems-tab cards',
    ),
    'og_site': PosterTemplate(
        type='og_site',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/og_site/global',
        ttl_hours=168,  # weekly
        description='Global Haven OG card — replaces static haven-preview.png',
    ),
    'landing_og': PosterTemplate(
        type='landing_og',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/landing_og/global',
        ttl_hours=168,  # weekly
        description='Landing-page OG card — cosmic-compass + wordmark + 3 live stats, served for havenmap.online/ embeds',
    ),
    'og_system': PosterTemplate(
        type='og_system',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/og_system/{key}',
        ttl_hours=24,
        description='Per-system OG card for /systems/:id share embeds',
    ),
    'og_community': PosterTemplate(
        type='og_community',
        version=1,
        width=1200,
        height=630,
        spa_route='/poster/og_community/{key}',
        ttl_hours=24,
        description='Per-community OG card for /community-stats/:tag share embeds',
    ),
}


def get_template(poster_type: str) -> Optional[PosterTemplate]:
    """Return the registered template, or None if unknown."""
    return REGISTRY.get(poster_type)


def list_templates() -> list[dict]:
    """Return registry as a list of dicts for the admin queue UI."""
    return [
        {
            'type': t.type,
            'version': t.version,
            'width': t.width,
            'height': t.height,
            'ttl_hours': t.ttl_hours,
            'requires_opt_in_check': t.requires_opt_in_check,
            'description': t.description,
        }
        for t in REGISTRY.values()
    ]


# ============================================================================
# Playwright lifecycle
# Keep one persistent browser process alive for the lifetime of the app.
# Booting Chromium per-request would burn ~3 seconds and 200MB of churn.
# ============================================================================

_browser = None  # Resolved lazily; set in lifespan startup
_browser_lock = asyncio.Lock()
_render_semaphore = asyncio.Semaphore(RENDER_CONCURRENCY)


async def init_browser():
    """Boot the persistent Playwright Chromium instance. Called from FastAPI lifespan."""
    global _browser
    async with _browser_lock:
        if _browser is not None:
            return _browser
        try:
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            _browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage'],  # Pi-friendly
            )
            # Stash the playwright handle on the browser so shutdown can stop it
            _browser._playwright_handle = playwright
            logger.info('Poster service: Playwright Chromium booted')
        except Exception as e:
            logger.exception(f'Poster service: failed to boot Playwright: {e}')
            _browser = None
            raise
    return _browser


async def shutdown_browser():
    """Tear down Playwright. Called from FastAPI lifespan shutdown."""
    global _browser
    if _browser is None:
        return
    try:
        playwright = getattr(_browser, '_playwright_handle', None)
        await _browser.close()
        if playwright is not None:
            await playwright.stop()
        logger.info('Poster service: Playwright shut down cleanly')
    except Exception as e:
        logger.warning(f'Poster service: shutdown error (non-fatal): {e}')
    finally:
        _browser = None


def is_browser_ready() -> bool:
    """Return True if the persistent browser is booted and reachable."""
    return _browser is not None


# ============================================================================
# Cache table I/O
# Schema (from migration v1.70.0):
#   poster_cache(id, poster_type, cache_key, template_version,
#                generated_at, data_hash, file_path, render_ms)
# ============================================================================

def _cache_lookup(poster_type: str, cache_key: str) -> Optional[dict]:
    """Return the cache row for (type, key) or None."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, poster_type, cache_key, template_version,
                   generated_at, data_hash, file_path, render_ms
            FROM poster_cache
            WHERE poster_type = ? AND cache_key = ?
            LIMIT 1
        ''', (poster_type, cache_key))
        row = cursor.fetchone()
        return dict(row) if row else None


def _cache_write(poster_type: str, cache_key: str, template_version: int,
                 data_hash: str, file_path: str, render_ms: int) -> None:
    """UPSERT a cache row."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO poster_cache
                (poster_type, cache_key, template_version, generated_at, data_hash, file_path, render_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(poster_type, cache_key) DO UPDATE SET
                template_version = excluded.template_version,
                generated_at = excluded.generated_at,
                data_hash = excluded.data_hash,
                file_path = excluded.file_path,
                render_ms = excluded.render_ms
        ''', (
            poster_type, cache_key, template_version,
            datetime.now(timezone.utc).isoformat(),
            data_hash, file_path, render_ms,
        ))
        conn.commit()


def _cache_delete(poster_type: str, cache_key: str) -> Optional[str]:
    """DELETE a cache row, return the file_path that was removed (or None)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT file_path FROM poster_cache WHERE poster_type = ? AND cache_key = ?',
            (poster_type, cache_key),
        )
        row = cursor.fetchone()
        file_path = row['file_path'] if row else None
        cursor.execute(
            'DELETE FROM poster_cache WHERE poster_type = ? AND cache_key = ?',
            (poster_type, cache_key),
        )
        conn.commit()
        return file_path


def invalidate(poster_type: str, cache_key: str) -> bool:
    """Drop the cache entry for (type, key) and remove the PNG from disk.

    Called by approval handlers when underlying data changes (system approved,
    region named, etc.). Next consumer request will re-render fresh.

    Returns True if a row was dropped, False if no entry existed.
    """
    file_path = _cache_delete(poster_type, cache_key)
    if file_path:
        try:
            p = Path(file_path)
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.warning(f'Poster invalidate: failed to remove {file_path}: {e}')
        logger.info(f'Poster invalidate: dropped {poster_type}/{cache_key}')
        return True
    return False


def is_cache_fresh(poster_type: str, cache_key: str, row: dict) -> bool:
    """Decide whether a cache row can be served as-is.

    Fresh if:
      - template_version matches current registry version (auto-invalidates on bump)
      - file exists on disk
      - generated_at is within the template's TTL
    """
    template = REGISTRY.get(poster_type)
    if template is None:
        return False
    if row.get('template_version') != template.version:
        return False
    file_path = row.get('file_path')
    if not file_path or not Path(file_path).exists():
        return False
    try:
        generated_at = datetime.fromisoformat(row['generated_at'].replace('Z', '+00:00'))
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - generated_at
        if age > timedelta(hours=template.ttl_hours):
            return False
    except (ValueError, KeyError, TypeError):
        return False
    return True


# ============================================================================
# Render
# ============================================================================

def _build_render_url(template: PosterTemplate, cache_key: str) -> str:
    """Construct the SPA URL Playwright opens for this template/key."""
    base = get_render_base_url().rstrip('/')
    # Mount under /haven-ui because that's the SPA base path in production
    # (vite.config.mjs base: '/haven-ui/'). Renderer URL is the chrome-less
    # /poster/:type/:key route.
    spa_path = template.spa_route.format(key=cache_key)
    return f'{base}/haven-ui{spa_path}'


def _build_output_path(template: PosterTemplate, cache_key: str) -> Path:
    """Where this poster's PNG lives on disk."""
    safe_key = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in cache_key)[:64]
    return get_posters_dir() / template.type / f'{safe_key}_v{template.version}.png'


async def _render(template: PosterTemplate, cache_key: str, output_path: Path) -> int:
    """Open the SPA route in headless browser, wait for ready flag, screenshot.

    Returns render duration in milliseconds. Raises on timeout or error.
    """
    if not is_browser_ready():
        await init_browser()

    url = _build_render_url(template, cache_key)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f'Rendering {template.type}/{cache_key} from {url}')

    start = time.monotonic()

    async with _render_semaphore:
        context = await _browser.new_context(
            viewport={'width': template.width, 'height': template.height},
            device_scale_factor=2,  # Render at 2x for crisp images
        )
        try:
            page = await context.new_page()
            try:
                # Navigate and wait for the poster's ready flag
                await page.goto(url, wait_until='domcontentloaded', timeout=RENDER_TIMEOUT_S * 1000)
                # Wait for the JS flag the React component sets after data + render
                await page.wait_for_function(
                    'window.__POSTER_READY === true',
                    timeout=POSTER_READY_TIMEOUT_MS,
                )
                # Brief settle so any final layout shifts (font swap, etc.) commit
                await page.wait_for_timeout(150)
                await page.screenshot(
                    path=str(output_path),
                    full_page=False,
                    omit_background=False,
                    type='png',
                    clip={'x': 0, 'y': 0, 'width': template.width, 'height': template.height},
                )
            finally:
                await page.close()
        finally:
            await context.close()

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(f'Rendered {template.type}/{cache_key} in {duration_ms}ms')
    return duration_ms


# ============================================================================
# Data hash (skip-render optimization)
# ============================================================================

def compute_data_hash(poster_type: str, cache_key: str) -> Optional[str]:
    """Hash of the underlying data so we can skip re-renders that wouldn't differ.

    Returns None if no cheap hash source is known for this poster type — in
    that case we always re-render when TTL elapses. Intended to be extended as
    we add cheap data signatures (e.g., max(submission_date) for voyager).
    """
    # Future optimization: compute hashes per poster type from inexpensive
    # SQL queries. For now we rely on TTL + event-driven invalidation.
    return None


# ============================================================================
# Public entry point
# ============================================================================

async def get_or_render(poster_type: str, cache_key: str) -> Optional[Path]:
    """Return the file path to a cached or freshly-rendered poster PNG.

    Returns None if the poster type is unknown.

    Cache lookup → return file path if fresh.
    Else render → write cache → return file path.

    Caller (the route) handles 404, opt-in checks, headers.
    """
    template = REGISTRY.get(poster_type)
    if template is None:
        return None

    # Check cache first
    row = _cache_lookup(poster_type, cache_key)
    if row and is_cache_fresh(poster_type, cache_key, row):
        return Path(row['file_path'])

    # Render fresh
    output_path = _build_output_path(template, cache_key)
    try:
        render_ms = await _render(template, cache_key, output_path)
    except Exception as e:
        logger.exception(f'Render failed for {poster_type}/{cache_key}: {e}')
        # On failure: if a stale-but-existent cache row points at a real file,
        # serve that as fallback rather than 5xx-ing the consumer.
        if row and row.get('file_path') and Path(row['file_path']).exists():
            logger.warning(f'Serving stale cache for {poster_type}/{cache_key} after render failure')
            return Path(row['file_path'])
        raise

    data_hash = compute_data_hash(poster_type, cache_key) or ''
    _cache_write(
        poster_type=poster_type,
        cache_key=cache_key,
        template_version=template.version,
        data_hash=data_hash,
        file_path=str(output_path),
        render_ms=render_ms,
    )
    return output_path


def force_refresh(poster_type: str, cache_key: str) -> bool:
    """Drop cache for (type, key) so the next request renders fresh.

    Called by the manual /refresh endpoint and by event-driven invalidation
    hooks in routes/approvals.py and routes/regions.py.
    """
    return invalidate(poster_type, cache_key)


def cache_stats() -> dict:
    """Return aggregate stats for the admin queue UI."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT poster_type, COUNT(*) as cnt,
                   AVG(render_ms) as avg_ms,
                   MAX(generated_at) as latest
            FROM poster_cache
            GROUP BY poster_type
        ''')
        per_type = [dict(r) for r in cursor.fetchall()]
        cursor.execute('SELECT COUNT(*) as total FROM poster_cache')
        total = cursor.fetchone()['total']
    return {
        'browser_ready': is_browser_ready(),
        'render_concurrency': RENDER_CONCURRENCY,
        'render_timeout_s': RENDER_TIMEOUT_S,
        'total_cached': total,
        'per_type': per_type,
        'registry': list_templates(),
    }


def prune_old_cache_rows(days: int = CACHE_PRUNE_AFTER_DAYS) -> int:
    """Drop cache rows older than `days` whose files haven't been re-requested.

    Called by the weekly cron. Returns the number of rows pruned.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT file_path FROM poster_cache WHERE generated_at < ?', (cutoff,))
        files_to_remove = [r['file_path'] for r in cursor.fetchall() if r['file_path']]
        cursor.execute('DELETE FROM poster_cache WHERE generated_at < ?', (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
    for fp in files_to_remove:
        try:
            p = Path(fp)
            if p.exists():
                p.unlink()
        except Exception:
            pass
    logger.info(f'Poster prune: dropped {deleted} cache rows older than {days} days')
    return deleted
