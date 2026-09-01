"""
Backfill module for filling specific data gaps.

This module provides smart backfilling capabilities that only fetch
and insert data for specific gaps rather than re-ingesting entire periods.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from cryptoquant.collectors.coinbase_client import CandleGranularity, CoinbaseClient
from cryptoquant.database.session import get_session
from cryptoquant.ingestion.historic import (
    fetch_and_store_candles,
    get_tracked_pairs,
    GRANULARITY_MAP,
)

logger = logging.getLogger(__name__)


def backfill_candle_gap(
    product_id: str,
    start_date: datetime,
    end_date: datetime,
    granularity: str = "hourly",
) -> dict:
    """
    Fill a specific gap in market price data.
    
    Args:
        product_id: Trading pair symbol (e.g., "BTC-USD")
        start_date: Start of gap (inclusive, UTC timezone-aware)
        end_date: End of gap (inclusive, UTC timezone-aware)
        granularity: Candle interval (default: "hourly")
    
    Returns:
        Dictionary with statistics: inserted, skipped, errors
    """
    log = logger
    log.info("=" * 80)
    log.info("BACKFILL: Filling gap for %s", product_id)
    log.info("Gap period: %s to %s", start_date, end_date)
    log.info("=" * 80)
    
    # Validate timezone
    if start_date.tzinfo is None or end_date.tzinfo is None:
        raise ValueError("start_date and end_date must be timezone-aware (UTC)")
    
    # Get granularity enum
    if granularity not in GRANULARITY_MAP:
        raise ValueError(f"Invalid granularity: {granularity}")
    
    granularity_enum = GRANULARITY_MAP[granularity]
    
    # Initialize client and session
    client = CoinbaseClient()
    session = get_session()
    
    try:
        # Get trading pair info
        pairs = get_tracked_pairs(session, product_id=product_id)
        if not pairs:
            raise ValueError(f"Trading pair {product_id} not found")
        
        symbol, trading_pair_id = pairs[0]
        
        # Fetch and store candles for this specific gap
        stats = fetch_and_store_candles(
            client=client,
            session=session,
            product_id=symbol,
            trading_pair_id=trading_pair_id,
            granularity=granularity_enum,
            start_date=start_date,
            end_date=end_date,
            log=log,
        )
        
        log.info("=" * 80)
        log.info("BACKFILL COMPLETE: %s", product_id)
        log.info("Inserted: %d, Skipped: %d, Errors: %d", 
                stats["inserted"], stats["skipped"], stats["errors"])
        log.info("=" * 80)
        
        return stats
        
    finally:
        session.close()


def backfill_multiple_gaps(gaps: list[dict], granularity: str = "hourly") -> dict:
    """
    Fill multiple gaps in sequence.
    
    Args:
        gaps: List of gap dictionaries with keys:
              - product_id: Trading pair symbol
              - start_date: Gap start (UTC timezone-aware)
              - end_date: Gap end (UTC timezone-aware)
        granularity: Candle interval (default: "hourly")
    
    Returns:
        Dictionary with aggregate statistics
    """
    log = logger
    total_stats = {"inserted": 0, "skipped": 0, "errors": 0}
    
    log.info("=" * 80)
    log.info("BACKFILL: Processing %d gap(s)", len(gaps))
    log.info("=" * 80)
    
    for idx, gap in enumerate(gaps, 1):
        log.info("\n[%d/%d] Processing gap for %s", idx, len(gaps), gap["product_id"])
        
        try:
            stats = backfill_candle_gap(
                product_id=gap["product_id"],
                start_date=gap["start_date"],
                end_date=gap["end_date"],
                granularity=granularity,
            )
            
            total_stats["inserted"] += stats["inserted"]
            total_stats["skipped"] += stats["skipped"]
            total_stats["errors"] += stats["errors"]
            
        except Exception as exc:
            log.error("Failed to backfill gap for %s: %s", gap["product_id"], exc)
            total_stats["errors"] += 1
    
    log.info("\n" + "=" * 80)
    log.info("BACKFILL BATCH COMPLETE")
    log.info("Total Inserted: %d", total_stats["inserted"])
    log.info("Total Skipped: %d", total_stats["skipped"])
    log.info("Total Errors: %d", total_stats["errors"])
    log.info("=" * 80)
    
    return total_stats
