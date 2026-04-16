"""Vega resource acceptance tests.

resource query is covered by test_lifecycle.py (self-created catalog with
physical resources, avoids dependency on environment data).
"""

from __future__ import annotations

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


async def test_vega_resource_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case, resource_id: str,
):
    """vega resource get returns resource details."""
    result = await cli_agent.run_cli("vega", "resource", "get", resource_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_resource_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_resource_list_all(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """vega resource list-all returns resources via /resources/list endpoint."""
    result = await cli_agent.run_cli("vega", "resource", "list-all")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_resource_list_all", [result], det, module="adp/vega")
    assert det.passed, det.failures
