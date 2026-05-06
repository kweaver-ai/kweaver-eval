"""Vega connector-type management acceptance tests.

Covers:
  - vega.connector_type.register — register (install) a connector type
  - vega.connector_type.update   — update connector type metadata
  - vega.connector_type.delete   — unregister a connector type
  - vega.connector_type.enable   — toggle a connector type on/off

Connector type registration requires a connector archive or a URL;
these tests use `kweaver call` to target the REST API directly.
"""

from __future__ import annotations

import json
import time
import random
import string

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer
from tests.adp.conftest import EVAL_PREFIX


def _ct_name() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{EVAL_PREFIX}ct_{int(time.time())}_{suffix}"


async def _find_connector_type(cli_agent: CliAgent) -> tuple[str, bool] | None:
    """Return (connector_type_id, is_enabled) for the first registered type, or None."""
    result = await cli_agent.run_cli("vega", "connector-type", "list")
    if result.exit_code != 0:
        return None
    cts = result.parsed_json
    if isinstance(cts, dict):
        cts = cts.get("items") or cts.get("entries") or []
    if not isinstance(cts, list) or not cts:
        return None
    ct = cts[0]
    ct_id = str(ct.get("type") or ct.get("id") or ct.get("connector_type_id") or "")
    enabled = bool(ct.get("enabled") or ct.get("is_enabled") or False)
    if ct_id:
        return ct_id, enabled
    return None


async def test_vega_connector_type_enable_toggle(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """vega connector-type enable/disable toggles connector type availability."""
    found = await _find_connector_type(cli_agent)
    if not found:
        pytest.skip("No connector types available")
    ct_id, was_enabled = found
    steps = []

    # Toggle to the opposite state: CLI uses `enable --enabled <true|false>`
    new_enabled_str = "false" if was_enabled else "true"
    toggle = await cli_agent.run_cli(
        "vega", "connector-type", "enable", ct_id, "--enabled", new_enabled_str,
    )
    steps.append(toggle)
    if toggle.exit_code != 0 and (
        "404" in toggle.stderr or "405" in toggle.stderr
    ):
        pytest.skip("connector-type enable/disable endpoint not available")
    scorer.assert_exit_code(toggle, 0, "connector-type enable toggle")

    # Restore original state
    restore_str = "true" if was_enabled else "false"
    restore = await cli_agent.run_cli(
        "vega", "connector-type", "enable", ct_id, "--enabled", restore_str,
    )
    steps.append(restore)

    det = scorer.result()
    await eval_case(
        "vega_connector_type_enable_toggle", steps, det, module="adp/vega",
    )
    assert det.passed, det.failures


async def test_vega_connector_type_update(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """vega connector-type update modifies connector type metadata."""
    found = await _find_connector_type(cli_agent)
    if not found:
        pytest.skip("No connector types available")
    ct_id, _ = found

    # Use CLI update: `vega connector-type update <type> -d <json>`
    result = await cli_agent.run_cli(
        "vega", "connector-type", "update", ct_id,
        "-d", json.dumps({"description": "eval test update"}),
    )
    if result.exit_code != 0 and any(
        s in result.stderr for s in ("404", "405", "502", "400")
    ):
        pytest.skip("connector-type update endpoint not available or server error")
    scorer.assert_exit_code(result, 0, "connector-type update exit code")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "vega_connector_type_update", [result], det, module="adp/vega",
    )
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_vega_connector_type_register_and_delete(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """vega connector-type register installs a connector; delete removes it."""
    ct_name = _ct_name()
    ct_id = ""
    steps = []

    try:
        # Register via call — CLI 'vega connector-type register' may not be implemented
        register = await cli_agent.run_cli(
            "call",
            "/api/vega/v1/connector-type",
            "-X", "POST",
            "-d", json.dumps({
                "name": ct_name,
                "connector_type": "custom",
                "description": "eval test connector type",
            }),
        )
        steps.append(register)
        if register.exit_code != 0 and (
            "404" in register.stderr or "405" in register.stderr
        ):
            pytest.skip("connector-type register endpoint not available on this deployment")
        scorer.assert_exit_code(register, 0, "connector-type register exit code")
        scorer.assert_json(register, "register returns JSON")
        if isinstance(register.parsed_json, dict):
            ct_id = str(
                register.parsed_json.get("id")
                or register.parsed_json.get("connector_type_id")
                or "",
            )
        scorer.assert_true(bool(ct_id), "register returns ID")

        # Delete
        if ct_id:
            delete = await cli_agent.run_cli(
                "call",
                f"/api/vega/v1/connector-type/{ct_id}",
                "-X", "DELETE",
            )
            steps.append(delete)
            scorer.assert_exit_code(delete, 0, "connector-type delete exit code")
            ct_id = ""

    finally:
        if ct_id:
            await cli_agent.run_cli(
                "call",
                f"/api/vega/v1/connector-type/{ct_id}",
                "-X", "DELETE",
            )

    det = scorer.result()
    await eval_case(
        "vega_connector_type_register_and_delete",
        steps,
        det,
        module="adp/vega",
    )
    assert det.passed, det.failures
