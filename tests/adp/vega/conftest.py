"""Vega module conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.vega]


@pytest.fixture(scope="session")
async def catalog_id(cli_agent: CliAgent) -> str:
    """Find the first available Vega catalog ID. Skips if none found."""
    result = await cli_agent.run_cli("vega", "catalog", "list")
    if result.exit_code != 0:
        pytest.skip("Cannot list Vega catalogs")
    catalogs = result.parsed_json
    if not isinstance(catalogs, list) or len(catalogs) == 0:
        if isinstance(catalogs, dict):
            catalogs = catalogs.get("items") or catalogs.get("entries") or []
        if not catalogs:
            pytest.skip("No Vega catalogs available")
    cat = catalogs[0] if isinstance(catalogs, list) else catalogs
    cat_id = str(cat.get("id") or cat.get("catalog_id") or "")
    if not cat_id:
        pytest.skip("Cannot determine catalog ID")
    return cat_id


@pytest.fixture(scope="session")
async def resource_id(cli_agent: CliAgent) -> str:
    """Find the first available Vega resource ID. Skips if none found."""
    result = await cli_agent.run_cli("vega", "resource", "list")
    if result.exit_code != 0:
        pytest.skip("Cannot list Vega resources")
    resources = result.parsed_json
    if not isinstance(resources, list) or len(resources) == 0:
        if isinstance(resources, dict):
            resources = resources.get("items") or resources.get("entries") or []
        if not resources:
            pytest.skip("No Vega resources available")
    res = resources[0] if isinstance(resources, list) else resources
    res_id = str(res.get("id") or res.get("resource_id") or "")
    if not res_id:
        pytest.skip("Cannot determine resource ID")
    return res_id
