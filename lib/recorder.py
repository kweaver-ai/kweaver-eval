"""Run history recorder: writes results to timestamped directories."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from lib.types import CaseResult


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
        """Write results.json + report.md and return path to run directory."""
        results_path = self._run_dir / "results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(self._results, f, indent=2, ensure_ascii=False)

        md_path = self._run_dir / "report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self._render_markdown())
        return self._run_dir

    def _render_markdown(self) -> str:
        """Render results as a readable Markdown report (Chinese)."""
        total = len(self._results)
        passed = sum(1 for r in self._results if r["status"] == "pass")
        failed = sum(1 for r in self._results if r["status"] == "fail")
        skipped = sum(1 for r in self._results if r["status"] == "skip")
        rate = f"{passed / total * 100:.0f}%" if total else "N/A"

        lines = [
            "# 评估报告",
            "",
            f"**{total}** 用例 | "
            f"**{passed}** 通过 | "
            f"**{failed}** 失败 | "
            f"**{skipped}** 跳过 | "
            f"通过率 **{rate}**",
            "",
            "## 测试结果",
            "",
            "| 用例 | 确定性 | Judge | 发现 |",
            "|------|--------|-------|------|",
        ]
        for r in self._results:
            det = "通过" if r.get("deterministic", {}).get("passed") else "失败"
            judge = r.get("judge")
            if judge:
                verdict = judge.get("verdict", "?")
                findings = judge.get("findings", [])
                finding_summary = self._summarize_findings(findings)
            else:
                verdict = "-"
                finding_summary = ""
            lines.append(
                f"| {r['name']} | {det} | {verdict} | {finding_summary} |",
            )

        # Failures detail
        failures = [r for r in self._results if r["status"] == "fail"]
        if failures:
            lines.extend(["", "## 失败详情", ""])
            for r in failures:
                lines.append(f"### {r['name']}")
                det = r.get("deterministic", {})
                for f in det.get("failures", []):
                    lines.append(f"- {f}")
                judge = r.get("judge")
                if judge:
                    for f in judge.get("findings", []):
                        sev = f.get("severity", "?")
                        msg = f.get("message", "")
                        lines.append(f"- **[{sev}]** {msg}")
                lines.append("")

        # Judge findings (warn/medium+)
        warn_cases = [
            r for r in self._results
            if (r.get("judge") or {}).get("verdict") == "warn"
        ]
        if warn_cases:
            lines.extend(["## 警告项", ""])
            for r in warn_cases:
                findings = r.get("judge", {}).get("findings", [])
                notable = [
                    f for f in findings
                    if f.get("severity") in ("medium", "high", "critical")
                ]
                if notable:
                    lines.append(f"**{r['name']}**")
                    for f in notable:
                        lines.append(
                            f"- [{f.get('severity')}] {f.get('message', '')}",
                        )
                    lines.append("")

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _summarize_findings(findings: list[dict]) -> str:
        if not findings:
            return ""
        by_sev: dict[str, int] = {}
        for f in findings:
            sev = f.get("severity", "?")
            by_sev[sev] = by_sev.get(sev, 0) + 1
        return ", ".join(f"{c}x {s}" for s, c in by_sev.items())

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
