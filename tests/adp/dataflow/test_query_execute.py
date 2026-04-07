"""Dataflow query and execution acceptance tests.

Covers: run, dry-run, preview, node execution — operations that exercise
the data pipeline without full lifecycle (create/delete).
Pattern: follows vega/test_query.py conventions.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_dataflow_dry_run(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    df_with_source: dict,
):
    """dataflow run --dry-run validates execution plan without running."""
    df_id = df_with_source["id"]
    result = await cli_agent.run_cli(
        "dataflow", "run", df_id,
        "--dry-run",
    )
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_dry_run", [result], det, module="adp/dataflow",
                    eval_hints={
                        "focus": "plan_validity",
                        "description": "Dry-run should return execution plan with estimated costs and node order",
                    })
    assert det.passed, det.failures


async def test_dataflow_preview_source(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    df_with_source: dict,
):
    """dataflow preview shows source data sample without full execution."""
    df_id = df_with_source["id"]
    result = await cli_agent.run_cli(
        "dataflow", "preview", df_id,
        "--node", "source",
        "--limit", "5",
    )
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_preview_source", [result], det, module="adp/dataflow",
                    eval_hints={
                        "focus": "data_quality",
                        "description": "Preview should return actual data rows with correct schema from source",
                        "latency_budget_ms": 10000,
                    })
    assert det.passed, det.failures


async def test_dataflow_execute_single_node(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    df_with_source: dict,
):
    """dataflow execute --node runs a single pipeline node in isolation."""
    df_id = df_with_source["id"]
    result = await cli_agent.run_cli(
        "dataflow", "run", df_id,
        "--node", "source",
        timeout=60.0,
    )
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_execute_node", [result], det, module="adp/dataflow",
                    eval_hints={
                        "focus": "node_execution",
                        "description": "Single-node execution should complete with output row count and schema",
                        "latency_budget_ms": 60000,
                    })
    assert det.passed, det.failures


async def test_dataflow_history(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    df_id: str,
):
    """dataflow history lists past executions for a dataflow."""
    result = await cli_agent.run_cli(
        "dataflow", "history", df_id,
        "--limit", "10",
    )
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_history", [result], det, module="adp/dataflow")
    assert det.passed, det.failures


async def test_dataflow_schema_inference(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    df_with_source: dict,
):
    """dataflow schema infers output schema from source + transformations."""
    df_id = df_with_source["id"]
    result = await cli_agent.run_cli(
        "dataflow", "schema", df_id,
    )
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_field(
        result, "fields",
        label="schema contains fields array",
    )
    if isinstance(result.parsed_json, dict):
        fields = result.parsed_json.get("fields")
        if isinstance(fields, list) and fields:
            scorer.assert_true(
                all(f.get("name") for f in fields),
                "each field has a name",
            )
    det = scorer.result(result.duration_ms)
    await eval_case("dataflow_schema_inference", [result], det, module="adp/dataflow",
                    eval_hints={
                        "focus": "schema_accuracy",
                        "description": "Inferred schema should match source types after transformation rules applied",
                    })
    assert det.passed, det.failures
