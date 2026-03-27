.PHONY: test test-full test-report lint ci install

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-full:
	EVAL_AGENT_JUDGE=1 pytest tests/ -v --tb=short

test-report:
	EVAL_AGENT_JUDGE=1 EVAL_REPORT=1 pytest tests/ -v --tb=short

lint:
	ruff check .
	pyright

ci: lint test
