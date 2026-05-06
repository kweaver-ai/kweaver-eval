"""ADP (AI Data Platform) product line conftest."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from lib.agents.cli_agent import CliAgent
from lib.eval_db import EVAL_SCHEMA, bootstrap as _bootstrap_eval_db

# Common naming prefix for any platform resource created by the eval suite.
# Cleanup logic and "find-existing" fast paths filter resources by this prefix.
EVAL_PREFIX = "eval_"

# Tables seeded into the eval-owned schema (see lib/eval_db.py).
EVAL_DB_TABLES = ("suppliers", "materials", "skills", "mat_skill")

# BKN's `create-from-ds` auto-detect inspects sample data, not the actual
# schema's PRIMARY KEY constraint, so we still need to spell PKs out
# explicitly even though lib/eval_db.py defines them at the SQL level.
EVAL_DB_PK_MAP = (
    "suppliers:supplier_id,materials:sku,skills:skill_id,mat_skill:sku"
)

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
    """Verify CLI is authenticated before running any ADP tests.

    Supports no-auth mode via KWEAVER_TOKEN=__NO_AUTH__ environment variable.
    When no-auth mode is enabled, skip authentication check.
    """
    import os

    # Check if no-auth mode is enabled
    token = os.environ.get("KWEAVER_TOKEN", "")
    if token == "__NO_AUTH__":
        # No-auth mode: skip authentication check
        return

    # Normal mode: verify authentication
    result = await cli_agent.run_cli("auth", "status")
    if result.exit_code != 0 or "Token status:" not in result.stdout:
        pytest.skip("Not authenticated — run `kweaver auth login` first or set KWEAVER_TOKEN=__NO_AUTH__")


@pytest.fixture(scope="session")
def db_credentials() -> dict:
    """MySQL credentials for the eval-owned schema.

    Connection params come from KWEAVER_TEST_DB_* env vars; the schema name
    is fixed to EVAL_SCHEMA so the eval is self-contained and idempotent
    (re-seeded once per session by `_seed_eval_db` below).
    """
    creds = {
        "host": os.environ.get("KWEAVER_TEST_DB_HOST", ""),
        "port": os.environ.get("KWEAVER_TEST_DB_PORT", "3306"),
        "user": os.environ.get("KWEAVER_TEST_DB_USER", ""),
        "password": os.environ.get("KWEAVER_TEST_DB_PASS", ""),
        "database": EVAL_SCHEMA,
        "db_type": os.environ.get("KWEAVER_TEST_DB_TYPE", "mysql"),
    }
    if not all([creds["host"], creds["user"], creds["password"]]):
        pytest.skip("E2E database not configured (KWEAVER_TEST_DB_HOST/USER/PASS)")
    return creds


@pytest.fixture(scope="session", autouse=True)
def _seed_eval_db(request) -> None:
    """Drop + recreate + reseed the eval-owned schema before any ADP test runs.

    Skipped silently when DB credentials are not configured; tests that
    actually need the schema will skip themselves on the same condition.
    """
    host = os.environ.get("KWEAVER_TEST_DB_HOST", "")
    user = os.environ.get("KWEAVER_TEST_DB_USER", "")
    password = os.environ.get("KWEAVER_TEST_DB_PASS", "")
    if not all([host, user, password]):
        return
    port = int(os.environ.get("KWEAVER_TEST_DB_PORT", "3306"))
    _bootstrap_eval_db(host, port, user, password)
