"""
Historic OHLCV data ingestion pipeline.

Contains the reusable building blocks for fetching candle data from Coinbase
and persisting it to the database.  Both the CLI script and the scheduler call
``run_ingestion()`` as the primary entry point.

Supports two modes:
- **Historical mode**: Fetch N days back from now (e.g., 3 years of data)
- **Incremental mode**: Fetch from last ingestion timestamp to now (for daily updates)
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, DBAPIError

from cryptoquant.collectors.coinbase_client import CandleGranularity, CoinbaseClient
from cryptoquant.database.models import MarketPrice, TrackedPair, TradingPair
from cryptoquant.database.session import get_session

logger = logging.getLogger(__name__)

GRANULARITY_MAP: dict[str, CandleGranularity] = {
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
    Return (symbol, trading_pair_id) tuples for pairs that should be processed.

    Args:
        session: SQLAlchemy session.
        product_id: If provided, return only this specific pair.

    Raises:
        ValueError: When the requested pair is not found, or no active pairs exist.
    """
    if product_id:
        pair = (
            session.query(TradingPair.symbol, TradingPair.id)
            .filter(TradingPair.symbol == product_id)
            .first()
        )
        if not pair:
            raise ValueError(f"Trading pair '{product_id}' not found in database")
        return [pair]

    tracked = (
        session.query(TradingPair.symbol, TradingPair.id)
        .join(TrackedPair, TradingPair.symbol == TrackedPair.product_id)
        .filter(TrackedPair.is_tracking_active == True)  # noqa: E712
        .all()
    )

    if not tracked:
        raise ValueError(
            "No active tracked pairs found. Enable tracking in crypto.tracked_pairs table."
        )
    return tracked


def get_last_ingestion_time(session, trading_pair_id: int) -> Optional[datetime]:
    """
    Get the most recent candle timestamp for a trading pair.
    
    Args:
        session: SQLAlchemy session.
        trading_pair_id: Primary key of the trading pair.
    
    Returns:
        Most recent timestamp, or None if no data exists.
    """
    result = (
        session.query(func.max(MarketPrice.timestamp))
        .filter(MarketPrice.trading_pair_id == trading_pair_id)
        .scalar()
    )
    return result


def fetch_and_store_candles(
    client: CoinbaseClient,
    session,
    product_id: str,
    trading_pair_id: int,
    granularity: CandleGranularity,
    start_date: datetime,
    end_date: datetime,
    log: logging.Logger,
    max_retries: int = 3,
    retry_delay: int = 30,
) -> dict:
    """
    Fetch OHLCV candles for one pair and persist them to the database.

    Args:
        client: Coinbase API client.
        session: SQLAlchemy session.
        product_id: Coinbase product identifier (e.g. ``"BTC-USD"``).
        trading_pair_id: Primary key of the corresponding ``TradingPair`` row.
        granularity: Candle interval.
        start_date: Inclusive start of the fetch window (UTC).
        end_date: Inclusive end of the fetch window (UTC).
        log: Logger to use for this operation.
        max_retries: Maximum retry attempts for database errors (default: 3).
        retry_delay: Seconds to wait between retries (default: 30).

    Returns:
        ``{"inserted": int, "skipped": int, "errors": int}``
    """
    stats: dict[str, int] = {"inserted": 0, "skipped": 0, "errors": 0}

    try:
        log.info(
            "Fetching %s candles for %s from %s to %s",
            granularity.value,
            product_id,
            start_date.date(),
            end_date.date(),
        )

        candles = client.get_candles(
            product_id=product_id,
            granularity=granularity,
            start=start_date,
            end=end_date,
        )

        if not candles:
            log.warning("No candles returned for %s", product_id)
            return stats

        log.info("Fetched %d candles for %s", len(candles), product_id)

        batch_size = 100
        for i in range(0, len(candles), batch_size):
            batch = candles[i : i + batch_size]
            batch_inserted = 0
            batch_skipped = 0

            for candle in batch:
                retry_count = 0
                while retry_count <= max_retries:
                    try:
                        # Use a savepoint so a duplicate on one row doesn't abort
                        # the whole batch transaction.
                        with session.begin_nested():
                            session.add(
                                MarketPrice(
                                    trading_pair_id=trading_pair_id,
                                    timestamp=candle.start,
                                    open=Decimal(str(candle.open)),
                                    high=Decimal(str(candle.high)),
                                    low=Decimal(str(candle.low)),
                                    close=Decimal(str(candle.close)),
                                    volume=Decimal(str(candle.volume)),
                                    data_source="coinbase",
                                )
                            )
                        batch_inserted += 1
                        break  # Success, exit retry loop
                    except IntegrityError:
                        # Duplicate - skip and move on
                        batch_skipped += 1
                        session.rollback()  # Clean up transaction state
                        break
                    except (OperationalError, DBAPIError) as exc:
                        # Database connection/communication error
                        retry_count += 1
                        session.rollback()  # Critical: clean up invalid transaction
                        
                        if retry_count <= max_retries:
                            log.warning(
                                "Database error inserting candle for %s at %s (attempt %d/%d): %s. Retrying in %ds...",
                                product_id,
                                candle.start,
                                retry_count,
                                max_retries,
                                exc,
                                retry_delay,
                            )
                            time.sleep(retry_delay)
                        else:
                            log.error(
                                "Failed to insert candle for %s at %s after %d attempts: %s",
                                product_id,
                                candle.start,
                                max_retries,
                                exc,
                            )
                            stats["errors"] += 1
                    except Exception as exc:
                        # Other unexpected errors
                        log.error(
                            "Error inserting candle for %s at %s: %s",
                            product_id,
                            candle.start,
                            exc,
                        )
                        session.rollback()  # Clean up transaction state
                        stats["errors"] += 1
                        break

            # Commit batch with retry logic
            retry_count = 0
            while retry_count <= max_retries:
                try:
                    session.commit()
                    stats["inserted"] += batch_inserted
                    stats["skipped"] += batch_skipped
                    break  # Success
                except (OperationalError, DBAPIError) as exc:
                    retry_count += 1
                    session.rollback()
                    
                    if retry_count <= max_retries:
                        log.warning(
                            "Database error committing batch for %s (attempt %d/%d): %s. Retrying in %ds...",
                            product_id,
                            retry_count,
                            max_retries,
                            exc,
                            retry_delay,
                        )
                        time.sleep(retry_delay)
                    else:
                        log.error(
                            "Failed to commit batch for %s after %d attempts: %s",
                            product_id,
                            max_retries,
                            exc,
                        )
                        stats["errors"] += batch_inserted
                except Exception as exc:
                    log.error("Unexpected error committing batch for %s: %s", product_id, exc)
                    session.rollback()
                    stats["errors"] += batch_inserted
                    break

        log.info(
            "Completed %s: %d inserted, %d skipped, %d errors",
            product_id,
            stats["inserted"],
            stats["skipped"],
            stats["errors"],
        )

    except Exception as exc:
        log.error("Error fetching candles for %s: %s", product_id, exc)
        session.rollback()  # Ensure clean state
        stats["errors"] += 1

    return stats


def run_ingestion(
    granularity: str = "hourly",
    days: int = 1,
    product_id: Optional[str] = None,
    incremental: bool = False,
) -> dict:
    """
    Fetch and store OHLCV data for all active tracked pairs.

    This is the primary callable entry point for both the scheduler and any
    other programmatic consumer.  The CLI script (``collect_historic_data.py``)
    provides the interactive/progress-bar wrapper on top of this function.

    Args:
        granularity: Key from ``GRANULARITY_MAP`` (e.g. ``"hourly"``).
        days: Number of days back from *now* to fetch (ignored if incremental=True).
        product_id: Restrict to a single pair; ``None`` fetches all tracked pairs.
        incremental: If True, fetch from last ingestion timestamp to now.

    Modes:
        - **Historical** (incremental=False): Fetch `days` back from now.
          Use for initial 3-year data load.
        - **Incremental** (incremental=True): Fetch from last timestamp to now.
          Use for daily updates. Falls back to 7 days if no previous data exists.

    Returns:
        Aggregated ``{"inserted": int, "skipped": int, "errors": int}`` across
        all processed pairs.

    Raises:
        ValueError: If ``granularity`` is not a valid key, or no tracked pairs exist.
    """
    _log = logging.getLogger(__name__)

    if granularity.lower() not in GRANULARITY_MAP:
        raise ValueError(
            f"Unknown granularity '{granularity}'. "
            f"Valid options: {list(GRANULARITY_MAP.keys())}"
        )

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    candle_granularity = GRANULARITY_MAP[granularity.lower()]

    _log.info(
        "Ingestion started: granularity=%s, days=%d, product_id=%s",
        granularity,
        days,
        product_id or "all",
    )

    client = CoinbaseClient()
    session = get_session()

    try:
        tracked_pairs = get_tracked_pairs(session, product_id)
        mode = "incremental" if incremental else "historical"
        _log.info("Processing %d pair(s) in %s mode", len(tracked_pairs), mode)

        total: dict[str, int] = {"inserted": 0, "skipped": 0, "errors": 0}

        for pair_symbol, pair_id in tracked_pairs:
            # Determine start_date based on mode
            if incremental:
                last_time = get_last_ingestion_time(session, pair_id)
                if last_time:
                    # Start from last timestamp + 1 hour to avoid duplicate
                    pair_start = last_time + timedelta(hours=1)
                    _log.info(
                        "%s: Incremental from %s",
                        pair_symbol,
                        pair_start.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    )
                else:
                    # No previous data - fetch 7 days as initial seed
                    pair_start = end_date - timedelta(days=7)
                    _log.info(
                        "%s: No previous data, fetching %d days",
                        pair_symbol,
                        7,
                    )
            else:
                # Historical mode: use days parameter
                pair_start = start_date
                _log.info(
                    "%s: Historical load, fetching %d days",
                    pair_symbol,
                    days,
                )

            stats = fetch_and_store_candles(
                client=client,
                session=session,
                product_id=pair_symbol,
                trading_pair_id=pair_id,
                granularity=candle_granularity,
                start_date=pair_start,
                end_date=end_date,
                log=_log,
            )
            for key in total:
                total[key] += stats[key]

        _log.info(
            "Ingestion completed: inserted=%d, skipped=%d, errors=%d",
            total["inserted"],
            total["skipped"],
            total["errors"],
        )
        return total
    finally:
        session.close()
