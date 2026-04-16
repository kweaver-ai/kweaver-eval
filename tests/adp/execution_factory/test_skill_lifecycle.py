"""Execution Factory — skill lifecycle acceptance tests.

Covers:
  - skill.register   — install a skill from the marketplace
  - skill.uninstall  — remove an installed skill

These tests require that the marketplace contains at least one skill that is
not currently installed. They are destructive and use try/finally cleanup.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def _find_market_skill_not_installed(cli_agent: CliAgent) -> str | None:
    """Return the ID of a marketplace skill not currently installed, or None."""
    market_result = await cli_agent.run_cli("skill", "market")
    if market_result.exit_code != 0:
        return None
    market = market_result.parsed_json
    if isinstance(market, dict):
        market = market.get("entries") or market.get("items") or market.get("data") or []
    if not isinstance(market, list) or not market:
        return None

    installed_result = await cli_agent.run_cli("skill", "list")
    installed_ids: set[str] = set()
    if installed_result.exit_code == 0:
        installed = installed_result.parsed_json
        if isinstance(installed, dict):
            installed = installed.get("entries") or installed.get("items") or []
        if isinstance(installed, list):
            for s in installed:
                sid = str(s.get("id") or s.get("skill_id") or "")
                if sid:
                    installed_ids.add(sid)

    for item in market:
        mid = str(item.get("id") or item.get("skill_id") or "")
        if mid and mid not in installed_ids:
            return mid
    return None


@pytest.mark.destructive
async def test_skill_register_and_uninstall(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """skill register installs a marketplace skill; skill uninstall removes it."""
    skill_id = await _find_market_skill_not_installed(cli_agent)
    if not skill_id:
        pytest.skip("No marketplace skill available to install (all may already be installed or market is empty)")

    installed = False
    steps = []

    try:
        # Register (install)
        register = await cli_agent.run_cli("skill", "register", skill_id)
        if register.exit_code != 0 and (
            "unknown" in register.stderr.lower()
            or "command not found" in register.stderr.lower()
        ):
            pytest.skip("skill register command not available in this SDK version")
        steps.append(register)
        scorer.assert_exit_code(register, 0, "skill register exit code")
        installed = True

        # Uninstall
        uninstall = await cli_agent.run_cli("skill", "uninstall", skill_id, "-y")
        if uninstall.exit_code != 0 and (
            "unknown" in uninstall.stderr.lower()
            or "command not found" in uninstall.stderr.lower()
        ):
            # Try alternative command name
            uninstall = await cli_agent.run_cli(
                "skill", "delete", skill_id, "-y",
            )
        steps.append(uninstall)
        scorer.assert_exit_code(uninstall, 0, "skill uninstall exit code")
        installed = False

    finally:
        if installed:
            # Best-effort cleanup
            await cli_agent.run_cli("skill", "uninstall", skill_id, "-y")

    det = scorer.result()
    await eval_case(
        "skill_register_and_uninstall", steps, det, module="adp/execution_factory",
    )
    assert det.passed, det.failures


async def test_skill_register_invalid_id(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """skill register with a nonexistent ID returns a non-zero exit code."""
    result = await cli_agent.run_cli(
        "skill", "register", "nonexistent_skill_000_does_not_exist",
    )
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        pytest.skip("skill register command not available in this SDK version")
    scorer.assert_true(
        result.exit_code != 0,
        "skill register with invalid ID returns non-zero exit",
    )
    det = scorer.result(result.duration_ms)
    await eval_case(
        "skill_register_invalid_id", [result], det, module="adp/execution_factory",
    )
    assert det.passed, det.failures
