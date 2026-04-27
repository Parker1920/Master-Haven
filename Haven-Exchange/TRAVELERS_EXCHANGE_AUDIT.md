# Travelers Exchange — Code Audit Report

**Date:** 2026-04-26
**Codebase Location:** `Master-Haven/Haven-Exchange/`
**Live URL:** travelers-exchange.online (port 8010, Docker on Pi)

---

## Phase 1: Codebase Located

The Travelers Exchange lives at `Master-Haven/Haven-Exchange/` — a standalone FastAPI + SQLite + Jinja2 application, Dockerized on port 8010. Completely separate from the Haven discovery mapping system (Haven-UI on port 8005) and the real-money crypto trade-engine (`Master-Haven/trade-engine/`).

---

## Phase 2: Structural Inventory

### File Tree (non-cache, non-pyc)

```
Haven-Exchange/
├── Dockerfile                          # Python 3.11-slim, uvicorn on :8010
├── docker-compose.yml                  # Single service "economy", persistent ./data volume
├── requirements.txt                    # 8 deps (fastapi, sqlalchemy, bcrypt, jinja2, apscheduler…)
├── GUIDE.md                            # User-facing how-to guide
├── .gitignore
├── .python-version
├── data/
│   ├── .gitkeep
│   └── economy.db                      # SQLite — single production database
└── app/
    ├── __init__.py
    ├── main.py                         # FastAPI app, startup seeding, APScheduler (GDP + stock recalc every 24h)
    ├── config.py                       # Settings singleton (DB_PATH, wallet prefixes, BASE_RATE=500, currency name)
    ├── database.py                     # SQLAlchemy engine + SessionLocal + get_db dependency
    ├── models.py                       # 16 ORM models (568 lines)
    ├── auth.py                         # bcrypt passwords, session tokens (cookie-based), role dependencies
    ├── blockchain.py                   # SHA-256 hash-chained ledger engine, thread-safe tx creation
    ├── gdp.py                          # 4-pillar GDP calculation (treasury, tx volume, revenue, active citizens)
    ├── valuation.py                    # 3-pillar stock valuation (population, activity, cashflow)
    ├── wallet.py                       # Deterministic wallet address generation (SHA-256 truncated)
    ├── routes/
    │   ├── __init__.py
    │   ├── auth_routes.py              # POST /api/auth/{register,login,logout}
    │   ├── transaction_routes.py       # POST /api/transactions/transfer, GET /api/ledger
    │   ├── wallet_routes.py            # GET /api/wallet, /api/wallet/search, /api/wallet/{addr}
    │   ├── mint_routes.py              # World Mint admin: stats, execute, allocations, GDP, nation approve/suspend
    │   ├── nation_routes.py            # Nation apply, join/leave, members, distribute, distribute-bulk
    │   ├── shop_routes.py              # Shop CRUD, listing CRUD, purchase with cross-nation conversion
    │   ├── stock_routes.py             # Stock list, buy/sell, portfolio, rankings, history
    │   ├── bank_routes.py              # Bank CRUD, loan issue/pay/forgive, GlobalSettings management
    │   └── page_routes.py              # ALL Jinja2 HTML page renders (~3,533 lines)
    ├── static/
    │   ├── css/style.css
    │   └── js/app.js
    └── templates/                      # 32 Jinja2 HTML templates
        ├── base.html                   # Layout shell
        ├── landing.html, login.html, register.html, dashboard.html, settings.html
        ├── send.html, history.html, ledger.html, tx_detail.html
        ├── nations.html, nations_apply.html, nation_detail.html
        ├── nation/treasury.html, nation/distribute.html, nation/members.html
        ├── market.html, market_shop.html, market_buy.html
        ├── shop_create.html, shop_manage.html, shop_ipo.html
        ├── exchange.html, exchange_detail.html, exchange_trade.html, portfolio.html
        ├── bank_list.html, bank_create.html, bank_detail.html
        ├── loan_apply.html, loan_detail.html, loans_mine.html
        ├── wallet_lookup.html, wallet_search.html
        └── mint/dashboard.html, mint/settings.html, mint/stats.html
```

### Python Files Summary

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 210 | App init, startup seeding, schema migrations, APScheduler |
| `config.py` | 33 | Settings class (BASE_RATE=500, wallet prefixes, secret key) |
| `database.py` | 58 | SQLAlchemy engine, session factory, init_db() |
| `models.py` | 568 | 16 ORM models across users, nations, transactions, shops, stocks, banks, loans |
| `auth.py` | 172 | bcrypt, session tokens (7-day), get_current_user, require_login, require_role |
| `blockchain.py` | 375 | Hash-chained ledger, create_transaction (thread-safe), verify_chain, balance recompute |
| `gdp.py` | 392 | 4-pillar GDP engine (0.5x–2.0x multiplier), peer-relative normalization |
| `valuation.py` | 629 | 3-pillar stock valuation, nation + business scoring, ticker generation |
| `wallet.py` | 64 | SHA-256 deterministic address generation (TRV-, TRV-NATION-, TRV-BANK-) |
| `auth_routes.py` | 167 | Registration, login, logout (form-encoded, cookie auth) |
| `transaction_routes.py` | 162 | Transfer, tx lookup, public ledger (paginated) |
| `wallet_routes.py` | 198 | Wallet info, search, address lookup, address tx history |
| `mint_routes.py` | 631 | World Mint: stats, minting, allocations, nation approve/suspend, GDP |
| `nation_routes.py` | 447 | Nation CRUD, join/leave, distribute, bulk distribute |
| `shop_routes.py` | 384 | Shop/listing CRUD, purchase with GDP-aware cross-nation pricing |
| `stock_routes.py` | 548 | Stock list/detail, buy/sell (thread-locked), portfolio, rankings |
| `bank_routes.py` | 718 | Bank CRUD, loan issue/pay (burn split), loan forgive, global settings |
| `page_routes.py` | 3,533 | ALL HTML page rendering (Jinja2 template contexts) |
| **Total** | **~9,259** | |

### Database Schema (16 Tables)

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `users` | All accounts | wallet_address, nation_id, role, balance |
| `nations` | Gaming nations/guilds | treasury_address, treasury_balance, currency_name/code, gdp_score/multiplier |
| `transactions` | Immutable hash-chained ledger | tx_hash, prev_hash, tx_type, from/to_address, amount |
| `mint_allocations` | Monthly minting schedules | nation_id, period, member_count, base_rate, calculated/approved_amount |
| `shops` | Player-owned shops | owner_id, nation_id, total_sales, total_revenue |
| `shop_listings` | Individual products/services | shop_id, title, price (TC), category, is_available |
| `stocks` | Tradeable nation/business stocks | ticker, stock_type, entity_id, total/available_shares, current/previous_price |
| `stock_holdings` | User share ownership | user_id, stock_id, shares, avg_buy_price |
| `stock_transactions` | Trade records | stock_id, buyer/seller_id, shares, price_per_share, tx_type |
| `stock_valuations` | Daily valuation snapshots | stock_id, 3 pillar scores, composite_score, calculated_price |
| `gdp_snapshots` | Daily GDP snapshots | nation_id, 4 pillar scores, composite_score, gdp_multiplier |
| `sessions` | Login sessions | token (PK), user_id, expires_at |
| `global_settings` | Singleton economy config | burn_rate_bps, interest_rate_cap_bps |
| `banks` | Nation-scoped banks | nation_id, owner_id, wallet_address, balance, total_loaned/burned |
| `loans` | Active/closed loans | bank_id, borrower_id, principal, outstanding, interest_rate, burn_rate_snapshot |
| `loan_payments` | Payment records w/ burn tracking | loan_id, amount, burn_amount, bank_amount, balance_after, tx_hash |

### Transaction Types on the Ledger

`GENESIS`, `MINT`, `DISTRIBUTE`, `TRANSFER`, `PURCHASE`, `BURN`, `TAX`, `STOCK_BUY`, `STOCK_SELL`, `LOAN`, `LOAN_PAYMENT`, `LOAN_FORGIVE`

### User Roles

| Role | Count | Capabilities |
|------|-------|-------------|
| `citizen` | Default | Send TC, shop, trade stocks, take loans |
| `nation_leader` | Per nation | All citizen + distribute from treasury, create banks, manage nation |
| `world_mint` | 1 (admin) | Mint TC, approve nations, manage allocations, GDP recalc, global settings |

### Infrastructure

- **Runtime:** Python 3.11-slim Docker container, uvicorn, single worker
- **Database:** SQLite `data/economy.db` (persistent Docker volume)
- **Auth:** bcrypt passwords, 64-char hex session tokens in httponly cookies (7-day expiry)
- **Scheduling:** APScheduler background jobs — GDP recalc + stock price recalc every 24h
- **Thread safety:** `_tx_lock` (threading.Lock) serializes all ledger writes; `_stock_lock` serializes stock trades

---

## Phase 3: Spec Reconciliation

### 1. Currency Naming

**Status: IMPLEMENTED ✅**

The base currency is "Travelers Coin" (TC), configured in `config.py`:
- `CURRENCY_NAME = "Travelers Coin"`, `CURRENCY_SHORT = "TC"`
- Wallet prefix: `TRV-` (changed from older `HVN-` prefix — startup migration handles rename)
- Nation wallet prefix: `TRV-NATION-`
- Bank wallet prefix: `TRV-BANK-`
- World Mint address: `TRV-00000000`

Each nation defines its own `currency_name` and `currency_code` (2–5 uppercase alpha, unique). Display conversion uses `tc_to_national()` which divides TC by the GDP multiplier. Templates show dual pricing (national coin + TC equivalent) for cross-nation transactions.

### 2. Keeper Coin-Award Flow (Discord Bot Integration)

**Status: NOT IMPLEMENTED ❌**

There is zero Keeper Discord bot integration in the codebase. No webhook endpoints, no bot-triggered minting, no coin-award automation. The only Discord reference is the `discord_invite` field on the Nation model (a simple link for nation discovery pages).

The Keeper bot (`keeper-discord-bot-main/`) in the Master-Haven monorepo is wired to the Haven discovery API, not to the Travelers Exchange. There is no `/api/bot/award` or equivalent endpoint. All currency enters the system exclusively through World Mint manual minting or allocation execution.

**Gap:** If the spec calls for automated coin awards based on Discord activity (e.g., Haven discovery submissions triggering TC rewards), that entire pipeline is missing — no API endpoint, no bot integration, no event-driven minting.

### 3. Bank Role Scope

**Status: IMPLEMENTED ✅ — Nation-scoped**

Banks are strictly scoped to nations:
- Nation leaders create banks (`POST /api/banks`), max 4 per nation
- Bank operators must be members of the same nation
- Borrowers must be members of the same nation as the bank
- Borrowers limited to 1 active loan at a time (across all banks)
- Nation leaders can forgive loans; bank operators issue and manage them
- World Mint sets global `burn_rate_bps` and `interest_rate_cap_bps` via `GlobalSettings`

**Loan repayment flow:** Payment splits into bank portion (returns to bank reserves) and burn portion (destroyed via BURN tx to World Mint address). Burn rate is snapshot at loan creation time so mid-loan rate changes don't retroactively affect existing loans.

**Note:** The `interest_rate` field exists on Loan but is only a snapshot of the cap — there's no actual interest accrual logic. Outstanding balance never grows; it only decreases via payments. Interest is effectively informational/decorative.

### 4. Functional Business Gating

**Status: IMPLEMENTED ✅**

Shop creation requires:
- User must be a member of an approved nation
- One shop per user (enforced by unique `owner_id`)
- Shop name cannot be empty

IPO eligibility requires:
- 10+ completed sales (`IPO_MIN_SALES = 10`)
- 30+ days since shop creation (`IPO_MIN_DAYS = 30`)
- 100–1,000 shares per IPO

Business stock purchase gating:
- Buyer must be a member of the shop's nation (nation-locked investment)
- Nation stocks have no such restriction (anyone can buy)

### 5. Departments

**Status: NOT IMPLEMENTED ❌**

There are zero references to "departments" anywhere in the codebase. No models, no routes, no templates. If the spec calls for organizational departments within nations (e.g., Treasury Dept, Defense Dept, Commerce Dept), the entire feature is missing.

### 6. Stock Market

**Status: IMPLEMENTED ✅**

Two stock types exist:
- **Nation stocks:** Auto-created when a nation is approved. 10,000 shares at 10 TC base price. Anyone can buy. Proceeds go to nation treasury.
- **Business stocks:** Created via shop IPO. 100–1,000 shares at 5 TC base price. Same-nation members only.

Valuation engine runs every 24h (APScheduler) with three pillars normalized against peer maxes:
- Nations: population, activity (active members + tx count), cashflow
- Businesses: unique customers, activity (purchases + listings), revenue
- Price formula: `base_price × composite_score / 50` (min 1 TC)

Trading is thread-locked (`_stock_lock`). Buy/sell creates blockchain transactions (STOCK_BUY/STOCK_SELL). Selling triggers entity buyback (nation treasury or shop owner pays). Portfolio tracking with average buy price and gain/loss.

### 7. World Mint

**Status: IMPLEMENTED ✅**

World Mint is the sole admin role with full economy control:
- **Direct minting:** Mint TC to any wallet or treasury (`POST /api/mint/execute`)
- **Allocation cycle:** Calculate → Approve → Execute. Formula: `member_count × BASE_RATE (500)` per nation per month. Can override approved amount.
- **Batch execution:** `POST /api/mint/execute-all-approved` for one-click distribution
- **Nation governance:** Approve/suspend nations
- **GDP management:** Force recalculation, view history
- **Global settings:** Set burn rate and interest rate cap (basis points)
- **Economy dashboard:** Total supply, tx count, users, nations, 30d active, chain validity, GDP overview

The admin seed user is `username=admin`, `password=changeme` with `wallet_address=TRV-00000000`. Created on startup if not exists.

### 8. Economic Health / GDP

**Status: IMPLEMENTED ✅**

GDP multiplier (0.5x–2.0x) per nation based on four equally-weighted pillars:

| Pillar | Weight | Metric | Source |
|--------|--------|--------|--------|
| Treasury Health | 25% | Treasury balance / member count | `nations.treasury_balance` ÷ active members |
| Transaction Volume | 25% | 30-day tx count involving nation addresses | `transactions` table |
| Business Revenue | 25% | 30-day shop purchase revenue | `transactions` WHERE type=PURCHASE to shop owner |
| Active Citizens | 25% | % of members active in 30 days | `users.last_active` |

Each pillar is peer-normalized (0–100) against the max value across all approved nations. Composite average maps to multiplier range 50–200 (stored as int × 100).

Exchange rate: `1 NationCoin = (gdp_multiplier / 100) TC`. Cross-nation purchases show dual pricing. GDP snapshots stored daily for historical charting.

Auto-recalculation triggers: APScheduler every 24h, plus `maybe_recalculate_gdp()` on page loads if stale.

### 9. Blockchain / Ledger

**Status: IMPLEMENTED ✅ (simulated, not real blockchain)**

The "blockchain" is a simulated SHA-256 hash chain in SQLite:
- Each transaction hashes `prev_hash + from + to + amount + timestamp + nonce`
- Thread-locked writes guarantee linear chain ordering
- Genesis block on first startup
- `verify_chain()` walks the full chain validating prev_hash linkage (cannot fully verify hash recomputation because raw ISO timestamp isn't stored — acknowledged in code comments)
- `get_balance_from_chain()` recomputes any address balance from scratch (incoming - outgoing)
- 12 transaction types covering all money flows

Balance management is dual-tracked: cached on `users.balance` / `nations.treasury_balance` / `banks.balance` for fast reads, and recomputable from the ledger for audit verification.

---

## Notable Findings

### Security Observations

1. **Hardcoded secret key:** `config.py` has `SECRET_KEY = "travelers-exchange-secret-change-me"`. This is used as salt for wallet address generation. Should be in `.env`.

2. **Default admin password:** `changeme` — fine for dev, needs rotation in production.

3. **No CSRF protection:** Form-based auth routes accept raw POST with no CSRF token. The httponly + samesite=lax cookie mitigates most vectors but isn't complete.

4. **Transfer endpoint uses `get_current_user` not `require_login`:** `POST /api/transactions/transfer` uses `get_current_user` which returns `None` for unauthenticated users instead of blocking. If `current_user` is None, the endpoint would crash on `current_user.wallet_address`. Should use `require_login`.

5. **No rate limiting:** No request rate limits on any endpoint (auth, minting, trading).

### Architectural Notes

1. **`page_routes.py` is 3,533 lines** — the largest file by far. Contains all HTML page rendering logic interleaved with business logic (form handling, redirects, GDP recalc triggers). This is the primary maintenance burden.

2. **No interest accrual on loans:** The `interest_rate` field is stored but never used for calculation. Loan `outstanding` only decreases via payments. This may be intentional (interest-free loans with burn as the "cost of borrowing") but should be documented.

3. **Stock sell assumes entity can afford buyback:** When a user sells shares, the entity (nation treasury or shop owner) pays at current market price. If the treasury/owner has insufficient balance, the sell fails with a ValueError from `create_transaction`. There's no liquidity pool or market maker.

4. **No nation stock auto-creation on approval:** The `approve_nation` endpoint in `mint_routes.py` does NOT call `create_nation_stock()`. The stock creation happens in `page_routes.py` as a side effect of the HTML form handler. The API-only path misses it. (Verified: `approve_nation` in mint_routes sets status to approved and promotes leader, but does not create stock.)

5. **Balances stored as integers:** All amounts (TC, prices, balances) are integers. No fractional TC. This is clean and avoids floating-point issues. GDP conversion to national coins returns floats for display only.

6. **`member_count` is manually tracked:** `nation.member_count` is incremented/decremented on join/leave rather than computed via COUNT query. This can drift if any code path modifies `user.nation_id` without updating the counter.
