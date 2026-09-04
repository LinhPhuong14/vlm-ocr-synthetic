"""One local model, and the boundary it is not allowed to cross.

    from agent.ollama import Model
    model = Model()                       # qwen2.5:7b-instruct on 127.0.0.1
    reply = model.chat(system, user, seed=7)

**Nothing under `agent/` may be imported by `generators/` or `pipeline/`,
and `tests/test_llm.py` asserts it.** That is the whole architecture in one
sentence, and it is worth the sentence because the tempting design is the wrong
one.

The tempting design is to call a model while a page is being drawn, so every
page gets fresh wording. What that costs is the promise the rest of the
repository is built on: the same seed draws the same bytes. `tools/baseline.py`
fingerprints images, `tests/test_worklist.py` renders one page two ways and
compares sha256, and `docs/renderers.md` compares backends on the claim that
only the drawing differs. A generator in the render path retires all three, and
it retires them quietly -- the images still come out, they are simply no longer
the same images.

So the model runs **here**, in a step of its own, and what it produces is an
ordinary file in git: a corpus line, a layout YAML, a variation list. A person
reads the diff before it draws anything. The renderer keeps reading files, the
way it always has, and cannot tell that a file was written by a model rather
than by a person -- which is exactly the property that keeps the render path
deterministic and offline.

## What is reproducible here, and what is not

The model is given a seed and a temperature and Ollama honours both, so the
same prompt against the same weights on the same build tends to give the same
text. **Tends to** is as far as this file will go: a different Ollama build, a
different quantisation, or a different thread count can move a token, and
nothing downstream should depend on it not moving.

What IS reproducible is the committed file. That is the artefact, the prompt
and the model are recorded beside it by `provenance.py`, and re-running the
generator is a way to get *more* material rather than a way to get the same
material back.

## Local, or a server -- one environment variable apart

`VLM_LLM_HOST` points this at another machine, and nothing else changes: a
remote Ollama speaks the same `/api/chat` as a local one. That is why the
client stayed Ollama-shaped instead of becoming an OpenAI-compatible one --
"put the model on the GPU box" should be a hostname, not a rewrite.

What does NOT move with the hostname is the boundary at the top of this file.
A server makes the tempting design cheaper (the latency argument goes away) and
no more correct: a page whose wording came from a live call is a page nobody
can redraw. See `docs/llm-in-pipeline.md` for the design that gets per-page
LLM variety and keeps a run reproducible -- it works by writing the model's
decisions down BEFORE the render rather than by calling from inside it.

The default is still loopback, and the reasons that put it there stand: no key
leaves the machine, no run depends on a service being up. The cost is quality
and speed -- a 7B at 4-bit on CPU runs about 5 tokens a second and writes
`Dầu-tahini` when asked for groceries. Which is why every generator in this
package validates what comes back and reports what it threw away, rather than
trusting it.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parent
PROMPT_DIR = TOOLS_ROOT / "prompts"

# Where the weights are, and which ones. Both are read from the environment so
# a machine with a GPU -- or a shared server with a 70B on it -- is pointed at
# without editing code and without a second config file:
#
#     VLM_LLM_HOST   http://gpu-box.lan:11434     (default: loopback)
#     VLM_LLM_MODEL  qwen2.5:32b-instruct         (default: the 7B below)
#     VLM_LLM_TOKEN  a bearer token, when the server sits behind auth
#
# The protocol is Ollama's `/api/chat` either way. A remote Ollama speaks the
# same thing as a local one, so "run it on the server" is a hostname and not a
# rewrite -- which is why this stayed Ollama rather than becoming an
# OpenAI-compatible client that would have to grow its own auth, its own error
# shapes and its own streaming.
HOST = os.environ.get("VLM_LLM_HOST", "http://127.0.0.1:11434").rstrip("/")
MODEL = os.environ.get("VLM_LLM_MODEL", "qwen2.5:7b-instruct")
TOKEN = os.environ.get("VLM_LLM_TOKEN", "")

# Loopback must NOT go through a proxy, and a remote host generally must.
#
# This container routes outbound traffic through an agent proxy, so a request
# to 127.0.0.1 built from the environment's proxy settings goes to the proxy
# and fails. It used to be "no proxy, ever", which was right while the only
# host was loopback and becomes wrong the moment `VLM_LLM_HOST` names a server
# on another machine. So there are two openers and `_opener_for` picks by host.
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_PROXIED = urllib.request.build_opener()


def _is_local(host: str) -> bool:
    return any(mark in host for mark in ("127.0.0.1", "localhost", "[::1]"))


def _opener_for(host: str):
    return _DIRECT if _is_local(host) else _PROXIED


class LLMError(RuntimeError):
    """The server is not there, or it answered with something unusable."""


@dataclass(frozen=True)
class Reply:
    """What came back, and enough about how to put it in a provenance stamp."""

    text: str
    model: str
    digest: str          # the weights, not the tag: a tag can be re-pointed
    seed: int
    temperature: float
    prompt_sha: str      # sha256 of system + user, so a stamp names the ask
    tokens: int
    seconds: float

    @property
    def rate(self) -> float:
        return self.tokens / self.seconds if self.seconds else 0.0


def _call(path: str, payload: dict | None, timeout: float,
          host: str = "") -> dict:
    """One request. `payload=None` is a GET -- `/api/tags` only answers to one,
    and sending it a body gets a 405 that reads exactly like a missing model.

    `host` defaults to `HOST` rather than being read from it directly, because
    it used to BE read directly: `Model(host=...)` set an attribute that this
    function never looked at, so pointing a Model at another server silently
    asked the default one. The parameter is how that cannot happen again.
    """
    host = (host or HOST).rstrip("/")
    headers = {} if payload is None else {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(
        host + path if path.startswith("/") else path,
        data=None if payload is None else json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    try:
        with _opener_for(host).open(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # The server IS there and said no, which is a different problem and
        # was reported as the same one until it happened: a cold load of a 7B
        # on a busy CPU can exceed Ollama's own start-up timeout and come back
        # as a 500, and being told to `ollama serve` while ollama was serving
        # is the least useful sentence available.
        detail = ""
        try:
            detail = error.read().decode("utf-8")[:300]
        except Exception:  # noqa: BLE001 -- best effort on an error path
            pass
        raise LLMError(
            f"the local model server answered {error.code} {error.reason}. "
            f"{detail}\n"
            "A 500 on /api/chat is usually the model failing to load in time "
            "-- it is several GB off disk on the first call after an eviction. "
            "Warm it with a one-word request and a long timeout, then retry."
        ) from error
    except urllib.error.URLError as error:
        where = ("the local model at " + host if _is_local(host)
                 else f"the model server at {host} (VLM_LLM_HOST)")
        raise LLMError(
            f"cannot reach {where} ({error}).\n"
            "Start it with:  ollama serve &\n"
            "and pull the weights with:  ollama pull " + MODEL + "\n"
            "See agent/README.md. Nothing here falls back to a hosted "
            "model: a generator that silently changed where the text came from "
            "would put unattributable material in the corpus."
        ) from error


def prompt(name: str) -> str:
    """A committed prompt, by file stem.

    Prompts are files rather than string literals for the same reason the rules
    are YAML: the person who should be editing the Vietnamese in them is not
    necessarily the person who edits Python, and a prompt that changed inside a
    commit touching six other things is a prompt nobody reviewed.
    """
    path = PROMPT_DIR / f"{name}.md"
    if not path.exists():
        have = ", ".join(sorted(p.stem for p in PROMPT_DIR.glob("*.md"))) or "none"
        raise LLMError(f"no prompt {name!r} in {PROMPT_DIR}; have {have}")
    return path.read_text(encoding="utf-8")


class Model:
    """A handle on one set of local weights."""

    def __init__(self, name: str = MODEL, host: str = HOST,
                 temperature: float = 0.9):
        self.name = name
        self.host = host
        self.temperature = temperature
        self._digest = ""

    # -- what is actually running ------------------------------------------

    def digest(self) -> str:
        """The weights' own id, cached.

        A tag is mutable -- `qwen2.5:7b-instruct` can be re-pulled and mean
        different weights next week -- so the stamp records the digest and the
        tag is only how a human recognises it.
        """
        if not self._digest:
            listing = _call("/api/tags", None, timeout=30, host=self.host)
            for item in listing.get("models", []):
                if item.get("name") == self.name:
                    self._digest = str(item.get("digest", ""))[:16]
                    break
            if not self._digest:
                have = ", ".join(m.get("name", "?") for m in listing.get("models", []))
                raise LLMError(
                    f"the local server has no model {self.name!r}; it has: {have or 'none'}.\n"
                    f"Pull it with:  ollama pull {self.name}")
        return self._digest

    def available(self) -> bool:
        try:
            self.digest()
        except LLMError:
            return False
        return True

    # -- asking ------------------------------------------------------------

    def chat(self, system: str, user: str, *, seed: int = 0,
             num_predict: int = 800, timeout: float = 900.0) -> Reply:
        """One turn. Blocking, and slow enough that callers should say so.

        `timeout` is fifteen minutes by default and that is not paranoia: a 7B
        at 4-bit on this container's CPU writes about five tokens a second, so
        a 700-token answer is over two minutes and a batch is an afternoon.
        Every generator here prints progress for that reason.
        """
        digest = self.digest()
        started = time.monotonic()
        reply = _call("/api/chat", {
            "model": self.name,
            "stream": False,
            "options": {"temperature": self.temperature, "seed": seed,
                        "num_predict": num_predict},
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }, timeout=timeout, host=self.host)
        elapsed = time.monotonic() - started
        text = ((reply.get("message") or {}).get("content") or "").strip()
        if not text:
            raise LLMError(f"the model returned nothing: {json.dumps(reply)[:300]}")
        return Reply(
            text=text, model=self.name, digest=digest, seed=seed,
            temperature=self.temperature,
            prompt_sha=hashlib.sha256(
                (system + "\0" + user).encode("utf-8")).hexdigest()[:16],
            tokens=int(reply.get("eval_count") or 0), seconds=elapsed,
        )


def retab(line: str, columns: int) -> str:
    """`Bánh mì 18000 30000` -> `Bánh mì\\t18000\\t30000`, when it is unambiguous.

    A chat model shown a tab-separated example reproduces the columns and loses
    the tab, and it does it for a whole round at a time: measured on
    `items_market`, round one lost **15 of 15 lines** to "1 columns; this
    family has 3" while round two, same prompt and a different seed, got the
    tabs right and lost none.

    This is format, not content -- the same category as stripping a `1.` off
    the front -- and the rule is deliberately narrow enough that it cannot
    invent a column: the line must have NO tab already, and its last
    `columns - 1` whitespace-separated tokens must all be plain integers. A
    name ending in a number (`Sữa 1L`) has one integer at the end, not two, so
    a two-price line is the only thing this can match. Anything else is
    returned untouched and the validator rejects it, which is the right
    outcome: a guess about where a column ends is a guess in the dataset.
    """
    if "\t" in line or columns < 2:
        return line
    parts = line.split()
    if len(parts) < columns:
        return line
    tail = parts[-(columns - 1):]
    if not all(token.isdigit() for token in tail):
        return line
    return "\t".join([" ".join(parts[:-(columns - 1)]), *tail])


def lines_of(text: str) -> list[str]:
    """The model's answer as a list of candidate lines.

    Strips the three things a chat model adds to a list however firmly it is
    told not to: a ``` fence, a `1.` or `-` bullet, and a trailing full stop.
    Nothing here judges the CONTENT -- that is each generator's own validator,
    and it must stay that way, because a cleaner that silently repaired a bad
    line would be a cleaner that let a bad line through.
    """
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("```"):
            continue
        while line[:1] in "-*•":
            line = line[1:].strip()
        head, dot, rest = line.partition(".")
        if dot and head.isdigit() and rest.strip():
            line = rest.strip()
        line = line.rstrip(".")
        if line:
            # Whitespace is squeezed WITHIN a column, never across them. The
            # first version wrote `" ".join(line.split())`, which collapses the
            # tab too -- so every three-column line the model produced came
            # back as one column and was rejected for having one column. The
            # tests in `tests/test_llm.py` caught it before a corpus did.
            out.append("\t".join(" ".join(cell.split())
                                 for cell in line.split("\t")))
    return out


__all__ = ["HOST", "MODEL", "TOKEN", "LLMError", "Model", "Reply", "lines_of",
           "prompt"]
