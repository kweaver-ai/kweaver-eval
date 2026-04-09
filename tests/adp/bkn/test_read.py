"""BKN read-only acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_bkn_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """bkn list returns a JSON array of knowledge networks."""
    result = await cli_agent.run_cli("bkn", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="bkn list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_export(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn export returns KN data as JSON."""
    result = await cli_agent.run_cli("bkn", "export", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_export", [result], det, module="adp/bkn")
    assert det.passed, det.failures


@pytest.mark.known_bug("bkn search returns markdown-wrapped output (backtick-quoted) instead of clean JSON when vectorizer is enabled")
async def test_bkn_search(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn search returns results for a query."""
    result = await cli_agent.run_cli("bkn", "search", kn_id, "test")
    if result.exit_code != 0 and "DefaultSmallModelEnabled" in result.stderr:
        pytest.skip("bkn search requires vectorizer (DefaultSmallModelEnabled is false)")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_search", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_get(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn get returns knowledge network details."""
    result = await cli_agent.run_cli("bkn", "get", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_get", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_stats(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn stats returns statistics for a knowledge network."""
    result = await cli_agent.run_cli("bkn", "stats", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_stats", [result], det, module="adp/bkn")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_bkn_create_and_delete(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """bkn create (empty) then delete."""
    import time
    from tests.adp.bkn.conftest import _short_suffix

    kn_name = f"eval_empty_{int(time.time())}_{_short_suffix()}"
    kn_id = ""
    steps = []

    try:
        create = await cli_agent.run_cli(
            "bkn", "create", "--name", kn_name,
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "bkn create")
        scorer.assert_json(create, "bkn create returns JSON")
        if isinstance(create.parsed_json, dict):
            kn_id = str(
                create.parsed_json.get("kn_id")
                or create.parsed_json.get("id")
                or "",
            )
        scorer.assert_true(bool(kn_id), "bkn create returns KN ID")

        # Verify via get
        if kn_id:
            get_result = await cli_agent.run_cli("bkn", "get", kn_id)
            steps.append(get_result)
            scorer.assert_exit_code(get_result, 0, "bkn get created KN")
            scorer.assert_json(get_result, "bkn get returns JSON")

        # Delete
        if kn_id:
            delete = await cli_agent.run_cli("bkn", "delete", kn_id, "-y")
            steps.append(delete)
            scorer.assert_exit_code(delete, 0, "bkn delete")
            kn_id = ""

    finally:
        if kn_id:
            await cli_agent.run_cli("bkn", "delete", kn_id, "-y")

    det = scorer.result()
    await eval_case("bkn_create_delete", steps, det, module="adp/bkn")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_bkn_update(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """bkn create then update name."""
    import time
    from tests.adp.bkn.conftest import _short_suffix

    kn_name = f"eval_upd_{int(time.time())}_{_short_suffix()}"
    kn_id = ""
    steps = []

    try:
        create = await cli_agent.run_cli("bkn", "create", "--name", kn_name)
        if create.exit_code != 0:
            pytest.skip("bkn create failed")
        if isinstance(create.parsed_json, dict):
            kn_id = str(
                create.parsed_json.get("kn_id")
                or create.parsed_json.get("id")
                or "",
            )
        if not kn_id:
            pytest.skip("Cannot get KN ID from create")

        # Update name
        new_name = f"eval_upd_renamed_{int(time.time())}_{_short_suffix()}"
        update = await cli_agent.run_cli(
            "bkn", "update", kn_id, "--name", new_name,
        )
        steps.append(update)
        scorer.assert_exit_code(update, 0, "bkn update")

        # Verify via get
        get_result = await cli_agent.run_cli("bkn", "get", kn_id)
        steps.append(get_result)
        scorer.assert_exit_code(get_result, 0, "bkn get after update")
        scorer.assert_json(get_result, "bkn get returns JSON")

    finally:
        if kn_id:
            await cli_agent.run_cli("bkn", "delete", kn_id, "-y")

    det = scorer.result()
    await eval_case("bkn_update", steps, det, module="adp/bkn")
    assert det.passed, det.failures
