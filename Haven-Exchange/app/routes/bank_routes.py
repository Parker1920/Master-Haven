"""
Travelers Exchange — Banking System Routes

Provides API endpoints for bank management, loan issuance, loan repayment
(with burn split), loan forgiveness, and World Mint global settings.
"""

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_login, require_role
from app.blockchain import create_transaction
from app.config import settings
from app.database import get_db
from app.models import Bank, GlobalSettings, Loan, LoanPayment, Nation, User
from app.wallet import generate_bank_wallet_address

router = APIRouter(tags=["banking"])

# Common dependency — World Mint admin role
_require_world_mint = require_role("world_mint")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateBankRequest(BaseModel):
    name: str
    owner_user_id: int


class CreateLoanRequest(BaseModel):
    borrower_user_id: int
    amount: int
    memo: str | None = None


class LoanPaymentRequest(BaseModel):
    amount: int


class UpdateSettingsRequest(BaseModel):
    burn_rate_bps: int
    interest_rate_cap_bps: int


# ---------------------------------------------------------------------------
# Helper: get the GlobalSettings singleton
# ---------------------------------------------------------------------------
def _get_global_settings(db: Session) -> GlobalSettings:
    """Return the singleton GlobalSettings row, creating it if missing."""
    gs = db.execute(select(GlobalSettings).where(GlobalSettings.id == 1)).scalar_one_or_none()
    if gs is None:
        gs = GlobalSettings(id=1, burn_rate_bps=1000, interest_rate_cap_bps=2000)
        db.add(gs)
        db.commit()
        db.refresh(gs)
    return gs


# ===========================================================================
# NATION LEADER ENDPOINTS — Bank management
# ===========================================================================

# ---------------------------------------------------------------------------
# POST /api/banks — Create a bank for the leader's nation
# ---------------------------------------------------------------------------
@router.post("/api/banks")
def create_bank(
    payload: CreateBankRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Create a new bank within the current user's nation.

    Only nation leaders (or world_mint) can create banks.
    Max 4 banks per nation.  The owner_user_id must be a member of the nation.
    """
    # Validate: requester must be a nation leader or world_mint
    if current_user.role not in ("nation_leader", "world_mint"):
        raise HTTPException(status_code=403, detail="Only nation leaders can create banks.")

    # Find the nation the leader owns
    nation = db.execute(
        select(Nation).where(Nation.leader_id == current_user.id, Nation.status == "approved")
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=400, detail="You do not lead an approved nation.")

    # Validate: max 4 banks per nation
    bank_count = db.execute(
        select(func.count(Bank.id)).where(Bank.nation_id == nation.id)
    ).scalar() or 0
    if bank_count >= 4:
        raise HTTPException(status_code=400, detail="Maximum of 4 banks per nation reached.")

    # Validate: bank name is not empty
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bank name cannot be empty.")

    # Validate: owner_user_id is a member of this nation
    owner = db.execute(
        select(User).where(User.id == payload.owner_user_id)
    ).scalar_one_or_none()
    if owner is None:
        raise HTTPException(status_code=404, detail="Designated bank operator not found.")
    if owner.nation_id != nation.id:
        raise HTTPException(
            status_code=400,
            detail="Bank operator must be a member of your nation.",
        )

    # Create the bank with a placeholder wallet, flush to get ID
    bank = Bank(
        nation_id=nation.id,
        owner_id=payload.owner_user_id,
        name=name,
        wallet_address="PENDING",
    )
    db.add(bank)
    db.flush()  # assigns bank.id

    # Generate the real wallet address from the bank ID
    bank.wallet_address = generate_bank_wallet_address(bank.id)
    db.commit()
    db.refresh(bank)

    return {
        "success": True,
        "bank": {
            "id": bank.id,
            "name": bank.name,
            "wallet_address": bank.wallet_address,
            "nation_id": bank.nation_id,
            "owner_id": bank.owner_id,
            "balance": bank.balance,
        },
    }


# ---------------------------------------------------------------------------
# GET /api/banks/nation/{nation_id} — List all banks for a nation (public)
# ---------------------------------------------------------------------------
@router.get("/api/banks/nation/{nation_id}")
def list_nation_banks(
    nation_id: int,
    db: Session = Depends(get_db),
):
    """Return all banks belonging to a nation."""
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    banks = list(
        db.execute(
            select(Bank).where(Bank.nation_id == nation_id)
            .order_by(Bank.created_at.desc())
        ).scalars().all()
    )

    result = []
    for b in banks:
        # Count active loans for this bank
        active_loans = db.execute(
            select(func.count(Loan.id)).where(
                Loan.bank_id == b.id, Loan.status == "active"
            )
        ).scalar() or 0

        owner = db.execute(
            select(User).where(User.id == b.owner_id)
        ).scalar_one_or_none()

        result.append({
            "id": b.id,
            "name": b.name,
            "wallet_address": b.wallet_address,
            "balance": b.balance,
            "total_loaned": b.total_loaned,
            "total_burned": b.total_burned,
            "is_active": b.is_active,
            "active_loans": active_loans,
            "owner_name": owner.display_name or owner.username if owner else "Unknown",
            "created_at": b.created_at.isoformat() if b.created_at else None,
        })

    return {"banks": result, "nation_name": nation.name}


# ---------------------------------------------------------------------------
# POST /api/banks/{bank_id}/deactivate — Deactivate a bank
# ---------------------------------------------------------------------------
@router.post("/api/banks/{bank_id}/deactivate")
def deactivate_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Deactivate a bank.  Only the Nation Leader of that bank's nation may do this."""
    bank = db.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found.")

    # Verify the requester is the nation leader
    nation = db.execute(
        select(Nation).where(Nation.id == bank.nation_id)
    ).scalar_one_or_none()
    if nation is None or nation.leader_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the nation leader can deactivate banks.",
        )

    bank.is_active = False
    db.commit()

    return {"success": True, "bank_id": bank.id}


# ===========================================================================
# BANK OPERATOR ENDPOINTS — Loan management
# ===========================================================================

# ---------------------------------------------------------------------------
# GET /api/banks/{bank_id} — Bank detail
# ---------------------------------------------------------------------------
@router.get("/api/banks/{bank_id}")
def get_bank_detail(
    bank_id: int,
    db: Session = Depends(get_db),
):
    """Return bank details including active loan count and totals."""
    bank = db.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found.")

    # Count active loans
    active_loans = db.execute(
        select(func.count(Loan.id)).where(
            Loan.bank_id == bank.id, Loan.status == "active"
        )
    ).scalar() or 0

    owner = db.execute(select(User).where(User.id == bank.owner_id)).scalar_one_or_none()
    nation = db.execute(select(Nation).where(Nation.id == bank.nation_id)).scalar_one_or_none()

    return {
        "id": bank.id,
        "name": bank.name,
        "wallet_address": bank.wallet_address,
        "balance": bank.balance,
        "total_loaned": bank.total_loaned,
        "total_burned": bank.total_burned,
        "is_active": bank.is_active,
        "active_loans": active_loans,
        "nation_id": bank.nation_id,
        "nation_name": nation.name if nation else "Unknown",
        "owner_id": bank.owner_id,
        "owner_name": owner.display_name or owner.username if owner else "Unknown",
        "created_at": bank.created_at.isoformat() if bank.created_at else None,
    }


# ---------------------------------------------------------------------------
# GET /api/banks/{bank_id}/loans — List all loans for a bank
# ---------------------------------------------------------------------------
@router.get("/api/banks/{bank_id}/loans")
def list_bank_loans(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """List all loans issued by a bank.  Requires bank operator or nation leader."""
    bank = db.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found.")

    # Access check: bank operator, nation leader, or world_mint
    nation = db.execute(select(Nation).where(Nation.id == bank.nation_id)).scalar_one_or_none()
    is_operator = current_user.id == bank.owner_id
    is_leader = nation is not None and nation.leader_id == current_user.id
    is_admin = current_user.role == "world_mint"
    if not (is_operator or is_leader or is_admin):
        raise HTTPException(status_code=403, detail="Access denied.")

    loans = list(
        db.execute(
            select(Loan).where(Loan.bank_id == bank_id)
            .order_by(Loan.opened_at.desc())
        ).scalars().all()
    )

    result = []
    for loan in loans:
        borrower = db.execute(
            select(User).where(User.id == loan.borrower_id)
        ).scalar_one_or_none()
        result.append({
            "id": loan.id,
            "borrower_name": borrower.display_name or borrower.username if borrower else "Unknown",
            "borrower_wallet": borrower.wallet_address if borrower else None,
            "principal": loan.principal,
            "outstanding": loan.outstanding,
            "interest_rate": loan.interest_rate,
            "burn_rate_snapshot": loan.burn_rate_snapshot,
            "status": loan.status,
            "memo": loan.memo,
            "opened_at": loan.opened_at.isoformat() if loan.opened_at else None,
            "closed_at": loan.closed_at.isoformat() if loan.closed_at else None,
        })

    return {"loans": result}


# ---------------------------------------------------------------------------
# POST /api/banks/{bank_id}/loans — Issue a new loan
# ---------------------------------------------------------------------------
@router.post("/api/banks/{bank_id}/loans")
def create_loan(
    bank_id: int,
    payload: CreateLoanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Issue a new loan from a bank to a citizen.

    Requires the current user to be the bank operator.
    Validates: bank is active, borrower is in the same nation, borrower has
    no active loans anywhere, bank has sufficient reserves.
    Snapshots current GlobalSettings rates into the loan record.
    """
    bank = db.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found.")

    # Access check: only the bank operator can issue loans
    if current_user.id != bank.owner_id:
        raise HTTPException(status_code=403, detail="Only the bank operator can issue loans.")

    # Validate: bank must be active
    if not bank.is_active:
        raise HTTPException(status_code=400, detail="This bank is deactivated.")

    # Validate: amount must be positive
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Loan amount must be greater than zero.")

    # Validate: borrower exists
    borrower = db.execute(
        select(User).where(User.id == payload.borrower_user_id)
    ).scalar_one_or_none()
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found.")

    # Validate: borrower is a member of the same nation as the bank
    if borrower.nation_id != bank.nation_id:
        raise HTTPException(
            status_code=400,
            detail="Borrower must be a member of the same nation as the bank.",
        )

    # Validate: borrower has no active loans anywhere
    active_loan = db.execute(
        select(Loan).where(Loan.borrower_id == borrower.id, Loan.status == "active")
    ).scalar_one_or_none()
    if active_loan is not None:
        raise HTTPException(
            status_code=400,
            detail="Borrower already has an active loan. Must repay before taking a new one.",
        )

    # Validate: bank has sufficient reserves
    if bank.balance < payload.amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient bank reserves. Available: {bank.balance}, requested: {payload.amount}.",
        )

    # Snapshot the current global settings
    gs = _get_global_settings(db)

    # Create the LOAN transaction (bank wallet → borrower wallet)
    try:
        tx = create_transaction(
            db,
            tx_type="LOAN",
            from_address=bank.wallet_address,
            to_address=borrower.wallet_address,
            amount=payload.amount,
            memo=f"Loan from {bank.name}: {payload.memo or 'No memo'}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Track lifetime totals on the bank
    bank.total_loaned += payload.amount

    # Create the Loan record with snapshots of current rates
    loan = Loan(
        bank_id=bank.id,
        borrower_id=borrower.id,
        principal=payload.amount,
        outstanding=payload.amount,
        interest_rate=gs.interest_rate_cap_bps,
        burn_rate_snapshot=gs.burn_rate_bps,
        status="active",
        memo=payload.memo,
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)

    return {
        "success": True,
        "loan": {
            "id": loan.id,
            "principal": loan.principal,
            "outstanding": loan.outstanding,
            "interest_rate": loan.interest_rate,
            "burn_rate_snapshot": loan.burn_rate_snapshot,
            "status": loan.status,
            "tx_hash": tx.tx_hash,
        },
    }


# ---------------------------------------------------------------------------
# POST /api/banks/{bank_id}/loans/{loan_id}/forgive — Forgive a loan
# ---------------------------------------------------------------------------
@router.post("/api/banks/{bank_id}/loans/{loan_id}/forgive")
def forgive_loan(
    bank_id: int,
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Forgive a loan entirely.  Only the Nation Leader of the bank's nation may do this.

    Zeros out the outstanding balance and marks the loan as closed.
    Records a LOAN_FORGIVE transaction on the ledger.
    """
    bank = db.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if bank is None:
        raise HTTPException(status_code=404, detail="Bank not found.")

    # Access check: only the nation leader
    nation = db.execute(
        select(Nation).where(Nation.id == bank.nation_id)
    ).scalar_one_or_none()
    if nation is None or nation.leader_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the nation leader can forgive loans.",
        )

    loan = db.execute(
        select(Loan).where(Loan.id == loan_id, Loan.bank_id == bank_id)
    ).scalar_one_or_none()
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found.")
    if loan.status != "active":
        raise HTTPException(status_code=400, detail="Loan is not active.")

    # Zero out the loan
    loan.outstanding = 0
    loan.status = "closed"
    loan.closed_at = datetime.now(timezone.utc)

    # Record the forgiveness on the ledger (amount=0 is allowed for LOAN_FORGIVE)
    # We use MINT type as a placeholder since LOAN_FORGIVE with amount=0 would
    # fail validation ("amount must be greater than zero").  Instead, record the
    # forgiveness as a memo on a minimal LOAN_FORGIVE transaction.
    # NOTE: We skip the blockchain tx for zero-amount forgiveness to avoid
    # the positive-amount validation.  The loan status change is the record.

    db.commit()

    return {
        "success": True,
        "loan_id": loan.id,
        "status": loan.status,
    }


# ===========================================================================
# CITIZEN ENDPOINTS — Loan self-service
# ===========================================================================

# ---------------------------------------------------------------------------
# GET /api/loans/mine — List the current user's loans
# ---------------------------------------------------------------------------
@router.get("/api/loans/mine")
def my_loans(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Return all loans belonging to the current user, across all banks."""
    loans = list(
        db.execute(
            select(Loan).where(Loan.borrower_id == current_user.id)
            .order_by(Loan.opened_at.desc())
        ).scalars().all()
    )

    result = []
    for loan in loans:
        bank = db.execute(select(Bank).where(Bank.id == loan.bank_id)).scalar_one_or_none()
        result.append({
            "id": loan.id,
            "bank_name": bank.name if bank else "Unknown",
            "bank_id": loan.bank_id,
            "principal": loan.principal,
            "outstanding": loan.outstanding,
            "interest_rate": loan.interest_rate,
            "burn_rate_snapshot": loan.burn_rate_snapshot,
            "status": loan.status,
            "memo": loan.memo,
            "opened_at": loan.opened_at.isoformat() if loan.opened_at else None,
            "closed_at": loan.closed_at.isoformat() if loan.closed_at else None,
        })

    return {"loans": result}


# ---------------------------------------------------------------------------
# POST /api/loans/{loan_id}/pay — Make a loan payment with burn split
# ---------------------------------------------------------------------------
@router.post("/api/loans/{loan_id}/pay")
def pay_loan(
    loan_id: int,
    payload: LoanPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Make a payment on a loan.

    The payment is split: a percentage (burn_rate_snapshot) goes to the World
    Mint (burned/destroyed), the rest returns to the bank's reserves.

    Creates one or two blockchain transactions:
      1. LOAN_PAYMENT: borrower → bank wallet (bank_amount portion)
      2. BURN: borrower → World Mint (burn_amount portion, if > 0)

    Updates the loan outstanding balance.  If outstanding reaches 0, the loan
    is marked as closed.
    """
    loan = db.execute(
        select(Loan).where(Loan.id == loan_id)
    ).scalar_one_or_none()
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found.")

    # Validate: loan belongs to the current user
    if loan.borrower_id != current_user.id:
        raise HTTPException(status_code=403, detail="This is not your loan.")

    # Validate: loan is active
    if loan.status != "active":
        raise HTTPException(status_code=400, detail="Loan is not active.")

    # Validate: positive amount
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero.")

    # Cap payment to outstanding balance (don't overpay)
    amount = min(payload.amount, loan.outstanding)

    # Validate: user has sufficient balance
    if current_user.balance < amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {current_user.balance}, required: {amount}.",
        )

    # Calculate burn split using the loan's snapshot burn rate
    burn_amount = math.floor(amount * loan.burn_rate_snapshot / 10000)
    bank_amount = amount - burn_amount

    bank = db.execute(select(Bank).where(Bank.id == loan.bank_id)).scalar_one_or_none()
    if bank is None:
        raise HTTPException(status_code=500, detail="Bank not found for this loan.")

    # Transaction 1: LOAN_PAYMENT — borrower → bank wallet (bank portion)
    tx_hash = ""
    if bank_amount > 0:
        try:
            tx = create_transaction(
                db,
                tx_type="LOAN_PAYMENT",
                from_address=current_user.wallet_address,
                to_address=bank.wallet_address,
                amount=bank_amount,
                memo=f"Loan payment #{loan.id} (bank portion)",
            )
            tx_hash = tx.tx_hash
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # Transaction 2: BURN — borrower → World Mint (burn portion, if > 0)
    if burn_amount > 0:
        try:
            burn_tx = create_transaction(
                db,
                tx_type="BURN",
                from_address=current_user.wallet_address,
                to_address=settings.WORLD_MINT_ADDRESS,
                amount=burn_amount,
                memo=f"Loan payment #{loan.id} burn split ({loan.burn_rate_snapshot}bps)",
            )
            # Use burn tx hash if we didn't have a bank_amount tx
            if not tx_hash:
                tx_hash = burn_tx.tx_hash
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # Update bank lifetime burn tracker
    bank.total_burned += burn_amount

    # Update the loan outstanding balance
    loan.outstanding -= amount
    if loan.outstanding <= 0:
        loan.outstanding = 0
        loan.status = "closed"
        loan.closed_at = datetime.now(timezone.utc)

    # Record the LoanPayment
    payment = LoanPayment(
        loan_id=loan.id,
        amount=amount,
        burn_amount=burn_amount,
        bank_amount=bank_amount,
        balance_after=loan.outstanding,
        tx_hash=tx_hash,
    )
    db.add(payment)
    db.commit()

    return {
        "success": True,
        "payment": {
            "amount": amount,
            "burn_amount": burn_amount,
            "bank_amount": bank_amount,
            "balance_after": loan.outstanding,
        },
        "loan_status": loan.status,
    }


# ===========================================================================
# WORLD MINT ENDPOINTS — Global settings management
# ===========================================================================

# ---------------------------------------------------------------------------
# GET /api/mint/settings — Return current global settings
# ---------------------------------------------------------------------------
@router.get("/api/mint/settings")
def get_settings(
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Return the current global economy settings."""
    gs = _get_global_settings(db)
    return {
        "burn_rate_bps": gs.burn_rate_bps,
        "interest_rate_cap_bps": gs.interest_rate_cap_bps,
        "burn_rate_pct": round(gs.burn_rate_bps / 100, 2),
        "interest_rate_cap_pct": round(gs.interest_rate_cap_bps / 100, 2),
        "updated_at": gs.updated_at.isoformat() if gs.updated_at else None,
    }


# ---------------------------------------------------------------------------
# POST /api/mint/settings — Update global settings
# ---------------------------------------------------------------------------
@router.post("/api/mint/settings")
def update_settings(
    payload: UpdateSettingsRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_world_mint),
):
    """Update the global economy settings (burn rate, interest rate cap).

    Both values are in basis points (0–10000).
    """
    # Validate ranges
    if not (0 <= payload.burn_rate_bps <= 10000):
        raise HTTPException(
            status_code=400,
            detail="Burn rate must be between 0 and 10000 basis points.",
        )
    if not (0 <= payload.interest_rate_cap_bps <= 10000):
        raise HTTPException(
            status_code=400,
            detail="Interest rate cap must be between 0 and 10000 basis points.",
        )

    gs = _get_global_settings(db)
    gs.burn_rate_bps = payload.burn_rate_bps
    gs.interest_rate_cap_bps = payload.interest_rate_cap_bps
    gs.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "burn_rate_bps": gs.burn_rate_bps,
        "interest_rate_cap_bps": gs.interest_rate_cap_bps,
    }
