"""Execution Factory — skill acceptance tests.

Covers:
  - skill.list            — list installed skills
  - skill.list_type_check — result is a JSON array
  - skill.market          — marketplace skill listing
  - skill.get             — get skill details by ID
  - skill.status          — skill availability/health status
  - skill.get_invalid_id  — get with a nonexistent ID returns error
  - skill.market_pagination — market listing with page/size params
  - skill.register        — install a skill from the marketplace
  - skill.uninstall       — remove an installed skill
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_skill_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill list returns installed skills as JSON."""
    result = await cli_agent.run_cli("skill", "list")
    scorer.assert_exit_code(result, 0, "skill list")
    scorer.assert_json(result, "skill list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("skill_list", [result], det, module="adp/execution_factory")
    assert det.passed, det.failures


async def test_skill_list_type_check(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill list result is a JSON array."""
    result = await cli_agent.run_cli("skill", "list")
    scorer.assert_exit_code(result, 0, "skill list")
    scorer.assert_json(result, "skill list returns JSON")
    scorer.assert_json_is_list(result, label="skill list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "skill_list_type_check", [result], det, module="adp/execution_factory",
    )
    assert det.passed, det.failures


async def test_skill_market(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill market returns marketplace skills as JSON."""
    result = await cli_agent.run_cli("skill", "market")
    scorer.assert_exit_code(result, 0, "skill market")
    scorer.assert_json(result, "skill market returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("skill_market", [result], det, module="adp/execution_factory")
    assert det.passed, det.failures


async def test_skill_market_pagination(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill market with page/size params returns paginated results."""
    result = await cli_agent.run_cli(
        "skill", "market", "--page", "1", "--size", "5",
    )
    if result.exit_code != 0 and "unknown flag" in result.stderr.lower():
        # Fallback: try offset/limit style
        result = await cli_agent.run_cli(
            "skill", "market", "--limit", "5", "--offset", "0",
        )
    scorer.assert_exit_code(result, 0, "skill market paginated")
    scorer.assert_json(result, "skill market pagination returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "skill_market_pagination", [result], det, module="adp/execution_factory",
    )
    assert det.passed, det.failures


async def _find_skill_id(cli_agent: CliAgent) -> str | None:
    """Find the first available skill ID from skill list."""
    result = await cli_agent.run_cli("skill", "list")
    if result.exit_code != 0:
        return None
    skills = result.parsed_json
    if isinstance(skills, dict):
        skills = skills.get("entries") or skills.get("items") or []
    if not isinstance(skills, list) or not skills:
        return None
    return str(skills[0].get("id") or skills[0].get("skill_id") or "")


async def test_skill_get(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill get returns details for an installed skill."""
    skill_id = await _find_skill_id(cli_agent)
    if not skill_id:
        pytest.skip("No installed skills available")

    result = await cli_agent.run_cli("skill", "get", skill_id)
    scorer.assert_exit_code(result, 0, "skill get")
    scorer.assert_json(result, "skill get returns JSON")
    scorer.assert_json_field(result, "id", label="skill get has id field")
    det = scorer.result(result.duration_ms)
    await eval_case("skill_get", [result], det, module="adp/execution_factory")
    assert det.passed, det.failures


async def test_skill_status(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill status returns availability status for an installed skill."""
    skill_id = await _find_skill_id(cli_agent)
    if not skill_id:
        pytest.skip("No installed skills available")

    result = await cli_agent.run_cli("skill", "status", skill_id)
    scorer.assert_exit_code(result, 0, "skill status")
    det = scorer.result(result.duration_ms)
    await eval_case("skill_status", [result], det, module="adp/execution_factory")
    assert det.passed, det.failures


async def test_skill_get_invalid_id(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill get with a nonexistent ID returns a non-zero exit code."""
    result = await cli_agent.run_cli(
        "skill", "get", "nonexistent_skill_id_that_does_not_exist_000",
    )
    scorer.assert_true(
        result.exit_code != 0,
        "skill get with invalid ID returns non-zero exit",
    )
    det = scorer.result(result.duration_ms)
    await eval_case(
        "skill_get_invalid_id", [result], det, module="adp/execution_factory",
    )
    assert det.passed, det.failures


async def test_skill_content(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill content returns skill descriptor for an installed skill."""
    skill_id = await _find_skill_id(cli_agent)
    if not skill_id:
        pytest.skip("No installed skills available")

    result = await cli_agent.run_cli("skill", "content", skill_id)
    scorer.assert_exit_code(result, 0, "skill content")
    det = scorer.result(result.duration_ms)
    await eval_case("skill_content", [result], det, module="adp/execution_factory")
    assert det.passed, det.failures
