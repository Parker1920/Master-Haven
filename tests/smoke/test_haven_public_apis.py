"""
Smoke tests for Haven's public APIs that feed the poster service.

These are the data sources for /fingerprint and /atlas slash commands.
If they return wrong-shape data, the posters render blank.

Test list (PROPOSAL §3):
  6. test_haven_voyager_fingerprint_api  — GET /api/public/voyager-fingerprint
  7. test_haven_galaxy_atlas_api         — GET /api/public/galaxy-atlas
"""

import pytest

pytestmark = pytest.mark.smoke


def test_haven_voyager_fingerprint_api(
    http_session, haven_base_url, smoke_timeout, poster_remote_username
):
    """Public voyager-fingerprint endpoint returns valid JSON for a real user."""
    resp = http_session.get(
        f"{haven_base_url}/api/public/voyager-fingerprint",
        params={"username": poster_remote_username},
        timeout=smoke_timeout,
    )
    # Endpoint may legitimately 404 if the username has no contributions.
    # In smoke we want PASS only if the username exists; fail otherwise so
    # Parker rebaselines POSTER_REMOTE_USERNAME if needed.
    assert resp.status_code == 200, (
        f"got {resp.status_code} for username={poster_remote_username!r}: "
        f"{resp.text[:200]}. If this username has no Haven contributions, "
        f"set POSTER_REMOTE_USERNAME in tests/.env to one that does."
    )
    body = resp.json()
    assert isinstance(body, dict), f"expected dict, got {type(body)}"
    # Don't pin specific keys — the endpoint is being iterated. Just assert
    # the response is a non-empty mapping.
    assert len(body) >= 1, f"empty response body: {body!r}"


def test_haven_galaxy_atlas_api(
    http_session, haven_base_url, smoke_timeout, poster_remote_galaxy
):
    """Public galaxy-atlas endpoint returns valid JSON for Euclid (or whatever
    galaxy is configured)."""
    resp = http_session.get(
        f"{haven_base_url}/api/public/galaxy-atlas",
        params={"galaxy": poster_remote_galaxy},
        timeout=smoke_timeout,
    )
    assert resp.status_code == 200, (
        f"got {resp.status_code} for galaxy={poster_remote_galaxy!r}: "
        f"{resp.text[:200]}"
    )
    body = resp.json()
    assert isinstance(body, dict), f"expected dict, got {type(body)}"
    assert len(body) >= 1, f"empty response body: {body!r}"
