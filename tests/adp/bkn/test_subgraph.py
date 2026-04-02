"""BKN subgraph query acceptance tests."""

from __future__ import annotations

import json

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_bkn_subgraph_basic(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn subgraph returns graph data for a query with source OT."""
    kn_id, ot_id = kn_with_data

    body = json.dumps({"source_object_type_id": ot_id, "limit": 5})
    result = await cli_agent.run_cli("bkn", "subgraph", kn_id, body)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_subgraph_basic", [result], det, module="adp/bkn")
    assert det.passed, det.failures
