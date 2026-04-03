"""Agent sessions, history, and trace acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_agent_sessions(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """agent sessions lists conversations for an agent."""
    # Do a quick chat first to ensure at least one session exists
    await cli_agent.run_cli(
        "agent", "chat", chat_agent_id, "-m", "你好", "--no-stream",
        timeout=60.0,
    )

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
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """agent history returns conversation detail with messages."""
    # Chat to get a conversation_id
    chat = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "你好",
        "--no-stream",
        timeout=60.0,
    )
    if chat.exit_code != 0:
        pytest.skip("Cannot create conversation for history test")

    from .test_chat import _extract_conversation_id
    cid = _extract_conversation_id(chat.stdout + "\n" + chat.stderr)
    if not cid:
        pytest.skip("Cannot extract conversation_id from chat output")

    # history now requires agent_id + conversation_id
    result = await cli_agent.run_cli(
        "agent", "history", chat_agent_id, cid, "--limit", "10",
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
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """agent trace returns session trace data for a conversation."""
    # Chat to get a conversation_id
    chat = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "你好",
        "--no-stream",
        timeout=60.0,
    )
    if chat.exit_code != 0:
        pytest.skip("Cannot create conversation for trace test")

    from .test_chat import _extract_conversation_id
    cid = _extract_conversation_id(chat.stdout + "\n" + chat.stderr)
    if not cid:
        pytest.skip("Cannot extract conversation_id from chat output")

    # trace now requires agent_id + conversation_id
    result = await cli_agent.run_cli("agent", "trace", chat_agent_id, cid)
    steps = [chat, result]
    scorer.assert_exit_code(result, 0, "agent trace")
    scorer.assert_json(result, "agent trace returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_trace", steps, det, module="adp/agent")
    assert det.passed, det.failures
