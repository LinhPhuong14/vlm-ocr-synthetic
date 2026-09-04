# Why synthdog stopped at Python 3.12

> **This constraint is gone.** The glyph renderer was deleted
> ([renderers.md](renderers.md)) and took its pins with it; `make setup` now
> runs on any Python 3.9+. The page stays because the measurements cost two
> days and answer a question that outlives the backend — *what does depending
> on an unmaintained package actually cost, and how do you find out?* Read it
> as a record, not as instructions.

`generators/synthdog/requirements.txt` pinned `pillow<10`, `numpy<2` and
`opencv-python<5`, and capped the interpreter at 3.12. Those were not
conservative guesses — every one of them was hit.

Everything below was measured on **CPython 3.14.7**, installed from
python-build-standalone.

## The wall is not one package

| attempt | result |
| ------- | ------ |
| `pip install pygame` | no cp314 wheel exists → falls back to a source build, which **fails** |
| `pip install synthtiger` | pulls `pygame==2.6.1` → same failure |
| `pip install pygame-ce` | **works** (2.5.8 ships cp314 wheels, and provides the same `import pygame`) |
| synthtiger + pygame-ce, NumPy 2 | `import synthtiger` → `AttributeError: np.sctypes was removed in the NumPy 2.0 release` (via `imgaug`) |
| synthtiger + pygame-ce, NumPy 1.26 (2 min source build) | `import synthtiger` → scipy dies on `np.long`, removed in NumPy 2 |

So swapping `pygame` for `pygame-ce` clears the first wall and reveals the real
one: **`imgaug` has been unmaintained since 2020** and needs NumPy 1.x APIs,
while every scipy build that exists for 3.14 is compiled against NumPy 2. No
combination of pins satisfies both.

## Where the wheels actually stop

| package | version needed by synthtiger | last CPython with a wheel |
| ------- | ---------------------------- | ------------------------- |
| `pygame` | 2.6.1 | cp313 |
| `numpy` | 1.26.4 (last 1.x) | **cp312** |
| `scipy` | 1.13.1 (last supporting NumPy 1.x) | **cp312** |
| `imgaug` | 0.4.0 | pure Python, but needs NumPy 1.x |

Add Pillow to that table and the ceiling drops again:

| package | version needed | last CPython with a Linux wheel |
| ------- | -------------- | ------------------------------- |
| `pillow` | 9.5.0 (`pillow<10`) | **cp311** |

**CPython 3.11 was the last interpreter where the whole stack installed from
wheels.** On 3.12, `pillow<10` resolves to 9.5.0, whose manylinux wheels stop at
cp311, so pip falls back to a source build that fails. Measured on this
repository, not inferred from release notes — which is why `make setup` refused
3.12 even though synthtiger itself would have run there.

The other two pins had their own causes, both documented in that same
requirements file: synthtiger 1.2.1 calls `ImageFont.getsize()`, removed in
Pillow 10; and `opencv-python>=5` requires NumPy 2, which conflicts with
`numpy<2`.

## The failure mode to recognise

synthtiger caught exceptions inside its generation loop and retried, so a
version mismatch did not raise — **it hung**. Generation produced nothing and
printed nothing. This is the part worth carrying forward: a dependency that
retries instead of failing turns an install problem into a silent one, and the
cost is not the pin, it is that the pin is invisible until someone waits an
hour for images that were never coming.

## What replaced it

One renderer, one environment, and its dependencies are ones that still ship
wheels for the current interpreter. The repo's floor is Python 3.9 — set by the
rule-base, which has to import without any image library at all — and there is
no ceiling. If a future dependency wants to introduce one, this page is the
argument for choosing a different dependency.
