"""`agent/compose.py`: content the model writes, validated the corpus's own way.

The claim this file defends: a value that reaches `content_overrides.json`
has already passed `corpus_rules.check_name` AND carries a Vietnamese
diacritic, and a value that fails either is dropped from its page rather than
failing the page -- mirroring `tests/test_agent.py`'s claim about `plan()`.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from agent import client, compose, planner, policy, variants  # noqa: E402
from agent import rules as agent_rules  # noqa: E402

CATALOGUE = variants.build(count=24, seed=11)


@pytest.fixture(scope="module")
def built():
    pol = policy.load()
    return agent_rules.compose(CATALOGUE, pol), pol


class _Stub(BaseHTTPRequestHandler):
    """Answers every field in the schema with a fixed, in-bounds value."""

    delay: float = 0.0

    def log_message(self, *_args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"data":[]}')

    def do_POST(self):
        if self.delay:
            time.sleep(self.delay)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        schema = (body["response_format"]["json_schema"]["schema"]
                 ["properties"]["pages"]["items"])
        block = (body["response_format"]["json_schema"]["schema"]
                ["properties"]["pages"]["minItems"])
        page = {}
        for name, spec in schema["properties"].items():
            if spec.get("type") == "array":
                low = spec["items"].get("minLength", 2)
                page[name] = [("Bánh Mì Đặc Biệt" + "a" * low)[:low + 4]] * spec["minItems"]
            elif "enum" in spec:
                page[name] = spec["enum"][0]
            else:
                low = spec.get("minLength", 2)
                page[name] = ("Cửa Hàng Kiểm Thử Toàn Diện" + "a" * low)[:low + 4]
        payload = {"choices": [{"message": {"content": json.dumps(
            {"pages": [page] * block})}}]}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())


@pytest.fixture
def stub():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def _client(server) -> client.Client:
    host, port = server.server_address
    return client.Client(url=f"http://{host}:{port}/v1", model="stub", timeout=10)


def test_a_diacritic_free_value_is_dropped_not_failed():
    shape, envelope = compose._store_name_bounds("market")
    assert compose._validate_free_text("CUA HANG KIEM THU", shape, envelope) \
        == "no Vietnamese diacritic"
    assert compose._validate_free_text("Cửa Hàng Kiểm Thử", shape, envelope) == ""


def test_an_out_of_bounds_value_is_rejected_with_the_corpus_rules_reason():
    shape, envelope = compose._store_name_bounds("eatery")
    too_long = "Đ" * (envelope.longest()[1] + 20)
    assert "characters" in compose._validate_free_text(too_long, shape, envelope)


def test_medical_schema_offers_only_the_documents_own_diagnoses():
    import yaml
    document = yaml.safe_load((REPO_ROOT / "rulebase" / "documents"
                               / "hospital_bill.yaml").read_text(encoding="utf-8"))
    schema = compose.schema_for("medical", document, block=4)
    diag_enum = schema["properties"]["pages"]["items"]["properties"]["admission.diagnosis"]["enum"]
    assert set(diag_enum) == {code for code, _name in document["diagnoses"]}


def test_a_profile_with_no_eligible_field_gets_no_schema():
    assert compose.schema_for("export", {}, block=4) is None


def test_composing_matches_sequential_byte_for_byte(built, stub):
    rules, pol = built
    decisions = planner.plan(40, seed=3, rules=rules, policy=pol)
    sequential = compose.decide(decisions, rules, llm=_client(stub), concurrency=1)
    concurrent = compose.decide(decisions, rules, llm=_client(stub), concurrency=4)
    assert [p.content for p in sequential] == [p.content for p in concurrent]
    assert [p.rejected for p in sequential] == [p.rejected for p in concurrent]


def test_composing_is_actually_concurrent(built, stub):
    rules, pol = built
    decisions = planner.plan(40, seed=3, rules=rules, policy=pol)
    _Stub.delay = 0.3
    try:
        start = time.time()
        compose.decide(decisions, rules, llm=_client(stub), concurrency=1)
        sequential_seconds = time.time() - start

        start = time.time()
        compose.decide(decisions, rules, llm=_client(stub), concurrency=4)
        concurrent_seconds = time.time() - start
    finally:
        _Stub.delay = 0.0
    assert concurrent_seconds < sequential_seconds / 1.5


def test_a_dead_server_leaves_every_page_with_no_override(built):
    rules, pol = built
    decisions = planner.plan(10, seed=3, rules=rules, policy=pol)
    pages = compose.decide(decisions, rules, llm=None)
    assert all(p.content == {} and p.by == "coverage" for p in pages)


def test_write_produces_a_lean_lookup_keyed_by_seed(tmp_path):
    pages = [compose.ComposedPage(seed=7, document="supermarket", profile="market",
                                  content={"store.name": "Cửa Hàng An Vui"}, by="llm"),
             compose.ComposedPage(seed=8, document="supermarket", profile="market")]
    ledger = tmp_path / "compose.jsonl"
    overrides = tmp_path / "content_overrides.json"
    compose.write(pages, ledger, overrides)
    lookup = json.loads(overrides.read_text(encoding="utf-8"))
    assert lookup == {"7": {"store.name": "Cửa Hàng An Vui"}}
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["seed"] == 7
