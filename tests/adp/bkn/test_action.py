"""BKN action-type acceptance tests.

Tests action-type list/query/execute and action-log/execution tracking.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def _find_kn_with_actions(cli_agent: CliAgent) -> tuple[str, str] | None:
    """Find a KN with action types. Returns (kn_id, at_id) or None."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "20")
    if result.exit_code != 0:
        return None
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or []
    if not isinstance(kns, list):
        return None
    for kn in kns:
        kn_id = str(kn.get("id") or kn.get("kn_id") or "")
        if not kn_id:
            continue
        at_result = await cli_agent.run_cli(
            "bkn", "action-type", "list", kn_id,
        )
        if at_result.exit_code != 0:
            continue
        entries = at_result.parsed_json
        if isinstance(entries, dict):
            entries = entries.get("entries") or entries.get("items") or []
        if isinstance(entries, list) and entries:
            at_id = str(entries[0].get("id") or "")
            if at_id:
                return kn_id, at_id
    return None


async def test_bkn_action_type_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn action-type list returns action types for a KN."""
    found = await _find_kn_with_actions(cli_agent)
    if not found:
        pytest.skip("No KN with action types available")
    kn_id, _at_id = found

    result = await cli_agent.run_cli("bkn", "action-type", "list", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_action_type_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_action_type_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn action-type query returns action details."""
    found = await _find_kn_with_actions(cli_agent)
    if not found:
        pytest.skip("No KN with action types available")
    kn_id, at_id = found

    result = await cli_agent.run_cli(
        "bkn", "action-type", "query", kn_id, at_id, "{}",
    )
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_action_type_query", [result], det, module="adp/bkn")
    assert det.passed, det.failures


@pytest.mark.destructive
@pytest.mark.tbd("execute needs _instance_identities param")
@pytest.mark.known_bug("action-log list 500: index_not_found not handled in QueryExecutions")
async def test_bkn_action_execute_and_log(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn action-type execute triggers an action; then check logs."""
    found = await _find_kn_with_actions(cli_agent)
    if not found:
        pytest.skip("No KN with action types available")
    kn_id, at_id = found
    steps = []

    # Step 1: execute action (may fail if action needs specific params)
    execute = await cli_agent.run_cli(
        "bkn", "action-type", "execute", kn_id, at_id, "{}",
        timeout=120.0,
    )
    steps.append(execute)
    scorer.assert_exit_code(execute, 0, "action execute")
    scorer.assert_json(execute, "action execute returns JSON")
    execute_ok = execute.exit_code == 0

    # Step 2: get execution ID if execute succeeded
    exec_id = ""
    if execute_ok and isinstance(execute.parsed_json, dict):
        exec_id = str(
            execute.parsed_json.get("execution_id")
            or execute.parsed_json.get("id")
            or "",
        )

    # Step 3: action-execution get (only if we have an ID)
    if exec_id:
        exec_get = await cli_agent.run_cli(
            "bkn", "action-execution", "get", kn_id, exec_id,
        )
        steps.append(exec_get)
        scorer.assert_exit_code(exec_get, 0, "action-execution get")
        scorer.assert_json(exec_get, "action-execution get returns JSON")

    # Step 4: action-log list
    log_list = await cli_agent.run_cli(
        "bkn", "action-log", "list", kn_id,
    )
    steps.append(log_list)
    scorer.assert_exit_code(log_list, 0, "action-log list")
    scorer.assert_json(log_list, "action-log list returns JSON")

    # Step 5: action-log get (if logs exist)
    log_entries = log_list.parsed_json
    if isinstance(log_entries, dict):
        log_entries = (
            log_entries.get("entries")
            or log_entries.get("items")
            or []
        )
    if isinstance(log_entries, list) and log_entries:
        log_id = str(log_entries[0].get("id") or "")
        if log_id:
            log_get = await cli_agent.run_cli(
                "bkn", "action-log", "get", kn_id, log_id,
            )
            steps.append(log_get)
            scorer.assert_exit_code(log_get, 0, "action-log get")
            scorer.assert_json(
                log_get, "action-log get returns JSON",
            )

    det = scorer.result()
    await eval_case(
        "bkn_action_execute_and_log", steps, det, module="adp/bkn",
    )
    assert det.passed, det.failures
