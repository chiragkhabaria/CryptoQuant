"""Unit tests for scoring rules."""

from decimal import Decimal

import pytest

from cryptoquant.analytics.scoring import ScoringConfig, calculate_scores, calculate_signal


def ind(ema="100", rsi="50", hist="0", atr="0.5"):
    return {
        "ema_200": Decimal(ema),
        "rsi_14": Decimal(rsi),
        "macd_histogram": Decimal(hist),
        "atr_14": Decimal(atr),
    }


def test_missing_inputs_return_none():
    scores = calculate_scores({"ema_200": None, "rsi_14": None, "macd_histogram": None, "atr_14": None}, close=Decimal("100"))
    assert all(v is None for v in scores.values())
    assert calculate_scores(ind(), close=None)["technical_score"] is None


def test_neutral_inputs_score_fifty_components():
    s = calculate_scores(ind(), close=Decimal("100"))
    assert s["ema_score"] == Decimal("50.0")
    assert s["rsi_score"] == Decimal("50.0")
    assert s["macd_score"] == Decimal("50.0")


def test_bullish_inputs_score_high_and_buy():
    s = calculate_scores(ind(ema="90", rsi="25", hist="0.5", atr="0.2"), close=Decimal("100"))
    assert s["ema_score"] == Decimal("100.0")
    assert s["rsi_score"] == Decimal("100.0")
    assert s["macd_score"] == Decimal("100.0")
    assert s["atr_score"] == Decimal("100.0")
    assert calculate_signal(s["technical_score"]) == "BUY"


def test_bearish_inputs_score_low_and_avoid():
    s = calculate_scores(ind(ema="120", rsi="80", hist="-0.5", atr="5"), close=Decimal("100"))
    assert s["technical_score"] == Decimal("0.0")
    assert calculate_signal(s["technical_score"]) == "AVOID"


def test_scores_bounded_0_100():
    s = calculate_scores(ind(ema="1", rsi="1", hist="1000", atr="0"), close=Decimal("100"))
    for v in s.values():
        assert Decimal("0") <= v <= Decimal("100")


@pytest.mark.parametrize(
    "score,expected",
    [(None, None), ("65", "BUY"), ("64.99", "HOLD"), ("35", "HOLD"), ("34.99", "AVOID")],
)
def test_signal_thresholds(score, expected):
    value = None if score is None else Decimal(score)
    assert calculate_signal(value) == expected


def test_custom_config_changes_signal():
    cfg = ScoringConfig(buy_threshold=50.0)
    assert calculate_signal(Decimal("55"), cfg) == "BUY"
