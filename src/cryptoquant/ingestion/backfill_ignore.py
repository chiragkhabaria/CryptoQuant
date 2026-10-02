"""Known-unfillable data ranges that the backfill must not try to fill again."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml

DEFAULT_IGNORE_FILE = Path(__file__).resolve().parents[3] / "config" / "backfill_ignore.yaml"
_STEP = timedelta(hours=1)


@dataclass(frozen=True)
class IgnoreWindow:
    start: datetime
    end: datetime
    product_id: Optional[str] = None  # None applies to every pair
    reason: str = ""


def _to_utc(value, field: str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError(f"backfill ignore: '{field}' must be an ISO timestamp, got {value!r}")
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def load_ignore_windows(path: Path = DEFAULT_IGNORE_FILE) -> list[IgnoreWindow]:
    """Load ignore windows; a missing file means nothing is ignored."""
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    windows = []
    for entry in data.get("ignore") or []:
        start = _to_utc(entry.get("start"), "start")
        end = _to_utc(entry.get("end", entry.get("start")), "end")
        if end < start:
            raise ValueError(f"backfill ignore: end {end} is before start {start}")
        windows.append(IgnoreWindow(start, end, entry.get("product_id"), entry.get("reason", "")))
    return windows


def filter_ignored_gaps(
    gaps: list[dict], windows: list[IgnoreWindow], pair_key: str = "product_id"
) -> list[dict]:
    """
    Remove ignored hours from gaps (``start_date``/``end_date`` are inclusive, hourly).

    A gap partly covered by a window is trimmed to the uncovered hours.
    """
    if not windows:
        return gaps

    result = []
    for gap in gaps:
        pieces = [(gap["start_date"], gap["end_date"])]
        for window in windows:
            if window.product_id not in (None, gap[pair_key]):
                continue
            remaining = []
            for start, end in pieces:
                if window.end < start or window.start > end:
                    remaining.append((start, end))
                    continue
                if start < window.start:
                    remaining.append((start, window.start - _STEP))
                if end > window.end:
                    remaining.append((window.end + _STEP, end))
            pieces = remaining
        result.extend({**gap, "start_date": s, "end_date": e} for s, e in pieces)
    return result
