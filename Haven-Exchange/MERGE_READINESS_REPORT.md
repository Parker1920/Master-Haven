# Travelers Exchange — Merge-Readiness Report

**Branch:** `audit-v2-remediation`
**Tip:** `d258b85`
**Target:** `main`
**Date:** 2026-04-27
**Reporter:** Claude (Phase C of remediation finalization)

---

## Verdict: **READY TO MERGE** — with two non-blocking notes

Both notes are documentation, not implementation. The branch can ship as-is;
the notes are flagged so Parker decides whether to address them in this
merge or post-merge.

1. The V3 audit (`TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md`) contains one
   stale claim that no longer matches code, introduced by the Phase B
   follow-up (Interpretation 2 switch). Easy fix; details in §5.
2. Two pre-existing security issues (hardcoded `SECRET_KEY`,
   hardcoded `"changeme"` admin password) remain. Already flagged in
   the V3 audit; reproduced here so they're visible at merge time. See §8.

---

## 1. Working tree status — PASS

```
$ git status
On branch audit-v2-remediation
nothing to commit, working tree clean
```

No uncommitted changes. No untracked files needing attention.

(Note: the *main* worktree at `C:/Master-Haven` has unrelated dirty state
from NMS-Haven-Extractor work — that's an unrelated checkout, not part of
this merge.)

## 2. Commit history integrity — PASS

16 commits ahead of main, linear, descriptively named, aligned with the
phase structure:

```
d258b85  Switch interest cap to Interpretation 2 (running-balance cap)
99460d5  Phase B: document interest cap behavior interpretations
9905811  Phase A: complete remediation log entries 2D-2K, 3-5
483d521  Phase 5: E2E smoke tests (52/52), smoke report, wallet route auth fix
50d4722  Phase 3+4: V3 audit (43/48, 90%) and V2-to-V3 diff
b6e0f77  Phase 2K: World Mint authority corrections
3deb2b6  Phase 2J: auto-stimulus proposals on GDP drop (3 tiers)
fddba04  Phase 2I: idle wallet demurrage with DEMURRAGE_BURN tx type
c8050f6  Phase 2H: document wallet health metrics in remediation log
1148676  Phase 2H: wallet health metrics (tx counts, volume lifetime+30d)
b59f8b8  Phase 2E-2G: per-business GDP, resource depot subtype, stock closure
2a764a3  Phase 2D: add shop approval workflow with NL gatekeeping
6ce7038  Phase 2C: add treasury lending via lender_type abstraction
a12a4bd  Phase 2B: rework loan payment with interest-first allocation and 20/80 split
9657cb0  Phase 2A: implement loan interest accrual with 100% cap
342a526  Phase 1: fix transfer auth, nation stock API path, loan forgive ledger entry
```

No merge commits, no rebase artifacts, no fixup chains. History reads as
the work was done.

## 3. No merge conflicts with main — PASS

Used `git merge-tree --write-tree main audit-v2-remediation` (in-memory
merge dry run; doesn't touch any worktree). Exit 0, no conflict markers
in output. The main worktree has unrelated dirty state from NMS-Haven-Extractor
work, so a literal `git checkout main && git merge` would have polluted
that worktree — hence the in-memory check.

24 files would change on merge. No file in the changeset is touched on the
main branch since the audit-v2-remediation branch point, so no overlap.

## 4. Smoke test re-run — PASS

```
$ py -m pytest tests/smoke_test_e2e.py --tb=short
======================= 52 passed, 6 warnings in 13.50s =======================
```

All 52 scenarios pass. The 6 warnings are pre-existing FastAPI `on_event`
deprecation warnings in `app/main.py:332,338` — not caused by this branch.

Smoke tests were re-run a second time after the Interpretation 2 switch
(commit `d258b85`); also 52/52.

## 5. V3 audit freshness check — PARTIAL (1 stale claim found)

Spot-checked 5 IMPLEMENTED claims:

| # | Claim | Result |
|---|-------|--------|
| 1 | Phase 2K — `buy_stock` rejects `world_mint` role | ✓ verified at `app/routes/stock_routes.py:345` |
| 2 | Phase 2D — `Shop.status` workflow + `/approve` endpoint | ✓ verified at `app/routes/shop_routes.py:510-511` |
| 3 | Phase 2I — `DEMURRAGE_BURN` tx type | ✓ verified at `app/blockchain.py:32, 213-219`; `app/demurrage.py:108` |
| 4 | Phase 2H — User wallet-health columns | ✓ verified at `app/models.py:54-71` |
| 5 | Phase 2A — "interest_frozen flips permanently when cap is reached" | **❌ STALE** |

### The stale claim

The V3 audit's row at line 93 reads:

> 100% interest cap on loans (max debt = 2× principal) — **IMPLEMENTED** —
> Phase 2A. `Loan.cap_amount = principal` at creation. `accrued_interest`
> never exceeds `cap_amount`. **`interest_frozen` flips permanently when
> cap is reached.** Daily `accrue_daily_interest()` job in `interest.py`.

After the Phase B follow-up (commit `d258b85`), `interest_frozen` is no
longer permanent: it's flipped back to `False` by `pay_loan` when a payment
brings `accrued_interest` below `cap_amount`, and the daily job re-evaluates
all active loans regardless of frozen state.

**Recommended fix:** edit `TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md`
line 93 to replace "flips permanently when cap is reached" with "flips
back and forth based on running balance (running-balance cap, see
INTEREST_CAP_BEHAVIOR.md)".

The category score (8/8 Banks & Lending, 43/48 overall) remains correct —
the cap rule is still enforced, just differently than originally documented.
Not a regression; not a blocker; just stale audit prose.

## 6. Docker configuration check — PASS

```
$ git diff main...audit-v2-remediation -- Dockerfile docker-compose.yml
(empty)
```

Neither `Dockerfile` nor `docker-compose.yml` has been modified on this
branch. Production deployment surface is unchanged. The Pi's bind-mounted
data directory convention (verified at `docker-compose.yml`) is unaffected.

## 7. Database migration readiness — PASS

`app/main.py::_run_schema_migrations` (lines 80-131) wraps every
schema change in idempotent `ALTER TABLE ... ADD COLUMN` statements. SQLite
will return "duplicate column" for already-applied migrations, and the
migration runner catches that error and continues. Verified all categories:

| Table | Migration columns added | Idempotent? |
|-------|------------------------|-------------|
| `loans` | accrued_interest, cap_amount, interest_frozen, last_accrual_at, interest_burn_rate_snapshot, total_interest_paid, total_burned_during_payments, final_close_burn, lender_type, lender_wallet_address, treasury_nation_id | ✓ |
| `loan_payments` | interest_portion, principal_portion, is_final_payment | ✓ |
| `shops` | status, approved_by, approved_at, rejected_reason, gdp_contribution_30d, gdp_last_calculated, shop_type, mining_setup | ✓ |
| `stocks` | closed_at, closure_reason | ✓ |
| `users` | transaction_count_lifetime, transaction_count_30d, volume_lifetime, volume_30d, wallet_health_last_calculated | ✓ |
| `nations` | demurrage_enabled, demurrage_rate_bps, mint_cap | ✓ |
| `global_settings` | interest_burn_rate_bps | ✓ |
| `stimulus_proposals` (new table) | created via `Base.metadata.create_all()` | ✓ (no-op if exists) |

Backfills present and correct:
- `UPDATE loans SET cap_amount = principal WHERE cap_amount = 0 AND principal > 0` (Phase 2A)
- `UPDATE loans SET lender_type = 'bank' ...` (Phase 2C)
- `UPDATE loans SET lender_wallet_address = (SELECT wallet_address FROM banks ...)` (Phase 2C)
- `UPDATE shops SET status = 'approved' WHERE status IS NULL` (Phase 2D grandfathering)

No manual DB intervention required. A production DB on the Pi with pre-2A
data will migrate forward cleanly on first server start after the merge.

## 8. Security debt inventory — INFORMATIONAL ONLY

Two pre-existing issues remain. Neither was in scope for the V2
remediation, both are flagged in the V3 audit (lines 211-213). Reproduced
here so they're visible at merge time:

### 8a. Hardcoded `SECRET_KEY`

`app/config.py:13`:
```python
SECRET_KEY: str = "travelers-exchange-secret-change-me"
```

Used to sign session cookies. With this hardcoded, any attacker with
read access to the repo can forge sessions for any user including
`world_mint`. In a closed self-hosted deployment with no public source
exposure, the practical risk is reduced but not zero.

**Recommended fix (not in this merge):** read from `os.environ` with a
fallback that aborts startup if not set in production:
```python
SECRET_KEY: str = os.environ.get("TRAVELERS_SECRET_KEY") or _abort_if_prod()
```

### 8b. Hardcoded admin password

`app/main.py:229`:
```python
hashed_pw = bcrypt.hashpw("changeme".encode(), bcrypt.gensalt()).decode()
```

Seeds the `admin` user with password `"changeme"` on first boot. Anyone
who reads the repo or guesses the obvious value can log in as
`world_mint` until the password is rotated.

**Recommended fix (not in this merge):** seed only when an
`ADMIN_INITIAL_PASSWORD` env var is set; otherwise leave admin
unprovisioned and require explicit `flask shell` or equivalent setup step.

### Block production deploy?

That's Parker's call. Both issues are **pre-existing**, not introduced by
this remediation. Two reasonable positions:

- **Ship and harden post-merge.** Closed community, internal Pi, no public
  source. The remediation work is the headline value; gating it on auth
  hardening delays the loan/business/stock fixes that are the user-visible
  payoff. File a follow-up ticket for the auth hardening.
- **Block on auth hardening first.** Both fixes are <50 lines of code each
  and roughly an hour of work. If the deployment will be exposed
  beyond the closed community in the foreseeable future, fix now rather
  than relying on remembering later.

Neither position blocks the *merge to main* itself — these are
production-deploy concerns that exist whether the branch lands or not.

---

## Final summary

| Check | Status |
|-------|--------|
| 1. Working tree clean | ✅ PASS |
| 2. Commit history integrity | ✅ PASS |
| 3. No merge conflicts | ✅ PASS |
| 4. Smoke tests (52/52) | ✅ PASS |
| 5. V3 audit freshness | ⚠️ 1 stale claim (line 93, doc-only fix) |
| 6. Docker config unchanged | ✅ PASS |
| 7. DB migrations idempotent | ✅ PASS |
| 8. Security debt | ℹ️ 2 pre-existing items, deploy-time decision |

**Verdict: READY TO MERGE.** The audit-v2-remediation branch is structurally
clean, tests pass, migrations are forward-only and safe, and there are no
conflicts with main. The single stale audit claim is a 5-second prose edit
in a documentation file. The two security debt items predate this work and
are deploy-time concerns, not merge-time blockers.
