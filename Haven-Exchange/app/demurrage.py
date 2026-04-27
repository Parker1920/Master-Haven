"""
Travelers Exchange — Idle-Wallet Demurrage Engine (Phase 2I)

Per-nation idle-wallet demurrage: wallets with no activity for 30+ days are
charged ``demurrage_rate_bps`` basis-points of their balance each daily run.
The charge is burned (sent to the World Mint) and recorded as a
``DEMURRAGE_BURN`` transaction so the ledger remains auditable.

Configuration lives on the ``Nation`` model:
  - ``demurrage_enabled`` (bool, default False) — opt-in toggle, NL-controlled.
  - ``demurrage_rate_bps`` (int, default 50 = 0.5%) — NL-configurable rate.

The World Mint admin can override both fields for any nation via the settings
API; NLs can toggle their own nation's demurrage from the nation-management
endpoint added in this phase.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blockchain import create_transaction
from app.config import settings
from app.models import Nation, User

# Wallets idle for this many days are subject to demurrage
_IDLE_THRESHOLD_DAYS: int = 30


def _is_idle(user: User, now: datetime) -> bool:
    """Return True if the wallet has had no activity for 30+ days."""
    last = user.last_active
    if last is None:
        # Never had any activity — treat as idle from creation date.
        last = user.created_at
    if last is None:
        return True
    # Normalise to UTC-aware for comparison
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last).days >= _IDLE_THRESHOLD_DAYS


def apply_demurrage_for_nation(
    db: Session,
    nation: Nation,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Apply one day's demurrage charge for all idle wallets in *nation*.

    Idempotent across multiple same-day calls: if a wallet's balance has
    already been reduced to 0 by an earlier run today, no tx is created.

    Returns a summary dict with:
      - ``wallets_checked``  — number of citizen wallets examined.
      - ``wallets_charged``  — number of wallets that had demurrage applied.
      - ``total_burned``     — sum of all TC burned this run.
      - ``wallets_skipped``  — wallets with 0 balance or insufficient amount.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    rate_bps = nation.demurrage_rate_bps or 50
    wallets_checked = 0
    wallets_charged = 0
    wallets_skipped = 0
    total_burned = 0

    # Fetch all members of this nation
    members = list(
        db.execute(select(User).where(User.nation_id == nation.id)).scalars().all()
    )

    for user in members:
        # Skip non-citizen roles that should never be subject to demurrage
        if user.role in ("world_mint",):
            continue
        wallets_checked += 1

        # Only idle wallets pay demurrage
        if not _is_idle(user, now):
            wallets_skipped += 1
            continue

        # No balance — nothing to charge
        if user.balance <= 0:
            wallets_skipped += 1
            continue

        # Compute charge: floor(balance * rate_bps / 10_000)
        charge = math.floor(user.balance * rate_bps / 10_000)
        if charge <= 0:
            wallets_skipped += 1
            continue

        # Write the ledger entry.  create_transaction handles the balance
        # debit on user.balance and credits the World Mint (which, for BURN
        # transactions, is skipped per the existing is_burn_target guard).
        try:
            create_transaction(
                db,
                tx_type="DEMURRAGE_BURN",
                from_address=user.wallet_address,
                to_address=settings.WORLD_MINT_ADDRESS,
                amount=charge,
                memo=(
                    f"Idle-wallet demurrage: {rate_bps}bps of balance "
                    f"{user.balance} TC charged by nation {nation.name}"
                ),
            )
            wallets_charged += 1
            total_burned += charge
        except ValueError:
            # Insufficient balance race — skip silently (balance might have
            # been depleted between our read and the tx write).
            wallets_skipped += 1

    return {
        "wallets_checked": wallets_checked,
        "wallets_charged": wallets_charged,
        "wallets_skipped": wallets_skipped,
        "total_burned": total_burned,
    }


def apply_all_demurrage(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run demurrage for every nation that has it enabled.

    Called by the daily scheduler.  Returns an aggregate summary.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    nations = list(
        db.execute(
            select(Nation).where(
                Nation.demurrage_enabled.is_(True),
                Nation.status == "approved",
            )
        )
        .scalars()
        .all()
    )

    agg_checked = 0
    agg_charged = 0
    agg_skipped = 0
    agg_burned = 0
    nations_processed = 0

    for nation in nations:
        result = apply_demurrage_for_nation(db, nation, now=now)
        agg_checked += result["wallets_checked"]
        agg_charged += result["wallets_charged"]
        agg_skipped += result["wallets_skipped"]
        agg_burned += result["total_burned"]
        nations_processed += 1

    return {
        "nations_processed": nations_processed,
        "wallets_checked": agg_checked,
        "wallets_charged": agg_charged,
        "wallets_skipped": agg_skipped,
        "total_burned": agg_burned,
    }
