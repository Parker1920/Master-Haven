import aiohttp 
from aiohttp import ClientTimeout
import asyncio
from typing import Any, Optional
from discord.ext import commands

BASE_URL="https://travelers-exchange.online/"
API_KEY="tx_live_c7f3247ac8aa28027e83e83e7f907192"

class TravelersExchangeAPI:
    def __init__(self, bot, base_url, api_key, timeout=30):
        self.bot = bot
        self.base_url = BASE_URL
        self.api_key = API_KEY
        self.timeout = timeout

        
        self.session = aiohttp.ClientSession(timeout=ClientTimeout(total=self.timeout))

# ---------------- Session ----------------
    
    async def start(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession(
            
        )
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    # ---------------- Internal ----------------
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        discord_user_id: int | None = None,
        params: dict | None = None,
        json: dict | None = None,
    ) -> Any:
        if not self.session:
            await self.start()
    
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
        if discord_user_id:
            headers["X-Discord-User-Id"] = str(discord_user_id)
    
        url = f"{self.base_url}{endpoint}"
    
        async with self.session.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json,
        ) as response:
            try:
                data = await response.json()
            except Exception:
                data = {"detail": await response.text()}
    
            if response.status >= 400:
                raise ExchangeAPIError(
                    response.status,
                    data.get("detail", "Unknown API error"),
                )
    
            return data
    
    async def get(self, endpoint: str, **kwargs):
        return await self._request("GET", endpoint, **kwargs)
    
    async def post(self, endpoint: str, **kwargs):
        return await self._request("POST", endpoint, **kwargs)
    
    async def put(self, endpoint: str, **kwargs):
        return await self._request("PUT", endpoint, **kwargs)
    
    # ---------------- Formatting Helpers ----------------
    
    @staticmethod
    def format_tc(amount: int) -> str:
        return f"{amount:,} TC"
    
    @staticmethod
    def format_national(
        amount: int,
        currency_code: str,
        gdp_multiplier_x100: int,
    ) -> str:
        converted = int((amount * gdp_multiplier_x100) / 100)
        return f"{converted:,} {currency_code}"
    
    @staticmethod
    def format_wallet_short(address: str) -> str:
        if len(address) <= 14:
            return address
    
        return f"{address[:8]}…{address[-4:]}"
    
    @staticmethod
    def format_tx_hash_short(tx_hash: str) -> str:
        return f"{tx_hash[:12]}…"
    
    # ============================================================
    # WALLET / LEDGER
    # ============================================================
    
    async def get_my_wallet(self, discord_user_id: int):
        return await self.get(
            "/api/wallet",
            discord_user_id=discord_user_id,
        )
    
    async def search_wallets(self, query: str, limit: int = 10):
        return await self.get(
            "/api/wallet/search",
            params={"q": query, "limit": limit},
        )
    
    async def get_wallet(self, address: str):
        return await self.get(f"/api/wallet/{address}")
    
    async def get_wallet_transactions(
        self,
        address: str,
        page: int = 1,
        per_page: int = 25,
    ):
        return await self.get(
            f"/api/wallet/{address}/transactions",
            params={
                "page": page,
                "per_page": per_page,
            },
        )
    
    async def get_ledger(
        self,
        page: int = 1,
        per_page: int = 25,
    ):
        return await self.get(
            "/api/ledger",
            params={
                "page": page,
                "per_page": per_page,
            },
        )
    
    async def get_transaction(self, tx_hash: str):
        return await self.get(f"/api/transactions/{tx_hash}")
    
    async def transfer_tc(
        self,
        discord_user_id: int,
        to_address: str,
        amount: int,
        memo: str | None = None,
    ):
        payload = {
            "to_address": to_address,
            "amount": amount,
        }
    
        if memo:
            payload["memo"] = memo
    
        return await self.post(
            "/api/transactions/transfer",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    # ============================================================
    # NATIONS
    # ============================================================
    
    async def apply_nation(
        self,
        discord_user_id: int,
        name: str,
        currency_name: str,
        currency_code: str,
        description: str | None = None,
        discord_invite: str | None = None,
        game: str | None = None,
    ):
        payload = {
            "name": name,
            "currency_name": currency_name,
            "currency_code": currency_code,
        }
    
        if description:
            payload["description"] = description
    
        if discord_invite:
            payload["discord_invite"] = discord_invite
    
        if game:
            payload["game"] = game
    
        return await self.post(
            "/api/nations/apply",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def get_nations(self):
        return await self.get("/api/nations")
    
    async def join_nation(
        self,
        discord_user_id: int,
        nation_id: int,
    ):
        return await self.post(
            f"/api/nations/{nation_id}/join",
            discord_user_id=discord_user_id,
        )
    
    async def leave_nation(
        self,
        discord_user_id: int,
        nation_id: int,
    ):
        return await self.post(
            f"/api/nations/{nation_id}/leave",
            discord_user_id=discord_user_id,
        )
    
    async def get_nation_members(self, nation_id: int):
        return await self.get(f"/api/nations/{nation_id}/members")
    
    async def distribute_nation_funds(
        self,
        discord_user_id: int,
        nation_id: int,
        to_address: str,
        amount: int,
        memo: str | None = None,
    ):
        payload = {
            "to_address": to_address,
            "amount": amount,
        }
    
        if memo:
            payload["memo"] = memo
    
        return await self.post(
            f"/api/nations/{nation_id}/distribute",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def distribute_bulk(
        self,
        discord_user_id: int,
        nation_id: int,
        distributions: list[dict],
        memo: str | None = None,
    ):
        payload = {
            "distributions": distributions,
        }
    
        if memo:
            payload["memo"] = memo
    
        return await self.post(
            f"/api/nations/{nation_id}/distribute-bulk",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def get_demurrage(self, nation_id: int):
        return await self.get(f"/api/nations/{nation_id}/demurrage")
    
    async def update_demurrage(
        self,
        discord_user_id: int,
        nation_id: int,
        enabled: bool,
        rate_bps: int,
    ):
        return await self.put(
            f"/api/nations/{nation_id}/demurrage",
            discord_user_id=discord_user_id,
            json={
                "demurrage_enabled": enabled,
                "demurrage_rate_bps": rate_bps,
            },
        )
    
    # ============================================================
    # BANKS / LOANS
    # ============================================================
    
    async def create_bank(
        self,
        discord_user_id: int,
        name: str,
        owner_user_id: int,
    ):
        return await self.post(
            "/api/banks",
            discord_user_id=discord_user_id,
            json={
                "name": name,
                "owner_user_id": owner_user_id,
            },
        )
    
    async def get_nation_banks(self, nation_id: int):
        return await self.get(f"/api/banks/nation/{nation_id}")
    
    async def get_bank(self, bank_id: int):
        return await self.get(f"/api/banks/{bank_id}")
    
    async def deactivate_bank(
        self,
        discord_user_id: int,
        bank_id: int,
    ):
        return await self.post(
            f"/api/banks/{bank_id}/deactivate",
            discord_user_id=discord_user_id,
        )
    
    async def get_bank_loans(
        self,
        discord_user_id: int,
        bank_id: int,
    ):
        return await self.get(
            f"/api/banks/{bank_id}/loans",
            discord_user_id=discord_user_id,
        )
    
    async def issue_loan(
        self,
        discord_user_id: int,
        bank_id: int,
        borrower_user_id: int,
        amount: int,
        memo: str | None = None,
    ):
        payload = {
            "borrower_user_id": borrower_user_id,
            "amount": amount,
        }
    
        if memo:
            payload["memo"] = memo
    
        return await self.post(
            f"/api/banks/{bank_id}/loans",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def forgive_bank_loan(
        self,
        discord_user_id: int,
        bank_id: int,
        loan_id: int,
    ):
        return await self.post(
            f"/api/banks/{bank_id}/loans/{loan_id}/forgive",
            discord_user_id=discord_user_id,
        )
    
    async def get_my_loans(self, discord_user_id: int):
        return await self.get(
            "/api/loans/mine",
            discord_user_id=discord_user_id,
        )
    
    async def pay_loan(
        self,
        discord_user_id: int,
        loan_id: int,
        amount: int,
    ):
        return await self.post(
            f"/api/loans/{loan_id}/pay",
            discord_user_id=discord_user_id,
            json={"amount": amount},
        )
    
    # ============================================================
    # SHOPS
    # ============================================================
    
    async def create_shop(
        self,
        discord_user_id: int,
        name: str,
        description: str | None = None,
        shop_type: str | None = None,
        mining_setup: str | None = None,
    ):
        payload = {
            "name": name,
        }
    
        if description:
            payload["description"] = description
    
        if shop_type:
            payload["shop_type"] = shop_type
    
        if mining_setup:
            payload["mining_setup"] = mining_setup
    
        return await self.post(
            "/api/shops",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def get_shops(
        self,
        nation_id: int | None = None,
        shop_type: str | None = None,
    ):
        params = {}
    
        if nation_id:
            params["nation_id"] = nation_id
    
        if shop_type:
            params["type"] = shop_type
    
        return await self.get(
            "/api/shops",
            params=params,
        )
    
    async def get_pending_shops(self, discord_user_id: int):
        return await self.get(
            "/api/shops/pending",
            discord_user_id=discord_user_id,
        )
    
    async def get_shop(self, shop_id: int):
        return await self.get(f"/api/shops/{shop_id}")
    
    async def create_listing(
        self,
        discord_user_id: int,
        shop_id: int,
        title: str,
        price: int,
        category: str,
        description: str | None = None,
    ):
        payload = {
            "title": title,
            "price": price,
            "category": category,
        }
    
        if description:
            payload["description"] = description
    
        return await self.post(
            f"/api/shops/{shop_id}/listings",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def buy_listing(
        self,
        discord_user_id: int,
        shop_id: int,
        listing_id: int,
    ):
        return await self.post(
            f"/api/shops/{shop_id}/listings/{listing_id}/buy",
            discord_user_id=discord_user_id,
        )
    
    # ============================================================
    # STOCKS
    # ============================================================
    
    async def get_stocks(
        self,
        stock_type: str | None = None,
        sort_by: str | None = None,
    ):
        params = {}
    
        if stock_type:
            params["stock_type"] = stock_type
    
        if sort_by:
            params["sort_by"] = sort_by
    
        return await self.get(
            "/api/stocks",
            params=params,
        )
    
    async def get_portfolio(self, discord_user_id: int):
        return await self.get(
            "/api/stocks/portfolio",
            discord_user_id=discord_user_id,
        )
    
    async def get_stock_rankings(self):
        return await self.get("/api/stocks/rankings")
    
    async def get_stock(self, ticker: str):
        return await self.get(f"/api/stocks/{ticker}")
    
    async def get_stock_history(self, ticker: str):
        return await self.get(f"/api/stocks/{ticker}/history")
    
    async def buy_stock(
        self,
        discord_user_id: int,
        ticker: str,
        shares: int,
    ):
        return await self.post(
            f"/api/stocks/{ticker}/buy",
            discord_user_id=discord_user_id,
            json={"shares": shares},
        )
    
    async def sell_stock(
        self,
        discord_user_id: int,
        ticker: str,
        shares: int,
    ):
        return await self.post(
            f"/api/stocks/{ticker}/sell",
            discord_user_id=discord_user_id,
            json={"shares": shares},
        )
    
    async def close_stock(
        self,
        discord_user_id: int,
        stock_id: int,
    ):
        return await self.post(
            f"/api/stocks/{stock_id}/close",
            discord_user_id=discord_user_id,
        )
    
    # ============================================================
    # WORLD MINT
    # ============================================================
    
    async def get_mint_stats(self, discord_user_id: int):
        return await self.get(
            "/api/mint/stats",
            discord_user_id=discord_user_id,
        )
    
    async def mint_execute(
        self,
        discord_user_id: int,
        to_address: str,
        amount: int,
        memo: str | None = None,
    ):
        payload = {
            "to_address": to_address,
            "amount": amount,
        }
    
        if memo:
            payload["memo"] = memo
    
        return await self.post(
            "/api/mint/execute",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def get_allocations(self, discord_user_id: int):
        return await self.get(
            "/api/mint/allocations",
            discord_user_id=discord_user_id,
        )
    
    async def approve_allocation(
        self,
        discord_user_id: int,
        allocation_id: int,
        approved_amount: int | None = None,
    ):
        payload = {}
    
        if approved_amount is not None:
            payload["approved_amount"] = approved_amount
    
        return await self.post(
            f"/api/mint/allocations/{allocation_id}/approve",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def execute_allocation(
        self,
        discord_user_id: int,
        allocation_id: int,
    ):
        return await self.post(
            f"/api/mint/allocations/{allocation_id}/execute",
            discord_user_id=discord_user_id,
        )
    
    async def execute_all_approved(self, discord_user_id: int):
        return await self.post(
            "/api/mint/execute-all-approved",
            discord_user_id=discord_user_id,
        )
    
    async def calculate_allocations(
        self,
        discord_user_id: int,
        period: str | None = None,
    ):
        payload = {}
    
        if period:
            payload["period"] = period
    
        return await self.post(
            "/api/mint/calculate-allocations",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def approve_nation(
        self,
        discord_user_id: int,
        nation_id: int,
    ):
        return await self.post(
            f"/api/mint/nations/{nation_id}/approve",
            discord_user_id=discord_user_id,
        )
    
    async def suspend_nation(
        self,
        discord_user_id: int,
        nation_id: int,
    ):
        return await self.post(
            f"/api/mint/nations/{nation_id}/suspend",
            discord_user_id=discord_user_id,
        )
    
    async def recalculate_gdp(self, discord_user_id: int):
        return await self.post(
            "/api/mint/recalculate-gdp",
            discord_user_id=discord_user_id,
        )
    
    async def get_gdp_history(
        self,
        discord_user_id: int,
        nation_id: int | None = None,
        limit: int = 50,
    ):
        params = {
            "limit": limit,
        }
    
        if nation_id:
            params["nation_id"] = nation_id
    
        return await self.get(
            "/api/mint/gdp-history",
            discord_user_id=discord_user_id,
            params=params,
        )
    
    async def get_stimulus_proposals(
        self,
        discord_user_id: int,
        status: str | None = None,
        limit: int = 50,
    ):
        params = {
            "limit": limit,
        }
    
        if status:
            params["status"] = status
    
        return await self.get(
            "/api/mint/stimulus-proposals",
            discord_user_id=discord_user_id,
            params=params,
        )
    
    async def approve_stimulus(
        self,
        discord_user_id: int,
        proposal_id: int,
        approved_amount: int | None = None,
        reason: str | None = None,
    ):
        payload = {}
    
        if approved_amount is not None:
            payload["approved_amount"] = approved_amount
    
        if reason:
            payload["reason"] = reason
    
        return await self.post(
            f"/api/mint/stimulus-proposals/{proposal_id}/approve",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def reject_stimulus(
        self,
        discord_user_id: int,
        proposal_id: int,
        reason: str | None = None,
    ):
        payload = {}
    
        if reason:
            payload["reason"] = reason
    
        return await self.post(
            f"/api/mint/stimulus-proposals/{proposal_id}/reject",
            discord_user_id=discord_user_id,
            json=payload,
        )
    
    async def get_mint_settings(self, discord_user_id: int):
        return await self.get(
            "/api/mint/settings",
            discord_user_id=discord_user_id,
        )
    
    async def update_mint_settings(
        self,
        discord_user_id: int,
        burn_bps: int | None = None,
        interest_cap_bps: int | None = None,
        interest_burn_bps: int | None = None,
    ):
        payload = {}
    
        if burn_bps is not None:
            payload["burn_bps"] = burn_bps
    
        if interest_cap_bps is not None:
            payload["interest_cap_bps"] = interest_cap_bps
    
        if interest_burn_bps is not None:
            payload["interest_burn_bps"] = interest_burn_bps
    
        return await self.post(
            "/api/mint/settings",
            discord_user_id=discord_user_id,
            json=payload,
        )
async def setup(bot):
    await bot.add_cog(
        TravelersExchangeAPI(
            bot,
            api_key="tx_live_c7f3247ac8aa28027e83e83e7f907192"
        )
    )