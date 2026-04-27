# Travelers Exchange — Merge & Deploy Prep Log

**Date:** 2026-04-28
**Source dispatch:** Merge-and-deploy-prep follow-up to the Phase A/B/C
remediation finalization.
**Branch flow:** `audit-v2-remediation` → `main` (no push, no Pi).

---

## Phase 1 — Stale Audit Prose Fix

**Goal:** The V3 audit's row at line 93 still described `interest_frozen`
as flipping "permanently when cap is reached" — superseded by the
Interpretation 2 switch in commit `d258b85`. Phase C flagged this as
the only stale claim found in the V3 audit. Phase 1 fixes the prose.

### Change

`Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md` line 93 —
replaced the "flips permanently when cap is reached" sentence with
language reflecting Interpretation 2:

- Notes the Phase B follow-up commit (`d258b85`).
- Describes the flag as toggling based on running balance: flips True
  when cap is reached, False when payments draw `accrued_interest`
  below cap.
- Cross-references `INTEREST_CAP_BEHAVIOR.md` for the full doc.

No score changes. No category changes. No other lines touched.

### Phase 1 commit
Committed as `b3e995b` — `fix: V3 audit line 93 stale interest cap prose`.

---

## Phase 2 — Merge to Main

**Goal:** Merge `audit-v2-remediation` into `main` with `--no-ff` so the
remediation work remains identifiable as a unit in history. Preserve
the unrelated NMS-Haven-Extractor dirty state in the main worktree.

### Pre-merge state

- Active branch: `main`
- Tip of `main`: `79f3bcd upgrades people upgrades`
- Tip of `audit-v2-remediation`: `b3e995b fix: V3 audit line 93 stale interest cap prose`
- Main worktree dirty (NMS-Haven-Extractor work, unrelated):
  - Modified: `CLAUDE.md`, `NMS-Haven-Extractor/dist/HavenExtractor/FIRST_TIME_SETUP.bat`, `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py`, `NMS-Haven-Extractor/pyproject.toml`
  - Deleted: `HavenExtractor-mod-v1.9.2.zip`
  - Untracked: `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT.md`, `HavenExtractor-mod-v1.9.3.zip`, `audit/`

### Blocker found and resolved

First merge attempt was refused by git:

```
error: The following untracked working tree files would be overwritten by merge:
	Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V2_2026-04-26.md
```

The untracked file in the main worktree was an older draft of the V2
audit that differed from the branch version by exactly one line (the
branch version added a closing sentence to the architectural finding
on `verify_chain()`). Parker authorised deletion of the redundant
untracked copy — branch version is a strict superset, nothing lost.

After `rm Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V2_2026-04-26.md`,
the merge proceeded cleanly.

### Merge command

```
git merge --no-ff audit-v2-remediation \
  -m "Merge audit-v2-remediation: full V2 remediation, V3 audit, smoke test, interest cap fix"
```

### Post-merge state

- Tip of `main`: `98b5e9d Merge audit-v2-remediation: full V2 remediation, V3 audit, smoke test, interest cap fix`
- 19 commits ahead of `origin/main`
- 17 phase commits + the prose fix + the merge commit all visible in `git log --oneline -20`
- Working tree dirty state from NMS-Haven-Extractor: **intact and untouched** (same five modified/deleted entries, same three untracked entries minus the deleted V2 audit)
- `audit-v2-remediation` branch: **retained** (not deleted)
- Not pushed to remote.

### Phase 2 commit
The merge commit `98b5e9d` is itself Phase 2's commit. The Phase 2 log
entry above is uncommitted in the working tree at this point and will
ride along on the Phase 3 commit.

---

## Phase 3 — Post-Merge Verification

**Verdict: MERGE VERIFIED**

All five checks pass.

### 1. Smoke test re-run on main

```
$ py -m pytest Haven-Exchange/tests/smoke_test_e2e.py --tb=short
======================= 52 passed, 6 warnings in 14.83s =======================
```

52/52 pass on the merged `main` tree. 6 warnings are pre-existing FastAPI
`on_event` deprecations.

### 2. Expected files present on main

All 11 expected files present:

- ✅ `Haven-Exchange/REMEDIATION_LOG_2026-04-26.md`
- ✅ `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md`
- ✅ `Haven-Exchange/AUDIT_DIFF_V2_TO_V3.md`
- ✅ `Haven-Exchange/SMOKE_TEST_REPORT.md`
- ✅ `Haven-Exchange/INTEREST_CAP_BEHAVIOR.md`
- ✅ `Haven-Exchange/MERGE_READINESS_REPORT.md`
- ✅ `Haven-Exchange/tests/smoke_test_e2e.py`
- ✅ `Haven-Exchange/app/interest.py`
- ✅ `Haven-Exchange/app/demurrage.py`
- ✅ `Haven-Exchange/app/stimulus.py`
- ✅ `Haven-Exchange/app/wallet_health.py`

### 3. Code spot-checks (5 of 5 pass)

| # | Claim | Verified at |
|---|-------|-------------|
| 1 | Phase 2K — `buy_stock` WM guard | `app/routes/stock_routes.py:345` |
| 2 | Phase 2D — Shop status workflow + `/approve` route | `app/routes/shop_routes.py:508-511` |
| 3 | Phase 2I — `DEMURRAGE_BURN` tx type | `app/blockchain.py:32, 213, 219` |
| 4 | Phase 2H — User wallet-health columns | `app/models.py:54, 59, 68, 71` |
| 5 | Phase 2A — interest accrual engine | `app/interest.py:48 (_accrue_loan), :124 (accrue_daily_interest)` |

### 4. Stale audit prose fix verified

Line 93 of `TRAVELERS_EXCHANGE_AUDIT_V3_2026-04-26.md` on main now reads:

> 100% interest cap on loans (max debt = 2× principal) — **IMPLEMENTED** —
> Phase 2A (cap behavior switched to Interpretation 2 in commit `d258b85`).
> `Loan.cap_amount = principal` at creation. `accrued_interest` never
> exceeds `cap_amount`. `interest_frozen` toggles based on running
> balance — flips True when cap is reached, False when payments draw
> `accrued_interest` below cap. See `INTEREST_CAP_BEHAVIOR.md`. Daily
> `accrue_daily_interest()` job in `interest.py`.

No "flips permanently" prose remains. The Phase 1 fix is correctly on main.

### 5. NMS-Haven-Extractor dirty state intact

Pre-merge dirty list (5 changed entries + 3 untracked) is preserved on
main, modulo the `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT_V2_2026-04-26.md`
untracked file deleted in Phase 2 (the redundant copy):

- ✅ Modified: `CLAUDE.md`
- ✅ Modified: `NMS-Haven-Extractor/dist/HavenExtractor/FIRST_TIME_SETUP.bat`
- ✅ Modified: `NMS-Haven-Extractor/dist/HavenExtractor/mod/haven_extractor.py`
- ✅ Modified: `NMS-Haven-Extractor/pyproject.toml`
- ✅ Deleted: `HavenExtractor-mod-v1.9.2.zip`
- ✅ Untracked: `Haven-Exchange/TRAVELERS_EXCHANGE_AUDIT.md`
- ✅ Untracked: `HavenExtractor-mod-v1.9.3.zip`
- ✅ Untracked: `audit/`

(Plus the Phase 2/3 log appendage in `Haven-Exchange/MERGE_DEPLOY_PREP_LOG_2026-04-28.md` itself, which is the intended uncommitted change for this phase's commit.)

Nothing belonging to the Extractor work was modified, removed, or
otherwise touched by the merge.

### Phase 3 commit
This commit folds in the Phase 2 and Phase 3 log appendages to
`MERGE_DEPLOY_PREP_LOG_2026-04-28.md` (per dispatch: Phase 2 had no
separate commit since the merge was its commit). Commit message:
`Phase 3: post-merge verification log entries`.
