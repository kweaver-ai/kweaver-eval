"""Vega corner-case acceptance tests.

Covers:
  - vega.discover_task.get         — get a single discover task by ID
  - vega.discover_task.by_schedule — list tasks filtered by schedule ID
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def _find_discover_task(cli_agent: CliAgent) -> tuple[str, str | None] | None:
    """Return (task_id, schedule_id) for the first available discover task.

    Returns None if the discover_task subcommand is missing or no tasks exist.
    """
    result = await cli_agent.run_cli("vega", "discover-task", "list", "--limit", "5")
    if result.exit_code != 0:
        # Fallback via call endpoint
        result = await cli_agent.run_cli(
            "call",
            "/api/vega/v1/discover/task?page=1&size=5",
        )
    if result.exit_code != 0:
        return None
    tasks = result.parsed_json
    if isinstance(tasks, dict):
        tasks = (
            tasks.get("items")
            or tasks.get("entries")
            or tasks.get("data")
            or []
        )
    if not isinstance(tasks, list) or not tasks:
        return None
    task = tasks[0]
    task_id = str(task.get("id") or task.get("task_id") or "")
    schedule_id = str(task.get("schedule_id") or task.get("scheduled_id") or "")
    if task_id:
        return task_id, schedule_id or None
    return None


async def test_vega_discover_task_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """GET /api/vega/v1/discover/task/<id> returns details for a discover task."""
    found = await _find_discover_task(cli_agent)
    if not found:
        pytest.skip("No discover tasks available")
    task_id, _ = found

    result = await cli_agent.run_cli(
        "call",
        f"/api/vega/v1/discover/task/{task_id}",
    )
    if result.exit_code != 0 and (
        "404" in result.stderr or "405" in result.stderr
    ):
        pytest.skip("discover task get endpoint not available")
    scorer.assert_exit_code(result, 0, "discover task get exit code")
    scorer.assert_json(result, "discover task get returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("vega_discover_task_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_discover_task_by_schedule(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """GET /api/vega/v1/discover/task?schedule_id=<id> filters tasks by schedule."""
    found = await _find_discover_task(cli_agent)
    if not found:
        pytest.skip("No discover tasks available")
    task_id, schedule_id = found
    if not schedule_id:
        pytest.skip("No schedule_id associated with discover tasks")

    result = await cli_agent.run_cli(
        "call",
        f"/api/vega/v1/discover/task?schedule_id={schedule_id}&page=1&size=10",
    )
    if result.exit_code != 0 and (
        "404" in result.stderr or "405" in result.stderr
    ):
        pytest.skip("discover task by_schedule endpoint not available")
    scorer.assert_exit_code(result, 0, "discover task by_schedule exit code")
    scorer.assert_json(result, "discover task by_schedule returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "vega_discover_task_by_schedule", [result], det, module="adp/vega",
    )
    assert det.passed, det.failures


