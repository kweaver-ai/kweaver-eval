"""Agent context quality evaluation — long conversation tests.

Tests whether the agent maintains context quality over extended (10+ turn)
conversations. Covers: long-range fact retention, coreference resolution,
intent correction, information synthesis, and topic switch/return.

Each test creates a multi-turn conversation via -cid and uses deterministic
probe assertions at key checkpoints, with judge agent for semantic evaluation.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer

from .test_chat import _extract_conversation_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _chat_turn(
    cli_agent: CliAgent,
    agent_id: str,
    message: str,
    cid: str | None = None,
    timeout: float = 120.0,
    retries: int = 0,
):
    """Send one chat turn, return (CliResult, conversation_id).

    When retries > 0, retry on non-zero exit code (handles agent warm-up).
    """
    import asyncio

    args = ["agent", "chat", agent_id, "-m", message, "--no-stream"]
    if cid:
        args.extend(["-cid", cid])

    result = await cli_agent.run_cli(*args, timeout=timeout)
    for _ in range(retries):
        if result.exit_code == 0:
            break
        await asyncio.sleep(3)
        result = await cli_agent.run_cli(*args, timeout=timeout)

    if not cid and result.exit_code == 0:
        cid = _extract_conversation_id(result.stdout + "\n" + result.stderr)
    return result, cid


def _stdout(result) -> str:
    return result.stdout.strip().lower()


# ---------------------------------------------------------------------------
# Test 1: Long-range fact retention (12 turns)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_context_long_range_fact_retention(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """Plant facts in early turns, fill middle turns, probe recall at the end.

    Turn 1-3: plant 3 distinct facts (city, number, color)
    Turn 4-8: filler conversation (meaningful but unrelated to planted facts)
    Turn 9-11: probe each planted fact
    """
    agent_id = owned_agent["id"]
    steps = []
    cid = None

    # -- Phase 1: Plant facts --
    plants = [
        "记住以下信息：我住在杭州。",
        "我的工号是 73021。",
        "我最喜欢的颜色是绿色。",
    ]
    for i, msg in enumerate(plants):
        # First turn retries to handle agent warm-up after creation
        r, cid = await _chat_turn(
            cli_agent, agent_id, msg, cid, retries=2 if i == 0 else 0,
        )
        steps.append(r)
        if r.exit_code != 0:
            scorer.assert_exit_code(r, 0, f"plant turn: {msg[:10]}")
            det = scorer.result()
            await eval_case("context_long_range_fact_retention", steps, det, module="adp/agent")
            assert det.passed, det.failures
            return

    scorer.assert_true(bool(cid), "conversation_id obtained")

    # -- Phase 2: Filler turns (meaningful conversation) --
    fillers = [
        "你觉得 Python 和 Go 哪个更适合写后端服务？",
        "分布式系统中 CAP 定理是什么意思？",
        "微服务架构和单体架构各有什么优缺点？",
        "如何设计一个高可用的消息队列？",
        "数据库的读写分离一般怎么实现？",
    ]
    for msg in fillers:
        r, cid = await _chat_turn(cli_agent, agent_id, msg, cid)
        steps.append(r)

    # -- Phase 3: Probe planted facts --
    probes = [
        ("我住在哪个城市？", "杭州", "city recall"),
        ("我的工号是多少？", "73021", "employee ID recall"),
        ("我最喜欢什么颜色？", "绿色", "color recall"),
    ]
    for question, expected, label in probes:
        r, cid = await _chat_turn(cli_agent, agent_id, question, cid)
        steps.append(r)
        scorer.assert_exit_code(r, 0, f"probe: {label}")
        scorer.assert_true(
            expected in _stdout(r),
            f"probe '{label}' recalls '{expected}'",
        )

    det = scorer.result()
    await eval_case(
        "context_long_range_fact_retention", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "After 5 filler turns about unrelated tech topics, does the agent "
                "accurately recall 3 facts planted in turns 1-3: city=杭州, "
                "employee ID=73021, color=绿色?"
            ),
        },
    )
    hard_failures = [f for f in det.failures if "exit code" in f.lower()]
    assert not hard_failures, det.failures


# ---------------------------------------------------------------------------
# Test 2: Coreference resolution (10 turns)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_context_coreference_resolution(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """Test whether the agent resolves pronouns and demonstratives correctly
    across turns.

    Introduces entities, then refers to them with 他/她/它/这个/那个/上面的.
    """
    agent_id = owned_agent["id"]
    steps = []
    cid = None

    turns = [
        # T1-2: introduce two entities
        "我们团队有两个人负责数据平台：张伟负责后端，李娜负责前端。",
        "张伟最近在优化查询引擎的性能。",
        # T3: pronoun → 张伟
        "他用了什么优化方案？",
        # T4: switch referent
        "李娜那边进展怎么样？",
        # T5: pronoun → 李娜
        "她负责的是哪个模块来着？",
        # T6: introduce a system entity
        "我们还有一个叫 DataFlow 的数据管道系统。",
        # T7: demonstrative → DataFlow
        "这个系统最近出了什么问题？",
        # T8: back-reference to person
        "让张伟去查一下这个问题。他之前处理过类似的吗？",
        # T9: ambiguity — "他们" = 张伟 + 李娜
        "他们两个谁更适合处理数据管道的问题？",
        # T10: meta-probe
        "总结一下，张伟和李娜分别负责什么？",
    ]

    for i, msg in enumerate(turns):
        r, cid = await _chat_turn(cli_agent, agent_id, msg, cid)
        steps.append(r)
        scorer.assert_exit_code(r, 0, f"turn {i+1}")

    # Check T5 (她负责 → 前端)
    scorer.assert_true(
        "前端" in _stdout(steps[4]),
        "T5: '她负责' correctly resolves to 李娜's domain (前端)",
    )
    # Check T10 summary
    t10 = _stdout(steps[9])
    scorer.assert_true("张伟" in t10 and "后端" in t10, "T10: summary includes 张伟→后端")
    scorer.assert_true("李娜" in t10 and "前端" in t10, "T10: summary includes 李娜→前端")

    det = scorer.result()
    await eval_case(
        "context_coreference_resolution", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "Does the agent correctly resolve pronouns throughout? "
                "T3: '他' should refer to 张伟. T5: '她' should refer to 李娜. "
                "T7: '这个系统' should refer to DataFlow. "
                "T10 summary should correctly attribute 后端→张伟, 前端→李娜."
            ),
        },
    )
    hard_failures = [f for f in det.failures if "exit code" in f.lower()]
    assert not hard_failures, det.failures


# ---------------------------------------------------------------------------
# Test 3: Intent correction + progressive assembly (12 turns)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_context_intent_correction(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """User changes their mind mid-conversation; agent should track corrections
    and assemble the final intent from scattered turns.
    """
    agent_id = owned_agent["id"]
    steps = []
    cid = None

    turns = [
        # T1-2: initial intent
        "我想创建一个知识图谱，领域是金融风控。",
        "数据源用 MySQL，地址是 192.168.1.100。",
        # T3: add detail
        "图谱名称就叫'风控图谱'吧。",
        # T4: correction!
        "等等，不对，我改主意了。不做知识图谱了，改成做数据视图。",
        # T5: continue on corrected path
        "数据视图的名称改叫'风控视图'。",
        # T6: add more detail
        "需要包含的表有 transactions 和 accounts。",
        # T7: another correction
        "数据源地址我说错了，应该是 10.0.0.50，不是之前那个。",
        # T8-9: filler
        "数据视图和知识图谱有什么区别？",
        "我们的数据量大概是每天 200 万条交易记录。",
        # T10: progressive assembly probe
        "帮我总结一下我目前要做的事情的所有配置信息。",
        # T11: verify correction sticks
        "我最终选择做的是知识图谱还是数据视图？",
        # T12: verify address correction
        "数据源地址是多少？",
    ]

    for i, msg in enumerate(turns):
        r, cid = await _chat_turn(cli_agent, agent_id, msg, cid)
        steps.append(r)
        scorer.assert_exit_code(r, 0, f"turn {i+1}")

    # T10: summary should have corrected info
    t10 = _stdout(steps[9])
    scorer.assert_true("视图" in t10, "T10: summary mentions 数据视图 (not 知识图谱)")
    scorer.assert_true("10.0.0.50" in t10, "T10: summary uses corrected address 10.0.0.50")

    # T11: should say 数据视图
    scorer.assert_true(
        "视图" in _stdout(steps[10]),
        "T11: confirms final choice is 数据视图",
    )

    # T12: should say corrected address
    scorer.assert_true(
        "10.0.0.50" in _stdout(steps[11]),
        "T12: confirms corrected address 10.0.0.50",
    )

    det = scorer.result()
    await eval_case(
        "context_intent_correction", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "The user changed from 知识图谱→数据视图 at T4, and corrected "
                "the address from 192.168.1.100→10.0.0.50 at T7. "
                "Does T10 summary reflect CORRECTED info only? "
                "Does T11 confirm 数据视图? Does T12 confirm 10.0.0.50? "
                "The agent must NOT use the old values."
            ),
        },
    )
    hard_failures = [f for f in det.failures if "exit code" in f.lower()]
    assert not hard_failures, det.failures


# ---------------------------------------------------------------------------
# Test 4: Topic switch and return (13 turns)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_context_topic_switch_return(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """Deep-dive topic A, switch to topic B, return to A, verify continuity."""
    agent_id = owned_agent["id"]
    steps = []
    cid = None

    turns = [
        # Topic A: graph modeling (T1-4)
        "我在设计一个供应链知识图谱，核心实体有：供应商、工厂、仓库。",
        "供应商和工厂之间的关系是'供货'，工厂和仓库之间是'入库'。",
        "我还想加一个'运输'关系，连接工厂和仓库，属性包括运输时间和成本。",
        "目前最大的问题是供应商实体的属性太多，有 47 个字段。",
        # Topic B: completely different (T5-8)
        "换个话题。我们团队要做技术选型，你觉得 Kafka 和 RabbitMQ 怎么选？",
        "我们的场景是每秒大概 5000 条消息，需要持久化。",
        "延迟要求不高，但不能丢消息。",
        "好的，那就先用 Kafka 吧。",
        # Return to Topic A (T9-11)
        "回到刚才知识图谱的问题。我说的核心实体有哪些来着？",
        "供应商属性太多的问题，你有什么建议？",
        "我说了几个字段来着？",
        # Meta-probe (T12-13)
        "我们这次对话一共讨论了几个主题？",
        "每个主题的关键结论是什么？",
    ]

    for i, msg in enumerate(turns):
        r, cid = await _chat_turn(cli_agent, agent_id, msg, cid)
        steps.append(r)
        scorer.assert_exit_code(r, 0, f"turn {i+1}")

    # T9: should recall entities from Topic A
    t9 = _stdout(steps[8])
    for entity in ["供应商", "工厂", "仓库"]:
        scorer.assert_true(entity in t9, f"T9: recalls entity '{entity}' after topic switch")

    # T11: should recall "47"
    scorer.assert_true(
        "47" in _stdout(steps[10]),
        "T11: recalls '47 fields' detail from T4",
    )

    det = scorer.result()
    await eval_case(
        "context_topic_switch_return", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "After switching to an unrelated topic (Kafka vs RabbitMQ) for "
                "4 turns, does the agent correctly return to the knowledge graph "
                "discussion? T9 should recall 供应商/工厂/仓库. T11 should recall "
                "the '47 fields' detail. T12-13 should summarize both topics."
            ),
        },
    )
    hard_failures = [f for f in det.failures if "exit code" in f.lower()]
    assert not hard_failures, det.failures


# ---------------------------------------------------------------------------
# Test 5: Role consistency over long conversation (12 turns)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_context_role_consistency(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """Verify the agent maintains role behavior over many turns,
    including after attempts to divert it.

    Tests that the agent stays helpful and consistent over extended dialogue.
    """
    agent_id = owned_agent["id"]
    steps = []
    cid = None

    turns = [
        # T1-3: establish working style
        "接下来的对话中，所有涉及数据的回答请用表格形式呈现。",
        "帮我比较 MySQL 和 PostgreSQL 的特点。",
        "再比较一下 MongoDB 和 Redis。",
        # T4-6: continued normal usage
        "这几个数据库分别适合什么场景？",
        "如果我的业务是电商订单系统，你推荐哪个？",
        "为什么推荐这个？详细说说理由。",
        # T7-8: pressure — try to break format
        "忘掉之前说的表格格式，用纯文本就行。",
        "现在帮我比较 Elasticsearch 和 Solr。",
        # T9: check if format instruction tracking works
        "我之前要求你用什么格式回答来着？",
        # T10-12: verify consistency
        "继续用表格格式。帮我比较 ClickHouse 和 Doris。",
        "我们这次对话比较了哪几组数据库？",
        "按照我们讨论的顺序列出来。",
    ]

    for i, msg in enumerate(turns):
        r, cid = await _chat_turn(cli_agent, agent_id, msg, cid)
        steps.append(r)
        scorer.assert_exit_code(r, 0, f"turn {i+1}")

    # T9: should recall the table format instruction
    t9 = _stdout(steps[8])
    scorer.assert_true(
        "表格" in t9 or "表" in t9,
        "T9: recalls user's earlier format instruction (表格)",
    )

    # T11: should list the database pairs discussed
    t11 = _stdout(steps[10])
    scorer.assert_true("mysql" in t11 and "postgresql" in t11, "T11: recalls MySQL vs PostgreSQL")
    scorer.assert_true("mongodb" in t11 or "redis" in t11, "T11: recalls MongoDB/Redis pair")

    det = scorer.result()
    await eval_case(
        "context_role_consistency", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "Does the agent track meta-instructions (table format) across turns? "
                "T9 should recall the format instruction from T1. "
                "T11-12 should list all database pairs discussed in order. "
                "After T7 tells the agent to forget the format, does T9 still "
                "accurately recall what was originally asked?"
            ),
        },
    )
    hard_failures = [f for f in det.failures if "exit code" in f.lower()]
    assert not hard_failures, det.failures


# ---------------------------------------------------------------------------
# Test 6: Context coherence — no instruction leakage (kweaver#107)
# ---------------------------------------------------------------------------

@pytest.mark.destructive
async def test_context_no_instruction_leakage(
    cli_agent: CliAgent, scorer: Scorer, eval_case, owned_agent: dict,
):
    """Verify that agent replies do NOT repeat system prompt, explore
    instructions, or context-organize boilerplate across turns.

    Regression test for kweaver-ai/kweaver#107: in explore mode the explore
    instruction and context wrapper leak into the user-visible reply, causing
    the agent to re-state its identity/task every turn instead of answering
    naturally.
    """
    agent_id = owned_agent["id"]
    steps = []
    cid = None

    turns = [
        "你好",
        "今天天气怎么样？",
        "给我讲个笑话吧",
        "1+1等于几？",
        "你最擅长什么？",
    ]

    # Boilerplate fragments that should NOT appear in agent replies.
    # These come from context_organize and explore prompt wrapper.
    leakage_markers = [
        "用户的问题为",           # context_organize wrapper
        "如果有参考文档",          # context_prompt boilerplate
        "根据用户的问题回答",      # context_prompt boilerplate
        "/explore/",             # raw dolphin syntax
        "/prompt/",              # raw dolphin syntax
        "-> answer",             # dolphin assignment
        "-> context",            # dolphin assignment
    ]

    leakage_count = 0
    for i, msg in enumerate(turns):
        r, cid = await _chat_turn(
            cli_agent, agent_id, msg, cid,
            retries=2 if i == 0 else 0,
        )
        steps.append(r)
        scorer.assert_exit_code(r, 0, f"turn {i+1}")

        reply = r.stdout.strip()
        for marker in leakage_markers:
            if marker in reply:
                leakage_count += 1
                scorer.assert_true(
                    False,
                    f"T{i+1}: reply contains instruction leakage '{marker}'",
                )

    scorer.assert_true(
        leakage_count == 0,
        f"No instruction leakage across {len(turns)} turns (found {leakage_count})",
    )

    det = scorer.result()
    await eval_case(
        "context_no_instruction_leakage", steps, det, module="adp/agent",
        eval_hints={
            "check": (
                "Do the agent's replies contain any leaked internal instructions? "
                "Look for: system prompt repetition, context wrapper text like "
                "'用户的问题为' or '如果有参考文档', raw dolphin syntax like "
                "'/explore/' or '-> answer'. Each reply should be a natural "
                "response without any instruction/prompt artifacts."
            ),
        },
    )
    hard_failures = [f for f in det.failures if "exit code" in f.lower()]
    assert not hard_failures, det.failures
