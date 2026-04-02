"""BKN module conftest — fixtures for knowledge network tests.

db_credentials fixture is inherited from tests/adp/conftest.py.
"""

from __future__ import annotations

import random
import string
import time

import pytest

from lib.agents.cli_agent import CliAgent

EVAL_PREFIX = "eval_"


def _short_suffix() -> str:
    """Return a short random suffix like 'a3x' to avoid name collisions."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=4))


# ---------------------------------------------------------------------------
# Resource cleanup helpers
# ---------------------------------------------------------------------------

async def _list_eval_kns(cli_agent: CliAgent) -> list[str]:
    """Return IDs of KNs whose name starts with EVAL_PREFIX."""
    result = await cli_agent.run_cli("bkn", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return []
    return [
        str(kn.get("id") or kn.get("kn_id") or "")
        for kn in result.parsed_json
        if str(kn.get("name", "")).startswith(EVAL_PREFIX)
    ]


async def _list_eval_ds(cli_agent: CliAgent) -> list[str]:
    """Return IDs of datasources whose name starts with EVAL_PREFIX."""
    result = await cli_agent.run_cli("ds", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return []
    return [
        str(ds.get("id") or ds.get("datasource_id") or "")
        for ds in result.parsed_json
        if str(ds.get("name", "")).startswith(EVAL_PREFIX)
    ]


async def _cleanup_eval_resources(cli_agent: CliAgent) -> None:
    """Delete all eval_ prefixed KNs and DSs. Order: KN first, then DS."""
    for kn_id in await _list_eval_kns(cli_agent):
        if kn_id:
            await cli_agent.run_cli("bkn", "delete", kn_id, "-y")

    for ds_id in await _list_eval_ds(cli_agent):
        if ds_id:
            await cli_agent.run_cli("ds", "delete", ds_id, "-y")


# ---------------------------------------------------------------------------
# Session-level cleanup fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
async def cleanup_eval_resources(cli_agent: CliAgent):
    """Clean up residual eval_ resources before and after the test session."""
    # Before: clean residuals from previous interrupted runs
    await _cleanup_eval_resources(cli_agent)
    yield
    # After: clean anything this session created
    await _cleanup_eval_resources(cli_agent)


# ---------------------------------------------------------------------------
# KN discovery / creation helpers
# ---------------------------------------------------------------------------

async def _find_existing_kn(cli_agent: CliAgent) -> str | None:
    """Find an existing KN ID from bkn list."""
    result = await cli_agent.run_cli("bkn", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return None
    for kn in result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if kn_id:
            return kn_id
    return None


async def _find_kn_with_object_types(cli_agent: CliAgent) -> tuple[str, str] | None:
    """Find a KN with queryable object types. Returns (kn_id, ot_id) or None.

    Verifies that the OT can actually be queried (not just that it exists),
    since orphan KNs with deleted datasources will have OTs but fail on query.
    """
    result = await cli_agent.run_cli("bkn", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return None
    for kn in result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if not kn_id:
            continue
        ot_result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
        ot_entries = ot_result.parsed_json
        if isinstance(ot_entries, dict):
            ot_entries = ot_entries.get("entries", [])
        if (
            ot_result.exit_code == 0
            and isinstance(ot_entries, list)
            and ot_entries
        ):
            ot = ot_entries[0]
            ot_id = str(ot.get("id") or ot.get("ot_id") or "")
            if not ot_id:
                continue
            # Verify query actually works (catch orphan KNs)
            probe = await cli_agent.run_cli(
                "bkn", "object-type", "query", kn_id, ot_id, "--limit", "1",
            )
            if probe.exit_code == 0:
                return kn_id, ot_id
    return None


async def _find_kn_with_rich_data(
    cli_agent: CliAgent,
) -> tuple[str, str, list[dict]] | None:
    """Find a KN with >=2 OTs that have common properties and queryable data.

    Returns (kn_id, first_ot_id, ot_entries) or None.
    This ensures downstream tests (relation-type update, object-type properties)
    have the data they need.
    """
    result = await cli_agent.run_cli("bkn", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return None

    for kn in result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if not kn_id:
            continue
        ot_result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
        ot_entries = ot_result.parsed_json
        if isinstance(ot_entries, dict):
            ot_entries = ot_entries.get("entries", [])
        if ot_result.exit_code != 0 or not isinstance(ot_entries, list) or len(ot_entries) < 2:
            continue

        # Check first OT is queryable
        first_ot_id = str(ot_entries[0].get("id") or ot_entries[0].get("ot_id") or "")
        if not first_ot_id:
            continue
        probe = await cli_agent.run_cli(
            "bkn", "object-type", "query", kn_id, first_ot_id, "--limit", "1",
        )
        if probe.exit_code != 0:
            continue

        # Check that at least 2 OTs share a common property (for RT tests)
        second_ot_id = str(ot_entries[1].get("id") or ot_entries[1].get("ot_id") or "")
        if not second_ot_id:
            continue
        src_get = await cli_agent.run_cli("bkn", "object-type", "get", kn_id, first_ot_id)
        tgt_get = await cli_agent.run_cli("bkn", "object-type", "get", kn_id, second_ot_id)
        src_props: set[str] = set()
        tgt_props: set[str] = set()
        for get_r, prop_set in [(src_get, src_props), (tgt_get, tgt_props)]:
            if isinstance(get_r.parsed_json, dict):
                entry = get_r.parsed_json
                if "entries" in entry:
                    entry = (entry["entries"] or [{}])[0]
                for p in entry.get("data_properties") or []:
                    prop_set.add(p.get("name", ""))
        common = src_props & tgt_props - {""}
        if common:
            return kn_id, first_ot_id, ot_entries

    return None


async def _create_kn_from_db(cli_agent: CliAgent, creds: dict) -> tuple[str, str] | None:
    """Create a datasource + KN from DB credentials. Returns (ds_id, kn_id) or None on failure."""
    ds_name = f"{EVAL_PREFIX}fixture_{int(time.time())}_{_short_suffix()}"
    kn_name = f"{EVAL_PREFIX}kn_{int(time.time())}_{_short_suffix()}"

    # Step 1: ds connect
    connect = await cli_agent.run_cli(
        "ds", "connect", creds["db_type"], creds["host"], creds["port"], creds["database"],
        "--account", creds["user"], "--password", creds["password"], "--name", ds_name,
    )
    if connect.exit_code != 0:
        return None
    ds_id = ""
    if isinstance(connect.parsed_json, list) and connect.parsed_json:
        ds_id = str(connect.parsed_json[0].get("datasource_id") or connect.parsed_json[0].get("id") or "")
    elif isinstance(connect.parsed_json, dict):
        ds_id = str(connect.parsed_json.get("datasource_id") or connect.parsed_json.get("id") or "")
    if not ds_id:
        return None

    # Step 2: bkn create-from-ds
    create = await cli_agent.run_cli(
        "bkn", "create-from-ds", ds_id, "--name", kn_name, "--no-build",
    )
    if create.exit_code != 0:
        await cli_agent.run_cli("ds", "delete", ds_id, "-y")
        return None
    kn_id = ""
    if isinstance(create.parsed_json, dict):
        kn_id = str(create.parsed_json.get("kn_id") or create.parsed_json.get("id") or "")
    if not kn_id:
        await cli_agent.run_cli("ds", "delete", ds_id, "-y")
        return None

    return ds_id, kn_id


# ---------------------------------------------------------------------------
# Session-scoped KN fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
async def kn_id(cli_agent: CliAgent, db_credentials: dict):
    """Ensure a KN exists. Fast path: use existing. Slow path: create from DB."""
    # Fast path: find existing KN
    existing = await _find_existing_kn(cli_agent)
    if existing:
        yield existing
        return

    # Slow path: create from DB
    result = await _create_kn_from_db(cli_agent, db_credentials)
    if not result:
        pytest.skip("Cannot create KN (ds connect failed)")
    ds_id, kn_id = result
    yield kn_id
    # Cleanup handled by cleanup_eval_resources fixture


@pytest.fixture(scope="session")
async def kn_with_data(cli_agent: CliAgent, db_credentials: dict):
    """Ensure a KN with rich data exists. Returns (kn_id, ot_id).

    Prefers KNs with >=2 OTs sharing common properties, so downstream tests
    (relation-type update, object-type properties) can run without skipping.
    """
    # Fast path: find existing KN with rich data
    rich = await _find_kn_with_rich_data(cli_agent)
    if rich:
        kn_id, ot_id, _ = rich
        yield kn_id, ot_id
        return

    # Fallback: find any KN with at least one queryable OT
    found = await _find_kn_with_object_types(cli_agent)
    if found:
        yield found
        return

    # Slow path: create from DB (newly created KN won't have OT data without build)
    result = await _create_kn_from_db(cli_agent, db_credentials)
    if not result:
        pytest.skip("Cannot create KN (ds connect failed)")
    ds_id, kn_id = result

    # Check if the new KN has object types (create-from-ds may auto-discover schema)
    ot_result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
    entries = ot_result.parsed_json
    if isinstance(entries, dict):
        entries = entries.get("entries", [])
    if ot_result.exit_code == 0 and isinstance(entries, list) and entries:
        ot = entries[0]
        ot_id = str(ot.get("id") or ot.get("ot_id") or "")
        if ot_id:
            yield kn_id, ot_id
            return

    # Still no OT — skip (build required but too slow for fixture)
    pytest.skip("No KN with object types available (build required)")
