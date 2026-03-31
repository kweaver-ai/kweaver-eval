"""BKN module conftest — fixtures for knowledge network tests.

db_credentials fixture is inherited from tests/adp/conftest.py.
"""

from __future__ import annotations

import time

import pytest

from lib.agents.cli_agent import CliAgent


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
    """Find a KN that has object types. Returns (kn_id, ot_id) or None."""
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
            if ot_id:
                return kn_id, ot_id
    return None


async def _create_kn_from_db(cli_agent: CliAgent, creds: dict) -> tuple[str, str] | None:
    """Create a datasource + KN from DB credentials. Returns (ds_id, kn_id) or None on failure."""
    ds_name = f"eval_fixture_{int(time.time())}"
    kn_name = f"eval_kn_{int(time.time())}"

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
    # Cleanup
    await cli_agent.run_cli("bkn", "delete", kn_id, "-y")
    await cli_agent.run_cli("ds", "delete", ds_id, "-y")


@pytest.fixture(scope="session")
async def kn_with_data(cli_agent: CliAgent, db_credentials: dict):
    """Ensure a KN with object types exists. Returns (kn_id, ot_name)."""
    # Fast path: find existing KN with data
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
            await cli_agent.run_cli("bkn", "delete", kn_id, "-y")
            await cli_agent.run_cli("ds", "delete", ds_id, "-y")
            return

    # Still no OT — skip (build required but too slow for fixture)
    await cli_agent.run_cli("bkn", "delete", kn_id, "-y")
    await cli_agent.run_cli("ds", "delete", ds_id, "-y")
    pytest.skip("No KN with object types available (build required)")
