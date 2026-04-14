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

## CRITICAL CONSTRAINT

Your job is **producing the report only**.

**DO NOT:**
- Modify README.md, test files, or any project files
- Run tests
- Write code

**ONLY produce:**
- `{stage}/{role}/supplement-report.md`
- `{stage}/{role}/result.json`

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
