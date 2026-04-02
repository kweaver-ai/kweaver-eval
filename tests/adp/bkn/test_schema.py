"""BKN schema (object-type, relation-type, action-type) acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_bkn_object_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn object-type list returns object types for a KN."""
    result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    # CLI may return list or {entries: list}
    data = result.parsed_json
    if isinstance(data, dict):
        data = data.get("entries", data)
    scorer.assert_true(isinstance(data, list), "object-type list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_object_type_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_relation_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn relation-type list returns relation types for a KN."""
    result = await cli_agent.run_cli("bkn", "relation-type", "list", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_relation_type_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_object_type_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case, kn_with_data: tuple[str, str]
):
    """bkn object-type query returns instances for an object type."""
    kn_id, ot_id = kn_with_data
    result = await cli_agent.run_cli("bkn", "object-type", "query", kn_id, ot_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_object_type_query", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_object_type_properties(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn object-type properties queries instance properties by primary key."""
    kn_id, ot_id = kn_with_data

    # First query an instance to get its primary key value
    query_result = await cli_agent.run_cli(
        "bkn", "object-type", "query", kn_id, ot_id, "--limit", "1",
    )
    if query_result.exit_code != 0 or not isinstance(query_result.parsed_json, dict):
        pytest.skip("Cannot query instances to find primary key")
    entries = query_result.parsed_json.get("datas") or query_result.parsed_json.get("data") or []
    if isinstance(query_result.parsed_json, list):
        entries = query_result.parsed_json
    if not entries:
        pytest.skip("No instances available for properties query")
    instance = entries[0] if isinstance(entries, list) else entries

    # Get OT schema to find primary key(s)
    ot_get = await cli_agent.run_cli("bkn", "object-type", "get", kn_id, ot_id)
    if ot_get.exit_code != 0 or not isinstance(ot_get.parsed_json, dict):
        pytest.skip("Cannot get object type schema")
    ot_data = ot_get.parsed_json
    if "entries" in ot_data and isinstance(ot_data["entries"], list):
        ot_data = ot_data["entries"][0] if ot_data["entries"] else {}

    # Prefer _instance_identity from query result (contains full composite key)
    identity = instance.get("_instance_identity")
    if not identity:
        # Fallback: build from primary_keys (plural) or display_key
        pk_names = ot_data.get("primary_keys") or []
        if not pk_names:
            pk_name = ot_data.get("display_key") or ot_data.get("primary_key") or ""
            pk_names = [pk_name] if pk_name else []
        if not pk_names:
            pk_names = [next(iter(instance.keys()), "")]
        identity = {k: instance[k] for k in pk_names if k in instance}
    if not identity:
        pytest.skip("Cannot determine primary key for properties query")

    import json
    # Pick only regular data properties (exclude internal _ fields)
    data_props = [k for k in instance.keys() if not k.startswith("_")][:3]
    if not data_props:
        data_props = list(instance.keys())[:3]
    props_body = json.dumps({
        "_instance_identities": [identity],
        "properties": data_props,
    }, ensure_ascii=False)
    result = await cli_agent.run_cli(
        "bkn", "object-type", "properties", kn_id, ot_id, props_body,
    )
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_object_type_properties", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures
