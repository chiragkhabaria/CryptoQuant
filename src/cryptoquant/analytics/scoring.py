"""
Scoring Engine

Converts technical indicators into component scores, an aggregate technical
score and a BUY / HOLD / AVOID signal.

Scale
-----
Every score is on a 0-100 scale where 50 is neutral, >50 bullish and <50
bearish. Scores fit the ``Numeric(5, 2)`` columns of ``technical_analysis``.

Component rules (all thresholds live in :class:`ScoringConfig`)
---------------------------------------------------------------
- ema_score  : distance of close from EMA 200. +ema_full_scale_pct above -> 100,
               the same distance below -> 0 (trend following).
- rsi_score  : mean reversion. RSI <= rsi_oversold -> 100, >= rsi_overbought -> 0,
               linear in between (50 at RSI 50).
- macd_score : MACD histogram relative to close. +macd_full_scale_pct -> 100,
               -macd_full_scale_pct -> 0 (momentum).
- atr_score  : volatility penalty. ATR/close <= atr_low_pct -> 100 (calm),
               >= atr_high_pct -> 0 (risky). Not directional.

technical_score is the weighted average of the components. Signal:
    technical_score >= buy_threshold   -> BUY
    technical_score <  avoid_threshold -> AVOID
    otherwise                          -> HOLD

These defaults are a starting hypothesis, not a finalized strategy. Validate
and tune them with the backtests (see docs/backtesting/BACKTESTING.md).
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

logger = logging.getLogger(__name__)

SIGNAL_BUY = "BUY"
SIGNAL_HOLD = "HOLD"
SIGNAL_AVOID = "AVOID"


@dataclass(frozen=True)
class ScoringConfig:
    """Tunable scoring parameters."""

    ema_full_scale_pct: float = 0.10
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_full_scale_pct: float = 0.002
    atr_low_pct: float = 0.003
    atr_high_pct: float = 0.025

    weight_ema: float = 0.35
    weight_rsi: float = 0.20
    weight_macd: float = 0.35
    weight_atr: float = 0.10

    buy_threshold: float = 65.0
    avoid_threshold: float = 35.0


DEFAULT_CONFIG = ScoringConfig()

_EMPTY_SCORES: Dict[str, Optional[Decimal]] = {
    "ema_score": None,
    "rsi_score": None,
    "macd_score": None,
    "atr_score": None,
    "technical_score": None,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 2)))


def _f(value: Optional[Decimal]) -> Optional[float]:
    return None if value is None else float(value)


def calculate_scores(
    indicators: Dict[str, Optional[Decimal]],
    close: Optional[Decimal] = None,
    config: ScoringConfig = DEFAULT_CONFIG,
) -> Dict[str, Optional[Decimal]]:
    """
    Calculate component scores and the aggregate technical score.

    Args:
        indicators: Output of calculate_all_indicators().
        close: Close price of the candle being scored (required for the EMA
            and ATR components).
        config: Scoring parameters.

    Returns:
        Dict with ema_score, rsi_score, macd_score, atr_score and
        technical_score (0-100, Decimal). All None if any input needed for the
        aggregate is missing (e.g. during indicator warm-up).
    """
    ema = _f(indicators.get("ema_200"))
    rsi = _f(indicators.get("rsi_14"))
    hist = _f(indicators.get("macd_histogram"))
    atr = _f(indicators.get("atr_14"))
    price = _f(close)

    if None in (ema, rsi, hist, atr, price) or not price or not ema:
        return dict(_EMPTY_SCORES)

    ema_dist = (price - ema) / ema
    ema_score = 50 + 50 * _clamp(ema_dist / config.ema_full_scale_pct, -1, 1)

    span = config.rsi_overbought - config.rsi_oversold
    rsi_score = 100 * _clamp((config.rsi_overbought - rsi) / span, 0, 1)

    macd_score = 50 + 50 * _clamp((hist / price) / config.macd_full_scale_pct, -1, 1)

    atr_pct = atr / price
    atr_score = 100 * _clamp(
        (config.atr_high_pct - atr_pct) / (config.atr_high_pct - config.atr_low_pct), 0, 1
    )

    total_weight = config.weight_ema + config.weight_rsi + config.weight_macd + config.weight_atr
    technical = (
        ema_score * config.weight_ema
        + rsi_score * config.weight_rsi
        + macd_score * config.weight_macd
        + atr_score * config.weight_atr
    ) / total_weight

    return {
        "ema_score": _to_decimal(ema_score),
        "rsi_score": _to_decimal(rsi_score),
        "macd_score": _to_decimal(macd_score),
        "atr_score": _to_decimal(atr_score),
        "technical_score": _to_decimal(technical),
    }


def calculate_signal(
    technical_score: Optional[Decimal],
    config: ScoringConfig = DEFAULT_CONFIG,
) -> Optional[str]:
    """
    Map the aggregate technical score to BUY / HOLD / AVOID.

    Returns None when the score is unavailable (warm-up).
    """
    if technical_score is None:
        return None
    score = float(technical_score)
    if score >= config.buy_threshold:
        return SIGNAL_BUY
    if score < config.avoid_threshold:
        return SIGNAL_AVOID
    return SIGNAL_HOLD
