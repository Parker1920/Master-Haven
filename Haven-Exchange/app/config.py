"""
Haven Economy — Application Configuration
"""


class Settings:
    """Central configuration for the Haven Economy platform."""

    # Database
    DB_PATH: str = "data/economy.db"

    # Security — CHANGE THIS IN PRODUCTION
    SECRET_KEY: str = "haven-economy-secret-change-me"

    # Wallet address prefixes
    WALLET_PREFIX: str = "HVN-"
    NATION_WALLET_PREFIX: str = "HVN-NATION-"

    # The World Mint's fixed wallet address
    WORLD_MINT_ADDRESS: str = "HVN-00000000"

    # Minting parameters
    BASE_RATE: int = 500  # coins per active member per month

    # Session management
    SESSION_EXPIRY_DAYS: int = 7

    # Currency display
    CURRENCY_NAME: str = "Haven Marks"
    CURRENCY_SHORT: str = "HM"


settings = Settings()
