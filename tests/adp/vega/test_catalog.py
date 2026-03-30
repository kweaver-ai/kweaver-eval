"""Vega catalog acceptance tests."""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_vega_catalog_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega catalog list returns catalogs."""
    result = await cli_agent.run_cli("vega", "catalog", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_catalog_get(cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str):
    """vega catalog get returns catalog details."""
    result = await cli_agent.run_cli("vega", "catalog", "get", catalog_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_catalog_health(cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str):
    """vega catalog health returns health status for a catalog."""
    result = await cli_agent.run_cli("vega", "catalog", "health", catalog_id)
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_health", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_catalog_test_connection(
    cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str
):
    """vega catalog test-connection verifies catalog connectivity."""
    result = await cli_agent.run_cli("vega", "catalog", "test-connection", catalog_id)
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_test_connection", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_catalog_resources(
    cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str
):
    """vega catalog resources lists resources under a catalog."""
    result = await cli_agent.run_cli("vega", "catalog", "resources", catalog_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_resources", [result], det, module="adp/vega")
    assert det.passed, det.failures
