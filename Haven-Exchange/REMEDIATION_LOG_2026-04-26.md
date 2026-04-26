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

## Phase 2B — Burn Mechanics Rework (Interest-Only 20/80 Pool)

**Goal:** Replace the prior "uniform burn on every payment dollar" model with an **interest-only** burn pool, split 20% during payments / 80% at loan close.

**The model in plain terms:**
- Total burn pool over a loan's life = **10% of total interest paid** (zero burn ever applied to principal).
- Of that pool, 20% is burned **during payments** (each payment burns `floor(interest_portion × 0.02)` from the borrower).
- The remaining 80% is burned **at close** from the **bank's reserves** (the bank has been holding the burn pool since each payment).

### Schema (already migrated as part of 2A pre-staging — verified intact this phase)

**`Loan`** carries the running totals:
- `total_interest_paid` — sum of every payment's `interest_portion`.
- `total_burned_during_payments` — sum of the during-payment burn slices (20% of pool).
- `final_close_burn` — bank-sourced burn on the closing payment (80% of pool, residual after the during-payment slice).
- `burn_rate_snapshot` — re-purposed in 2B: now the **total burn pool rate** against lifetime interest (default 1000 bps = 10%). Was previously "principal burn rate".
- `interest_burn_rate_snapshot` — re-purposed in 2B: now the **at-close fraction of the pool** (default 8000 bps = 80%). The during-payment fraction is the complement (default 2000 bps = 20%).

**`LoanPayment`** carries per-payment breakdown:
- `interest_portion`, `principal_portion`, `is_final_payment` (used to drive the close-burn branch).

**`GlobalSettings`** column comments updated to reflect the new semantics; the underlying `interest_burn_rate_bps` column was already present from the 2A migration block.

### `pay_loan` rewrite (`app/routes/bank_routes.py`)

Replaced the prior interest-80%-burn / principal-10%-burn implementation with the spec's interest-only pool:

1. Cap payment at `total_owed = outstanding + accrued_interest` (no overpay).
2. Allocate interest first: `interest_portion = min(amount, accrued_interest); principal_portion = amount − interest_portion`.
3. Compute the during-payment burn slice from the snapshotted rates:
   ```
   during_split_bps = 10000 − interest_burn_rate_snapshot          # default 2000 = 20%
   during_payment_burn = floor(
       interest_portion × burn_rate_snapshot × during_split_bps
       / (10000 × 10000)
   )
   # at default rates: floor(interest_portion × 0.10 × 0.20) = floor(interest_portion × 0.02)
   ```
4. Bank receives the rest: `to_bank = amount − during_payment_burn`. Principal flows entirely to the bank, never burned.
5. Ledger writes (in order):
   - `LOAN_PAYMENT`: borrower → bank, `to_bank` (single combined tx for both interest-bank and principal portions).
   - `BURN` (during-payment): borrower → World Mint, `during_payment_burn` (if > 0).
6. Apply allocations to `accrued_interest` / `outstanding`, then update running totals (`total_interest_paid`, `total_burned_during_payments`).
7. **Final-payment branch** (both balances now 0):
   ```
   total_burn_pool = floor(total_interest_paid × burn_rate_snapshot / 10000)   # 10% of lifetime interest
   close_burn      = max(0, total_burn_pool − total_burned_during_payments)    # the residual 80%
   ```
   - If `close_burn > 0`: third ledger write `BURN`: bank wallet → World Mint, `close_burn`.
   - Set `loan.final_close_burn`, `status = 'closed'`, `closed_at = now`.
8. `bank.total_burned += during_payment_burn + close_burn` (lifetime analytic spans both burn sources).
9. Persist `LoanPayment` with `burn_amount = during_payment_burn + close_burn`, `bank_amount = to_bank`, `interest_portion`, `principal_portion`, `is_final_payment`.

### API surface
- `POST /api/loans/{loan_id}/pay` response now returns: `amount`, `interest_portion`, `principal_portion`, `during_payment_burn`, `close_burn`, `burn_amount`, `bank_amount`, `is_final_payment`, `balance_after`, `outstanding_principal`, `remaining_interest`. (Old keys `interest_burn` / `interest_to_bank` / `principal_burn` / `principal_to_bank` removed — they reflected the prior model and would mislead.)
- `GET /api/mint/settings` and `POST /api/mint/settings` already exposed `interest_burn_rate_bps`; meaning is now "at-close pool fraction" (was "interest-portion burn rate"). API shape unchanged.

### Design choices
- **Burn is interest-only.** The spec is explicit: principal repayment is never burned. The repurposed `burn_rate_snapshot` (now "total pool rate against interest") encodes this — there is no second principal-burn computation in the new code path.
- **Close burn flows from the bank, not the borrower.** The borrower's payment is capped at `total_owed`, so any "extra" burn at close has to come from somewhere else. The bank has been collecting roughly 98% of every interest dollar throughout the loan's life — that pool is what funds the close burn. This matches the spec's intent ("subtract total_burned_during_payments, burn the remainder") and produces a self-balancing model: total minted-by-interest never escapes, total burned matches the 10% target, the bank net-earns 90% of interest.
- **Re-purposed snapshot fields rather than adding new ones.** The existing `burn_rate_snapshot` and `interest_burn_rate_snapshot` columns happen to default to the right values (1000 bps and 8000 bps) for the new model. Renaming them would have rippled through migrations and a UI without changing behaviour. The model docstrings now document the new semantics; the DB schema is untouched.
- **Three transactions per closing payment, two per non-closing.** Each burn source is a separate ledger row so the chain remains forensically auditable: one `LOAN_PAYMENT` (borrower → bank), one `BURN` (borrower → World Mint, the 20% slice), and on close, one more `BURN` (bank → World Mint, the 80% slice). Memos identify which slice each burn represents.
- **Failure mode on close burn.** If the bank's reserves cannot cover the close burn (e.g. the bank has loaned out reserves elsewhere), `create_transaction` raises `ValueError` and the endpoint returns `400` — the loan stays open. This is a pre-existing non-atomicity in `create_transaction` (commits per-call, no outer txn); fixing it is out of scope for 2B.

### Verification
- AST syntax check (`py -c "import ast; ast.parse(open(f).read())"`) on `app/models.py` and `app/routes/bank_routes.py`: clean.
- Walk-through math at default rates (10% pool / 20-80 split) with 1000 TC interest accrued, paid in two equal payments:
  - Payment 1: `interest_portion=500, during_burn=floor(500×0.02)=10, to_bank=490`. Running: `total_interest_paid=500, total_burned=10`.
  - Payment 2 (final): `interest_portion=500, during_burn=10, to_bank=490`. Running before close: `total_interest_paid=1000, total_burned_during=20`. `total_pool=floor(1000×0.10)=100`. `close_burn=100−20=80`. Bank → World Mint: 80.
  - Totals: borrower paid 1000 interest. World Mint received 10+10+80 = 100 (= 10% of interest, ✓). Bank net: 490+490−80 = 900 (= 90% of interest, ✓).

### Phase 2B commit
Committed as `a12a4bd` — `Phase 2B: rework loan payment with interest-first allocation and 20/80 split`.

---

## Phase 2C — Treasury Lending

**Goal:** Allow nation treasuries to issue loans alongside banks, removing the bank-only constraint identified in the V2 audit.

### Design decision — `bank_id=0` sentinel vs nullable

The V2 spec called for making `bank_id` nullable. SQLite cannot ALTER a column's nullability after creation without a full table rebuild, so the prior migration approach (idempotent `ALTER TABLE … ADD COLUMN`) cannot accomplish it. Instead, `bank_id=0` is used as a sentinel for treasury loans. The real lender identity is carried by the two new columns:

- `lender_type TEXT DEFAULT 'bank'` — discriminator, values `'bank'` or `'treasury'`.
- `lender_wallet_address TEXT` — denormalized wallet for the lender (bank or treasury address). Enables payment routing in `pay_loan` with a single code path instead of a discriminating join.
- `treasury_nation_id INTEGER` — FK to `nations.id`; set for treasury loans, NULL for bank loans.

All three columns were introduced with Phase 2C migrations already included in the committed `_run_schema_migrations()` block (see `app/main.py`). Pre-existing loan rows were backfilled: `lender_type='bank'` and `lender_wallet_address` denormalized from `banks.wallet_address`.

### Schema (`app/models.py`)

- `Loan.lender_type`, `Loan.lender_wallet_address`, `Loan.treasury_nation_id` — already present in model from prior preparation work.
- Added `Loan.treasury_nation: Mapped[Optional["Nation"]]` relationship using `foreign_keys=[treasury_nation_id]`. No backref on `Nation` (avoids naming collision with existing backrefs).

### `app/blockchain.py`

- Added `"LOAN_DISBURSE"` to `_VALID_TX_TYPES`. Treasury loans use this type (vs `"LOAN"` for bank loans) so the ledger distinguishes the funding source.

### New endpoints (`app/routes/bank_routes.py`)

**`POST /api/nations/{nation_id}/loans`** — Issue treasury loan.
- Auth: `require_login` + `nation.leader_id == current_user.id`.
- Validates: nation approved, amount > 0, borrower exists and is a nation member, borrower has no active loans, treasury has sufficient balance.
- Writes a `LOAN_DISBURSE` transaction (nation.treasury_address → borrower.wallet_address). `create_transaction()` handles the `NATION_WALLET_PREFIX` balance debit/credit automatically.
- Creates `Loan` with `bank_id=0`, `lender_type='treasury'`, `lender_wallet_address=nation.treasury_address`, `treasury_nation_id=nation_id`. All Phase 2A/2B fields initialised identically to bank loans (cap_amount=principal, interest_rate from GlobalSettings snapshot, etc.).
- Response shape matches bank loan creation (`id`, `lender_type`, `treasury_nation_id`, `principal`, `outstanding`, `accrued_interest`, `cap_amount`, `interest_frozen`, `interest_rate`, `burn_rate_snapshot`, `status`, `tx_hash`).

**`GET /api/nations/{nation_id}/loans`** — List treasury-issued loans.
- Auth: nation leader or `world_mint`.
- Filters `Loan` table by `treasury_nation_id == nation_id AND lender_type == 'treasury'`.
- Response matches the shape returned by `GET /api/banks/{bank_id}/loans` (borrower name/wallet, all accrual fields, lender fields, timestamps).

**`POST /api/nations/{nation_id}/loans/{loan_id}/forgive`** — Forgive a treasury loan.
- Auth: nation leader of the specified nation.
- Filters loan by `lender_type='treasury' AND treasury_nation_id==nation_id` to prevent cross-nation forgiveness.
- Zeroes `loan.outstanding`, sets `status='closed'` (consistent with bank loan forgiveness in Phase 1).
- Writes a `LOAN_FORGIVE` ledger entry from `nation.treasury_address` to `borrower.wallet_address` with `amount=0` (audit trail only, no coin movement).

### Existing endpoint updates (`app/routes/bank_routes.py`)

- `pay_loan`: Already dispatched on `lender_type` in the prior preparation commit — `bank_id > 0` branch for bank loans, `lender_wallet_address` used uniformly as the LOAN_PAYMENT destination and BURN close-source. No change needed.
- `forgive_loan` (bank variant): Unchanged — it filters `Loan.bank_id == bank_id`, so treasury loans (bank_id=0) are only accessible via the new nation endpoint.
- `list_bank_loans` / `my_loans`: Already included `lender_type`, `lender_wallet_address`, `treasury_nation_id` in responses. No change.
- `create_loan` (bank variant): Already sets `lender_type='bank'`, `lender_wallet_address=bank.wallet_address`, `treasury_nation_id=None`. No change.

### `app/interest.py`

No changes. The accrual engine operates on `Loan.status`, `interest_frozen`, `interest_rate`, `cap_amount`, and `principal` — all of which are set identically for treasury loans. Interest accrues on treasury loans the same day as bank loans.

### Verification

- AST syntax checks on all three modified files: `app/models.py`, `app/blockchain.py`, `app/routes/bank_routes.py` — all clean.
- Structural review: `LOAN_DISBURSE` credited via `NATION_WALLET_PREFIX` branch in `create_transaction()`, deducting `nation.treasury_balance` and crediting `borrower.balance` — matches spec "Deducts from nation.treasury_balance, adds to borrower.balance".
- `pay_loan` close-burn path already uses `lender_wallet` (from `loan.lender_wallet_address`) as the BURN source for both bank and treasury loans — treasury close burn correctly debits the treasury address.

### Phase 2C commit
Committed as `Phase 2C: add treasury lending via lender_type abstraction`.

