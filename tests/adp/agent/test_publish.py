"""Agent publish/unpublish acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer

from .conftest import _agent_name


@pytest.mark.destructive
async def test_agent_publish_unpublish(
    cli_agent: CliAgent, scorer: Scorer, eval_case, llm_id: str,
):
    """Agent publish/unpublish lifecycle: create -> publish -> unpublish -> delete."""
    name = _agent_name()
    agent_id = ""
    steps = []

    try:
        # Step 1: create agent
        create = await cli_agent.run_cli(
            "agent", "create",
            "--name", name,
            "--profile", "Eval publish test — safe to delete",
            "--key", f"{name}_key",
            "--system-prompt", "You are a test assistant.",
            "--llm-id", llm_id,
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "agent create")
        if isinstance(create.parsed_json, dict):
            agent_id = str(create.parsed_json.get("id") or "")
        scorer.assert_true(bool(agent_id), "agent create returns ID")

        # Step 2: publish
        publish = await cli_agent.run_cli("agent", "publish", agent_id)
        steps.append(publish)
        combined = publish.stdout + publish.stderr
        if publish.exit_code != 0 and "Permission" in combined:
            pytest.skip("Current user does not have publish permission")
        scorer.assert_exit_code(publish, 0, "agent publish")

        # Step 3: unpublish
        unpublish = await cli_agent.run_cli("agent", "unpublish", agent_id)
        steps.append(unpublish)
        scorer.assert_exit_code(unpublish, 0, "agent unpublish")

    finally:
        if agent_id:
            delete = await cli_agent.run_cli("agent", "delete", agent_id, "-y")
            steps.append(delete)

    det = scorer.result()
    await eval_case("agent_publish_unpublish", steps, det, module="adp/agent")
    assert det.passed, det.failures
