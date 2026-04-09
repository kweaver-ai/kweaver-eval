"""BKN object-type update acceptance tests (destructive).

Ported from kweaver-sdk e2e/object-type-update.test.ts.
Tests add/update/remove data property cycle on an existing object type.
"""

from __future__ import annotations

import json
import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_object_type_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn object-type get succeeds for an available object type."""
    kn_id, ot_id = kn_with_data

    result = await cli_agent.run_cli("bkn", "object-type", "get", kn_id, ot_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_object_type_get", [result], det, module="adp/bkn")
    assert det.passed, det.failures


@pytest.mark.known_bug("bkn-backend UpdateObjectType missing Branch assignment — adp#445 fixed relation-type but object-type handler has identical unfiled bug")
@pytest.mark.destructive
async def test_object_type_update_property_cycle(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """Object-type update: add -> update -> remove a temp property."""
    kn_id, ot_id = kn_with_data

    suffix = f"{int(time.time())}_{id(object()) % 10000}"
    prop_name = f"eval_tmp_{suffix}"
    steps = []

    # Step 1: add property
    add_json = json.dumps({
        "name": prop_name,
        "display_name": "Eval Temp",
        "type": "string",
        "comment": "kweaver-eval e2e",
        "mapped_field": {
            "name": prop_name,
            "type": "string",
            "display_name": "Eval Temp",
        },
    })
    add = await cli_agent.run_cli(
        "bkn", "object-type", "update", kn_id, ot_id,
        "--add-property", add_json,
    )
    steps.append(add)
    scorer.assert_exit_code(add, 0, "add-property")

    # Step 2: update property
    update_json = json.dumps({
        "name": prop_name,
        "display_name": "Eval Temp Updated",
        "type": "string",
        "comment": "kweaver-eval e2e updated",
        "mapped_field": {
            "name": prop_name,
            "type": "string",
            "display_name": "Eval Temp Updated",
        },
    })
    update = await cli_agent.run_cli(
        "bkn", "object-type", "update", kn_id, ot_id,
        "--update-property", update_json,
    )
    steps.append(update)
    scorer.assert_exit_code(update, 0, "update-property")

    # Step 3: verify update
    get = await cli_agent.run_cli("bkn", "object-type", "get", kn_id, ot_id)
    steps.append(get)
    scorer.assert_exit_code(get, 0, "get after update")
    if isinstance(get.parsed_json, dict):
        entry = get.parsed_json
        if "entries" in entry and isinstance(entry["entries"], list):
            entry = entry["entries"][0] if entry["entries"] else {}
        props = entry.get("data_properties") or []
        found_prop = next(
            (p for p in props if p.get("name") == prop_name), None,
        )
        scorer.assert_true(found_prop is not None, "temp property exists")
        if found_prop:
            scorer.assert_true(
                "Updated" in (found_prop.get("display_name") or ""),
                "property display_name was updated",
            )

    # Step 4: remove property
    remove = await cli_agent.run_cli(
        "bkn", "object-type", "update", kn_id, ot_id,
        "--remove-property", prop_name,
    )
    steps.append(remove)
    scorer.assert_exit_code(remove, 0, "remove-property")

    # Step 5: verify removal
    final = await cli_agent.run_cli(
        "bkn", "object-type", "get", kn_id, ot_id,
    )
    steps.append(final)
    scorer.assert_exit_code(final, 0, "get after remove")
    if isinstance(final.parsed_json, dict):
        entry = final.parsed_json
        if "entries" in entry and isinstance(entry["entries"], list):
            entry = entry["entries"][0] if entry["entries"] else {}
        props = entry.get("data_properties") or []
        still_there = any(p.get("name") == prop_name for p in props)
        scorer.assert_true(not still_there, "temp property removed")

    det = scorer.result()
    await eval_case(
        "bkn_object_type_update_cycle", steps, det, module="adp/bkn",
    )
    assert det.passed, det.failures
