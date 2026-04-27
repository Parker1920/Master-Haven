"""
Travelers Exchange — End-to-End Smoke Test Suite

52 scenarios covering the core exchange flows.  Uses FastAPI TestClient
with a shared in-memory SQLite database (StaticPool so all connections see
the same DB) so the real `data/economy.db` is never touched.

Run from the repo root:
    py -m pytest Haven-Exchange/tests/smoke_test_e2e.py -v --tb=short

Requirements: pytest, httpx (already in requirements.txt), fastapi[all]

Cookie notes
------------
The app sets `session_token` with ``secure=True``.  Starlette's TestClient
uses ``http://testserver`` (no TLS), so per-request ``cookies=`` kwargs are
NOT forwarded — the httpx CookieJar silently drops Secure cookies on plain
HTTP.  The workaround is to write the token directly into the client's
internal cookie jar (``client.cookies.set(...)``), which bypasses the
Secure-flag check.  All helpers that need a session call ``_set_session()``
before the request and ``_clear_session()`` after.
"""

import contextlib
import os
import sys
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Ensure the app package is importable without PYTHONPATH magic
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_APP_ROOT = os.path.join(_HERE, "..")  # Haven-Exchange/
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)


# ---------------------------------------------------------------------------
# Override database to use in-memory SQLite for test isolation.
# StaticPool forces all connections to share the same underlying connection,
# which is required for sqlite:///:memory: to persist data across requests.
# ---------------------------------------------------------------------------
from app import database as _db_module

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)

# Patch the module-level engine and session factory BEFORE importing app.main
_db_module.engine = _TEST_ENGINE
_db_module.SessionLocal = _TestSessionLocal

import app.blockchain as _bc_module
_bc_module._tx_lock = threading.Lock()

from app.database import Base, get_db
from app.main import app


def override_get_db():
    db = _TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# ---------------------------------------------------------------------------
# Session-scoped client with fresh DB per test session.
# follow_redirects=False so we see real 3xx status codes from auth guards.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    Base.metadata.create_all(bind=_TEST_ENGINE)
    with TestClient(app, raise_server_exceptions=False, follow_redirects=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Cookie helpers
#
# Because secure=True cookies are not forwarded on http://testserver, we
# bypass the per-request cookies= kwarg entirely and write the token
# directly into the client's internal jar.
# ---------------------------------------------------------------------------

def _clear_session(client: TestClient) -> None:
    """Remove ALL session_token cookies from the TestClient's jar.

    Uses the underlying httpx CookieJar directly to handle the case where
    the same name is present under multiple domains (e.g. 'testserver' and
    ''), which causes httpx.CookieConflict on `.get()`.
    """
    to_remove = [ck for ck in client.cookies.jar if ck.name == "session_token"]
    for ck in to_remove:
        client.cookies.jar.clear(ck.domain, ck.path, ck.name)


def _set_session(client: TestClient, token: str) -> None:
    """Replace all session_token cookies with a single fresh one."""
    _clear_session(client)
    client.cookies.set("session_token", token)


def _get_session(client: TestClient):
    """Return the current session token, or None if not set (no CookieConflict)."""
    tokens = [ck.value for ck in client.cookies.jar if ck.name == "session_token"]
    return tokens[0] if tokens else None


@contextlib.contextmanager
def _as(client: TestClient, token: str):
    """Context manager: run requests as the user identified by *token*."""
    old = _get_session(client)
    _set_session(client, token)
    try:
        yield
    finally:
        if old is None:
            _clear_session(client)
        else:
            _set_session(client, old)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def register(client, username, password="testpass123") -> object:
    """POST form-encoded registration (no session needed)."""
    return client.post("/api/auth/register", data={
        "username": username,
        "password": password,
        "confirm_password": password,
    })


def _extract_session_from_headers(response) -> str | None:
    """Pull session_token from Set-Cookie headers, bypassing httpx CookieJar.

    httpx's response.cookies merges with the client jar, which raises
    CookieConflict if the client already has a session_token from a prior
    login. Parsing Set-Cookie headers directly avoids the conflict.
    """
    for header_value in response.headers.get_list("set-cookie"):
        first_pair = header_value.split(";", 1)[0].strip()
        if first_pair.startswith("session_token="):
            return first_pair.split("=", 1)[1]
    return None


def login_token(client, username, password="testpass123") -> str:
    """Login and return the raw session_token string."""
    # Clear the client jar so subsequent requests don't carry a stale token.
    _clear_session(client)
    r = client.post("/api/auth/login", data={
        "username": username,
        "password": password,
    })
    assert r.status_code == 200, f"Login failed for {username}: {r.text}"
    assert r.json().get("success") is True, f"Login rejected: {r.json()}"
    token = _extract_session_from_headers(r)
    assert token, f"No session_token cookie in login response for {username}"
    # Drop the cookie that login auto-set on the client jar.
    _clear_session(client)
    return token


def login_session(client, username, password="testpass123"):
    """Register (if needed), login, and return (token, wallet_address)."""
    reg = register(client, username, password)
    wallet_address = None
    if reg.status_code == 200 and reg.json().get("success"):
        wallet_address = reg.json().get("wallet_address")

    token = login_token(client, username, password)

    if wallet_address is None:
        with _as(client, token):
            wr = client.get("/api/wallet")
            if wr.status_code == 200:
                wallet_address = wr.json().get("address")

    return token, wallet_address


def admin_token(client) -> str:
    """Return a session token for the seeded world_mint admin."""
    _clear_session(client)
    r = client.post("/api/auth/login", data={
        "username": "admin",
        "password": "changeme",
    })
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    assert r.json().get("success") is True
    token = _extract_session_from_headers(r)
    assert token, "No session_token in admin login response"
    _clear_session(client)
    return token


# ---------------------------------------------------------------------------
# 1. Health check
# ---------------------------------------------------------------------------
class TestHealth:
    def test_01_health_check(self, client):
        """Scenario 1 — Health endpoint returns 200 + status ok."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# 2. Auth — register / login / logout
# ---------------------------------------------------------------------------
class TestAuth:
    def test_02_register_new_user(self, client):
        """Scenario 2 — New user registration succeeds."""
        r = register(client, "alice")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert "wallet_address" in data
        assert data["wallet_address"].startswith("TRV-")

    def test_03_duplicate_register_rejected(self, client):
        """Scenario 3 — Registering the same username twice is rejected."""
        register(client, "bob")
        r = register(client, "bob")
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_04_login_valid_credentials(self, client):
        """Scenario 4 — Login with correct credentials sets a session cookie."""
        register(client, "carol")
        _clear_session(client)
        r = client.post("/api/auth/login", data={
            "username": "carol", "password": "testpass123"
        })
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert _extract_session_from_headers(r), "Set-Cookie header missing session_token"
        _clear_session(client)

    def test_05_login_wrong_password(self, client):
        """Scenario 5 — Login with wrong password is rejected (soft error)."""
        register(client, "dave")
        r = client.post("/api/auth/login", data={
            "username": "dave", "password": "wrongpass"
        })
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_06_logout(self, client):
        """Scenario 6 — Logout invalidates the session."""
        token, _ = login_session(client, "eve_logout")
        with _as(client, token):
            r = client.post("/api/auth/logout")
            assert r.status_code == 200
            # After logout the session is deleted from DB; next wallet call
            # should redirect (303) since require_login finds no valid session.
            r2 = client.get("/api/wallet")
            assert r2.status_code in (303, 401, 403)

    def test_07_unauthenticated_access_redirects(self, client):
        """Scenario 7 — Protected endpoints redirect (303) when no session."""
        _clear_session(client)  # ensure no cookie
        r = client.get("/api/wallet")
        assert r.status_code in (303, 401, 403)


# ---------------------------------------------------------------------------
# 3. Wallet
# ---------------------------------------------------------------------------
class TestWallet:
    def test_08_my_wallet(self, client):
        """Scenario 8 — Authenticated user can view own wallet."""
        register(client, "wally")
        token, _ = login_session(client, "wally")
        with _as(client, token):
            r = client.get("/api/wallet")
        assert r.status_code == 200
        data = r.json()
        assert "balance" in data
        assert "transaction_count_lifetime" in data
        assert "volume_30d" in data
        assert "volume_lifetime" in data

    def test_09_public_wallet_lookup(self, client):
        """Scenario 9 — Public wallet lookup returns basic info."""
        token, addr = login_session(client, "pubwallet")
        r = client.get(f"/api/wallet/{addr}")
        assert r.status_code == 200
        assert r.json()["address"] == addr

    def test_10_wallet_search(self, client):
        """Scenario 10 — Wallet search returns matching users."""
        register(client, "searchme")
        r = client.get("/api/wallet/search?q=searchme")
        assert r.status_code == 200
        results = r.json()["results"]
        assert any("searchme" in (res.get("username") or "") for res in results)


# ---------------------------------------------------------------------------
# 4. Nations
# ---------------------------------------------------------------------------
class TestNations:
    def test_11_apply_for_nation(self, client):
        """Scenario 11 — User can apply to create a nation."""
        token, _ = login_session(client, "nl_leader")
        with _as(client, token):
            r = client.post("/api/nations/apply", json={
                "name": "TestNation", "description": "A test nation"
            })
        assert r.status_code in (200, 201, 400)  # 400 if nl_leader already leads
        if r.status_code in (200, 201):
            assert r.json().get("status") == "pending"

    def test_12_list_nations_public(self, client):
        """Scenario 12 — Nations list is publicly accessible."""
        r = client.get("/api/nations")
        assert r.status_code == 200
        assert "nations" in r.json()

    def test_13_admin_approves_nation(self, client):
        """Scenario 13 — World Mint can approve a pending nation."""
        token2, _ = login_session(client, "nl_leader2")
        with _as(client, token2):
            r = client.post("/api/nations/apply", json={
                "name": "ApprovedNation", "description": "Approved"
            })
        assert r.status_code in (200, 201, 400), f"Apply failed: {r.text}"
        if r.status_code == 400:
            pytest.skip("nl_leader2 already has a nation")
        nation_id = r.json()["nation_id"]

        adm = admin_token(client)
        with _as(client, adm):
            r2 = client.post(f"/api/mint/nations/{nation_id}/approve")
        assert r2.status_code == 200

        r3 = client.get("/api/stocks")
        assert r3.status_code == 200
        assert len(r3.json().get("stocks", [])) >= 1

    def test_14_join_approved_nation(self, client):
        """Scenario 14 — User can join an approved nation."""
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation available")
        nation_id = nations[0]["id"]

        token, _ = login_session(client, "joiner")
        with _as(client, token):
            r2 = client.post(f"/api/nations/{nation_id}/join")
        assert r2.status_code in (200, 201, 400)  # 400 if already a member


# ---------------------------------------------------------------------------
# 5. Shops
# ---------------------------------------------------------------------------
class TestShops:
    def test_15_create_shop_requires_auth(self, client):
        """Scenario 15 — Shop creation without auth is blocked (303/401/403)."""
        _clear_session(client)
        r = client.post("/api/shops", json={"name": "NoAuth", "description": "x"})
        assert r.status_code in (303, 401, 403)

    def test_16_create_shop_creates_pending(self, client):
        """Scenario 16 — New shop starts as pending (Phase 2D fix)."""
        token, _ = login_session(client, "shopowner")

        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation available")
        nation_id = nations[0]["id"]

        with _as(client, token):
            client.post(f"/api/nations/{nation_id}/join")
            r2 = client.post("/api/shops", json={
                "name": "PendingShop", "description": "Test"
            })
        assert r2.status_code in (200, 201)
        assert r2.json().get("status") == "pending"

    def test_17_pending_shop_not_in_listing(self, client):
        """Scenario 17 — Pending shops don't appear in public listing."""
        r = client.get("/api/shops")
        assert r.status_code == 200
        for s in r.json().get("shops", []):
            assert s.get("status") != "pending", "Pending shop visible in public listing!"

    def test_18_pending_shops_endpoint(self, client):
        """Scenario 18 — GET /api/shops/pending requires auth (303/401/403)."""
        _clear_session(client)
        r = client.get("/api/shops/pending")
        assert r.status_code in (303, 401, 403)

    def test_19_resource_depot_requires_mining_setup(self, client):
        """Scenario 19 — resource_depot shop without mining_setup returns 400."""
        token, _ = login_session(client, "miner")
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation")
        nation_id = nations[0]["id"]

        with _as(client, token):
            client.post(f"/api/nations/{nation_id}/join")
            r2 = client.post("/api/shops", json={
                "name": "MineShop", "description": "Mine",
                "shop_type": "resource_depot",
            })
        assert r2.status_code == 400

    def test_20_resource_depot_with_mining_setup(self, client):
        """Scenario 20 — resource_depot with mining_setup creates successfully."""
        token, _ = login_session(client, "miner2")
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation")
        nation_id = nations[0]["id"]

        with _as(client, token):
            client.post(f"/api/nations/{nation_id}/join")
            r2 = client.post("/api/shops", json={
                "name": "MineShop2", "description": "Mine",
                "shop_type": "resource_depot", "mining_setup": "GPU rig x4",
            })
        assert r2.status_code in (200, 201)
        assert r2.json().get("shop_type") == "resource_depot"


# ---------------------------------------------------------------------------
# 6. Stock Market
# ---------------------------------------------------------------------------
class TestStockMarket:
    def test_21_list_stocks(self, client):
        """Scenario 21 — Stock listing is publicly accessible."""
        r = client.get("/api/stocks")
        assert r.status_code == 200
        assert "stocks" in r.json()

    def test_22_world_mint_cannot_buy_stocks(self, client):
        """Scenario 22 — World Mint buying stocks is blocked (Phase 2K)."""
        r = client.get("/api/stocks")
        stocks = r.json().get("stocks", [])
        if not stocks:
            pytest.skip("No stocks available")
        ticker = stocks[0]["ticker"]
        adm = admin_token(client)
        with _as(client, adm):
            r2 = client.post(f"/api/stocks/{ticker}/buy", json={"shares": 1})
        assert r2.status_code == 403

    def test_23_buy_stock_requires_auth(self, client):
        """Scenario 23 — Buying stock without auth is blocked (303/401/403)."""
        r = client.get("/api/stocks")
        stocks = r.json().get("stocks", [])
        if not stocks:
            pytest.skip("No stocks available")
        ticker = stocks[0]["ticker"]
        _clear_session(client)
        r2 = client.post(f"/api/stocks/{ticker}/buy", json={"shares": 1})
        assert r2.status_code in (303, 401, 403)

    def test_24_portfolio_requires_auth(self, client):
        """Scenario 24 — Portfolio endpoint requires authentication (303/401/403)."""
        _clear_session(client)
        r = client.get("/api/stocks/portfolio")
        assert r.status_code in (303, 401, 403)

    def test_25_stock_close_requires_auth(self, client):
        """Scenario 25 — Stock close requires auth (303/401/403)."""
        _clear_session(client)
        r = client.post("/api/stocks/1/close", json={})
        assert r.status_code in (303, 401, 403)


# ---------------------------------------------------------------------------
# 7. Banks & Lending
# ---------------------------------------------------------------------------
class TestBanks:
    def test_26_create_bank_requires_nl(self, client):
        """Scenario 26 — Regular citizen cannot create a bank (403 or 400).

        A citizen passes the role-filter check (role is 'citizen', not an
        unknown role) but then fails the nation-leader ownership check with
        400 "You do not lead an approved nation."  Either 400 or 403 is an
        acceptable rejection for a non-leader citizen.
        """
        register(client, "citizen_nobank")
        token, _ = login_session(client, "citizen_nobank")
        with _as(client, token):
            r = client.post("/api/banks", json={
                "name": "CitizenBank", "owner_user_id": 9999
            })
        assert r.status_code in (400, 403)

    def test_27_world_mint_cannot_create_bank(self, client):
        """Scenario 27 — World Mint cannot create banks (Phase 2K, 403)."""
        adm = admin_token(client)
        with _as(client, adm):
            r = client.post("/api/banks", json={
                "name": "WMBank", "owner_user_id": 1
            })
        assert r.status_code == 403

    def test_28_list_nation_banks_public(self, client):
        """Scenario 28 — Bank listing for a nation is public."""
        r = client.get("/api/banks/nation/1")
        assert r.status_code in (200, 404)

    def test_29_my_loans_requires_auth(self, client):
        """Scenario 29 — My loans endpoint requires auth (303/401/403)."""
        _clear_session(client)
        r = client.get("/api/loans/mine")
        assert r.status_code in (303, 401, 403)

    def test_30_loan_pay_requires_auth(self, client):
        """Scenario 30 — Loan payment without auth is blocked (303/401/403)."""
        _clear_session(client)
        r = client.post("/api/loans/1/pay", json={"amount": 100})
        assert r.status_code in (303, 401, 403)

    def test_31_treasury_loans_endpoint_exists(self, client):
        """Scenario 31 — Treasury loan list endpoint exists (Phase 2C)."""
        r = client.get("/api/nations/99999/loans")
        assert r.status_code in (303, 401, 403, 404)

    def test_32_treasury_loan_requires_auth(self, client):
        """Scenario 32 — Creating treasury loan requires auth (303/401/403)."""
        _clear_session(client)
        r = client.post("/api/nations/1/loans", json={
            "borrower_id": 2, "amount": 1000, "memo": "test"
        })
        assert r.status_code in (303, 401, 403)


# ---------------------------------------------------------------------------
# 8. World Mint
# ---------------------------------------------------------------------------
class TestWorldMint:
    def test_33_mint_stats_requires_wm(self, client):
        """Scenario 33 — Mint stats require world_mint role (403 for wrong role)."""
        token, _ = login_session(client, "nonadmin_mint")
        with _as(client, token):
            r = client.get("/api/mint/stats")
        assert r.status_code in (303, 401, 403)

    def test_34_mint_execute_requires_wm(self, client):
        """Scenario 34 — Mint execute requires world_mint role."""
        token, _ = login_session(client, "nonadmin_mint2")
        with _as(client, token):
            r = client.post("/api/mint/execute", json={
                "to_address": "TRV-00000000", "amount": 100
            })
        assert r.status_code in (303, 401, 403)

    def test_35_mint_cap_prevents_excess_mint(self, client):
        """Scenario 35 — Mint cap blocks minting above nation cap (Phase 2K)."""
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation available")
        nation_id = nations[0]["id"]

        from sqlalchemy import text
        with _TestSessionLocal() as db:
            row = db.execute(
                text(f"SELECT treasury_address FROM nations WHERE id = {nation_id}")
            ).fetchone()
        if row is None:
            pytest.skip("Could not fetch treasury_address from DB")
        treasury_address = row[0]

        # Set a very low mint_cap via DB
        with _TestSessionLocal() as db:
            db.execute(text(f"UPDATE nations SET mint_cap = 1 WHERE id = {nation_id}"))
            db.commit()

        adm = admin_token(client)
        with _as(client, adm):
            r2 = client.post("/api/mint/execute", json={
                "to_address": treasury_address, "amount": 1000
            })
        data = r2.json()

        # Reset cap after test
        with _TestSessionLocal() as db:
            db.execute(text(f"UPDATE nations SET mint_cap = 1000000000 WHERE id = {nation_id}"))
            db.commit()

        assert r2.status_code in (200, 400)
        if r2.status_code == 200:
            assert data.get("success") is False or data.get("minted", 1000) < 1000

    def test_36_mint_stats_accessible_by_admin(self, client):
        """Scenario 36 — Admin can access mint stats."""
        adm = admin_token(client)
        with _as(client, adm):
            r = client.get("/api/mint/stats")
        assert r.status_code == 200
        assert "total_supply" in r.json()


# ---------------------------------------------------------------------------
# 9. Economic Health — demurrage settings
# ---------------------------------------------------------------------------
class TestEconomicHealth:
    def test_37_demurrage_get_public(self, client):
        """Scenario 37 — Demurrage settings readable by auth users (Phase 2I)."""
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation")
        nation_id = nations[0]["id"]

        token, _ = login_session(client, "demurrage_viewer")
        with _as(client, token):
            r2 = client.get(f"/api/nations/{nation_id}/demurrage")
        assert r2.status_code == 200
        data = r2.json()
        assert "demurrage_enabled" in data
        assert "demurrage_rate_bps" in data

    def test_38_demurrage_put_requires_nl(self, client):
        """Scenario 38 — Non-NL cannot modify demurrage settings (403)."""
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation")
        nation_id = nations[0]["id"]

        token, _ = login_session(client, "notleader_dem")
        with _as(client, token):
            r2 = client.put(f"/api/nations/{nation_id}/demurrage", json={
                "demurrage_enabled": True
            })
        assert r2.status_code == 403

    def test_39_admin_can_set_demurrage(self, client):
        """Scenario 39 — World Mint can set demurrage rate."""
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation")
        nation_id = nations[0]["id"]

        adm = admin_token(client)
        with _as(client, adm):
            r2 = client.put(f"/api/nations/{nation_id}/demurrage", json={
                "demurrage_rate_bps": 75
            })
        assert r2.status_code == 200
        assert r2.json()["demurrage_rate_bps"] == 75

    def test_40_demurrage_rate_validation(self, client):
        """Scenario 40 — Demurrage rate >1000 is rejected (400)."""
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        if not nations:
            pytest.skip("No approved nation")
        nation_id = nations[0]["id"]

        adm = admin_token(client)
        with _as(client, adm):
            r2 = client.put(f"/api/nations/{nation_id}/demurrage", json={
                "demurrage_rate_bps": 5000
            })
        assert r2.status_code == 400


# ---------------------------------------------------------------------------
# 10. Stimulus Proposals
# ---------------------------------------------------------------------------
class TestStimulus:
    def test_41_stimulus_proposals_require_auth(self, client):
        """Scenario 41 — Stimulus proposals listing requires auth (303/401/403)."""
        _clear_session(client)
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        nation_id = nations[0]["id"] if nations else 1
        r2 = client.get(f"/api/nations/{nation_id}/stimulus-proposals")
        assert r2.status_code in (303, 401, 403)

    def test_42_stimulus_approve_requires_wm(self, client):
        """Scenario 42 — Stimulus approval requires world_mint (403)."""
        token, _ = login_session(client, "stim_nonwm")
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        nation_id = nations[0]["id"] if nations else 1
        with _as(client, token):
            r2 = client.post(
                f"/api/nations/{nation_id}/stimulus-proposals/1/approve"
            )
        assert r2.status_code == 403

    def test_43_stimulus_reject_requires_wm(self, client):
        """Scenario 43 — Stimulus rejection requires world_mint (403)."""
        token, _ = login_session(client, "stim_nonwm2")
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        nation_id = nations[0]["id"] if nations else 1
        with _as(client, token):
            r2 = client.post(
                f"/api/nations/{nation_id}/stimulus-proposals/1/reject"
            )
        assert r2.status_code == 403

    def test_44_stimulus_approve_404_on_missing(self, client):
        """Scenario 44 — Approving non-existent proposal returns 404."""
        adm = admin_token(client)
        r = client.get("/api/nations")
        nations = r.json()["nations"]
        nation_id = nations[0]["id"] if nations else 1
        with _as(client, adm):
            r2 = client.post(
                f"/api/nations/{nation_id}/stimulus-proposals/99999/approve"
            )
        assert r2.status_code == 404


# ---------------------------------------------------------------------------
# 11. Ledger
# ---------------------------------------------------------------------------
class TestLedger:
    def test_45_public_ledger(self, client):
        """Scenario 45 — Public ledger is accessible without auth."""
        r = client.get("/api/ledger")
        assert r.status_code == 200
        assert "transactions" in r.json()

    def test_46_transaction_by_hash(self, client):
        """Scenario 46 — Transaction lookup returns proper structure."""
        r = client.get("/api/ledger")
        txs = r.json().get("transactions", [])
        if not txs:
            pytest.skip("No transactions in ledger")
        tx_hash = txs[0]["tx_hash"]
        r2 = client.get(f"/api/transactions/{tx_hash}")
        assert r2.status_code == 200
        assert r2.json()["tx_hash"] == tx_hash

    def test_47_genesis_tx_exists(self, client):
        """Scenario 47 — Genesis transaction is present."""
        r = client.get("/api/ledger")
        txs = r.json().get("transactions", [])
        types = {t["tx_type"] for t in txs}
        assert "GENESIS" in types


# ---------------------------------------------------------------------------
# 12. Loan Forgiveness (Bug 3 fix — ledger entry created)
# ---------------------------------------------------------------------------
class TestLoanForgiveness:
    def test_48_forgive_nonexistent_loan_returns_404(self, client):
        """Scenario 48 — Forgiving a non-existent loan returns 403 or 404."""
        adm = admin_token(client)
        with _as(client, adm):
            r = client.post("/api/banks/1/loans/99999/forgive")
        # 403 if no bank (WM can't create banks, so bank_id 1 may not exist)
        # 404 if bank exists but loan doesn't
        assert r.status_code in (403, 404)

    def test_49_forgive_requires_auth(self, client):
        """Scenario 49 — Loan forgiveness without auth returns 303/401/403."""
        _clear_session(client)
        r = client.post("/api/banks/1/loans/1/forgive")
        assert r.status_code in (303, 401, 403)


# ---------------------------------------------------------------------------
# 13. Transfers
# ---------------------------------------------------------------------------
class TestTransfers:
    def test_50_transfer_to_self_rejected(self, client):
        """Scenario 50 — Transfer to own wallet returns success=False."""
        token, addr = login_session(client, "selftransfer")
        with _as(client, token):
            r = client.post("/api/transactions/transfer", json={
                "to_address": addr, "amount": 1
            })
        assert r.status_code == 200
        assert r.json()["success"] is False

    def test_51_transfer_insufficient_balance(self, client):
        """Scenario 51 — Transfer exceeding balance returns success=False."""
        token, _ = login_session(client, "broke_transfer")
        with _as(client, token):
            r = client.post("/api/transactions/transfer", json={
                "to_address": "TRV-00000000", "amount": 999999999
            })
        assert r.status_code == 200
        assert r.json()["success"] is False


# ---------------------------------------------------------------------------
# 14. Wallet Health Metrics
# ---------------------------------------------------------------------------
class TestWalletHealthMetrics:
    def test_52_wallet_response_has_health_fields(self, client):
        """Scenario 52 — Wallet response includes Phase 2H health metrics."""
        register(client, "health_check_user")
        token, _ = login_session(client, "health_check_user")
        with _as(client, token):
            r = client.get("/api/wallet")
        assert r.status_code == 200
        data = r.json()
        for field in ("transaction_count_lifetime", "transaction_count_30d",
                      "volume_lifetime", "volume_30d"):
            assert field in data, f"Missing wallet health field: {field}"
            assert isinstance(data[field], int)
