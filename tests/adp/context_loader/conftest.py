"""Context Loader module conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent


@pytest.fixture(scope="session", autouse=True)
async def cl_config_active(cli_agent: CliAgent, cl_kn_id: str) -> bool:
    """Ensure context-loader has an active config. Auto-configures if needed."""
    result = await cli_agent.run_cli("context-loader", "config", "show")
    if result.exit_code == 0:
        return True

    # Auto-configure with the first available KN
    setup = await cli_agent.run_cli(
        "context-loader", "config", "set", "--kn-id", cl_kn_id,
    )
    if setup.exit_code != 0:
        pytest.skip(f"Cannot configure context-loader: {setup.stderr[:200]}")

    # Verify
    verify = await cli_agent.run_cli("context-loader", "config", "show")
    if verify.exit_code != 0:
        pytest.skip("context-loader config set succeeded but show still fails")
    return True


@pytest.fixture(scope="session")
async def cl_kn_id(cli_agent: CliAgent) -> str:
    """Find a KN for context loader tests. Skips if none available."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "10")
    if result.exit_code != 0:
        pytest.skip("Cannot list KNs")
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or kns.get("items") or []
    if not isinstance(kns, list) or not kns:
        pytest.skip("No KNs available")
    kn_id = str(kns[0].get("id") or kns[0].get("kn_id") or "")
    if not kn_id:
        pytest.skip("Cannot determine KN ID")
    return kn_id


@pytest.fixture(scope="session")
async def cl_kn_with_ot(cli_agent: CliAgent) -> tuple[str, str]:
    """Find a KN with queryable object types. Returns (kn_id, ot_id).

    Probes query to skip orphan KNs whose datasource was deleted.
    """
    result = await cli_agent.run_cli("bkn", "list", "--limit", "20")
    if result.exit_code != 0:
        pytest.skip("Cannot list KNs")
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or kns.get("items") or []
    if not isinstance(kns, list):
        pytest.skip("No KNs available")
    for kn in kns:
        kn_id = str(kn.get("id") or kn.get("kn_id") or "")
        if not kn_id:
            continue
        ot_result = await cli_agent.run_cli(
            "bkn", "object-type", "list", kn_id,
        )
        entries = ot_result.parsed_json
        if isinstance(entries, dict):
            entries = entries.get("entries") or []
        if ot_result.exit_code == 0 and isinstance(entries, list) and entries:
            ot_id = str(
                entries[0].get("id") or entries[0].get("ot_id") or "",
            )
            if not ot_id:
                continue
            probe = await cli_agent.run_cli(
                "bkn", "object-type", "query", kn_id, ot_id, "--limit", "1",
            )
            if probe.exit_code == 0:
                return kn_id, ot_id
    pytest.skip("No KN with queryable object types available")
