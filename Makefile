# Everything you need after `git clone`. See CONTRIBUTING.md.
PYTHON ?= python3
VENV   ?= .venv
BIN     = $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help setup test test-fast lint format doctor render benchmark gallery dataset clean

help:  ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Create the venv and install everything, including chromium
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q -U pip
	$(BIN)/pip install -q -e ".[all]"
	$(BIN)/playwright install chromium || \
	  echo "note: chromium not installed; the html backend will report why"
	$(BIN)/python -m vlm_ocr_synthetic doctor

test:  ## Run the whole suite
	$(BIN)/python -m pytest

test-fast:  ## Run everything that does not render (sub-second)
	$(BIN)/python -m pytest -m "not slow"

lint:  ## Check style and imports
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:  ## Fix what can be fixed automatically
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

doctor:  ## Is this environment usable?
	$(BIN)/python -m vlm_ocr_synthetic doctor

render:  ## Render the samples with every backend, into data/
	$(BIN)/python -m vlm_ocr_synthetic render -r all

gallery:  ## Rebuild the README previews in data/samples/
	$(BIN)/python experiments/build_gallery.py

benchmark:  ## Compare the backends, into data/benchmark/
	$(BIN)/python -m vlm_ocr_synthetic benchmark --pages 3

dataset:  ## Plan a dataset run without rendering anything
	$(BIN)/python -m vlm_ocr_synthetic generate --dry-run

clean:  ## Remove caches and generated pages (keeps data/samples and the report)
	rm -rf .pytest_cache .ruff_cache **/__pycache__ build dist *.egg-info
	rm -rf data/dataset data/compare
