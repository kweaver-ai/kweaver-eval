# Triage

Run newly written tests, classify failures, and determine whether more test
writing is needed.

## CRITICAL CONSTRAINT

Your job is **running tests and classifying failures only**.

**DO NOT:**
- Write new test files or new test functions
- Modify test logic or assertions
- Modify lib/ code, pyproject.toml, or any non-test files
- Read entire codebases to investigate — only read specific files when needed to classify a failure

**ONLY:**
- Run existing tests
- Add skip markers (`known_bug`, `wait_for_env`, `wait_for_cli`) to failing tests
- Update the coverage gap tracking
- Write the gate artifact

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
