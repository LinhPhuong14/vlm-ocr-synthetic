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
TABLES  ?= 60
PROFILE ?= data/profile
PROFILE_N ?= 8
LAYOUT  ?=

.DEFAULT_GOAL := help
.PHONY: help setup setup-synthdog setup-html setup-genalog setup-writevit \
        textures patterns handwriting signatures \
        receipts preview preview-grid dataset dataset-clean proof showcase \
        ornaments templates \
        preflight check-rules check-corpus check-boxes migrate-metadata \
        distribution monitor \
        list-degradations legibility \
        lint format check clean

help:  ## Show this help
	@$(TASKS)

# ---------------------------------------------------------------- setup

setup:           ## Build the renderer environment (html)
	$(TASKS) setup
setup-html:      ## HTML renderer: playwright + a headless browser
	$(TASKS) setup-html
setup-writevit:  ## handwriting: clone WriteViT beside the repo, fetch its weights
	$(TASKS) setup-writevit
setup-synthdog:  ## patterns: synthtiger (retired as a document backend)
	$(TASKS) setup-synthdog
setup-genalog:   ## WeasyPrint + PyMuPDF (retired; only to re-read old sets)
	$(TASKS) setup-genalog
patterns:        ## Regenerate every shared pattern: paper, backgrounds, ornaments
	$(TASKS) patterns
textures:        ## Regenerate the shared paper and background textures
	$(TASKS) textures
ornaments:       ## Regenerate the seals and flourishes in textures/ornament
	$(TASKS) ornaments
templates:       ## Print the reference sheets in samples/*-templates
	$(TASKS) templates
signatures:      ## Regenerate samples/signatures: the style grid and two signed sheets
	$(TASKS) signatures

# ------------------------------------------------------------ generation

receipts:        ## 100 receipts with the glyph renderer, via the synthtiger CLI
	$(TASKS) receipts
dataset:         ## Build a labelled dataset with the html renderer (N=20)
	$(TASKS) dataset -o $(DATASET) -n $(N)
dataset-clean:   ## The same dataset with no ageing and no distortion at all
	$(TASKS) dataset-clean -o $(DATASET) -n $(N)
tables:          ## Table-structure images, from the html backend (TABLES=60)
	$(TASKS) tables -o data/tables60 -n $(TABLES)
handwriting:     ## Regenerate data/hand12: every form field filled in with ink
	$(TASKS) handwriting
run:             ## Run pipeline.yaml: preflight, shards in parallel, assemble
	$(TASKS) run
baseline-write:  ## Capture the golden fingerprint (needs REASON="...")
	$(TASKS) baseline-write --reason "$(REASON)"
baseline-verify: ## Regenerate the fixed plans and compare to the golden file
	$(TASKS) baseline-verify
proof:           ## Run Tesseract over $(DATASET) and score it against the labels
	$(TASKS) proof --dataset $(DATASET)
profile:         ## Time every stage of every renderer into $(PROFILE)
	$(TASKS) profile --count $(PROFILE_N) --out $(PROFILE)
check-boxes:     ## Verify every renderer's boxes still land on its text
	$(TASKS) check-boxes --dataset $(DATASET)
migrate-metadata: ## Bring $(DATASET)'s metadata.jsonl into the current schema
	$(TASKS) migrate-metadata --dataset $(DATASET)
showcase:        ## One before/after image per degradation into samples/degradation/
	$(TASKS) showcase
preview:         ## Render a grid of sample receipts to eyeball the config
	$(TASKS) preview
preview-grid:    ## Print a sampled receipt as text (LAYOUT=<id> to pin one)
	@$(TASKS) preview-grid $(if $(LAYOUT),--layout $(LAYOUT),)

# ------------------------------------------------------------- the rules

preflight:       ## Every check that must pass before generating an image
	@$(TASKS) preflight
check-rules:     ## Validate rules/: unreachable values, bad tags, missing files
	$(TASKS) check-rules
blanks:          ## The phôi gốc each document is drawn from, and any drift
	@$(TASKS) blanks
check-corpus:    ## Validate corpus/: missing files, wrong column counts
	@$(TASKS) check-corpus
distribution:    ## Show what 2000 draws from the rules actually look like
	@$(TASKS) distribution
monitor:         ## Rule space; add RUN=data/run01 to watch a run instead
	@$(TASKS) monitor $(if $(RUN),--run $(RUN),)
list-degradations:  ## Names usable in an augmentation chain
	@$(TASKS) list-degradations
legibility:      ## does an ageing chain age the text out of its own label boxes?
	$(TASKS) legibility

# -------------------------------------------------------------- quality

check:           ## Byte-compile every tracked Python file (no dependencies needed)
	@$(TASKS) check
lint:            ## Lint the first-party code (correctness and imports, not formatting)
	$(TASKS) lint
format:          ## Apply the fixes ruff can make safely
	$(TASKS) format
clean:           ## Remove caches and generated output
	$(TASKS) clean
