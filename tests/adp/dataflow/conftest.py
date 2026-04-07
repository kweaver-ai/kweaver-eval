"""Dataflow module conftest — fixtures for data pipeline tests.

Dataflow depends on ds (datasource) and optionally bkn (knowledge network).
CLI commands (pending):
    kweaver dataflow list          — list dataflows
    kweaver dataflow get <id>      — get dataflow details
    kweaver dataflow create ...    — create a dataflow
    kweaver dataflow delete <id>   — delete a dataflow
    kweaver dataflow run <id>      — execute a dataflow
    kweaver dataflow status <id>   — check run status
    kweaver dataflow logs <id>     — get execution logs

Fixture strategy:
    - Read tests: discover existing resources via `dataflow list` (skip if none)
    - Lifecycle tests: require EVAL_RUN_DESTRUCTIVE=1 + db_credentials
    - Query/Execute tests: require a runnable dataflow or create one
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.dataflow]


@pytest.fixture(scope="session")
async def df_id(cli_agent: CliAgent) -> str:
    """Find the first available dataflow ID. Skips if none found or CLI not ready."""
    result = await cli_agent.run_cli("dataflow", "list")
    if result.exit_code != 0:
        if "command not found" in result.stderr.lower() or "unknown" in result.stderr.lower():
            pytest.skip("dataflow CLI not yet available")
        pytest.skip(f"Cannot list dataflows: {result.stderr.strip()}")
    if not isinstance(result.parsed_json, list):
        pytest.skip("dataflow list did not return a list")
    for df in result.parsed_json:
        df_id = str(df.get("id") or df.get("dataflow_id") or df.get("df_id") or "")
        if df_id:
            return df_id
    pytest.skip("No dataflows available")


@pytest.fixture(scope="session")
async def df_with_source(cli_agent: CliAgent) -> dict:
    """Find a dataflow with a configured source (ds/catalog). Returns minimal info dict.

    Skips if no such dataflow exists.
    """
    result = await cli_agent.run_cli("dataflow", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        pytest.skip("Cannot list dataflows")
    for df in result.parsed_json:
        source = df.get("source") or df.get("catalog_id") or df.get("datasource_id") or ""
        if source:
            return {
                "id": str(df.get("id") or ""),
                "name": str(df.get("name") or ""),
                "source": source,
            }
    pytest.skip("No dataflow with configured source available")
