"""Deterministic synthetic bars for tests and offline demos."""

import math
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from cryptoquant.analytics.indicators import calculate_all_indicators
from cryptoquant.analytics.scoring import calculate_scores, calculate_signal
from cryptoquant.strategies.base import Bar


class _Candle:
    """Minimal stand-in for MarketPrice used by calculate_all_indicators."""

    def __init__(self, o: float, h: float, l: float, c: float) -> None:
        self.open, self.high, self.low, self.close = (Decimal(str(round(x, 8))) for x in (o, h, l, c))


def make_synthetic_bars(n: int = 2000, seed: int = 7, start_price: float = 100.0) -> List[Bar]:
    """Random-walk hourly bars with a slow cycle, scored with the real engine."""
    rng = random.Random(seed)
    t0 = datetime(2025, 1, 1)
    price = start_price
    candles: List[_Candle] = []
    stamps: List[datetime] = []
    for i in range(n):
        drift = 0.0004 * math.sin(i / 400)
        o = price
        c = o * (1 + drift + rng.gauss(0, 0.006))
        h = max(o, c) * (1 + abs(rng.gauss(0, 0.002)))
        l = min(o, c) * (1 - abs(rng.gauss(0, 0.002)))
        candles.append(_Candle(o, h, l, c))
        stamps.append(t0 + timedelta(hours=i))
        price = c

    bars: List[Bar] = []
    for i, candle in enumerate(candles):
        window = candles[max(0, i - 199): i + 1]
        score = signal = atr = None
        if len(window) >= 200:
            ind = calculate_all_indicators(window)
            scores = calculate_scores(ind, close=candle.close)
            score = scores["technical_score"]
            signal = calculate_signal(score)
            atr = ind["atr_14"]
        bars.append(
            Bar(
                timestamp=stamps[i],
                open=float(candle.open),
                high=float(candle.high),
                low=float(candle.low),
                close=float(candle.close),
                atr=None if atr is None else float(atr),
                score=None if score is None else float(score),
                signal=signal,
            )
        )
    return bars
