"""
Travelers Exchange — Stock Market API Routes

Provides API endpoints for stock listing, trading, portfolio, and rankings.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.blockchain import create_transaction
from app.database import get_db
from app.models import (
    Nation,
    Shop,
    Stock,
    StockHolding,
    StockTransaction,
    StockValuation,
    User,
)
from app.valuation import _stock_lock, maybe_recalculate

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class BuyStockRequest(BaseModel):
    shares: int


class SellStockRequest(BaseModel):
    shares: int


class CloseStockRequest(BaseModel):
    reason: str | None = None


# ---------------------------------------------------------------------------
# GET /api/stocks — List all active stocks
# ---------------------------------------------------------------------------
@router.get("")
def list_stocks(
    stock_type: str | None = Query(None),
    sort_by: str = Query("ticker"),
    db: Session = Depends(get_db),
):
    maybe_recalculate(db)

    conditions = [Stock.is_active == True]  # noqa: E712
    if stock_type in ("nation", "business"):
        conditions.append(Stock.stock_type == stock_type)

    query = select(Stock).where(*conditions)

    if sort_by == "price":
        query = query.order_by(Stock.current_price.desc())
    elif sort_by == "change":
        query = query.order_by(
            (Stock.current_price - Stock.previous_price).desc()
        )
    else:
        query = query.order_by(Stock.ticker.asc())

    stocks = list(db.execute(query).scalars().all())

    result = []
    for s in stocks:
        change = s.current_price - s.previous_price
        change_pct = (
            round(change / s.previous_price * 100)
            if s.previous_price > 0
            else 0
        )

        # Get entity name
        entity_name = s.name
        if s.stock_type == "nation":
            nation = db.execute(
                select(Nation).where(Nation.id == s.entity_id)
            ).scalar_one_or_none()
            if nation:
                entity_name = nation.name
        elif s.stock_type == "business":
            shop = db.execute(
                select(Shop).where(Shop.id == s.entity_id)
            ).scalar_one_or_none()
            if shop:
                entity_name = shop.name

        result.append({
            "ticker": s.ticker,
            "name": s.name,
            "stock_type": s.stock_type,
            "current_price": s.current_price,
            "previous_price": s.previous_price,
            "price_change": change,
            "price_change_pct": change_pct,
            "total_shares": s.total_shares,
            "available_shares": s.available_shares,
            "entity_name": entity_name,
        })

    return {"stocks": result}


# ---------------------------------------------------------------------------
# GET /api/stocks/portfolio — User's stock holdings
# (Must be before /{ticker} to avoid being captured as a ticker)
# ---------------------------------------------------------------------------
@router.get("/portfolio", name="api_portfolio")
def get_portfolio(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    holdings = list(
        db.execute(
            select(StockHolding)
            .where(StockHolding.user_id == current_user.id)
            .order_by(StockHolding.acquired_at.desc())
        ).scalars().all()
    )

    total_value = 0
    total_invested = 0
    items = []

    for h in holdings:
        stock = db.execute(
            select(Stock).where(Stock.id == h.stock_id)
        ).scalar_one_or_none()
        if stock is None:
            continue

        current_value = h.shares * stock.current_price
        invested = h.shares * h.avg_buy_price
        gain_loss = current_value - invested

        total_value += current_value
        total_invested += invested

        items.append({
            "ticker": stock.ticker,
            "name": stock.name,
            "stock_type": stock.stock_type,
            "shares": h.shares,
            "avg_buy_price": h.avg_buy_price,
            "current_price": stock.current_price,
            "current_value": current_value,
            "gain_loss": gain_loss,
        })

    return {
        "holdings": items,
        "total_value": total_value,
        "total_invested": total_invested,
        "total_gain_loss": total_value - total_invested,
    }


# ---------------------------------------------------------------------------
# GET /api/stocks/rankings — Rankings by performance
# (Must be before /{ticker} to avoid being captured as a ticker)
# ---------------------------------------------------------------------------
@router.get("/rankings", name="api_rankings")
def get_rankings(
    db: Session = Depends(get_db),
):
    maybe_recalculate(db)

    stocks = list(
        db.execute(
            select(Stock)
            .where(Stock.is_active == True)  # noqa: E712
            .order_by(Stock.current_price.desc())
        ).scalars().all()
    )

    result = []
    for s in stocks:
        change = s.current_price - s.previous_price
        change_pct = (
            round(change / s.previous_price * 100)
            if s.previous_price > 0
            else 0
        )

        latest_val = db.execute(
            select(StockValuation)
            .where(StockValuation.stock_id == s.id)
            .order_by(StockValuation.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        result.append({
            "ticker": s.ticker,
            "name": s.name,
            "stock_type": s.stock_type,
            "current_price": s.current_price,
            "price_change": change,
            "price_change_pct": change_pct,
            "composite_score": latest_val.composite_score if latest_val else 0,
            "market_cap": s.current_price * (s.total_shares - s.available_shares),
        })

    return {"rankings": result}


# ---------------------------------------------------------------------------
# GET /api/stocks/{ticker} — Stock detail
# ---------------------------------------------------------------------------
@router.get("/{ticker}")
def get_stock(
    ticker: str,
    db: Session = Depends(get_db),
):
    stock = db.execute(
        select(Stock).where(Stock.ticker == ticker.upper())
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    # Latest valuation
    latest_val = db.execute(
        select(StockValuation)
        .where(StockValuation.stock_id == stock.id)
        .order_by(StockValuation.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Recent trades (last 20)
    recent_trades = list(
        db.execute(
            select(StockTransaction)
            .where(StockTransaction.stock_id == stock.id)
            .order_by(StockTransaction.created_at.desc())
            .limit(20)
        ).scalars().all()
    )

    change = stock.current_price - stock.previous_price
    change_pct = (
        round(change / stock.previous_price * 100)
        if stock.previous_price > 0
        else 0
    )

    return {
        "ticker": stock.ticker,
        "name": stock.name,
        "stock_type": stock.stock_type,
        "entity_id": stock.entity_id,
        "current_price": stock.current_price,
        "previous_price": stock.previous_price,
        "price_change": change,
        "price_change_pct": change_pct,
        "total_shares": stock.total_shares,
        "available_shares": stock.available_shares,
        "valuation": {
            "population_score": latest_val.population_score if latest_val else 0,
            "activity_score": latest_val.activity_score if latest_val else 0,
            "cashflow_score": latest_val.cashflow_score if latest_val else 0,
            "composite_score": latest_val.composite_score if latest_val else 0,
            "snapshot_date": latest_val.snapshot_date if latest_val else None,
        },
        "recent_trades": [
            {
                "shares": t.shares,
                "price_per_share": t.price_per_share,
                "total_cost": t.total_cost,
                "tx_type": t.tx_type,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in recent_trades
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/stocks/{ticker}/history — Price history
# ---------------------------------------------------------------------------
@router.get("/{ticker}/history")
def get_stock_history(
    ticker: str,
    db: Session = Depends(get_db),
):
    stock = db.execute(
        select(Stock).where(Stock.ticker == ticker.upper())
    ).scalar_one_or_none()
    if stock is None:
        raise HTTPException(status_code=404, detail="Stock not found")

    history = list(
        db.execute(
            select(StockValuation)
            .where(StockValuation.stock_id == stock.id)
            .order_by(StockValuation.snapshot_date.desc())
            .limit(90)
        ).scalars().all()
    )

    return {
        "ticker": stock.ticker,
        "history": [
            {
                "date": v.snapshot_date,
                "price": v.calculated_price,
                "population_score": v.population_score,
                "activity_score": v.activity_score,
                "cashflow_score": v.cashflow_score,
                "composite_score": v.composite_score,
            }
            for v in history
        ],
    }


# ---------------------------------------------------------------------------
# POST /api/stocks/{ticker}/buy — Buy shares
# ---------------------------------------------------------------------------
@router.post("/{ticker}/buy")
def buy_stock(
    ticker: str,
    payload: BuyStockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    with _stock_lock:
        stock = db.execute(
            select(Stock).where(Stock.ticker == ticker.upper())
        ).scalar_one_or_none()
        if stock is None:
            raise HTTPException(status_code=404, detail="Stock not found")
        if not stock.is_active:
            raise HTTPException(status_code=400, detail="This stock is not active")

        # Phase 2K: World Mint is prohibited from buying stocks
        if current_user.role == "world_mint":
            raise HTTPException(
                status_code=403,
                detail="World Mint cannot purchase stocks.",
            )

        shares = payload.shares
        if shares <= 0:
            raise HTTPException(status_code=400, detail="Must buy at least 1 share")
        if shares > stock.available_shares:
            raise HTTPException(
                status_code=400,
                detail=f"Only {stock.available_shares} shares available",
            )

        total_cost = shares * stock.current_price
        if current_user.balance < total_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient balance. Need {total_cost} HM, have {current_user.balance} HM",
            )

        # Business stock: check nation membership
        if stock.stock_type == "business":
            shop = db.execute(
                select(Shop).where(Shop.id == stock.entity_id)
            ).scalar_one_or_none()
            if shop and current_user.nation_id != shop.nation_id:
                raise HTTPException(
                    status_code=403,
                    detail="You must be a member of the shop's nation to buy business stocks",
                )

        # Determine counterparty address
        if stock.stock_type == "nation":
            nation = db.execute(
                select(Nation).where(Nation.id == stock.entity_id)
            ).scalar_one_or_none()
            if nation is None:
                raise HTTPException(status_code=500, detail="Nation not found for stock")
            to_address = nation.treasury_address
        else:
            shop = db.execute(
                select(Shop).where(Shop.id == stock.entity_id)
            ).scalar_one_or_none()
            if shop is None:
                raise HTTPException(status_code=500, detail="Shop not found for stock")
            owner = db.execute(
                select(User).where(User.id == shop.owner_id)
            ).scalar_one_or_none()
            if owner is None:
                raise HTTPException(status_code=500, detail="Shop owner not found")
            to_address = owner.wallet_address

        # Create blockchain transaction
        try:
            tx = create_transaction(
                db,
                tx_type="STOCK_BUY",
                from_address=current_user.wallet_address,
                to_address=to_address,
                amount=total_cost,
                memo=f"Bought {shares} shares of {stock.ticker} at {stock.current_price} HM/share",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # Update available shares
        stock.available_shares -= shares

        # Upsert holding
        holding = db.execute(
            select(StockHolding).where(
                StockHolding.user_id == current_user.id,
                StockHolding.stock_id == stock.id,
            )
        ).scalar_one_or_none()

        if holding is None:
            holding = StockHolding(
                user_id=current_user.id,
                stock_id=stock.id,
                shares=shares,
                avg_buy_price=stock.current_price,
            )
            db.add(holding)
        else:
            # Recalculate average buy price
            old_total = holding.shares * holding.avg_buy_price
            new_total = shares * stock.current_price
            holding.avg_buy_price = round(
                (old_total + new_total) / (holding.shares + shares)
            )
            holding.shares += shares

        # Record stock transaction
        stx = StockTransaction(
            stock_id=stock.id,
            buyer_id=current_user.id,
            seller_id=None,
            shares=shares,
            price_per_share=stock.current_price,
            total_cost=total_cost,
            tx_type="BUY",
        )
        db.add(stx)
        db.commit()

        return {
            "success": True,
            "tx_hash": tx.tx_hash,
            "shares_bought": shares,
            "total_cost": total_cost,
        }


# ---------------------------------------------------------------------------
# POST /api/stocks/{ticker}/sell — Sell shares
# ---------------------------------------------------------------------------
@router.post("/{ticker}/sell")
def sell_stock(
    ticker: str,
    payload: SellStockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    with _stock_lock:
        stock = db.execute(
            select(Stock).where(Stock.ticker == ticker.upper())
        ).scalar_one_or_none()
        if stock is None:
            raise HTTPException(status_code=404, detail="Stock not found")
        if not stock.is_active:
            raise HTTPException(status_code=400, detail="This stock is not active")

        shares = payload.shares
        if shares <= 0:
            raise HTTPException(status_code=400, detail="Must sell at least 1 share")

        holding = db.execute(
            select(StockHolding).where(
                StockHolding.user_id == current_user.id,
                StockHolding.stock_id == stock.id,
            )
        ).scalar_one_or_none()

        if holding is None or holding.shares < shares:
            available = holding.shares if holding else 0
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient shares. You hold {available}, trying to sell {shares}",
            )

        total_proceeds = shares * stock.current_price

        # Determine counterparty address (entity buys back)
        if stock.stock_type == "nation":
            nation = db.execute(
                select(Nation).where(Nation.id == stock.entity_id)
            ).scalar_one_or_none()
            if nation is None:
                raise HTTPException(status_code=500, detail="Nation not found")
            from_address = nation.treasury_address
        else:
            shop = db.execute(
                select(Shop).where(Shop.id == stock.entity_id)
            ).scalar_one_or_none()
            if shop is None:
                raise HTTPException(status_code=500, detail="Shop not found")
            owner = db.execute(
                select(User).where(User.id == shop.owner_id)
            ).scalar_one_or_none()
            if owner is None:
                raise HTTPException(status_code=500, detail="Shop owner not found")
            from_address = owner.wallet_address

        # Create blockchain transaction (entity pays seller)
        try:
            tx = create_transaction(
                db,
                tx_type="STOCK_SELL",
                from_address=from_address,
                to_address=current_user.wallet_address,
                amount=total_proceeds,
                memo=f"Sold {shares} shares of {stock.ticker} at {stock.current_price} HM/share",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        # Update shares
        stock.available_shares += shares
        holding.shares -= shares

        # Remove holding if no shares left
        if holding.shares <= 0:
            db.delete(holding)

        # Record stock transaction
        stx = StockTransaction(
            stock_id=stock.id,
            buyer_id=None,
            seller_id=current_user.id,
            shares=shares,
            price_per_share=stock.current_price,
            total_cost=total_proceeds,
            tx_type="SELL",
        )
        db.add(stx)
        db.commit()

        return {
            "success": True,
            "tx_hash": tx.tx_hash,
            "shares_sold": shares,
            "total_proceeds": total_proceeds,
        }


# ---------------------------------------------------------------------------
# POST /api/stocks/{stock_id}/close — Close a stock and pay out holders
# ---------------------------------------------------------------------------
@router.post("/{stock_id}/close")
def close_stock(
    stock_id: int,
    payload: CloseStockRequest = CloseStockRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    with _stock_lock:
        stock = db.execute(
            select(Stock).where(Stock.id == stock_id)
        ).scalar_one_or_none()
        if stock is None:
            raise HTTPException(status_code=404, detail="Stock not found")
        if not stock.is_active:
            raise HTTPException(status_code=400, detail="Stock is already closed")

        # Auth: world_mint can close any stock; shop owner can close their business stock
        if current_user.role != "world_mint":
            if stock.stock_type == "business":
                shop = db.execute(
                    select(Shop).where(Shop.id == stock.entity_id)
                ).scalar_one_or_none()
                if shop is None or shop.owner_id != current_user.id:
                    raise HTTPException(
                        status_code=403,
                        detail="Only the shop owner or World Mint can close this stock",
                    )
            else:
                raise HTTPException(
                    status_code=403,
                    detail="Only the World Mint can close nation stocks",
                )

        # Determine payout source wallet
        if stock.stock_type == "nation":
            nation = db.execute(
                select(Nation).where(Nation.id == stock.entity_id)
            ).scalar_one_or_none()
            if nation is None:
                raise HTTPException(status_code=500, detail="Nation not found for stock")
            payout_from = nation.treasury_address
        else:
            shop = db.execute(
                select(Shop).where(Shop.id == stock.entity_id)
            ).scalar_one_or_none()
            if shop is None:
                raise HTTPException(status_code=500, detail="Shop not found for stock")
            owner = db.execute(
                select(User).where(User.id == shop.owner_id)
            ).scalar_one_or_none()
            if owner is None:
                raise HTTPException(status_code=500, detail="Shop owner not found")
            payout_from = owner.wallet_address

        price_per_share = stock.current_price

        holdings = list(
            db.execute(
                select(StockHolding).where(
                    StockHolding.stock_id == stock.id,
                    StockHolding.shares > 0,
                )
            ).scalars().all()
        )

        payouts_issued = 0
        payouts_forfeited = 0
        holders_paid = 0

        for holding in holdings:
            payout_amount = holding.shares * price_per_share
            holder = db.execute(
                select(User).where(User.id == holding.user_id)
            ).scalar_one_or_none()

            if payout_amount > 0 and holder is not None:
                try:
                    create_transaction(
                        db,
                        tx_type="STOCK_PAYOUT",
                        from_address=payout_from,
                        to_address=holder.wallet_address,
                        amount=payout_amount,
                        memo=(
                            f"Stock closure payout: {holding.shares} shares of "
                            f"{stock.ticker} at {price_per_share} TC/share"
                        ),
                    )
                    payouts_issued += payout_amount
                    holders_paid += 1
                except ValueError:
                    # Insufficient funds — forced closure, holding zeroed without pay
                    payouts_forfeited += payout_amount

            # Zero out holding regardless of whether payout succeeded
            holding.shares = 0

        now = datetime.now(timezone.utc)
        stock.is_active = False
        stock.closed_at = now
        stock.closure_reason = payload.reason
        db.commit()

        return {
            "success": True,
            "ticker": stock.ticker,
            "price_per_share": price_per_share,
            "payouts_issued": payouts_issued,
            "payouts_forfeited": payouts_forfeited,
            "holders_paid": holders_paid,
            "closed_at": now.isoformat(),
        }
