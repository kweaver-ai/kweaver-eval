# Agent Conventions

## Project

kweaver-eval: evaluation and acceptability testing for the KWeaver system.

## Structure

- `lib/` — core library (agents, types, scorer, recorder, feedback, reporter)
- `lib/agents/` — pluggable agent abstraction (BaseAgent, CliAgent, JudgeAgent)
- `roles/` — role prompt files (soul.md + instructions.md per role)
- `tests/adp/` — ADP product line acceptance tests
  - `bkn/` — Business Knowledge Network (list, export, search, schema, lifecycle)
  - `vega/` — Vega engine (health, catalogs, resources, connector-types)
  - `ds/` — Datasource (list, get, tables, lifecycle)
  - `context_loader/` — Context Loader / MCP
  - `dataflow/` — Dataflow (pending CLI)
  - `execution_factory/` — Execution Factory (pending CLI)
- `tests/agent/` — cross-module agent-driven evaluation
- `test-result/` — output artifacts (gitignored)
- `docs/superpowers/specs/` — design specs
- `docs/superpowers/plans/` — implementation plans

## Testing

Aligned with [TESTING.zh.md](https://github.com/kweaver-ai/kweaver/blob/main/rules/TESTING.zh.md):

- `make test` — collect-only (no external deps)
- `make test-at` — acceptance tests against live service
- `make test-at-full` — AT + agent judge scoring
- `make test-smoke` — minimal health check subset
- `make test-destructive` — lifecycle tests (create/delete resources)
- `make test-report` — full run with aggregate report
- `make test-bkn` / `make test-vega` / etc. — per-module

## Code Style

- All comments and docstrings in English
- All log messages in English
- ruff + pyright for linting
