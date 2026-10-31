"""Database access for backtests: load bars, persist results."""

import json
import logging
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from cryptoquant.database.models import (
    BacktestEquity,
    BacktestRun,
    BacktestTrade,
    MarketPrice,
    TechnicalAnalysis,
    TrackedPair,
    TradingPair,
)
from cryptoquant.strategies.base import Bar

from .engine import BacktestResult

logger = logging.getLogger(__name__)


def _opt(value) -> Optional[float]:
    return None if value is None else float(value)


def get_tracked_pairs(session: Session, symbols: Optional[List[str]] = None) -> List[Tuple[int, str]]:
    """Active tracked pairs as (trading_pair_id, symbol)."""
    query = (
        session.query(TradingPair.id, TradingPair.symbol)
        .join(TrackedPair, TradingPair.symbol == TrackedPair.product_id)
        .filter(TrackedPair.is_tracking_active == True)  # noqa: E712
    )
    if symbols:
        query = query.filter(TradingPair.symbol.in_(symbols))
    return [(r[0], r[1]) for r in query.order_by(TradingPair.symbol).all()]


def load_bars(
    session: Session,
    trading_pair_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Bar]:
    """Candles that have a technical analysis row, oldest first."""
    query = (
        session.query(MarketPrice, TechnicalAnalysis)
        .join(TechnicalAnalysis, TechnicalAnalysis.market_price_id == MarketPrice.id)
        .filter(MarketPrice.trading_pair_id == trading_pair_id)
    )
    if start:
        query = query.filter(MarketPrice.timestamp >= start)
    if end:
        query = query.filter(MarketPrice.timestamp <= end)

    return [
        Bar(
            timestamp=price.timestamp,
            open=float(price.open),
            high=float(price.high),
            low=float(price.low),
            close=float(price.close),
            atr=_opt(analysis.atr_14),
            score=_opt(analysis.technical_score),
            signal=analysis.signal,
        )
        for price, analysis in query.order_by(MarketPrice.timestamp).yield_per(5000)
    ]


def save_result(
    session: Session,
    trading_pair_id: int,
    result: BacktestResult,
    scoring_version: str = "v1",
) -> int:
    """Persist a backtest run with its trades and equity curve. Returns run id."""
    m = result.metrics
    cfg = result.config
    run = BacktestRun(
        trading_pair_id=trading_pair_id,
        strategy_name=result.strategy_name,
        strategy_params=json.dumps(result.strategy_params),
        scoring_version=scoring_version,
        start_time=result.equity[0].timestamp,
        end_time=result.equity[-1].timestamp,
        initial_capital=cfg.initial_capital,
        fee_bps=cfg.fee_bps,
        slippage_bps=cfg.slippage_bps,
        stop_atr_mult=cfg.stop_atr_mult,
        total_return=m["total_return"],
        benchmark_return=m["benchmark_return"],
        excess_return=m["excess_return"],
        cagr=m["cagr"],
        max_drawdown=m["max_drawdown"],
        sharpe=m["sharpe"],
        win_rate=m["win_rate"],
        profit_factor=m["profit_factor"],
        avg_trade_return=m["avg_trade_return"],
        exposure=m["exposure"],
        num_trades=m["num_trades"],
        num_bars=m["num_bars"],
        total_fees=m["total_fees"],
        final_equity=m["final_equity"],
    )
    session.add(run)
    session.flush()

    session.bulk_insert_mappings(
        BacktestTrade,
        [
            {
                "run_id": run.id,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "quantity": t.quantity,
                "fees": t.fees,
                "pnl": t.pnl,
                "return_pct": t.return_pct,
                "bars_held": t.bars_held,
                "exit_reason": t.exit_reason,
            }
            for t in result.trades
        ],
    )
    session.bulk_insert_mappings(
        BacktestEquity,
        [
            {
                "run_id": run.id,
                "timestamp": p.timestamp,
                "equity": p.equity,
                "drawdown": p.drawdown,
                "benchmark_equity": p.benchmark_equity,
                "in_position": p.in_position,
            }
            for p in result.equity
        ],
    )
    session.commit()
    logger.info("Saved backtest run %d (%d trades, %d bars)", run.id, len(result.trades), len(result.equity))
    return run.id
