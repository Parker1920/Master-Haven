"""
Travelers Exchange — Marketplace & Shop Routes

Provides API endpoints for shop management, listing CRUD, and purchases.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.blockchain import create_transaction
from app.database import get_db
from app.gdp import tc_to_national
from app.models import Nation, Shop, ShopListing, User

router = APIRouter(prefix="/api/shops", tags=["shops"])

VALID_CATEGORIES = {"service", "coordinates", "item", "other"}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
VALID_SHOP_TYPES = {"general", "resource_depot"}


class CreateShopRequest(BaseModel):
    name: str
    description: str | None = None
    shop_type: str = "general"
    mining_setup: str | None = None


class CreateListingRequest(BaseModel):
    title: str
    description: str | None = None
    price: int
    category: str = "other"


class UpdateListingRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    price: int | None = None
    category: str | None = None
    is_available: bool | None = None


class RejectShopRequest(BaseModel):
    reason: str | None = None


# ---------------------------------------------------------------------------
# GET /api/shops — list all active shops
# ---------------------------------------------------------------------------
@router.get("")
def list_shops(
    nation_id: int | None = Query(None),
    type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    conditions = [Shop.status == "approved", Shop.is_active == True]  # noqa: E712
    if nation_id is not None:
        conditions.append(Shop.nation_id == nation_id)
    if type is not None:
        conditions.append(Shop.shop_type == type)

    # Phase 2E: rank by 30-day GDP contribution (highest first).  Shops
    # tied at 0 contribution (newly approved, no sales yet) fall back to
    # creation order so brand-new shops aren't permanently buried at the
    # bottom of the listing.
    shops = list(
        db.execute(
            select(Shop)
            .where(*conditions)
            .order_by(Shop.gdp_contribution_30d.desc(), Shop.created_at.desc())
        )
        .scalars()
        .all()
    )

    result = []
    for shop in shops:
        owner = db.execute(
            select(User).where(User.id == shop.owner_id)
        ).scalar_one_or_none()
        nation = db.execute(
            select(Nation).where(Nation.id == shop.nation_id)
        ).scalar_one_or_none()
        listing_count = (
            db.execute(
                select(func.count(ShopListing.id)).where(
                    ShopListing.shop_id == shop.id,
                    ShopListing.is_available == True,  # noqa: E712
                )
            ).scalar()
            or 0
        )
        result.append(
            {
                "id": shop.id,
                "name": shop.name,
                "description": shop.description,
                "shop_type": shop.shop_type,
                "owner_name": (
                    owner.display_name or owner.username if owner else "Unknown"
                ),
                "nation_id": shop.nation_id,
                "nation_name": nation.name if nation else "Unknown",
                "total_sales": shop.total_sales,
                "total_revenue": shop.total_revenue,
                "gdp_contribution_30d": shop.gdp_contribution_30d,
                "listing_count": listing_count,
                "created_at": shop.created_at.isoformat() if shop.created_at else None,
            }
        )

    return {"shops": result}


# ---------------------------------------------------------------------------
# GET /api/shops/pending — list shops awaiting NL approval
# NL sees pending shops for their nation; world_mint sees all pending shops.
# ---------------------------------------------------------------------------
@router.get("/pending")
def list_pending_shops(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    if current_user.role == "world_mint":
        shops = list(
            db.execute(
                select(Shop).where(Shop.status == "pending").order_by(Shop.created_at.desc())
            )
            .scalars()
            .all()
        )
    else:
        # Must be NL of an approved nation
        if current_user.nation_id is None:
            raise HTTPException(status_code=403, detail="Not a nation leader")
        nation = db.execute(
            select(Nation).where(Nation.id == current_user.nation_id)
        ).scalar_one_or_none()
        if nation is None or nation.leader_id != current_user.id:
            raise HTTPException(status_code=403, detail="Only nation leaders can view pending shops")
        shops = list(
            db.execute(
                select(Shop).where(
                    Shop.status == "pending",
                    Shop.nation_id == current_user.nation_id,
                ).order_by(Shop.created_at.desc())
            )
            .scalars()
            .all()
        )

    result = []
    for shop in shops:
        owner = db.execute(
            select(User).where(User.id == shop.owner_id)
        ).scalar_one_or_none()
        nation = db.execute(
            select(Nation).where(Nation.id == shop.nation_id)
        ).scalar_one_or_none()
        result.append(
            {
                "id": shop.id,
                "name": shop.name,
                "description": shop.description,
                "status": shop.status,
                "owner_name": owner.display_name or owner.username if owner else "Unknown",
                "nation_id": shop.nation_id,
                "nation_name": nation.name if nation else "Unknown",
                "created_at": shop.created_at.isoformat() if shop.created_at else None,
            }
        )

    return {"shops": result}


# ---------------------------------------------------------------------------
# GET /api/shops/{shop_id} — shop detail with listings
# ---------------------------------------------------------------------------
@router.get("/{shop_id}")
def get_shop(
    shop_id: int,
    db: Session = Depends(get_db),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")

    owner = db.execute(
        select(User).where(User.id == shop.owner_id)
    ).scalar_one_or_none()
    nation = db.execute(
        select(Nation).where(Nation.id == shop.nation_id)
    ).scalar_one_or_none()

    listings = list(
        db.execute(
            select(ShopListing).where(
                ShopListing.shop_id == shop.id,
                ShopListing.is_available == True,  # noqa: E712
            )
            .order_by(ShopListing.created_at.desc())
        )
        .scalars()
        .all()
    )

    # Currency info for display conversion
    gdp_mult = nation.gdp_multiplier if nation and nation.gdp_multiplier else 100
    currency_code = nation.currency_code if nation else "TC"

    return {
        "id": shop.id,
        "name": shop.name,
        "description": shop.description,
        "shop_type": shop.shop_type,
        "mining_setup": shop.mining_setup,
        "owner_name": owner.display_name or owner.username if owner else "Unknown",
        "nation_id": shop.nation_id,
        "nation_name": nation.name if nation else "Unknown",
        "currency_code": currency_code,
        "gdp_multiplier": gdp_mult,
        "total_sales": shop.total_sales,
        "total_revenue": shop.total_revenue,
        "gdp_contribution_30d": shop.gdp_contribution_30d,
        "gdp_last_calculated": (
            shop.gdp_last_calculated.isoformat() if shop.gdp_last_calculated else None
        ),
        "is_active": shop.is_active,
        "created_at": shop.created_at.isoformat() if shop.created_at else None,
        "listings": [
            {
                "id": l.id,
                "title": l.title,
                "description": l.description,
                "price_tc": l.price,
                "price_national": tc_to_national(l.price, gdp_mult),
                "currency_code": currency_code,
                "category": l.category,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in listings
        ],
    }


# ---------------------------------------------------------------------------
# POST /api/shops — create a shop
# ---------------------------------------------------------------------------
@router.post("")
def create_shop(
    payload: CreateShopRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    if current_user.nation_id is None:
        raise HTTPException(
            status_code=400, detail="You must be a member of a nation to open a shop"
        )

    nation = db.execute(
        select(Nation).where(Nation.id == current_user.nation_id)
    ).scalar_one_or_none()
    if nation is None or nation.status != "approved":
        raise HTTPException(
            status_code=400, detail="Your nation must be approved"
        )

    existing = db.execute(
        select(Shop).where(Shop.owner_id == current_user.id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=400, detail="You already own a shop")

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Shop name cannot be empty")

    shop_type = payload.shop_type or "general"
    if shop_type not in VALID_SHOP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid shop_type. Must be one of: {', '.join(sorted(VALID_SHOP_TYPES))}",
        )
    mining_setup = payload.mining_setup.strip() if payload.mining_setup else None
    if shop_type == "resource_depot" and not mining_setup:
        raise HTTPException(
            status_code=400,
            detail="mining_setup is required for resource_depot shops",
        )

    shop = Shop(
        owner_id=current_user.id,
        nation_id=current_user.nation_id,
        name=name,
        description=payload.description.strip() if payload.description else None,
        shop_type=shop_type,
        mining_setup=mining_setup,
        status="pending",
        is_active=False,
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)

    return {
        "success": True,
        "shop_id": shop.id,
        "name": shop.name,
        "shop_type": shop.shop_type,
        "status": "pending",
        "message": "Shop created and is pending Nation Leader approval before going live.",
    }


# ---------------------------------------------------------------------------
# POST /api/shops/{shop_id}/listings — create a listing
# ---------------------------------------------------------------------------
@router.post("/{shop_id}/listings")
def create_listing(
    shop_id: int,
    payload: CreateListingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    if current_user.id != shop.owner_id:
        raise HTTPException(status_code=403, detail="You do not own this shop")

    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
        )
    if payload.price <= 0:
        raise HTTPException(status_code=400, detail="Price must be greater than 0")

    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    # Convert national coin price to TC for storage
    # Seller enters price in their national coin; stored as TC internally
    nation = db.execute(
        select(Nation).where(Nation.id == shop.nation_id)
    ).scalar_one_or_none()
    gdp_mult = nation.gdp_multiplier if nation and nation.gdp_multiplier else 100
    tc_price = round(payload.price * gdp_mult / 100)
    if tc_price <= 0:
        tc_price = payload.price  # fallback to raw price if conversion fails

    listing = ShopListing(
        shop_id=shop.id,
        title=title,
        description=payload.description.strip() if payload.description else None,
        price=tc_price,
        category=payload.category,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)

    return {"success": True, "listing_id": listing.id}


# ---------------------------------------------------------------------------
# POST /api/shops/{shop_id}/listings/{listing_id}/buy — purchase a listing
# ---------------------------------------------------------------------------
@router.post("/{shop_id}/listings/{listing_id}/buy")
def buy_listing(
    shop_id: int,
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")

    listing = db.execute(
        select(ShopListing).where(ShopListing.id == listing_id)
    ).scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.shop_id != shop.id:
        raise HTTPException(status_code=400, detail="Listing does not belong to this shop")
    if not listing.is_available:
        raise HTTPException(status_code=400, detail="This listing is not available")
    if not shop.is_active:
        raise HTTPException(status_code=400, detail="This shop is not active")
    if current_user.id == shop.owner_id:
        raise HTTPException(status_code=400, detail="You cannot buy from your own shop")
    if current_user.balance < listing.price:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    owner = db.execute(
        select(User).where(User.id == shop.owner_id)
    ).scalar_one_or_none()
    if owner is None:
        raise HTTPException(status_code=500, detail="Shop owner not found")

    try:
        tx = create_transaction(
            db,
            tx_type="PURCHASE",
            from_address=current_user.wallet_address,
            to_address=owner.wallet_address,
            amount=listing.price,
            memo=f"Purchase: {listing.title} from {shop.name}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    shop.total_sales += 1
    shop.total_revenue += listing.price
    # Phase 2E: keep the marketplace ranking warm in real time.  The full
    # 30-day window is still recomputed by the daily GDP job (which also
    # decays purchases that age past 30 days); this just means a fresh
    # sale moves the shop up immediately rather than at the next tick.
    shop.gdp_contribution_30d = (shop.gdp_contribution_30d or 0) + listing.price
    shop.gdp_last_calculated = datetime.now(timezone.utc)
    db.commit()

    # Cross-nation conversion info
    seller_nation = db.execute(
        select(Nation).where(Nation.id == shop.nation_id)
    ).scalar_one_or_none()
    buyer_nation = db.execute(
        select(Nation).where(Nation.id == current_user.nation_id)
    ).scalar_one_or_none() if current_user.nation_id else None

    seller_gdp = seller_nation.gdp_multiplier if seller_nation and seller_nation.gdp_multiplier else 100
    buyer_gdp = buyer_nation.gdp_multiplier if buyer_nation and buyer_nation.gdp_multiplier else 100

    return {
        "success": True,
        "tx_hash": tx.tx_hash,
        "amount_tc": listing.price,
        "seller_price": tc_to_national(listing.price, seller_gdp),
        "seller_currency": seller_nation.currency_code if seller_nation else "TC",
        "buyer_cost": tc_to_national(listing.price, buyer_gdp),
        "buyer_currency": buyer_nation.currency_code if buyer_nation else "TC",
    }


# ---------------------------------------------------------------------------
# PUT /api/shops/{shop_id}/listings/{listing_id} — update a listing
# ---------------------------------------------------------------------------
@router.put("/{shop_id}/listings/{listing_id}")
def update_listing(
    shop_id: int,
    listing_id: int,
    payload: UpdateListingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    if current_user.id != shop.owner_id:
        raise HTTPException(status_code=403, detail="You do not own this shop")

    listing = db.execute(
        select(ShopListing).where(ShopListing.id == listing_id)
    ).scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.shop_id != shop.id:
        raise HTTPException(status_code=400, detail="Listing does not belong to this shop")

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        listing.title = title
    if payload.description is not None:
        listing.description = payload.description.strip() or None
    if payload.price is not None:
        if payload.price <= 0:
            raise HTTPException(status_code=400, detail="Price must be greater than 0")
        listing.price = payload.price
    if payload.category is not None:
        if payload.category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
            )
        listing.category = payload.category
    if payload.is_available is not None:
        listing.is_available = payload.is_available

    db.commit()
    return {"success": True}


# ---------------------------------------------------------------------------
# POST /api/shops/{shop_id}/approve — NL approves a pending shop
# ---------------------------------------------------------------------------
@router.post("/{shop_id}/approve")
def approve_shop(
    shop_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")

    nation = db.execute(
        select(Nation).where(Nation.id == shop.nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=500, detail="Shop's nation not found")

    if current_user.role != "world_mint" and current_user.id != nation.leader_id:
        raise HTTPException(
            status_code=403, detail="Only the nation leader or World Mint can approve shops"
        )

    if shop.status == "approved":
        raise HTTPException(status_code=400, detail="Shop is already approved")

    shop.status = "approved"
    shop.is_active = True
    shop.approved_by = current_user.id
    shop.approved_at = datetime.now(timezone.utc)
    shop.rejected_reason = None
    db.commit()

    return {"success": True, "shop_id": shop.id, "status": "approved"}


# ---------------------------------------------------------------------------
# POST /api/shops/{shop_id}/reject — NL rejects a pending shop
# ---------------------------------------------------------------------------
@router.post("/{shop_id}/reject")
def reject_shop(
    shop_id: int,
    payload: RejectShopRequest = RejectShopRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")

    nation = db.execute(
        select(Nation).where(Nation.id == shop.nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=500, detail="Shop's nation not found")

    if current_user.role != "world_mint" and current_user.id != nation.leader_id:
        raise HTTPException(
            status_code=403, detail="Only the nation leader or World Mint can reject shops"
        )

    if shop.status == "approved":
        raise HTTPException(status_code=400, detail="Cannot reject an already-approved shop; use suspend instead")

    shop.status = "rejected"
    shop.is_active = False
    shop.rejected_reason = payload.reason
    db.commit()

    return {"success": True, "shop_id": shop.id, "status": "rejected"}


# ---------------------------------------------------------------------------
# POST /api/shops/{shop_id}/suspend — NL suspends an approved shop
# ---------------------------------------------------------------------------
@router.post("/{shop_id}/suspend")
def suspend_shop(
    shop_id: int,
    payload: RejectShopRequest = RejectShopRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")

    nation = db.execute(
        select(Nation).where(Nation.id == shop.nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=500, detail="Shop's nation not found")

    if current_user.role != "world_mint" and current_user.id != nation.leader_id:
        raise HTTPException(
            status_code=403, detail="Only the nation leader or World Mint can suspend shops"
        )

    if shop.status == "suspended":
        raise HTTPException(status_code=400, detail="Shop is already suspended")

    shop.status = "suspended"
    shop.is_active = False
    shop.rejected_reason = payload.reason
    db.commit()

    return {"success": True, "shop_id": shop.id, "status": "suspended"}
