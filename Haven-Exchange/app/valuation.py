"""
Haven Economy — Stock Valuation Engine

Handles stock creation, ticker generation, and the three-pillar valuation
system that drives stock prices based on real performance metrics.
"""

import re
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, or_, select

from app.models import (
    Nation,
    Shop,
    ShopListing,
    Stock,
    StockHolding,
    StockValuation,
    Transaction,
    User,
)

# Serialises all stock buy/sell operations
_stock_lock = threading.Lock()

# Base prices for new stocks
NATION_BASE_PRICE = 10   # HM per share
BUSINESS_BASE_PRICE = 5  # HM per share
NATION_TOTAL_SHARES = 10_000
BUSINESS_MIN_SHARES = 100
BUSINESS_MAX_SHARES = 1_000

# IPO eligibility requirements
IPO_MIN_SALES = 10
IPO_MIN_DAYS = 30


# ---------------------------------------------------------------------------
# Ticker generation
# ---------------------------------------------------------------------------
def generate_ticker(name: str, db) -> str:
    """Generate a unique ticker from a name.

    Takes first letter of each word, uppercased. If collision, appends digits.
    Max 6 characters for the base ticker.
    """
    words = re.sub(r"[^a-zA-Z\s]", "", name).split()
    if not words:
        base = "STK"
    elif len(words) == 1:
        base = words[0][:4].upper()
    else:
        base = "".join(w[0] for w in words[:6]).upper()

    if not base:
        base = "STK"

    # Check for collision
    candidate = base
    suffix = 1
    while True:
        existing = db.execute(
            select(Stock).where(Stock.ticker == candidate)
        ).scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base}{suffix}"
        suffix += 1
        if suffix > 99:
            # Fallback: use longer substring
            candidate = name[:6].upper().replace(" ", "") + str(suffix)


# ---------------------------------------------------------------------------
# Stock creation
# ---------------------------------------------------------------------------
def create_nation_stock(db, nation: Nation) -> Stock:
    """Create a stock for a newly approved nation.

    Returns the created Stock object. Idempotent — skips if stock exists.
    """
    existing = db.execute(
        select(Stock).where(
            Stock.stock_type == "nation",
            Stock.entity_id == nation.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    ticker = generate_ticker(nation.name, db)
    stock = Stock(
        ticker=ticker,
        name=nation.name,
        stock_type="nation",
        entity_id=nation.id,
        total_shares=NATION_TOTAL_SHARES,
        available_shares=NATION_TOTAL_SHARES,
        current_price=NATION_BASE_PRICE,
        previous_price=NATION_BASE_PRICE,
    )
    db.add(stock)
    db.flush()

    # Create initial valuation snapshot
    now = datetime.now(timezone.utc)
    valuation = StockValuation(
        stock_id=stock.id,
        population_score=50,
        activity_score=50,
        cashflow_score=50,
        composite_score=50,
        calculated_price=NATION_BASE_PRICE,
        snapshot_date=now.strftime("%Y-%m-%d"),
    )
    db.add(valuation)
    stock.last_valued_at = now
    db.commit()
    db.refresh(stock)
    return stock


def create_business_stock(db, shop: Shop, num_shares: int) -> Stock:
    """Create a stock for a shop IPO.

    Validates eligibility: 10+ completed sales, 30+ days active.
    Raises ValueError on failure.
    """
    # Check no existing stock
    existing = db.execute(
        select(Stock).where(
            Stock.stock_type == "business",
            Stock.entity_id == shop.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("This shop already has a stock listed")

    # Validate eligibility
    if shop.total_sales < IPO_MIN_SALES:
        raise ValueError(
            f"Shop needs at least {IPO_MIN_SALES} completed sales "
            f"(currently has {shop.total_sales})"
        )

    if shop.created_at:
        days_active = (datetime.now(timezone.utc) - shop.created_at.replace(tzinfo=timezone.utc)).days
        if days_active < IPO_MIN_DAYS:
            raise ValueError(
                f"Shop must be at least {IPO_MIN_DAYS} days old "
                f"(currently {days_active} days)"
            )

    # Validate share count
    if num_shares < BUSINESS_MIN_SHARES or num_shares > BUSINESS_MAX_SHARES:
        raise ValueError(
            f"Number of shares must be between {BUSINESS_MIN_SHARES} and {BUSINESS_MAX_SHARES}"
        )

    ticker = generate_ticker(shop.name, db)
    stock = Stock(
        ticker=ticker,
        name=shop.name,
        stock_type="business",
        entity_id=shop.id,
        total_shares=num_shares,
        available_shares=num_shares,
        current_price=BUSINESS_BASE_PRICE,
        previous_price=BUSINESS_BASE_PRICE,
    )
    db.add(stock)
    db.flush()

    now = datetime.now(timezone.utc)
    valuation = StockValuation(
        stock_id=stock.id,
        population_score=50,
        activity_score=50,
        cashflow_score=50,
        composite_score=50,
        calculated_price=BUSINESS_BASE_PRICE,
        snapshot_date=now.strftime("%Y-%m-%d"),
    )
    db.add(valuation)
    stock.last_valued_at = now
    db.commit()
    db.refresh(stock)
    return stock


# ---------------------------------------------------------------------------
# Three-pillar valuation
# ---------------------------------------------------------------------------
def _score_nation_stock(db, stock: Stock, all_nation_metrics: dict) -> dict:
    """Calculate pillar scores for a nation stock."""
    nation_id = stock.entity_id
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Pillar 1: Population — active members
    member_count = (
        db.execute(
            select(func.count(User.id)).where(
                User.nation_id == nation_id,
                User.is_active == True,  # noqa: E712
            )
        ).scalar()
        or 0
    )

    # Pillar 2: Activity — members active in 30 days + tx count
    active_members = (
        db.execute(
            select(func.count(User.id)).where(
                User.nation_id == nation_id,
                User.last_active >= thirty_days_ago,
            )
        ).scalar()
        or 0
    )

    # Get all wallet addresses for nation members
    member_addresses = [
        row[0]
        for row in db.execute(
            select(User.wallet_address).where(User.nation_id == nation_id)
        ).all()
    ]

    # Also include the nation treasury address
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    treasury_addr = nation.treasury_address if nation else None

    tx_count = 0
    if member_addresses:
        tx_count = (
            db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.created_at >= thirty_days_ago,
                    or_(
                        Transaction.from_address.in_(member_addresses),
                        Transaction.to_address.in_(member_addresses),
                    ),
                )
            ).scalar()
            or 0
        )

    activity_metric = active_members + tx_count

    # Pillar 3: Cash Flow — HM flowing through nation (not treasury balance)
    cashflow = 0
    all_addrs = list(member_addresses)
    if treasury_addr:
        all_addrs.append(treasury_addr)

    if all_addrs:
        cashflow = (
            db.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.created_at >= thirty_days_ago,
                    or_(
                        Transaction.from_address.in_(all_addrs),
                        Transaction.to_address.in_(all_addrs),
                    ),
                )
            ).scalar()
            or 0
        )

    # Normalize against max values across all nations
    max_pop = all_nation_metrics.get("max_population", 0)
    max_act = all_nation_metrics.get("max_activity", 0)
    max_cf = all_nation_metrics.get("max_cashflow", 0)

    pop_score = round(member_count / max_pop * 100) if max_pop > 0 else 50
    act_score = round(activity_metric / max_act * 100) if max_act > 0 else 50
    cf_score = round(cashflow / max_cf * 100) if max_cf > 0 else 50

    # Clamp to 0-100
    pop_score = max(0, min(100, pop_score))
    act_score = max(0, min(100, act_score))
    cf_score = max(0, min(100, cf_score))

    composite = round((pop_score + act_score + cf_score) / 3)

    return {
        "population_score": pop_score,
        "activity_score": act_score,
        "cashflow_score": cf_score,
        "composite_score": composite,
        "raw": {
            "population": member_count,
            "activity": activity_metric,
            "cashflow": cashflow,
        },
    }


def _score_business_stock(db, stock: Stock, all_biz_metrics: dict) -> dict:
    """Calculate pillar scores for a business stock."""
    shop_id = stock.entity_id
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    # Get shop and owner
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None:
        return {
            "population_score": 0, "activity_score": 0,
            "cashflow_score": 0, "composite_score": 0,
        }

    owner = db.execute(select(User).where(User.id == shop.owner_id)).scalar_one_or_none()
    owner_addr = owner.wallet_address if owner else ""

    # Pillar 1: Customers — unique buyers in last 30 days
    unique_customers = (
        db.execute(
            select(func.count(distinct(Transaction.from_address))).where(
                Transaction.to_address == owner_addr,
                Transaction.tx_type == "PURCHASE",
                Transaction.created_at >= thirty_days_ago,
            )
        ).scalar()
        or 0
    )

    # Pillar 2: Activity — purchase tx count + listing count
    purchase_count = (
        db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.to_address == owner_addr,
                Transaction.tx_type == "PURCHASE",
                Transaction.created_at >= thirty_days_ago,
            )
        ).scalar()
        or 0
    )
    listing_count = (
        db.execute(
            select(func.count(ShopListing.id)).where(
                ShopListing.shop_id == shop_id,
            )
        ).scalar()
        or 0
    )
    activity_metric = purchase_count + listing_count

    # Pillar 3: Cash Flow — sales revenue in last 30 days
    revenue = (
        db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.to_address == owner_addr,
                Transaction.tx_type == "PURCHASE",
                Transaction.created_at >= thirty_days_ago,
            )
        ).scalar()
        or 0
    )

    # Normalize
    max_cust = all_biz_metrics.get("max_customers", 0)
    max_act = all_biz_metrics.get("max_activity", 0)
    max_cf = all_biz_metrics.get("max_cashflow", 0)

    pop_score = round(unique_customers / max_cust * 100) if max_cust > 0 else 50
    act_score = round(activity_metric / max_act * 100) if max_act > 0 else 50
    cf_score = round(revenue / max_cf * 100) if max_cf > 0 else 50

    pop_score = max(0, min(100, pop_score))
    act_score = max(0, min(100, act_score))
    cf_score = max(0, min(100, cf_score))

    composite = round((pop_score + act_score + cf_score) / 3)

    return {
        "population_score": pop_score,
        "activity_score": act_score,
        "cashflow_score": cf_score,
        "composite_score": composite,
    }


def _gather_nation_maxes(db) -> dict:
    """Gather max metrics across all nation stocks for normalization."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    nation_stocks = list(
        db.execute(
            select(Stock).where(Stock.stock_type == "nation", Stock.is_active == True)  # noqa: E712
        ).scalars().all()
    )

    max_pop = 0
    max_act = 0
    max_cf = 0

    for stock in nation_stocks:
        nation_id = stock.entity_id

        pop = (
            db.execute(
                select(func.count(User.id)).where(
                    User.nation_id == nation_id,
                    User.is_active == True,  # noqa: E712
                )
            ).scalar()
            or 0
        )
        max_pop = max(max_pop, pop)

        active = (
            db.execute(
                select(func.count(User.id)).where(
                    User.nation_id == nation_id,
                    User.last_active >= thirty_days_ago,
                )
            ).scalar()
            or 0
        )

        member_addrs = [
            r[0]
            for r in db.execute(
                select(User.wallet_address).where(User.nation_id == nation_id)
            ).all()
        ]

        nation = db.execute(
            select(Nation).where(Nation.id == nation_id)
        ).scalar_one_or_none()
        treasury_addr = nation.treasury_address if nation else None

        tx_count = 0
        if member_addrs:
            tx_count = (
                db.execute(
                    select(func.count(Transaction.id)).where(
                        Transaction.created_at >= thirty_days_ago,
                        or_(
                            Transaction.from_address.in_(member_addrs),
                            Transaction.to_address.in_(member_addrs),
                        ),
                    )
                ).scalar()
                or 0
            )
        max_act = max(max_act, active + tx_count)

        all_addrs = list(member_addrs)
        if treasury_addr:
            all_addrs.append(treasury_addr)

        cf = 0
        if all_addrs:
            cf = (
                db.execute(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                        Transaction.created_at >= thirty_days_ago,
                        or_(
                            Transaction.from_address.in_(all_addrs),
                            Transaction.to_address.in_(all_addrs),
                        ),
                    )
                ).scalar()
                or 0
            )
        max_cf = max(max_cf, cf)

    return {
        "max_population": max_pop,
        "max_activity": max_act,
        "max_cashflow": max_cf,
    }


def _gather_business_maxes(db) -> dict:
    """Gather max metrics across all business stocks for normalization."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    biz_stocks = list(
        db.execute(
            select(Stock).where(Stock.stock_type == "business", Stock.is_active == True)  # noqa: E712
        ).scalars().all()
    )

    max_cust = 0
    max_act = 0
    max_cf = 0

    for stock in biz_stocks:
        shop = db.execute(select(Shop).where(Shop.id == stock.entity_id)).scalar_one_or_none()
        if not shop:
            continue
        owner = db.execute(select(User).where(User.id == shop.owner_id)).scalar_one_or_none()
        if not owner:
            continue
        addr = owner.wallet_address

        cust = (
            db.execute(
                select(func.count(distinct(Transaction.from_address))).where(
                    Transaction.to_address == addr,
                    Transaction.tx_type == "PURCHASE",
                    Transaction.created_at >= thirty_days_ago,
                )
            ).scalar()
            or 0
        )
        max_cust = max(max_cust, cust)

        pcount = (
            db.execute(
                select(func.count(Transaction.id)).where(
                    Transaction.to_address == addr,
                    Transaction.tx_type == "PURCHASE",
                    Transaction.created_at >= thirty_days_ago,
                )
            ).scalar()
            or 0
        )
        lcount = (
            db.execute(
                select(func.count(ShopListing.id)).where(
                    ShopListing.shop_id == stock.entity_id,
                )
            ).scalar()
            or 0
        )
        max_act = max(max_act, pcount + lcount)

        rev = (
            db.execute(
                select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                    Transaction.to_address == addr,
                    Transaction.tx_type == "PURCHASE",
                    Transaction.created_at >= thirty_days_ago,
                )
            ).scalar()
            or 0
        )
        max_cf = max(max_cf, rev)

    return {
        "max_customers": max_cust,
        "max_activity": max_act,
        "max_cashflow": max_cf,
    }


# ---------------------------------------------------------------------------
# Recalculation
# ---------------------------------------------------------------------------
def recalculate_all_prices(db) -> int:
    """Recalculate prices for all active stocks.

    Returns the number of stocks recalculated.
    """
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    # Gather normalization maxes
    nation_maxes = _gather_nation_maxes(db)
    biz_maxes = _gather_business_maxes(db)

    stocks = list(
        db.execute(
            select(Stock).where(Stock.is_active == True)  # noqa: E712
        ).scalars().all()
    )

    count = 0
    for stock in stocks:
        if stock.stock_type == "nation":
            scores = _score_nation_stock(db, stock, nation_maxes)
            base_price = NATION_BASE_PRICE
        elif stock.stock_type == "business":
            scores = _score_business_stock(db, stock, biz_maxes)
            base_price = BUSINESS_BASE_PRICE
        else:
            continue

        composite = scores["composite_score"]
        new_price = max(1, round(base_price * composite / 50))

        # Update stock
        stock.previous_price = stock.current_price
        stock.current_price = new_price
        stock.last_valued_at = now

        # Save valuation snapshot
        valuation = StockValuation(
            stock_id=stock.id,
            population_score=scores["population_score"],
            activity_score=scores["activity_score"],
            cashflow_score=scores["cashflow_score"],
            composite_score=composite,
            calculated_price=new_price,
            snapshot_date=today,
        )
        db.add(valuation)
        count += 1

    db.commit()
    return count


def maybe_recalculate(db) -> None:
    """Recalculate prices if the most recent valuation is older than 24 hours."""
    latest = db.execute(
        select(Stock.last_valued_at)
        .where(Stock.is_active == True)  # noqa: E712
        .order_by(Stock.last_valued_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest is None:
        return  # No stocks exist

    now = datetime.now(timezone.utc)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)

    if (now - latest).total_seconds() > 86400:
        recalculate_all_prices(db)
