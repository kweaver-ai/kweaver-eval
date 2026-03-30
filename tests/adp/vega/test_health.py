"""Vega health/stats/inspect acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_vega_health(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega health returns service health status."""
    result = await cli_agent.run_cli("vega", "health")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_health", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_stats(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega stats returns catalog statistics."""
    result = await cli_agent.run_cli("vega", "stats")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_stats", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_inspect(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega inspect returns combined health + catalog + tasks report."""
    result = await cli_agent.run_cli("vega", "inspect")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_inspect", [result], det, module="adp/vega")
    assert det.passed, det.failures
