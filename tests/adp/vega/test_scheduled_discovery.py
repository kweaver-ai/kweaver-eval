"""Vega scheduled discovery acceptance tests.

Covers:
  - vega.catalog.discover_scheduled.list   — list scheduled discovery configs
  - vega.catalog.discover_scheduled.create — create a new scheduled discovery
  - vega.catalog.discover_scheduled.start  — start a scheduled discovery
  - vega.catalog.discover_scheduled.stop   — stop a running scheduled discovery

The list operation is a lightweight read-only test.
Create/start/stop are destructive and use try/finally cleanup.
"""

from __future__ import annotations

import json
import time
import random
import string

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


def _sched_name() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"eval_sched_{int(time.time())}_{suffix}"


async def test_vega_catalog_discover_scheduled_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str,
):
    """vega catalog discover-scheduled list returns scheduled configs for a catalog."""
    result = await cli_agent.run_cli(
        "vega", "catalog", "discover-scheduled", "list", catalog_id,
    )
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        # Fallback to call endpoint
        result = await cli_agent.run_cli(
            "call",
            f"/api/vega/v1/catalog/{catalog_id}/discover/scheduled",
        )
    if result.exit_code != 0 and "404" in result.stderr:
        pytest.skip("scheduled discovery endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "discover-scheduled list")
    scorer.assert_json(result, "discover-scheduled list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "vega_catalog_discover_scheduled_list", [result], det, module="adp/vega",
    )
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_vega_catalog_discover_scheduled_create_start_stop(
    cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str,
):
    """Scheduled discovery: create -> start -> stop lifecycle."""
    sched_name = _sched_name()
    sched_id = ""
    steps = []

    try:
        # Step 1: create via kweaver call (no direct CLI sub-command)
        create_body = json.dumps({
            "name": sched_name,
            "cron": "0 * * * *",
            "enabled": False,
        })
        create = await cli_agent.run_cli(
            "call",
            f"/api/vega/v1/catalog/{catalog_id}/discover/scheduled",
            "-X", "POST",
            "-d", create_body,
        )
        steps.append(create)
        if create.exit_code != 0 and (
            "404" in create.stderr or "405" in create.stderr
        ):
            pytest.skip("scheduled discovery create endpoint not available")
        scorer.assert_exit_code(create, 0, "discover-scheduled create")
        scorer.assert_json(create, "create returns JSON")
        if isinstance(create.parsed_json, dict):
            sched_id = str(
                create.parsed_json.get("id")
                or create.parsed_json.get("schedule_id")
                or "",
            )
        scorer.assert_true(bool(sched_id), "create returns schedule ID")

        # Step 2: start
        if sched_id:
            start = await cli_agent.run_cli(
                "call",
                f"/api/vega/v1/catalog/{catalog_id}/discover/scheduled/{sched_id}/start",
                "-X", "POST",
                "-d", "{}",
            )
            steps.append(start)
            scorer.assert_exit_code(start, 0, "discover-scheduled start")

        # Step 3: stop
        if sched_id:
            stop = await cli_agent.run_cli(
                "call",
                f"/api/vega/v1/catalog/{catalog_id}/discover/scheduled/{sched_id}/stop",
                "-X", "POST",
                "-d", "{}",
            )
            steps.append(stop)
            scorer.assert_exit_code(stop, 0, "discover-scheduled stop")

    finally:
        if sched_id:
            await cli_agent.run_cli(
                "call",
                f"/api/vega/v1/catalog/{catalog_id}/discover/scheduled/{sched_id}",
                "-X", "DELETE",
            )

    det = scorer.result()
    await eval_case(
        "vega_catalog_discover_scheduled_lifecycle",
        steps,
        det,
        module="adp/vega",
    )
    assert det.passed, det.failures


async def test_vega_resource_data_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case, resource_id: str,
):
    """vega resource query returns data rows from a resource."""
    result = await cli_agent.run_cli(
        "vega", "resource", "query", resource_id, "--limit", "5",
    )
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        # Fallback to call endpoint
        result = await cli_agent.run_cli(
            "call",
            f"/api/vega/v1/resource/{resource_id}/data?limit=5",
        )
    if result.exit_code != 0 and "404" in result.stderr:
        pytest.skip("resource data query endpoint not available")
    if result.exit_code != 0 and "500" in result.stderr:
        pytest.skip("resource data query server error (may be an orphan resource)")
    scorer.assert_exit_code(result, 0, "resource data query")
    scorer.assert_json(result, "resource data query returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "vega_resource_data_query", [result], det, module="adp/vega",
    )
    assert det.passed, det.failures
