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

| Module | Total | Pass | Known Bug | Wait Env |
|--------|-------|------|-----------|----------|
| Agent | 11 | 10 | 1 | 0 |
| BKN | 26 | 25 | 1 | 0 |
| Vega (+ DS + Dataview) | 27 | 19 | 6 | 2 |
| Context Loader | 3 | 3 | 0 | 0 |
| **Total** | **67** | **57 (85%)** | **8** | **2** |

### Agent (Decision Agent)

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Agent List | `agent list` | `test_agent_list` | pass |
| Agent Get | `agent get` | `test_agent_get` | pass (destructive) |
| Agent Get by Key | `agent get-by-key` | `test_agent_get_by_key` | pass (destructive) |
| Agent CRUD Lifecycle | `agent create/get/update/delete` | `test_agent_crud_lifecycle` | pass (destructive) |
| Chat Single Turn | `agent chat -m ... --no-stream` | `test_agent_chat_single_turn` | pass |
| Chat Multi Turn | `agent chat -m ... -cid ...` | `test_agent_chat_multi_turn` | pass |
| Chat Streaming | `agent chat -m ... --stream` | `test_agent_chat_stream` | pass |
| Sessions | `agent sessions` | `test_agent_sessions` | pass |
| History | `agent history` | `test_agent_history` | pass |
| Trace | `agent trace` | `test_agent_trace` | pass |
| Publish/Unpublish | `agent publish/unpublish` | `test_agent_publish_unpublish` | known_bug |

**Known Bug:**
- **Publish nil pointer** — `FillPublishedByName` dereferences nil when UM service returns `(nil, nil)`. Fix exists on branch `fix/98-nil-pointer-in-get-user-id-name-map` but not merged to main.

### BKN (Business Knowledge Network)

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| BKN List | `bkn list` | `test_bkn_list` | pass |
| BKN Get | `bkn get` | `test_bkn_get` | pass |
| BKN Export | `bkn export` | `test_bkn_export` | pass |
| BKN Search | `bkn search` | `test_bkn_search` | pass |
| BKN Stats | `bkn stats` | `test_bkn_stats` | pass |
| BKN Create & Delete | `bkn create / delete` | `test_bkn_create_and_delete` | pass (destructive) |
| BKN Update | `bkn update` | `test_bkn_update` | pass (destructive) |
| Object Type List | `bkn object-type list` | `test_bkn_object_type_list` | pass |
| Object Type Query | `bkn object-type query` | `test_bkn_object_type_query` | pass |
| Object Type Properties | `bkn object-type query --properties` | `test_bkn_object_type_properties` | pass |
| Object Type Get | `bkn object-type get` | `test_object_type_get` | pass |
| Object Type Update | `bkn object-type update` | `test_object_type_update_property_cycle` | pass (destructive) |
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

**Known Bug:**
- **action execute invalid identity** ([adp#442](https://github.com/kweaver-ai/adp/issues/442)): returns 500 instead of 400 for invalid `_instance_identities`.

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
| Discovery Task Get | `vega discovery-task get` | `test_vega_discovery_task_get` | pass |
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
- **catalog resources 500** ([adp#447](https://github.com/kweaver-ai/adp/issues/447)): `FilterResources` sends empty resources array to Hydra when catalog has no resources.
- **resource list-all 404** ([adp#448](https://github.com/kweaver-ai/adp/issues/448)): `ListResources` handler returns 404 instead of 400 when `resource_type` param missing.
- **ds delete 500**: backend database error when deleting datasource on dip.aishu.cn.

### Context Loader

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| BKN List (via CL) | `context-loader bkn list` | `test_context_loader_bkn_list` | pass |
| BKN Export (via CL) | `context-loader bkn export` | `test_context_loader_bkn_export` | pass |
| OT Query (via CL) | `context-loader object-type query` | `test_context_loader_object_type_query` | pass |

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
│   ├── dataflow/           # Dataflow (pending CLI)
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

# Per-module
make test-agent          # Agent module only
make test-bkn            # BKN module only
make test-vega           # Vega module only (includes DS + Dataview)
make test-context-loader # Context Loader module only
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

## License

See [LICENSE](LICENSE).
