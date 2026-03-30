"""Vega resource acceptance tests."""

from __future__ import annotations

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


