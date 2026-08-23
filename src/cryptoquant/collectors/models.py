"""
Coinbase API Data Models

Pydantic models for Coinbase Advanced API responses.
Provides type-safe parsing and validation for API data.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, validator


class CandleGranularity(str, Enum):
    """Supported candle granularities for Coinbase API."""

    ONE_MINUTE = "ONE_MINUTE"
    FIVE_MINUTE = "FIVE_MINUTE"
    FIFTEEN_MINUTE = "FIFTEEN_MINUTE"
    THIRTY_MINUTE = "THIRTY_MINUTE"
    ONE_HOUR = "ONE_HOUR"
    TWO_HOUR = "TWO_HOUR"
    SIX_HOUR = "SIX_HOUR"
    ONE_DAY = "ONE_DAY"


class Product(BaseModel):
    """
    Coinbase product (trading pair) information.

    Represents a tradeable cryptocurrency pair on Coinbase.
    """

    product_id: str = Field(..., description="Unique product identifier (e.g., BTC-USD)")
    base_currency_id: str = Field(..., description="Base currency symbol (e.g., BTC)")
    quote_currency_id: str = Field(..., description="Quote currency symbol (e.g., USD)")
    base_display_symbol: str = Field(..., description="Display symbol for base currency")
    quote_display_symbol: str = Field(..., description="Display symbol for quote currency")
    status: str = Field(..., description="Trading status (online, offline, delisted)")
    trading_disabled: bool = Field(False, description="Whether trading is disabled")
    base_increment: Decimal = Field(..., description="Minimum order size increment")
    quote_increment: Decimal = Field(..., description="Minimum price increment")
    base_min_size: Decimal = Field(..., description="Minimum order size")
    base_max_size: Decimal = Field(..., description="Maximum order size")
    quote_min_size: Optional[Decimal] = Field(None, description="Minimum order value")
    quote_max_size: Optional[Decimal] = Field(None, description="Maximum order value")

    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "BTC-USD",
                "base_currency_id": "BTC",
                "quote_currency_id": "USD",
                "base_display_symbol": "BTC",
                "quote_display_symbol": "USD",
                "status": "online",
                "trading_disabled": False,
                "base_increment": "0.00000001",
                "quote_increment": "0.01",
                "base_min_size": "0.0001",
                "base_max_size": "1000",
            }
        }


class Candle(BaseModel):
    """
    OHLCV candle data from Coinbase.

    Represents a single candlestick with price and volume information.
    """

    start: datetime = Field(..., description="Candle start time")
    low: Decimal = Field(..., description="Lowest price during period")
    high: Decimal = Field(..., description="Highest price during period")
    open: Decimal = Field(..., description="Opening price")
    close: Decimal = Field(..., description="Closing price")
    volume: Decimal = Field(..., description="Trading volume")

    @validator("start", pre=True)
    def parse_timestamp(cls, v: int | str | datetime) -> datetime:
        """Convert Unix timestamp to datetime."""
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            v = int(v)
        # Return timezone-aware datetime in UTC
        from datetime import timezone
        return datetime.fromtimestamp(v, tz=timezone.utc)

    class Config:
        json_schema_extra = {
            "example": {
                "start": 1672531200,
                "low": "16500.50",
                "high": "16750.25",
                "open": "16600.00",
                "close": "16700.00",
                "volume": "125.5",
            }
        }


class ProductsResponse(BaseModel):
    """Response from GET /api/v3/brokerage/products"""

    products: list[Product]
    num_products: int = Field(..., description="Total number of products")


class CandlesResponse(BaseModel):
    """Response from GET /api/v3/brokerage/products/{product_id}/candles"""

    candles: list[Candle]
