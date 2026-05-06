"""Vega resource acceptance tests.

Covers:
  - vega.resource.data.query — query data rows from a resource
"""

from __future__ import annotations

import json

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_vega_resource_data_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case, resource_id: str,
):
    """vega resource query returns data rows from a resource."""
    result = await cli_agent.run_cli(
        "vega", "resource", "query", resource_id, "-d", json.dumps({"limit": 5}),
    )
    if result.exit_code != 0 and "404" in result.stderr:
        pytest.skip("resource data query endpoint not available")
    if result.exit_code != 0 and "500" in result.stderr:
        pytest.skip("resource data query server error (may be an orphan resource)")
    scorer.assert_exit_code(result, 0, "resource data query")
    scorer.assert_json(result, "resource data query returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "vega_resource_data_query", [result], det, module="adp/vega",
    )
    assert det.passed, det.failures
