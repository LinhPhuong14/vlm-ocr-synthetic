"""Build the contents of one newspaper/magazine page from a recipe.

A sibling to `rulebase.content`, not an extension of it. `Receipt`/`Invoice`
model a transaction: a store, a basket, a total, sometimes two parties and a
signature. A newspaper front page, a classifieds page, a table of contents,
a Q&A interview have none of that -- a headline, a byline, paragraphs of
running prose, a list of question/answer pairs. Reusing `Receipt` here would
mean a class whose `ground_truth()` branches ten different ways depending on
which unrelated fields happen to be set; four small, honest dataclasses (one
per page composition) are the more direct restatement of what each page
actually is.

Nothing outside `rulebase/content.py` + `rulebase/layout.py` +
`generators/html/sheets/*.py` inspects a content object's concrete type --
every consumer (`sheets.build()`, `pipeline/record.py`, `pipeline/
invariants.py`, every renderer entrypoint) only ever calls `.ground_truth()`
(a dict) and `.text_sequence()` (a string). So these four classes need no
shared base class with `Receipt`, and `rulebase.make_content()`'s dispatch
(see `rulebase/__init__.py`) only needs to tell "a Receipt" from "not," never
which of the four this is.

The one place a periodical page still has to speak `Receipt`'s language is
`build_grid()` (`rulebase/layout.py`): `tests/test_layout.py`'s geometry
suite and `pipeline/preflight.py::sheet_overflow()` build every layout in
`rulebase.available_layouts()` unconditionally, with no exemption. Neither
ever reads `.ground_truth()` off what they build, and the CSS-sheet path
(`--template auto`, the default everywhere now) never touches the grid at
all -- `rulebase.make_content()` is what it calls, and that never builds a
grid. So each class's `as_grid_receipt()` owes nothing but "doesn't crash
`header`/`parties`/`notes`/`footer`, doesn't overflow a declared A4 sheet."
It is never shown to a reader and never checked against a label.

Corpus, not procedural text. This repo's whole content model is deterministic
weighted sampling from fixed, hand-authored strings (`rulebase/documents/
authorisation_letter.yaml`'s `notes:` is one fixed bank of legal clauses,
drawn whole every time that document is chosen) -- never sentence generation
at runtime. `rulebase.corpus.periodical()` follows the same rule: a bank of
whole articles/transcripts/page-sets, one drawn per page, with only the
fields around them (a reporter's name, a date, a page number) actually
randomised. See `rulebase/corpus/vi/periodical_*.yaml`.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from datetime import date as _date
from typing import Any

from . import corpus
from .content import Invoice, Receipt, Store

_WEEKDAYS_VI = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật")
_BYLINE_LEADS = ("Bài", "Bài và ảnh", "Thực hiện")
_LANG = "vi"


# ---------------------------------------------------------------- helpers


def _compact(value: Any) -> Any:
    """Strip empty strings/lists/dicts recursively, keep the shape otherwise.

    Every class's `ground_truth()` below is `_compact(asdict(self))`. Unlike
    `Receipt.ground_truth()` (hand-built field by field, because `Receipt`'s
    dataclass fields are not all label-shaped -- `money_style`, `upper`
    control rendering, not content), a periodical page's fields already ARE
    the label one to one, so mirroring `asdict()` is a more direct
    restatement of "the label is built from the same objects the render
    draws from" than reproducing the same mapping by hand four times over.
    """
    if isinstance(value, dict):
        cleaned = {key: _compact(item) for key, item in value.items()}
        return {key: item for key, item in cleaned.items() if item not in ({}, [], "", None)}
    if isinstance(value, (list, tuple)):
        return [_compact(item) for item in value if item not in ({}, [], "", None)]
    return value


def _flat_strings(value: Any) -> list[str]:
    """Every leaf string in a nested structure, in `asdict()`'s own order."""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        return [text for item in value.values() for text in _flat_strings(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in _flat_strings(item)]
    return []


def _dateline(rng: random.Random) -> tuple[str, str]:
    """(weekday name, "DD · M · YYYY") for a recent, plausible issue date."""
    day = _date(rng.randrange(2024, 2027), rng.randrange(1, 13), rng.randrange(1, 29))
    return _WEEKDAYS_VI[day.weekday()], f"{day.day} · {day.month} · {day.year}"


def _byline(rng: random.Random) -> str:
    """A reporter byline with a fresh name every draw.

    The name comes from `corpus.people()` rather than being baked into each
    corpus story: the same article should not always carry the same
    reporter, any more than the same invoice always names the same buyer.
    """
    return f"{rng.choice(_BYLINE_LEADS)}: {rng.choice(corpus.people(_LANG))}"


def _thousands(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# ---------------------------------------------------------- lead + sidebar


@dataclass
class TeaserItem:
    kicker: str = ""
    headline: str = ""
    blurb: str = ""
    page_ref: str = ""


@dataclass
class SidebarItem:
    label: str = ""
    text: str = ""


@dataclass
class BottomStory:
    caption: str = ""
    headline: str = ""
    body: list[str] = field(default_factory=list)
    jump_line: str = ""


@dataclass
class ArticlePage:
    """A front page: a lead story, a rail of shorter items, teasers, a
    bottom strip -- or a leaner subset of the same slots (see
    `newspaper_front_tabloid.html`'s follow-up, which reuses this class with
    `teasers=[]`/`bottom_stories=[]` and nothing else new)."""

    doc_type: str = field(default="periodical_lead_sidebar", init=False)
    masthead: str = ""
    slogan: str = ""
    dateline_day: str = ""
    issue_date: str = ""
    issue_no: str = ""
    price: str = ""
    website: str = ""
    hotline: str = ""
    page_no: str = ""
    footer_line: str = ""
    kicker: str = ""
    headline: str = ""
    deck: str = ""
    byline: str = ""
    lead_caption: str = ""
    body: list[str] = field(default_factory=list)
    jump_line: str = ""
    sidebar_title: str = ""
    sidebar_items: list[SidebarItem] = field(default_factory=list)
    sidebar_caption: str = ""
    sidebar_headline: str = ""
    sidebar_body: list[str] = field(default_factory=list)
    sidebar_jump: str = ""
    teasers: list[TeaserItem] = field(default_factory=list)
    bottom_stories: list[BottomStory] = field(default_factory=list)

    def ground_truth(self) -> dict[str, Any]:
        return _compact(asdict(self)) | {"doc_type": self.doc_type}

    def text_sequence(self) -> str:
        return " ".join(_flat_strings(asdict(self)))

    def as_grid_receipt(self) -> Receipt:
        """See the module docstring: never real pixels, never checked
        against a label -- just enough for `build_grid` not to crash and for
        `preflight`'s height estimate to stay under an A4 sheet."""
        notes = [self.kicker, self.deck]
        if self.body:
            notes += ["", self.body[0][:200]]
        return Receipt(
            profile="periodical", title=self.headline, store=Store(name=self.masthead),
            meta=[], items=[], totals=[], footer=[self.footer_line] if self.footer_line else [],
            money_style="dot", upper=False, folded=False,
            invoice=Invoice(left=[("Tác giả", self.byline)] if self.byline else [], notes=notes),
        )


def _build_lead_sidebar(rng: random.Random, document: dict) -> ArticlePage:
    pool = list(corpus.periodical("article", _LANG))
    rng.shuffle(pool)
    draws = iter(pool)

    def draw() -> dict:
        return dict(next(draws))

    lead = draw()
    weekday, issue_date = _dateline(rng)
    page = ArticlePage(
        masthead=document.get("masthead", ""), slogan=document.get("slogan", ""),
        dateline_day=weekday, issue_date=issue_date,
        issue_no=f"Số {_thousands(rng.randrange(1000, 9999))} · Năm thứ {rng.randrange(5, 40)}",
        price=document.get("price", ""), website=document.get("website", ""),
        hotline=document.get("hotline", ""), page_no="1",
        footer_line=document.get("footer_line", ""),
        kicker=lead["kicker"], headline=lead["headline"], deck=lead["deck"],
        byline=_byline(rng), lead_caption=lead["lead_caption"],
        body=list(lead["body"]), jump_line=lead.get("jump_line", ""),
    )

    for _ in range(int(document.get("teaser_count", 0))):
        item = draw()
        page.teasers.append(TeaserItem(
            kicker=item["kicker"], headline=item["headline"], blurb=item["deck"],
            page_ref=f"Trang {rng.randrange(2, 20)}",
        ))

    box = rng.choice(corpus.periodical("sidebar_box", _LANG))
    page.sidebar_title = box["title"]
    page.sidebar_items = [SidebarItem(**row) for row in box["items"]]

    if document.get("secondary_rail", True):
        secondary = draw()
        page.sidebar_caption = secondary["lead_caption"]
        page.sidebar_headline = secondary["headline"]
        page.sidebar_body = list(secondary["body"])[:3]
        page.sidebar_jump = secondary.get("jump_line", "")

    for _ in range(int(document.get("bottom_count", 0))):
        item = draw()
        page.bottom_stories.append(BottomStory(
            caption=item["lead_caption"], headline=item["headline"],
            body=list(item["body"]), jump_line=item.get("jump_line", ""),
        ))
    return page


# --------------------------------------------------------------- classifieds


@dataclass
class ClassifiedAd:
    lead_in: str = ""
    body: str = ""
    phone: str = ""
    heading: str = ""


@dataclass
class ClassifiedCategory:
    name: str = ""
    ads: list[ClassifiedAd] = field(default_factory=list)


@dataclass
class Notice:
    title: str = ""
    body: list[str] = field(default_factory=list)
    signed: str = ""


@dataclass
class Obituary:
    title: str = ""
    name: str = ""
    body: list[str] = field(default_factory=list)


@dataclass
class ClassifiedsPage:
    """A page of categorised ads, legal notices and obituaries. Kept as one
    whole story-set per draw (see `rulebase.corpus.periodical`'s module
    docstring): the ads on a real classifieds page are placed by different
    people in the same issue, not slots one composer fills independently."""

    doc_type: str = field(default="periodical_classifieds", init=False)
    section: str = ""
    masthead: str = ""
    issue_date: str = ""
    page_no: str = ""
    rate_line_1: str = ""
    rate_line_2: str = ""
    footer_disclaimer: str = ""
    categories: list[ClassifiedCategory] = field(default_factory=list)
    notices: list[Notice] = field(default_factory=list)
    obituaries: list[Obituary] = field(default_factory=list)
    condolence: str = ""

    def ground_truth(self) -> dict[str, Any]:
        return _compact(asdict(self)) | {"doc_type": self.doc_type}

    def text_sequence(self) -> str:
        return " ".join(_flat_strings(asdict(self)))

    def as_grid_receipt(self) -> Receipt:
        notes = [self.rate_line_1, self.rate_line_2]
        if self.categories:
            first = self.categories[0]
            notes += ["", first.name]
            if first.ads:
                notes.append(first.ads[0].body[:200])
        return Receipt(
            profile="periodical", title=self.section, store=Store(name=self.masthead),
            meta=[], items=[], totals=[],
            footer=[self.footer_disclaimer] if self.footer_disclaimer else [],
            money_style="dot", upper=False, folded=False, invoice=Invoice(notes=notes),
        )


def _build_classifieds(rng: random.Random, document: dict) -> ClassifiedsPage:
    source = rng.choice(corpus.periodical("classifieds", _LANG))
    _weekday, issue_date = _dateline(rng)
    page = ClassifiedsPage(
        section=document.get("section", ""), masthead=document.get("masthead", ""),
        issue_date=issue_date, page_no=str(rng.randrange(10, 32)),
        rate_line_1=source.get("rate_line_1", ""), rate_line_2=source.get("rate_line_2", ""),
        footer_disclaimer=document.get("footer_disclaimer", ""),
        condolence=source.get("condolence", ""),
    )
    for category in source.get("categories", []):
        page.categories.append(ClassifiedCategory(
            name=category["name"], ads=[ClassifiedAd(**ad) for ad in category.get("ads", [])],
        ))
    for notice in source.get("notices", []):
        page.notices.append(Notice(**notice))
    for obituary in source.get("obituaries", []):
        page.obituaries.append(Obituary(**obituary))
    return page


# --------------------------------------------------------------------- toc


@dataclass
class TocEntry:
    page_no: str = ""
    title: str = ""
    teaser: str = ""


@dataclass
class TocSection:
    name: str = ""
    entries: list[TocEntry] = field(default_factory=list)


@dataclass
class TocPage:
    """A table of contents: one hero feature plus a grid of section-grouped
    entries. Kept as one whole page-set per draw, same reasoning as
    `ClassifiedsPage` -- a real issue's contents page is one coherent list,
    not independent slots."""

    doc_type: str = field(default="periodical_toc", init=False)
    masthead: str = ""
    issue_label: str = ""
    footer_left: str = ""
    footer_right: str = ""
    hero_kicker: str = ""
    hero_page_no: str = ""
    hero_headline: str = ""
    hero_teaser: str = ""
    hero_byline: str = ""
    sections: list[TocSection] = field(default_factory=list)

    def ground_truth(self) -> dict[str, Any]:
        return _compact(asdict(self)) | {"doc_type": self.doc_type}

    def text_sequence(self) -> str:
        return " ".join(_flat_strings(asdict(self)))

    def as_grid_receipt(self) -> Receipt:
        notes = [self.hero_kicker, self.hero_headline, "", self.hero_teaser[:200]]
        return Receipt(
            profile="periodical", title="Mục lục", store=Store(name=self.masthead),
            meta=[], items=[], totals=[], footer=[self.footer_left] if self.footer_left else [],
            money_style="dot", upper=False, folded=False,
            invoice=Invoice(left=[("Bài đinh", self.hero_byline)] if self.hero_byline else [],
                            notes=notes),
        )


def _build_toc(rng: random.Random, document: dict) -> TocPage:
    source = rng.choice(corpus.periodical("toc", _LANG))
    hero = source.get("hero", {})
    page = TocPage(
        masthead=document.get("masthead", ""), issue_label=document.get("issue_label", ""),
        footer_left=document.get("footer_left", ""), footer_right=document.get("footer_right", ""),
        hero_kicker=hero.get("kicker", ""), hero_page_no=hero.get("page_no", ""),
        hero_headline=hero.get("headline", ""), hero_teaser=hero.get("teaser", ""),
        hero_byline=hero.get("byline", ""),
    )
    for section in source.get("sections", []):
        page.sections.append(TocSection(
            name=section["name"],
            entries=[TocEntry(**entry) for entry in section.get("entries", [])],
        ))
    return page


# ---------------------------------------------------------------------- qa


@dataclass
class QaPair:
    question: str = ""
    answer: str = ""


@dataclass
class BioRow:
    year: str = ""
    text: str = ""


@dataclass
class QaPage:
    """A Q&A interview: alternating question/answer pairs, one pull-quote,
    a short biography table. One whole transcript per draw."""

    doc_type: str = field(default="periodical_qa", init=False)
    section: str = ""
    headline: str = ""
    subject_name: str = ""
    subject_role: str = ""
    deck: str = ""
    byline_by: str = ""
    byline_photo: str = ""
    footer_note: str = ""
    footer_right: str = ""
    qa_pairs: list[QaPair] = field(default_factory=list)
    pull_quote: str = ""
    bio_title: str = ""
    bio_rows: list[BioRow] = field(default_factory=list)

    def ground_truth(self) -> dict[str, Any]:
        return _compact(asdict(self)) | {"doc_type": self.doc_type}

    def text_sequence(self) -> str:
        return " ".join(_flat_strings(asdict(self)))

    def as_grid_receipt(self) -> Receipt:
        notes = [self.deck]
        if self.qa_pairs:
            first = self.qa_pairs[0]
            notes += ["", first.question, first.answer[:200]]
        return Receipt(
            profile="periodical", title=self.headline, store=Store(name=self.subject_name),
            meta=[], items=[], totals=[], footer=[self.footer_note] if self.footer_note else [],
            money_style="dot", upper=False, folded=False,
            invoice=Invoice(left=[("Thực hiện", self.byline_by)] if self.byline_by else [],
                            notes=notes),
        )


def _build_qa(rng: random.Random, document: dict) -> QaPage:
    source = rng.choice(corpus.periodical("qa", _LANG))
    writer, photographer = rng.sample(corpus.people(_LANG), 2)
    page = QaPage(
        section=source.get("section", ""), headline=source.get("headline", ""),
        subject_name=source.get("subject_name", ""), subject_role=source.get("subject_role", ""),
        deck=source.get("deck", ""), byline_by=f"Thực hiện: {writer}",
        byline_photo=f"Ảnh: {photographer}", footer_note=document.get("footer_note", ""),
        footer_right=f"{document.get('masthead', '')} · Trang {rng.randrange(20, 120)}",
        pull_quote=source.get("pull_quote", ""), bio_title="Tiểu sử",
        qa_pairs=[QaPair(**pair) for pair in source.get("qa", [])],
        bio_rows=[BioRow(**row) for row in source.get("bio_rows", [])],
    )
    return page


# ---------------------------------------------------------------- dispatch

_BUILDERS = {
    "lead_sidebar": _build_lead_sidebar,
    "classifieds": _build_classifieds,
    "toc": _build_toc,
    "qa_pairs": _build_qa,
}


def build(recipe, rng: random.Random):
    """The one entry point `rulebase.make_content()` calls for `kind:
    periodical` documents -- mirrors `rulebase.content.build()`'s own
    flag-driven dispatch (`is_invoice`, `no_items`, `form_fields`), applied
    one level up: `composition` picks which of the four page shapes to
    build, the same way those flags pick which shape of `Receipt` to build.
    """
    document = recipe.choices["document"].params
    composition = document.get("composition")
    builder = _BUILDERS.get(composition)
    if builder is None:
        raise ValueError(
            f"{recipe.choices['document'].id}: unknown periodical composition "
            f"{composition!r}; have {', '.join(sorted(_BUILDERS))}"
        )
    return builder(rng, document)


__all__ = [
    "ArticlePage",
    "BioRow",
    "BottomStory",
    "ClassifiedAd",
    "ClassifiedCategory",
    "ClassifiedsPage",
    "Notice",
    "Obituary",
    "QaPage",
    "QaPair",
    "SidebarItem",
    "TeaserItem",
    "TocEntry",
    "TocPage",
    "TocSection",
    "build",
]
