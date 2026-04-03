"""Agent CRUD lifecycle acceptance tests (destructive).

Lifecycle: create -> get -> get --verbose -> get-by-key -> update -> delete.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer

from .conftest import _agent_name


@pytest.mark.destructive
async def test_agent_crud_lifecycle(
    cli_agent: CliAgent, scorer: Scorer, eval_case, llm_id: str,
):
    """Agent lifecycle: create -> get -> get --verbose -> get-by-key -> update -> delete."""
    name = _agent_name()
    agent_key = f"{name}_key"
    agent_id = ""
    steps = []

    try:
        # Step 1: create
        create = await cli_agent.run_cli(
            "agent", "create",
            "--name", name,
            "--profile", "Eval test agent — safe to delete",
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
        get_v = await cli_agent.run_cli("agent", "get", agent_id, "--verbose")
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
        new_name = f"{name}_updated"
        update = await cli_agent.run_cli(
            "agent", "update", agent_id, "--name", new_name,
        )
        steps.append(update)
        scorer.assert_exit_code(update, 0, "agent update")

        # Step 4b: verify update
        verify = await cli_agent.run_cli("agent", "get", agent_id, "--verbose")
        steps.append(verify)
        scorer.assert_exit_code(verify, 0, "agent get after update")
        if isinstance(verify.parsed_json, dict):
            scorer.assert_true(
                verify.parsed_json.get("name") == new_name,
                "agent name updated",
            )

    finally:
        if agent_id:
            delete = await cli_agent.run_cli("agent", "delete", agent_id, "-y")
            steps.append(delete)
            scorer.assert_exit_code(delete, 0, "agent delete")

    det = scorer.result()
    await eval_case("agent_crud_lifecycle", steps, det, module="adp/agent")
    assert det.passed, det.failures
