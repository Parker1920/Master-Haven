# Smoke Test Report — Travelers Exchange V3

**Date:** 2026-04-26
**Branch:** `audit-v2-remediation`
**Test file:** `Haven-Exchange/tests/smoke_test_e2e.py`
**Final result:** **52 / 52 PASSED — 0 failed, 0 skipped**

---

## Run Command

```
py -m pytest Haven-Exchange/tests/smoke_test_e2e.py -v --tb=short
```

---

## Results by Category

| # | Scenario | Class | Result |
|---|----------|-------|--------|
| 01 | Health endpoint returns 200 + status ok | TestHealth | PASS |
| 02 | New user registration succeeds | TestAuth | PASS |
| 03 | Duplicate registration rejected | TestAuth | PASS |
| 04 | Login with correct credentials sets session cookie | TestAuth | PASS |
| 05 | Login with wrong password rejected | TestAuth | PASS |
| 06 | Logout invalidates the session | TestAuth | PASS |
| 07 | Unauthenticated access to protected endpoint redirects (303) | TestAuth | PASS |
| 08 | Authenticated user can view own wallet | TestWallet | PASS |
| 09 | Public wallet lookup returns basic info | TestWallet | PASS |
| 10 | Wallet search returns matching users | TestWallet | PASS |
| 11 | User can apply to create a nation | TestNations | PASS |
| 12 | Nations list is publicly accessible | TestNations | PASS |
| 13 | World Mint can approve a pending nation | TestNations | PASS |
| 14 | User can join an approved nation | TestNations | PASS |
| 15 | Shop creation without auth is blocked | TestShops | PASS |
| 16 | New shop starts as pending (Phase 2D) | TestShops | PASS |
| 17 | Pending shops don't appear in public listing (Phase 2D) | TestShops | PASS |
| 18 | GET /api/shops/pending requires auth | TestShops | PASS |
| 19 | resource_depot shop without mining_setup returns 400 (Phase 2F) | TestShops | PASS |
| 20 | resource_depot with mining_setup creates successfully (Phase 2F) | TestShops | PASS |
| 21 | Stock listing is publicly accessible | TestStockMarket | PASS |
| 22 | World Mint cannot buy stocks (Phase 2K) | TestStockMarket | PASS |
| 23 | Buying stock without auth is blocked | TestStockMarket | PASS |
| 24 | Portfolio endpoint requires authentication | TestStockMarket | PASS |
| 25 | Stock close requires auth | TestStockMarket | PASS |
| 26 | Regular citizen cannot create a bank | TestBanks | PASS |
| 27 | World Mint cannot create banks (Phase 2K) | TestBanks | PASS |
| 28 | Bank listing for a nation is public | TestBanks | PASS |
| 29 | My loans endpoint requires auth | TestBanks | PASS |
| 30 | Loan payment without auth is blocked | TestBanks | PASS |
| 31 | Treasury loan list endpoint exists (Phase 2C) | TestBanks | PASS |
| 32 | Creating treasury loan requires auth | TestBanks | PASS |
| 33 | Mint stats require world_mint role | TestWorldMint | PASS |
| 34 | Mint execute requires world_mint role | TestWorldMint | PASS |
| 35 | Mint cap blocks minting above nation cap (Phase 2K) | TestWorldMint | PASS |
| 36 | Admin can access mint stats | TestWorldMint | PASS |
| 37 | Demurrage settings readable by auth users (Phase 2I) | TestEconomicHealth | PASS |
| 38 | Non-NL cannot modify demurrage settings (Phase 2I) | TestEconomicHealth | PASS |
| 39 | World Mint can set demurrage rate (Phase 2I) | TestEconomicHealth | PASS |
| 40 | Demurrage rate >1000 bps is rejected (Phase 2I) | TestEconomicHealth | PASS |
| 41 | Stimulus proposals listing requires auth (Phase 2J) | TestStimulus | PASS |
| 42 | Stimulus approval requires world_mint (Phase 2J) | TestStimulus | PASS |
| 43 | Stimulus rejection requires world_mint (Phase 2J) | TestStimulus | PASS |
| 44 | Approving non-existent proposal returns 404 (Phase 2J) | TestStimulus | PASS |
| 45 | Public ledger is accessible without auth | TestLedger | PASS |
| 46 | Transaction lookup by hash returns proper structure | TestLedger | PASS |
| 47 | Genesis transaction is present in ledger | TestLedger | PASS |
| 48 | Forgiving a non-existent loan returns 403 or 404 | TestLoanForgiveness | PASS |
| 49 | Loan forgiveness without auth is blocked | TestLoanForgiveness | PASS |
| 50 | Transfer to own wallet returns success=False | TestTransfers | PASS |
| 51 | Transfer exceeding balance returns success=False | TestTransfers | PASS |
| 52 | Wallet response includes Phase 2H health metric fields | TestWalletHealthMetrics | PASS |

---

## Infrastructure Notes

### DB Isolation

All tests use an in-memory SQLite database via SQLAlchemy `StaticPool`.  The
`_TestSessionLocal` is patched into `app.database` before `app.main` is
imported, so every request served by the TestClient uses the same empty
in-memory DB.  The real `data/economy.db` file is never touched.

### Cookie Handling

The app sets `session_token` with `Secure=True`.  Starlette's `TestClient`
uses `http://testserver` (no TLS), so the standard `cookies=` kwarg on
per-request calls silently drops Secure cookies — the httpx CookieJar
obeys the Secure flag.

Fix: write tokens directly into the client's internal jar via
`client.cookies.set("session_token", token)`, which bypasses the Secure-flag
check.  The `_as(client, token)` context manager handles swap/restore.  A
secondary issue — httpx raises `CookieConflict` when multiple cookies share
the same name under different domains — was resolved by iterating
`client.cookies.jar` directly and calling `jar.clear(domain, path, name)`
before setting a new token.

### Auth Redirect Behavior

`require_login` raises `HTTPException(status_code=303)` (redirect to
`/login`) rather than 401.  All tests that probe unauthenticated access
accept `status_code in (303, 401, 403)` to accommodate this design.

### Bank Creation (test_26)

`create_bank` allows `role == 'citizen'` past the role-filter check (the
filter targets unknown roles, not citizens) but then returns HTTP 400 "You do
not lead an approved nation" when the citizen doesn't own a nation.  The test
accepts `status_code in (400, 403)` since both codes correctly block a
non-leader citizen from creating a bank.

---

## Phase Coverage

| Phase | Features Tested |
|-------|----------------|
| 2C | Treasury loan endpoints (31, 32) |
| 2D | Shop pending status (16, 17) |
| 2F | Resource depot + mining_setup (19, 20) |
| 2H | Wallet health metric fields (8, 52) |
| 2I | Demurrage GET/PUT endpoints + rate validation (37–40) |
| 2J | Stimulus proposal listing + approve/reject + 404 (41–44) |
| 2K | WM stock buy guard (22), WM bank creation guard (27), Mint cap enforcement (35) |
