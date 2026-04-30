"""
Verification tests for /api/extraction.

Exercises the actual handler against an in-process Haven backend backed by
a throwaway SQLite DB. No live infrastructure. Conftest's `pytest_sessionstart`
guard rail ensures we cannot accidentally hit the production DB.

Test list (PROPOSAL §3):
  10. test_extraction_creates_pending_row    — basic happy path → pending_systems
  11. test_extraction_no_trade_data_nullified — no_trade_data=True → fields=None  (P1)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.verify, pytest.mark.extractor]


def _load_fixture(fixtures_dir: Path, name: str) -> dict:
    return json.loads((fixtures_dir / name).read_text(encoding="utf-8"))


def test_extraction_creates_pending_row(haven_client, haven_module, fixtures_dir):
    """POST canonical extractor payload → 201 + row in pending_systems."""
    payload = _load_fixture(fixtures_dir, "extractor_payload_basic.json")

    resp = haven_client.post("/api/extraction", json=payload)
    assert resp.status_code == 201, (
        f"got {resp.status_code}: {resp.text[:300]}"
    )
    body = resp.json()
    assert body.get("status") == "ok"
    assert body.get("submission_id") is not None
    assert body.get("planet_count") == 1
    assert body.get("moon_count") == 0

    # Verify the row landed in pending_systems with correct values.
    conn = haven_module.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, glyph_code, status, source, system_name, galaxy, reality, "
            "discord_tag, personal_discord_username, game_mode "
            "FROM pending_systems WHERE id = ?",
            (body["submission_id"],),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    assert row is not None, f"submission {body['submission_id']} not in pending_systems"
    rd = dict(row)
    assert rd["glyph_code"] == payload["glyph_code"]
    assert rd["status"] == "pending"
    assert rd["system_name"] == payload["system_name"]
    assert rd["galaxy"] == payload["galaxy_name"]
    assert rd["reality"] == payload["reality"]
    assert rd["personal_discord_username"] == payload["discord_username"]
    assert rd["game_mode"] == payload["game_mode"]
    # No X-API-Key header sent → resolved source is 'manual' (per resolve_source()
    # in routes/approvals.py — anonymous calls bucket as manual, only authenticated
    # calls bucket as haven_extractor or keeper_bot).
    assert rd["source"] == "manual", (
        f"expected source='manual' for unauthenticated call, got {rd['source']!r}"
    )


@pytest.mark.p1
def test_extraction_no_trade_data_nullified(haven_client, haven_module, fixtures_dir):
    """no_trade_data=True payload → economy/conflict/lifeform stored as NULL.

    Guards the v1.48.2 fix: when NMS reports '-Data Unavailable-' for economy
    and lifeform (race_raw > 6), the extractor sends `no_trade_data: true` and
    omits those fields. The backend must store NULL, not the literal "Unknown".
    """
    payload = _load_fixture(fixtures_dir, "extractor_payload_no_trade.json")
    assert payload.get("no_trade_data") is True, "fixture isn't no_trade"
    # Sanity: the omitted fields aren't in the fixture
    assert "economy_type" not in payload
    assert "conflict_level" not in payload
    assert "dominant_lifeform" not in payload

    resp = haven_client.post("/api/extraction", json=payload)
    assert resp.status_code == 201, (
        f"got {resp.status_code}: {resp.text[:300]}"
    )
    submission_id = resp.json()["submission_id"]

    # Inspect the JSON blob the backend stored. submission_data carries the
    # canonical pre-approval shape; on approval those NULL values become the
    # NULL economy_type column on `systems`. We assert the pre-approval shape
    # since approval requires admin auth (out of scope for v1).
    conn = haven_module.get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT system_data FROM pending_systems WHERE id = ?",
            (submission_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    assert row is not None
    submission_data = json.loads(row["system_data"])
    assert submission_data.get("no_trade_data") is True

    # The four trade-related fields must be null (not the string "Unknown").
    for field in ("economy_type", "economy_level", "conflict_level", "dominant_lifeform"):
        assert submission_data.get(field) is None, (
            f"{field!r} should be None for no_trade_data row, "
            f"got {submission_data.get(field)!r}"
        )
