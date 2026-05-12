# Travelers Exchange — Keeper Bot API Reference

**Audience:** Stars (The_Keeper maintainer) — implementing Discord cogs against the Exchange API.
**Verified against:** branch `keeper-integration-p0` (latest commit on this branch).

> Anything in this file is a working contract. If a field disappears or changes shape, treat it as a breaking change and ping Parker.

---

## TL;DR — how the bot works

1. Parker hands Stars one bearer token (`tx_live_<32 hex>`).
2. Every Exchange API request the bot ever makes carries two headers:
   ```
   Authorization: Bearer <KEEPER_API_KEY>
   X-Discord-User-Id: <discord_user_id>
   ```
3. **First time the bot calls any user-tier endpoint with a brand-new `X-Discord-User-Id`, the Exchange auto-creates a User row for that Discord user.** No website detour, no link code, no password the user has to set. They just type `/wallet` in Discord and they're an Exchange user.
4. Every subsequent call is the Exchange running the underlying logic *as that Discord user*. All existing role/permission checks (`citizen`, `nation_leader`, `world_mint`) apply exactly as if they were on the website.

That's the whole protocol.

### Optional headers used during auto-provision

When auto-creating a user, the Exchange uses these to populate the new User row:

- `X-Discord-Username` → `users.username` (default: `discord_<id>`). Sanitized to alphanumeric/`_-.`. Collisions get a numeric suffix.
- `X-Discord-Display` → `users.display_name` (default: NULL).

Pass them on every call — the Exchange ignores them after the first call (when the user already exists). If you don't pass them, you'll end up with a username like `discord_999888777` and no display name. Cleanest pattern: bot always passes `X-Discord-Username` set to the Discord member's `name` and `X-Discord-Display` to their `global_name`/`display_name`.

---

## Conventions

- **Base URL:** `https://travelers-exchange.online`
- **Format:** Request bodies are JSON unless explicitly marked `application/x-www-form-urlencoded`. Responses are always JSON.
- **Money:** All amounts are integers in TC. Display in national currency by computing `amount * gdp_multiplier / 100` (the multiplier is stored as `int * 100`; e.g. 125 = 1.25x).
- **Wallets:** `TRV-<8-hex>` for users, `TRV-NATION-<8-hex>` for treasuries, `TRV-BANK-<8-hex>` for banks.
- **Errors:** FastAPI shape — `{"detail": "Human-readable message"}` with HTTP 4xx. Surface `detail` verbatim in Discord embeds; it's already user-friendly.
- **Special case:** `/api/transactions/transfer` returns HTTP 200 with `{"success": false, "error": "..."}` for business errors (insufficient balance, etc.). Render `error` if `success` is false.

## Rate limits

- 600 mutating req/min/key
- 60 mutating req/min/discord_id
- GET/HEAD/OPTIONS not throttled
- Overage → HTTP 429 with `{"detail": "..."}`. Treat as transient; back off and retry.

---

## 1. Wallet, Ledger, Transfers

| Method | Path | Auth | Body / Query | Notes |
|---|---|---|---|---|
| GET | `/api/wallet` | user | — | Caller's wallet incl. balance + 30d activity. **Auto-provisions on first call.** |
| GET | `/api/wallet/search?q=&limit=` | public | `q` ≥ 1 char, `limit` 1–20 (default 8) | Prefix search across users + treasuries |
| GET | `/api/wallet/{address}` | public | — | Public view; user-shape OR treasury-shape |
| GET | `/api/wallet/{address}/transactions?page=&per_page=` | public | `per_page` ≤ 100 | Paginated tx history |
| GET | `/api/ledger?page=&per_page=` | public | `per_page` ≤ 100 | Global ledger feed |
| GET | `/api/transactions/{tx_hash}` | public | full hash or `tx_<first12>` | One transaction |
| POST | `/api/transactions/transfer` | user | `{"to_address","amount","memo?"}` | Send TC. Returns `200` even on business errors — check `success`. |

## 2. Account self-service (NEW — bot-callable)

| Method | Path | Auth | Body | Notes |
|---|---|---|---|---|
| POST | `/api/auth/settings/password` | user | `{"old_password","new_password"}` | New password ≥ 8 chars. 403 if old wrong. |
| POST | `/api/auth/settings/display-name` | user | `{"display_name?"}` | Empty/null clears it |

## 3. Nations

| Method | Path | Auth | Body / Query | Notes |
|---|---|---|---|---|
| GET | `/api/nations` | public | — | All approved nations + GDP info |
| POST | `/api/nations/apply` | user | `{"name","currency_name?","currency_code?","description?","discord_invite?","game?"}` | `currency_code` 2–5 uppercase, unique |
| POST | `/api/nations/{id}/join` | user | — | 400 if already in a nation / nation not approved |
| POST | `/api/nations/{id}/leave` | user | — | 400 if leader (must transfer first) |
| GET | `/api/nations/{id}/members` | public | — | Member roster |
| **POST** | **`/api/nations/{id}/edit-description`** | **nation_leader** | **`{"description?"}`** | **NEW.** Leader edits description |
| **PUT** | **`/api/nations/{id}/identity`** | **nation_leader** | **`{"name?","currency_name?","currency_code?","discord_invite?","game?"}`** | **NEW.** Leader rename / re-currency / etc. Any field optional; only sent fields update. |
| **GET** | **`/api/nations/{id}/treasury`** | **user (must be member)** | **—** | **NEW.** Balance + recent distributions + allocation history in one call |
| POST | `/api/nations/{id}/distribute` | nation_leader | `{"to_address","amount","memo?"}` | Single payout |
| POST | `/api/nations/{id}/distribute-bulk` | nation_leader | `{"distributions":[{"to_address","amount"}], "memo?"}` | Atomic batch |
| GET | `/api/nations/{id}/demurrage` | user (member) | — | Current settings |
| PUT | `/api/nations/{id}/demurrage` | nation_leader | `{"demurrage_enabled?","demurrage_rate_bps?"}` | 1–1000 bps |
| GET | `/api/nations/{id}/stimulus-proposals?status=` | nation_leader | — | Filter `pending|approved|rejected` |
| POST | `/api/nations/{id}/stimulus-proposals/{pid}/approve` | nation_leader | `{"reason?"}` | |
| POST | `/api/nations/{id}/stimulus-proposals/{pid}/reject` | nation_leader | `{"reason?"}` | |

## 4. Banks & Loans

| Method | Path | Auth | Body | Notes |
|---|---|---|---|---|
| POST | `/api/banks` | nation_leader | `{"name","owner_user_id"}` | Owner must be nation member; 4-bank cap |
| GET | `/api/banks/nation/{nation_id}` | public | — | All banks in a nation |
| GET | `/api/banks/{bank_id}` | public | — | Bank detail |
| POST | `/api/banks/{bank_id}/deactivate` | nation_leader | — | |
| GET | `/api/banks/{bank_id}/loans` | bank_op / nation_leader / world_mint | — | |
| POST | `/api/banks/{bank_id}/loans` | bank_op | `{"borrower_user_id","amount","memo?"}` | Bank-issued loan |
| POST | `/api/banks/{bank_id}/loans/{loan_id}/forgive` | nation_leader | — | |
| POST | `/api/nations/{nation_id}/loans` | nation_leader | `{"borrower_user_id","amount","memo?"}` | Treasury-issued loan |
| GET | `/api/nations/{nation_id}/loans` | nation_leader / world_mint | — | |
| POST | `/api/nations/{nation_id}/loans/{loan_id}/forgive` | nation_leader | — | |
| **POST** | **`/api/loans/apply`** | **user (citizen)** | **`{"bank_id","amount","memo?"}`** | **NEW.** Citizen-initiated apply against an active bank in their nation. 409 if active loan exists. |
| GET | `/api/loans/mine` | user | — | All caller's loans |
| **GET** | **`/api/loans/{loan_id}`** | **borrower / bank_op / nation_leader / world_mint** | **—** | **NEW.** Single loan detail with payment history |
| POST | `/api/loans/{loan_id}/pay` | borrower | `{"amount"}` | Returns full burn-split breakdown — render every field in the embed |

**`/api/loans/{loan_id}/pay` response:**
```json
{
  "success": true, "tx_hash": "...",
  "interest_portion": 12, "principal_portion": 88,
  "during_payment_burn": 8, "close_burn": 0,
  "burn_amount": 8, "bank_amount": 92,
  "is_final_payment": false,
  "remaining_principal": 412, "remaining_interest": 28
}
```

## 5. Shops & Marketplace

| Method | Path | Auth | Body / Query | Notes |
|---|---|---|---|---|
| POST | `/api/shops` | user | `{"name","description?","shop_type":"general|resource_depot","mining_setup?"}` | `mining_setup` required for resource_depot. Shop starts `pending`. |
| GET | `/api/shops?nation_id=&type=` | public | — | Approved + active shops |
| GET | `/api/shops/pending` | nation_leader (own nation) / world_mint | — | |
| GET | `/api/shops/{id}` | public | — | Shop detail with listings (TC + national price) |
| POST | `/api/shops/{id}/listings` | shop_owner | `{"title","description?","price","category"}` | `price` is in **national currency** |
| POST | `/api/shops/{id}/listings/{lid}/buy` | user | — | Server transfers TC, marks unavailable |
| PUT | `/api/shops/{id}/listings/{lid}` | shop_owner | any of `{title,description,price,category,is_available}` | Partial update |
| POST | `/api/shops/{id}/approve` | nation_leader (NOT own shop) / world_mint | — | |
| POST | `/api/shops/{id}/reject` | same | `{"reason?"}` | |
| POST | `/api/shops/{id}/suspend` | same | `{"reason?"}` | |
| **POST** | **`/api/shops/{id}/ipo`** | **shop_owner / world_mint** | **`{"num_shares"}`** | **NEW.** IPO an approved shop into a tradable business stock. Returns `{"ticker"}`. |

## 6. Stock Market

| Method | Path | Auth | Body / Query | Notes |
|---|---|---|---|---|
| GET | `/api/stocks?stock_type=&sort_by=` | public | — | All active stocks |
| GET | `/api/stocks/portfolio` | user | — | Caller's holdings + total gain/loss |
| GET | `/api/stocks/rankings` | public | — | Performance leaderboard |
| GET | `/api/stocks/{ticker}` | public | — | Detail w/ recent trades |
| GET | `/api/stocks/{ticker}/history` | public | — | 90-day price history |
| POST | `/api/stocks/{ticker}/buy` | user | `{"shares"}` | Business stocks gated on nation membership |
| POST | `/api/stocks/{ticker}/sell` | user | `{"shares"}` | |
| POST | `/api/stocks/{stock_id}/close` | world_mint OR shop_owner | `{"reason?"}` | |

## 7. World Mint (admin) — gate Discord-side too

All endpoints require `role=world_mint` on the resolved Exchange user. Recommend gating these Discord commands behind a Discord role check on top.

| Method | Path | Body | Notes |
|---|---|---|---|
| GET | `/api/mint/stats` | — | Dashboard subset |
| **GET** | **`/api/mint/stats/detailed`** | **—** | **NEW.** Hash chain status + supply breakdown + tx-by-type counts + per-nation table |
| POST | `/api/mint/execute` | `{"to_address","amount","memo?"}` | Mint TC. Subject to per-nation `mint_cap`. |
| GET | `/api/mint/allocations` | — | Pending + approved + recent |
| POST | `/api/mint/allocations/{id}/approve` | `{"approved_amount?"}` | |
| POST | `/api/mint/allocations/{id}/execute` | — | Distribute one |
| POST | `/api/mint/execute-all-approved` | — | Batch-distribute |
| POST | `/api/mint/calculate-allocations` | `{"period?"}` | Generate next batch |
| POST | `/api/mint/nations/{id}/approve` | — | Approves + auto-IPOs nation stock |
| POST | `/api/mint/nations/{id}/reject` | — | |
| POST | `/api/mint/nations/{id}/suspend` | — | Demotes leader to citizen (unless they lead another approved nation) |
| POST | `/api/mint/nations/{id}/unsuspend` | — | Re-promotes leader |
| **PUT** | **`/api/mint/nations/{id}/identity`** | **`{"name?","currency_name?","currency_code?","discord_invite?","game?"}`** | **NEW.** WM rename / re-currency / etc. Keeps nation Stock row in sync. |
| POST | `/api/mint/recalculate-gdp` | — | Force recalc + stimulus check |
| **POST** | **`/api/mint/recalculate-stocks`** | **—** | **NEW.** Force stock-price recalc |
| GET | `/api/mint/gdp-history?nation_id=&limit=` | — | Snapshots; `limit` default 30 |
| GET | `/api/mint/stimulus-proposals?status=&limit=` | — | |
| POST | `/api/mint/stimulus-proposals/{id}/approve` | `{"approved_amount?","reason?"}` | |
| POST | `/api/mint/stimulus-proposals/{id}/reject` | `{"reason?"}` | |
| GET | `/api/mint/settings` | — | Global `{burn_rate_bps, interest_rate_cap_bps, interest_burn_rate_bps}` |
| POST | `/api/mint/settings` | `{"burn_rate_bps","interest_rate_cap_bps","interest_burn_rate_bps?"}` | |

---

## Working examples

```bash
BOT_KEY="tx_live_<32hex>"
DISCORD_ID="123456789012345678"

# 1. Brand new Discord user — auto-provisions on first call.
curl -s "$BASE/api/wallet" \
  -H "Authorization: Bearer $BOT_KEY" \
  -H "X-Discord-User-Id: $DISCORD_ID" \
  -H "X-Discord-Username: parker_demo" \
  -H "X-Discord-Display: Parker"
# → {"address":"TRV-...","balance":0,"display_name":"Parker",...}

# 2. Send TC — same headers; the resolved user must have balance.
curl -s -X POST "$BASE/api/transactions/transfer" \
  -H "Authorization: Bearer $BOT_KEY" \
  -H "X-Discord-User-Id: $DISCORD_ID" \
  -H "Content-Type: application/json" \
  -d '{"to_address":"TRV-aaaa1111","amount":50,"memo":"From Discord"}'
# → {"success":true,"tx_hash":"..."}  OR  {"success":false,"error":"Insufficient balance..."}

# 3. Apply for a nation.
curl -s -X POST "$BASE/api/nations/apply" \
  -H "Authorization: Bearer $BOT_KEY" \
  -H "X-Discord-User-Id: $DISCORD_ID" \
  -H "Content-Type: application/json" \
  -d '{"name":"Atlantia","currency_name":"AtlanCoin","currency_code":"ATC"}'

# 4. Open a shop (after WM approves the nation).
curl -s -X POST "$BASE/api/shops" \
  -H "Authorization: Bearer $BOT_KEY" \
  -H "X-Discord-User-Id: $DISCORD_ID" \
  -H "Content-Type: application/json" \
  -d '{"name":"Parker Trading Co","description":"Ships, parts, and base modules","shop_type":"general"}'
# → {"success":true,"shop_id":1,"status":"pending"}

# 5. NL approves a pending shop in their nation.
curl -s -X POST "$BASE/api/shops/1/approve" \
  -H "Authorization: Bearer $BOT_KEY" \
  -H "X-Discord-User-Id: <leader_discord_id>"
# 403 if it's the leader's OWN shop — those go via /mint instead.

# 6. List a product (price in NATIONAL currency, server converts to TC).
curl -s -X POST "$BASE/api/shops/1/listings" \
  -H "Authorization: Bearer $BOT_KEY" \
  -H "X-Discord-User-Id: $DISCORD_ID" \
  -H "Content-Type: application/json" \
  -d '{"title":"Hauler ship","description":"30 slots, fully loaded","price":150000,"category":"item"}'

# 7. Pay a loan and render every field of the burn breakdown.
curl -s -X POST "$BASE/api/loans/42/pay" \
  -H "Authorization: Bearer $BOT_KEY" \
  -H "X-Discord-User-Id: $DISCORD_ID" \
  -H "Content-Type: application/json" \
  -d '{"amount":100}'
```

---

## What to do when

| HTTP | Meaning | Discord message |
|---|---|---|
| 200 + `{"success":false}` | Business error on `/transfer` or similar | Surface `error` in red |
| 303 / 401 | Bot key bad or missing | "Bot is misconfigured — ping Parker." |
| 403 | User lacks role (citizen calling NL endpoint, etc.) | Surface `detail` |
| 404 | Resource doesn't exist | Surface `detail` |
| 409 | Conflict (already linked, name taken, double-vote, etc.) | Surface `detail` |
| 429 | Rate-limited | Back off 30s and retry |
| 500 | Server bug | Generic "Something went wrong, ping Parker" |

---

## Branch / commit Stars is targeting

- Branch: `keeper-integration-p0`
- Repo: `Parker1920/Master-Haven`
- Spec: `Haven-Exchange/EXCHANGE_KEEPER_INTEGRATION_SPEC.md`
- Reference (this file): `Haven-Exchange/KEEPER_API_REFERENCE.md`

The branch is not yet merged to `main`. URL behavior is identical against the running Pi `https://travelers-exchange.online` once merged + deployed.

---

## Cookie note (web users only — bot doesn't care)

`auth_routes.py:_set_session_cookie` currently has `secure=False` for local-dev demo purposes. **Flip back to `secure=True` before deploying to production** — the bot uses bearer auth not cookies, so this only affects browser sessions on production HTTPS.
