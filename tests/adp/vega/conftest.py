"""Vega module conftest.

db_credentials fixture is inherited from tests/adp/conftest.py.
"""

from __future__ import annotations

import json

import pytest

from lib.agents.cli_agent import CliAgent


@pytest.fixture(scope="session")
async def catalog_id(cli_agent: CliAgent) -> str:
    """Find a reachable Vega catalog ID. Probes each catalog to skip orphans
    whose underlying connector has been deleted."""
    result = await cli_agent.run_cli("vega", "catalog", "list", "--limit", "20")
    if result.exit_code != 0:
        pytest.skip("Cannot list Vega catalogs")
    catalogs = result.parsed_json
    if isinstance(catalogs, dict):
        catalogs = catalogs.get("items") or catalogs.get("entries") or []
    if not isinstance(catalogs, list) or len(catalogs) == 0:
        pytest.skip("No Vega catalogs available")
    for cat in catalogs:
        cat_id = str(cat.get("id") or cat.get("catalog_id") or "")
        if not cat_id:
            continue
        probe = await cli_agent.run_cli("vega", "catalog", "get", cat_id)
        if probe.exit_code == 0:
            return cat_id
    pytest.skip("No reachable Vega catalog found (all may be orphans)")


@pytest.fixture(scope="session")
async def resource_id(cli_agent: CliAgent) -> str:
    """Find a reachable Vega resource ID. Probes each resource to skip orphans
    whose underlying catalog or connector has been deleted."""
    result = await cli_agent.run_cli("vega", "resource", "list", "--limit", "20")
    if result.exit_code != 0:
        pytest.skip("Cannot list Vega resources")
    resources = result.parsed_json
    if isinstance(resources, dict):
        resources = resources.get("items") or resources.get("entries") or []
    if not isinstance(resources, list) or len(resources) == 0:
        pytest.skip("No Vega resources available")
    for res in resources:
        res_id = str(res.get("id") or res.get("resource_id") or "")
        if not res_id:
            continue
        probe = await cli_agent.run_cli("vega", "resource", "get", res_id)
        if probe.exit_code == 0:
            return res_id
    pytest.skip("No reachable Vega resource found (all may be orphans)")


@pytest.fixture(scope="session")
async def ds_id(cli_agent: CliAgent) -> str:
    """Find a reachable datasource ID. Probes each datasource to skip orphans
    that have been deleted or are otherwise unreachable."""
    result = await cli_agent.run_cli("ds", "list", "--limit", "20")
    if result.exit_code != 0:
        pytest.skip("Cannot list datasources")
    parsed = result.parsed_json
    if isinstance(parsed, dict):
        entries = parsed.get("entries") or parsed.get("items") or []
    elif isinstance(parsed, list):
        entries = parsed
    else:
        entries = []
    if not isinstance(entries, list) or len(entries) == 0:
        pytest.skip("No datasources available")
    for ds in entries:
        did = str(ds.get("id") or ds.get("ds_id") or ds.get("datasource_id") or "")
        if not did:
            continue
        probe = await cli_agent.run_cli("ds", "get", did)
        if probe.exit_code == 0:
            return did
    pytest.skip("No reachable datasource found (all may be orphans)")


@pytest.fixture(scope="session")
async def dataview_id(cli_agent: CliAgent) -> str:
    """Find a queryable dataview ID. Probes query to skip orphan dataviews
    whose underlying datasource has been deleted."""
    result = await cli_agent.run_cli("dataview", "list", "--limit", "20")
    if result.exit_code != 0:
        pytest.skip("Cannot list dataviews")
    parsed = result.parsed_json
    entries = parsed if isinstance(parsed, list) else (parsed or {}).get("entries") or []
    if not isinstance(entries, list) or len(entries) == 0:
        pytest.skip("No dataviews available")
    for dv in entries:
        dvid = str(dv.get("id") or "")
        if not dvid:
            continue
        probe = await cli_agent.run_cli("dataview", "query", dvid, "--limit", "1")
        if probe.exit_code == 0:
            return dvid
    pytest.skip("No queryable dataview found (all may be orphans)")


@pytest.fixture(scope="session")
def vega_connector_config(db_credentials: dict) -> str:
    """Build connector_config JSON string for vega catalog create.

    Uses shared db_credentials from adp conftest, with vega-specific
    field mapping (username, databases array).
    """
    cfg = {
        "host": db_credentials["host"],
        "port": int(db_credentials["port"]),
        "username": db_credentials["user"],
        "password": db_credentials["password"],
        "databases": [db_credentials["database"]],
    }
    return json.dumps(cfg)
