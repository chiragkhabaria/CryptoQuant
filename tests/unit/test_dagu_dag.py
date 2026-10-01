"""Guards the Dagu deployment files against the mistakes that broke the mini PC rollout."""
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DAGU_DIR = REPO_ROOT / "deploy" / "dagu"
DAG_FILE = DAGU_DIR / "dags" / "crypto_backfill.yaml"
CONFIG_TEMPLATE = DAGU_DIR / "dagu_config.yaml"

DRIVE_PATH = re.compile(r"\b[A-Za-z]:[\\/]")
GO_DURATION = re.compile(r"^(\d+(ns|us|ms|s|m|h))+$")
STEP_ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


@pytest.fixture(scope="module")
def dag() -> dict:
    return yaml.safe_load(DAG_FILE.read_text(encoding="utf-8"))


def test_entrypoint_does_not_define_name(dag):
    assert "name" not in dag


@pytest.mark.parametrize("path", sorted(DAGU_DIR.rglob("*.yaml")), ids=lambda p: p.name)
def test_no_machine_specific_drive_paths(path):
    assert not DRIVE_PATH.search(path.read_text(encoding="utf-8"))


def test_working_dir_is_relative_and_resolves_to_repo_root(dag):
    working_dir = Path(dag["working_dir"])
    assert not working_dir.is_absolute()
    assert (DAG_FILE.parent / working_dir).resolve() == REPO_ROOT


def test_catchup_window_uses_go_duration_syntax(dag):
    assert GO_DURATION.match(str(dag["catchup_window"]))


def test_steps_are_valid_and_reference_existing_scripts(dag):
    ids = [step["id"] for step in dag["steps"]]
    assert all(STEP_ID.match(step_id) for step_id in ids)
    for step in dag["steps"]:
        assert step.get("depends", ids[0]) in ids
        script = re.search(r"scripts[\\/][\w.]+\.py", step["run"])
        assert script and (REPO_ROOT / script.group(0).replace("\\", "/")).is_file()


def test_config_template_enables_queues_for_catchup():
    config = yaml.safe_load(CONFIG_TEMPLATE.read_text(encoding="utf-8"))
    assert config["queues"]["enabled"] is True
    assert "paths" not in config
