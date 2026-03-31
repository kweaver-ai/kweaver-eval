"""Token refresh acceptance tests.

Ported from kweaver-sdk e2e/token-refresh.test.ts.
Validates that CLI auto-refreshes an expired OAuth token.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


def _kweaver_config_dir() -> Path:
    return Path.home() / ".kweaver"


def _find_token_file() -> Path | None:
    """Find the token.json for the current platform."""
    cfg_dir = _kweaver_config_dir()
    if not cfg_dir.is_dir():
        return None
    # Look for platform dirs with token.json
    for platform_dir in cfg_dir.iterdir():
        if platform_dir.is_dir():
            token_file = platform_dir / "token.json"
            if token_file.exists():
                return token_file
    return None


@pytest.mark.api
@pytest.mark.tbd("Token file path lookup does not match CLI storage layout")
async def test_token_auto_refresh(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """CLI auto-refreshes expired token on next command."""
    token_file = _find_token_file()
    if not token_file:
        pytest.skip("No token.json found in ~/.kweaver/")

    original = json.loads(token_file.read_text())
    if not original.get("refreshToken", "").strip():
        pytest.skip("No refresh token available")

    # Expire the token artificially
    expired = {**original, "expiresAt": "2020-01-01T00:00:00.000Z"}
    token_file.write_text(json.dumps(expired))
    steps = []

    try:
        # Run a command that triggers auto-refresh
        result = await cli_agent.run_cli("bkn", "list", "--limit", "1")
        steps.append(result)
        scorer.assert_exit_code(result, 0, "bkn list after token expiry")

        # Verify token was refreshed
        refreshed = json.loads(token_file.read_text())
        scorer.assert_true(
            refreshed.get("expiresAt", "") != "2020-01-01T00:00:00.000Z",
            "token expiresAt updated after refresh",
        )

        # Verify auth status
        status = await cli_agent.run_cli("auth", "status")
        steps.append(status)
        scorer.assert_exit_code(status, 0, "auth status after refresh")
        scorer.assert_stdout_contains(status, "Token status:", "auth reports active")

    finally:
        # Restore original token if refresh failed
        current = json.loads(token_file.read_text())
        if current.get("expiresAt") == "2020-01-01T00:00:00.000Z":
            token_file.write_text(json.dumps(original))

    det = scorer.result()
    await eval_case("token_auto_refresh", steps, det)
    assert det.passed, det.failures
