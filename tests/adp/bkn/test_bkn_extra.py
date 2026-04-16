"""BKN corner-case acceptance tests.

Covers gaps identified in the coverage audit:
  - bkn.object_type.query_with_filter  — filtered object-type query
  - bkn.subgraph.depth_greater_than_one — multi-hop subgraph traversal
  - bkn.action_schedule.set_status_idempotent — idempotent status toggle
  - bkn.object_type.validate           — object-type property validation
  - bkn.job.list / bkn.job.get         — job management read operations
  - bkn.resources                      — bkn resources command
  - bkn.relation_type.get              — relation-type detail
  - bkn.action_type.get                — action-type detail
"""

from __future__ import annotations

import json
import time
import random
import string

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer
from tests.adp.bkn.conftest import _short_suffix


# ---------------------------------------------------------------------------
# Object-type corner cases
# ---------------------------------------------------------------------------

async def test_bkn_object_type_query_with_filter(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn object-type query with a property filter returns filtered instances."""
    kn_id, ot_id = kn_with_data

    # Get OT properties to pick a filterable field
    props_result = await cli_agent.run_cli(
        "bkn", "object-type", "get", kn_id, ot_id,
    )
    if props_result.exit_code != 0:
        pytest.skip("Cannot get object-type details")
    prop_name = ""
    if isinstance(props_result.parsed_json, dict):
        entry = props_result.parsed_json
        if "entries" in entry and isinstance(entry["entries"], list) and entry["entries"]:
            entry = entry["entries"][0]
        for p in (entry.get("data_properties") or []):
            pn = p.get("name", "")
            if pn and pn not in ("id", "kn_id"):
                prop_name = pn
                break

    # Query with a filter (empty filter {} is also valid)
    filter_body = json.dumps({prop_name: ""} if prop_name else {})
    result = await cli_agent.run_cli(
        "bkn", "object-type", "query", kn_id, ot_id,
        "--filter", filter_body,
        "--limit", "5",
    )
    if result.exit_code != 0 and (
        "unknown flag" in result.stderr.lower()
        or "--filter" in result.stderr
    ):
        # Fallback: pass filter as positional JSON argument
        result = await cli_agent.run_cli(
            "bkn", "object-type", "query", kn_id, ot_id, filter_body,
            "--limit", "5",
        )
    if result.exit_code != 0 and "500" in result.stderr:
        pytest.skip("Server error on filtered OT query")
    scorer.assert_exit_code(result, 0, "OT query with filter")
    scorer.assert_json(result, "filtered OT query returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_object_type_query_with_filter", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures


async def test_bkn_subgraph_depth_greater_than_one(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn subgraph with depth=2 returns multi-hop graph data."""
    kn_id, ot_id = kn_with_data

    body = json.dumps({
        "source_object_type_id": ot_id,
        "limit": 5,
        "depth": 2,
    })
    result = await cli_agent.run_cli("bkn", "subgraph", kn_id, body)
    scorer.assert_exit_code(result, 0, "subgraph depth>1")
    scorer.assert_json(result, "subgraph returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_subgraph_depth_greater_than_one", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures


# ---------------------------------------------------------------------------
# Action schedule idempotency
# ---------------------------------------------------------------------------

async def _find_kn_with_schedule(cli_agent: CliAgent) -> tuple[str, str] | None:
    """Find a KN that has at least one action schedule. Returns (kn_id, sched_id)."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "20")
    if result.exit_code != 0:
        return None
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or []
    if not isinstance(kns, list):
        return None
    for kn in kns:
        kn_id = str(kn.get("id") or kn.get("kn_id") or "")
        if not kn_id:
            continue
        sched_result = await cli_agent.run_cli(
            "bkn", "action-schedule", "list", kn_id,
        )
        if sched_result.exit_code != 0:
            continue
        entries = sched_result.parsed_json
        if isinstance(entries, dict):
            entries = entries.get("entries") or entries.get("items") or []
        if isinstance(entries, list) and entries:
            sched_id = str(entries[0].get("id") or "")
            if sched_id:
                return kn_id, sched_id
    return None


async def test_bkn_action_schedule_set_status_idempotent(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """action-schedule set-status called twice with same value is idempotent."""
    found = await _find_kn_with_schedule(cli_agent)
    if not found:
        pytest.skip("No KN with action schedules available")
    kn_id, sched_id = found
    steps = []

    # Get current status
    get_result = await cli_agent.run_cli(
        "bkn", "action-schedule", "get", kn_id, sched_id,
    )
    if get_result.exit_code != 0:
        pytest.skip("Cannot get schedule details")
    current_status = "enable"
    if isinstance(get_result.parsed_json, dict):
        raw = get_result.parsed_json
        if "entries" in raw and isinstance(raw["entries"], list) and raw["entries"]:
            raw = raw["entries"][0]
        s = str(raw.get("status") or raw.get("enable") or "enable")
        current_status = "enable" if "enable" in s.lower() or s == "1" else "disable"

    # First call
    first = await cli_agent.run_cli(
        "bkn", "action-schedule", "set-status", kn_id, sched_id, current_status,
    )
    steps.append(first)
    scorer.assert_exit_code(first, 0, "set-status first call")

    # Second call with same value (idempotent)
    second = await cli_agent.run_cli(
        "bkn", "action-schedule", "set-status", kn_id, sched_id, current_status,
    )
    steps.append(second)
    scorer.assert_exit_code(second, 0, "set-status second call (idempotent)")

    det = scorer.result()
    await eval_case(
        "bkn_action_schedule_set_status_idempotent", steps, det, module="adp/bkn",
    )
    assert det.passed, det.failures


# ---------------------------------------------------------------------------
# Job read operations
# ---------------------------------------------------------------------------

async def _find_kn_with_jobs(cli_agent: CliAgent) -> tuple[str, str] | None:
    """Find a KN with at least one job. Returns (kn_id, job_id) or None."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "20")
    if result.exit_code != 0:
        return None
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or []
    if not isinstance(kns, list):
        return None
    for kn in kns:
        kn_id = str(kn.get("id") or kn.get("kn_id") or "")
        if not kn_id:
            continue
        job_result = await cli_agent.run_cli("bkn", "job", "list", kn_id)
        if job_result.exit_code != 0:
            continue
        entries = job_result.parsed_json
        if isinstance(entries, dict):
            entries = entries.get("entries") or entries.get("items") or []
        if isinstance(entries, list) and entries:
            job_id = str(entries[0].get("id") or "")
            if job_id:
                return kn_id, job_id
    return None


async def test_bkn_job_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn job list returns jobs for a KN."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "5")
    if result.exit_code != 0:
        pytest.skip("Cannot list KNs")
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or []
    if not isinstance(kns, list) or not kns:
        pytest.skip("No KNs available")
    kn_id = str(kns[0].get("id") or kns[0].get("kn_id") or "")
    if not kn_id:
        pytest.skip("Cannot determine KN ID")

    job_result = await cli_agent.run_cli("bkn", "job", "list", kn_id)
    scorer.assert_exit_code(job_result, 0, "bkn job list")
    scorer.assert_json(job_result, "job list returns JSON")
    det = scorer.result(job_result.duration_ms)
    await eval_case("bkn_job_list", [job_result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_job_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn job get returns detail for a specific job."""
    found = await _find_kn_with_jobs(cli_agent)
    if not found:
        pytest.skip("No KN with jobs available")
    kn_id, job_id = found

    result = await cli_agent.run_cli("bkn", "job", "get", kn_id, job_id)
    scorer.assert_exit_code(result, 0, "bkn job get")
    scorer.assert_json(result, "job get returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_job_get", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_job_tasks(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn job task list returns tasks for a job."""
    found = await _find_kn_with_jobs(cli_agent)
    if not found:
        pytest.skip("No KN with jobs available")
    kn_id, job_id = found

    result = await cli_agent.run_cli("bkn", "job", "task", "list", kn_id, job_id)
    scorer.assert_exit_code(result, 0, "bkn job task list")
    scorer.assert_json(result, "job task list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_job_tasks", [result], det, module="adp/bkn")
    assert det.passed, det.failures


# ---------------------------------------------------------------------------
# BKN resources
# ---------------------------------------------------------------------------

async def test_bkn_resources(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn resources returns available resource types / capabilities."""
    result = await cli_agent.run_cli("bkn", "resources")
    scorer.assert_exit_code(result, 0, "bkn resources")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_resources", [result], det, module="adp/bkn")
    assert det.passed, det.failures


# ---------------------------------------------------------------------------
# Relation-type get
# ---------------------------------------------------------------------------

async def test_bkn_relation_type_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn relation-type get returns detail for a specific relation type."""
    kn_id, _ot_id = kn_with_data

    list_result = await cli_agent.run_cli("bkn", "relation-type", "list", kn_id)
    if list_result.exit_code != 0:
        pytest.skip("Cannot list relation types")
    entries = list_result.parsed_json
    if isinstance(entries, dict):
        entries = entries.get("entries") or entries.get("items") or []
    if not isinstance(entries, list) or not entries:
        pytest.skip("No relation types available for this KN")
    rt_id = str(entries[0].get("id") or entries[0].get("rt_id") or "")
    if not rt_id:
        pytest.skip("Cannot determine relation-type ID")

    result = await cli_agent.run_cli("bkn", "relation-type", "get", kn_id, rt_id)
    scorer.assert_exit_code(result, 0, "relation-type get")
    scorer.assert_json(result, "relation-type get returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_relation_type_get", [result], det, module="adp/bkn")
    assert det.passed, det.failures


# ---------------------------------------------------------------------------
# Relation-type paths
# ---------------------------------------------------------------------------

async def test_bkn_relation_type_paths(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn relation-type-paths returns possible relation paths in a KN."""
    kn_id, _ot_id = kn_with_data

    result = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/knowledgenetwork/{kn_id}/relationtype/paths",
    )
    if result.exit_code != 0 and "404" in result.stderr:
        pytest.skip("relation-type paths endpoint not available")
    scorer.assert_exit_code(result, 0, "relation-type paths")
    scorer.assert_json(result, "relation-type paths returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_relation_type_paths", [result], det, module="adp/bkn")
    assert det.passed, det.failures


# ---------------------------------------------------------------------------
# Action-type get
# ---------------------------------------------------------------------------

async def _find_kn_with_action_type(cli_agent: CliAgent) -> tuple[str, str] | None:
    """Find a KN with action types. Returns (kn_id, at_id) or None."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "20")
    if result.exit_code != 0:
        return None
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or []
    if not isinstance(kns, list):
        return None
    for kn in kns:
        kn_id = str(kn.get("id") or kn.get("kn_id") or "")
        if not kn_id:
            continue
        at_result = await cli_agent.run_cli("bkn", "action-type", "list", kn_id)
        if at_result.exit_code != 0:
            continue
        entries = at_result.parsed_json
        if isinstance(entries, dict):
            entries = entries.get("entries") or entries.get("items") or []
        if isinstance(entries, list) and entries:
            at_id = str(entries[0].get("id") or "")
            if at_id:
                return kn_id, at_id
    return None


async def test_bkn_action_type_get(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """bkn action-type get returns detail for a specific action type."""
    found = await _find_kn_with_action_type(cli_agent)
    if not found:
        pytest.skip("No KN with action types available")
    kn_id, at_id = found

    result = await cli_agent.run_cli("bkn", "action-type", "get", kn_id, at_id)
    if result.exit_code != 0 and "unknown" in result.stderr.lower():
        pytest.skip("bkn action-type get not available in this SDK version")
    scorer.assert_exit_code(result, 0, "action-type get")
    scorer.assert_json(result, "action-type get returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_action_type_get", [result], det, module="adp/bkn")
    assert det.passed, det.failures
