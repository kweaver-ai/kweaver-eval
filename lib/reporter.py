"""Aggregate report generation."""

from __future__ import annotations

import json

from lib.agents.judge_agent import JudgeAgent
from lib.feedback import FeedbackTracker
from lib.types import AgentRequest, CaseResult


class Reporter:
    """Generates aggregate reports from evaluation results."""

    def __init__(self, feedback: FeedbackTracker):
        self._feedback = feedback

    def deterministic_summary(self, results: list[CaseResult]) -> dict:
        """Generate deterministic-only summary (no agent cost)."""
        total = len(results)
        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        skipped = sum(1 for r in results if r.status == "skip")

        failures = []
        for r in results:
            if r.deterministic and r.deterministic.failures:
                failures.append({
                    "case": r.name,
                    "failures": r.deterministic.failures,
                })

        persistent = self._feedback.get_persistent_items()
        human_attn = self._feedback.get_human_attention_items()

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pass_rate": f"{passed / total * 100:.1f}%" if total > 0 else "N/A",
            "failure_details": failures,
            "persistent_issues": [
                {"id": i.id, "message": i.message, "times_seen": i.times_seen, "test_case": i.test_case}
                for i in persistent
            ],
            "needs_human_attention": [
                {"id": i.id, "message": i.message, "times_seen": i.times_seen, "test_case": i.test_case}
                for i in human_attn
            ],
        }

    async def agent_report(self, results: list[CaseResult]) -> dict:
        """Generate full report with agent health analysis."""
        det_summary = self.deterministic_summary(results)
        judge = JudgeAgent(role="health_analyst")

        request = AgentRequest(
            action="Generate aggregate health report for this evaluation run.",
            context={
                "deterministic_summary": det_summary,
                "case_results": [
                    {
                        "name": r.name,
                        "status": r.status,
                        "deterministic_passed": r.deterministic.passed if r.deterministic else None,
                        "judge_verdict": r.judge.verdict if r.judge else None,
                        "judge_findings": [
                            {"severity": f.severity.value, "message": f.message}
                            for f in (r.judge.findings if r.judge else [])
                        ],
                    }
                    for r in results
                ],
                "feedback_items": [
                    {"message": i.message, "times_seen": i.times_seen, "severity": i.severity}
                    for i in self._feedback.all_items()
                    if not i.resolved
                ],
            },
        )

        result = await judge.run(request)
        try:
            agent_analysis = json.loads(result.output)
        except (json.JSONDecodeError, ValueError):
            agent_analysis = {"raw": result.output}

        return {
            "deterministic": det_summary,
            "agent_analysis": agent_analysis,
        }
