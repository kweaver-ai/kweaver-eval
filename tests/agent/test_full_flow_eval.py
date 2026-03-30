"""Agent-driven full flow evaluation.

Cross-module end-to-end scenario using agent judge for semantic evaluation.
"""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_bkn_list_acceptability(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """Evaluate whether bkn list output is acceptable from a user perspective."""
    result = await cli_agent.run_cli("bkn", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="bkn list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_list_acceptability", [result], det, module="adp/bkn")
    assert det.passed, det.failures
