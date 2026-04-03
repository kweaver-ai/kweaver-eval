"""Agent read-only acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_agent_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """agent list returns a JSON array of published agents."""
    result = await cli_agent.run_cli("agent", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="agent list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_list", [result], det, module="adp/agent")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_agent_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """agent get returns agent details by ID (requires ownership)."""
    agent_id = owned_agent["id"]
    result = await cli_agent.run_cli("agent", "get", agent_id, "--verbose")
    scorer.assert_exit_code(result, 0, "agent get")
    scorer.assert_json(result, "agent get returns JSON")
    scorer.assert_json_field(result, "id", label="agent get returns id field")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_get", [result], det, module="adp/agent")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_agent_get_by_key(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """agent get-by-key returns the same agent as get by ID."""
    agent_id = owned_agent["id"]
    agent_key = owned_agent["key"]
    result = await cli_agent.run_cli("agent", "get-by-key", agent_key)
    scorer.assert_exit_code(result, 0, "agent get-by-key")
    scorer.assert_json(result, "agent get-by-key returns JSON")
    if isinstance(result.parsed_json, dict):
        scorer.assert_true(
            result.parsed_json.get("id") == agent_id,
            "get-by-key returns same agent ID",
        )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_get_by_key", [result], det, module="adp/agent")
    assert det.passed, det.failures
