"""Context Loader MCP endpoint acceptance tests.

Covers:
  - context.mcp.tools       — list available MCP tools
  - context.config.list      — list context-loader configurations
  - context.config.show      — show active context-loader config

Removed (server-side not supported):
  - resources, templates, prompts, resource_read, prompt_get
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_context_loader_tools(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_config_active: bool,
):
    """context-loader tools returns list of available MCP tools."""
    result = await cli_agent.run_cli("context-loader", "tools")
    scorer.assert_exit_code(result, 0, "context-loader tools")
    scorer.assert_json(result, "tools returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_mcp_tools", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures


async def test_context_loader_config_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """context-loader config list returns configuration entries."""
    result = await cli_agent.run_cli("context-loader", "config", "list")
    scorer.assert_exit_code(result, 0, "context-loader config list")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_config_list", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures


async def test_context_loader_config_show(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_config_active: bool,
):
    """context-loader config show returns active config details."""
    result = await cli_agent.run_cli("context-loader", "config", "show")
    scorer.assert_exit_code(result, 0, "context-loader config show")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_config_show", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures
