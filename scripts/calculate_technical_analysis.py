#!/usr/bin/env python
"""
Technical Analysis Calculation Script

Calculates technical indicators (EMA, RSI, MACD, ATR) for market_prices data
and stores results in the crypto.technical_analysis table.

Usage:
    # Historical backfill (30 days)
    python scripts/calculate_technical_analysis.py --mode historical --days 30
    
    # Historical with specific date range
    python scripts/calculate_technical_analysis.py --mode historical --start 2026-07-01 --end 2026-07-31
    
    # Incremental (process new candles since last calculation)
    python scripts/calculate_technical_analysis.py --mode incremental
    
    # Single trading pair
    python scripts/calculate_technical_analysis.py --mode historical --days 7 --pair BTC-USD
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

import click
from tqdm import tqdm

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cryptoquant.database.session import get_session
from cryptoquant.database.models import TradingPair
from cryptoquant.analytics.analytics_pipeline import (
    run_technical_analysis,
    analyze_all_pairs
)


# Setup logging
def setup_logging(log_file: Optional[str] = None):
    """Configure logging to console and file"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path(__file__).parent.parent / "logs"
        
        # Create log directory
        try:
            log_dir.mkdir(exist_ok=True, parents=True)
        except Exception as e:
            print(f"Warning: Could not create log directory: {e}")
            print("Falling back to console-only logging")
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            return
        
        # Determine log file path
        if log_file:
            log_path = log_dir / log_file
        else:
            log_path = log_dir / f"technical_analysis_{timestamp}.log"
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.FileHandler(log_path, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        logger.info(f"Logging to: {log_path}")
        
    except Exception as e:
        print(f"Error setting up logging: {e}")
        logging.basicConfig(level=logging.INFO)


def get_trading_pair_id(session, symbol: str) -> Optional[int]:
    """Get trading pair ID from symbol"""
    pair = (
        session.query(TradingPair)
        .filter(TradingPair.symbol == symbol)
        .first()
    )
    
    if pair:
        return pair.id
    else:
        logger = logging.getLogger(__name__)
        logger.error(f"Trading pair not found: {symbol}")
        return None


@click.command()
@click.option(
    '--mode',
    type=click.Choice(['historical', 'incremental']),
    required=True,
    help='Analysis mode: historical (backfill) or incremental (new data only)'
)
@click.option(
    '--start',
    type=str,
    help='Start date (YYYY-MM-DD) for historical mode'
)
@click.option(
    '--end',
    type=str,
    help='End date (YYYY-MM-DD) for historical mode'
)
@click.option(
    '--days',
    type=int,
    help='Number of days to backfill (alternative to --start/--end)'
)
@click.option(
    '--pair',
    type=str,
    help='Trading pair symbol (e.g., BTC-USD). If not specified, processes all tracked pairs.'
)
@click.option(
    '--version',
    type=str,
    default='v1',
    help='Calculation version string (default: v1)'
)
@click.option(
    '--log-file',
    type=str,
    help='Log file name (default: technical_analysis_TIMESTAMP.log)'
)
def main(
    mode: str,
    start: Optional[str],
    end: Optional[str],
    days: Optional[int],
    pair: Optional[str],
    version: str,
    log_file: Optional[str]
):
    """
    Calculate technical indicators for market price data.
    
    This script reads OHLCV data from crypto.market_prices and calculates
    technical indicators (EMA, RSI, MACD, ATR), storing results in
    crypto.technical_analysis.
    
    Examples:
        # Backfill last 30 days for all pairs
        python scripts/calculate_technical_analysis.py --mode historical --days 30
        
        # Backfill specific date range
        python scripts/calculate_technical_analysis.py --mode historical --start 2026-07-01 --end 2026-07-31
        
        # Process new data since last calculation
        python scripts/calculate_technical_analysis.py --mode incremental
        
        # Single pair backfill
        python scripts/calculate_technical_analysis.py --mode historical --days 7 --pair BTC-USD
    """
    # Setup logging
    setup_logging(log_file)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("TECHNICAL ANALYSIS CALCULATION")
    logger.info("=" * 80)
    logger.info(f"Mode: {mode}")
    logger.info(f"Version: {version}")
    if pair:
        logger.info(f"Trading Pair: {pair}")
    else:
        logger.info("Trading Pair: ALL TRACKED PAIRS")
    
    try:
        session = get_session()
        
        # Determine date range for historical mode
        start_date = None
        end_date = None
        
        if mode == 'historical':
            if start and end:
                # Explicit date range
                start_date = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                end_date = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            elif days:
                # Relative date range
                end_date = datetime.now(timezone.utc)
                start_date = end_date - timedelta(days=days)
            else:
                logger.error("Historical mode requires either --start/--end or --days")
                return 1
            
            logger.info(f"Date Range: {start_date.date()} to {end_date.date()}")
        
        # Process single pair or all pairs
        if pair:
            # Single pair mode
            trading_pair_id = get_trading_pair_id(session, pair)
            
            if not trading_pair_id:
                logger.error(f"Trading pair '{pair}' not found in database")
                return 1
            
            logger.info("-" * 80)
            logger.info(f"Processing: {pair}")
            logger.info("-" * 80)
            
            result = run_technical_analysis(
                trading_pair_id=trading_pair_id,
                start_date=start_date,
                end_date=end_date,
                incremental=(mode == 'incremental'),
                calculation_version=version,
                session=session
            )
            
            # Print results
            logger.info("")
            logger.info("=" * 80)
            logger.info("RESULTS")
            logger.info("=" * 80)
            logger.info(f"Mode: {result['mode']}")
            logger.info(f"Trading Pair: {pair}")
            if result['start_date']:
                logger.info(f"Date Range: {result['start_date']} to {result['end_date']}")
            logger.info(f"Candles Processed: {result['candles_processed']}")
            logger.info(f"Candles Skipped (Warm-up): {result['candles_skipped_warmup']}")
            logger.info(f"Analyses Saved: {result['analyses_saved']}")
            logger.info(f"Errors: {result['errors']}")
            logger.info(f"Success: {'✓ YES' if result['success'] else '✗ NO'}")
            logger.info("=" * 80)
            
            return 0 if result['success'] else 1
        
        else:
            # All pairs mode
            logger.info("-" * 80)
            logger.info("Processing: ALL TRACKED PAIRS")
            logger.info("-" * 80)
            
            summary = analyze_all_pairs(
                start_date=start_date,
                end_date=end_date,
                incremental=(mode == 'incremental'),
                calculation_version=version
            )
            
            # Print summary
            logger.info("")
            logger.info("=" * 80)
            logger.info("SUMMARY")
            logger.info("=" * 80)
            logger.info(f"Total Pairs: {summary['total_pairs']}")
            logger.info(f"Successful: {summary['successful_pairs']}")
            logger.info(f"Failed: {summary['failed_pairs']}")
            logger.info(f"Total Analyses Saved: {summary['total_analyses_saved']}")
            logger.info("")
            logger.info("Per-Pair Results:")
            logger.info("-" * 80)
            
            for result in summary['pair_results']:
                pair_id = result['trading_pair_id']
                pair_obj = session.query(TradingPair).get(pair_id)
                pair_symbol = pair_obj.symbol if pair_obj else f"ID={pair_id}"
                
                status = "✓" if result['success'] else "✗"
                logger.info(
                    f"{status} {pair_symbol:12s} | "
                    f"Processed: {result['candles_processed']:4d} | "
                    f"Saved: {result['analyses_saved']:4d} | "
                    f"Skipped: {result['candles_skipped_warmup']:3d} | "
                    f"Errors: {result['errors']:2d}"
                )
            
            logger.info("=" * 80)
            
            return 0 if summary['successful_pairs'] == summary['total_pairs'] else 1
    
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        return 130
    
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1
    
    finally:
        if 'session' in locals():
            session.close()


if __name__ == '__main__':
    sys.exit(main())
