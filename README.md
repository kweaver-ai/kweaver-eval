# kweaver-eval

Harness engineering feedback loop: dual-scoring (deterministic + agent judge) acceptability tests for the KWeaver system.

## Overview

kweaver-eval validates the entire KWeaver stack (SDK CLI, platform API, harness/skills) as an independent verification project. It serves as the **Verify** function in KWeaver's [harness engineering](https://openai.com/index/harness-engineering/) feedback loop.

Every test case produces two scoring dimensions:

| Dimension | What it checks | When it applies |
|-----------|---------------|-----------------|
| **Deterministic** | exit code, JSON structure, field values | Every case |
| **Agent Judge** | Semantic evaluation with severity grading | Opt-in per case |

## Quick Start

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Edit .env — all config keys are declared there.
# Sensitive values (passwords, API keys) go in ~/.env.secrets.

# 3. Set credentials (not committed to git)
cat >> ~/.env.secrets << 'EOF'
export KWEAVER_USERNAME=you@example.com
export KWEAVER_PASSWORD=your-password
export KWEAVER_TEST_DB_HOST=10.0.0.1
export KWEAVER_TEST_DB_USER=root
export KWEAVER_TEST_DB_PASS=your-db-password
EOF

# 4. Authenticate CLI (-k for self-signed cert)
kweaver auth login https://dip.aishu.cn -u <user> -p <pass> -k

# 5. Run tests
make test              # Collect-only (verify setup, no network)
make test-at           # Acceptance tests against live service
make test-agent        # Agent module only
make test-bkn          # BKN module only
make test-vega         # Vega module only
make test-at-full      # AT + agent judge scoring
```

### Configuration

`.env` is the **single source of truth** for all config keys. Values
resolve in priority order: `shell env` > `~/.env.secrets` > `.env`.

| File | What goes here | Git tracked |
|------|---------------|-------------|
| `.env` | All keys with defaults (URLs, flags, DB type/port) | Yes |
| `~/.env.secrets` | Sensitive values (passwords, API keys) | No |
| `~/.kweaver/` | CLI auth tokens (auto-managed by `kweaver auth login`) | No |

BKN and Vega lifecycle tests share the same `db_credentials` fixture
(`tests/adp/conftest.py`). Vega uses a dedicated `kweaver_eval_test`
database to avoid polluting existing data.

## Test Coverage Summary

| Module | Total | Pass | Known Bug | Wait Env | Wait CLI |
|--------|-------|------|-----------|----------|----------|
| Agent | 33 | 33 | 0 | 0 | 0 |
| BKN | 26 | 23 | 3 | 0 | 0 |
| Vega (+ DS + Dataview) | 27 | 19 | 6 | 2 | 0 |
| Dataflow | 14 | 0 | 0 | 0 | 14 |
| Context Loader | 3 | 3 | 0 | 0 | 0 |
| Token Refresh | 1 | 1 | 0 | 0 | 0 |
| **Total** | **104** | **79 (76%)** | **9** | **2** | **14** |

### Agent (Decision Agent)

#### Read & CRUD

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Agent List | `agent list` | `test_agent_list` | pass |
| Agent Get | `agent get` | `test_agent_get` | pass (destructive) |
| Agent Get by Key | `agent get-by-key` | `test_agent_get_by_key` | pass (destructive) |
| Agent CRUD Lifecycle | `agent create/get/update/delete` | `test_agent_crud_lifecycle` | pass (destructive) |
| Config Update | `agent update --system-prompt` | `test_agent_config_update` | pass (destructive) |
| Publish/Unpublish | `agent publish/unpublish` | `test_agent_publish_unpublish` | pass (destructive) |

#### Chat

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Chat Single Turn | `agent chat -m ... --no-stream` | `test_agent_chat_single_turn` | pass |
| Chat Multi Turn | `agent chat -m ... -cid ...` | `test_agent_chat_multi_turn` | pass |
| Chat Streaming | `agent chat -m ... --stream` | `test_agent_chat_stream` | pass |

#### Chat Robustness

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Stream Chunk Integrity | `agent chat --stream` vs `--no-stream` | `test_stream_chunk_integrity` | pass (destructive) |
| Stream with Knowledge | `agent chat --stream` | `test_stream_with_knowledge_retrieval` | pass (destructive) |
| Long Message Input | `agent chat -m <2KB+>` | `test_long_message_input` | pass (destructive) |
| Special Chars in Query | `agent chat -m <special chars>` | `test_special_chars_in_query` | pass (destructive) |
| Knowledge Multi-Turn | `agent chat -cid ...` (3-turn drill-down) | `test_knowledge_multi_turn_drill_down` | pass (destructive) |
| Expired/Foreign CID | `agent chat -cid <foreign>` | `test_cid_expired_or_foreign` | pass (destructive) |
| CID Reuse After Gap | `agent chat -cid ...` | `test_cid_reuse_after_gap` | pass (destructive) |
| Concurrent Sessions | `agent chat -cid ...` (parallel) | `test_concurrent_sessions_isolated` | pass (destructive) |
| Stream Multi-Turn + KN | `agent chat --stream -cid ...` (3-turn) | `test_stream_multi_turn_with_knowledge` | pass (destructive) |

#### Context Quality

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Long-Range Fact Retention | `agent chat -cid ...` (12-turn) | `test_context_long_range_fact_retention` | pass (destructive) |
| Coreference Resolution | `agent chat -cid ...` (10-turn) | `test_context_coreference_resolution` | pass (destructive) |
| Intent Correction | `agent chat -cid ...` (12-turn) | `test_context_intent_correction` | pass (destructive) |
| Topic Switch & Return | `agent chat -cid ...` (13-turn) | `test_context_topic_switch_return` | pass (destructive) |
| Role Consistency | `agent chat -cid ...` (12-turn) | `test_context_role_consistency` | pass (destructive) |
| No Instruction Leakage | `agent chat -cid ...` (5-turn) | `test_context_no_instruction_leakage` | pass (destructive) |

#### Sessions & Trace

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Sessions | `agent sessions` | `test_agent_sessions` | pass |
| History | `agent history` | `test_agent_history` | pass |
| Trace | `agent trace` | `test_agent_trace` | pass |

#### Error Paths

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Get Invalid ID | `agent get <invalid>` | `test_agent_get_invalid_id` | pass |
| Chat Invalid ID | `agent chat <invalid>` | `test_agent_chat_invalid_id` | pass |
| Delete Invalid ID | `agent delete <invalid>` | `test_agent_delete_invalid_id` | pass |
| Get by Invalid Key | `agent get-by-key <invalid>` | `test_agent_get_by_key_invalid` | pass |
| Chat Invalid CID | `agent chat -cid <invalid>` | `test_agent_chat_invalid_cid` | pass (destructive) |
| Create Duplicate Key | `agent create --key <dup>` | `test_agent_create_duplicate_key` | pass (destructive) |

### BKN (Business Knowledge Network)

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| BKN List | `bkn list` | `test_bkn_list` | pass |
| BKN Get | `bkn get` | `test_bkn_get` | pass |
| BKN Export | `bkn export` | `test_bkn_export` | pass |
| BKN Search | `bkn search` | `test_bkn_search` | known_bug |
| BKN Stats | `bkn stats` | `test_bkn_stats` | pass |
| BKN Create & Delete | `bkn create / delete` | `test_bkn_create_and_delete` | pass (destructive) |
| BKN Update | `bkn update` | `test_bkn_update` | pass (destructive) |
| Object Type List | `bkn object-type list` | `test_bkn_object_type_list` | pass |
| Object Type Query | `bkn object-type query` | `test_bkn_object_type_query` | pass |
| Object Type Properties | `bkn object-type query --properties` | `test_bkn_object_type_properties` | pass |
| Object Type Get | `bkn object-type get` | `test_object_type_get` | pass |
| Object Type Update | `bkn object-type update` | `test_object_type_update_property_cycle` | known_bug (destructive) |
| Object Type Create & Delete | `bkn object-type create / delete` | `test_object_type_create_and_delete` | pass (destructive) |
| Relation Type List | `bkn relation-type list` | `test_bkn_relation_type_list` | pass |
| Relation Type CRUD | `bkn relation-type create/update/delete` | `test_relation_type_update` | pass (destructive) |
| Action Type List | `bkn action-type list` | `test_bkn_action_type_list` | pass |
| Action Type Query | `bkn action-type query` | `test_bkn_action_type_query` | pass |
| Action Execute & Log | `bkn action-type execute` | `test_bkn_action_execute_and_log` | pass (destructive) |
| Action Log Cancel | `bkn action-log cancel` | `test_bkn_action_log_cancel` | pass (destructive) |
| Action Invalid Identity | `bkn action-type execute` (error) | `test_bkn_action_execute_invalid_identity` | known_bug |
| Build | `bkn build` | `test_bkn_build_no_wait` | pass (destructive) |
| Subgraph | `bkn subgraph` | `test_bkn_subgraph_basic` | pass |
| Version Pull | `bkn pull` | `test_bkn_pull` | pass |
| Version Validate | `bkn validate` | `test_bkn_validate_after_pull` | pass |
| Version Push | `bkn push` | `test_bkn_push_after_pull` | pass (destructive) |
| Full Lifecycle | ds connect -> bkn create -> build -> query -> cleanup | `test_bkn_full_lifecycle` | pass (destructive) |

**Known Bugs:**
- **action execute invalid identity** ([adp#442](https://github.com/kweaver-ai/adp/issues/442)): returns 500 instead of 400 for invalid `_instance_identities`.
- **bkn search** — returns markdown-wrapped output (backtick-quoted) instead of clean JSON when vectorizer is enabled.
- **object-type update property cycle** — `UpdateObjectType` missing Branch assignment ([adp#445](https://github.com/kweaver-ai/adp/issues/445) fixed relation-type but object-type handler has identical unfiled bug).

### Vega (Metadata Engine + DS + Dataview)

#### Vega Core

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Health | `vega health` | `test_vega_health` | pass |
| Stats | `vega stats` | `test_vega_stats` | pass |
| Inspect | `vega inspect` | `test_vega_inspect` | pass |
| Catalog List | `vega catalog list` | `test_vega_catalog_list` | pass |
| Catalog Get | `vega catalog get` | `test_vega_catalog_get` | pass |
| Catalog Health | `vega catalog health` | `test_vega_catalog_health` | pass |
| Catalog Test Connection | `vega catalog test-connection` | `test_vega_catalog_test_connection` | pass |
| Catalog Resources | `vega catalog resources` | `test_vega_catalog_resources` | known_bug |
| Catalog Discover | `vega catalog discover` | `test_vega_catalog_discover` | pass |
| Catalog Lifecycle | `vega catalog create/update/delete` | `test_vega_catalog_lifecycle` | pass (destructive) |
| Connector Type List | `vega connector-type list` | `test_vega_connector_type_list` | pass |
| Connector Type Get | `vega connector-type get` | `test_vega_connector_type_get` | known_bug |
| Resource List | `vega resource list` | `test_vega_resource_list` | pass |
| Resource Get | `vega resource get` | `test_vega_resource_get` | pass |
| Resource List All | `vega resource list-all` | `test_vega_resource_list_all` | known_bug |
| Discovery Task List | `vega discovery-task list` | `test_vega_discovery_task_list` | known_bug |
| Discovery Task Get | `vega discovery-task get` | `test_vega_discovery_task_get` | known_bug |
| Dataset Lifecycle | `vega resource create/update-docs/build` | `test_vega_dataset_lifecycle` | wait_for_env |
| Query Execute | `vega resource query` (cross-resource) | `test_vega_query_execute` | wait_for_env |

#### Datasource (DS)

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| DS List | `ds list` | `test_datasource_list` | pass |
| DS Get | `ds get` | `test_datasource_get` | pass |
| DS Tables | `ds tables` | `test_datasource_tables` | pass |
| DS Connect & Delete | `ds connect / delete` | `test_datasource_connect_and_delete` | known_bug |

#### Dataview

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Dataview List | `dataview list` | `test_dataview_list` | pass |
| Dataview Get | `dataview get` | `test_dataview_get` | pass |
| Dataview Find | `dataview find` | `test_dataview_find` | pass |
| Dataview Query | `dataview query` | `test_dataview_query` | pass |

**Known Bugs:**
- **connector-type get 404** ([adp#427](https://github.com/kweaver-ai/adp/issues/427)): handler reads `c.Param("id")` but route defines `:type`.
- **discovery-task list 404** ([adp#428](https://github.com/kweaver-ai/adp/issues/428)): handler requires catalog_id but route has no path param.
- **discovery-task get** — `discovery-task` subcommand removed from SDK; use `catalog discover --wait` instead.
- **catalog resources 500** ([adp#447](https://github.com/kweaver-ai/adp/issues/447)): `FilterResources` sends empty resources array to Hydra when catalog has no resources.
- **resource list-all 404** ([adp#448](https://github.com/kweaver-ai/adp/issues/448)): `ListResources` handler returns 404 instead of 400 when `resource_type` param missing.
- **ds delete 500**: backend database error when deleting datasource on dip.aishu.cn.

### Context Loader

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| BKN List (via CL) | `context-loader bkn list` | `test_context_loader_bkn_list` | pass |
| BKN Export (via CL) | `context-loader bkn export` | `test_context_loader_bkn_export` | pass |
| OT Query (via CL) | `context-loader object-type query` | `test_context_loader_object_type_query` | pass |

### Dataflow

> **Note:** Dataflow CLI is implemented in the TypeScript SDK with **4 core commands**.
> See [`packages/typescript/src/commands/dataflow.ts`](../kweaver-sdk/packages/typescript/src/commands/dataflow.ts).
>
> **Implemented commands:**
> - `kweaver dataflow list` — List all dataflows
> - `kweaver dataflow run <dagId> --file <path> | --url <url> --name <filename>` — Trigger execution
> - `kweaver dataflow runs <dagId> [--since <date>]` — List run history
> - `kweaver dataflow logs <dagId> <instanceId> [--detail]` — Show execution logs
>
> **To activate tests**, ensure the TypeScript CLI is installed:
> ```bash
> cd kweaver-sdk/packages/typescript
> npm install && npx tsc -p tsconfig.json && npm link
> ```

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Dataflow List | `dataflow list` | `test_dataflow_list` | ✅ Implemented |
| Dataflow Run (local file) | `dataflow run <dagId> --file <path>` | `test_dataflow_run_with_url` | ✅ Implemented |
| Dataflow Run (remote URL) | `dataflow run <dagId> --url <url> --name <name>` | `test_dataflow_run_with_url` | ✅ Implemented |
| Dataflow Runs History | `dataflow runs <dagId> [--since <date>]` | `test_dataflow_runs` | ✅ Implemented |
| Dataflow Logs | `dataflow logs <dagId> <instanceId> [--detail]` | `test_dataflow_logs` | ✅ Implemented |


### Token Refresh

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Auto Token Refresh | `bkn list` + `auth status` | `test_token_auto_refresh` | pass |

## Project Structure

```
lib/
├── agents/                 # Pluggable agent abstraction
│   ├── base.py             # BaseAgent ABC with role prompt loading
│   ├── cli_agent.py        # Executes kweaver CLI as subprocess
│   └── judge_agent.py      # Evaluates results via Claude API
├── types.py                # Severity, CliResult, CaseResult, etc.
├── scorer.py               # Deterministic assertion helpers
├── recorder.py             # Timestamped run history
├── feedback.py             # Cross-run feedback tracking
└── reporter.py             # Aggregate report generation
roles/                      # Judge role prompts (soul.md + instructions.md)
tests/
├── adp/                    # ADP product line
│   ├── agent/              # Agent: CRUD, chat, sessions, history, trace, publish
│   ├── bkn/                # BKN: list, export, search, schema, actions, lifecycle
│   ├── vega/               # Vega: health, catalogs, resources, DS, dataview, lifecycle
│   ├── context_loader/     # Context Loader / MCP
│   ├── dataflow/           # Dataflow: list, get, validate, run, lifecycle
│   └── execution_factory/  # Execution Factory (pending CLI)
test-result/
├── runs/<timestamp>/       # Per-run results, logs, reports
└── feedback.json           # Persistent cross-run issue tracker
```

## Running Tests

```bash
make test                # Collect-only (no external deps)
make test-at             # Acceptance tests against live service
make test-at-full        # AT + agent judge scoring
make test-smoke          # Minimal health check (smoke markers)
make test-report         # Full run with aggregate report
make lint                # Run ruff check + pyright
make ci                  # Lint + acceptance tests

# Per-module
make test-agent          # Agent module only
make test-bkn            # BKN module only
make test-vega           # Vega module only (includes DS + Dataview)
make test-context-loader # Context Loader module only
make test-dataflow       # Dataflow module only
```

Lifecycle tests (create/delete resources) require `EVAL_RUN_DESTRUCTIVE=1` and appropriate DB credentials.

## Architecture

### Agent Design

Borrowed from [shadowcoder](https://github.com/kweaver-ai/shadowcoder)'s agent abstraction:

- **BaseAgent** — abstract interface with pluggable transports
- **CliAgent** — executes `kweaver` CLI commands as subprocess
- **JudgeAgent** — evaluates results via Claude API with role prompts

### Severity Grading

Agent judge findings use a four-level severity scale:

| Severity | Meaning | Impact |
|----------|---------|--------|
| CRITICAL | System broken | Case fails |
| HIGH | Major feature degraded | Case fails |
| MEDIUM | Minor issue | Warning |
| LOW | Cosmetic | Warning |

### Role Prompts

Each judge role is defined by `soul.md` (persona) + `instructions.md` (task). Search order: project-level, user-level, built-in.

### Feedback Tracking

Issues are tracked across runs in `test-result/feedback.json`:
- `times_seen >= 3` — flagged as persistent
- `times_seen >= 5` — requires human attention
- Auto-resolved after consecutive absences

## Environment Variables

All config keys are declared in `.env.example`. Key groups:

| Group | Variables | Required |
|-------|-----------|----------|
| Platform | `KWEAVER_BASE_URL`, `KWEAVER_BUSINESS_DOMAIN`, `NODE_TLS_REJECT_UNAUTHORIZED` | Yes |
| Auth | `KWEAVER_USERNAME`, `KWEAVER_PASSWORD` | Yes (in ~/.env.secrets) |
| Database | `KWEAVER_TEST_DB_HOST/PORT/USER/PASS/NAME/TYPE` | For lifecycle tests |
| Feature flags | `EVAL_AGENT_JUDGE`, `EVAL_REPORT` | No |
| API keys | `ANTHROPIC_API_KEY` | When EVAL_AGENT_JUDGE=1 |

## TODO

### P0 — 阻塞测试准确性

- [ ] Vega `discovery-task` 子命令已从 SDK 移除，相关测试需迁移到 `catalog discover --wait`
- [ ] BKN object-type update known_bug 需单独提 issue（与 adp#445 同源但未归档）
- [ ] BKN search known_bug 需提 issue 跟踪（markdown-wrapped output）

### P1 — 测试覆盖缺口

- [ ] Vega dataset lifecycle / query execute 依赖环境未就绪（wait_for_env），需跟进环境部署
- [ ] Execution Factory 测试用例（待 CLI 支持）
- [ ] `tests/agent/test_full_flow_eval.py` 未纳入任何 make target，需归入测试流程

### P2 — 质量改进

- [ ] Agent context quality 测试依赖 agent judge 评分，考虑补充 deterministic 断言兜底
- [ ] Dataflow 已有测试但未标记 `smoke`，需补充冒烟标记

## License

See [LICENSE](LICENSE).
