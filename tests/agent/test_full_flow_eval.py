"""Agent-driven full flow evaluation.

This test uses the JudgeAgent to semantically evaluate whether
a BKN lifecycle operation produces acceptable results.
"""

from __future__ import annotations

import os

from lib.agents.cli_agent import CliAgent
from lib.agents.judge_agent import JudgeAgent
from lib.feedback import FeedbackTracker
from lib.recorder import Recorder
from lib.scorer import Scorer
from lib.types import CaseResult, Finding, Severity


async def test_bkn_list_acceptability(
    cli_agent: CliAgent, scorer: Scorer, recorder: Recorder, feedback_tracker: FeedbackTracker
):
    """Evaluate whether bkn list output is acceptable from a user perspective.

    Deterministic: checks exit code and JSON format.
    Agent judge: evaluates output quality, completeness, usability.
    """
    result = await cli_agent.run_cli("bkn", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="bkn list returns array")

    det = scorer.result(result.duration_ms)

    # Agent judge (opt-in via env var)
    judge_result = None
    if os.environ.get("EVAL_AGENT_JUDGE"):
        judge = JudgeAgent(role="acceptability_judge")
        from lib.types import AgentRequest

        agent_result = await judge.run(AgentRequest(
            action="Evaluate whether the 'bkn list' command output is acceptable for a user.",
            context={
                "case_name": "test_bkn_list_acceptability",
                "steps": [
                    {
                        "command": result.command,
                        "exit_code": result.exit_code,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "duration_ms": result.duration_ms,
                    }
                ],
                "deterministic_result": {
                    "passed": det.passed,
                    "failures": det.failures,
                },
            },
        ))
        import json

        try:
            jdata = json.loads(agent_result.output)
            from lib.types import JudgeResult

            judge_result = JudgeResult(
                verdict=jdata.get("verdict", "fail"),
                findings=[
                    Finding(
                        severity=Severity(f.get("severity", "medium")),
                        message=f.get("message", ""),
                        location=f.get("location", ""),
                    )
                    for f in jdata.get("findings", [])
                ],
                reasoning=jdata.get("reasoning", ""),
                model=agent_result.model,
            )
            # Record findings in feedback tracker
            for finding in judge_result.findings:
                feedback_tracker.record_finding("test_bkn_list_acceptability", finding)
        except (json.JSONDecodeError, ValueError):
            pass

    case = CaseResult(
        name="test_bkn_list_acceptability",
        status="pass" if det.passed else "fail",
        deterministic=det,
        judge=judge_result,
        steps=[result],
    )
    recorder.record_case(case)
    assert det.passed, det.failures
