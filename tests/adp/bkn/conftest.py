"""BKN module conftest — fixtures for knowledge network tests."""

from __future__ import annotations

import os

import pytest

from lib.agents.cli_agent import CliAgent


@pytest.fixture(scope="session")
async def kn_id(cli_agent: CliAgent) -> str:
    """Find the first available KN ID. Skips if none found."""
    result = await cli_agent.run_cli("bkn", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        pytest.skip("Cannot list KNs")
    for kn in result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if kn_id:
            return kn_id
    pytest.skip("No KN available")


@pytest.fixture(scope="session")
async def kn_with_data(cli_agent: CliAgent) -> tuple[str, str]:
    """Find a KN with object types. Returns (kn_id, ot_name). Skips if none found."""
    result = await cli_agent.run_cli("bkn", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        pytest.skip("Cannot list KNs")
    for kn in result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if not kn_id:
            continue
        ot_result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
        if (
            ot_result.exit_code == 0
            and isinstance(ot_result.parsed_json, list)
            and ot_result.parsed_json
        ):
            ot = ot_result.parsed_json[0]
            ot_name = str(ot.get("name") or ot.get("ot_name") or "")
            if ot_name:
                return kn_id, ot_name
    pytest.skip("No KN with object types available")


@pytest.fixture(scope="session")
def db_credentials() -> dict:
    """Read KWEAVER_TEST_DB_* env vars. Skips if not configured."""
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
