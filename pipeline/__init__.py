"""Everything that runs a generation job.

`preflight` is the only member so far. Sharding, parallelism and resume land
here next, which is why it is a package rather than one more script in
`tools/`: those need to import each other, and `tools/` is a flat drawer of
independent entry points.
"""
