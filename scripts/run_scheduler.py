#!/usr/bin/env python
"""
CryptoQuant Scheduler — launcher script.

Starts the long-running scheduling process that periodically invokes
configured ingestion and processing jobs.

Usage:
    python scripts/run_scheduler.py

Environment variables (all have sensible defaults):
    SCHEDULER_ENABLED           true/false  (default: true)
    INGESTION_INTERVAL_MINUTES  integer     (default: 60)
    INGESTION_GRANULARITY       daily/hourly/...  (default: hourly)
    INGESTION_LOOKBACK_DAYS     integer     (default: 1)
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

# Make src/ importable when running the script directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cryptoquant.scheduling.scheduler import start_scheduler

# ---------------------------------------------------------------------------
# Logging — configure before anything else so all module loggers inherit it.
# ---------------------------------------------------------------------------
_log_dir = Path(__file__).resolve().parent.parent / "logs"
_log_dir.mkdir(exist_ok=True)
_log_file = _log_dir / f"scheduler_{datetime.now().strftime('%Y%m%d')}.log"

_file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_stream_handler = logging.StreamHandler(sys.stdout)
if hasattr(_stream_handler.stream, "reconfigure"):
    _stream_handler.stream.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[_file_handler, _stream_handler],
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=" * 70)
    logger.info("CryptoQuant Scheduler starting")
    logger.info("=" * 70)
    start_scheduler()
    logger.info("CryptoQuant Scheduler shut down.")


if __name__ == "__main__":
    main()
