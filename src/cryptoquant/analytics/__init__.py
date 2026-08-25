"""
Phase 2: Technical Analysis Engine

This module contains the analytics pipeline for calculating technical indicators,
scores, and signals from market price data.

Components:
- market_data_reader: Query OHLCV data with proper time windows
- indicators: Pure calculation functions (EMA, RSI, MACD, ATR)
- scoring: Convert indicators to scores and signals (Phase 3)
- technical_repository: Persist results to database
- analytics_pipeline: Orchestrate the full workflow
"""

from .analytics_pipeline import run_technical_analysis, analyze_all_pairs
from .indicators import (
    calculate_ema,
    calculate_rsi,
    calculate_macd,
    calculate_atr,
    calculate_all_indicators,
)
from .market_data_reader import (
    get_candles_for_calculation,
    get_candles_range,
    get_last_analysis_timestamp,
    has_sufficient_data,
)
from .scoring import calculate_scores, calculate_signal
from .technical_repository import (
    save_technical_analysis,
    get_latest_analysis,
    get_analysis_by_timestamp,
    delete_analysis_for_version,
    count_analysis_records,
)

__all__ = [
    # Pipeline
    "run_technical_analysis",
    "analyze_all_pairs",
    # Indicators
    "calculate_ema",
    "calculate_rsi",
    "calculate_macd",
    "calculate_atr",
    "calculate_all_indicators",
    # Data Reader
    "get_candles_for_calculation",
    "get_candles_range",
    "get_last_analysis_timestamp",
    "has_sufficient_data",
    # Scoring
    "calculate_scores",
    "calculate_signal",
    # Repository
    "save_technical_analysis",
    "get_latest_analysis",
    "get_analysis_by_timestamp",
    "delete_analysis_for_version",
    "count_analysis_records",
    # Module names (for backwards compatibility)
    "market_data_reader",
    "indicators",
    "scoring",
    "technical_repository",
    "analytics_pipeline",
]
