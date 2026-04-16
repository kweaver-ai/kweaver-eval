"""BKN action-schedule acceptance tests.

Covers:
  - bkn.action_schedule.list       — list schedules for a KN
  - bkn.action_schedule.get        — get schedule detail
  - bkn.action_schedule.set_status — enable/disable a schedule
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def _find_kn_with_schedules(cli_agent: CliAgent) -> tuple[str, str] | None:
    """Find a KN that has action schedules. Returns (kn_id, schedule_id) or None."""
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
        sched_result = await cli_agent.run_cli(
            "bkn", "action-schedule", "list", kn_id,
        )
        if sched_result.exit_code != 0:
            continue
        entries = sched_result.parsed_json
        if isinstance(entries, dict):
            entries = entries.get("entries") or entries.get("items") or []
        if isinstance(entries, list) and entries:
            sched_id = str(entries[0].get("id") or "")
            if sched_id:
                return kn_id, sched_id
    return None


async def test_bkn_action_schedule_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn action-schedule list returns schedules for a KN."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "5")
    if result.exit_code != 0:
        pytest.skip("Cannot list KNs")
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or []
    if not isinstance(kns, list) or not kns:
        pytest.skip("No KNs available")
    kn_id = str(kns[0].get("id") or kns[0].get("kn_id") or "")
    if not kn_id:
        pytest.skip("Cannot determine KN ID")

    sched_result = await cli_agent.run_cli(
        "bkn", "action-schedule", "list", kn_id,
    )
    scorer.assert_exit_code(sched_result, 0, "action-schedule list")
    scorer.assert_json(sched_result, "action-schedule list returns JSON")
    det = scorer.result(sched_result.duration_ms)
    await eval_case(
        "bkn_action_schedule_list", [sched_result], det, module="adp/bkn",
    )
    assert det.passed, det.failures


async def test_bkn_action_schedule_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn action-schedule get returns schedule detail."""
    found = await _find_kn_with_schedules(cli_agent)
    if not found:
        pytest.skip("No KN with action schedules available")
    kn_id, sched_id = found

    result = await cli_agent.run_cli(
        "bkn", "action-schedule", "get", kn_id, sched_id,
    )
    scorer.assert_exit_code(result, 0, "action-schedule get")
    scorer.assert_json(result, "action-schedule get returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_action_schedule_get", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures


async def test_bkn_action_schedule_set_status(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn action-schedule set-status toggles schedule enable/disable."""
    found = await _find_kn_with_schedules(cli_agent)
    if not found:
        pytest.skip("No KN with action schedules available")
    kn_id, sched_id = found

    result = await cli_agent.run_cli(
        "bkn", "action-schedule", "set-status", kn_id, sched_id, "disable",
    )
    scorer.assert_exit_code(result, 0, "action-schedule set-status disable")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_action_schedule_set_status", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures
