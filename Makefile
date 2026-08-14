# Task shortcuts. Each renderer has its own environment -- see README.md.
PYTHON       ?= python3
SYNTHDOG      = generators/synthdog
SYNTHDOG_VENV = $(SYNTHDOG)/.venv
HTML_VENV     = generators/html/.venv
GENALOG_VENV  = generators/genalog/.venv

# Anything that only needs numpy/opencv/pyyaml can run in whichever venv exists.
TOOLPY        = $(SYNTHDOG_VENV)/bin/python

DATASET      ?= data/dataset60
N            ?= 20
LAYOUT       ?=

.DEFAULT_GOAL := help
.PHONY: help setup setup-synthdog setup-html setup-genalog textures \
        receipts preview preview-grid dataset proof showcase \
        check-rules check-corpus distribution list-degradations \
        lint format check clean

help:  ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup

setup: setup-synthdog setup-html setup-genalog  ## Build all three renderer environments

setup-synthdog:  ## glyph renderer: synthtiger (needs Python 3.8-3.11)
	@$(PYTHON) -c 'import sys; v=sys.version_info; \
	  sys.exit(0 if v < (3, 12) else "synthdog needs Python 3.8-3.11; see docs/python-versions.md")'
	$(PYTHON) -m venv $(SYNTHDOG_VENV)
	$(SYNTHDOG_VENV)/bin/pip install -q -U pip setuptools wheel
	$(SYNTHDOG_VENV)/bin/pip install -q -r $(SYNTHDOG)/requirements.txt
	$(SYNTHDOG_VENV)/bin/python -c "import synthtiger, PIL, numpy, cv2; \
	  print('synthtiger', synthtiger.__version__, '| pillow', PIL.__version__)"

setup-html:  ## HTML renderer: playwright + a headless browser
	$(PYTHON) -m venv $(HTML_VENV)
	$(HTML_VENV)/bin/pip install -q -U pip
	$(HTML_VENV)/bin/pip install -q -r generators/html/requirements.txt
	$(HTML_VENV)/bin/python -c "import playwright, cv2; print('html renderer ready')"

setup-genalog:  ## genalog renderer: WeasyPrint + PyMuPDF
	$(PYTHON) -m venv $(GENALOG_VENV)
	$(GENALOG_VENV)/bin/pip install -q -U pip
	@# genalog pins numpy 1.18 / WeasyPrint 51, neither of which has a wheel for
	@# Python 3.9+; the pins are unused by what we call. See generators/genalog/.
	$(GENALOG_VENV)/bin/pip install -q --no-deps genalog
	$(GENALOG_VENV)/bin/pip install -q -r generators/genalog/requirements.txt
	$(GENALOG_VENV)/bin/python -c "import genalog, weasyprint; print('genalog renderer ready')"

textures:  ## Regenerate the shared paper textures into textures/paper/
	$(TOOLPY) tools/make_textures.py

# ------------------------------------------------------------ generation

receipts:  ## 100 receipts with the glyph renderer, via the synthtiger CLI
	cd $(SYNTHDOG) && .venv/bin/synthtiger -o ./outputs/VNReceipt -c 100 -w 4 -v \
	  template_receipt.py SynthVNReceipt config_vi_receipt.yaml

dataset:  ## Build a labelled dataset with all three renderers (N=20 each)
	$(TOOLPY) tools/generate_dataset.py -o $(DATASET) -n $(N)

proof:  ## Run Tesseract over $(DATASET) and score it against the labels
	$(TOOLPY) tools/ocr_proof.py $(DATASET)

showcase:  ## One before/after image per degradation into samples/degradation/
	$(TOOLPY) tools/degradation_showcase.py

preview:  ## Render a grid of sample receipts to eyeball the config
	cd $(SYNTHDOG) && .venv/bin/python tools/preview_receipt.py \
	  --count 8 --grid 4 --seed 2026 --out /tmp/preview

preview-grid:  ## Print a sampled receipt as text (LAYOUT=<id> to pin one)
	@$(PYTHON) tools/preview_grid.py $(if $(LAYOUT),--layout $(LAYOUT),--all)

# ------------------------------------------------------------- the rules

check-rules:  ## Validate rules/: unreachable values, bad tags, missing files
	$(TOOLPY) tools/rules_report.py --check

check-corpus:  ## Validate corpus/: missing files, wrong column counts
	@$(PYTHON) tools/rules_report.py --corpus

distribution:  ## Show what 2000 draws from the rules actually look like
	@$(PYTHON) tools/rules_report.py --distribution

list-degradations:  ## Names usable in an augmentation chain
	@$(TOOLPY) -c "import degradation; print('\n'.join(degradation.names()))"

# -------------------------------------------------------------- quality

check:  ## Byte-compile every tracked Python file (no dependencies needed)
	@git ls-files '*.py' | grep -v '^generators/html-table/' | xargs -r $(PYTHON) -m py_compile && \
	  echo "all python files compile"

lint:  ## Lint the first-party code (correctness and imports, not formatting)
	ruff check .

format:  ## Apply the fixes ruff can make safely
	ruff check --fix .

clean:  ## Remove caches and generated output
	rm -rf .ruff_cache **/__pycache__ $(SYNTHDOG)/outputs /tmp/preview
