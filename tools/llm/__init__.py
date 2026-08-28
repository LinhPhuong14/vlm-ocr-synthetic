"""The generation step, which runs beside the pipeline and never inside it.

See `client.py` for why that boundary exists and `tests/test_llm.py` for the
test that keeps it. Nothing in this package is imported by `generators/` or
`pipeline/`; what it produces is ordinary committed files that they read.
"""
