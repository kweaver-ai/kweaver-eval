# Modular Test Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure kweaver-eval from flat test layout to module-based hierarchy under `tests/adp/`, aligned with TESTING.zh.md, with eval_case helper and updated Makefile/markers.

**Architecture:** Directory-per-module layout (`tests/adp/{bkn,vega,ds,context_loader}/`) with three conftest layers (L0 global, L1 ADP, L2 module). Existing tests migrate to new locations, new `eval_case` fixture reduces boilerplate. Makefile targets align with TESTING.zh.md (`test` = collect-only, `test-at` = run).

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, allure-pytest, ruff, pyright

**Spec:** `docs/superpowers/specs/2026-03-30-modular-test-restructure-design.md`

---

### Task 1: Update pyproject.toml — markers and dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add allure-pytest dependency and update markers**

```toml
[project]
name = "kweaver-eval"
version = "0.1.0"
description = "Evaluation and acceptability testing for the KWeaver system"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "python-dotenv>=1.0",
    "allure-pytest>=2.13",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.8",
    "pyright>=1.1",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "api: acceptance test hitting live service",
    "smoke: minimal subset for quick health check",
    "destructive: test mutates server state (requires EVAL_RUN_DESTRUCTIVE=1)",
    "adp: AI Data Platform",
    "bkn: Business Knowledge Network",
    "vega: Vega engine",
    "ds: Datasource",
    "context_loader: Context Loader / MCP",
    "dataflow: Dataflow (pending CLI)",
    "execution_factory: Execution Factory (pending CLI)",
]
addopts = "-v --tb=short"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.pyright]
pythonVersion = "3.11"
typeCheckingMode = "basic"
```

- [ ] **Step 2: Install updated dependencies**

Run: `pip install -e ".[dev]"`
Expected: allure-pytest installs successfully

- [ ] **Step 3: Verify collection still works**

Run: `python3 -m pytest tests/ --collect-only -q`
Expected: existing tests still collected, no warnings about unknown markers

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add allure-pytest dep and register module markers"
```

---

### Task 2: Update Makefile — align with TESTING.zh.md

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Replace Makefile content**

```makefile
.PHONY: test test-at test-at-full test-smoke test-destructive test-report lint ci install
.PHONY: test-bkn test-vega test-ds test-context-loader

install:
	pip install -e ".[dev]"

# UT semantic: no external deps, verify test collection only
test:
	python3 -m pytest tests/ --collect-only -q

# Acceptance tests
test-at:
	@mkdir -p test-result
	python3 -m pytest tests/ -v -s --tb=short -m api \
		--junitxml=test-result/junit.xml \
		--alluredir=test-result/allure

# AT + agent judge scoring
test-at-full:
	EVAL_AGENT_JUDGE=1 $(MAKE) test-at

# Smoke: minimal health check
test-smoke:
	python3 -m pytest tests/ -v -s --tb=short -m smoke

# Destructive: lifecycle tests that create/delete resources
test-destructive:
	EVAL_RUN_DESTRUCTIVE=1 python3 -m pytest tests/ -v -s --tb=short \
		-m "api and destructive" \
		--junitxml=test-result/junit.xml \
		--alluredir=test-result/allure

# Report: full run with aggregate health report
test-report:
	EVAL_AGENT_JUDGE=1 EVAL_REPORT=1 $(MAKE) test-at

lint:
	ruff check .
	pyright

ci: lint test-at

# Per-module shortcuts
test-bkn:
	python3 -m pytest tests/adp/bkn/ -v -s --tb=short -m api
test-vega:
	python3 -m pytest tests/adp/vega/ -v -s --tb=short -m api
test-ds:
	python3 -m pytest tests/adp/ds/ -v -s --tb=short -m api
test-context-loader:
	python3 -m pytest tests/adp/context_loader/ -v -s --tb=short -m api
```

- [ ] **Step 2: Verify `make test` works (collect-only)**

Run: `make test`
Expected: prints collected test count, exit 0

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: align Makefile targets with TESTING.zh.md"
```

---

### Task 3: Update L0 conftest — add eval_case fixture, update marker handling

**Files:**
- Modify: `conftest.py`

- [ ] **Step 1: Update conftest.py with eval_case and updated marker config**

```python
"""Root pytest configuration for kweaver-eval."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lib.agents.cli_agent import CliAgent
from lib.agents.judge_agent import JudgeAgent
from lib.feedback import FeedbackTracker
from lib.recorder import Recorder
from lib.scorer import Scorer
from lib.types import (
    AgentRequest,
    CaseResult,
    DeterministicResult,
    Finding,
    JudgeResult,
    Severity,
)


def _load_env_file(path: str) -> None:
    """Load environment variables from a file (simple .env parser)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ")
        eq = line.find("=")
        if eq < 0:
            continue
        key = line[:eq].strip()
        value = line[eq + 1 :].strip().strip("\"'")
        if key not in os.environ:
            os.environ[key] = value


# Load env files: local .env first, then ~/.env.secrets as fallback
_load_env_file(".env")
_load_env_file(os.path.join(Path.home(), ".env.secrets"))


def pytest_addoption(parser):
    parser.addoption(
        "--run-destructive",
        action="store_true",
        default=False,
        help="Run destructive tests",
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-destructive") and not os.environ.get("EVAL_RUN_DESTRUCTIVE"):
        skip = pytest.mark.skip(
            reason="destructive test (use --run-destructive or EVAL_RUN_DESTRUCTIVE=1)"
        )
        for item in items:
            if "destructive" in item.keywords:
                item.add_marker(skip)


# ---------- Session-scoped fixtures ----------


@pytest.fixture(scope="session")
def base_url() -> str:
    url = os.environ.get("KWEAVER_BASE_URL", "")
    if not url:
        pytest.skip("KWEAVER_BASE_URL not set")
    return url


@pytest.fixture(scope="session")
def cli_agent() -> CliAgent:
    return CliAgent()


@pytest.fixture(scope="session")
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture(scope="session")
def feedback_tracker() -> FeedbackTracker:
    return FeedbackTracker()


# ---------- Per-test fixtures ----------


@pytest.fixture
def scorer() -> Scorer:
    return Scorer()


# ---------- eval_case helper ----------


@pytest.fixture
def eval_case(recorder: Recorder, feedback_tracker: FeedbackTracker):
    """Helper that wraps deterministic + optional agent judge + record into one call.

    Usage:
        await eval_case("test_name", [cli_result], det_result,
                         module="adp/bkn", eval_hints={...})
    """

    async def _eval(
        name: str,
        steps: list,
        det: DeterministicResult,
        *,
        module: str | None = None,
        eval_hints: dict | None = None,
    ) -> None:
        judge_result: JudgeResult | None = None

        if os.environ.get("EVAL_AGENT_JUDGE"):
            judge = JudgeAgent(role="acceptability_judge")
            context: dict = {
                "case_name": name,
                "steps": [
                    {
                        "command": s.command,
                        "exit_code": s.exit_code,
                        "stdout": s.stdout,
                        "stderr": s.stderr,
                        "duration_ms": s.duration_ms,
                    }
                    for s in steps
                ],
                "deterministic_result": {
                    "passed": det.passed,
                    "failures": det.failures,
                },
            }
            if module:
                context["module"] = module
            if eval_hints:
                context["eval_hints"] = eval_hints

            agent_result = await judge.run(AgentRequest(
                action=f"Evaluate whether the '{name}' test output is acceptable.",
                context=context,
            ))
            try:
                jdata = json.loads(agent_result.output)
                judge_result = JudgeResult(
                    verdict=jdata.get("verdict", "fail"),
                    findings=[
                        Finding(
                            severity=Severity(f.get("severity", "medium")),
                            message=f.get("message", ""),
                            location=f.get("location", ""),
                        )
                        for f in jdata.get("findings", [])
                    ],
                    reasoning=jdata.get("reasoning", ""),
                    model=agent_result.model,
                )
                for finding in judge_result.findings:
                    feedback_tracker.record_finding(name, finding)
            except (json.JSONDecodeError, ValueError):
                pass

        recorder.record_case(CaseResult(
            name=name,
            status="pass" if det.passed else "fail",
            deterministic=det,
            judge=judge_result,
            steps=steps,
        ))

    return _eval


# ---------- Session teardown ----------


@pytest.fixture(scope="session", autouse=True)
def finalize(recorder, feedback_tracker):
    """Flush results and save feedback after all tests."""
    yield
    recorder.flush()
    feedback_tracker.save()
```

- [ ] **Step 2: Verify collection still works**

Run: `make test`
Expected: all existing tests still collected

- [ ] **Step 3: Commit**

```bash
git add conftest.py
git commit -m "feat: add eval_case fixture and clean up marker config"
```

---

### Task 4: Create directory structure and L1/L2 conftest files

**Files:**
- Create: `tests/adp/__init__.py`
- Create: `tests/adp/conftest.py`
- Create: `tests/adp/bkn/__init__.py`
- Create: `tests/adp/bkn/conftest.py`
- Create: `tests/adp/vega/__init__.py`
- Create: `tests/adp/vega/conftest.py`
- Create: `tests/adp/ds/__init__.py`
- Create: `tests/adp/ds/conftest.py`
- Create: `tests/adp/context_loader/__init__.py`
- Create: `tests/adp/context_loader/conftest.py`
- Create: `tests/adp/dataflow/__init__.py`
- Create: `tests/adp/dataflow/conftest.py`
- Create: `tests/adp/execution_factory/__init__.py`
- Create: `tests/adp/execution_factory/conftest.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p tests/adp/bkn tests/adp/vega tests/adp/ds tests/adp/context_loader tests/adp/dataflow tests/adp/execution_factory
touch tests/adp/__init__.py tests/adp/bkn/__init__.py tests/adp/vega/__init__.py tests/adp/ds/__init__.py tests/adp/context_loader/__init__.py tests/adp/dataflow/__init__.py tests/adp/execution_factory/__init__.py
```

- [ ] **Step 2: Create L1 conftest — `tests/adp/conftest.py`**

```python
"""ADP (AI Data Platform) product line conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.api, pytest.mark.adp]


@pytest.fixture(scope="session", autouse=True)
async def ensure_authenticated(cli_agent: CliAgent):
    """Verify CLI is authenticated before running any ADP tests."""
    result = await cli_agent.run_cli("auth", "status")
    if result.exit_code != 0 or "Token status:" not in result.stdout:
        pytest.skip("Not authenticated — run `kweaver auth login` first")
```

- [ ] **Step 3: Create L2 conftest — `tests/adp/bkn/conftest.py`**

```python
"""BKN module conftest — fixtures for knowledge network tests."""

from __future__ import annotations

import os

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.bkn]


@pytest.fixture(scope="session")
async def kn_id(cli_agent: CliAgent) -> str:
    """Find the first available KN ID. Skips if none found."""
    result = await cli_agent.run_cli("bkn", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        pytest.skip("Cannot list KNs")
    for kn in result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if kn_id:
            return kn_id
    pytest.skip("No KN available")


@pytest.fixture(scope="session")
async def kn_with_data(cli_agent: CliAgent) -> tuple[str, str]:
    """Find a KN with object types. Returns (kn_id, ot_name). Skips if none found."""
    result = await cli_agent.run_cli("bkn", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        pytest.skip("Cannot list KNs")
    for kn in result.parsed_json:
        kn_id = str(kn.get("kn_id") or kn.get("id") or "")
        if not kn_id:
            continue
        ot_result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
        if (
            ot_result.exit_code == 0
            and isinstance(ot_result.parsed_json, list)
            and ot_result.parsed_json
        ):
            ot = ot_result.parsed_json[0]
            ot_name = str(ot.get("name") or ot.get("ot_name") or "")
            if ot_name:
                return kn_id, ot_name
    pytest.skip("No KN with object types available")


@pytest.fixture(scope="session")
def db_credentials() -> dict:
    """Read KWEAVER_TEST_DB_* env vars. Skips if not configured."""
    creds = {
        "host": os.environ.get("KWEAVER_TEST_DB_HOST", ""),
        "port": os.environ.get("KWEAVER_TEST_DB_PORT", "3306"),
        "user": os.environ.get("KWEAVER_TEST_DB_USER", ""),
        "password": os.environ.get("KWEAVER_TEST_DB_PASS", ""),
        "database": os.environ.get("KWEAVER_TEST_DB_NAME", ""),
        "db_type": os.environ.get("KWEAVER_TEST_DB_TYPE", "mysql"),
    }
    if not all([creds["host"], creds["user"], creds["password"], creds["database"]]):
        pytest.skip("E2E database not configured (KWEAVER_TEST_DB_* env vars)")
    return creds
```

- [ ] **Step 4: Create L2 conftest — `tests/adp/ds/conftest.py`**

```python
"""Datasource module conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.ds]


@pytest.fixture(scope="session")
async def ds_id(cli_agent: CliAgent) -> str:
    """Find the first available datasource ID. Skips if none found."""
    result = await cli_agent.run_cli("ds", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, dict):
        pytest.skip("Cannot list datasources")
    entries = result.parsed_json.get("entries", [])
    if not isinstance(entries, list) or len(entries) == 0:
        pytest.skip("No datasources available")
    ds = entries[0]
    ds_id = str(ds.get("id") or ds.get("ds_id") or ds.get("datasource_id", ""))
    if not ds_id:
        pytest.skip("Cannot determine datasource ID")
    return ds_id
```

- [ ] **Step 5: Create L2 conftest — `tests/adp/vega/conftest.py`**

```python
"""Vega module conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.vega]


@pytest.fixture(scope="session")
async def catalog_id(cli_agent: CliAgent) -> str:
    """Find the first available Vega catalog ID. Skips if none found."""
    result = await cli_agent.run_cli("vega", "catalog", "list")
    if result.exit_code != 0:
        pytest.skip("Cannot list Vega catalogs")
    catalogs = result.parsed_json
    if not isinstance(catalogs, list) or len(catalogs) == 0:
        # Some responses wrap in a dict
        if isinstance(catalogs, dict):
            catalogs = catalogs.get("items") or catalogs.get("entries") or []
        if not catalogs:
            pytest.skip("No Vega catalogs available")
    cat = catalogs[0] if isinstance(catalogs, list) else catalogs
    cat_id = str(cat.get("id") or cat.get("catalog_id") or "")
    if not cat_id:
        pytest.skip("Cannot determine catalog ID")
    return cat_id


@pytest.fixture(scope="session")
async def resource_id(cli_agent: CliAgent) -> str:
    """Find the first available Vega resource ID. Skips if none found."""
    result = await cli_agent.run_cli("vega", "resource", "list")
    if result.exit_code != 0:
        pytest.skip("Cannot list Vega resources")
    resources = result.parsed_json
    if not isinstance(resources, list) or len(resources) == 0:
        if isinstance(resources, dict):
            resources = resources.get("items") or resources.get("entries") or []
        if not resources:
            pytest.skip("No Vega resources available")
    res = resources[0] if isinstance(resources, list) else resources
    res_id = str(res.get("id") or res.get("resource_id") or "")
    if not res_id:
        pytest.skip("Cannot determine resource ID")
    return res_id
```

- [ ] **Step 6: Create L2 conftest — `tests/adp/context_loader/conftest.py`**

```python
"""Context Loader module conftest."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent

pytestmark = [pytest.mark.context_loader]


@pytest.fixture(scope="session")
async def cl_config_active(cli_agent: CliAgent) -> bool:
    """Ensure context-loader has an active config. Skips if not."""
    result = await cli_agent.run_cli("context-loader", "config", "show")
    if result.exit_code != 0:
        pytest.skip("No active context-loader config")
    return True
```

- [ ] **Step 7: Create placeholder conftest files for pending modules**

`tests/adp/dataflow/conftest.py`:

```python
"""Dataflow module conftest — placeholder, pending CLI implementation."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.dataflow]
```

`tests/adp/execution_factory/conftest.py`:

```python
"""Execution Factory module conftest — placeholder, pending CLI implementation."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.execution_factory]
```

- [ ] **Step 8: Verify directory structure and collection**

Run: `make test`
Expected: all existing tests collected (new directories have no tests yet, so count unchanged)

- [ ] **Step 9: Commit**

```bash
git add tests/adp/
git commit -m "feat: create module directory structure with L1/L2 conftest"
```

---

### Task 5: Migrate BKN tests

**Files:**
- Create: `tests/adp/bkn/test_read.py` (from `tests/scripted/test_bkn_lifecycle.py` read-only tests)
- Create: `tests/adp/bkn/test_schema.py` (from `tests/scripted/test_query.py`)
- Create: `tests/adp/bkn/test_lifecycle.py` (from `tests/scripted/test_bkn_lifecycle.py` destructive)

- [ ] **Step 1: Create `tests/adp/bkn/test_read.py`**

```python
"""BKN read-only acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_bkn_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """bkn list returns a JSON array of knowledge networks."""
    result = await cli_agent.run_cli("bkn", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="bkn list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_export(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn export returns KN data as JSON."""
    result = await cli_agent.run_cli("bkn", "export", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_export", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_search(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn search returns results for a query."""
    result = await cli_agent.run_cli("bkn", "search", kn_id, "test")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_search", [result], det, module="adp/bkn")
    assert det.passed, det.failures
```

- [ ] **Step 2: Create `tests/adp/bkn/test_schema.py`**

```python
"""BKN schema (object-type, relation-type, action-type) acceptance tests."""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_bkn_object_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn object-type list returns object types for a KN."""
    result = await cli_agent.run_cli("bkn", "object-type", "list", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="object-type list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_object_type_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_relation_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case, kn_id: str):
    """bkn relation-type list returns relation types for a KN."""
    result = await cli_agent.run_cli("bkn", "relation-type", "list", kn_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_relation_type_list", [result], det, module="adp/bkn")
    assert det.passed, det.failures


async def test_bkn_object_type_query(
    cli_agent: CliAgent, scorer: Scorer, eval_case, kn_with_data: tuple[str, str]
):
    """bkn object-type query returns instances for an object type."""
    kn_id, ot_name = kn_with_data
    result = await cli_agent.run_cli("bkn", "object-type", "query", kn_id, ot_name)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_object_type_query", [result], det, module="adp/bkn")
    assert det.passed, det.failures
```

- [ ] **Step 3: Create `tests/adp/bkn/test_lifecycle.py`**

```python
"""BKN lifecycle (destructive) acceptance tests."""

from __future__ import annotations

import time

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.destructive
async def test_bkn_full_lifecycle(
    cli_agent: CliAgent, scorer: Scorer, eval_case, db_credentials: dict
):
    """Full lifecycle: ds connect -> bkn create -> export -> search -> cleanup."""
    creds = db_credentials
    ds_name = f"e2e_eval_{int(time.time())}"
    kn_name = f"e2e_kn_{int(time.time())}"
    ds_id = ""
    kn_id = ""
    steps = []

    try:
        # Step 1: ds connect
        connect = await cli_agent.run_cli(
            "ds", "connect", creds["db_type"], creds["host"], creds["port"], creds["database"],
            "--account", creds["user"], "--password", creds["password"], "--name", ds_name,
        )
        steps.append(connect)
        scorer.assert_exit_code(connect, 0, "ds connect")
        scorer.assert_json(connect, "ds connect returns JSON")
        if isinstance(connect.parsed_json, list) and connect.parsed_json:
            first = connect.parsed_json[0]
            ds_id = str(first.get("datasource_id") or first.get("id") or "")
        elif isinstance(connect.parsed_json, dict):
            d = connect.parsed_json
            ds_id = str(d.get("datasource_id") or d.get("id") or "")
        scorer.assert_true(bool(ds_id), "ds connect returns datasource ID")

        # Step 2: bkn create-from-ds
        create = await cli_agent.run_cli(
            "bkn", "create-from-ds", ds_id, "--name", kn_name, "--no-build",
        )
        steps.append(create)
        scorer.assert_exit_code(create, 0, "bkn create-from-ds")
        scorer.assert_json(create, "bkn create-from-ds returns JSON")
        if isinstance(create.parsed_json, dict):
            kn_id = str(create.parsed_json.get("kn_id") or create.parsed_json.get("id") or "")
        scorer.assert_true(bool(kn_id), "bkn create-from-ds returns KN ID")

        # Step 3: bkn export
        export = await cli_agent.run_cli("bkn", "export", kn_id)
        steps.append(export)
        scorer.assert_exit_code(export, 0, "bkn export")
        scorer.assert_json(export, "bkn export returns JSON")

        # Step 4: bkn search
        search = await cli_agent.run_cli("bkn", "search", kn_id, "test")
        steps.append(search)
        scorer.assert_exit_code(search, 0, "bkn search")

    finally:
        if kn_id:
            await cli_agent.run_cli("bkn", "delete", kn_id, "-y")
        if ds_id:
            await cli_agent.run_cli("ds", "delete", ds_id, "-y")

    det = scorer.result()
    await eval_case("bkn_full_lifecycle", steps, det, module="adp/bkn")
    assert det.passed, det.failures
```

- [ ] **Step 4: Verify BKN tests collect**

Run: `python3 -m pytest tests/adp/bkn/ --collect-only -q`
Expected: 7 tests collected (3 read + 3 schema + 1 lifecycle)

- [ ] **Step 5: Commit**

```bash
git add tests/adp/bkn/test_read.py tests/adp/bkn/test_schema.py tests/adp/bkn/test_lifecycle.py
git commit -m "feat: migrate BKN tests to modular structure"
```

---

### Task 6: Migrate DS tests

**Files:**
- Create: `tests/adp/ds/test_read.py`

- [ ] **Step 1: Create `tests/adp/ds/test_read.py`**

```python
"""Datasource read-only acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_datasource_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """ds list returns a JSON dict with an entries array."""
    result = await cli_agent.run_cli("ds", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_true(
        isinstance(result.parsed_json, dict)
        and isinstance(result.parsed_json.get("entries"), list),
        "ds list returns dict with entries array",
    )
    det = scorer.result(result.duration_ms)
    await eval_case("ds_list", [result], det, module="adp/ds")
    assert det.passed, det.failures


async def test_datasource_get(cli_agent: CliAgent, scorer: Scorer, eval_case, ds_id: str):
    """ds get retrieves a specific datasource by ID."""
    result = await cli_agent.run_cli("ds", "get", ds_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("ds_get", [result], det, module="adp/ds")
    assert det.passed, det.failures


async def test_datasource_tables(cli_agent: CliAgent, scorer: Scorer, eval_case, ds_id: str):
    """ds tables returns table info for a datasource."""
    result = await cli_agent.run_cli("ds", "tables", ds_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("ds_tables", [result], det, module="adp/ds")
    assert det.passed, det.failures
```

- [ ] **Step 2: Verify DS tests collect**

Run: `python3 -m pytest tests/adp/ds/ --collect-only -q`
Expected: 3 tests collected

- [ ] **Step 3: Commit**

```bash
git add tests/adp/ds/test_read.py
git commit -m "feat: migrate datasource tests to modular structure"
```

---

### Task 7: Migrate agent tests (temporary ADP location)

**Files:**
- Create: `tests/adp/test_agent.py`

- [ ] **Step 1: Create `tests/adp/test_agent.py`**

```python
"""Agent CRUD acceptance tests.

Temporarily located under adp/. Will move to tests/decision_agent/
when that product line is set up.
"""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def _find_accessible_agent(cli_agent: CliAgent) -> str | None:
    """Find an agent ID that the current user can access."""
    result = await cli_agent.run_cli("agent", "list")
    if result.exit_code != 0 or not isinstance(result.parsed_json, list):
        return None
    for agent in result.parsed_json:
        agent_id = str(agent.get("id") or agent.get("agent_id") or "")
        if not agent_id:
            continue
        check = await cli_agent.run_cli("agent", "get", agent_id)
        if check.exit_code == 0:
            return agent_id
    return None


async def test_agent_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """agent list returns a JSON array."""
    result = await cli_agent.run_cli("agent", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="agent list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("agent_list", [result], det)
    assert det.passed, det.failures


async def test_agent_get(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """agent get returns agent detail."""
    agent_id = await _find_accessible_agent(cli_agent)
    if not agent_id:
        pytest.skip("No accessible agents available")
    result = await cli_agent.run_cli("agent", "get", agent_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("agent_get", [result], det)
    assert det.passed, det.failures


async def test_agent_get_verbose(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """agent get --verbose returns full config."""
    agent_id = await _find_accessible_agent(cli_agent)
    if not agent_id:
        pytest.skip("No accessible agents available")
    result = await cli_agent.run_cli("agent", "get", agent_id, "--verbose")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("agent_get_verbose", [result], det)
    assert det.passed, det.failures
```

- [ ] **Step 2: Verify collection**

Run: `python3 -m pytest tests/adp/test_agent.py --collect-only -q`
Expected: 3 tests collected

- [ ] **Step 3: Commit**

```bash
git add tests/adp/test_agent.py
git commit -m "feat: migrate agent tests to adp/ (temporary location)"
```

---

### Task 8: Delete old test files and update agent test

**Files:**
- Delete: `tests/scripted/test_auth.py`
- Delete: `tests/scripted/test_bkn_lifecycle.py`
- Delete: `tests/scripted/test_datasource.py`
- Delete: `tests/scripted/test_query.py`
- Delete: `tests/scripted/test_agent.py`
- Delete: `tests/scripted/__init__.py`
- Delete: `tests/scripted/` directory
- Modify: `tests/agent/test_full_flow_eval.py` (use eval_case)

- [ ] **Step 1: Update `tests/agent/test_full_flow_eval.py` to use eval_case**

```python
"""Agent-driven full flow evaluation.

Cross-module end-to-end scenario using agent judge for semantic evaluation.
"""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_bkn_list_acceptability(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """Evaluate whether bkn list output is acceptable from a user perspective."""
    result = await cli_agent.run_cli("bkn", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    scorer.assert_json_is_list(result, label="bkn list returns array")
    det = scorer.result(result.duration_ms)
    await eval_case("bkn_list_acceptability", [result], det, module="adp/bkn")
    assert det.passed, det.failures
```

- [ ] **Step 2: Remove old scripted tests**

```bash
rm -rf tests/scripted/
```

- [ ] **Step 3: Verify full collection with new structure**

Run: `make test`
Expected: tests collected from `tests/adp/` and `tests/agent/`, no references to `tests/scripted/`

- [ ] **Step 4: Commit**

```bash
git add -A tests/
git commit -m "refactor: remove tests/scripted/, update agent test to use eval_case"
```

---

### Task 9: Create Vega test stubs

**Files:**
- Create: `tests/adp/vega/test_health.py`
- Create: `tests/adp/vega/test_catalog.py`
- Create: `tests/adp/vega/test_resource.py`
- Create: `tests/adp/vega/test_connector_type.py`

- [ ] **Step 1: Create `tests/adp/vega/test_health.py`**

```python
"""Vega health/stats/inspect acceptance tests."""

from __future__ import annotations

import pytest

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


@pytest.mark.smoke
async def test_vega_health(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega health returns service health status."""
    result = await cli_agent.run_cli("vega", "health")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_health", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_stats(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega stats returns catalog statistics."""
    result = await cli_agent.run_cli("vega", "stats")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_stats", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_inspect(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega inspect returns combined health + catalog + tasks report."""
    result = await cli_agent.run_cli("vega", "inspect")
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_inspect", [result], det, module="adp/vega")
    assert det.passed, det.failures
```

- [ ] **Step 2: Create `tests/adp/vega/test_catalog.py`**

```python
"""Vega catalog acceptance tests."""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_vega_catalog_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega catalog list returns catalogs."""
    result = await cli_agent.run_cli("vega", "catalog", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_catalog_get(cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str):
    """vega catalog get returns catalog details."""
    result = await cli_agent.run_cli("vega", "catalog", "get", catalog_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_catalog_health(cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str):
    """vega catalog health returns health status for a catalog."""
    result = await cli_agent.run_cli("vega", "catalog", "health", catalog_id)
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_health", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_catalog_test_connection(
    cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str
):
    """vega catalog test-connection verifies catalog connectivity."""
    result = await cli_agent.run_cli("vega", "catalog", "test-connection", catalog_id)
    scorer.assert_exit_code(result, 0)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_test_connection", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_catalog_resources(
    cli_agent: CliAgent, scorer: Scorer, eval_case, catalog_id: str
):
    """vega catalog resources lists resources under a catalog."""
    result = await cli_agent.run_cli("vega", "catalog", "resources", catalog_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_catalog_resources", [result], det, module="adp/vega")
    assert det.passed, det.failures
```

- [ ] **Step 3: Create `tests/adp/vega/test_resource.py`**

```python
"""Vega resource acceptance tests."""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_vega_resource_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega resource list returns resources."""
    result = await cli_agent.run_cli("vega", "resource", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_resource_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_resource_get(cli_agent: CliAgent, scorer: Scorer, eval_case, resource_id: str):
    """vega resource get returns resource details."""
    result = await cli_agent.run_cli("vega", "resource", "get", resource_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_resource_get", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_resource_preview(
    cli_agent: CliAgent, scorer: Scorer, eval_case, resource_id: str
):
    """vega resource preview returns a data preview."""
    result = await cli_agent.run_cli("vega", "resource", "preview", resource_id)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_resource_preview", [result], det, module="adp/vega")
    assert det.passed, det.failures
```

- [ ] **Step 4: Create `tests/adp/vega/test_connector_type.py`**

```python
"""Vega connector-type acceptance tests."""

from __future__ import annotations

from lib.agents.cli_agent import CliAgent
from lib.scorer import Scorer


async def test_vega_connector_type_list(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega connector-type list returns supported connector types."""
    result = await cli_agent.run_cli("vega", "connector-type", "list")
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_connector_type_list", [result], det, module="adp/vega")
    assert det.passed, det.failures


async def test_vega_connector_type_get(cli_agent: CliAgent, scorer: Scorer, eval_case):
    """vega connector-type get returns details for a specific type."""
    # First get list to find a type name
    list_result = await cli_agent.run_cli("vega", "connector-type", "list")
    if list_result.exit_code != 0 or not isinstance(list_result.parsed_json, list):
        import pytest
        pytest.skip("Cannot list connector types")
    if not list_result.parsed_json:
        import pytest
        pytest.skip("No connector types available")
    ct = list_result.parsed_json[0]
    ct_type = str(ct.get("type") or ct.get("name") or ct.get("id") or "")
    if not ct_type:
        import pytest
        pytest.skip("Cannot determine connector type identifier")

    result = await cli_agent.run_cli("vega", "connector-type", "get", ct_type)
    scorer.assert_exit_code(result, 0)
    scorer.assert_json(result)
    det = scorer.result(result.duration_ms)
    await eval_case("vega_connector_type_get", [result], det, module="adp/vega")
    assert det.passed, det.failures
```

- [ ] **Step 5: Verify Vega tests collect**

Run: `python3 -m pytest tests/adp/vega/ --collect-only -q`
Expected: 12 tests collected (3 health + 5 catalog + 3 resource + 2 connector-type, note: test_vega_catalog_discover not included yet since it modifies state)

- [ ] **Step 6: Commit**

```bash
git add tests/adp/vega/
git commit -m "feat: add Vega read-only acceptance tests"
```

---

### Task 10: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update AGENTS.md to reflect new structure**

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: update AGENTS.md for modular test structure"
```

---

### Task 11: Final verification

- [ ] **Step 1: Verify full collection**

Run: `make test`
Expected: all tests collected from `tests/adp/` and `tests/agent/`, zero from `tests/scripted/`

- [ ] **Step 2: Verify lint passes**

Run: `make lint`
Expected: no errors

- [ ] **Step 3: Verify per-module collection**

Run: `python3 -m pytest tests/adp/bkn/ --collect-only -q`
Expected: 7 tests

Run: `python3 -m pytest tests/adp/vega/ --collect-only -q`
Expected: 12 tests

Run: `python3 -m pytest tests/adp/ds/ --collect-only -q`
Expected: 3 tests

- [ ] **Step 4: Verify marker filtering**

Run: `python3 -m pytest tests/ --collect-only -q -m smoke`
Expected: shows only smoke-marked tests (bkn_list, ds_list, vega_health)

Run: `python3 -m pytest tests/ --collect-only -q -m bkn`
Expected: shows only BKN tests

- [ ] **Step 5: Commit any remaining fixes if needed**
