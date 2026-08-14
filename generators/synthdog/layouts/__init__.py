"""
Donut
Copyright (c) 2022-present NAVER Corp.
MIT License

SynthDoG's own grid-stacking code, used only by the ORIGINAL `template.py`
(English/Japanese/Korean/Chinese wiki pages). The receipt template does not
touch it.

Not to be confused with `rulebase/layouts/`, which holds the five receipt bố
cục -- those are YAML measured off real receipts, and are what you want if you
came here looking for "the layouts".
"""
from layouts.grid import Grid
from layouts.grid_stack import GridStack

__all__ = ["Grid", "GridStack"]
