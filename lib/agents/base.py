"""Abstract base agent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from lib.types import AgentRequest, AgentResult


class BaseAgent(ABC):
    """Abstract agent that can execute actions via different transports."""

    @abstractmethod
    async def run(self, request: AgentRequest) -> AgentResult:
        """Execute a request and return structured result."""
        ...

    @abstractmethod
    def get_model(self) -> str:
        """Return the model identifier for this agent."""
        ...

    def _load_role_prompt(self, role: str) -> str:
        """Load role prompt from soul.md + instructions.md.

        Search order:
        1. .kweaver-eval/roles/<role>/
        2. ~/.kweaver-eval/roles/<role>/
        3. roles/<role>/ (built-in)
        """
        search_paths = [
            Path(".kweaver-eval/roles") / role,
            Path.home() / ".kweaver-eval/roles" / role,
            Path("roles") / role,
        ]
        for base in search_paths:
            soul = base / "soul.md"
            instructions = base / "instructions.md"
            if soul.exists() or instructions.exists():
                parts = []
                if soul.exists():
                    parts.append(soul.read_text(encoding="utf-8"))
                if instructions.exists():
                    parts.append(instructions.read_text(encoding="utf-8"))
                return "\n\n".join(parts)
        return ""
