"""
Backfill script for filling data gaps.

Usage:
    python scripts/run_backfill.py --type candles
    python scripts/run_backfill.py --type analysis
    python scripts/run_backfill.py --type all
"""
import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cryptoquant.database.session import get_session
from cryptoquant.ingestion.backfill import backfill_multiple_gaps
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"logs/backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

log = logging.getLogger(__name__)


def detect_candle_gaps(session) -> list[dict]:
    """
    Detect all gaps in market_prices data.
    
    Returns:
        List of gap dictionaries with product_id, start_date, end_date
    """
    query = text("""
    WITH ordered_candles AS (
        SELECT
            mp.trading_pair_id,
            tp.symbol,
            mp.timestamp AS gap_start,
            LEAD(mp.timestamp) OVER (PARTITION BY mp.trading_pair_id ORDER BY mp.timestamp) AS gap_end,
            DATEDIFF(HOUR, mp.timestamp, LEAD(mp.timestamp) OVER (PARTITION BY mp.trading_pair_id ORDER BY mp.timestamp)) AS hours_gap
        FROM crypto.market_prices AS mp
        INNER JOIN crypto.trading_pairs AS tp ON tp.id = mp.trading_pair_id
    )
    SELECT
        symbol AS currency_pair,
        gap_start,
        gap_end,
        hours_gap,
        DATEADD(HOUR, 1, gap_start) AS backfill_start,
        DATEADD(HOUR, -1, gap_end) AS backfill_end
    FROM ordered_candles
    WHERE gap_end IS NOT NULL
      AND hours_gap > 1
    ORDER BY symbol, gap_start
    """)
    
    result = session.execute(query).fetchall()
    
    gaps = []
    for row in result:
        gaps.append({
            "product_id": row.currency_pair,
            "start_date": row.backfill_start.replace(tzinfo=timezone.utc),
            "end_date": row.backfill_end.replace(tzinfo=timezone.utc),
        })
    
    return gaps


def backfill_candles():
    """Detect and backfill candle gaps."""
    log.info("=" * 80)
    log.info("BACKFILL: Starting candle gap detection and backfill")
    log.info("=" * 80)
    
    session = get_session()
    try:
        gaps = detect_candle_gaps(session)
        
        if not gaps:
            log.info("✓ No candle gaps detected - data is complete!")
            return
        
        log.info(f"Detected {len(gaps)} gap(s) to backfill")
        
        # Group by pair for logging
        pairs = {}
        for gap in gaps:
            pair = gap["product_id"]
            if pair not in pairs:
                pairs[pair] = []
            pairs[pair].append(gap)
        
        for pair, pair_gaps in pairs.items():
            total_hours = sum([
                (g["end_date"] - g["start_date"]).total_seconds() / 3600
                for g in pair_gaps
            ])
            log.info(f"  {pair}: {len(pair_gaps)} gap(s), ~{total_hours:.0f} hours missing")
        
        # Execute backfill
        stats = backfill_multiple_gaps(gaps, granularity="hourly")
        
        log.info("=" * 80)
        log.info("BACKFILL COMPLETE")
        log.info(f"Total inserted: {stats['inserted']}")
        log.info(f"Total skipped: {stats['skipped']}")
        log.info(f"Total errors: {stats['errors']}")
        log.info("=" * 80)
        
    finally:
        session.close()


def backfill_analysis():
    """Backfill technical analysis by running incremental mode."""
    log.info("=" * 80)
    log.info("BACKFILL: Starting technical analysis backfill")
    log.info("=" * 80)
    
    # For analysis, we can just run the existing incremental analysis
    # which will process all market_prices without analysis
    import subprocess
    
    cmd = [sys.executable, "scripts/calculate_technical_analysis.py", "--mode", "incremental"]
    
    log.info(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    
    if result.returncode == 0:
        log.info("✓ Technical analysis backfill complete")
    else:
        log.error(f"✗ Technical analysis backfill failed with code {result.returncode}")
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Backfill data gaps")
    parser.add_argument(
        "--type",
        choices=["candles", "analysis", "all"],
        default="all",
        help="Type of backfill to run (default: all)",
    )
    
    args = parser.parse_args()
    
    log.info("=" * 80)
    log.info("BACKFILL JOB STARTED")
    log.info(f"Type: {args.type}")
    log.info(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    log.info("=" * 80)
    
    try:
        if args.type in ["candles", "all"]:
            backfill_candles()
        
        if args.type in ["analysis", "all"]:
            backfill_analysis()
        
        log.info("\n" + "=" * 80)
        log.info("✅ BACKFILL JOB COMPLETED SUCCESSFULLY")
        log.info("=" * 80)
        
    except Exception as exc:
        log.error(f"\n❌ BACKFILL JOB FAILED: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
