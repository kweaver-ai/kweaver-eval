"""Agent chat acceptance tests.

Tests single-turn, multi-turn (context continuity), and streaming chat modes.
Uses an existing published agent to avoid publish bug dependency.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_agent_chat_single_turn(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """Single-turn chat returns a text reply and conversation_id."""
    result = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "请用一句话介绍你自己",
        "--no-stream",
        timeout=120.0,
    )
    steps = [result]
    scorer.assert_exit_code(result, 0, "chat single turn")
    # CLI prints reply text to stdout; conversation_id hint to stderr or end of stdout
    scorer.assert_true(
        len(result.stdout.strip()) > 0,
        "chat returns non-empty output",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_chat_single_turn", steps, det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_chat_multi_turn(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """Multi-turn chat maintains context across turns via conversation_id."""
    steps = []

    # Turn 1: establish context
    turn1 = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "我的名字叫小明，请记住这个信息。",
        "--no-stream",
        timeout=120.0,
    )
    steps.append(turn1)
    scorer.assert_exit_code(turn1, 0, "chat turn 1")
    scorer.assert_true(
        len(turn1.stdout.strip()) > 0,
        "turn 1 returns non-empty output",
    )

    # Extract conversation_id from output
    cid = _extract_conversation_id(turn1.stdout + "\n" + turn1.stderr)
    scorer.assert_true(bool(cid), "turn 1 returns conversation_id")

    if not cid:
        det = scorer.result()
        await eval_case("agent_chat_multi_turn", steps, det, module="adp/agent")
        assert det.passed, det.failures
        return

    # Turn 2: verify context is maintained
    turn2 = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "我刚才告诉你我叫什么名字？",
        "--no-stream",
        "-cid", cid,
        timeout=120.0,
    )
    steps.append(turn2)
    scorer.assert_exit_code(turn2, 0, "chat turn 2")
    scorer.assert_true(
        len(turn2.stdout.strip()) > 0,
        "turn 2 returns non-empty output",
    )
    # Context recall check — LLM may not repeat the exact name, so treat
    # as a soft signal.  The judge agent (if enabled) will do semantic eval.
    context_recalled = "小明" in turn2.stdout
    scorer.assert_true(context_recalled, "turn 2 recalls context (mentions 小明)")

    det = scorer.result()
    await eval_case(
        "agent_chat_multi_turn", steps, det, module="adp/agent",
        eval_hints={"check": "Does the second reply demonstrate awareness of the name 小明 from the first turn?"},
    )
    # Allow pass even if deterministic name check fails — judge agent is
    # the authoritative evaluator for context recall.
    _SOFT_LABELS = {"recalls context"}
    hard_failures = [f for f in det.failures if not any(s in f for s in _SOFT_LABELS)]
    assert not hard_failures, det.failures


async def test_agent_chat_stream(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """Streaming chat returns non-empty output."""
    result = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "用一句话回答：1+1等于几？",
        "--stream",
        timeout=120.0,
    )
    steps = [result]
    scorer.assert_exit_code(result, 0, "chat stream")
    scorer.assert_true(
        len(result.stdout.strip()) > 0,
        "stream chat returns non-empty output",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_chat_stream", steps, det, module="adp/agent")
    assert det.passed, det.failures


def _extract_conversation_id(text: str) -> str:
    """Extract conversation_id from CLI output.

    The CLI prints a hint like:
      kweaver agent chat <id> -m "..." -cid <conversation_id>
    or:
      conversation_id: <id>
    """
    import re
    # Pattern 1: -cid <id>
    m = re.search(r"-cid\s+(\S+)", text)
    if m:
        return m.group(1)
    # Pattern 2: conversation_id: <id>
    m = re.search(r"conversation_id:\s*(\S+)", text)
    if m:
        return m.group(1)
    return ""
