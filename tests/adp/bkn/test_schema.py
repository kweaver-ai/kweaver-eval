"""BKN schema (object-type, relation-type, action-type) acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_bkn_object_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn object-type list returns object types for a KN."""
    result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    # CLI may return list or {entries: list}
    data = result.parsed_json
    if isinstance(data, dict):
        data = data.get("entries", data)
    scorer.assert_true(isinstance(data, list), "object-type list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_object_type_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_relation_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn relation-type list returns relation types for a KN."""
    result = await cli_agent.run_cli("bkn", "relation-type", "list", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_relation_type_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_object_type_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case, kn_with_data: tuple[str, str]
):
    """bkn object-type query returns instances for an object type."""
    kn_id, ot_id = kn_with_data
    result = await cli_agent.run_cli("bkn", "object-type", "query", kn_id, ot_id)
    if result.exit_code != 0 and "500" in (result.stderr + result.stdout):
        pytest.skip("Backend 500 — KN data source may be unavailable")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_object_type_query", [result], det, module="adp/bkn")
    assert det.passed, det.failures
