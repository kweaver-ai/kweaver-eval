"""Dataflow lifecycle (destructive) acceptance tests.

Covers: create, update, delete — operations that create/remove server resources.
Requires: EVAL_RUN_DESTRUCTIVE=1 + database credentials.
Pattern: follows bkn/test_lifecycle.py conventions (try/finally cleanup).
"""

from __future__ import annotations

import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer
from tests.adp.bkn.conftest import _short_suffix


@pytest.mark.destructive
async def test_dataflow_create_and_delete(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    db_credentials: dict,
):
    """dataflow create (empty pipeline) then delete."""
    suffix = f"{int(time.time())}_{_short_suffix()}"
    df_name = f"eval_df_{suffix}"
    df_id = ""
    steps = []

    try:
        create = await cli_agent.run_cli(
            "dataflow", "create",
            "--name", df_name,
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "dataflow create")
        scorer.assert_json(create, "dataflow create returns JSON")
        if isinstance(create.parsed_json, dict):
            df_id = str(
                create.parsed_json.get("id")
                or create.parsed_json.get("dataflow_id")
                or "",
            )
        scorer.assert_true(bool(df_id), "dataflow create returns dataflow ID")

        if df_id:
            get_result = await cli_agent.run_cli(
                "dataflow", "get", df_id,
            )
            steps.append(get_result)
            scorer.assert_exit_code(get_result, 0, "dataflow get created dataflow")
            scorer.assert_json(get_result, "dataflow get returns JSON")

    finally:
        if df_id:
            await cli_agent.run_cli("dataflow", "delete", df_id, "-y")

    det = scorer.result()
    await eval_case("dataflow_create_delete", steps, det, module="adp/dataflow")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_dataflow_update(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    db_credentials: dict,
):
    """dataflow create then update name/description."""
    suffix = f"{int(time.time())}_{_short_suffix()}"
    df_name = f"eval_df_upd_{suffix}"
    df_id = ""
    steps = []

    try:
        create = await cli_agent.run_cli(
            "dataflow", "create",
            "--name", df_name,
            "--description", "original description",
        )
        if create.exit_code != 0:
            pytest.skip(f"dataflow create failed: {create.stderr.strip()}")
        if isinstance(create.parsed_json, dict):
            df_id = str(
                create.parsed_json.get("id")
                or create.parsed_json.get("dataflow_id")
                or "",
            )
        if not df_id:
            pytest.skip("Cannot get dataflow ID from create")

        new_name = f"eval_df_renamed_{int(time.time())}_{_short_suffix()}"
        update = await cli_agent.run_cli(
            "dataflow", "update", df_id,
            "--name", new_name,
            "--description", "updated description",
        )
        steps.append(update)
        scorer.assert_exit_code(update, 0, "dataflow update")

        verify = await cli_agent.run_cli(
            "dataflow", "get", df_id,
        )
        steps.append(verify)
        scorer.assert_exit_code(verify, 0, "dataflow get after update")
        scorer.assert_json_field(
            verify, "name",
            expected=new_name,
            label="dataflow name updated",
        )

    finally:
        if df_id:
            await cli_agent.run_cli("dataflow", "delete", df_id, "-y")

    det = scorer.result()
    await eval_case("dataflow_update", steps, det, module="adp/dataflow")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_dataflow_full_lifecycle(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    db_credentials: dict,
):
    """Full lifecycle: ds connect -> dataflow create with source -> validate -> run -> status -> logs -> cleanup.

    This is the most comprehensive E2E test for dataflow.
    """
    creds = db_credentials
    suffix = f"{int(time.time())}_{_short_suffix()}"
    ds_name = f"eval_ds_df_{suffix}"
    df_name = f"eval_df_full_{suffix}"
    ds_id = ""
    df_id = ""
    run_id = ""
    steps = []

    try:
        connect = await cli_agent.run_cli(
            "ds", "connect",
            creds["db_type"], creds["host"], creds["port"], creds["database"],
            "--account", creds["user"],
            "--password", creds["password"],
            "--name", ds_name,
        )
        steps.append(connect)
        scorer.assert_exit_code(connect, 0, "ds connect (for dataflow source)")
        scorer.assert_json(connect, "ds connect returns JSON")
        if isinstance(connect.parsed_json, list) and connect.parsed_json:
            ds_id = str(
                connect.parsed_json[0].get("datasource_id")
                or connect.parsed_json[0].get("id")
                or "",
            )
        elif isinstance(connect.parsed_json, dict):
            ds_id = str(
                connect.parsed_json.get("datasource_id")
                or connect.parsed_json.get("id")
                or "",
            )
        scorer.assert_true(bool(ds_id), "ds connect returns datasource ID")

        create = await cli_agent.run_cli(
            "dataflow", "create",
            "--name", df_name,
            "--source-ds", ds_id,
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "dataflow create with source")
        scorer.assert_json(create, "dataflow create returns JSON")
        if isinstance(create.parsed_json, dict):
            df_id = str(
                create.parsed_json.get("id")
                or create.parsed_json.get("dataflow_id")
                or "",
            )
        scorer.assert_true(bool(df_id), "dataflow create returns dataflow ID")

        validate = await cli_agent.run_cli(
            "dataflow", "validate", df_id,
        )
        steps.append(validate)
        scorer.assert_exit_code(validate, 0, "dataflow validate")

        run = await cli_agent.run_cli(
            "dataflow", "run", df_id,
            timeout=120.0,
        )
        steps.append(run)
        scorer.assert_exit_code(run, 0, "dataflow run")
        if isinstance(run.parsed_json, dict):
            run_id = str(
                run.parsed_json.get("run_id")
                or run.parsed_json.get("execution_id")
                or run.parsed_json.get("id")
                or "",
            )

        if run_id:
            status = await cli_agent.run_cli(
                "dataflow", "status", df_id,
                "--run", run_id,
            )
            steps.append(status)
            scorer.assert_exit_code(status, 0, "dataflow status after run")

            logs = await cli_agent.run_cli(
                "dataflow", "logs", df_id,
                "--run", run_id,
                "--limit", "20",
            )
            steps.append(logs)
            scorer.assert_exit_code(logs, 0, "dataflow logs after run")

    finally:
        if df_id:
            await cli_agent.run_cli("dataflow", "delete", df_id, "-y")
        if ds_id:
            await cli_agent.run_cli("ds", "delete", ds_id, "-y")

    det = scorer.result()
    await eval_case("dataflow_full_lifecycle", steps, det, module="adp/dataflow",
                    eval_hints={
                        "focus": "e2e_correctness",
                        "description": "Full data pipeline: source -> transform -> sink. Verify each stage completes.",
                        "latency_budget_ms": 120000,
                    })
    assert det.passed, det.failures
