# Remediation Tracker V5

**Started:** 2026-05-06T20:38:00-04:00
**Branch:** audit-v4-remediation
**Baseline commit:** 7b27b288f71e0becf0182ec914661824e308ef9e

## Phase status

| Phase | Status | Started | Completed | Smoke tests | Commit |
|---|---|---|---|---|---|
| 0 | done | 2026-05-06 20:38 | 2026-05-06 20:40 | 52/52 | (in-flight) |
| 1 | done | 2026-05-06 20:42 | 2026-05-06 21:08 | 52/52 | 3050916 |
| 2 | done | 2026-05-06 21:09 | 2026-05-06 21:25 | 52/52 | b489b36 |
| 3 | done | 2026-05-06 21:26 | 2026-05-06 21:55 | 52/52 | b875422 |
| 4 | done | 2026-05-06 21:56 | 2026-05-06 22:18 | 52/52 | 0cc707e |
| 5 | done | 2026-05-06 22:19 | 2026-05-06 22:38 | 52/52 | eded972 |
| 6 | done | 2026-05-06 22:39 | 2026-05-06 22:48 | 52/52 | (in-flight) |
| 7 | pending | — | — | — | — |
| 8 | pending | — | — | — | — |
| 9 | pending | — | — | — | — |
| 10 | pending | — | — | — | — |
| 11 | pending | — | — | — | — |

## Findings tracker

(Numbering follows the remediation prompt's phase-by-phase fix list, mapping back to V4 audit Section 3 / Section 4 / Section 5 where possible.)

| # | Title | Phase | Status | Files touched | Verified | Notes |
|---|---|---|---|---|---|---|
| 1 | /shop/ipo NameError 500 | 1 | done | page_routes.py | live: GET /shop/ipo→200 | module-level datetime+timedelta+timezone import; removed 9 local duplicates |
| 2 | No UI to approve pending shops | 1 | done | page_routes.py, mint/pending_shops.html, nation/pending_shops.html, mint/dashboard.html, dashboard.html, base.html | live: WM approves Alice's shop via /mint/shops/pending; Alice approves Bob's via /nation/shops/pending | new routes /mint/shops/pending, /nation/shops/pending + approve/reject; nav + dashboard cards added |
| 3 | Nation leader can self-approve own shop | 1 | done | shop_routes.py, page_routes.py | live: Alice POST /api/shops/2/approve→403; UI redirect with clear error | guards in approve_shop, reject_shop, suspend_shop and /nation/shops/{id}/approve |
| 4 | Helper for relational leader check | 2 | done | app/auth.py | live: imports work | added is_leader_of, get_led_nation in Phase 1 |
| 5 | Suspend nation demotes leader role | 2 | done | mint_routes.py, page_routes.py | live: alice citizen after suspend | preserves world_mint role; checks for other-led nations |
| 6 | Unsuspend re-promotes leader role | 2 | done | mint_routes.py, page_routes.py | live: alice nation_leader after unsuspend | new POST /api/mint/nations/{id}/unsuspend + page route |
| 7 | WM-as-leader access to /nation/* | 2 | done | page_routes.py | live: admin (WM) gets 200 on all 4 nation pages while leading Adminland | bulk-replaced 7 guard blocks via regex sub |
| 8 | Standardize role-check pattern | 2 | done | page_routes.py | grep -c found 0 occurrences after replace | get_led_nation is the canonical pattern; existing relational checks left as-is |
| 9 | Reject pending nation endpoint | 2 | done | mint_routes.py | live: API rejects, status=rejected | added POST /api/mint/nations/{id}/reject; page-route version pre-existed |
| 10 | Unsuspend nation endpoint | 2 | done | mint_routes.py, page_routes.py | (covered by fix 6) | API + page-route POST |
| 11 | Leadership-transfer flow | 2 | deferred-to-followup | — | — | needs design input |
| 12 | Validate user not already in nation on apply | 2 | done | page_routes.py | live: alice (member of Atlantia) gets "You already lead a nation" | also blocks citizens-of-other-nations from applying; rejected nation names re-usable |
| 13 | Hide "Open a Shop" CTA when ineligible | 3 | done | dashboard.html | live: bob (no nation) sees no Open a Shop button | wrapped CTA in `{% if user_nation and user_nation.status=='approved' %}` |
| 14 | Pending-nation user shouldn't see shop CTA | 3 | done | shop_manage.html, page_routes.py | live: carol (pending) sees "application is still pending" message | added user_pending_nation to base context |
| 15 | Suspended-nation leader navbar gate | 3 | done | base.html, page_routes.py | live: alice's nav has Treasury before/0 after suspend | navbar keys off user_led_nation (status=approved) |
| 16 | Approve/Reject buttons on /mint/nations | 3 | done | mint/nations.html | live: 2 Approve + 2 Restore buttons on /mint/nations | also added Suspend for approved + Restore for suspended |
| 17 | /nations empty-state CTA | 3 | done | nations.html | live: "Be the first" + "Apply to lead a nation" CTA | logged-out users prompted to register first |
| 18 | Block listing creation on pending shops | 3 | done | page_routes.py | live: bob's POST → "Your shop must be approved", listings table empty | guard in shop_listing_create_post + toggle_post |
| 19 | Pending-shop banner on /shop/manage | 3 | done | shop_manage.html | live: alert-info banner rendered for pending shop; listings form hidden | also rendered for rejected/suspended states |
| 20 | /loans/apply empty state by role | 3 | done | loan_apply.html | role-aware CTA wired (live test in Phase 6) | shows "Create a Bank" to leaders, "ask your nation leader" otherwise |
| 21 | /send max="0" poisoning | 4 | done | send.html | live: balance=0 user submits, max attr removed when balance=0 | drops max attr instead of poisoning at zero |
| 22 | Form input preservation across POST handlers | 4 | partial | send.html, nations_apply.html, shop_create.html, page_routes.py | live: /send, /nations/apply, /shop/create all preserve input on error | added _render_form_error helper; refactored 3 high-impact POST handlers; remaining (/banks/create, /loans/apply POST, /register, /login, exchange trade, distribute, ipo) NOT refactored — will use redirect+error pattern. Deferred to follow-up sweep. |
| 23 | Shop creation form too thin | 4 | done | shop_create.html, page_routes.py | live: resource_depot without mining_setup → inline error; with mining_setup → success | added shop_type select + conditional mining_setup textarea; smoke test #19/#20 still pass |
| 24 | CSRF tokens | 4 | deferred-to-followup | — | — | separate security pass |
| 25 | New-user onboarding banner | 5 | done | _partials/onboarding.html, dashboard.html, page_routes.py | live: eve sees Welcome banner, then pending banner, then nothing after approval | state machine in partial; is_new_user computed from created_at < 24h |
| 26 | Promote no-nation guidance | 5 | done | _partials/onboarding.html | (covered by fix 25) | compact "join a nation" prompt for users past first 24h |
| 27 | Apply-for-Nation entry point | 5 | done | nations.html | live: "Don't see your community" banner on /nations for non-member users | hides for users with pending app or already in nation |
| 28 | Banks in navbar | 5 | done | base.html | live: /banks/nation/{id} link in nav for users with a nation | conditional on user_nation since no top-level /banks page exists |
| 29 | Loans in navbar | 5 | done | base.html | live: /loans/mine link in nav | always visible to logged-in users |
| 30 | Distribute in navbar (leader-only) | 5 | done | base.html | live: /nation/distribute link in leader nav block | gated on user_led_nation |
| 31 | Promote pending-nation status | 5 | done | dashboard.html | live: pulse animation + larger font + ⏳ icon | inline @keyframes pulse; expanded help text |
| 32 | Mobile nav grouping | 7 | pending | — | — | V4 §F.2 |
| 33 | Sub-toggle pattern for sections | 7 | pending | — | — | tied to fix 32 |
| 34 | Breadcrumbs | 7 | pending | — | — | new |
| 35 | Favicon | 7 | pending | — | — | static asset |
| 36 | Open Graph meta tags | 7 | pending | — | — | base.html |
| 37 | Stop auto-dismissing errors | 8 | pending | — | — | V4 §F.4 |
| 38 | Standardize empty-state icons | 8 | pending | — | — | hygiene |
| 39 | Filter recent transactions on dashboard | 8 | pending | — | — | UX |
| 40 | Quick Actions visual hierarchy | 8 | pending | — | — | UX |
| 41 | Footer dynamic year | 8 | pending | — | — | trivial |
| 42 | Logout fallback form | 8 | pending | — | — | progressive enhancement |
| 43 | Wallet copy progressive enhancement | 8 | pending | — | — | data-copy attr |
| 44 | Pass user to docs templates | 9 | pending | — | — | V4 §N.1 |
| 45 | Cookie secure=True doc comment | 9 | pending | — | — | V4 §N.6, comment only |
| 46 | requirements-dev.txt for pytest+httpx | 10 | pending | — | — | V4 §N.8 |

### Unassessed (acknowledged, no fix in this run)
- UNASSESSED.1: Real-browser visual rendering (curl driver only)
- UNASSESSED.2: Concurrency / race conditions
- UNASSESSED.3: Real production data behavior
- UNASSESSED.4: Cloudflare/Pi end-to-end behavior under TLS

### Deferred-to-followup
- 11: Leadership-transfer flow (needs design input from Parker)
- 24: CSRF tokens (separate security pass)

## Phase 6 — State matrix verification

All 8 states walked live:

| State | User | Result |
|---|---|---|
| 1. New user, no nation (<24h) | newby | PASS — onboarding banner shown, no Open a Shop, no leader nav |
| 2. Pending nation app | pending_user | PASS — pending banner with pulse animation, no Open a Shop |
| 3. Citizen of approved nation | bob (in Atlantia) | PASS — no onboarding, no leader nav |
| 4. Leader of approved nation | alice (Atlantia) | PASS — Treasury+Distribute+Members+Pending Shops nav present (x2 = nav + dashboard card) |
| 5. Leader of suspended nation | shea (SheaLand suspended) | PASS — role demoted to citizen, no leader nav |
| 6. WM also leading a nation | admin (Adminland) | PASS — Mint nav + Treasury nav both visible, /nation/treasury returns 200 |
| 7. Shop owner with pending shop | bob (Bob Shop) | PASS — pending banner on /shop/manage, listing form replaced with placeholder |
| 8. Shop owner with approved shop | alice (Alice Shop) | PASS — full management UI, IPO link visible |
