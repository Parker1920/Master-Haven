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
    interest_burn_rate_bps: int | None = None  # Phase 2B; optional for back-compat


# ---------------------------------------------------------------------------
# Helper: get the GlobalSettings singleton
# ---------------------------------------------------------------------------
def _get_global_settings(db: Session) -> GlobalSettings:
    """Return the singleton GlobalSettings row, creating it if missing."""
    gs = db.execute(select(GlobalSettings).where(GlobalSettings.id == 1)).scalar_one_or_none()
    if gs is None:
        gs = GlobalSettings(
            id=1,
            burn_rate_bps=1000,
            interest_rate_cap_bps=2000,
            interest_burn_rate_bps=8000,
        )
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
            "accrued_interest": loan.accrued_interest,
            "total_owed": loan.outstanding + loan.accrued_interest,
            "cap_amount": loan.cap_amount,
            "interest_frozen": loan.interest_frozen,
            "last_accrual_at": loan.last_accrual_at.isoformat() if loan.last_accrual_at else None,
            "interest_rate": loan.interest_rate,
            "burn_rate_snapshot": loan.burn_rate_snapshot,
            "lender_type": loan.lender_type,
            "lender_wallet_address": loan.lender_wallet_address,
            "treasury_nation_id": loan.treasury_nation_id,
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

    # Create the Loan record with snapshots of current rates.
    # Phase 2A: cap_amount = principal (100% lifetime interest cap),
    # last_accrual_at seeded to "now" so the daily job has a reference.
    # Phase 2B: snapshot the interest burn rate (default 8000 bps = 80%).
    now = datetime.now(timezone.utc)
    loan = Loan(
        bank_id=bank.id,
        lender_type="bank",
        lender_wallet_address=bank.wallet_address,
        treasury_nation_id=None,
        borrower_id=borrower.id,
        principal=payload.amount,
        outstanding=payload.amount,
        accrued_interest=0,
        cap_amount=payload.amount,
        interest_frozen=False,
        last_accrual_at=now,
        interest_rate=gs.interest_rate_cap_bps,
        burn_rate_snapshot=gs.burn_rate_bps,
        interest_burn_rate_snapshot=gs.interest_burn_rate_bps,
        total_interest_paid=0,
        total_burned_during_payments=0,
        final_close_burn=0,
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
            "accrued_interest": loan.accrued_interest,
            "cap_amount": loan.cap_amount,
            "interest_frozen": loan.interest_frozen,
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

    # Capture the outstanding balance before zeroing for the audit memo.
    forgiven_amount = loan.outstanding

    # Zero out the loan
    loan.outstanding = 0
    loan.status = "closed"
    loan.closed_at = datetime.now(timezone.utc)

    # Record the forgiveness on the ledger as a LOAN_FORGIVE transaction.
    # No coin movement occurs — the bank loses a receivable, not balance —
    # so the tx amount is 0. The forgiven principal is captured in the memo
    # for audit purposes. blockchain.create_transaction() permits amount=0
    # for LOAN_FORGIVE specifically.
    borrower = db.execute(
        select(User).where(User.id == loan.borrower_id)
    ).scalar_one_or_none()
    forgive_memo = (
        f"Loan #{loan.id} forgiven by NL ({forgiven_amount} TC outstanding)"
    )
    if borrower is not None:
        try:
            create_transaction(
                db,
                tx_type="LOAN_FORGIVE",
                from_address=bank.wallet_address,
                to_address=borrower.wallet_address,
                amount=0,
                memo=forgive_memo,
            )
        except ValueError as exc:
            # Fail loud — the status change should not commit if the audit
            # entry can't be written.
            raise HTTPException(status_code=500, detail=f"Could not record forgiveness on the ledger: {exc}")

    db.commit()

    return {
        "success": True,
        "loan_id": loan.id,
        "status": loan.status,
    }


# ===========================================================================
# NATION TREASURY LOAN ENDPOINTS — Phase 2C
# ===========================================================================

# ---------------------------------------------------------------------------
# POST /api/nations/{nation_id}/loans — Issue a treasury loan
# ---------------------------------------------------------------------------
@router.post("/api/nations/{nation_id}/loans")
def create_treasury_loan(
    nation_id: int,
    payload: CreateTreasuryLoanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Issue a loan directly from a nation's treasury to a citizen.

    Only the nation leader of the specified nation may call this endpoint.
    The loan is recorded with lender_type='treasury' and bank_id=0 (sentinel
    — SQLite cannot alter nullability post-creation, so 0 denotes no bank).
    A LOAN_DISBURSE ledger entry is written from the treasury to the borrower.
    """
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id, Nation.status == "approved")
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found or not approved.")

    # Auth: caller must be this nation's leader
    if nation.leader_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the nation leader can issue treasury loans.",
        )

    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Loan amount must be greater than zero.")

    borrower = db.execute(
        select(User).where(User.id == payload.borrower_user_id)
    ).scalar_one_or_none()
    if borrower is None:
        raise HTTPException(status_code=404, detail="Borrower not found.")

    if borrower.nation_id != nation_id:
        raise HTTPException(
            status_code=400,
            detail="Borrower must be a member of this nation.",
        )

    # Borrower must have no active loans anywhere (same rule as bank loans)
    active_loan = db.execute(
        select(Loan).where(Loan.borrower_id == borrower.id, Loan.status == "active")
    ).scalar_one_or_none()
    if active_loan is not None:
        raise HTTPException(
            status_code=400,
            detail="Borrower already has an active loan. Must repay before taking a new one.",
        )

    if nation.treasury_balance < payload.amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient treasury balance. "
                f"Available: {nation.treasury_balance}, requested: {payload.amount}."
            ),
        )

    gs = _get_global_settings(db)

    # LOAN_DISBURSE: treasury_address → borrower wallet.
    # create_transaction handles balance updates for NATION_WALLET_PREFIX addresses.
    try:
        tx = create_transaction(
            db,
            tx_type="LOAN_DISBURSE",
            from_address=nation.treasury_address,
            to_address=borrower.wallet_address,
            amount=payload.amount,
            memo=f"Treasury loan from {nation.name}: {payload.memo or 'No memo'}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # bank_id=0 is the sentinel for treasury loans (no bank entity involved).
    now = datetime.now(timezone.utc)
    loan = Loan(
        bank_id=0,
        lender_type="treasury",
        lender_wallet_address=nation.treasury_address,
        treasury_nation_id=nation_id,
        borrower_id=borrower.id,
        principal=payload.amount,
        outstanding=payload.amount,
        accrued_interest=0,
        cap_amount=payload.amount,
        interest_frozen=False,
        last_accrual_at=now,
        interest_rate=gs.interest_rate_cap_bps,
        burn_rate_snapshot=gs.burn_rate_bps,
        interest_burn_rate_snapshot=gs.interest_burn_rate_bps,
        total_interest_paid=0,
        total_burned_during_payments=0,
        final_close_burn=0,
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
            "lender_type": loan.lender_type,
            "treasury_nation_id": loan.treasury_nation_id,
            "principal": loan.principal,
            "outstanding": loan.outstanding,
            "accrued_interest": loan.accrued_interest,
            "cap_amount": loan.cap_amount,
            "interest_frozen": loan.interest_frozen,
            "interest_rate": loan.interest_rate,
            "burn_rate_snapshot": loan.burn_rate_snapshot,
            "status": loan.status,
            "tx_hash": tx.tx_hash,
        },
    }


# ---------------------------------------------------------------------------
# GET /api/nations/{nation_id}/loans — List all treasury-issued loans
# ---------------------------------------------------------------------------
@router.get("/api/nations/{nation_id}/loans")
def list_treasury_loans(
    nation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """List all loans issued by a nation's treasury.

    Requires the nation leader or world_mint.
    """
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    is_leader = nation.leader_id == current_user.id
    is_admin = current_user.role == "world_mint"
    if not (is_leader or is_admin):
        raise HTTPException(status_code=403, detail="Access denied.")

    loans = list(
        db.execute(
            select(Loan).where(
                Loan.treasury_nation_id == nation_id,
                Loan.lender_type == "treasury",
            )
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
            "lender_type": loan.lender_type,
            "lender_wallet_address": loan.lender_wallet_address,
            "treasury_nation_id": loan.treasury_nation_id,
            "principal": loan.principal,
            "outstanding": loan.outstanding,
            "accrued_interest": loan.accrued_interest,
            "total_owed": loan.outstanding + loan.accrued_interest,
            "cap_amount": loan.cap_amount,
            "interest_frozen": loan.interest_frozen,
            "last_accrual_at": loan.last_accrual_at.isoformat() if loan.last_accrual_at else None,
            "interest_rate": loan.interest_rate,
            "burn_rate_snapshot": loan.burn_rate_snapshot,
            "status": loan.status,
            "memo": loan.memo,
            "opened_at": loan.opened_at.isoformat() if loan.opened_at else None,
            "closed_at": loan.closed_at.isoformat() if loan.closed_at else None,
        })

    return {"loans": result, "nation_name": nation.name}


# ---------------------------------------------------------------------------
# POST /api/nations/{nation_id}/loans/{loan_id}/forgive — Forgive a treasury loan
# ---------------------------------------------------------------------------
@router.post("/api/nations/{nation_id}/loans/{loan_id}/forgive")
def forgive_treasury_loan(
    nation_id: int,
    loan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_login),
):
    """Forgive a treasury-issued loan. Only the Nation Leader may do this.

    Zeros the outstanding balance and marks the loan closed.
    Records a LOAN_FORGIVE transaction from the treasury to the borrower wallet
    (amount=0 — no coins move; the entry exists for audit purposes only).
    """
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        raise HTTPException(status_code=404, detail="Nation not found.")

    if nation.leader_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the nation leader can forgive treasury loans.",
        )

    loan = db.execute(
        select(Loan).where(
            Loan.id == loan_id,
            Loan.lender_type == "treasury",
            Loan.treasury_nation_id == nation_id,
        )
    ).scalar_one_or_none()
    if loan is None:
        raise HTTPException(status_code=404, detail="Treasury loan not found.")
    if loan.status != "active":
        raise HTTPException(status_code=400, detail="Loan is not active.")

    forgiven_amount = loan.outstanding
    loan.outstanding = 0
    loan.status = "closed"
    loan.closed_at = datetime.now(timezone.utc)

    borrower = db.execute(
        select(User).where(User.id == loan.borrower_id)
    ).scalar_one_or_none()
    forgive_memo = f"Treasury loan #{loan.id} forgiven by NL ({forgiven_amount} TC outstanding)"
    if borrower is not None:
        try:
            create_transaction(
                db,
                tx_type="LOAN_FORGIVE",
                from_address=nation.treasury_address,
                to_address=borrower.wallet_address,
                amount=0,
                memo=forgive_memo,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Could not record forgiveness on the ledger: {exc}",
            )

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
        # Phase 2C: lender label depends on lender_type — bank loans show
        # the bank name, treasury loans show the lending nation.
        lender_name = "Unknown"
        if loan.lender_type == "bank" and loan.bank_id > 0:
            b = db.execute(select(Bank).where(Bank.id == loan.bank_id)).scalar_one_or_none()
            if b is not None:
                lender_name = b.name
        elif loan.lender_type == "treasury" and loan.treasury_nation_id:
            n = db.execute(
                select(Nation).where(Nation.id == loan.treasury_nation_id)
            ).scalar_one_or_none()
            if n is not None:
                lender_name = f"{n.name} Treasury"
        result.append({
            "id": loan.id,
            "bank_name": lender_name,
            "bank_id": loan.bank_id,
            "lender_type": loan.lender_type,
            "lender_wallet_address": loan.lender_wallet_address,
            "treasury_nation_id": loan.treasury_nation_id,
            "principal": loan.principal,
            "outstanding": loan.outstanding,
            "accrued_interest": loan.accrued_interest,
            "total_owed": loan.outstanding + loan.accrued_interest,
            "cap_amount": loan.cap_amount,
            "interest_frozen": loan.interest_frozen,
            "last_accrual_at": loan.last_accrual_at.isoformat() if loan.last_accrual_at else None,
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
    """Make a payment on a loan with the Phase 2B 20/80 interest-only burn.

    Burn applies to the **interest portion only** — principal repayments are
    never burned.  The total burn pool over a loan's lifetime is
    ``floor(total_interest_paid * burn_rate_snapshot / 10000)`` (10% by default).
    The pool is split:

      - 20% **during payments** — each payment burns
        ``floor(interest_portion * burn_rate * during_split / 10000^2)``
        which equals ``floor(interest_portion * 0.02)`` at default rates.
        Source: borrower wallet → World Mint.
      - 80% **at close** — when the final payment zeroes both
        ``accrued_interest`` and ``outstanding``, the remainder
        (``total_pool − total_burned_during_payments``) is burned from the
        bank's reserves.  Source: bank wallet → World Mint.

    Allocation order (oldest debt first):
      1. ``interest_portion`` — applied to ``loan.accrued_interest``.
      2. ``principal_portion`` — applied to ``loan.outstanding``.

    Up to three ledger transactions per payment:
      1. LOAN_PAYMENT: borrower → bank (``amount − during_payment_burn``).
      2. BURN (during): borrower → World Mint (``during_payment_burn``, if > 0).
      3. BURN (close):  bank → World Mint (``close_burn``, on final payment).

    Updates per-loan analytics: ``total_interest_paid``,
    ``total_burned_during_payments``, ``final_close_burn`` on the closing payment.
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

    # Total amount owed = principal_remaining + accrued_interest_remaining.
    # Cap payment to the total owed (don't overpay).
    total_owed = loan.outstanding + loan.accrued_interest
    if total_owed <= 0:
        # Defensive: loan is active but nothing owed.  Close it and bail.
        loan.status = "closed"
        loan.closed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=400, detail="Loan has no outstanding balance.")

    amount = min(payload.amount, total_owed)

    # Validate: user has sufficient balance
    if current_user.balance < amount:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {current_user.balance}, required: {amount}.",
        )

    # Phase 2C: dispatch on lender_type — bank or treasury.  We resolve a
    # single ``lender_wallet`` (the destination for the LOAN_PAYMENT and the
    # source for the close burn) plus an optional ``bank`` reference for
    # bank-only analytics (total_burned).
    bank = None
    if loan.lender_type == "bank" and loan.bank_id > 0:
        bank = db.execute(select(Bank).where(Bank.id == loan.bank_id)).scalar_one_or_none()
        if bank is None:
            raise HTTPException(status_code=500, detail="Bank not found for this loan.")

    lender_wallet = loan.lender_wallet_address
    if not lender_wallet:
        raise HTTPException(
            status_code=500,
            detail="Loan has no lender wallet address recorded.",
        )

    # ------------------------------------------------------------------
    # Phase 2B: split payment into interest first, then principal.
    # Burn applies **only** to the interest portion.
    # ------------------------------------------------------------------
    interest_portion = min(amount, loan.accrued_interest)
    principal_portion = amount - interest_portion

    # During-payment burn = interest_portion × burn_rate × during_fraction
    # With defaults (burn_rate_snapshot=1000bps, interest_burn_rate_snapshot=8000bps):
    #   = interest_portion × 0.10 × 0.20 = floor(interest_portion × 0.02)
    during_split_bps = 10000 - loan.interest_burn_rate_snapshot
    during_payment_burn = math.floor(
        interest_portion * loan.burn_rate_snapshot * during_split_bps
        / (10000 * 10000)
    )

    # Everything except the during-payment burn flows to the lender
    # (principal is never burned).
    to_lender = amount - during_payment_burn

    # Ledger tx 1: LOAN_PAYMENT — borrower → lender (bank or treasury).
    tx_hash = ""
    if to_lender > 0:
        lender_label = "treasury" if loan.lender_type == "treasury" else "bank"
        try:
            tx = create_transaction(
                db,
                tx_type="LOAN_PAYMENT",
                from_address=current_user.wallet_address,
                to_address=lender_wallet,
                amount=to_lender,
                memo=(
                    f"Loan #{loan.id} {lender_label} payment "
                    f"(interest {interest_portion}, principal {principal_portion})"
                ),
            )
            tx_hash = tx.tx_hash
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # Ledger tx 2: during-payment BURN — borrower → World Mint.
    if during_payment_burn > 0:
        try:
            burn_tx = create_transaction(
                db,
                tx_type="BURN",
                from_address=current_user.wallet_address,
                to_address=settings.WORLD_MINT_ADDRESS,
                amount=during_payment_burn,
                memo=f"Loan #{loan.id} interest burn (20% of pool)",
            )
            if not tx_hash:
                tx_hash = burn_tx.tx_hash
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # Apply allocations and update running totals before close-burn math.
    loan.accrued_interest -= interest_portion
    loan.outstanding -= principal_portion
    loan.total_interest_paid += interest_portion
    loan.total_burned_during_payments += during_payment_burn

    # ------------------------------------------------------------------
    # Final payment: burn the remaining 80% of the pool from the lender's
    # reserves (bank wallet or nation treasury).
    # ------------------------------------------------------------------
    is_final = (loan.accrued_interest == 0 and loan.outstanding == 0)
    close_burn = 0
    if is_final:
        total_burn_pool = math.floor(
            loan.total_interest_paid * loan.burn_rate_snapshot / 10000
        )
        close_burn = max(0, total_burn_pool - loan.total_burned_during_payments)

        if close_burn > 0:
            try:
                create_transaction(
                    db,
                    tx_type="BURN",
                    from_address=lender_wallet,
                    to_address=settings.WORLD_MINT_ADDRESS,
                    amount=close_burn,
                    memo=f"Loan #{loan.id} close burn (80% of pool)",
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

        loan.final_close_burn = close_burn
        loan.status = "closed"
        loan.closed_at = datetime.now(timezone.utc)

    # Bank lifetime burn analytic includes both the borrower-sourced
    # during-payment burn and the bank-sourced close burn.  Treasury loans
    # don't roll up here (no bank entity); per-nation analytics could be
    # added in a later phase if needed.
    if bank is not None:
        bank.total_burned += during_payment_burn + close_burn

    balance_after = loan.outstanding + loan.accrued_interest
    burn_amount = during_payment_burn + close_burn

    # Record the LoanPayment with the per-portion breakdown.
    payment = LoanPayment(
        loan_id=loan.id,
        amount=amount,
        burn_amount=burn_amount,
        bank_amount=to_lender,
        interest_portion=interest_portion,
        principal_portion=principal_portion,
        is_final_payment=is_final,
        balance_after=balance_after,
        tx_hash=tx_hash,
    )
    db.add(payment)
    db.commit()

    return {
        "success": True,
        "payment": {
            "amount": amount,
            "interest_portion": interest_portion,
            "principal_portion": principal_portion,
            "during_payment_burn": during_payment_burn,
            "close_burn": close_burn,
            "burn_amount": burn_amount,
            "bank_amount": to_lender,
            "is_final_payment": is_final,
            "balance_after": balance_after,
            "outstanding_principal": loan.outstanding,
            "remaining_interest": loan.accrued_interest,
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
        "interest_burn_rate_bps": gs.interest_burn_rate_bps,
        "burn_rate_pct": round(gs.burn_rate_bps / 100, 2),
        "interest_rate_cap_pct": round(gs.interest_rate_cap_bps / 100, 2),
        "interest_burn_rate_pct": round(gs.interest_burn_rate_bps / 100, 2),
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
    if payload.interest_burn_rate_bps is not None and not (
        0 <= payload.interest_burn_rate_bps <= 10000
    ):
        raise HTTPException(
            status_code=400,
            detail="Interest burn rate must be between 0 and 10000 basis points.",
        )

    gs = _get_global_settings(db)
    gs.burn_rate_bps = payload.burn_rate_bps
    gs.interest_rate_cap_bps = payload.interest_rate_cap_bps
    if payload.interest_burn_rate_bps is not None:
        gs.interest_burn_rate_bps = payload.interest_burn_rate_bps
    gs.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "burn_rate_bps": gs.burn_rate_bps,
        "interest_rate_cap_bps": gs.interest_rate_cap_bps,
        "interest_burn_rate_bps": gs.interest_burn_rate_bps,
    }
