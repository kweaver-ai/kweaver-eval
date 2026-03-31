"""Vega connector-type acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_vega_connector_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega connector-type list returns supported connector types."""
    result = await cli_agent.run_cli("vega", "connector-type", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_connector_type_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


@pytest.mark.known_bug("https://github.com/kweaver-ai/adp/issues/427")
async def test_vega_connector_type_get(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega connector-type get returns details for a specific type.

    Known bug: GetConnectorType handler reads c.Param("id") but route
    defines :type — param name mismatch causes 404.
    """
    # First get list to find a type name
    list_result = await cli_agent.run_cli("vega", "connector-type", "list")
    if list_result.exit_code != 0 or not isinstance(list_result.parsed_json, list):
        pytest.skip("Cannot list connector types")
    if not list_result.parsed_json:
        pytest.skip("No connector types available")
    ct = list_result.parsed_json[0]
    ct_type = str(ct.get("type") or ct.get("name") or ct.get("id") or "")
    if not ct_type:
        pytest.skip("Cannot determine connector type identifier")

    result = await cli_agent.run_cli("vega", "connector-type", "get", ct_type)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_connector_type_get", [result], det, module="adp/vega")
    assert det.passed, det.failures
