"""Data quality checks over stored candles, analysis rows and job runs.

Candles are hourly (the ingestion pipeline stores one granularity). All
timestamps in the database are naive UTC.
"""

from datetime import datetime, timedelta
from typing import Iterable, Optional, Sequence

import pandas as pd
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from cryptoquant.backtesting.repository import get_tracked_pairs
from cryptoquant.database.models import JobRun, MarketPrice, TechnicalAnalysis

FRESH_HOURS = 6.0  # ingestion runs every 4h, so up to ~5h old is normal
STALE_HOURS = 12.0
OUTLIER_MOVE_PCT = 0.15
WINDOWS_HOURS = (24, 24 * 7, 24 * 30)

STATUS_FRESH = "fresh"
STATUS_STALE = "stale"
STATUS_OLD = "old"
STATUS_NO_DATA = "no data"
STATUS_ICONS = {STATUS_FRESH: "🟢", STATUS_STALE: "🟡", STATUS_OLD: "🔴", STATUS_NO_DATA: "⚫"}

CANDLE_COLUMNS = ["symbol", "timestamp", "open", "high", "low", "close", "volume"]


def utcnow() -> datetime:
    return datetime.utcnow()


def freshness_status(age_hours: Optional[float]) -> str:
    if age_hours is None or pd.isna(age_hours):
        return STATUS_NO_DATA
    if age_hours <= FRESH_HOURS:
        return STATUS_FRESH
    if age_hours <= STALE_HOURS:
        return STATUS_STALE
    return STATUS_OLD


def _floor_hour(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def load_candles(
    session: Session, since: datetime, symbols: Optional[Sequence[str]] = None
) -> pd.DataFrame:
    """Candles of tracked pairs since ``since`` (oldest first)."""
    pairs = get_tracked_pairs(session, list(symbols) if symbols else None)
    names = {pid: sym for pid, sym in pairs}
    if not names:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    rows = (
        session.query(
            MarketPrice.trading_pair_id,
            MarketPrice.timestamp,
            MarketPrice.open,
            MarketPrice.high,
            MarketPrice.low,
            MarketPrice.close,
            MarketPrice.volume,
        )
        .filter(MarketPrice.trading_pair_id.in_(list(names)), MarketPrice.timestamp >= since)
        .order_by(MarketPrice.trading_pair_id, MarketPrice.timestamp)
        .all()
    )
    df = pd.DataFrame(
        [(names[r[0]], *r[1:]) for r in rows],
        columns=CANDLE_COLUMNS,
    )
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def freshness(session: Session, now: Optional[datetime] = None) -> pd.DataFrame:
    """Last candle, age and traffic-light status for every tracked pair."""
    now = now or utcnow()
    pairs = get_tracked_pairs(session)
    stats = {
        r[0]: r
        for r in session.query(
            MarketPrice.trading_pair_id,
            func.min(MarketPrice.timestamp),
            func.max(MarketPrice.timestamp),
            func.count(MarketPrice.id),
        )
        .group_by(MarketPrice.trading_pair_id)
        .all()
    }
    records = []
    for pair_id, symbol in pairs:
        _, first, last, total = stats.get(pair_id, (pair_id, None, None, 0))
        age = (now - last).total_seconds() / 3600 if last else None
        status = freshness_status(age)
        records.append(
            {
                "symbol": symbol,
                "status": status,
                "icon": STATUS_ICONS[status],
                "last_candle": last,
                "age_hours": round(age, 1) if age is not None else None,
                "first_candle": first,
                "candles": int(total or 0),
            }
        )
    return pd.DataFrame(
        records,
        columns=["symbol", "status", "icon", "last_candle", "age_hours", "first_candle", "candles"],
    )


def completeness(
    candles: pd.DataFrame,
    first_candle: pd.Series,
    now: Optional[datetime] = None,
    windows: Iterable[int] = WINDOWS_HOURS,
) -> pd.DataFrame:
    """
    Expected vs actual hourly candles per pair and window.

    ``first_candle`` maps symbol -> first stored candle so newly listed coins are
    not penalised for hours before they existed. The current, still forming
    hour is excluded from the expected range.
    """
    now = now or utcnow()
    last_full = pd.Timestamp(_floor_hour(now) - timedelta(hours=1))
    records = []
    for symbol, first in first_candle.items():
        if candles.empty:
            stamps = pd.DatetimeIndex([])
        else:
            stamps = pd.DatetimeIndex(candles.loc[candles["symbol"] == symbol, "timestamp"]).floor("h").unique()
        for window in windows:
            start = last_full - pd.Timedelta(hours=window - 1)
            if pd.notna(first):
                start = max(start, pd.Timestamp(first).floor("h"))
            expected = max(int((last_full - start).total_seconds() // 3600) + 1, 0)
            actual = int(((stamps >= start) & (stamps <= last_full)).sum())
            missing = max(expected - actual, 0)
            records.append(
                {
                    "symbol": symbol,
                    "window_hours": window,
                    "expected": expected,
                    "actual": actual,
                    "missing": missing,
                    "pct_complete": round(100 * min(actual, expected) / expected, 1) if expected else None,
                }
            )
    return pd.DataFrame(
        records,
        columns=["symbol", "window_hours", "expected", "actual", "missing", "pct_complete"],
    )


def find_gaps(candles: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Runs of missing hourly candles for one pair within the loaded range."""
    ts = candles.loc[candles["symbol"] == symbol, "timestamp"].sort_values().drop_duplicates()
    records = []
    previous = None
    for current in ts:
        if previous is not None:
            hours = (current - previous).total_seconds() / 3600
            if hours > 1.0001:
                records.append(
                    {
                        "gap_start": previous + timedelta(hours=1),
                        "gap_end": current - timedelta(hours=1),
                        "missing_candles": int(round(hours)) - 1,
                    }
                )
        previous = current
    return pd.DataFrame(records, columns=["gap_start", "gap_end", "missing_candles"])


def integrity(candles: pd.DataFrame, outlier_pct: float = OUTLIER_MOVE_PCT) -> pd.DataFrame:
    """Per-pair counts of suspicious candles."""
    records = []
    for symbol, group in candles.groupby("symbol", sort=True):
        group = group.sort_values("timestamp")
        non_positive = (group[["open", "high", "low", "close"]] <= 0).any(axis=1)
        invalid_range = (
            (group["high"] < group["low"])
            | (group["close"] > group["high"])
            | (group["close"] < group["low"])
            | (group["open"] > group["high"])
            | (group["open"] < group["low"])
        )
        move = group["close"].pct_change().abs()
        records.append(
            {
                "symbol": symbol,
                "candles": len(group),
                "zero_volume": int((group["volume"] <= 0).sum()),
                "invalid_ohlc": int((invalid_range | non_positive).sum()),
                "outlier_moves": int((move > outlier_pct).sum()),
                "duplicates": int(group["timestamp"].duplicated().sum()),
            }
        )
    return pd.DataFrame(
        records,
        columns=["symbol", "candles", "zero_volume", "invalid_ohlc", "outlier_moves", "duplicates"],
    )


def analysis_coverage(session: Session, since: datetime) -> pd.DataFrame:
    """Candles vs technical-analysis rows vs scored rows per pair since ``since``."""
    pairs = get_tracked_pairs(session)
    candle_counts = dict(
        session.query(MarketPrice.trading_pair_id, func.count(MarketPrice.id))
        .filter(MarketPrice.timestamp >= since)
        .group_by(MarketPrice.trading_pair_id)
        .all()
    )
    analysis = {
        r[0]: (r[1], r[2], r[3])
        for r in session.query(
            TechnicalAnalysis.trading_pair_id,
            func.count(TechnicalAnalysis.id),
            func.sum(case((TechnicalAnalysis.technical_score.isnot(None), 1), else_=0)),
            func.max(TechnicalAnalysis.timestamp),
        )
        .filter(TechnicalAnalysis.timestamp >= since)
        .group_by(TechnicalAnalysis.trading_pair_id)
        .all()
    }
    records = []
    for pair_id, symbol in pairs:
        candles = int(candle_counts.get(pair_id, 0))
        rows, scored, last = analysis.get(pair_id, (0, 0, None))
        rows, scored = int(rows or 0), int(scored or 0)
        records.append(
            {
                "symbol": symbol,
                "candles": candles,
                "analysis_rows": rows,
                "scored_rows": scored,
                "unanalysed_candles": max(candles - rows, 0),
                "last_analysis": last,
            }
        )
    return pd.DataFrame(
        records,
        columns=["symbol", "candles", "analysis_rows", "scored_rows", "unanalysed_candles", "last_analysis"],
    )


def recent_job_runs(session: Session, limit: int = 50) -> pd.DataFrame:
    """Most recent job runs, newest first."""
    rows = session.query(JobRun).order_by(JobRun.id.desc()).limit(limit).all()
    records = []
    for r in rows:
        duration = (
            round((r.finished_at - r.started_at).total_seconds(), 1)
            if r.finished_at and r.started_at
            else None
        )
        records.append(
            {
                "id": r.id,
                "job": r.job_type,
                "status": r.status,
                "by": r.triggered_by,
                "created": r.created_at,
                "started": r.started_at,
                "duration_s": duration,
                "rows": r.rows_written,
                "error": r.error,
            }
        )
    return pd.DataFrame(
        records,
        columns=["id", "job", "status", "by", "created", "started", "duration_s", "rows", "error"],
    )


def summarize(fresh: pd.DataFrame, complete: pd.DataFrame, integ: pd.DataFrame) -> dict:
    """Headline numbers for the page header."""
    day = complete[complete["window_hours"] == 24] if not complete.empty else complete
    return {
        "pairs": len(fresh),
        "fresh": int((fresh["status"] == STATUS_FRESH).sum()) if not fresh.empty else 0,
        "attention": int(fresh["status"].isin([STATUS_STALE, STATUS_OLD, STATUS_NO_DATA]).sum())
        if not fresh.empty
        else 0,
        "missing_24h": int(day["missing"].sum()) if not day.empty else 0,
        "integrity_issues": int(integ[["invalid_ohlc", "duplicates"]].sum().sum()) if not integ.empty else 0,
    }
