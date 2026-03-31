"""Agent CRUD lifecycle acceptance tests (destructive).

Ported from kweaver-sdk e2e/agent-crud.test.ts.
Lifecycle: create -> get -> get-by-key -> update -> delete.
Publish/unpublish skipped due to known backend bug (nil pointer in
FillPublishedByName).
"""

from __future__ import annotations

import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer

TEST_PREFIX = f"eval_agent_{int(time.time())}"


async def _find_llm_model(cli_agent: CliAgent) -> str | None:
    """Discover first available LLM model ID via agent create --help dry-run.

    Falls back to checking model-factory API via kweaver call.
    """
    result = await cli_agent.run_cli(
        "call", "/api/mf-model-manager/v1/llm/list?page=1&size=10",
    )
    if result.exit_code != 0 or not isinstance(result.parsed_json, dict):
        return None
    models = result.parsed_json.get("data") or []
    if not isinstance(models, list):
        return None
    for m in models:
        if isinstance(m, dict) and m.get("model_type") == "llm":
            return str(m.get("model_id") or "")
    return None


@pytest.mark.destructive
async def test_agent_crud_lifecycle(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """Agent lifecycle: create -> get -> get --verbose -> get-by-key -> update -> delete."""
    llm_id = await _find_llm_model(cli_agent)
    if not llm_id:
        pytest.skip("No LLM model available in model-factory")

    agent_id = ""
    agent_key = f"{TEST_PREFIX}_key"
    steps = []

    try:
        # Step 1: create
        create = await cli_agent.run_cli(
            "agent", "create",
            "--name", f"{TEST_PREFIX}_agent",
            "--profile", "Eval test agent - safe to delete",
            "--key", agent_key,
            "--system-prompt", "You are a test assistant.",
            "--llm-id", llm_id,
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "agent create")
        scorer.assert_json(create, "agent create returns JSON")
        if isinstance(create.parsed_json, dict):
            agent_id = str(create.parsed_json.get("id") or "")
        scorer.assert_true(bool(agent_id), "agent create returns ID")

        # Step 2: get
        get = await cli_agent.run_cli("agent", "get", agent_id)
        steps.append(get)
        scorer.assert_exit_code(get, 0, "agent get")
        scorer.assert_json(get, "agent get returns JSON")

        # Step 2b: get --verbose
        get_v = await cli_agent.run_cli(
            "agent", "get", agent_id, "--verbose",
        )
        steps.append(get_v)
        scorer.assert_exit_code(get_v, 0, "agent get --verbose")
        scorer.assert_json(get_v, "agent get --verbose returns JSON")

        # Step 3: get-by-key
        get_key = await cli_agent.run_cli("agent", "get-by-key", agent_key)
        steps.append(get_key)
        scorer.assert_exit_code(get_key, 0, "agent get-by-key")
        scorer.assert_json(get_key, "agent get-by-key returns JSON")
        if isinstance(get_key.parsed_json, dict):
            scorer.assert_true(
                get_key.parsed_json.get("id") == agent_id,
                "get-by-key returns same agent ID",
            )

        # Step 4: update
        new_name = f"{TEST_PREFIX}_updated"
        update = await cli_agent.run_cli(
            "agent", "update", agent_id, "--name", new_name,
        )
        steps.append(update)
        scorer.assert_exit_code(update, 0, "agent update")

        # Verify update
        verify = await cli_agent.run_cli("agent", "get", agent_id)
        steps.append(verify)
        scorer.assert_exit_code(verify, 0, "agent get after update")
        if isinstance(verify.parsed_json, dict):
            scorer.assert_true(
                verify.parsed_json.get("name") == new_name,
                "agent name updated",
            )

        # Note: publish/unpublish skipped — known backend bug
        # (nil pointer in FillPublishedByName)

    finally:
        if agent_id:
            await cli_agent.run_cli("agent", "delete", agent_id, "-y")

    det = scorer.result()
    await eval_case("agent_crud_lifecycle", steps, det)
    assert det.passed, det.failures
