.DEFAULT_GOAL := help
PYTHON := .venv/bin/python

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Dev setup ─────────────────────────────────────────────────────────────────

.PHONY: install
install:  ## Create venv and install all dependencies
	uv venv && uv pip install -e ".[dev]"

# ── Tests & lint ──────────────────────────────────────────────────────────────

.PHONY: test
test:  ## Run the full pytest suite
	$(PYTHON) -m pytest -v

.PHONY: lint
lint:  ## Lint and format check with ruff
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

.PHONY: fmt
fmt:  ## Auto-fix formatting with ruff
	.venv/bin/ruff check --fix . && .venv/bin/ruff format .

# ── Job fetching ──────────────────────────────────────────────────────────────
# Pass limit=N to override results per query, e.g.: make fetch-ds limit=50

limit ?=  # empty by default — script falls back to config.yaml value
LIMIT_ARG = $(if $(limit),--limit $(limit),)

.PHONY: fetch
fetch:  ## Fetch all roles defined in config.yaml  [limit=N]
	$(PYTHON) scripts/run_fetch.py $(LIMIT_ARG)

.PHONY: fetch-ds
fetch-ds:  ## Fetch data science roles  [limit=N]
	$(PYTHON) scripts/run_fetch.py \
		--what "data scientist" \
		--what "machine learning engineer" \
		--what "AI engineer" \
		$(LIMIT_ARG)

.PHONY: fetch-swe
fetch-swe:  ## Fetch software developer roles  [limit=N]
	$(PYTHON) scripts/run_fetch.py \
		--what "software developer" \
		--what "backend developer" \
		--what "python developer" \
		$(LIMIT_ARG)

.PHONY: fetch-ml
fetch-ml:  ## Fetch ML/AI engineering roles  [limit=N]
	$(PYTHON) scripts/run_fetch.py \
		--what "ML engineer" \
		--what "MLOps engineer" \
		--what "AI researcher" \
		$(LIMIT_ARG)
