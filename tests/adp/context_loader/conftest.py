"""Context Loader module conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent


@pytest.fixture(scope="session")
async def cl_config_active(cli_agent: CliAgent) -> bool:
    """Ensure context-loader has an active config. Skips if not."""
    result = await cli_agent.run_cli("context-loader", "config", "show")
    if result.exit_code != 0:
        pytest.skip("No active context-loader config")
    return True
