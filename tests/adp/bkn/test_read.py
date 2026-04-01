"""BKN read-only acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_bkn_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """bkn list returns a JSON array of knowledge networks."""
    result = await cli_agent.run_cli("bkn", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="bkn list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_export(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn export returns KN data as JSON."""
    result = await cli_agent.run_cli("bkn", "export", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_export", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_search(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn search returns results for a query."""
    result = await cli_agent.run_cli("bkn", "search", kn_id, "test")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_search", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_get(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn get returns knowledge network details."""
    result = await cli_agent.run_cli("bkn", "get", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_get", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_stats(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn stats returns statistics for a knowledge network."""
    result = await cli_agent.run_cli("bkn", "stats", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_stats", [result], det, module="adp/bkn")
    assert det.passed, det.failures
