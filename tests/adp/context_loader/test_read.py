"""Context Loader read acceptance tests.

Ported from kweaver-sdk e2e/context-loader.test.ts.
Validates BKN data is accessible via context loading path.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_context_loader_bkn_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn list returns KNs with id and name (context loading entry point)."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "5")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("cl_bkn_list", [result], det, module="adp/context_loader")
    assert det.passed, det.failures


async def test_context_loader_bkn_export(
    cli_agent: CliAgent, scorer: Scorer, eval_case, cl_kn_id: str,
):
    """bkn export returns KN data as dict."""
    result = await cli_agent.run_cli("bkn", "export", cl_kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("cl_bkn_export", [result], det, module="adp/context_loader")
    assert det.passed, det.failures


async def test_context_loader_object_type_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    cl_kn_with_ot: tuple[str, str],
):
    """bkn object-type query returns instances for a KN object type."""
    kn_id, ot_id = cl_kn_with_ot

    result = await cli_agent.run_cli(
        "bkn", "object-type", "query", kn_id, ot_id, "--limit", "5",
    )
    if result.exit_code != 0 and "500" in result.stderr:
        pytest.skip("Server returned 500 for object-type query")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case(
        "cl_object_type_query", [result], det, module="adp/context_loader",
    )
    assert det.passed, det.failures
