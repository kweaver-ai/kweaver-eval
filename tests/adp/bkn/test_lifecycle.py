"""BKN lifecycle (destructive) acceptance tests."""

from __future__ import annotations

import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.destructive
async def test_bkn_full_lifecycle(
    cli_agent: CliAgent, scorer: Scorer, eval_case, db_credentials: dict
):
    """Full lifecycle: ds connect -> bkn create -> export -> search -> cleanup."""
    creds = db_credentials
    ds_name = f"e2e_eval_{int(time.time())}"
    kn_name = f"e2e_kn_{int(time.time())}"
    ds_id = ""
    kn_id = ""
    steps = []

    try:
        # Step 1: ds connect
        connect = await cli_agent.run_cli(
            "ds", "connect", creds["db_type"], creds["host"], creds["port"], creds["database"],
            "--account", creds["user"], "--password", creds["password"], "--name", ds_name,
        )
        steps.append(connect)
        scorer.assert_exit_code(connect, 0, "ds connect")
        scorer.assert_json(connect, "ds connect returns JSON")
        if isinstance(connect.parsed_json, list) and connect.parsed_json:
            first = connect.parsed_json[0]
            ds_id = str(first.get("datasource_id") or first.get("id") or "")
        elif isinstance(connect.parsed_json, dict):
            d = connect.parsed_json
            ds_id = str(d.get("datasource_id") or d.get("id") or "")
        scorer.assert_true(bool(ds_id), "ds connect returns datasource ID")

        # Step 2: bkn create-from-ds
        create = await cli_agent.run_cli(
            "bkn", "create-from-ds", ds_id, "--name", kn_name, "--no-build",
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "bkn create-from-ds")
        scorer.assert_json(create, "bkn create-from-ds returns JSON")
        if isinstance(create.parsed_json, dict):
            kn_id = str(create.parsed_json.get("kn_id") or create.parsed_json.get("id") or "")
        scorer.assert_true(bool(kn_id), "bkn create-from-ds returns KN ID")

        # Step 3: bkn export
        export = await cli_agent.run_cli("bkn", "export", kn_id)
        steps.append(export)
        scorer.assert_exit_code(export, 0, "bkn export")
        scorer.assert_json(export, "bkn export returns JSON")

        # Step 4: bkn search
        search = await cli_agent.run_cli("bkn", "search", kn_id, "test")
        steps.append(search)
        scorer.assert_exit_code(search, 0, "bkn search")

    finally:
        if kn_id:
            await cli_agent.run_cli("bkn", "delete", kn_id, "-y")
        if ds_id:
            await cli_agent.run_cli("ds", "delete", ds_id, "-y")

    det = scorer.result()
    await eval_case("bkn_full_lifecycle", steps, det, module="adp/bkn")
    assert det.passed, det.failures
