"""Root pytest configuration for kweaver-eval."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lib.agents.cli_agent import CliAgent
from lib.feedback import FeedbackTracker
from lib.recorder import Recorder
from lib.scorer import Scorer


def _load_env_file(path: str) -> None:
    """Load environment variables from a file (simple .env parser)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ")
        eq = line.find("=")
        if eq < 0:
            continue
        key = line[:eq].strip()
        value = line[eq + 1 :].strip().strip("\"'")
        if key not in os.environ:
            os.environ[key] = value


# Load env files: local .env first, then ~/.env.secrets as fallback
_load_env_file(".env")
_load_env_file(os.path.join(Path.home(), ".env.secrets"))


def pytest_addoption(parser):
    parser.addoption("--run-destructive", action="store_true", default=False, help="Run destructive tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "destructive: test mutates server state")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-destructive") and not os.environ.get("EVAL_RUN_DESTRUCTIVE"):
        skip = pytest.mark.skip(reason="destructive test (use --run-destructive or EVAL_RUN_DESTRUCTIVE=1)")
        for item in items:
            if "destructive" in item.keywords:
                item.add_marker(skip)


# ---------- Session-scoped fixtures ----------


@pytest.fixture(scope="session")
def base_url() -> str:
    url = os.environ.get("KWEAVER_BASE_URL", "")
    if not url:
        pytest.skip("KWEAVER_BASE_URL not set")
    return url


@pytest.fixture(scope="session")
def cli_agent() -> CliAgent:
    return CliAgent()


@pytest.fixture(scope="session")
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture(scope="session")
def feedback_tracker() -> FeedbackTracker:
    return FeedbackTracker()


# ---------- Per-test fixtures ----------


@pytest.fixture
def scorer() -> Scorer:
    return Scorer()


# ---------- Session teardown ----------


@pytest.fixture(scope="session", autouse=True)
def finalize(recorder, feedback_tracker):
    """Flush results and save feedback after all tests."""
    yield
    recorder.flush()
    feedback_tracker.save()
