"""Agent CRUD acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.recorder import Recorder
from lib.scorer import Scorer
from lib.types import CaseResult


async def _find_agent(cli_agent: CliAgent) -> str | None:
    """Find an accessible agent ID."""
    result = await cli_agent.run_cli("agent", "list", "--json")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return None
    for agent in result.parsed_json:
        agent_id = str(agent.get("id") or agent.get("agent_id") or "")
        if agent_id:
            return agent_id
    return None


async def test_agent_list(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """agent list returns a JSON array."""
    result = await cli_agent.run_cli("agent", "list", "--json")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="agent list returns array")

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_agent_list",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


async def test_agent_get(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """agent get returns agent detail."""
    agent_id = await _find_agent(cli_agent)
    if not agent_id:
        pytest.skip("No agents available")

    result = await cli_agent.run_cli("agent", "get", agent_id, "--json")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_agent_get",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


async def test_agent_get_verbose(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """agent get --verbose returns full config."""
    agent_id = await _find_agent(cli_agent)
    if not agent_id:
        pytest.skip("No agents available")

    result = await cli_agent.run_cli("agent", "get", agent_id, "--verbose", "--json")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_agent_get_verbose",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures
