"""Run backtests over tracked pairs using stored signals."""

import logging
from datetime import datetime
from typing import List, Optional

from cryptoquant.database.session import get_session
from cryptoquant.strategies.base import Strategy
from cryptoquant.strategies.signal_strategy import SignalStrategy

from .engine import BacktestConfig, run_backtest
from .repository import get_tracked_pairs, load_bars, save_result

logger = logging.getLogger(__name__)

MIN_BARS = 250


def run_backtests(
    strategy: Optional[Strategy] = None,
    config: BacktestConfig = BacktestConfig(),
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    symbols: Optional[List[str]] = None,
    save: bool = True,
) -> List[dict]:
    """
    Backtest every active tracked pair (or ``symbols``) and optionally persist.

    Returns one summary dict per pair: symbol, run_id, metrics (or error).
    """
    strategy = strategy or SignalStrategy()
    session = get_session()
    summaries: List[dict] = []
    try:
        for pair_id, symbol in get_tracked_pairs(session, symbols):
            try:
                bars = load_bars(session, pair_id, start, end)
                scored = sum(1 for b in bars if b.signal is not None)
                if scored < MIN_BARS:
                    logger.warning("%s: only %d scored bars, skipping", symbol, scored)
                    summaries.append({"symbol": symbol, "error": f"only {scored} scored bars"})
                    continue
                result = run_backtest(bars, strategy, config)
                run_id = save_result(session, pair_id, result) if save else None
                summaries.append({"symbol": symbol, "run_id": run_id, **result.metrics})
                logger.info(
                    "%s: return %.2f%% vs buy&hold %.2f%%, %d trades",
                    symbol,
                    result.metrics["total_return"] * 100,
                    result.metrics["benchmark_return"] * 100,
                    result.metrics["num_trades"],
                )
            except Exception as exc:
                session.rollback()
                logger.exception("%s: backtest failed", symbol)
                summaries.append({"symbol": symbol, "error": str(exc)})
    finally:
        session.close()
    return summaries
