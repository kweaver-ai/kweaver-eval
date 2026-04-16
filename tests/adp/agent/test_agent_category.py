"""Agent category management acceptance tests.

Covers:
  - agent.category.list   — list categories (already covered in test_read.py via
                            `kweaver agent category-list`; here via call for completeness)
  - agent.category.create — create a new category
  - agent.category.update — rename a category
  - agent.category.delete — delete a category

The `kweaver agent` CLI does not expose category sub-commands directly; these
are reached via `kweaver call` against the cognitive-search REST API.
"""

from __future__ import annotations

import json
import time
import random
import string

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


_EVAL_PREFIX = "eval_cat_"


def _cat_name() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{_EVAL_PREFIX}{int(time.time())}_{suffix}"


async def test_agent_category_list(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """agent category-list returns a JSON list of categories."""
    result = await cli_agent.run_cli("agent", "category-list")
    if result.exit_code != 0 and (
        "unknown" in result.stderr.lower()
        or "command not found" in result.stderr.lower()
    ):
        # Fallback to call endpoint
        result = await cli_agent.run_cli(
            "call",
            "/api/cognitive-search/v1/agent/category/list",
        )
    scorer.assert_exit_code(result, 0, "agent category list")
    scorer.assert_json(result, "category list returns JSON")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_category_list", [result], det, module="adp/agent")
    assert det.passed, det.failures


@pytest.mark.destructive
async def test_agent_category_crud(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
):
    """Agent category lifecycle: create -> update -> delete."""
    name = _cat_name()
    cat_id = ""
    steps = []

    try:
        # Step 1: create
        create = await cli_agent.run_cli(
            "call",
            "/api/cognitive-search/v1/agent/category",
            "-X", "POST",
            "-d", json.dumps({"name": name}),
        )
        steps.append(create)
        if create.exit_code != 0 and (
            "404" in create.stderr or "405" in create.stderr
        ):
            pytest.skip("agent category create endpoint not available")
        scorer.assert_exit_code(create, 0, "category create")
        scorer.assert_json(create, "category create returns JSON")
        if isinstance(create.parsed_json, dict):
            cat_id = str(
                create.parsed_json.get("id")
                or create.parsed_json.get("category_id")
                or "",
            )
        scorer.assert_true(bool(cat_id), "category create returns ID")

        # Step 2: update (rename)
        if cat_id:
            new_name = f"{name}_upd"
            update = await cli_agent.run_cli(
                "call",
                f"/api/cognitive-search/v1/agent/category/{cat_id}",
                "-X", "PUT",
                "-d", json.dumps({"name": new_name}),
            )
            steps.append(update)
            scorer.assert_exit_code(update, 0, "category update")

        # Step 3: delete
        if cat_id:
            delete = await cli_agent.run_cli(
                "call",
                f"/api/cognitive-search/v1/agent/category/{cat_id}",
                "-X", "DELETE",
            )
            steps.append(delete)
            scorer.assert_exit_code(delete, 0, "category delete")
            cat_id = ""

    finally:
        if cat_id:
            await cli_agent.run_cli(
                "call",
                f"/api/cognitive-search/v1/agent/category/{cat_id}",
                "-X", "DELETE",
            )

    det = scorer.result()
    await eval_case("agent_category_crud", steps, det, module="adp/agent")
    assert det.passed, det.failures
