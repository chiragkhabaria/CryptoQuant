from datetime import datetime

from cryptoquant.strategies.base import Action, Bar
from cryptoquant.strategies.signal_strategy import ScoreStrategy


def _bar(score):
    return Bar(timestamp=datetime(2025, 1, 1), open=1, high=1, low=1, close=1, score=score)


def test_score_strategy_enter_exit_hold():
    s = ScoreStrategy(enter_score=65, exit_score=35)
    assert s.decide(_bar(70), False) == Action.ENTER
    assert s.decide(_bar(50), False) == Action.HOLD
    assert s.decide(_bar(30), True) == Action.EXIT
    assert s.decide(_bar(50), True) == Action.HOLD
    assert s.decide(_bar(None), False) == Action.HOLD
