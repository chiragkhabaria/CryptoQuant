"""
Run backtests over the stored scores/signals and persist the results.

Results are written to crypto.backtest_runs / backtest_trades / backtest_equity
and can be queried via crypto.vw_backtest_summary.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --symbols BTC-USD ETH-USD --start 2025-01-01
    python scripts/run_backtest.py --fee-bps 60 --stop-atr 3 --no-save
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cryptoquant.backtesting.engine import BacktestConfig
from cryptoquant.backtesting.runner import run_backtests
from cryptoquant.strategies.signal_strategy import SignalStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--symbols", nargs="*", help="Symbols (default: all tracked pairs)")
    parser.add_argument("--start", type=_date)
    parser.add_argument("--end", type=_date)
    parser.add_argument("--capital", type=float, default=10_000.0)
    parser.add_argument("--fee-bps", type=float, default=40.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--stop-atr", type=float, default=None, help="ATR stop multiple (default: no stop)")
    parser.add_argument("--no-save", action="store_true", help="Do not persist results")
    args = parser.parse_args()

    config = BacktestConfig(
        initial_capital=args.capital,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        stop_atr_mult=args.stop_atr,
    )
    results = run_backtests(
        SignalStrategy(), config, args.start, args.end, args.symbols, save=not args.no_save
    )

    print(f"\n{'pair':<12}{'run':>6}{'return':>10}{'buy&hold':>10}{'maxDD':>9}{'sharpe':>8}{'trades':>8}{'win%':>7}")
    failures = 0
    for r in results:
        if "error" in r:
            failures += 1
            print(f"{r['symbol']:<12} ERROR: {r['error']}")
            continue
        sharpe = f"{r['sharpe']:.2f}" if r["sharpe"] is not None else "n/a"
        win = f"{r['win_rate'] * 100:.0f}" if r["win_rate"] is not None else "n/a"
        print(
            f"{r['symbol']:<12}{str(r['run_id'] or '-'):>6}{r['total_return'] * 100:>9.1f}%"
            f"{r['benchmark_return'] * 100:>9.1f}%{r['max_drawdown'] * 100:>8.1f}%"
            f"{sharpe:>8}{r['num_trades']:>8}{win:>7}"
        )
    return 1 if failures == len(results) else 0


if __name__ == "__main__":
    sys.exit(main())
