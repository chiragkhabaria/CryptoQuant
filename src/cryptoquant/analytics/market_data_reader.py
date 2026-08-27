"""
Market Data Reader

Queries OHLCV candle data from crypto.market_prices with proper time windows
to support technical indicator calculations.

Key principle: NO LOOK-AHEAD BIAS
- When calculating for timestamp T, only return data up to and including T
- Never return data from the future
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from cryptoquant.database.models import MarketPrice

logger = logging.getLogger(__name__)


def get_candles_for_calculation(
    session: Session,
    trading_pair_id: int,
    target_timestamp: datetime,
    lookback_periods: int,
    granularity: str = "hourly"
) -> List[MarketPrice]:
    """
    Fetch candles needed for indicator calculation at a specific timestamp.
    
    This function enforces NO LOOK-AHEAD: only returns data up to target_timestamp.
    
    Args:
        session: SQLAlchemy session
        trading_pair_id: Trading pair to query
        target_timestamp: The candle timestamp to calculate indicators FOR
        lookback_periods: Number of historical candles needed (e.g., 200 for EMA 200)
        granularity: Candle interval ('hourly', 'daily', etc.)
        
    Returns:
        List of MarketPrice objects ordered oldest→newest, ending at target_timestamp.
        Returns empty list if insufficient data.
        
    Example:
        # Calculate EMA 200 for BTC-USD at 2026-08-24 10:00
        candles = get_candles_for_calculation(
            session,
            trading_pair_id=1,
            target_timestamp=datetime(2026, 8, 24, 10, 0),
            lookback_periods=200
        )
        # Returns up to 200 hourly candles ending at 2026-08-24 10:00
    """
    try:
        # Query candles up to and including target_timestamp
        candles = (
            session.query(MarketPrice)
            .filter(MarketPrice.trading_pair_id == trading_pair_id)
            .filter(MarketPrice.timestamp <= target_timestamp)
            .order_by(MarketPrice.timestamp.desc())
            .limit(lookback_periods)
            .all()
        )
        
        # Reverse to get oldest→newest order (required for indicator calculations)
        candles.reverse()
        
        logger.debug(
            "Fetched %d candles for pair_id=%d up to %s (requested %d)",
            len(candles),
            trading_pair_id,
            target_timestamp,
            lookback_periods
        )
        
        return candles
        
    except Exception as e:
        logger.error(
            "Error fetching candles for pair_id=%d at %s: %s",
            trading_pair_id,
            target_timestamp,
            e
        )
        return []


def get_candles_range(
    session: Session,
    trading_pair_id: int,
    start_timestamp: datetime,
    end_timestamp: datetime
) -> List[MarketPrice]:
    """
    Fetch all candles in a date range (for historical backfill).
    
    Args:
        session: SQLAlchemy session
        trading_pair_id: Trading pair to query
        start_timestamp: Inclusive start of range
        end_timestamp: Inclusive end of range
        
    Returns:
        List of MarketPrice objects ordered oldest→newest
        
    Example:
        # Get all BTC-USD candles for August 2026
        candles = get_candles_range(
            session,
            trading_pair_id=1,
            start_timestamp=datetime(2026, 8, 1),
            end_timestamp=datetime(2026, 8, 31, 23, 59)
        )
    """
    try:
        candles = (
            session.query(MarketPrice)
            .filter(MarketPrice.trading_pair_id == trading_pair_id)
            .filter(MarketPrice.timestamp >= start_timestamp)
            .filter(MarketPrice.timestamp <= end_timestamp)
            .order_by(MarketPrice.timestamp.asc())
            .all()
        )
        
        logger.info(
            "Fetched %d candles for pair_id=%d from %s to %s",
            len(candles),
            trading_pair_id,
            start_timestamp,
            end_timestamp
        )
        
        return candles
        
    except Exception as e:
        logger.error(
            "Error fetching candle range for pair_id=%d: %s",
            trading_pair_id,
            e
        )
        return []


def get_last_analysis_timestamp(
    session: Session,
    trading_pair_id: int
) -> Optional[datetime]:
    """
    Get the most recent timestamp with technical analysis for a trading pair.
    
    Used for incremental processing: determines where to resume calculations.
    
    Args:
        session: SQLAlchemy session
        trading_pair_id: Trading pair to query
        
    Returns:
        Most recent timestamp with analysis as timezone-aware UTC datetime,
        or None if no analysis exists
        
    Example:
        last_time = get_last_analysis_timestamp(session, trading_pair_id=1)
        if last_time:
            # Resume from next candle after last_time
            start = last_time + timedelta(hours=1)
        else:
            # No previous analysis, start from 7 days ago
            start = now - timedelta(days=7)
    """
    from cryptoquant.database.models import TechnicalAnalysis
    
    try:
        from sqlalchemy import func
        
        result = (
            session.query(func.max(TechnicalAnalysis.timestamp))
            .filter(TechnicalAnalysis.trading_pair_id == trading_pair_id)
            .scalar()
        )
        
        # Ensure result is timezone-aware (database returns naive datetime)
        if result is not None:
            result = result.replace(tzinfo=timezone.utc)
        
        if result:
            logger.debug(
                "Last analysis timestamp for pair_id=%d: %s",
                trading_pair_id,
                result
            )
        
        return result
        
    except Exception as e:
        logger.error(
            "Error getting last analysis timestamp for pair_id=%d: %s",
            trading_pair_id,
            e
        )
        return None


def has_sufficient_data(
    candles: List[MarketPrice],
    required_periods: int
) -> bool:
    """
    Check if we have sufficient candles for indicator calculation.
    
    Args:
        candles: List of candles to validate
        required_periods: Minimum candles needed (e.g., 200 for EMA 200)
        
    Returns:
        True if sufficient data, False otherwise
        
    Example:
        candles = get_candles_for_calculation(...)
        if has_sufficient_data(candles, required_periods=200):
            ema = calculate_ema(candles, period=200)
        else:
            logger.warning("Insufficient data for EMA 200")
    """
    sufficient = len(candles) >= required_periods
    
    if not sufficient:
        logger.debug(
            "Insufficient data: %d candles < %d required",
            len(candles),
            required_periods
        )
    
    return sufficient
