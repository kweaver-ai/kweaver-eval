# Modular Test Restructure Design

> Date: 2026-03-30
> Scope: Restructure kweaver-eval from flat test layout to module-based hierarchy, aligned with TESTING.zh.md

---

## 1. Context

kweaver-eval currently has a flat test structure under `tests/scripted/` covering BKN, datasource, query, agent, and auth. The project needs to:

1. Organize tests by product module (ADP > bkn/vega/ds/dataflow/ef/context-loader)
2. Support future product lines (ISF, Decision Agent, TraceAI)
3. Align with [KWeaver-Core TESTING.zh.md](https://github.com/kweaver-ai/kweaver/blob/main/rules/TESTING.zh.md) conventions
4. Scale LLM-based evaluation per module

### Architecture dependency chain (top → bottom)

```
context-loader → bkn
bkn → vega, execution-factory, dataflow
vega → ds
execution-factory → ds
dataflow → ds
```

### CLI status

| Module | CLI | Status |
|--------|-----|--------|
| ds | `kweaver ds` | TS CLI ready |
| bkn | `kweaver bkn` | TS CLI ready |
| vega | `kweaver vega` | TS CLI ready |
| context-loader | `kweaver context-loader` | TS CLI ready |
| dataflow | — | CLI pending |
| execution-factory | — | CLI pending |

> Note: CLI is TypeScript only. Python package is SDK only (no CLI).

---

## 2. Directory Structure

```
tests/
  conftest.py                      # L0: global fixtures
  adp/
    conftest.py                    # L1: ADP product line
    bkn/
      conftest.py                  # L2: BKN module fixtures
      test_read.py                 # list, get, stats, export, search
      test_schema.py               # object-type/relation-type/action-type CRUD
      test_lifecycle.py            # ds connect -> bkn create -> build -> verify -> delete
      test_directory.py            # validate, push, pull
    vega/
      conftest.py
      test_health.py               # health, stats, inspect
      test_catalog.py              # list, get, health, test-connection, discover, resources
      test_resource.py             # list, get, query, preview
      test_connector_type.py       # list, get
      test_lifecycle.py            # catalog create -> discover -> resource query -> delete
    ds/
      conftest.py
      test_read.py                 # list, get, tables
      test_lifecycle.py            # connect -> tables -> delete
    context_loader/
      conftest.py
      test_config.py               # set, use, list, show, remove
      test_mcp.py                  # tools, resources, templates, prompts
      test_query.py                # kn-search, query-object-instance, query-instance-subgraph
      test_logic.py                # get-logic-properties, get-action-info
    dataflow/
      conftest.py                  # placeholder, pending CLI
    execution_factory/
      conftest.py                  # placeholder, pending CLI
  agent/
    test_full_flow_eval.py         # cross-module end-to-end agent evaluation
```

---

## 3. Conftest Layer Design

### L0 — `tests/conftest.py` (global)

Session-scoped fixtures (unchanged from current):
- `base_url` — `KWEAVER_BASE_URL` from env
- `cli_agent` — `CliAgent()` instance
- `recorder` — `Recorder()` instance
- `feedback_tracker` — `FeedbackTracker()` instance

Per-test fixture:
- `scorer` — `Scorer()` instance

New fixtures:
- `eval_case` — helper that wraps deterministic result + optional agent judge + recorder + feedback tracker into a single call

Autouse session fixture:
- `finalize` — flush results and save feedback

### L1 — `tests/adp/conftest.py` (ADP product line)

```python
pytestmark = [pytest.mark.api, pytest.mark.adp]
```

Session-scoped, autouse:
- `ensure_authenticated` — runs `kweaver auth status`, skips all ADP tests if auth fails

### L2 — Module conftest files

Each module conftest sets `pytestmark` for module marker and provides resource-finding fixtures.

**`tests/adp/ds/conftest.py`**:
- `ds_id` — session-scoped, finds first available datasource from `kweaver ds list`

**`tests/adp/bkn/conftest.py`**:
- `kn_id` — session-scoped, finds first available KN from `kweaver bkn list`
- `kn_with_data` — session-scoped, finds KN with object types (for query tests)
- `db_credentials` — reads `KWEAVER_TEST_DB_*` env vars (for lifecycle tests)

**`tests/adp/vega/conftest.py`**:
- `catalog_id` — session-scoped, finds first available catalog
- `resource_id` — session-scoped, finds first available resource

**`tests/adp/context_loader/conftest.py`**:
- `cl_config_active` — session-scoped, ensures active context-loader config exists

Design rules:
- Resource not found → `pytest.skip()`, not fail
- Lifecycle tests create their own resources, do not depend on L2 fixtures
- Fixtures return IDs only; tests call CLI themselves for details

---

## 4. Makefile Targets (aligned with TESTING.zh.md)

```makefile
.PHONY: test test-at test-at-full test-smoke test-destructive lint ci

# UT semantic: no external deps, verify test collection only
test:
	python3 -m pytest tests/ --collect-only -q

# Acceptance tests
test-at:
	@mkdir -p test-result
	python3 -m pytest tests/ -v -s --tb=short -m api \
		--junitxml=test-result/junit.xml \
		--alluredir=test-result/allure

# AT + agent judge scoring
test-at-full:
	EVAL_AGENT_JUDGE=1 $(MAKE) test-at

# Smoke: minimal health check
test-smoke:
	python3 -m pytest tests/ -v -s --tb=short -m smoke

# Destructive: lifecycle tests that create/delete resources
test-destructive:
	EVAL_RUN_DESTRUCTIVE=1 python3 -m pytest tests/ -v -s --tb=short \
		-m "api and destructive" \
		--junitxml=test-result/junit.xml \
		--alluredir=test-result/allure

# Report: full run with aggregate health report
test-report:
	EVAL_AGENT_JUDGE=1 EVAL_REPORT=1 $(MAKE) test-at

lint:
	python3 -m ruff check .
	python3 -m pyright

ci: lint test-at

# Per-module shortcuts
test-bkn:
	python3 -m pytest tests/adp/bkn/ -v -s --tb=short -m api
test-vega:
	python3 -m pytest tests/adp/vega/ -v -s --tb=short -m api
test-ds:
	python3 -m pytest tests/adp/ds/ -v -s --tb=short -m api
test-context-loader:
	python3 -m pytest tests/adp/context_loader/ -v -s --tb=short -m api
```

### Artifacts

Output to `test-result/` (gitignored):

| Artifact | Source | Consumer |
|----------|--------|----------|
| `junit.xml` | pytest `--junitxml` | CI, compliance |
| `allure/` | pytest `--alluredir` | CI, compliance |
| `runs/<timestamp>/results.json` | Recorder | kweaver-eval internal |
| `runs/<timestamp>/report.json` | Reporter | kweaver-eval internal |
| `feedback.json` | FeedbackTracker | cross-run tracking |

---

## 5. Pytest Markers

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "api: acceptance test hitting live service",
    "smoke: minimal subset for quick health check",
    "destructive: creates/deletes resources (requires EVAL_RUN_DESTRUCTIVE=1)",
    "adp: AI Data Platform",
    "bkn: Business Knowledge Network",
    "vega: Vega engine",
    "ds: Datasource",
    "context_loader: Context Loader / MCP",
    "dataflow: Dataflow (pending CLI)",
    "execution_factory: Execution Factory (pending CLI)",
]
```

Marker application strategy:
- `api` + product line + module markers applied via `pytestmark` in L2 conftest (batch, not per-function)
- `destructive` applied manually on specific lifecycle test functions
- `smoke` applied manually on 1-2 core read tests per module

---

## 6. LLM Evaluation Design

### 6.1 Judge roles

| Role | Purpose | When |
|------|---------|------|
| `acceptability_judge` | Single case: is the result acceptable? | After each test (opt-in) |
| `regression_judge` | Compare to history: any degradation? | When historical data exists |
| `health_analyst` | Aggregate report across all modules | After full test run |

### 6.2 Module-specific evaluation

Default: all modules use `acceptability_judge` with `eval_hints` for module-specific criteria.

Exception: modules with semantically complex outputs (e.g., context-loader search relevance) get dedicated judge roles under `roles/<module>_judge/`.

### 6.3 eval_case helper

```python
# tests/conftest.py
@pytest.fixture
def eval_case(recorder, feedback_tracker):
    async def _eval(name, steps, det, module=None, eval_hints=None):
        judge = None
        if os.getenv("EVAL_AGENT_JUDGE") == "1":
            judge_agent = JudgeAgent()
            judge = await judge_agent.evaluate(
                case_name=name,
                steps=steps,
                deterministic=det,
                eval_hints=eval_hints,
            )
            for f in judge.findings:
                feedback_tracker.record_finding(name, f, module=module)
        recorder.record_case(CaseResult(
            name=name,
            status="pass" if det.passed else "fail",
            deterministic=det,
            judge=judge,
        ))
    return _eval
```

### 6.4 eval_hints examples

```python
# vega: latency tolerance is higher for discover operations
await eval_case("vega_catalog_discover", [result], det,
    module="adp/vega",
    eval_hints={
        "focus": "operation_completion",
        "description": "Discover is async; verify task was submitted successfully",
        "latency_budget_ms": 30000,
    })

# context-loader: semantic relevance matters
await eval_case("context_loader_kn_search", [result], det,
    module="adp/context_loader",
    eval_hints={
        "focus": "semantic_relevance",
        "description": "Search results should be semantically relevant to query, not just structurally correct",
        "latency_budget_ms": 5000,
    })
```

### 6.5 Module-level aggregation

FeedbackTracker gains a `module` field on findings for per-module filtering.

Reporter's `health_analyst` produces module-level status:

```json
{
  "overall_status": "degraded",
  "module_status": {
    "adp/bkn": "healthy",
    "adp/vega": "degraded",
    "adp/ds": "healthy",
    "adp/context_loader": "broken"
  },
  "sections": [],
  "top_issues": []
}
```

---

## 7. Migration Plan

### Existing test migration

| Current file | Target | Notes |
|-------------|--------|-------|
| `tests/scripted/test_auth.py` | `tests/adp/conftest.py` `ensure_authenticated` | Becomes fixture, not standalone test |
| `tests/scripted/test_bkn_lifecycle.py` | `tests/adp/bkn/test_read.py` + `test_lifecycle.py` | Split read-only vs destructive |
| `tests/scripted/test_datasource.py` | `tests/adp/ds/test_read.py` | Direct move |
| `tests/scripted/test_query.py` | `tests/adp/bkn/test_schema.py` | Object-type query → schema |
| `tests/scripted/test_agent.py` | `tests/adp/test_agent.py` | Temp location; move to `tests/decision_agent/` later |
| `tests/agent/test_full_flow_eval.py` | `tests/agent/test_full_flow_eval.py` | No change |

After migration: delete `tests/scripted/`.

### New test coverage (this week, by priority)

**P0 — BKN completion**:
- `test_read.py`: add stats, get, update
- `test_schema.py`: object-type/relation-type/action-type CRUD
- `test_directory.py`: validate, push, pull
- `test_lifecycle.py`: add build step verification

**P0 — Vega (new)**:
- `test_health.py`: health, stats, inspect
- `test_catalog.py`: list, get, health, test-connection, discover, resources
- `test_resource.py`: list, get, query, preview
- `test_connector_type.py`: list, get
- `test_lifecycle.py`: catalog create -> discover -> resource query -> delete

**P1 — DS completion**:
- `test_lifecycle.py`: connect -> tables -> delete

**P1 — Context Loader (new)**:
- `test_config.py`, `test_mcp.py`, `test_query.py`, `test_logic.py`

**P2 — Dataflow / Execution Factory**: placeholder directories, pending CLI

---

## 8. Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Directory-per-module (Approach A) | Full coverage per module needs multiple files; fixtures need isolation |
| 2 | `make test` = collect-only | Align with TESTING.zh.md: `test` must have no external deps |
| 3 | Dual artifact output | junit.xml + allure for compliance; results.json + report.json for eval-specific value |
| 4 | eval_hints over per-module judge roles | Most modules share evaluation criteria; hints cover differences without role proliferation |
| 5 | Agent test stays in adp/ temporarily | Decision Agent module not in scope this week |
| 6 | CLI-first testing | If CLI doesn't exist for a module, prioritize adding CLI over testing internal APIs |
| 7 | Skip on missing resources, not fail | Read tests depend on environment data; missing data = not ready, not broken |
