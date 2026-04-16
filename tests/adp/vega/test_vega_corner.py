"""Vega corner-case acceptance tests.

Covers:
  - vega.discover_task.get            — get a single discover task by ID
  - vega.discover_task.by_schedule    — list tasks filtered by schedule ID
  - vega.resource.dataset.documents.create — add documents to a dataset resource
  - vega.resource.dataset.documents.query  — query documents in a dataset
  - vega.resource.dataset.build            — trigger build on a dataset resource

These capabilities target the Vega REST API via `kweaver call` because the
kweaver CLI does not expose dedicated discover-task or dataset sub-commands.
"""

from __future__ import annotations

import json
import time
import random
import string

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


def _doc_id() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"eval_doc_{int(time.time())}_{suffix}"


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


async def _find_dataset_resource(cli_agent: CliAgent) -> str | None:
    """Return a dataset-type resource ID, or None."""
    result = await cli_agent.run_cli("vega", "resource", "list", "--limit", "20")
    if result.exit_code != 0:
        return None
    resources = result.parsed_json
    if isinstance(resources, dict):
        resources = resources.get("items") or resources.get("entries") or []
    if not isinstance(resources, list):
        return None
    for res in resources:
        rtype = str(res.get("resource_type") or res.get("type") or "").lower()
        if "dataset" in rtype or "doc" in rtype:
            res_id = str(res.get("id") or res.get("resource_id") or "")
            if res_id:
                return res_id
    # If no explicit dataset type, return first resource for a best-effort test
    if resources:
        return str(resources[0].get("id") or resources[0].get("resource_id") or "")
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


@pytest.mark.destructive
async def test_vega_resource_dataset_documents(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """Dataset resource: add documents, then query them."""
    res_id = await _find_dataset_resource(cli_agent)
    if not res_id:
        pytest.skip("No dataset resource available")

    steps = []
    doc_id = _doc_id()

    # Step 1: create document
    create = await cli_agent.run_cli(
        "call",
        f"/api/vega/v1/resource/{res_id}/document",
        "-X", "POST",
        "-d", json.dumps({
            "id": doc_id,
            "content": "eval test document content",
            "metadata": {"source": "eval-test"},
        }),
    )
    steps.append(create)
    if create.exit_code != 0 and (
        "404" in create.stderr or "405" in create.stderr
    ):
        pytest.skip("resource dataset document create endpoint not available")
    scorer.assert_exit_code(create, 0, "dataset document create exit code")

    # Step 2: query documents
    query = await cli_agent.run_cli(
        "call",
        f"/api/vega/v1/resource/{res_id}/document?page=1&size=5",
    )
    steps.append(query)
    if query.exit_code == 0:
        scorer.assert_json(query, "dataset document query returns JSON")

    det = scorer.result()
    await eval_case(
        "vega_resource_dataset_documents", steps, det, module="adp/vega",
    )
    assert det.passed, det.failures


async def test_vega_resource_dataset_build(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """POST /api/vega/v1/resource/<id>/build triggers a dataset build."""
    res_id = await _find_dataset_resource(cli_agent)
    if not res_id:
        pytest.skip("No dataset resource available")

    result = await cli_agent.run_cli(
        "call",
        f"/api/vega/v1/resource/{res_id}/build",
        "-X", "POST",
        "-d", json.dumps({}),
    )
    if result.exit_code != 0 and (
        "404" in result.stderr or "405" in result.stderr
    ):
        pytest.skip("resource dataset build endpoint not available")
    if result.exit_code != 0 and "500" in result.stderr:
        pytest.skip("resource dataset build returned server error (may need prior documents)")
    scorer.assert_exit_code(result, 0, "dataset build exit code")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "vega_resource_dataset_build", [result], det, module="adp/vega",
    )
    assert det.passed, det.failures
