# TRAVELERS EXCHANGE CODE AUDIT — V2

**Date:** 2026-04-26
**Auditor:** Claude (read-only reconnaissance)
**Scope:** 8 locked design decision categories — nothing else

---

## 1. Codebase Location

**Path:** `Master-Haven/Haven-Exchange/`
**Single candidate found.** No ambiguity. Confirmed by presence of `Dockerfile`, `docker-compose.yml`, `app/main.py` (FastAPI), `app/models.py` (SQLAlchemy ORM), `app/blockchain.py`, `app/gdp.py`, `data/economy.db` (SQLite).

---

## 2. Structural Inventory

### A. File Tree

```
Haven-Exchange/
├── .gitignore                       (509 B,  2026-03-11)
├── .python-version                  (8 B,    2026-03-11)
├── Dockerfile                       (642 B,  2026-03-11)
├── docker-compose.yml               (552 B,  2026-03-12)
├── requirements.txt                 (160 B,  2026-03-16)
├── GUIDE.md                         (5,217 B, 2026-03-12)
├── TRAVELERS_EXCHANGE_AUDIT.md      (18,269 B, 2026-04-26) ← v1 audit
├── data/
│   ├── .gitkeep                     (0 B)
│   └── economy.db                   (98,304 B, 2026-03-12)
├── app/
│   ├── __init__.py                  (0 B)
│   ├── config.py                    (803 B,  33 lines)
│   ├── database.py                  (1,507 B, 57 lines)
│   ├── auth.py                      (5,201 B, 171 lines)
│   ├── wallet.py                    (1,825 B, 63 lines)
│   ├── blockchain.py                (14,382 B, 374 lines)
│   ├── gdp.py                       (13,149 B, 391 lines)
│   ├── valuation.py                 (19,860 B, 628 lines)
│   ├── models.py                    (23,212 B, 567 lines)
│   ├── main.py                      (7,974 B, 209 lines)
│   ├── routes/
│   │   ├── __init__.py              (0 B)
│   │   ├── auth_routes.py           (4,991 B, 166 lines)
│   │   ├── transaction_routes.py    (5,875 B, 161 lines)
│   │   ├── wallet_routes.py         (6,726 B, 197 lines)
│   │   ├── nation_routes.py         (14,765 B, 446 lines)
│   │   ├── shop_routes.py           (14,217 B, 383 lines)
│   │   ├── stock_routes.py          (18,805 B, 547 lines)
│   │   ├── bank_routes.py           (26,739 B, 717 lines)
│   │   ├── mint_routes.py           (20,579 B, 630 lines)
│   │   └── page_routes.py           (115,179 B, 3,533 lines)
│   ├── templates/
│   │   ├── base.html                (4,567 B)
│   │   ├── landing.html             (3,019 B)
│   │   ├── login.html               (1,473 B)
│   │   ├── register.html            (3,139 B)
│   │   ├── dashboard.html           (8,748 B)
│   │   ├── settings.html            (4,336 B)
│   │   ├── send.html                (2,312 B)
│   │   ├── history.html             (6,518 B)
│   │   ├── ledger.html              (5,211 B)
│   │   ├── tx_detail.html           (7,287 B)
│   │   ├── nations.html             (1,986 B)
│   │   ├── nations_apply.html       (4,835 B)
│   │   ├── nation_detail.html       (11,633 B)
│   │   ├── nation/treasury.html     (6,982 B)
│   │   ├── nation/distribute.html   (4,846 B)
│   │   ├── nation/members.html      (3,572 B)
│   │   ├── market.html              (4,795 B)
│   │   ├── market_shop.html         (3,397 B)
│   │   ├── market_buy.html          (3,135 B)
│   │   ├── shop_create.html         (1,400 B)
│   │   ├── shop_manage.html         (6,937 B)
│   │   ├── shop_ipo.html            (3,151 B)
│   │   ├── exchange.html            (3,436 B)
│   │   ├── exchange_detail.html     (10,743 B)
│   │   ├── exchange_trade.html      (4,736 B)
│   │   ├── portfolio.html           (3,662 B)
│   │   ├── wallet_search.html       (2,562 B)
│   │   ├── wallet_lookup.html       (6,835 B)
│   │   ├── bank_list.html           (3,415 B)
│   │   ├── bank_create.html         (1,774 B)
│   │   ├── bank_detail.html         (4,882 B)
│   │   ├── loan_apply.html          (3,325 B)
│   │   ├── loan_detail.html         (4,715 B)
│   │   ├── loans_mine.html          (4,145 B)
│   │   ├── mint/dashboard.html      (14,331 B)
│   │   ├── mint/stats.html          (6,069 B)
│   │   └── mint/settings.html       (2,718 B)
│   └── static/
│       ├── css/style.css            (48,057 B)
│       └── js/app.js                (22,877 B)
```

**Total Python:** 9,273 lines across 20 files (18 non-empty).
**Total templates:** 37 HTML files.
**Total static:** 2 files (1 CSS, 1 JS).

### B. Python File Detail

**app/config.py** (33 lines)
Imports: none external. Class: `Settings`. No routes. Defines: `DB_PATH`, `SECRET_KEY`, `WALLET_PREFIX="TRV-"`, `NATION_WALLET_PREFIX="TRV-NATION-"`, `WORLD_MINT_ADDRESS="TRV-00000000"`, `BASE_RATE=500`, `SESSION_EXPIRY_DAYS=7`, `CURRENCY_NAME="Travelers Coin"`, `CURRENCY_SHORT="TC"`.

**app/database.py** (57 lines)
Imports: `os`, `sqlalchemy`. Class: `Base(DeclarativeBase)`. Functions: `init_db()`, `get_db()`. No routes.

**app/auth.py** (171 lines)
Imports: `random`, `secrets`, `datetime`, `bcrypt`, `fastapi`, `sqlalchemy`. Functions: `hash_password()`, `verify_password()`, `create_session()`, `delete_session()`, `get_current_user()`, `require_login()`, `require_role()`. No routes.

**app/wallet.py** (63 lines)
Imports: `hashlib`. Functions: `generate_wallet_address()`, `generate_nation_treasury_address()`, `generate_bank_wallet_address()`. No routes.

**app/blockchain.py** (374 lines)
Imports: `hashlib`, `secrets`, `threading`, `datetime`, `sqlalchemy`. Constants: `GENESIS_HASH`, `_tx_lock`, `_VALID_TX_TYPES={MINT, DISTRIBUTE, TRANSFER, PURCHASE, BURN, TAX, GENESIS, STOCK_BUY, STOCK_SELL, LOAN, LOAN_PAYMENT, LOAN_FORGIVE}`. Functions: `compute_tx_hash()`, `get_last_hash()`, `create_genesis_block()`, `create_transaction()`, `get_transaction_by_hash()`, `get_transactions_for_address()`, `get_all_transactions()`, `verify_chain()`, `get_balance_from_chain()`. No routes.

**app/gdp.py** (391 lines)
Imports: `datetime`, `sqlalchemy`. Constants: `GDP_MIN=50`, `GDP_MAX=200`. Functions: `_calculate_nation_gdp()`, `_norm()`, `_gather_gdp_maxes()`, `recalculate_all_gdp()`, `maybe_recalculate_gdp()`, `get_gdp_multiplier_float()`, `tc_to_national()`, `national_to_tc()`, `format_currency()`. No routes.

**app/valuation.py** (628 lines)
Imports: `re`, `threading`, `datetime`, `sqlalchemy`. Constants: `_stock_lock`, `NATION_BASE_PRICE=10`, `BUSINESS_BASE_PRICE=5`, `NATION_TOTAL_SHARES=10000`, `BUSINESS_MIN_SHARES=100`, `BUSINESS_MAX_SHARES=1000`, `IPO_MIN_SALES=10`, `IPO_MIN_DAYS=30`. Functions: `generate_ticker()`, `create_nation_stock()`, `create_business_stock()`, `_score_nation_stock()`, `_score_business_stock()`, `_gather_nation_maxes()`, `_gather_business_maxes()`, `recalculate_all_prices()`, `maybe_recalculate()`. No routes.

**app/models.py** (567 lines)
Imports: `datetime`, `sqlalchemy`. 16 ORM classes: `User`, `Nation`, `Transaction`, `MintAllocation`, `Shop`, `ShopListing`, `Stock`, `StockHolding`, `StockTransaction`, `StockValuation`, `GdpSnapshot`, `Session_`, `GlobalSettings`, `Bank`, `Loan`, `LoanPayment`. No routes.

**app/main.py** (209 lines)
Imports: `os`, `bcrypt`, `fastapi`, `apscheduler`, plus all app modules. Functions: `_run_schema_migrations()`, `on_startup()`, `start_scheduler()`, `stop_scheduler()`. Routes: `GET /health`. Seeds admin user (password "changeme"), genesis block, GlobalSettings (burn_rate_bps=1000, interest_rate_cap_bps=2000). APScheduler: GDP + stock recalc every 24h.

**app/routes/auth_routes.py** (166 lines)
Routes: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`.

**app/routes/transaction_routes.py** (161 lines)
Routes: `POST /api/transactions/transfer`, `GET /api/transactions/{tx_hash}`, `GET /api/ledger`.

**app/routes/wallet_routes.py** (197 lines)
Routes: `GET /api/wallet`, `GET /api/wallet/search`, `GET /api/wallet/{address}`, `GET /api/wallet/{address}/transactions`.

**app/routes/nation_routes.py** (446 lines)
Routes: `POST /api/nations/apply`, `GET /api/nations`, `POST /api/nations/{nation_id}/join`, `POST /api/nations/{nation_id}/leave`, `GET /api/nations/{nation_id}/members`, `POST /api/nations/{nation_id}/distribute`, `POST /api/nations/{nation_id}/distribute-bulk`.

**app/routes/shop_routes.py** (383 lines)
Routes: `GET /api/shops`, `GET /api/shops/{shop_id}`, `POST /api/shops`, `POST /api/shops/{shop_id}/listings`, `POST /api/shops/{shop_id}/listings/{listing_id}/buy`, `PUT /api/shops/{shop_id}/listings/{listing_id}`.

**app/routes/stock_routes.py** (547 lines)
Routes: `GET /api/stocks`, `GET /api/stocks/portfolio`, `GET /api/stocks/rankings`, `GET /api/stocks/{ticker}`, `GET /api/stocks/{ticker}/history`, `POST /api/stocks/{ticker}/buy`, `POST /api/stocks/{ticker}/sell`.

**app/routes/bank_routes.py** (717 lines)
Routes: `POST /api/banks`, `GET /api/banks/nation/{nation_id}`, `POST /api/banks/{bank_id}/deactivate`, `GET /api/banks/{bank_id}`, `GET /api/banks/{bank_id}/loans`, `POST /api/banks/{bank_id}/loans`, `POST /api/banks/{bank_id}/loans/{loan_id}/forgive`, `GET /api/loans/mine`, `POST /api/loans/{loan_id}/pay`, `GET /api/mint/settings`, `POST /api/mint/settings`.

**app/routes/mint_routes.py** (630 lines)
Routes: `GET /api/mint/stats`, `POST /api/mint/execute`, `GET /api/mint/allocations`, `POST /api/mint/allocations/{allocation_id}/approve`, `POST /api/mint/nations/{nation_id}/approve`, `POST /api/mint/nations/{nation_id}/suspend`, `POST /api/mint/calculate-allocations`, `POST /api/mint/allocations/{allocation_id}/execute`, `POST /api/mint/execute-all-approved`, `POST /api/mint/recalculate-gdp`, `GET /api/mint/gdp-history`.

**app/routes/page_routes.py** (3,533 lines)
67 HTML page routes serving all Jinja2 templates. All user-facing UI. Includes form POST handlers that duplicate API logic for server-side rendering (nation apply, send, shop create, stock buy/sell, loan apply/pay, mint execute, settings update). Notable: `create_nation_stock()` is called from the page route `POST /mint/nations/{nation_id}/approve` (line 2113), NOT from the API route `POST /api/mint/nations/{nation_id}/approve` in mint_routes.py.

### C. Database Models — Full Schema

**users** — `id` (PK, int), `username` (str, unique), `password_hash` (str), `email` (str, nullable), `wallet_address` (str, unique), `display_name` (str, nullable), `nation_id` (FK→nations.id, nullable), `role` (str, default "citizen"), `balance` (int, default 0), `created_at` (datetime), `last_active` (datetime, nullable), `is_active` (bool, default True).

**nations** — `id` (PK, int), `name` (str, unique), `leader_id` (FK→users.id), `treasury_address` (str, unique), `treasury_balance` (int, default 0), `member_count` (int, default 0), `description` (text, nullable), `discord_invite` (str, nullable), `game` (str, nullable), `status` (str, default "pending"), `approved_at` (datetime, nullable), `created_at` (datetime), `currency_name` (str, nullable), `currency_code` (str, nullable), `gdp_score` (int, default 50), `gdp_multiplier` (int, default 100), `gdp_last_calculated` (datetime, nullable).

**transactions** — `id` (PK, int), `tx_hash` (str, unique), `prev_hash` (str), `tx_type` (str), `from_address` (str), `to_address` (str), `amount` (int), `fee` (int, default 0), `memo` (text, nullable), `nonce` (str), `status` (str, default "confirmed"), `created_at` (datetime).

**mint_allocations** — `id` (PK, int), `nation_id` (FK→nations.id), `period` (str), `member_count` (int), `base_rate` (int), `calculated_amount` (int), `approved_amount` (int, nullable), `status` (str, default "pending"), `approved_at` (datetime, nullable), `distributed_at` (datetime, nullable), `created_at` (datetime).

**shops** — `id` (PK, int), `owner_id` (FK→users.id, unique), `nation_id` (FK→nations.id), `name` (str), `description` (text, nullable), `is_active` (bool, default True), `total_sales` (int, default 0), `total_revenue` (int, default 0), `created_at` (datetime).

**shop_listings** — `id` (PK, int), `shop_id` (FK→shops.id), `title` (str), `description` (text, nullable), `price` (int), `category` (str, default "other"), `is_available` (bool, default True), `created_at` (datetime).

**stocks** — `id` (PK, int), `ticker` (str, unique), `name` (str), `stock_type` (str: "nation"|"business"), `entity_id` (int), `total_shares` (int), `available_shares` (int), `current_price` (int), `previous_price` (int, default 0), `last_valued_at` (datetime, nullable), `created_at` (datetime), `is_active` (bool, default True).

**stock_holdings** — `id` (PK, int), `user_id` (FK→users.id), `stock_id` (FK→stocks.id), `shares` (int, default 0), `avg_buy_price` (int, default 0), `acquired_at` (datetime). Unique constraint: `(user_id, stock_id)`.

**stock_transactions** — `id` (PK, int), `stock_id` (FK→stocks.id), `buyer_id` (FK→users.id, nullable), `seller_id` (FK→users.id, nullable), `shares` (int), `price_per_share` (int), `total_cost` (int), `tx_type` (str: "BUY"|"SELL"|"IPO"), `created_at` (datetime).

**stock_valuations** — `id` (PK, int), `stock_id` (FK→stocks.id), `population_score` (int), `activity_score` (int), `cashflow_score` (int), `composite_score` (int), `calculated_price` (int), `snapshot_date` (str), `created_at` (datetime).

**gdp_snapshots** — `id` (PK, int), `nation_id` (FK→nations.id), `treasury_score` (int), `activity_score` (int), `revenue_score` (int), `citizens_score` (int), `composite_score` (int), `gdp_multiplier` (int, default 100), `snapshot_date` (str), `created_at` (datetime).

**sessions** — `id` (PK, str = token), `user_id` (FK→users.id), `created_at` (datetime), `expires_at` (datetime).

**global_settings** — `id` (PK, int, default 1), `burn_rate_bps` (int, default 1000), `interest_rate_cap_bps` (int, default 2000), `updated_at` (datetime).

**banks** — `id` (PK, int), `nation_id` (FK→nations.id), `owner_id` (FK→users.id), `name` (text), `wallet_address` (text, unique), `balance` (int, default 0), `total_loaned` (int, default 0), `total_burned` (int, default 0), `is_active` (bool, default True), `created_at` (datetime).

**loans** — `id` (PK, int), `bank_id` (FK→banks.id), `borrower_id` (FK→users.id), `principal` (int), `outstanding` (int), `interest_rate` (int), `burn_rate_snapshot` (int), `status` (text, default "active"), `memo` (text, nullable), `opened_at` (datetime), `closed_at` (datetime, nullable).

**loan_payments** — `id` (PK, int), `loan_id` (FK→loans.id), `amount` (int), `burn_amount` (int), `bank_amount` (int), `balance_after` (int), `tx_hash` (text), `created_at` (datetime).

**Total: 16 tables.**

### D. Jinja2 Templates

37 HTML templates across 3 directories: `templates/` (root: 27 files), `templates/mint/` (3 files), `templates/nation/` (3 files). Plus `base.html` as the shared layout.

### E. Dockerfile & Docker Compose

**Dockerfile:** Python 3.11-slim, copies requirements.txt + app code, installs curl for healthcheck, exposes port 8010, runs uvicorn on 0.0.0.0:8010.

**docker-compose.yml:** Single service `travelers-exchange` (container name `economy`), builds from `.`, maps port 8010:8010, persistent volume `./data:/app/data`, healthcheck via curl on /health every 30s, restart unless-stopped.

### F. Static Assets

`app/static/css/style.css` (48,057 B) — Full custom CSS framework with dark theme, custom properties, grid system, component styles (cards, badges, tables, forms, alerts, modals, progress bars). No external CSS framework.

`app/static/js/app.js` (22,877 B) — Client-side JS for: form submission interception, confirmation dialogs, wallet address copy, auto-search/autocomplete, stock chart rendering, bulk distribution UI, toast notifications, mobile nav toggle.

---

## 3. Reconciliation Table

### 1. NAMING & IDENTITY

| Decision | Status | Evidence |
|----------|--------|----------|
| Wallet prefix is "TRV-" for personal wallets | **IMPLEMENTED** | `config.py:15` → `WALLET_PREFIX = "TRV-"`. `wallet.py:28` → `f"{settings.WALLET_PREFIX}{short_hash}"`. |
| Nation wallet prefix is "TRV-NATION-" | **IMPLEMENTED** | `config.py:16` → `NATION_WALLET_PREFIX = "TRV-NATION-"`. `wallet.py:46` → `f"{settings.NATION_WALLET_PREFIX}{short_hash}"`. |
| Bank wallet prefix is "TRV-BANK-" | **IMPLEMENTED** | `wallet.py:63` → `return f"TRV-BANK-{short_hash}"`. Note: hardcoded string, not from `config.py` (config only defines `WALLET_PREFIX` and `NATION_WALLET_PREFIX`, not a `BANK_WALLET_PREFIX`). |
| World Mint address pattern | **IMPLEMENTED** | `config.py:20` → `WORLD_MINT_ADDRESS = "TRV-00000000"`. Fixed address, not generated. |
| Underlying currency identifier (TRV or TC) is uniform across nations | **IMPLEMENTED** | `config.py:29-30` → `CURRENCY_NAME = "Travelers Coin"`, `CURRENCY_SHORT = "TC"`. All internal balances stored as integer TC. National currencies are display-layer conversions via GDP multiplier. `gdp.py:349-368` handles `tc_to_national()` and `national_to_tc()`. |
| Nations table has currency_display_name and currency_ticker fields | **IMPLEMENTED** | `models.py:91-92` → `currency_name` (equivalent to display name) and `currency_code` (equivalent to ticker). Validated as 2-5 uppercase alpha in `nation_routes.py:103`. |
| Templates render transactions with per-viewer's nation localization | **IMPLEMENTED** | `page_routes.py:90-125` → `_base_context()` resolves the viewing user's nation, computes `user_currency` dict (code, name, gdp, gdp_multiplier) and `user_balance_national`, injects `tc_to_national` function into template context. Dashboard, treasury, market, shop, and wallet templates use these for dual TC/national display. |

### 2. KEEPER BOT INTEGRATION

| Decision | Status | Evidence |
|----------|--------|----------|
| API endpoint for external bot to award coins | **MISSING** | No endpoint accepting nation_id + member + amount + reason. No bot-facing API exists. The only coin creation path is `POST /api/mint/execute` (requires `world_mint` session cookie — not API-key-based, not bot-compatible). |
| Awards drawn from nation treasury | **MISSING** | No award mechanism exists. |
| Per-nation, per-department rate configuration | **MISSING** | No department concept. No per-nation rate config for bot awards. |
| keeper_enabled flag per nation | **MISSING** | No such field on the Nation model or anywhere in the codebase. |

**Summary: Entire Keeper bot integration is absent.** The only Discord reference is `nations.discord_invite` (a URL string for the nation profile page).

### 3. BANKS & LENDING

| Decision | Status | Evidence |
|----------|--------|----------|
| Banks table exists | **IMPLEMENTED** | `models.py:446-486` → `Bank` model with `id`, `nation_id`, `owner_id`, `name`, `wallet_address`, `balance`, `total_loaned`, `total_burned`, `is_active`, `created_at`. |
| Max 4 banks per nation enforced | **IMPLEMENTED** | `bank_routes.py:97-101` → `bank_count = ... count(Bank.id) ... where(Bank.nation_id == nation.id)`, `if bank_count >= 4: raise HTTPException(... "Maximum of 4 banks per nation reached.")`. |
| NL-appointed bank operators | **IMPLEMENTED** | `bank_routes.py:86-87` → `if current_user.role not in ("nation_leader", "world_mint"): raise HTTPException(... "Only nation leaders can create banks.")`. Payload takes `owner_user_id`, validated as nation member at lines 109-118. |
| Treasury can also issue loans (lender_type field or equivalent abstraction) | **MISSING** | Loans are exclusively bank-issued. `Loan.bank_id` is a required FK to `banks`. No `lender_type` field. No mechanism for the nation treasury to directly issue loans. The treasury can only distribute (DISTRIBUTE tx type), not lend. |
| Loan repayment burn implemented | **IMPLEMENTED** | `bank_routes.py:584-626` → Payment split into `burn_amount` and `bank_amount`. Burn sent to `settings.WORLD_MINT_ADDRESS` as BURN tx. |
| Burn rate is 10% of interest paid | **CONFLICTS** | The burn rate is 10% of the **total payment amount**, not 10% of interest. `bank_routes.py:585` → `burn_amount = math.floor(amount * loan.burn_rate_snapshot / 10000)`. The code burns a percentage of every payment dollar, not specifically the interest portion. There is no interest accrual calculation anywhere — `loan.outstanding` is set equal to `loan.principal` at creation and payments reduce it directly. Interest is never computed or added to the balance. |
| Burn split is 20% during payments / 80% at close | **CONFLICTS** | The burn split is **uniform** at the snapshot burn rate (default 10%) on every payment. There is no differential rate between mid-loan payments and final payment. `burn_amount = floor(amount * burn_rate_snapshot / 10000)` applies identically regardless of whether the payment closes the loan or not. No 20/80 split exists. |
| 100% interest cap on loans (max debt = 2× principal) | **PARTIAL** | `GlobalSettings.interest_rate_cap_bps` defaults to 2000 (20% annual). This is snapshotted into `Loan.interest_rate` at creation (`bank_routes.py:413`). However, **interest is never actually accrued**. The `outstanding` balance never increases — it only decreases via payments. The cap exists as a stored field but has no enforcement mechanism because there's no interest calculation engine. |

### 4. BUSINESSES

| Decision | Status | Evidence |
|----------|--------|----------|
| Businesses table has status field (pending/approved/rejected) | **MISSING** | There is no `businesses` table. The closest entity is `shops`, which has `is_active` (bool) but no approval workflow. `shops.is_active` defaults to True — shops go live immediately on creation with no NL review. |
| approved_by field tracks NL | **MISSING** | No approval field on shops. |
| 30-day GDP contribution tracked per business | **PARTIAL** | GDP pillar 3 (Business Revenue) sums 30-day PURCHASE transactions flowing to shop owner wallets per nation (`gdp.py:89-109`). But this is aggregated at the nation level, not tracked as a per-business metric. No per-shop GDP contribution field exists. |
| Marketplace sorting by GDP contribution | **MISSING** | `shop_routes.py:59` → `order_by(Shop.created_at.desc())`. No GDP-based sorting. |
| Resource Depot subtype with mining setup disclosure fields | **MISSING** | No shop subtypes. `ShopListing.category` has `{service, coordinates, item, other}` but no "resource_depot" type. No mining-related fields anywhere. |

### 5. STOCK MARKET

| Decision | Status | Evidence |
|----------|--------|----------|
| Two-tier (nation stocks + business stocks) | **IMPLEMENTED** | `Stock.stock_type` → `"nation"` or `"business"` (`models.py:242`). `create_nation_stock()` and `create_business_stock()` in `valuation.py`. |
| Three-pillar valuation engine | **IMPLEMENTED** | Nation pillars: population, activity, cashflow (`valuation.py:196-300`). Business pillars: customers, activity, cashflow (`valuation.py:303-384`). Peer-relative normalization via `_gather_nation_maxes()` and `_gather_business_maxes()`. |
| IPO flow with thresholds | **IMPLEMENTED** | `valuation.py:131-160` → `create_business_stock()` validates `IPO_MIN_SALES=10`, `IPO_MIN_DAYS=30`, share count between 100-1000. UI at `/shop/ipo` page route. |
| Nation stocks: open to all | **IMPLEMENTED** | `stock_routes.py:354-363` → Nation stock membership check only fires for `stock.stock_type == "business"`. Nation stocks have no membership gate. |
| Business stocks: same-nation members only | **IMPLEMENTED** | `stock_routes.py:355-363` → `if stock.stock_type == "business": ... if current_user.nation_id != shop.nation_id: raise HTTPException(status_code=403, ...)`. |
| No dividends | **IMPLEMENTED** | No dividend code, no dividend tx type, no dividend-related fields anywhere in models or routes. |
| Closure payout from business wallet (Option A) | **MISSING** | No stock closure or delisting mechanism exists. `Stock.is_active` can be set to False but there is no closure endpoint, no payout logic, and no forfeiture code. |
| Forced closure forfeits owner excess | **MISSING** | No forced closure mechanism. |

### 6. WORLD MINT AUTHORITY

| Decision | Status | Evidence |
|----------|--------|----------|
| Mint endpoint can target any wallet type (treasury, business, member) | **PARTIAL** | `POST /api/mint/execute` accepts any `to_address` string. It validates existence for user wallets and nation treasuries (`mint_routes.py:165-182`). However, it does **not** validate or handle bank wallet addresses (`TRV-BANK-*`). A mint to a bank wallet would be accepted by `blockchain.py:create_transaction()` (which credits bank balances for `TRV-BANK-` addresses at line 208-212) but the mint_routes validation only checks User and Nation — a bank address would fail the User lookup and return an error. There's also no concept of a "business wallet" — shops use the owner's personal wallet. |
| Monthly mint cap enforcement | **MISSING** | No cap on minting. `POST /api/mint/execute` has no limit. The allocation cycle (calculate → approve → execute) provides a suggested amount based on `BASE_RATE * member_count` but the World Mint admin can override `approved_amount` to any value, and can also use `/api/mint/execute` to mint arbitrary amounts outside the allocation system entirely. |
| World Mint cannot buy/sell stocks | **MISSING** | No enforcement. The `require_login` dependency on buy/sell stock routes does not check `user.role != "world_mint"`. The admin user seeded at startup could buy stocks. The only protection is social — the admin account wouldn't normally browse to `/exchange/{ticker}/trade`. |
| World Mint cannot override NL decisions | **PARTIAL** | Nation approval and suspension are World Mint powers (`mint_routes.py:301-364`). But within a nation, bank creation requires `role in ("nation_leader", "world_mint")` (`bank_routes.py:86`) — so the World Mint CAN create banks in any nation. Loan forgiveness is NL-only (`bank_routes.py:459`). Distribution is NL-only (`nation_routes.py:318`). So enforcement is inconsistent: some NL powers are protected, but bank creation is not. |

### 7. ECONOMIC HEALTH

| Decision | Status | Evidence |
|----------|--------|----------|
| Per-nation 30-day rolling GDP | **IMPLEMENTED** | `gdp.py` → 4-pillar calculation using 30-day windows for transaction volume, business revenue, and active citizens. Snapshots saved to `gdp_snapshots`. Recalculated every 24h via APScheduler and on-demand via `POST /api/mint/recalculate-gdp`. |
| GDP buff/debuff applied at shop transaction time | **IMPLEMENTED** | `shop_routes.py:243-244` → Listing creation converts national price to TC: `tc_price = round(payload.price * gdp_mult / 100)`. Purchase response (`shop_routes.py:329-333`) returns both seller and buyer prices via `tc_to_national()` using each nation's GDP multiplier. Cross-nation pricing is GDP-driven. |
| Wallet health metrics: last_activity_at, transaction counts, volume | **PARTIAL** | `User.last_active` exists and is updated on every authenticated request (`auth.py:114`). But there are no `transaction_count_lifetime`, `transaction_count_30d`, or `volume_30d` fields on the User model. These metrics are computed dynamically only within GDP calculation — not stored per-wallet. |
| Idle wallet demurrage | **MISSING** | No demurrage code. No per-nation toggle. No NL-configurable rate. No burn mechanism for idle wallets. |
| Auto-stimulus triggers | **MISSING** | No auto-alert system. No warning/mild/strong tiers. No proposed-for-approval stimulus mechanism. |

### 8. LEDGER

| Decision | Status | Evidence |
|----------|--------|----------|
| Hash-chained transaction ledger | **IMPLEMENTED** | `blockchain.py:34-44` → `compute_tx_hash()` uses SHA-256 of `prev_hash + from_addr + to_addr + amount + timestamp + nonce`. Each transaction stores `prev_hash` linking to the previous transaction's `tx_hash`. Thread-safe via `_tx_lock` mutex. |
| Public ledger with transaction detail pages | **IMPLEMENTED** | `GET /api/ledger` → paginated public ledger (`transaction_routes.py:132-161`). `GET /api/transactions/{tx_hash}` → single transaction lookup. HTML pages at `/ledger` and `/tx/{tx_hash}` with filters by type and address. |
| Wallet lookup | **IMPLEMENTED** | `GET /api/wallet/{address}` → public wallet info (`wallet_routes.py:113-149`). `GET /api/wallet/search` → search by username/display_name/address prefix. `GET /api/wallet/{address}/transactions` → per-address tx history. HTML pages at `/wallet/search` and `/wallet/{address}`. |
| Chain verification | **IMPLEMENTED** | `blockchain.py:285-341` → `verify_chain()` walks the full chain verifying `prev_hash` linkage. **Limitation noted in code comments:** cannot fully recompute tx_hash because the raw ISO timestamp string used at creation time is not stored — only the SQLite `created_at` column exists, which may be reformatted by the DB. Linkage verification works; hash recomputation does not. Result displayed on mint stats page and ledger page. |

---

## 4. Notable Findings

**Bug: Transfer endpoint uses `get_current_user` instead of `require_login`.** `transaction_routes.py:43` → `current_user: User = Depends(get_current_user)`. Since `get_current_user` returns `None` for unauthenticated users, the subsequent `current_user.wallet_address` (line 64) will raise `AttributeError: 'NoneType' object has no attribute 'wallet_address'`. Should be `require_login`.

**Bug: Nation stock creation only happens in page_routes.py.** When a nation is approved via the API route `POST /api/mint/nations/{nation_id}/approve` (`mint_routes.py:301`), `create_nation_stock()` is NOT called. It IS called in the HTML form handler `POST /mint/nations/{nation_id}/approve` (`page_routes.py:2113`). Any nation approved via API (e.g., by a future bot or mobile client) would never get a stock created.

**Bug: Interest is never accrued.** The `Loan` model has `interest_rate` and `outstanding` fields, and `interest_rate_cap_bps` exists in GlobalSettings, but there is no code anywhere that computes interest and adds it to `loan.outstanding`. Loans are effectively interest-free despite the interest rate being displayed to users. The scheduled jobs only recalculate GDP and stock prices, not loan interest.

**Bug: Loan forgiveness skips blockchain transaction.** `bank_routes.py:478-484` → Comment says the LOAN_FORGIVE tx type would fail validation because amount=0. The forgiveness is recorded only as a status change on the Loan row, with no ledger entry. This creates a gap in the chain's record of monetary events.

**Security: Hardcoded SECRET_KEY.** `config.py:13` → `SECRET_KEY = "travelers-exchange-secret-change-me"`. This is used as the salt for wallet address generation. Not read from environment. The same key also seeds the admin password hash (deterministic wallet addresses).

**Security: Admin seeded with password "changeme".** `main.py:129` → `bcrypt.hashpw("changeme".encode(), ...)`. If the DB is recreated on the Pi, the admin account has a trivially guessable password.

**Architectural: page_routes.py duplicates all business logic.** At 3,533 lines, this file re-implements every API operation as form POST handlers. Changes to API routes must be manually mirrored here. The nation approval divergence (stock creation) is a direct consequence of this duplication.

**Architectural: `verify_chain()` cannot fully verify hash integrity.** As documented in comments at `blockchain.py:317-333`, the raw ISO timestamp used in hash computation is not stored. Only chain linkage is verified, not hash recomputation. Result displayed on mint stats page and ledger page.

---

## 5. Summary

The Travelers Exchange codebase implements a working simulated economy with 16 database tables, a hash-chained ledger, GDP-driven exchange rates, a two-tier stock market, and a banking system with loan burn mechanics. Of the 8 audited design categories: Naming/Identity and Ledger are fully implemented; Stock Market and Economic Health are substantially implemented with specific gaps (no closure mechanism, no wallet health metrics, no demurrage, no auto-stimulus); Banks/Lending has the core infrastructure but conflicts on burn split behavior (uniform rate vs. 20/80 split) and lacks interest accrual entirely; World Mint is partially implemented with no mint cap and incomplete access restrictions; Businesses lack an approval workflow and the Resource Depot subtype; and Keeper Bot Integration is entirely absent. Three bugs warrant attention before production use: the unauthenticated transfer crash, the API-path stock creation gap, and the non-functional interest system.
