"""Judge agent: evaluates test results via Claude API with role prompts."""

from __future__ import annotations

import json
import time

from lib.agents.base import BaseAgent
from lib.types import AgentRequest, AgentResult, Finding, JudgeResult, Severity


class JudgeAgent(BaseAgent):
    """Evaluates test case results using Claude API with configurable role prompts."""

    def __init__(self, role: str = "acceptability_judge", model: str = "claude-sonnet-4-20250514"):
        self._role = role
        self._model = model
        self._client = None

    def get_model(self) -> str:
        return self._model

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    async def run(self, request: AgentRequest) -> AgentResult:
        """Evaluate test results. Returns AgentResult with JudgeResult serialized as JSON."""
        system_prompt = self._load_role_prompt(self._role)
        user_prompt = request.prompt_override or self._build_prompt(request)

        start = time.monotonic()
        client = self._get_client()
        message = client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system_prompt or "You are a QA evaluation agent.",
            messages=[{"role": "user", "content": user_prompt}],
        )
        elapsed = (time.monotonic() - start) * 1000

        raw = message.content[0].text
        judge_result = self._parse_response(raw)
        judge_result.model = self._model

        return AgentResult(
            output=json.dumps({
                "verdict": judge_result.verdict,
                "findings": [
                    {"severity": f.severity.value, "message": f.message, "location": f.location}
                    for f in judge_result.findings
                ],
                "reasoning": judge_result.reasoning,
            }),
            model=self._model,
            duration_ms=elapsed,
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )

    def _build_prompt(self, request: AgentRequest) -> str:
        ctx = request.context
        parts = [f"## Task\n{request.action}"]
        if "case_name" in ctx:
            parts.append(f"## Test Case\n{ctx['case_name']}")
        if "steps" in ctx:
            parts.append("## Execution Steps")
            for i, step in enumerate(ctx["steps"], 1):
                parts.append(
                    f"### Step {i}: `{' '.join(step.get('command', []))}`\n"
                    f"- exit_code: {step.get('exit_code')}\n"
                    f"- duration: {step.get('duration_ms', 0):.0f}ms\n"
                    f"- stdout: ```\n{step.get('stdout', '')[:2000]}\n```\n"
                    f"- stderr: ```\n{step.get('stderr', '')[:500]}\n```"
                )
        if "deterministic_result" in ctx:
            det = ctx["deterministic_result"]
            parts.append(
                f"## Deterministic Result\n"
                f"- passed: {det.get('passed')}\n"
                f"- failures: {det.get('failures', [])}"
            )
        return "\n\n".join(parts)

    def _parse_response(self, raw: str) -> JudgeResult:
        """Parse judge response. Expects JSON with verdict, findings, reasoning."""
        try:
            data = json.loads(self._extract_json(raw))
        except (json.JSONDecodeError, ValueError):
            return JudgeResult(
                verdict="fail",
                findings=[
                    Finding(severity=Severity.MEDIUM, message="Could not parse judge response")
                ],
                reasoning=raw[:500],
            )

        findings = []
        for f in data.get("findings", []):
            try:
                sev = Severity(f.get("severity", "medium"))
            except ValueError:
                sev = Severity.MEDIUM
            findings.append(Finding(
                severity=sev,
                message=f.get("message", ""),
                location=f.get("location", ""),
            ))

        return JudgeResult(
            verdict=data.get("verdict", "fail"),
            findings=findings,
            reasoning=data.get("reasoning", ""),
        )

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON from text, handling markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines) - 1
            if lines[end].strip() == "```":
                return "\n".join(lines[start:end])
        if text.startswith("{") or text.startswith("["):
            return text
        for marker in ["```json\n", "```\n"]:
            idx = text.find(marker)
            if idx >= 0:
                start = idx + len(marker)
                end = text.find("```", start)
                if end > start:
                    return text[start:end]
        return text
