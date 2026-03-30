"""Datasource read-only acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_datasource_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """ds list returns a JSON dict with an entries array."""
    result = await cli_agent.run_cli("ds", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_true(
        isinstance(result.parsed_json, dict)
        and isinstance(result.parsed_json.get("entries"), list),
        "ds list returns dict with entries array",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("ds_list", [result], det, module="adp/ds")
    assert det.passed, det.failures


async def test_datasource_get(cli_agent: CliAgent, scorer: Scorer, eval_case, ds_id: str):
    """ds get retrieves a specific datasource by ID."""
    result = await cli_agent.run_cli("ds", "get", ds_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("ds_get", [result], det, module="adp/ds")
    assert det.passed, det.failures


async def test_datasource_tables(cli_agent: CliAgent, scorer: Scorer, eval_case, ds_id: str):
    """ds tables returns table info for a datasource."""
    result = await cli_agent.run_cli("ds", "tables", ds_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("ds_tables", [result], det, module="adp/ds")
    assert det.passed, det.failures
