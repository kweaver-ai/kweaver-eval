"""Run history recorder: writes results to timestamped directories."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from lib.types import CaseResult, CliResult


class Recorder:
    """Records test run results to timestamped directories under test-result/runs/."""

    def __init__(self, base_dir: str = "test-result"):
        self._base = Path(base_dir)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        self._run_dir = self._base / "runs" / ts
        self._run_dir.mkdir(parents=True, exist_ok=True)
        (self._run_dir / "logs").mkdir(exist_ok=True)
        self._results: list[dict] = []

        # Update latest symlink
        latest = self._base / "runs" / "latest"
        if latest.is_symlink() or latest.exists():
            latest.unlink()
        latest.symlink_to(self._run_dir.name)

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def record_case(self, case: CaseResult) -> None:
        """Record a single case result."""
        self._results.append(self._serialize_case(case))
        # Write per-case log
        log_path = self._run_dir / "logs" / f"{case.name}.log"
        with open(log_path, "w", encoding="utf-8") as f:
            for step in case.steps:
                f.write(f"$ {' '.join(step.command)}\n")
                f.write(f"exit_code: {step.exit_code}\n")
                f.write(f"duration: {step.duration_ms:.0f}ms\n")
                if step.stdout:
                    f.write(f"--- stdout ---\n{step.stdout}\n")
                if step.stderr:
                    f.write(f"--- stderr ---\n{step.stderr}\n")
                f.write("\n")

    def flush(self) -> Path:
        """Write results.json and return path to run directory."""
        results_path = self._run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(self._results, f, indent=2, ensure_ascii=False)
        return self._run_dir

    def write_report(self, report: dict) -> None:
        """Write aggregate report."""
        report_path = self._run_dir / "report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _serialize_case(case: CaseResult) -> dict:
        d = asdict(case)
        # Ensure enum values are strings
        if d.get("judge") and d["judge"].get("findings"):
            for f in d["judge"]["findings"]:
                if hasattr(f.get("severity"), "value"):
                    f["severity"] = f["severity"].value
        return d
