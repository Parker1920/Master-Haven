# Inter-Civilization Economy System

## The Concept

An in-game cryptocurrency economy for No Man's Sky civilizations to use for roleplay, inter-civ services, and community engagement. **This has no real-world monetary value** - it's purely for fun and community interaction.

---

## How It Works

### Currencies

**Universal Currency: Haven Coin**
- The main currency used across all civilizations
- Starting supply: 100,000 HAVEN
- Used for trading between any civs or individuals

**Civilization Currencies**
- Each civ can create their own currency (e.g., "GHDF-Coin", "Hub-Coin", "Qitanian Units")
- Civs control their own currency's initial supply
- Can be traded on the marketplace for Haven Coin or other civ currencies

---

## Earning Coins

### Discovery Rewards
When your system/planet/moon discoveries get approved, you automatically earn coins:

| Discovery Type | Reward |
|---------------|--------|
| New System | Configurable (default ~10 HAVEN) |
| New Planet | Configurable (default ~5 HAVEN) |
| New Moon | Configurable (default ~2 HAVEN) |

Rewards go directly to the individual discoverer's wallet (identified by Discord username).

If your civ has its own currency, you'll also earn that currency for discoveries tagged to your civ.

---

## Wallets

### Civilization Treasury
- Each partner civ gets a treasury wallet
- Holds the civ's collective funds
- Can be used for inter-civ transactions

### Individual Wallets
- Every user gets a personal wallet (linked to Discord username)
- Holds your personal earnings and trades
- You control your own funds

---

## The Marketplace

Trade currencies with other players and civs:

**How Exchange Works:**
1. Post an offer: "Trading 100 HAVEN for 50 GHDF-Coin"
2. Your 100 HAVEN gets held in escrow
3. Someone accepts your offer
4. They get your 100 HAVEN, you get their 50 GHDF-Coin
5. Or cancel anytime to get your HAVEN back

Exchange rates are whatever the community agrees on - pure supply and demand!

---

## Public Ledger

**Every transaction is public** - like a blockchain:

- See all transfers, trades, and discovery rewards
- Full transparency for the community
- Track the flow of coins between civs
- Verify any transaction with its unique hash

---

## Use Cases

### For Fun/Roleplay
- Build your personal wealth as an explorer
- Compete with other explorers on earnings
- Civ-vs-civ economic competition

### Inter-Civ Services
- Pay other civs for exploration contracts
- Commission region mapping
- Fund joint expeditions
- Bounties for finding specific resources/systems

### Community Events
- Prize pools for competitions
- Rewards for community contributions
- Civ treasury funding for projects

---

## Technical Overview

**Backend:** Python FastAPI + SQLite
**Frontend:** React
**Integration:** Hooks into existing discovery approval flow

### Database Tables
- `currencies` - Currency definitions
- `wallets` - User and civ wallets
- `wallet_balances` - Balance per currency per wallet
- `transactions` - Full public ledger
- `exchange_offers` - Marketplace listings
- `discovery_rewards` - Reward configuration

### New UI Pages
- **Economy Dashboard** - View your wallet and balances
- **Public Ledger** - Browse all transactions
- **Marketplace** - Trade currencies
- **Currency Admin** - Manage currencies and rewards

---

## Summary

| Feature | Description |
|---------|-------------|
| Haven Coin | Universal currency for all civs |
| Civ Currencies | Each civ can mint their own |
| Discovery Rewards | Earn coins for approved discoveries |
| Wallets | Personal + civ treasury wallets |
| Marketplace | Exchange currencies at agreed rates |
| Public Ledger | Transparent transaction history |
| Real Value | **None** - purely for fun! |

---

*This is a community feature for the Voyagers Haven NMS discovery platform.*
