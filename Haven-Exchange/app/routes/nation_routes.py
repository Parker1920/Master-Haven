"""
Travelers Exchange — Nation Management Routes

Provides endpoints for nation application, membership (join/leave),
member listing, and treasury distribution by nation leaders.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.blockchain import create_transaction
from app.config import settings
from app.database import get_db
from app.models import Nation, User
from app.wallet import generate_nation_treasury_address

router = APIRouter(prefix="/api/nations", tags=["nations"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class NationApplyRequest(BaseModel):
    name: str
    description: str | None = None
    discord_invite: str | None = None
    game: str | None = None
    currency_name: str | None = None   # e.g. "Voyager Credits"
    currency_code: str | None = None   # e.g. "VGC" (2-5 uppercase alpha)


class JoinNationRequest(BaseModel):
    """No body needed — nation_id comes from the path."""
    pass


class DistributeRequest(BaseModel):
    to_address: str
    amount: int
    memo: str | None = None


class BulkDistributionItem(BaseModel):
    to_address: str
    amount: int


class DistributeBulkRequest(BaseModel):
    distributions: list[BulkDistributionItem]
    memo: str | None = None


# ---------------------------------------------------------------------------
# POST /api/nations/apply
# ---------------------------------------------------------------------------
@router.post("/apply")
def apply_nation(
    payload: NationApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Submit an application to create a new nation.

    The current user becomes the nation's leader once the application is
    approved by the World Mint operator.  The nation starts in "pending"
    status.
    """

    # Validate: name not empty
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Nation name cannot be empty.")

    # Validate: user doesn't already lead a nation
    existing_nation = db.execute(
        select(Nation).where(Nation.leader_id == current_user.id)
    ).scalar_one_or_none()
    if existing_nation is not None:
        raise HTTPException(
            status_code=400,
            detail="You already lead a nation. A user can only lead one nation.",
        )

    # Validate: name is unique
    name_taken = db.execute(
        select(Nation).where(Nation.name == payload.name.strip())
    ).scalar_one_or_none()
    if name_taken is not None:
        raise HTTPException(
            status_code=400,
            detail=f"A nation with the name '{payload.name.strip()}' already exists.",
        )

    # Validate currency code (2-5 uppercase alpha)
    import re
    currency_code = (payload.currency_code or "").strip().upper()
    currency_name = (payload.currency_name or "").strip()
    if currency_code:
        if not re.match(r"^[A-Z]{2,5}$", currency_code):
            raise HTTPException(
                status_code=400,
                detail="Currency code must be 2-5 uppercase letters (e.g., VGC).",
            )
        # Ensure currency code is unique
        code_taken = db.execute(
            select(Nation).where(Nation.currency_code == currency_code)
        ).scalar_one_or_none()
        if code_taken is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Currency code '{currency_code}' is already in use.",
            )

    # Create the Nation with a placeholder treasury address, flush to get ID
    nation = Nation(
        name=payload.name.strip(),
        leader_id=current_user.id,
        treasury_address="placeholder",
        description=payload.description,
        discord_invite=payload.discord_invite,
        game=payload.game,
        currency_name=currency_name or None,
        currency_code=currency_code or None,
        status="pending",
        member_count=0,
    )
    db.add(nation)
    db.flush()  # generates nation.id

    # Generate the real treasury address now that we have the ID
    nation.treasury_address = generate_nation_treasury_address(
        nation.id, settings.SECRET_KEY
    )
    db.commit()

    return {
        "success": True,
        "nation_id": nation.id,
        "name": nation.name,
        "status": "pending",
    }


# ---------------------------------------------------------------------------
# GET /api/nations — list all approved nations
# ---------------------------------------------------------------------------
@router.get("")
def list_nations(db: Session = Depends(get_db)):
    """Return all approved nations with GDP info."""
    nations = list(
        db.execute(
            select(Nation).where(Nation.status == "approved")
            .order_by(Nation.name)
        ).scalars().all()
    )
    return {
        "nations": [
            {
                "id": n.id,
                "name": n.name,
                "member_count": n.member_count,
                "currency_name": n.currency_name,
                "currency_code": n.currency_code,
                "gdp_score": n.gdp_score,
                "gdp_multiplier": n.gdp_multiplier,
                "gdp_display": round(n.gdp_multiplier / 100, 2),
            }
            for n in nations
        ]
    }


# ---------------------------------------------------------------------------
# POST /api/nations/{nation_id}/join
# ---------------------------------------------------------------------------
@router.post("/{nation_id}/join")
def join_nation(
    nation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Join an approved nation as a member."""

    # Validate: nation exists
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    # Validate: nation is approved
    if nation.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="This nation is not currently accepting members (not approved).",
        )

    # Validate: user isn't already in a nation
    if current_user.nation_id is not None:
        raise HTTPException(
            status_code=400,
            detail="You are already a member of a nation. Leave your current nation first.",
        )

    # Join the nation
    current_user.nation_id = nation_id
    nation.member_count += 1
    db.commit()

    return {"success": True, "nation_name": nation.name}


# ---------------------------------------------------------------------------
# POST /api/nations/{nation_id}/leave
# ---------------------------------------------------------------------------
@router.post("/{nation_id}/leave")
def leave_nation(
    nation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Leave a nation the current user belongs to."""

    # Validate: user is actually in this nation
    if current_user.nation_id != nation_id:
        raise HTTPException(
            status_code=400,
            detail="You are not a member of this nation.",
        )

    # Validate: nation exists
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    # Cannot leave if they're the nation leader
    if current_user.id == nation.leader_id:
        raise HTTPException(
            status_code=400,
            detail="Nation leaders cannot leave their own nation.",
        )

    # Leave the nation
    current_user.nation_id = None
    nation.member_count -= 1
    db.commit()

    return {"success": True}


# ---------------------------------------------------------------------------
# GET /api/nations/{nation_id}/members
# ---------------------------------------------------------------------------
@router.get("/{nation_id}/members")
def list_members(
    nation_id: int,
    db: Session = Depends(get_db),
):
    """Return a public list of all members belonging to a nation."""

    # Validate: nation exists
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    # Fetch all users whose nation_id matches
    members = list(
        db.execute(
            select(User).where(User.nation_id == nation_id)
        ).scalars().all()
    )

    return [
        {
            "username": m.username,
            "display_name": m.display_name,
            "wallet_address": m.wallet_address,
            "balance": m.balance,
            "last_active": (
                m.last_active.isoformat() if m.last_active else None
            ),
        }
        for m in members
    ]


# ---------------------------------------------------------------------------
# POST /api/nations/{nation_id}/distribute
# ---------------------------------------------------------------------------
@router.post("/{nation_id}/distribute")
def distribute(
    nation_id: int,
    payload: DistributeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Distribute currency from the nation treasury to a nation member.

    Only the nation leader may perform distributions.
    """

    # Validate: nation exists
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    # Validate: only the leader can distribute
    if current_user.id != nation.leader_id:
        raise HTTPException(
            status_code=403,
            detail="Only the nation leader can distribute from the treasury.",
        )

    # Validate: amount is positive
    if payload.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Distribution amount must be greater than zero.",
        )

    # Validate: recipient exists and is a member of this nation
    recipient = db.execute(
        select(User).where(User.wallet_address == payload.to_address)
    ).scalar_one_or_none()
    if recipient is None:
        raise HTTPException(
            status_code=404,
            detail=f"No user found with wallet address '{payload.to_address}'.",
        )
    if recipient.nation_id != nation_id:
        raise HTTPException(
            status_code=400,
            detail="Recipient is not a member of this nation.",
        )

    # Execute the distribution transaction
    try:
        tx = create_transaction(
            db,
            tx_type="DISTRIBUTE",
            from_address=nation.treasury_address,
            to_address=payload.to_address,
            amount=payload.amount,
            memo=payload.memo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "success": True,
        "tx_hash": f"tx_{tx.tx_hash[:12]}",
        "amount": payload.amount,
    }


# ---------------------------------------------------------------------------
# POST /api/nations/{nation_id}/distribute-bulk
# ---------------------------------------------------------------------------
@router.post("/{nation_id}/distribute-bulk")
def distribute_bulk(
    nation_id: int,
    payload: DistributeBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Distribute currency from the nation treasury to multiple members.

    Only the nation leader may perform bulk distributions.  Each
    distribution creates a separate DISTRIBUTE transaction on the ledger.
    """

    # Validate: nation exists
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    # Validate: only the leader can distribute
    if current_user.id != nation.leader_id:
        raise HTTPException(
            status_code=403,
            detail="Only the nation leader can distribute from the treasury.",
        )

    # Validate: distributions list is not empty
    if not payload.distributions:
        raise HTTPException(
            status_code=400,
            detail="Distributions list cannot be empty.",
        )

    # Validate each distribution entry before executing any
    for item in payload.distributions:
        if item.amount <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Distribution amount must be greater than zero (got {item.amount} for {item.to_address}).",
            )
        recipient = db.execute(
            select(User).where(User.wallet_address == item.to_address)
        ).scalar_one_or_none()
        if recipient is None:
            raise HTTPException(
                status_code=404,
                detail=f"No user found with wallet address '{item.to_address}'.",
            )
        if recipient.nation_id != nation_id:
            raise HTTPException(
                status_code=400,
                detail=f"Recipient '{item.to_address}' is not a member of this nation.",
            )

    # Execute all distributions
    total_amount = 0
    count = 0
    try:
        for item in payload.distributions:
            create_transaction(
                db,
                tx_type="DISTRIBUTE",
                from_address=nation.treasury_address,
                to_address=item.to_address,
                amount=item.amount,
                memo=payload.memo,
            )
            total_amount += item.amount
            count += 1
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "success": True,
        "count": count,
        "total_amount": total_amount,
    }


# Treasury lending endpoints (POST/GET/forgive) live in app/routes/bank_routes.py
# under the absolute /api/nations/{nation_id}/loans path — kept there so the
# bank-loan and treasury-loan handlers share request/response shapes and the
# _get_global_settings + lender_type plumbing.
