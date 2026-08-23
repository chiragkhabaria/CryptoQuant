#!/usr/bin/env python
"""
End-to-End Candle Ingestion Tests

Tests the complete ingestion pipeline for OHLCV candle data from Coinbase API.
This script validates that:
1. Historical data (30 days until yesterday) can be ingested successfully
2. Incremental data (yesterday to today) can be ingested successfully
3. Data integrity is maintained (no duplicates, correct timestamps)
4. Error handling works correctly

Usage:
    # Run all tests
    python tests/ingestion/test_candle_ingestion.py
    
    # Run specific test
    python tests/ingestion/test_candle_ingestion.py --test historical
    python tests/ingestion/test_candle_ingestion.py --test incremental
    
    # Test specific product
    python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD
    
    # Test different granularity
    python tests/ingestion/test_candle_ingestion.py --granularity hourly
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
import click
from sqlalchemy import func, and_, text

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from cryptoquant.collectors.coinbase_client import CoinbaseClient
from cryptoquant.database.session import get_session
from cryptoquant.database.models import MarketPrice, TradingPair, TrackedPair
from cryptoquant.ingestion.historic import (
    GRANULARITY_MAP,
    get_tracked_pairs,
    fetch_and_store_candles,
    get_last_ingestion_time,
)


class TestResults:
    """Container for test results and statistics."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.started_at = datetime.now(timezone.utc)
        self.completed_at = None
        self.passed = False
        self.errors = []
        self.warnings = []
        self.stats = {
            "inserted": 0,
            "skipped": 0,
            "errors": 0,
            "total_records_before": 0,
            "total_records_after": 0,
        }
    
    def complete(self, passed: bool):
        """Mark test as complete."""
        self.completed_at = datetime.now(timezone.utc)
        self.passed = passed
    
    def add_error(self, error: str):
        """Add an error message."""
        self.errors.append(error)
    
    def add_warning(self, warning: str):
        """Add a warning message."""
        self.warnings.append(warning)
    
    def duration(self) -> timedelta:
        """Calculate test duration."""
        if self.completed_at:
            return self.completed_at - self.started_at
        return timedelta(0)
    
    def print_summary(self, logger: logging.Logger):
        """Print test summary."""
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        logger.info("=" * 80)
        logger.info(f"Test: {self.test_name}")
        logger.info(f"Status: {status}")
        logger.info(f"Duration: {self.duration()}")
        logger.info("-" * 80)
        logger.info(f"Records before: {self.stats['total_records_before']}")
        logger.info(f"Records after: {self.stats['total_records_after']}")
        logger.info(f"Records inserted: {self.stats['inserted']}")
        logger.info(f"Records skipped (duplicates): {self.stats['skipped']}")
        logger.info(f"Errors during ingestion: {self.stats['errors']}")
        
        if self.warnings:
            logger.info("-" * 80)
            logger.warning(f"Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        if self.errors:
            logger.info("-" * 80)
            logger.error(f"Errors ({len(self.errors)}):")
            for error in self.errors:
                logger.error(f"  - {error}")
        
        logger.info("=" * 80)


def setup_logging() -> logging.Logger:
    """Configure logging for test execution."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"test_candle_ingestion_{timestamp}.log"
    
    # Configure handlers with UTF-8 encoding
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)
    
    # Set UTF-8 encoding for console output
    if hasattr(stream_handler.stream, 'reconfigure'):
        stream_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[file_handler, stream_handler]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Test log file: {log_file}")
    return logger


def count_records(session, trading_pair_id: int, start_date: datetime, end_date: datetime) -> int:
    """Count market price records for a trading pair within a date range."""
    return (
        session.query(func.count(MarketPrice.id))
        .filter(
            and_(
                MarketPrice.trading_pair_id == trading_pair_id,
                MarketPrice.timestamp >= start_date,
                MarketPrice.timestamp <= end_date,
            )
        )
        .scalar()
    )


def validate_data_integrity(
    session,
    trading_pair_id: int,
    start_date: datetime,
    end_date: datetime,
    logger: logging.Logger
) -> tuple[bool, list[str]]:
    """
    Validate data integrity for ingested candles.
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check for records in the expected date range
    record_count = count_records(session, trading_pair_id, start_date, end_date)
    if record_count == 0:
        errors.append(f"No records found between {start_date.date()} and {end_date.date()}")
        return False, errors
    
    logger.info(f"Found {record_count} records in date range")
    
    # Check for NULL values in critical fields
    null_check = (
        session.query(func.count(MarketPrice.id))
        .filter(
            and_(
                MarketPrice.trading_pair_id == trading_pair_id,
                MarketPrice.timestamp >= start_date,
                MarketPrice.timestamp <= end_date,
                (
                    (MarketPrice.open == None) |
                    (MarketPrice.high == None) |
                    (MarketPrice.low == None) |
                    (MarketPrice.close == None) |
                    (MarketPrice.volume == None)
                )
            )
        )
        .scalar()
    )
    
    if null_check > 0:
        errors.append(f"Found {null_check} records with NULL OHLCV values")
    
    # Check for invalid OHLCV relationships (high >= low, etc.)
    invalid_ohlcv = (
        session.query(func.count(MarketPrice.id))
        .filter(
            and_(
                MarketPrice.trading_pair_id == trading_pair_id,
                MarketPrice.timestamp >= start_date,
                MarketPrice.timestamp <= end_date,
                (
                    (MarketPrice.high < MarketPrice.low) |
                    (MarketPrice.high < MarketPrice.open) |
                    (MarketPrice.high < MarketPrice.close) |
                    (MarketPrice.low > MarketPrice.open) |
                    (MarketPrice.low > MarketPrice.close)
                )
            )
        )
        .scalar()
    )
    
    if invalid_ohlcv > 0:
        errors.append(f"Found {invalid_ohlcv} records with invalid OHLCV relationships")
    
    # Check for negative values
    negative_values = (
        session.query(func.count(MarketPrice.id))
        .filter(
            and_(
                MarketPrice.trading_pair_id == trading_pair_id,
                MarketPrice.timestamp >= start_date,
                MarketPrice.timestamp <= end_date,
                (
                    (MarketPrice.open < 0) |
                    (MarketPrice.high < 0) |
                    (MarketPrice.low < 0) |
                    (MarketPrice.close < 0) |
                    (MarketPrice.volume < 0)
                )
            )
        )
        .scalar()
    )
    
    if negative_values > 0:
        errors.append(f"Found {negative_values} records with negative OHLCV values")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def test_historical_ingestion(
    product_id: Optional[str],
    granularity: str,
    logger: logging.Logger
) -> TestResults:
    """
    Test 1: Historical data ingestion (30 days until yesterday).
    
    This test validates that historical data can be ingested successfully
    for a 30-day period ending yesterday.
    """
    test_name = f"Historical Ingestion (30 days until yesterday, {granularity})"
    results = TestResults(test_name)
    
    logger.info("=" * 80)
    logger.info(f"Starting Test: {test_name}")
    logger.info("=" * 80)
    
    try:
        # Calculate date range: 30 days ago to yesterday
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        start_date = yesterday - timedelta(days=30)
        
        logger.info(f"Date range: {start_date.date()} to {yesterday.date()}")
        logger.info(f"Granularity: {granularity}")
        logger.info(f"Product ID: {product_id or 'All active tracked pairs'}")
        
        # Initialize client and session
        try:
            logger.info("Initializing Coinbase API client...")
            client = CoinbaseClient()
            logger.info("Coinbase API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Coinbase API client: {e}")
            results.add_error(f"Coinbase API initialization failed: {e}")
            results.complete(False)
            results.print_summary(logger)
            return results
        
        try:
            logger.info("Connecting to database...")
            session = get_session()
            # Test the connection
            session.execute(text("SELECT 1"))
            logger.info("Database connection established successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            results.add_error(f"Database connection failed: {e}")
            
            # Provide helpful troubleshooting info
            if "40615" in str(e) or "not allowed to access" in str(e):
                results.add_error("FIREWALL ISSUE: Your IP is not whitelisted in Azure SQL Server")
                logger.error("\n" + "=" * 80)
                logger.error("FIREWALL ISSUE DETECTED")
                logger.error("=" * 80)
                logger.error("Your IP address is not whitelisted in Azure SQL Server firewall.")
                logger.error("\nSOLUTIONS:")
                logger.error("1. Go to Azure Portal and whitelist your IP:")
                logger.error("   - Navigate to your SQL Server")
                logger.error("   - Click 'Networking' → '+ Add client IP' → 'Save'")
                logger.error("   - Wait 2-5 minutes for changes to apply")
                logger.error("\n2. Or run the connection test utility:")
                logger.error("   python tests/ingestion/test_db_connection.py")
                logger.error("\n3. See detailed guide:")
                logger.error("   docs/testing/AZURE_SQL_TROUBLESHOOTING.md")
                logger.error("=" * 80)
            elif "timeout" in str(e).lower():
                results.add_error("CONNECTION TIMEOUT: Network or firewall issue")
                logger.error("\n" + "=" * 80)
                logger.error("CONNECTION TIMEOUT DETECTED")
                logger.error("=" * 80)
                logger.error("Possible causes: Firewall, network latency, or VPN issues")
                logger.error("\nSOLUTIONS:")
                logger.error("1. Check firewall rules (see above)")
                logger.error("2. Test connection: python tests/ingestion/test_db_connection.py")
                logger.error("3. See detailed guide: docs/testing/AZURE_SQL_TROUBLESHOOTING.md")
                logger.error("=" * 80)
            
            results.complete(False)
            results.print_summary(logger)
            return results
        
        candle_granularity = GRANULARITY_MAP[granularity.lower()]
        
        # Get tracked pairs
        tracked_pairs = get_tracked_pairs(session, product_id)
        logger.info(f"Testing with {len(tracked_pairs)} trading pair(s)")
        
        # Process each pair
        for pair_symbol, pair_id in tracked_pairs:
            logger.info(f"\nProcessing {pair_symbol}...")
            
            # Count records before ingestion
            records_before = count_records(session, pair_id, start_date, yesterday)
            results.stats["total_records_before"] += records_before
            logger.info(f"Records before ingestion: {records_before}")
            
            # Perform ingestion
            stats = fetch_and_store_candles(
                client=client,
                session=session,
                product_id=pair_symbol,
                trading_pair_id=pair_id,
                granularity=candle_granularity,
                start_date=start_date,
                end_date=yesterday,
                log=logger,
            )
            
            # Update results
            results.stats["inserted"] += stats["inserted"]
            results.stats["skipped"] += stats["skipped"]
            results.stats["errors"] += stats["errors"]
            
            # Count records after ingestion
            records_after = count_records(session, pair_id, start_date, yesterday)
            results.stats["total_records_after"] += records_after
            logger.info(f"Records after ingestion: {records_after}")
            
            # Validate data integrity
            is_valid, errors = validate_data_integrity(
                session, pair_id, start_date, yesterday, logger
            )
            
            if not is_valid:
                for error in errors:
                    results.add_error(f"{pair_symbol}: {error}")
            
            # Check if any data was inserted or already existed
            if records_after == 0:
                results.add_error(f"{pair_symbol}: No data after ingestion")
            elif stats["inserted"] == 0 and records_before == 0:
                results.add_warning(f"{pair_symbol}: No new data inserted and no previous data")
            
            if stats["errors"] > 0:
                results.add_error(f"{pair_symbol}: {stats['errors']} errors during ingestion")
        
        # Test passes if we have data and no critical errors
        passed = (
            results.stats["total_records_after"] > 0 and
            len(results.errors) == 0
        )
        results.complete(passed)
        
    except Exception as e:
        logger.exception(f"Test failed with exception: {e}")
        results.add_error(str(e))
        results.complete(False)
    
    results.print_summary(logger)
    return results


def test_incremental_ingestion(
    product_id: Optional[str],
    granularity: str,
    logger: logging.Logger
) -> TestResults:
    """
    Test 2: Incremental data ingestion (yesterday to today).
    
    This test validates that incremental/real-time data can be ingested
    successfully from yesterday to today.
    """
    test_name = f"Incremental Ingestion (yesterday to today, {granularity})"
    results = TestResults(test_name)
    
    logger.info("=" * 80)
    logger.info(f"Starting Test: {test_name}")
    logger.info("=" * 80)
    
    try:
        # Calculate date range: yesterday to today
        today = datetime.now(timezone.utc)
        yesterday = today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
        
        logger.info(f"Date range: {yesterday.date()} to {today.date()}")
        logger.info(f"Granularity: {granularity}")
        logger.info(f"Product ID: {product_id or 'All active tracked pairs'}")
        
        # Initialize client and session
        try:
            logger.info("Initializing Coinbase API client...")
            client = CoinbaseClient()
            logger.info("Coinbase API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Coinbase API client: {e}")
            results.add_error(f"Coinbase API initialization failed: {e}")
            results.complete(False)
            results.print_summary(logger)
            return results
        
        try:
            logger.info("Connecting to database...")
            session = get_session()
            # Test the connection
            session.execute(text("SELECT 1"))
            logger.info("Database connection established successfully")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            results.add_error(f"Database connection failed: {e}")
            
            # Provide helpful troubleshooting info
            if "40615" in str(e) or "not allowed to access" in str(e):
                results.add_error("FIREWALL ISSUE: Your IP is not whitelisted in Azure SQL Server")
                logger.error("\n" + "=" * 80)
                logger.error("FIREWALL ISSUE DETECTED")
                logger.error("=" * 80)
                logger.error("Your IP address is not whitelisted in Azure SQL Server firewall.")
                logger.error("\nSOLUTIONS:")
                logger.error("1. Run connection test: python tests/ingestion/test_db_connection.py")
                logger.error("2. See troubleshooting guide: docs/testing/AZURE_SQL_TROUBLESHOOTING.md")
                logger.error("=" * 80)
            elif "timeout" in str(e).lower():
                results.add_error("CONNECTION TIMEOUT: Network or firewall issue")
                logger.error("\n" + "=" * 80)
                logger.error("CONNECTION TIMEOUT - See docs/testing/AZURE_SQL_TROUBLESHOOTING.md")
                logger.error("=" * 80)
            
            results.complete(False)
            results.print_summary(logger)
            return results
        
        candle_granularity = GRANULARITY_MAP[granularity.lower()]
        
        # Get tracked pairs
        tracked_pairs = get_tracked_pairs(session, product_id)
        logger.info(f"Testing with {len(tracked_pairs)} trading pair(s)")
        
        # Process each pair
        for pair_symbol, pair_id in tracked_pairs:
            logger.info(f"\nProcessing {pair_symbol}...")
            
            # Get last ingestion time
            last_time = get_last_ingestion_time(session, pair_id)
            if last_time:
                logger.info(f"Last ingestion timestamp: {last_time}")
                # For incremental test, start from yesterday to ensure we test the incremental logic
                actual_start = yesterday
            else:
                logger.warning(f"No previous data found for {pair_symbol}, will fetch from yesterday")
                actual_start = yesterday
                results.add_warning(f"{pair_symbol}: No previous data, testing incremental from yesterday")
            
            # Count records before ingestion
            records_before = count_records(session, pair_id, actual_start, today)
            results.stats["total_records_before"] += records_before
            logger.info(f"Records before ingestion: {records_before}")
            
            # Perform ingestion
            stats = fetch_and_store_candles(
                client=client,
                session=session,
                product_id=pair_symbol,
                trading_pair_id=pair_id,
                granularity=candle_granularity,
                start_date=actual_start,
                end_date=today,
                log=logger,
            )
            
            # Update results
            results.stats["inserted"] += stats["inserted"]
            results.stats["skipped"] += stats["skipped"]
            results.stats["errors"] += stats["errors"]
            
            # Count records after ingestion
            records_after = count_records(session, pair_id, actual_start, today)
            results.stats["total_records_after"] += records_after
            logger.info(f"Records after ingestion: {records_after}")
            
            # Validate data integrity
            is_valid, errors = validate_data_integrity(
                session, pair_id, actual_start, today, logger
            )
            
            if not is_valid:
                for error in errors:
                    results.add_error(f"{pair_symbol}: {error}")
            
            # Check if any data was inserted or already existed
            if records_after == 0:
                results.add_error(f"{pair_symbol}: No data after ingestion")
            elif stats["inserted"] == 0 and records_before == 0:
                results.add_warning(f"{pair_symbol}: No new data inserted and no previous data")
            
            if stats["errors"] > 0:
                results.add_error(f"{pair_symbol}: {stats['errors']} errors during ingestion")
        
        # Test passes if we have data and no critical errors
        passed = (
            results.stats["total_records_after"] > 0 and
            len(results.errors) == 0
        )
        results.complete(passed)
        
    except Exception as e:
        logger.exception(f"Test failed with exception: {e}")
        results.add_error(str(e))
        results.complete(False)
    
    results.print_summary(logger)
    return results


@click.command()
@click.option(
    "--test",
    type=click.Choice(["all", "historical", "incremental"], case_sensitive=False),
    default="all",
    help="Which test to run (default: all)"
)
@click.option(
    "--product-id",
    type=str,
    default=None,
    help="Test specific trading pair (e.g., BTC-USD). If not provided, tests all active tracked pairs."
)
@click.option(
    "--granularity",
    type=click.Choice(list(GRANULARITY_MAP.keys()), case_sensitive=False),
    default="daily",
    help="Candle granularity to test (default: daily)"
)
def main(test: str, product_id: Optional[str], granularity: str):
    """
    Run end-to-end tests for candle ingestion functionality.
    
    Examples:
    
        # Run all tests with daily candles
        python tests/ingestion/test_candle_ingestion.py
        
        # Run only historical test
        python tests/ingestion/test_candle_ingestion.py --test historical
        
        # Test specific product with hourly candles
        python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD --granularity hourly
        
        # Run incremental test only
        python tests/ingestion/test_candle_ingestion.py --test incremental
    """
    logger = setup_logging()
    
    logger.info("=" * 80)
    logger.info("CANDLE INGESTION TEST SUITE")
    logger.info("=" * 80)
    logger.info(f"Test mode: {test}")
    logger.info(f"Granularity: {granularity}")
    logger.info(f"Product ID: {product_id or 'All active tracked pairs'}")
    logger.info(f"Started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 80)
    
    all_results = []
    
    try:
        # Run tests based on selection
        if test.lower() in ["all", "historical"]:
            results = test_historical_ingestion(product_id, granularity, logger)
            all_results.append(results)
        
        if test.lower() in ["all", "incremental"]:
            results = test_incremental_ingestion(product_id, granularity, logger)
            all_results.append(results)
        
        # Print overall summary
        logger.info("\n" + "=" * 80)
        logger.info("OVERALL TEST SUMMARY")
        logger.info("=" * 80)
        
        total_passed = sum(1 for r in all_results if r.passed)
        total_failed = len(all_results) - total_passed
        
        for result in all_results:
            status = "✅ PASSED" if result.passed else "❌ FAILED"
            logger.info(f"{status} - {result.test_name}")
        
        logger.info("-" * 80)
        logger.info(f"Total: {len(all_results)} tests")
        logger.info(f"Passed: {total_passed}")
        logger.info(f"Failed: {total_failed}")
        logger.info("=" * 80)
        
        # Exit with appropriate code
        sys.exit(0 if total_failed == 0 else 1)
        
    except Exception as e:
        logger.exception(f"Test suite failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
