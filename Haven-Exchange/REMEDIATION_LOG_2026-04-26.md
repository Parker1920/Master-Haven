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
Committed as `342a526` — `Phase 1: fix transfer auth, nation stock API path, loan forgive ledger entry`.

---

## Phase 2A — Loan Interest Accrual Engine

**Goal:** Add a daily accrual job that grows a per-loan `accrued_interest` field based on the loan's snapshot APR, capped at 100% of principal.

### Schema additions (`app/models.py` — `Loan`)
- `accrued_interest INTEGER DEFAULT 0 NOT NULL` — interest accumulated but not yet paid. Phase 2B will draw this down via the 20/80 split.
- `cap_amount INTEGER DEFAULT 0 NOT NULL` — lifetime ceiling on accrued interest. Set to `principal` at creation = 100% cap (V2 audit requirement).
- `interest_frozen BOOLEAN DEFAULT 0 NOT NULL` — flips to `True` once `accrued_interest` reaches `cap_amount`. Frozen loans are permanently skipped by the accrual job (cap is **lifetime**, so even if payments draw it down, no fresh accrual).
- `last_accrual_at DATETIME NULL` — most recent accrual timestamp; used by the elapsed-days computation for idempotent + backlog-tolerant runs.

### Migration (`app/main.py::_run_schema_migrations`)
- Four idempotent `ALTER TABLE loans ADD COLUMN` statements.
- Backfill: `UPDATE loans SET cap_amount = principal WHERE cap_amount = 0 AND principal > 0` so any pre-existing loan rows participate in the cap rule from day one.

### Accrual engine (`app/interest.py`, new file)
- `_accrue_loan(loan, now)`: per-loan helper.
  - Skips if `status != 'active'`, `interest_frozen`, `interest_rate <= 0`, or `cap_amount <= 0`.
  - Bootstraps `last_accrual_at` to `opened_at` on the very first run.
  - Treats naïve SQLite timestamps as UTC.
  - Daily interest = `floor(principal * interest_rate_bps / 10000 / 365)`.
  - Multiplies by elapsed days (≥ 1) — so missing a day's run auto-recovers on the next.
  - Caps the increment so cumulative `accrued_interest` never exceeds `cap_amount`; flips `interest_frozen` when the cap lands exactly.
  - Updates `last_accrual_at = now` even when sub-1-TC daily rate produces 0 added (prevents silent perpetual-zero loops on micro-loans).
- `accrue_daily_interest(db, *, now=None)`: top-level job.
  - Selects only `status='active' AND interest_frozen IS FALSE`.
  - Returns a summary dict (`loans_processed`, `loans_accrued`, `total_interest_added`, `loans_frozen`) — useful for future telemetry and the smoke test.

### Design choices
- **Simple, not compound.** Interest accrues against `principal`, not `principal + accrued_interest`. Compound interest combined with consumer-style loans creates runaway debt; the V2 audit's 100% lifetime cap is naturally enforced with simple interest.
- **Lifetime cap, not running-balance cap.** `cap_amount` is fixed at creation. Once `interest_frozen` flips, it stays frozen for the life of the loan even if borrower payments drive `accrued_interest` back down. This matches the audit dispatch's "100% cap" intent (a lifetime ceiling on what the bank can ever charge).
- **Daily idempotency.** Two job runs in the same calendar day produce 0 added on the second run because `(now - last_accrual_at).days == 0`. Backlog days from a missed run are absorbed in one go on the next run.

### Loan creation update (`app/routes/bank_routes.py::create_loan`)
- Sets `accrued_interest=0`, `cap_amount=principal`, `interest_frozen=False`, `last_accrual_at=now` when persisting the new `Loan`.
- Response now includes `accrued_interest`, `cap_amount`, `interest_frozen`.

### Listing endpoints (`list_bank_loans`, `my_loans`)
- Each loan dict gains `accrued_interest`, `total_owed` (= outstanding + accrued_interest), `cap_amount`, `interest_frozen`, `last_accrual_at`.
- `outstanding` retains its current meaning (principal balance only); Phase 2B will update payment splitting to draw down `accrued_interest` first.

### Scheduler (`app/main.py`)
- New `_scheduled_interest_accrual()` wrapper opens its own SessionLocal session.
- Registered alongside the existing GDP/stock recalc jobs at 24h interval, id `interest_accrual`.

### Verification
- Synthetic in-memory test (`py -c …`) covered five edge cases: same-day idempotency (0 added), 1-day accrual on 20% APR / 100k principal (54 TC), multi-year cap landing (frozen at 100,000 exact), frozen-loan skip (0 added on later runs), zero-interest-rate skip, closed-loan skip. All passed.
- AST syntax check on the four touched files: clean.

### Phase 2A commit
Pending — committed at end of phase with message: `Phase 2A: implement loan interest accrual with 100% cap`.

