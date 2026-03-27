# Agent Conventions

## Project

kweaver-eval: evaluation and acceptability testing for the KWeaver system.

## Structure

- `lib/` — core library (agents, types, scorer, recorder, feedback, reporter)
- `lib/agents/` — pluggable agent abstraction (BaseAgent, CliAgent, JudgeAgent)
- `roles/` — role prompt files (soul.md + instructions.md per role)
- `tests/scripted/` — deterministic scripted test cases (ported from kweaver-sdk e2e)
- `tests/agent/` — agent-driven test cases (agent plans CLI call sequences)
- `test-result/` — output artifacts (gitignored), timestamped run directories

## Testing

- `make test` — deterministic scoring only, no API cost
- `make test-full` — deterministic + agent judge scoring
- `make test-report` — full run with aggregate report

## Code Style

- All comments and docstrings in English
- All log messages in English
- ruff + pyright for linting
