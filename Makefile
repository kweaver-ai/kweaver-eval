.PHONY: test test-at test-at-full test-smoke test-destructive test-report lint ci install
.PHONY: test-bkn test-vega test-ds test-context-loader

install:
	pip install -e ".[dev]"

# UT semantic: no external deps, verify test collection only
test:
	python3 -m pytest tests/ --collect-only -q

# Allure flag (only if plugin is installed)
ALLURE_FLAG := $(shell python3 -c "import allure_pytest" 2>/dev/null && echo "--alluredir=test-result/allure")

# Acceptance tests
test-at:
	@mkdir -p test-result
	python3 -m pytest tests/ -v -s --tb=short -m api \
		--junitxml=test-result/junit.xml $(ALLURE_FLAG)

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
		--junitxml=test-result/junit.xml $(ALLURE_FLAG)

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
