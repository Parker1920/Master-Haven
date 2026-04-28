# Travelers Exchange — Landing & Docs Integration Log

**Date:** 2026-04-28
**Branch:** `landing-docs-integration` (off main)
**Source mockups:** Four standalone HTML files in `C:\Users\parke\Downloads\` (`01-landing.html`, `02-docs-index.html`, `03-power-user.html`, `04-nation-leader-pitch.html`)

**Note on commit structure:** the static integration (new templates,
CSS, `docs_routes.py`, archived old landing) was committed by Parker as
`48e41c9` while I was building in parallel — same mockup sources, same
result on disk. This commit (the one this log is part of) adds the
runtime wiring that `48e41c9` left undone: FastAPI router registration,
Swagger UI relocation, the `/` redirect for logged-in users, and the
`Docs` link in the in-app nav. End state is identical to what the
dispatch describes as a single-commit deliverable; the work is just
split across two commits because of the parallel timing.

---

## Decisions

### 1. base.html compatibility — STANDALONE TEMPLATES

Reading `app/templates/base.html` showed it contains the in-app navbar
(Ledger / Nations / Search / Market / Exchange / Dashboard / Send /
History / My Shop / Portfolio / Settings / Mint / Logout) plus a footer
strip and `/static/css/style.css` link. The four marketing mockups each
have their own complete header/footer/nav structure. Forcing them to
extend `base.html` would render the in-app nav on top of the marketing
nav — two stacked headers.

**Choice:** all four new templates are standalone full-page HTML files
that do **not** extend `base.html`. They link directly to
`marketing-base.css` (shared) plus `landing.css` or `docs.css`
(page-specific) instead of the global `style.css`.

This means:
- Anonymous users see clean marketing pages with no in-app chrome.
- Logged-in users navigating from the in-app nav to "Docs" leave the
  in-app shell and land on a standalone marketing-style docs page. The
  in-app nav re-appears as soon as they navigate back to any in-app
  route. Acceptable — docs are a destination, not part of the workflow.

### 2. Logged-in users at `/` — REDIRECT TO `/dashboard`

Per dispatch recommendation. The marketing landing is for new visitors;
returning logged-in users should jump straight to their dashboard.
Implemented via a `RedirectResponse(url="/dashboard", status_code=303)`
at the top of `landing_page` in `page_routes.py`. Removed the now-unused
stats query (total_users / total_transactions / total_nations) since the
new landing doesn't display those numbers.

### 3. CSS structure — OPTION B (per dispatch directive)

Three files:

- `app/static/css/marketing-base.css` — :root design tokens, `*` reset,
  body baseline, `.marketing-nav` + `.marketing-logo` + nav links,
  `.btn-mkt` variants, `.marketing-footer` group, common nav responsive
  breakpoint. Loaded by all four templates.
- `app/static/css/landing.css` — landing-specific (hero, basics-grid,
  loop-section, places-grid, start-grid, cta-section, highlight-box,
  landing's own responsive overrides).
- `app/static/css/docs.css` — shared by docs index + power_user +
  nation_leaders. Includes doc-card styles for the index, the
  doc-switcher strip, the layout/sidebar/content structure, sections,
  callouts, tables, key-points, code-block, example-block, pillar-grid,
  auth-matrix, tier-grid, tx-type-list, check-list, pull-quote,
  qa-block, cta-block, plus all docs-specific responsive overrides.

Class names were prefixed (`marketing-`, `lp-`, `docs-`) to avoid
collision with the global `style.css` used by the in-app templates.

### 4. Discord invite on Nation Leader CTA — LEFT AS `#`

Per dispatch — Parker to fill in the real invite URL when ready.
Comment in `nation_leaders.html` flags this:
`<!-- CTA: Discord invite — placeholder per dispatch, Parker to confirm -->`

### 5. FastAPI built-in Swagger relocated — `/api/docs` and `/api/redoc`

**Issue caught during testing:** FastAPI's auto-generated Swagger UI
was already mounted at `/docs` by default and shadowed the new
`docs_routes.docs_index` route. First test call to `/docs` returned
the 942-byte Swagger HTML, not the marketing template.

**Fix:** initialised `FastAPI(...)` with `docs_url="/api/docs"` and
`redoc_url="/api/redoc"` so the API debugging UIs move out of the way.
The user-facing `/docs` is now claimed by `docs_routes.py`.
`/api/docs` and `/api/redoc` continue to serve the developer Swagger
and ReDoc, respectively.

---

## Files created

| File | Purpose |
|---|---|
| `app/templates/landing.html` | New public landing (replaces old) |
| `app/templates/docs/index.html` | Docs hub |
| `app/templates/docs/power_user.html` | "Under the Hood" guide |
| `app/templates/docs/nation_leaders.html` | NL pitch document |
| `app/routes/docs_routes.py` | Routes for `/docs`, `/docs/learn`, `/docs/nation-leaders` |
| `app/static/css/marketing-base.css` | Shared design tokens, nav, btn, footer |
| `app/static/css/landing.css` | Landing-specific styles |
| `app/static/css/docs.css` | Shared by all three docs pages |
| `app/templates/_archive/landing.html.pre-2026-04-28` | Old landing, archived for reference |

## Files modified

| File | Change |
|---|---|
| `app/main.py` | Added `docs_url="/api/docs"` + `redoc_url="/api/redoc"` to FastAPI init; imported and registered `docs_router` |
| `app/routes/page_routes.py` | `/` route: redirects logged-in users to /dashboard, drops the stats query, renders new standalone landing template |
| `app/templates/base.html` | Added `<a href="/docs">Docs</a>` between Portfolio and Settings in the logged-in nav, with `active_page == 'docs'` highlighting |

## Verification

### Smoke tests (existing suite)

```
$ py -m pytest tests/smoke_test_e2e.py --tb=short -q
52 passed, 6 warnings in 13.70s
```

No regressions from the integration.

### In-process HTTP probes (TestClient against the assembled app)

| Path | Status | Notes |
|---|---|---|
| `/` (anonymous) | 200 | marketing-base.css linked, 7,384 bytes — new landing rendered |
| `/docs` | 200 | docs index, 3,892 bytes |
| `/docs/learn` | 200 | power-user guide, 36,745 bytes |
| `/docs/nation-leaders` | 200 | NL pitch, 28,105 bytes |
| `/api/docs` | 200 | Swagger UI, 942 bytes (relocated) |
| `/static/css/marketing-base.css` | 200 | 3,571 bytes |
| `/static/css/landing.css` | 200 | 5,819 bytes |
| `/static/css/docs.css` | 200 | 19,135 bytes |

### Logged-in `/` redirect

Verified in code that `landing_page` returns
`RedirectResponse(url="/dashboard", status_code=303)` whenever
`get_current_user` resolves a non-None user. Not exercised in an
automated test in this commit (would require setting up a logged-in
TestClient session); manual verification flagged below.

## Manual verification checklist

These the existing automated suite does NOT cover. Walk through after
deploy:

- [ ] `/` (logged out) renders the new landing
- [ ] `/` (logged in) redirects to `/dashboard`
- [ ] `/docs` renders the hub, all three doc cards click through
- [ ] `/docs/learn` renders with working sidebar:
      smooth scroll, active-section tracking, mobile drawer (`☰ Sections`)
- [ ] `/docs/nation-leaders` renders with working sidebar
- [ ] Logged-in nav shows "Docs" between Portfolio and Settings
- [ ] All four pages responsive at ~380 px viewport
- [ ] No console errors on any page
- [ ] Old landing template archived (`_archive/landing.html.pre-2026-04-28`),
      not deleted; not registered as a route
- [ ] Smoke test 52/52 (already verified)
- [ ] FastAPI dev tooling still reachable at `/api/docs` and `/api/redoc`
- [ ] Discord invite URL on `/docs/nation-leaders` "Get In Touch" button —
      currently `#`, Parker to update with real invite

## Test coverage gap

The four new pages are **not** covered by automated tests in this
commit. The existing `tests/smoke_test_e2e.py` covers backend behaviour
(auth, transactions, nations, etc.) and doesn't exercise the marketing
surface.

A reasonable follow-up would be a small `tests/test_marketing_pages.py`
that asserts:

- `GET /` returns 200 for anonymous users and contains the new hero
- `GET /` returns a 303 redirect to `/dashboard` for logged-in users
- `GET /docs`, `/docs/learn`, `/docs/nation-leaders` return 200 with
  the correct title/marker strings

Not in this commit per dispatch scope ("frontend integration only").

## Open questions / blockers for Parker

1. **Discord invite URL** — currently placeholder `#` on the NL pitch
   CTA button. Replace with the real Voyager's Haven invite link.
2. **FastAPI dev tooling URLs** — moved `/docs` → `/api/docs` and
   `/redoc` → `/api/redoc`. If anything else in the project (deploy
   docs, monitoring, bookmarks) references the old paths, those need
   updating.
3. **`active_page='docs'` highlight on logged-in nav** — currently the
   active class will only ever apply if base.html renders for a
   `/docs/*` URL. Since the docs templates are standalone (don't
   extend base.html), the logged-in nav is not actually rendered while
   the user is reading docs. If you'd prefer the docs pages to keep
   the in-app nav visible at the top, the templates would need to be
   refactored to extend base.html — that's a separate decision and
   would require integrating the marketing styles with the in-app
   layout.

## Commit

Single commit on `landing-docs-integration`. Not pushed. Not deployed.
