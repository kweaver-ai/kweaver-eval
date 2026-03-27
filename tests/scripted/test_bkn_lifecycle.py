"""BKN (Business Knowledge Network) lifecycle acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.recorder import Recorder
from lib.scorer import Scorer
from lib.types import CaseResult


# ---------- Read-only tests ----------


async def test_bkn_list(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """bkn list returns a JSON array of knowledge networks."""
    result = await cli_agent.run_cli("bkn", "list", "--json")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="bkn list returns array")

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_bkn_list",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


async def _find_kn_id(cli_agent: CliAgent) -> str | None:
    """Find an available KN ID from bkn list."""
    result = await cli_agent.run_cli("bkn", "list", "--json")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return None
    for kn in result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if kn_id:
            return kn_id
    return None


async def test_bkn_export(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """bkn export returns KN data as JSON."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KN available")

    result = await cli_agent.run_cli("bkn", "export", kn_id, "--json")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_bkn_export",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


async def test_bkn_search(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """bkn search returns results for a query."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KN available")

    result = await cli_agent.run_cli("bkn", "search", kn_id, "test", "--json")
    scorer.assert_exit_code(result, 0)

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_bkn_search",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


async def test_bkn_object_type_list(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """bkn object-type list returns object types for a KN."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KN available")

    result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id, "--json")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="object-type list returns array")

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_bkn_object_type_list",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


async def test_bkn_relation_type_list(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """bkn relation-type list returns relation types for a KN."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KN available")

    result = await cli_agent.run_cli("bkn", "relation-type", "list", kn_id, "--json")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_bkn_relation_type_list",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


# ---------- Destructive tests ----------


@pytest.mark.destructive
async def test_bkn_full_lifecycle(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """Full lifecycle: ds connect -> bkn create-from-ds -> bkn export -> bkn search -> cleanup.

    Requires KWEAVER_TEST_DB_* env vars and EVAL_RUN_DESTRUCTIVE=1.
    """
    import os
    import time

    db_host = os.environ.get("KWEAVER_TEST_DB_HOST", "")
    db_port = os.environ.get("KWEAVER_TEST_DB_PORT", "3306")
    db_user = os.environ.get("KWEAVER_TEST_DB_USER", "")
    db_pass = os.environ.get("KWEAVER_TEST_DB_PASS", "")
    db_name = os.environ.get("KWEAVER_TEST_DB_NAME", "")
    db_type = os.environ.get("KWEAVER_TEST_DB_TYPE", "mysql")

    if not all([db_host, db_user, db_pass, db_name]):
        pytest.skip("E2E database not configured")

    steps = []
    ds_name = f"e2e_eval_{int(time.time())}"
    kn_name = f"e2e_kn_{int(time.time())}"
    ds_id = ""
    kn_id = ""

    try:
        # Step 1: ds connect
        connect = await cli_agent.run_cli(
            "ds", "connect", db_type, db_host, db_port, db_name,
            "--account", db_user, "--password", db_pass, "--name", ds_name, "--json",
        )
        steps.append(connect)
        scorer.assert_exit_code(connect, 0, "ds connect")
        scorer.assert_json(connect, "ds connect returns JSON")
        if isinstance(connect.parsed_json, list) and connect.parsed_json:
            ds_id = str(connect.parsed_json[0].get("datasource_id") or connect.parsed_json[0].get("id") or "")
        elif isinstance(connect.parsed_json, dict):
            ds_id = str(connect.parsed_json.get("datasource_id") or connect.parsed_json.get("id") or "")
        scorer.assert_true(bool(ds_id), "ds connect returns datasource ID")

        # Step 2: bkn create-from-ds
        create = await cli_agent.run_cli(
            "bkn", "create-from-ds", ds_id, "--name", kn_name, "--no-build", "--json",
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "bkn create-from-ds")
        scorer.assert_json(create, "bkn create-from-ds returns JSON")
        if isinstance(create.parsed_json, dict):
            kn_id = str(create.parsed_json.get("kn_id") or create.parsed_json.get("id") or "")
        scorer.assert_true(bool(kn_id), "bkn create-from-ds returns KN ID")

        # Step 3: bkn export
        export = await cli_agent.run_cli("bkn", "export", kn_id, "--json")
        steps.append(export)
        scorer.assert_exit_code(export, 0, "bkn export")
        scorer.assert_json(export, "bkn export returns JSON")

        # Step 4: bkn search
        search = await cli_agent.run_cli("bkn", "search", kn_id, "test", "--json")
        steps.append(search)
        scorer.assert_exit_code(search, 0, "bkn search")

    finally:
        if kn_id:
            await cli_agent.run_cli("bkn", "delete", kn_id, "-y")
        if ds_id:
            await cli_agent.run_cli("ds", "delete", ds_id, "-y")

    det = scorer.result()
    recorder.record_case(CaseResult(
        name="test_bkn_full_lifecycle",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=steps,
    ))
    assert det.passed, det.failures
