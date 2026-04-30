"""
Smoke tests against the live Haven backend.

These hit the actual HTTP endpoints — either localhost:8005 (Pi cron mode)
or https://havenmap.online (Win-dev manual mode). Read-only. No DB writes.

Test list (PROPOSAL §3):
  1. test_haven_status_ok            — GET /api/status
  2. test_haven_db_stats_sane        — GET /api/db_stats
  3. test_haven_communities_listed   — GET /api/communities
  4. test_haven_systems_paged        — GET /api/systems?limit=10
"""

import re
import pytest

pytestmark = pytest.mark.smoke

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def test_haven_status_ok(http_session, haven_base_url, smoke_timeout):
    """Liveness probe — same endpoint Haven-UI/docker-compose.yml healthchecks."""
    resp = http_session.get(f"{haven_base_url}/api/status", timeout=smoke_timeout)
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert body.get("status") == "ok", f"unexpected status field: {body!r}"
    version = body.get("version")
    assert version and SEMVER_RE.match(version), (
        f"version {version!r} doesn't match semver pattern"
    )


def test_haven_db_stats_sane(http_session, haven_base_url, smoke_timeout):
    """DB connectivity + sanity. Uses lower-bound assertions only (Q9)."""
    resp = http_session.get(f"{haven_base_url}/api/db_stats", timeout=smoke_timeout)
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()

    # Top-level shape — every numeric field is a non-negative integer.
    # We accept whichever key set the endpoint actually returns; just verify
    # that any numeric value is sane.
    numeric_keys = [k for k, v in body.items() if isinstance(v, (int, float))]
    assert numeric_keys, f"no numeric stat fields in response: {list(body.keys())}"
    for k in numeric_keys:
        assert body[k] >= 0, f"stat {k!r} is negative: {body[k]}"

    # Loose floor — the production DB has thousands of systems. Assert
    # >= 100 as a "the schema and table exist and have data" check, not a
    # measure of growth. Per PROPOSAL §10.5, this needs rebaselining at
    # the 6-month review.
    candidate_total_keys = (
        "total_systems", "systems", "system_count", "system_total",
    )
    total = next((body.get(k) for k in candidate_total_keys if k in body), None)
    if total is not None:
        assert total >= 100, (
            f"expected a populated systems count (>=100), got {total}. "
            "If the live DB is genuinely <100 systems, rebaseline this floor."
        )


def test_haven_communities_listed(http_session, haven_base_url, smoke_timeout):
    """At least one Discord community partner is registered + visible."""
    resp = http_session.get(f"{haven_base_url}/api/communities", timeout=smoke_timeout)
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()

    # Endpoint may return either a list or a {"communities": [...]} envelope.
    # Tolerate both.
    if isinstance(body, dict):
        communities = body.get("communities", body.get("items", []))
    else:
        communities = body

    assert isinstance(communities, list), f"expected list, got {type(communities)}"
    assert len(communities) >= 1, "no communities returned"

    first = communities[0]
    assert isinstance(first, dict), f"community entries should be dicts, got {first!r}"
    # Tolerate either schema; both `name` and `tag` (or `discord_tag`) are
    # documented in different places.
    name_key = next((k for k in ("name", "display_name", "community_name")
                     if k in first), None)
    tag_key = next((k for k in ("tag", "discord_tag", "slug") if k in first), None)
    assert name_key, f"community has no name-like field: {list(first.keys())}"
    assert tag_key, f"community has no tag-like field: {list(first.keys())}"


def test_haven_systems_paged(http_session, haven_base_url, smoke_timeout):
    """Page-1 systems query returns up to `limit` rows with the expected shape."""
    resp = http_session.get(
        f"{haven_base_url}/api/systems",
        params={"limit": 10, "page": 1},
        timeout=smoke_timeout,
    )
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()

    # The endpoint may return either a list or a {"systems": [...]} envelope.
    if isinstance(body, dict):
        systems = body.get("systems", body.get("items", body.get("data", [])))
    else:
        systems = body

    assert isinstance(systems, list), f"expected list, got {type(systems)}"
    assert len(systems) <= 10, f"limit=10 was ignored: got {len(systems)} rows"

    if systems:
        first = systems[0]
        assert isinstance(first, dict)
        # Required canonical fields per the systems schema.
        for key in ("id", "glyph_code", "galaxy"):
            assert key in first, (
                f"system row missing {key!r}; got keys {list(first.keys())}"
            )
