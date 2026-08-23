"""
APScheduler configuration and lifecycle management.

Reads job definitions from a YAML config file and creates jobs dynamically.
Supports both cron and interval triggers, plus run-on-startup capability.
"""
import importlib
import logging
import signal
import sys
from pathlib import Path
from typing import Any

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from cryptoquant.config.settings import get_settings

logger = logging.getLogger(__name__)


def create_scheduler() -> BlockingScheduler:
    """Return a configured ``BlockingScheduler`` (not yet started)."""
    return BlockingScheduler(
        job_defaults={
            "coalesce": True,        # collapse missed firings into one run
            "max_instances": 1,      # prevent overlapping executions
            "misfire_grace_time": 300,  # tolerate up to 5-minute clock drift
        },
        timezone="UTC",
    )


def load_jobs_config(config_path: Path) -> list[dict[str, Any]]:
    """
    Load and parse the jobs YAML configuration file.
    
    Returns:
        List of job definition dictionaries.
    
    Raises:
        FileNotFoundError: If config file doesn't exist.
        yaml.YAMLError: If config file is malformed.
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"Jobs config file not found: {config_path}\n"
            "Create config/jobs.yaml to define scheduled jobs."
        )
    
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    if not config or "jobs" not in config:
        logger.warning("No jobs defined in %s", config_path)
        return []
    
    return config["jobs"]


def get_job_function(function_name: str):
    """
    Dynamically import and return the job function by name.
    
    Args:
        function_name: Function name (must exist in cryptoquant.scheduling.jobs).
    
    Returns:
        Callable job function.
    
    Raises:
        AttributeError: If function doesn't exist in jobs module.
    """
    jobs_module = importlib.import_module("cryptoquant.scheduling.jobs")
    try:
        return getattr(jobs_module, function_name)
    except AttributeError:
        raise AttributeError(
            f"Job function '{function_name}' not found in cryptoquant.scheduling.jobs"
        )


def create_trigger(job_config: dict[str, Any]):
    """
    Create an APScheduler trigger from job config.
    
    Args:
        job_config: Job definition dict with 'type', 'cron', or 'interval_minutes'.
    
    Returns:
        CronTrigger or IntervalTrigger instance.
    
    Raises:
        ValueError: If job type is unknown or required fields are missing.
    """
    job_type = job_config.get("type", "interval")
    
    if job_type == "cron":
        cron_expr = job_config.get("cron")
        if not cron_expr:
            raise ValueError(f"Job '{job_config['id']}' has type=cron but no 'cron' field")
        
        # Parse cron: "minute hour day month day_of_week"
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression for job '{job_config['id']}': {cron_expr}\n"
                "Expected format: 'minute hour day month day_of_week'"
            )
        
        return CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone="UTC",
        )
    
    elif job_type == "interval":
        interval_minutes = job_config.get("interval_minutes")
        if not interval_minutes:
            raise ValueError(
                f"Job '{job_config['id']}' has type=interval but no 'interval_minutes' field"
            )
        return IntervalTrigger(minutes=interval_minutes, timezone="UTC")
    
    else:
        raise ValueError(
            f"Unknown job type '{job_type}' for job '{job_config['id']}'. "
            "Valid types: 'cron', 'interval'"
        )


def register_jobs(scheduler: BlockingScheduler, config_path: Path) -> None:
    """
    Load jobs from YAML config and register them with the scheduler.
    
    Args:
        scheduler: APScheduler instance.
        config_path: Path to jobs.yaml file.
    """
    jobs_config = load_jobs_config(config_path)
    
    registered_count = 0
    for job_def in jobs_config:
        # Skip disabled jobs
        if not job_def.get("enabled", True):
            logger.info("Skipping disabled job: %s", job_def.get("id", "unknown"))
            continue
        
        job_id = job_def["id"]
        job_name = job_def.get("name", job_id)
        function_name = job_def["function"]
        
        try:
            job_func = get_job_function(function_name)
            trigger = create_trigger(job_def)
            
            scheduler.add_job(
                job_func,
                trigger=trigger,
                id=job_id,
                name=job_name,
                replace_existing=True,
            )
            
            # Log the schedule details
            if job_def.get("type") == "cron":
                logger.info(
                    "Registered job '%s' — cron: %s",
                    job_id,
                    job_def.get("cron"),
                )
            else:
                logger.info(
                    "Registered job '%s' — interval: %d minute(s)",
                    job_id,
                    job_def.get("interval_minutes"),
                )
            
            # Run immediately on startup if configured
            if job_def.get("run_on_startup", False):
                logger.info("Running job '%s' immediately (run_on_startup=true)", job_id)
                try:
                    job_func()
                except Exception:
                    logger.exception("Startup execution of job '%s' failed", job_id)
            
            registered_count += 1
            
        except Exception as exc:
            logger.error("Failed to register job '%s': %s", job_id, exc)
            continue
    
    logger.info("Successfully registered %d job(s)", registered_count)


def start_scheduler() -> None:
    """
    Create the scheduler, load jobs from YAML config, then block until shutdown.

    Respects ``SCHEDULER_ENABLED``; exits immediately when disabled.
    Handles SIGINT and SIGTERM for graceful shutdown.
    """
    settings = get_settings()

    if not settings.scheduler_enabled:
        logger.warning("Scheduler is disabled (SCHEDULER_ENABLED=false). Nothing to do.")
        return

    # Resolve config path relative to project root
    config_path = Path(settings.scheduler_jobs_config)
    if not config_path.is_absolute():
        # Assume relative to project root (where pyproject.toml lives)
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        config_path = project_root / config_path
    
    logger.info("Loading job definitions from: %s", config_path)

    scheduler = create_scheduler()
    register_jobs(scheduler, config_path)

    job_count = len(scheduler.get_jobs())
    if job_count == 0:
        logger.warning("No jobs were registered. Scheduler will run but do nothing.")
    
    logger.info("Scheduler initialised with %d job(s). Starting...", job_count)

    def _handle_shutdown(signum, frame):  # noqa: ARG001
        logger.info("Received signal %d — shutting down scheduler gracefully...", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_shutdown)
    try:
        signal.signal(signal.SIGTERM, _handle_shutdown)
    except (OSError, ValueError):
        pass  # SIGTERM is not available on all platforms (e.g. Windows)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
