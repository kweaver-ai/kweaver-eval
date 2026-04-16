"""Agent catalog acceptance tests.

Covers:
  - agent.personal_list   — list agents in personal workspace
  - agent.category.list   — list agent categories
  - agent.template.list   — list published agent templates
  - agent.template.get    — get a template by ID
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_agent_personal_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent personal-list returns agents in the personal workspace."""
    result = await cli_agent.run_cli("agent", "personal-list")
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        pytest.skip("agent personal-list not available in this SDK version")
    scorer.assert_exit_code(result, 0, "agent personal-list")
    scorer.assert_json(result, "personal-list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_personal_list", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_category_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent category-list returns available categories."""
    result = await cli_agent.run_cli("agent", "category-list")
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        pytest.skip("agent category-list not available in this SDK version")
    scorer.assert_exit_code(result, 0, "agent category-list")
    scorer.assert_json(result, "category-list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_category_list", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_template_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent template-list returns published agent templates."""
    result = await cli_agent.run_cli("agent", "template-list")
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        pytest.skip("agent template-list not available in this SDK version")
    scorer.assert_exit_code(result, 0, "agent template-list")
    scorer.assert_json(result, "template-list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_template_list", [result], det, module="adp/agent")
    assert det.passed, det.failures


async def test_agent_template_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent template-get returns a specific template by ID."""
    # First discover a template ID
    list_result = await cli_agent.run_cli("agent", "template-list")
    if list_result.exit_code != 0:
        pytest.skip("Cannot list templates")
    templates = list_result.parsed_json
    if isinstance(templates, dict):
        templates = (
            templates.get("entries")
            or templates.get("items")
            or templates.get("data")
            or []
        )
    if not isinstance(templates, list) or not templates:
        pytest.skip("No templates available")
    tmpl_id = str(templates[0].get("id") or templates[0].get("template_id") or "")
    if not tmpl_id:
        pytest.skip("Cannot determine template ID")

    result = await cli_agent.run_cli("agent", "template-get", tmpl_id)
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        pytest.skip("agent template-get not available in this SDK version")
    scorer.assert_exit_code(result, 0, "agent template-get")
    scorer.assert_json(result, "template-get returns JSON")
    scorer.assert_json_field(result, "id", label="template-get returns id field")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_template_get", [result], det, module="adp/agent")
    assert det.passed, det.failures
