"""Datasource acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.recorder import Recorder
from lib.scorer import Scorer
from lib.types import CaseResult


async def test_datasource_list(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """ds list returns a JSON dict with an entries array of datasources."""
    result = await cli_agent.run_cli("ds", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_true(
        isinstance(result.parsed_json, dict) and isinstance(result.parsed_json.get("entries"), list),
        "ds list returns dict with entries array",
    )

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_datasource_list",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


async def test_datasource_get(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """ds get retrieves a specific datasource by ID."""
    list_result = await cli_agent.run_cli("ds", "list")
    entries = []
    if list_result.exit_code == 0 and isinstance(list_result.parsed_json, dict):
        entries = list_result.parsed_json.get("entries", [])
    if not isinstance(entries, list) or len(entries) == 0:
        pytest.skip("No datasources available")

    ds = entries[0]
    ds_id = str(ds.get("id") or ds.get("ds_id") or ds.get("datasource_id", ""))
    if not ds_id:
        pytest.skip("Cannot determine datasource ID")

    result = await cli_agent.run_cli("ds", "get", ds_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_datasource_get",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[list_result, result],
    ))
    assert det.passed, det.failures


async def test_datasource_tables(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """ds tables returns table info for a datasource."""
    list_result = await cli_agent.run_cli("ds", "list")
    entries = []
    if list_result.exit_code == 0 and isinstance(list_result.parsed_json, dict):
        entries = list_result.parsed_json.get("entries", [])
    if not isinstance(entries, list) or len(entries) == 0:
        pytest.skip("No datasources available")

    ds = entries[0]
    ds_id = str(ds.get("id") or ds.get("ds_id") or ds.get("datasource_id", ""))
    if not ds_id:
        pytest.skip("Cannot determine datasource ID")

    result = await cli_agent.run_cli("ds", "tables", ds_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_datasource_tables",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[list_result, result],
    ))
    assert det.passed, det.failures
