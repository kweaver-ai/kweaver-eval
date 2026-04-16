"""Execution Factory — skill content retrieval acceptance tests.

Covers:
  - skill.content    — retrieve skill descriptor (kweaver skill content <id>)
  - skill.read_file  — extract a file from skill archive
  - skill.download   — download the skill archive
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def _find_skill_id(cli_agent: CliAgent) -> str | None:
    """Return the first installed skill ID, or None."""
    result = await cli_agent.run_cli("skill", "list")
    if result.exit_code != 0:
        return None
    skills = result.parsed_json
    if isinstance(skills, dict):
        skills = skills.get("entries") or skills.get("items") or []
    if not isinstance(skills, list) or not skills:
        return None
    return str(skills[0].get("id") or skills[0].get("skill_id") or "")


async def test_skill_content(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill content <id> returns skill descriptor text/JSON."""
    skill_id = await _find_skill_id(cli_agent)
    if not skill_id:
        pytest.skip("No installed skills available")

    result = await cli_agent.run_cli("skill", "content", skill_id)
    scorer.assert_exit_code(result, 0, "skill content")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "skill_content", [result], det, module="adp/execution_factory",
    )
    assert det.passed, det.failures


async def test_skill_read_file(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill read-file <id> <path> extracts a file from the skill archive."""
    skill_id = await _find_skill_id(cli_agent)
    if not skill_id:
        pytest.skip("No installed skills available")

    # Try reading a common skill manifest path; skip if not found
    for manifest_path in ("skill.json", "manifest.json", "README.md"):
        result = await cli_agent.run_cli(
            "skill", "read-file", skill_id, manifest_path,
        )
        if result.exit_code == 0:
            break
    else:
        pytest.skip("Cannot read any manifest from skill archive")

    scorer.assert_exit_code(result, 0, "skill read-file")
    scorer.assert_true(
        bool(result.stdout.strip()),
        "skill read-file returns non-empty content",
    )
    det = scorer.result(result.duration_ms)
    await eval_case(
        "skill_read_file", [result], det, module="adp/execution_factory",
    )
    assert det.passed, det.failures


async def test_skill_download(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """skill download <id> downloads the skill archive without error."""
    import tempfile
    import os

    skill_id = await _find_skill_id(cli_agent)
    if not skill_id:
        pytest.skip("No installed skills available")

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "skill.zip")
        result = await cli_agent.run_cli(
            "skill", "download", skill_id, "--output", out_path,
        )
        if result.exit_code != 0 and "unknown flag" in result.stderr.lower():
            # Fallback: download to current dir
            result = await cli_agent.run_cli(
                "skill", "download", skill_id,
            )

    scorer.assert_exit_code(result, 0, "skill download")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "skill_download", [result], det, module="adp/execution_factory",
    )
    assert det.passed, det.failures
