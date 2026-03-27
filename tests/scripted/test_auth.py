"""Auth and token refresh acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.recorder import Recorder
from lib.scorer import Scorer
from lib.types import CaseResult


@pytest.fixture
def auth_scorer():
    return Scorer()


async def test_auth_status(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """Verify auth status returns current authentication info."""
    result = await cli_agent.run_cli("auth", "status")
    scorer.assert_exit_code(result, 0)
    scorer.assert_stdout_contains(result, "Token status:", label="auth status shows token info")

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_auth_status",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures


async def test_auth_whoami(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """Verify auth whoami returns user identity."""
    result = await cli_agent.run_cli("auth", "status")
    scorer.assert_exit_code(result, 0)
    scorer.assert_stdout_contains(result, "Token status:", label="auth status shows token info")

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_auth_whoami",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures
