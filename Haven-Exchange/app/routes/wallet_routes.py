"""
Travelers Exchange — Wallet Routes

Endpoints for viewing wallet information and per-address transaction
history.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.blockchain import get_transactions_for_address
from app.config import settings
from app.database import get_db
from app.models import Nation, User

router = APIRouter(prefix="/api/wallet", tags=["wallets"])


# ---------------------------------------------------------------------------
# GET /api/wallet  — authenticated user's own wallet
# ---------------------------------------------------------------------------
@router.get("")
def my_wallet(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's wallet details."""
    nation_name = None
    if current_user.nation_id is not None:
        nation = db.execute(
            select(Nation).where(Nation.id == current_user.nation_id)
        ).scalar_one_or_none()
        if nation is not None:
            nation_name = nation.name

    return {
        "address": current_user.wallet_address,
        "balance": current_user.balance,
        "display_name": current_user.display_name,
        "nation": nation_name,
        "created_at": (
            current_user.created_at.isoformat() if current_user.created_at else None
        ),
    }


# ---------------------------------------------------------------------------
# GET /api/wallet/search  — search wallets by username, display name, or address
# ---------------------------------------------------------------------------
@router.get("/search")
def wallet_search(
    q: str = Query("", min_length=1),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Search wallets by username prefix, display name, or address prefix."""
    q = q.strip()
    if not q:
        return {"results": []}

    results = []

    # Search users
    users = list(
        db.execute(
            select(User).where(
                or_(
                    User.username.ilike(f"{q}%"),
                    User.display_name.ilike(f"{q}%"),
                    User.wallet_address.ilike(f"{q}%"),
                )
            ).limit(limit)
        ).scalars().all()
    )
    for u in users:
        results.append({
            "address": u.wallet_address,
            "display_name": u.display_name,
            "username": u.username,
            "type": "user",
        })

    # Search nation treasuries
    if len(results) < limit:
        remaining = limit - len(results)
        nations = list(
            db.execute(
                select(Nation).where(
                    or_(
                        Nation.name.ilike(f"{q}%"),
                        Nation.treasury_address.ilike(f"{q}%"),
                    )
                ).limit(remaining)
            ).scalars().all()
        )
        for n in nations:
            results.append({
                "address": n.treasury_address,
                "display_name": n.name,
                "username": None,
                "type": "nation_treasury",
            })

    return {"results": results}


# ---------------------------------------------------------------------------
# GET /api/wallet/{address}  — public wallet / treasury lookup
# ---------------------------------------------------------------------------
@router.get("/{address}")
def wallet_info(address: str, db: Session = Depends(get_db)):
    """Return public information for a wallet or nation treasury address."""
    # Nation treasury lookup
    if address.startswith(settings.NATION_WALLET_PREFIX):
        nation = db.execute(
            select(Nation).where(Nation.treasury_address == address)
        ).scalar_one_or_none()
        if nation is None:
            raise HTTPException(status_code=404, detail="Nation treasury not found.")
        return {
            "address": nation.treasury_address,
            "balance": nation.treasury_balance,
            "display_name": nation.name,
            "type": "nation_treasury",
        }

    # User wallet lookup
    user = db.execute(
        select(User).where(User.wallet_address == address)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    nation_name = None
    if user.nation_id is not None:
        nation = db.execute(
            select(Nation).where(Nation.id == user.nation_id)
        ).scalar_one_or_none()
        if nation is not None:
            nation_name = nation.name

    return {
        "address": user.wallet_address,
        "balance": user.balance,
        "display_name": user.display_name,
        "nation": nation_name,
    }


# ---------------------------------------------------------------------------
# GET /api/wallet/{address}/transactions  — address transaction history
# ---------------------------------------------------------------------------
@router.get("/{address}/transactions")
def wallet_transactions(
    address: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return paginated transaction history for a given address (public)."""
    # Verify address exists
    if address.startswith(settings.NATION_WALLET_PREFIX):
        exists = db.execute(
            select(Nation.id).where(Nation.treasury_address == address)
        ).scalar_one_or_none()
    else:
        exists = db.execute(
            select(User.id).where(User.wallet_address == address)
        ).scalar_one_or_none()

    if exists is None:
        raise HTTPException(status_code=404, detail="Address not found.")

    offset = (page - 1) * per_page
    transactions = get_transactions_for_address(db, address, limit=per_page, offset=offset)

    return {
        "address": address,
        "transactions": [
            {
                "tx_hash": tx.tx_hash,
                "tx_type": tx.tx_type,
                "from_address": tx.from_address,
                "to_address": tx.to_address,
                "amount": tx.amount,
                "fee": tx.fee,
                "memo": tx.memo,
                "status": tx.status,
                "created_at": tx.created_at.isoformat() if tx.created_at else None,
            }
            for tx in transactions
        ],
        "page": page,
        "per_page": per_page,
    }
