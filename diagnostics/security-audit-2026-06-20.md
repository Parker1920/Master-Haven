# Master Haven Ecosystem — Full Security Audit

**Date:** 2026-06-20
**Auditor:** Claude (automated, read-only)
**Scope:** All 5 websites + 2 bots in the Master-Haven monorepo
**Constraints:** Read-only. No fixes applied. No code uploaded to external services. All tools run locally.

---

## Phase 0 — Service Inventory

| # | Service | Type | Internet-Facing | Port | Tech Stack |
|---|---------|------|-----------------|------|------------|
| 1 | Haven-UI (frontend) | Web app | Yes | 5173/8005 | React 18, Vite, Tailwind |
| 2 | Haven-UI backend | API server | Yes | 8005 | Python, FastAPI, SQLite |
| 3 | NMS-Haven-Extractor | In-game mod | No (client-side) | — | Python, PyMHF |
| 4 | NMS-Debug-Enabler | In-game mod | No (client-side) | — | Python, PyMHF |
| 5 | NMS-Memory-Browser | Desktop tool | No (local) | — | Python, PyQt6 |
| 6 | NMS-Save-Watcher | Local service | No (local) | 8006 | Python, FastAPI |
| 7 | The_Keeper | Discord bot | Yes (Discord API) | — | Python, discord.py |
| 8 | Philbert-discord | Discord bot | Yes (Discord API) | — | Node.js, discord.js |
| 9 | Planet_Atlas | Web app | No (local tool) | 8050 | Python, Dash, Plotly |
| 10 | Haven-Exchange | Web app (WIP) | Not yet deployed | 8010 | Python, FastAPI |
| 11 | Travelers-Collective | Web app (WIP) | Not yet deployed | — | Python, FastAPI |
| 12 | SkyScraper | Static site | Yes | 80 (nginx) | HTML/CSS/JS |
| 13 | Viobot | Static docs | Yes | 80 (nginx) | HTML |
| 14 | Grand Festival | Web app | Yes | 8082 | Python FastAPI + React |
| 15 | Travelers Archive | Web app | Yes | 8020 | Python, FastAPI |
| 16 | glyphtool | CLI utility | No (local) | — | Python |
| 17 | scripts/ | Maintenance | No (local) | — | Python, Bash |

**Internet-facing attack surface:** Haven-UI backend (8005), The_Keeper (Discord), Philbert-discord (Discord), SkyScraper (nginx), Viobot (nginx), Grand Festival (8082), Travelers Archive (8020). All proxied through Nginx Proxy Manager + Cloudflare on the Pi.

---

## Phase 1 — Secrets Scanning

**Tools used:** gitleaks v8.18.4, trufflehog v3.82.13 (both local, no live verification)

### CRITICAL Findings

#### CRIT-01: Tebex/Buycraft Live API Key (HARDCODED)
- **File:** `The_Keeper/exchange/exchange.py` lines 8 and 790
- **Secret:** `tx_live_c7f3247ac8aa28027e83e83e7f907192`
- **Risk:** Live payment-processing API key. If the repo were ever made public, anyone could access the Tebex store admin API — view transactions, modify products, potentially issue refunds.
- **Committed by:** whrstrsg (Stars)
- **In git history:** YES — requires rotation regardless of current HEAD state
- **Action:** ROTATE IMMEDIATELY via Tebex dashboard. Move to `.env`.

#### CRIT-02: Discord Webhook Credentials (HARDCODED)
- **File:** `Philbert-discord/index.js` lines 284-286
- **Secrets:**
  - Webhook ID: `1437621723619917834`
  - Webhook Token: `vyRYwLEIo0Jdvi-Nmcd5DLj38kBYUu7JCJXuV8TalV1XBkvDQ06xLatLdN0eZuX6x-lp`
- **Risk:** Anyone with these values can post arbitrary messages to the target Discord channel, impersonating the webhook. Social engineering / spam vector.
- **In git history:** YES
- **Action:** Delete and recreate the webhook in Discord server settings. Move credentials to `.env`.

### HIGH Findings

#### HIGH-01: Grand Festival Default Admin Password
- **File:** `grand-festival/docker-compose.yml` line 22
- **Secret:** `GrandFestival2026!` (hardcoded as `ADMIN_PASSWORD` env var)
- **Risk:** Anyone reading the repo knows the admin password. If the service is internet-facing, immediate admin access.
- **Action:** Change to a runtime-injected secret (Docker secret or `.env` file not committed).

#### HIGH-02: Travelers-Collective Default Passwords
- **File:** `Travelers-Collective/docker-compose.yml` lines 11, 39, 41
- **Secrets:** `collective_dev_password`, `change-me`
- **Risk:** Same as HIGH-01 — default passwords in committed config.
- **Action:** Move to `.env` or Docker secrets.

#### HIGH-03: Haven-Exchange Placeholder JWT Secret
- **File:** `Haven-Exchange/app/config.py` lines ~10-15
- **Secret:** `travelers-exchange-secret-change-me`
- **Risk:** If deployed as-is, JWT tokens are trivially forgeable.
- **Action:** Generate a random secret, inject via environment variable.

### OK / Safe Findings

| Item | Status | Detail |
|------|--------|--------|
| The_Keeper Discord bot token | SAFE | Loaded from `.env` via `dotenv` (`bot.py` line 6) |
| Philbert Discord bot token | SAFE | Loaded from `process.env.token` (`index.js` line 2606) |
| Haven-UI backend session secret | SAFE | Not hardcoded in source (runtime config) |
| Haven Extractor API keys | SAFE | Per-user keys, SHA256-hashed at storage, gitignored config |

### Gitleaks / TruffleHog Scanner Notes
- gitleaks flagged ~15 results; most were false positives (base64-encoded glyph art, test data).
- trufflehog ran in offline mode (no live verification). The Tebex key and webhook token are the only confirmed real secrets.
- **Live verification could later confirm:** whether the Tebex key is still active (hit Tebex API with a read-only call), whether the webhook token is still valid (attempt a GET on the webhook URL).

---

## Phase 2 — Repo Hygiene

### Committed Database Files

| File | Risk | Detail |
|------|------|--------|
| `The_Keeper/cogs/Data/xp.db` | LOW | SQLite DB with Discord user XP/activity data (snowflake IDs, message counts). Not sensitive PII but unnecessary in version control. |
| `The_Keeper/Data/users.json` | LOW | Discord user data JSON. Same concern — user metadata shouldn't live in git history. |

### .gitignore Coverage

| Path | Status | Note |
|------|--------|------|
| `Haven-UI/data/haven_ui.db` | COVERED | Main app DB is gitignored ✓ |
| `Haven-UI/photos/*` | COVERED | User-uploaded photos gitignored ✓ |
| `Haven-UI/.env` | COVERED | Backend env vars gitignored ✓ |
| `The_Keeper/.env` | COVERED | Bot token safe (loaded from env) ✓ |
| `The_Keeper/cogs/Data/xp.db` | NOT IGNORED | Committed — should be gitignored |
| `The_Keeper/Data/users.json` | NOT IGNORED | Committed — should be gitignored |
| `Philbert-discord/node_modules/` | COVERED | gitignored ✓ |
| `grand-festival/data/` | COVERED | Runtime data gitignored ✓ |

### Recommendations
- Add `The_Keeper/cogs/Data/*.db` and `The_Keeper/Data/users.json` to `.gitignore`, then `git rm --cached` them.
- The committed DB files are LOW risk (Discord snowflake IDs are semi-public) but represent unnecessary data in version control.

---

## Phase 3 — Dependency CVEs

### Python Dependencies (Haven-UI Backend)

**Note:** No `requirements.txt` file exists at `Haven-UI/backend/requirements.txt`. Versions sourced from the backend CLAUDE.md.

| Package | Pinned Version | Latest (as of 2026-06) | CVE Risk | Detail |
|---------|---------------|----------------------|----------|--------|
| **python-multipart** | 0.0.6 | 0.0.20+ | **CRITICAL** | CVE-2024-24762: ReDoS in content-type header parsing. CVE-2024-47874: header injection. Both fixed in 0.0.7+. This is the multipart parser FastAPI uses for file uploads — every `POST /api/photos`, `/api/extraction` file payload, CSV import is exposed. |
| **starlette** | 0.27.0 | 0.46+ | **HIGH** | CVE-2024-24768: CORS middleware bypass via crafted Origin header. CVE-2023-30798: multipart DoS. Multiple path traversal fixes in 0.36+. Starlette is the ASGI layer under FastAPI — every request passes through it. |
| **fastapi** | 0.98.0 | 0.115+ | **HIGH** | Inherits all Starlette CVEs. FastAPI 0.98.0 pins Starlette 0.27.x. Upgrading FastAPI pulls a fixed Starlette. |
| **jinja2** | 3.1.2 | 3.1.6+ | **MEDIUM** | CVE-2024-22195: XSS in `xmlattr` filter. CVE-2024-34064: sandbox escape via template expressions. Used by the poster/SSR system (Playwright renders Jinja templates). Sandbox escape is exploitable only if attacker-controlled template strings are rendered — currently templates are developer-authored, so risk is theoretical unless user input reaches a Jinja render. |
| **Pillow** | >=10.0.0 | 11.2+ | **MEDIUM** | Multiple buffer overflow CVEs in image parsing (TIFF, JPEG, WebP). Pillow processes user-uploaded photos at `POST /api/photos` and war media upload. A crafted image could trigger code execution in the Pillow C extensions. Docker container limits blast radius. |
| **requests** | 2.31.0 | 2.32+ | **LOW** | CVE-2024-35195: session cookies leaked cross-domain on redirects. Only used for outbound Discord webhook calls — low risk. |
| **uvicorn** | 0.23.1 | 0.34+ | **LOW** | No critical CVEs, but >18 months behind on HTTP/1.1 parsing hardening. |

### JavaScript Dependencies (Haven-UI Frontend)

| Package | Version | Status |
|---------|---------|--------|
| react | ^18.2.0 | Current major ✓ |
| vite | ^7.2.2 | Current major ✓ |
| axios | ^1.4.0 | ~2 minor behind, no critical CVEs |
| react-router-dom | ^6.20.1 | Current major ✓ |
| three | ^0.170.0 | Current ✓ |
| tailwindcss | ^3.4.18 | Current ✓ |

**JS verdict:** Frontend dependencies are reasonably current. No known critical CVEs.

### Priority

1. **python-multipart 0.0.6 → 0.0.20+** — Immediate. The ReDoS and header injection are internet-facing.
2. **fastapi + starlette** — Upgrade together. Fixes CORS bypass, multipart DoS, path traversal.
3. **Pillow** — Upgrade to latest 11.x. Buffer overflows in image parsing are exploitable via photo upload.
4. **jinja2** — Upgrade to 3.1.6+. Low urgency since templates are developer-authored.

### Action Item
Create a `requirements.txt` (or `pyproject.toml`) with pinned versions. The current state of "versions documented in CLAUDE.md but no lock file" means `pip install` on a fresh deploy pulls whatever's latest — which could be breaking, or could silently stay on the vulnerable version if cached.

---

## Phase 4 — Application-Level SAST

### 4.1 CORS Configuration

| Service | Config | Verdict |
|---------|--------|---------|
| **Haven-UI backend** | Explicit origin allowlist (6 domains), `allow_credentials=True` | **SAFE** ✓ — NOT `["*"]`. Origins: localhost dev, havenmap.online, Pi LAN IP. |
| **Travelers-Collective** | `allow_origins=["*"]`, `allow_credentials=True` | **VULNERABLE** — wildcard + credentials = any origin can make authenticated requests. Not yet deployed, but must fix before deployment. |
| **Haven-Exchange** | No CORSMiddleware configured | **NEEDS ATTENTION** — defaults to same-origin (safe), but needs explicit CORS before any cross-origin frontend is added. |
| **Grand Festival** | No CORSMiddleware configured | Same-origin default. Safe for current use. |
| **Travelers Archive** | No CORSMiddleware configured | Same-origin default. Safe. |

### 4.2 SQL Injection

**Pattern analysis across 15 route files:**

The codebase uses f-strings extensively for SQL construction, but with a critical distinction:
- **User-supplied VALUES are always parameterized** with `?` placeholders — verified across `approvals.py`, `discoveries.py`, `systems.py`, `regions.py`, `warroom.py`, `profiles.py`, `csv_import.py`, `analytics.py`.
- **F-strings are used for SQL STRUCTURE** (table names, column names, WHERE clause fragments like `AND s.discord_tag = ?`) — but these structural elements are always derived from hardcoded Python constants or validated enums, never from raw user input.
- **Example** (`systems.py:1340-1382`): `_build_advanced_filter_clauses()` constructs WHERE fragments with f-strings, but every column name is hardcoded at the call site. The actual filter VALUES go through `params.append(value)` → `?`.

**Verdict:** No SQL injection vulnerabilities found. The f-string pattern looks alarming at first glance but is safe because only developer-controlled identifiers are interpolated. Parameterized values are used consistently for all user input.

### 4.3 Path Traversal / File Upload

| Endpoint | File | Verdict |
|----------|------|---------|
| `POST /api/photos` (happy path) | `csv_import.py` | **SAFE** — `process_image()` generates its own filename (`secrets.token_hex(8).webp`) |
| `POST /api/photos` (Pillow failure fallback) | `csv_import.py:~71` | **VULNERABLE (LOW)** — Falls back to `dest = PHOTOS_DIR / filename` using the raw user-supplied filename. A crafted name like `../../config.py` could write outside PHOTOS_DIR. Mitigated by: (1) extension whitelist (`.jpg/.png/.webp/.gif`), (2) Docker container filesystem isolation, (3) the fallback only triggers when Pillow crashes on the image. |
| War media upload | `warroom.py:2930-2980` | **SAFE** — `new_filename = f"{secrets.token_hex(8)}.webp"` (never uses raw filename) |
| Archive media upload | `archive/app/routes/media.py:83-86` | **SAFE** — `stored_name = f"{secrets.token_urlsafe(16)}{ext}"` (random filename) |
| Grand Festival upload | `grand-festival/backend/routes/public.py:45-46` | **SAFE** — Has explicit `path.resolve()` + `path.parent != upload_root` guard |

### 4.4 Authentication & Authorization

**Auth pattern:** Consistent use of `get_session(session)` → session_data checks across all admin endpoints. Session is a signed cookie.

**Public write endpoints (by design — no auth required):**

| Endpoint | Purpose | Risk Assessment |
|----------|---------|-----------------|
| `POST /api/submit_system` | Submit system to approval queue | Safe — goes to pending queue, not live |
| `POST /api/submit_discovery` | Submit discovery to approval queue | Safe — pending queue |
| `POST /api/check_glyph_codes` | Validate glyph codes | Safe — read-only check |
| `POST /api/extractor/register` | Self-register for extractor API key | Safe — creates a personal key only |
| `POST /api/profiles/create` | Create user profile on first submission | Safe — member-tier only |
| `POST /api/profiles/claim` | Claim existing profile | Safe — requires username match |
| `POST /api/discoveries/{id}/view` | Increment view counter | Safe — no auth needed for view tracking |

**Rate limiting:** Intentionally removed in v1.43.1 (self-hosted, no longer behind ngrok). The public write endpoints above have **no rate limiting**. This is acceptable for current traffic levels but could be abused for queue flooding if the site gains significant traffic. Consider lightweight per-IP limiting on `submit_system` / `submit_discovery` if abuse occurs.

**Self-approval prevention:** `check_self_submission()` helper exists and is wired into all approval paths. Verified.

### 4.5 Debug Mode Exposure

| Service | Debug Setting | Risk |
|---------|--------------|------|
| `Planet_Atlas/main.py:1793` | `debug=True` | **SAFE** — local-only tool, never internet-facing |
| Haven-UI backend | No `debug=True` found | **SAFE** ✓ |
| Grand Festival | No `debug=True` found | **SAFE** ✓ |

### 4.6 Bot Token Security

| Bot | Token Handling | Verdict |
|-----|---------------|---------|
| The_Keeper | `dotenv` → `os.getenv('DISCORD_TOKEN')` | **SAFE** ✓ |
| Philbert-discord | `process.env.token` (line 2606) | **SAFE** ✓ (but webhook creds are hardcoded — see CRIT-02) |

### 4.7 Session Security

- Sessions use signed cookies (FastAPI/Starlette `SessionMiddleware`)
- Session timeout: 10 minutes inactivity (configurable)
- No `HttpOnly` / `Secure` / `SameSite` flags explicitly set — Starlette's SessionMiddleware defaults to `httponly=True, samesite='lax'`. `Secure` flag is NOT set by default — sessions could be intercepted on plain HTTP. Currently mitigated by Cloudflare enforcing HTTPS on the public domain, but the Pi's LAN interface (port 8005) serves plain HTTP.

### 4.8 Sensitive Data in Logs

- No credential logging patterns found in route handlers.
- Activity log (`db.add_activity_log`) records usernames and actions, not passwords or tokens.
- Audit log records approve/reject actions with reviewer identity — appropriate.

---

## Phase 5 — Executive Summary & Rotation Checklist

### Risk Matrix

| ID | Severity | Finding | Service | Status |
|----|----------|---------|---------|--------|
| CRIT-01 | **CRITICAL** | Tebex live API key hardcoded + in git history | The_Keeper | ROTATE NOW |
| CRIT-02 | **CRITICAL** | Discord webhook ID + token hardcoded + in git history | Philbert-discord | ROTATE NOW |
| HIGH-01 | **HIGH** | python-multipart 0.0.6 — ReDoS + header injection CVEs | Haven-UI backend | UPGRADE |
| HIGH-02 | **HIGH** | starlette 0.27.0 — CORS bypass + multipart DoS CVEs | Haven-UI backend | UPGRADE |
| HIGH-03 | **HIGH** | fastapi 0.98.0 — inherits all Starlette CVEs | Haven-UI backend | UPGRADE |
| HIGH-04 | **HIGH** | Grand Festival default admin password in compose | Grand Festival | CHANGE |
| HIGH-05 | **HIGH** | Travelers-Collective default passwords in compose | Travelers-Collective | CHANGE |
| HIGH-06 | **HIGH** | Haven-Exchange placeholder JWT secret | Haven-Exchange | CHANGE (before deploy) |
| MED-01 | **MEDIUM** | Jinja2 3.1.2 — sandbox escape CVE | Haven-UI backend | UPGRADE |
| MED-02 | **MEDIUM** | Pillow >=10.0.0 — buffer overflow CVEs in image parsing | Haven-UI backend | UPGRADE |
| MED-03 | **MEDIUM** | Path traversal in photo upload Pillow-failure fallback | Haven-UI backend | FIX |
| MED-04 | **MEDIUM** | Travelers-Collective CORS wildcard + credentials | Travelers-Collective | FIX (before deploy) |
| LOW-01 | **LOW** | Committed DB + user data in The_Keeper | The_Keeper | GITIGNORE |
| LOW-02 | **LOW** | No requirements.txt / dependency lock file | Haven-UI backend | CREATE |
| LOW-03 | **LOW** | No rate limiting on public write endpoints | Haven-UI backend | MONITOR |
| LOW-04 | **LOW** | Session cookie lacks `Secure` flag on LAN | Haven-UI backend | MONITOR |
| INFO-01 | **INFO** | requests 2.31.0 — cookie leak on redirect CVE | Haven-UI backend | LOW PRIORITY |
| INFO-02 | **INFO** | uvicorn 18+ months behind | Haven-UI backend | LOW PRIORITY |

### Immediate Rotation Checklist

**Do these TODAY — they're in git history and irreversible without rotation:**

1. **Tebex API Key** (`tx_live_c7f3247ac8aa28027e83e83e7f907192`)
   - Go to Tebex dashboard → API Keys → Regenerate
   - Update `The_Keeper/.env` with new key
   - Confirm old key returns 401
   - The old key is burned into git history forever — even going private won't help if any clone exists

2. **Discord Webhook** (ID `1437621723619917834`)
   - Go to Discord server → Settings → Integrations → Webhooks
   - Delete the webhook, create a new one
   - Update Philbert-discord to load from `.env`
   - Old webhook URL is in git history — it WILL be abused if the repo goes public

3. **Grand Festival admin password**
   - Change `ADMIN_PASSWORD` in the running container's env
   - Remove the hardcoded value from `docker-compose.yml`
   - Use a `.env` file or Docker secret

### Dependency Upgrade Path (Prioritized)

```
# Step 1: Create requirements.txt with current (vulnerable) versions
# Step 2: Upgrade in order of risk
pip install python-multipart>=0.0.20    # CRITICAL - ReDoS + header injection
pip install fastapi>=0.115.0            # HIGH - pulls fixed starlette
pip install Pillow>=11.0.0              # MEDIUM - buffer overflows
pip install jinja2>=3.1.6               # MEDIUM - sandbox escape
pip install requests>=2.32.0            # LOW
pip install uvicorn>=0.34.0             # LOW
# Step 3: Run the app, run existing tests, verify nothing broke
```

### What Was NOT Found (Positive Notes)

- **No SQL injection** — consistent parameterized queries throughout
- **No hardcoded Haven bot tokens** — both bots load from environment
- **No debug mode exposed** on internet-facing services
- **Good CORS config** on the main Haven-UI backend (explicit allowlist)
- **Good file upload security** on 4 of 5 upload paths (random filenames)
- **Self-approval prevention** working and consistently applied
- **Session cookies** use `httponly` and `samesite=lax` by default
- **Haven-UI frontend deps** are reasonably current with no critical CVEs

### Post-Audit: Git History Cleanup (Parker's Decision)

The Tebex key and webhook credentials are in git history. Options:
1. **BFG Repo-Cleaner** — rewrites history to remove the secrets. Breaks all existing clones' ability to cleanly pull. Best if the repo might ever go public.
2. **Do nothing + rotate** — if the repo stays private forever, rotating the secrets is sufficient. The old values in history become harmless.
3. **Go nuclear** — fresh repo with a squashed initial commit. Loses all history. Only if paranoid.

**Recommendation:** Rotate the secrets (mandatory regardless), then decide on BFG based on whether the repo will ever be public or shared beyond the current team.

---

*Audit complete. All findings are read-only observations. No code was modified. GATE — awaiting Parker's review before any remediation.*
