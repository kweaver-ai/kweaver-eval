"""Agent sessions, history, and trace acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer

from .test_chat import _extract_conversation_id


@pytest.fixture(scope="module")
async def _conversation(cli_agent: CliAgent, chat_agent_id: str) -> dict:
    """Create a single conversation shared by history/trace tests.

    Returns dict with 'agent_id' and 'cid'.
    """
    chat = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "你好",
        "--no-stream",
        timeout=60.0,
    )
    if chat.exit_code != 0:
        pytest.skip("Cannot create conversation for session tests")
    cid = _extract_conversation_id(chat.stdout + "\n" + chat.stderr)
    if not cid:
        pytest.skip("Cannot extract conversation_id from chat output")
    return {"agent_id": chat_agent_id, "cid": cid, "chat_result": chat}


async def test_agent_sessions(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
    _conversation: dict,
):
    """agent sessions lists conversations for an agent."""
    result = await cli_agent.run_cli(
        "agent", "sessions", chat_agent_id, "--limit", "10",
    )
    scorer.assert_exit_code(result, 0, "agent sessions")
    scorer.assert_json(result, "agent sessions returns JSON")
    if isinstance(result.parsed_json, dict):
        entries = result.parsed_json.get("entries") or []
        scorer.assert_true(len(entries) > 0, "sessions returns at least one entry")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_sessions", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_history(
    cli_agent: CliAgent, scorer: Scorer, eval_case, _conversation: dict,
):
    """agent history returns conversation detail with messages."""
    agent_id = _conversation["agent_id"]
    cid = _conversation["cid"]

    result = await cli_agent.run_cli(
        "agent", "history", agent_id, cid, "--limit", "10",
    )
    scorer.assert_exit_code(result, 0, "agent history")
    scorer.assert_json(result, "agent history returns JSON")
    if isinstance(result.parsed_json, dict):
        messages = result.parsed_json.get("Messages") or []
        scorer.assert_true(len(messages) > 0, "history contains messages")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_history", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_trace(
    cli_agent: CliAgent, scorer: Scorer, eval_case, _conversation: dict,
):
    """agent trace returns session trace data for a conversation."""
    agent_id = _conversation["agent_id"]
    cid = _conversation["cid"]

    result = await cli_agent.run_cli("agent", "trace", agent_id, cid)
    steps = [_conversation["chat_result"], result]
    scorer.assert_exit_code(result, 0, "agent trace")
    scorer.assert_json(result, "agent trace returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_trace", steps, det, module="adp/agent")
    assert det.passed, det.failures
