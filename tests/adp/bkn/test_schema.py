"""BKN schema (object-type, relation-type, action-type) acceptance tests."""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_bkn_object_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn object-type list returns object types for a KN."""
    result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="object-type list returns array")
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
    kn_id, ot_name = kn_with_data
    result = await cli_agent.run_cli("bkn", "object-type", "query", kn_id, ot_name)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_object_type_query", [result], det, module="adp/bkn")
    assert det.passed, det.failures
