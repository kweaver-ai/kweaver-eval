"""Agent config operations acceptance tests.

Covers:
  - agent.config.copy         — copy an agent's config
  - agent.config.ai_autogen   — AI-assisted content generation for agent
  - agent.avatar.built_in.list — list built-in avatar options

These operations are not exposed as dedicated CLI sub-commands; they are
reached via `kweaver call` targeting the decision-agent REST API.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_agent_avatar_builtin_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """GET /api/cognitive-search/v1/agent/built-in-avatar/list returns avatar options."""
    result = await cli_agent.run_cli(
        "call",
        "/api/cognitive-search/v1/agent/built-in-avatar/list",
    )
    # Endpoint may vary by deployment; accept 200 with JSON or a 404/redirect
    # that still indicates the agent service is reachable.
    if result.exit_code != 0 and "404" in result.stderr:
        pytest.skip("Built-in avatar list endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "avatar list exit code")
    scorer.assert_json(result, "avatar list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_avatar_builtin_list", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_config_copy(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """POST /api/cognitive-search/v1/agent/<id>/copy duplicates an agent's config."""
    import json

    result = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/agent/{chat_agent_id}/copy",
        "-X", "POST",
        "-d", json.dumps({}),
    )
    if result.exit_code != 0 and ("404" in result.stderr or "405" in result.stderr):
        pytest.skip("agent copy endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "agent config copy exit code")
    scorer.assert_json(result, "agent config copy returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_config_copy", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_config_ai_autogen(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """POST /api/cognitive-search/v1/agent/<id>/ai-autogen triggers AI content generation."""
    import json

    body = json.dumps({"type": "system_prompt"})
    result = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/agent/{chat_agent_id}/ai-autogen",
        "-X", "POST",
        "-d", body,
    )
    if result.exit_code != 0 and (
        "404" in result.stderr
        or "405" in result.stderr
        or "not implemented" in result.stderr.lower()
    ):
        pytest.skip("agent ai-autogen endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "agent ai-autogen exit code")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_config_ai_autogen", [result], det, module="adp/agent")
    assert det.passed, det.failures
