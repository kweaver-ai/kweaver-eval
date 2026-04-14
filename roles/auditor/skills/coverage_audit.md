# Coverage Audit

Analyze test coverage gaps across all KWeaver modules by comparing backend
capabilities against existing test cases.

## Module Mapping

Coverage is measured by **module capability**, not CLI command tree:

| Module | CLI Domains |
|--------|-------------|
| Decision Agent | `agent` |
| BKN | `bkn` |
| Vega | `vega` + `ds` + `dataview` |
| Context Loader | `context-loader` |
| Execution Factory | `skill` |
| Dataflow | `dataflow` |
| TraceAI | (no CLI yet) |

**Important:** `dataview` is part of Vega, `skill` is part of Execution Factory.
These are CLI organization quirks, not module boundaries.

## Step 1: Extract capabilities

Build a capability inventory for each module. You decide the best sources — options include:
- `kweaver --help` and `kweaver <domain> --help` for CLI-exposed capabilities
- SDK CLI source at `~/dev/github/kweaver-sdk/` for detailed command definitions
- Backend source at `~/dev/github/kweaver/` for API-level capabilities (especially modules without CLI like TraceAI)
- The existing README coverage tables in `~/dev/github/kweaver-eval/README.md`

Be strategic — don't read entire codebases. Start with CLI help and README, then
drill into source only where gaps are unclear.

Record each capability as a short identifier, e.g., `agent.list`, `agent.chat.stream`,
`bkn.object_type.create`, `vega.catalog.discover`.

For each capability, note whether CLI support exists (`cli_available` / `cli_missing`).

## Step 2: Scan existing test cases

Read test files under `~/dev/github/kweaver-eval/tests/`:

1. Map each test function to a module capability
2. Check markers to determine status:
   - No skip marker → `covered`
   - `@pytest.mark.known_bug(...)` → `covered_known_bug`
   - `@pytest.mark.wait_for_env(...)` → `covered_wait_env`
   - `@pytest.mark.wait_for_cli(...)` → `covered_wait_cli` (re-check if CLI now available)

## Step 3: Incremental awareness

For tests marked `wait_for_cli`:
- If SDK CLI now supports the command (found in Step 1) → move to `gaps_core`
  (the skip should be removed and the test re-verified)

For tests marked `wait_for_env`:
- If the env_checker stage passed all checks → consider moving to `gaps_core`

## Step 4: Compute gaps

For each module:
- `covered` = capabilities with passing tests
- `gaps_core` = capabilities with no test OR with stale wait_for_* markers, that represent core CRUD/lifecycle/read flows
- `gaps_corner` = missing corner cases for covered capabilities (error paths, edge cases, concurrency, boundary values)

## Step 5: Write gate artifact

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
