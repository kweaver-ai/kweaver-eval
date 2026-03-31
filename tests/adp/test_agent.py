"""Agent read-only acceptance tests.

agent get / get --verbose are covered by test_agent_lifecycle.py
(self-created agent avoids 403 on other users' agents).
"""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_agent_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """agent list returns a JSON array."""
    result = await cli_agent.run_cli("agent", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="agent list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_list", [result], det)
    assert det.passed, det.failures
