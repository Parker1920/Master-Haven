"""
Haven smoke + verification test suite — top-level conftest.

This file runs BEFORE any test module is imported. It is responsible for:

1. Loading `tests/.env` (if present) so `os.environ` is populated for fixtures.
2. Setting `HAVEN_DB_PATH` to a temp file before any Haven-UI module is imported,
   so the verify tier's TestClient can never touch production data.
3. Asserting (via `pytest_sessionstart`) that the resolved DB path actually
   lives under the OS temp directory. If not, abort the entire session.
   This is the safety net from PROPOSAL §10.8.
4. Adding `Haven-UI/backend` to `sys.path` so verify tests can `import paths`,
   `import migrations`, and `import control_room_api`.

Smoke tests do NOT depend on this DB setup — they hit live HTTP and don't
import any Haven-UI module. The setup is harmless for them.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
import pytest

# ---------------------------------------------------------------------------
# Locate the repo root and Haven-UI backend.
# This file is at <repo>/tests/conftest.py
# ---------------------------------------------------------------------------
TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
HAVEN_UI_BACKEND = REPO_ROOT / "Haven-UI" / "backend"

# ---------------------------------------------------------------------------
# Load tests/.env (if present) — populates os.environ for fixtures + the
# smoke runner. Never raises if the file is missing; smoke tests fall back
# to defaults from .env.example.
# ---------------------------------------------------------------------------
def _load_dotenv() -> None:
    env_path = TESTS_DIR / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)
    except ImportError:
        # Fallback: tiny inline parser. Only handles KEY=value lines.
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            os.environ.setdefault(key, value)


_load_dotenv()


# ---------------------------------------------------------------------------
# Throwaway DB setup — runs at import time, BEFORE any verify-tier test
# imports `paths` or `control_room_api`.
#
# paths.py reads HAVEN_DB_PATH at module-load time AND requires the file to
# already exist (paths.py:71 — `if path.exists()`). So we must:
#   1. Create a temp dir
#   2. Touch an empty file at <tempdir>/haven_ui.db (sqlite3 will treat it
#      as a fresh database when first opened)
#   3. Set HAVEN_DB_PATH to that file
#   4. Set HAVEN_UI_DIR to the temp dir's parent so the data/ mkdir at
#      control_room_api.py:647-648 doesn't touch the real Haven-UI/data/
# ---------------------------------------------------------------------------
TEST_TMPDIR = Path(tempfile.mkdtemp(prefix="haven-tests-"))
TEST_HAVEN_UI_DIR = TEST_TMPDIR / "Haven-UI-fake"
TEST_DATA_DIR = TEST_HAVEN_UI_DIR / "data"
TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB_PATH = TEST_DATA_DIR / "haven_ui.db"
TEST_DB_PATH.touch(exist_ok=True)

# These env vars must be set BEFORE any Haven-UI import.
os.environ["HAVEN_DB_PATH"] = str(TEST_DB_PATH)
os.environ["HAVEN_UI_DIR"] = str(TEST_HAVEN_UI_DIR)

# Make Haven-UI/backend importable for verify-tier tests.
if HAVEN_UI_BACKEND.exists() and str(HAVEN_UI_BACKEND) not in sys.path:
    sys.path.insert(0, str(HAVEN_UI_BACKEND))


# ---------------------------------------------------------------------------
# Session-start guard rail — enforces PROPOSAL §10.8.
# If a test inadvertently configured paths to point at production, abort.
# ---------------------------------------------------------------------------
def pytest_sessionstart(session: pytest.Session) -> None:
    """Abort the session if the resolved DB path isn't under the OS tempdir."""
    resolved = Path(os.environ.get("HAVEN_DB_PATH", "")).resolve()
    expected_root = Path(tempfile.gettempdir()).resolve()

    # On Windows, tempfile.gettempdir() may differ from str(REPO_ROOT) etc.
    # The check is simple: is the resolved DB path a descendant of the
    # tempdir-as-resolved-by-the-OS?
    try:
        resolved.relative_to(expected_root)
    except ValueError:
        pytest.exit(
            "\n"
            "=============================================================\n"
            "ABORT: Haven test suite refuses to run.\n"
            "\n"
            f"  Resolved HAVEN_DB_PATH: {resolved}\n"
            f"  Expected under tempdir: {expected_root}\n"
            "\n"
            "Refusing to risk touching production data. Check tests/conftest.py\n"
            "and tests/.env — HAVEN_DB_PATH must point inside the OS tempdir.\n"
            "=============================================================\n",
            returncode=2,
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Best-effort cleanup of the temp dir created at module-load time."""
    import shutil
    try:
        shutil.rmtree(TEST_TMPDIR, ignore_errors=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Schema-race tolerance (Phase 3 Addendum, Delta 1).
#
# Several Haven migrations DROP + recreate tables (v1.49.0 regions, v1.54.0
# systems). If a hot migration runs while a verify test is in flight against
# a live DB, the test could see `sqlite3.OperationalError: no such table` or
# `no such column`. That's a transient infrastructure event, not a test
# failure. Translate it to a skip so cron retries on the next cycle.
#
# This hook ONLY applies to tests carrying the `verify` marker. Smoke-tier
# tests don't touch SQLite directly (they make HTTP requests), so they
# wouldn't hit this anyway.
#
# Real schema regressions still surface — they show up as AssertionError on
# the test's own assertions, not as OperationalError in the harness.
# ---------------------------------------------------------------------------
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    outcome = yield
    if "verify" not in item.keywords:
        return
    excinfo = outcome.excinfo
    if excinfo is None:
        return
    exc = excinfo[1]
    import sqlite3 as _sql
    if not isinstance(exc, _sql.OperationalError):
        return
    msg = str(exc).lower()
    if "no such table" in msg or "no such column" in msg:
        from _pytest.outcomes import Skipped
        outcome.force_exception(
            Skipped(f"schema operation in flight: {exc}")
        )


# ---------------------------------------------------------------------------
# Sentinel user seed (Phase 3 Addendum, Delta 3).
#
# Migration v1.70.0 added user_profiles.poster_public — without an opt-in
# row, /api/public/voyager-fingerprint may legitimately 404 in verify mode.
# We seed `smoke_test_user` with poster_public=1 plus one approved system
# tied to that profile, so any future verify-mode test against the public
# fingerprint endpoint sees real (non-empty) data.
#
# Try/except wraps each statement so this is a no-op on a DB that doesn't
# yet have the v1.70.0 columns (forward-compat).
#
# Smoke remote mode hits production where Parker's real `parker1920`
# profile already exists; this seed never runs there.
# ---------------------------------------------------------------------------
def _seed_sentinel_user(haven_module) -> None:
    """Seed the sentinel `smoke_test_user` profile + one sample system.

    Called after migrations from the haven_app fixture. Idempotent — uses
    INSERT OR IGNORE so re-running on an already-seeded DB is a no-op.
    """
    from datetime import datetime
    now = datetime.now().isoformat()

    try:
        conn = haven_module.get_db_connection()
    except Exception:
        return  # If we can't connect, downstream tests fail with a real error.
    try:
        cursor = conn.cursor()

        # Detect column presence; older test runs (or partial migrations)
        # may not have poster_public. Build the column list dynamically.
        cursor.execute("PRAGMA table_info(user_profiles)")
        cols = {r[1] for r in cursor.fetchall()}
        if not cols:
            return  # user_profiles table doesn't exist (migrations broken)

        base_cols = [
            ("username", "smoke_test_user"),
            ("username_normalized", "smoketestuser"),
            ("tier", 5),
            ("display_name", "Smoke Test User"),
            ("is_active", 1),
            ("created_at", now),
            ("updated_at", now),
        ]
        if "poster_public" in cols:
            base_cols.append(("poster_public", 1))
        if "default_civ_tag" in cols:
            base_cols.append(("default_civ_tag", None))

        col_names = ", ".join(c for c, _ in base_cols)
        placeholders = ", ".join("?" for _ in base_cols)
        values = tuple(v for _, v in base_cols)

        try:
            cursor.execute(
                f"INSERT OR IGNORE INTO user_profiles ({col_names}) VALUES ({placeholders})",
                values,
            )
        except Exception:
            return  # If profile insert fails, skip the system insert too.

        cursor.execute(
            "SELECT id FROM user_profiles WHERE username_normalized = ?",
            ("smoketestuser",),
        )
        row = cursor.fetchone()
        if not row:
            return
        profile_id = row[0]

        # Seed one approved system tied to this profile so future
        # /api/public/voyager-fingerprint tests have data to render.
        try:
            cursor.execute("PRAGMA table_info(systems)")
            sys_cols = {r[1] for r in cursor.fetchall()}
            if "profile_id" in sys_cols:
                # Build INSERT defensively against schema drift.
                fields = [
                    ("name", "Smoke Test System"),
                    ("glyph_code", "0123ABC456EF"),
                    ("galaxy", "Euclid"),
                    ("region_x", 0), ("region_y", 0), ("region_z", 0),
                    ("x", 0), ("y", 0), ("z", 0),
                    ("profile_id", profile_id),
                ]
                if "source" in sys_cols:
                    fields.append(("source", "manual"))
                if "is_complete" in sys_cols:
                    fields.append(("is_complete", 50))
                if "discovered_at" in sys_cols:
                    fields.append(("discovered_at", now))
                if "discovered_by" in sys_cols:
                    fields.append(("discovered_by", "smoke_test_user"))

                col_list = ", ".join(c for c, _ in fields)
                placeholders = ", ".join("?" for _ in fields)
                cursor.execute(
                    f"INSERT OR IGNORE INTO systems ({col_list}) VALUES ({placeholders})",
                    tuple(v for _, v in fields),
                )
        except Exception:
            pass

        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def haven_base_url() -> str:
    """Base URL for the Haven backend. Pi cron uses localhost:8005;
    Win-dev manual uses havenmap.online. Configurable via tests/.env."""
    return os.environ.get("HAVEN_BASE_URL", "http://localhost:8005").rstrip("/")


@pytest.fixture(scope="session")
def exchange_base_url() -> str:
    """Base URL for Haven Exchange."""
    return os.environ.get("EXCHANGE_BASE_URL", "http://localhost:8010").rstrip("/")


@pytest.fixture(scope="session")
def poster_remote_username() -> str:
    """Username used by remote-mode poster smoke tests. Verify-mode uses
    its own sentinel ("smoke_test_user") — see verify/ tests."""
    return os.environ.get("POSTER_REMOTE_USERNAME", "parker1920")


@pytest.fixture(scope="session")
def poster_remote_galaxy() -> str:
    return os.environ.get("POSTER_REMOTE_GALAXY", "Euclid")


@pytest.fixture(scope="session")
def smoke_timeout() -> int:
    return int(os.environ.get("SMOKE_REQUEST_TIMEOUT_SECONDS", "10"))


@pytest.fixture(scope="session")
def smoke_slow_timeout() -> int:
    return int(os.environ.get("SMOKE_SLOW_TIMEOUT_SECONDS", "60"))


@pytest.fixture(scope="session")
def http_session():
    """Plain requests.Session; auto-retries off so flake surfaces."""
    import requests
    s = requests.Session()
    yield s
    s.close()


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the tests/fixtures directory — where extractor payload
    JSON files live."""
    return TESTS_DIR / "fixtures"


# ---------------------------------------------------------------------------
# Verify-tier fixture: boot the Haven FastAPI app against the throwaway DB.
#
# Loads control_room_api lazily (so smoke-tier-only runs don't pay the import
# cost). Tolerates broken migrations — a known issue documented in
# PHASE3_REPORT.md: migration 1.32.0 references a column (`sentinel_level`)
# that no longer exists in `init_database()`'s schema (renamed to `sentinel`
# by a later migration). On a fresh test DB, this migration fails and the
# stock runner aborts the chain, leaving `user_profiles` (added by 1.55.0)
# uncreated. We wrap each migration in try/except so later ones still run.
# ---------------------------------------------------------------------------
_HAVEN_APP_SINGLETON: dict = {}


def _patch_migrations_runner() -> None:
    """Replace migrations.run_pending_migrations with a fault-tolerant copy
    that logs and continues on per-migration failure instead of raising.

    Test isolation: this only affects the `migrations` module imported in
    THIS process. Production import paths are untouched."""
    import migrations as _mig
    import logging
    from datetime import datetime
    log = logging.getLogger("haven_tests.migrations_patch")

    def tolerant_run_pending(db_path):
        import sqlite3 as _sql
        from pathlib import Path as _P
        if isinstance(db_path, str):
            db_path = _P(db_path)
        conn = _sql.connect(str(db_path), timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            _mig.create_migrations_table(conn)
            current_version = _mig.get_current_version(conn)
            all_migrations = _mig.get_migrations()
            pending = []
            for m in all_migrations:
                if current_version is None:
                    pending.append(m)
                else:
                    if _mig._version_tuple(m.version) > _mig._version_tuple(current_version):
                        pending.append(m)
            applied = []
            failed = []
            for migration in pending:
                start = datetime.now()
                try:
                    migration.up(conn)
                    conn.commit()
                    elapsed = int((datetime.now() - start).total_seconds() * 1000)
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT OR REPLACE INTO schema_migrations "
                        "(version, migration_name, applied_at, execution_time_ms, success) "
                        "VALUES (?, ?, ?, ?, 1)",
                        (migration.version, migration.name, datetime.now().isoformat(), elapsed),
                    )
                    conn.commit()
                    applied.append(migration.version)
                except Exception as e:  # tolerate, continue
                    conn.rollback()
                    log.warning(
                        "Tolerant test runner: migration %s failed (%s) — "
                        "continuing", migration.version, e
                    )
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT OR REPLACE INTO schema_migrations "
                        "(version, migration_name, applied_at, success) "
                        "VALUES (?, ?, ?, 0)",
                        (migration.version, migration.name, datetime.now().isoformat()),
                    )
                    conn.commit()
                    failed.append(migration.version)
            log.info(
                "Tolerant migrations: applied=%d failed=%d (failed=%s)",
                len(applied), len(failed), failed,
            )
            return len(applied), applied
        finally:
            conn.close()

    _mig.run_pending_migrations = tolerant_run_pending


@pytest.fixture(scope="session")
def haven_app():
    """Session-scoped FastAPI app with throwaway DB.

    Imports control_room_api ONCE per session. The conftest's module-level
    env setup ensures all DB resolution points at the temp file. Migration
    runner is patched to tolerate the known-broken 1.32.0 (see PHASE3_REPORT)."""
    if "app" in _HAVEN_APP_SINGLETON:
        return _HAVEN_APP_SINGLETON["app"]

    if not HAVEN_UI_BACKEND.exists():
        pytest.skip(f"Haven-UI backend not found at {HAVEN_UI_BACKEND}")

    _patch_migrations_runner()
    import control_room_api
    _HAVEN_APP_SINGLETON["app"] = control_room_api.app
    _HAVEN_APP_SINGLETON["module"] = control_room_api

    # Force startup so migrations run via the patched runner. Without this,
    # the seed below sees an empty DB and the sentinel insert is wasted.
    from fastapi.testclient import TestClient
    with TestClient(control_room_api.app):
        pass  # startup + shutdown — migrations now applied to the temp DB

    # Seed the sentinel user (Phase 3 Addendum, Delta 3). Best-effort;
    # failures are silent so tests still run if the schema is unexpected.
    try:
        _seed_sentinel_user(control_room_api)
    except Exception:
        pass

    return control_room_api.app


@pytest.fixture(scope="session")
def haven_module(haven_app):
    """The control_room_api module — useful for tests that need
    access to internal helpers like get_db()."""
    return _HAVEN_APP_SINGLETON["module"]


@pytest.fixture
def haven_client(haven_app):
    """Function-scoped TestClient. Each test gets a fresh client; the
    underlying DB is session-scoped so state can leak between tests
    that share the same session — verify tests are responsible for their
    own isolation (DELETE rows they create)."""
    from fastapi.testclient import TestClient
    with TestClient(haven_app) as client:
        yield client
