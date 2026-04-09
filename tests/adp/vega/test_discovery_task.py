"""Vega discovery-task acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.known_bug("https://github.com/kweaver-ai/adp/issues/428")
async def test_vega_discovery_task_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega discovery-task list returns tasks.

    Known bug: ListDiscoverTasks handler requires catalog_id from path
    param but route /discover-tasks has none — always returns 404.
    """
    result = await cli_agent.run_cli("vega", "discovery-task", "list")
    if result.exit_code != 0:
        pytest.skip("discovery-task list blocked by kweaver-ai/adp#428")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_discovery_task_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


@pytest.mark.known_bug("discovery-task subcommand removed from SDK; use catalog discover --wait instead")
async def test_vega_discovery_task_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str,
):
    """vega discovery-task get returns details for a task found via discover."""
    # Trigger a discover to get a task ID
    discover = await cli_agent.run_cli("vega", "catalog", "discover", catalog_id)
    if discover.exit_code != 0 or not isinstance(discover.parsed_json, dict):
        pytest.skip("Cannot trigger discover on catalog")
    task_id = str(discover.parsed_json.get("id") or "")
    if not task_id:
        pytest.skip("Discover did not return a task ID")

    result = await cli_agent.run_cli("vega", "discovery-task", "get", task_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_field(result, "status", label="task has status field")
    det = scorer.result(result.duration_ms)
    await eval_case("vega_discovery_task_get", [result], det, module="adp/vega")
    assert det.passed, det.failures
