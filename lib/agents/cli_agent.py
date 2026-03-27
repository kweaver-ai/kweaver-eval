"""CLI agent: executes kweaver CLI commands as subprocess."""

from __future__ import annotations

import asyncio
import json
import time

from lib.agents.base import BaseAgent
from lib.types import AgentRequest, AgentResult, CliResult


class CliAgent(BaseAgent):
    """Executes kweaver CLI commands as subprocess."""

    def __init__(self, cli_binary: str = "kweaver"):
        self._cli = cli_binary

    def get_model(self) -> str:
        return f"cli:{self._cli}"

    async def run(self, request: AgentRequest) -> AgentResult:
        """Run a CLI command. request.context["args"] must be a list of strings."""
        args = request.context.get("args", [])
        timeout = request.context.get("timeout", 30.0)
        result = await self.run_cli(*args, timeout=timeout)
        return AgentResult(
            output=result.stdout,
            model=self.get_model(),
            duration_ms=result.duration_ms,
            usage={"exit_code": result.exit_code},
        )

    async def run_cli(self, *args: str, timeout: float = 30.0) -> CliResult:
        """Run kweaver CLI command as subprocess."""
        cmd = [self._cli, *args]
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            elapsed = (time.monotonic() - start) * 1000
            return CliResult(
                command=cmd,
                exit_code=-1,
                stdout="",
                stderr=f"Timeout after {timeout}s",
                duration_ms=elapsed,
            )

        elapsed = (time.monotonic() - start) * 1000
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        parsed = None
        try:
            parsed = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            pass

        return CliResult(
            command=cmd,
            exit_code=proc.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            duration_ms=elapsed,
            parsed_json=parsed,
        )
