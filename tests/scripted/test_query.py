"""Query acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.recorder import Recorder
from lib.scorer import Scorer
from lib.types import CaseResult


async def _find_kn_with_data(cli_agent: CliAgent) -> tuple[str, str] | None:
    """Find a KN that has object types with data. Returns (kn_id, ot_name) or None."""
    list_result = await cli_agent.run_cli("bkn", "list", "--json")
    if list_result.exit_code != 0 or not isinstance(list_result.parsed_json, list):
        return None
    for kn in list_result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if not kn_id:
            continue
        ot_result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id, "--json")
        is_list = isinstance(ot_result.parsed_json, list)
        if ot_result.exit_code == 0 and is_list and ot_result.parsed_json:
            ot = ot_result.parsed_json[0]
            ot_name = str(ot.get("name") or ot.get("ot_name") or "")
            if ot_name:
                return kn_id, ot_name
    return None


async def test_bkn_object_type_query(cli_agent: CliAgent, scorer: Scorer, recorder: Recorder):
    """bkn object-type query returns instances for an object type."""
    found = await _find_kn_with_data(cli_agent)
    if not found:
        pytest.skip("No KN with object types available")
    kn_id, ot_name = found

    result = await cli_agent.run_cli("bkn", "object-type", "query", kn_id, ot_name, "--json")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)

    det = scorer.result(result.duration_ms)
    recorder.record_case(CaseResult(
        name="test_bkn_object_type_query",
        status="pass" if det.passed else "fail",
        deterministic=det,
        steps=[result],
    ))
    assert det.passed, det.failures
