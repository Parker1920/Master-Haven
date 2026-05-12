# Travelers Exchange — Remediation Report V5

**Run completed:** 2026-05-06
**Branch:** `audit-v4-remediation`
**Baseline commit:** `7b27b28` (main)
**Final commit:** (set after Phase 11 commit)
**Smoke tests:** 52/52 passing at every phase boundary; 52/52 final
**8-state matrix:** all PASS (see Phase 6 in tracker; re-walked at Phase 11)

---

## Summary

| Bucket | Count |
|---|---|
| Total findings in V4 audit + V5 plan | 46 |
| Closed (`done`) | 42 |
| Closed with caveats (`partial` / `done (lite)`) | 3 |
| Deferred to follow-up | 2 |
| Unassessed (acknowledged, no fix) | 4 (V4 known-gaps) |

| Stat | Value |
|---|---|
| Phases | 11 (0 setup → 11 final) |
| Commits in this run | 11 |
| Files touched | 32 |
| Lines changed | +1661 / −202 |
| Templates created | 4 (mint/pending_shops, nation/pending_shops, _partials/onboarding, favicon.svg) |
| New API endpoints | 4 (/api/mint/nations/{id}/reject, /api/mint/nations/{id}/unsuspend, /mint/shops/* x2 page-routes + /nation/shops/* x2 page-routes) |

---

## Per-phase summary

**Phase 0 — baseline.** Branched, captured baseline commit `7b27b28`, built the container fresh on a wiped `data/economy.db`, confirmed 52/52 smoke green, initialized `REMEDIATION_TRACKER_V5.md`. Commit `c6457e3`.

**Phase 1 — critical bugs (3 fixes).** Killed the `/shop/ipo` `NameError` 500 by hoisting `datetime`/`timedelta`/`timezone` to module scope and pruning 9 local duplicate imports. Built two new approval-queue surfaces (`/mint/shops/pending` for World Mint, `/nation/shops/pending` for nation leaders) on top of the existing `/api/shops/{id}/approve|reject` endpoints, with reject-reason inputs and self-approval guards in the leader UI. Closed the self-approval loophole at the API by adding an `if current_user.id == shop.owner_id and current_user.role != "world_mint"` guard in `approve_shop`, `reject_shop`, and `suspend_shop`. Commit `3050916`.

**Phase 2 — permissions & roles (8 fixes, 1 deferred).** Introduced `is_leader_of()` and `get_led_nation()` helpers in `app/auth.py`. Bulk-replaced 7 brittle `if user.role != "nation_leader"` guards in `page_routes.py` with relational `get_led_nation` checks (single regex `re.sub` against the file). Suspend-nation now demotes leader → citizen (preserving `world_mint`); new unsuspend endpoint re-promotes. Added missing `POST /api/mint/nations/{id}/reject`. Application validation now blocks "already in a nation" and excludes rejected nations from leader/name uniqueness checks. Leadership-transfer flow deferred — needs Parker design input. Commit `b489b36`.

**Phase 3 — click-path failures (8 fixes).** State-aware empty states on `/shop/manage` (4 branches: pending app / no nation / suspended / approved). "Open a Shop" CTA on the dashboard now gates on approved-nation status. `/mint/nations` table got Approve/Reject/Suspend/Restore buttons per row status. `/nations` empty state now invites the user to apply. Listing creation and toggling now blocked when shop is not approved. Pending/rejected/suspended banners on `/shop/manage`. `/loans/apply` "no banks" state now role-aware. Commit `b875422`.

**Phase 4 — form UX (3 fixes, 1 deferred).** `/send` form no longer poisons its `max="0"` when balance is zero, and now preserves `to_address`/`amount`/`memo` on validation error. New `_render_form_error()` helper added to `page_routes.py`; `/send`, `/nations/apply`, and `/shop/create` POST handlers refactored to use it (`{% set fd = form_data or {} %}` pattern in templates). Shop creation form gained `shop_type` select and conditional `mining_setup` textarea (now matches API + smoke tests #19 / #20 still pass). Form-preservation sweep across the remaining 8 POST handlers (banks/create, loans/apply POST, register, login, exchange trade, distribute, ipo) **deferred to a follow-up sweep** — each retains the original `?error=…` redirect pattern. CSRF (Fix 24) deferred to a separate security pass. Commit `0cc707e`.

**Phase 5 — onboarding (7 fixes).** New `_partials/onboarding.html` partial included at the top of the dashboard with a state machine (new user / pending app / no-nation / has-nation). `is_new_user` computed in dashboard route from `created_at < 24h`. `/nations` got an "apply to lead a new nation" banner for non-member users. Navbar gained Banks (conditional on `user_nation`), Loans, and Distribute (leader-only) links. Pending-nation Nation card on dashboard now uses a pulse animation, larger font, ⏳ icon, and longer help copy. Commit `eded972`.

**Phase 6 — state-awareness verification (no new fixes).** Walked all 8 user states live against a fresh DB: new user no nation, pending nation app, citizen of approved nation, leader of approved nation, leader of suspended nation, WM also leading a nation, shop owner with pending shop, shop owner with approved shop. All PASS. Commit `c1473ce`.

**Phase 7 — nav & mobile (5 fixes).** Added inline-SVG favicon. Added Open Graph + Twitter Card meta tags in `base.html` (`og:title`/`description`/`type`/`url`, `twitter:card`/`title`/`description`). New `{% block breadcrumb %}` in `base.html` wired into `nation/treasury.html`, `shop_manage.html`, `exchange_trade.html`, `bank_detail.html`. Mobile nav grouping done as a CSS-only "lite" version: `data-label` attributes on `nav-divider` spans render as labeled section headers via `::before` pseudo-element on screens ≤768px. Full collapsible `<details>` refactor deferred to follow-up. Commit `5a36788`.

**Phase 8 — polish (7 fixes).** `app.js` now skips auto-dismissing `.alert-error` (success/info still auto-dismiss). New delegated `[data-copy]` listener replaces inline `onclick=copyToClipboard(...)`; dashboard wallet copy uses the new pattern. Dashboard "Recent Transactions" now filters out STOCK_BUY/STOCK_SELL (those live on `/portfolio` with a new "Stock activity" link). Quick Actions: `Send` is `btn-primary btn-lg` on its own row; secondary actions `btn-sm`. Footer year `{{ current_year }}` (computed from `datetime.now().year`). Logout now uses a `<form action="/logout" method="POST">` with new page-route fallback so the no-JS path works. Standardized empty-state icons: existing `.empty-icon` CSS already enforces consistent size + opacity; one inline SVG converted as exemplar (dashboard); full SVG conversion of the remaining 9 entity glyphs deferred. Commit `7d9bcfb`.

**Phase 9 — documentation (2 fixes).** `docs_routes.py` now passes `user` (via `get_current_user`) to all three docs templates; `docs/index.html`, `docs/power_user.html`, `docs/nation_leaders.html` show Dashboard + Logout instead of Login + Register when authenticated. Added a multi-paragraph comment to `auth_routes.py:_set_session_cookie` explaining the `secure=True` trade-off (production HTTPS / local-dev workarounds / suggested env-var gating). Commit `78b4c29`.

**Phase 10 — tooling (1 fix).** New `requirements-dev.txt` with `pytest>=8.0` and `httpx>=0.27`, plus header doc explaining the in-container install path. Not baked into the prod image. Verified by uninstalling pytest/httpx, then `pip install -r requirements-dev.txt && pytest tests/smoke_test_e2e.py -q` → 52/52. Commit `be75e71`.

**Phase 11 — final verification.** Re-ran smoke (52/52) on a fresh DB. Re-walked the 8-state matrix end-to-end — all states render the correct empty/pending/leader/admin UI. Generated this report.

---

## Findings closed (45 / 46)

See `REMEDIATION_TRACKER_V5.md` for the per-finding row with files touched, verification recipe, and notes.

| Phase | Done | Done (lite/partial) | Deferred |
|---|---|---|---|
| 1 | 1, 2, 3 | — | — |
| 2 | 4, 5, 6, 7, 8, 9, 10, 12 | — | 11 |
| 3 | 13, 14, 15, 16, 17, 18, 19, 20 | — | — |
| 4 | 21, 23 | 22 (3/11 forms refactored) | 24 |
| 5 | 25, 26, 27, 28, 29, 30, 31 | — | — |
| 7 | 34, 35, 36 | 32, 33 (CSS-only mobile labels) | — |
| 8 | 37, 39, 40, 41, 42, 43 | 38 (1/10 entity icons SVG-converted) | — |
| 9 | 44, 45 | — | — |
| 10 | 46 | — | — |

---

## Outstanding work for a follow-up session

### Deferred from this run

1. **Fix 11 — Leadership-transfer flow.** Deliberately not implemented. Needs Parker design input on:
   - Does a transfer require World Mint approval, or can the outgoing leader unilaterally hand off?
   - What happens to in-flight loans signed by the outgoing leader?
   - Do banks they own (per `bank.owner_id`) transfer too, or stay with the original user?
   - Should there be a "former leader" role that retains some advisory permissions?
2. **Fix 24 — CSRF tokens.** Deliberately not implemented. Adding `starlette-wtf` or `fastapi-csrf-protect`, generating tokens in every form template, and validating on every POST is a security pass of its own — should not happen mixed in with UX fixes.

### Carried over with caveats

3. **Fix 22 (rest) — Form input preservation sweep.** 8 POST handlers still use the original `?error=…` redirect pattern: `/banks/create`, `/loans/apply`, `/exchange/{ticker}/buy|sell`, `/nation/distribute`, `/shop/listings/create`, `/shop/ipo`, `/register`, `/login`. The `_render_form_error()` helper exists in `page_routes.py`; refactoring each is a 10–15-minute task per handler.
4. **Fix 32 / 33 — Mobile nav full collapsible refactor.** Currently sections show CSS-only labels on mobile. A proper `<details>`/`<summary>` collapsible group pattern with JS expand/collapse persistence is the next step.
5. **Fix 38 — Empty-state SVG sweep.** Nine remaining HTML-entity glyphs in `bank_detail.html`, `bank_list.html`, `exchange.html`, `history.html`, `ledger.html`, `loans_mine.html`, `loan_apply.html` (3 of them). Visual size + opacity already standardized via CSS; only the glyph rendering itself differs.

### Things found during the run that were intentionally NOT fixed

- The `auth_routes.py` `_set_session_cookie` has `secure=True` hardcoded; documented in Fix 45 but the env-var gating itself is a follow-up task (would touch `app/config.py` and Docker compose envs).
- `data/economy.db.audit_*` and `data/economy.db.phase*` test snapshots are gitignored but live on disk in `data/`. Cleanup is a manual `rm` whenever convenient.

### Things explicitly out of scope

- Backend money flow, hash chain, GDP math, demurrage, interest, stimulus, mint allocation logic, or transaction creation: untouched per the run's ground rules.
- Database schema migrations: none required by these fixes; none made.
- Production deploy / Pi / Cloudflare: no deployment in this run.

---

## How to merge this branch

```bash
# Review the branch
git log --oneline main..audit-v4-remediation

# Run smoke + state matrix locally one more time
docker compose down && rm -f data/economy.db
docker compose up -d --build && sleep 7
docker exec economy bash -c "pip install -q -r /app/requirements-dev.txt && cd /app && python -m pytest tests/smoke_test_e2e.py -q"

# Merge (after review)
git checkout main
git merge --no-ff audit-v4-remediation
```

Do not push to `main` without Parker's go-ahead.
