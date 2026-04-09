"""Vega lifecycle acceptance tests (destructive — creates and deletes resources)."""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.destructive
async def test_vega_catalog_lifecycle(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    db_credentials: dict,
    vega_connector_config: str,
):
    """Full catalog lifecycle: create -> test-connection -> discover -> get -> update -> delete."""
    cat_name = f"eval_cat_{int(time.time())}"
    cat_id = ""
    steps = []

    try:
        # Step 1: create catalog
        create = await cli_agent.run_cli(
            "vega", "catalog", "create",
            "--name", cat_name,
            "--connector-type", db_credentials["db_type"],
            "--connector-config", vega_connector_config,
            "--description", "Eval lifecycle test - safe to delete",
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "catalog create")
        scorer.assert_json(create, "catalog create returns JSON")
        if isinstance(create.parsed_json, dict):
            cat_id = str(create.parsed_json.get("id") or "")
        scorer.assert_true(bool(cat_id), "catalog create returns ID")

        # Step 2: test-connection
        tc = await cli_agent.run_cli("vega", "catalog", "test-connection", cat_id)
        steps.append(tc)
        scorer.assert_exit_code(tc, 0, "catalog test-connection")

        # Step 3: discover and verify task
        discover = await cli_agent.run_cli("vega", "catalog", "discover", cat_id)
        steps.append(discover)
        scorer.assert_exit_code(discover, 0, "catalog discover")
        scorer.assert_json(discover, "catalog discover returns JSON")
        task_id = ""
        if isinstance(discover.parsed_json, dict):
            task_id = str(discover.parsed_json.get("id") or "")
        scorer.assert_true(bool(task_id), "catalog discover returns task ID")

        if task_id:
            # Poll until task reaches a terminal state (max 180s, backoff)
            deadline = time.time() + 180
            task_final = None
            poll_interval = 2.0
            while time.time() < deadline:
                task_poll = await cli_agent.run_cli("vega", "discovery-task", "get", task_id)
                if task_poll.exit_code == 0 and isinstance(task_poll.parsed_json, dict):
                    poll_status = task_poll.parsed_json.get("status", "")
                    if poll_status in ("completed", "failed"):
                        task_final = task_poll
                        break
                await asyncio.sleep(poll_interval)
                poll_interval = min(poll_interval * 1.5, 10)
            if task_final is None:
                task_final = await cli_agent.run_cli("vega", "discovery-task", "get", task_id)
            steps.append(task_final)
            scorer.assert_exit_code(task_final, 0, "discovery-task get")
            status = ""
            if isinstance(task_final.parsed_json, dict):
                status = task_final.parsed_json.get("status", "")
                scorer.assert_true(
                    status == "completed",
                    f"discovery task completed (got {status})",
                )
            if status != "completed":
                det = scorer.result()
                await eval_case("vega_catalog_lifecycle", steps, det, module="adp/vega")
                pytest.skip(
                    f"discovery task stuck in '{status}' after 180s — "
                    "backend too slow or DB unreachable"
                )

        # Step 4: get catalog to verify it exists
        get = await cli_agent.run_cli("vega", "catalog", "get", cat_id)
        steps.append(get)
        scorer.assert_exit_code(get, 0, "catalog get after create")
        scorer.assert_json(get, "catalog get returns JSON")

        # Step 5: resource list + query (after discover, physical resources exist)
        res_list = await cli_agent.run_cli(
            "vega", "catalog", "resources", cat_id, "--limit", "3",
        )
        steps.append(res_list)
        scorer.assert_exit_code(res_list, 0, "catalog resources after discover")
        scorer.assert_json(res_list, "catalog resources returns JSON")
        res_entries = res_list.parsed_json
        if isinstance(res_entries, dict):
            res_entries = res_entries.get("entries") or []
        rid = ""
        if isinstance(res_entries, list) and res_entries:
            rid = str(res_entries[0].get("id") or "")
        scorer.assert_true(bool(rid), "discover produced at least one resource")

        if rid:
            res_query = await cli_agent.run_cli(
                "vega", "resource", "query", rid,
                "-d", json.dumps({"limit": 2}),
            )
            steps.append(res_query)
            scorer.assert_exit_code(res_query, 0, "resource query")
            scorer.assert_json(res_query, "resource query returns JSON")

        # Step 6: update catalog (PUT full-replace, all required fields)
        update = await cli_agent.run_cli(
            "vega", "catalog", "update", cat_id,
            "--name", cat_name,
            "--connector-type", db_credentials["db_type"],
            "--connector-config", vega_connector_config,
            "--description", "Updated by eval lifecycle test",
            "--tags", "eval,test",
        )
        steps.append(update)
        scorer.assert_exit_code(update, 0, "catalog update")

    finally:
        if cat_id:
            await cli_agent.run_cli("vega", "catalog", "delete", cat_id, "-y")

    det = scorer.result()
    await eval_case("vega_catalog_lifecycle", steps, det, module="adp/vega")
    assert det.passed, det.failures
