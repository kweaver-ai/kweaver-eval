"""Vega query execute acceptance tests.

Tests the cross-resource query engine (SQL-like joins).
Requires physical resources from a discovered catalog.
"""

from __future__ import annotations

import json
import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.destructive
@pytest.mark.wait_for_env("Query execute returns 500 — connector not found on dip-poc")
async def test_vega_query_execute(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    db_credentials: dict,
    vega_connector_config: str,
):
    """query execute: create catalog -> discover -> query across resources."""
    cat_name = f"eval_query_cat_{int(time.time())}"
    cat_id = ""
    steps = []

    try:
        # Step 1: create catalog + discover to get physical resources
        create_cat = await cli_agent.run_cli(
            "vega", "catalog", "create",
            "--name", cat_name,
            "--connector-type", db_credentials["db_type"],
            "--connector-config", vega_connector_config,
            "--description", "Eval query test - safe to delete",
        )
        steps.append(create_cat)
        scorer.assert_exit_code(create_cat, 0, "catalog create")
        if isinstance(create_cat.parsed_json, dict):
            cat_id = str(create_cat.parsed_json.get("id") or "")
        scorer.assert_true(bool(cat_id), "catalog create returns ID")

        discover = await cli_agent.run_cli(
            "vega", "catalog", "discover", cat_id,
        )
        steps.append(discover)
        scorer.assert_exit_code(discover, 0, "catalog discover")

        # Wait for discover to complete
        if isinstance(discover.parsed_json, dict):
            task_id = str(discover.parsed_json.get("id") or "")
            if task_id:
                await cli_agent.run_cli(
                    "vega", "discovery-task", "get", task_id,
                )

        # Step 2: list resources to get IDs for query
        res_list = await cli_agent.run_cli(
            "vega", "catalog", "resources", cat_id, "--limit", "5",
        )
        steps.append(res_list)
        scorer.assert_exit_code(res_list, 0, "catalog resources")
        res_entries = res_list.parsed_json
        if isinstance(res_entries, dict):
            res_entries = res_entries.get("entries") or []
        if not isinstance(res_entries, list) or not res_entries:
            pytest.skip("No resources after discover")

        rid = str(res_entries[0].get("id") or "")
        scorer.assert_true(bool(rid), "found resource for query")

        # Step 3: single-table query execute
        query_payload = json.dumps({
            "tables": [{"resource_id": rid, "alias": "t1"}],
            "output_fields": ["t1.*"],
            "limit": 5,
        })
        query_exec = await cli_agent.run_cli(
            "vega", "query", "execute", "-d", query_payload,
        )
        steps.append(query_exec)
        scorer.assert_exit_code(query_exec, 0, "query execute")
        scorer.assert_json(query_exec, "query execute returns JSON")

        # Step 4: multi-table join (if 2+ resources)
        if len(res_entries) >= 2:
            rid2 = str(res_entries[1].get("id") or "")
            if rid2:
                join_payload = json.dumps({
                    "tables": [
                        {"resource_id": rid, "alias": "t1"},
                        {"resource_id": rid2, "alias": "t2"},
                    ],
                    "joins": [{
                        "type": "inner",
                        "left_table_alias": "t1",
                        "right_table_alias": "t2",
                        "on": [{
                            "left_field": "product_code",
                            "right_field": "product_code",
                        }],
                    }],
                    "output_fields": ["t1.*", "t2.*"],
                    "limit": 3,
                })
                join_exec = await cli_agent.run_cli(
                    "vega", "query", "execute", "-d", join_payload,
                )
                steps.append(join_exec)
                # Join may fail if tables don't share fields — not a hard assert
                if join_exec.exit_code == 0:
                    scorer.assert_json(
                        join_exec, "join query returns JSON",
                    )

    finally:
        if cat_id:
            await cli_agent.run_cli(
                "vega", "catalog", "delete", cat_id, "-y",
            )

    det = scorer.result()
    await eval_case(
        "vega_query_execute", steps, det, module="adp/vega",
    )
    assert det.passed, det.failures
