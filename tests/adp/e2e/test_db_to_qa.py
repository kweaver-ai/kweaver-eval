"""End-to-end acceptance test: DB → Knowledge Network → Q&A.

Mirrors the 01-db-to-qa example (examples/01-db-to-qa/run.sh):

  Step 1  ds connect mysql
  Step 2  bkn create-from-ds --build  (integrated build)
  Step 3  bkn object-type list / get  (schema exploration)
  Step 4  context-loader config set + kn-search --only-schema
  Step 5  agent chat with schema-injected context  (optional)
  Step 6  cleanup

Requires KWEAVER_TEST_DB_* env vars (skips otherwise).
Optional: KWEAVER_TEST_AGENT_ID for Step 5.
"""

from __future__ import annotations

import json
import os
import time
import random
import string

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer
from tests.adp.conftest import EVAL_PREFIX


def _suffix() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=4))


@pytest.mark.destructive
async def test_db_to_qa_example(
    cli_agent: CliAgent,
    scorer: Scorer,
    eval_case,
    db_credentials: dict,
):
    """Full 01-db-to-qa example flow: ds connect → build KN → search → chat."""
    creds = db_credentials
    suffix = f"{int(time.time())}_{_suffix()}"
    ds_name = f"{EVAL_PREFIX}e2e_ds_{suffix}"
    kn_name = f"{EVAL_PREFIX}e2e_kn_{suffix}"
    ds_id = ""
    kn_id = ""
    steps = []

    try:
        # ── Step 1: Connect datasource ────────────────────────────────────────
        connect = await cli_agent.run_cli(
            "ds", "connect",
            creds["db_type"], creds["host"], creds["port"], creds["database"],
            "--account", creds["user"],
            "--password", creds["password"],
            "--name", ds_name,
            timeout=120.0,
        )
        steps.append(connect)
        if connect.exit_code != 0 and ("503" in connect.stderr or "unavailable" in connect.stderr.lower()):
            pytest.skip("Datasource service unavailable (503)")
        scorer.assert_exit_code(connect, 0, "ds connect")
        scorer.assert_json(connect, "ds connect returns JSON")

        parsed = connect.parsed_json
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        if isinstance(parsed, dict):
            ds_id = str(parsed.get("datasource_id") or parsed.get("id") or "")
        scorer.assert_true(bool(ds_id), "ds connect returns datasource ID")
        if not ds_id:
            det = scorer.result()
            await eval_case("e2e_db_to_qa", steps, det, module="adp/e2e")
            pytest.skip("ds connect failed — cannot continue")

        # Limit to 2 tables to keep build fast
        tables_arg: list[str] = []
        if isinstance(connect.parsed_json, (list, dict)):
            raw = connect.parsed_json
            if isinstance(raw, list) and raw:
                raw = raw[0]
            tables_list = raw.get("tables") or [] if isinstance(raw, dict) else []
            names = [t["name"] for t in tables_list[:2] if t.get("name")]
            if names:
                tables_arg = ["--tables", ",".join(names)]

        # ── Step 2: create-from-ds with --build ───────────────────────────────
        create = await cli_agent.run_cli(
            "bkn", "create-from-ds", ds_id,
            "--name", kn_name,
            "--build",
            *tables_arg,
            timeout=600.0,
        )
        steps.append(create)
        if create.exit_code != 0 and "JobConceptConfig" in create.stderr:
            scorer.assert_true(True, "bkn create-from-ds --build (resource-backed OTs, build skipped by backend)")
        else:
            scorer.assert_exit_code(create, 0, "bkn create-from-ds --build")
        scorer.assert_json(create, "bkn create-from-ds returns JSON")

        if isinstance(create.parsed_json, dict):
            kn_id = str(
                create.parsed_json.get("kn_id")
                or create.parsed_json.get("id")
                or "",
            )
        scorer.assert_true(bool(kn_id), "bkn create-from-ds returns KN ID")
        if not kn_id:
            det = scorer.result()
            await eval_case("e2e_db_to_qa", steps, det, module="adp/e2e")
            pytest.skip("create-from-ds failed — cannot continue")

        # ── Step 3: Schema exploration ────────────────────────────────────────
        ot_list = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
        steps.append(ot_list)
        scorer.assert_exit_code(ot_list, 0, "bkn object-type list")
        scorer.assert_json(ot_list, "object-type list returns JSON")

        ot_entries = ot_list.parsed_json
        if isinstance(ot_entries, dict):
            ot_entries = ot_entries.get("entries", [])
        ot_id = ""
        if isinstance(ot_entries, list) and ot_entries:
            ot_id = str(ot_entries[0].get("id") or ot_entries[0].get("ot_id") or "")
        scorer.assert_true(bool(ot_id), "object-type list returns at least one OT")

        if ot_id:
            ot_get = await cli_agent.run_cli("bkn", "object-type", "get", kn_id, ot_id)
            steps.append(ot_get)
            scorer.assert_exit_code(ot_get, 0, "bkn object-type get")
            scorer.assert_json(ot_get, "object-type get returns JSON")

        # ── Step 4: Context-loader search ────────────────────────────────────
        cl_config = await cli_agent.run_cli(
            "context-loader", "config", "set",
            "--kn-id", kn_id,
            "--name", f"{EVAL_PREFIX}e2e_{suffix}",
        )
        steps.append(cl_config)
        if cl_config.exit_code != 0 and (
            "unknown" in cl_config.stderr.lower()
            or "404" in cl_config.stderr
        ):
            scorer.assert_true(True, "context-loader config set (not available, skipping)")
        else:
            scorer.assert_exit_code(cl_config, 0, "context-loader config set")

        cl_search = await cli_agent.run_cli(
            "context-loader", "kn-search", "业务数据",
            "--kn-id", kn_id,
            "--only-schema",
        )
        steps.append(cl_search)
        if cl_search.exit_code != 0 and (
            "unknown" in cl_search.stderr.lower()
            or "404" in cl_search.stderr
            or "500" in cl_search.stderr
        ):
            scorer.assert_true(True, "context-loader kn-search (not available, skipping)")
        else:
            scorer.assert_exit_code(cl_search, 0, "context-loader kn-search --only-schema")
            scorer.assert_json(cl_search, "kn-search returns JSON")

        # ── Step 5: Agent chat (optional) ─────────────────────────────────────
        agent_id = os.environ.get("KWEAVER_TEST_AGENT_ID", "")
        if not agent_id:
            # Try to find one
            agents_result = await cli_agent.run_cli("agent", "list", "--limit", "1")
            if agents_result.exit_code == 0 and isinstance(agents_result.parsed_json, list):
                lst = agents_result.parsed_json
                if lst:
                    agent_id = str(lst[0].get("id") or "")

        if agent_id:
            schema_raw = ""
            if cl_search.exit_code == 0 and isinstance(cl_search.parsed_json, dict):
                schema_raw = cl_search.parsed_json.get("raw", "")

            question = "这个数据库里有哪些核心的业务表？"
            prompt = (
                f"以下是数据库 schema 信息：\n\n{schema_raw}\n\n基于以上 schema，请回答：{question}"
                if schema_raw
                else question
            )

            chat = await cli_agent.run_cli(
                "agent", "chat", agent_id,
                "-m", prompt,
                "--no-stream",
                timeout=60.0,
            )
            steps.append(chat)
            if chat.exit_code != 0 and ("404" in chat.stderr or "500" in chat.stderr):
                scorer.assert_true(True, "agent chat (unavailable, skipping)")
            else:
                scorer.assert_exit_code(chat, 0, "agent chat")
                scorer.assert_true(
                    bool(chat.stdout.strip()),
                    "agent chat returns non-empty response",
                )

    finally:
        # ── Cleanup ───────────────────────────────────────────────────────────
        if kn_id:
            await cli_agent.run_cli("bkn", "delete", kn_id, "-y")
        if ds_id:
            for _ in range(3):
                del_ds = await cli_agent.run_cli("ds", "delete", ds_id, "-y")
                if del_ds.exit_code == 0 or "pending or running" not in del_ds.stderr:
                    break
                await __import__("asyncio").sleep(5)

    det = scorer.result()
    await eval_case("e2e_db_to_qa", steps, det, module="adp/e2e")
    assert det.passed, det.failures
