# Test Supplement Pipeline — Design Spec

Automated test case gap analysis and supplementation for kweaver-eval, orchestrated as a Petri pipeline.

---

## Goal

Analyze test coverage gaps across all KWeaver modules, supplement missing test cases (core flows + corner cases), triage failures, and produce a summary report. The pipeline is **reentrant** — running it again after SDK/backend capability growth automatically picks up new gaps.

## Modules

Coverage is measured against **module capabilities**, not CLI command tree:

| Module | CLI Domains | Notes |
|--------|-------------|-------|
| Decision Agent | `agent` | CRUD, chat, sessions, context quality, error paths |
| BKN | `bkn` | Knowledge network, object/relation types, actions, versioning |
| Vega | `vega` + `ds` + `dataview` | Metadata engine, datasources, dataviews |
| Context Loader | `context-loader` | MCP-based context access |
| Execution Factory | `skill` + (future `dataflow`) | Skill registry, dataflow |
| Dataflow | `dataflow` | Pipeline execution (wait_for_cli) |
| TraceAI | (no CLI yet) | Tracing/observability |

## Pipeline Structure

```yaml
name: test-supplement
stages:
  - name: env-check
    roles: [env_checker]

  - name: coverage-audit
    roles: [auditor]
    overrides:
      auditor:
        model: opus

  - repeat:
      name: supplement-loop
      max_iterations: 5
      until: coverage-sufficient
      stages:
        - name: write-tests
          roles: [test_writer]
          max_retries: 2
        - name: run-and-triage
          roles: [triage_runner]
          max_retries: 1

  - name: report
    roles: [reporter]
```

Default model: **sonnet**. Auditor overridden to **opus** (cross-repo reasoning).

## Roles

### env_checker

**Purpose**: Verify runtime environment, fail-fast if unusable.

**Checks**:
1. `kweaver auth status` — token valid
2. `kweaver vega health` — backend reachable
3. `python3 -m pytest tests/ --collect-only -q` — test collection works
4. Required env vars present (`KWEAVER_BASE_URL`, etc.)

**Skills**: `petri:shell_tools`, `petri:file_operations`, custom `check_env.md`

**Gate** (`env-ready`):
- Evidence: `env-check/env_checker/result.json`
- Check: `ready == true`

### auditor

**Purpose**: Extract capability inventory from kweaver backend (the primary test target), cross-reference with SDK CLI availability, diff against existing tests, output gap report.

**Sources** (read via `petri:file_operations`):
1. `~/dev/github/kweaver` backend code → **authoritative capability inventory** (API-level, including TraceAI and other modules without CLI yet)
2. `~/dev/github/kweaver-sdk` source → which backend capabilities have CLI support
3. `kweaver --help` + subcommand help → CLI-accessible surface area

**Incremental awareness**:
- Scans existing test cases and their **actual markers** (pass / known_bug / wait_for_env / wait_for_cli)
- Gap = full capabilities − (tests that exist AND are not blocked by wait_for_*)
- Previously `wait_for_cli` tests: if SDK now supports the command → re-enter gap list
- Previously `wait_for_env` tests: if env check passes for that feature → re-enter gap list

**Output artifact**: `coverage-audit/auditor/coverage-gap.json`
```json
{
  "modules": {
    "<module>": {
      "covered": ["<capability>", ...],
      "gaps_core": ["<capability>", ...],
      "gaps_corner": ["<capability>", ...]
    }
  },
  "summary": {
    "total_capabilities": 120,
    "covered": 85,
    "gaps_core": 20,
    "gaps_corner": 15
  }
}
```

**Skills**: `petri:shell_tools`, `petri:file_operations`, custom `coverage_audit.md`

**Gate** (`audit-complete`):
- Evidence: `coverage-audit/auditor/coverage-gap.json`
- Check: `summary.total_capabilities > 0`

### test_writer

**Purpose**: Each loop iteration, pick a batch of uncovered capabilities and write test cases.

**Workflow**:
1. Read `coverage-gap.json` + previous triage results (if any)
2. Priority: core flows > corner cases, rotate across modules
3. Follow existing test style (fixtures, markers, assert patterns)
4. Mark tests: `@pytest.mark.api`, destructive tests add `@pytest.mark.destructive`
5. Place tests in correct module directory (e.g., `tests/adp/traceai/`)
6. New fixtures go in the module's `conftest.py`

**Constraints**:
- Follow AGENTS.md code style (English comments/docstrings)
- `pytest --collect-only` must succeed after writing

**Skills**: `petri:shell_tools`, `petri:file_operations`, custom `write_tests.md`

**Gate** (`tests-collected`):
- Evidence: `write-tests/test_writer/result.json`
- Check: `new_tests_count > 0`

### triage_runner

**Purpose**: Run new tests, classify failures, update gap tracking.

**Core principle**: The primary test target is **kweaver (backend)**. The SDK CLI is the test vehicle, not the test subject. When failures occur, triage must distinguish the root cause layer.

**Workflow**:
1. Run tests via `make test-at` or per-module targets
2. Classify failures by root cause:
   - `known_bug` (backend) — kweaver/adp backend bug, associate with kweaver/adp issue
   - `known_bug` (SDK) — CLI-layer bug (param parsing, output format, etc.), associate with kweaver-sdk issue
   - `wait_for_env` — environment not ready
   - `wait_for_cli` — SDK CLI not yet available for this capability
3. Apply `pytest.mark.skip(reason=...)` or `pytest.mark.xfail` to classified tests, noting the issue layer and link in the reason string
4. Update `coverage-gap.json` — remove capabilities that are now covered
5. Decide: are there remaining actionable gaps (core flows or corner cases that can be written)?

**Skills**: `petri:shell_tools`, `petri:file_operations`, custom `triage.md`

**Gate** (`coverage-sufficient` — repeat exit condition):
- Evidence: `run-and-triage/triage_runner/result.json`
- Check: `has_remaining_gaps == false`
- `true` (gaps remain) → gate fails → loop continues
- `false` (all done or remaining are wait_for_*) → gate passes → exit loop

### reporter

**Purpose**: Produce final summary report.

**Output** (`report/reporter/supplement-report.md`):
- Per-module coverage comparison (before / after)
- New test case inventory
- Failure classification distribution (known_bug / wait_for_env / wait_for_cli)
- Overall pass rate
- Residual issues and recommendations

**Skills**: `petri:file_operations`, custom `report.md`

**Gate** (`report-done`):
- Evidence: `report/reporter/result.json`
- Check: `completed == true`

## Gate Summary

| Role | Gate ID | Evidence Path | Check |
|------|---------|---------------|-------|
| env_checker | `env-ready` | `env-check/env_checker/result.json` | `ready == true` |
| auditor | `audit-complete` | `coverage-audit/auditor/coverage-gap.json` | `summary.total_capabilities > 0` |
| test_writer | `tests-collected` | `write-tests/test_writer/result.json` | `new_tests_count > 0` |
| triage_runner | `coverage-sufficient` | `run-and-triage/triage_runner/result.json` | `has_remaining_gaps == false` |
| reporter | `report-done` | `report/reporter/result.json` | `completed == true` |

## Reentrance

The pipeline is designed to be run repeatedly as the system evolves:

- **SDK adds new commands** → auditor's CLI capability extraction picks them up → new gaps appear
- **Backend adds new APIs** → auditor's source code scan finds them → new gaps appear
- **Environment becomes available** → previously `wait_for_env` tests get re-evaluated
- **Tests already passing** → excluded from gap list, not re-written

No pipeline structure changes needed for reentrance — the auditor's incremental awareness logic handles it.

## File Layout

```
kweaver-eval/
  petri.yaml
  pipeline.yaml
  roles/
    env_checker/
      role.yaml
      soul.md
      gate.yaml
      skills/
        check_env.md
    auditor/
      role.yaml
      soul.md
      gate.yaml
      skills/
        coverage_audit.md
    test_writer/
      role.yaml
      soul.md
      gate.yaml
      skills/
        write_tests.md
    triage_runner/
      role.yaml
      soul.md
      gate.yaml
      skills/
        triage.md
    reporter/
      role.yaml
      soul.md
      gate.yaml
      skills/
        report.md
```
