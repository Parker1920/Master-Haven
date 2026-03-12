"""
Travelers Exchange — Application Configuration
"""


class Settings:
    """Central configuration for the Travelers Exchange platform."""

    # Database
    DB_PATH: str = "data/economy.db"

    # Security — CHANGE THIS IN PRODUCTION
    SECRET_KEY: str = "travelers-exchange-secret-change-me"

    # Wallet address prefixes
    WALLET_PREFIX: str = "TRV-"
    NATION_WALLET_PREFIX: str = "TRV-NATION-"

    # The World Mint's fixed wallet address
    WORLD_MINT_ADDRESS: str = "TRV-00000000"

    # Minting parameters
    BASE_RATE: int = 500  # coins per active member per month

    # Session management
    SESSION_EXPIRY_DAYS: int = 7

    # Currency display
    CURRENCY_NAME: str = "Travelers Coin"
    CURRENCY_SHORT: str = "TC"


settings = Settings()
