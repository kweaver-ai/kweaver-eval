# Write Tests

Supplement missing test cases for kweaver-eval based on the coverage gap report.

## CRITICAL CONSTRAINT

Your job is **writing test code only**.

**DO NOT:**
- Run the actual test suite (`pytest -m api` or `make test-at`)
- Add skip markers like `known_bug`, `wait_for_env`, `wait_for_cli` to tests — that's triage's job
- Modify lib/ code, pyproject.toml, or any non-test files
- Classify or diagnose failures

**ONLY:**
- Write new test files under `tests/adp/`
- Verify collection with `pytest --collect-only`
- Write the gate artifact

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
