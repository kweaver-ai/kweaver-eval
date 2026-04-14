# Test Supplement Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Petri pipeline in kweaver-eval that automatically audits test coverage gaps against kweaver backend capabilities, supplements missing test cases, triages failures, and reports results.

**Architecture:** Five roles (env_checker, auditor, test_writer, triage_runner, reporter) in a linear pipeline with a repeat loop (max 5 iterations) around write-tests and run-and-triage stages. The auditor uses opus for cross-repo reasoning; all other roles use sonnet. Agent reads kweaver-eval, kweaver-sdk, and kweaver repos via file_operations.

**Tech Stack:** Petri pipeline engine, Python/pytest (kweaver-eval test framework), kweaver CLI

---

## File Structure

```
kweaver-eval/
  petri.yaml                              # Provider + model config
  pipeline.yaml                           # Pipeline definition
  roles/
    env_checker/
      role.yaml                           # Skills: shell_tools, file_operations, check_env
      soul.md                             # Persona
      gate.yaml                           # Gate: env-ready
      skills/
        check_env.md                      # Environment check instructions
    auditor/
      role.yaml                           # Skills: shell_tools, file_operations, coverage_audit
      soul.md                             # Persona
      gate.yaml                           # Gate: audit-complete
      skills/
        coverage_audit.md                 # Coverage gap analysis instructions
    test_writer/
      role.yaml                           # Skills: shell_tools, file_operations, write_tests
      soul.md                             # Persona
      gate.yaml                           # Gate: tests-collected
      skills/
        write_tests.md                    # Test writing instructions
    triage_runner/
      role.yaml                           # Skills: shell_tools, file_operations, triage
      soul.md                             # Persona
      gate.yaml                           # Gate: coverage-sufficient
      skills/
        triage.md                         # Triage instructions
    reporter/
      role.yaml                           # Skills: file_operations, report
      soul.md                             # Persona
      gate.yaml                           # Gate: report-done
      skills/
        report.md                         # Report generation instructions
```

---

### Task 1: Project-level Petri config

**Files:**
- Create: `petri.yaml`
- Create: `pipeline.yaml`

- [ ] **Step 1: Create petri.yaml**

```yaml
providers:
  default:
    type: pi

models:
  opus:
    provider: default
    model: claude-opus-4-6
  sonnet:
    provider: default
    model: claude-sonnet-4-6

defaults:
  model: sonnet
  gate_strategy: all
  max_retries: 3
```

- [ ] **Step 2: Create pipeline.yaml**

```yaml
name: test-supplement
description: Automated test case gap analysis and supplement for kweaver-eval

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

- [ ] **Step 3: Validate config**

Run: `cd ~/dev/github/kweaver-eval && petri validate`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd ~/dev/github/kweaver-eval
git add petri.yaml pipeline.yaml
git commit -m "feat: add petri pipeline config for test supplement workflow"
```

---

### Task 2: env_checker role

**Files:**
- Create: `roles/env_checker/role.yaml`
- Create: `roles/env_checker/soul.md`
- Create: `roles/env_checker/gate.yaml`
- Create: `roles/env_checker/skills/check_env.md`

- [ ] **Step 1: Create role.yaml**

```yaml
persona: soul.md
skills:
  - petri:shell_tools
  - petri:file_operations
  - check_env
```

- [ ] **Step 2: Create soul.md**

```markdown
You are a DevOps verification agent. Your sole job is to confirm that the runtime
environment is ready for acceptance testing. You are precise and fail-fast — if
any check fails, you report exactly what is missing and stop immediately.
You never attempt to fix the environment yourself.
```

- [ ] **Step 3: Create gate.yaml**

```yaml
id: env-ready
description: All environment prerequisites must be satisfied
evidence:
  path: "{stage}/{role}/result.json"
  check:
    field: ready
    equals: true
```

- [ ] **Step 4: Create skills/check_env.md**

```markdown
# Check Environment

Verify that the kweaver-eval runtime environment is ready for acceptance testing.

## Checks

Run each check in order. If any check fails, stop and write the gate artifact
with `ready: false` and the failure details.

### 1. CLI authentication

```bash
kweaver auth status
```

**Pass condition:** exit code 0, stdout contains "Token status:".

### 2. Backend reachability

```bash
kweaver vega health
```

**Pass condition:** exit code 0.

### 3. Test collection

```bash
cd ~/dev/github/kweaver-eval && python3 -m pytest tests/ --collect-only -q
```

**Pass condition:** exit code 0, output shows collected test count > 0.

### 4. Required environment variables

Check that these are set and non-empty:
- `KWEAVER_BASE_URL`

Read the `.env` file at `~/dev/github/kweaver-eval/.env` and `~/.env.secrets`
to see if values are present (either in the environment or in those files).

## Gate artifact

Write `{stage}/{role}/result.json`:

```json
{
  "ready": true,
  "checks": {
    "auth": "pass",
    "backend": "pass",
    "test_collection": "pass",
    "env_vars": "pass"
  }
}
```

If any check fails, set `ready` to `false` and change that check's value to a
string describing the failure (e.g., `"auth": "FAIL: exit code 1 — not authenticated"`).
```

- [ ] **Step 5: Commit**

```bash
cd ~/dev/github/kweaver-eval
git add roles/env_checker/
git commit -m "feat: add env_checker role for pipeline environment verification"
```

---

### Task 3: auditor role

**Files:**
- Create: `roles/auditor/role.yaml`
- Create: `roles/auditor/soul.md`
- Create: `roles/auditor/gate.yaml`
- Create: `roles/auditor/skills/coverage_audit.md`

- [ ] **Step 1: Create role.yaml**

```yaml
persona: soul.md
skills:
  - petri:shell_tools
  - petri:file_operations
  - coverage_audit
```

- [ ] **Step 2: Create soul.md**

```markdown
You are a senior QA architect specializing in test coverage analysis. You
systematically extract capability inventories from source code and compare them
against existing test suites. You are thorough but practical — you distinguish
core flows from corner cases and prioritize accordingly.

You work across three codebases:
- `~/dev/github/kweaver` — the backend (authoritative capability source)
- `~/dev/github/kweaver-sdk` — the SDK CLI (test vehicle)
- `~/dev/github/kweaver-eval` — the test suite (coverage target)

The primary test target is **kweaver backend**. The SDK CLI is the testing
vehicle, not the test subject.
```

- [ ] **Step 3: Create gate.yaml**

```yaml
id: audit-complete
description: Coverage gap report must be produced with valid capability inventory
evidence:
  path: "{stage}/{role}/coverage-gap.json"
  check:
    field: summary.total_capabilities
    gte: 1
```

- [ ] **Step 4: Create skills/coverage_audit.md**

This is the most complex skill. It must instruct the auditor on:
- How to extract capabilities from each source
- Module mapping rules
- Incremental awareness logic
- Output format

```markdown
# Coverage Audit

Analyze test coverage gaps across all KWeaver modules by comparing backend
capabilities against existing test cases.

## Module Mapping

Coverage is measured by **module capability**, not CLI command tree:

| Module | CLI Domains | Backend Source |
|--------|-------------|----------------|
| Decision Agent | `agent` | `~/dev/github/kweaver/decision-agent/` |
| BKN | `bkn` | `~/dev/github/kweaver/adp/` (knowledge network handlers) |
| Vega | `vega` + `ds` + `dataview` | `~/dev/github/kweaver/adp/` (vega/metadata handlers) |
| Context Loader | `context-loader` | `~/dev/github/kweaver/adp/` (context-loader handlers) |
| Execution Factory | `skill` | `~/dev/github/kweaver/adp/` (execution-factory handlers) |
| Dataflow | `dataflow` | `~/dev/github/kweaver/adp/` (dataflow handlers) |
| TraceAI | (no CLI yet) | `~/dev/github/kweaver/trace-ai/` |

**Important:** `dataview` is part of Vega, `skill` is part of Execution Factory.
These are CLI organization quirks, not module boundaries.

## Step 1: Extract backend capabilities

For each module, read the backend source code to identify exposed API endpoints
and capabilities. Look for:
- HTTP handler registrations (route definitions)
- gRPC service definitions
- Public API methods

Record each capability as a short identifier, e.g., `agent.list`, `agent.chat.stream`,
`bkn.object_type.create`, `vega.catalog.discover`.

## Step 2: Check SDK CLI support

For each backend capability, check if the SDK CLI exposes it:

1. Run `kweaver --help` and `kweaver <domain> --help` for each domain
2. Read SDK CLI source at `~/dev/github/kweaver-sdk/src/kweaver/cli/` for
   detailed command definitions
3. Mark each capability as:
   - `cli_available` — CLI command exists
   - `cli_missing` — no CLI command (test must wait or use `kweaver call`)

## Step 3: Scan existing test cases

Read all test files under `~/dev/github/kweaver-eval/tests/`:

1. Map each test function to a module capability
2. Check markers to determine status:
   - No skip marker → `covered`
   - `@pytest.mark.known_bug(...)` → `covered_known_bug`
   - `@pytest.mark.wait_for_env(...)` → `covered_wait_env`
   - `@pytest.mark.wait_for_cli(...)` → `covered_wait_cli` (re-check if CLI now available)

## Step 4: Incremental awareness

For tests marked `wait_for_cli`:
- If SDK CLI now supports the command (found in Step 2) → move to `gaps_core`
  (the skip should be removed and the test re-verified)

For tests marked `wait_for_env`:
- If the env_checker stage passed all checks → consider moving to `gaps_core`

## Step 5: Compute gaps

For each module:
- `covered` = capabilities with passing tests
- `gaps_core` = capabilities with no test OR with stale wait_for_* markers, that represent core CRUD/lifecycle/read flows
- `gaps_corner` = missing corner cases for covered capabilities (error paths, edge cases, concurrency, boundary values)

## Step 6: Write gate artifact

Write `{stage}/{role}/coverage-gap.json`:

```json
{
  "modules": {
    "agent": {
      "covered": ["list", "get", "chat.single_turn", "chat.multi_turn"],
      "gaps_core": ["trace.detail_view"],
      "gaps_corner": ["chat.max_message_length", "chat.empty_message"]
    },
    "traceai": {
      "covered": [],
      "gaps_core": ["health", "list_traces", "get_trace"],
      "gaps_corner": []
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

Also write a human-readable `{stage}/{role}/coverage-report.md` summarizing the
findings per module with a table format matching the README's existing coverage tables.
```

- [ ] **Step 5: Commit**

```bash
cd ~/dev/github/kweaver-eval
git add roles/auditor/
git commit -m "feat: add auditor role for coverage gap analysis"
```

---

### Task 4: test_writer role

**Files:**
- Create: `roles/test_writer/role.yaml`
- Create: `roles/test_writer/soul.md`
- Create: `roles/test_writer/gate.yaml`
- Create: `roles/test_writer/skills/write_tests.md`

- [ ] **Step 1: Create role.yaml**

```yaml
persona: soul.md
skills:
  - petri:shell_tools
  - petri:file_operations
  - write_tests
```

- [ ] **Step 2: Create soul.md**

```markdown
You are a senior test engineer writing acceptance tests for the KWeaver platform.
You write clean, consistent tests that follow the existing codebase conventions
exactly. You never invent new patterns — you study the existing tests and replicate
their style.

You understand that the primary test target is the kweaver backend. The CLI is
just the test vehicle. When you write assertions, you are validating backend behavior.
```

- [ ] **Step 3: Create gate.yaml**

```yaml
id: tests-collected
description: New test cases must be written and collectible by pytest
evidence:
  path: "{stage}/{role}/result.json"
  check:
    field: new_tests_count
    gte: 1
```

- [ ] **Step 4: Create skills/write_tests.md**

```markdown
# Write Tests

Supplement missing test cases for kweaver-eval based on the coverage gap report.

## Working directory

All test files live in `~/dev/github/kweaver-eval/`. Always work in this directory.

## Input

Read the coverage gap report from the auditor's artifact:
- `coverage-audit/auditor/coverage-gap.json` — structured gap data
- `coverage-audit/auditor/coverage-report.md` — human-readable summary

If this is a retry within the supplement loop, also read:
- `run-and-triage/triage_runner/result.json` — previous triage results

## Priority

1. Core flows (`gaps_core`) before corner cases (`gaps_corner`)
2. Rotate across modules — don't exhaust one module before touching others
3. Skip capabilities marked `cli_missing` unless you can use `kweaver call` as a workaround

## Test conventions

**Study these files before writing any tests:**
- `~/dev/github/kweaver-eval/conftest.py` — root fixtures (`cli_agent`, `scorer`, `eval_case`)
- `~/dev/github/kweaver-eval/tests/adp/conftest.py` — ADP fixtures, auto-markers
- Existing test files in the target module directory

**Patterns to follow:**

1. Every test is `async def test_<name>(cli_agent: CliAgent, scorer: Scorer, eval_case):`
2. CLI calls use `result = await cli_agent.run_cli("domain", "subcommand", ...args)`
3. Assertions use `scorer.assert_exit_code(result, 0)`, `scorer.assert_json(result)`, etc.
4. Every test ends with:
   ```python
   det = scorer.result(result.duration_ms)
   await eval_case("test_name", [result], det, module="adp/<module>")
   assert det.passed, det.failures
   ```
5. Destructive tests (create/delete) use `@pytest.mark.destructive` and try/finally cleanup
6. Known bugs use `@pytest.mark.known_bug("description")`
7. All docstrings and comments in English
8. Module directory: `tests/adp/<module>/` (create new directories as needed, e.g., `tests/adp/traceai/`)
9. New directories need an `__init__.py` file
10. New fixtures go in the module's `conftest.py`

**Do NOT:**
- Change existing test files unless fixing a stale `wait_for_cli` marker
- Add dependencies to pyproject.toml
- Modify lib/ code
- Write tests that require interactive input

## Verification

After writing tests, run:

```bash
cd ~/dev/github/kweaver-eval && python3 -m pytest tests/ --collect-only -q
```

All new tests must be collected without errors.

## Gate artifact

Write `{stage}/{role}/result.json`:

```json
{
  "new_tests_count": 12,
  "files_created": ["tests/adp/traceai/test_health.py", "..."],
  "files_modified": [],
  "capabilities_addressed": ["traceai.health", "agent.trace.detail", "..."]
}
```
```

- [ ] **Step 5: Commit**

```bash
cd ~/dev/github/kweaver-eval
git add roles/test_writer/
git commit -m "feat: add test_writer role for test case supplementation"
```

---

### Task 5: triage_runner role

**Files:**
- Create: `roles/triage_runner/role.yaml`
- Create: `roles/triage_runner/soul.md`
- Create: `roles/triage_runner/gate.yaml`
- Create: `roles/triage_runner/skills/triage.md`

- [ ] **Step 1: Create role.yaml**

```yaml
persona: soul.md
skills:
  - petri:shell_tools
  - petri:file_operations
  - triage
```

- [ ] **Step 2: Create soul.md**

```markdown
You are a senior QA engineer specializing in test triage. You run tests, analyze
failures precisely, and classify each failure by root cause. You distinguish
between backend bugs (kweaver/adp), CLI bugs (kweaver-sdk), environment issues,
and missing CLI support.

You never guess — you read error output carefully, cross-reference with the
kweaver and kweaver-sdk source code when needed, and make evidence-based
classifications.
```

- [ ] **Step 3: Create gate.yaml**

```yaml
id: coverage-sufficient
description: All actionable coverage gaps must be addressed
evidence:
  path: "{stage}/{role}/result.json"
  check:
    field: has_remaining_gaps
    equals: false
```

- [ ] **Step 4: Create skills/triage.md**

```markdown
# Triage

Run newly written tests, classify failures, and determine whether more test
writing is needed.

## Working directory

`~/dev/github/kweaver-eval/`

## Step 1: Run tests

Run the full acceptance test suite:

```bash
cd ~/dev/github/kweaver-eval && python3 -m pytest tests/ -v -s --tb=short -m api --junitxml=test-result/junit.xml
```

If that takes too long or you only need to verify newly added tests, run
per-module:

```bash
python3 -m pytest tests/adp/<module>/ -v -s --tb=short -m api
```

## Step 2: Classify failures

For each failing test, determine root cause:

### known_bug (backend)
The test correctly invokes the CLI, but the backend returns an error or wrong data.
- Evidence: HTTP 500, incorrect response schema, wrong business logic
- Action: Add `@pytest.mark.known_bug("description — kweaver/adp issue")` to the test
- If you can identify the backend handler, note the file path in the description

### known_bug (SDK CLI)
The CLI itself has a bug — wrong parameter parsing, incorrect output formatting,
missing subcommand routing.
- Evidence: CLI exits non-zero before reaching the backend, malformed request, output format issues
- Action: Add `@pytest.mark.known_bug("description — kweaver-sdk issue")` to the test

### wait_for_env
The test requires an environment resource that is not available (e.g., specific
database, special config).
- Evidence: Connection refused, resource not found, config missing
- Action: Add `@pytest.mark.wait_for_env("description")` to the test

### wait_for_cli
The SDK CLI does not yet have the subcommand needed for this test.
- Evidence: "Unknown command" or similar from CLI
- Action: Add `@pytest.mark.wait_for_cli("description")` to the test

**Important:** Read `~/dev/github/kweaver-sdk` and `~/dev/github/kweaver` source
code when you need to distinguish backend vs. CLI bugs. Don't guess based on
error messages alone.

## Step 3: Update coverage gap

Read the current `coverage-audit/auditor/coverage-gap.json`.

For each capability that now has a test (regardless of pass/fail/skip):
- Move it from `gaps_core` or `gaps_corner` to `covered`

Write the updated gap data to `{stage}/{role}/updated-gap.json`.

## Step 4: Determine loop exit

Count remaining actionable gaps:
- `gaps_core` items where `cli_available` is true → actionable
- `gaps_corner` items where the parent capability has a passing test → actionable
- Items blocked by `wait_for_cli` or `wait_for_env` → NOT actionable

If actionable gaps remain → `has_remaining_gaps: true` (loop continues)
If no actionable gaps → `has_remaining_gaps: false` (loop exits)

## Gate artifact

Write `{stage}/{role}/result.json`:

```json
{
  "has_remaining_gaps": false,
  "tests_run": 120,
  "tests_passed": 95,
  "tests_failed": 10,
  "tests_skipped": 15,
  "new_marks_added": {
    "known_bug_backend": ["test_foo", "test_bar"],
    "known_bug_sdk": ["test_baz"],
    "wait_for_env": [],
    "wait_for_cli": ["test_qux"]
  },
  "remaining_actionable_gaps": 0,
  "remaining_blocked_gaps": 5
}
```
```

- [ ] **Step 5: Commit**

```bash
cd ~/dev/github/kweaver-eval
git add roles/triage_runner/
git commit -m "feat: add triage_runner role for test execution and failure classification"
```

---

### Task 6: reporter role

**Files:**
- Create: `roles/reporter/role.yaml`
- Create: `roles/reporter/soul.md`
- Create: `roles/reporter/gate.yaml`
- Create: `roles/reporter/skills/report.md`

- [ ] **Step 1: Create role.yaml**

```yaml
persona: soul.md
skills:
  - petri:file_operations
  - report
```

- [ ] **Step 2: Create soul.md**

```markdown
You are a technical report writer. You produce clear, data-driven summaries
of test coverage improvements. Your reports are structured for quick scanning —
tables over prose, numbers over narratives. You always include before/after
comparisons so progress is immediately visible.
```

- [ ] **Step 3: Create gate.yaml**

```yaml
id: report-done
description: Summary report must be produced
evidence:
  path: "{stage}/{role}/result.json"
  check:
    field: completed
    equals: true
```

- [ ] **Step 4: Create skills/report.md**

```markdown
# Generate Report

Produce a final summary report of the test supplement pipeline run.

## Input artifacts

Read all available artifacts:
- `coverage-audit/auditor/coverage-gap.json` — initial gap analysis (the "before" state)
- `coverage-audit/auditor/coverage-report.md` — human-readable initial audit
- `run-and-triage/triage_runner/result.json` — final triage results (the "after" state)
- `run-and-triage/triage_runner/updated-gap.json` — final gap state
- `write-tests/test_writer/result.json` — what was written

## Report structure

Write the report to `{stage}/{role}/supplement-report.md`:

### 1. Executive Summary
- One paragraph: what was done, key numbers (tests added, coverage change)

### 2. Coverage Comparison (Before / After)

| Module | Before | After | Delta | Notes |
|--------|--------|-------|-------|-------|
| Agent | 33/40 | 38/40 | +5 | ... |
| ... | ... | ... | ... | ... |
| **Total** | **X/Y** | **X'/Y'** | **+N** | ... |

### 3. New Test Cases

| Module | Test | Capability | Status |
|--------|------|------------|--------|
| ... | ... | ... | pass / known_bug / wait_for_* |

### 4. Failure Classification

| Category | Count | Tests |
|----------|-------|-------|
| known_bug (backend) | N | test_a, test_b |
| known_bug (SDK) | N | test_c |
| wait_for_env | N | test_d |
| wait_for_cli | N | test_e, test_f |

### 5. Residual Gaps

List capabilities that remain uncovered and why (blocked by CLI, blocked by env, etc.)

### 6. Recommendations

Actionable next steps: bugs to file, env to provision, CLI features to request.

## Also update README

If the report shows significant coverage changes, update the "Test Coverage Summary"
table in `~/dev/github/kweaver-eval/README.md` to reflect the new state.

## Gate artifact

Write `{stage}/{role}/result.json`:

```json
{
  "completed": true,
  "total_new_tests": 25,
  "coverage_before_pct": 76,
  "coverage_after_pct": 88
}
```
```

- [ ] **Step 5: Commit**

```bash
cd ~/dev/github/kweaver-eval
git add roles/reporter/
git commit -m "feat: add reporter role for pipeline summary generation"
```

---

### Task 7: Add .petri to .gitignore

**Files:**
- Modify: `.gitignore` (if exists, otherwise create)

- [ ] **Step 1: Check existing .gitignore**

```bash
cd ~/dev/github/kweaver-eval && cat .gitignore 2>/dev/null || echo "No .gitignore"
```

- [ ] **Step 2: Add .petri/ to .gitignore**

Append to `.gitignore` (or create it):

```
# Petri runtime artifacts
.petri/
```

- [ ] **Step 3: Commit**

```bash
cd ~/dev/github/kweaver-eval
git add .gitignore
git commit -m "chore: add .petri/ to gitignore"
```

---

### Task 8: Validate and dry-run

- [ ] **Step 1: Validate the full pipeline config**

```bash
cd ~/dev/github/kweaver-eval && petri validate
```

Expected: No errors. All roles found, all gates referenced correctly.

- [ ] **Step 2: Verify role file structure**

```bash
cd ~/dev/github/kweaver-eval && find roles/ -type f | sort
```

Expected output:
```
roles/auditor/gate.yaml
roles/auditor/role.yaml
roles/auditor/skills/coverage_audit.md
roles/auditor/soul.md
roles/env_checker/gate.yaml
roles/env_checker/role.yaml
roles/env_checker/skills/check_env.md
roles/env_checker/soul.md
roles/reporter/gate.yaml
roles/reporter/role.yaml
roles/reporter/skills/report.md
roles/reporter/soul.md
roles/test_writer/gate.yaml
roles/test_writer/role.yaml
roles/test_writer/skills/write_tests.md
roles/test_writer/soul.md
roles/triage_runner/gate.yaml
roles/triage_runner/role.yaml
roles/triage_runner/skills/triage.md
roles/triage_runner/soul.md
```

- [ ] **Step 3: Spot-check YAML parsing**

```bash
cd ~/dev/github/kweaver-eval && python3 -c "
import yaml
for f in ['petri.yaml', 'pipeline.yaml']:
    with open(f) as fh:
        d = yaml.safe_load(fh)
        print(f'{f}: OK ({list(d.keys())})')
for role in ['env_checker', 'auditor', 'test_writer', 'triage_runner', 'reporter']:
    for yf in ['role.yaml', 'gate.yaml']:
        path = f'roles/{role}/{yf}'
        with open(path) as fh:
            d = yaml.safe_load(fh)
            print(f'{path}: OK')
"
```

Expected: All files parse without error.

- [ ] **Step 4: Final commit if any fixes needed**

```bash
cd ~/dev/github/kweaver-eval
git add -A
git status
# Only commit if there are changes
git diff --cached --quiet || git commit -m "fix: address validation issues in pipeline config"
```
