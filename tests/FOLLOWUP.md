# Haven Smoke + Verification Test Suite — v2 Follow-up Items

**Status:** Items deferred from v1 ([PROPOSAL.md](PROPOSAL.md)) for explicit reasons. Listed here so we don't lose them.
**Sibling:** [INVESTIGATION_REPORT.md](INVESTIGATION_REPORT.md) (Phase 1), [PROPOSAL.md](PROPOSAL.md) (Phase 2)
**Date:** 2026-04-29

This is a backlog. Each item has a **why-deferred** note so future-Parker can decide whether it's still relevant.

---

## A. Tests deferred from v1's P1 list

These were in the Phase-1 proposed test list but cut for the 12-14-test budget (Q8). All would be valuable; none are urgent.

| Test | Why deferred | Estimated effort |
|---|---|---|
| `GET /` returns 200 with `<meta property="og:image">` containing `https://` | Smoke-on-OG-cards is nice-to-have. The og:image protocol fix already shipped (commit `0a75cee`); regression risk is low. | 30 min |
| `GET /voyager/{username}` returns 200 with rendered HTML | SSR coverage. The poster smoke tests cover the underlying API; the HTML wrapper is unlikely to break independently. | 30 min |
| `/api/discoveries POST` enqueues to `pending_discoveries` (not direct insert) | This was in v1.48.3's release notes as a fix. The verify tier could regression-test it. Cut because /api/extraction round-trip tests already prove the pending-queue insert mechanism works. | 1 hr |
| `/api/posters/voyager_og/{slug}.png` cache key is correctly normalized | Unit test on `normalize_username_for_dedup`. Pure function, easy to test. Cut because it's tested transitively by the /fingerprint URL test. | 20 min |
| `/api/extraction` correctly resolves `source` for `Keeper 2.0` API key → `keeper_bot` | Source resolution covered indirectly by the basic extraction test. Cut for budget. | 30 min |
| Wire existing 52 Haven-Exchange smoke scenarios into the cron pipeline | They already exist and pass. Cut because adding a cron entry is trivial later. | 30 min |
| Playwright `wizard-*.spec.ts` re-validation against `/haven-ui/wizard` (current SPA route, not legacy `/#/wizard`) | Frontend tests; separate concern from the smoke suite. Phase 1 noted the route may have changed. | 1 hr investigation + fix |

**Combined v2 tests budget:** add ~5-7 of the above to push the suite from 14 to ~20 tests.

---

## B. Repo-hygiene follow-ups

| Item | Why deferred | Trigger |
|---|---|---|
| **Final deletion of files in `tests/archive/`** | Phase 3 moves the 5 stale files there instead of deleting outright (safer two-step). | Delete after v1 has run successfully for 30 days (≈ 2026-06-01). |
| **Delete `Haven-UI/raspberry/`** (the legacy systemd-era deploy guide) | Documented in INVESTIGATION_REPORT §11 as out-of-date. Not part of v1 because it's not a test artifact. | Cleanup PR after v1. |
| **Delete `Haven-UI/scripts/deploy_to_pi.ps1` / `apply_update_remote.sh` / `create_update_archive.ps1`** | All pre-Docker era. Production is Docker now. | Same cleanup PR. |
| **Audit `Haven-UI/scripts/` for other stale `test_*.py` and `migrate_*.py` files** | Phase 1 found `test_approval.py`, `test_signed_hex_glyphs.py`, etc. — likely fine but worth a once-over. | Q3 2026. |

---

## C. Coverage gaps to consider for v2

These are areas v1 doesn't cover. Each entry weighs **value** vs. **effort**.

### C.1 WarRoom subsystem (67 routes)

- **Value:** Medium. WarRoom is feature-rich but has a smaller user base. Outages there don't impact the typical Haven workflow.
- **Effort:** Large. Lots of state (conflicts, claims, peace proposals); requires multi-step test scenarios.
- **Recommendation:** wait until WarRoom usage grows or a regression actually fires.

### C.2 CSV import flow

- **Value:** Medium-high — partner onboarding depends on it.
- **Effort:** Small. Three endpoints (`/api/csv_preview`, `/api/import_csv`, `/api/photos`); fixture-driven test would be ~50 lines.
- **Recommendation:** v2 candidate.

### C.3 Approval workflow round-trip

- **Value:** High — central to the whole product.
- **Effort:** Medium. Needs admin session fixture, then submit → approve → assert in `systems` table.
- **Recommendation:** strong v2 candidate. v1's extraction round-trip touches part of this; v2 should cover the manual web-wizard path too.

### C.4 Profile claim / fuzzy-match flow

- **Value:** Medium — recently introduced (v1.48.0); regression risk exists.
- **Effort:** Medium. Requires seeded user_profiles data.
- **Recommendation:** v2 candidate.

### C.5 Glyph encoding / decoding round-trip

- **Value:** High — the entire coordinate system depends on it. A bug here corrupts every submission.
- **Effort:** Small. Pure-function tests; the v1.50.6 work fixed a glyph bug, demonstrating the risk is real.
- **Recommendation:** strong v2 candidate. Could even be a P0 in v2.

### C.6 Extractor `nms_namegen` integration

- **Value:** Medium — `tests/test_nms_namegen.py` already covers imports.
- **Effort:** Small to medium. Could compare against `assets/nms_namegen/test_vectors.json` if such a thing existed (it doesn't — would need to generate from known-good game data).
- **Recommendation:** low priority.

### C.7 Public API rate limiting / abuse paths

- **Value:** Low (no current abuse).
- **Effort:** Medium.
- **Recommendation:** defer indefinitely unless an incident occurs.

### C.8 Galaxy summary correctness

- **Value:** Medium — `/api/galaxies/summary` powers the home page; the v1.51.1 bug (named vs populated counts asymmetry) suggests this query is bug-prone.
- **Effort:** Small.
- **Recommendation:** v2 candidate.

---

## D. Infrastructure / operational follow-ups

These aren't tests — they're ops items the test suite work surfaced.

### D.1 Off-Pi backup strategy

- **Status:** None exists. `POST /api/backup` copies to the same volume.
- **Risk:** Pi disk failure = total data loss for `~/haven-data` and `~/haven-photos`.
- **Recommended action:**
  - Daily `rsync` from `~/haven-data/` and `~/haven-photos/` to a remote (NAS, B2, S3 — cheap option).
  - Encrypted at rest.
  - 30-day retention.
- **Effort:** Small. ~30 lines of shell + cron.
- **Owner:** Parker.

### D.2 `tests/archive/` final purge

- After v1 runs stably for 30 days, the `tests/archive/` folder can be deleted entirely. Set a calendar reminder for ≈ 2026-06-01.

### D.3 Tighten `db_stats` ranges every 6 months

- Per Q9 / §10.5 of [PROPOSAL.md](PROPOSAL.md), the lower-bound assertions decay in usefulness as the DB grows.
- **Recommended action:** add a manual review item to recalibrate the floors. Set calendar reminder for ≈ 2026-10-29.
- Optional: `tests/maintenance/rebaseline.py` script that queries live `/api/db_stats` and prints suggested new floors. Out of scope for v1; trivial to add later.

### D.4 Document the `haven-net` Docker network

- Phase 1 §8 noted the production state may diverge from the compose files (Haven-UI doesn't auto-join `haven-net`).
- **Recommended action:** add a single line to `Haven-UI/docker-compose.yml` joining it to `haven-net`, OR document the manual `docker network connect` step in a top-level `DEPLOY.md`.
- **Effort:** 5 minutes.
- **Owner:** Parker (one-line config change).

### D.5 Top-level `docker-compose.yml`

- Currently each service has its own. A top-level compose that orchestrates all four (Haven, Keeper, Exchange, Viobot) would simplify deploy and let `docker compose up` start everything atomically.
- **Effort:** Medium — has to handle the network sharing.
- **Recommendation:** v2 candidate; not blocking.

### D.6 Public-facing `/api/health` endpoint

- Haven uses `/api/status` for healthcheck (returns `{status, version}`). Exchange uses `/health` (returns `{status, service}`). Inconsistency.
- **Recommended action:** add an `/api/health` alias to Haven that mirrors Exchange's shape. Backwards-compatible — `/api/status` keeps working.
- **Effort:** 10 minutes.
- **Recommendation:** trivial v2 candidate. Not high-value (smoke tests already work fine on `/api/status`), but reduces cognitive load.

---

## E. Test infrastructure improvements (v2+)

### E.1 GitHub Actions integration

- v1 runs only on the Pi (cron) and Win-dev (manual).
- v2 could add a GitHub Actions workflow that runs the verify tier on every PR (against in-memory DB — no live infra).
- **Effort:** Medium. Requires a Python venv setup step in the runner.
- **Recommendation:** v2 candidate, especially if collaboration scales beyond just Parker.

### E.2 Cross-service contract tests

- Verify that the extractor payload shape matches what `/api/extraction` accepts, mechanically.
- Today: relies on the JSON schema in `approvals.py:2425-2463` doc comment matching what the extractor at `haven_extractor.py:4266` actually sends.
- **Recommended action:** generate fixture from extractor source code at test time; assert it's a strict subset of the backend's accepted fields.
- **Effort:** Small.
- **Recommendation:** v2 candidate after the extractor stabilizes (currently churning at ~1 release per week).

### E.3 Performance budgets

- v1 has no runtime assertions. A 5-second `/api/systems` response would still pass.
- v2 could add `assert response_time_ms < 1500` for hot endpoints.
- **Effort:** Small.
- **Recommendation:** v2 candidate.

### E.4 Visual regression for posters

- Current poster tests assert `image/png` + size > 5 KB. Doesn't catch "rendered the wrong text" or "rendered a blank canvas".
- Could compare against a reference image with a tolerance.
- **Effort:** Medium-large (image diffing infra; storage of reference images).
- **Recommendation:** v3+ unless poster bugs become a recurring problem.

---

## F. Items explicitly NOT planned for v2 either

These came up during Phase 1/2 but Parker should know we considered and rejected them:

| Item | Rejected because |
|---|---|
| Loading test data into a separate Pi DB and running smoke against it | Production data is what users see; testing against fake data hides issues. v1's lower-bound assertions suffice. |
| Mocking the entire backend with WireMock | Misses the integration concerns (FastAPI routing, SQLite connection lifecycle) that are the actual failure surface. |
| Property-based testing (Hypothesis) | Premature. We don't yet have unit tests for the affected functions, let alone property-based ones. |
| Keeper integration tests via real Discord guild | Fragile, slow, requires a test guild. The mock-based pattern in `The_Keeper/tests/test_commands.py` already provides 95% of the value. |
| End-to-end browser tests of the SPA via Playwright (beyond the existing `wizard-*.spec.ts`) | Separate concern. Frontend tests are not the smoke suite's territory. |
| Mutation testing | Way too heavy for a 14-test suite. |

---

## G. Calendar of review dates

| Date | Action |
|---|---|
| 2026-05-29 (~30 days post-v1) | Confirm v1 has run cleanly. If yes, schedule deletion of `tests/archive/`. |
| 2026-06-29 (~60 days) | First scheduled v2 planning meeting (mental note). Pull from §A and §C. |
| 2026-10-29 (~6 months) | Rebaseline `/api/db_stats` lower-bound assertions per §D.3. |
| 2027-04-29 (~1 year) | Full re-audit of the suite. Are tests still relevant? Are new failure modes uncovered? |

---

**End of follow-up backlog.** This list is the contract for what `v1 is intentionally not solving`. v2 picks from here when Parker's ready.
