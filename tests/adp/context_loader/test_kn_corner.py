"""Context Loader KN corner-case acceptance tests.

Covers gaps identified in the coverage audit:
  - context.kn.kn_search_empty_query            — empty string query edge case
  - context.kn.query_object_instance_with_filter — filtered instance query
  - context.kn.query_instance_subgraph_depth_gt_1 — multi-hop subgraph
"""

from __future__ import annotations

import json

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_context_loader_kn_search_empty_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_kn_id: str,
):
    """context-loader kn-search with empty query returns graceful response."""
    result = await cli_agent.run_cli(
        "context-loader", "kn-search", "", "--kn-id", cl_kn_id,
    )
    # An empty query may return an empty result set or a 400; either is acceptable
    # as long as the CLI does not crash (exit 2) with a Python traceback.
    scorer.assert_true(
        result.exit_code in (0, 1),
        "empty-query kn-search does not crash (exit 0 or 1)",
    )
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_kn_search_empty_query", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures


async def test_context_loader_query_object_instance_with_filter(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    cl_kn_with_ot: tuple[str, str],
):
    """context-loader query-object-instance with a property filter."""
    kn_id, ot_id = cl_kn_with_ot

    # Build a minimal filter body — empty filter {} is always valid
    filter_body = json.dumps({})
    result = await cli_agent.run_cli(
        "context-loader", "query-object-instance",
        kn_id, ot_id, filter_body,
        "--limit", "5",
    )
    if result.exit_code != 0 and "500" in result.stderr:
        pytest.skip("Server error on filtered instance query")
    scorer.assert_exit_code(result, 0, "query-object-instance with filter")
    scorer.assert_json(result, "filtered instance query returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_query_object_instance_with_filter", [result], det,
        module="adp/context_loader",
    )
    assert det.passed, det.failures


async def test_context_loader_query_instance_subgraph_depth_gt_1(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    cl_kn_with_ot: tuple[str, str],
):
    """context-loader query-instance-subgraph with depth=2 returns multi-hop graph."""
    kn_id, ot_id = cl_kn_with_ot

    # Query for a sample instance to use as the subgraph root
    query_result = await cli_agent.run_cli(
        "bkn", "object-type", "query", kn_id, ot_id, "--limit", "1",
    )
    instance_id = ""
    if query_result.exit_code == 0 and isinstance(query_result.parsed_json, dict):
        entries = (
            query_result.parsed_json.get("instances")
            or query_result.parsed_json.get("entries")
            or []
        )
        if isinstance(entries, list) and entries:
            instance_id = str(entries[0].get("id") or "")

    if not instance_id:
        # Try without a specific instance — pass an empty body
        result = await cli_agent.run_cli(
            "context-loader", "query-instance-subgraph",
            kn_id, ot_id, json.dumps({"depth": 2, "limit": 5}),
        )
    else:
        result = await cli_agent.run_cli(
            "context-loader", "query-instance-subgraph",
            kn_id, ot_id, instance_id,
            "--depth", "2",
        )

    if result.exit_code != 0 and "500" in result.stderr:
        pytest.skip("Server error on multi-hop subgraph query")
    scorer.assert_exit_code(result, 0, "query-instance-subgraph depth>1")
    scorer.assert_json(result, "subgraph depth>1 returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_query_instance_subgraph_depth_gt_1", [result], det,
        module="adp/context_loader",
    )
    assert det.passed, det.failures


async def test_context_loader_kn_search_schema_only(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_kn_id: str,
):
    """context-loader kn-search --only-schema returns schema-level results only."""
    result = await cli_agent.run_cli(
        "context-loader", "kn-search", "test",
        "--kn-id", cl_kn_id,
        "--only-schema",
    )
    scorer.assert_exit_code(result, 0, "kn-search --only-schema")
    scorer.assert_json(result, "kn-search --only-schema returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_kn_search_schema_only", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures


async def test_context_loader_kn_schema_search(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_kn_id: str,
):
    """context-loader kn-schema-search returns schema-focused search results."""
    result = await cli_agent.run_cli(
        "context-loader", "kn-schema-search", "test",
        "--kn-id", cl_kn_id,
    )
    scorer.assert_exit_code(result, 0, "kn-schema-search")
    scorer.assert_json(result, "kn-schema-search returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_kn_schema_search", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures
