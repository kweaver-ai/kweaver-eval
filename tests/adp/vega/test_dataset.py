"""Vega dataset lifecycle acceptance tests (destructive).

Tests dataset document CRUD and build workflow:
  create resource(dataset) -> create docs -> query -> update docs -> delete docs -> build -> cleanup
"""

from __future__ import annotations

import json
import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.destructive
async def test_vega_dataset_lifecycle(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    db_credentials: dict,
    vega_connector_config: str,
):
    """Dataset lifecycle: create catalog -> create dataset resource -> docs CRUD -> build."""
    cat_name = f"eval_ds_cat_{int(time.time())}"
    cat_id = ""
    res_id = ""
    doc_ids: list[str] = []
    steps = []

    try:
        # Step 1: create catalog for dataset
        create_cat = await cli_agent.run_cli(
            "vega", "catalog", "create",
            "--name", cat_name,
            "--connector-type", db_credentials["db_type"],
            "--connector-config", vega_connector_config,
            "--description", "Eval dataset lifecycle - safe to delete",
        )
        steps.append(create_cat)
        scorer.assert_exit_code(create_cat, 0, "catalog create")
        if isinstance(create_cat.parsed_json, dict):
            cat_id = str(create_cat.parsed_json.get("id") or "")
        scorer.assert_true(bool(cat_id), "catalog create returns ID")

        # Step 2: create dataset resource
        create_res = await cli_agent.run_cli(
            "vega", "resource", "create",
            "--catalog-id", cat_id,
            "--name", f"eval_dataset_{int(time.time())}",
            "--category", "dataset",
        )
        steps.append(create_res)
        scorer.assert_exit_code(create_res, 0, "resource create (dataset)")
        scorer.assert_json(create_res, "resource create returns JSON")
        if isinstance(create_res.parsed_json, dict):
            res_id = str(create_res.parsed_json.get("id") or "")
        scorer.assert_true(bool(res_id), "resource create returns ID")

        # Step 3: create docs
        docs_payload = json.dumps([
            {"title": "eval doc 1", "content": "test content alpha"},
            {"title": "eval doc 2", "content": "test content beta"},
        ])
        create_docs = await cli_agent.run_cli(
            "vega", "dataset", "create-docs", res_id, "-d", docs_payload,
        )
        steps.append(create_docs)
        scorer.assert_exit_code(create_docs, 0, "dataset create-docs")
        scorer.assert_json(create_docs, "create-docs returns JSON")
        if isinstance(create_docs.parsed_json, dict):
            doc_ids = create_docs.parsed_json.get("ids") or []
        scorer.assert_true(len(doc_ids) > 0, "create-docs returns doc IDs")

        # Step 4: query docs via resource data
        query_body = json.dumps({"limit": 10})
        query_docs = await cli_agent.run_cli(
            "vega", "resource", "query", res_id, "-d", query_body,
        )
        steps.append(query_docs)
        scorer.assert_exit_code(query_docs, 0, "resource query (dataset)")
        scorer.assert_json(query_docs, "resource query returns JSON")

        # Step 5: update docs
        if doc_ids:
            update_payload = json.dumps([
                {"id": doc_ids[0], "title": "eval doc 1 updated"},
            ])
            update_docs = await cli_agent.run_cli(
                "vega", "dataset", "update-docs", res_id,
                "-d", update_payload,
            )
            steps.append(update_docs)
            scorer.assert_exit_code(update_docs, 0, "dataset update-docs")

        # Step 6: delete one doc by ID
        if len(doc_ids) > 1:
            delete_docs = await cli_agent.run_cli(
                "vega", "dataset", "delete-docs", res_id, doc_ids[-1],
            )
            steps.append(delete_docs)
            scorer.assert_exit_code(delete_docs, 0, "dataset delete-docs")

        # Step 7: build dataset
        build = await cli_agent.run_cli(
            "vega", "dataset", "build", res_id, "--mode", "full",
        )
        steps.append(build)
        scorer.assert_exit_code(build, 0, "dataset build")
        scorer.assert_json(build, "dataset build returns JSON")
        task_id = ""
        if isinstance(build.parsed_json, dict):
            task_id = str(build.parsed_json.get("task_id") or "")

        # Step 8: check build status
        if task_id:
            build_status = await cli_agent.run_cli(
                "vega", "dataset", "build-status", res_id, task_id,
            )
            steps.append(build_status)
            scorer.assert_exit_code(build_status, 0, "dataset build-status")
            scorer.assert_json(
                build_status, "build-status returns JSON",
            )

    finally:
        if res_id:
            await cli_agent.run_cli(
                "vega", "resource", "delete", res_id, "-y",
            )
        if cat_id:
            await cli_agent.run_cli(
                "vega", "catalog", "delete", cat_id, "-y",
            )

    det = scorer.result()
    await eval_case(
        "vega_dataset_lifecycle", steps, det, module="adp/vega",
    )
    assert det.passed, det.failures
