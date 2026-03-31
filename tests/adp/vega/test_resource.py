"""Vega resource acceptance tests."""

from __future__ import annotations

import json

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_vega_resource_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega resource list returns resources."""
    result = await cli_agent.run_cli("vega", "resource", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_resource_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_resource_get(cli_agent: CliAgent, scorer: Scorer, eval_case, resource_id: str):
    """vega resource get returns resource details."""
    result = await cli_agent.run_cli("vega", "resource", "get", resource_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_resource_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


@pytest.mark.tbd("No persistent physical resource — lifecycle cleans up")
async def test_vega_resource_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """vega resource query executes a data query against a physical resource."""
    # Find a resource from a physical catalog (query only works on physical)
    list_result = await cli_agent.run_cli("vega", "resource", "list")
    if list_result.exit_code != 0:
        pytest.skip("Cannot list resources")
    resources = list_result.parsed_json
    if isinstance(resources, dict):
        resources = resources.get("entries") or resources.get("items") or []
    if not isinstance(resources, list):
        pytest.skip("No resources available")

    # Pick a resource with a non-empty catalog that is physical
    rid = ""
    for r in resources:
        cat_id = r.get("catalog_id", "")
        category = r.get("category", "")
        if cat_id and category in ("table", "index"):
            rid = str(r.get("id") or "")
            break
    if not rid:
        pytest.skip("No queryable (table/index) resource available")

    query_body = json.dumps({"limit": 5})
    result = await cli_agent.run_cli(
        "vega", "resource", "query", rid, "-d", query_body,
    )
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_resource_query", [result], det, module="adp/vega")
    assert det.passed, det.failures
