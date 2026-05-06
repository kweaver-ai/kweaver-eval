"""BKN subgraph query acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer
from tests.adp.bkn.conftest import build_subgraph_body


async def test_bkn_subgraph_basic(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn subgraph returns graph data for a one-hop relation path."""
    kn_id, _ = kn_with_data

    body = await build_subgraph_body(cli_agent, kn_id, depth=1, limit=5)
    if body is None:
        pytest.skip("KN has no relation types — subgraph requires at least one")

    result = await cli_agent.run_cli("bkn", "subgraph", kn_id, body)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_subgraph_basic", [result], det, module="adp/bkn")
    assert det.passed, det.failures
