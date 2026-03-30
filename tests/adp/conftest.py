"""ADP (AI Data Platform) product line conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.api, pytest.mark.adp]


@pytest.fixture(scope="session", autouse=True)
async def ensure_authenticated(cli_agent: CliAgent):
    """Verify CLI is authenticated before running any ADP tests."""
    result = await cli_agent.run_cli("auth", "status")
    if result.exit_code != 0 or "Token status:" not in result.stdout:
        pytest.skip("Not authenticated — run `kweaver auth login` first")
