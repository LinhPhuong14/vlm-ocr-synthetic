# Task shortcuts. Each generator has its own environment -- see README.md.
PYTHON       ?= python3
SYNTHDOG      = generators/synthdog
SYNTHDOG_VENV = generators/synthdog/.venv

.DEFAULT_GOAL := help
.PHONY: help setup receipts preview lint format check clean

help:  ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Create synthdog's venv and install its pinned dependencies
	@$(PYTHON) -c 'import sys; v=sys.version_info; \
	  sys.exit(0 if v < (3, 12) else "synthdog needs Python 3.8-3.11; see docs/python-versions.md")'
	$(PYTHON) -m venv $(SYNTHDOG_VENV)
	$(SYNTHDOG_VENV)/bin/pip install -q -U pip setuptools wheel
	$(SYNTHDOG_VENV)/bin/pip install -q -r $(SYNTHDOG)/requirements.txt
	$(SYNTHDOG_VENV)/bin/python -c "import synthtiger, PIL, numpy, cv2; \
	  print('synthtiger', synthtiger.__version__, '| pillow', PIL.__version__)"

receipts:  ## Generate 100 Vietnamese receipts into generators/synthdog/outputs/
	cd $(SYNTHDOG) && .venv/bin/synthtiger -o ./outputs/VNReceipt -c 100 -w 4 -v \
	  template_receipt.py SynthVNReceipt config_vi_receipt.yaml

preview:  ## Render a grid of sample receipts to eyeball the config
	cd $(SYNTHDOG) && .venv/bin/python tools/preview_receipt.py \
	  --count 8 --grid 4 --seed 2026 --out /tmp/preview

check:  ## Byte-compile every tracked Python file (no dependencies needed)
	@git ls-files '*.py' | grep -v '^generators/html-table/' | xargs -r $(PYTHON) -m py_compile && \
	  echo "all python files compile"

lint:  ## Lint the generators (correctness and imports, not formatting)
	ruff check .

format:  ## Apply the fixes ruff can make safely
	ruff check --fix .

clean:  ## Remove caches and generated output
	rm -rf .ruff_cache **/__pycache__ $(SYNTHDOG)/outputs /tmp/preview
