"""
Quick verification script to check technical analysis results
"""

import sys
from pathlib import Path

src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cryptoquant.database.session import get_session
from cryptoquant.database.models import TechnicalAnalysis, TradingPair
from sqlalchemy import func

session = get_session()

# Count total records
total = session.query(TechnicalAnalysis).count()
print(f"Total technical analysis records: {total}")

# Count by pair
pairs = (
    session.query(
        TradingPair.symbol,
        func.count(TechnicalAnalysis.id).label('count')
    )
    .join(TechnicalAnalysis, TechnicalAnalysis.trading_pair_id == TradingPair.id)
    .group_by(TradingPair.symbol)
    .all()
)

print("\nRecords by trading pair:")
for symbol, count in pairs:
    print(f"  {symbol}: {count}")

# Show sample records for BTC-USD
print("\nSample BTC-USD records (latest 5):")
samples = (
    session.query(TechnicalAnalysis)
    .filter(TechnicalAnalysis.trading_pair_id == 1)
    .order_by(TechnicalAnalysis.timestamp.desc())
    .limit(5)
    .all()
)

for sample in samples:
    print(f"\n  Timestamp: {sample.timestamp}")
    print(f"  EMA 200: {sample.ema_200}")
    print(f"  RSI 14: {sample.rsi_14}")
    print(f"  MACD: {sample.macd}")
    print(f"  ATR 14: {sample.atr_14}")
    print(f"  Signal: {sample.signal}")

session.close()
print("\n✓ Verification complete")
