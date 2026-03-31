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
kweaver auth login https://dip-poc.aishu.cn -u <user> -p <pass> -k

# 5. Run tests
make test              # Collect-only (verify setup, no network)
make test-at           # Acceptance tests against live service
make test-vega         # Vega module only
make test-bkn          # BKN module only
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

## Test Coverage

### Vega (vega-backend)

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| Health | `vega health` | `test_vega_health` | pass |
| Stats | `vega stats` | `test_vega_stats` | pass |
| Inspect | `vega inspect` | `test_vega_inspect` | pass |
| Catalog List | `vega catalog list` | `test_vega_catalog_list` | pass |
| Catalog Get | `vega catalog get` | `test_vega_catalog_get` | pass |
| Catalog Health | `vega catalog health` | `test_vega_catalog_health` | pass |
| Catalog Test Connection | `vega catalog test-connection` | `test_vega_catalog_test_connection` | pass |
| Catalog Resources | `vega catalog resources` | `test_vega_catalog_resources` | pass |
| Catalog Discover | `vega catalog discover` | `test_vega_catalog_discover` | pass |
| Catalog Create | `vega catalog create` | `test_vega_catalog_lifecycle` | pass (destructive) |
| Catalog Update | `vega catalog update` | `test_vega_catalog_lifecycle` | pass (destructive) |
| Catalog Delete | `vega catalog delete` | `test_vega_catalog_lifecycle` | pass (destructive) |
| Resource List | `vega resource list` | `test_vega_resource_list` | pass |
| Resource Get | `vega resource get` | `test_vega_resource_get` | pass |
| Resource Query | `vega resource query` | `test_vega_resource_query` | skip (no physical resource) |
| Connector Type List | `vega connector-type list` | `test_vega_connector_type_list` | pass |
| Connector Type Get | `vega connector-type get` | `test_vega_connector_type_get` | skip (backend bug) |
| Discovery Task List | `vega discovery-task list` | `test_vega_discovery_task_list` | skip (backend bug) |
| Discovery Task Get | `vega discovery-task get` | `test_vega_discovery_task_get` | pass |

**Coverage: 17 tests, 20/24 endpoints (83%)**

#### Known Backend Bugs (pending fix)

- **`connector-type get` 404** ([kweaver-ai/adp#427](https://github.com/kweaver-ai/adp/issues/427)): `GetConnectorType` handler reads `c.Param("id")` but route defines `:type` — param name mismatch.
- **`discovery-task list` 404** ([kweaver-ai/adp#428](https://github.com/kweaver-ai/adp/issues/428)): `ListDiscoveryTasks` handler requires catalog_id but route has no path param.

### BKN (Business Knowledge Network)

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| BKN List | `bkn list` | `test_bkn_list` | pass |
| BKN Export | `bkn export` | `test_bkn_export` | pass |
| BKN Search | `bkn search` | `test_bkn_search` | pass |
| Object Type List | `bkn object-type list` | `test_bkn_object_type_list` | pass |
| Relation Type List | `bkn relation-type list` | `test_bkn_relation_type_list` | pass |
| Object Type Query | `bkn object-type query` | `test_bkn_object_type_query` | pass |
| Full Lifecycle | ds connect → bkn create → export → search → cleanup | `test_bkn_full_lifecycle` | pass (destructive) |

### DS (Datasource)

| Capability | CLI Command | Test | Status |
|------------|-------------|------|--------|
| DS List | `ds list` | `test_datasource_list` | pass |
| DS Get | `ds get` | `test_datasource_get` | pass |
| DS Tables | `ds tables` | `test_datasource_tables` | pass |

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
│   ├── bkn/                # BKN: list, export, search, schema, lifecycle
│   ├── vega/               # Vega: health, catalogs, resources, connector-types, lifecycle
│   ├── ds/                 # DS: list, get, tables
│   ├── context_loader/     # Context Loader / MCP (pending)
│   ├── dataflow/           # Dataflow (pending CLI)
│   └── execution_factory/  # Execution Factory (pending CLI)
└── agent/                  # Cross-module agent-driven evaluation
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
make test-bkn            # BKN module only
make test-vega           # Vega module only
make test-ds             # Datasource module only
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
