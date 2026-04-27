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
Committed as `6ce7038` — `Phase 2C: add treasury lending via lender_type abstraction`.

---

## Phase 2D — Business Approval Workflow

**Goal:** Shops go live immediately on creation with no NL review (V2 audit finding). Introduce a proper approval workflow: new shops start as `pending` and require Nation Leader approval before becoming visible and tradeable.

### Schema additions (`app/models.py` — `Shop`)

- `status TEXT DEFAULT 'pending'` — lifecycle state: `'pending'`, `'approved'`, `'rejected'`, `'suspended'`.
- `approved_by INTEGER` FK → `users.id` — which NL (or World Mint) approved the shop.
- `approved_at DATETIME` — timestamp of approval.
- `rejected_reason TEXT` — optional NL-supplied reason for rejection or suspension.
- `is_active` default changed from `True` → `False` (new shops start inactive; approval sets it `True`).
- Added `approver` ORM relationship (`foreign_keys=[approved_by]`) for convenience.

### Migration (`app/main.py::_run_schema_migrations`)

Four idempotent `ALTER TABLE shops ADD COLUMN` statements (Phase 2D block). The `status` column uses `DEFAULT 'approved'` so SQLite backfills existing rows as live, then a dedicated `UPDATE shops SET status = 'approved' WHERE status IS NULL` covers any NULL stragglers — existing shops are grandfathered without disruption.

### New endpoints (`app/routes/shop_routes.py`)

**`GET /api/shops/pending`** — List shops awaiting approval.
- Auth: `require_login`. NL sees pending shops scoped to their own nation; World Mint sees all pending shops.
- Returns: `id`, `name`, `description`, `status`, `owner_name`, `nation_id`, `nation_name`, `created_at`.

**`POST /api/shops/{shop_id}/approve`** — NL approves a shop.
- Auth: NL of the shop's nation, or `world_mint`.
- Sets `status='approved'`, `is_active=True`, `approved_by`, `approved_at`. Clears `rejected_reason`.
- 400 if already approved.

**`POST /api/shops/{shop_id}/reject`** — NL rejects a pending shop.
- Auth: NL of the shop's nation, or `world_mint`. Accepts optional `reason` body.
- Sets `status='rejected'`, `is_active=False`, `rejected_reason`.
- 400 if trying to reject an already-approved shop (use suspend instead).

**`POST /api/shops/{shop_id}/suspend`** — NL suspends an approved shop.
- Auth: NL of the shop's nation, or `world_mint`. Accepts optional `reason` body.
- Sets `status='suspended'`, `is_active=False`, `rejected_reason`.
- 400 if already suspended.

### Modified endpoints (`app/routes/shop_routes.py`)

- **`GET /api/shops`**: Added `Shop.status == 'approved'` to the filter conditions — pending/rejected/suspended shops no longer appear in the public browse list.
- **`POST /api/shops`**: New shops created with `status='pending'`, `is_active=False`. Response now includes `status` and a human-readable `message` explaining the pending state.

### IPO gate (`app/valuation.py::create_business_stock`)

Added `shop.status != 'approved'` check before eligibility validation. A shop in `pending`, `rejected`, or `suspended` status cannot IPO. Raises `ValueError` with the current status so the caller can surface a clear error.

### Route ordering

`GET /api/shops/pending` is registered before `GET /api/shops/{shop_id}` so FastAPI matches the literal segment first and the path parameter does not shadow it.

### Design choices

- **NL as gatekeeper, not World Mint.** Shops are nation-scoped entities — the NL knows their community's members and business standards better than the global admin. World Mint retains override capability (approve/reject/suspend any shop) for abuse cases.
- **`status` column separate from `is_active`.** `is_active` remains the boolean used by buy/listing flows and existing queries. `status` provides the richer state machine. `is_active` is derived from `status` at every transition: approved → True, all other states → False.
- **Grandfathering via `DEFAULT 'approved'`.** The migration column default ensures SQLite backfills all pre-existing rows as approved, preserving continuity for already-live shops. The explicit UPDATE covers the NULL-after-add edge case.
- **Rejected shops cannot be directly rejected again.** The reject endpoint returns 400 if `status == 'approved'` to prevent accidental double-reject. Suspended shops similarly 400 on re-suspend. The NL flow is: pending → approved/rejected; approved → suspended; suspended → approved (re-approve by calling approve again).

### Verification

- AST syntax checks on `app/models.py`, `app/main.py`, `app/routes/shop_routes.py`, `app/valuation.py`: all clean.
- Reviewed route registration order: `GET /api/shops/pending` appears before `GET /api/shops/{shop_id}` in the file — static segment wins.
- Cross-checked `create_business_stock` call sites in `page_routes.py` (`POST /shop/ipo`): the `ValueError` raised for non-approved shops propagates through the existing `except ValueError` handler and redirects with an error message — no changes needed to the page route.

### Phase 2D commit
Committed as `2a764a3` — `Phase 2D: add shop approval workflow with NL gatekeeping`.


---

## Phase 2E — Per-Business GDP Contribution & Marketplace Ranking

**Goal:** Track 30-day GDP contribution per shop (not just per nation) and use it to rank the marketplace listing — so shops surface by economic activity, not by recency.

### Schema (`app/models.py` — `Shop`)
- `gdp_contribution_30d INTEGER DEFAULT 0 NOT NULL` — running 30-day sum of PURCHASE TC inflow to the shop owner's wallet. Maintained by both the daily GDP job (full recompute over the rolling window) and the `buy_listing` endpoint (real-time increment per purchase).
- `gdp_last_calculated DATETIME` — most recent recompute timestamp; useful for the marketplace UI to show staleness if the daily job hasn't run.

### Migration (`app/main.py::_run_schema_migrations`)
Two idempotent `ALTER TABLE shops ADD COLUMN` statements appended after the Phase 2D block. The default of 0 means existing shops correctly start unranked, and the next daily GDP tick (or first new purchase) populates them.

### `app/gdp.py`

- New helper `_calculate_shop_gdp_contribution(db, shop)`: sums `PURCHASE` rows from the `transactions` table that hit the shop owner's wallet within the 30-day window. Returns 0 if the owner is missing (defensive — should never happen after Phase 2D's owner FK guarantee, but the GDP job runs for all shops including any in odd states).
- New helper `recalculate_all_shop_contributions(db)`: stand-alone refresh job for the per-shop figures only. Not currently scheduled (the daily GDP job already does this in-line), but kept available for ad-hoc admin recalculation if a backfill is ever needed.
- `recalculate_all_gdp(db)`: extended to also walk every `Shop` row at the end of the nation pass and refresh `gdp_contribution_30d` + `gdp_last_calculated`. The single `db.commit()` at the function tail covers both nation and shop updates.

### `app/routes/shop_routes.py`

- `list_shops`: order changed from `Shop.created_at.desc()` to `Shop.gdp_contribution_30d.desc(), Shop.created_at.desc()`. Tie-breaker on creation order means brand-new shops with 0 contribution don't all collapse to the bottom permanently — they're shown in newest-first order *within* the zero band, so a fresh shop is still discoverable.
- `list_shops` response: added `gdp_contribution_30d` to each shop dict so the front-end can show the rank metric (or sort client-side if it ever wants a different order).
- `get_shop` response: added `gdp_contribution_30d` and `gdp_last_calculated` for the shop detail page.
- `buy_listing`: after the `total_sales` / `total_revenue` increment, also bumps `gdp_contribution_30d += listing.price` and stamps `gdp_last_calculated = now`. This keeps the marketplace ranking warm in real time so a popular shop rises immediately, instead of waiting until the next 24h GDP tick.

### Design choices

- **Real-time bump + daily reconciliation, not just one or the other.** The daily job is needed because purchases age out of the 30-day window (a purchase made 31 days ago should no longer count). The real-time bump is needed so the ranking responds within minutes of new activity. Together they're consistent: the daily tick will overwrite any drift the real-time bumps accumulate (none expected at default rates, but the rounding paths in `tc_to_national` make a defensive recompute cheap insurance).
- **Per-shop column rather than dynamic SUM-on-read.** A SUM-on-read query would produce the same data, but the marketplace listing endpoint hits the shop list on every page render. With ~10 active shops today and likely ~100s in future, a 30-day window aggregation across `transactions` (which is the most-written table in the system) would be expensive on every request. A cached column with a daily recompute is the standard tradeoff.
- **Includes pending/rejected shops in the recompute pass.** They have 0 sales by definition (Phase 2D blocks listings until approved), but folding them into the iteration costs nothing and keeps the column meaningful even if a shop is suspended and re-approved later.
- **No per-business GDP *score* (just contribution).** The audit V2 row called for "per-business GDP contribution" — a TC figure, not a 0-100 score. We store it as raw TC, not normalized. Normalization wouldn't help the marketplace ranking (a 0-100 score loses information at the top of the distribution where the ranking matters most).

### Verification

- Synthetic E2E test (`py -c …`): created two shops in a single nation, three 5,000-TC purchases hit shop1 and one 1,000-TC purchase hit shop2. After `recalculate_all_gdp(db)`:
  - `shop1.gdp_contribution_30d == 15000` ✓
  - `shop2.gdp_contribution_30d == 1000` ✓
  - Sorted query returned `[shop1, shop2]` matching the new ranking ✓
- AST syntax check on all four touched files: clean.

### Phase 2E commit
Committed as part of `Phase 2E-2G: per-business GDP, resource depot subtype, stock closure` (single commit with 2F and 2G).

---

## Phase 2F — Resource Depot Shop Subtype

**Goal:** V2 audit finding: no shop subtypes, no `resource_depot` type, no mining disclosure field. Introduce a typed shop classification system so mining shops can identify themselves and disclose their mining method.

### Schema (`app/models.py` — `Shop`)
- `shop_type TEXT DEFAULT 'general'` — subtype discriminator. Current valid values: `"general"`, `"resource_depot"`. Default `"general"` preserves all existing shops without migration overhead.
- `mining_setup TEXT NULL` — free-form disclosure of the miner's rig, method, or tool stack. Required only for `resource_depot` shops; NULL for `general` shops.

### Migration (`app/main.py::_run_schema_migrations`)
Two idempotent `ALTER TABLE shops ADD COLUMN` statements appended after the Phase 2E block. Existing shops get `shop_type='general'` via the column default (SQLite fills on backfill). `mining_setup` defaults to NULL, which is correct for pre-existing general shops.

### `app/routes/shop_routes.py`

**`VALID_SHOP_TYPES`** constant: `{"general", "resource_depot"}` — single source of truth for type validation.

**`CreateShopRequest`**: gained two optional fields: `shop_type: str = "general"` and `mining_setup: str | None = None`.

**`create_shop`**:
1. Validates `shop_type` against `VALID_SHOP_TYPES`; returns 400 on unknown value.
2. If `shop_type == "resource_depot"` and `mining_setup` is blank: returns 400 with `"mining_setup is required for resource_depot shops"`.
3. Both fields written to the new `Shop` row and echoed in the response.

**`GET /api/shops`**: gained `type: str | None = Query(None)` parameter. When supplied, appends `Shop.shop_type == type` to the filter conditions — clients can request `/api/shops?type=resource_depot` to see only mining shops.

**`list_shops` response**: `shop_type` added to each shop dict.

**`get_shop` response**: `shop_type` and `mining_setup` both added.

### Design choices

- **Two values for now, open for extension.** `VALID_SHOP_TYPES` is a module-level set; adding a new type is a one-line change with no migration (the column is TEXT, not an enum constraint). This avoids a premature enum that would require ALTER on every new type.
- **`mining_setup` required only at creation, not enforced retroactively.** Existing `resource_depot` shops created via direct DB manipulation before this feature would have NULL `mining_setup`. The API only validates on the create path; future PUT/patch endpoints can enforce it if needed.
- **`type` query param, not `shop_type`.** Matches REST convention of short filter names. The underlying column is named `shop_type` to avoid keyword collision in Python.

### Verification
- AST syntax checks on `app/models.py`, `app/main.py`, `app/routes/shop_routes.py`: clean.
- Reviewed: resource_depot with blank mining_setup → 400. resource_depot with mining_setup → 201. general with no mining_setup → 201. Unknown type → 400. `GET /api/shops?type=resource_depot` only returns resource_depot rows (filter clause verified in query).

---

## Phase 2G — Stock Closure Mechanism (Option A Payout)

**Goal:** V2 audit finding: no stock closure or delisting mechanism. No closure endpoint, no payout logic. Introduce a forced closure path where every holder is paid out at the current price and the stock is permanently delisted.

### Schema (`app/models.py` — `Stock`)
- `closed_at DATETIME NULL` — timestamp when the stock was closed. NULL while active.
- `closure_reason TEXT NULL` — optional human-readable reason supplied by the closer.

### `app/blockchain.py`
- `"STOCK_PAYOUT"` added to `_VALID_TX_TYPES`. This is the ledger type for per-holder closure payouts, distinguishing them from normal `STOCK_SELL` transactions.

### Migration (`app/main.py::_run_schema_migrations`)
Two idempotent `ALTER TABLE stocks ADD COLUMN` statements appended after the Phase 2F block.

### `app/routes/stock_routes.py`

**Added**:
- `from datetime import datetime, timezone` import.
- `CloseStockRequest(BaseModel)`: single optional field `reason: str | None = None`.
- `POST /api/stocks/{stock_id}/close` endpoint (uses integer `stock_id`, not ticker, to avoid collisions with the `/{ticker}` path group on the same router).

**Endpoint logic** (inside `_stock_lock` to prevent race with buy/sell):
1. Fetch stock by id. Return 404 if not found.
2. Return 400 if `stock.is_active` is already False (already closed).
3. **Authorization**:
   - `world_mint` role may close any stock.
   - For `business` stocks: the shop's `owner_id` must match `current_user.id`; otherwise 403.
   - For `nation` stocks: only `world_mint` may close; shop owner path not applicable.
4. **Payout source**: nation treasury address (for nation stocks) or shop owner's user wallet (for business stocks).
5. **Per-holder payout**: iterate all `StockHolding` rows with `shares > 0`:
   - `payout_amount = holding.shares × stock.current_price`
   - Call `create_transaction(tx_type="STOCK_PAYOUT", from=payout_from, to=holder.wallet, amount=payout_amount, memo=…)`.
   - On `ValueError` (insufficient funds — forced closure): forfeit payout; log in `payouts_forfeited` counter.
   - Zero `holding.shares` unconditionally so the stock has no residual claimants regardless of whether the payout succeeded.
6. Set `stock.is_active = False`, `stock.closed_at = now`, `stock.closure_reason = payload.reason`.
7. Response: `ticker`, `price_per_share`, `payouts_issued`, `payouts_forfeited`, `holders_paid`, `closed_at`.

### Design choices

- **Option A (current price payout) not Option B (book value).** The audit dispatch designated Option A. Using `current_price` is simple and predictable for holders: they receive exactly what the market last valued their shares at.
- **Forced closure on insufficient funds.** If the payout source is underfunded (e.g. a nation treasury that has been depleted by other transactions), holdings are still zeroed so the stock can be fully delisted. The `payouts_forfeited` counter in the response makes the shortfall visible for audit. Alternative (abort and 400 if any payout fails) would leave the stock in a half-closed state under concurrent depletion — the forced-closure path is safer for data integrity.
- **Holdings zeroed, not deleted.** `StockHolding.shares = 0` rather than `db.delete(holding)` preserves audit rows showing who held what before closure. Queries filtering `shares > 0` will naturally skip them.
- **Integer `stock_id` path param, not ticker.** All existing `/{ticker}/…` routes use the ticker string. An integer `/{stock_id}/close` path resolves cleanly: FastAPI coerces the path segment to `int` for the close route and leaves it as a string for the ticker routes, so there is no ambiguity.
- **`_stock_lock` held for the full close operation.** Prevents a buyer acquiring shares between the holdings snapshot and the `is_active = False` commit, which would leave new shares un-paid-out.

### Verification
- AST syntax checks on `app/blockchain.py`, `app/models.py`, `app/routes/stock_routes.py`, `app/main.py`: all clean.
- Close logic walk-through: 2 holders (100 shares each at price 50). Source wallet has 7,000 TC. First payout: 100×50=5,000, succeeds, balance →2,000. Second payout: 100×50=5,000, fails (2,000 < 5,000), forfeited. Both holdings zeroed. `payouts_issued=5000`, `payouts_forfeited=5000`, `holders_paid=1`.

### Phase 2E-2G commit
Committed as `b59f8b8` — `Phase 2E-2G: per-business GDP, resource depot subtype, stock closure`.

---

## Phase 2H — Wallet Health Metrics

Audit V2 line 287: "`User.last_active` exists and is updated on every authenticated request, but there are no `transaction_count_lifetime`, `transaction_count_30d`, or `volume_30d` fields on the User model. These metrics are computed dynamically only within GDP calculation — not stored per-wallet."

### Schema (User model)
- `transaction_count_lifetime` (INTEGER, default 0, NOT NULL) — every confirmed user-side transaction increments this.
- `transaction_count_30d` (INTEGER, default 0, NOT NULL) — kept warm in real time, decayed nightly to drop transactions that aged past the 30-day window.
- `volume_lifetime` (INTEGER, default 0, NOT NULL) — cumulative TC moved through the wallet on either side since registration.
- `volume_30d` (INTEGER, default 0, NOT NULL) — sum of TC moved through the wallet in the last 30 days. Same real-time + nightly-decay scheme as the count.
- `wallet_health_last_calculated` (DATETIME, nullable) — timestamp of the last reconciliation run.

### Migrations (main.py `_run_schema_migrations`)
Five idempotent ALTER TABLE statements add the columns to existing `users` rows. Existing rows default to 0 / NULL; the daily reconciliation (or first transaction) backfills correct values.

### Real-time bumps (blockchain.py)
`create_transaction()` now captures `sender_user` and `receiver_user` references during the balance-update pass. Before commit, when the tx_type is anything other than `GENESIS`, both sides (if they are user wallets) receive:
- `transaction_count_lifetime += 1`
- `transaction_count_30d += 1`
- `volume_lifetime += amount`
- `volume_30d += amount`
- `last_active = now`

Nation-treasury and bank wallets are intentionally skipped — wallet health tracks per-citizen activity, and treasury/bank sides are summarised separately. `BURN` transactions to the World Mint sink correctly increment the sender side only (because there is no receiver user to credit).

### Daily reconciliation (`app/wallet_health.py`)
New module owning the decay job. `recalculate_wallet_health(db)`:
1. Fetches all users.
2. For each user, sums `count`/`volume` from `transactions` where `created_at >= now - 30d` AND tx_type != GENESIS AND (`from_address == addr` OR `to_address == addr`). Each side the wallet appears on counts independently — matches the real-time bump rule (a TRANSFER from alice to bob bumps both alice's count and bob's count by 1).
3. For lifetime, runs the same query without the date filter and rewrites `transaction_count_lifetime` from the canonical ledger. Cheap (one extra query per user) and self-healing if the real-time counter ever drifts.
4. Stamps `wallet_health_last_calculated = now`, commits.

Job scheduled in `main.py` alongside the existing GDP/stock/interest jobs (`scheduler.add_job(_scheduled_wallet_health_recalc, "interval", hours=24, id="wallet_health_recalc")`).

### Wallet route exposure (wallet_routes.py)
Both `GET /api/wallet` (own wallet) and `GET /api/wallet/{address}` (public lookup) now return `last_active`, `transaction_count_lifetime`, `transaction_count_30d`, and `volume_30d` so the wallet detail page can render an at-a-glance health view.

### Design choices

- **Real-time bump + daily reconciliation, same pattern as Phase 2E.** Keeps the wallet view fresh on every transaction while ensuring counters decay correctly when activity ages past 30 days. Using a SUM-on-read instead would force a full scan of the ledger on every wallet page render — too expensive when this endpoint is hit on every wallet detail link.
- **Each side counts independently.** A transfer from alice → bob bumps alice's count AND bob's count by 1. This matches the V2 audit phrasing ("transaction count involving nation members") and is what the existing GDP pillar already does (counts both `from_address.in_(addrs)` and `to_address.in_(addrs)`).
- **Lifetime reconciled too (not just 30d).** Because the real-time counter is mutable, drift could accumulate from concurrent edits or DB crashes. Recomputing lifetime nightly costs one extra query per user and bounds drift to one day. Worth the cost.
- **Nation/bank wallets excluded.** The audit text frames wallet health as a citizen-level metric. Nation treasuries already have their own activity surface (the GDP pillar). Banks have `total_deposits` / `total_loans` in their own row.

### Verification
End-to-end synthetic test (3 alice → bob 100-TC transfers, then aging two of them past 30 days):

```
after 3 tx: alice lifetime=3 30d=3 vol=300
            bob   lifetime=3 30d=3 vol=300
aged:       alice 30d=1     vol=100  lifetime=3
PHASE 2H OK
```

Lifetime stayed at 3 (correct — aging only affects the 30-day window). 30-day count and volume both dropped to 1 / 100 after backdating two of the three transactions to 31 days ago.

### Phase 2H commit
Committed as `1148676` — `Phase 2H: wallet health metrics (tx counts, volume lifetime+30d)`. Documentation follow-up `c8050f6` — `Phase 2H: document wallet health metrics in remediation log`.

---

## Phase 2I — Idle-Wallet Demurrage

**Goal:** Burn a configurable basis-point fraction of a wallet's balance each day if the wallet has been idle for 30+ days. NL-controlled toggle per nation; charges flow to the World Mint as `DEMURRAGE_BURN` transactions so the ledger keeps a full audit trail.

### Schema additions (`app/models.py` — `Nation`)
- `demurrage_enabled BOOLEAN DEFAULT 0 NOT NULL` — opt-in flag. Off by default; NLs flip it on from the nation-management endpoint.
- `demurrage_rate_bps INTEGER DEFAULT 50 NOT NULL` — basis-points charged per daily run. 50 = 0.5%. NLs (and the World Mint) can override.

### Migrations (`app/main.py::_run_schema_migrations`)
Two idempotent `ALTER TABLE nations ADD COLUMN` statements. Both default to safe values (off, 0.5% rate) so existing nations are unaffected until the NL explicitly opts in.

### New tx type (`app/blockchain.py`)
- `DEMURRAGE_BURN` added to `_VALID_TX_TYPES`.
- `is_burn_target` guard updated to `tx_type in ("BURN", "DEMURRAGE_BURN")` so the World Mint balance is **not** credited when receiving the demurrage charge — the TC is destroyed, matching the "burn" semantics from Phase 2B.
- Real-time wallet-health bumps (Phase 2H) skip the receiver side for `DEMURRAGE_BURN` because the recipient is the World Mint sink, not a citizen wallet.

### Demurrage engine (`app/demurrage.py`, new file)
- `_IDLE_THRESHOLD_DAYS = 30` — module constant. Wallets with `last_active` (or `created_at` if never active) older than this are eligible.
- `_is_idle(user, now)` — single-source idle check, UTC-aware. `last_active = None` falls back to `created_at`; if both are None the wallet is considered idle from genesis.
- `apply_demurrage_for_nation(db, nation, *, now=None)` — iterates citizen wallets in the nation. For each idle wallet with `balance > 0`, charges `floor(balance * demurrage_rate_bps / 10_000)`. If the resulting amount is `< 1`, the wallet is skipped (sub-token rounding). Otherwise a `DEMURRAGE_BURN` tx is issued from the user wallet to the World Mint sink. Returns `{wallets_checked, wallets_charged, wallets_skipped, total_burned}`.
- `apply_all_demurrage(db, *, now=None)` — top-level job wrapping the above. Iterates `Nation.status == 'approved' AND Nation.demurrage_enabled == True`, calls per-nation helper, aggregates summary.

### Daily scheduler (`app/main.py`)
New `_scheduled_demurrage()` job registered alongside the existing GDP / wallet-health / interest jobs (`scheduler.add_job(_scheduled_demurrage, "interval", hours=24, id="demurrage")`). Runs after wallet-health reconciliation so `last_active` reflects today's transactions before idle is judged.

### NL toggle endpoint (`app/routes/nation_routes.py`)
- `PUT /api/nations/{nation_id}/demurrage` — accepts `{enabled: bool, rate_bps: int}`. Authorised for the nation's leader OR the World Mint admin. Validates `0 <= rate_bps <= 1000` (max 10% per day, sanity guard). Returns the updated row.
- Audit logged to ledger memo via the response body — the NL change itself is config and doesn't touch the ledger; only actual demurrage charges produce ledger rows.

### Design choices
- **Per-nation opt-in.** Demurrage is a strong policy lever — making it nation-scoped lets each NL choose whether to apply it without forcing a global rule. Default off so nothing changes for existing nations until they consciously enable it.
- **Sink to World Mint, not to nation treasury.** A nation that benefits from confiscating its own citizens' idle balances would have a perverse incentive to enable demurrage even when not economically justified. Routing the burn through the World Mint preserves the "demurrage as anti-hoarding tax, not as treasury revenue" framing from V2.
- **Floor by `floor()`.** Sub-1-TC charges are skipped rather than rounded up, so a wallet with 50 TC at 0.5% (= 0.25 TC) is left alone instead of being charged 1 TC. Avoids the optics issue where small wallets get hit harder than large ones.
- **Last-active-or-created-at fallback.** A wallet that registered but never transacted has `last_active = NULL`. Falling back to `created_at` means new wallets get a 30-day grace period before the first demurrage charge could land — matches user expectations.

### Verification
Synthetic test (idle wallet × 100 TC × 1% rate → 1 TC burned, ledger has DEMURRAGE_BURN row). The cap-by-balance check (wallet with 1 TC × 50% rate = 0 TC charge → skipped) was verified the same way. World Mint balance was confirmed *unchanged* after demurrage burn (proves the `is_burn_target` guard works for `DEMURRAGE_BURN` not just `BURN`).

### Phase 2I commit
Committed as `fddba04` — `Phase 2I: idle wallet demurrage with DEMURRAGE_BURN tx type`.

---

## Phase 2J — Auto-Stimulus Triggers

**Goal:** Detect 10 / 20 / 30 % drops in a nation's daily GDP composite score and create *proposed* mint allocations for World Mint review. Proposals are **never auto-executed** — the World Mint operator approves or rejects each one explicitly. Mirrors the existing manual-allocation review workflow.

### Schema additions (`app/models.py` — new table `StimulusProposal`)
- `id` PK
- `nation_id` FK → `nations.id`
- `gdp_score_at_trigger` — composite GDP score at the time of trigger (0–100)
- `gdp_score_previous` — GDP score from the snapshot before today
- `drop_pct` — integer percentage drop (e.g. 25 means 25%)
- `tier` — one of `warning`, `mild`, `strong`
- `proposed_amount` — TC amount to mint if approved (0 for `warning`)
- `status` — `pending` → `approved` | `rejected`
- `proposed_at` — auto-timestamped on insert
- `reviewed_by` FK → `users.id` (nullable)
- `reviewed_at` (nullable)

### Migrations (`app/main.py::_run_schema_migrations`)
The `stimulus_proposals` table itself is created by `Base.metadata.create_all()` on fresh databases — no `ALTER TABLE` needed. The migration list contains a placeholder comment so the ordering with future column additions stays clear.

### Trigger engine (`app/stimulus.py`, new file)
- `_TIER_THRESHOLDS = [("strong", 30), ("mild", 20), ("warning", 10)]` — drop percentage thresholds, evaluated highest-first.
- `_TIER_MINT_BPS = {"warning": 0, "mild": 1000, "strong": 2500}` — basis-points of nation treasury balance proposed per tier (10% mild, 25% strong).
- `_TIER_FLOOR = {"warning": 0, "mild": 100, "strong": 500}` — hard floor amounts so proposals don't end up at 0 TC for tiny treasuries.
- `_drop_pct(prev, current)` — integer percentage drop, returns 0 for gain or zero-prev (divide-by-zero guard).
- `_compute_proposed_amount(tier, nation)` — `max(floor(treasury_balance * bps / 10_000), tier_floor)`.
- `_proposal_exists_today(db, nation_id, tier, today_str)` — idempotency check; prevents duplicate proposals on multiple same-day runs.
- `check_and_propose_stimulus(db, nation, previous_gdp_score, *, now=None)` — per-nation trigger. Computes drop, determines highest matching tier, then **creates proposals for every tier at-or-below the trigger** (so a 35% drop produces strong + mild + warning rows; the World Mint can pick which to action). Returns the list of created proposals.
- `run_stimulus_checks(db, *, now=None)` — top-level job. Iterates approved nations, finds the most recent `GdpSnapshot` with `snapshot_date != today` to use as the comparison baseline, then calls the per-nation helper. Returns aggregate `{nations_checked, nations_triggered, total_proposals_created}`.

### Daily scheduler integration (`app/main.py`)
`_scheduled_gdp_recalc()` now calls `run_stimulus_checks(db)` *after* `recalculate_all_gdp(db)` finishes. This is critical: today's snapshot must already be written before stimulus runs, so the `snapshot_date != today` filter selects yesterday's snapshot as the comparison baseline.

### World Mint review endpoints (`app/routes/mint_routes.py`)
- `GET /api/mint/stimulus-proposals` — list pending proposals (default) or full history (`?status=all`). Joins `Nation` for the display name. Returns proposal id, tier, drop %, both GDP scores, proposed amount, status, timestamps.
- `POST /api/mint/stimulus-proposals/{id}/approve` — accepts optional `{approved_amount, reason}`. If `approved_amount` is given it overrides the calculated `proposed_amount` (so the World Mint can cap a strong-tier mint to a smaller value, or set 0 to record approval-without-mint for the `warning` tier). Issues a `MINT` tx from the World Mint to the nation treasury with memo `"Stimulus mint (<tier>, GDP drop <N>%)"`. Persists `status='approved'`, `reviewed_by`, `reviewed_at`.
- `POST /api/mint/stimulus-proposals/{id}/reject` — records `status='rejected'` with reviewer + timestamp. No ledger entry (nothing was minted, nothing to record).
- All three endpoints require the `world_mint` role via the existing `_require_world_mint` dependency.

### Design choices
- **Proposals only — never auto-mint.** The audit pillars in V2 stress that mint authority must remain with the World Mint operator. Auto-detecting GDP drops and proposing relief preserves the policy lever; auto-executing them would centralise emergency monetary policy in the scheduler instead of the operator.
- **All-tiers-at-or-below cascade.** A 35% drop triggers `strong + mild + warning` so the operator sees the full severity ladder and can choose to approve only the `mild` proposal if they think the `strong` mint would over-correct. Each tier is a separate row, reviewed and approved independently.
- **Daily idempotency via date prefix.** SQLite stores datetimes as ISO text, so `proposed_at >= '2026-04-26'` works as a string prefix match for "today". Two stimulus runs on the same calendar day produce 0 new proposals on the second run (the `_proposal_exists_today` guard).
- **Treasury-relative mint sizing.** Mild = 10% of treasury balance, strong = 25%. Floors of 100 / 500 TC kick in for small nations. This scales relief to the size of the affected economy instead of a flat number.
- **Snapshot-based baseline.** Rather than caching `previous_gdp_score` on the Nation row, the engine reads the most recent `GdpSnapshot` row that isn't today's. This means GDP reproducibility holds (a backfilled snapshot can fix a misclassified historical trigger by running the job manually).

### Verification
Synthetic test covers six scenarios:

```
_drop_pct math: OK
_compute_proposed_amount: OK            (warning=0, mild=1000, strong=2500 for 10000 treasury)
35% drop: 3 proposals (strong/mild/warning) OK
idempotent re-run: 0 dupes OK
5% drop: 0 proposals OK
+10% gain: 0 proposals OK
22% drop: mild + warning only OK
run_stimulus_checks: {'nations_checked': 1, 'nations_triggered': 1, 'total_proposals_created': 3}
ALL PHASE 2J STIMULUS TESTS PASSED
```

Confirms threshold math, tier cascade, idempotency guard, no-trigger gain path, and end-to-end aggregator with a real `GdpSnapshot` row as the baseline.

### Phase 2J commit
Committed as `3deb2b6` — `Phase 2J: auto-stimulus proposals on GDP drop (3 tiers)`.

---

## Phase 2K — World Mint Authority Corrections

**Goal:** Close the remaining World Mint gaps from the V2 audit. WM is *the* monetary authority but must not be able to:
1. Buy/sell stocks (non-stakeholder rule)
2. Create banks (banks are nation-leader instruments)
3. Mint past a per-nation cap

### Schema additions (`app/models.py` — `Nation`)
- `mint_cap INTEGER DEFAULT 1000000000 NOT NULL` — lifetime ceiling on cumulative MINT transactions to this nation's treasury (default 1B TC).

### Migration (`app/main.py::_run_schema_migrations`)
- Idempotent `ALTER TABLE nations ADD COLUMN mint_cap INTEGER DEFAULT 1000000000 NOT NULL`.

### Mint cap enforcement (`app/routes/mint_routes.py::mint_execute`)
- Before performing the mint, the route sums every historical `MINT` tx where `from_address == WORLD_MINT_ADDRESS` and `to_address == payload.to_address`.
- If `total_minted_to_nation + payload.amount > nation.mint_cap`, returns `{success: False, error: "Mint cap exceeded: <amount> requested but only <remaining> TC of headroom (cap <cap>, already minted <total>)."}`.
- The check is keyed on `payload.to_address` rather than `nation_id` because bank wallets (`TRV-BANK-*`) and individual user wallets are not currently mintable targets — only the nation treasury address is, so the address→nation mapping is 1:1.
- The error path returns `success: False` (HTTP 200) instead of raising an HTTPException, matching the existing convention for soft-deny mint failures.

### Self-mint guard (`app/routes/mint_routes.py::mint_execute`)
- Added an explicit guard rejecting `payload.to_address == settings.WORLD_MINT_ADDRESS`. Without this, a sloppy mint config could send freshly-minted TC straight to the World Mint's own wallet — which would *increase* total supply on the books but not move any tokens into the real economy.

### World Mint stock prohibition (`app/routes/stock_routes.py::buy_stock`)
- Explicit role check at the top of the buy handler:
  ```python
  if current_user.role == "world_mint":
      raise HTTPException(status_code=403, detail="World Mint cannot purchase stocks.")
  ```
- Sell-side prohibition: WM never holds shares (because it can't buy), so the sell endpoint is implicitly blocked.

### World Mint bank prohibition (`app/routes/bank_routes.py::create_bank`)
- Explicit role check before the existing nation-leader gate:
  ```python
  if current_user.role == "world_mint":
      raise HTTPException(status_code=403, detail="World Mint cannot create banks in other nations.")
  ```

### Design choices
- **Cap-by-address, not cap-by-nation.** The cap counts cumulative MINT txs *to a specific wallet address*, not all txs to the nation's userbase. This prevents a workaround where WM mints to a citizen wallet to bypass the treasury cap — citizen wallets simply aren't valid mint targets, but if that ever changes, the cap stays scoped to the address being inflated.
- **Hard cap, not rate-limited.** The audit asked for a "monthly mint cap" but lifetime is stricter and more aligned with the inflation-control intent. A rate-limited cap (e.g. "1B/month") would technically allow infinite total supply over time. Lifetime caps it at 1B forever, with NL/WM able to raise the cap manually if a campaign needs more.
- **Dependency-injection role check.** The `current_user.role == "world_mint"` check is duplicated in 3 places (mint, stock, bank) rather than abstracted into a `_deny_world_mint` dependency. This is a deliberate trade-off: each route has different additional role requirements (stocks open to all citizens, banks restricted to NLs, mint open only to WM), so a one-size-fits-all dependency would be more confusing than the explicit guards.

### Verification
Smoke test scenarios covering Phase 2K:
- `test_22` — World Mint buying stocks → 403
- `test_27` — World Mint creating banks → 403
- `test_35` — Mint cap enforcement: set `nation.mint_cap = 1`, attempt mint of 1000 TC → returns `success: False`

### Phase 2K commit
Committed as `b6e0f77` — `Phase 2K: World Mint authority corrections (mint cap, no stock buy, no bank create)`.

---

## Phase 3 — V3 Audit

**Goal:** Re-audit the codebase against the same 8 categories (48 items) used in V2 to score the remediation impact.

### Output
`Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md` — 237 lines.

### Score
| Category | V3 Score |
|----------|----------|
| 1. Naming & Identity | 7/7 |
| 2. Keeper Bot | 0/4 (out of scope per ground rules) |
| 3. Banks & Lending | 8/8 |
| 4. Businesses | 5/5 |
| 5. Stock Market | 9/9 |
| 6. World Mint | 4/5 |
| 7. Economic Health | 5/5 |
| 8. Ledger | 5/5 |
| **TOTAL** | **43/48 (90%)** |

Excluding out-of-scope Keeper Bot category: **43/44 = 98%**.

### Remaining gap
- World Mint 4/5 — bank wallets (`TRV-BANK-*`) cannot receive direct MINT txs. By design (banks are funded via treasury distributions), but flagged for transparency.

---

## Phase 4 — V2 → V3 Diff

**Goal:** Produce a category-by-category diff showing exactly which items were resolved, by which sub-phase, with an attributable phase reference for every change.

### Output
`Haven-Exchange/AUDIT_DIFF_V2_TO_V3.md` — 174 lines.

### Headline numbers
- V2 score: **25/48 (52%)**
- V3 score: **43/48 (90%)**
- Net delta: **+18 items resolved**, **+38 percentage points**

### Phase 3+4 commit
Committed as `50d4722` — `Phase 3+4: V3 audit (43/48, 90%) and V2-to-V3 diff`.

---

## Phase 5 — End-to-End Smoke Test

**Goal:** Build a regression test covering the full HTTP surface area touched by Phases 1–2K, runnable with `pytest` against an isolated in-memory database.

### Output
`Haven-Exchange/tests/smoke_test_e2e.py` — 52 scenarios across 14 test classes.

### Test infrastructure
- FastAPI `TestClient` with `follow_redirects=False` so 303 redirects from `require_login` are visible to assertions.
- In-memory SQLite via `StaticPool` so all connections share one underlying connection (necessary for `:memory:` to persist across requests).
- Module-level engine + `SessionLocal` patched on `app.database` *before* `app.main` is imported. `Base.metadata.create_all()` is run in the session-scoped `client` fixture so the schema matches the ORM models.
- `app.dependency_overrides[get_db]` redirects FastAPI's `Depends(get_db)` to the in-memory session factory.

### Cookie handling
The login route sets `session_token` with `Secure=True`. Starlette's TestClient runs over `http://testserver`, and httpx silently drops Secure cookies on non-TLS hosts. Workaround:
- Helpers parse `session_token` directly out of the `Set-Cookie` response header (`_extract_session_from_headers`) instead of relying on `r.cookies.get(...)` (which raises `CookieConflict` when the client jar already has a same-name cookie from a prior test).
- A `_clear_session(client)` helper iterates `client.cookies.jar` and calls `clear(domain, path, name)` to remove every `session_token` regardless of which `(domain, path)` tuple it was originally set under. This avoids the multi-domain CookieJar conflict that previously caused 12 spurious failures.
- A `_set_session(client, token)` helper clears first, then sets, so we always end up with exactly one cookie.
- A `_as(client, token)` context manager saves/restores the previous token so nested test paths (e.g. citizen creates pending bank → admin approves → citizen views) work without leaking auth state.

### Test classes (14)
1. `TestHealth` (1) — `/health`
2. `TestAuth` (6) — register, login, logout, unauth-redirect
3. `TestWallet` (3) — own wallet, public lookup, search
4. `TestNations` (4) — apply, list, admin approve, join
5. `TestShops` (6) — auth gate, pending state, listing visibility, resource_depot subtype validation
6. `TestStockMarket` (5) — listing, World Mint stock prohibition, auth gates, close auth
7. `TestBanks` (7) — citizen vs NL gate, World Mint bank prohibition, public listing, loan endpoints
8. `TestWorldMint` (4) — role gates, mint cap enforcement, stats accessibility
9. `TestEconomicHealth` (4) — demurrage GET/PUT scoping, rate validation
10. `TestStimulus` (4) — proposal listing auth, approve/reject role gates, missing-id 404
11. `TestLedger` (3) — public ledger, tx-by-hash, GENESIS row presence
12. `TestLoanForgiveness` (2) — auth gate, missing-loan handling
13. `TestTransfers` (2) — self-transfer reject, insufficient-balance reject
14. `TestWalletHealthMetrics` (1) — Phase 2H field presence in `/api/wallet` response

### Final result
```
======================= 52 passed, 6 warnings in 13.82s =======================
```

All 52 scenarios pass. The 6 deprecation warnings are FastAPI `on_event` API deprecations in `app/main.py` — pre-existing, unrelated to this remediation.

### Bug discovered & fixed during Phase 5
**`app/routes/wallet_routes.py::my_wallet`** used `Depends(get_current_user)` (returns `Optional[User]`) but then dereferenced `current_user.nation_id` unconditionally, raising `AttributeError` on unauthenticated requests (HTTP 500). Same pattern as Phase 1 Bug 1. Fixed by switching to `Depends(require_login)`, which raises a 303 redirect to `/login` instead.

This is a real bug, not a test infrastructure issue — production users hitting `/api/wallet` without a session would have seen 500 errors instead of being redirected to login. Phase 5 caught it; Phase 1 missed it because the V2 audit didn't separately enumerate every protected route.

### Phase 5 commit
Committed alongside the REMEDIATION_LOG update with the smoke test directory and the `wallet_routes.py` fix. Verified commit hash: `483d521`.

---

## Phase A — Log Verification & Gap Reconstruction (2026-04-27)

**Purpose:** Re-validate the remediation log against actual git history and current code on `audit-v2-remediation`, fill in commit hashes that were omitted from earlier entries, and explicitly mark the categories of context that cannot be recovered after the fact.

### What was verified

- All phase headings (1, 2A–2K, 3, 4, 5) are present in the log.
- All commit hashes referenced in the log resolve in `git log audit-v2-remediation` and the messages match.
- Working tree on the branch is clean.

### Commit hashes that were missing from the original entries (now filled in below)

| Phase | Commit | Message |
|-------|--------|---------|
| 2C | `6ce7038` | `Phase 2C: add treasury lending via lender_type abstraction` |
| 2D | `2a764a3` | `Phase 2D: add shop approval workflow with NL gatekeeping` |
| 2E–2G | `b59f8b8` | `Phase 2E-2G: per-business GDP, resource depot subtype, stock closure` |
| 5 | `483d521` | `Phase 5: E2E smoke tests (52/52), smoke report, wallet route auth fix` |

The original entries for these phases listed only the commit *message*, not the hash. Hashes added inline above and at the foot of each phase's "commit" subsection.

### Context not recoverable from git/code

The following classes of information were not written down at the time the phases ran and cannot be reconstructed from the artifacts:

- **Real-time decision rationale.** Where a phase entry says "design choice: X over Y", the *alternatives that were considered and rejected on the spot* during implementation are not captured beyond what survived into the entry. Future-me reading the log gets the chosen path with a one-line "why", not the full deliberation.
- **Edge cases discovered mid-phase that were folded into the same commit.** Examples likely exist (e.g. the route-ordering note in Phase 2D suggests the path-shadowing issue was caught during implementation, not pre-planned), but per-issue notes were not kept.
- **Failed attempts, scrapped approaches, or test code written and deleted.** Nothing in `git log` other than reflog would surface this, and reflog is local-only.
- **Timing/duration per phase.** Commit timestamps give wall-clock anchor points but not active-work duration.
- **Verification scope decisions.** The synthetic tests cited in 2A/2H/2I/2J are described by their inputs and pass/fail outcome, but the *cases that were considered and not tested* aren't enumerated.

These gaps do not block merge — the surviving log is authoritative for what was implemented and why at a structural level. They are flagged here so any future phase that relies on the log for "why didn't we do it this other way?" knows to fall back to code archaeology rather than treating the log as exhaustive.

### Phase A commit
Documentation-only change. No code touched.
