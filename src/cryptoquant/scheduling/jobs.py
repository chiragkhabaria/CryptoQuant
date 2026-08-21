"""
Scheduled job implementations.

Each function here is a thin wrapper around an existing application entry
point.  Jobs must not contain business logic; they delegate entirely to
the application layer and handle exceptions so that a single job failure
never terminates the scheduler process.
"""
import logging
import time

from cryptoquant.config.settings import get_settings
from cryptoquant.ingestion.historic import run_ingestion

logger = logging.getLogger(__name__)


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
                )
                time.sleep(retry_delay_seconds)
            else:
                logger.exception(
                    "historic_ingestion_job: all %d attempts failed — giving up until next scheduled run",
                    max_retries,
                )
