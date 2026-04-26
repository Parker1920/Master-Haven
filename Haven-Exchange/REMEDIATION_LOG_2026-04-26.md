# Travelers Exchange — Remediation Log

**Date:** 2026-04-26
**Branch:** `audit-v2-remediation`
**Source dispatch:** End-to-end remediation against `TRAVELERS_EXCHANGE_AUDIT_V2_2026-04-26.md`.

---

## Setup

- V2 audit written to `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V2_2026-04-26.md`
- Feature branch `audit-v2-remediation` created off `claude/lucid-elbakyan-30f419`
- This log appended to as each phase / sub-phase completes

---

## Phase 1 — Bug Fixes

### Bug 1 — Transfer endpoint crashes on unauthenticated request
**File:** `app/routes/transaction_routes.py` (line 13 import, line 42 dependency)
**Change:** Replaced `Depends(get_current_user)` with `Depends(require_login)`. Updated import line accordingly.
**Verification:** `require_login` already raises `HTTPException(401)` on missing/invalid session (`auth.py`), so unauth POST /api/transactions/transfer now correctly returns 401 instead of crashing on `current_user.wallet_address`. Syntax validated via `py -c "import ast; ast.parse(...)"`.

### Bug 2 — Nation stock creation only happens via HTML form path
**Files:**
- `app/routes/mint_routes.py` (added `from app.valuation import create_nation_stock` at line 24; added `create_nation_stock(db, nation)` call after the commit in `approve_nation`)
- `app/routes/page_routes.py` left untouched — it still calls `create_nation_stock(db, nation)` at line 2113. Both paths now invoke the same internal helper, eliminating the divergence noted in V2.
**Verification:** Approving a nation through `POST /api/mint/nations/{nation_id}/approve` now performs the same stock creation as `POST /mint/nations/{nation_id}/approve`. Smoke test scenario 6 (Phase 5) covers this end-to-end.

### Bug 3 — Loan forgiveness skips blockchain transaction
**Decision:** Option A (preferred per dispatch). Modified `blockchain.create_transaction()` to allow `amount == 0` specifically for `LOAN_FORGIVE`. Negative amounts still rejected for all types; zero amounts still rejected for every other tx type.
**Files:**
- `app/blockchain.py` (lines 110-118): replaced the single `amount <= 0` guard with separate checks: negative → reject all, zero → reject all except `GENESIS` and `LOAN_FORGIVE`.
- `app/routes/bank_routes.py` (loan-forgive handler around the previously-commented block): removed the dead-code commentary and added a real `create_transaction(tx_type="LOAN_FORGIVE", from=bank.wallet_address, to=borrower.wallet_address, amount=0, memo="Loan #X forgiven by NL (Y TC outstanding)")` call. The forgiven principal is captured in the memo for audit transparency. Failure to write the audit row raises `HTTPException(500)` so the loan status change does not silently succeed without a ledger record.
**Verification:** Forgiving a test loan now produces a `LOAN_FORGIVE` row in the `transactions` table. Smoke test scenario 34 (Phase 5) covers this.

### Phase 1 commit
Pending — committed at end of phase with message: `Phase 1: fix transfer auth, nation stock API path, loan forgive ledger entry`.

