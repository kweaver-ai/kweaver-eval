"""Dataflow read-only acceptance tests.

Covers: list, runs, logs — operations that do not mutate server state.
Pattern: follows bkn/test_read.py and vega/test_health.py conventions.

Note: Only implemented commands are tested here. Additional read operations
(get, status, validate) will be added when CLI support is available.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_dataflow_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """dataflow list returns a JSON array of dataflows.
    
    In no-auth mode (KWEAVER_TOKEN=__NO_AUTH__), this test validates:
    - CLI command is available and executable
    - Command structure is correct
    - Error handling works properly (may return 401)
    
    In authenticated mode, this test validates:
    - API returns valid dataflow list
    - Response format is correct
    """
    result = await cli_agent.run_cli("dataflow", "list")
    
    # Check if CLI command is available
    if result.exit_code != 0 and (
        "command not found" in result.stderr.lower()
        or "unknown" in result.stderr.lower()
        or "not implemented" in result.stderr.lower()
    ):
        pytest.skip("dataflow CLI not yet available")
    
    # In no-auth mode, CLI may return 401 - this is expected behavior
    # We still validate the CLI executed correctly
    import os
    is_no_auth = os.environ.get("KWEAVER_TOKEN") == "__NO_AUTH__"
    
    if is_no_auth:
        # No-auth mode: just verify CLI executed (exit code can be 0 or 1)
        # The important thing is the command ran without crashing
        scorer.assert_true(
            result.exit_code in [0, 1],
            "dataflow list CLI executed (no-auth mode)"
        )
        det = scorer.result(result.duration_ms)
        await eval_case("dataflow_list_no_auth", [result], det, module="adp/dataflow",
                        eval_hints={
                            "focus": "cli_availability",
                            "description": "CLI command is available and executes in no-auth mode. API may return 401.",
                            "latency_budget_ms": 5000,
                        })
        assert det.passed, det.failures
    else:
        # Authenticated mode: full validation
        scorer.assert_exit_code(result, 0)
        scorer.assert_json(result)
        scorer.assert_json_is_list(result, label="dataflow list returns array")
        det = scorer.result(result.duration_ms)
        await eval_case("dataflow_list", [result], det, module="adp/dataflow")
        assert det.passed, det.failures


async def test_dataflow_runs(
    cli_agent: CliAgent, scorer: Scorer, eval_case, df_id: str,
):
    """dataflow runs returns run history for a specific dataflow.
    
    In no-auth mode, this test validates CLI command availability.
    In authenticated mode, this test validates API response structure.
    """
    result = await cli_agent.run_cli("dataflow", "runs", df_id)
    if result.exit_code != 0 and (
        "command not found" in result.stderr.lower()
        or "unknown" in result.stderr.lower()
    ):
        pytest.skip("dataflow runs CLI not yet available")
    
    import os
    is_no_auth = os.environ.get("KWEAVER_TOKEN") == "__NO_AUTH__"
    
    if is_no_auth:
        # No-auth mode: just verify CLI executed
        scorer.assert_true(
            result.exit_code in [0, 1],
            "dataflow runs CLI executed (no-auth mode)"
        )
        det = scorer.result(result.duration_ms)
        await eval_case("dataflow_runs_no_auth", [result], det, module="adp/dataflow",
                        eval_hints={
                            "focus": "cli_availability",
                            "description": "CLI command executes in no-auth mode. API may return 401.",
                            "latency_budget_ms": 5000,
                        })
        assert det.passed, det.failures
    else:
        # Authenticated mode: full validation
        scorer.assert_exit_code(result, 0)
        scorer.assert_json(result)
        # runs should return a list (may be empty if no runs exist)
        if isinstance(result.parsed_json, list):
            scorer.assert_true(True, label="dataflow runs returns array")
        else:
            scorer.assert_true(False, label="dataflow runs returns array")
        
        det = scorer.result(result.duration_ms)
        await eval_case("dataflow_runs", [result], det, module="adp/dataflow",
                        eval_hints={
                            "focus": "run_history_structure",
                            "description": "Run history should include instance IDs, timestamps, and status",
                            "latency_budget_ms": 5000,
                        })
        assert det.passed, det.failures


async def test_dataflow_logs(
    cli_agent: CliAgent, scorer: Scorer, eval_case, df_id: str,
):
    """dataflow logs returns recent execution log entries.
    
    In no-auth mode, this test validates CLI command availability.
    In authenticated mode, this test validates log output structure.
    """
    # First get runs to find an instance ID
    runs_result = await cli_agent.run_cli("dataflow", "runs", df_id)
    if runs_result.exit_code != 0:
        pytest.skip(f"Cannot get runs for dataflow {df_id}: {runs_result.stderr.strip()}")
    
    # Parse runs to get an instance ID
    if not isinstance(runs_result.parsed_json, list) or len(runs_result.parsed_json) == 0:
        pytest.skip(f"No runs found for dataflow {df_id}")
    
    instance_id = runs_result.parsed_json[0].get("id") or runs_result.parsed_json[0].get("instance_id")
    if not instance_id:
        pytest.skip("No valid instance ID found in runs")
    
    result = await cli_agent.run_cli("dataflow", "logs", df_id, str(instance_id))
    
    import os
    is_no_auth = os.environ.get("KWEAVER_TOKEN") == "__NO_AUTH__"
    
    if is_no_auth:
        # No-auth mode: just verify CLI executed
        scorer.assert_true(
            result.exit_code in [0, 1],
            "dataflow logs CLI executed (no-auth mode)"
        )
        det = scorer.result(result.duration_ms)
        await eval_case("dataflow_logs_no_auth", [result], det, module="adp/dataflow",
                        eval_hints={
                            "focus": "cli_availability",
                            "description": "CLI command executes in no-auth mode. API may return 401.",
                            "latency_budget_ms": 5000,
                        })
        assert det.passed, det.failures
    else:
        # Authenticated mode: full validation
        scorer.assert_exit_code(result, 0)
        # Logs may not be JSON, so just check exit code
        det = scorer.result(result.duration_ms)
        await eval_case("dataflow_logs", [result], det, module="adp/dataflow",
                        eval_hints={
                            "focus": "log_quality",
                            "description": "Logs should be structured with timestamps and levels (info/warn/error)",
                            "latency_budget_ms": 5000,
                        })
        assert det.passed, det.failures
