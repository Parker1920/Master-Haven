"""
Travelers Exchange — GDP Calculation Engine

Computes a GDP multiplier (0.5x–2.0x) for each nation based on four
economic pillars.  The multiplier drives exchange rates between national
currencies: 1 NationCoin = (gdp_multiplier / 100) TC.

Pillars (25 % each):
  1. Treasury Health  — treasury balance per capita
  2. Transaction Volume — transaction count involving nation members (30 d)
  3. Business Revenue  — total shop revenue for the nation (30 d)
  4. Active Citizens   — ratio of recently-active members to total members
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    GdpSnapshot,
    Nation,
    Shop,
    Transaction,
    User,
)


# ---------------------------------------------------------------------------
# Multiplier range
# ---------------------------------------------------------------------------
GDP_MIN = 50    # 0.50x  (stored as int × 100)
GDP_MAX = 200   # 2.00x


# ---------------------------------------------------------------------------
# Per-nation GDP calculation
# ---------------------------------------------------------------------------
def _calculate_nation_gdp(db: Session, nation: Nation, maxes: dict) -> dict:
    """Compute the four GDP pillar scores for a single nation.

    Returns a dict with per-pillar scores (0–100), composite score, and
    the resulting GDP multiplier (int × 100).
    """
    nation_id = nation.id
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # -- Pillar 1: Treasury Health (balance per capita) ---------------------
    member_count = (
        db.execute(
            select(func.count(User.id)).where(
                User.nation_id == nation_id,
                User.is_active == True,  # noqa: E712
            )
        ).scalar()
        or 0
    )
    per_capita = (
        nation.treasury_balance / member_count if member_count > 0 else 0
    )

    # -- Pillar 2: Transaction Volume (30-day) ----------------------------
    member_addresses = [
        row[0]
        for row in db.execute(
            select(User.wallet_address).where(User.nation_id == nation_id)
        ).all()
    ]
    all_addrs = list(member_addresses)
    if nation.treasury_address:
        all_addrs.append(nation.treasury_address)

    tx_count = 0
    if all_addrs:
        tx_count = (
            db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.created_at >= thirty_days_ago,
                    or_(
                        Transaction.from_address.in_(all_addrs),
                        Transaction.to_address.in_(all_addrs),
                    ),
                )
            ).scalar()
            or 0
        )

    # -- Pillar 3: Business Revenue (30-day shop revenue) -----------------
    # Sum revenue from purchase transactions flowing to shop owners in this nation
    shop_owner_addrs = [
        row[0]
        for row in db.execute(
            select(User.wallet_address)
            .join(Shop, Shop.owner_id == User.id)
            .where(Shop.nation_id == nation_id)
        ).all()
    ]
    revenue = 0
    if shop_owner_addrs:
        revenue = (
            db.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.tx_type == "PURCHASE",
                    Transaction.created_at >= thirty_days_ago,
                    Transaction.to_address.in_(shop_owner_addrs),
                )
            ).scalar()
            or 0
        )

    # -- Pillar 4: Active Citizens (% active in 30 d) --------------------
    active_count = (
        db.execute(
            select(func.count(User.id)).where(
                User.nation_id == nation_id,
                User.last_active >= thirty_days_ago,
            )
        ).scalar()
        or 0
    )
    active_ratio = active_count / member_count if member_count > 0 else 0

    # -- Normalize each pillar against max across all nations (0–100) -----
    max_pc = maxes.get("max_per_capita", 0)
    max_tx = maxes.get("max_tx_count", 0)
    max_rev = maxes.get("max_revenue", 0)
    max_ar = maxes.get("max_active_ratio", 0)

    treasury_score = _norm(per_capita, max_pc)
    activity_score = _norm(tx_count, max_tx)
    revenue_score = _norm(revenue, max_rev)
    citizens_score = _norm(active_ratio, max_ar)

    composite = round((treasury_score + activity_score + revenue_score + citizens_score) / 4)

    # Map composite (0–100) → multiplier (GDP_MIN–GDP_MAX)
    # multiplier = 50 + (composite / 100) * 150  →  range 50–200
    multiplier = round(GDP_MIN + (composite / 100) * (GDP_MAX - GDP_MIN))
    multiplier = max(GDP_MIN, min(GDP_MAX, multiplier))

    return {
        "treasury_score": treasury_score,
        "activity_score": activity_score,
        "revenue_score": revenue_score,
        "citizens_score": citizens_score,
        "composite_score": composite,
        "gdp_multiplier": multiplier,
        "raw": {
            "per_capita": per_capita,
            "tx_count": tx_count,
            "revenue": revenue,
            "active_ratio": round(active_ratio, 4),
            "member_count": member_count,
        },
    }


def _norm(value: float, max_value: float) -> int:
    """Normalize a value to 0–100 against a max.  Returns 50 if max is 0."""
    if max_value <= 0:
        return 50
    return max(0, min(100, round(value / max_value * 100)))


# ---------------------------------------------------------------------------
# Gather max metrics across all approved nations
# ---------------------------------------------------------------------------
def _gather_gdp_maxes(db: Session) -> dict:
    """Pre-compute the maximum value for each pillar across all nations.

    Used for peer-relative normalization.
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    nations = list(
        db.execute(
            select(Nation).where(Nation.status == "approved")
        ).scalars().all()
    )

    max_per_capita = 0.0
    max_tx_count = 0
    max_revenue = 0
    max_active_ratio = 0.0

    for nation in nations:
        nid = nation.id

        # Member count
        mc = (
            db.execute(
                select(func.count(User.id)).where(
                    User.nation_id == nid,
                    User.is_active == True,  # noqa: E712
                )
            ).scalar()
            or 0
        )

        # Per-capita treasury
        pc = nation.treasury_balance / mc if mc > 0 else 0
        max_per_capita = max(max_per_capita, pc)

        # Transaction count
        addrs = [
            r[0] for r in db.execute(
                select(User.wallet_address).where(User.nation_id == nid)
            ).all()
        ]
        if nation.treasury_address:
            addrs.append(nation.treasury_address)

        txc = 0
        if addrs:
            txc = (
                db.execute(
                    select(func.count(Transaction.id)).where(
                        Transaction.created_at >= thirty_days_ago,
                        or_(
                            Transaction.from_address.in_(addrs),
                            Transaction.to_address.in_(addrs),
                        ),
                    )
                ).scalar()
                or 0
            )
        max_tx_count = max(max_tx_count, txc)

        # Shop revenue
        shop_addrs = [
            r[0] for r in db.execute(
                select(User.wallet_address)
                .join(Shop, Shop.owner_id == User.id)
                .where(Shop.nation_id == nid)
            ).all()
        ]
        rev = 0
        if shop_addrs:
            rev = (
                db.execute(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                        Transaction.tx_type == "PURCHASE",
                        Transaction.created_at >= thirty_days_ago,
                        Transaction.to_address.in_(shop_addrs),
                    )
                ).scalar()
                or 0
            )
        max_revenue = max(max_revenue, rev)

        # Active ratio
        ac = (
            db.execute(
                select(func.count(User.id)).where(
                    User.nation_id == nid,
                    User.last_active >= thirty_days_ago,
                )
            ).scalar()
            or 0
        )
        ar = ac / mc if mc > 0 else 0
        max_active_ratio = max(max_active_ratio, ar)

    return {
        "max_per_capita": max_per_capita,
        "max_tx_count": max_tx_count,
        "max_revenue": max_revenue,
        "max_active_ratio": max_active_ratio,
    }


# ---------------------------------------------------------------------------
# Recalculate all nations
# ---------------------------------------------------------------------------
def _calculate_shop_gdp_contribution(db: Session, shop: Shop) -> int:
    """Sum 30-day PURCHASE inflow to the given shop's owner wallet.

    Returns the running 30-day GDP contribution in TC.  Used by the daily
    GDP job to update ``Shop.gdp_contribution_30d`` and to rank shops in
    the marketplace by economic contribution rather than recency.
    """
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    owner = db.execute(
        select(User).where(User.id == shop.owner_id)
    ).scalar_one_or_none()
    if owner is None:
        return 0
    return (
        db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.tx_type == "PURCHASE",
                Transaction.created_at >= thirty_days_ago,
                Transaction.to_address == owner.wallet_address,
            )
        ).scalar()
        or 0
    )


def recalculate_all_shop_contributions(db: Session) -> int:
    """Refresh ``Shop.gdp_contribution_30d`` for every shop in the system.

    Includes pending/rejected shops too — the contribution is purely an
    audit metric of historical revenue and is independent of approval state.
    Returns the number of shops touched.
    """
    now = datetime.now(timezone.utc)
    shops = list(db.execute(select(Shop)).scalars().all())
    for shop in shops:
        shop.gdp_contribution_30d = _calculate_shop_gdp_contribution(db, shop)
        shop.gdp_last_calculated = now
    db.commit()
    return len(shops)


def recalculate_all_gdp(db: Session) -> int:
    """Recalculate GDP for every approved nation.

    Saves a GdpSnapshot per nation and updates the cached columns on the
    Nation row.  Also refreshes per-shop ``gdp_contribution_30d`` so the
    marketplace ranking stays in sync.  Returns the number of nations
    recalculated.
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    maxes = _gather_gdp_maxes(db)

    nations = list(
        db.execute(
            select(Nation).where(Nation.status == "approved")
        ).scalars().all()
    )

    count = 0
    for nation in nations:
        scores = _calculate_nation_gdp(db, nation, maxes)

        # Update cached columns
        nation.gdp_score = scores["composite_score"]
        nation.gdp_multiplier = scores["gdp_multiplier"]
        nation.gdp_last_calculated = now

        # Save snapshot
        snapshot = GdpSnapshot(
            nation_id=nation.id,
            treasury_score=scores["treasury_score"],
            activity_score=scores["activity_score"],
            revenue_score=scores["revenue_score"],
            citizens_score=scores["citizens_score"],
            composite_score=scores["composite_score"],
            gdp_multiplier=scores["gdp_multiplier"],
            snapshot_date=today,
        )
        db.add(snapshot)
        count += 1

    # Phase 2E: refresh per-shop GDP contribution so the marketplace
    # ranking reflects the same 30-day window the nation pillar uses.
    shops = list(db.execute(select(Shop)).scalars().all())
    for shop in shops:
        shop.gdp_contribution_30d = _calculate_shop_gdp_contribution(db, shop)
        shop.gdp_last_calculated = now

    db.commit()
    return count


def maybe_recalculate_gdp(db: Session) -> None:
    """Recalculate GDP if the most recent snapshot is older than 24 hours."""
    latest = db.execute(
        select(Nation.gdp_last_calculated)
        .where(Nation.status == "approved")
        .order_by(Nation.gdp_last_calculated.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest is None:
        # No approved nations or never calculated — try anyway
        recalculate_all_gdp(db)
        return

    now = datetime.now(timezone.utc)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)

    if (now - latest).total_seconds() > 86400:
        recalculate_all_gdp(db)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------
def get_gdp_multiplier_float(nation: Nation) -> float:
    """Return the GDP multiplier as a float (e.g. 1.8)."""
    return (nation.gdp_multiplier or 100) / 100.0


def tc_to_national(tc_amount: int, gdp_multiplier: int) -> float:
    """Convert a TC amount to national coin units.

    gdp_multiplier is stored as int × 100 (e.g. 180 = 1.8x).
    1 NationCoin = (gdp_multiplier / 100) TC
    So: national_coins = tc_amount / (gdp_multiplier / 100) = tc_amount * 100 / gdp_multiplier
    """
    if gdp_multiplier <= 0:
        gdp_multiplier = 100
    return round(tc_amount * 100 / gdp_multiplier, 2)


def national_to_tc(national_amount: float, gdp_multiplier: int) -> int:
    """Convert national coin units to TC.

    national_amount × (gdp_multiplier / 100) = TC
    """
    if gdp_multiplier <= 0:
        gdp_multiplier = 100
    return round(national_amount * gdp_multiplier / 100)


def format_currency(tc_amount: int, nation: Nation | None = None) -> dict:
    """Return a display dict with national coin amount, TC amount, and currency info.

    Used by templates to show both national and TC values.
    """
    if nation and nation.currency_code and nation.gdp_multiplier:
        national = tc_to_national(tc_amount, nation.gdp_multiplier)
        return {
            "display": national,
            "tc": tc_amount,
            "code": nation.currency_code,
            "name": nation.currency_name or nation.currency_code,
            "gdp": nation.gdp_multiplier / 100.0,
        }
    return {
        "display": tc_amount,
        "tc": tc_amount,
        "code": "TC",
        "name": "Travelers Coin",
        "gdp": 1.0,
    }
