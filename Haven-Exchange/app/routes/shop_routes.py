"""
Travelers Exchange — Marketplace & Shop Routes

Provides API endpoints for shop management, listing CRUD, and purchases.
"""

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
class CreateShopRequest(BaseModel):
    name: str
    description: str | None = None


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


# ---------------------------------------------------------------------------
# GET /api/shops — list all active shops
# ---------------------------------------------------------------------------
@router.get("")
def list_shops(
    nation_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    conditions = [Shop.is_active == True]  # noqa: E712
    if nation_id is not None:
        conditions.append(Shop.nation_id == nation_id)

    shops = list(
        db.execute(select(Shop).where(*conditions).order_by(Shop.created_at.desc()))
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
                "owner_name": (
                    owner.display_name or owner.username if owner else "Unknown"
                ),
                "nation_id": shop.nation_id,
                "nation_name": nation.name if nation else "Unknown",
                "total_sales": shop.total_sales,
                "total_revenue": shop.total_revenue,
                "listing_count": listing_count,
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
        "owner_name": owner.display_name or owner.username if owner else "Unknown",
        "nation_id": shop.nation_id,
        "nation_name": nation.name if nation else "Unknown",
        "currency_code": currency_code,
        "gdp_multiplier": gdp_mult,
        "total_sales": shop.total_sales,
        "total_revenue": shop.total_revenue,
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

    shop = Shop(
        owner_id=current_user.id,
        nation_id=current_user.nation_id,
        name=name,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)

    return {"success": True, "shop_id": shop.id, "name": shop.name}


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
