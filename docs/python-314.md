# Why synthdog stops at Python 3.12

`synthdog/requirements.txt` pins `pillow<10`, `numpy<2` and `opencv-python<5`,
and caps the interpreter at 3.12. Those are not conservative guesses — every
one of them was hit. This page records the measurements so nobody has to
rediscover them, and so the cap is not "relaxed" by someone on a new laptop.

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

`numpy` and `scipy` are what set the ceiling: **CPython 3.11 is the last interpreter where the whole
stack installs from wheels** on Linux: `pillow<10` resolves to 9.5.0, whose
manylinux wheels stop at cp311, so 3.12 falls back to a source build that
fails. Measured here, not inferred.

## What this means in practice

- Create the synthdog environment with a 3.8 – 3.12 interpreter. `make setup`
  refuses to continue on anything newer rather than producing a broken venv.
- If your system Python is 3.13+, get an older one rather than relaxing a pin:
  `uv python install 3.12`, `pyenv install 3.12`, or your distribution's
  `python3.12` package.
- The other two pins have their own causes, both documented in
  `synthdog/requirements.txt`: synthtiger 1.2.1 calls `ImageFont.getsize()`,
  removed in Pillow 10; and `opencv-python>=5` requires NumPy 2, which conflicts
  with `numpy<2`.

## The failure mode to recognise

synthtiger catches exceptions inside its generation loop and retries, so a
version mismatch does not raise — **it hangs**. If generation produces nothing
and prints nothing, that is what has happened. Re-run with `-v` to see the
traceback.
