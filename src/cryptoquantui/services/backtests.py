"""Backtest results, score explanation and score-vs-outcome analysis."""

from dataclasses import fields
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from cryptoquant.analytics.scoring import DEFAULT_CONFIG, ScoringConfig
from cryptoquant.backtesting.repository import get_tracked_pairs
from cryptoquant.database.models import (
    BacktestEquity,
    BacktestRun,
    BacktestTrade,
    MarketPrice,
    TechnicalAnalysis,
    TradingPair,
)

RUN_COLUMNS = [
    "run_id", "symbol", "strategy", "start", "end", "created", "num_trades", "total_return",
    "benchmark_return", "excess_return", "cagr", "max_drawdown", "sharpe", "win_rate",
    "profit_factor", "exposure", "total_fees", "final_equity",
]
NUMERIC_RUN_COLUMNS = [
    "total_return", "benchmark_return", "excess_return", "cagr", "max_drawdown", "sharpe",
    "win_rate", "profit_factor", "exposure", "total_fees", "final_equity",
]
SCORE_BUCKETS = [(0, 35, "AVOID (<35)"), (35, 50, "HOLD low (35-50)"), (50, 65, "HOLD high (50-65)"), (65, 101, "BUY (>=65)")]


def _runs_frame(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=RUN_COLUMNS)
    for col in NUMERIC_RUN_COLUMNS:
        df[col] = pd.to_numeric(df[col])
    return df


def verdict(row: pd.Series) -> str:
    """One-line reading of a run versus simply holding the coin."""
    if row["num_trades"] == 0:
        return "No trades"
    excess = row["excess_return"]
    if pd.notna(excess) and excess > 0:
        return "Beats buy & hold"
    if pd.notna(row["total_return"]) and row["total_return"] > 0:
        return "Profitable, lags buy & hold"
    return "Loses money"


def latest_runs(session: Session) -> pd.DataFrame:
    """Most recent run per (pair, strategy)."""
    newest = (
        session.query(func.max(BacktestRun.id))
        .group_by(BacktestRun.trading_pair_id, BacktestRun.strategy_name)
        .subquery()
    )
    rows = (
        session.query(
            BacktestRun.id, TradingPair.symbol, BacktestRun.strategy_name, BacktestRun.start_time,
            BacktestRun.end_time, BacktestRun.created_at, BacktestRun.num_trades,
            BacktestRun.total_return, BacktestRun.benchmark_return, BacktestRun.excess_return,
            BacktestRun.cagr, BacktestRun.max_drawdown, BacktestRun.sharpe, BacktestRun.win_rate,
            BacktestRun.profit_factor, BacktestRun.exposure, BacktestRun.total_fees,
            BacktestRun.final_equity,
        )
        .join(TradingPair, TradingPair.id == BacktestRun.trading_pair_id)
        .filter(BacktestRun.id.in_(session.query(newest.c[0])))
        .order_by(TradingPair.symbol, BacktestRun.strategy_name)
        .all()
    )
    df = _runs_frame(rows)
    df["verdict"] = df.apply(verdict, axis=1) if not df.empty else []
    return df


def run_history(session: Session, symbol: str) -> pd.DataFrame:
    """All runs for one pair, oldest first (to see results drift over time)."""
    rows = (
        session.query(
            BacktestRun.id, TradingPair.symbol, BacktestRun.strategy_name, BacktestRun.start_time,
            BacktestRun.end_time, BacktestRun.created_at, BacktestRun.num_trades,
            BacktestRun.total_return, BacktestRun.benchmark_return, BacktestRun.excess_return,
            BacktestRun.cagr, BacktestRun.max_drawdown, BacktestRun.sharpe, BacktestRun.win_rate,
            BacktestRun.profit_factor, BacktestRun.exposure, BacktestRun.total_fees,
            BacktestRun.final_equity,
        )
        .join(TradingPair, TradingPair.id == BacktestRun.trading_pair_id)
        .filter(TradingPair.symbol == symbol)
        .order_by(BacktestRun.id)
        .all()
    )
    return _runs_frame(rows)


def equity_curve(session: Session, run_id: int) -> pd.DataFrame:
    rows = (
        session.query(
            BacktestEquity.timestamp, BacktestEquity.equity, BacktestEquity.drawdown,
            BacktestEquity.benchmark_equity, BacktestEquity.in_position,
        )
        .filter(BacktestEquity.run_id == run_id)
        .order_by(BacktestEquity.timestamp)
        .all()
    )
    df = pd.DataFrame(rows, columns=["timestamp", "equity", "drawdown", "benchmark_equity", "in_position"])
    for col in ("equity", "drawdown", "benchmark_equity"):
        df[col] = pd.to_numeric(df[col])
    return df


def trades(session: Session, run_id: int) -> pd.DataFrame:
    rows = (
        session.query(
            BacktestTrade.entry_time, BacktestTrade.exit_time, BacktestTrade.entry_price,
            BacktestTrade.exit_price, BacktestTrade.pnl, BacktestTrade.return_pct,
            BacktestTrade.fees, BacktestTrade.bars_held, BacktestTrade.exit_reason,
        )
        .filter(BacktestTrade.run_id == run_id)
        .order_by(BacktestTrade.entry_time)
        .all()
    )
    df = pd.DataFrame(
        rows,
        columns=["entry_time", "exit_time", "entry_price", "exit_price", "pnl", "return_pct",
                 "fees", "bars_held", "exit_reason"],
    )
    for col in ("entry_price", "exit_price", "pnl", "return_pct", "fees"):
        df[col] = pd.to_numeric(df[col])
    return df


def score_explainer(config: ScoringConfig = DEFAULT_CONFIG) -> dict:
    """Plain-language description of the scoring model, built from its config."""
    total = config.weight_ema + config.weight_rsi + config.weight_macd + config.weight_atr
    components = [
        {
            "component": "EMA (trend)", "weight_pct": round(100 * config.weight_ema / total),
            "measures": "Distance of price from the 200-period EMA.",
            "low_means": f"Price {config.ema_full_scale_pct:.0%} or more below EMA200 -> 0 (downtrend)",
            "high_means": f"Price {config.ema_full_scale_pct:.0%} or more above EMA200 -> 100 (uptrend)",
        },
        {
            "component": "RSI (mean reversion)", "weight_pct": round(100 * config.weight_rsi / total),
            "measures": "14-period RSI, read contrarian: oversold is attractive.",
            "low_means": f"RSI >= {config.rsi_overbought:g} -> 0 (overbought)",
            "high_means": f"RSI <= {config.rsi_oversold:g} -> 100 (oversold)",
        },
        {
            "component": "MACD (momentum)", "weight_pct": round(100 * config.weight_macd / total),
            "measures": "MACD histogram relative to price.",
            "low_means": f"Histogram <= -{config.macd_full_scale_pct:.1%} of price -> 0 (falling momentum)",
            "high_means": f"Histogram >= +{config.macd_full_scale_pct:.1%} of price -> 100 (rising momentum)",
        },
        {
            "component": "ATR (volatility)", "weight_pct": round(100 * config.weight_atr / total),
            "measures": "14-period ATR as a share of price. Not directional; calm is better.",
            "low_means": f"ATR >= {config.atr_high_pct:.1%} of price -> 0 (risky)",
            "high_means": f"ATR <= {config.atr_low_pct:.1%} of price -> 100 (calm)",
        },
    ]
    return {
        "components": pd.DataFrame(components),
        "buy_threshold": config.buy_threshold,
        "avoid_threshold": config.avoid_threshold,
        "summary": (
            "Every component is scored 0-100 (50 = neutral). The technical score is their weighted "
            f"average. Score >= {config.buy_threshold:g} gives BUY, below {config.avoid_threshold:g} "
            "gives AVOID, anything between is HOLD. The backtest strategy trades these signals, so "
            "changing weights or thresholds changes backtest results."
        ),
        "config": {f.name: getattr(config, f.name) for f in fields(config)},
    }


def signal_distribution(session: Session, since: datetime) -> pd.DataFrame:
    """Share of BUY / HOLD / AVOID signals per pair since ``since``."""
    rows = (
        session.query(TradingPair.symbol, TechnicalAnalysis.signal, func.count(TechnicalAnalysis.id))
        .join(TradingPair, TradingPair.id == TechnicalAnalysis.trading_pair_id)
        .filter(TechnicalAnalysis.timestamp >= since, TechnicalAnalysis.signal.isnot(None))
        .group_by(TradingPair.symbol, TechnicalAnalysis.signal)
        .all()
    )
    df = pd.DataFrame(rows, columns=["symbol", "signal", "count"])
    if df.empty:
        return pd.DataFrame(columns=["symbol", "BUY", "HOLD", "AVOID"])
    wide = df.pivot_table(index="symbol", columns="signal", values="count", aggfunc="sum", fill_value=0)
    for col in ("BUY", "HOLD", "AVOID"):
        if col not in wide:
            wide[col] = 0
    return wide[["BUY", "HOLD", "AVOID"]].reset_index()


def score_vs_forward_returns(
    session: Session,
    symbol: str,
    horizon_hours: int = 24,
    lookback_days: int = 365,
    now: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Average forward return by score bucket for one pair.

    Answers: when the score was high, did price actually rise afterwards?
    Returns columns bucket, observations, avg_forward_return, hit_rate.
    """
    now = now or datetime.utcnow()
    pairs = dict((s, i) for i, s in get_tracked_pairs(session))
    pair_id = pairs.get(symbol)
    columns = ["bucket", "observations", "avg_forward_return", "hit_rate"]
    if pair_id is None:
        return pd.DataFrame(columns=columns)
    rows = (
        session.query(MarketPrice.timestamp, MarketPrice.close, TechnicalAnalysis.technical_score)
        .outerjoin(TechnicalAnalysis, TechnicalAnalysis.market_price_id == MarketPrice.id)
        .filter(MarketPrice.trading_pair_id == pair_id,
                MarketPrice.timestamp >= now - timedelta(days=lookback_days))
        .order_by(MarketPrice.timestamp)
        .all()
    )
    df = pd.DataFrame(rows, columns=["timestamp", "close", "score"])
    if df.empty:
        return pd.DataFrame(columns=columns)
    df["close"] = pd.to_numeric(df["close"])
    df["score"] = pd.to_numeric(df["score"])
    df["forward"] = df["close"].shift(-horizon_hours) / df["close"] - 1
    df = df.dropna(subset=["score", "forward"])
    records = []
    for low, high, label in SCORE_BUCKETS:
        part = df[(df["score"] >= low) & (df["score"] < high)]
        records.append(
            {
                "bucket": label,
                "observations": len(part),
                "avg_forward_return": part["forward"].mean() if len(part) else None,
                "hit_rate": (part["forward"] > 0).mean() if len(part) else None,
            }
        )
    return pd.DataFrame(records, columns=columns)


def aggregate_summary(runs: pd.DataFrame) -> dict:
    """Headline numbers across the latest runs."""
    if runs.empty:
        return {"runs": 0, "beating": 0, "avg_excess": None, "median_sharpe": None}
    return {
        "runs": len(runs),
        "beating": int((runs["excess_return"] > 0).sum()),
        "avg_excess": runs["excess_return"].mean(),
        "median_sharpe": runs["sharpe"].median(),
    }
