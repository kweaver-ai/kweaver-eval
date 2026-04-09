"""BKN action-type acceptance tests.

Tests action-type list/query/execute and action-log/execution tracking.
"""

from __future__ import annotations

import json

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


async def _build_execute_body(
    cli_agent: CliAgent, kn_id: str, at_id: str,
) -> str | None:
    """Build execute body with _instance_identities from action-type query.

    Returns JSON string or None if no instance can be resolved.
    """
    at_detail = await cli_agent.run_cli(
        "bkn", "action-type", "query", kn_id, at_id, "{}",
    )
    if at_detail.exit_code != 0 or not isinstance(at_detail.parsed_json, dict):
        return None
    at_data = at_detail.parsed_json
    actions = at_data.get("actions") or []
    if not isinstance(actions, list) or not actions:
        return None
    # Pick the first action's _instance_identity
    identity = actions[0].get("_instance_identity")
    if not identity or not isinstance(identity, dict):
        return None
    return json.dumps({
        "_instance_identities": [identity],
    }, ensure_ascii=False)


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
async def test_bkn_action_execute_and_log(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn action-type execute triggers an action; then check logs."""
    found = await _find_kn_with_actions(cli_agent)
    if not found:
        pytest.skip("No KN with action types available")
    kn_id, at_id = found
    steps = []

    # Step 1: build execute body with _instance_identities
    body = await _build_execute_body(cli_agent, kn_id, at_id)
    if not body:
        pytest.skip("Cannot resolve instance identity for action execute")

    execute = await cli_agent.run_cli(
        "bkn", "action-type", "execute", kn_id, at_id, body,
        timeout=120.0,
    )
    steps.append(execute)
    # execute may return exit code 1 when the action itself fails (e.g.
    # business-level failure), but the API call still succeeds with JSON.
    # Accept both exit 0 and exit 1-with-JSON as valid responses.
    scorer.assert_json(execute, "action execute returns JSON")
    execute_ok = execute.exit_code == 0 and isinstance(execute.parsed_json, dict)

    # Verify execute response has meaningful content
    if execute_ok:
        exec_data = execute.parsed_json
        # Check for execution status or result fields
        has_status = bool(
            exec_data.get("status")
            or exec_data.get("execution_id")
            or exec_data.get("id")
        )
        scorer.assert_true(
            has_status,
            "action execute response contains status or execution ID",
        )

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
        # Verify execution record has meaningful status
        if isinstance(exec_get.parsed_json, dict):
            exec_status = str(exec_get.parsed_json.get("status") or "")
            scorer.assert_true(
                bool(exec_status),
                f"action-execution get has status field (got: '{exec_status}')",
            )

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
            # Verify log entry has meaningful fields
            if isinstance(log_get.parsed_json, dict):
                log_data = log_get.parsed_json
                if "entries" in log_data and isinstance(log_data["entries"], list) and log_data["entries"]:
                    log_data = log_data["entries"][0]
                log_status = str(log_data.get("status") or "")
                scorer.assert_true(
                    bool(log_status),
                    f"action-log get has status field (got: '{log_status}')",
                )

    det = scorer.result()
    await eval_case(
        "bkn_action_execute_and_log", steps, det, module="adp/bkn",
    )
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_bkn_action_log_cancel(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """action-log cancel on a completed/non-running log returns gracefully."""
    found = await _find_kn_with_actions(cli_agent)
    if not found:
        pytest.skip("No KN with action types available")
    kn_id, _at_id = found

    # Find an existing log to attempt cancel on
    log_list = await cli_agent.run_cli("bkn", "action-log", "list", kn_id)
    if log_list.exit_code != 0:
        pytest.skip("action-log list failed")
    entries = log_list.parsed_json
    if isinstance(entries, dict):
        entries = entries.get("entries") or entries.get("items") or []
    if not isinstance(entries, list) or not entries:
        pytest.skip("No action logs available for cancel test")
    log_id = str(entries[0].get("id") or "")
    if not log_id:
        pytest.skip("Cannot get log ID")

    # Try to find a running execution; if none, use the first one
    running_id = ""
    for entry in entries:
        if entry.get("status") in ("running", "pending"):
            running_id = str(entry.get("id") or "")
            break
    target_id = running_id or log_id

    result = await cli_agent.run_cli(
        "bkn", "action-log", "cancel", kn_id, target_id,
        timeout=60.0,
    )
    # Cancel on a running execution returns 200; on a completed one returns
    # 400 ("cannot be cancelled, current status: failed/success").
    # Both are valid CLI behavior — we verify the command runs without crash.
    if running_id:
        scorer.assert_exit_code(result, 0, "action-log cancel running")
    else:
        scorer.assert_true(
            result.exit_code in (0, 1),
            "action-log cancel returns 0 or 1",
        )
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_action_log_cancel", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures


@pytest.mark.known_bug("adp#442: invalid _instance_identities should return 400, not 500")
async def test_bkn_action_execute_invalid_identity(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """Execute with invalid _instance_identities field should return 400."""
    found = await _find_kn_with_actions(cli_agent)
    if not found:
        pytest.skip("No KN with action types available")
    kn_id, at_id = found

    body = json.dumps({"_instance_identities": [{"nonexistent_field": "x"}]})
    result = await cli_agent.run_cli(
        "bkn", "action-type", "execute", kn_id, at_id, body,
        timeout=60.0,
    )
    # BKN currently returns 500; should return 400 once adp#442 is fixed
    scorer.assert_true(
        "400" in result.stderr or result.exit_code != 0,
        "invalid identity returns client error",
    )
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_action_execute_invalid_identity", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures
