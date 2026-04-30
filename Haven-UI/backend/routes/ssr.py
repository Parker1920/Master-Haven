"""
Server-side rendering shim for Open Graph link previews.

Discord, Twitter, Slack, and Reddit scrapers do NOT execute JavaScript. The
Haven UI is a single-page React app that emits the same generic OG tags for
every URL — so when someone pastes /voyager/turpitzz or /atlas/Euclid into
Discord, the resulting embed shows the global Haven preview, never the
specific user's card or galaxy.

This shim intercepts the share-friendly URL patterns BEFORE the SPA static
fallback catches them. For each scraper-friendly route, it returns minimal
HTML with route-specific og:* and twitter:* meta tags, plus a tiny JS
redirect so real browsers seamlessly hand off to the SPA.

Mount before the SPA fallback in control_room_api.py.
"""

import logging
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger('control.room')

router = APIRouter()

# Resolves to Haven-UI/landing/. Independent of control_room_api so this
# module can be imported without the parent app loaded.
LANDING_DIR = Path(__file__).resolve().parent.parent.parent / 'landing'


# ============================================================================
# OG payload builders — one per share-route pattern.
# Each returns a dict {title, description, image, image_w, image_h, url}.
# ============================================================================

def _ogcard(poster_type: str, key: str, w: int = 1200, h: int = 630) -> str:
    """Construct the absolute PNG URL for the given poster + key."""
    safe_key = quote(key, safe='')
    return f'/api/posters/{poster_type}/{safe_key}.png'


def build_site_og() -> dict:
    """Root domain OG payload — havenmap.online itself shows the site card."""
    return {
        'title': "Voyager's Haven — a community atlas of No Man's Sky",
        'description': "Browse, name, and map No Man's Sky discoveries together. Live data from havenmap.online.",
        'image': _ogcard('og_site', 'global'),
        'image_w': 1200,
        'image_h': 630,
        'url': '/',
    }


def build_voyager_og(username: str) -> dict:
    return {
        'title': f"{username} — Voyager's Haven",
        'description': f"{username}'s galaxy fingerprint card. Live data from havenmap.online.",
        'image': _ogcard('voyager_og', username),
        'image_w': 1200,
        'image_h': 630,
        'url': f'/voyager/{quote(username, safe="")}',
    }


def build_atlas_og(galaxy: str) -> dict:
    return {
        'title': f"{galaxy} — Voyager's Haven",
        'description': f"A political atlas of the {galaxy} galaxy. Live data from havenmap.online.",
        'image': _ogcard('atlas', galaxy),
        'image_w': 680,
        'image_h': 920,
        'url': f'/atlas/{quote(galaxy, safe="")}',
    }


def build_system_og(system_id: str) -> dict:
    return {
        'title': f"Star System — Voyager's Haven",
        'description': f"View the data for this charted star system on havenmap.online.",
        'image': _ogcard('og_system', system_id),
        'image_w': 1200,
        'image_h': 630,
        'url': f'/systems/{quote(system_id, safe="")}',
    }


def build_community_og(tag: str) -> dict:
    return {
        'title': f"{tag} — Community Stats — Voyager's Haven",
        'description': f"The {tag} charting community on havenmap.online.",
        'image': _ogcard('og_community', tag),
        'image_w': 1200,
        'image_h': 630,
        'url': f'/community-stats/{quote(tag, safe="")}',
    }


# ============================================================================
# HTML template
# Minimal HTML that emits og/twitter meta tags + a JS redirect that takes a
# real browser to the SPA equivalent of the route.
# ============================================================================

OG_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>

  <!-- Open Graph -->
  <meta property="og:type" content="website">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:image" content="{image_abs}">
  <meta property="og:image:width" content="{image_w}">
  <meta property="og:image:height" content="{image_h}">
  <meta property="og:url" content="{url_abs}">
  <meta property="og:site_name" content="Voyager's Haven">

  <!-- Twitter -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{image_abs}">

  <!-- Discord embed colour -->
  <meta name="theme-color" content="#00C2B3">

  <link rel="canonical" href="{url_abs}">

  <!-- Real browsers fall through to the SPA. Discord/Twitter/Slack scrapers
       stop at the meta tags above and never run this script. -->
  <script>
    (function () {{
      try {{
        var spa = "/haven-ui{spa_url}";
        if (window.location.pathname.indexOf("/haven-ui") !== 0) {{
          window.location.replace(spa + window.location.search + window.location.hash);
        }}
      }} catch (e) {{ /* no-op */ }}
    }})();
  </script>
</head>
<body style="background:#0a0e2a;color:#e0e7ff;font-family:system-ui,sans-serif;">
  <noscript>
    <p style="padding:32px;">
      <a href="/haven-ui{spa_url}" style="color:#00C2B3;">Open this page in Voyager's Haven</a>
    </p>
  </noscript>
</body>
</html>
"""


def _render_og(payload: dict, request: Request) -> HTMLResponse:
    """Format the OG template with absolute URLs anchored to this request's host."""
    base = str(request.base_url).rstrip('/')
    image_abs = payload['image']
    if image_abs.startswith('/'):
        image_abs = base + image_abs
    url_abs = payload['url']
    if url_abs.startswith('/'):
        url_abs = base + url_abs

    html = OG_TEMPLATE.format(
        title=_html_escape(payload['title']),
        description=_html_escape(payload['description']),
        image_abs=image_abs,
        image_w=payload['image_w'],
        image_h=payload['image_h'],
        url_abs=url_abs,
        spa_url=payload['url'],
    )
    return HTMLResponse(html, headers={
        'Cache-Control': 'public, max-age=300, must-revalidate',
        'X-Haven-OG': '1',
    })


def _html_escape(s: str) -> str:
    return (str(s)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#x27;'))


# ============================================================================
# Routes — these MUST mount BEFORE the SPA static fallback in
# control_room_api.py so scrapers see meta tags, not the generic SPA shell.
#
# Real users hitting these paths in a browser get the meta tags briefly then
# the inline JS redirects them to /haven-ui/voyager/:user etc. — perceptually
# instant for any non-headless browser.
# ============================================================================

@router.get('/', response_class=HTMLResponse)
async def og_root(request: Request):
    """Serves the Voyager's Haven landing page with OG meta tags injected
    at the top of <head>. Scrapers grab the dynamic og_site poster + tags;
    real browsers see the full landing page (no redirect to /haven-ui/).

    Falls back to the legacy OG-card-with-redirect template if landing/
    is missing — keeps environments without the landing dir unbroken.
    """
    landing_index = LANDING_DIR / 'index.html'
    if not landing_index.exists():
        return _render_og(build_site_og(), request)

    payload = build_site_og()
    base = str(request.base_url).rstrip('/')
    image_abs = payload['image']
    if image_abs.startswith('/'):
        image_abs = base + image_abs

    og_block = (
        '\n  <!-- Dynamic OG/Twitter tags (injected per-request by SSR). -->\n'
        '  <!-- Scrapers honor the FIRST og:* tag, so these win over the static -->\n'
        '  <!-- block further down in <head>. -->\n'
        f'  <meta property="og:type" content="website">\n'
        f'  <meta property="og:title" content="{_html_escape(payload["title"])}">\n'
        f'  <meta property="og:description" content="{_html_escape(payload["description"])}">\n'
        f'  <meta property="og:image" content="{image_abs}">\n'
        f'  <meta property="og:image:width" content="{payload["image_w"]}">\n'
        f'  <meta property="og:image:height" content="{payload["image_h"]}">\n'
        f'  <meta property="og:url" content="{base}/">\n'
        f'  <meta property="og:site_name" content="Voyager\'s Haven">\n'
        f'  <meta name="twitter:card" content="summary_large_image">\n'
        f'  <meta name="twitter:title" content="{_html_escape(payload["title"])}">\n'
        f'  <meta name="twitter:description" content="{_html_escape(payload["description"])}">\n'
        f'  <meta name="twitter:image" content="{image_abs}">\n'
        f'  <meta name="theme-color" content="#00C2B3">\n'
    )

    html = landing_index.read_text(encoding='utf-8')
    html = html.replace('<head>', '<head>' + og_block, 1)

    return HTMLResponse(html, headers={
        'Cache-Control': 'public, max-age=300, must-revalidate',
        'X-Haven-OG': 'landing',
    })


@router.get('/voyager/{username}', response_class=HTMLResponse)
async def og_voyager(username: str, request: Request):
    return _render_og(build_voyager_og(username), request)


@router.get('/atlas/{galaxy}', response_class=HTMLResponse)
async def og_atlas(galaxy: str, request: Request):
    return _render_og(build_atlas_og(galaxy), request)


@router.get('/systems/{system_id}', response_class=HTMLResponse)
async def og_system(system_id: str, request: Request):
    return _render_og(build_system_og(system_id), request)


@router.get('/community-stats/{tag}', response_class=HTMLResponse)
async def og_community(tag: str, request: Request):
    return _render_og(build_community_og(tag), request)
