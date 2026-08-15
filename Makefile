# Convenience wrapper around tasks.py.
#
# Every task is defined in `tasks.py`, not here: Windows has no `make`, and a
# second copy of the task list in a .bat file would drift from this one. On any
# platform `python tasks.py <task>` does exactly what `make <task>` does.
#
#   make dataset N=5 DATASET=/tmp/thu    ==    python tasks.py dataset -n 5 -o /tmp/thu

PYTHON  ?= python3
TASKS    = $(PYTHON) tasks.py

DATASET ?= data/dataset60
N       ?= 20
LAYOUT  ?=

.DEFAULT_GOAL := help
.PHONY: help setup setup-synthdog setup-html setup-genalog textures \
        receipts preview preview-grid dataset dataset-clean proof showcase \
        check-rules check-corpus distribution list-degradations \
        lint format check clean

help:  ## Show this help
	@$(TASKS)

# ---------------------------------------------------------------- setup

setup:           ## Build all three renderer environments
	$(TASKS) setup
setup-synthdog:  ## glyph renderer: synthtiger (needs Python 3.8-3.11)
	$(TASKS) setup-synthdog
setup-html:      ## HTML renderer: playwright + a headless browser
	$(TASKS) setup-html
setup-genalog:   ## genalog renderer: WeasyPrint + PyMuPDF
	$(TASKS) setup-genalog
textures:        ## Regenerate the shared paper and background textures
	$(TASKS) textures

# ------------------------------------------------------------ generation

receipts:        ## 100 receipts with the glyph renderer, via the synthtiger CLI
	$(TASKS) receipts
dataset:         ## Build a labelled dataset with all three renderers (N=20 each)
	$(TASKS) dataset -o $(DATASET) -n $(N)
dataset-clean:   ## The same dataset with no ageing and no distortion at all
	$(TASKS) dataset-clean -o $(DATASET) -n $(N)
proof:           ## Run Tesseract over $(DATASET) and score it against the labels
	$(TASKS) proof --dataset $(DATASET)
showcase:        ## One before/after image per degradation into samples/degradation/
	$(TASKS) showcase
preview:         ## Render a grid of sample receipts to eyeball the config
	$(TASKS) preview
preview-grid:    ## Print a sampled receipt as text (LAYOUT=<id> to pin one)
	@$(TASKS) preview-grid $(if $(LAYOUT),--layout $(LAYOUT),)

# ------------------------------------------------------------- the rules

check-rules:     ## Validate rules/: unreachable values, bad tags, missing files
	$(TASKS) check-rules
check-corpus:    ## Validate corpus/: missing files, wrong column counts
	@$(TASKS) check-corpus
distribution:    ## Show what 2000 draws from the rules actually look like
	@$(TASKS) distribution
list-degradations:  ## Names usable in an augmentation chain
	@$(TASKS) list-degradations

# -------------------------------------------------------------- quality

check:           ## Byte-compile every tracked Python file (no dependencies needed)
	@$(TASKS) check
lint:            ## Lint the first-party code (correctness and imports, not formatting)
	$(TASKS) lint
format:          ## Apply the fixes ruff can make safely
	$(TASKS) format
clean:           ## Remove caches and generated output
	$(TASKS) clean
