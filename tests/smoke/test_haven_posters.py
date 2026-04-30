"""
Smoke tests for Haven's poster rendering endpoints.

These exercise the Playwright + Chromium pipeline — the most flake-prone part
of the smoke suite. Tagged @slow + @p1 so cron throttling kicks in (3-strike
rule from PROPOSAL §5).

Test list (PROPOSAL §3):
  8. test_haven_voyager_poster_renders  — /api/posters/voyager_og/{slug}.png
  9. test_haven_atlas_poster_renders    — /api/posters/atlas/{galaxy}.png
"""

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.slow, pytest.mark.p1]


def test_haven_voyager_poster_renders(
    http_session, haven_base_url, smoke_slow_timeout, poster_remote_username
):
    """Voyager card PNG renders, has plausible body size."""
    slug = poster_remote_username.lower().lstrip("#").rstrip()
    url = f"{haven_base_url}/api/posters/voyager_og/{slug}.png"
    resp = http_session.get(url, timeout=smoke_slow_timeout)
    assert resp.status_code == 200, (
        f"got {resp.status_code} for {url}: {resp.text[:200]}"
    )
    ctype = resp.headers.get("content-type", "")
    assert ctype.startswith("image/png"), f"wrong content-type: {ctype!r}"
    body_len = len(resp.content)
    assert body_len > 5_000, (
        f"poster body suspiciously small ({body_len} bytes); "
        f"renderer may have output a blank canvas"
    )


def test_haven_atlas_poster_renders(
    http_session, haven_base_url, smoke_slow_timeout, poster_remote_galaxy
):
    """Galaxy atlas PNG renders, has plausible body size."""
    from urllib.parse import quote
    galaxy_path = quote(poster_remote_galaxy, safe="")
    url = f"{haven_base_url}/api/posters/atlas/{galaxy_path}.png"
    resp = http_session.get(url, timeout=smoke_slow_timeout)
    assert resp.status_code == 200, (
        f"got {resp.status_code} for {url}: {resp.text[:200]}"
    )
    ctype = resp.headers.get("content-type", "")
    assert ctype.startswith("image/png"), f"wrong content-type: {ctype!r}"
    body_len = len(resp.content)
    assert body_len > 5_000, (
        f"poster body suspiciously small ({body_len} bytes); "
        f"renderer may have output a blank canvas"
    )
