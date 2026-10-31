"""Signal-driven long/flat strategy."""

from dataclasses import dataclass, field
from typing import FrozenSet

from .base import Action, Bar


@dataclass(frozen=True)
class SignalStrategy:
    """
    Long/flat strategy driven by the stored BUY/HOLD/AVOID signal.

    Enters when flat and the signal is in ``enter_on``; exits when in a
    position and the signal is in ``exit_on``. Bars without a signal
    (indicator warm-up) are ignored.
    """

    enter_on: FrozenSet[str] = field(default_factory=lambda: frozenset({"BUY"}))
    exit_on: FrozenSet[str] = field(default_factory=lambda: frozenset({"AVOID"}))
    name: str = "signal_long_flat"

    def params(self) -> dict:
        return {"enter_on": sorted(self.enter_on), "exit_on": sorted(self.exit_on)}

    def decide(self, bar: Bar, in_position: bool) -> Action:
        if bar.signal is None:
            return Action.HOLD
        if not in_position and bar.signal in self.enter_on:
            return Action.ENTER
        if in_position and bar.signal in self.exit_on:
            return Action.EXIT
        return Action.HOLD


@dataclass(frozen=True)
class ScoreStrategy:
    """
    Long/flat strategy on the raw technical score (0-100).

    Enters when flat and score >= enter_score; exits when in a position and
    score < exit_score. Used to explore threshold sensitivity without
    re-scoring stored rows.
    """

    enter_score: float = 65.0
    exit_score: float = 35.0
    name: str = "score_threshold"

    def params(self) -> dict:
        return {"enter_score": self.enter_score, "exit_score": self.exit_score}

    def decide(self, bar: Bar, in_position: bool) -> Action:
        if bar.score is None:
            return Action.HOLD
        if not in_position and bar.score >= self.enter_score:
            return Action.ENTER
        if in_position and bar.score < self.exit_score:
            return Action.EXIT
        return Action.HOLD
