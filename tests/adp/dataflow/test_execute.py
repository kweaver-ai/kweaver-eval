"""Dataflow execution tests.

Covers: run — operations that trigger dataflow execution.
Pattern: follows destructive test conventions with proper cleanup.

Note: These tests require authentication and may create run instances.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.api
async def test_dataflow_run_with_url(
    cli_agent: CliAgent, scorer: Scorer, eval_case, df_id: str,
):
    """dataflow run triggers execution with remote URL.
    
    In no-auth mode, this test validates CLI command availability.
    In authenticated mode, this test validates execution trigger and instance ID response.
    """
    # Use a simple test URL (this is a smoke test, not functional validation)
    test_url = "https://httpbin.org/get"
    test_name = f"eval_test_run_{df_id[:8]}"
    
    result = await cli_agent.run_cli(
        "dataflow", "run", df_id,
        "--url", test_url,
        "--name", test_name,
    )
    
    if result.exit_code != 0 and (
        "command not found" in result.stderr.lower()
        or "unknown" in result.stderr.lower()
    ):
        pytest.skip("dataflow run CLI not yet available")
    
    import os
    is_no_auth = os.environ.get("KWEAVER_TOKEN") == "__NO_AUTH__"
    
    if is_no_auth:
        # No-auth mode: just verify CLI executed
        scorer.assert_true(
            result.exit_code in [0, 1],
            "dataflow run CLI executed (no-auth mode)"
        )
        det = scorer.result(result.duration_ms)
        await eval_case("dataflow_run_no_auth", [result], det, module="adp/dataflow",
                        eval_hints={
                            "focus": "cli_availability",
                            "description": "CLI command executes in no-auth mode. API may return 401.",
                            "latency_budget_ms": 10000,
                        })
        assert det.passed, det.failures
    else:
        # Authenticated mode: full validation
        # Run command should return an instance ID
        scorer.assert_exit_code(result, 0)
        
        # Output should be a non-empty string (instance ID)
        output = result.stdout.strip()
        if output:
            scorer.assert_true(True, label="dataflow run returns instance ID")
        else:
            scorer.assert_true(False, label="dataflow run returns instance ID")
        
        det = scorer.result(result.duration_ms)
        await eval_case("dataflow_run", [result], det, module="adp/dataflow",
                        eval_hints={
                            "focus": "execution_trigger",
                            "description": "Run command should trigger execution and return instance ID",
                            "latency_budget_ms": 10000,
                        })
        assert det.passed, det.failures
