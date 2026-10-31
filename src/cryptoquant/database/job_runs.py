"""
Job run log.

Records every background job execution in ``crypto.job_runs`` so the UI can show
history, and doubles as the queue for UI-triggered jobs (status ``queued``).

Logging is best-effort: a failure to write the log never breaks the job itself.
Set ``JOB_LOG_ENABLED=0`` to disable tracking (used by the test suite).
"""

import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Iterator, Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from cryptoquant.database.models import JobRun

logger = logging.getLogger(__name__)

JOB_INGEST = "ingest"
JOB_BACKFILL = "backfill"
JOB_ANALYTICS = "analytics"
JOB_BACKTEST = "backtest"
JOB_RESCORE = "rescore"
JOB_TYPES = (JOB_INGEST, JOB_BACKFILL, JOB_ANALYTICS, JOB_BACKTEST, JOB_RESCORE)

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

TRIGGER_SCHEDULER = "scheduler"
TRIGGER_UI = "ui"

MAX_ERROR_CHARS = 4000


def _now() -> datetime:
    return datetime.utcnow()


def is_enabled() -> bool:
    return os.environ.get("JOB_LOG_ENABLED", "1").lower() not in ("0", "false", "no")


def _dump(params: Optional[dict]) -> Optional[str]:
    return json.dumps(params, default=str) if params else None


class JobHandle:
    """Mutable result holder yielded by :func:`track_job`."""

    def __init__(self, run_id: Optional[int]) -> None:
        self.run_id = run_id
        self.rows_written: Optional[int] = None
        self.error: Optional[str] = None

    def fail(self, error: str) -> None:
        """Mark the run failed without raising (for jobs that swallow exceptions)."""
        self.error = error


_current_handle: ContextVar[Optional[JobHandle]] = ContextVar("current_job_handle", default=None)


def report_rows(rows: int) -> None:
    """Record rows written on the job run active in this context (no-op if none)."""
    handle = _current_handle.get()
    if handle is not None:
        handle.rows_written = rows


def report_failure(error: str) -> None:
    """Mark the job run active in this context as failed (no-op if none)."""
    handle = _current_handle.get()
    if handle is not None:
        handle.fail(error)


def tracked_job(job_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: record each call of a scheduler job in the job run log."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with track_job(job_type, TRIGGER_SCHEDULER):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def _default_session_factory() -> Session:
    from cryptoquant.database.session import get_session

    return get_session()


def enqueue_job(
    session: Session,
    job_type: str,
    params: Optional[dict] = None,
    triggered_by: str = TRIGGER_UI,
) -> int:
    """Insert a ``queued`` run and return its id."""
    if job_type not in JOB_TYPES:
        raise ValueError(f"Unknown job type '{job_type}'. Valid: {JOB_TYPES}")
    run = JobRun(
        job_type=job_type,
        status=STATUS_QUEUED,
        triggered_by=triggered_by,
        params=_dump(params),
        created_at=_now(),
    )
    session.add(run)
    session.commit()
    return run.id


def has_active_job(session: Session, job_type: str) -> bool:
    """True if a run of this type is queued or running."""
    return (
        session.query(JobRun.id)
        .filter(JobRun.job_type == job_type, JobRun.status.in_([STATUS_QUEUED, STATUS_RUNNING]))
        .first()
        is not None
    )


def claim_next_queued(session: Session) -> Optional[JobRun]:
    """Atomically move the oldest queued run to ``running`` and return it."""
    candidate = (
        session.query(JobRun.id)
        .filter(JobRun.status == STATUS_QUEUED)
        .order_by(JobRun.id)
        .first()
    )
    if candidate is None:
        return None
    claimed = session.execute(
        update(JobRun)
        .where(JobRun.id == candidate[0], JobRun.status == STATUS_QUEUED)
        .values(status=STATUS_RUNNING, started_at=_now())
    )
    session.commit()
    if claimed.rowcount != 1:
        return None  # another worker got it
    return session.get(JobRun, candidate[0])


def finish_job(
    session: Session,
    run_id: int,
    error: Optional[str] = None,
    rows_written: Optional[int] = None,
) -> None:
    """Mark a run ``success`` (no error) or ``failed``."""
    session.execute(
        update(JobRun)
        .where(JobRun.id == run_id)
        .values(
            status=STATUS_FAILED if error else STATUS_SUCCESS,
            error=error[:MAX_ERROR_CHARS] if error else None,
            rows_written=rows_written,
            finished_at=_now(),
        )
    )
    session.commit()


def fail_stale_running(session: Session, older_than_minutes: int = 120) -> int:
    """Fail runs stuck in ``running`` (e.g. process killed). Returns rows updated."""
    cutoff = _now() - timedelta(minutes=older_than_minutes)
    result = session.execute(
        update(JobRun)
        .where(JobRun.status == STATUS_RUNNING, JobRun.started_at < cutoff)
        .values(status=STATUS_FAILED, error="Marked failed: run did not finish (process restarted?)", finished_at=_now())
    )
    session.commit()
    return result.rowcount


@contextmanager
def track_job(
    job_type: str,
    triggered_by: str = TRIGGER_SCHEDULER,
    params: Optional[dict] = None,
    session_factory: Optional[Callable[[], Session]] = None,
    run_id: Optional[int] = None,
) -> Iterator[JobHandle]:
    """
    Record a job execution.

    Pass ``run_id`` to track an already-queued run (UI worker); otherwise a new
    ``running`` row is created. Set ``handle.rows_written`` for a count, call
    ``handle.fail(msg)`` to record a failure without raising. An exception
    raised in the body is recorded and re-raised.
    """
    handle = JobHandle(run_id)
    factory = session_factory or _default_session_factory
    token = _current_handle.set(handle)

    if is_enabled() and run_id is None:
        try:
            session = factory()
            try:
                run = JobRun(
                    job_type=job_type,
                    status=STATUS_RUNNING,
                    triggered_by=triggered_by,
                    params=_dump(params),
                    created_at=_now(),
                    started_at=_now(),
                )
                session.add(run)
                session.commit()
                handle.run_id = run.id
            finally:
                session.close()
        except Exception:
            logger.warning("job log: could not record start of %s job", job_type, exc_info=True)

    try:
        yield handle
    except Exception as exc:
        handle.error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        _current_handle.reset(token)
        if is_enabled() and handle.run_id is not None:
            try:
                session = factory()
                try:
                    finish_job(session, handle.run_id, handle.error, handle.rows_written)
                finally:
                    session.close()
            except Exception:
                logger.warning("job log: could not record end of %s job", job_type, exc_info=True)
