import os
import math
from typing import Any, Dict, Optional
import httpx
from discord.ext import commands

class ExchangeAPIError(Exception):
    """Custom exception to catch and bubble up FastAPI errors to the Discord UI."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


class ExchangeAPIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(base_url=self.base_url)

    async def close(self):
        await self.client.aclose()

    async def _request(
        self, method: str, path: str, discord_user_id: Optional[str] = None,
        json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if discord_user_id:
            headers["X-Discord-User-Id"] = str(discord_user_id)

        try:
            response = await self.client.request(
                method=method, url=path, headers=headers, json=json_data, params=params
            )
            if response.is_error:
                try:
                    error_data = response.json()
                    detail = error_data.get("detail", "Unknown error occurred.")
                except Exception:
                    detail = response.text or "Internal Server Error"
                raise ExchangeAPIError(response.status_code, detail)

            return response.json() if response.content else {}
        except httpx.RequestError as exc:
            raise ExchangeAPIError(500, f"Transport error connecting to Exchange: {exc}")

    # --- Formatting Helpers ---
    @staticmethod
    def format_tc(amount: int) -> str: 
        return f"{amount:,} TC"
    
    @staticmethod
    def format_wallet_short(address: str) -> str:
        return f"`{address}`" if len(address) <= 12 else f"`{address[:8]}...{address[-4:]}`"

    # --- API Methods ---
    async def get_wallet(self, discord_user_id: str) -> Dict[str, Any]:
        return await self._request("GET", "/api/wallet", discord_user_id=discord_user_id)

    async def list_nations(self) -> list:
        # Fixed: Moved to ExchangeAPIClient and fixed indentation block
        return await self._request("GET", "/api/nations") 

    async def join_nation(self, discord_user_id: str, nation_id: int) -> Dict[str, Any]:
        # Fixed: Moved to ExchangeAPIClient and fixed indentation block
        return await self._request(
            "POST",
            f"/api/nations/{nation_id}/join",
            discord_user_id=discord_user_id,
        )


class ExchangeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        base_url = os.getenv("EXCHANGE_BASE_URL", "https://travelers-exchange.online")
        api_key = os.getenv("EXCHANGE_API")
        
        self.client = ExchangeAPIClient(base_url=base_url, api_key=api_key)

    async def cog_unload(self):
        """Runs automatically if the cog is reloaded or bot shuts down."""
        await self.client.close()


async def setup(bot):
    await bot.add_cog(ExchangeCog(bot))
