# Haven Economy — How to Use

## Getting Started

1. **Register** an account at `/register`
2. You start with **0 Haven Marks (HM)** — currency comes from nation treasuries
3. Join a nation to start participating in the economy

---

## For Citizens

### Join a Nation
- Browse `/nations` and click into any approved nation
- Click **Join** — you can only belong to one nation at a time

### Receive Currency
- Your nation leader distributes HM from the treasury to members
- Check your balance on `/dashboard`

### Send Currency
- Go to `/send`, enter a wallet address and amount
- You can find anyone's wallet via `/wallet/search`

### Shop the Marketplace
- Browse `/market` to see listings from all shops
- Filter by nation, category, or price range
- Click **Buy** on any listing you can afford

### Trade Stocks
- Browse the exchange at `/exchange`
- Click any stock to see its detail page, then **Trade**
- **Buy** shares if you have the HM (business stocks require same-nation membership)
- **Sell** shares back at the current market price
- Track your holdings at `/portfolio`

### View the Ledger
- `/ledger` shows every transaction on the blockchain
- Filter by type (MINT, TRANSFER, PURCHASE, STOCK_BUY, etc.)

---

## For Nation Leaders

Everything above, plus:

### Treasury
- Go to `/nation/treasury` to see your nation's balance
- The World Mint allocates HM to your treasury based on member count

### Distribute Funds
- `/nation/distribute` — send HM to a single member
- **Bulk distribute** — split an amount equally across all members

### Grow Your Nation
- More members = larger monthly allocation from the World Mint
- Your nation's stock price rises with population, activity, and cash flow

---

## For Shop Owners

Everything above, plus:

### Create a Shop
- Go to `/shop/create` (must be in a nation first)
- Add listings with a title, price, and category

### Manage Listings
- `/shop/manage` shows your shop dashboard
- Toggle listings on/off, view sales and revenue stats

### Launch an IPO
- Once your shop has **10+ sales** and is **30+ days old**, go to `/shop/ipo`
- Issue 100–1,000 shares at 5 HM base price
- Members of your nation can then invest in your business on the exchange

---

## For the World Mint (Admin)

### Mint Dashboard
- `/mint` — overview of the entire economy
- Approve or reject nation applications
- Approving a nation auto-creates its stock on the exchange

### Currency Supply
- **Direct mint** — send HM to any address
- **Calculate allocations** — generate monthly allocations (member count x base rate)
- **Approve & execute** allocations to fund nation treasuries

### Stock Management
- **Recalculate stock prices** — triggers the valuation engine to re-score all stocks

---

## How Stock Prices Work

Every stock is scored on three pillars (0–100 each):

| Pillar | Nations | Businesses |
|--------|---------|------------|
| **Population / Customers** | Member count | Unique customers |
| **Activity** | Transactions in last 30 days | Sales in last 30 days |
| **Cash Flow** | Treasury balance | Total revenue |

Scores are normalized against all stocks of the same type. The composite score (average of all three) determines the price:

```
price = base_price x composite_score / 50
```

A score of 50 = base price. Higher = more expensive. Minimum price is always 1 HM.

---

## Quick Reference

| Action | Where |
|--------|-------|
| Register | `/register` |
| Dashboard | `/dashboard` |
| Send HM | `/send` |
| Transaction history | `/history` |
| Browse nations | `/nations` |
| Apply to create nation | `/nations/apply` |
| Marketplace | `/market` |
| Create shop | `/shop/create` |
| Manage shop | `/shop/manage` |
| Stock exchange | `/exchange` |
| Portfolio | `/portfolio` |
| Search wallets | `/wallet/search` |
| Public ledger | `/ledger` |
| Account settings | `/settings` |
