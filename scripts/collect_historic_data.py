#!/usr/bin/env python
"""
Historic Market Data Ingestion Script

Fetches historical OHLCV (Open, High, Low, Close, Volume) data from Coinbase API
for tracked trading pairs and stores it in the crypto.market_prices table.

Usage:
    python scripts/collect_historic_data.py --granularity daily --days 1095
    python scripts/collect_historic_data.py --granularity hourly --days 90
    python scripts/collect_historic_data.py --product-id BTC-USD --days 7
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
import logging

import click
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cryptoquant.collectors.coinbase_client import CoinbaseClient, CandleGranularity
from cryptoquant.database.session import get_session
from cryptoquant.database.models import TradingPair, TrackedPair, MarketPrice


# Setup logging
def setup_logging(log_file: Optional[str] = None):
    """Configure logging to console and file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    if log_file is None:
        log_file = log_dir / f"historic_ingestion_{timestamp}.log"
    
    # Configure handlers with UTF-8 encoding to support Unicode characters
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)
    
    # Set UTF-8 encoding for console output on Windows
    if hasattr(stream_handler.stream, 'reconfigure'):
        stream_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[file_handler, stream_handler]
    )
    return logging.getLogger(__name__)


# Granularity mapping
GRANULARITY_MAP = {
    "minute": CandleGranularity.ONE_MINUTE,
    "five_minute": CandleGranularity.FIVE_MINUTE,
    "fifteen_minute": CandleGranularity.FIFTEEN_MINUTE,
    "thirty_minute": CandleGranularity.THIRTY_MINUTE,
    "hourly": CandleGranularity.ONE_HOUR,
    "two_hour": CandleGranularity.TWO_HOUR,
    "six_hour": CandleGranularity.SIX_HOUR,
    "daily": CandleGranularity.ONE_DAY,
}


def get_tracked_pairs(session, product_id: Optional[str] = None) -> list[tuple[str, int]]:
    """
    Get list of tracked trading pairs to process.
    
    Returns:
        List of (product_id, trading_pair_id) tuples
    """
    if product_id:
        # Fetch specific pair
        pair = (
            session.query(TradingPair.symbol, TradingPair.id)
            .filter(TradingPair.symbol == product_id)
            .first()
        )
        if not pair:
            raise ValueError(f"Trading pair '{product_id}' not found in database")
        return [pair]
    
    # Fetch all active tracked pairs
    tracked = (
        session.query(TradingPair.symbol, TradingPair.id)
        .join(TrackedPair, TradingPair.symbol == TrackedPair.product_id)
        .filter(TrackedPair.is_tracking_active == True)
        .all()
    )
    
    if not tracked:
        raise ValueError("No active tracked pairs found. Enable tracking in crypto.tracked_pairs table.")
    
    return tracked


def fetch_and_store_candles(
    client: CoinbaseClient,
    session,
    product_id: str,
    trading_pair_id: int,
    granularity: CandleGranularity,
    start_date: datetime,
    end_date: datetime,
    logger: logging.Logger
) -> dict:
    """
    Fetch candles from API and store in database.
    
    Returns:
        Dict with stats: {inserted, skipped, errors}
    """
    stats = {"inserted": 0, "skipped": 0, "errors": 0}
    
    try:
        # Fetch candles from Coinbase API
        logger.info(f"Fetching {granularity.value} candles for {product_id} from {start_date.date()} to {end_date.date()}")
        
        candles = client.get_candles(
            product_id=product_id,
            granularity=granularity,
            start=start_date,
            end=end_date
        )
        
        if not candles:
            logger.warning(f"No candles returned for {product_id}")
            return stats
        
        logger.info(f"Fetched {len(candles)} candles for {product_id}")
        
        # Insert candles in batches
        batch_size = 100
        for i in range(0, len(candles), batch_size):
            batch = candles[i:i+batch_size]
            
            for candle in batch:
                try:
                    market_price = MarketPrice(
                        trading_pair_id=trading_pair_id,
                        timestamp=candle.start,
                        open=Decimal(str(candle.open)),
                        high=Decimal(str(candle.high)),
                        low=Decimal(str(candle.low)),
                        close=Decimal(str(candle.close)),
                        volume=Decimal(str(candle.volume)),
                        data_source="coinbase"
                    )
                    session.add(market_price)
                    stats["inserted"] += 1
                    
                except IntegrityError:
                    # Duplicate timestamp - skip
                    session.rollback()
                    stats["skipped"] += 1
                except Exception as e:
                    logger.error(f"Error inserting candle for {product_id} at {candle.start}: {e}")
                    session.rollback()
                    stats["errors"] += 1
            
            # Commit batch
            try:
                session.commit()
            except Exception as e:
                logger.error(f"Error committing batch for {product_id}: {e}")
                session.rollback()
                stats["errors"] += len(batch) - stats["skipped"]
        
        logger.info(f"Completed {product_id}: {stats['inserted']} inserted, {stats['skipped']} skipped, {stats['errors']} errors")
        
    except Exception as e:
        logger.error(f"Error fetching candles for {product_id}: {e}")
        stats["errors"] += 1
    
    return stats


@click.command()
@click.option(
    "--granularity",
    type=click.Choice(list(GRANULARITY_MAP.keys()), case_sensitive=False),
    default="daily",
    help="Candle granularity (default: daily)"
)
@click.option(
    "--days",
    type=int,
    default=None,
    help="Number of days of history to fetch (e.g., 1095 for 3 years)"
)
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Start date (YYYY-MM-DD format)"
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="End date (YYYY-MM-DD format, default: today)"
)
@click.option(
    "--product-id",
    type=str,
    default=None,
    help="Specific trading pair to process (e.g., BTC-USD). If not provided, processes all active tracked pairs."
)
@click.option(
    "--log-file",
    type=str,
    default=None,
    help="Custom log file path (default: logs/historic_ingestion_{timestamp}.log)"
)
def main(
    granularity: str,
    days: Optional[int],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    product_id: Optional[str],
    log_file: Optional[str]
):
    """
    Fetch historical OHLCV data from Coinbase API for tracked trading pairs.
    
    Examples:
    
        # Load 3 years of daily data for all tracked pairs
        python scripts/collect_historic_data.py --granularity daily --days 1095
        
        # Load 90 days of hourly data
        python scripts/collect_historic_data.py --granularity hourly --days 90
        
        # Load specific date range for BTC-USD
        python scripts/collect_historic_data.py --product-id BTC-USD --start-date 2023-01-01 --end-date 2023-12-31
        
        # Test with last 7 days for one pair
        python scripts/collect_historic_data.py --product-id BTC-USD --days 7
    """
    # Setup logging
    logger = setup_logging(log_file)
    logger.info("=" * 80)
    logger.info("Historic Data Ingestion Started")
    logger.info("=" * 80)
    
    # Validate date parameters
    if days and (start_date or end_date):
        logger.error("Cannot specify both --days and --start-date/--end-date")
        sys.exit(1)
    
    # Calculate date range
    if not end_date:
        end_date = datetime.now(timezone.utc)
    else:
        end_date = end_date.replace(tzinfo=timezone.utc)
    
    if days:
        start_date = end_date - timedelta(days=days)
    elif not start_date:
        logger.error("Must specify either --days or --start-date")
        sys.exit(1)
    else:
        start_date = start_date.replace(tzinfo=timezone.utc)
    
    # Get granularity
    candle_granularity = GRANULARITY_MAP[granularity.lower()]
    
    logger.info(f"Configuration:")
    logger.info(f"  Granularity: {granularity} ({candle_granularity.value})")
    logger.info(f"  Date Range: {start_date.date()} to {end_date.date()}")
    logger.info(f"  Product ID: {product_id or 'All active tracked pairs'}")
    
    # Initialize client and session
    try:
        client = CoinbaseClient()
        session = get_session()
        logger.info("✅ Coinbase client and database session initialized")
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        sys.exit(1)
    
    # Get tracked pairs to process
    try:
        tracked_pairs = get_tracked_pairs(session, product_id)
        logger.info(f"Found {len(tracked_pairs)} pair(s) to process")
    except Exception as e:
        logger.error(f"Error getting tracked pairs: {e}")
        sys.exit(1)
    
    # Process each pair
    total_stats = {"inserted": 0, "skipped": 0, "errors": 0}
    
    with tqdm(total=len(tracked_pairs), desc="Processing pairs") as pbar:
        for pair_symbol, pair_id in tracked_pairs:
            pbar.set_description(f"Processing {pair_symbol}")
            
            stats = fetch_and_store_candles(
                client=client,
                session=session,
                product_id=pair_symbol,
                trading_pair_id=pair_id,
                granularity=candle_granularity,
                start_date=start_date,
                end_date=end_date,
                logger=logger
            )
            
            # Update totals
            for key in total_stats:
                total_stats[key] += stats[key]
            
            pbar.update(1)
    
    # Final summary
    session.close()
    logger.info("=" * 80)
    logger.info("Historic Data Ingestion Completed")
    logger.info(f"Total Records Inserted: {total_stats['inserted']}")
    logger.info(f"Total Records Skipped (duplicates): {total_stats['skipped']}")
    logger.info(f"Total Errors: {total_stats['errors']}")
    logger.info("=" * 80)
    
    if total_stats["errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
