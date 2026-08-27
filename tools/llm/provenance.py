"""Where a generated line came from, written beside it.

A corpus file is plain text a Vietnamese speaker edits by hand -- `corpus.py`
says so and it is the reason the format is what it is. Once a model can add to
that file, the file has two kinds of line in it, and a reader who cannot tell
them apart cannot do their job: "is `Dầu-tahini` a real product I have not heard
of, or did a 7B invent it?" is a question the file has to answer.

So a generated block is fenced by comments naming the model's digest, the
prompt, the seed and the day:

    # >>> llm qwen2.5:7b-instruct@845dbda0ea48 prompt=items:3f2a seed=11 2026-08-26
    Nước mắm Nam Ngư 500ml\t28000\t35000
    ...
    # <<< llm

Comment lines, so every existing reader skips them untouched -- `corpus._lines`
already drops anything starting with `#`, and did before this file existed.

Two things this deliberately does not do. It does not put the provenance in a
sidecar file, because a sidecar goes stale the moment somebody edits the line by
hand and nothing notices. And it does not claim the block can be regenerated:
the stamp records what was asked and what answered, not a promise that asking
again returns the same text. See `client.py` on what is and is not reproducible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

OPEN = "# >>> llm"
CLOSE = "# <<< llm"

_STAMP = re.compile(
    r"^# >>> llm (?P<model>\S+)@(?P<digest>\S+) prompt=(?P<prompt>\S+) "
    r"seed=(?P<seed>\d+) (?P<date>\d{4}-\d{2}-\d{2})\s*$")


@dataclass(frozen=True)
class Stamp:
    model: str
    digest: str
    prompt: str          # `name:sha` -- which prompt file, and its content hash
    seed: int
    date: str            # ISO day; passed in rather than read off the clock

    def open_line(self) -> str:
        return (f"{OPEN} {self.model}@{self.digest} prompt={self.prompt} "
                f"seed={self.seed} {self.date}")

    def block(self, lines: list[str]) -> str:
        """The fenced block, ready to append. Empty when there is nothing."""
        if not lines:
            return ""
        return "\n".join([self.open_line(), *lines, CLOSE, ""])


def blocks(text: str) -> list[tuple[Stamp, list[str]]]:
    """Every generated block in a file, with its stamp.

    For the audit direction: given a corpus, which of it is a model's? A test
    uses this, and so does anyone deciding whether to trust a line.
    """
    out: list[tuple[Stamp, list[str]]] = []
    current: Stamp | None = None
    body: list[str] = []
    for line in text.splitlines():
        match = _STAMP.match(line)
        if match:
            current = Stamp(model=match["model"], digest=match["digest"],
                            prompt=match["prompt"], seed=int(match["seed"]),
                            date=match["date"])
            body = []
        elif line.strip() == CLOSE and current is not None:
            out.append((current, body))
            current, body = None, []
        elif current is not None:
            body.append(line)
    return out


def generated(text: str) -> set[str]:
    """Every line in a file that a model wrote. For dedup against itself."""
    return {line for _stamp, body in blocks(text) for line in body if line.strip()}


def human(text: str) -> set[str]:
    """Every non-comment line a PERSON wrote.

    The complement of `generated`, and the more useful half: a generator must
    not propose something the corpus already has, whoever put it there.
    """
    every = {line for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith("#")}
    return every - generated(text)


__all__ = ["CLOSE", "OPEN", "Stamp", "blocks", "generated", "human"]
