"""
Travelers Exchange — World Mint Admin Routes

Provides the administrative endpoints for the World Mint operator:
global economy stats, minting execution, allocation management, and
nation approval/suspension.

ALL endpoints require the ``world_mint`` role.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_role
from app.blockchain import create_transaction, verify_chain
from app.config import settings
from app.database import get_db
from app.gdp import recalculate_all_gdp
from app.models import (
    GdpSnapshot,
    MintAllocation,
    Nation,
    StimulusProposal,
    Transaction,
    User,
)
from app.valuation import create_nation_stock

router = APIRouter(prefix="/api/mint", tags=["mint"])

# Common dependency — every endpoint in this router requires world_mint role
_require_world_mint = require_role("world_mint")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class MintExecuteRequest(BaseModel):
    to_address: str
    amount: int
    memo: str | None = None


class AllocationApproveRequest(BaseModel):
    approved_amount: int | None = None


class CalculateAllocationsRequest(BaseModel):
    period: str | None = None


class StimulusReviewRequest(BaseModel):
    """Optional override for the proposed mint amount on approval."""

    approved_amount: int | None = None
    reason: str | None = None


# ---------------------------------------------------------------------------
# GET /api/mint/stats
# ---------------------------------------------------------------------------
@router.get("/stats")
def mint_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Return global economy statistics for the World Mint dashboard."""

    # Sum of all user balances (excluding the world_mint admin)
    total_user_balances = (
        db.execute(
            select(func.coalesce(func.sum(User.balance), 0)).where(
                User.role != "world_mint"
            )
        ).scalar()
        or 0
    )

    # Sum of all nation treasury balances
    total_nation_balances = (
        db.execute(
            select(func.coalesce(func.sum(Nation.treasury_balance), 0))
        ).scalar()
        or 0
    )

    total_supply = total_user_balances + total_nation_balances

    # Total transaction count
    total_transactions = (
        db.execute(select(func.count(Transaction.id))).scalar() or 0
    )

    # Total users excluding the world_mint admin
    total_users = (
        db.execute(
            select(func.count(User.id)).where(User.role != "world_mint")
        ).scalar()
        or 0
    )

    # Total approved nations
    total_nations = (
        db.execute(
            select(func.count(Nation.id)).where(Nation.status == "approved")
        ).scalar()
        or 0
    )

    # Active users in the last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    active_users_30d = (
        db.execute(
            select(func.count(User.id)).where(
                User.last_active >= thirty_days_ago
            )
        ).scalar()
        or 0
    )

    # Chain validity
    chain_result = verify_chain(db)
    chain_valid = chain_result["valid"]

    # GDP overview — per-nation scores
    gdp_nations = list(
        db.execute(
            select(Nation).where(Nation.status == "approved")
            .order_by(Nation.gdp_multiplier.desc())
        ).scalars().all()
    )
    gdp_overview = [
        {
            "name": n.name,
            "currency_code": n.currency_code or "TC",
            "gdp_score": n.gdp_score,
            "gdp_multiplier": n.gdp_multiplier,
            "gdp_display": round(n.gdp_multiplier / 100, 2),
            "member_count": n.member_count,
        }
        for n in gdp_nations
    ]
    avg_gdp = (
        round(sum(n.gdp_multiplier for n in gdp_nations) / len(gdp_nations) / 100, 2)
        if gdp_nations else 1.0
    )

    return {
        "total_supply": total_supply,
        "total_transactions": total_transactions,
        "total_users": total_users,
        "total_nations": total_nations,
        "active_users_30d": active_users_30d,
        "chain_valid": chain_valid,
        "gdp_overview": gdp_overview,
        "avg_gdp_multiplier": avg_gdp,
    }


# ---------------------------------------------------------------------------
# POST /api/mint/execute
# ---------------------------------------------------------------------------
@router.post("/execute")
def mint_execute(
    payload: MintExecuteRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Mint new currency and send it to a user wallet or nation treasury."""

    # Validate amount
    if payload.amount <= 0:
        return {"success": False, "error": "Amount must be greater than zero."}

    # Validate that the target address exists and enforce mint_cap for nations
    if payload.to_address.startswith(settings.NATION_WALLET_PREFIX):
        recipient = db.execute(
            select(Nation).where(Nation.treasury_address == payload.to_address)
        ).scalar_one_or_none()
        if recipient is None:
            return {
                "success": False,
                "error": f"Nation treasury '{payload.to_address}' not found.",
            }

        # Phase 2K: mint_cap enforcement — total MINT txs to this treasury
        # must not exceed nation.mint_cap after this mint.
        total_minted_to_nation = db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.tx_type == "MINT",
                Transaction.from_address == settings.WORLD_MINT_ADDRESS,
                Transaction.to_address == payload.to_address,
            )
        ).scalar() or 0
        cap = getattr(recipient, "mint_cap", 1_000_000_000)
        if total_minted_to_nation + payload.amount > cap:
            remaining = max(0, cap - total_minted_to_nation)
            return {
                "success": False,
                "error": (
                    f"Mint cap exceeded: {total_minted_to_nation} TC already minted to "
                    f"{recipient.name} (cap={cap} TC). Only {remaining} TC remaining."
                ),
            }
    else:
        recipient = db.execute(
            select(User).where(User.wallet_address == payload.to_address)
        ).scalar_one_or_none()
        if recipient is None:
            return {
                "success": False,
                "error": f"Wallet '{payload.to_address}' not found.",
            }
        # Phase 2K: World Mint wallet cannot mint directly to itself
        if payload.to_address == settings.WORLD_MINT_ADDRESS:
            return {
                "success": False,
                "error": "World Mint cannot mint directly to its own wallet.",
            }

    try:
        tx = create_transaction(
            db,
            tx_type="MINT",
            from_address=settings.WORLD_MINT_ADDRESS,
            to_address=payload.to_address,
            amount=payload.amount,
            memo=payload.memo,
        )
        return {
            "success": True,
            "tx_hash": f"tx_{tx.tx_hash[:12]}",
            "amount": payload.amount,
            "to_address": payload.to_address,
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# GET /api/mint/allocations
# ---------------------------------------------------------------------------
@router.get("/allocations")
def list_allocations(
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Return all mint allocations with nation names."""

    stmt = (
        select(MintAllocation, Nation.name.label("nation_name"))
        .join(Nation, MintAllocation.nation_id == Nation.id)
        .order_by(MintAllocation.created_at.desc())
    )
    rows = db.execute(stmt).all()

    allocations = []
    for allocation, nation_name in rows:
        allocations.append(
            {
                "id": allocation.id,
                "nation_id": allocation.nation_id,
                "nation_name": nation_name,
                "period": allocation.period,
                "member_count": allocation.member_count,
                "base_rate": allocation.base_rate,
                "calculated_amount": allocation.calculated_amount,
                "approved_amount": allocation.approved_amount,
                "status": allocation.status,
                "approved_at": (
                    allocation.approved_at.isoformat()
                    if allocation.approved_at
                    else None
                ),
                "distributed_at": (
                    allocation.distributed_at.isoformat()
                    if allocation.distributed_at
                    else None
                ),
                "created_at": (
                    allocation.created_at.isoformat()
                    if allocation.created_at
                    else None
                ),
            }
        )

    return {"allocations": allocations}


# ---------------------------------------------------------------------------
# POST /api/mint/allocations/{allocation_id}/approve
# ---------------------------------------------------------------------------
@router.post("/allocations/{allocation_id}/approve")
def approve_allocation(
    allocation_id: int,
    payload: AllocationApproveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Approve a pending mint allocation."""

    allocation = db.execute(
        select(MintAllocation).where(MintAllocation.id == allocation_id)
    ).scalar_one_or_none()

    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found.")

    if allocation.status == "approved":
        raise HTTPException(
            status_code=400, detail="Allocation is already approved."
        )

    # Use provided approved_amount or fall back to calculated_amount
    approved_amount = (
        payload.approved_amount
        if payload.approved_amount is not None
        else allocation.calculated_amount
    )

    allocation.status = "approved"
    allocation.approved_amount = approved_amount
    allocation.approved_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "allocation_id": allocation.id,
        "approved_amount": approved_amount,
    }


# ---------------------------------------------------------------------------
# POST /api/mint/nations/{nation_id}/approve
# ---------------------------------------------------------------------------
@router.post("/nations/{nation_id}/approve")
def approve_nation(
    nation_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Approve a pending nation application."""

    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    if nation.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Nation is not pending (current status: {nation.status}).",
        )

    nation.status = "approved"
    nation.approved_at = datetime.now(timezone.utc)

    # Promote the nation leader: set their role and add them as a member
    leader = db.execute(
        select(User).where(User.id == nation.leader_id)
    ).scalar_one_or_none()
    if leader is not None:
        if leader.role != "world_mint":
            leader.role = "nation_leader"
        leader.nation_id = nation.id
        nation.member_count += 1

    db.commit()

    # Auto-create nation stock (mirrors page route behavior; previously this
    # was only called from the HTML form handler in page_routes.py).
    create_nation_stock(db, nation)

    return {
        "success": True,
        "nation_id": nation.id,
        "nation_name": nation.name,
    }


# ---------------------------------------------------------------------------
# POST /api/mint/nations/{nation_id}/reject
# ---------------------------------------------------------------------------
@router.post("/nations/{nation_id}/reject")
def reject_nation(
    nation_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Reject a pending nation application.

    Status is moved to ``rejected``; ``leader_id`` and other identity
    fields are preserved for audit purposes.  The applicant may re-apply
    with a different name (or the same name once the rejected row is
    excluded from uniqueness checks — see nations_apply_post).
    """

    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    if nation.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Only pending nations can be rejected (current status: {nation.status}).",
        )

    nation.status = "rejected"
    db.commit()

    return {"success": True, "nation_id": nation.id, "status": "rejected"}


# ---------------------------------------------------------------------------
# POST /api/mint/nations/{nation_id}/suspend
# ---------------------------------------------------------------------------
@router.post("/nations/{nation_id}/suspend")
def suspend_nation(
    nation_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Suspend an approved nation.

    Also demotes the leader's user.role back to ``citizen`` if they don't
    lead any other approved nation.  ``world_mint`` is preserved.
    """

    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    nation.status = "suspended"

    leader = db.execute(
        select(User).where(User.id == nation.leader_id)
    ).scalar_one_or_none()
    if leader is not None and leader.role == "nation_leader":
        # Only demote if they don't lead any *other* approved nation
        other_led = db.execute(
            select(func.count(Nation.id)).where(
                Nation.leader_id == leader.id,
                Nation.status == "approved",
                Nation.id != nation.id,
            )
        ).scalar() or 0
        if other_led == 0:
            leader.role = "citizen"

    db.commit()

    return {"success": True}


# ---------------------------------------------------------------------------
# POST /api/mint/nations/{nation_id}/unsuspend — Restore a suspended nation
# ---------------------------------------------------------------------------
@router.post("/nations/{nation_id}/unsuspend")
def unsuspend_nation(
    nation_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Restore a suspended nation back to ``approved`` and re-promote leader."""

    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")
    if nation.status != "suspended":
        raise HTTPException(status_code=400, detail="Nation is not suspended.")

    nation.status = "approved"

    leader = db.execute(
        select(User).where(User.id == nation.leader_id)
    ).scalar_one_or_none()
    if leader is not None and leader.role not in ("world_mint", "nation_leader"):
        leader.role = "nation_leader"

    db.commit()

    return {"success": True}


# ---------------------------------------------------------------------------
# POST /api/mint/calculate-allocations
# ---------------------------------------------------------------------------
@router.post("/calculate-allocations")
def calculate_allocations(
    payload: CalculateAllocationsRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Calculate monthly mint allocations for all approved nations.

    For each approved nation, creates a pending MintAllocation row based on
    the nation's member_count and the configured BASE_RATE.  Skips nations
    that already have an allocation for the target period (idempotent).
    """

    # Determine the target period (default: next month in "YYYY-MM" format)
    if payload.period:
        period = payload.period
    else:
        now = datetime.now(timezone.utc)
        # Advance to the first day of next month
        next_month = now.replace(day=1) + timedelta(days=32)
        period = next_month.strftime("%Y-%m")

    # Fetch all approved nations
    nations = list(
        db.execute(
            select(Nation).where(Nation.status == "approved")
        ).scalars().all()
    )

    allocations_created = 0
    total_calculated = 0

    for nation in nations:
        # Skip if an allocation already exists for this nation + period
        existing = db.execute(
            select(MintAllocation).where(
                MintAllocation.nation_id == nation.id,
                MintAllocation.period == period,
            )
        ).scalar_one_or_none()

        if existing is not None:
            continue

        calculated_amount = nation.member_count * settings.BASE_RATE

        allocation = MintAllocation(
            nation_id=nation.id,
            period=period,
            member_count=nation.member_count,
            base_rate=settings.BASE_RATE,
            calculated_amount=calculated_amount,
            status="pending",
        )
        db.add(allocation)
        allocations_created += 1
        total_calculated += calculated_amount

    db.commit()

    return {
        "success": True,
        "allocations_created": allocations_created,
        "total_calculated": total_calculated,
    }


# ---------------------------------------------------------------------------
# POST /api/mint/allocations/{allocation_id}/execute
# ---------------------------------------------------------------------------
@router.post("/allocations/{allocation_id}/execute")
def execute_allocation(
    allocation_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Execute a single approved allocation by minting currency to the nation's treasury."""

    allocation = db.execute(
        select(MintAllocation).where(MintAllocation.id == allocation_id)
    ).scalar_one_or_none()

    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found.")

    if allocation.status == "distributed":
        raise HTTPException(
            status_code=400, detail="Allocation has already been distributed."
        )

    if allocation.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Allocation must be approved before execution (current status: {allocation.status}).",
        )

    # Look up the nation to get its treasury address and name
    nation = db.execute(
        select(Nation).where(Nation.id == allocation.nation_id)
    ).scalar_one_or_none()

    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found for this allocation.")

    try:
        tx = create_transaction(
            db,
            tx_type="MINT",
            from_address=settings.WORLD_MINT_ADDRESS,
            to_address=nation.treasury_address,
            amount=allocation.approved_amount,
            memo=f"Mint allocation for period {allocation.period}",
        )
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    allocation.status = "distributed"
    allocation.distributed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "tx_hash": f"tx_{tx.tx_hash[:12]}",
        "amount": allocation.approved_amount,
        "nation_name": nation.name,
    }


# ---------------------------------------------------------------------------
# POST /api/mint/execute-all-approved
# ---------------------------------------------------------------------------
@router.post("/execute-all-approved")
def execute_all_approved(
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Execute all approved (not yet distributed) allocations in one batch."""

    allocations = list(
        db.execute(
            select(MintAllocation).where(MintAllocation.status == "approved")
        ).scalars().all()
    )

    if not allocations:
        return {
            "success": True,
            "executed": 0,
            "total_minted": 0,
            "details": [],
        }

    executed = 0
    total_minted = 0
    details = []

    for allocation in allocations:
        nation = db.execute(
            select(Nation).where(Nation.id == allocation.nation_id)
        ).scalar_one_or_none()

        if nation is None:
            details.append(
                {
                    "allocation_id": allocation.id,
                    "success": False,
                    "error": "Nation not found.",
                }
            )
            continue

        try:
            tx = create_transaction(
                db,
                tx_type="MINT",
                from_address=settings.WORLD_MINT_ADDRESS,
                to_address=nation.treasury_address,
                amount=allocation.approved_amount,
                memo=f"Mint allocation for period {allocation.period}",
            )
        except ValueError as exc:
            details.append(
                {
                    "allocation_id": allocation.id,
                    "nation_name": nation.name,
                    "success": False,
                    "error": str(exc),
                }
            )
            continue

        allocation.status = "distributed"
        allocation.distributed_at = datetime.now(timezone.utc)
        db.commit()

        executed += 1
        total_minted += allocation.approved_amount
        details.append(
            {
                "allocation_id": allocation.id,
                "nation_name": nation.name,
                "tx_hash": f"tx_{tx.tx_hash[:12]}",
                "amount": allocation.approved_amount,
                "success": True,
            }
        )

    return {
        "success": True,
        "executed": executed,
        "total_minted": total_minted,
        "details": details,
    }


# ---------------------------------------------------------------------------
# POST /api/mint/recalculate-gdp
# ---------------------------------------------------------------------------
@router.post("/recalculate-gdp")
def recalculate_gdp(
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Force a GDP recalculation for all approved nations."""
    count = recalculate_all_gdp(db)
    return {"success": True, "nations_recalculated": count}


# ---------------------------------------------------------------------------
# GET /api/mint/gdp-history
# ---------------------------------------------------------------------------
@router.get("/gdp-history")
def gdp_history(
    nation_id: int | None = None,
    limit: int = 30,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Return GDP snapshot history for chart display."""
    stmt = select(GdpSnapshot).order_by(GdpSnapshot.created_at.desc()).limit(limit)
    if nation_id is not None:
        stmt = stmt.where(GdpSnapshot.nation_id == nation_id)

    snapshots = list(db.execute(stmt).scalars().all())

    return {
        "snapshots": [
            {
                "nation_id": s.nation_id,
                "snapshot_date": s.snapshot_date,
                "treasury_score": s.treasury_score,
                "activity_score": s.activity_score,
                "revenue_score": s.revenue_score,
                "citizens_score": s.citizens_score,
                "composite_score": s.composite_score,
                "gdp_multiplier": s.gdp_multiplier,
                "gdp_display": round(s.gdp_multiplier / 100, 2),
            }
            for s in snapshots
        ]
    }


# ---------------------------------------------------------------------------
# Phase 2J — Stimulus proposal review endpoints
# ---------------------------------------------------------------------------
# The daily GDP job (``run_stimulus_checks``) creates ``StimulusProposal`` rows
# whenever a nation's composite GDP score drops 10/20/30% from the previous
# snapshot.  Proposals are *never* auto-executed — the World Mint reviews them
# here and explicitly approves (mint into the nation treasury) or rejects.


@router.get("/stimulus-proposals")
def list_stimulus_proposals(
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Return stimulus proposals for World Mint review.

    Default returns only ``pending`` proposals.  Pass ``status=all`` to see
    the full history (approved + rejected included).
    """

    stmt = select(StimulusProposal, Nation.name.label("nation_name")).join(
        Nation, StimulusProposal.nation_id == Nation.id
    )
    if status is None or status == "pending":
        stmt = stmt.where(StimulusProposal.status == "pending")
    elif status != "all":
        stmt = stmt.where(StimulusProposal.status == status)

    stmt = stmt.order_by(StimulusProposal.proposed_at.desc()).limit(limit)
    rows = db.execute(stmt).all()

    return {
        "proposals": [
            {
                "id": p.id,
                "nation_id": p.nation_id,
                "nation_name": nation_name,
                "tier": p.tier,
                "drop_pct": p.drop_pct,
                "gdp_score_at_trigger": p.gdp_score_at_trigger,
                "gdp_score_previous": p.gdp_score_previous,
                "proposed_amount": p.proposed_amount,
                "status": p.status,
                "proposed_at": p.proposed_at.isoformat() if p.proposed_at else None,
                "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
                "reviewed_by": p.reviewed_by,
            }
            for (p, nation_name) in rows
        ]
    }


@router.post("/stimulus-proposals/{proposal_id}/approve")
def approve_stimulus_proposal(
    proposal_id: int,
    payload: StimulusReviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Approve a pending stimulus proposal and mint into the nation treasury.

    For ``warning`` tier proposals (proposed_amount = 0) approval is recorded
    without minting — the tier is informational only.
    """

    proposal = db.execute(
        select(StimulusProposal).where(StimulusProposal.id == proposal_id)
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=404, detail="Stimulus proposal not found.")
    if proposal.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Proposal is not pending (current status: {proposal.status}).",
        )

    nation = db.execute(
        select(Nation).where(Nation.id == proposal.nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    # World Mint may override the calculated amount (e.g. cap to a smaller
    # mint than the formula suggests, or zero out a strong-tier mint).
    final_amount = (
        payload.approved_amount
        if payload.approved_amount is not None
        else proposal.proposed_amount
    )
    if final_amount < 0:
        raise HTTPException(status_code=400, detail="Amount cannot be negative.")

    tx_hash: str | None = None
    if final_amount > 0:
        try:
            tx = create_transaction(
                db,
                tx_type="MINT",
                from_address=settings.WORLD_MINT_ADDRESS,
                to_address=nation.treasury_address,
                amount=final_amount,
                memo=(
                    f"Stimulus mint ({proposal.tier}, "
                    f"GDP drop {proposal.drop_pct}%)"
                ),
            )
            tx_hash = f"tx_{tx.tx_hash[:12]}"
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    proposal.status = "approved"
    proposal.proposed_amount = final_amount
    proposal.reviewed_by = admin.id
    proposal.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "proposal_id": proposal.id,
        "minted": final_amount,
        "tx_hash": tx_hash,
        "nation_name": nation.name,
    }


@router.post("/stimulus-proposals/{proposal_id}/reject")
def reject_stimulus_proposal(
    proposal_id: int,
    payload: StimulusReviewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Reject a pending stimulus proposal without minting."""

    proposal = db.execute(
        select(StimulusProposal).where(StimulusProposal.id == proposal_id)
    ).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=404, detail="Stimulus proposal not found.")
    if proposal.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Proposal is not pending (current status: {proposal.status}).",
        )

    proposal.status = "rejected"
    proposal.reviewed_by = admin.id
    proposal.reviewed_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "proposal_id": proposal.id,
        "status": "rejected",
    }


# ---------------------------------------------------------------------------
# WM nation-identity edit + manual stock recalc + detailed stats
# ---------------------------------------------------------------------------

import re as _re_id


class MintEditNationIdentityRequest(BaseModel):
    name: str | None = None
    currency_name: str | None = None
    currency_code: str | None = None
    discord_invite: str | None = None
    game: str | None = None


@router.put("/nations/{nation_id}/identity")
def mint_edit_nation_identity(
    nation_id: int,
    payload: MintEditNationIdentityRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """World-Mint-only nation identity edit.  Renames the nation, swaps
    currency name/code, updates discord invite or game.  Keeps the
    backing nation Stock row in sync (ticker + name).
    """
    from app.models import Stock as _Stock

    nation = db.execute(select(Nation).where(Nation.id == nation_id)).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="Name cannot be empty.")
        if new_name != nation.name:
            clash = db.execute(
                select(Nation).where(Nation.name == new_name, Nation.id != nation_id)
            ).scalar_one_or_none()
            if clash is not None:
                raise HTTPException(status_code=409, detail=f"Nation name already taken by #{clash.id}.")
            nation.name = new_name

    if payload.currency_name is not None:
        nation.currency_name = payload.currency_name.strip() or None

    if payload.currency_code is not None:
        cc = payload.currency_code.strip().upper() or None
        if cc and not _re_id.match(r"^[A-Z]{2,8}$", cc):
            raise HTTPException(status_code=400, detail="Currency code must be 2-8 uppercase letters.")
        if cc:
            ticker_clash = db.execute(
                select(_Stock).where(
                    _Stock.ticker == cc,
                    ~((_Stock.stock_type == "nation") & (_Stock.entity_id == nation.id)),
                )
            ).scalar_one_or_none()
            if ticker_clash is not None:
                raise HTTPException(status_code=409, detail=f"Ticker {cc} already in use.")
        nation.currency_code = cc

    if payload.discord_invite is not None:
        nation.discord_invite = payload.discord_invite.strip() or None
    if payload.game is not None:
        nation.game = payload.game.strip() or None

    # Sync nation stock
    nation_stock = db.execute(
        select(_Stock).where(_Stock.stock_type == "nation", _Stock.entity_id == nation.id)
    ).scalar_one_or_none()
    if nation_stock is not None:
        nation_stock.name = nation.name
        if nation.currency_code:
            nation_stock.ticker = nation.currency_code
        else:
            from app.valuation import generate_ticker
            nation_stock.ticker = generate_ticker(nation.name, db)

    db.commit()
    return {
        "success": True,
        "name": nation.name,
        "currency_name": nation.currency_name,
        "currency_code": nation.currency_code,
        "discord_invite": nation.discord_invite,
        "game": nation.game,
    }


@router.post("/recalculate-stocks")
def mint_recalculate_stocks(
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Force a recalculation of every active stock's price."""
    from app.valuation import recalculate_all_prices
    n = recalculate_all_prices(db)
    return {"success": True, "stocks_recalculated": n}


@router.get("/stats/detailed")
def mint_stats_detailed(
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Deep economy stats: hash chain status, nations breakdown, supply
    by holder type, recent transaction-type counts.  Mirrors the data
    behind the website's /mint/stats page.
    """
    from sqlalchemy import func as _func
    from app.blockchain import verify_chain
    from app.models import Transaction as _Tx

    chain = verify_chain(db)

    user_balance = db.execute(
        select(_func.coalesce(_func.sum(User.balance), 0)).where(User.role != "world_mint")
    ).scalar() or 0
    nation_balance = db.execute(
        select(_func.coalesce(_func.sum(Nation.treasury_balance), 0))
    ).scalar() or 0

    tx_by_type = {
        row[0]: row[1]
        for row in db.execute(
            select(_Tx.tx_type, _func.count(_Tx.id)).group_by(_Tx.tx_type)
        ).all()
    }

    nations = list(
        db.execute(select(Nation).where(Nation.status == "approved").order_by(Nation.name)).scalars().all()
    )

    return {
        "chain": {
            "valid": chain["valid"],
            "errors": chain.get("errors", []),
            "block_count": chain.get("block_count", 0),
        },
        "supply": {
            "user_balances": user_balance,
            "nation_treasuries": nation_balance,
            "total": user_balance + nation_balance,
        },
        "transactions_by_type": tx_by_type,
        "nations": [
            {
                "id": n.id,
                "name": n.name,
                "treasury_balance": n.treasury_balance,
                "member_count": n.member_count,
                "gdp_score": n.gdp_score,
                "gdp_multiplier": n.gdp_multiplier,
                "currency_code": n.currency_code,
                "demurrage_enabled": n.demurrage_enabled,
                "demurrage_rate_bps": n.demurrage_rate_bps,
                "mint_cap": n.mint_cap,
            }
            for n in nations
        ],
    }
