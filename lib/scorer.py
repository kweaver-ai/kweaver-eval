"""Deterministic scoring helpers for test assertions."""

from __future__ import annotations

from lib.types import CliResult, DeterministicResult


class Scorer:
    """Collects deterministic assertions and produces a DeterministicResult."""

    def __init__(self):
        self._assertions: list[str] = []
        self._failures: list[str] = []

    def assert_exit_code(self, result: CliResult, expected: int = 0, label: str = "") -> None:
        desc = label or f"`{' '.join(result.command)}` exit code"
        self._assertions.append(f"{desc} == {expected}")
        if result.exit_code != expected:
            self._failures.append(f"{desc}: expected {expected}, got {result.exit_code}")

    def assert_json(self, result: CliResult, label: str = "") -> None:
        desc = label or f"`{' '.join(result.command)}` returns valid JSON"
        self._assertions.append(desc)
        if result.parsed_json is None:
            self._failures.append(f"{desc}: stdout is not valid JSON")

    def assert_json_field(
        self, result: CliResult, field: str, *, expected=None, label: str = ""
    ) -> None:
        desc = label or f"`{' '.join(result.command)}` .{field}"
        if result.parsed_json is None:
            self._assertions.append(desc)
            self._failures.append(f"{desc}: no JSON to check")
            return
        data = result.parsed_json
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
        if not isinstance(data, dict):
            self._assertions.append(desc)
            self._failures.append(f"{desc}: JSON is not an object")
            return
        if field not in data:
            self._assertions.append(f"{desc} exists")
            self._failures.append(f"{desc}: field missing")
            return
        if expected is not None:
            self._assertions.append(f"{desc} == {expected!r}")
            if data[field] != expected:
                self._failures.append(f"{desc}: expected {expected!r}, got {data[field]!r}")
        else:
            self._assertions.append(f"{desc} exists")

    def assert_json_is_list(
        self, result: CliResult, *, min_length: int = 0, label: str = "",
    ) -> None:
        desc = label or f"`{' '.join(result.command)}` returns list"
        self._assertions.append(desc)
        if not isinstance(result.parsed_json, list):
            self._failures.append(f"{desc}: expected list, got {type(result.parsed_json).__name__}")
        elif len(result.parsed_json) < min_length:
            self._failures.append(
                f"{desc}: expected >= {min_length} items, got {len(result.parsed_json)}"
            )

    def assert_stdout_contains(self, result: CliResult, substring: str, label: str = "") -> None:
        desc = label or f"stdout contains '{substring}'"
        self._assertions.append(desc)
        if substring not in result.stdout:
            self._failures.append(f"{desc}: not found in stdout")

    def assert_true(self, condition: bool, description: str) -> None:
        self._assertions.append(description)
        if not condition:
            self._failures.append(f"{description}: False")

    def result(self, duration_ms: float = 0.0) -> DeterministicResult:
        return DeterministicResult(
            passed=len(self._failures) == 0,
            assertions=list(self._assertions),
            failures=list(self._failures),
            duration_ms=duration_ms,
        )
