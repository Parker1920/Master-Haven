"""
Smoke test for Haven Exchange.

Just confirms the container is responding. The 52-scenario in-process suite
in Haven-Exchange/tests/smoke_test_e2e.py covers behavior comprehensively;
this is liveness-only.

Test list (PROPOSAL §3):
  5. test_exchange_health_ok — GET /health
"""

import pytest

pytestmark = pytest.mark.smoke


def test_exchange_health_ok(http_session, exchange_base_url, smoke_timeout):
    resp = http_session.get(f"{exchange_base_url}/health", timeout=smoke_timeout)
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert body.get("status") == "ok", f"unexpected status: {body!r}"
    assert body.get("service") == "Travelers Exchange", (
        f"unexpected service identifier: {body!r}"
    )
