"""
Server-side rendering shim for Open Graph link previews.

Discord, Twitter, Slack, and Reddit scrapers do NOT execute JavaScript. The
Haven UI is a single-page React app that emits the same generic OG tags for
every URL — so when someone pastes /voyager/turpitzz or /atlas/Euclid into
Discord, the resulting embed shows the global Haven preview, never the
specific user's card or galaxy.

This shim intercepts the share-friendly URL patterns BEFORE the SPA static
fallback catches them. The behavior splits by client:

  - Bot scrapers (Discordbot, Twitterbot, etc.): minimal HTML with route-
    specific og:* / twitter:* meta tags. Bots stop at the meta tags, so
    that's all they ever see.
  - Real browsers: the SPA index.html served at the original path. The URL
    stays as /voyager/<slug> in the address bar, and the SPA's own router
    (App.jsx POSTER_ROUTE_PREFIXES) handles the chromeless-poster mode.
    Vite emits absolute /haven-ui/assets/... paths so the static assets
    load from any URL prefix.

Previously this route returned a JS redirect to /haven-ui/voyager/<slug>,
which broke the share URL by changing the address bar. Option A keeps the
URL clean.

Mount before the SPA fallback in control_room_api.py.
"""

import logging
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

logger = logging.getLogger('control.room')

router = APIRouter()

# Resolves to Haven-UI/landing/. Independent of control_room_api so this
# module can be imported without the parent app loaded.
LANDING_DIR = Path(__file__).resolve().parent.parent.parent / 'landing'


# ----------------------------------------------------------------------------
# Bot detection — match against the User-Agent string. Conservative list of
# scraper UAs that don't run JS; anything else falls through to the SPA.
#
# Substrings are matched case-insensitively. Ordered roughly by frequency
# of social-share traffic so the early-out hits common cases first.
# ----------------------------------------------------------------------------

_BOT_UA_SUBSTRINGS = (
    'discordbot',
    'twitterbot',
    'facebookexternalhit',
    'facebot',
    'slackbot',
    'slack-imgproxy',
    'linkedinbot',
    'whatsapp',
    'telegrambot',
    'pinterest',
    'redditbot',
    'embedly',
    'applebot',
    'bingbot',
    'googlebot',
    'iframely',
    'mastodon',
    'snapchat',
    'tumblr',
    'vkshare',
    'yandex',
    'baiduspider',
    'duckduckbot',
)


def is_bot_ua(user_agent: Optional[str]) -> bool:
    if not user_agent:
        # No UA at all is suspicious enough to treat as a bot — real browsers
        # always send one. Scrapers occasionally omit it.
        return True
    ua_lower = user_agent.lower()
    return any(needle in ua_lower for needle in _BOT_UA_SUBSTRINGS)


# ----------------------------------------------------------------------------
# SPA index resolver — mirrors _serve_spa_index() in control_room_api.py.
# Importing that helper would create a circular dependency (this router is
# imported BY control_room_api.py), so we duplicate the path logic here.
# Kept in sync by reading the same HAVEN_UI_DIR layout: dist/index.html
# (production build) with static/index.html as the fallback.
# ----------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_HAVEN_UI_DIR = _BACKEND_DIR.parent

_SPA_INDEX_CANDIDATES = (
    _HAVEN_UI_DIR / 'dist' / 'index.html',
    _HAVEN_UI_DIR / 'static' / 'index.html',
)


def _serve_spa_index_response():
    """Return a FileResponse for the SPA index, or 404 HTML if the build is missing."""
    for candidate in _SPA_INDEX_CANDIDATES:
        if candidate.exists():
            # No-cache headers — index.html must always be revalidated so a
            # new asset bundle hash is picked up immediately on deploy.
            return FileResponse(
                str(candidate),
                media_type='text/html',
                headers={'Cache-Control': 'no-cache, no-store, must-revalidate'},
            )
    return HTMLResponse('<h1>Haven UI not found</h1>', status_code=404)


# ============================================================================
# OG payload builders — one per share-route pattern.
# Each returns a dict {title, description, image, image_w, image_h, url}.
# ============================================================================

def _ogcard(poster_type: str, key: str, w: int = 1200, h: int = 630) -> str:
    """Construct the absolute PNG URL for the given poster + key."""
    safe_key = quote(key, safe='')
    return f'/api/posters/{poster_type}/{safe_key}.png'


def build_site_og() -> dict:
    """Root domain OG payload — havenmap.online itself shows the landing card.

    Uses landing_og (cosmic-compass + Cinzel wordmark + 3 live stats) so
    Discord/Twitter previews match the landing page aesthetic. The older
    og_site card stays in the registry for any callers that still pin to it,
    but is no longer the default at the root URL.
    """
    return {
        'title': "Voyager's Haven — a community atlas of No Man's Sky",
        'description': "Browse, name, and map No Man's Sky discoveries together. Live data from havenmap.online.",
        'image': _ogcard('landing_og', 'global'),
        'image_w': 1200,
        'image_h': 630,
        'url': '/',
    }


def build_voyager_og(username: str) -> dict:
    # The URL slug uses hyphens for spaces (e.g. /voyager/hiroki-rinn). For the
    # human-facing OG title we want "Hiroki Rinn" — image and canonical URLs
    # stay on the raw slug so scrapers fetch the right card.
    display_name = username.replace('-', ' ').strip().title() or username
    return {
        'title': f"{display_name} — Voyager's Haven",
        'description': f"{display_name}'s galaxy fingerprint card. Live data from havenmap.online.",
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
</head>
<body style="background:#0a0e2a;color:#e0e7ff;font-family:system-ui,sans-serif;">
  <p style="padding:32px;">
    <a href="{url_abs}" style="color:#00C2B3;">Open in Voyager's Haven</a>
  </p>
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
# control_room_api.py so bot scrapers see meta tags, not the generic SPA shell.
#
# Per-route browser behavior:
#   - Poster routes (/voyager, /atlas): serve the SPA index AT THE ORIGINAL
#     PATH so the URL bar stays clean. The SPA's <BrowserRouter> picks an
#     empty basename when the pathname starts with a poster prefix
#     (see Haven-UI/src/main.jsx) so its routes match without /haven-ui.
#   - Chromed share routes (/, /systems/:id, /community-stats/:tag): 302
#     redirect to the equivalent /haven-ui/... path. Those pages render
#     full chrome (Navbar etc.) which depend on the basename being set,
#     and use <Link> nav that needs the prefix.
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
    if is_bot_ua(request.headers.get('user-agent')):
        return _render_og(build_voyager_og(username), request)
    return _serve_spa_index_response()


@router.get('/atlas/{galaxy}', response_class=HTMLResponse)
async def og_atlas(galaxy: str, request: Request):
    if is_bot_ua(request.headers.get('user-agent')):
        return _render_og(build_atlas_og(galaxy), request)
    return _serve_spa_index_response()


@router.get('/systems/{system_id}', response_class=HTMLResponse)
async def og_system(system_id: str, request: Request):
    if is_bot_ua(request.headers.get('user-agent')):
        return _render_og(build_system_og(system_id), request)
    return RedirectResponse(
        url=f'/haven-ui/systems/{quote(system_id, safe="")}',
        status_code=302,
    )


@router.get('/community-stats/{tag}', response_class=HTMLResponse)
async def og_community(tag: str, request: Request):
    if is_bot_ua(request.headers.get('user-agent')):
        return _render_og(build_community_og(tag), request)
    return RedirectResponse(
        url=f'/haven-ui/community-stats/{quote(tag, safe="")}',
        status_code=302,
    )
