"""
Travelers Exchange — Transaction Routes

Endpoints for creating transfers, viewing individual transactions, and
browsing the public ledger.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.blockchain import (
    create_transaction,
    get_all_transactions,
    get_transaction_by_hash,
)
from app.database import get_db
from app.models import Nation, Transaction, User

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class TransferRequest(BaseModel):
    to_address: str
    amount: int
    memo: str | None = None


# ---------------------------------------------------------------------------
# POST /api/transactions/transfer
# ---------------------------------------------------------------------------
@router.post("/transfer")
def transfer(
    payload: TransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transfer currency from the authenticated user's wallet to another address."""
    # Validate amount
    if payload.amount <= 0:
        return {"success": False, "error": "Amount must be greater than zero."}

    # Validate destination exists (user wallet or nation treasury)
    if payload.to_address.startswith(settings.NATION_WALLET_PREFIX):
        recipient = db.execute(
            select(Nation).where(Nation.treasury_address == payload.to_address)
        ).scalar_one_or_none()
        if recipient is None:
            return {"success": False, "error": f"Nation treasury '{payload.to_address}' not found."}
    else:
        recipient = db.execute(
            select(User).where(User.wallet_address == payload.to_address)
        ).scalar_one_or_none()
        if recipient is None:
            return {"success": False, "error": f"Wallet '{payload.to_address}' not found."}

    # Prevent self-transfer
    if payload.to_address == current_user.wallet_address:
        return {"success": False, "error": "Cannot transfer to your own wallet."}

    try:
        tx = create_transaction(
            db,
            tx_type="TRANSFER",
            from_address=current_user.wallet_address,
            to_address=payload.to_address,
            amount=payload.amount,
            memo=payload.memo,
        )
        return {
            "success": True,
            "tx_hash": f"tx_{tx.tx_hash[:12]}",
        }
    except ValueError as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# GET /api/transactions/{tx_hash}
# ---------------------------------------------------------------------------
@router.get("/{tx_hash}")
def get_transaction(tx_hash: str, db: Session = Depends(get_db)):
    """Look up a single transaction by its hash (public)."""
    # Allow lookups with or without the "tx_" prefix
    raw_hash = tx_hash
    if raw_hash.startswith("tx_"):
        # The short form only has 12 chars — do a prefix search
        prefix = raw_hash[3:]
        tx = db.execute(
            select(Transaction).where(Transaction.tx_hash.startswith(prefix))
        ).scalar_one_or_none()
    else:
        tx = get_transaction_by_hash(db, raw_hash)

    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    return {
        "tx_hash": tx.tx_hash,
        "prev_hash": tx.prev_hash,
        "tx_type": tx.tx_type,
        "from_address": tx.from_address,
        "to_address": tx.to_address,
        "amount": tx.amount,
        "fee": tx.fee,
        "memo": tx.memo,
        "nonce": tx.nonce,
        "status": tx.status,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/ledger  (mounted on the router but at /api/ledger via main.py
#                   alias — or we add a separate route below)
# ---------------------------------------------------------------------------
# NOTE: The spec says GET /api/ledger.  We register a standalone route on the
# router but override the prefix by using the app-level include.  Alternatively
# we define it here with a full path and include it without prefix.  To keep
# things simple, this endpoint is placed in this module but the router for it
# is separate.

ledger_router = APIRouter(tags=["transactions"])


@ledger_router.get("/api/ledger")
def public_ledger(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return a paginated view of all confirmed transactions (public)."""
    offset = (page - 1) * per_page
    transactions, total = get_all_transactions(db, limit=per_page, offset=offset)

    return {
        "transactions": [
            {
                "tx_hash": tx.tx_hash,
                "prev_hash": tx.prev_hash,
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
        "total": total,
        "page": page,
        "per_page": per_page,
    }
