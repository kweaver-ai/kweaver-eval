"""BKN version management tests (pull, push, validate)."""

from __future__ import annotations

import os
import tempfile

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_bkn_pull(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_id: str,
):
    """bkn pull downloads a KN tar and extracts to a local directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "pulled_kn")
        result = await cli_agent.run_cli(
            "bkn", "pull", kn_id, out_dir,
            timeout=120.0,
        )
        scorer.assert_exit_code(result, 0, "bkn pull")
        # Verify something was extracted
        has_files = os.path.isdir(out_dir) and os.listdir(out_dir)
        scorer.assert_true(bool(has_files), "bkn pull extracts files")
        det = scorer.result(result.duration_ms)
        await eval_case("bkn_pull", [result], det, module="adp/bkn")
        assert det.passed, det.failures


async def test_bkn_validate_after_pull(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_id: str,
):
    """Pull a KN then validate the local directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "validate_kn")
        pull = await cli_agent.run_cli(
            "bkn", "pull", kn_id, out_dir,
            timeout=120.0,
        )
        if pull.exit_code != 0:
            pytest.skip("bkn pull failed, cannot validate")

        result = await cli_agent.run_cli(
            "bkn", "validate", out_dir,
            timeout=60.0,
        )
        scorer.assert_exit_code(result, 0, "bkn validate")
        det = scorer.result(result.duration_ms)
        await eval_case("bkn_validate", [result], det, module="adp/bkn")
        assert det.passed, det.failures


@pytest.mark.destructive
async def test_bkn_push_after_pull(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_id: str,
):
    """Pull a KN, then push it back (round-trip)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = os.path.join(tmpdir, "push_kn")
        pull = await cli_agent.run_cli(
            "bkn", "pull", kn_id, out_dir,
            timeout=120.0,
        )
        if pull.exit_code != 0:
            pytest.skip("bkn pull failed, cannot push")

        steps = [pull]
        result = await cli_agent.run_cli(
            "bkn", "push", out_dir,
            timeout=180.0,
        )
        steps.append(result)
        scorer.assert_exit_code(result, 0, "bkn push")
        scorer.assert_json(result, "bkn push returns JSON")
        det = scorer.result()
        await eval_case("bkn_push", steps, det, module="adp/bkn")
        assert det.passed, det.failures
