"""
Travelers Exchange — FastAPI Application Entry Point

Initialises the database, seeds the World Mint admin user, and mounts
static files + Jinja2 templates.  Route modules are included as they
become available.
"""

import os

import bcrypt
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from apscheduler.schedulers.background import BackgroundScheduler

from app.blockchain import create_genesis_block
from app.config import settings
from app.database import SessionLocal, init_db
from app.models import Bank, GdpSnapshot, GlobalSettings, Loan, LoanPayment, User  # noqa: F401  — ensures models are registered with Base
from app.routes.mint_routes import router as mint_router
from app.routes.nation_routes import router as nation_router
from app.routes.page_routes import router as page_router
from app.routes.transaction_routes import ledger_router, router as transaction_router
from app.routes.wallet_routes import router as wallet_router

# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------
app = FastAPI(title="Travelers Exchange")

# ---------------------------------------------------------------------------
# Static files & templates
# ---------------------------------------------------------------------------
# Ensure the static directory exists so mounting never fails on a fresh clone
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# ---------------------------------------------------------------------------
# Router includes (uncomment as agents deliver their route modules)
# ---------------------------------------------------------------------------
from app.routes.auth_routes import router as auth_router
app.include_router(auth_router)
app.include_router(transaction_router)
app.include_router(ledger_router)
app.include_router(wallet_router)
app.include_router(mint_router)
app.include_router(nation_router)
from app.routes.shop_routes import router as shop_router
app.include_router(shop_router)
from app.routes.stock_routes import router as stock_router
app.include_router(stock_router)
from app.routes.bank_routes import router as bank_router
app.include_router(bank_router)
app.include_router(page_router)


# ---------------------------------------------------------------------------
# Schema migrations  (idempotent — safe to re-run on every startup)
# ---------------------------------------------------------------------------
def _run_schema_migrations() -> None:
    """Add columns introduced after initial create_all.

    SQLAlchemy's create_all only creates missing *tables*, not missing columns.
    Each statement uses 'ADD COLUMN' which SQLite will reject with
    'duplicate column name' if it already exists — we catch and ignore that.
    """
    import sqlite3

    db_path = os.path.join("data", "economy.db")
    if not os.path.exists(db_path):
        return  # fresh DB, create_all handled everything

    conn = sqlite3.connect(db_path)
    migrations = [
        # Nation currency & GDP columns (Phase 1)
        "ALTER TABLE nations ADD COLUMN currency_name TEXT",
        "ALTER TABLE nations ADD COLUMN currency_code TEXT",
        "ALTER TABLE nations ADD COLUMN gdp_score INTEGER DEFAULT 50",
        "ALTER TABLE nations ADD COLUMN gdp_multiplier INTEGER DEFAULT 100",
        "ALTER TABLE nations ADD COLUMN gdp_last_calculated DATETIME",
        # Loan interest accrual columns (Phase 2A)
        "ALTER TABLE loans ADD COLUMN accrued_interest INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE loans ADD COLUMN cap_amount INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE loans ADD COLUMN interest_frozen BOOLEAN DEFAULT 0 NOT NULL",
        "ALTER TABLE loans ADD COLUMN last_accrual_at DATETIME",
        # Loan interest burn split tracking (Phase 2B)
        "ALTER TABLE loans ADD COLUMN interest_burn_rate_snapshot INTEGER DEFAULT 8000 NOT NULL",
        "ALTER TABLE loans ADD COLUMN total_interest_paid INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE loans ADD COLUMN total_burned_during_payments INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE loans ADD COLUMN final_close_burn INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE loan_payments ADD COLUMN interest_portion INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE loan_payments ADD COLUMN principal_portion INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE loan_payments ADD COLUMN is_final_payment BOOLEAN DEFAULT 0 NOT NULL",
        "ALTER TABLE global_settings ADD COLUMN interest_burn_rate_bps INTEGER DEFAULT 8000 NOT NULL",
        # Treasury lending (Phase 2C)
        "ALTER TABLE loans ADD COLUMN lender_type TEXT DEFAULT 'bank' NOT NULL",
        "ALTER TABLE loans ADD COLUMN lender_wallet_address TEXT",
        "ALTER TABLE loans ADD COLUMN treasury_nation_id INTEGER",
        # Shop approval workflow (Phase 2D)
        # Default 'approved' so existing shops are grandfathered as live.
        "ALTER TABLE shops ADD COLUMN status TEXT DEFAULT 'approved'",
        "ALTER TABLE shops ADD COLUMN approved_by INTEGER",
        "ALTER TABLE shops ADD COLUMN approved_at TEXT",
        "ALTER TABLE shops ADD COLUMN rejected_reason TEXT",
        # Per-shop GDP contribution (Phase 2E)
        "ALTER TABLE shops ADD COLUMN gdp_contribution_30d INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE shops ADD COLUMN gdp_last_calculated DATETIME",
        # Resource depot subtype (Phase 2F)
        "ALTER TABLE shops ADD COLUMN shop_type TEXT DEFAULT 'general'",
        "ALTER TABLE shops ADD COLUMN mining_setup TEXT",
        # Stock closure (Phase 2G)
        "ALTER TABLE stocks ADD COLUMN closed_at DATETIME",
        "ALTER TABLE stocks ADD COLUMN closure_reason TEXT",
        # Wallet health metrics (Phase 2H)
        "ALTER TABLE users ADD COLUMN transaction_count_lifetime INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE users ADD COLUMN transaction_count_30d INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE users ADD COLUMN volume_lifetime INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE users ADD COLUMN volume_30d INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE users ADD COLUMN wallet_health_last_calculated DATETIME",
        # Idle-wallet demurrage (Phase 2I)
        "ALTER TABLE nations ADD COLUMN demurrage_enabled BOOLEAN DEFAULT 0 NOT NULL",
        "ALTER TABLE nations ADD COLUMN demurrage_rate_bps INTEGER DEFAULT 50 NOT NULL",
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists

    # Backfill cap_amount = principal for any existing loan rows where
    # cap_amount is still 0 (i.e. created before Phase 2A).  Without this,
    # the accrual job would skip them due to the cap_amount<=0 guard.
    try:
        conn.execute(
            "UPDATE loans SET cap_amount = principal "
            "WHERE cap_amount = 0 AND principal > 0"
        )
    except sqlite3.OperationalError:
        pass

    # Phase 2B backfill: existing LoanPayment rows recorded before the
    # principal/interest split was a thing — treat them as 100% principal so
    # historical analytics queries don't see zero-volume rows.
    try:
        conn.execute(
            "UPDATE loan_payments SET principal_portion = amount "
            "WHERE principal_portion = 0 AND interest_portion = 0 AND amount > 0"
        )
    except sqlite3.OperationalError:
        pass

    # Phase 2C backfill: pre-treasury-lending loan rows are all bank loans.
    # Set lender_type to 'bank' and denormalize lender_wallet_address from
    # the linked banks row so pay_loan can route payments uniformly.
    try:
        conn.execute(
            "UPDATE loans SET lender_type = 'bank' "
            "WHERE lender_type IS NULL OR lender_type = ''"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "UPDATE loans "
            "SET lender_wallet_address = ("
            "  SELECT wallet_address FROM banks WHERE banks.id = loans.bank_id"
            ") "
            "WHERE lender_wallet_address IS NULL AND bank_id > 0"
        )
    except sqlite3.OperationalError:
        pass

    # Phase 2D backfill: existing shops created before the approval workflow
    # are grandfathered as 'approved' so they remain live immediately.
    try:
        conn.execute(
            "UPDATE shops SET status = 'approved' WHERE status IS NULL"
        )
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Startup event
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    """Run once when the application starts."""

    # 1. Ensure the data directory exists
    os.makedirs("data", exist_ok=True)

    # 2. Create all database tables
    init_db()

    # 2b. Lightweight schema migration — add columns that create_all won't add
    #     to existing tables.  Each ALTER is idempotent (duplicate column is ignored).
    _run_schema_migrations()

    # 3. Seed the World Mint admin user if it does not already exist
    db = SessionLocal()
    try:
        # Check by username first (handles rename from HVN- to TRV- prefix)
        existing_admin = (
            db.query(User)
            .filter(
                (User.wallet_address == settings.WORLD_MINT_ADDRESS)
                | (User.username == "admin")
            )
            .first()
        )
        # If admin exists but has old wallet prefix, update it
        if existing_admin and existing_admin.wallet_address != settings.WORLD_MINT_ADDRESS:
            existing_admin.wallet_address = settings.WORLD_MINT_ADDRESS
            db.commit()
        if existing_admin is None:
            hashed_pw = bcrypt.hashpw("changeme".encode(), bcrypt.gensalt()).decode()
            admin_user = User(
                username="admin",
                password_hash=hashed_pw,
                wallet_address=settings.WORLD_MINT_ADDRESS,
                role="world_mint",
                display_name="World Mint",
                balance=0,
            )
            db.add(admin_user)
            db.commit()

        # 4. Create genesis block if the transactions table is empty
        create_genesis_block(db)

        # 5. Seed default GlobalSettings if the table is empty
        existing_settings = db.query(GlobalSettings).first()
        if existing_settings is None:
            default_settings = GlobalSettings(
                id=1,
                burn_rate_bps=1000,            # 10% burn on principal portion
                interest_rate_cap_bps=2000,    # 20% annual interest cap
                interest_burn_rate_bps=8000,   # 80% burn on interest portion (Phase 2B 20/80)
            )
            db.add(default_settings)
            db.commit()

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Background scheduler — GDP and stock price recalculation every 24 hours
# ---------------------------------------------------------------------------
from app.demurrage import apply_all_demurrage
from app.gdp import recalculate_all_gdp
from app.interest import accrue_daily_interest
from app.valuation import recalculate_all_prices
from app.wallet_health import recalculate_wallet_health

scheduler = BackgroundScheduler()


def _scheduled_gdp_recalc() -> None:
    """Recalculate GDP scores for all approved nations.  Uses its own DB session."""
    db = SessionLocal()
    try:
        recalculate_all_gdp(db)
    finally:
        db.close()


def _scheduled_stock_recalc() -> None:
    """Recalculate stock prices for all active stocks.  Uses its own DB session."""
    db = SessionLocal()
    try:
        recalculate_all_prices(db)
    finally:
        db.close()


def _scheduled_interest_accrual() -> None:
    """Apply daily interest to every active, non-frozen loan."""
    db = SessionLocal()
    try:
        accrue_daily_interest(db)
    finally:
        db.close()


def _scheduled_wallet_health_recalc() -> None:
    """Reconcile wallet-health metrics & decay 30-day counters past their window."""
    db = SessionLocal()
    try:
        recalculate_wallet_health(db)
    finally:
        db.close()


def _scheduled_demurrage() -> None:
    """Apply idle-wallet demurrage for all nations that have it enabled."""
    db = SessionLocal()
    try:
        apply_all_demurrage(db)
    finally:
        db.close()


# Add jobs: run every 24 hours (86400 seconds)
scheduler.add_job(_scheduled_gdp_recalc, "interval", hours=24, id="gdp_recalc")
scheduler.add_job(_scheduled_stock_recalc, "interval", hours=24, id="stock_recalc")
scheduler.add_job(_scheduled_interest_accrual, "interval", hours=24, id="interest_accrual")
scheduler.add_job(
    _scheduled_wallet_health_recalc, "interval", hours=24, id="wallet_health_recalc"
)
scheduler.add_job(
    _scheduled_demurrage, "interval", hours=24, id="demurrage"
)


@app.on_event("startup")
def start_scheduler() -> None:
    """Start the background scheduler when the app comes up."""
    scheduler.start()


@app.on_event("shutdown")
def stop_scheduler() -> None:
    """Gracefully shut down the background scheduler."""
    scheduler.shutdown(wait=False)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
def health_check() -> dict:
    """Simple health-check endpoint."""
    return {"status": "ok", "service": "Travelers Exchange"}
