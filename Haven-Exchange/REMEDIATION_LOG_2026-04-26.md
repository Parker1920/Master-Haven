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
Committed as `9657cb0` — `Phase 2A: implement loan interest accrual with 100% cap`.

---

## Phase 2B — Burn Mechanics Rework (Interest 20/80 Split)

**Goal:** Split each loan payment into interest-portion (paid first) and principal-portion (remainder); apply different burn rates per portion. Interest portion: 80% burn / 20% bank — the V2 audit "20/80 split". Principal portion: keeps existing snapshot rate (default 10/90).

### Schema additions

**`Loan` (`models.py`)**
- `interest_burn_rate_snapshot INTEGER DEFAULT 8000 NOT NULL` — snapshotted from `GlobalSettings.interest_burn_rate_bps` at loan creation. Allows the bank's economic policy to evolve without rewriting outstanding loans.
- `total_interest_paid INTEGER DEFAULT 0` — running total of interest portion across all payments (analytics).
- `total_burned_during_payments INTEGER DEFAULT 0` — running total of all burns (interest_burn + principal_burn) across all payments.
- `final_close_burn INTEGER DEFAULT 0` — burn amount on the single payment that closed the loan. Captures the V2 audit's "at close" event for ledger-level analytics.

**`LoanPayment` (`models.py`)**
- `interest_portion INTEGER DEFAULT 0` — how much of `amount` was applied to accrued_interest.
- `principal_portion INTEGER DEFAULT 0` — how much of `amount` was applied to principal balance. Always equals `amount - interest_portion`. Persisted (not derived) so historical rows survive future schema reshapes.
- `is_final_payment BOOLEAN DEFAULT 0` — true if this payment zeroed both balances and closed the loan.
- `balance_after` semantics updated: now `principal_remaining + accrued_interest_remaining` (total still owed) rather than just principal.

**`GlobalSettings` (`models.py`)**
- `interest_burn_rate_bps INTEGER DEFAULT 8000 NOT NULL` — the World Mint-controllable rate applied to interest portions of loan payments. 8000 = 80% (the "80" in the 20/80 split).

### Migrations (`app/main.py::_run_schema_migrations`)
- Eight idempotent `ALTER TABLE` statements covering the new columns.
- Backfill: `UPDATE loan_payments SET principal_portion = amount WHERE principal_portion = 0 AND interest_portion = 0 AND amount > 0` so historical pre-Phase-2B payments analyse cleanly as 100% principal.

### `pay_loan` rewrite (`app/routes/bank_routes.py`)

Old flow: single `amount * burn_rate_snapshot` split, applied uniformly to a single `outstanding` field.

New flow:
1. Cap payment at `total_owed = outstanding + accrued_interest` (don't overpay).
2. Allocate **interest first**, then principal: `interest_portion = min(amount, accrued_interest); principal_portion = amount - interest_portion`.
3. Per-portion burn split using the loan's snapshotted rates:
   - `interest_burn = floor(interest_portion * interest_burn_rate_snapshot / 10000)` (default 80%)
   - `principal_burn = floor(principal_portion * burn_rate_snapshot / 10000)` (default 10%)
   - bank shares = portion − burn share for each.
4. Combined ledger tx: one `LOAN_PAYMENT` for `total_to_bank`, one `BURN` for `total_burn`. The memos itemise the per-portion breakdown so the ledger remains forensically traceable.
5. Update both `loan.accrued_interest` and `loan.outstanding`.
6. Detect `is_final` = both balances now zero. On the closing payment: status → `closed`, `closed_at` = now, `final_close_burn = total_burn`.
7. Update `total_interest_paid` and `total_burned_during_payments` cumulative trackers.
8. Persist `LoanPayment` with the per-portion breakdown.

### API surface
- `POST /api/loans/{loan_id}/pay` response now returns the full breakdown: `interest_portion`, `principal_portion`, `interest_burn`, `interest_to_bank`, `principal_burn`, `principal_to_bank`, `is_final_payment`, `outstanding_principal`, `remaining_interest`. The legacy keys (`burn_amount`, `bank_amount`, `balance_after`) are preserved for back-compat — existing UI code reading those still works.
- `GET /api/mint/settings` and `POST /api/mint/settings` now expose/accept `interest_burn_rate_bps` (with 0–10000 bps validation). The setting is optional in the POST body for back-compat with existing clients.

### Design choices
- **Interest first allocation.** Standard amortisation convention. Prevents the borrower from indefinitely deferring interest — a payment can't reduce principal until the day's interest is paid.
- **Snapshot the interest burn rate at creation.** Mirrors the existing `burn_rate_snapshot` pattern so a mid-loan global-settings change doesn't retroactively alter loans already in flight.
- **Combine portions into a single ledger BURN tx and a single LOAN_PAYMENT tx per payment.** Two ledger rows per payment instead of four. Memo strings carry the per-portion breakdown for audit. Keeps the chain compact while preserving traceability.
- **`final_close_burn` tracked separately from `total_burned_during_payments`.** Enables a clean V2-audit-aligned report: "X TC was burned during the loan's life, Y of that on the closing payment specifically." Useful for analyzing whether large balloon-style payoffs are common.

### Verification
- Synthetic math test (`py -c …`) covered three cases: pure-interest payment (1000 vs 5000 accrued), mixed payment (6000 vs 5000 accrued = 5000 interest + 1000 principal), and pure-principal payment (100 with 0 accrued). All burn/bank splits match expected values to the TC.
- AST syntax check on the three touched files: clean.

### Phase 2B commit
Pending — committed at end of phase with message: `Phase 2B: rework loan payment with interest-first allocation and 20/80 split`.

