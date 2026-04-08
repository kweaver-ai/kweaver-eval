"""Agent error path tests — verify graceful handling of invalid inputs."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_agent_get_invalid_id(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent get with a non-existent ID returns non-zero exit code."""
    result = await cli_agent.run_cli("agent", "get", "nonexistent_id_000")
    scorer.assert_true(
        result.exit_code != 0,
        "agent get with invalid ID returns non-zero exit code",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_get_invalid_id", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_chat_invalid_id(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent chat with a non-existent agent ID fails gracefully."""
    result = await cli_agent.run_cli(
        "agent", "chat", "nonexistent_id_000",
        "-m", "hello",
        "--no-stream",
        timeout=30.0,
    )
    scorer.assert_true(
        result.exit_code != 0,
        "agent chat with invalid ID returns non-zero exit code",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_chat_invalid_id", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_delete_invalid_id(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent delete with a non-existent ID fails gracefully."""
    result = await cli_agent.run_cli(
        "agent", "delete", "nonexistent_id_000", "-y",
    )
    scorer.assert_true(
        result.exit_code != 0,
        "agent delete with invalid ID returns non-zero exit code",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_delete_invalid_id", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_get_by_key_invalid(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent get-by-key with a non-existent key fails gracefully."""
    result = await cli_agent.run_cli("agent", "get-by-key", "no_such_key_xyz")
    scorer.assert_true(
        result.exit_code != 0,
        "agent get-by-key with invalid key returns non-zero exit code",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_get_by_key_invalid", [result], det, module="adp/agent")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_agent_chat_invalid_cid(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """agent chat with a valid agent but invalid conversation_id fails or starts fresh."""
    result = await cli_agent.run_cli(
        "agent", "chat", chat_agent_id,
        "-m", "hello",
        "-cid", "invalid_conversation_000",
        "--no-stream",
        timeout=30.0,
    )
    # Some backends may start a new conversation; others may error.
    # Either way, no crash / hang is the key assertion.
    scorer.assert_true(
        result.exit_code is not None,
        "agent chat with invalid cid completes without hanging",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_chat_invalid_cid", [result], det, module="adp/agent")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_agent_create_duplicate_key(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """agent create with a duplicate key fails gracefully."""
    existing_key = owned_agent["key"]
    result = await cli_agent.run_cli(
        "agent", "create",
        "--name", "eval_dup_key_test",
        "--profile", "Duplicate key test — should fail",
        "--key", existing_key,
        "--system-prompt", "test",
        "--llm-id", "any",
    )
    # Duplicate key should be rejected
    scorer.assert_true(
        result.exit_code != 0,
        "agent create with duplicate key returns non-zero exit code",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("agent_create_duplicate_key", [result], det, module="adp/agent")
    assert det.passed, det.failures
