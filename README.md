# kweaver-eval

Harness engineering feedback loop: dual-scoring (deterministic + agent judge) acceptability tests for the KWeaver system.

## Overview

kweaver-eval validates the entire KWeaver stack (SDK CLI, platform API, harness/skills) as an independent verification project. It serves as the **Verify** function in KWeaver's [harness engineering](https://openai.com/index/harness-engineering/) feedback loop.

Every test case produces two scoring dimensions:

| Dimension | What it checks | When it applies |
|-----------|---------------|-----------------|
| **Deterministic** | exit code, JSON structure, field values | Every case |
| **Agent Judge** | Semantic evaluation with severity grading | Opt-in per case |

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure (or rely on ~/.env.secrets)
cp .env.example .env
# Edit .env with your KWEAVER_BASE_URL

# Ensure kweaver CLI is authenticated
kweaver auth login <platform-url> -u <user> -p <pass> -k

# Run tests (deterministic only, no API cost)
make test

# Run with agent judge scoring (requires ANTHROPIC_API_KEY)
make test-full

# Full run with aggregate health report
make test-report
```

## Project Structure

```
lib/
├── agents/                 # Pluggable agent abstraction
│   ├── base.py             # BaseAgent ABC with role prompt loading
│   ├── cli_agent.py        # Executes kweaver CLI as subprocess
│   └── judge_agent.py      # Evaluates results via Claude API
├── types.py                # Severity, CliResult, CaseResult, etc.
├── scorer.py               # Deterministic assertion helpers
├── recorder.py             # Timestamped run history
├── feedback.py             # Cross-run feedback tracking
└── reporter.py             # Aggregate report generation
roles/                      # Judge role prompts (soul.md + instructions.md)
tests/
├── scripted/               # Deterministic cases (ported from kweaver-sdk e2e)
└── agent/                  # Agent-driven evaluation cases
test-result/
├── runs/<timestamp>/       # Per-run results, logs, reports
│   ├── results.json
│   ├── report.json
│   └── logs/
└── feedback.json           # Persistent cross-run issue tracker
```

## Architecture

### Agent Design

Borrowed from [shadowcoder](https://github.com/kweaver-ai/shadowcoder)'s agent abstraction:

- **BaseAgent** — abstract interface with pluggable transports
- **CliAgent** — executes `kweaver` CLI commands as subprocess
- **JudgeAgent** — evaluates results via Claude API with role prompts

### Severity Grading

Agent judge findings use a four-level severity scale:

| Severity | Meaning | Impact |
|----------|---------|--------|
| CRITICAL | System broken | Case fails |
| HIGH | Major feature degraded | Case fails |
| MEDIUM | Minor issue | Warning |
| LOW | Cosmetic | Warning |

### Role Prompts

Each judge role is defined by `soul.md` (persona) + `instructions.md` (task). Search order: project-level, user-level, built-in.

### Feedback Tracking

Issues are tracked across runs in `test-result/feedback.json`:
- `times_seen >= 3` — flagged as persistent
- `times_seen >= 5` — requires human attention
- Auto-resolved after consecutive absences

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `KWEAVER_BASE_URL` | Yes | KWeaver platform URL |
| `KWEAVER_USERNAME` | Yes* | Auth (or set in ~/.env.secrets) |
| `KWEAVER_PASSWORD` | Yes* | Auth (or set in ~/.env.secrets) |
| `EVAL_RUN_DESTRUCTIVE` | No | Enable destructive tests (create/delete) |
| `EVAL_AGENT_JUDGE` | No | Enable agent judge scoring |
| `ANTHROPIC_API_KEY` | For judge | Required when EVAL_AGENT_JUDGE=1 |

## License

See [LICENSE](LICENSE).
