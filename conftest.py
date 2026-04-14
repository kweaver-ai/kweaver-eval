"""Root pytest configuration for kweaver-eval."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lib.agents.cli_agent import CliAgent
from lib.agents.judge_agent import JudgeAgent
from lib.feedback import FeedbackTracker
from lib.recorder import Recorder
from lib.scorer import Scorer
from lib.types import (
    AgentRequest,
    CaseResult,
    DeterministicResult,
    Finding,
    JudgeResult,
    Severity,
)


def _load_env_file(path: str) -> None:
    """Load environment variables from a file (simple .env parser)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ")
        eq = line.find("=")
        if eq < 0:
            continue
        key = line[:eq].strip()
        value = line[eq + 1 :].strip().strip("\"'")
        if key not in os.environ:
            os.environ[key] = value


# Load env files: local .env first, then ~/.env.secrets as fallback
_load_env_file(".env")
_load_env_file(os.path.join(Path.home(), ".env.secrets"))



# ---------- Auto-skip marked tests ----------


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-skip tests marked known_bug, wait_for_env, or tbd."""
    for item in items:
        for marker_name in ("known_bug", "wait_for_env", "tbd"):
            marker = item.get_closest_marker(marker_name)
            if marker:
                reason = marker.args[0] if marker.args else marker_name
                item.add_marker(pytest.mark.skip(reason=reason))


# ---------- Session-scoped fixtures ----------


@pytest.fixture(scope="session")
def base_url() -> str:
    url = os.environ.get("KWEAVER_BASE_URL", "")
    if not url:
        pytest.skip("KWEAVER_BASE_URL not set")
    return url


@pytest.fixture(scope="session")
def cli_agent() -> CliAgent:
    """Create CLI agent with platform-appropriate command."""
    import sys
    # On Windows, use kweaver.cmd if available, otherwise fall back to kweaver
    if sys.platform == "win32":
        return CliAgent(cli_binary="kweaver.cmd")
    return CliAgent()


@pytest.fixture(scope="session")
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture(scope="session")
def feedback_tracker() -> FeedbackTracker:
    return FeedbackTracker()


# ---------- Per-test fixtures ----------


@pytest.fixture
def scorer() -> Scorer:
    return Scorer()


# ---------- eval_case helper ----------


@pytest.fixture
def eval_case(recorder: Recorder, feedback_tracker: FeedbackTracker):
    """Helper that wraps deterministic + optional agent judge + record into one call.

    Usage:
        await eval_case("test_name", [cli_result], det_result,
                         module="adp/bkn", eval_hints={...})
    """

    async def _eval(
        name: str,
        steps: list,
        det: DeterministicResult,
        *,
        module: str | None = None,
        eval_hints: dict | None = None,
    ) -> None:
        judge_result: JudgeResult | None = None

        if os.environ.get("EVAL_AGENT_JUDGE"):
            judge = JudgeAgent(role="acceptability_judge")
            context: dict = {
                "case_name": name,
                "steps": [
                    {
                        "command": s.command,
                        "exit_code": s.exit_code,
                        "stdout": s.stdout,
                        "stderr": s.stderr,
                        "duration_ms": s.duration_ms,
                    }
                    for s in steps
                ],
                "deterministic_result": {
                    "passed": det.passed,
                    "failures": det.failures,
                },
            }
            if module:
                context["module"] = module
            if eval_hints:
                context["eval_hints"] = eval_hints

            agent_result = await judge.run(AgentRequest(
                action=f"Evaluate whether the '{name}' test output is acceptable.",
                context=context,
            ))
            try:
                jdata = json.loads(agent_result.output)
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
                for finding in judge_result.findings:
                    feedback_tracker.record_finding(name, finding)
            except (json.JSONDecodeError, ValueError):
                pass

        recorder.record_case(CaseResult(
            name=name,
            status="pass" if det.passed else "fail",
            deterministic=det,
            judge=judge_result,
            steps=steps,
        ))

    return _eval


# ---------- Session teardown ----------


@pytest.fixture(scope="session", autouse=True)
def finalize(recorder, feedback_tracker):
    """Flush results and save feedback after all tests."""
    yield
    recorder.flush()
    feedback_tracker.save()
