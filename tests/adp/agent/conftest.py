"""Agent module conftest — fixtures for decision agent tests."""

from __future__ import annotations

import random
import string
import time

import pytest

from lib.agents.cli_agent import CliAgent

EVAL_PREFIX = "eval_"


def _short_suffix() -> str:
    """Return a short random suffix like 'a3x' to avoid name collisions."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=4))


def _agent_name() -> str:
    """Generate a unique eval agent name."""
    return f"{EVAL_PREFIX}agent_{int(time.time())}_{_short_suffix()}"


# ---------------------------------------------------------------------------
# Resource cleanup helpers
# ---------------------------------------------------------------------------

async def _list_eval_agents(cli_agent: CliAgent) -> list[str]:
    """Return IDs of agents whose name starts with EVAL_PREFIX."""
    result = await cli_agent.run_cli("agent", "list", "--limit", "100")
    parsed = result.parsed_json
    if result.exit_code != 0 or parsed is None:
        return []
    entries = parsed if isinstance(parsed, list) else parsed.get("entries") or parsed.get("data") or []
    if not isinstance(entries, list):
        return []
    return [
        str(a.get("id") or a.get("agent_id") or "")
        for a in entries
        if str(a.get("name", "")).startswith(EVAL_PREFIX)
    ]


async def _cleanup_eval_agents(cli_agent: CliAgent) -> None:
    """Delete all eval_ prefixed agents."""
    for agent_id in await _list_eval_agents(cli_agent):
        if agent_id:
            await cli_agent.run_cli("agent", "delete", agent_id, "-y")


# ---------------------------------------------------------------------------
# Session-level fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
async def cleanup_eval_agent_resources(cli_agent: CliAgent):
    """Clean up residual eval_ agents before and after the test session."""
    await _cleanup_eval_agents(cli_agent)
    yield
    await _cleanup_eval_agents(cli_agent)


@pytest.fixture(scope="session")
async def llm_id(cli_agent: CliAgent) -> str:
    """Discover first available LLM model ID from model-factory."""
    result = await cli_agent.run_cli(
        "call", "/api/mf-model-manager/v1/llm/list?page=1&size=10",
    )
    if result.exit_code != 0 or not isinstance(result.parsed_json, dict):
        pytest.skip("Cannot query model-factory for LLM models")
    models = result.parsed_json.get("data") or []
    if not isinstance(models, list):
        pytest.skip("No LLM models returned from model-factory")
    for m in models:
        if isinstance(m, dict) and m.get("model_type") == "llm":
            mid = str(m.get("model_id") or "")
            if mid:
                return mid
    pytest.skip("No LLM model available in model-factory")


@pytest.fixture(scope="session")
async def chat_agent_id(cli_agent: CliAgent) -> str:
    """Find an existing published agent that can actually respond to chat.

    Iterates through agents and does a quick probe chat to verify.
    """
    result = await cli_agent.run_cli("agent", "list", "--limit", "30", "--verbose")
    parsed = result.parsed_json
    if result.exit_code != 0 or parsed is None:
        pytest.skip("Cannot list agents")
    entries = parsed if isinstance(parsed, list) else parsed.get("entries") or parsed.get("data") or []
    if not isinstance(entries, list) or len(entries) == 0:
        pytest.skip("No agents available for chat testing")

    # Prefer non-built-in agents first, then built-in
    candidates = []
    for a in entries:
        if isinstance(a, dict):
            aid = str(a.get("id") or a.get("agent_id") or "")
            if aid:
                candidates.append((aid, a.get("is_built_in", 0)))
    candidates.sort(key=lambda x: x[1])  # non-built-in first

    for aid, _ in candidates:
        probe = await cli_agent.run_cli(
            "agent", "chat", aid, "-m", "hi", "--no-stream",
            timeout=30.0,
        )
        if probe.exit_code == 0 and len(probe.stdout.strip()) > 0:
            return aid

    pytest.skip("No agents available that can respond to chat")


@pytest.fixture(scope="session")
async def owned_agent(cli_agent: CliAgent, llm_id: str) -> dict:
    """Create a session-scoped eval agent owned by current user.

    Returns dict with 'id' and 'key'. Cleaned up by cleanup_eval_agent_resources.
    Used for get/get-by-key tests that require ownership.
    """
    name = _agent_name()
    key = f"{name}_key"
    result = await cli_agent.run_cli(
        "agent", "create",
        "--name", name,
        "--profile", "Eval session agent — safe to delete",
        "--key", key,
        "--system-prompt", "You are a test assistant.",
        "--llm-id", llm_id,
    )
    if result.exit_code != 0 or not isinstance(result.parsed_json, dict):
        pytest.skip("Cannot create eval agent for read tests")
    agent_id = str(result.parsed_json.get("id") or "")
    if not agent_id:
        pytest.skip("Agent create did not return ID")
    return {"id": agent_id, "key": key, "name": name}
