"""
Re-score stored technical analysis rows with the current scoring rules.

No indicator recalculation and no Coinbase calls; only updates the score and
signal columns. Run this once after deploying the scoring engine (to backfill
scores on history) and again whenever scoring thresholds change.

Usage:
    python scripts/rescore_analysis.py
    python scripts/rescore_analysis.py --symbols BTC-USD ETH-USD
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cryptoquant.analytics.rescore import rescore_all
from cryptoquant.backtesting.repository import get_tracked_pairs
from cryptoquant.database.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--symbols", nargs="*", help="Limit to these symbols (default: all tracked pairs)")
    args = parser.parse_args()

    session = get_session()
    try:
        pairs = get_tracked_pairs(session, args.symbols)
        if not pairs:
            print("No tracked pairs found")
            return 1
        logging.info("Re-scoring %d pair(s); first query may be slow if Azure SQL is waking up", len(pairs))
        names = dict(pairs)
        results = rescore_all(session, [pid for pid, _ in pairs])
        for pid, count in results.items():
            print(f"{names[pid]:<12} {count:>8} rows re-scored")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
