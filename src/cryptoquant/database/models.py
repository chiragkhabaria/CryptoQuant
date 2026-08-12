"""
SQLAlchemy Database Models

Defines the database schema for CryptoQuant platform using SQLAlchemy ORM.
Compatible with Azure SQL and other SQL databases.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Asset(Base):
    """
    Cryptocurrency assets table.

    Stores information about individual cryptocurrencies (BTC, ETH, etc.)
    """

    __tablename__ = "assets"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String(50), nullable=True, index=True, comment="Sample product ID where this asset appears")
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    display_symbol = Column(String(20), nullable=True)
    asset_type = Column(String(20), nullable=False, default="cryptocurrency")
    decimals = Column(Integer, nullable=False, default=8)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    base_pairs = relationship("TradingPair", foreign_keys="[TradingPair.base_asset_id]", back_populates="base_asset")
    quote_pairs = relationship("TradingPair", foreign_keys="[TradingPair.quote_asset_id]", back_populates="quote_asset")

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, symbol='{self.symbol}', name='{self.name}')>"


class TradingPair(Base):
    """
    Trading pairs table.

    Represents tradeable pairs (e.g., BTC-USD) on exchanges.
    Matches Coinbase Product API structure.
    """

    __tablename__ = "trading_pairs"
    __table_args__ = {"schema": "crypto"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    base_asset_id = Column(Integer, ForeignKey("crypto.assets.id"), nullable=False)
    quote_asset_id = Column(Integer, ForeignKey("crypto.assets.id"), nullable=False)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="online")
    trading_disabled = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=True, index=True)
    
    # Order size constraints from Coinbase Product API
    base_increment = Column(Numeric(18, 8), nullable=True)
    quote_increment = Column(Numeric(18, 8), nullable=True)
    base_min_size = Column(Numeric(18, 8), nullable=True)
    base_max_size = Column(Numeric(18, 8), nullable=True)
    quote_min_size = Column(Numeric(18, 8), nullable=True)
    quote_max_size = Column(Numeric(18, 8), nullable=True)
    
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    base_asset = relationship("Asset", foreign_keys=[base_asset_id], back_populates="base_pairs")
    quote_asset = relationship("Asset", foreign_keys=[quote_asset_id], back_populates="quote_pairs")
    market_prices = relationship("MarketPrice", back_populates="trading_pair", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<TradingPair(id={self.id}, symbol='{self.symbol}')>"


class MarketPrice(Base):
    """
    Market price time-series data (OHLCV).

    Stores historical price and volume data for trading pairs.
    """

    __tablename__ = "market_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trading_pair_id = Column(Integer, ForeignKey("crypto.trading_pairs.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Numeric(18, 8), nullable=False)
    high = Column(Numeric(18, 8), nullable=False)
    low = Column(Numeric(18, 8), nullable=False)
    close = Column(Numeric(18, 8), nullable=False)
    volume = Column(Numeric(18, 8), nullable=False)
    data_source = Column(String(50), nullable=False, default="coinbase")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    trading_pair = relationship("TradingPair", back_populates="market_prices")

    # Composite unique constraint to prevent duplicate data
    __table_args__ = (
        UniqueConstraint("trading_pair_id", "timestamp", name="uq_market_price_pair_timestamp"),
        Index("ix_market_prices_pair_time", "trading_pair_id", "timestamp"),
        Index("ix_market_prices_timestamp_desc", "timestamp"),
        {"schema": "crypto"},
    )

    def __repr__(self) -> str:
        return f"<MarketPrice(id={self.id}, pair_id={self.trading_pair_id}, timestamp={self.timestamp}, close={self.close})>"
