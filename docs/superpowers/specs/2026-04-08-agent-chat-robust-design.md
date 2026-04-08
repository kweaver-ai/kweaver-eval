# Agent Chat Robustness Tests — Design Spec

## Goal

Supplement agent test coverage for **usability and robustness** (gaps #1, #2, #3, #8, #10 from coverage audit). All tests integrate with BKN knowledge network and context loader — no isolated agent-only testing.

## Non-Goals

- Management/admin features (config deep fields, list filtering, batch ops)
- Modifying existing test files (`test_chat.py`, `test_context_quality.py`)

---

## Fixture: `owned_agent_with_kn`

**Scope:** session  
**Returns:** `dict` with keys `agent_id`, `kn_id`, `ot_id`  
**Location:** `tests/adp/agent/conftest.py`

### Logic

1. **Discover KN** — reuse `_find_kn_with_object_types()` pattern from bkn conftest: iterate `bkn list`, find a KN with queryable OTs (probe `object-type query` to skip orphans). Read-only — never modify discovered KN.
2. **Fallback: create KN** — if no existing KN found, use `db_credentials` to `ds connect` + `bkn create-from-ds` + `bkn build --wait`. New resources use `eval_` prefix for cleanup.
3. **Create agent** — call `_build_explore_config()` with the KN bound into `data_source.kg` and `data_source.knowledge_network`. Create via `agent create --config`.
4. **Cleanup** — agent cleaned by existing `cleanup_eval_agent_resources`. Newly created KN/DS cleaned by extending cleanup or relying on bkn cleanup pattern.

### Agent Config Additions (vs plain `owned_agent`)

```python
config["data_source"]["kg"] = [{"id": kn_id, "name": kn_name}]
config["data_source"]["knowledge_network"] = [{"id": kn_id, "name": kn_name}]
```

System prompt adjusted to instruct agent to use knowledge network data when answering.

---

## Test File: `test_chat_robust.py`

**Location:** `tests/adp/agent/test_chat_robust.py`  
**Marker:** `@pytest.mark.destructive` (creates agent + conversations)  
**Dependencies:** `owned_agent_with_kn` fixture

### Test Cases

#### Stream Robustness (Gap #1)

| Test | Description | Assertions |
|------|-------------|------------|
| `test_stream_chunk_integrity` | Same question asked via `--stream` and `--no-stream`, compare results | Both exit 0; both non-empty; judge evaluates semantic equivalence |
| `test_stream_with_knowledge_retrieval` | Ask about data that exists in KN via `--stream` | Exit 0; output contains KN ground-truth value (pre-queried from OT) |

#### Multi-turn Boundaries (Gap #2)

| Test | Description | Assertions |
|------|-------------|------------|
| `test_long_message_input` | Send >2KB message (long JSON-like structured text) | Exit 0; non-empty response; no timeout |
| `test_special_chars_in_query` | Message with SQL keywords, quotes, newlines, emoji, angle brackets | Exit 0; non-empty response; no crash |
| `test_knowledge_multi_turn_drill_down` | Turn 1: ask general question about KN data; Turn 2-3: drill into specific fields/values | Exit 0 all turns; final turn contains specific field value from KN |

#### CID Edge Cases (Gap #3)

| Test | Description | Assertions |
|------|-------------|------------|
| `test_cid_expired_or_foreign` | Create conversation on agent A, use its cid to chat agent B (or non-existent agent) | Non-zero exit OR fresh conversation (no hang, no crash) |
| `test_cid_reuse_after_gap` | Chat 2 turns, then send 3rd turn with same cid after brief pause | Exit 0; context from earlier turns retained |

#### Concurrent Sessions (Gap #8)

| Test | Description | Assertions |
|------|-------------|------------|
| `test_concurrent_sessions_isolated` | Open two conversations in parallel (asyncio.gather), each plants a unique fact, then cross-probe | Each session recalls its own fact; neither session leaks the other's fact |

#### Stream + Multi-turn (Gap #10)

| Test | Description | Assertions |
|------|-------------|------------|
| `test_stream_multi_turn_with_knowledge` | 3-turn conversation in `--stream` mode with cid, involving KN data retrieval | All turns exit 0; cid maintained; turn 3 recalls info from turn 1 + contains KN data |

---

## Assertion Strategy

### Ground Truth from KN

Before chat tests, query the KN's first OT to get real instance data:

```python
probe = await cli_agent.run_cli("bkn", "object-type", "query", kn_id, ot_id, "--limit", "3")
# Extract a concrete field value as ground truth for knowledge-grounded assertions
```

This value becomes the expected substring in agent replies when asking about that data.

### Hard vs Soft

- **Hard:** exit_code, non-empty output, no timeout/crash — `assert det.passed`
- **Soft:** content matching (KN value in reply, context recall) — `_assert_hard_only(det)` pattern, deferred to judge agent for semantic eval
- **Stream equivalence:** judge agent compares stream vs no-stream answers

### Concurrent Test

Use `asyncio.gather` to run two `_chat_turn` sequences in parallel. Each uses its own cid. Assertions check isolation — session A's fact should not appear in session B's probe response.

---

## File Structure (no changes to existing files)

```
tests/adp/agent/
  conftest.py          # + owned_agent_with_kn fixture
  test_chat.py         # unchanged
  test_context_quality.py  # unchanged
  test_chat_robust.py  # NEW — all 10 test cases above
  ...
```

---

## Dependencies & Preconditions

- Environment must have at least one KN with queryable OTs, OR `db_credentials` configured for fallback creation
- `llm_id` fixture (existing) for agent model selection
- All new tests marked `destructive` — only run when `EVAL_RUN_DESTRUCTIVE=1`
