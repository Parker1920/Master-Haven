"""
Travelers Exchange — Page Routes (HTML Templates)

Serves all user-facing HTML pages via Jinja2 templates.
"""

import math
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
    hash_password,
    require_login,
    require_role,
    verify_password,
)
from app.blockchain import (
    create_transaction,
    get_all_transactions,
    get_transaction_by_hash,
    get_transactions_for_address,
    verify_chain,
)
from app.config import settings
from app.database import get_db
from app.models import (
    Bank,
    GlobalSettings,
    Loan,
    LoanPayment,
    MintAllocation,
    Nation,
    Shop,
    ShopListing,
    Stock,
    StockHolding,
    StockTransaction,
    StockValuation,
    Transaction,
    User,
)
from app.gdp import (
    _calculate_nation_gdp,
    _gather_gdp_maxes,
    format_currency,
    maybe_recalculate_gdp,
    recalculate_all_gdp,
    tc_to_national,
)
from app.valuation import (
    _stock_lock,
    create_business_stock,
    create_nation_stock,
    maybe_recalculate,
    recalculate_all_prices,
)
from app.wallet import generate_nation_treasury_address

router = APIRouter(tags=["pages"])

templates = Jinja2Templates(directory="app/templates")

# ---------------------------------------------------------------------------
# Register custom Jinja2 filters
# ---------------------------------------------------------------------------

def format_number(value):
    """Format an integer with comma separators."""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


templates.env.filters["format_number"] = format_number

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PER_PAGE = 25


def _base_context(request: Request, user: Optional[User], db: Session = None, **kwargs) -> dict:
    """Build the base template context that every page needs.

    Includes the user's nation currency info for balance display conversion.
    """
    # Resolve user's nation for currency context
    user_nation = None
    if user and user.nation_id and db:
        user_nation = db.execute(
            select(Nation).where(Nation.id == user.nation_id)
        ).scalar_one_or_none()

    user_currency = {
        "code": user_nation.currency_code if user_nation and user_nation.currency_code else "TC",
        "name": user_nation.currency_name if user_nation and user_nation.currency_name else "Travelers Coin",
        "gdp": round((user_nation.gdp_multiplier or 100) / 100, 2) if user_nation else 1.0,
        "gdp_multiplier": user_nation.gdp_multiplier if user_nation else 100,
    }

    # Convert user balance to national coin
    user_balance_national = None
    if user and user_nation and user_nation.gdp_multiplier:
        user_balance_national = tc_to_national(user.balance, user_nation.gdp_multiplier)

    ctx = {
        "request": request,
        "user": user,
        "user_nation": user_nation,
        "user_currency": user_currency,
        "user_balance_national": user_balance_national,
        "settings": settings,
        "active_page": kwargs.pop("active_page", ""),
        "tc_to_national": tc_to_national,
    }
    ctx.update(kwargs)
    return ctx


def _paginate(total: int, page: int, per_page: int = PER_PAGE) -> dict:
    """Return pagination metadata."""
    total_pages = max(1, math.ceil(total / per_page))
    page = max(1, min(page, total_pages))
    return {
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "offset": (page - 1) * per_page,
    }


def _build_name_map(db: Session) -> dict:
    """Return a dict mapping wallet/treasury address -> human-readable display name."""
    name_map: dict = {}
    users = db.execute(
        select(User.wallet_address, User.display_name, User.username)
    ).all()
    for wallet_address, display_name, username in users:
        name_map[wallet_address] = display_name or username
    nations = db.execute(
        select(Nation.treasury_address, Nation.name)
    ).all()
    for treasury_address, name in nations:
        name_map[treasury_address] = name
    name_map["SYSTEM"] = "System"
    name_map[settings.WORLD_MINT_ADDRESS] = "World Mint"
    return name_map


# =========================================================================
# PUBLIC PAGES
# =========================================================================

# ---------------------------------------------------------------------------
# GET / — Landing page (public, marketing)
# ---------------------------------------------------------------------------
@router.get("/")
def landing_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Public marketing landing page.

    Logged-in users are redirected to /dashboard — they've already
    onboarded and don't need the marketing pitch on every visit.
    Anonymous users see the full standalone landing template (no
    base.html nav layered on top).
    """
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(
        "landing.html",
        {"request": request},
    )


# ---------------------------------------------------------------------------
# GET /login
# ---------------------------------------------------------------------------
@router.get("/login")
def login_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Don't auto-redirect — let users switch accounts from the login page
    ctx = _base_context(request, user, db=db, active_page="login")
    return templates.TemplateResponse("login.html", ctx)


# ---------------------------------------------------------------------------
# GET /register
# ---------------------------------------------------------------------------
@router.get("/register")
def register_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)
    ctx = _base_context(request, user, db=db, active_page="register")
    return templates.TemplateResponse("register.html", ctx)


# ---------------------------------------------------------------------------
# GET /ledger — Public ledger
# ---------------------------------------------------------------------------
@router.get("/ledger")
def ledger_page(
    request: Request,
    page: int = Query(1, ge=1),
    tx_type: str = Query(""),
    address: str = Query(""),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    valid_types = {"MINT", "DISTRIBUTE", "TRANSFER", "PURCHASE", "BURN", "TAX", "GENESIS", "STOCK_BUY", "STOCK_SELL"}

    conditions = []

    if tx_type and tx_type in valid_types:
        conditions.append(Transaction.tx_type == tx_type)

    if address and address.strip():
        addr = address.strip()
        conditions.append(
            or_(
                Transaction.from_address == addr,
                Transaction.to_address == addr,
            )
        )

    if conditions:
        total = db.execute(
            select(func.count(Transaction.id)).where(*conditions)
        ).scalar() or 0
        pag = _paginate(total, page)
        transactions = list(
            db.execute(
                select(Transaction)
                .where(*conditions)
                .order_by(Transaction.created_at.desc())
                .limit(pag["per_page"])
                .offset(pag["offset"])
            ).scalars().all()
        )
    else:
        transactions, total = get_all_transactions(db, limit=PER_PAGE, offset=(page - 1) * PER_PAGE)
        pag = _paginate(total, page)

    chain_result = verify_chain(db)
    name_map = _build_name_map(db)

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="ledger",
        transactions=transactions,
        name_map=name_map,
        tx_type=tx_type,
        address_filter=address,
        tx_types=sorted(valid_types - {"GENESIS"}),
        chain_valid=chain_result["valid"],
        total_tx_count=total,
        **pag,
    )
    return templates.TemplateResponse("ledger.html", ctx)


# ---------------------------------------------------------------------------
# GET /tx/{tx_hash} — Transaction detail
# ---------------------------------------------------------------------------
@router.get("/tx/{tx_hash}")
def tx_detail_page(
    tx_hash: str,
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Support both full hash and prefix lookups
    if tx_hash.startswith("tx_"):
        prefix = tx_hash[3:]
        tx = db.execute(
            select(Transaction).where(Transaction.tx_hash.startswith(prefix))
        ).scalar_one_or_none()
    else:
        tx = get_transaction_by_hash(db, tx_hash)

    if tx is None:
        return RedirectResponse(url="/ledger?error=Transaction+not+found", status_code=303)

    # Find the next transaction in the chain (if any)
    next_tx = db.execute(
        select(Transaction).where(Transaction.prev_hash == tx.tx_hash)
    ).scalar_one_or_none()

    name_map = _build_name_map(db)
    ctx = _base_context(request, user, db=db, active_page="ledger", tx=tx, next_tx=next_tx, name_map=name_map, block_number=tx.id)
    return templates.TemplateResponse("tx_detail.html", ctx)


# ---------------------------------------------------------------------------
# GET /nations — Nation directory
# ---------------------------------------------------------------------------
@router.get("/nations")
def nations_page(
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nations = list(
        db.execute(
            select(Nation)
            .where(Nation.status == "approved")
            .order_by(Nation.name.asc())
        )
        .scalars()
        .all()
    )

    ctx = _base_context(request, user, db=db, active_page="nations", nations=nations)
    return templates.TemplateResponse("nations.html", ctx)


# ---------------------------------------------------------------------------
# GET /nations/apply — Nation application form
# ---------------------------------------------------------------------------
@router.get("/nations/apply")
def nations_apply_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    # Check if user already leads a nation
    existing_nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id)
    ).scalar_one_or_none()

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="nations",
        existing_nation=existing_nation,
    )
    return templates.TemplateResponse("nations_apply.html", ctx)


# ---------------------------------------------------------------------------
# POST /nations/apply — Process nation application
# ---------------------------------------------------------------------------
@router.post("/nations/apply")
def nations_apply_post(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    game: str = Form(""),
    discord_invite: str = Form(""),
    currency_name: str = Form(""),
    currency_code: str = Form(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    # Validate: user doesn't already lead a nation
    existing_nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id)
    ).scalar_one_or_none()
    if existing_nation is not None:
        return RedirectResponse(
            url="/nations/apply?error=You+already+lead+a+nation",
            status_code=303,
        )

    # Validate: name is unique
    name_taken = db.execute(
        select(Nation).where(Nation.name == name.strip())
    ).scalar_one_or_none()
    if name_taken is not None:
        return RedirectResponse(
            url="/nations/apply?error=A+nation+with+that+name+already+exists",
            status_code=303,
        )

    # Validate currency code if provided
    import re
    cc = currency_code.strip().upper() if currency_code else ""
    cn = currency_name.strip() if currency_name else ""
    if cc:
        if not re.match(r"^[A-Z]{2,5}$", cc):
            return RedirectResponse(
                url="/nations/apply?error=Currency+code+must+be+2-5+uppercase+letters",
                status_code=303,
            )
        code_taken = db.execute(
            select(Nation).where(Nation.currency_code == cc)
        ).scalar_one_or_none()
        if code_taken is not None:
            return RedirectResponse(
                url=f"/nations/apply?error=Currency+code+{cc}+is+already+in+use",
                status_code=303,
            )

    # Create the nation with placeholder address, flush to get ID
    nation = Nation(
        name=name.strip(),
        leader_id=user.id,
        treasury_address="placeholder",
        description=description.strip() or None,
        discord_invite=discord_invite.strip() or None,
        game=game.strip() or None,
        currency_name=cn or None,
        currency_code=cc or None,
        status="pending",
        member_count=0,
    )
    db.add(nation)
    db.flush()

    # Generate real treasury address now that we have the ID
    nation.treasury_address = generate_nation_treasury_address(
        nation.id, settings.SECRET_KEY
    )
    db.commit()

    return RedirectResponse(
        url="/dashboard?success=Nation+application+submitted+successfully",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /nations/{nation_id} — Nation profile
# ---------------------------------------------------------------------------
@router.get("/nations/{nation_id}")
def nation_detail_page(
    nation_id: int,
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(url="/nations?error=Nation+not+found", status_code=303)

    # Get leader name
    leader = db.execute(
        select(User).where(User.id == nation.leader_id)
    ).scalar_one_or_none()
    leader_name = leader.display_name or leader.username if leader else None

    # Get members
    members = list(
        db.execute(
            select(User).where(User.nation_id == nation.id)
        )
        .scalars()
        .all()
    )

    # Determine if the viewing user can join or leave this nation
    can_join = False
    can_leave = False
    is_leader = False
    if user is not None and nation.status == "approved":
        if user.nation_id is None:
            can_join = True
        elif user.nation_id == nation.id and user.id != nation.leader_id:
            can_leave = True
    if user is not None and user.id == nation.leader_id:
        is_leader = True

    # Compute GDP pillar breakdown for audit display
    gdp_breakdown = None
    if nation.status == "approved" and nation.gdp_multiplier:
        try:
            maxes = _gather_gdp_maxes(db)
            gdp_breakdown = _calculate_nation_gdp(db, nation, maxes)
        except Exception:
            pass  # Non-critical — page still renders without breakdown

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="nations",
        nation=nation,
        leader_name=leader_name,
        members=members,
        can_join=can_join,
        can_leave=can_leave,
        is_leader=is_leader,
        gdp_breakdown=gdp_breakdown,
    )
    return templates.TemplateResponse("nation_detail.html", ctx)


# ---------------------------------------------------------------------------
# POST /nations/{nation_id}/join — Join a nation
# ---------------------------------------------------------------------------
@router.post("/nations/{nation_id}/join")
def nation_join_post(
    nation_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/nations?error=Nation+not+found", status_code=303
        )

    if nation.status != "approved":
        return RedirectResponse(
            url=f"/nations/{nation_id}?error=This+nation+is+not+accepting+members",
            status_code=303,
        )

    if user.nation_id is not None:
        return RedirectResponse(
            url=f"/nations/{nation_id}?error=You+are+already+a+member+of+a+nation",
            status_code=303,
        )

    user.nation_id = nation_id
    nation.member_count += 1
    db.commit()

    return RedirectResponse(
        url=f"/nations/{nation_id}?success=You+have+joined+{nation.name.replace(' ', '+')}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# POST /nations/{nation_id}/leave — Leave a nation
# ---------------------------------------------------------------------------
@router.post("/nations/{nation_id}/leave")
def nation_leave_post(
    nation_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=Nation+not+found", status_code=303
        )

    if user.nation_id != nation_id:
        return RedirectResponse(
            url="/dashboard?error=You+are+not+a+member+of+this+nation",
            status_code=303,
        )

    if user.id == nation.leader_id:
        return RedirectResponse(
            url=f"/nations/{nation_id}?error=Nation+leaders+cannot+leave+their+own+nation",
            status_code=303,
        )

    user.nation_id = None
    nation.member_count -= 1
    db.commit()

    return RedirectResponse(
        url="/dashboard?success=You+have+left+the+nation",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# POST /nations/{nation_id}/edit-description — Leader edits nation description
# ---------------------------------------------------------------------------
@router.post("/nations/{nation_id}/edit-description")
def nation_edit_description_post(
    nation_id: int,
    request: Request,
    description: str = Form(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(url="/nations?error=Nation+not+found", status_code=303)

    if user.id != nation.leader_id:
        return RedirectResponse(
            url=f"/nations/{nation_id}?error=Only+the+nation+leader+can+edit+the+description",
            status_code=303,
        )

    nation.description = description.strip()
    db.commit()

    return RedirectResponse(
        url=f"/nations/{nation_id}?success=Description+updated",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /nation/settings — Nation leader's identity-edit page
# ---------------------------------------------------------------------------
@router.get("/nation/settings")
def nation_settings_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Form letting a nation leader rename their own nation and update its
    currency display fields. World Mint admin has the same capability via
    /mint/nations/{id}/edit-identity for any nation; this page is the
    self-service equivalent for the leader of a single nation.
    """
    if user.role != "nation_leader":
        return RedirectResponse(
            url="/dashboard?error=You+must+be+a+nation+leader+to+edit+nation+settings",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=No+approved+nation+found+for+your+account",
            status_code=303,
        )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="nation",
        nation=nation,
    )
    return templates.TemplateResponse("nation/settings.html", ctx)


# ---------------------------------------------------------------------------
# POST /nation/settings — Save nation identity edits (self-edit)
# ---------------------------------------------------------------------------
@router.post("/nation/settings")
def nation_settings_post(
    request: Request,
    name: str = Form(...),
    currency_name: str = Form(""),
    currency_code: str = Form(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Process the identity-edit form. Same validation rules as the World
    Mint admin equivalent: name required and unique across nations,
    currency code 2-8 chars and auto-uppercased, blank currency fields
    stored as NULL.
    """
    if user.role != "nation_leader":
        return RedirectResponse(
            url="/dashboard?error=You+must+be+a+nation+leader+to+edit+nation+settings",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=No+approved+nation+found+for+your+account",
            status_code=303,
        )

    new_name = (name or "").strip()
    new_currency_name = (currency_name or "").strip() or None
    new_currency_code = (currency_code or "").strip().upper() or None

    if not new_name:
        return RedirectResponse(
            url="/nation/settings?error=Name+is+required",
            status_code=303,
        )

    # Uniqueness guard if the name actually changed.
    if new_name != nation.name:
        clash = db.execute(
            select(Nation).where(Nation.name == new_name, Nation.id != nation.id)
        ).scalar_one_or_none()
        if clash is not None:
            return RedirectResponse(
                url="/nation/settings?error=Nation+name+already+taken",
                status_code=303,
            )

    # Sanity bounds on the currency code (used as a short tag in tables).
    if new_currency_code and (len(new_currency_code) > 8 or len(new_currency_code) < 2):
        return RedirectResponse(
            url="/nation/settings?error=Currency+code+must+be+2-8+characters",
            status_code=303,
        )

    # If the new currency_code would collide with another stock's ticker,
    # reject before any writes — keeps stocks.ticker globally unique.
    if new_currency_code:
        ticker_clash = db.execute(
            select(Stock).where(
                Stock.ticker == new_currency_code,
                ~((Stock.stock_type == "nation") & (Stock.entity_id == nation.id)),
            )
        ).scalar_one_or_none()
        if ticker_clash is not None:
            return RedirectResponse(
                url=(
                    "/nation/settings?error=Ticker+"
                    + new_currency_code
                    + "+already+in+use+by+another+stock"
                ),
                status_code=303,
            )

    nation.name = new_name
    nation.currency_name = new_currency_name
    nation.currency_code = new_currency_code

    # Keep the matching nation Stock row in sync — `stocks.name` and
    # `stocks.ticker` are denormalised copies that the exchange page reads
    # directly, so they have to be updated whenever nation identity changes.
    nation_stock = db.execute(
        select(Stock).where(
            Stock.stock_type == "nation",
            Stock.entity_id == nation.id,
        )
    ).scalar_one_or_none()
    if nation_stock is not None:
        nation_stock.name = new_name
        # Use the configured currency_code as the ticker.  If it's blank,
        # regenerate from the new name.
        if new_currency_code:
            nation_stock.ticker = new_currency_code
        else:
            from app.valuation import generate_ticker
            nation_stock.ticker = generate_ticker(new_name, db)

    db.commit()

    return RedirectResponse(
        url="/nation/settings?success=Nation+settings+updated",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /nation/treasury — Nation leader treasury dashboard
# ---------------------------------------------------------------------------
@router.get("/nation/treasury")
def nation_treasury_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.role != "nation_leader":
        return RedirectResponse(
            url="/dashboard?error=You+must+be+a+nation+leader+to+access+the+treasury",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=No+approved+nation+found",
            status_code=303,
        )

    # Recent DISTRIBUTE transactions from this treasury (last 20)
    recent_distributions = get_transactions_for_address(
        db, nation.treasury_address, limit=20, offset=0
    )

    # Allocation history for this nation
    allocations = list(
        db.execute(
            select(MintAllocation)
            .where(MintAllocation.nation_id == nation.id)
            .order_by(MintAllocation.created_at.desc())
        )
        .scalars()
        .all()
    )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="treasury",
        nation=nation,
        recent_distributions=recent_distributions,
        allocations=allocations,
    )
    return templates.TemplateResponse("nation/treasury.html", ctx)


# ---------------------------------------------------------------------------
# GET /nation/distribute — Distribution form
# ---------------------------------------------------------------------------
@router.get("/nation/distribute")
def nation_distribute_page(
    request: Request,
    to: str = Query(None),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.role != "nation_leader":
        return RedirectResponse(
            url="/dashboard?error=You+must+be+a+nation+leader+to+distribute+funds",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=No+approved+nation+found",
            status_code=303,
        )

    # Get all nation members for the dropdown
    members = list(
        db.execute(
            select(User).where(User.nation_id == nation.id)
        )
        .scalars()
        .all()
    )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="treasury",
        nation=nation,
        members=members,
        prefill_address=to,
    )
    return templates.TemplateResponse("nation/distribute.html", ctx)


# ---------------------------------------------------------------------------
# POST /nation/distribute — Process single distribution
# ---------------------------------------------------------------------------
@router.post("/nation/distribute")
def nation_distribute_post(
    request: Request,
    to_address: str = Form(...),
    amount: int = Form(...),
    memo: str = Form(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.role != "nation_leader":
        return RedirectResponse(
            url="/dashboard?error=You+must+be+a+nation+leader",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=No+approved+nation+found",
            status_code=303,
        )

    try:
        create_transaction(
            db,
            tx_type="DISTRIBUTE",
            from_address=nation.treasury_address,
            to_address=to_address.strip(),
            amount=amount,
            memo=memo.strip() or None,
        )
        return RedirectResponse(
            url=f"/nation/treasury?success=Distributed+{amount}+{settings.CURRENCY_SHORT}+successfully",
            status_code=303,
        )
    except ValueError as exc:
        error_msg = str(exc).replace(" ", "+")
        return RedirectResponse(
            url=f"/nation/distribute?error={error_msg}",
            status_code=303,
        )


# ---------------------------------------------------------------------------
# POST /nation/distribute-bulk — Process bulk distribution
# ---------------------------------------------------------------------------
@router.post("/nation/distribute-bulk")
def nation_distribute_bulk_post(
    request: Request,
    amount_per_member: int = Form(...),
    memo: str = Form(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.role != "nation_leader":
        return RedirectResponse(
            url="/dashboard?error=You+must+be+a+nation+leader",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=No+approved+nation+found",
            status_code=303,
        )

    # Get all members
    members = list(
        db.execute(
            select(User).where(User.nation_id == nation.id)
        )
        .scalars()
        .all()
    )

    if not members:
        return RedirectResponse(
            url="/nation/distribute?error=No+members+to+distribute+to",
            status_code=303,
        )

    total_needed = amount_per_member * len(members)
    if nation.treasury_balance < total_needed:
        return RedirectResponse(
            url=f"/nation/distribute?error=Insufficient+treasury+balance.+Need+{total_needed}+but+have+{nation.treasury_balance}",
            status_code=303,
        )

    distributed_count = 0
    try:
        for member in members:
            create_transaction(
                db,
                tx_type="DISTRIBUTE",
                from_address=nation.treasury_address,
                to_address=member.wallet_address,
                amount=amount_per_member,
                memo=memo.strip() or None,
            )
            distributed_count += 1
    except ValueError as exc:
        error_msg = str(exc).replace(" ", "+")
        return RedirectResponse(
            url=f"/nation/treasury?error=Bulk+distribution+failed+after+{distributed_count}+transfers:+{error_msg}",
            status_code=303,
        )

    total_distributed = amount_per_member * distributed_count
    return RedirectResponse(
        url=f"/nation/treasury?success=Distributed+{total_distributed}+{settings.CURRENCY_SHORT}+to+{distributed_count}+members",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /nation/members — Member management page
# ---------------------------------------------------------------------------
@router.get("/nation/members")
def nation_members_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.role != "nation_leader":
        return RedirectResponse(
            url="/dashboard?error=You+must+be+a+nation+leader",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=No+approved+nation+found",
            status_code=303,
        )

    members = list(
        db.execute(
            select(User).where(User.nation_id == nation.id)
        )
        .scalars()
        .all()
    )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="members",
        nation=nation,
        members=members,
    )
    return templates.TemplateResponse("nation/members.html", ctx)


# ---------------------------------------------------------------------------
# GET /market — Marketplace browse
# ---------------------------------------------------------------------------
@router.get("/market")
def market_page(
    request: Request,
    page: int = Query(1, ge=1),
    nation_id: int = Query(None),
    category: str = Query(""),
    min_price: int = Query(None),
    max_price: int = Query(None),
    q: str = Query(""),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = [Shop.is_active == True, ShopListing.is_available == True]  # noqa: E712
    if nation_id is not None:
        conditions.append(Shop.nation_id == nation_id)
    if category:
        conditions.append(ShopListing.category == category)
    if min_price is not None:
        conditions.append(ShopListing.price >= min_price)
    if max_price is not None:
        conditions.append(ShopListing.price <= max_price)
    if q.strip():
        conditions.append(ShopListing.title.ilike(f"%{q.strip()}%"))

    total = (
        db.execute(
            select(func.count(ShopListing.id))
            .join(Shop, ShopListing.shop_id == Shop.id)
            .where(*conditions)
        ).scalar()
        or 0
    )
    pag = _paginate(total, page)

    rows = list(
        db.execute(
            select(ShopListing, Shop)
            .join(Shop, ShopListing.shop_id == Shop.id)
            .where(*conditions)
            .order_by(ShopListing.created_at.desc())
            .limit(pag["per_page"])
            .offset(pag["offset"])
        ).all()
    )

    nations_list = list(
        db.execute(
            select(Nation)
            .where(Nation.status == "approved")
            .order_by(Nation.name)
        ).scalars().all()
    )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="market",
        listings=rows,
        nations=nations_list,
        nation_id=nation_id,
        category=category,
        min_price=min_price,
        max_price=max_price,
        q=q,
        **pag,
    )
    return templates.TemplateResponse("market.html", ctx)


# ---------------------------------------------------------------------------
# GET /market/{shop_id} — Shop detail
# ---------------------------------------------------------------------------
@router.get("/market/{shop_id}")
def market_shop_page(
    shop_id: int,
    request: Request,
    error: str = Query(""),
    success: str = Query(""),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None or not shop.is_active:
        return RedirectResponse(url="/market?error=Shop+not+found", status_code=303)

    listings = list(
        db.execute(
            select(ShopListing)
            .where(ShopListing.shop_id == shop.id, ShopListing.is_available == True)  # noqa: E712
            .order_by(ShopListing.created_at.desc())
        ).scalars().all()
    )

    owner = db.execute(select(User).where(User.id == shop.owner_id)).scalar_one_or_none()
    owner_name = owner.display_name or owner.username if owner else "Unknown"
    nation = db.execute(select(Nation).where(Nation.id == shop.nation_id)).scalar_one_or_none()
    is_owner = user is not None and user.id == shop.owner_id

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="market",
        shop=shop,
        listings=listings,
        owner_name=owner_name,
        nation=nation,
        is_owner=is_owner,
        flash_error=error if error else None,
        flash_success=success if success else None,
    )
    return templates.TemplateResponse("market_shop.html", ctx)


# ---------------------------------------------------------------------------
# GET /market/{shop_id}/buy/{listing_id} — Purchase confirmation
# ---------------------------------------------------------------------------
@router.get("/market/{shop_id}/buy/{listing_id}")
def market_buy_page(
    shop_id: int,
    listing_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None or not shop.is_active:
        return RedirectResponse(url="/market?error=Shop+not+found", status_code=303)

    listing = db.execute(select(ShopListing).where(ShopListing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.shop_id != shop.id or not listing.is_available:
        return RedirectResponse(url=f"/market/{shop_id}?error=Listing+not+found", status_code=303)

    if user.id == shop.owner_id:
        return RedirectResponse(url=f"/market/{shop_id}?error=Cannot+buy+from+your+own+shop", status_code=303)

    owner = db.execute(select(User).where(User.id == shop.owner_id)).scalar_one_or_none()
    owner_name = owner.display_name or owner.username if owner else "Unknown"

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="market",
        shop=shop,
        listing=listing,
        owner_name=owner_name,
        balance_after=user.balance - listing.price,
    )
    return templates.TemplateResponse("market_buy.html", ctx)


# ---------------------------------------------------------------------------
# POST /market/{shop_id}/buy/{listing_id} — Execute purchase
# ---------------------------------------------------------------------------
@router.post("/market/{shop_id}/buy/{listing_id}")
def market_buy_post(
    shop_id: int,
    listing_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(Shop).where(Shop.id == shop_id)).scalar_one_or_none()
    if shop is None or not shop.is_active:
        return RedirectResponse(url="/market?error=Shop+not+found", status_code=303)

    listing = db.execute(select(ShopListing).where(ShopListing.id == listing_id)).scalar_one_or_none()
    if listing is None or listing.shop_id != shop.id or not listing.is_available:
        return RedirectResponse(url=f"/market/{shop_id}?error=Listing+not+available", status_code=303)

    if user.id == shop.owner_id:
        return RedirectResponse(url=f"/market/{shop_id}?error=Cannot+buy+from+your+own+shop", status_code=303)

    owner = db.execute(select(User).where(User.id == shop.owner_id)).scalar_one_or_none()
    if owner is None:
        return RedirectResponse(url=f"/market/{shop_id}?error=Shop+owner+not+found", status_code=303)

    try:
        create_transaction(
            db,
            tx_type="PURCHASE",
            from_address=user.wallet_address,
            to_address=owner.wallet_address,
            amount=listing.price,
            memo=f"Purchase: {listing.title} from {shop.name}",
        )
    except ValueError as exc:
        error_msg = str(exc).replace(" ", "+")
        return RedirectResponse(url=f"/market/{shop_id}?error={error_msg}", status_code=303)

    shop.total_sales += 1
    shop.total_revenue += listing.price
    db.commit()

    return RedirectResponse(
        url=f"/market/{shop_id}?success=Purchase+successful!+{listing.price}+{settings.CURRENCY_SHORT}+sent",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /wallet/search — Wallet search page
# ---------------------------------------------------------------------------
@router.get("/wallet/search")
def wallet_search_page(
    request: Request,
    q: str = Query(""),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = []
    if q.strip():
        search_q = q.strip()
        users = list(
            db.execute(
                select(User).where(
                    or_(
                        User.username.ilike(f"{search_q}%"),
                        User.display_name.ilike(f"{search_q}%"),
                        User.wallet_address.ilike(f"{search_q}%"),
                    )
                ).limit(20)
            ).scalars().all()
        )
        for u in users:
            results.append({
                "address": u.wallet_address,
                "display_name": u.display_name or u.username,
                "username": u.username,
                "type": "user",
                "balance": u.balance,
            })
        nations = list(
            db.execute(
                select(Nation).where(
                    or_(
                        Nation.name.ilike(f"{search_q}%"),
                        Nation.treasury_address.ilike(f"{search_q}%"),
                    ),
                    Nation.status == "approved",
                ).limit(10)
            ).scalars().all()
        )
        for n in nations:
            results.append({
                "address": n.treasury_address,
                "display_name": n.name,
                "username": None,
                "type": "nation_treasury",
                "balance": n.treasury_balance,
                "nation_id": n.id,
            })

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="",
        q=q,
        results=results,
    )
    return templates.TemplateResponse("wallet_search.html", ctx)


# ---------------------------------------------------------------------------
# GET /wallet/{address} — Public wallet lookup
# ---------------------------------------------------------------------------
@router.get("/wallet/{address}")
def wallet_lookup_page(
    address: str,
    request: Request,
    page: int = Query(1, ge=1),
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner_name = None
    nation_name = None
    nation_id = None
    wallet_type = "user"
    balance = 0

    if address.startswith(settings.NATION_WALLET_PREFIX):
        nation = db.execute(
            select(Nation).where(Nation.treasury_address == address)
        ).scalar_one_or_none()
        if nation is None:
            return RedirectResponse(url="/ledger?error=Wallet+not+found", status_code=303)
        balance = nation.treasury_balance
        owner_name = nation.name
        wallet_type = "nation_treasury"
        nation_id = nation.id
    else:
        wallet_user = db.execute(
            select(User).where(User.wallet_address == address)
        ).scalar_one_or_none()
        if wallet_user is None:
            return RedirectResponse(url="/ledger?error=Wallet+not+found", status_code=303)
        balance = wallet_user.balance
        owner_name = wallet_user.display_name or wallet_user.username
        if wallet_user.nation_id:
            nation_obj = db.execute(
                select(Nation).where(Nation.id == wallet_user.nation_id)
            ).scalar_one_or_none()
            if nation_obj:
                nation_name = nation_obj.name

    # Get transactions for this address
    # Count total for pagination
    total_count = (
        db.execute(
            select(func.count(Transaction.id)).where(
                or_(
                    Transaction.from_address == address,
                    Transaction.to_address == address,
                )
            )
        ).scalar()
        or 0
    )

    pag = _paginate(total_count, page)
    transactions = get_transactions_for_address(
        db, address, limit=pag["per_page"], offset=pag["offset"]
    )

    name_map = _build_name_map(db)
    can_send = user is not None and address != getattr(user, 'wallet_address', None)

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="",
        address=address,
        balance=balance,
        owner_name=owner_name,
        nation_name=nation_name,
        wallet_type=wallet_type,
        transactions=transactions,
        name_map=name_map,
        can_send=can_send,
        nation_id=nation_id,
        **pag,
    )
    return templates.TemplateResponse("wallet_lookup.html", ctx)


# =========================================================================
# AUTHENTICATED PAGES
# =========================================================================

# ---------------------------------------------------------------------------
# GET /dashboard
# ---------------------------------------------------------------------------
@router.get("/dashboard")
def dashboard_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    # Get nation info
    nation = None
    if user.nation_id:
        nation = db.execute(
            select(Nation).where(Nation.id == user.nation_id)
        ).scalar_one_or_none()

    # Check if user is a nation leader
    led_nation = None
    if user.role == "nation_leader":
        led_nation = db.execute(
            select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
        ).scalar_one_or_none()

    # Check for pending nation application
    pending_nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "pending")
    ).scalar_one_or_none()

    # Recent transactions (last 10)
    recent_transactions = get_transactions_for_address(
        db, user.wallet_address, limit=10, offset=0
    )

    name_map = _build_name_map(db)

    # Check if user has a shop
    user_shop = db.execute(select(Shop).where(Shop.owner_id == user.id)).scalar_one_or_none()

    # Portfolio stats
    portfolio_holdings = list(
        db.execute(
            select(StockHolding).where(StockHolding.user_id == user.id)
        ).scalars().all()
    )
    portfolio_value = 0
    portfolio_invested = 0
    for h in portfolio_holdings:
        stk = db.execute(select(Stock).where(Stock.id == h.stock_id)).scalar_one_or_none()
        if stk:
            portfolio_value += h.shares * stk.current_price
            portfolio_invested += h.shares * h.avg_buy_price

    portfolio_stats = None
    if portfolio_holdings:
        portfolio_stats = {
            "total_value": portfolio_value,
            "total_invested": portfolio_invested,
            "gain_loss": portfolio_value - portfolio_invested,
            "stock_count": len(portfolio_holdings),
        }

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="dashboard",
        nation=nation,
        led_nation=led_nation,
        pending_nation=pending_nation,
        recent_transactions=recent_transactions,
        name_map=name_map,
        user_shop=user_shop,
        portfolio_stats=portfolio_stats,
    )
    return templates.TemplateResponse("dashboard.html", ctx)


# ---------------------------------------------------------------------------
# GET /send
# ---------------------------------------------------------------------------
@router.get("/send")
def send_page(
    request: Request,
    to: str = Query(None),
    error: str = Query(None),
    success: str = Query(None),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="send",
        prefill_address=to,
        flash_error=error,
        flash_success=success,
    )
    return templates.TemplateResponse("send.html", ctx)


# ---------------------------------------------------------------------------
# POST /send — Process transfer form
# ---------------------------------------------------------------------------
@router.post("/send")
def send_post(
    request: Request,
    to_address: str = Form(...),
    amount: int = Form(...),
    memo: str = Form(None),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    try:
        create_transaction(
            db,
            tx_type="TRANSFER",
            from_address=user.wallet_address,
            to_address=to_address.strip(),
            amount=amount,
            memo=memo or None,
        )
        return RedirectResponse(
            url="/dashboard?success=Transfer+sent+successfully",
            status_code=303,
        )
    except ValueError as exc:
        error_msg = str(exc).replace(" ", "+")
        return RedirectResponse(
            url=f"/send?error={error_msg}",
            status_code=303,
        )


# ---------------------------------------------------------------------------
# GET /history — Full transaction history
# ---------------------------------------------------------------------------
@router.get("/history")
def history_page(
    request: Request,
    page: int = Query(1, ge=1),
    tx_type: str = Query(""),
    direction: str = Query(""),
    date_from: str = Query(""),
    date_to: str = Query(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    from datetime import datetime as dt, timedelta

    valid_types = {"MINT", "DISTRIBUTE", "TRANSFER", "PURCHASE", "BURN", "TAX", "GENESIS", "STOCK_BUY", "STOCK_SELL"}

    # Build filter conditions
    conditions = []

    if direction == "sent":
        conditions.append(Transaction.from_address == user.wallet_address)
    elif direction == "received":
        conditions.append(Transaction.to_address == user.wallet_address)
    else:
        conditions.append(
            or_(
                Transaction.from_address == user.wallet_address,
                Transaction.to_address == user.wallet_address,
            )
        )

    if tx_type and tx_type in valid_types:
        conditions.append(Transaction.tx_type == tx_type)

    if date_from:
        try:
            df = dt.strptime(date_from, "%Y-%m-%d")
            conditions.append(Transaction.created_at >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt_end = dt.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            conditions.append(Transaction.created_at < dt_end)
        except ValueError:
            pass

    # Count
    total_count = (
        db.execute(
            select(func.count(Transaction.id)).where(*conditions)
        ).scalar()
        or 0
    )

    pag = _paginate(total_count, page)
    transactions = list(
        db.execute(
            select(Transaction)
            .where(*conditions)
            .order_by(Transaction.created_at.desc())
            .limit(pag["per_page"])
            .offset(pag["offset"])
        ).scalars().all()
    )

    name_map = _build_name_map(db)

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="history",
        transactions=transactions,
        name_map=name_map,
        tx_type=tx_type,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        tx_types=sorted(valid_types - {"GENESIS"}),
        **pag,
    )
    return templates.TemplateResponse("history.html", ctx)


# ---------------------------------------------------------------------------
# GET /shop/manage — Shop management dashboard
# ---------------------------------------------------------------------------
@router.get("/shop/manage")
def shop_manage_page(
    request: Request,
    success: str = Query(""),
    error: str = Query(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(Shop).where(Shop.owner_id == user.id)).scalar_one_or_none()

    listings = []
    unique_customers = 0
    recent_sales = []
    name_map = {}

    if shop is not None:
        listings = list(
            db.execute(
                select(ShopListing)
                .where(ShopListing.shop_id == shop.id)
                .order_by(ShopListing.created_at.desc())
            ).scalars().all()
        )

        from sqlalchemy import distinct
        unique_customers = (
            db.execute(
                select(func.count(distinct(Transaction.from_address))).where(
                    Transaction.to_address == user.wallet_address,
                    Transaction.tx_type == "PURCHASE",
                )
            ).scalar()
            or 0
        )

        recent_sales = list(
            db.execute(
                select(Transaction)
                .where(
                    Transaction.to_address == user.wallet_address,
                    Transaction.tx_type == "PURCHASE",
                )
                .order_by(Transaction.created_at.desc())
                .limit(10)
            ).scalars().all()
        )

        name_map = _build_name_map(db)

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="shop",
        shop=shop,
        listings=listings,
        unique_customers=unique_customers,
        recent_sales=recent_sales,
        name_map=name_map,
        flash_error=error if error else None,
        flash_success=success if success else None,
    )
    return templates.TemplateResponse("shop_manage.html", ctx)


# ---------------------------------------------------------------------------
# GET /shop/create — Shop creation form
# ---------------------------------------------------------------------------
@router.get("/shop/create")
def shop_create_page(
    request: Request,
    error: str = Query(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.nation_id is None:
        return RedirectResponse(url="/shop/manage?error=You+must+join+a+nation+first", status_code=303)

    nation = db.execute(select(Nation).where(Nation.id == user.nation_id)).scalar_one_or_none()
    if nation is None or nation.status != "approved":
        return RedirectResponse(url="/shop/manage?error=Your+nation+must+be+approved", status_code=303)

    existing = db.execute(select(Shop).where(Shop.owner_id == user.id)).scalar_one_or_none()
    if existing is not None:
        return RedirectResponse(url="/shop/manage", status_code=303)

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="shop",
        nation_name=nation.name,
        flash_error=error if error else None,
    )
    return templates.TemplateResponse("shop_create.html", ctx)


# ---------------------------------------------------------------------------
# POST /shop/create — Process shop creation
# ---------------------------------------------------------------------------
@router.post("/shop/create")
def shop_create_post(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    if user.nation_id is None:
        return RedirectResponse(url="/shop/manage?error=You+must+join+a+nation+first", status_code=303)

    nation = db.execute(select(Nation).where(Nation.id == user.nation_id)).scalar_one_or_none()
    if nation is None or nation.status != "approved":
        return RedirectResponse(url="/shop/manage?error=Your+nation+must+be+approved", status_code=303)

    existing = db.execute(select(Shop).where(Shop.owner_id == user.id)).scalar_one_or_none()
    if existing is not None:
        return RedirectResponse(url="/shop/manage?error=You+already+own+a+shop", status_code=303)

    shop_name = name.strip()
    if not shop_name:
        return RedirectResponse(url="/shop/create?error=Shop+name+cannot+be+empty", status_code=303)

    shop = Shop(
        owner_id=user.id,
        nation_id=user.nation_id,
        name=shop_name,
        description=description.strip() or None,
    )
    db.add(shop)
    db.commit()

    return RedirectResponse(url="/shop/manage?success=Shop+created+successfully", status_code=303)


# ---------------------------------------------------------------------------
# POST /shop/listings/create — Create a listing
# ---------------------------------------------------------------------------
@router.post("/shop/listings/create")
def shop_listing_create_post(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    price: int = Form(...),
    category: str = Form("other"),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(Shop).where(Shop.owner_id == user.id)).scalar_one_or_none()
    if shop is None:
        return RedirectResponse(url="/shop/manage?error=You+don't+have+a+shop", status_code=303)

    valid_categories = {"service", "coordinates", "item", "other"}
    if category not in valid_categories:
        return RedirectResponse(url="/shop/manage?error=Invalid+category", status_code=303)

    if price <= 0:
        return RedirectResponse(url="/shop/manage?error=Price+must+be+greater+than+0", status_code=303)

    listing_title = title.strip()
    if not listing_title:
        return RedirectResponse(url="/shop/manage?error=Title+cannot+be+empty", status_code=303)

    listing = ShopListing(
        shop_id=shop.id,
        title=listing_title,
        description=description.strip() or None,
        price=price,
        category=category,
    )
    db.add(listing)
    db.commit()

    return RedirectResponse(url="/shop/manage?success=Listing+created", status_code=303)


# ---------------------------------------------------------------------------
# POST /shop/listings/{listing_id}/toggle — Toggle listing availability
# ---------------------------------------------------------------------------
@router.post("/shop/listings/{listing_id}/toggle")
def shop_listing_toggle_post(
    listing_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    listing = db.execute(select(ShopListing).where(ShopListing.id == listing_id)).scalar_one_or_none()
    if listing is None:
        return RedirectResponse(url="/shop/manage?error=Listing+not+found", status_code=303)

    shop = db.execute(select(Shop).where(Shop.id == listing.shop_id)).scalar_one_or_none()
    if shop is None or shop.owner_id != user.id:
        return RedirectResponse(url="/shop/manage?error=Unauthorized", status_code=303)

    listing.is_available = not listing.is_available
    db.commit()

    status = "activated" if listing.is_available else "deactivated"
    return RedirectResponse(url=f"/shop/manage?success=Listing+{status}", status_code=303)


# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------
@router.get("/settings")
def settings_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    nation = None
    if user.nation_id:
        nation = db.execute(
            select(Nation).where(Nation.id == user.nation_id)
        ).scalar_one_or_none()

    ctx = _base_context(request, user, db=db, active_page="settings", nation=nation)
    return templates.TemplateResponse("settings.html", ctx)


# ---------------------------------------------------------------------------
# POST /settings/password — Change password
# ---------------------------------------------------------------------------
@router.post("/settings/password")
def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_new_password: str = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    # Validate old password
    if not verify_password(old_password, user.password_hash):
        return RedirectResponse(
            url="/settings?error=Current+password+is+incorrect",
            status_code=303,
        )

    # Validate new password
    if len(new_password) < 8:
        return RedirectResponse(
            url="/settings?error=New+password+must+be+at+least+8+characters",
            status_code=303,
        )

    if new_password != confirm_new_password:
        return RedirectResponse(
            url="/settings?error=New+passwords+do+not+match",
            status_code=303,
        )

    # Update password
    user.password_hash = hash_password(new_password)
    db.commit()

    return RedirectResponse(
        url="/settings?success=Password+changed+successfully",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# POST /settings/display-name — Change display name
# ---------------------------------------------------------------------------
@router.post("/settings/display-name")
def change_display_name(
    request: Request,
    display_name: str = Form(""),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    user.display_name = display_name.strip() or None
    db.commit()

    return RedirectResponse(
        url="/settings?success=Display+name+updated",
        status_code=303,
    )


# =========================================================================
# WORLD MINT PAGES
# =========================================================================

_require_world_mint = require_role("world_mint")

# ---------------------------------------------------------------------------
# GET /mint — Mint dashboard
# ---------------------------------------------------------------------------
@router.get("/mint")
def mint_dashboard_page(
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    # Stats
    total_user_balances = (
        db.execute(
            select(func.coalesce(func.sum(User.balance), 0)).where(
                User.role != "world_mint"
            )
        ).scalar()
        or 0
    )
    total_nation_balances = (
        db.execute(
            select(func.coalesce(func.sum(Nation.treasury_balance), 0))
        ).scalar()
        or 0
    )
    total_supply = total_user_balances + total_nation_balances

    total_transactions = (
        db.execute(select(func.count(Transaction.id))).scalar() or 0
    )
    total_users = (
        db.execute(
            select(func.count(User.id)).where(User.role != "world_mint")
        ).scalar()
        or 0
    )
    total_nations = (
        db.execute(
            select(func.count(Nation.id)).where(Nation.status == "approved")
        ).scalar()
        or 0
    )

    from datetime import datetime, timedelta, timezone
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    active_users_30d = (
        db.execute(
            select(func.count(User.id)).where(User.last_active >= thirty_days_ago)
        ).scalar()
        or 0
    )

    chain_result = verify_chain(db)
    chain_valid = chain_result["valid"]

    # Recent MINT transactions (last 10)
    recent_mints = list(
        db.execute(
            select(Transaction)
            .where(Transaction.tx_type == "MINT")
            .order_by(Transaction.created_at.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )

    # Pending nations for approval
    pending_nations = list(
        db.execute(
            select(Nation)
            .where(Nation.status == "pending")
            .order_by(Nation.created_at.desc())
        )
        .scalars()
        .all()
    )

    # Pending allocations (awaiting approval)
    pending_allocations = list(
        db.execute(
            select(MintAllocation, Nation.name.label("nation_name"))
            .join(Nation, MintAllocation.nation_id == Nation.id)
            .where(MintAllocation.status == "pending")
            .order_by(MintAllocation.created_at.desc())
        )
        .all()
    )

    # Approved allocations (ready to execute)
    approved_allocations = list(
        db.execute(
            select(MintAllocation, Nation.name.label("nation_name"))
            .join(Nation, MintAllocation.nation_id == Nation.id)
            .where(MintAllocation.status == "approved")
            .order_by(MintAllocation.created_at.desc())
        )
        .all()
    )

    # Recently distributed allocations (last 10)
    recent_allocations = list(
        db.execute(
            select(MintAllocation, Nation.name.label("nation_name"))
            .join(Nation, MintAllocation.nation_id == Nation.id)
            .where(MintAllocation.status == "distributed")
            .order_by(MintAllocation.distributed_at.desc())
            .limit(10)
        )
        .all()
    )

    # GDP nations for overview
    gdp_nations = list(
        db.execute(
            select(Nation)
            .where(Nation.status == "approved")
            .order_by(Nation.name)
        )
        .scalars()
        .all()
    )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="mint",
        total_supply=total_supply,
        total_transactions=total_transactions,
        total_users=total_users,
        total_nations=total_nations,
        active_users_30d=active_users_30d,
        chain_valid=chain_valid,
        recent_mints=recent_mints,
        pending_nations=pending_nations,
        pending_allocations=pending_allocations,
        approved_allocations=approved_allocations,
        recent_allocations=recent_allocations,
        gdp_nations=gdp_nations,
    )
    return templates.TemplateResponse("mint/dashboard.html", ctx)


# ---------------------------------------------------------------------------
# GET /mint/stats — Detailed economy statistics
# ---------------------------------------------------------------------------
@router.get("/mint/stats")
def mint_stats_page(
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    # Chain verification
    chain_result = verify_chain(db)
    chain_valid = chain_result["valid"]
    chain_errors = len(chain_result["errors"])

    total_transactions = (
        db.execute(select(func.count(Transaction.id))).scalar() or 0
    )

    # Supply
    total_user_balances = (
        db.execute(
            select(func.coalesce(func.sum(User.balance), 0)).where(
                User.role != "world_mint"
            )
        ).scalar()
        or 0
    )
    total_nation_balances = (
        db.execute(
            select(func.coalesce(func.sum(Nation.treasury_balance), 0))
        ).scalar()
        or 0
    )
    total_supply = total_user_balances + total_nation_balances

    # Total ever minted
    total_minted = (
        db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.tx_type == "MINT"
            )
        ).scalar()
        or 0
    )

    # Transactions by type
    tx_type_rows = list(
        db.execute(
            select(
                Transaction.tx_type,
                func.count(Transaction.id),
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .group_by(Transaction.tx_type)
            .order_by(func.count(Transaction.id).desc())
        ).all()
    )
    tx_by_type = [
        {"type": row[0], "count": row[1], "volume": row[2]}
        for row in tx_type_rows
    ]

    # Top wallets by balance (top 10 users)
    top_user_rows = list(
        db.execute(
            select(User)
            .where(User.role != "world_mint", User.balance > 0)
            .order_by(User.balance.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )
    top_wallets = [
        {
            "name": u.display_name or u.username,
            "address": u.wallet_address,
            "balance": u.balance,
        }
        for u in top_user_rows
    ]

    # Nation treasuries
    nation_rows = list(
        db.execute(
            select(Nation).order_by(Nation.treasury_balance.desc())
        )
        .scalars()
        .all()
    )
    nation_treasuries = [
        {
            "id": n.id,
            "name": n.name,
            "treasury_address": n.treasury_address,
            "treasury_balance": n.treasury_balance,
            "member_count": n.member_count,
            "status": n.status,
        }
        for n in nation_rows
    ]

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="mint",
        chain_valid=chain_valid,
        chain_errors=chain_errors,
        total_transactions=total_transactions,
        total_supply=total_supply,
        total_minted=total_minted,
        tx_by_type=tx_by_type,
        top_wallets=top_wallets,
        nation_treasuries=nation_treasuries,
    )
    return templates.TemplateResponse("mint/stats.html", ctx)


# ---------------------------------------------------------------------------
# POST /mint/execute — Process mint form
# ---------------------------------------------------------------------------
@router.post("/mint/execute")
def mint_execute_post(
    request: Request,
    to_address: str = Form(...),
    amount: int = Form(...),
    memo: str = Form(None),
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    try:
        create_transaction(
            db,
            tx_type="MINT",
            from_address=settings.WORLD_MINT_ADDRESS,
            to_address=to_address.strip(),
            amount=amount,
            memo=memo or None,
        )
        return RedirectResponse(
            url="/mint?success=Minted+" + str(amount) + "+" + settings.CURRENCY_SHORT + "+successfully",
            status_code=303,
        )
    except ValueError as exc:
        error_msg = str(exc).replace(" ", "+")
        return RedirectResponse(
            url=f"/mint?error={error_msg}",
            status_code=303,
        )


# ---------------------------------------------------------------------------
# POST /mint/nations/{nation_id}/approve — Approve a pending nation
# ---------------------------------------------------------------------------
@router.post("/mint/nations/{nation_id}/approve")
def mint_approve_nation_post(
    nation_id: int,
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/mint?error=Nation+not+found", status_code=303
        )

    if nation.status != "pending":
        return RedirectResponse(
            url="/mint?error=Nation+is+not+pending", status_code=303
        )

    nation.status = "approved"
    nation.approved_at = datetime.now(timezone.utc)

    # Promote the nation leader
    leader = db.execute(
        select(User).where(User.id == nation.leader_id)
    ).scalar_one_or_none()
    if leader is not None:
        if leader.role != "world_mint":
            leader.role = "nation_leader"
        leader.nation_id = nation.id
        nation.member_count += 1

    db.commit()

    # Auto-create nation stock
    create_nation_stock(db, nation)

    return RedirectResponse(
        url=f"/mint?success=Nation+'{nation.name}'+approved+successfully".replace("'", "%27"),
        status_code=303,
    )


# ---------------------------------------------------------------------------
# POST /mint/nations/{nation_id}/reject — Reject a pending nation
# ---------------------------------------------------------------------------
@router.post("/mint/nations/{nation_id}/reject")
def mint_reject_nation_post(
    nation_id: int,
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/mint?error=Nation+not+found", status_code=303
        )

    nation.status = "rejected"
    db.commit()

    return RedirectResponse(
        url="/mint?success=Nation+rejected", status_code=303
    )


# ---------------------------------------------------------------------------
# GET /mint/nations — World Mint nation directory (with edit links)
# ---------------------------------------------------------------------------
@router.get("/mint/nations")
def mint_nations_directory(
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    """List every nation with its identity fields and an edit link.

    World Mint admin can rename or re-tag any nation regardless of status.
    """
    nations = db.execute(
        select(Nation).order_by(Nation.status, Nation.name)
    ).scalars().all()

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="mint",
        nations=nations,
    )
    return templates.TemplateResponse("mint/nations.html", ctx)


# ---------------------------------------------------------------------------
# GET /mint/nations/{nation_id}/edit-identity — Identity edit form
# ---------------------------------------------------------------------------
@router.get("/mint/nations/{nation_id}/edit-identity")
def mint_edit_nation_identity_form(
    nation_id: int,
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/mint/nations?error=Nation+not+found", status_code=303
        )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="mint",
        nation=nation,
    )
    return templates.TemplateResponse("mint/nation_edit.html", ctx)


# ---------------------------------------------------------------------------
# POST /mint/nations/{nation_id}/edit-identity — Process identity edit
# ---------------------------------------------------------------------------
@router.post("/mint/nations/{nation_id}/edit-identity")
def mint_edit_nation_identity_post(
    nation_id: int,
    request: Request,
    name: str = Form(...),
    currency_name: str = Form(""),
    currency_code: str = Form(""),
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    """World Mint may rename a nation and/or change its currency display
    fields.  ``name`` is unique across nations — uniqueness is enforced
    here so the user gets a clean 303 redirect with an error message
    instead of a 500 from the constraint violation.
    """
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/mint/nations?error=Nation+not+found", status_code=303
        )

    # Normalise inputs.  Empty strings for the optional currency fields
    # are converted back to NULL so the schema's nullable semantics hold.
    new_name = (name or "").strip()
    new_currency_name = (currency_name or "").strip() or None
    new_currency_code = (currency_code or "").strip().upper() or None

    if not new_name:
        return RedirectResponse(
            url=f"/mint/nations/{nation_id}/edit-identity?error=Name+is+required",
            status_code=303,
        )

    # Uniqueness guard: if the name changed, ensure no other nation has it.
    if new_name != nation.name:
        clash = db.execute(
            select(Nation).where(Nation.name == new_name, Nation.id != nation_id)
        ).scalar_one_or_none()
        if clash is not None:
            return RedirectResponse(
                url=(
                    f"/mint/nations/{nation_id}/edit-identity"
                    f"?error=Nation+name+already+taken+by+%23{clash.id}"
                ),
                status_code=303,
            )

    # Sanity bounds on the currency code (used as a short tag in tables).
    if new_currency_code and (len(new_currency_code) > 8 or len(new_currency_code) < 2):
        return RedirectResponse(
            url=(
                f"/mint/nations/{nation_id}/edit-identity"
                f"?error=Currency+code+must+be+2-8+characters"
            ),
            status_code=303,
        )

    # If the new currency_code would collide with another stock's ticker,
    # reject before any writes — keeps stocks.ticker globally unique.
    if new_currency_code:
        ticker_clash = db.execute(
            select(Stock).where(
                Stock.ticker == new_currency_code,
                ~((Stock.stock_type == "nation") & (Stock.entity_id == nation.id)),
            )
        ).scalar_one_or_none()
        if ticker_clash is not None:
            return RedirectResponse(
                url=(
                    f"/mint/nations/{nation_id}/edit-identity"
                    f"?error=Ticker+{new_currency_code}+already+in+use+by+another+stock"
                ),
                status_code=303,
            )

    nation.name = new_name
    nation.currency_name = new_currency_name
    nation.currency_code = new_currency_code

    # Keep the matching nation Stock row in sync — `stocks.name` and
    # `stocks.ticker` are denormalised copies that the exchange page reads
    # directly, so they have to be updated whenever nation identity changes.
    nation_stock = db.execute(
        select(Stock).where(
            Stock.stock_type == "nation",
            Stock.entity_id == nation.id,
        )
    ).scalar_one_or_none()
    if nation_stock is not None:
        nation_stock.name = new_name
        if new_currency_code:
            nation_stock.ticker = new_currency_code
        else:
            from app.valuation import generate_ticker
            nation_stock.ticker = generate_ticker(new_name, db)

    db.commit()

    return RedirectResponse(
        url=f"/mint/nations?success=Updated+nation+%23{nation_id}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# POST /mint/calculate-allocations — Calculate monthly allocations (page)
# ---------------------------------------------------------------------------
@router.post("/mint/calculate-allocations")
def mint_calculate_allocations_post(
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone

    # Determine the target period (next month in "YYYY-MM" format)
    now = datetime.now(timezone.utc)
    next_month = now.replace(day=1) + timedelta(days=32)
    period = next_month.strftime("%Y-%m")

    # Fetch all approved nations
    nations = list(
        db.execute(
            select(Nation).where(Nation.status == "approved")
        ).scalars().all()
    )

    allocations_created = 0
    for nation in nations:
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

    db.commit()

    if allocations_created > 0:
        return RedirectResponse(
            url=f"/mint?success=Calculated+{allocations_created}+allocations+for+period+{period}",
            status_code=303,
        )
    else:
        return RedirectResponse(
            url=f"/mint?info=No+new+allocations+to+calculate+for+{period}",
            status_code=303,
        )


# ---------------------------------------------------------------------------
# POST /mint/allocations/{allocation_id}/approve — Approve an allocation (page)
# ---------------------------------------------------------------------------
@router.post("/mint/allocations/{allocation_id}/approve")
def mint_approve_allocation_post(
    allocation_id: int,
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    allocation = db.execute(
        select(MintAllocation).where(MintAllocation.id == allocation_id)
    ).scalar_one_or_none()

    if allocation is None:
        return RedirectResponse(
            url="/mint?error=Allocation+not+found", status_code=303
        )

    if allocation.status != "pending":
        return RedirectResponse(
            url="/mint?error=Allocation+is+not+pending", status_code=303
        )

    allocation.status = "approved"
    allocation.approved_amount = allocation.calculated_amount
    allocation.approved_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(
        url="/mint?success=Allocation+approved", status_code=303
    )


# ---------------------------------------------------------------------------
# POST /mint/allocations/{allocation_id}/execute — Execute an allocation (page)
# ---------------------------------------------------------------------------
@router.post("/mint/allocations/{allocation_id}/execute")
def mint_execute_allocation_post(
    allocation_id: int,
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    allocation = db.execute(
        select(MintAllocation).where(MintAllocation.id == allocation_id)
    ).scalar_one_or_none()

    if allocation is None:
        return RedirectResponse(
            url="/mint?error=Allocation+not+found", status_code=303
        )

    if allocation.status != "approved":
        return RedirectResponse(
            url="/mint?error=Allocation+must+be+approved+before+execution",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.id == allocation.nation_id)
    ).scalar_one_or_none()

    if nation is None:
        return RedirectResponse(
            url="/mint?error=Nation+not+found+for+this+allocation",
            status_code=303,
        )

    try:
        create_transaction(
            db,
            tx_type="MINT",
            from_address=settings.WORLD_MINT_ADDRESS,
            to_address=nation.treasury_address,
            amount=allocation.approved_amount,
            memo=f"Mint allocation for period {allocation.period}",
        )
    except ValueError as exc:
        error_msg = str(exc).replace(" ", "+")
        return RedirectResponse(
            url=f"/mint?error={error_msg}", status_code=303
        )

    allocation.status = "distributed"
    allocation.distributed_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(
        url=f"/mint?success=Allocation+executed:+{allocation.approved_amount}+{settings.CURRENCY_SHORT}+minted+to+{nation.name.replace(' ', '+')}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# POST /mint/recalculate-stocks — Recalculate all stock prices
# ---------------------------------------------------------------------------
@router.post("/mint/recalculate-gdp")
def mint_recalculate_gdp_post(
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    count = recalculate_all_gdp(db)
    return RedirectResponse(
        url=f"/mint?success=Recalculated+GDP+for+{count}+nations",
        status_code=303,
    )


@router.post("/mint/recalculate-stocks")
def mint_recalculate_stocks_post(
    request: Request,
    user: User = Depends(_require_world_mint),
    db: Session = Depends(get_db),
):
    count = recalculate_all_prices(db)
    return RedirectResponse(
        url=f"/mint?success=Recalculated+prices+for+{count}+stocks",
        status_code=303,
    )


# =========================================================================
# STOCK EXCHANGE PAGES
# =========================================================================

# ---------------------------------------------------------------------------
# GET /exchange — Stock exchange listing
# ---------------------------------------------------------------------------
@router.get("/exchange")
def exchange_page(
    request: Request,
    stock_type: str = Query(""),
    sort_by: str = Query("ticker"),
    user: Optional[User] = Depends(get_current_user),
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

    # Compute total market cap
    total_market_cap = sum(
        s.current_price * (s.total_shares - s.available_shares)
        for s in stocks
    )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="exchange",
        stocks=stocks,
        stock_type=stock_type,
        sort_by=sort_by,
        total_market_cap=total_market_cap,
        total_stocks=len(stocks),
    )
    return templates.TemplateResponse("exchange.html", ctx)


# ---------------------------------------------------------------------------
# GET /exchange/{ticker} — Stock detail page
# ---------------------------------------------------------------------------
@router.get("/exchange/{ticker}")
def exchange_detail_page(
    ticker: str,
    request: Request,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stock = db.execute(
        select(Stock).where(Stock.ticker == ticker.upper())
    ).scalar_one_or_none()
    if stock is None:
        return RedirectResponse(url="/exchange?error=Stock+not+found", status_code=303)

    # Latest valuation
    latest_val = db.execute(
        select(StockValuation)
        .where(StockValuation.stock_id == stock.id)
        .order_by(StockValuation.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Price history (last 30 snapshots)
    price_history = list(
        db.execute(
            select(StockValuation)
            .where(StockValuation.stock_id == stock.id)
            .order_by(StockValuation.snapshot_date.desc())
            .limit(30)
        ).scalars().all()
    )

    # Recent trades
    recent_trades = list(
        db.execute(
            select(StockTransaction)
            .where(StockTransaction.stock_id == stock.id)
            .order_by(StockTransaction.created_at.desc())
            .limit(20)
        ).scalars().all()
    )

    # Entity info
    entity_info = {}
    if stock.stock_type == "nation":
        nation = db.execute(
            select(Nation).where(Nation.id == stock.entity_id)
        ).scalar_one_or_none()
        if nation:
            entity_info = {
                "name": nation.name,
                "member_count": nation.member_count,
                "treasury_balance": nation.treasury_balance,
                "game": nation.game,
            }
    elif stock.stock_type == "business":
        shop = db.execute(
            select(Shop).where(Shop.id == stock.entity_id)
        ).scalar_one_or_none()
        if shop:
            owner = db.execute(
                select(User).where(User.id == shop.owner_id)
            ).scalar_one_or_none()
            entity_info = {
                "name": shop.name,
                "owner_name": (owner.display_name or owner.username) if owner else "Unknown",
                "total_sales": shop.total_sales,
                "total_revenue": shop.total_revenue,
            }

    # User's holding (if logged in)
    user_holding = None
    if user:
        user_holding = db.execute(
            select(StockHolding).where(
                StockHolding.user_id == user.id,
                StockHolding.stock_id == stock.id,
            )
        ).scalar_one_or_none()

    # Build name map for trades
    name_map = _build_name_map(db)

    shares_outstanding = stock.total_shares - stock.available_shares
    market_cap = stock.current_price * shares_outstanding

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="exchange",
        stock=stock,
        latest_val=latest_val,
        price_history=list(reversed(price_history)),
        recent_trades=recent_trades,
        entity_info=entity_info,
        user_holding=user_holding,
        name_map=name_map,
        shares_outstanding=shares_outstanding,
        market_cap=market_cap,
    )
    return templates.TemplateResponse("exchange_detail.html", ctx)


# ---------------------------------------------------------------------------
# GET /exchange/{ticker}/trade — Buy/sell interface
# ---------------------------------------------------------------------------
@router.get("/exchange/{ticker}/trade")
def exchange_trade_page(
    ticker: str,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    stock = db.execute(
        select(Stock).where(Stock.ticker == ticker.upper())
    ).scalar_one_or_none()
    if stock is None:
        return RedirectResponse(url="/exchange?error=Stock+not+found", status_code=303)

    user_holding = db.execute(
        select(StockHolding).where(
            StockHolding.user_id == user.id,
            StockHolding.stock_id == stock.id,
        )
    ).scalar_one_or_none()

    # Check business stock eligibility
    can_buy = True
    buy_blocked_reason = ""
    if stock.stock_type == "business":
        shop = db.execute(
            select(Shop).where(Shop.id == stock.entity_id)
        ).scalar_one_or_none()
        if shop and user.nation_id != shop.nation_id:
            can_buy = False
            buy_blocked_reason = "You must be a member of this shop's nation to buy"

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="exchange",
        stock=stock,
        user_holding=user_holding,
        can_buy=can_buy,
        buy_blocked_reason=buy_blocked_reason,
    )
    return templates.TemplateResponse("exchange_trade.html", ctx)


# ---------------------------------------------------------------------------
# POST /exchange/{ticker}/buy — Execute stock buy
# ---------------------------------------------------------------------------
@router.post("/exchange/{ticker}/buy")
def exchange_buy_post(
    ticker: str,
    request: Request,
    shares: int = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    with _stock_lock:
        stock = db.execute(
            select(Stock).where(Stock.ticker == ticker.upper())
        ).scalar_one_or_none()
        if stock is None:
            return RedirectResponse(url="/exchange?error=Stock+not+found", status_code=303)

        if shares <= 0:
            return RedirectResponse(
                url=f"/exchange/{stock.ticker}/trade?error=Must+buy+at+least+1+share",
                status_code=303,
            )
        if shares > stock.available_shares:
            return RedirectResponse(
                url=f"/exchange/{stock.ticker}/trade?error=Only+{stock.available_shares}+shares+available",
                status_code=303,
            )

        total_cost = shares * stock.current_price
        if user.balance < total_cost:
            return RedirectResponse(
                url=f"/exchange/{stock.ticker}/trade?error=Insufficient+balance.+Need+{total_cost}+HM",
                status_code=303,
            )

        # Business stock nation check
        if stock.stock_type == "business":
            shop = db.execute(
                select(Shop).where(Shop.id == stock.entity_id)
            ).scalar_one_or_none()
            if shop and user.nation_id != shop.nation_id:
                return RedirectResponse(
                    url=f"/exchange/{stock.ticker}/trade?error=Must+be+in+this+nation+to+buy",
                    status_code=303,
                )

        # Determine counterparty
        if stock.stock_type == "nation":
            nation = db.execute(
                select(Nation).where(Nation.id == stock.entity_id)
            ).scalar_one_or_none()
            to_address = nation.treasury_address if nation else ""
        else:
            shop = db.execute(
                select(Shop).where(Shop.id == stock.entity_id)
            ).scalar_one_or_none()
            owner = db.execute(
                select(User).where(User.id == shop.owner_id)
            ).scalar_one_or_none() if shop else None
            to_address = owner.wallet_address if owner else ""

        try:
            create_transaction(
                db,
                tx_type="STOCK_BUY",
                from_address=user.wallet_address,
                to_address=to_address,
                amount=total_cost,
                memo=f"Bought {shares} shares of {stock.ticker} at {stock.current_price} HM/share",
            )
        except ValueError as exc:
            error_msg = str(exc).replace(" ", "+")
            return RedirectResponse(
                url=f"/exchange/{stock.ticker}/trade?error={error_msg}",
                status_code=303,
            )

        stock.available_shares -= shares

        # Upsert holding
        holding = db.execute(
            select(StockHolding).where(
                StockHolding.user_id == user.id,
                StockHolding.stock_id == stock.id,
            )
        ).scalar_one_or_none()

        if holding is None:
            holding = StockHolding(
                user_id=user.id,
                stock_id=stock.id,
                shares=shares,
                avg_buy_price=stock.current_price,
            )
            db.add(holding)
        else:
            old_total = holding.shares * holding.avg_buy_price
            new_total = shares * stock.current_price
            holding.avg_buy_price = round(
                (old_total + new_total) / (holding.shares + shares)
            )
            holding.shares += shares

        stx = StockTransaction(
            stock_id=stock.id,
            buyer_id=user.id,
            shares=shares,
            price_per_share=stock.current_price,
            total_cost=total_cost,
            tx_type="BUY",
        )
        db.add(stx)
        db.commit()

    return RedirectResponse(
        url=f"/exchange/{stock.ticker}?success=Bought+{shares}+shares+for+{total_cost}+HM",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# POST /exchange/{ticker}/sell — Execute stock sell
# ---------------------------------------------------------------------------
@router.post("/exchange/{ticker}/sell")
def exchange_sell_post(
    ticker: str,
    request: Request,
    shares: int = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    with _stock_lock:
        stock = db.execute(
            select(Stock).where(Stock.ticker == ticker.upper())
        ).scalar_one_or_none()
        if stock is None:
            return RedirectResponse(url="/exchange?error=Stock+not+found", status_code=303)

        if shares <= 0:
            return RedirectResponse(
                url=f"/exchange/{stock.ticker}/trade?error=Must+sell+at+least+1+share",
                status_code=303,
            )

        holding = db.execute(
            select(StockHolding).where(
                StockHolding.user_id == user.id,
                StockHolding.stock_id == stock.id,
            )
        ).scalar_one_or_none()

        if holding is None or holding.shares < shares:
            available = holding.shares if holding else 0
            return RedirectResponse(
                url=f"/exchange/{stock.ticker}/trade?error=You+only+hold+{available}+shares",
                status_code=303,
            )

        total_proceeds = shares * stock.current_price

        # Entity buys back
        if stock.stock_type == "nation":
            nation = db.execute(
                select(Nation).where(Nation.id == stock.entity_id)
            ).scalar_one_or_none()
            from_address = nation.treasury_address if nation else ""
        else:
            shop = db.execute(
                select(Shop).where(Shop.id == stock.entity_id)
            ).scalar_one_or_none()
            owner = db.execute(
                select(User).where(User.id == shop.owner_id)
            ).scalar_one_or_none() if shop else None
            from_address = owner.wallet_address if owner else ""

        try:
            create_transaction(
                db,
                tx_type="STOCK_SELL",
                from_address=from_address,
                to_address=user.wallet_address,
                amount=total_proceeds,
                memo=f"Sold {shares} shares of {stock.ticker} at {stock.current_price} HM/share",
            )
        except ValueError as exc:
            error_msg = str(exc).replace(" ", "+")
            return RedirectResponse(
                url=f"/exchange/{stock.ticker}/trade?error={error_msg}",
                status_code=303,
            )

        stock.available_shares += shares
        holding.shares -= shares
        if holding.shares <= 0:
            db.delete(holding)

        stx = StockTransaction(
            stock_id=stock.id,
            seller_id=user.id,
            shares=shares,
            price_per_share=stock.current_price,
            total_cost=total_proceeds,
            tx_type="SELL",
        )
        db.add(stx)
        db.commit()

    return RedirectResponse(
        url=f"/exchange/{stock.ticker}?success=Sold+{shares}+shares+for+{total_proceeds}+HM",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /portfolio — User's stock portfolio
# ---------------------------------------------------------------------------
@router.get("/portfolio")
def portfolio_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    holdings = list(
        db.execute(
            select(StockHolding)
            .where(StockHolding.user_id == user.id)
            .order_by(StockHolding.acquired_at.desc())
        ).scalars().all()
    )

    portfolio_items = []
    total_value = 0
    total_invested = 0

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

        portfolio_items.append({
            "stock": stock,
            "holding": h,
            "current_value": current_value,
            "gain_loss": gain_loss,
        })

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="portfolio",
        portfolio_items=portfolio_items,
        total_value=total_value,
        total_invested=total_invested,
        total_gain_loss=total_value - total_invested,
    )
    return templates.TemplateResponse("portfolio.html", ctx)


# ---------------------------------------------------------------------------
# GET /shop/ipo — IPO creation form
# ---------------------------------------------------------------------------
@router.get("/shop/ipo")
def shop_ipo_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(Shop).where(Shop.owner_id == user.id)).scalar_one_or_none()
    if shop is None:
        return RedirectResponse(url="/shop/manage?error=You+need+a+shop+first", status_code=303)

    # Check if stock already exists
    existing_stock = db.execute(
        select(Stock).where(Stock.stock_type == "business", Stock.entity_id == shop.id)
    ).scalar_one_or_none()
    if existing_stock:
        return RedirectResponse(
            url=f"/exchange/{existing_stock.ticker}?info=Your+shop+already+has+a+stock",
            status_code=303,
        )

    # Eligibility checks
    from app.valuation import IPO_MIN_DAYS, IPO_MIN_SALES
    from datetime import timezone as tz

    eligible = True
    reasons = []
    if shop.total_sales < IPO_MIN_SALES:
        eligible = False
        reasons.append(f"Need {IPO_MIN_SALES} sales (have {shop.total_sales})")
    if shop.created_at:
        days = (datetime.now(tz.utc) - shop.created_at.replace(tzinfo=tz.utc)).days
        if days < IPO_MIN_DAYS:
            eligible = False
            reasons.append(f"Shop must be {IPO_MIN_DAYS}+ days old ({days} days)")

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="shop",
        shop=shop,
        eligible=eligible,
        reasons=reasons,
    )
    return templates.TemplateResponse("shop_ipo.html", ctx)


# ---------------------------------------------------------------------------
# POST /shop/ipo — Process IPO
# ---------------------------------------------------------------------------
@router.post("/shop/ipo")
def shop_ipo_post(
    request: Request,
    num_shares: int = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    shop = db.execute(select(Shop).where(Shop.owner_id == user.id)).scalar_one_or_none()
    if shop is None:
        return RedirectResponse(url="/shop/manage?error=You+need+a+shop+first", status_code=303)

    try:
        stock = create_business_stock(db, shop, num_shares)
        return RedirectResponse(
            url=f"/exchange/{stock.ticker}?success=IPO+successful!+{stock.ticker}+is+now+listed",
            status_code=303,
        )
    except ValueError as exc:
        error_msg = str(exc).replace(" ", "+")
        return RedirectResponse(
            url=f"/shop/ipo?error={error_msg}",
            status_code=303,
        )


# =========================================================================
# BANKING PAGES
# =========================================================================

# ---------------------------------------------------------------------------
# GET /banks/nation/{nation_id} — List banks for a nation
# ---------------------------------------------------------------------------
@router.get("/banks/nation/{nation_id}")
def banks_list_page(
    request: Request,
    nation_id: int,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Display all banks for a given nation."""
    nation = db.execute(
        select(Nation).where(Nation.id == nation_id)
    ).scalar_one_or_none()
    if nation is None:
        return RedirectResponse(url="/nations?error=Nation+not+found", status_code=303)

    banks = list(
        db.execute(
            select(Bank).where(Bank.nation_id == nation_id)
            .order_by(Bank.created_at.desc())
        ).scalars().all()
    )

    # Build bank data with active loan counts
    bank_data = []
    for b in banks:
        active_loans = db.execute(
            select(func.count(Loan.id)).where(
                Loan.bank_id == b.id, Loan.status == "active"
            )
        ).scalar() or 0
        owner = db.execute(select(User).where(User.id == b.owner_id)).scalar_one_or_none()
        bank_data.append({
            "id": b.id,
            "name": b.name,
            "wallet_address": b.wallet_address,
            "balance": b.balance,
            "total_loaned": b.total_loaned,
            "total_burned": b.total_burned,
            "is_active": b.is_active,
            "active_loans": active_loans,
            "owner_name": owner.display_name or owner.username if owner else "Unknown",
        })

    # Check if the current user is the nation leader
    is_leader = user is not None and nation.leader_id == user.id

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="banks",
        nation_name=nation.name,
        banks=bank_data,
        is_leader=is_leader,
        nation_id=nation_id,
    )
    return templates.TemplateResponse("bank_list.html", ctx)


# ---------------------------------------------------------------------------
# GET /banks/create — Bank creation form (Nation Leader only)
# (Must be registered BEFORE /banks/{bank_id} to avoid "create" matching as an ID)
# ---------------------------------------------------------------------------
@router.get("/banks/create")
def bank_create_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Show the bank creation form.  Nation leaders only."""
    if user.role not in ("nation_leader", "world_mint"):
        return RedirectResponse(
            url="/dashboard?error=Only+nation+leaders+can+create+banks",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()
    if nation is None:
        return RedirectResponse(
            url="/dashboard?error=No+approved+nation+found",
            status_code=303,
        )

    # Get nation members for the operator dropdown
    members = list(
        db.execute(
            select(User).where(User.nation_id == nation.id)
        ).scalars().all()
    )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="banks",
        nation=nation,
        members=members,
    )
    return templates.TemplateResponse("bank_create.html", ctx)


# ---------------------------------------------------------------------------
# POST /banks/create — Handle bank creation form submission
# ---------------------------------------------------------------------------
@router.post("/banks/create")
def bank_create_post(
    request: Request,
    name: str = Form(...),
    owner_user_id: int = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Process the bank creation form.  Delegates to the API logic."""
    if user.role not in ("nation_leader", "world_mint"):
        return RedirectResponse(
            url="/dashboard?error=Only+nation+leaders+can+create+banks",
            status_code=303,
        )

    nation = db.execute(
        select(Nation).where(Nation.leader_id == user.id, Nation.status == "approved")
    ).scalar_one_or_none()
    if nation is None:
        return RedirectResponse(url="/dashboard?error=No+approved+nation+found", status_code=303)

    # Check max 4 banks
    bank_count = db.execute(
        select(func.count(Bank.id)).where(Bank.nation_id == nation.id)
    ).scalar() or 0
    if bank_count >= 4:
        return RedirectResponse(
            url=f"/banks/nation/{nation.id}?error=Maximum+of+4+banks+reached",
            status_code=303,
        )

    # Validate owner is a nation member
    owner = db.execute(select(User).where(User.id == owner_user_id)).scalar_one_or_none()
    if owner is None or owner.nation_id != nation.id:
        return RedirectResponse(
            url=f"/banks/create?error=Operator+must+be+a+nation+member",
            status_code=303,
        )

    from app.wallet import generate_bank_wallet_address

    bank = Bank(
        nation_id=nation.id,
        owner_id=owner_user_id,
        name=name.strip(),
        wallet_address="PENDING",
    )
    db.add(bank)
    db.flush()
    bank.wallet_address = generate_bank_wallet_address(bank.id)
    db.commit()

    return RedirectResponse(
        url=f"/banks/{bank.id}?success=Bank+created+successfully",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /banks/{bank_id} — Bank detail page
# (Registered AFTER /banks/create and /banks/nation/{id} to avoid path conflicts)
# ---------------------------------------------------------------------------
@router.get("/banks/{bank_id}")
def bank_detail_page(
    request: Request,
    bank_id: int,
    user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Display bank details, loans, and stats."""
    bank = db.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if bank is None:
        return RedirectResponse(url="/nations?error=Bank+not+found", status_code=303)

    owner = db.execute(select(User).where(User.id == bank.owner_id)).scalar_one_or_none()
    nation = db.execute(select(Nation).where(Nation.id == bank.nation_id)).scalar_one_or_none()

    # Active loan count
    active_loan_count = db.execute(
        select(func.count(Loan.id)).where(
            Loan.bank_id == bank.id, Loan.status == "active"
        )
    ).scalar() or 0

    # All loans for this bank
    loans = list(
        db.execute(
            select(Loan).where(Loan.bank_id == bank.id)
            .order_by(Loan.opened_at.desc())
        ).scalars().all()
    )

    loan_data = []
    for loan in loans:
        borrower = db.execute(
            select(User).where(User.id == loan.borrower_id)
        ).scalar_one_or_none()
        loan_data.append({
            "id": loan.id,
            "borrower_name": borrower.display_name or borrower.username if borrower else "Unknown",
            "borrower_wallet": borrower.wallet_address if borrower else "",
            "principal": loan.principal,
            "outstanding": loan.outstanding,
            "interest_rate": loan.interest_rate,
            "status": loan.status,
            "opened_at": loan.opened_at.isoformat() if loan.opened_at else None,
        })

    # Check if current user is the nation leader (for forgive button)
    is_leader = user is not None and nation is not None and nation.leader_id == user.id

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="banks",
        bank=bank,
        owner_name=owner.display_name or owner.username if owner else "Unknown",
        nation_name=nation.name if nation else "Unknown",
        active_loan_count=active_loan_count,
        loans=loan_data,
        is_leader=is_leader,
    )
    return templates.TemplateResponse("bank_detail.html", ctx)


# ---------------------------------------------------------------------------
# GET /loans/apply — Loan application form
# ---------------------------------------------------------------------------
@router.get("/loans/apply")
def loan_apply_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Show the loan application form for citizens."""
    # Get active banks in the user's nation
    banks = []
    if user.nation_id:
        banks = list(
            db.execute(
                select(Bank).where(
                    Bank.nation_id == user.nation_id,
                    Bank.is_active == True,  # noqa: E712
                )
            ).scalars().all()
        )

    # Check if user already has an active loan
    has_active_loan = db.execute(
        select(Loan).where(Loan.borrower_id == user.id, Loan.status == "active")
    ).scalar_one_or_none() is not None

    # Get current global settings for display
    gs = db.execute(
        select(GlobalSettings).where(GlobalSettings.id == 1)
    ).scalar_one_or_none()
    burn_rate_pct = round((gs.burn_rate_bps if gs else 1000) / 100, 1)
    interest_rate_cap_pct = round((gs.interest_rate_cap_bps if gs else 2000) / 100, 1)

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="loans",
        banks=banks,
        has_active_loan=has_active_loan,
        burn_rate_pct=burn_rate_pct,
        interest_rate_cap_pct=interest_rate_cap_pct,
    )
    return templates.TemplateResponse("loan_apply.html", ctx)


# ---------------------------------------------------------------------------
# POST /loans/apply — Handle loan application form submission
# ---------------------------------------------------------------------------
@router.post("/loans/apply")
def loan_apply_post(
    request: Request,
    bank_id: int = Form(...),
    amount: int = Form(...),
    memo: str = Form(None),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Process the loan application.  Creates the loan via bank operator logic."""
    bank = db.execute(select(Bank).where(Bank.id == bank_id)).scalar_one_or_none()
    if bank is None:
        return RedirectResponse(url="/loans/apply?error=Bank+not+found", status_code=303)

    # The loan issuance is performed by the bank operator via the API.
    # For the citizen self-service form, we create the loan directly since
    # the bank operator pre-approves loans by making the bank active.
    # Validate all the same rules as the API endpoint.

    if not bank.is_active:
        return RedirectResponse(url="/loans/apply?error=Bank+is+not+active", status_code=303)

    if user.nation_id != bank.nation_id:
        return RedirectResponse(url="/loans/apply?error=Must+be+in+same+nation", status_code=303)

    active_loan = db.execute(
        select(Loan).where(Loan.borrower_id == user.id, Loan.status == "active")
    ).scalar_one_or_none()
    if active_loan is not None:
        return RedirectResponse(url="/loans/apply?error=You+already+have+an+active+loan", status_code=303)

    if amount <= 0:
        return RedirectResponse(url="/loans/apply?error=Amount+must+be+positive", status_code=303)

    if bank.balance < amount:
        return RedirectResponse(url="/loans/apply?error=Bank+has+insufficient+reserves", status_code=303)

    # Snapshot global settings
    gs = db.execute(select(GlobalSettings).where(GlobalSettings.id == 1)).scalar_one_or_none()
    if gs is None:
        gs_burn = 1000
        gs_interest = 2000
    else:
        gs_burn = gs.burn_rate_bps
        gs_interest = gs.interest_rate_cap_bps

    # Create the LOAN transaction
    try:
        tx = create_transaction(
            db,
            tx_type="LOAN",
            from_address=bank.wallet_address,
            to_address=user.wallet_address,
            amount=amount,
            memo=f"Loan from {bank.name}: {memo or 'No memo'}",
        )
    except ValueError as exc:
        error_msg = str(exc).replace(" ", "+")
        return RedirectResponse(url=f"/loans/apply?error={error_msg}", status_code=303)

    bank.total_loaned += amount

    loan = Loan(
        bank_id=bank.id,
        borrower_id=user.id,
        principal=amount,
        outstanding=amount,
        interest_rate=gs_interest,
        burn_rate_snapshot=gs_burn,
        status="active",
        memo=memo,
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)

    return RedirectResponse(
        url=f"/loans/{loan.id}?success=Loan+approved+and+disbursed",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /loans/mine — Citizen's loan dashboard
# (Must be registered BEFORE /loans/{loan_id} to avoid "mine" matching as an ID)
# ---------------------------------------------------------------------------
@router.get("/loans/mine")
def loans_mine_page(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Display the current user's loan dashboard."""
    all_loans = list(
        db.execute(
            select(Loan).where(Loan.borrower_id == user.id)
            .order_by(Loan.opened_at.desc())
        ).scalars().all()
    )

    # Build loan data with bank names
    active_loans = []
    closed_loans = []
    for loan in all_loans:
        bank = db.execute(select(Bank).where(Bank.id == loan.bank_id)).scalar_one_or_none()
        loan_dict = {
            "id": loan.id,
            "bank_name": bank.name if bank else "Unknown",
            "bank_id": loan.bank_id,
            "principal": loan.principal,
            "outstanding": loan.outstanding,
            "interest_rate": loan.interest_rate,
            "burn_rate_snapshot": loan.burn_rate_snapshot,
            "status": loan.status,
            "opened_at": loan.opened_at.isoformat() if loan.opened_at else None,
            "closed_at": loan.closed_at.isoformat() if loan.closed_at else None,
        }
        if loan.status == "active":
            active_loans.append(loan_dict)
        else:
            closed_loans.append(loan_dict)

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="loans",
        active_loans=active_loans,
        closed_loans=closed_loans,
    )
    return templates.TemplateResponse("loans_mine.html", ctx)


# ---------------------------------------------------------------------------
# GET /loans/{loan_id} — Loan detail page
# ---------------------------------------------------------------------------
@router.get("/loans/{loan_id}")
def loan_detail_page(
    request: Request,
    loan_id: int,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Display loan details and payment history."""
    loan = db.execute(select(Loan).where(Loan.id == loan_id)).scalar_one_or_none()
    if loan is None:
        return RedirectResponse(url="/loans/mine?error=Loan+not+found", status_code=303)

    # Only the borrower, bank operator, nation leader, or world_mint can see this
    bank = db.execute(select(Bank).where(Bank.id == loan.bank_id)).scalar_one_or_none()
    nation = db.execute(
        select(Nation).where(Nation.id == bank.nation_id)
    ).scalar_one_or_none() if bank else None

    allowed = (
        user.id == loan.borrower_id
        or (bank and user.id == bank.owner_id)
        or (nation and user.id == nation.leader_id)
        or user.role == "world_mint"
    )
    if not allowed:
        return RedirectResponse(url="/dashboard?error=Access+denied", status_code=303)

    # Payment history
    payments = list(
        db.execute(
            select(LoanPayment).where(LoanPayment.loan_id == loan.id)
            .order_by(LoanPayment.created_at.desc())
        ).scalars().all()
    )

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="loans",
        loan=loan,
        bank_name=bank.name if bank else "Unknown",
        payments=payments,
    )
    return templates.TemplateResponse("loan_detail.html", ctx)


# ---------------------------------------------------------------------------
# POST /loans/{loan_id}/pay — Handle loan payment form submission
# ---------------------------------------------------------------------------
@router.post("/loans/{loan_id}/pay")
def loan_pay_post(
    request: Request,
    loan_id: int,
    amount: int = Form(...),
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """Process a loan payment from the form."""
    import math as _math

    loan = db.execute(select(Loan).where(Loan.id == loan_id)).scalar_one_or_none()
    if loan is None:
        return RedirectResponse(url="/loans/mine?error=Loan+not+found", status_code=303)
    if loan.borrower_id != user.id:
        return RedirectResponse(url="/loans/mine?error=Not+your+loan", status_code=303)
    if loan.status != "active":
        return RedirectResponse(url=f"/loans/{loan_id}?error=Loan+is+not+active", status_code=303)
    if amount <= 0:
        return RedirectResponse(url=f"/loans/{loan_id}?error=Amount+must+be+positive", status_code=303)

    # Cap to outstanding
    amount = min(amount, loan.outstanding)

    if user.balance < amount:
        return RedirectResponse(
            url=f"/loans/{loan_id}?error=Insufficient+balance",
            status_code=303,
        )

    # Calculate burn split
    burn_amount = _math.floor(amount * loan.burn_rate_snapshot / 10000)
    bank_amount = amount - burn_amount

    bank = db.execute(select(Bank).where(Bank.id == loan.bank_id)).scalar_one_or_none()
    if bank is None:
        return RedirectResponse(url=f"/loans/{loan_id}?error=Bank+not+found", status_code=303)

    # Transaction 1: LOAN_PAYMENT — borrower → bank
    tx_hash = ""
    if bank_amount > 0:
        try:
            tx = create_transaction(
                db,
                tx_type="LOAN_PAYMENT",
                from_address=user.wallet_address,
                to_address=bank.wallet_address,
                amount=bank_amount,
                memo=f"Loan payment #{loan.id} (bank portion)",
            )
            tx_hash = tx.tx_hash
        except ValueError as exc:
            error_msg = str(exc).replace(" ", "+")
            return RedirectResponse(url=f"/loans/{loan_id}?error={error_msg}", status_code=303)

    # Transaction 2: BURN — borrower → World Mint (if burn > 0)
    if burn_amount > 0:
        try:
            burn_tx = create_transaction(
                db,
                tx_type="BURN",
                from_address=user.wallet_address,
                to_address=settings.WORLD_MINT_ADDRESS,
                amount=burn_amount,
                memo=f"Loan payment #{loan.id} burn split ({loan.burn_rate_snapshot}bps)",
            )
            if not tx_hash:
                tx_hash = burn_tx.tx_hash
        except ValueError as exc:
            error_msg = str(exc).replace(" ", "+")
            return RedirectResponse(url=f"/loans/{loan_id}?error={error_msg}", status_code=303)

    # Update bank and loan
    bank.total_burned += burn_amount
    loan.outstanding -= amount
    if loan.outstanding <= 0:
        loan.outstanding = 0
        loan.status = "closed"
        from datetime import datetime, timezone
        loan.closed_at = datetime.now(timezone.utc)

    payment = LoanPayment(
        loan_id=loan.id,
        amount=amount,
        burn_amount=burn_amount,
        bank_amount=bank_amount,
        balance_after=loan.outstanding,
        tx_hash=tx_hash or "no_tx",
    )
    db.add(payment)
    db.commit()

    if loan.status == "closed":
        return RedirectResponse(
            url=f"/loans/{loan_id}?success=Loan+fully+repaid!",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/loans/{loan_id}?success=Payment+of+{amount}+{settings.CURRENCY_SHORT}+recorded",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# GET /mint/settings — World Mint global settings page
# ---------------------------------------------------------------------------
@router.get("/mint/settings")
def mint_settings_page(
    request: Request,
    user: User = Depends(require_role("world_mint")),
    db: Session = Depends(get_db),
):
    """Display the World Mint global settings form."""
    gs = db.execute(
        select(GlobalSettings).where(GlobalSettings.id == 1)
    ).scalar_one_or_none()

    if gs is None:
        # Seed if missing
        gs = GlobalSettings(id=1, burn_rate_bps=1000, interest_rate_cap_bps=2000)
        db.add(gs)
        db.commit()
        db.refresh(gs)

    ctx = _base_context(
        request,
        user,
        db=db,
        active_page="mint",
        gs=gs,
        burn_rate_pct=round(gs.burn_rate_bps / 100, 1),
        interest_rate_cap_pct=round(gs.interest_rate_cap_bps / 100, 1),
    )
    return templates.TemplateResponse("mint/settings.html", ctx)


# ---------------------------------------------------------------------------
# POST /mint/settings — Handle settings form submission
# ---------------------------------------------------------------------------
@router.post("/mint/settings")
def mint_settings_post(
    request: Request,
    burn_rate_bps: int = Form(...),
    interest_rate_cap_bps: int = Form(...),
    user: User = Depends(require_role("world_mint")),
    db: Session = Depends(get_db),
):
    """Process the global settings update form."""
    from datetime import datetime, timezone

    # Validate ranges
    burn_rate_bps = max(0, min(10000, burn_rate_bps))
    interest_rate_cap_bps = max(0, min(10000, interest_rate_cap_bps))

    gs = db.execute(
        select(GlobalSettings).where(GlobalSettings.id == 1)
    ).scalar_one_or_none()

    if gs is None:
        gs = GlobalSettings(id=1)
        db.add(gs)

    gs.burn_rate_bps = burn_rate_bps
    gs.interest_rate_cap_bps = interest_rate_cap_bps
    gs.updated_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(
        url="/mint/settings?success=Settings+updated+successfully",
        status_code=303,
    )
