"""
Safety-net unit tests:

  - Webhook URL redaction works as specified (PROPOSAL §10.7)
  - DB-path guard rail in conftest aborts on production paths (PROPOSAL §10.8)

These are pure unit tests; no live infra, no Haven backend, no Discord.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.verify


# ---------------------------------------------------------------------------
# Webhook redaction
# ---------------------------------------------------------------------------
@pytest.mark.redaction
class TestRedaction:
    def setup_method(self) -> None:
        from haven_smoke import redact as r
        self.redact = r.redact
        self.placeholder = r.REDACTION_PLACEHOLDER

    def test_redacts_canonical_discord_url(self):
        # Note: this string is fake — it's not a real webhook URL. Even if it
        # were, the test only ever stores it in-process; it never gets posted.
        sample = "Failed: https://discord.com/api/webhooks/1234567890/abcDEF_xyz-token here"
        out = self.redact(sample)
        assert "1234567890" not in out
        assert "abcDEF_xyz-token" not in out
        assert self.placeholder in out

    def test_redacts_legacy_discordapp_url(self):
        sample = "https://discordapp.com/api/webhooks/9/secrettokenval-1 stuff"
        out = self.redact(sample)
        assert "secrettokenval-1" not in out
        assert self.placeholder in out

    def test_idempotent(self):
        sample = "https://discord.com/api/webhooks/1/abcDEF"
        once = self.redact(sample)
        twice = self.redact(once)
        assert once == twice
        assert self.placeholder in once

    def test_handles_multiple_urls(self):
        sample = (
            "first https://discord.com/api/webhooks/1/aa "
            "second https://discord.com/api/webhooks/2/bb"
        )
        out = self.redact(sample)
        assert "aa" not in out
        assert "bb" not in out
        assert out.count(self.placeholder) == 2

    def test_unaffected_non_webhook_urls(self):
        sample = "see https://havenmap.online/api/status for liveness"
        out = self.redact(sample)
        assert out == sample, "non-webhook URLs must not be redacted"

    def test_empty_and_none(self):
        assert self.redact("") == ""
        assert self.redact(None) is None  # type: ignore[arg-type]

    def test_redacts_in_traceback(self):
        # Simulate a typical exception message with the URL embedded.
        tb = textwrap.dedent("""
            Traceback (most recent call last):
              File "alerter.py", line 42, in post_alert
                requests.post("https://discord.com/api/webhooks/9/oops", json={})
            ConnectionError: failed
        """)
        out = self.redact(tb)
        assert "oops" not in out
        assert self.placeholder in out

    def test_pattern_is_case_insensitive(self):
        sample = "https://DISCORD.COM/api/webhooks/1/UPPERCASE"
        out = self.redact(sample)
        assert "UPPERCASE" not in out
        assert self.placeholder in out


# ---------------------------------------------------------------------------
# DB-path guard rail — directly invoke conftest.pytest_sessionstart after
# pointing HAVEN_DB_PATH at a path OUTSIDE the OS tempdir, and assert
# pytest.exit raises with returncode=2.
# ---------------------------------------------------------------------------
@pytest.mark.guardrail
def test_guardrail_aborts_on_production_path(monkeypatch):
    """Directly invoke conftest.pytest_sessionstart with a poisoned env var
    and confirm it raises pytest.Exit with the right message + returncode."""
    # Repo root is two levels above this file: tests/verify/test_safety_unit.py
    repo_root = Path(__file__).resolve().parent.parent.parent
    # A path that is GUARANTEED not under the OS tempdir.
    fake_prod_db = repo_root / "Haven-UI" / "data" / "haven_ui.db"
    # The file doesn't need to exist — the guard rail checks the path string.
    monkeypatch.setenv("HAVEN_DB_PATH", str(fake_prod_db))

    # Import conftest fresh so we get pytest_sessionstart. It's at tests/conftest.py.
    tests_dir = repo_root / "tests"
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
    import conftest as parent_conftest

    # pytest.exit raises pytest.Exit (BaseException subclass)
    with pytest.raises(pytest.exit.Exception) as excinfo:
        parent_conftest.pytest_sessionstart(session=None)  # session unused

    msg = str(excinfo.value)
    assert "ABORT" in msg, f"expected ABORT in exit message, got: {msg!r}"
    assert "refuses to run" in msg, f"expected 'refuses to run', got: {msg!r}"
    # returncode should be 2 per conftest.pytest_sessionstart's pytest.exit call
    assert getattr(excinfo.value, "returncode", None) == 2, (
        f"expected returncode=2, got {getattr(excinfo.value, 'returncode', None)}"
    )


@pytest.mark.guardrail
def test_guardrail_passes_for_tempdir_path(monkeypatch):
    """Sanity check: a path UNDER the OS tempdir does NOT trigger the abort."""
    import tempfile as _tf
    repo_root = Path(__file__).resolve().parent.parent.parent
    safe_db = Path(_tf.gettempdir()) / "haven-tests-safe-probe" / "haven_ui.db"
    safe_db.parent.mkdir(parents=True, exist_ok=True)
    safe_db.touch(exist_ok=True)
    monkeypatch.setenv("HAVEN_DB_PATH", str(safe_db))

    tests_dir = repo_root / "tests"
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))
    import conftest as parent_conftest

    # Should NOT raise.
    parent_conftest.pytest_sessionstart(session=None)
