"""BKN build acceptance tests (destructive).

Ported from kweaver-sdk e2e/build.test.ts.
Triggers a --no-wait build on a KN with object types.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.destructive
async def test_bkn_build_no_wait(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """bkn build --no-wait triggers a build and returns immediately."""
    kn_id, _ot_id = kn_with_data

    result = await cli_agent.run_cli("bkn", "build", kn_id, "--no-wait")
    # Build may fail if another build is running or no buildable concepts
    if result.exit_code != 0:
        err = result.stderr + result.stdout
        if any(k in err for k in ("running", "conflict", "already")):
            pytest.skip("Another build is already running on this KN")
        if any(k in err for k in ("NoneConceptType", "JobConceptConfig")):
            pytest.skip("KN has no buildable concepts")

    scorer.assert_exit_code(result, 0, "bkn build --no-wait")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_build_no_wait", [result], det, module="adp/bkn")
    assert det.passed, det.failures
