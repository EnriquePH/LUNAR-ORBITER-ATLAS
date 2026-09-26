PYTHON := .venv/bin/python
SITE_PORT := 8765
# Missions for `make download`, e.g. make download MISSIONS="1 4" (default: all).
MISSIONS :=
MARKDOWN := README.md CLAUDE.md PLAN.md CHANGELOG.md

.PHONY: help install run stop download test lint lint-md format check icons site clean

help:  ## List the available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-10s %s\n", $$1, $$2}'

.venv:
	python3 -m venv .venv
	$(PYTHON) -m pip install --quiet --upgrade pip

install: .venv  ## Create .venv and install the viewer with dev tools
	$(PYTHON) -m pip install --quiet -e ".[dev]"

run:  ## Start the viewer on the port from config.json
	./scripts/run.sh

stop:  ## Stop the viewer running on the port from config.json
	./scripts/run.sh --stop

download:  ## Pre-fill the photo cache in data/lpi (MISSIONS="1 4" to limit)
	$(PYTHON) -m orbiter.catalog $(MISSIONS)

test:  ## Run the test suite
	$(PYTHON) -m pytest

lint:  ## Check code style with Ruff
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

lint-md:  ## Lint the Markdown files (needs uv; line length not checked)
	uvx pymarkdownlnt --disable-rules md013 scan $(MARKDOWN)

format:  ## Format the code with Ruff, then apply its lint fixes
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

check: lint test  ## Lint and test

icons:  ## Build favicon and icons from assets/icon.png and assets/logo.png
	$(PYTHON) scripts/build_icons.py

site:  ## Serve the GitHub Pages site locally on http://127.0.0.1:8765/
	$(PYTHON) -m http.server $(SITE_PORT) --bind 127.0.0.1 --directory site

clean:  ## Remove tool caches (keeps data/ and draft/)
	rm -rf .pytest_cache .ruff_cache build *.egg-info
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
