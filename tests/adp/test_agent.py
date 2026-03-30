"""Agent CRUD acceptance tests.

Temporarily located under adp/. Will move to tests/decision_agent/
when that product line is set up.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def _find_accessible_agent(cli_agent: CliAgent) -> str | None:
    """Find an agent ID that the current user can access."""
    result = await cli_agent.run_cli("agent", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return None
    for agent in result.parsed_json:
        agent_id = str(agent.get("id") or agent.get("agent_id") or "")
        if not agent_id:
            continue
        check = await cli_agent.run_cli("agent", "get", agent_id)
        if check.exit_code == 0:
            return agent_id
    return None


async def test_agent_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """agent list returns a JSON array."""
    result = await cli_agent.run_cli("agent", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="agent list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_list", [result], det)
    assert det.passed, det.failures


async def test_agent_get(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """agent get returns agent detail."""
    agent_id = await _find_accessible_agent(cli_agent)
    if not agent_id:
        pytest.skip("No accessible agents available")
    result = await cli_agent.run_cli("agent", "get", agent_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("agent_get", [result], det)
    assert det.passed, det.failures


async def test_agent_get_verbose(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """agent get --verbose returns full config."""
    agent_id = await _find_accessible_agent(cli_agent)
    if not agent_id:
        pytest.skip("No accessible agents available")
    result = await cli_agent.run_cli("agent", "get", agent_id, "--verbose")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("agent_get_verbose", [result], det)
    assert det.passed, det.failures
