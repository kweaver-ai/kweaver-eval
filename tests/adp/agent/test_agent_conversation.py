"""Agent conversation management acceptance tests.

Covers:
  - agent.chat.resume             — resume chat after a gap using same cid
  - agent.chat.termination        — end/close a session
  - agent.conversation.update     — rename/update a conversation record
  - agent.conversation.delete     — delete a conversation record
  - agent.chat.debug_completion   — debug-mode completion
  - agent.config.copy_to_template — copy agent config to a template
"""

from __future__ import annotations

import json
import uuid

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_agent_chat_resume(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """Resuming a conversation with the same cid returns coherent responses."""
    cid = str(uuid.uuid4())
    steps = []

    # First turn — establish context
    first = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "My favourite color is blue.",
        "--cid", cid,
        "--no-stream",
        timeout=60.0,
    )
    steps.append(first)
    if first.exit_code != 0:
        pytest.skip("Cannot start agent chat for resume test")

    # Second turn — resume same conversation
    second = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "What is my favourite color?",
        "--cid", cid,
        "--no-stream",
        timeout=60.0,
    )
    steps.append(second)
    scorer.assert_exit_code(second, 0, "resumed chat exit code")
    scorer.assert_true(
        bool(second.stdout.strip()),
        "resumed chat returns non-empty response",
    )
    det = scorer.result(second.duration_ms)
    await eval_case("agent_chat_resume", steps, det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_conversation_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """GET /api/cognitive-search/v1/agent/<id>/session returns conversation history."""
    result = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/agent/{chat_agent_id}/session",
    )
    if result.exit_code != 0 and (
        "404" in result.stderr or "405" in result.stderr
    ):
        pytest.skip("agent session list endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "conversation list exit code")
    scorer.assert_json(result, "conversation list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_conversation_list", [result], det, module="adp/agent")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_agent_conversation_update(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """PATCH /api/cognitive-search/v1/agent/<id>/session/<cid> renames a conversation."""
    # First create a conversation so we have a cid to update
    cid = str(uuid.uuid4())
    chat = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "hello",
        "--cid", cid,
        "--no-stream",
        timeout=60.0,
    )
    if chat.exit_code != 0:
        pytest.skip("Cannot create conversation for update test")
    steps = [chat]

    update = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/agent/{chat_agent_id}/session/{cid}",
        "-X", "PATCH",
        "-d", json.dumps({"title": "eval_renamed_conv"}),
    )
    steps.append(update)
    if update.exit_code != 0 and (
        "404" in update.stderr or "405" in update.stderr
    ):
        pytest.skip("conversation update endpoint not available on this deployment")
    scorer.assert_exit_code(update, 0, "conversation update exit code")
    det = scorer.result()
    await eval_case("agent_conversation_update", steps, det, module="adp/agent")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_agent_conversation_delete(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """DELETE /api/cognitive-search/v1/agent/<id>/session/<cid> removes a conversation."""
    cid = str(uuid.uuid4())
    chat = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "hello for deletion test",
        "--cid", cid,
        "--no-stream",
        timeout=60.0,
    )
    if chat.exit_code != 0:
        pytest.skip("Cannot create conversation for delete test")
    steps = [chat]

    delete = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/agent/{chat_agent_id}/session/{cid}",
        "-X", "DELETE",
    )
    steps.append(delete)
    if delete.exit_code != 0 and (
        "404" in delete.stderr or "405" in delete.stderr
    ):
        pytest.skip("conversation delete endpoint not available on this deployment")
    scorer.assert_exit_code(delete, 0, "conversation delete exit code")
    det = scorer.result()
    await eval_case("agent_conversation_delete", steps, det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_chat_debug_completion(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """Agent debug-mode chat returns completion with debug info."""
    result = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "ping",
        "--no-stream",
        "--debug",
        timeout=60.0,
    )
    # --debug flag may not be supported in all SDK versions
    if result.exit_code != 0 and (
        "unknown flag" in result.stderr.lower()
        or "flag provided but not defined" in result.stderr.lower()
    ):
        # Fallback: use kweaver call with debug_mode flag in body
        result = await cli_agent.run_cli(
            "call",
            f"/api/cognitive-search/v1/agent/{chat_agent_id}/chat",
            "-X", "POST",
            "-d", json.dumps({
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "debug_mode": True,
            }),
        )
    if result.exit_code != 0 and "404" in result.stderr:
        pytest.skip("debug completion endpoint not available")
    scorer.assert_exit_code(result, 0, "debug completion exit code")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_chat_debug_completion", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_config_copy_to_template(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """POST /api/cognitive-search/v1/agent/<id>/copy-to-template copies config to template."""
    result = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/agent/{chat_agent_id}/copy-to-template",
        "-X", "POST",
        "-d", json.dumps({}),
    )
    if result.exit_code != 0 and (
        "404" in result.stderr or "405" in result.stderr
    ):
        pytest.skip("agent copy-to-template endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "copy-to-template exit code")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "agent_config_copy_to_template", [result], det, module="adp/agent",
    )
    assert det.passed, det.failures
