"""Talking to whatever LLM server the run was pointed at, or to none.

    llm = client.from_env()          # None when no server is configured
    picks = llm.decide(prompt, schema)

Any OpenAI-compatible endpoint: vLLM (`vllm serve ... --port 8000`), SGLang,
llama.cpp's server, Ollama (`/v1`), or a hosted one. Written on `urllib`
because the driver has to run under the repository's bare interpreter, which
has PyYAML and nothing else -- adding a dependency to the one module that is
allowed to be absent would be the wrong trade.

**A missing server is a mode, not a failure.** `from_env()` returns None when
`VLM_LLM_URL` is unset, and the planner then runs its offline policy, which is
the same decision procedure with the model's judgement replaced by a coverage
objective. A run that silently degraded would be the bad outcome; a run that
records which mode it used, per image, is not -- see `planner.Decision.by`.

The schema is sent as `response_format: {type: json_schema}`, which vLLM
enforces by constrained decoding (`--structured-outputs-config.backend
xgrammar`). Enforcement matters more than prompting here: the ids the model
returns have to be ids the rules actually define, and an enum in the schema is
the only mechanism that makes that true by construction rather than by hope.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

URL_ENV = "VLM_LLM_URL"
MODEL_ENV = "VLM_LLM_MODEL"
KEY_ENV = "VLM_LLM_KEY"


class LLMError(RuntimeError):
    """The server answered, and the answer was not usable."""


@dataclass
class Client:
    """One endpoint, one model, and a bounded retry."""

    url: str
    model: str
    key: str = "EMPTY"
    timeout: float = 120.0
    retries: int = 2
    temperature: float = 0.85
    # Qwen3.x and gpt-oss think by default. For picking ids off a list that is
    # spend with no return, so it is asked for explicitly and low; a server
    # that does not know the field ignores it.
    reasoning_effort: str = "low"

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.url.rstrip("/") + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.key}"})
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, OSError, ValueError) as error:
                last = error
                if attempt < self.retries:
                    time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"{self.url}: {last}")

    def decide(self, system: str, user: str, schema: dict) -> dict:
        """One JSON object matching `schema`. Raises rather than guessing."""
        answer = self._post({
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "plan", "schema": schema,
                                                "strict": True}},
            "temperature": self.temperature,
            "reasoning_effort": self.reasoning_effort,
        })
        try:
            content = answer["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMError(f"no content in the reply: {answer}") from error
        try:
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise LLMError(f"reply was not JSON: {content[:300]!r}") from error

    def alive(self) -> bool:
        try:
            request = urllib.request.Request(
                self.url.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {self.key}"})
            with urllib.request.urlopen(request, timeout=10) as response:
                return 200 <= response.status < 300
        except Exception:       # noqa: BLE001 -- any failure means "not there"
            return False


def from_env() -> Client | None:
    """The configured client, or None when this run has no server."""
    url = os.environ.get(URL_ENV, "").strip()
    if not url:
        return None
    return Client(url=url, model=os.environ.get(MODEL_ENV, "planner").strip() or "planner",
                  key=os.environ.get(KEY_ENV, "EMPTY"))


__all__ = ["KEY_ENV", "MODEL_ENV", "URL_ENV", "Client", "LLMError", "from_env"]
