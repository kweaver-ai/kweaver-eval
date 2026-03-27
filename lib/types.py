"""Core type definitions for kweaver-eval."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """Severity level for agent judge findings."""

    CRITICAL = "critical"   # System broken, blocks usage
    HIGH = "high"           # Major feature degraded
    MEDIUM = "medium"       # Minor issue, workaround exists
    LOW = "low"             # Cosmetic or optimization opportunity


@dataclass
class CliResult:
    """Result of a single CLI command execution."""

    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    parsed_json: dict | list | None = None  # Auto-parsed if stdout is valid JSON


@dataclass
class Finding:
    """A single finding from an agent judge."""

    severity: Severity
    message: str
    location: str = ""  # Which step or assertion triggered this


@dataclass
class JudgeResult:
    """Result from agent judge evaluation."""

    verdict: str  # "pass" | "fail" | "warn"
    findings: list[Finding] = field(default_factory=list)
    reasoning: str = ""
    model: str = ""


@dataclass
class DeterministicResult:
    """Result of deterministic scoring for a case."""

    passed: bool
    assertions: list[str]  # Description of each assertion
    failures: list[str]  # Failed assertion details
    duration_ms: float = 0.0


@dataclass
class CaseResult:
    """Complete result for a single test case."""

    name: str
    status: str  # "pass" | "fail" | "skip"
    deterministic: DeterministicResult
    judge: JudgeResult | None = None
    steps: list[CliResult] = field(default_factory=list)
    timestamp: str = ""  # ISO format


@dataclass
class AgentRequest:
    """Request to an agent."""

    action: str
    context: dict = field(default_factory=dict)
    prompt_override: str | None = None


@dataclass
class AgentResult:
    """Result from an agent execution."""

    output: str
    model: str = ""
    duration_ms: float = 0.0
    usage: dict = field(default_factory=dict)
