"""
Strategy interface.

A strategy turns one bar (price + indicators + signal) into a decision. The
backtester and, later, the live decision pipeline call the same code so that
backtest results predict live behaviour.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol


class Action(str, Enum):
    ENTER = "ENTER"
    EXIT = "EXIT"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Bar:
    """One candle plus the analysis computed at its close."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    atr: Optional[float] = None
    score: Optional[float] = None
    signal: Optional[str] = None


class Strategy(Protocol):
    name: str

    def params(self) -> dict: ...

    def decide(self, bar: Bar, in_position: bool) -> Action: ...
