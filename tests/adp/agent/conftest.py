"""Agent module conftest — fixtures for decision agent tests."""

from __future__ import annotations

import json
import random
import string
import time

import pytest

from lib.agents.cli_agent import CliAgent
from tests.adp.conftest import EVAL_DB_PK_MAP, EVAL_DB_TABLES, EVAL_PREFIX


def _short_suffix() -> str:
    """Return a short random suffix like 'a3x' to avoid name collisions."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=4))


def _agent_name() -> str:
    """Generate a unique eval agent name."""
    return f"{EVAL_PREFIX}agent_{int(time.time())}_{_short_suffix()}"


# ---------------------------------------------------------------------------
# Resource cleanup helpers
# ---------------------------------------------------------------------------

async def _list_eval_agents(cli_agent: CliAgent) -> list[str]:
    """Return IDs of agents whose name starts with EVAL_PREFIX."""
    result = await cli_agent.run_cli("agent", "list", "--limit", "100")
    parsed = result.parsed_json
    if result.exit_code != 0 or parsed is None:
        return []
    entries = parsed if isinstance(parsed, list) else parsed.get("entries") or parsed.get("data") or []
    if not isinstance(entries, list):
        return []
    return [
        str(a.get("id") or a.get("agent_id") or "")
        for a in entries
        if str(a.get("name", "")).startswith(EVAL_PREFIX)
    ]


async def _cleanup_eval_agents(cli_agent: CliAgent) -> None:
    """Delete all eval_ prefixed agents."""
    for agent_id in await _list_eval_agents(cli_agent):
        if agent_id:
            await cli_agent.run_cli("agent", "delete", agent_id, "-y")


# ---------------------------------------------------------------------------
# Session-level fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
async def cleanup_eval_agent_resources(cli_agent: CliAgent):
    """Clean up residual eval_ agents before and after the test session."""
    await _cleanup_eval_agents(cli_agent)
    yield
    await _cleanup_eval_agents(cli_agent)


# Soft preference for LLM selection — used only to *order* candidates so a
# probe-based search runs cheap models first. **Not** a hard allowlist:
# we always probe every model and pick the first one whose chat actually
# works, so a deprovisioned/arrears-blocked model is auto-skipped without
# code changes.
#
# Match is exact (lower-cased model_name == pref). Names not in this list still
# get picked up as fallback candidates by `_ordered_candidates`.
#
# Why `deepseek-chat` first (env 62, 2026-05-08): the thinking-mode variants
# (`deepseek-v4-flash`, `deepseek-v4-pro`) emit `reasoning_content` tokens that
# the agent runtime drops on multi-turn re-feed (KN-bound or memory-instruction
# prompts), so DeepSeek's API returns `invalid_request_error: The
# reasoning_content in the thinking mode must be passed back to the API`. Plain
# chat without those prompts works for thinking models, but `owned_agent*`
# scenarios use both — pick the non-thinking model. `deepseek-v4-flash-chat`
# is excluded because its upstream API key on env 62 (****3ffd) is invalid.
_LLM_PREFERENCE = (
    "deepseek-chat",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "qwen3-max",
)


async def _fetch_llm_models(cli_agent: CliAgent) -> list[dict]:
    """Fetch LLM models from model-factory."""
    result = await cli_agent.run_cli(
        "call", "/api/mf-model-manager/v1/llm/list?page=1&size=100",
    )
    if result.exit_code != 0 or not isinstance(result.parsed_json, dict):
        return []
    models = result.parsed_json.get("data") or []
    return [m for m in models if isinstance(m, dict) and m.get("model_type") == "llm"]


def _pick_llm(models: list[dict]) -> tuple[str, str] | None:
    """Return the highest-preference (model_id, model_name) pair, or None."""
    cands = _ordered_candidates(models)
    return cands[0] if cands else None


def _ordered_candidates(models: list[dict]) -> list[tuple[str, str]]:
    """Return (model_id, model_name) pairs ordered by _LLM_PREFERENCE, then the rest."""
    by_name: dict[str, tuple[str, str]] = {}
    for m in models:
        name = str(m.get("model_name", "")).lower()
        mid = str(m.get("model_id") or "")
        mname = str(m.get("model_name") or "")
        if mid:
            by_name[name] = (mid, mname)
    ordered: list[tuple[str, str]] = []
    used: set[str] = set()
    for pref in _LLM_PREFERENCE:
        pair = by_name.get(pref)
        if pair and pref not in used:
            ordered.append(pair)
            used.add(pref)
    for name, pair in by_name.items():
        if name not in used:
            ordered.append(pair)
    return ordered


async def _probe_chat(cli_agent: CliAgent, model_id: str) -> str | None:
    """Create a temp agent with this LLM, smoke-test chat, return its ID on success.

    Caller is responsible for cleanup of the returned agent ID.
    Returns None if creation or the chat probe fails.
    """
    create = await cli_agent.run_cli(
        "agent", "create",
        "--name", f"{EVAL_PREFIX}chat_probe_{int(time.time())}_{_short_suffix()}",
        "--llm-id", model_id,
        "--profile", "eval chat-capable agent",
    )
    if create.exit_code != 0 or not isinstance(create.parsed_json, dict):
        return None
    aid = str(create.parsed_json.get("id") or create.parsed_json.get("agent_id") or "")
    if not aid:
        return None
    probe = await cli_agent.run_cli(
        "agent", "chat", aid, "-m", "hi", "--no-stream", timeout=30.0,
    )
    if probe.exit_code == 0 and len(probe.stdout.strip()) > 0:
        return aid
    await cli_agent.run_cli("agent", "delete", aid, "-y")
    return None


@pytest.fixture(scope="session")
async def llm_id(cli_agent: CliAgent) -> str:
    """Return an LLM model ID ordered by preference (no probe).

    Many tests need only an ID — for agent CRUD, schema validation, etc. —
    and shouldn't be blocked when the platform's chat path (Redis / LLM
    backend) is temporarily down. The chat-probing lives in `chat_agent_id`.
    """
    models = await _fetch_llm_models(cli_agent)
    if not models:
        pytest.skip("No LLM models returned from model-factory")
    candidates = _ordered_candidates(models)
    if not candidates:
        pytest.skip("No LLM model available in model-factory")
    return candidates[0][0]


@pytest.fixture(scope="session")
async def chat_agent_id(cli_agent: CliAgent) -> str:
    """Return an agent ID that responds to chat.

    Path 1: probe existing agents — fast and lets us reuse a working setup.
    Path 2: iterate every LLM in preference order, create a throwaway eval
    agent bound to it, probe chat. Return the first one that answers.

    This decouples chat-capable tests from whichever specific LLM is
    healthy at the moment, and from whatever agents someone else happened
    to leave on the platform.
    """
    import asyncio as _aio

    # Path 1: probe pre-existing platform agents.
    for _attempt in range(3):
        result = await cli_agent.run_cli("agent", "list", "--limit", "30", "--verbose")
        parsed = result.parsed_json
        if result.exit_code != 0 or parsed is None:
            await _aio.sleep(3)
            continue
        entries = parsed if isinstance(parsed, list) else parsed.get("entries") or parsed.get("data") or []
        if not isinstance(entries, list) or len(entries) == 0:
            break

        candidates = []
        for a in entries:
            if isinstance(a, dict):
                aid = str(a.get("id") or a.get("agent_id") or "")
                if aid:
                    candidates.append((aid, a.get("is_built_in", 0)))
        candidates.sort(key=lambda x: x[1])

        for aid, _ in candidates:
            probe = await cli_agent.run_cli(
                "agent", "chat", aid, "-m", "hi", "--no-stream",
                timeout=45.0,
            )
            if probe.exit_code == 0 and len(probe.stdout.strip()) > 0:
                return aid

        await _aio.sleep(3)

    # Path 2: iterate LLM models in preference order, create+probe per LLM.
    models = await _fetch_llm_models(cli_agent)
    for mid, _ in _ordered_candidates(models):
        aid = await _probe_chat(cli_agent, mid)
        if aid:
            return aid

    pytest.skip(
        "No agents and no LLM models can respond to chat — "
        "platform chat backend is likely down (check Redis / model-factory)",
    )


def _build_explore_config(llm_id: str, llm_name: str, system_prompt: str = "") -> dict:
    """Build a complete explore-mode agent config with dolphin orchestration."""
    return {
        "input": {
            "fields": [
                {"name": "query", "type": "string", "desc": ""},
                {"name": "history", "type": "object", "desc": ""},
                {"name": "tool", "type": "object", "desc": ""},
                {"name": "header", "type": "object", "desc": ""},
                {"name": "self_config", "type": "object", "desc": ""},
            ],
            "rewrite": {
                "enable": False,
                "llm_config": {
                    "id": "", "name": "test", "model_type": "llm",
                    "temperature": 0.5, "top_p": 0.5, "max_tokens": 1000,
                },
            },
            "augment": {"enable": False, "data_source": {"kg": []}},
            "is_temp_zone_enabled": 0,
        },
        "system_prompt": system_prompt,
        "dolphin": "",
        "is_dolphin_mode": 0,
        "pre_dolphin": [
            {
                "key": "context_organize",
                "name": "上下文组织模块",
                "value": '\n{"query": "用户的问题为: "+$query} -> context\n',
                "enabled": True,
                "edited": False,
            },
        ],
        "post_dolphin": [],
        "data_source": {
            "kg": [], "doc": [], "metric": [],
            "kn_entry": [], "knowledge_network": [],
            "advanced_config": {"kg": None, "doc": None},
        },
        "skills": {"tools": [], "agents": [], "mcps": []},
        "llms": [
            {
                "is_default": True,
                "llm_config": {
                    "id": llm_id,
                    "name": llm_name,
                    "model_type": "llm",
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 1,
                    "max_tokens": 4096,
                },
            },
        ],
        "is_data_flow_set_enabled": 0,
        "output": {
            "variables": {
                "answer_var": "answer",
                "doc_retrieval_var": "doc_retrieval_res",
                "graph_retrieval_var": "graph_retrieval_res",
                "related_questions_var": "related_questions",
            },
            "default_format": "markdown",
        },
        "memory": {"is_enabled": True},
        "related_question": {"is_enabled": False},
        "plan_mode": {"is_enabled": False},
        "metadata": {"config_version": "v1"},
    }


@pytest.fixture(scope="session")
async def owned_agent(cli_agent: CliAgent, llm_id: str) -> dict:
    """Create a session-scoped eval agent with explore-mode dolphin config.

    Returns dict with 'id', 'key', 'name'.
    Cleaned up by cleanup_eval_agent_resources.
    """
    name = _agent_name()
    key = f"{name}_key"
    # Re-fetch to get model name (llm_id fixture only provides ID).
    models = await _fetch_llm_models(cli_agent)
    pair = _pick_llm(models)
    if not pair:
        pytest.skip("No LLM model available in model-factory")
    mid, mname = pair
    config = _build_explore_config(
        llm_id=mid,
        llm_name=mname,
        system_prompt="你是一个通用助手。请认真记住用户在对话中告诉你的所有信息，"
        "在后续对话中准确引用这些信息。回答尽量简洁。",
    )
    result = await cli_agent.run_cli(
        "agent", "create",
        "--name", name,
        "--profile", "Eval explore agent — safe to delete",
        "--key", key,
        "--config", json.dumps(config),
    )
    if result.exit_code != 0 or not isinstance(result.parsed_json, dict):
        pytest.skip(f"Cannot create eval agent: {result.stderr or result.stdout}")
    agent_id = str(result.parsed_json.get("id") or "")
    if not agent_id:
        pytest.skip("Agent create did not return ID")
    return {"id": agent_id, "key": key, "name": name}


async def _find_kn_with_queryable_ot(cli_agent: CliAgent) -> tuple[str, str, str] | None:
    """Find an existing KN with a queryable OT. Returns (kn_id, kn_name, ot_id) or None.

    Read-only discovery — never modifies found KNs.
    """
    result = await cli_agent.run_cli("bkn", "list", "--limit", "20")
    if result.exit_code != 0:
        return None
    kns = result.parsed_json
    if isinstance(kns, dict):
        kns = kns.get("entries") or kns.get("data") or []
    if not isinstance(kns, list):
        return None
    for kn in kns:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        kn_name = str(kn.get("name") or "")
        if not kn_id:
            continue
        ot_result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
        ot_entries = ot_result.parsed_json
        if isinstance(ot_entries, dict):
            ot_entries = ot_entries.get("entries") or []
        if ot_result.exit_code != 0 or not isinstance(ot_entries, list) or not ot_entries:
            continue
        ot_id = str(ot_entries[0].get("id") or ot_entries[0].get("ot_id") or "")
        if not ot_id:
            continue
        # Verify query actually works (skip orphan KNs)
        probe = await cli_agent.run_cli(
            "bkn", "object-type", "query", kn_id, ot_id, "--limit", "1",
        )
        if probe.exit_code == 0:
            return kn_id, kn_name, ot_id
    return None


async def _create_kn_for_agent(cli_agent: CliAgent, creds: dict) -> tuple[str, str, str] | None:
    """Create a KN from DB for agent binding. Returns (kn_id, kn_name, ot_id) or None."""
    ds_name = f"{EVAL_PREFIX}agkn_ds_{int(time.time())}_{_short_suffix()}"
    kn_name = f"{EVAL_PREFIX}agkn_{int(time.time())}_{_short_suffix()}"

    connect = await cli_agent.run_cli(
        "ds", "connect", creds["db_type"], creds["host"], creds["port"], creds["database"],
        "--account", creds["user"], "--password", creds["password"], "--name", ds_name,
    )
    if connect.exit_code != 0:
        return None
    ds_id = ""
    if isinstance(connect.parsed_json, list) and connect.parsed_json:
        ds_id = str(connect.parsed_json[0].get("datasource_id") or connect.parsed_json[0].get("id") or "")
    elif isinstance(connect.parsed_json, dict):
        ds_id = str(connect.parsed_json.get("datasource_id") or connect.parsed_json.get("id") or "")
    if not ds_id:
        return None

    create = await cli_agent.run_cli(
        "bkn", "create-from-ds", ds_id, "--name", kn_name,
        "--tables", ",".join(EVAL_DB_TABLES),
        "--pk-map", EVAL_DB_PK_MAP,
        timeout=300.0,
    )
    if create.exit_code != 0:
        await cli_agent.run_cli("ds", "delete", ds_id, "-y")
        return None
    kn_id = ""
    if isinstance(create.parsed_json, dict):
        kn_id = str(create.parsed_json.get("kn_id") or create.parsed_json.get("id") or "")
    if not kn_id:
        await cli_agent.run_cli("ds", "delete", ds_id, "-y")
        return None

    # Wait for build to complete
    build = await cli_agent.run_cli("bkn", "build", kn_id, "--wait", timeout=600.0)
    if build.exit_code != 0 and "JobConceptConfig" not in build.stderr:
        return None

    # Find first queryable OT
    ot_result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
    ot_entries = ot_result.parsed_json
    if isinstance(ot_entries, dict):
        ot_entries = ot_entries.get("entries") or []
    if not isinstance(ot_entries, list) or not ot_entries:
        return None
    ot_id = str(ot_entries[0].get("id") or ot_entries[0].get("ot_id") or "")
    if not ot_id:
        return None
    return kn_id, kn_name, ot_id


def _build_explore_config_with_kn(
    llm_id: str, llm_name: str, kn_id: str, kn_name: str,
) -> dict:
    """Build explore-mode agent config with a KN bound as data source."""
    config = _build_explore_config(
        llm_id=llm_id,
        llm_name=llm_name,
        system_prompt=(
            "你是一个知识助手。回答用户问题时，优先使用知识网络中的数据。"
            "如果知识网络中有相关信息，请基于这些信息回答。回答尽量简洁准确。"
        ),
    )
    config["data_source"]["knowledge_network"] = [
        {"knowledge_network_id": kn_id, "knowledge_network_name": kn_name},
    ]
    return config


@pytest.fixture(scope="session")
async def owned_agent_with_kn(
    cli_agent: CliAgent, llm_id: str, request: pytest.FixtureRequest,
) -> dict:
    """Create an eval agent bound to a KN with real data.

    Returns dict with 'agent_id', 'kn_id', 'ot_id'.
    Fast path: discover existing KN. Slow path: create from DB.
    db_credentials is only requested when the fast path fails.
    """
    # Step 1: discover or create KN (retry on transient TLS failures)
    import asyncio as _aio
    found = None
    for _attempt in range(3):
        found = await _find_kn_with_queryable_ot(cli_agent)
        if found:
            break
        await _aio.sleep(3)
    if not found:
        # Slow path — need DB credentials to create a KN
        db_credentials = request.getfixturevalue("db_credentials")
        found = await _create_kn_for_agent(cli_agent, db_credentials)
    if not found:
        pytest.skip("No KN with queryable data available and cannot create one")
    kn_id, kn_name, ot_id = found

    # Step 2: get LLM model name
    models = await _fetch_llm_models(cli_agent)
    pair = _pick_llm(models)
    if not pair:
        pytest.skip("No LLM model available")
    mid, mname = pair

    # Step 3: create agent with KN bound
    name = _agent_name()
    key = f"{name}_key"
    config = _build_explore_config_with_kn(mid, mname, kn_id, kn_name)
    result = await cli_agent.run_cli(
        "agent", "create",
        "--name", name,
        "--profile", "Eval agent with KN — safe to delete",
        "--key", key,
        "--config", json.dumps(config),
    )
    if result.exit_code != 0 or not isinstance(result.parsed_json, dict):
        pytest.skip(f"Cannot create eval agent with KN: {result.stderr or result.stdout}")
    agent_id = str(result.parsed_json.get("id") or "")
    if not agent_id:
        pytest.skip("Agent create did not return ID")
    return {"agent_id": agent_id, "kn_id": kn_id, "ot_id": ot_id}
