PYTHON := .venv/bin/python

.PHONY: help install run test lint format check clean icons

help:  ## List the available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-9s %s\n", $$1, $$2}'

.venv:
	python3 -m venv .venv
	$(PYTHON) -m pip install --quiet --upgrade pip

install: .venv  ## Create .venv and install the viewer with dev tools
	$(PYTHON) -m pip install --quiet -e ".[dev]"

run:  ## Start the viewer on the port from config.json
	./scripts/run.sh

test:  ## Run the test suite
	$(PYTHON) -m pytest

lint:  ## Check code style with Ruff
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:  ## Format the code with Ruff
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

check: lint test  ## Lint and test

icons:  ## Render favicon and PNG icons from orbiter/assets/logo.svg
	./scripts/build_icons.sh

clean:  ## Remove tool caches (keeps data/ and draft/)
	rm -rf .pytest_cache .ruff_cache build *.egg-info
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
