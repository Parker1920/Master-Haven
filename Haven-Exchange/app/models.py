"""
Travelers Exchange — SQLAlchemy ORM Models

Defines all core tables:
  - Users
  - Nations
  - Transactions
  - MintAllocations
  - Shops
  - ShopListings
  - Stocks
  - StockHoldings
  - StockTransactions
  - StockValuations
  - GdpSnapshots
  - Sessions
  - GlobalSettings
  - Banks
  - Loans
  - LoanPayments
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """A registered user / citizen / nation leader / world mint operator."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    wallet_address: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    nation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nations.id"), nullable=True
    )
    role: Mapped[str] = mapped_column(String, default="citizen")
    balance: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )
    last_active: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    nation: Mapped[Optional["Nation"]] = relationship(
        "Nation",
        foreign_keys=[nation_id],
        back_populates="members",
    )
    sessions: Mapped[List["Session_"]] = relationship(
        "Session_", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', wallet='{self.wallet_address}')>"


class Nation(Base):
    """A gaming nation / guild that participates in the economy."""

    __tablename__ = "nations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    leader_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    treasury_address: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    treasury_balance: Mapped[int] = mapped_column(Integer, default=0)
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discord_invite: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    game: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # National currency
    currency_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "Voyager Credits"
    currency_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # "VGC"

    # GDP — drives exchange rate multiplier
    gdp_score: Mapped[int] = mapped_column(Integer, default=50)           # composite 0-100
    gdp_multiplier: Mapped[int] = mapped_column(Integer, default=100)     # stored as int x100 (100 = 1.00x)
    gdp_last_calculated: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    leader: Mapped["User"] = relationship(
        "User",
        foreign_keys=[leader_id],
        backref="led_nations",
    )
    members: Mapped[List["User"]] = relationship(
        "User",
        foreign_keys=[User.nation_id],
        back_populates="nation",
    )
    mint_allocations: Mapped[List["MintAllocation"]] = relationship(
        "MintAllocation", back_populates="nation", cascade="all, delete-orphan"
    )
    gdp_snapshots: Mapped[List["GdpSnapshot"]] = relationship(
        "GdpSnapshot", back_populates="nation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Nation(id={self.id}, name='{self.name}', status='{self.status}')>"


class Transaction(Base):
    """An immutable ledger entry representing a currency movement."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tx_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    prev_hash: Mapped[str] = mapped_column(String, nullable=False)
    tx_type: Mapped[str] = mapped_column(String, nullable=False)
    from_address: Mapped[str] = mapped_column(String, nullable=False)
    to_address: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    fee: Mapped[int] = mapped_column(Integer, default=0)
    memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    nonce: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, type='{self.tx_type}', "
            f"amount={self.amount}, hash='{self.tx_hash[:12]}...')>"
        )


class MintAllocation(Base):
    """A monthly minting allocation for a nation based on active members."""

    __tablename__ = "mint_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nations.id"), nullable=False
    )
    period: Mapped[str] = mapped_column(String, nullable=False)  # "2026-03" format
    member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    base_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    calculated_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    approved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    distributed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    nation: Mapped["Nation"] = relationship("Nation", back_populates="mint_allocations")

    def __repr__(self) -> str:
        return (
            f"<MintAllocation(id={self.id}, nation_id={self.nation_id}, "
            f"period='{self.period}', status='{self.status}')>"
        )


class Shop(Base):
    """A player-owned shop attached to a nation."""

    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, unique=True
    )
    nation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    total_sales: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User", foreign_keys=[owner_id], backref="shop"
    )
    nation: Mapped["Nation"] = relationship(
        "Nation", foreign_keys=[nation_id], backref="shops"
    )
    listings: Mapped[List["ShopListing"]] = relationship(
        "ShopListing", back_populates="shop", cascade="all, delete-orphan"
    )


class ShopListing(Base):
    """A single listing (product / service) within a shop."""

    __tablename__ = "shop_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shops.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, default="other")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    shop: Mapped["Shop"] = relationship("Shop", back_populates="listings")


class Stock(Base):
    """A tradeable stock representing a nation or business."""

    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    stock_type: Mapped[str] = mapped_column(String, nullable=False)  # 'nation' or 'business'
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)  # nation_id or shop_id
    total_shares: Mapped[int] = mapped_column(Integer, nullable=False)
    available_shares: Mapped[int] = mapped_column(Integer, nullable=False)
    current_price: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_valued_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    holdings: Mapped[List["StockHolding"]] = relationship(
        "StockHolding", back_populates="stock", cascade="all, delete-orphan"
    )
    stock_transactions: Mapped[List["StockTransaction"]] = relationship(
        "StockTransaction", back_populates="stock", cascade="all, delete-orphan"
    )
    valuations: Mapped[List["StockValuation"]] = relationship(
        "StockValuation", back_populates="stock", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Stock(id={self.id}, ticker='{self.ticker}', price={self.current_price})>"


class StockHolding(Base):
    """A user's holding of shares in a specific stock."""

    __tablename__ = "stock_holdings"
    __table_args__ = (
        UniqueConstraint("user_id", "stock_id", name="uq_user_stock"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    stock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocks.id"), nullable=False
    )
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_buy_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acquired_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], backref="stock_holdings")
    stock: Mapped["Stock"] = relationship("Stock", back_populates="holdings")

    def __repr__(self) -> str:
        return f"<StockHolding(user_id={self.user_id}, stock='{self.stock_id}', shares={self.shares})>"


class StockTransaction(Base):
    """A record of a stock trade (buy, sell, or IPO)."""

    __tablename__ = "stock_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocks.id"), nullable=False
    )
    buyer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    seller_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_share: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    tx_type: Mapped[str] = mapped_column(String, nullable=False)  # 'BUY', 'SELL', 'IPO'
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    stock: Mapped["Stock"] = relationship("Stock", back_populates="stock_transactions")
    buyer: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[buyer_id], backref="stock_purchases"
    )
    seller: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[seller_id], backref="stock_sales"
    )

    def __repr__(self) -> str:
        return (
            f"<StockTransaction(id={self.id}, type='{self.tx_type}', "
            f"shares={self.shares}, total={self.total_cost})>"
        )


class StockValuation(Base):
    """A daily snapshot of a stock's valuation scores and price."""

    __tablename__ = "stock_valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("stocks.id"), nullable=False
    )
    population_score: Mapped[int] = mapped_column(Integer, default=0)
    activity_score: Mapped[int] = mapped_column(Integer, default=0)
    cashflow_score: Mapped[int] = mapped_column(Integer, default=0)
    composite_score: Mapped[int] = mapped_column(Integer, default=0)
    calculated_price: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_date: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    stock: Mapped["Stock"] = relationship("Stock", back_populates="valuations")

    def __repr__(self) -> str:
        return (
            f"<StockValuation(stock_id={self.stock_id}, date='{self.snapshot_date}', "
            f"price={self.calculated_price})>"
        )


class GdpSnapshot(Base):
    """A daily snapshot of a nation's GDP pillar scores and multiplier."""

    __tablename__ = "gdp_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nations.id"), nullable=False
    )
    treasury_score: Mapped[int] = mapped_column(Integer, default=0)
    activity_score: Mapped[int] = mapped_column(Integer, default=0)
    revenue_score: Mapped[int] = mapped_column(Integer, default=0)
    citizens_score: Mapped[int] = mapped_column(Integer, default=0)
    composite_score: Mapped[int] = mapped_column(Integer, default=0)
    gdp_multiplier: Mapped[int] = mapped_column(Integer, default=100)  # x100
    snapshot_date: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    nation: Mapped["Nation"] = relationship("Nation", back_populates="gdp_snapshots")

    def __repr__(self) -> str:
        return (
            f"<GdpSnapshot(nation_id={self.nation_id}, date='{self.snapshot_date}', "
            f"multiplier={self.gdp_multiplier})>"
        )


class Session_(Base):
    """A user login session identified by a token."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # session token
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session(id='{self.id[:12]}...', user_id={self.user_id})>"


# ---------------------------------------------------------------------------
# Global Settings — singleton row for World Mint config
# ---------------------------------------------------------------------------

class GlobalSettings(Base):
    """Singleton row storing global economy settings controlled by the World Mint."""

    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Phase 2B: total burn pool rate applied against lifetime interest paid
    # on a loan, in basis points (default 1000 = 10%).  Snapshotted into
    # Loan.burn_rate_snapshot at creation.  No portion of principal is
    # burned.
    burn_rate_bps: Mapped[int] = mapped_column(Integer, default=1000)
    # Maximum interest rate banks can charge, in basis points (2000 = 20% annual)
    interest_rate_cap_bps: Mapped[int] = mapped_column(Integer, default=2000)
    # Phase 2B: fraction of the burn pool burned **at loan close**, in
    # basis points (default 8000 = 80%).  The remainder (default 2000 =
    # 20%) is burned during payments.  Snapshotted into
    # Loan.interest_burn_rate_snapshot at creation.
    interest_burn_rate_bps: Mapped[int] = mapped_column(Integer, default=8000, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    def __repr__(self) -> str:
        return (
            f"<GlobalSettings(burn_rate={self.burn_rate_bps}bps, "
            f"interest_cap={self.interest_rate_cap_bps}bps)>"
        )


# ---------------------------------------------------------------------------
# Banking System — Banks, Loans, Loan Payments
# ---------------------------------------------------------------------------

class Bank(Base):
    """A bank within a nation, appointed by the Nation Leader."""

    __tablename__ = "banks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # The nation this bank belongs to
    nation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nations.id"), nullable=False
    )
    # The user appointed as bank operator
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Bank wallet address (format: TRV-BANK-xxxxxxxx)
    wallet_address: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # Current reserves held by the bank
    balance: Mapped[int] = mapped_column(Integer, default=0)
    # Lifetime total amount loaned out
    total_loaned: Mapped[int] = mapped_column(Integer, default=0)
    # Lifetime total amount burned via loan repayments
    total_burned: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    nation: Mapped["Nation"] = relationship(
        "Nation", foreign_keys=[nation_id], backref="banks"
    )
    owner: Mapped["User"] = relationship(
        "User", foreign_keys=[owner_id], backref="operated_banks"
    )
    loans: Mapped[List["Loan"]] = relationship(
        "Loan", back_populates="bank", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Bank(id={self.id}, name='{self.name}', balance={self.balance})>"


class Loan(Base):
    """A loan issued by a bank to a citizen."""

    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Which bank issued the loan.  Phase 2C: 0 is a sentinel meaning
    # "treasury loan" — the actual lender wallet lives on
    # ``lender_wallet_address`` and the nation on ``treasury_nation_id``.
    # We keep this column NOT NULL because ALTERing nullability in SQLite
    # would require a full table rebuild.
    bank_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("banks.id"), nullable=False
    )
    # Phase 2C: discriminator for which kind of entity issued the loan.
    # 'bank' (bank_id > 0, looked up via banks table) or 'treasury'
    # (bank_id == 0, looked up via treasury_nation_id).
    lender_type: Mapped[str] = mapped_column(Text, default="bank", nullable=False)
    # Phase 2C: denormalized wallet address of whichever entity issued the
    # loan.  For 'bank' loans this is bank.wallet_address; for 'treasury'
    # loans this is nation.treasury_address.  Lets payment routing work
    # without a discriminating join.
    lender_wallet_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Phase 2C: nation whose treasury issued the loan, NULL for bank loans.
    treasury_nation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nations.id"), nullable=True
    )
    # The citizen who received the loan
    borrower_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    # Original loan amount
    principal: Mapped[int] = mapped_column(Integer, nullable=False)
    # Principal balance still owed (decreases with each principal-portion payment).
    # Phase 2A: this remains the "principal_remaining" tracker.  Total amount
    # owed by the borrower is (outstanding + accrued_interest).
    outstanding: Mapped[int] = mapped_column(Integer, nullable=False)
    # Interest accrued but not yet paid.  Grows daily via the accrual job,
    # capped at cap_amount.  Decreases when payments are applied to interest
    # portion (Phase 2B).
    accrued_interest: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Lifetime cap on how much interest can ever accrue on this loan, set to
    # the principal at creation time (100% cap rule).  Once cumulative accrued
    # interest reaches this, interest_frozen flips True and no further interest
    # accrues — even on subsequent days.
    cap_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # True once total lifetime interest accrued has hit cap_amount.
    interest_frozen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Timestamp of the most recent accrual run that touched this loan; used by
    # the daily job to compute elapsed days since last accrual.  NULL on a
    # freshly-created loan (initialised to opened_at on first run).
    last_accrual_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    # Interest rate snapshot at loan creation time, in basis points (500 = 5% annual)
    interest_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    # Burn rate snapshot at loan creation, in basis points.  Phase 2B: this
    # is the **total burn pool rate** applied against lifetime interest
    # paid (default 1000 = 10%).  The pool is split 20%/80% during/at-close
    # via ``interest_burn_rate_snapshot``.  Principal repayments are never
    # burned.
    burn_rate_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    # Fraction of the total burn pool burned **at loan close**, in basis
    # points (default 8000 = 80%).  The remainder (10000 − this value,
    # default 2000 = 20%) is burned during payments.
    interest_burn_rate_snapshot: Mapped[int] = mapped_column(Integer, default=8000, nullable=False)
    # Lifetime total of interest_portion across all payments (Phase 2B).
    total_interest_paid: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Lifetime sum of during-payment interest burns (the 20% slice).  Used
    # at loan close to compute the residual close burn pool drained from
    # bank reserves.
    total_burned_during_payments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Amount burned from bank reserves on the closing payment (the 80%
    # slice).  Remains 0 until the loan closes.
    final_close_burn: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Loan lifecycle status: 'active', 'closed', 'defaulted'
    status: Mapped[str] = mapped_column(Text, default="active")
    # Borrower's stated purpose for the loan
    memo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    bank: Mapped["Bank"] = relationship("Bank", back_populates="loans")
    borrower: Mapped["User"] = relationship(
        "User", foreign_keys=[borrower_id], backref="loans"
    )
    # Phase 2C: nation whose treasury issued this loan (NULL for bank loans).
    treasury_nation: Mapped[Optional["Nation"]] = relationship(
        "Nation", foreign_keys=[treasury_nation_id]
    )
    payments: Mapped[List["LoanPayment"]] = relationship(
        "LoanPayment", back_populates="loan", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Loan(id={self.id}, principal={self.principal}, "
            f"outstanding={self.outstanding}, status='{self.status}')>"
        )


class LoanPayment(Base):
    """A single payment made against a loan, with burn split tracking."""

    __tablename__ = "loan_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # The loan this payment applies to
    loan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("loans.id"), nullable=False
    )
    # Total payment amount paid by the borrower (= bank_amount + the
    # during-payment burn).  On the closing payment, the close burn from
    # bank reserves is **not** included here — see Loan.final_close_burn.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Total burned in connection with this payment (during-payment burn +
    # close burn on the final payment).  Phase 2B: only the interest slice
    # is ever burned; principal is never burned.
    burn_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Portion of `amount` that flowed to the bank's reserves
    # (= amount − during-payment burn).
    bank_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # How much of `amount` was applied to accrued interest (interest-first
    # allocation; Phase 2B).  Always <= the loan's accrued_interest at the
    # time of the payment.
    interest_portion: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # How much of `amount` was applied to principal balance.  Equals
    # `amount - interest_portion`.  Persisted (not derived) so historical
    # rows survive future schema changes to amount.
    principal_portion: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # True if this payment closed the loan (zeroed both outstanding and
    # accrued_interest).
    is_final_payment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Outstanding loan balance after this payment.  Phase 2B: this is
    # `principal_remaining + accrued_interest_remaining` so the column
    # reflects total amount still owed.
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # Links to the main LOAN_PAYMENT transaction on the ledger
    tx_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        insert_default=func.current_timestamp()
    )

    # Relationships
    loan: Mapped["Loan"] = relationship("Loan", back_populates="payments")

    def __repr__(self) -> str:
        return (
            f"<LoanPayment(id={self.id}, loan_id={self.loan_id}, "
            f"amount={self.amount}, balance_after={self.balance_after})>"
        )
