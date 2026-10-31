"""Background execution of UI-triggered jobs.

The UI inserts ``queued`` rows in ``crypto.job_runs``; a worker claims and runs
them one at a time. Locally the worker is a daemon thread inside the Streamlit
process. For a deployment where the web process may restart (e.g. Azure App
Service), run it separately: ``python -m cryptoquantui.worker``.
"""

import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

from cryptoquant.database import job_runs
from cryptoquant.database.job_runs import (
    JOB_ANALYTICS,
    JOB_BACKFILL,
    JOB_BACKTEST,
    JOB_INGEST,
    JOB_RESCORE,
)
from cryptoquant.database.models import JobRun
from cryptoquant.database.session import get_session

logger = logging.getLogger(__name__)

JOB_LABELS = {
    JOB_INGEST: "Refresh candles",
    JOB_ANALYTICS: "Recalculate indicators",
    JOB_BACKFILL: "Backfill gaps",
    JOB_BACKTEST: "Run backtests",
    JOB_RESCORE: "Rescore analysis",
}

JOB_HELP = {
    JOB_INGEST: "Fetches the newest hourly candles from Coinbase for all tracked pairs and stores new ones. "
    "Safe to repeat; existing candles are skipped. Same as the 4-hourly scheduler job.",
    JOB_ANALYTICS: "Recalculates indicators (EMA200, RSI, MACD, ATR) and the 0-100 technical score for "
    "candles that have no analysis yet. Run after refreshing candles.",
    JOB_BACKFILL: "Looks for missing hourly candles in the stored history and downloads them. "
    "Can take several minutes. Same as the weekly Sunday job.",
    JOB_BACKTEST: "Replays the BUY/HOLD/AVOID signals over history for each pair using the fee, slippage and "
    "stop settings above, and saves a new run. Previous runs are kept.",
    JOB_RESCORE: "Recomputes the technical score and signal from stored indicators using the current "
    "scoring weights/thresholds. Does not fetch data. Run backtests afterwards to see the impact.",
}

POLL_SECONDS = 3
BACKFILL_TIMEOUT_SECONDS = 3600
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


class JobFailed(Exception):
    """Raised by an executor to fail the run with a clear message."""


def _run_ingest(params: dict) -> Optional[int]:
    from cryptoquant.ingestion.historic import run_ingestion

    stats = run_ingestion(granularity="hourly", days=1, incremental=True)
    if stats["errors"]:
        raise JobFailed(f"{stats['errors']} error(s) during ingestion (inserted {stats['inserted']})")
    return stats["inserted"] + stats.get("updated", 0)


def _run_analytics(params: dict) -> Optional[int]:
    from cryptoquant.analytics.analytics_pipeline import analyze_all_pairs

    result = analyze_all_pairs(incremental=True, calculation_version="v1")
    if result["failed_pairs"]:
        raise JobFailed(f"{result['failed_pairs']} pair(s) failed during analysis")
    return result["total_analyses_saved"]


def _run_backfill(params: dict) -> Optional[int]:
    script = SCRIPTS_DIR / "run_backfill.py"
    result = subprocess.run(
        [sys.executable, str(script), "--type", "all"],
        capture_output=True,
        text=True,
        timeout=BACKFILL_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise JobFailed(f"backfill exited with code {result.returncode}: {(result.stderr or '').strip()[-500:]}")
    return None


def _run_backtest(params: dict) -> Optional[int]:
    from cryptoquant.backtesting.engine import BacktestConfig
    from cryptoquant.backtesting.runner import run_backtests
    from cryptoquant.strategies.signal_strategy import SignalStrategy

    config = BacktestConfig(
        fee_bps=float(params.get("fee_bps", 40.0)),
        slippage_bps=float(params.get("slippage_bps", 5.0)),
        stop_atr_mult=params.get("stop_atr_mult"),
    )
    results = run_backtests(SignalStrategy(), config, symbols=params.get("symbols") or None)
    failed = [r["symbol"] for r in results if "error" in r]
    if results and len(failed) == len(results):
        raise JobFailed("all pairs failed/skipped: " + ", ".join(failed))
    return len(results) - len(failed)


def _run_rescore(params: dict) -> Optional[int]:
    from cryptoquant.analytics.rescore import rescore_all

    session = get_session()
    try:
        return sum(rescore_all(session).values())
    finally:
        session.close()


EXECUTORS: dict[str, Callable[[dict], Optional[int]]] = {
    JOB_INGEST: _run_ingest,
    JOB_ANALYTICS: _run_analytics,
    JOB_BACKFILL: _run_backfill,
    JOB_BACKTEST: _run_backtest,
    JOB_RESCORE: _run_rescore,
}


def submit(job_type: str, params: Optional[dict] = None) -> Optional[int]:
    """Queue a job from the UI. Returns the run id, or None if one is already queued/running."""
    session = get_session()
    try:
        if job_runs.has_active_job(session, job_type):
            return None
        return job_runs.enqueue_job(session, job_type, params, triggered_by=job_runs.TRIGGER_UI)
    finally:
        session.close()


def run_one(run: JobRun, executors: Optional[dict] = None, session_factory: Callable = get_session) -> None:
    """Execute a claimed run and record the outcome."""
    import json

    executors = executors or EXECUTORS
    params = json.loads(run.params) if run.params else {}
    error: Optional[str] = None
    rows: Optional[int] = None
    try:
        rows = executors[run.job_type](params)
    except JobFailed as exc:
        error = str(exc)
    except Exception as exc:
        logger.exception("job %s (%d) failed", run.job_type, run.id)
        error = f"{type(exc).__name__}: {exc}"

    session = session_factory()
    try:
        job_runs.finish_job(session, run.id, error=error, rows_written=rows)
    finally:
        session.close()


def process_queue(session_factory: Callable = get_session, executors: Optional[dict] = None) -> int:
    """Run queued jobs until the queue is empty. Returns how many ran."""
    ran = 0
    while True:
        session = session_factory()
        try:
            run = job_runs.claim_next_queued(session)
        finally:
            session.close()
        if run is None:
            return ran
        run_one(run, executors, session_factory)
        ran += 1


def worker_loop(stop: Optional[threading.Event] = None) -> None:
    """Poll the queue forever (or until ``stop`` is set)."""
    stop = stop or threading.Event()
    session = get_session()
    try:
        job_runs.fail_stale_running(session)
    finally:
        session.close()
    while not stop.is_set():
        try:
            process_queue()
        except Exception:
            logger.exception("job worker iteration failed")
        stop.wait(POLL_SECONDS)


_worker_lock = threading.Lock()
_worker_thread: Optional[threading.Thread] = None


def ensure_worker_started() -> None:
    """Start the in-process worker thread once."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is None or not _worker_thread.is_alive():
            _worker_thread = threading.Thread(target=worker_loop, name="cryptoquantui-worker", daemon=True)
            _worker_thread.start()
