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


async def test_bkn_action_schedule_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_action_schedule: tuple[str, str],
):
    """bkn action-schedule list returns schedules for a KN."""
    kn_id, _sched_id = kn_with_action_schedule

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
    kn_with_action_schedule: tuple[str, str],
):
    """bkn action-schedule get returns schedule detail."""
    kn_id, sched_id = kn_with_action_schedule

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
    kn_with_action_schedule: tuple[str, str],
):
    """bkn action-schedule set-status toggles schedule enable/disable."""
    kn_id, sched_id = kn_with_action_schedule

    result = await cli_agent.run_cli(
        "bkn", "action-schedule", "set-status", kn_id, sched_id, "inactive",
    )
    scorer.assert_exit_code(result, 0, "action-schedule set-status inactive")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_action_schedule_set_status", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures
