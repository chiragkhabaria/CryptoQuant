"""Cached, session-managed fetchers used by the Streamlit views."""

from contextlib import contextmanager
from datetime import timedelta

import streamlit as st

from cryptoquant.database.session import get_session
from cryptoquantui.services import backtests, coins, data_quality

TTL = 60


@contextmanager
def _session():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@st.cache_data(ttl=TTL, show_spinner=False)
def freshness():
    with _session() as s:
        return data_quality.freshness(s)


@st.cache_data(ttl=TTL, show_spinner=False)
def quality_bundle(lookback_days: int = 30):
    """Freshness, completeness, integrity and coverage computed from one candle load."""
    with _session() as s:
        now = data_quality.utcnow()
        since = now - timedelta(days=lookback_days)
        fresh = data_quality.freshness(s, now)
        candles = data_quality.load_candles(s, since)
        first = fresh.set_index("symbol")["first_candle"] if not fresh.empty else None
        complete = data_quality.completeness(candles, first, now) if first is not None else fresh
        integ = data_quality.integrity(candles)
        coverage = data_quality.analysis_coverage(s, since)
    return {"fresh": fresh, "complete": complete, "integrity": integ, "coverage": coverage, "candles": candles}


@st.cache_data(ttl=10, show_spinner=False)
def job_runs(limit: int = 50):
    with _session() as s:
        return data_quality.recent_job_runs(s, limit)


@st.cache_data(ttl=TTL, show_spinner=False)
def latest_backtests():
    with _session() as s:
        return backtests.latest_runs(s)


@st.cache_data(ttl=TTL, show_spinner=False)
def backtest_history(symbol: str):
    with _session() as s:
        return backtests.run_history(s, symbol)


@st.cache_data(ttl=TTL, show_spinner=False)
def equity_curve(run_id: int):
    with _session() as s:
        return backtests.equity_curve(s, run_id)


@st.cache_data(ttl=TTL, show_spinner=False)
def trades(run_id: int):
    with _session() as s:
        return backtests.trades(s, run_id)


@st.cache_data(ttl=TTL, show_spinner=False)
def score_buckets(symbol: str, horizon_hours: int):
    with _session() as s:
        return backtests.score_vs_forward_returns(s, symbol, horizon_hours=horizon_hours)


@st.cache_data(ttl=TTL, show_spinner=False)
def signal_distribution(days: int):
    with _session() as s:
        return backtests.signal_distribution(s, data_quality.utcnow() - timedelta(days=days))


@st.cache_data(ttl=TTL, show_spinner=False)
def symbols():
    with _session() as s:
        return coins.tracked_symbols(s)


@st.cache_data(ttl=TTL, show_spinner=False)
def overview(window_hours: int):
    with _session() as s:
        return coins.coin_overview(s, window_hours)


@st.cache_data(ttl=TTL, show_spinner=False)
def coin_candles(symbol: str, lookback_days: int):
    with _session() as s:
        return coins.candles_with_indicators(s, symbol, data_quality.utcnow() - timedelta(days=lookback_days))
