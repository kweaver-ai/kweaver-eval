"""Dataflow read-only acceptance tests.

Covers: list, get, status, logs — operations that do not mutate server state.
Pattern: follows bkn/test_read.py and vega/test_health.py conventions.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_dataflow_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """dataflow list returns a JSON array of dataflows."""
    result = await cli_agent.run_cli("dataflow", "list")
    if result.exit_code != 0 and (
        "command not found" in result.stderr.lower()
        or "unknown" in result.stderr.lower()
        or "not implemented" in result.stderr.lower()
    ):
        pytest.skip("dataflow CLI not yet available")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="dataflow list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_list", [result], det, module="adp/dataflow")
    assert det.passed, det.failures


async def test_dataflow_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case, df_id: str,
):
    """dataflow get returns details for a specific dataflow."""
    result = await cli_agent.run_cli("dataflow", "get", df_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_field(
        result, "id",
        label="dataflow get contains id field",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_get", [result], det, module="adp/dataflow")
    assert det.passed, det.failures


async def test_dataflow_get_verbose(
    cli_agent: CliAgent, scorer: Scorer, eval_case, df_id: str,
):
    """dataflow get --verbose returns full configuration including nodes/edges."""
    result = await cli_agent.run_cli("dataflow", "get", df_id, "--verbose")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_get_verbose", [result], det, module="adp/dataflow",
                    eval_hints={
                        "focus": "completeness",
                        "description": "Verbose output should include full DAG definition (nodes, edges, source/sink config)",
                    })
    assert det.passed, det.failures


async def test_dataflow_status(
    cli_agent: CliAgent, scorer: Scorer, eval_case, df_id: str,
):
    """dataflow status returns current execution state."""
    result = await cli_agent.run_cli("dataflow", "status", df_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_field(
        result, "status",
        label="dataflow status contains status field",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_status", [result], det, module="adp/dataflow")
    assert det.passed, det.failures


async def test_dataflow_logs(
    cli_agent: CliAgent, scorer: Scorer, eval_case, df_id: str,
):
    """dataflow logs returns recent execution log entries."""
    result = await cli_agent.run_cli("dataflow", "logs", df_id, "--limit", "10")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_logs", [result], det, module="adp/dataflow",
                    eval_hints={
                        "focus": "log_quality",
                        "description": "Logs should be structured with timestamps and levels (info/warn/error)",
                        "latency_budget_ms": 5000,
                    })
    assert det.passed, det.failures


async def test_dataflow_validate(
    cli_agent: CliAgent, scorer: Scorer, eval_case, df_id: str,
):
    """dataflow validate checks DAG correctness without executing."""
    result = await cli_agent.run_cli("dataflow", "validate", df_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_field(
        result, "valid",
        expected=True,
        label="dataflow validate reports valid DAG",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_validate", [result], det, module="adp/dataflow",
                    eval_hints={
                        "focus": "validation_accuracy",
                        "description": "Validation should detect cycles, missing sources, and type mismatches",
                    })
    assert det.passed, det.failures
