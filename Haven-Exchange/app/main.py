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

from app.blockchain import create_genesis_block
from app.config import settings
from app.database import SessionLocal, init_db
from app.models import GdpSnapshot, User  # noqa: F401  — ensures models are registered with Base
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
    ]
    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # column already exists
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

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
def health_check() -> dict:
    """Simple health-check endpoint."""
    return {"status": "ok", "service": "Travelers Exchange"}
