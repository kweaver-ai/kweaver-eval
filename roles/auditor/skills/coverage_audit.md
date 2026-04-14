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
