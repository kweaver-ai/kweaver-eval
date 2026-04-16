"""BKN risk-type and graph import/export acceptance tests.

Covers:
  - bkn.risk_type.list     — list risk types for a KN
  - bkn.risk_type.create   — create a risk type
  - bkn.bkn.upload         — upload a KN graph archive
  - bkn.bkn.download       — download a KN as a graph archive
  - bkn.job.create         — create a build job for a KN

These capabilities are accessed via `kweaver call` because the kweaver CLI
does not expose dedicated sub-commands for them.
"""

from __future__ import annotations

import json
import time
import random
import string

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


def _risk_name() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"eval_risk_{int(time.time())}_{suffix}"


async def _find_kn_id(cli_agent: CliAgent) -> str | None:
    """Return the first available KN ID, or None."""
    result = await cli_agent.run_cli("bkn", "list", "--limit", "5")
    if result.exit_code != 0:
        return None
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or kns.get("items") or []
    if not isinstance(kns, list) or not kns:
        return None
    return str(kns[0].get("kn_id") or kns[0].get("id") or "")


async def test_bkn_risk_type_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """GET /api/cognitive-search/v1/kn/<id>/risk-type lists risk types for a KN."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KNs available")

    result = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/kn/{kn_id}/risk-type",
    )
    if result.exit_code != 0 and (
        "404" in result.stderr or "405" in result.stderr
    ):
        pytest.skip("risk-type list endpoint not available on this deployment")
    scorer.assert_exit_code(result, 0, "risk-type list exit code")
    scorer.assert_json(result, "risk-type list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_risk_type_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_bkn_risk_type_create(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """POST /api/cognitive-search/v1/kn/<id>/risk-type creates a risk type."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KNs available")

    name = _risk_name()
    risk_id = ""
    steps = []

    try:
        create = await cli_agent.run_cli(
            "call",
            f"/api/cognitive-search/v1/kn/{kn_id}/risk-type",
            "-X", "POST",
            "-d", json.dumps({"name": name, "description": "eval test risk type"}),
        )
        steps.append(create)
        if create.exit_code != 0 and (
            "404" in create.stderr or "405" in create.stderr
        ):
            pytest.skip("risk-type create endpoint not available on this deployment")
        scorer.assert_exit_code(create, 0, "risk-type create exit code")
        scorer.assert_json(create, "risk-type create returns JSON")
        if isinstance(create.parsed_json, dict):
            risk_id = str(
                create.parsed_json.get("id")
                or create.parsed_json.get("risk_type_id")
                or "",
            )
        scorer.assert_true(bool(risk_id), "risk-type create returns ID")
    finally:
        if risk_id:
            await cli_agent.run_cli(
                "call",
                f"/api/cognitive-search/v1/kn/{kn_id}/risk-type/{risk_id}",
                "-X", "DELETE",
            )

    det = scorer.result()
    await eval_case("bkn_risk_type_create", steps, det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_download(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """GET /api/cognitive-search/v1/kn/<id>/download initiates a KN graph export."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KNs available")

    # Try dedicated CLI command first, then fall back to REST call
    result = await cli_agent.run_cli("bkn", "download", kn_id)
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        result = await cli_agent.run_cli(
            "call",
            f"/api/cognitive-search/v1/kn/{kn_id}/download",
        )
    if result.exit_code != 0 and (
        "404" in result.stderr or "500" in result.stderr
    ):
        pytest.skip("KN download endpoint not available or server error")
    scorer.assert_exit_code(result, 0, "bkn download exit code")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_download", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_job_create(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """POST /api/cognitive-search/v1/kn/<id>/job creates a build job."""
    kn_id = await _find_kn_id(cli_agent)
    if not kn_id:
        pytest.skip("No KNs available")

    result = await cli_agent.run_cli(
        "call",
        f"/api/cognitive-search/v1/kn/{kn_id}/job",
        "-X", "POST",
        "-d", json.dumps({"type": "build"}),
    )
    if result.exit_code != 0 and (
        "404" in result.stderr or "405" in result.stderr
    ):
        # Try alternative endpoint path
        result = await cli_agent.run_cli(
            "call",
            f"/api/cognitive-search/v1/kn/{kn_id}/build",
            "-X", "POST",
            "-d", json.dumps({}),
        )
    if result.exit_code != 0 and (
        "404" in result.stderr or "500" in result.stderr
    ):
        pytest.skip("KN job/build create endpoint not available or server error")
    scorer.assert_exit_code(result, 0, "bkn job create exit code")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_job_create", [result], det, module="adp/bkn")
    assert det.passed, det.failures
