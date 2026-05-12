# Travelers Exchange — Live Audit V4 (2026-05-06)

**Scope:** Front-end QoL / clickability and the user → nation-leader → business owner permission path.
**Methodology:** Live HTTP traffic against a freshly-built container with a fresh DB. Code is consulted only to corroborate observed UI behavior or pinpoint where a fix lands.
**Out of scope (covered by V1/V2/V3):** backend money flow, hash chain, GDP math, demurrage, locked design decisions.

---

## 1. Environment

| Item | Value |
|---|---|
| Host OS | Windows 11 Pro 26200 |
| Engine | Docker 29.2.1 |
| Compose file | [docker-compose.yml](docker-compose.yml) (built from this branch) |
| Image | `haven-exchange-travelers-exchange:latest` (sha256:51814c746f08…) |
| Container | `economy` |
| Container ID | `4684f991fca8` (initial) → `bf…` (post-rebuild after fresh DB) |
| Port | `localhost:8010 → 8010/tcp` (published, plain HTTP) |
| DB | `./data/economy.db` (mounted from host) — **wiped before audit**, prior file backed up to `data/economy.db.audit_backup_20260506_192253` |
| Test users | `admin / changeme` (seeded `world_mint`), `alice / password123` (registered live), `bob / password123` (registered live) |
| Cookie jars | `/tmp/aliceA.cookies`, `/tmp/admin.cookies`, `/tmp/bob.cookies` |
| Health | `GET /health → {"status":"ok","service":"Travelers Exchange"}` |

**Reproduction:**
```bash
cd C:/Master-Haven/Haven-Exchange
docker compose down
mv data/economy.db data/economy.db.bak  # back up
docker compose up -d --build
sleep 5 && curl -s http://localhost:8010/health
# admin user is auto-seeded; register alice/bob via /api/auth/register
```

**HTML snapshots** of every page walked are saved in `audit_v4_screenshots/*.html` (no real screenshots — driver was curl, not a browser). File names map to the flow they belong to (`A1_…`, `B5_…`, etc.).

---

## 2. Live Walkthrough Findings

### Flow A — Brand new user, no nation (Alice)

**A.1 Registration succeeds, lands on dashboard with helpful empty state.** ✅
`POST /api/auth/register` returned `{"success":true,"wallet_address":"TRV-6fa948f9"}`. Subsequent `GET /dashboard` (200) renders the Welcome card, balance 0 TC, and a Nation card that correctly says *"Not a member of any nation yet."* with `Browse Nations` and `Create a Nation` buttons. Both buttons go to the right places. This part of the empty state is good.

**A.2 "Open a Shop" button is shown to a user who can't open a shop.** ❌ HIGH
The dashboard's Quick Actions row renders an `Open a Shop` button for Alice (no nation, 0 TC) — gated only by `{% if user_shop %}` in [dashboard.html:114-115](app/templates/dashboard.html#L114-L115), not by nation status. Clicking it `GET /shop/create` issues a 303 to `/shop/manage?error=You+must+join+a+nation+first`.

The redirect target is even worse: the empty state on `/shop/manage` shows a big `Create Shop` button that links right back to `/shop/create`. Alice can click `Create Shop → "You must join a nation first" → Create Shop → "You must join a nation first"` indefinitely. The error message tells her *what* is wrong but offers no link to what she should actually do (`/nations` or `/nations/apply`).

Verbatim error shown:
```
You must join a nation first
```

**A.3 `Send` with 0 balance: error message is correct, but the form is hostile to retry.** ❌ HIGH
`POST /send` with `to_address=TRV-aaaa1111&amount=10&memo=test` redirected to `/send?error=Insufficient+balance.+Available:+0,+required:+10.` Two problems on the re-rendered form:
1. **No values are preserved.** [send.html](app/templates/send.html) does not interpolate the previous `to_address`, `amount`, or `memo` values back into the inputs. The user retypes everything.
2. **The amount input is poisoned.** The `<input type="number" id="amount" name="amount" required min="1" max="0" step="1">` line has `max="0"` because the server-rendered template sets `max` from `user.balance`. With balance 0 it's literally impossible to enter any positive number on this form. The error tells you "you need 10 TC" while the field forbids you from typing 10 again.

This same `?error=…` pattern (POST → redirect with the literal error string smuggled in the URL) is everywhere: [page_routes.py:1530-1535](app/routes/page_routes.py#L1530-L1535), [page_routes.py:3340-3344](app/routes/page_routes.py#L3340-L3344), and many more. It's a generic input-loss problem, not a one-off.

**A.4 `Portfolio`, `Nations`, and `History` empty states.** Mixed.
- `/portfolio` (200): "No holdings yet" with `Browse Exchange` button → good, actionable, single-click resolution.
- `/nations` (200) for a fresh DB: "No nations yet — There are no approved nations at this time. Check back later!" with **no CTA**. A new user looking for a nation to join hits a page that says "check back later" instead of "no nations yet — but you can found one yourself," even though `/nations/apply` exists and would solve their problem.
- `/history` (200): renders the "Genesis" entry and that's it. Acceptable.

**A.5 Path discovery for "how do I join/lead a nation."**
Both work: the navbar has a `Nations` link and the dashboard's Nation card has a `Create a Nation` button that routes to `/nations/apply`. Alice can find the apply path in two clicks. The form itself is reasonable.

---

### Flow B — Alice applies to lead a nation, World Mint approves

**B.1 `POST /nations/apply` succeeds.** ✅ Atlantia is created with `status='pending'`, `leader_id=2`, treasury wallet `TRV-NATION-bb1ea626`. Alice gets `success=Nation+application+submitted+successfully` flash on the dashboard.

**B.2 Alice's pending state on the dashboard.** ✅ Good Nation card. The card now shows `Atlantia` with a `Pending Approval` badge and the line *"Your nation application is being reviewed by the World Mint."* Clear and accurate.

**B.3 But the dashboard still shows "Open a Shop" for the same pending user.** ❌ HIGH (continuation of A.2)
`shop/create` continues to redirect to `/shop/manage?error=You+must+join+a+nation+first`. Worse — the error is *misleading*. Alice IS in a nation (it's just pending). The honest error would be *"Your nation application is still pending approval"* and the button shouldn't render until the nation is approved.

**B.4 World Mint approval: two routes, only one has the buttons.** ⚠️ MEDIUM
- `GET /mint` (the Mint dashboard) renders an `Approve` and `Reject` form for each pending nation. Works as expected.
- `GET /mint/nations` (the "All Nations" admin page) lists the same pending Atlantia row but its action column only contains `Edit` and `View`. There is **no Approve / Reject** button on this page. An admin who lands on `/mint/nations` first would conclude there's nothing to do, since there's no visible cue that the actions live on the Mint dashboard.

**B.5 After approval.** ✅
`POST /mint/nations/1/approve` → 303 to `/mint?success=Nation+'Atlantia'+approved+successfully`. DB confirms Alice is promoted to `nation_leader` and Atlantia is `approved`. Alice's next dashboard load shows a `Leader` badge on the Nation card and three new buttons (`Treasury`, `Distribute`, `Members`). The navbar gains a `Treasury` and `Members` group below the standard user links.

> Subtle gap: there is no visible indication that `Distribute` is a thing, *unless* you're on the dashboard's Nation card. The navbar has Treasury + Members but no Distribute. To distribute, Alice has to know to click `Treasury` or use the Nation card. Worth surfacing in the navbar.

---

### Flow C — Leader opens a business *(the flow Parker specifically flagged)*

**C.1 Shop creation form is fine but minimal.** ⚠️ LOW
`/shop/create` (200) shows two fields: `name` (required), `description` (optional). No nation selector (correct — derived from user), no shop category, no "preview" of the API endpoint's `category` field. Submission `POST /shop/create` with `name=Atlantis+Trading+Co&description=Test+shop` succeeds and redirects to `/shop/manage?success=Shop+created+successfully`.

**C.2 Shop is created with `status='pending'` but the manage page shows no indication of this.** ❌ HIGH
`/shop/manage` after creation renders:
- Page title `Atlantis Trading Co`
- Stats grid (4 zeros)
- "Add New Listing" form (fully functional)
- Buttons: `View Public Shop Page`, `IPO / Stock Listing`

There is **zero indication** that the shop is awaiting World Mint or Nation Leader approval. No badge, no banner, no muted note in the header. The leader has no way to know their shop is gated.

**C.3 Listings can be created on a pending shop.** ❌ HIGH
`POST /shop/listings/create` with `title=Test+Item&price=50` succeeded with `success=Listing+created` and the row landed in `shop_listings` despite the parent shop being `status='pending'`. The route at [page_routes.py:1767](app/routes/page_routes.py#L1767) does not check shop approval status before inserting. So the leader can fully populate inventory before the shop is approved — confusing UX, and a small data-integrity wart (listings exist for a shop that may end up rejected).

**C.4 `/shop/ipo` is a hard 500 for any user with a shop.** ❌ CRITICAL
`GET /shop/ipo` returns HTTP 500. Container log shows:
```
File "/app/app/routes/page_routes.py", line 3150, in shop_ipo_page
    days = (datetime.now(tz.utc) - shop.created_at.replace(tzinfo=tz.utc)).days
            ^^^^^^^^
NameError: name 'datetime' is not defined
```
The local import at [page_routes.py:3142](app/routes/page_routes.py#L3142) brings in `from datetime import timezone as tz` only — `datetime` itself is **not imported anywhere in the module** (`grep -n "^from datetime\|^import datetime" app/routes/page_routes.py` returns no matches). The IPO page is completely broken. Anyone who clicks `IPO / Stock Listing` from `/shop/manage` gets a generic Internal Server Error.

**C.5 No UI exists to approve / reject pending shops.** ❌ CRITICAL — *the blocker Parker flagged*
- `POST /api/shops/{shop_id}/approve` exists in [shop_routes.py:510](app/routes/shop_routes.py#L510). Works.
- `POST /api/shops/{shop_id}/reject` exists in [shop_routes.py:547](app/routes/shop_routes.py#L547). Works.
- `GET /api/shops/pending` exists in [shop_routes.py:129](app/routes/shop_routes.py#L129). Works.
- **No template renders a list of pending shops or a button that hits these endpoints.**
  Confirmed by `grep -rn 'shops/[0-9]\+/approve\|shop_approve' app/templates` — only doc files mention approval. The mint dashboard has approve buttons for *nations* but nothing for *shops*. The nation detail page has no shop list. The leader's own `/shop/manage` shows their own shop but offers no approve button (and shouldn't if self-approval is closed off).

The only way to advance a shop from pending → approved today is: hit the API by hand with `curl -X POST /api/shops/{id}/approve`. **There is no clickable path through the UI.**

**C.6 Even worse — the API allows the shop owner who is the nation leader to approve their own shop.** ❌ HIGH (security/business-logic)
[shop_routes.py:526](app/routes/shop_routes.py#L526) checks `if current_user.role != "world_mint" and current_user.id != nation.leader_id`. There is no separate guard ensuring the approver is not the shop owner. Verified live:
1. Reverted shop 1 to pending: `UPDATE shops SET status='pending' WHERE id=1`
2. As Alice (owner_id=2, leader_id=2 of nation 1), `POST /api/shops/1/approve`
3. Response: `{"success":true,"shop_id":1,"status":"approved"}`. DB now has `approved_by=2` (Alice).

A leader who founds a nation can launch shops on it, then sign off on them in the same session. World Mint never has to look. Combined with the missing pending-shops UI (C.5), this is *currently* the only working approval path — leader-self-approves via API. So the system effectively has no shop review.

---

### Flow D — World Mint as a nation leader

Hypothesis from prior audits: WM is silently locked out because page guards check `if user.role != "nation_leader"`.

Live test:
1. Promoted admin (role=`world_mint`) into a 2nd nation as its leader: `INSERT INTO nations (name, leader_id, status, …) VALUES ('Adminland', 1, 'approved', …); UPDATE users SET nation_id=2 WHERE id=1`.
2. `GET /nation/treasury` → 303 to `/dashboard?error=You+must+be+a+nation+leader+to+access+the+treasury`
3. `GET /nation/distribute` → 303 to `/dashboard?error=You+must+be+a+nation+leader+to+distribute+funds`
4. `GET /nation/members` → 303 to `/dashboard?error=You+must+be+a+nation+leader`
5. `GET /nation/settings` → 303 to `/dashboard?error=You+must+be+a+nation+leader+to+edit+nation+settings`

**CONFIRMED.** All four pages locked. Source: identical guard pattern at [page_routes.py:789](app/routes/page_routes.py#L789), [:843](app/routes/page_routes.py#L843), [:1010](app/routes/page_routes.py#L1010 ), [:633](app/routes/page_routes.py#L633). Every guard is `if user.role != "nation_leader"`.

`/banks/create` correctly uses the broader check `if user.role not in ("nation_leader", "world_mint")` ([page_routes.py:3271](app/routes/page_routes.py#L3271)). So the precedent for the right pattern is already in the codebase — the four nation pages are just out of date.

Severity: in production today this is dormant (Stars-as-WM is not also leading a nation), but it lights up the moment any WM user wants to run their own community as well. Likely to surface during onboarding of a future co-admin.

---

### Flow E — Suspended nation lifecycle

Live test:
1. `POST /api/mint/nations/1/suspend` (admin) → 200, DB: Atlantia status `approved → suspended`.
2. Alice's `users.role` is **not** demoted from `nation_leader`.
3. Alice `GET /nation/treasury` → 303 to `/dashboard?error=No+approved+nation+found` (because the route filters `Nation.status == "approved"`).
4. Same misleading error on `/nation/distribute` and `/nation/members`.
5. Alice `GET /shop/create` → "Your nation must be approved" (correct, but cookie-cutter).
6. Alice's dashboard:
   - Nation card now shows her as `Member` (not `Leader`) — derived from nation status, this part is right.
   - Navbar **still** shows `Treasury` and `Members` links because the navbar's gate is `user.role == "nation_leader"`, not `nation.status`. Clicking either dumps her on the dashboard with the misleading error from step 3.

Two findings here:
- **E.1 — Misleading error on suspended-nation page guards.** ❌ MEDIUM. The text "No approved nation found" is technically true but useless to a user whose nation was just suspended. They'll think their nation was deleted. Should say *"Your nation has been suspended by the World Mint. Contact admin@…"* or similar.
- **E.2 — Navbar still advertises leader pages after suspension.** ❌ MEDIUM. The Treasury / Members nav links in [base.html](app/templates/base.html) are gated on `user.role`, not on `nation.status`. Either demote the role on suspend, or extend the gate to check the nation's current status.

**E.3 — There is no "reject pending nation" endpoint exposed in the UI** other than the Reject button on the mint dashboard (which exists for *pending* nations only). For a *suspended* nation, the only operations are re-approve (via direct DB or another suspend toggle?) and the existing suspend endpoint. There's no `POST /api/mint/nations/{id}/unsuspend` and no `POST /api/mint/nations/{id}/delete`. A suspended nation is permanently in limbo from the UI's point of view.

---

### Flow F — Mobile experience

Driver was curl, so no real viewport rendering. Findings are based on inspecting the served markup + CSS.

**F.1 Mobile menu mechanics work.** ✅ [style.css:1577-1604](app/static/css/style.css#L1577-L1604) implements a standard hamburger pattern: at ≤768px, `.nav-links` is hidden and absolute-positioned, becomes `display:flex` when `.open` class is added (presumably by `static/js/app.js`). The toggle button gets `display:block` only on mobile. Standard pattern, should work.

**F.2 The mobile menu has 15 items for a nation leader.** ❌ MEDIUM
Counted from the served markup of Alice's dashboard (post-approval): `Ledger / Nations / Search / Market / Exchange | Dashboard / Send / History / My Shop / Portfolio / Docs / Settings | Treasury / Members | Logout` = 15 items. On a 375px-wide phone with the menu open at full-screen-width that's ~15 × ~48px tap targets = ~720px of vertical scrolling just for nav, on top of the Welcome header. Some items are redundant on mobile (e.g. Ledger and Search are both reachable from the Wallet card).

**F.3 The `Send` form's `max="0"` problem (A.3) is amplified on mobile.** ❌ HIGH (re-statement, not new). Mobile users can't easily long-press to inspect why their number input refuses values.

**F.4 The auto-dismiss alert pattern (`data-auto-dismiss="true"`) hides errors after a timeout** — confirmed by inspecting the DOM. On mobile this is fine for success but bad for errors, especially the long server-side error strings smuggled in `?error=…`. A user who paused to read just lost the message.

---

## 3. Confirmed Bugs (live verified, not just code-read)

| # | ID | Title | Evidence |
|---|---|---|---|
| 1 | C.4 | `/shop/ipo` always returns HTTP 500 | Container log + curl 500 + line 3150 NameError |
| 2 | C.5 | No UI to view/approve pending shops | `grep -rn 'shop.*approve' app/templates` finds zero |
| 3 | C.6 | Nation leader can self-approve their own shop | Live API call by Alice → DB shows `approved_by=2` (her id) |
| 4 | D.1 | World Mint locked out of `/nation/treasury,distribute,members,settings` | All 4 redirected to dashboard with role error |
| 5 | C.3 | Listings creatable on a `pending` shop | `INSERT INTO shop_listings` succeeded for shop status=pending |
| 6 | A.2/B.3 | "Open a Shop" CTA shown to users who cannot open one | Dashboard renders button regardless of nation status |
| 7 | A.3 | `/send` form wipes input AND sets `max="0"` on retry | Re-rendered HTML had no `value=` attrs and `max="0"` |
| 8 | E.1 | Suspended-nation leader gets "No approved nation found" | Verified by suspending then visiting Alice's leader pages |
| 9 | E.2 | Navbar continues to show leader links after nation suspension | Same dashboard render confirms `/nation/treasury` link present |
| 10 | B.4 | `/mint/nations` admin page missing Approve/Reject buttons | Action column renders Edit / View only |

---

## 4. New Findings (not in V1/V2/V3)

| # | Finding | Severity | Notes |
|---|---|---|---|
| N.1 | `/docs`, `/docs/learn`, `/docs/nation-leaders` show the marketing navbar (Login/Register buttons) even when logged in. | LOW | [docs_routes.py](app/routes/docs_routes.py) doesn't pass `user` to template context. Logged-in users see "Login" CTA on every doc page. |
| N.2 | "No nations yet" empty state on `/nations` lacks CTA to apply. | LOW | New users must already know `/nations/apply` exists. The page that lists nations should mention "or start your own." |
| N.3 | `/loans/apply` empty state ("No banks available") doesn't differentiate roles. A nation leader sees the same "Back to Dashboard" instead of a "Create a Bank" link. | LOW | `if user.role == 'nation_leader'` branch missing. |
| N.4 | `/shop/ipo` page (when fixed) accepts `num_shares` but never validates that the shop is `status='approved'`. | MEDIUM | Pending shops should not IPO. Same root cause as C.3. |
| N.5 | The `Distribute` action is missing from the navbar despite being a primary leader workflow. Only reachable via the dashboard Nation card. | LOW | Add to the leader nav block. |
| N.6 | Cookie is set with `secure=True` ([auth_routes.py:36](app/routes/auth_routes.py#L36)). Local dev or any plain-HTTP environment can't store the session in a real browser. Production behind Cloudflare is fine. | LOW (info) | Either gate by env, or document that local dev requires HTTPS. |
| N.7 | No "unsuspend / restore" endpoint exists for suspended nations. | MEDIUM | A WM who suspends accidentally has to flip the row in SQL. |
| N.8 | Smoke test suite imports from `tests/smoke_test_e2e.py` but the runtime container ships without `pytest` or `httpx`. | LOW | Add `pytest`, `httpx` to a `requirements-dev.txt` or expose a `pytest` profile. |

---

## 5. Severity-ranked fix list

Each item is sized to be one bounded task. File paths are absolute within the repo.

### CRITICAL

1. **Fix `/shop/ipo` 500.** Add `from datetime import datetime, timezone` at module top of [app/routes/page_routes.py](app/routes/page_routes.py) (and remove the duplicate local imports that hide the real one). ~5 line diff. (15 min.)
2. **Build a "Pending Shops" admin / leader UI.** Add a section to `/mint` (for WM) and `/nations/{id}` (for nation leader) that lists shops with `status='pending'`, with `Approve` and `Reject` form buttons that hit the existing API endpoints. New partial template + minor route changes in [app/routes/page_routes.py](app/routes/page_routes.py) and the mint/nation dashboard templates. ~80–120 lines. (2–3 h.)

### HIGH

3. **Block self-approval of shops.** Add `current_user.id != shop.owner_id` check in [shop_routes.py:526](app/routes/shop_routes.py#L526) (and the same in `reject_shop` and `suspend_shop`). 3-line diff. (10 min.)
4. **Hide "Open a Shop" CTA when the user can't open one.** Update [dashboard.html:114-115](app/templates/dashboard.html) to wrap the `Open a Shop` button in `{% if user_nation and user_nation.status == 'approved' %}`. Same logic for the `/shop/manage` empty state CTA in [shop_manage.html](app/templates/shop_manage.html). (15 min.)
5. **Show pending-shop status to the owner.** Add a `<div class="alert alert-info">Your shop is pending World Mint or Nation Leader approval.</div>` banner at the top of [shop_manage.html](app/templates/shop_manage.html) when `shop.status == 'pending'`, and disable the `Add New Listing` form below it. (20 min.)
6. **Block listing creation on pending shops.** In [page_routes.py:1767](app/routes/page_routes.py#L1767) (`shop_listing_create_post`), add `if shop.status != 'approved': return RedirectResponse(url='/shop/manage?error=Shop+must+be+approved', status_code=303)`. (5 min.)
7. **Fix the `/send` form's `max="0"` poisoning.** In [send.html](app/templates/send.html), change `max="{{ user.balance }}"` to `max="{{ user.balance if user.balance > 0 else '' }}"`. Even better: drop the `max` attribute entirely and rely on the server validation message. (10 min.)
8. **Preserve `to_address`, `amount`, `memo` on `/send` error.** Read the form body in `send_post` and put it back into the `?error=…` redirect via a session-scoped flash, OR change the route to render the template directly instead of `RedirectResponse(...)` so Jinja can echo the previous values. The whole codebase shares this pattern — the same fix should be applied to `/banks/create`, `/loans/apply`, `/nations/apply`, `/exchange/{ticker}/buy|sell`, `/nation/distribute`, `/shop/listings/create`. Consider a shared `flash_form_data` helper. (3–4 h for sweeping fix; 30 min for `/send` only.)
9. **Fix WM-as-nation-leader access.** Change `if user.role != "nation_leader"` to `if user.role not in ("nation_leader", "world_mint") or (user.role == "world_mint" and …)` on [page_routes.py:789](app/routes/page_routes.py#L789), [:843](app/routes/page_routes.py#L843), [:1010](app/routes/page_routes.py#L1010), [:633](app/routes/page_routes.py#L633), and the four corresponding POST handlers. Mirror the pattern already used at [page_routes.py:3271](app/routes/page_routes.py#L3271) (`/banks/create`). 8 small diffs. (45 min.)

### MEDIUM

10. **Suspended-nation messaging.** When a nation page guard fails because `nation.status != 'approved'` rather than because the user isn't the leader, return an `error=Your+nation+is+currently+suspended+by+the+World+Mint.` instead of `error=No+approved+nation+found`. (20 min.)
11. **Navbar gate for leader links should respect `nation.status`.** [base.html](app/templates/base.html) — don't render Treasury/Members when `user_nation.status != 'approved'`. (10 min.)
12. **Add `Approve` / `Reject` buttons to `/mint/nations` table** so the page isn't dead weight. (20 min.)
13. **Pass `user` into docs templates** so the marketing nav doesn't show Login/Register to authenticated users. Edit [docs_routes.py](app/routes/docs_routes.py) and template's nav include. (15 min.)
14. **Add `Distribute` to the leader nav block** in [base.html](app/templates/base.html). (5 min.)
15. **Validate IPO shop status.** In `/shop/ipo` POST handler at [page_routes.py:3170](app/routes/page_routes.py#L3170), add `if shop.status != 'approved': return RedirectResponse(...)`. (5 min.)
16. **Add an unsuspend (or full delete) endpoint** for suspended nations on the Mint dashboard. (1 h.)
17. **Mobile nav grouping.** Reduce the leader-mode flat list of 15 items by collapsing community/marketing links into a "More" submenu on screens ≤768px. (1–2 h CSS work.)

### LOW

18. Empty-state CTAs on `/nations`, `/loans/apply` to mention the apply / create-bank action. (15 min each.)
19. Stop auto-dismissing error-class alerts ([static/js/app.js](app/static/js/app.js)). Errors should stay until the user closes them. (10 min.)
20. Add `pytest` and `httpx` to a `requirements-dev.txt` so smoke tests can be re-run inside the prod image without ad-hoc `pip install`. (5 min.)

---

## 6. What I could not test and why

- **Real-browser visual rendering.** Driver was curl. Findings about color, alignment, and spacing are absent. Anything that requires "does this look broken at 375px in Safari" needs a real browser run with screenshots.
- **JavaScript behavior.** `static/js/app.js` was not loaded by curl. The `data-auto-dismiss`, `data-confirm`, and hamburger-toggle behaviors were inferred from the markup + CSS, not exercised. A confirm-dialog regression on `/send` (e.g. JS error) would not be caught here.
- **Concurrency / race conditions.** Single-user single-thread driver. The audit didn't try double-submitting a shop create or two leaders racing to approve.
- **Real production data.** The audit ran on a fresh DB. The "Pending shops table is empty" and "no banks yet" empty states are well-tested but the populated states for those same screens are not. Production behavior with hundreds of nations / thousands of users wasn't sampled.
- **Cloudflare / Pi end-to-end.** The audit ran against `localhost:8010` from a host with port published; the Pi production stack is behind Nginx Proxy Manager + Cloudflare. Cookie behavior under that path (especially `secure=True` with the actual TLS termination) was not verified.
- **CSV / file upload paths.** None hit during the walkthrough.
- **Smoke tests after edits.** No edits were made; the 52/52 smoke pass was only re-confirmed against the unchanged code (see §7 below).

---

## 7. Smoke test confirmation

```
docker exec economy bash -c "cd /app && python -m pytest tests/smoke_test_e2e.py -q"
…
52 passed, 6 warnings in 12.59s
```
(Required `pip install pytest httpx` inside the container — see fix #20.)

The audit made **zero code changes**. The DB was wiped at the start to give a fresh canvas; production users' DB lives on the Pi and was untouched.

---

## Console summary — top 5 highest-severity findings

1. **`/shop/ipo` is a hard 500.** `NameError: name 'datetime' is not defined` at [page_routes.py:3150](app/routes/page_routes.py#L3150). Module never imports `datetime`, only `timezone as tz` locally. Every leader who clicks the IPO button gets an Internal Server Error.
2. **There is no UI to approve a pending shop.** API endpoints exist (`/api/shops/{id}/approve`, `/api/shops/{id}/reject`, `/api/shops/pending`) but nothing in the templates surfaces them. The leader-opens-a-business flow Parker flagged is genuinely blocked beyond the "create" step unless someone hits the API by hand.
3. **A nation leader can self-approve their own shop.** [shop_routes.py:526](app/routes/shop_routes.py#L526) treats `current_user.id == nation.leader_id` as sufficient authorization without checking the leader is also the shop owner. Combined with #2, this means the *only currently-working* approval path is leader-self-approves-via-curl. There is effectively no shop review.
4. **World Mint who also leads a nation is silently locked out of every nation-leader page.** Hard `if user.role != "nation_leader"` guard on `/nation/treasury,distribute,members,settings`. Misleading "You must be a nation leader" error even though the user IS the nation leader. Dormant in current production but a one-line fix and easy to surface during co-admin onboarding.
5. **The "Open a Shop" CTA → `/shop/create` → `/shop/manage` redirect is a clickable infinite loop for users with no nation.** Same misleading error fires for users with a *pending* nation application. Combined with form-input wipe on `/send`'s POST-redirect-GET pattern, the empty-state and error paths feel hostile to the new user, exactly the QoL theme Parker flagged.

---

**Audit file:** [TRAVELERS_EXCHANGE_AUDIT_V4_2026-05-06.md](TRAVELERS_EXCHANGE_AUDIT_V4_2026-05-06.md)
**HTML evidence:** `audit_v4_screenshots/*.html`
**Smoke status:** 52/52 still passing.
