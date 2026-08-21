"""
Unit tests for the CryptoQuant scheduling layer.

All external dependencies (Coinbase API, database, APScheduler internals) are
mocked so these tests run without any network access or live credentials.
"""
import logging
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from apscheduler.schedulers.blocking import BlockingScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(**overrides):
    """Return a MagicMock that mimics the Settings object."""
    defaults = {
        "scheduler_enabled": True,
        "scheduler_jobs_config": "config/jobs.yaml",
        "ingestion_interval_minutes": 60,
        "ingestion_granularity": "hourly",
        "ingestion_lookback_days": 1,
    }
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _make_test_yaml_config(jobs: list[dict]) -> str:
    """Return a YAML string for testing."""
    import yaml
    return yaml.dump({"jobs": jobs})


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class TestHistoricIngestionJob:
    """Tests for ``historic_ingestion_job``."""

    def test_calls_run_ingestion_with_configured_params(self):
        """Job forwards configured granularity and lookback days to run_ingestion."""
        settings = _make_settings(ingestion_granularity="daily", ingestion_lookback_days=2)

        with (
            patch("cryptoquant.scheduling.jobs.get_settings", return_value=settings),
            patch("cryptoquant.scheduling.jobs.run_ingestion") as mock_run,
        ):
            mock_run.return_value = {"inserted": 10, "skipped": 0, "errors": 0}
            from cryptoquant.scheduling.jobs import historic_ingestion_job

            historic_ingestion_job()

            mock_run.assert_called_once_with(granularity="daily", days=2)

    def test_exception_is_logged_not_raised(self):
        """An ingestion failure must not propagate out of the job function."""
        settings = _make_settings()

        with (
            patch("cryptoquant.scheduling.jobs.get_settings", return_value=settings),
            patch(
                "cryptoquant.scheduling.jobs.run_ingestion",
                side_effect=RuntimeError("connection refused"),
            ),
        ):
            from cryptoquant.scheduling.jobs import historic_ingestion_job

            # Must not raise — scheduler must keep running after a job failure.
            historic_ingestion_job()

    def test_non_zero_error_count_logs_warning(self, caplog):
        """Partial errors in stats produce a WARNING-level log message."""
        settings = _make_settings()

        with (
            patch("cryptoquant.scheduling.jobs.get_settings", return_value=settings),
            patch(
                "cryptoquant.scheduling.jobs.run_ingestion",
                return_value={"inserted": 0, "skipped": 0, "errors": 3},
            ),
        ):
            from cryptoquant.scheduling.jobs import historic_ingestion_job

            with caplog.at_level(logging.WARNING, logger="cryptoquant.scheduling.jobs"):
                historic_ingestion_job()

            warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
            assert any("3 error(s)" in msg for msg in warning_messages)

    def test_successful_run_logs_completion(self, caplog):
        """A successful run emits an INFO-level 'completed' message."""
        settings = _make_settings()

        with (
            patch("cryptoquant.scheduling.jobs.get_settings", return_value=settings),
            patch(
                "cryptoquant.scheduling.jobs.run_ingestion",
                return_value={"inserted": 5, "skipped": 1, "errors": 0},
            ),
        ):
            from cryptoquant.scheduling.jobs import historic_ingestion_job

            with caplog.at_level(logging.INFO, logger="cryptoquant.scheduling.jobs"):
                historic_ingestion_job()

            info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
            assert any("completed" in msg for msg in info_messages)


# ---------------------------------------------------------------------------
# Scheduler creation and job registration
# ---------------------------------------------------------------------------

class TestSchedulerCreation:
    """Tests for scheduler setup and job registration."""

    def test_create_scheduler_returns_blocking_scheduler(self):
        """``create_scheduler`` produces a ``BlockingScheduler`` instance."""
        from cryptoquant.scheduling.scheduler import create_scheduler

        sched = create_scheduler()
        assert isinstance(sched, BlockingScheduler)

    def test_register_jobs_adds_cron_job(self, tmp_path):
        """``register_jobs`` registers a cron-based job from YAML config."""
        yaml_content = _make_test_yaml_config([
            {
                "id": "test_cron_job",
                "name": "Test Cron Job",
                "enabled": True,
                "type": "cron",
                "cron": "0 2 * * *",
                "function": "historic_ingestion_job",
                "run_on_startup": False,
            }
        ])
        
        config_file = tmp_path / "jobs.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")
        
        from cryptoquant.scheduling.scheduler import create_scheduler, register_jobs
        
        with patch("cryptoquant.scheduling.scheduler.get_job_function") as mock_get_func:
            mock_get_func.return_value = MagicMock()
            
            sched = create_scheduler()
            register_jobs(sched, config_file)
            
            job_ids = [job.id for job in sched.get_jobs()]
            assert "test_cron_job" in job_ids

    def test_register_jobs_adds_interval_job(self, tmp_path):
        """``register_jobs`` registers an interval-based job from YAML config."""
        yaml_content = _make_test_yaml_config([
            {
                "id": "test_interval_job",
                "name": "Test Interval Job",
                "enabled": True,
                "type": "interval",
                "interval_minutes": 15,
                "function": "historic_ingestion_job",
                "run_on_startup": False,
            }
        ])
        
        config_file = tmp_path / "jobs.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")
        
        from cryptoquant.scheduling.scheduler import create_scheduler, register_jobs
        
        with patch("cryptoquant.scheduling.scheduler.get_job_function") as mock_get_func:
            mock_get_func.return_value = MagicMock()
            
            sched = create_scheduler()
            register_jobs(sched, config_file)
            
            job = sched.get_job("test_interval_job")
            assert job is not None
            assert "0:15:00" in str(job.trigger)
    
    def test_register_jobs_skips_disabled_jobs(self, tmp_path):
        """Disabled jobs are not registered."""
        yaml_content = _make_test_yaml_config([
            {
                "id": "disabled_job",
                "name": "Disabled Job",
                "enabled": False,
                "type": "interval",
                "interval_minutes": 10,
                "function": "historic_ingestion_job",
            }
        ])
        
        config_file = tmp_path / "jobs.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")
        
        from cryptoquant.scheduling.scheduler import create_scheduler, register_jobs
        
        sched = create_scheduler()
        register_jobs(sched, config_file)
        
        job_ids = [job.id for job in sched.get_jobs()]
        assert "disabled_job" not in job_ids
    
    def test_register_jobs_runs_on_startup_when_configured(self, tmp_path):
        """Jobs with run_on_startup=true execute immediately."""
        yaml_content = _make_test_yaml_config([
            {
                "id": "startup_job",
                "name": "Startup Job",
                "enabled": True,
                "type": "interval",
                "interval_minutes": 60,
                "function": "historic_ingestion_job",
                "run_on_startup": True,
            }
        ])
        
        config_file = tmp_path / "jobs.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")
        
        from cryptoquant.scheduling.scheduler import create_scheduler, register_jobs
        
        mock_func = MagicMock()
        with patch("cryptoquant.scheduling.scheduler.get_job_function", return_value=mock_func):
            sched = create_scheduler()
            register_jobs(sched, config_file)
            
            # Job function should have been called immediately
            mock_func.assert_called_once()


class TestStartScheduler:
    """Tests for the ``start_scheduler`` entry point."""

    def test_disabled_scheduler_returns_without_starting(self, caplog):
        """``start_scheduler`` exits early and logs a warning when disabled."""
        settings = _make_settings(scheduler_enabled=False)

        with patch("cryptoquant.scheduling.scheduler.get_settings", return_value=settings):
            from cryptoquant.scheduling.scheduler import start_scheduler

            with caplog.at_level(logging.WARNING, logger="cryptoquant.scheduling.scheduler"):
                start_scheduler()

            assert any("disabled" in r.message.lower() for r in caplog.records)

    def test_enabled_scheduler_loads_config_and_starts(self, tmp_path):
        """``start_scheduler`` loads YAML config and calls ``scheduler.start()``."""
        yaml_content = _make_test_yaml_config([
            {
                "id": "test_job",
                "enabled": True,
                "type": "interval",
                "interval_minutes": 60,
                "function": "historic_ingestion_job",
                "run_on_startup": False,
            }
        ])
        
        config_file = tmp_path / "jobs.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")
        
        settings = _make_settings(scheduler_jobs_config=str(config_file))
        
        mock_scheduler = MagicMock(spec=BlockingScheduler)
        mock_scheduler.get_jobs.return_value = [MagicMock()]
        
        with (
            patch("cryptoquant.scheduling.scheduler.get_settings", return_value=settings),
            patch("cryptoquant.scheduling.scheduler.create_scheduler", return_value=mock_scheduler),
            patch("cryptoquant.scheduling.scheduler.get_job_function", return_value=MagicMock()),
        ):
            from cryptoquant.scheduling.scheduler import start_scheduler
            
            # BlockingScheduler.start() blocks; raise SystemExit which is caught
            # internally — start_scheduler() returns normally after that.
            mock_scheduler.start.side_effect = SystemExit(0)
            
            start_scheduler()  # must return without raising
            
            mock_scheduler.start.assert_called_once()


# ---------------------------------------------------------------------------
# Settings defaults
# ---------------------------------------------------------------------------

class TestSchedulerSettings:
    """Verify scheduler-related settings have correct defaults."""

    @pytest.fixture()
    def settings_obj(self):
        """Return a Settings instance with minimal required fields, bypassing validation."""
        from cryptoquant.config.settings import Settings

        with patch.object(Settings, "_validate_required_settings"):
            return Settings(
                coinbase_api_key="test_key",
                coinbase_api_secret="test_secret",
                database_url="sqlite:///test.db",
            )

    def test_scheduler_enabled_defaults_true(self, settings_obj):
        assert settings_obj.scheduler_enabled is True

    def test_ingestion_interval_defaults_60(self, settings_obj):
        assert settings_obj.ingestion_interval_minutes == 60

    def test_ingestion_granularity_defaults_hourly(self, settings_obj):
        assert settings_obj.ingestion_granularity == "hourly"

    def test_ingestion_lookback_days_defaults_1(self, settings_obj):
        assert settings_obj.ingestion_lookback_days == 1
