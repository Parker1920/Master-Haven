# Travelers Exchange — Interest Cap Behavior

**Status:** Resolved. Parker chose **Interpretation 2 (running-balance cap)**;
implementation switched on 2026-04-27 (commit applied alongside Phase B).
This document is now historical reference for both interpretations.

---

## Background

The remediation dispatch's Locked Decisions doc states:

> Interest accrues normally until cap is reached. At cap: interest stops
> accruing. Loan stays open. Borrower can still pay it down.

That language is ambiguous. Two interpretations are consistent with the
sentence; they diverge once the borrower actually starts paying interest
down.

The implementation chose one (Interpretation 1, lifetime cap) without
flagging the ambiguity. Phase B documents both so the call can be made
with eyes open.

---

## The two interpretations

### Interpretation 1 — Lifetime cap (currently implemented)

The cap is a **lifetime ceiling** on what the lender can ever charge as
interest on this loan.

- Once `accrued_interest` ever reaches `cap_amount`, `interest_frozen`
  flips to `True`.
- The flag never flips back. The accrual job filters frozen loans out
  forever ([interest.py:127](Haven-Exchange/app/interest.py#L127)).
- Even if borrower payments draw `accrued_interest` back to 0, no new
  interest accrues. The borrower can pay down outstanding principal
  with no further interest cost.

**Plain-English summary:** "The bank can never charge more than 100% of
the principal in total interest. Once it has charged that, it's done."

### Interpretation 2 — Running-balance cap (alternative)

The cap is a **real-time ceiling** on outstanding interest.

- Interest stops accruing whenever `accrued_interest >= cap_amount`.
- If borrower payments draw `accrued_interest` below the cap, accrual
  resumes the next day at the normal daily rate.
- The flag (if kept at all) tracks "currently at cap", not "ever hit
  cap".

**Plain-English summary:** "The bank can never have more than 100% of
the principal sitting as outstanding interest at one time. The borrower
can pay down the bill and re-accrue."

---

## Worked example — 100 TC loan

Setup chosen so daily interest math is clean: `principal = 100 TC`,
APR set so `daily_interest = 1 TC` (e.g. ≈365% APR). `cap_amount = 100`
(= principal, per the 100% rule). Borrower pays 50 TC at day 100, then
pays nothing for another 100 days, then pays 50 TC at day 200, etc.

Day-by-day after the cap is first hit:

| Day | Event | Accrued (Interp 1) | Frozen? (Interp 1) | Accrued (Interp 2) | Total interest charged so far (Interp 1) | Total interest charged so far (Interp 2) |
|-----|-------|---|---|---|---|---|
| 0   | loan opens, principal = 100 | 0 | False | 0 | 0 | 0 |
| 50  | accrual continues | 50 | False | 50 | 50 | 50 |
| 100 | cap hit — accrual stops | **100** | **True** | **100** | 100 | 100 |
| 100 | borrower pays 50 toward interest | 50 | True | 50 | 100 | 100 |
| 101 | next accrual run | 50 (no add) | True | **51** (+1 added) | 100 | 101 |
| 150 | 50 days later | 50 | True | **100** (cap re-hit) | 100 | 150 |
| 150 | borrower pays 50 toward interest | 0 | True | 50 | 100 | 150 |
| 151 | next accrual run | 0 (no add) | True | **51** (+1 added) | 100 | 151 |
| 200 | 50 days later | 0 | True | **100** (cap re-hit again) | 100 | 200 |

After 200 days, **Interpretation 1** has charged the borrower a total of
**100 TC** in interest (= 100% of principal, exactly the cap).
**Interpretation 2** has charged **200 TC** (= 200% of principal) and
will keep charging another 100 TC for every full pay-down cycle the
borrower runs.

Over the loan's life, the divergence grows without bound under
Interpretation 2 if the borrower keeps the loan open and keeps paying
interest down. Under Interpretation 1 it caps at 100 TC and stops.

---

## Which is currently implemented

**Interpretation 2 (as of 2026-04-27).** Parker chose the running-balance cap.
The code-level changes documented in the next section have been applied
plus one additional fix surfaced during verification: when the cap is held
across multiple daily runs, ``last_accrual_at`` is now advanced on the
cap-hold path so post-paydown elapsed time does not retroactively bank up
into a single large accrual.

**Historical: prior to 2026-04-27 the code implemented Interpretation 1.**
The remediation log's Phase 2A entry committed to it explicitly. The
specifics of that prior implementation:

- [app/interest.py:59](Haven-Exchange/app/interest.py#L59) — early
  return on `loan.interest_frozen`.
- [app/interest.py:70-73](Haven-Exchange/app/interest.py#L70-L73) — when
  `accrued_interest >= cap_amount`, sets `interest_frozen = True` and
  returns 0.
- [app/interest.py:97-101](Haven-Exchange/app/interest.py#L97-L101) —
  when an add would overshoot the cap, fills only to the cap and sets
  `interest_frozen = True`.
- [app/interest.py:127](Haven-Exchange/app/interest.py#L127) — the
  daily job's `select` filters with `Loan.interest_frozen.is_(False)`,
  so frozen loans are never even considered for re-accrual.
- `pay_loan` in
  [app/routes/bank_routes.py:1037](Haven-Exchange/app/routes/bank_routes.py#L1037)
  reduces `accrued_interest` but **never touches** `interest_frozen`.
  Once True, it stays True for the loan's life.

The Phase 2A entry in `REMEDIATION_LOG_2026-04-26.md` (line 71) and the
module docstring of `interest.py` (lines 17–21) both state the lifetime
intent explicitly. So the decision was deliberate, not accidental — but
it was a coin-flip the implementer made without raising the ambiguity.

---

## What changes for Interpretation 2

If Parker wants the running-balance cap instead, the minimal code change
is in two places, plus an optional cleanup:

### Required change 1 — `app/interest.py`

**Drop the `interest_frozen` filter from the daily job** so frozen loans
are re-evaluated each run:

```python
# Before (line 127)
select(Loan).where(Loan.status == "active", Loan.interest_frozen.is_(False))

# After
select(Loan).where(Loan.status == "active")
```

**Drop the early return at the top of `_accrue_loan`** so a previously
frozen loan whose balance has been paid down can re-enter accrual:

```python
# Before (line 59-60)
if loan.interest_frozen:
    return 0

# After
# (delete the two lines)
```

The existing cap check at line 70 (`if loan.accrued_interest >=
loan.cap_amount`) already does the right thing for Interpretation 2 —
it short-circuits when the running balance is at the cap, which is
exactly the running-cap rule. Same for the headroom calc at line 98
(it caps the per-run add to whatever fits below `cap_amount`).

### Required change 2 — `app/routes/bank_routes.py::pay_loan`

After the line that reduces `accrued_interest`
([bank_routes.py:1037](Haven-Exchange/app/routes/bank_routes.py#L1037)),
flip `interest_frozen` back to False so the next daily run picks the
loan back up:

```python
loan.accrued_interest -= interest_portion
if loan.interest_frozen and loan.accrued_interest < loan.cap_amount:
    loan.interest_frozen = False
```

(Without this change, the daily-job filter change above is enough on
its own — but leaving the flag stale is misleading on read, and the
loan-detail responses surface `interest_frozen` to clients.)

### Optional cleanup — drop the flag entirely

Under Interpretation 2, `interest_frozen` becomes a redundant denormalisation
of `accrued_interest >= cap_amount`. It can be:

- Kept as a cache (set on accrual, reset on payment) — minimal-change
  approach above.
- Removed entirely and computed on read (`@property` on the model). This
  is cleaner but requires:
  - dropping the column from the model and adding a `DROP COLUMN`-style
    migration (SQLite needs a table rebuild; non-trivial),
  - updating the four `interest_frozen=False` initialisers in
    `bank_routes.py` (lines 448, 656),
  - updating the five response dicts that include the field
    (bank_routes.py:334, 471, 681, 741, 875).

Recommendation if switching: keep the flag, change its semantics to
"currently at cap", apply the two minimal changes above. Don't bother
with the column drop unless something else forces a schema rebuild.

### What does NOT need to change

- Loan creation paths — `cap_amount = principal`, `interest_frozen =
  False`, `accrued_interest = 0` are correct for both interpretations.
- The cap math itself (per-day rate, headroom calculation, integer
  flooring) — both interpretations want exactly the same per-run logic.
- Phase 5 smoke tests — they don't exercise the frozen-and-paid-down
  path, so neither interpretation breaks them.
- The 100% cap-amount value — both interpretations agree on `cap_amount
  = principal`. The disagreement is about what the cap *means*.

### Verification you'd want to add if switching

- Test: borrower hits cap, pays 50% of accrued, runs daily job once,
  asserts `accrued_interest` increased by exactly the daily rate.
- Test: borrower hits cap, pays 100% of accrued, runs daily job, asserts
  `interest_frozen == False` and accrual resumed.
- Test: borrower never pays — Interpretation 1 and 2 produce identical
  results, regression-protect that case.

---

## Recommendation

This is a policy call, not a technical one. Both implementations are
clean and supported by the existing schema.

**Pick Interpretation 1 (current) if** the framing is "100% interest
cap = consumer protection ceiling on what the lender can ever extract."
This matches usury-cap intuitions and prevents the running-pay-down
cycle from quietly turning the loan into a perpetual interest stream.

**Pick Interpretation 2 if** the framing is "100% interest cap = the
maximum *outstanding* interest the borrower can owe at any moment."
This rewards borrowers who actively service interest (it lets them keep
borrowing principal-equivalent value) and matches some real-world
revolving-credit conventions.

The Locked Decisions doc reads slightly more naturally as Interpretation
2 in isolation ("borrower can still pay it down" implies *something*
should happen as a result of paying). But the Phase 2A entry committed
to Interpretation 1 with explicit reasoning. No code change should be
made until Parker confirms which one the project wants.
