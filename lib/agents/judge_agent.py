"""Judge agent: evaluates test results via Claude CLI with role prompts.

Uses `claude` CLI subprocess (same as shadowcoder) instead of Anthropic SDK,
so no ANTHROPIC_API_KEY is needed — authentication is handled by Claude Code.
"""

from __future__ import annotations

import asyncio
import json
import time

from lib.agents.base import BaseAgent
from lib.types import AgentRequest, AgentResult, Finding, JudgeResult, Severity


class JudgeAgent(BaseAgent):
    """Evaluates test case results using Claude CLI with configurable role prompts."""

    def __init__(self, role: str = "acceptability_judge", model: str = "sonnet"):
        self._role = role
        self._model = model

    def get_model(self) -> str:
        return self._model

    async def run(self, request: AgentRequest) -> AgentResult:
        """Evaluate test results via claude CLI subprocess."""
        system_prompt = self._load_role_prompt(self._role)
        user_prompt = request.prompt_override or self._build_prompt(request)

        start = time.monotonic()
        cmd = [
            "claude", "-p",
            "--output-format", "json",
            "--model", self._model,
        ]
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(user_prompt.encode("utf-8")),
            timeout=120.0,
        )
        elapsed = (time.monotonic() - start) * 1000

        stdout = stdout_bytes.decode("utf-8", errors="replace")

        # claude --output-format json returns {"result": "...", "usage": {...}}
        raw_text = ""
        usage = {}
        try:
            envelope = json.loads(stdout)
            raw_text = envelope.get("result", stdout)
            usage = envelope.get("usage", {})
        except (json.JSONDecodeError, ValueError):
            raw_text = stdout

        judge_result = self._parse_response(raw_text)
        judge_result.model = self._model

        return AgentResult(
            output=json.dumps({
                "verdict": judge_result.verdict,
                "findings": [
                    {
                        "severity": f.severity.value,
                        "message": f.message,
                        "location": f.location,
                    }
                    for f in judge_result.findings
                ],
                "reasoning": judge_result.reasoning,
            }),
            model=self._model,
            duration_ms=elapsed,
            usage=usage,
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
                    Finding(
                        severity=Severity.MEDIUM,
                        message="Could not parse judge response",
                    )
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
