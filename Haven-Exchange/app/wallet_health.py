"""
Travelers Exchange — Wallet Health Metrics

Per-user activity counters used to surface wallet activity on the public
wallet view and to drive idle-wallet demurrage (Phase 2I).

Real-time bumps to ``transaction_count_lifetime``, ``transaction_count_30d``,
``volume_lifetime``, and ``volume_30d`` happen inside
:func:`app.blockchain.create_transaction` on every confirmed user-side
transfer.  This module owns the daily reconciliation job that **decays**
activity that has aged past the 30-day window — without it, the 30d counters
would only ever grow.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Transaction, User


def _calculate_wallet_health_30d(db: Session, user: User) -> tuple[int, int]:
    """Return (transaction_count_30d, volume_30d) for a user from raw ledger.

    Counts every transaction in the last 30 days where the user's wallet
    is either the sender or receiver.  GENESIS rows are excluded since
    they don't represent real wallet activity.  Each tx is counted once
    on each side it touches the wallet (matches the real-time bump
    behaviour in ``create_transaction``).
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    addr = user.wallet_address

    rows = list(
        db.execute(
            select(Transaction.from_address, Transaction.to_address, Transaction.amount)
            .where(
                Transaction.created_at >= thirty_days_ago,
                Transaction.tx_type != "GENESIS",
                or_(
                    Transaction.from_address == addr,
                    Transaction.to_address == addr,
                ),
            )
        ).all()
    )

    tx_count = 0
    volume = 0
    for from_addr, to_addr, amount in rows:
        # Each side the wallet appears on counts as one event in the
        # real-time path; mirror that here so reconciliation matches.
        if from_addr == addr:
            tx_count += 1
            volume += amount
        if to_addr == addr:
            tx_count += 1
            volume += amount

    return tx_count, volume


def _calculate_lifetime_stats(db: Session, user: User) -> tuple[int, int]:
    """Return (transaction_count_lifetime, volume_lifetime) from raw ledger.

    Used for backfill of pre-Phase-2H rows where the columns were zero.
    Mirrors the real-time bump rule: count each side the wallet appears on.
    """
    addr = user.wallet_address
    rows = list(
        db.execute(
            select(Transaction.from_address, Transaction.to_address, Transaction.amount)
            .where(
                Transaction.tx_type != "GENESIS",
                or_(
                    Transaction.from_address == addr,
                    Transaction.to_address == addr,
                ),
            )
        ).all()
    )
    count = 0
    volume = 0
    for from_addr, to_addr, amount in rows:
        if from_addr == addr:
            count += 1
            volume += amount
        if to_addr == addr:
            count += 1
            volume += amount
    return count, volume


def recalculate_wallet_health(db: Session) -> int:
    """Refresh the wallet-health metrics for every user.

    Decays 30-day counters whose underlying transactions have aged past 30
    days, and fixes any drift between the real-time counters and the canonical
    ledger.  Lifetime counters are reconciled too (cheap; one extra query per
    user).  Returns the number of users touched.
    """
    now = datetime.now(timezone.utc)
    users = list(db.execute(select(User)).scalars().all())
    for user in users:
        tx30, vol30 = _calculate_wallet_health_30d(db, user)
        tx_life, vol_life = _calculate_lifetime_stats(db, user)
        user.transaction_count_30d = tx30
        user.volume_30d = vol30
        user.transaction_count_lifetime = tx_life
        user.volume_lifetime = vol_life
        user.wallet_health_last_calculated = now
    db.commit()
    return len(users)
