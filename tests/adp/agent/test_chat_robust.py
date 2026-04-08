"""Agent chat robustness tests — stream integrity, boundaries, concurrency.

All tests use an agent bound to a BKN knowledge network. Tests verify
usability and robustness in realistic scenarios involving knowledge retrieval,
streaming, multi-turn conversations, and concurrent sessions.
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer

from .test_chat import _extract_conversation_id
from .test_context_quality import _assert_hard_only, _chat_turn, _stdout

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _chat_turn_stream(
    cli_agent: CliAgent,
    agent_id: str,
    message: str,
    cid: str | None = None,
    timeout: float = 120.0,
):
    """Send one chat turn in stream mode, return (CliResult, conversation_id)."""
    args = ["agent", "chat", agent_id, "-m", message, "--stream"]
    if cid:
        args.extend(["-cid", cid])
    result = await cli_agent.run_cli(*args, timeout=timeout)
    if not cid and result.exit_code == 0:
        cid = _extract_conversation_id(result.stdout + "\n" + result.stderr)
    return result, cid


async def _query_ground_truth(
    cli_agent: CliAgent, kn_id: str, ot_id: str,
) -> tuple[str, list[str]]:
    """Query KN for ground truth data. Returns (ot_name, [field_value, ...]).

    Fetches first instance from the OT and extracts non-empty string values
    suitable for checking in agent replies.
    """
    # Get OT metadata for name
    ot_get = await cli_agent.run_cli("bkn", "object-type", "get", kn_id, ot_id)
    ot_name = ""
    if isinstance(ot_get.parsed_json, dict):
        entry = ot_get.parsed_json
        if "entries" in entry and isinstance(entry["entries"], list) and entry["entries"]:
            entry = entry["entries"][0]
        ot_name = str(entry.get("name") or entry.get("ot_name") or "")

    # Query instances
    result = await cli_agent.run_cli(
        "bkn", "object-type", "query", kn_id, ot_id, "--limit", "3",
    )
    values = []
    if result.exit_code == 0 and isinstance(result.parsed_json, (list, dict)):
        rows = result.parsed_json
        if isinstance(rows, dict):
            rows = rows.get("entries") or rows.get("data") or rows.get("items") or []
        if isinstance(rows, list):
            for row in rows[:3]:
                if isinstance(row, dict):
                    for v in row.values():
                        sv = str(v).strip()
                        if sv and len(sv) >= 2 and sv not in ("None", "null", "True", "False"):
                            values.append(sv)
                            if len(values) >= 3:
                                break
                if len(values) >= 3:
                    break
    return ot_name, values


# ---------------------------------------------------------------------------
# Stream robustness (Gap #1)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_stream_chunk_integrity(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict,
):
    """Stream and no-stream for same question should both succeed and be semantically similar."""
    agent_id = owned_agent_with_kn["agent_id"]
    question = "用一句话介绍知识图谱的概念。"

    # no-stream
    r_sync, _ = await _chat_turn(cli_agent, agent_id, question, retries=2)
    # stream
    r_stream, _ = await _chat_turn_stream(cli_agent, agent_id, question)

    steps = [r_sync, r_stream]
    scorer.assert_exit_code(r_sync, 0, "no-stream chat")
    scorer.assert_exit_code(r_stream, 0, "stream chat")
    scorer.assert_true(len(r_sync.stdout.strip()) > 0, "no-stream returns non-empty output")
    scorer.assert_true(len(r_stream.stdout.strip()) > 0, "stream returns non-empty output")

    det = scorer.result(r_sync.duration_ms + r_stream.duration_ms)
    await eval_case(
        "stream_chunk_integrity", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "Two replies to the same question — one via --no-stream, one via --stream. "
                "Are both coherent answers? Are they semantically similar (same core idea)?"
            ),
        },
    )
    _assert_hard_only(det)


@pytest.mark.destructive
async def test_stream_with_knowledge_retrieval(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict,
):
    """Stream mode should return knowledge-grounded answers from the bound KN."""
    agent_id = owned_agent_with_kn["agent_id"]
    kn_id = owned_agent_with_kn["kn_id"]
    ot_id = owned_agent_with_kn["ot_id"]

    ot_name, ground_truth = await _query_ground_truth(cli_agent, kn_id, ot_id)
    if not ot_name:
        pytest.skip("Cannot determine OT name for knowledge query")

    question = f"请列出知识网络中关于 {ot_name} 的一些数据记录。"
    r_stream, _ = await _chat_turn_stream(cli_agent, agent_id, question)

    steps = [r_stream]
    scorer.assert_exit_code(r_stream, 0, "stream knowledge retrieval")
    scorer.assert_true(
        len(r_stream.stdout.strip()) > 0,
        "stream returns non-empty output",
    )
    # Soft check: does the reply contain any ground truth value?
    reply = _stdout(r_stream)
    hit = any(v.lower() in reply for v in ground_truth)
    scorer.assert_true(hit, f"stream reply contains KN ground truth (checked {len(ground_truth)} values)")

    det = scorer.result(r_stream.duration_ms)
    await eval_case(
        "stream_knowledge_retrieval", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                f"Asked about '{ot_name}' data from KN. Does the stream reply "
                f"contain actual data records? Ground truth values: {ground_truth[:3]}"
            ),
        },
    )
    _assert_hard_only(det)


# ---------------------------------------------------------------------------
# Multi-turn boundaries (Gap #2)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_long_message_input(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict,
):
    """Agent handles a long (>2KB) input message without crash or timeout."""
    agent_id = owned_agent_with_kn["agent_id"]

    # Build a >2KB structured message
    long_msg = "请帮我分析以下数据字段列表，告诉我哪些字段最重要：\n"
    for i in range(80):
        long_msg += f"  - field_{i:03d}: 类型=string, 描述='测试字段编号{i}的详细描述信息，用于验证长消息处理'\n"

    r, _ = await _chat_turn(cli_agent, agent_id, long_msg, retries=1, timeout=180.0)
    steps = [r]
    scorer.assert_exit_code(r, 0, "long message input")
    scorer.assert_true(len(r.stdout.strip()) > 0, "long message returns non-empty output")

    det = scorer.result(r.duration_ms)
    await eval_case("long_message_input", steps, det, module="adp/agent")
    _assert_hard_only(det)


@pytest.mark.destructive
async def test_special_chars_in_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict,
):
    """Agent handles special characters without crash: SQL keywords, quotes, emoji, brackets."""
    agent_id = owned_agent_with_kn["agent_id"]

    message = (
        '请解释以下内容：SELECT * FROM "users" WHERE name = \'test\' AND id > 0; '
        "-- 这是注释 /* block */ <script>alert('xss')</script> "
        "换行测试\\n\\t制表符 "
        "emoji测试: 🎉🚀💡 "
        "花括号 {key: value} 方括号 [1, 2, 3]"
    )

    r, _ = await _chat_turn(cli_agent, agent_id, message, retries=1)
    steps = [r]
    scorer.assert_exit_code(r, 0, "special chars input")
    scorer.assert_true(len(r.stdout.strip()) > 0, "special chars returns non-empty output")

    det = scorer.result(r.duration_ms)
    await eval_case("special_chars_in_query", steps, det, module="adp/agent")
    _assert_hard_only(det)


@pytest.mark.destructive
async def test_knowledge_multi_turn_drill_down(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict,
):
    """Multi-turn drill-down: overview → specific field → verify knowledge grounding."""
    agent_id = owned_agent_with_kn["agent_id"]
    kn_id = owned_agent_with_kn["kn_id"]
    ot_id = owned_agent_with_kn["ot_id"]

    ot_name, ground_truth = await _query_ground_truth(cli_agent, kn_id, ot_id)
    if not ot_name or not ground_truth:
        pytest.skip("Cannot get ground truth for drill-down test")

    steps = []
    cid = None

    # Turn 1: overview
    r1, cid = await _chat_turn(
        cli_agent, agent_id,
        f"知识网络中有哪些关于 {ot_name} 的信息？请简要概述。",
        cid, retries=2,
    )
    steps.append(r1)
    scorer.assert_exit_code(r1, 0, "drill-down T1 overview")

    # Turn 2: drill into specifics
    r2, cid = await _chat_turn(
        cli_agent, agent_id,
        f"请列出 {ot_name} 的具体数据记录，包括各字段的值。",
        cid,
    )
    steps.append(r2)
    scorer.assert_exit_code(r2, 0, "drill-down T2 specifics")

    # Turn 3: ask about a specific value
    target_value = ground_truth[0]
    r3, cid = await _chat_turn(
        cli_agent, agent_id,
        f"数据中是否包含 '{target_value}' 这个值？它属于哪条记录的哪个字段？",
        cid,
    )
    steps.append(r3)
    scorer.assert_exit_code(r3, 0, "drill-down T3 specific value")
    scorer.assert_true(
        target_value.lower() in _stdout(r3),
        f"T3 reply confirms ground truth value '{target_value}'",
    )

    det = scorer.result()
    await eval_case(
        "knowledge_multi_turn_drill_down", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                f"3-turn drill-down on '{ot_name}' data. T1: overview. T2: specific records. "
                f"T3: asked about specific value '{target_value}'. "
                "Does the agent progressively provide more detail? Does T3 confirm the value?"
            ),
        },
    )
    _assert_hard_only(det)


# ---------------------------------------------------------------------------
# CID edge cases (Gap #3)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_cid_expired_or_foreign(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict, chat_agent_id: str,
):
    """Using agent A's conversation_id with agent B should fail or start fresh."""
    agent_a = owned_agent_with_kn["agent_id"]
    agent_b = chat_agent_id

    # Skip if both agents are the same
    if agent_a == agent_b:
        pytest.skip("owned_agent_with_kn and chat_agent_id are the same agent")

    # Create a conversation on agent A
    r1, cid_a = await _chat_turn(cli_agent, agent_a, "记住：密码是 alpha-bravo-42", retries=2)
    steps = [r1]
    scorer.assert_exit_code(r1, 0, "create conversation on agent A")
    scorer.assert_true(bool(cid_a), "got conversation_id from agent A")

    if not cid_a:
        det = scorer.result()
        await eval_case("cid_expired_or_foreign", steps, det, module="adp/agent")
        assert det.passed, det.failures
        return

    # Use agent A's cid to chat with agent B
    r2 = await cli_agent.run_cli(
        "agent", "chat", agent_b,
        "-m", "密码是什么？",
        "-cid", cid_a,
        "--no-stream",
        timeout=30.0,
    )
    steps.append(r2)

    # Either: non-zero exit (rejected), or: fresh conversation (no context leak)
    if r2.exit_code == 0:
        # Should NOT contain the secret from agent A
        scorer.assert_true(
            "alpha-bravo-42" not in r2.stdout,
            "foreign cid does not leak agent A's context to agent B",
        )
    else:
        scorer.assert_true(True, "foreign cid rejected with non-zero exit (expected)")

    det = scorer.result()
    await eval_case(
        "cid_expired_or_foreign", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "Agent A's conversation_id was used with Agent B. "
                "The system should either reject it or start a fresh conversation. "
                "It must NOT leak Agent A's context (secret: alpha-bravo-42) to Agent B."
            ),
        },
    )
    _assert_hard_only(det)


@pytest.mark.destructive
async def test_cid_reuse_after_gap(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict,
):
    """Conversation ID remains usable after a brief pause between turns."""
    agent_id = owned_agent_with_kn["agent_id"]
    steps = []
    cid = None

    # Turn 1: plant a fact
    r1, cid = await _chat_turn(cli_agent, agent_id, "记住：项目代号是 Phoenix-7", cid, retries=2)
    steps.append(r1)
    scorer.assert_exit_code(r1, 0, "T1 plant fact")

    # Turn 2: confirm it
    r2, cid = await _chat_turn(cli_agent, agent_id, "项目代号是什么？", cid)
    steps.append(r2)
    scorer.assert_exit_code(r2, 0, "T2 confirm fact")

    # Brief pause
    await asyncio.sleep(5)

    # Turn 3: reuse cid after gap
    r3, cid = await _chat_turn(cli_agent, agent_id, "再说一次，项目代号是什么？", cid)
    steps.append(r3)
    scorer.assert_exit_code(r3, 0, "T3 recall after gap")
    scorer.assert_true(
        "phoenix" in _stdout(r3) or "Phoenix" in r3.stdout or "7" in r3.stdout,
        "T3 recalls 'Phoenix-7' after pause",
    )

    det = scorer.result()
    await eval_case(
        "cid_reuse_after_gap", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "After planting fact 'Phoenix-7' and pausing 5 seconds, "
                "does T3 still recall the project codename via the same conversation_id?"
            ),
        },
    )
    _assert_hard_only(det)


# ---------------------------------------------------------------------------
# Concurrent sessions (Gap #8)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_concurrent_sessions_isolated(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict,
):
    """Two parallel conversations on the same agent should not leak context."""
    agent_id = owned_agent_with_kn["agent_id"]

    async def _session(fact: str, probe: str, label: str):
        """Run a 2-turn session: plant fact, then probe recall."""
        s_steps = []
        r1, cid = await _chat_turn(cli_agent, agent_id, f"记住：{fact}", retries=2)
        s_steps.append(r1)
        if r1.exit_code != 0 or not cid:
            return s_steps, None, cid
        r2, cid = await _chat_turn(cli_agent, agent_id, probe, cid)
        s_steps.append(r2)
        return s_steps, r2, cid

    # Run two sessions concurrently with distinct facts
    results = await asyncio.gather(
        _session("我的城市是北京", "我的城市是哪里？", "session_A"),
        _session("我的城市是上海", "我的城市是哪里？", "session_B"),
    )
    steps_a, probe_a, _ = results[0]
    steps_b, probe_b, _ = results[1]
    all_steps = [*steps_a, *steps_b]

    # Each session should recall its own fact
    if probe_a and probe_a.exit_code == 0:
        scorer.assert_exit_code(probe_a, 0, "session A probe")
        scorer.assert_true("北京" in _stdout(probe_a), "session A recalls 北京")
        # Should NOT contain session B's fact
        scorer.assert_true("上海" not in _stdout(probe_a), "session A does not leak 上海")

    if probe_b and probe_b.exit_code == 0:
        scorer.assert_exit_code(probe_b, 0, "session B probe")
        scorer.assert_true("上海" in _stdout(probe_b), "session B recalls 上海")
        scorer.assert_true("北京" not in _stdout(probe_b), "session B does not leak 北京")

    det = scorer.result()
    await eval_case(
        "concurrent_sessions_isolated", all_steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "Two concurrent sessions on the same agent. Session A planted '北京', "
                "Session B planted '上海'. Does each session recall only its own city? "
                "No cross-session context leakage?"
            ),
        },
    )
    _assert_hard_only(det)


# ---------------------------------------------------------------------------
# Stream + multi-turn combination (Gap #10)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_stream_multi_turn_with_knowledge(
    cli_agent: CliAgent, scorer: Scorer, eval_case,
    owned_agent_with_kn: dict,
):
    """3-turn stream conversation: plant fact + KN query + recall both."""
    agent_id = owned_agent_with_kn["agent_id"]
    kn_id = owned_agent_with_kn["kn_id"]
    ot_id = owned_agent_with_kn["ot_id"]

    ot_name, ground_truth = await _query_ground_truth(cli_agent, kn_id, ot_id)
    if not ot_name:
        pytest.skip("Cannot determine OT name for stream multi-turn test")

    steps = []
    cid = None

    # Turn 1 (stream): plant a user fact
    r1, cid = await _chat_turn_stream(cli_agent, agent_id, "记住：我的部门是数据平台组", cid)
    steps.append(r1)
    scorer.assert_exit_code(r1, 0, "stream T1 plant fact")
    scorer.assert_true(bool(cid), "stream T1 returns cid")

    if not cid:
        det = scorer.result()
        await eval_case("stream_multi_turn_with_knowledge", steps, det, module="adp/agent")
        assert det.passed, det.failures
        return

    # Turn 2 (stream): ask about KN data
    r2, cid = await _chat_turn_stream(
        cli_agent, agent_id,
        f"请查询知识网络中关于 {ot_name} 的数据。",
        cid,
    )
    steps.append(r2)
    scorer.assert_exit_code(r2, 0, "stream T2 knowledge query")

    # Turn 3 (stream): recall user fact + KN data
    r3, cid = await _chat_turn_stream(
        cli_agent, agent_id,
        f"总结一下：我的部门是什么？以及你刚才查到的 {ot_name} 数据有哪些？",
        cid,
    )
    steps.append(r3)
    scorer.assert_exit_code(r3, 0, "stream T3 recall")
    t3_out = _stdout(r3)

    # Check user fact recall
    scorer.assert_true(
        "数据平台" in t3_out,
        "stream T3 recalls user fact '数据平台组'",
    )
    # Check KN data presence (soft — judge does semantic eval)
    kn_hit = any(v.lower() in t3_out for v in ground_truth) if ground_truth else False
    if ground_truth:
        scorer.assert_true(kn_hit, "stream T3 includes KN ground truth")

    det = scorer.result()
    await eval_case(
        "stream_multi_turn_with_knowledge", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "3-turn stream conversation. T1 planted '数据平台组'. "
                f"T2 queried KN for '{ot_name}'. T3 asked to summarize both. "
                "Does T3 recall the department AND reference KN data? "
                f"Ground truth values: {ground_truth[:3]}"
            ),
        },
    )
    _assert_hard_only(det)
