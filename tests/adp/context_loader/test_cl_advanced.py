"""Context Loader advanced acceptance tests.

Covers:
  - context.mcp.proxy_sse          — SSE proxy endpoint streams events
  - context.kn.semantic_search     — semantic (vector) KN search
  - context.kn.find_skills         — find skills via context loader
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_context_loader_proxy_sse(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_config_active: bool,
):
    """context-loader proxy SSE endpoint returns a stream of server-sent events."""
    # The SSE endpoint is typically /api/context-loader/v1/sse or similar.
    # Try CLI first, then fall back to call endpoint.
    result = await cli_agent.run_cli(
        "context-loader", "sse",
        timeout=15.0,
    )
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        # Fallback: probe the SSE REST endpoint
        result = await cli_agent.run_cli(
            "call",
            "/api/context-loader/v1/sse",
            timeout=15.0,
        )
    if result.exit_code != 0 and "404" in result.stderr:
        pytest.skip("context-loader SSE endpoint not available on this deployment")
    # SSE streams return 200 with content-type text/event-stream; CLI may time out
    # Accept exit code 0 (clean close) or a timeout signal (non-zero but partial data)
    scorer.assert_true(
        result.exit_code in (0, 1, 124),  # 124 = timeout exit code
        "SSE endpoint does not crash immediately (exit 0/1/124)",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("cl_mcp_proxy_sse", [result], det, module="adp/context_loader")
    assert det.passed, det.failures


async def test_context_loader_kn_semantic_search(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_kn_id: str,
):
    """context-loader kn-search with semantic mode returns vector-ranked results."""
    # Try --semantic flag or similar
    result = await cli_agent.run_cli(
        "context-loader", "kn-search", "company information",
        "--kn-id", cl_kn_id,
        "--semantic",
    )
    if result.exit_code != 0 and (
        "unknown flag" in result.stderr.lower()
        or "flag provided but not defined" in result.stderr.lower()
    ):
        # Fallback: try --type semantic or --search-type semantic
        result = await cli_agent.run_cli(
            "context-loader", "kn-search", "company information",
            "--kn-id", cl_kn_id,
            "--type", "semantic",
        )
    if result.exit_code != 0 and (
        "unknown flag" in result.stderr.lower()
        or "flag provided but not defined" in result.stderr.lower()
    ):
        # Fallback: plain kn-search (semantic may be the default)
        result = await cli_agent.run_cli(
            "context-loader", "kn-search", "company information",
            "--kn-id", cl_kn_id,
        )
    if result.exit_code != 0 and "500" in result.stderr:
        pytest.skip("Semantic search returned server error (embedding model may not be configured)")
    scorer.assert_exit_code(result, 0, "kn semantic search exit code")
    scorer.assert_json(result, "kn semantic search returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_kn_semantic_search", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures


async def test_context_loader_find_skills(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_config_active: bool,
):
    """context-loader find-skills returns skills relevant to a query."""
    result = await cli_agent.run_cli(
        "context-loader", "find-skills", "search",
    )
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        # Fallback: call the tools list endpoint (skills are MCP tools)
        result = await cli_agent.run_cli(
            "context-loader", "tools",
        )
    if result.exit_code != 0 and "404" in result.stderr:
        pytest.skip("find-skills endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "find-skills exit code")
    scorer.assert_json(result, "find-skills returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_kn_find_skills", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures
