"""Dataview acceptance tests.

Dataview (data view) is part of the Vega module — provides SQL-queryable
views over datasource tables, supporting both atomic and custom types.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_dataview_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """dataview list returns a JSON array of data views."""
    result = await cli_agent.run_cli("dataview", "list", "--limit", "10")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("dataview_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_dataview_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case, dataview_id: str,
):
    """dataview get returns detail for a specific data view."""
    result = await cli_agent.run_cli("dataview", "get", dataview_id)
    scorer.assert_exit_code(result, 0, "dataview get")
    scorer.assert_json(result, "dataview get returns JSON")
    scorer.assert_json_field(result, "id", label="dataview get returns id")
    det = scorer.result(result.duration_ms)
    await eval_case("dataview_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_dataview_find(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """dataview find searches by name and returns matching views."""
    # First get a name to search for
    list_result = await cli_agent.run_cli("dataview", "list", "--limit", "1")
    if list_result.exit_code != 0:
        pytest.skip("Cannot list dataviews")
    parsed = list_result.parsed_json
    entries = parsed if isinstance(parsed, list) else (parsed or {}).get("entries") or []
    if not entries:
        pytest.skip("No dataviews available for find test")
    name = str(entries[0].get("name", ""))
    if not name:
        pytest.skip("Dataview has no name")
    # Use first 2 chars as search keyword to get a broad match
    keyword = name[:2]

    result = await cli_agent.run_cli("dataview", "find", "--name", keyword)
    scorer.assert_exit_code(result, 0, "dataview find")
    scorer.assert_json(result, "dataview find returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("dataview_find", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_dataview_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case, dataview_id: str,
):
    """dataview query executes SQL and returns data rows."""
    result = await cli_agent.run_cli(
        "dataview", "query", dataview_id, "--limit", "3",
    )
    scorer.assert_exit_code(result, 0, "dataview query")
    scorer.assert_json(result, "dataview query returns JSON")
    if isinstance(result.parsed_json, dict):
        entries = result.parsed_json.get("entries") or result.parsed_json.get("data") or []
        scorer.assert_true(
            isinstance(entries, list),
            "dataview query returns entries array",
        )
    det = scorer.result(result.duration_ms)
    await eval_case("dataview_query", [result], det, module="adp/vega")
    assert det.passed, det.failures
