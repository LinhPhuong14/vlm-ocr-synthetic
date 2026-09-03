"""The agent: its policy, its dressings, its plan, and the line it may not cross.

The claim this file defends is narrow and load-bearing: **an agent that decides
5000 pages cannot decide an illegal one, and cannot redraw a giấy tờ nhà nước.**
Both are enforced by the rules rather than by the planner, so both are tested
against the rules -- a planner bug should be unable to produce a bad page even
if nothing here noticed the bug.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from agent import client, planner, policy, variants  # noqa: E402
from agent import rules as agent_rules  # noqa: E402

CATALOGUE = variants.build(count=24, seed=11)


@pytest.fixture(scope="module")
def built():
    pol = policy.load()
    return agent_rules.compose(CATALOGUE, pol), pol


# ------------------------------------------------------------------- policy


def test_every_shipped_document_is_classified(built):
    rules, _ = built
    assert policy.problems(rules) == []


def test_a_document_cannot_be_in_two_classes(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(json.dumps({
        "classes": {"locked": {"documents": ["a"]}, "livery": {"documents": ["a"]},
                    "free": {"documents": []}},
        "tags": {"locked": "x", "livery": "y", "free": "z"},
    }), encoding="utf-8")
    with pytest.raises(policy.PolicyError, match="both"):
        policy.load(path)


def test_an_unclassified_document_is_refused_rather_than_defaulted():
    pol = policy.load()
    with pytest.raises(policy.PolicyError, match="no class"):
        pol.klass("bang_lai_xe")


# ------------------------------------------------------------ what may vary


def test_a_locked_document_can_draw_no_dressing_at_all(built):
    """The whole point: a prescribed form is never redrawn, only stamped."""
    rules, pol = built
    reach = agent_rules.reachable(rules, pol)
    for document in pol.documents("locked"):
        assert reach[document] == [agent_rules.NONE_ID], document


def test_a_livery_document_may_change_ink_but_not_geometry(built):
    rules, pol = built
    reach = agent_rules.reachable(rules, pol)
    for document in pol.documents("livery"):
        drawable = set(reach[document])
        assert agent_rules.NONE_ID in drawable
        assert drawable - {agent_rules.NONE_ID}, f"{document} can vary in nothing"
        levels = {option.params["level"] for option in rules["variant"]
                  if option.id in drawable}
        assert levels <= {"locked", "livery"}, document


def test_a_free_document_may_draw_every_dressing(built):
    rules, pol = built
    reach = agent_rules.reachable(rules, pol)
    every = {option.id for option in rules["variant"]}
    for document in pol.documents("free"):
        assert set(reach[document]) == every, document


def test_variant_is_drawn_straight_after_the_layout_it_dresses(built):
    rules, _ = built
    order = list(rules)
    assert order[order.index(agent_rules.AFTER) + 1] == agent_rules.ATTRIBUTE


# ---------------------------------------------------------------- dressings


def test_no_dressing_changes_pixels_without_changing_the_dom():
    """`text-transform` and a `content` carrying words are the two that would."""
    import sheets

    for dressing in variants.build(count=60, seed=3):
        assert sheets.variant.forbidden(dressing.css) == [], dressing.id


def test_the_catalogue_is_the_same_catalogue_for_the_same_seed():
    left = [v.id for v in variants.build(count=20, seed=7)]
    right = [v.id for v in variants.build(count=20, seed=7)]
    assert left == right
    assert len(set(left)) == len(left), "a catalogue must not repeat a dressing"


def test_asking_for_more_dressings_than_exist_fails_loudly():
    with pytest.raises(ValueError, match="distinct"):
        variants.build(count=10_000, seed=1)


def test_a_dressing_lands_inside_the_style_block_it_is_appended_to():
    import sheets

    option = type("O", (), {"id": "x", "params": {"css": "#sheet{color:#123456;}"}})()
    recipe = type("R", (), {"choices": {"variant": option}})()
    out = sheets.variant.apply("<style>a{}</style><body>", recipe)
    assert out.index("#sheet{color:#123456;}") < out.index("</style>")


def test_a_recipe_with_no_variant_leaves_the_page_untouched():
    """The shipped rules define no `variant`, so every committed set is safe."""
    import sheets

    recipe = type("R", (), {"choices": {}})()
    assert sheets.variant.apply("<style>a{}</style>", recipe) == "<style>a{}</style>"


def test_a_dressing_that_would_rewrite_the_pixels_is_refused():
    import sheets

    option = type("O", (), {"id": "bad",
                            "params": {"css": "#sheet{text-transform:uppercase;}"}})()
    recipe = type("R", (), {"choices": {"variant": option}})()
    with pytest.raises(ValueError, match="text-transform"):
        sheets.variant.apply("<style></style>", recipe)


# ------------------------------------------------------------------- the plan


def test_every_decision_is_a_page_the_sampler_actually_draws(built):
    rules, pol = built
    decisions = planner.plan(300, seed=99, rules=rules, policy=pol)
    assert planner.verify(decisions, rules) == []


def test_the_plan_never_redresses_a_locked_document(built):
    rules, pol = built
    for decision in planner.plan(400, seed=5, rules=rules, policy=pol):
        if pol.klass(decision.force["document"]) == "locked":
            assert decision.force["variant"] == agent_rules.NONE_ID


def test_coverage_beats_independent_draws_on_the_tail(built):
    """The reason the agent exists: 400 independent draws leave values unseen."""
    rules, pol = built
    balanced = planner.plan(400, seed=4, rules=rules, policy=pol, pressure=0.72)
    independent = planner.plan(400, seed=4, rules=rules, policy=pol, pressure=0.0)
    # `unused` counts only drawable values, so a switched-off one is not a miss.
    assert planner.unused(balanced, rules) == {}
    assert planner.unused(independent, rules) != {}


def test_a_locked_page_gets_its_variety_from_ink_instead(built):
    rules, pol = built
    decisions = planner.plan(600, seed=8, rules=rules, policy=pol)
    locked = [d for d in decisions if pol.klass(d.force["document"]) != "free"]
    bare = [d for d in locked if d.force["ornament"] == planner.BARE_ID]
    assert locked, "no locked or livery page was planned"
    assert len(bare) / len(locked) < 0.10


# ------------------------------------------------------------------ the model


class _Stub(BaseHTTPRequestHandler):
    """An OpenAI-compatible server that answers with whatever `pages` is set to."""

    pages: list = []

    def log_message(self, *_args):        # noqa: D102 -- silence the test run
        pass

    def do_GET(self):                     # noqa: N802 -- the stdlib spells it so
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"data":[]}')

    def do_POST(self):                    # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        block = (body["response_format"]["json_schema"]["schema"]
                 ["properties"]["pages"]["minItems"])
        payload = {"choices": [{"message": {"content": json.dumps(
            {"pages": [dict(self.pages[0]) for _ in range(block)]})}}]}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())


@pytest.fixture
def stub():
    server = HTTPServer(("127.0.0.1", 0), _Stub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()


def _client(server) -> client.Client:
    host, port = server.server_address
    return client.Client(url=f"http://{host}:{port}/v1", model="stub", timeout=10)


def test_the_model_decides_the_page_when_its_ids_are_legal(built, stub):
    rules, pol = built
    _Stub.pages = [{"document": "supermarket", "layout": "market_barcode",
                    "variant": "none", "content": "market_upper",
                    "visual": "till_thermal", "color": "mono_black",
                    "ornament": "no_ornament", "augmentation": "pristine"}]
    legal = {name: {o.id for o in options} for name, options in rules.items()}
    _Stub.pages[0] = {k: v for k, v in _Stub.pages[0].items() if v in legal.get(k, ())}
    if len(_Stub.pages[0]) < 3:
        pytest.skip("the shipped rules renamed the ids this stub names")
    decisions = planner.plan(6, seed=1, rules=rules, policy=pol, llm=_client(stub),
                             block=3)
    assert all(d.by == "llm" for d in decisions)
    assert planner.verify(decisions, rules) == []


def test_an_illegal_pick_is_replaced_and_said_so(built, stub):
    rules, pol = built
    _Stub.pages = [{"document": "vat_invoice_form", "layout": "market_barcode",
                    "variant": "none", "content": "market_upper",
                    "visual": "till_thermal", "color": "mono_black",
                    "ornament": "no_ornament", "augmentation": "pristine"}]
    decisions = planner.plan(4, seed=1, rules=rules, policy=pol, llm=_client(stub),
                             block=2)
    # A supermarket till layout is not a thing a statutory form can wear, so the
    # rules refuse it and the objective fills the slot instead.
    assert any("rules refused" in d.note for d in decisions)
    assert planner.verify(decisions, rules) == []


def test_a_server_that_is_not_there_is_a_mode_and_not_a_crash(built):
    rules, pol = built
    dead = client.Client(url="http://127.0.0.1:9/v1", model="none", timeout=1, retries=0)
    assert dead.alive() is False
    decisions = planner.plan(5, seed=2, rules=rules, policy=pol, llm=dead, block=2)
    assert all(d.by == "coverage" for d in decisions)


# ------------------------------------- dressing the layout, not just painting it


def test_a_move_reorders_the_blocks_of_the_phoi():
    """`sections:` is the list every family loops over, so reordering it is the
    one thing a variant can do that is a change of layout rather than of paint.
    """
    import sheets

    option = type("O", (), {"id": "x", "params": {
        "css": "", "moves": [["swap", "letterhead", "doctitle"],
                             ["after", "words", "signatures"]]}})()
    recipe = type("R", (), {"choices": {"variant": option}})()
    spec = {"sections": ["letterhead", "doctitle", "parties", "table", "totals",
                         "words", "signatures", "footer"]}
    out = sheets.variant.restructure(spec, recipe)
    assert out["sections"] == ["doctitle", "letterhead", "parties", "table",
                               "totals", "signatures", "words", "footer"]
    assert spec["sections"][0] == "letterhead", "the caller's spec was mutated"


def test_a_move_naming_a_block_this_phoi_lacks_is_a_no_op():
    """One dressing has to be wearable by a hotel folio and a hospital bill."""
    import sheets

    option = type("O", (), {"id": "x", "params": {
        "css": "", "moves": [["after", "words", "signatures"]]}})()
    recipe = type("R", (), {"choices": {"variant": option}})()
    spec = {"sections": ["doctitle", "table", "footer"]}
    assert sheets.variant.restructure(spec, recipe)["sections"] == spec["sections"]


def test_a_dressing_with_no_moves_leaves_the_phoi_alone():
    import sheets

    recipe = type("R", (), {"choices": {}})()
    spec = {"sections": ["doctitle", "table"]}
    assert sheets.variant.restructure(spec, recipe) is spec


def test_some_dressings_actually_restructure(built):
    rules, _ = built
    moved = [o for o in rules[agent_rules.ATTRIBUTE] if o.params.get("moves")]
    assert moved, "no dressing reorders anything, so `structure` is decorative"


# ------------------------------------- a value the rules switched off, either way


def test_the_chooser_reads_both_ways_a_value_is_switched_off(built):
    """`weight: 0` is the accidental switch-off and `enabled: false` the
    deliberate one. `_draw_once` reads both, so the chooser must too -- checking
    only `weight` would still have drawn `torn_edges` and `punched`, and punched
    holes through pages the label says are whole."""
    rules, pol = built
    off = {option.id for option in rules["augmentation"]
           if not option.enabled or option.weight <= 0}
    assert off, "the shipped rules switch nothing off, so this proves nothing"
    for decision in planner.plan(400, seed=6, rules=rules, policy=pol):
        assert decision.force["augmentation"] not in off


def test_a_till_roll_never_wears_a_dressing_that_sets_page_margins(built):
    """A roll is about 80 mm across and sets its own width in `till.py`.

    16 mm of margin each side leaves the item table too little to lay out in and
    the columns spill past the paper -- measured as a box seven pixels outside a
    606 px frame on `market_barcode`, which is a label describing ink that is not
    on the page. There is no millimetre value that is both a wide margin on A4
    and survivable on a roll, so the rules refuse the pairing instead.
    """
    rules, _ = built
    on_a_roll = frozenset({"aug_free", agent_rules.TILL_TAG})
    for option in rules[agent_rules.ATTRIBUTE]:
        if option.params.get("axes", {}).get("structure") in variants.WIDE_ONLY_STRUCTURE:
            assert not option.allowed(on_a_roll), option.id


def test_a_roll_wears_ink_and_not_geometry(built):
    """Every structure value sets the page's own margins in millimetres, so a
    thermal roll draws none of them -- it is 80 mm across and has no design
    margins to vary. What is left is the paint-only half of the catalogue, and
    the point of this test is that the half is still there rather than empty."""
    rules, _ = built
    on_a_roll = frozenset({"aug_free", agent_rules.TILL_TAG})
    drawable = [o for o in rules[agent_rules.ATTRIBUTE] if o.allowed(on_a_roll)]
    assert len(drawable) >= 8, f"a roll can only wear {len(drawable)} dressings"
    levels = {o.params.get("level") for o in drawable} - {"locked"}
    assert levels <= {"livery"}, f"a roll drew a geometry dressing: {levels}"


# ------------------------------------------------ a value the rules switched off


def test_weight_zero_means_never_not_rarely(built):
    """`_weighted_choice` has always read `weight: 0` as off.

    The coverage score divides by usage and floors at a tiny positive number, so
    a switched-off value would otherwise be picked the moment everything else
    had been used once -- which is the opposite of off, and would have drawn the
    WriteViT ink sources on a machine that has no WriteViT.
    """
    rules, pol = built
    # `seller_seal`, not `no_ornament`: the bare value is the only one some tag
    # sets can reach, and switching it off means the rules cannot draw a page at
    # all -- which `legal` reports rather than papering over, and which is a
    # different thing from the property under test here.
    rules = agent_rules.switch_off(rules, "ornament", ["seller_seal"])
    chooser = planner.Chooser(rules, tuple(rules), seed=3)
    assert all(option.id != "seller_seal"
               for option in chooser.legal("ornament", frozenset({"doc_invoice"})))
    for decision in planner.plan(400, seed=3, rules=rules, policy=pol):
        assert decision.force["ornament"] != "seller_seal"


def test_switching_off_keeps_the_value_it_switched(built):
    """Not a deletion: a record naming it must still be readable."""
    rules, _ = built
    off = agent_rules.switch_off(rules, "ornament", ["seller_seal"])
    assert {o.id for o in off["ornament"]} == {o.id for o in rules["ornament"]}
    seal = next(o for o in off["ornament"] if o.id == "seller_seal")
    assert seal.weight == 0
    assert seal.params == next(o for o in rules["ornament"]
                               if o.id == "seller_seal").params


def test_the_ink_sources_that_need_writevit_are_named(built):
    """Named, so a run without the clone switches them off deliberately."""
    rules, _ = built
    have = {option.id for option in rules["handwriting"]}
    assert set(agent_rules.NEEDS_WRITEVIT) <= have, have
