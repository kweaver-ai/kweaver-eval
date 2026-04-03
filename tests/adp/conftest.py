"""ADP (AI Data Platform) product line conftest."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lib.agents.cli_agent import CliAgent

# Directory name → pytest marker mapping
_MODULE_MARKERS = {
    "agent": "agent",
    "bkn": "bkn",
    "vega": "vega",
    "context_loader": "context_loader",
    "dataflow": "dataflow",
    "execution_factory": "execution_factory",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-apply api, adp, and module markers based on directory path."""
    for item in items:
        item_path = Path(item.fspath)
        # All tests under tests/adp/ get api + adp markers
        if "adp" in item_path.parts:
            item.add_marker(pytest.mark.api)
            item.add_marker(pytest.mark.adp)
            # Apply module marker based on parent directory name
            for part in item_path.parts:
                if part in _MODULE_MARKERS:
                    item.add_marker(getattr(pytest.mark, _MODULE_MARKERS[part]))


@pytest.fixture(scope="session", autouse=True)
async def ensure_authenticated(cli_agent: CliAgent):
    """Verify CLI is authenticated before running any ADP tests."""
    result = await cli_agent.run_cli("auth", "status")
    if result.exit_code != 0 or "Token status:" not in result.stdout:
        pytest.skip("Not authenticated — run `kweaver auth login` first")


@pytest.fixture(scope="session")
def db_credentials() -> dict:
    """Read KWEAVER_TEST_DB_* env vars. Shared by BKN and Vega lifecycle tests.

    Skips if required vars are not set.
    """
    creds = {
        "host": os.environ.get("KWEAVER_TEST_DB_HOST", ""),
        "port": os.environ.get("KWEAVER_TEST_DB_PORT", "3306"),
        "user": os.environ.get("KWEAVER_TEST_DB_USER", ""),
        "password": os.environ.get("KWEAVER_TEST_DB_PASS", ""),
        "database": os.environ.get("KWEAVER_TEST_DB_NAME", ""),
        "db_type": os.environ.get("KWEAVER_TEST_DB_TYPE", "mysql"),
    }
    if not all([creds["host"], creds["user"], creds["password"], creds["database"]]):
        pytest.skip("E2E database not configured (KWEAVER_TEST_DB_* env vars)")
    return creds
