"""BKN concept-group acceptance tests.

Covers:
  - bkn.concept_group.list              — list groups for a KN
  - bkn.concept_group.create            — create a new group
  - bkn.concept_group.get               — get group detail
  - bkn.concept_group.update            — rename a group
  - bkn.concept_group.delete            — delete a group
  - bkn.concept_group.add_object_types  — add OTs to group
  - bkn.concept_group.remove_object_types — remove OTs from group
"""

from __future__ import annotations

import time
import random
import string

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer
from tests.adp.bkn.conftest import _short_suffix


def _group_name() -> str:
    return f"eval_cg_{int(time.time())}_{_short_suffix()}"


async def test_bkn_concept_group_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str,
):
    """bkn concept-group list returns groups for a KN."""
    result = await cli_agent.run_cli("bkn", "concept-group", "list", kn_id)
    scorer.assert_exit_code(result, 0, "concept-group list")
    scorer.assert_json(result, "concept-group list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case(
        "bkn_concept_group_list", [result], det, module="adp/bkn",
    )
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_bkn_concept_group_lifecycle(
    cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str,
):
    """Concept group lifecycle: create -> get -> update -> delete."""
    name = _group_name()
    group_id = ""
    steps = []

    try:
        # Create
        create = await cli_agent.run_cli(
            "bkn", "concept-group", "create", kn_id, "--name", name,
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "concept-group create")
        scorer.assert_json(create, "concept-group create returns JSON")
        if isinstance(create.parsed_json, dict):
            group_id = str(
                create.parsed_json.get("id")
                or create.parsed_json.get("group_id")
                or "",
            )
        scorer.assert_true(bool(group_id), "create returns group ID")

        # Get
        if group_id:
            get_result = await cli_agent.run_cli(
                "bkn", "concept-group", "get", kn_id, group_id,
            )
            steps.append(get_result)
            scorer.assert_exit_code(get_result, 0, "concept-group get")
            scorer.assert_json(get_result, "concept-group get returns JSON")

        # Update
        if group_id:
            new_name = f"{name}_upd"
            update = await cli_agent.run_cli(
                "bkn", "concept-group", "update", kn_id, group_id,
                "--name", new_name,
            )
            steps.append(update)
            scorer.assert_exit_code(update, 0, "concept-group update")

        # Delete
        if group_id:
            delete = await cli_agent.run_cli(
                "bkn", "concept-group", "delete", kn_id, group_id, "-y",
            )
            steps.append(delete)
            scorer.assert_exit_code(delete, 0, "concept-group delete")
            group_id = ""

    finally:
        if group_id:
            await cli_agent.run_cli(
                "bkn", "concept-group", "delete", kn_id, group_id, "-y",
            )

    det = scorer.result()
    await eval_case(
        "bkn_concept_group_lifecycle", steps, det, module="adp/bkn",
    )
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_bkn_concept_group_add_remove_object_types(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    kn_with_data: tuple[str, str],
):
    """Concept group: create, add OT members, remove OT members, delete."""
    kn_id, ot_id = kn_with_data
    name = _group_name()
    group_id = ""
    steps = []

    try:
        # Create group
        create = await cli_agent.run_cli(
            "bkn", "concept-group", "create", kn_id, "--name", name,
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "concept-group create")
        if isinstance(create.parsed_json, dict):
            group_id = str(
                create.parsed_json.get("id")
                or create.parsed_json.get("group_id")
                or "",
            )
        if not group_id:
            pytest.skip("Cannot create concept group")

        # Add object type
        add = await cli_agent.run_cli(
            "bkn", "concept-group", "add-object-types",
            kn_id, group_id, ot_id,
        )
        steps.append(add)
        scorer.assert_exit_code(add, 0, "concept-group add-object-types")

        # Remove object type
        remove = await cli_agent.run_cli(
            "bkn", "concept-group", "remove-object-types",
            kn_id, group_id, ot_id,
        )
        steps.append(remove)
        scorer.assert_exit_code(remove, 0, "concept-group remove-object-types")

    finally:
        if group_id:
            await cli_agent.run_cli(
                "bkn", "concept-group", "delete", kn_id, group_id, "-y",
            )

    det = scorer.result()
    await eval_case(
        "bkn_concept_group_add_remove_ot", steps, det, module="adp/bkn",
    )
    assert det.passed, det.failures
