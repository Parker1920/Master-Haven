"""
Smoke tests for the SSR shim in routes/ssr.py.

Pre-deploy verification of the bot-vs-browser URL routing fix:

  - Bot scrapers (Discordbot, Twitterbot, etc.) get OG meta HTML so social
    embeds show the right card.
  - Real browsers on poster routes (/voyager, /atlas) get the SPA index
    served IN PLACE — no JS redirect, URL stays clean.
  - Real browsers on chromed routes (/, /systems/:id, /community-stats/:tag)
    get a server-side 302 to /haven-ui/...

Also pins:
  - og:image in index.html points at the dynamic poster, not haven-preview.png.
  - main.jsx selects basename based on poster path prefix.

The tests mount only the SSR APIRouter on a fresh FastAPI app — the full
control_room_api.py boot brings up DB / migrations / auth which we don't
need here. The SPA-index file is monkeypatched to a tmp file because the
worktree typically has no dist/ build (built only on deploy).

Run from repo root:
    py -m pytest Haven-UI/tests/test_ssr_routing.py -v
"""
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from routes import ssr  # noqa: E402  — sys.path tweak must precede import


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spa_index(tmp_path, monkeypatch):
    """Point ssr._SPA_INDEX_CANDIDATES at a tmp file with a known SPA shell.

    The real index.html in production has <div id="root"> + Vite-injected
    asset tags. We mimic that minimally so tests can assert the SPA index
    was served (vs the OG template, which has no #root).
    """
    f = tmp_path / 'index.html'
    f.write_text(
        '<!DOCTYPE html><html><head><title>Haven</title></head>'
        '<body><div id="root"></div>'
        '<script type="module" src="/haven-ui/assets/index.js"></script>'
        '</body></html>',
        encoding='utf-8',
    )
    monkeypatch.setattr(ssr, '_SPA_INDEX_CANDIDATES', (f,))
    return f


@pytest.fixture
def client(spa_index):
    app = FastAPI()
    app.include_router(ssr.router)
    return TestClient(app)


# Two bot UAs — Discord and Twitter cover the social-share case.
BOT_UAS = [
    'Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)',
    'Twitterbot/1.0',
]

# A current Chrome desktop UA — the browser path.
CHROME_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)


# ===========================================================================
# 1. Bot UA — every share route returns OG meta HTML.
# ===========================================================================

class TestBotUserAgent:
    @pytest.mark.parametrize('ua', BOT_UAS)
    def test_voyager_serves_og(self, client, ua):
        r = client.get('/voyager/hiroki-rinn', headers={'user-agent': ua})
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('text/html')
        # Has OG meta tags
        assert 'property="og:image"' in r.text
        assert 'property="og:title"' in r.text
        # Title has the title-cased display name (slug → "Hiroki Rinn")
        assert 'Hiroki Rinn' in r.text
        # Header marker confirms this is the OG path, not the SPA index
        assert r.headers.get('x-haven-og') == '1'

    @pytest.mark.parametrize('ua', BOT_UAS)
    def test_atlas_serves_og(self, client, ua):
        r = client.get('/atlas/Euclid', headers={'user-agent': ua})
        assert r.status_code == 200
        assert 'property="og:image"' in r.text
        assert 'Euclid' in r.text
        assert r.headers.get('x-haven-og') == '1'

    @pytest.mark.parametrize('ua', BOT_UAS)
    def test_systems_serves_og(self, client, ua):
        r = client.get('/systems/123', headers={'user-agent': ua})
        assert r.status_code == 200
        assert 'property="og:image"' in r.text
        assert r.headers.get('x-haven-og') == '1'

    @pytest.mark.parametrize('ua', BOT_UAS)
    def test_community_serves_og(self, client, ua):
        r = client.get('/community-stats/Haven', headers={'user-agent': ua})
        assert r.status_code == 200
        assert 'property="og:image"' in r.text
        assert 'Haven' in r.text
        assert r.headers.get('x-haven-og') == '1'

    @pytest.mark.parametrize('ua', BOT_UAS)
    def test_root_serves_og_site_card(self, client, ua):
        r = client.get('/', headers={'user-agent': ua})
        assert r.status_code == 200
        assert 'property="og:image"' in r.text
        # Root card is the "Voyager's Haven" site preview
        assert "Voyager's Haven" in r.text
        assert r.headers.get('x-haven-og') == '1'


# ===========================================================================
# 2. Bot UA — og:image URL is well-formed and points at /api/posters/.
# ===========================================================================

class TestOgImageWellFormed:
    @pytest.mark.parametrize('path,frag', [
        ('/voyager/hiroki-rinn', '/api/posters/voyager_og/hiroki-rinn'),
        ('/atlas/Euclid', '/api/posters/atlas/Euclid'),
        ('/systems/123', '/api/posters/og_system/123'),
        ('/community-stats/Haven', '/api/posters/og_community/Haven'),
        ('/', '/api/posters/og_site/global'),
    ])
    def test_image_url_points_at_poster_endpoint(self, client, path, frag):
        r = client.get(path, headers={'user-agent': 'Discordbot/2.0'})
        assert r.status_code == 200
        # Extract og:image content
        import re
        m = re.search(r'property="og:image"\s+content="([^"]+)"', r.text)
        assert m, f'og:image meta tag missing for {path}'
        url = m.group(1)
        # Must be absolute http(s) URL — Discord rejects bare paths
        assert url.startswith('http://') or url.startswith('https://'), (
            f'og:image not absolute URL: {url!r}'
        )
        # Must point at the live poster service, not a static file
        assert frag in url, f'og:image {url!r} missing fragment {frag!r}'
        # Must NOT contain internal docker hostnames
        assert '://haven:' not in url, f'og:image leaks internal hostname: {url!r}'
        # Plain ASCII path — no surprise unicode that'd trip Discord
        url.encode('ascii')


# ===========================================================================
# 3. Browser UA — poster routes serve SPA index in place; chromed routes 302.
# ===========================================================================

class TestBrowserUserAgent:
    def test_voyager_serves_spa_index(self, client):
        r = client.get('/voyager/hiroki-rinn', headers={'user-agent': CHROME_UA})
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('text/html')
        # Hallmark of the SPA index, not the OG template
        assert '<div id="root">' in r.text
        # OG header should NOT be present (that's the bot path)
        assert 'x-haven-og' not in (k.lower() for k in r.headers.keys())
        # Browsers on poster routes must NOT see the OG image meta — they
        # got the SPA shell, which has its own (generic) og:image set in
        # index.html. We accept that — the SSR shim only personalizes for bots.

    def test_atlas_serves_spa_index(self, client):
        r = client.get('/atlas/Euclid', headers={'user-agent': CHROME_UA})
        assert r.status_code == 200
        assert '<div id="root">' in r.text

    def test_root_redirects_to_haven_ui(self, client):
        r = client.get('/', headers={'user-agent': CHROME_UA}, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers['location'] == '/haven-ui/'

    def test_systems_redirects_to_haven_ui(self, client):
        r = client.get('/systems/123', headers={'user-agent': CHROME_UA}, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers['location'] == '/haven-ui/systems/123'

    def test_community_redirects_to_haven_ui(self, client):
        r = client.get('/community-stats/Haven', headers={'user-agent': CHROME_UA}, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers['location'] == '/haven-ui/community-stats/Haven'

    def test_chromed_redirect_preserves_special_chars(self, client):
        # Galaxy with a space → percent-encoded in redirect target.
        # systems/:id is the path we exercise here since atlas is a poster route.
        r = client.get('/systems/abc def', headers={'user-agent': CHROME_UA}, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers['location'] == '/haven-ui/systems/abc%20def'


# ===========================================================================
# 4. Edge cases.
# ===========================================================================

class TestEdgeCases:
    def test_no_user_agent_treated_as_bot(self, client):
        # Real browsers always send a UA. Missing = scraper. Serves OG.
        # httpx defaults to its own UA, so we explicitly clear it.
        r = client.get('/voyager/hiroki-rinn', headers={'user-agent': ''})
        assert r.status_code == 200
        assert r.headers.get('x-haven-og') == '1'

    def test_voyager_with_no_username_404s(self, client):
        # Trailing-slash form has no path param to bind to {username}.
        # FastAPI returns 404 (route doesn't match without a value).
        r = client.get('/voyager/', headers={'user-agent': 'Discordbot/2.0'})
        # FastAPI may redirect or 404 here depending on trailing-slash policy;
        # accept either, but reject 200 (which would mean a bogus card was rendered).
        assert r.status_code in (404, 307), (
            f'/voyager/ with empty user should not 200, got {r.status_code}'
        )

    def test_curl_user_agent_treated_as_bot(self, client):
        # curl/wget are scraper-like — treated as bot is harmless (they get
        # a static HTML page) and arguably more useful than a redirect they
        # then need to follow.
        r = client.get('/voyager/hiroki-rinn', headers={'user-agent': 'curl/8.0.0'})
        # Either branch is acceptable; just verify it doesn't crash.
        assert r.status_code in (200, 302)

    def test_googlebot_treated_as_bot(self, client):
        # Googlebot is on our bot list — should see OG meta even though it
        # can run JS. The OG is more cacheable / more reliable.
        r = client.get(
            '/voyager/hiroki-rinn',
            headers={'user-agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'},
        )
        assert r.status_code == 200
        assert r.headers.get('x-haven-og') == '1'


# ===========================================================================
# 5. is_bot_ua unit coverage — the matching itself.
# ===========================================================================

class TestIsBotUa:
    @pytest.mark.parametrize('ua', [
        'Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)',
        'Twitterbot/1.0',
        'facebookexternalhit/1.1',
        'Slackbot-LinkExpanding 1.0',
        'LinkedInBot/1.0',
        'WhatsApp/2.21.12.21 A',
        'TelegramBot (like TwitterBot)',
        'redditbot/1.0',
        'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
    ])
    def test_known_bots(self, ua):
        assert ssr.is_bot_ua(ua) is True

    @pytest.mark.parametrize('ua', [
        CHROME_UA,
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148',
    ])
    def test_known_browsers(self, ua):
        assert ssr.is_bot_ua(ua) is False

    def test_empty_ua_is_bot(self):
        assert ssr.is_bot_ua('') is True

    def test_none_ua_is_bot(self):
        assert ssr.is_bot_ua(None) is True

    def test_case_insensitive(self):
        assert ssr.is_bot_ua('DISCORDBOT/2.0') is True
        assert ssr.is_bot_ua('discordbot/2.0') is True


# ===========================================================================
# 6. index.html — og:image points at the dynamic poster, not haven-preview.png.
# ===========================================================================

class TestIndexHtmlOgTags:
    @pytest.fixture
    def index_html(self):
        path = HERE.parent / 'index.html'
        return path.read_text(encoding='utf-8')

    def test_og_image_points_at_dynamic_poster(self, index_html):
        # og:image must be the dynamic global site card, not the static PNG.
        # We assert positively (must be there) and negatively (must be gone).
        assert '/api/posters/og_site/global.png' in index_html
        assert 'haven-preview.png' not in index_html

    def test_twitter_image_matches(self, index_html):
        # Twitter:image and og:image should be the same dynamic URL.
        import re
        og = re.search(r'property="og:image"\s+content="([^"]+)"', index_html)
        tw = re.search(r'name="twitter:image"\s+content="([^"]+)"', index_html)
        assert og, 'og:image meta missing from index.html'
        assert tw, 'twitter:image meta missing from index.html'
        assert og.group(1) == tw.group(1), (
            f'og:image ({og.group(1)!r}) and twitter:image ({tw.group(1)!r}) drifted'
        )

    def test_og_url_no_haven_ui_prefix(self, index_html):
        # Site card og:url should be the bare domain — the SSR shim now
        # serves bots OG at the bare path, and we want canonical URLs to
        # match what's shareable.
        import re
        m = re.search(r'property="og:url"\s+content="([^"]+)"', index_html)
        assert m, 'og:url missing from index.html'
        assert m.group(1) == 'https://havenmap.online/', (
            f'og:url should be the bare domain, got {m.group(1)!r}'
        )


# ===========================================================================
# 7. main.jsx — conditional basename pattern present.
# ===========================================================================

class TestMainJsxBasename:
    @pytest.fixture
    def main_jsx(self):
        path = HERE.parent / 'src' / 'main.jsx'
        return path.read_text(encoding='utf-8')

    def test_conditional_basename_present(self, main_jsx):
        # Verify the prefix list matches the App.jsx POSTER_ROUTE_PREFIXES.
        # If they drift, share URLs break — keep this assertion strict.
        for prefix in ('/voyager/', '/atlas/', '/poster/'):
            assert prefix in main_jsx, (
                f'main.jsx missing poster prefix {prefix!r} — share URLs will break'
            )

    def test_basename_is_passed_to_router(self, main_jsx):
        # The Router receives the dynamic basename, not the literal "/haven-ui".
        # We can't run JSX, but we can check that the JSX uses the variable
        # name that the conditional logic computes.
        assert 'basename={routerBasename}' in main_jsx, (
            'main.jsx not wiring routerBasename into BrowserRouter'
        )
        # And the variable itself must be derived from window.location.
        assert 'window.location.pathname' in main_jsx, (
            'main.jsx not reading window.location.pathname for basename selection'
        )
