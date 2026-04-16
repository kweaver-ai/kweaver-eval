"""BKN action-type CRUD acceptance tests.

Covers:
  - bkn.action_type.create — create a new action type
  - bkn.action_type.update — update action type config
  - bkn.action_type.delete — delete an action type
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


def _at_name() -> str:
    return f"eval_at_{int(time.time())}_{_short_suffix()}"


async def _find_kn_id(cli_agent: CliAgent) -> str | None:
    """Return the first available KN ID."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "5")
    if result.exit_code != 0:
        return None
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or []
    if not isinstance(kns, list) or not kns:
        return None
    return str(kns[0].get("id") or kns[0].get("kn_id") or "")


@pytest.mark.destructive
async def test_bkn_action_type_lifecycle(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """BKN action-type: create -> update -> delete lifecycle."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KN available")

    name = _at_name()
    at_id = ""
    steps = []

    # Minimal action type config; exact schema varies by deployment.
    # The test documents the expected shape rather than asserting specific fields.
    at_config = json.dumps({
        "name": name,
        "type": "http",
        "config": {"url": "http://example.com/action", "method": "POST"},
    })

    try:
        create = await cli_agent.run_cli(
            "bkn", "action-type", "create", kn_id, at_config,
        )
        steps.append(create)
        if create.exit_code != 0 and (
            "unknown" in create.stderr.lower()
            or "command not found" in create.stderr.lower()
        ):
            pytest.skip("bkn action-type create not available in this SDK version")
        scorer.assert_exit_code(create, 0, "action-type create")
        scorer.assert_json(create, "action-type create returns JSON")
        if isinstance(create.parsed_json, dict):
            at_id = str(create.parsed_json.get("id") or "")
        scorer.assert_true(bool(at_id), "action-type create returns ID")

        # Update
        if at_id:
            new_config = json.dumps({"name": f"{name}_upd"})
            update = await cli_agent.run_cli(
                "bkn", "action-type", "update", kn_id, at_id, new_config,
            )
            steps.append(update)
            scorer.assert_exit_code(update, 0, "action-type update")

        # Delete
        if at_id:
            delete = await cli_agent.run_cli(
                "bkn", "action-type", "delete", kn_id, at_id, "-y",
            )
            steps.append(delete)
            scorer.assert_exit_code(delete, 0, "action-type delete")
            at_id = ""

    finally:
        if at_id:
            await cli_agent.run_cli(
                "bkn", "action-type", "delete", kn_id, at_id, "-y",
            )

    det = scorer.result()
    await eval_case(
        "bkn_action_type_lifecycle", steps, det, module="adp/bkn",
    )
    assert det.passed, det.failures
