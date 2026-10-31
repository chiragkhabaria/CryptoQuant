"""Per-coin overview and chart data."""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from cryptoquant.backtesting.repository import get_tracked_pairs
from cryptoquant.database.models import MarketPrice, TechnicalAnalysis

from .backtests import latest_runs
from .data_quality import load_candles

WINDOWS = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
DEFAULT_SYMBOL = "BTC-USD"
RESAMPLE_RULES = {"1h": None, "4h": "4h", "1d": "1D"}

OVERVIEW_COLUMNS = [
    "symbol", "price", "change_pct", "high", "low", "volume", "last_candle", "trend",
    "ema_distance_pct", "rsi", "score", "signal", "backtest_return", "backtest_vs_hold",
]


def default_symbol(symbols: list[str]) -> Optional[str]:
    if DEFAULT_SYMBOL in symbols:
        return DEFAULT_SYMBOL
    for s in symbols:
        if s.startswith("BTC"):
            return s
    return symbols[0] if symbols else None


def tracked_symbols(session: Session) -> list[str]:
    return [s for _, s in get_tracked_pairs(session)]


def _latest_analysis(session: Session) -> dict[int, tuple]:
    newest = (
        session.query(TechnicalAnalysis.trading_pair_id.label("pid"), func.max(TechnicalAnalysis.timestamp).label("ts"))
        .group_by(TechnicalAnalysis.trading_pair_id)
        .subquery()
    )
    rows = (
        session.query(
            TechnicalAnalysis.trading_pair_id, TechnicalAnalysis.ema_200, TechnicalAnalysis.rsi_14,
            TechnicalAnalysis.technical_score, TechnicalAnalysis.signal,
        )
        .join(newest, (newest.c.pid == TechnicalAnalysis.trading_pair_id) & (newest.c.ts == TechnicalAnalysis.timestamp))
        .all()
    )
    return {r[0]: r[1:] for r in rows}


def _f(value) -> Optional[float]:
    return None if value is None else float(value)


def coin_overview(session: Session, window_hours: int = 24, now: Optional[datetime] = None) -> pd.DataFrame:
    """One row per tracked coin summarising the last ``window_hours``."""
    now = now or datetime.utcnow()
    pairs = get_tracked_pairs(session)
    candles = load_candles(session, now - timedelta(hours=window_hours + 168))
    analysis = _latest_analysis(session)
    runs = latest_runs(session)
    best_runs = (
        runs.sort_values("total_return", ascending=False).drop_duplicates("symbol").set_index("symbol")
        if not runs.empty else pd.DataFrame()
    )

    records = []
    for pair_id, symbol in pairs:
        group = candles[candles["symbol"] == symbol]
        record = {c: None for c in OVERVIEW_COLUMNS}
        record["symbol"] = symbol
        if not group.empty:
            last = group.iloc[-1]
            cutoff = last["timestamp"] - timedelta(hours=window_hours)
            in_window = group[group["timestamp"] > cutoff]
            before = group[group["timestamp"] <= cutoff]
            reference = before.iloc[-1]["close"] if not before.empty else in_window.iloc[0]["open"]
            record.update(
                price=last["close"],
                change_pct=(last["close"] / reference - 1) if reference else None,
                high=in_window["high"].max(),
                low=in_window["low"].min(),
                volume=in_window["volume"].sum(),
                last_candle=last["timestamp"],
            )
            ema, rsi, score, signal = analysis.get(pair_id, (None,) * 4)
            ema = _f(ema)
            if ema:
                distance = last["close"] / ema - 1
                record["ema_distance_pct"] = distance
                record["trend"] = "Above EMA200" if distance >= 0 else "Below EMA200"
            record.update(rsi=_f(rsi), score=_f(score), signal=signal)
        if symbol in best_runs.index:
            run = best_runs.loc[symbol]
            record["backtest_return"] = run["total_return"]
            record["backtest_vs_hold"] = run["excess_return"]
        records.append(record)
    return pd.DataFrame(records, columns=OVERVIEW_COLUMNS)


def candles_with_indicators(session: Session, symbol: str, since: datetime) -> pd.DataFrame:
    """Candles joined with indicators and scores for one pair."""
    pair_id = next((i for i, s in get_tracked_pairs(session) if s == symbol), None)
    columns = ["timestamp", "open", "high", "low", "close", "volume", "ema_200", "rsi_14",
               "macd", "macd_signal", "macd_histogram", "technical_score", "signal"]
    if pair_id is None:
        return pd.DataFrame(columns=columns)
    rows = (
        session.query(
            MarketPrice.timestamp, MarketPrice.open, MarketPrice.high, MarketPrice.low,
            MarketPrice.close, MarketPrice.volume, TechnicalAnalysis.ema_200, TechnicalAnalysis.rsi_14,
            TechnicalAnalysis.macd, TechnicalAnalysis.macd_signal, TechnicalAnalysis.macd_histogram,
            TechnicalAnalysis.technical_score, TechnicalAnalysis.signal,
        )
        .outerjoin(TechnicalAnalysis, TechnicalAnalysis.market_price_id == MarketPrice.id)
        .filter(MarketPrice.trading_pair_id == pair_id, MarketPrice.timestamp >= since)
        .order_by(MarketPrice.timestamp)
        .all()
    )
    df = pd.DataFrame(rows, columns=columns)
    for col in columns[1:-1]:
        df[col] = pd.to_numeric(df[col])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def resample_candles(df: pd.DataFrame, rule: Optional[str]) -> pd.DataFrame:
    """Aggregate hourly candles to a coarser interval; indicators take the last value."""
    if rule is None or df.empty:
        return df
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    for col in df.columns:
        if col not in agg and col != "timestamp":
            agg[col] = "last"
    return df.set_index("timestamp").resample(rule).agg(agg).dropna(subset=["close"]).reset_index()
