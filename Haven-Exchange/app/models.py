"""
Haven Economy — SQLAlchemy ORM Models

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
  - Sessions
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
