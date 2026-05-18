"""Top-level `resource` command acceptance tests.

`kweaver resource` is the replacement for the removed `kweaver dataview`
command — it lists, finds, fetches, and queries vega-backend resources
(tables and logic views) without going through the vega catalog sub-tree.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_resource_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """resource list returns a JSON array of resources."""
    result = await cli_agent.run_cli("resource", "list", "--limit", "10")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("resource_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_resource_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case, resource_id: str,
):
    """resource get returns detail for a specific resource."""
    result = await cli_agent.run_cli("resource", "get", resource_id)
    scorer.assert_exit_code(result, 0, "resource get")
    scorer.assert_json(result, "resource get returns JSON")
    scorer.assert_json_field(result, "id", label="resource get returns id")
    det = scorer.result(result.duration_ms)
    await eval_case("resource_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_resource_find(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """resource find searches by name and returns matching resources."""
    list_result = await cli_agent.run_cli("resource", "list", "--limit", "1")
    if list_result.exit_code != 0:
        pytest.skip("Cannot list resources")
    parsed = list_result.parsed_json
    entries = parsed if isinstance(parsed, list) else (parsed or {}).get("entries") or []
    if not entries:
        pytest.skip("No resources available for find test")
    name = str(entries[0].get("name", ""))
    if not name:
        pytest.skip("Resource has no name")
    keyword = name[:2]

    result = await cli_agent.run_cli("resource", "find", "--name", keyword)
    scorer.assert_exit_code(result, 0, "resource find")
    scorer.assert_json(result, "resource find returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("resource_find", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_resource_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case, queryable_resource_id: str,
):
    """resource query fetches data rows from a resource."""
    result = await cli_agent.run_cli(
        "resource", "query", queryable_resource_id, "--limit", "3",
    )
    scorer.assert_exit_code(result, 0, "resource query")
    scorer.assert_json(result, "resource query returns JSON")
    if isinstance(result.parsed_json, dict):
        entries = (
            result.parsed_json.get("entries")
            or result.parsed_json.get("data")
            or []
        )
        scorer.assert_true(
            isinstance(entries, list),
            "resource query returns entries array",
        )
    det = scorer.result(result.duration_ms)
    await eval_case("resource_query", [result], det, module="adp/vega")
    assert det.passed, det.failures
