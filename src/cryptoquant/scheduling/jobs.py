"""
Scheduled job implementations.

Each function here is a thin wrapper around an existing application entry
point.  Jobs must not contain business logic; they delegate entirely to
the application layer and handle exceptions so that a single job failure
never terminates the scheduler process.
"""
import logging
import time

from cryptoquant.analytics.analytics_pipeline import analyze_all_pairs
from cryptoquant.config.settings import get_settings
from cryptoquant.ingestion.historic import run_ingestion

logger = logging.getLogger(__name__)


def incremental_ingestion_job() -> None:
    """
    Periodic job: fetch new OHLCV data from last watermark to now.

    Uses watermark logic (last ingested timestamp) to only fetch new data.
    Runs every 4 hours by default. Falls back to 7 days if no previous data exists.

    Implements retry logic (3 attempts with 60-second wait) to handle
    transient database connection issues.

    Exceptions are caught and logged; the scheduler process keeps running.
    """
    logger.info("incremental_ingestion_job: started")

    max_retries = 3
    retry_delay_seconds = 60

    for attempt in range(1, max_retries + 1):
        try:
            stats = run_ingestion(
                granularity="hourly",  # Hourly granularity for frequent updates
                days=1,  # Ignored in incremental mode
                incremental=True,  # Fetch from last timestamp to now
            )
            logger.info(
                "incremental_ingestion_job: completed — inserted=%d, skipped=%d, errors=%d",
                stats["inserted"],
                stats["skipped"],
                stats["errors"],
            )
            if stats["errors"] > 0:
                logger.warning(
                    "incremental_ingestion_job: %d error(s) occurred during ingestion",
                    stats["errors"],
                )
            # Success - exit retry loop
            return

        except Exception as exc:
            if attempt < max_retries:
                logger.warning(
                    "incremental_ingestion_job: attempt %d/%d failed — %s — retrying in %d seconds...",
                    attempt,
                    max_retries,
                    exc,
                    retry_delay_seconds,
                )
                time.sleep(retry_delay_seconds)
            else:
                logger.exception(
                    "incremental_ingestion_job: all %d attempts failed — giving up until next scheduled run",
                    max_retries,
                )


def historic_ingestion_job() -> None:
    """
    Periodic job: fetch and store recent OHLCV data for all tracked pairs.

    Reads ``ingestion_granularity`` and ``ingestion_lookback_days`` from
    application settings so the schedule can be tuned via environment
    variables without code changes.

    Implements retry logic (3 attempts with 60-second wait) to handle
    Azure SQL serverless connection timeouts.

    Exceptions are caught and logged; the scheduler process keeps running.
    """
    logger.info("historic_ingestion_job: started")
    settings = get_settings()

    max_retries = 3
    retry_delay_seconds = 60

    for attempt in range(1, max_retries + 1):
        try:
            stats = run_ingestion(
                granularity=settings.ingestion_granularity,
                days=settings.ingestion_lookback_days,
                incremental=False,  # Historical mode - fetch N days back
            )
            logger.info(
                "historic_ingestion_job: completed — inserted=%d, skipped=%d, errors=%d",
                stats["inserted"],
                stats["skipped"],
                stats["errors"],
            )
            if stats["errors"] > 0:
                logger.warning(
                    "historic_ingestion_job: %d error(s) occurred during ingestion",
                    stats["errors"],
                )
            # Success - exit retry loop
            return
            
        except Exception as exc:
            if attempt < max_retries:
                logger.warning(
                    "historic_ingestion_job: attempt %d/%d failed — %s — retrying in %d seconds...",
                    attempt,
                    max_retries,
                    exc,
                    retry_delay_seconds,
                )
                time.sleep(retry_delay_seconds)
            else:
                logger.exception(
                    "historic_ingestion_job: all %d attempts failed — giving up until next scheduled run",
                    max_retries,
                )


def incremental_technical_analysis_job() -> None:
    """
    Periodic job: calculate technical indicators for new candles.

    Runs in incremental mode - processes candles since last analysis timestamp.
    Falls back to 7 days if no previous analysis exists for a pair.

    Requires market_prices data to be present before running.
    Typically scheduled to run after incremental_ingestion_job completes.

    Implements retry logic (3 attempts with 60-second wait) to handle
    transient database issues.

    Exceptions are caught and logged; the scheduler process keeps running.
    """
    logger.info("incremental_technical_analysis_job: started")

    max_retries = 3
    retry_delay_seconds = 60

    for attempt in range(1, max_retries + 1):
        try:
            result = analyze_all_pairs(
                incremental=True,  # Process from last analysis timestamp to now
                calculation_version='v1'
            )
            logger.info(
                "incremental_technical_analysis_job: completed — %d pairs analyzed, %d analyses saved, %d errors",
                result['successful_pairs'],
                result['total_analyses_saved'],
                result['failed_pairs'],
            )
            if result['failed_pairs'] > 0:
                logger.warning(
                    "incremental_technical_analysis_job: %d pair(s) failed during analysis",
                    result['failed_pairs'],
                )
            # Success - exit retry loop
            return

        except Exception as exc:
            if attempt < max_retries:
                logger.warning(
                    "incremental_technical_analysis_job: attempt %d/%d failed — %s — retrying in %d seconds...",
                    attempt,
                    max_retries,
                    exc,
                    retry_delay_seconds,
                )
                time.sleep(retry_delay_seconds)
            else:
                logger.exception(
                    "incremental_technical_analysis_job: all %d attempts failed — giving up until next scheduled run",
                    max_retries,
                )
