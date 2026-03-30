"""Datasource module conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.ds]


@pytest.fixture(scope="session")
async def ds_id(cli_agent: CliAgent) -> str:
    """Find the first available datasource ID. Skips if none found."""
    result = await cli_agent.run_cli("ds", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, dict):
        pytest.skip("Cannot list datasources")
    entries = result.parsed_json.get("entries", [])
    if not isinstance(entries, list) or len(entries) == 0:
        pytest.skip("No datasources available")
    ds = entries[0]
    ds_id = str(ds.get("id") or ds.get("ds_id") or ds.get("datasource_id", ""))
    if not ds_id:
        pytest.skip("Cannot determine datasource ID")
    return ds_id
