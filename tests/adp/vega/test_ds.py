"""Datasource acceptance tests.

DS (datasource) is part of the Vega module — manages database connections
used by catalogs, resources, and dataviews.
"""

from __future__ import annotations

import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_datasource_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """ds list returns a JSON dict with an entries array."""
    result = await cli_agent.run_cli("ds", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_true(
        isinstance(result.parsed_json, dict)
        and isinstance(result.parsed_json.get("entries"), list),
        "ds list returns dict with entries array",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("ds_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_datasource_get(cli_agent: CliAgent, scorer: Scorer, eval_case, ds_id: str):
    """ds get retrieves a specific datasource by ID."""
    result = await cli_agent.run_cli("ds", "get", ds_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("ds_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_datasource_tables(cli_agent: CliAgent, scorer: Scorer, eval_case, ds_id: str):
    """ds tables returns table info for a datasource."""
    result = await cli_agent.run_cli("ds", "tables", ds_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("ds_tables", [result], det, module="adp/vega")
    assert det.passed, det.failures


@pytest.mark.destructive
@pytest.mark.known_bug("ds delete returns 500 — backend database error on dip.aishu.cn")
async def test_datasource_connect_and_delete(
    cli_agent: CliAgent, scorer: Scorer, eval_case, db_credentials: dict,
):
    """ds connect creates a datasource, then ds delete removes it."""
    name = f"eval_ds_{int(time.time())}"
    ds_id = ""
    steps = []

    try:
        # Step 1: connect
        connect = await cli_agent.run_cli(
            "ds", "connect",
            db_credentials["db_type"],
            db_credentials["host"],
            db_credentials["port"],
            db_credentials["database"],
            "--account", db_credentials["user"],
            "--password", db_credentials["password"],
            "--name", name,
        )
        steps.append(connect)
        scorer.assert_exit_code(connect, 0, "ds connect")
        scorer.assert_json(connect, "ds connect returns JSON")
        if isinstance(connect.parsed_json, dict):
            ds_id = str(
                connect.parsed_json.get("id")
                or connect.parsed_json.get("ds_id")
                or connect.parsed_json.get("datasource_id")
                or ""
            )
        scorer.assert_true(bool(ds_id), "ds connect returns ID")

        # Step 2: verify via get
        if ds_id:
            get = await cli_agent.run_cli("ds", "get", ds_id)
            steps.append(get)
            scorer.assert_exit_code(get, 0, "ds get after connect")

    finally:
        if ds_id:
            delete = await cli_agent.run_cli("ds", "delete", ds_id, "-y")
            steps.append(delete)
            scorer.assert_exit_code(delete, 0, "ds delete")

    det = scorer.result()
    await eval_case("ds_connect_and_delete", steps, det, module="adp/vega")
    assert det.passed, det.failures
