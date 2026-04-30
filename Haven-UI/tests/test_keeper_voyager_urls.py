"""
Smoke tests for The_Keeper/cmds/voyager.py URL construction.

Pre-deploy verification of the Keeper bot's /fingerprint and /atlas
slash-command URL plumbing. The original bug: HAVEN_API was set to
http://haven:8005 (internal docker URL) on the Pi, and voyager.py
embedded that into Discord embed image URLs. Discord rejects with
'400 Not a well formed URL' because `haven:8005` has no TLD and is
unreachable from outside the LAN.

The fix splits internal vs. public URL: HAVEN_API stays the
internal-call variable (other cogs use it that way), and a new
HAVEN_PUBLIC_URL drives anything bound for Discord embeds. These
tests exercise the resolver, the docker-URL guard, and verify no
internal hostnames can leak into a constructed embed URL.

We can't easily test the discord.py async slash-command bodies, so
we test the URL building deterministically:
  - HAVEN_PUBLIC_URL resolution (env precedence)
  - The docker-URL guard
  - The slug normalizer (mirror of frontend)
  - URL templates that the cog actually builds at runtime

Run from repo root:
    py -m pytest Haven-UI/tests/test_keeper_voyager_urls.py -v
"""
import importlib
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, quote

import pytest

HERE = Path(__file__).resolve().parent
KEEPER_DIR = HERE.parent.parent / 'The_Keeper'
if str(KEEPER_DIR) not in sys.path:
    sys.path.insert(0, str(KEEPER_DIR))


# Env vars voyager.py inspects. Cleared between tests so each scenario starts
# from a known state — the module reads os.environ at import time.
ENV_VARS = ('HAVEN_PUBLIC_URL', 'HAVEN_URL', 'HAVEN_API')


def reload_voyager(monkeypatch, **env):
    """Force voyager.py to re-evaluate its module-level URL constants."""
    for v in ENV_VARS:
        monkeypatch.delenv(v, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    if 'cmds.voyager' in sys.modules:
        del sys.modules['cmds.voyager']
    return importlib.import_module('cmds.voyager')


# ===========================================================================
# 1. HAVEN_PUBLIC_URL resolution — env precedence.
# ===========================================================================

class TestHavenPublicUrlResolution:
    def test_explicit_public_url_wins(self, monkeypatch):
        v = reload_voyager(monkeypatch, HAVEN_PUBLIC_URL='https://staging.havenmap.online')
        assert v.HAVEN_PUBLIC_URL == 'https://staging.havenmap.online'

    def test_falls_back_to_haven_url(self, monkeypatch):
        # No HAVEN_PUBLIC_URL set, but HAVEN_URL is — use it.
        v = reload_voyager(monkeypatch, HAVEN_URL='https://havenmap.online')
        assert v.HAVEN_PUBLIC_URL == 'https://havenmap.online'

    def test_default_when_neither_set(self, monkeypatch):
        # Both unset — default to the production public domain.
        v = reload_voyager(monkeypatch)
        assert v.HAVEN_PUBLIC_URL == 'https://havenmap.online'

    def test_haven_api_does_not_leak_to_public_url(self, monkeypatch):
        # The original bug: HAVEN_API was the only var set, and the bot
        # used it for embeds. The new resolver MUST NOT consider HAVEN_API.
        v = reload_voyager(monkeypatch, HAVEN_API='http://haven:8005')
        assert v.HAVEN_PUBLIC_URL == 'https://havenmap.online'
        assert v.HAVEN_PUBLIC_URL != 'http://haven:8005'

    def test_trailing_slash_stripped(self, monkeypatch):
        # f"{HAVEN_PUBLIC_URL}/voyager/x" must not produce //.
        v = reload_voyager(monkeypatch, HAVEN_PUBLIC_URL='https://havenmap.online/')
        assert v.HAVEN_PUBLIC_URL == 'https://havenmap.online'

    def test_multiple_trailing_slashes_stripped(self, monkeypatch):
        v = reload_voyager(monkeypatch, HAVEN_PUBLIC_URL='https://havenmap.online///')
        assert v.HAVEN_PUBLIC_URL == 'https://havenmap.online'


# ===========================================================================
# 2. Docker-URL guard — internal hostnames can't leak into Discord embeds.
# ===========================================================================

class TestDockerUrlGuard:
    def test_haven_internal_url_snapped_to_default(self, monkeypatch):
        # Someone copies HAVEN_API into HAVEN_PUBLIC_URL by mistake. The
        # guard must catch it — Discord can't fetch from `haven:8005`.
        v = reload_voyager(monkeypatch, HAVEN_PUBLIC_URL='http://haven:8005')
        assert v.HAVEN_PUBLIC_URL == 'https://havenmap.online'

    def test_haven_internal_via_haven_url_fallback_also_caught(self, monkeypatch):
        # Same mistake but via the legacy HAVEN_URL fallback path.
        v = reload_voyager(monkeypatch, HAVEN_URL='http://haven:8005')
        assert v.HAVEN_PUBLIC_URL == 'https://havenmap.online'

    def test_haven_internal_with_path_also_caught(self, monkeypatch):
        # The Pi's current .env actually has HAVEN_URL=https://havenmap.online/map/latest,
        # which is wrong but not internal. This test pins the docker-URL-only
        # guard — it should NOT munge non-docker URLs even if they're broken
        # in other ways.
        v = reload_voyager(monkeypatch, HAVEN_URL='https://havenmap.online/map/latest')
        # rstrip('/') only strips trailing slashes, not paths. The /map/latest
        # is fixable by the operator, not by code.
        assert v.HAVEN_PUBLIC_URL == 'https://havenmap.online/map/latest'

    def test_other_internal_hostnames_not_caught(self, monkeypatch):
        # The guard is intentionally narrow — only matches the specific
        # `haven:` docker hostname pattern. Document that behavior.
        v = reload_voyager(monkeypatch, HAVEN_PUBLIC_URL='http://localhost:8005')
        assert v.HAVEN_PUBLIC_URL == 'http://localhost:8005'


# ===========================================================================
# 3. Slug normalizer — mirrors the frontend identity.js (hyphenless variant).
# ===========================================================================

class TestNormalizeUsernameForUrl:
    @pytest.fixture
    def voyager(self, monkeypatch):
        return reload_voyager(monkeypatch)

    def test_strips_discriminator(self, voyager):
        assert voyager.normalize_username_for_url('TurpitZz#9999') == 'turpitzz'

    def test_lowercases(self, voyager):
        assert voyager.normalize_username_for_url('Turpitzz') == 'turpitzz'

    def test_handles_empty(self, voyager):
        assert voyager.normalize_username_for_url('') == ''
        assert voyager.normalize_username_for_url(None) == ''

    def test_preserves_internal_digits(self, voyager):
        # Don't strip a 4-digit suffix when the char before it is a digit.
        assert voyager.normalize_username_for_url('X1234567') == 'x1234567'

    def test_strips_hash_only(self, voyager):
        # The Keeper-side normalizer is simpler than the frontend slugifier:
        # it strips '#' and discriminator and lowercases. It does NOT convert
        # spaces to hyphens — that's done by the frontend's URL builder.
        # Confirm that contract: the keeper's job is just lowercase normalize.
        assert voyager.normalize_username_for_url('Hiroki Rinn') == 'hiroki rinn'


# ===========================================================================
# 4. URL templates — what the cog actually builds at runtime.
# ===========================================================================

class TestUrlTemplates:
    """Reconstruct the f-strings inside fingerprint() and atlas() and verify
    properties of the resulting URLs. The cog's slash-command callbacks are
    async + take Discord interactions, so we don't invoke them — but the URL
    template they use is short and unambiguous."""

    @pytest.fixture
    def voyager(self, monkeypatch):
        # Default env — HAVEN_PUBLIC_URL falls through to default.
        return reload_voyager(monkeypatch)

    def test_voyager_png_url_shape(self, voyager):
        slug = voyager.normalize_username_for_url('Hiroki Rinn').replace(' ', '-')
        # Mirror cmds/voyager.py:138.
        png = f'{voyager.HAVEN_PUBLIC_URL}/api/posters/voyager_og/{slug}.png?v=29658360'
        assert png == 'https://havenmap.online/api/posters/voyager_og/hiroki-rinn.png?v=29658360'

    def test_voyager_page_url_shape(self, voyager):
        slug = 'turpitzz'
        page = f'{voyager.HAVEN_PUBLIC_URL}/voyager/{slug}'
        assert page == 'https://havenmap.online/voyager/turpitzz'

    def test_atlas_png_url_with_space_galaxy(self, voyager):
        # Mirror cmds/voyager.py:189–190.
        galaxy = 'Hilbert Dimension'
        galaxy_path = quote(galaxy, safe='')
        png = f'{voyager.HAVEN_PUBLIC_URL}/api/posters/atlas/{galaxy_path}.png?v=29658360'
        # Spaces percent-encoded — Discord parses this as a valid URL.
        assert png == 'https://havenmap.online/api/posters/atlas/Hilbert%20Dimension.png?v=29658360'
        assert ' ' not in png  # No raw spaces, ever.

    def test_atlas_page_url_with_space_galaxy(self, voyager):
        galaxy = 'Hilbert Dimension'
        galaxy_path = quote(galaxy, safe='')
        page = f'{voyager.HAVEN_PUBLIC_URL}/atlas/{galaxy_path}'
        assert page == 'https://havenmap.online/atlas/Hilbert%20Dimension'
        assert ' ' not in page

    def test_atlas_simple_galaxy(self, voyager):
        galaxy_path = quote('Euclid', safe='')
        png = f'{voyager.HAVEN_PUBLIC_URL}/api/posters/atlas/{galaxy_path}.png?v=29658360'
        assert png == 'https://havenmap.online/api/posters/atlas/Euclid.png?v=29658360'


# ===========================================================================
# 5. No internal docker URLs in any constructed URL — the regression check.
# ===========================================================================

class TestNoDockerUrlsLeak:
    """The bug class we're guarding against: an internal docker hostname
    landing inside a Discord embed URL. This test exercises the most
    plausible misconfiguration combos and asserts the resolver wins."""

    @pytest.mark.parametrize('env', [
        # The exact Pi misconfiguration that triggered the original bug.
        {'HAVEN_API': 'http://haven:8005'},
        # Same but with the wrong-path HAVEN_URL also present.
        {
            'HAVEN_API': 'http://haven:8005',
            'HAVEN_URL': 'https://havenmap.online/map/latest',
        },
        # Operator copies HAVEN_API into HAVEN_PUBLIC_URL.
        {
            'HAVEN_PUBLIC_URL': 'http://haven:8005',
            'HAVEN_API': 'http://haven:8005',
        },
        # No env at all.
        {},
    ])
    def test_no_internal_hostname_in_resolved_url(self, monkeypatch, env):
        v = reload_voyager(monkeypatch, **env)
        public = v.HAVEN_PUBLIC_URL
        # No 'haven:' hostname (with port).
        assert '://haven:' not in public, f'leak: {public!r}'
        # Parsed hostname must contain a dot (TLD) — Discord's URL validator
        # rejects bare-hostname URLs.
        host = urlparse(public).hostname or ''
        assert '.' in host, f'hostname {host!r} has no TLD: {public!r}'
        # Scheme must be http(s).
        assert urlparse(public).scheme in ('http', 'https')

    @pytest.mark.parametrize('env,slug,galaxy', [
        ({}, 'hiroki-rinn', 'Hilbert Dimension'),
        ({'HAVEN_API': 'http://haven:8005'}, 'turpitzz', 'Euclid'),
        (
            {'HAVEN_PUBLIC_URL': 'http://haven:8005'},  # caught by guard
            'parker',
            'Calypso',
        ),
    ])
    def test_constructed_urls_safe_for_discord(self, monkeypatch, env, slug, galaxy):
        v = reload_voyager(monkeypatch, **env)
        galaxy_path = quote(galaxy, safe='')
        urls = [
            f'{v.HAVEN_PUBLIC_URL}/api/posters/voyager_og/{slug}.png?v=1',
            f'{v.HAVEN_PUBLIC_URL}/voyager/{slug}',
            f'{v.HAVEN_PUBLIC_URL}/api/posters/atlas/{galaxy_path}.png?v=1',
            f'{v.HAVEN_PUBLIC_URL}/atlas/{galaxy_path}',
        ]
        for url in urls:
            parsed = urlparse(url)
            assert parsed.scheme in ('http', 'https'), f'bad scheme: {url}'
            assert parsed.hostname, f'no host: {url}'
            assert '.' in parsed.hostname, f'no TLD: {url}'
            assert ' ' not in url, f'raw space in url: {url}'
            url.encode('ascii')  # No surprise unicode in the URL.


# ===========================================================================
# 6. .env.example — confirms the new env var is documented for operators.
# ===========================================================================

class TestEnvExample:
    @pytest.fixture
    def env_example(self):
        path = KEEPER_DIR / '.env.example'
        return path.read_text(encoding='utf-8')

    def test_haven_public_url_documented(self, env_example):
        assert 'HAVEN_PUBLIC_URL' in env_example, (
            '.env.example must document HAVEN_PUBLIC_URL — operators need '
            'to know to set it on the Pi'
        )

    def test_default_value_present(self, env_example):
        # The example should suggest the public URL as the value.
        assert 'havenmap.online' in env_example

    def test_internal_haven_api_documented(self, env_example):
        # Both the internal and public variables should be documented so the
        # operator understands they're distinct.
        assert 'HAVEN_API' in env_example
        assert 'haven:8005' in env_example, (
            '.env.example should show the internal docker URL example for HAVEN_API'
        )
