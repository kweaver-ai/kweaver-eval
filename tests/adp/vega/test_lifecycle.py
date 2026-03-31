"""Vega lifecycle acceptance tests (destructive — creates and deletes resources)."""

from __future__ import annotations

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
            task_get = await cli_agent.run_cli("vega", "discovery-task", "get", task_id)
            steps.append(task_get)
            scorer.assert_exit_code(task_get, 0, "discovery-task get")
            if isinstance(task_get.parsed_json, dict):
                status = task_get.parsed_json.get("status", "")
                scorer.assert_true(
                    status in ("completed", "running"),
                    f"discovery task status is valid (got {status})",
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
