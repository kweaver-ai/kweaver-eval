"""Agent release workflow acceptance tests.

Covers:
  - agent.release.list    — list release versions for an agent
  - agent.release.create  — create a new release (snapshot)
  - agent.release.publish — publish a release

These operations target the decision-agent release API via `kweaver call`.
"""

from __future__ import annotations

import json

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_agent_release_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case, chat_agent_id: str,
):
    """GET /api/cognitive-search/v1/agent/<id>/release/list returns release versions."""
    result = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/agent/{chat_agent_id}/release/list",
    )
    if result.exit_code != 0 and (
        "404" in result.stderr or "405" in result.stderr
    ):
        pytest.skip("agent release list endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "release list exit code")
    scorer.assert_json(result, "release list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_release_list", [result], det, module="adp/agent")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_agent_release_create_and_publish(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """Agent release: create a version snapshot, then publish it."""
    agent_id = owned_agent["id"]
    steps = []
    release_id = ""

    # Step 1: create release
    create = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/agent/{agent_id}/release",
        "-X", "POST",
        "-d", json.dumps({"description": "eval test release"}),
    )
    steps.append(create)
    if create.exit_code != 0 and (
        "404" in create.stderr or "405" in create.stderr
    ):
        pytest.skip("agent release create endpoint not available")
    scorer.assert_exit_code(create, 0, "release create exit code")
    scorer.assert_json(create, "release create returns JSON")
    if isinstance(create.parsed_json, dict):
        release_id = str(
            create.parsed_json.get("id")
            or create.parsed_json.get("release_id")
            or "",
        )
    scorer.assert_true(bool(release_id), "release create returns ID")

    # Step 2: publish release
    if release_id:
        publish = await cli_agent.run_cli(
            "call",
            f"/api/cognitive-search/v1/agent/{agent_id}/release/{release_id}/publish",
            "-X", "POST",
            "-d", json.dumps({}),
        )
        steps.append(publish)
        scorer.assert_exit_code(publish, 0, "release publish exit code")

    det = scorer.result()
    await eval_case(
        "agent_release_create_and_publish", steps, det, module="adp/agent",
    )
    assert det.passed, det.failures
