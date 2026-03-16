"""
Travelers Exchange — Wallet Address Generation
"""

import hashlib

from app.config import settings


def generate_wallet_address(user_id: int, salt: str = "") -> str:
    """Generate a deterministic wallet address from user_id + salt.

    Uses SHA-256 hash of "{user_id}:{salt}", takes the first 8 hex characters,
    and prepends the wallet prefix.

    Format: TRV-xxxxxxxx (8 hex chars)

    Args:
        user_id: The user's database ID.
        salt: Optional salt for additional uniqueness.

    Returns:
        A wallet address string like "TRV-a1b2c3d4".
    """
    raw = f"{user_id}:{salt}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    short_hash = digest[:8]
    return f"{settings.WALLET_PREFIX}{short_hash}"


def generate_nation_treasury_address(nation_id: int, salt: str = "") -> str:
    """Generate a deterministic treasury wallet address for a nation.

    Format: TRV-NATION-xxxxxxxx (8 hex chars)

    Args:
        nation_id: The nation's database ID.
        salt: Optional salt for additional uniqueness.

    Returns:
        A treasury address string like "TRV-NATION-a1b2c3d4".
    """
    raw = f"nation:{nation_id}:{salt}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    short_hash = digest[:8]
    return f"{settings.NATION_WALLET_PREFIX}{short_hash}"


def generate_bank_wallet_address(bank_id: int) -> str:
    """Generate a deterministic wallet address for a bank.

    Format: TRV-BANK-xxxxxxxx (8 hex chars)

    Args:
        bank_id: The bank's database ID.

    Returns:
        A bank wallet address string like "TRV-BANK-a1b2c3d4".
    """
    raw = f"{bank_id}:bank_salt"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    short_hash = digest[:8]
    return f"TRV-BANK-{short_hash}"
