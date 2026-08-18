"""Build the contents of one receipt from a recipe.

The output is a `Receipt`: field values and nothing about pixels. A backend
turns it into a grid (`rulebase.layout`) and then into an image. This is why
the glyph render and the HTML render carry identical text -- there is exactly
one place that decides what a line says.

The ground truth is produced here too, from the same objects the render uses,
so a label cannot describe something the image does not show.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from datetime import date as _date
from datetime import timedelta
from typing import Any

from . import corpus
from .text import apply_case, ascii_fold, money, quantity, words_vi

# What the title line says, by document kind. Taken from the sample photos.
TITLES = {
    "eatery": ["PHIẾU THANH TOÁN", "HOÁ ĐƠN THANH TOÁN", "PHIẾU TÍNH TIỀN", "HOÁ ĐƠN"],
    "market": ["HOÁ ĐƠN BÁN HÀNG", "PHIẾU TÍNH TIỀN", "HOÁ ĐƠN GTGT", "PHIẾU THANH TOÁN"],
    "invoice": ["HOÁ ĐƠN GIÁ TRỊ GIA TĂNG"],
    "utility_water": ["HOÁ ĐƠN GIÁ TRỊ GIA TĂNG (TIỀN NƯỚC)"],
    "utility_power": ["HOÁ ĐƠN GIÁ TRỊ GIA TĂNG (TIỀN ĐIỆN)"],
    "hotel": ["HOÁ ĐƠN"],
    "export": ["HOÁ ĐƠN XUẤT KHẨU (EXPORT INVOICE)"],
    "bakery": ["HOÁ ĐƠN"],
}
SHOP_PREFIXES = [
    "Quán Ăn", "Nhà Hàng", "Cửa Hàng", "Quán", "Cafe", "Quán Nhậu",
    "Bếp", "Tiệm Ăn", "Nhà Hàng - Karaoke", "Siêu Thị Mini",
]
UNITS = ["KG", "kg", "gói", "hộp", "chai", "lon", "cái", "phần"]


@dataclass
class Item:
    """One line of the bill.

    `note` is the second line a supermarket prints under the barcode -- the
    product name with its per-kilo price -- and `discount` the `KM` line that
    follows a promoted product.
    """

    stt: int
    name: str
    qty: float
    unit_price: int
    amount: int
    barcode: str = ""
    unit: str = ""
    note: str = ""
    discount: int = 0
    original_price: int = 0
    vat_rate: int = 0
    # A utility bill charges a meter reading rather than a basket: the quantity
    # is the difference between two numbers the reader can check, and `quota`
    # is the subsidised allowance the tariff is measured against.
    meter_now: int = 0
    meter_prev: int = 0
    quota: int = 0
    tier: str = ""
    # A stay invoice bills one line per night, so the line carries the night it
    # covers and the room it was slept in -- two columns of their own on the
    # page, and two facts a reader can check against the dates in the party
    # block. `ref` is deliberately not called `room`: the same column holds a
    # contract line number on other documents.
    date: str = ""
    ref: str = ""
    # Priced by weight: the till multiplied before printing, so the quantity
    # column shows 1 and the real weight goes on the name line.
    #
    # A flag and not `unit == "KG"`, which is what this used to be. An invoice
    # lists "Kg" among its units, `rules/content.yaml` upper-cases the page
    # four times in five, and the two together turned an ordinary invoice line
    # into a weighed one -- which put a weight and a per-kilo price in the
    # label that no invoice layout has a column for.
    weighed: bool = False

    def display_qty(self) -> float:
        """What goes in the SL column.

        A weighed item prints SL 1: the till has already multiplied, and the
        real weight belongs on the name line ("157.500/KG 0,950 KG"). Printing
        0,950 in a four-character column is what produced "0.40".
        """
        return 1 if self.weighed else self.qty

    def display_unit_price(self) -> int:
        """And the price column then shows what that one weighed unit cost."""
        return self.amount if self.weighed else self.unit_price


@dataclass
class Store:
    """Who issued the paper. On an invoice this is the seller's letterhead.

    `tax_code` and `account` are blank on a till receipt and filled on a VAT
    invoice, which is the one document that has to identify its issuer well
    enough for the tax office to find them.
    """

    name: str
    branch: str = ""
    address: str = ""
    address2: str = ""
    phone: str = ""
    website: str = ""
    tax_code: str = ""
    account: str = ""


@dataclass
class Party:
    """The other side of an invoice: who is billed, and who takes delivery."""

    name: str = ""
    tax_code: str = ""
    address: str = ""
    locality: str = ""
    phone: str = ""
    account: str = ""
    code: str = ""                     # mã số khách hàng / customer number


@dataclass
class Invoice:
    """Everything a VAT invoice carries and a till receipt does not.

    A thermal receipt identifies nobody: it prints what was bought and what
    was paid. An invoice is a legal instrument, so it names both parties, is
    serially numbered, states the period it covers, writes the amount out in
    words, and ends in signatures. All of that lives here rather than growing
    `Receipt`, so a till receipt stays exactly the object it was.

    `left` and `right` are the party block as (label, value) pairs, in print
    order. Which fields appear is a property of the document kind and comes
    from `rules/document.yaml`; how they are arranged on the page is the
    layout's business.
    """

    serial: str = ""                   # Ký hiệu
    number: str = ""                   # Số
    form_no: str = ""                  # Mẫu số
    subtitle: str = ""                 # (Bản thể hiện của hoá đơn điện tử)
    period: str = ""                   # Tháng 01 năm 2025
    buyer: Party = field(default_factory=Party)
    consignee: Party = field(default_factory=Party)
    left_title: str = ""
    right_title: str = ""
    left: list[tuple[str, str]] = field(default_factory=list)
    right: list[tuple[str, str]] = field(default_factory=list)
    words_label: str = ""              # "Số tiền bằng chữ:"
    words: str = ""
    signatures: list[tuple[str, str]] = field(default_factory=list)
    signed_by: str = ""                # "Được ký bởi: ..."
    signed_at: str = ""                # "Ngày ký : 09/01/2025"
    notes: list[str] = field(default_factory=list)
    # The one-line strip of keys across the top of a modern invoice -- "Số hoá
    # đơn: INV001421 | Ngày: 30/09/2024 | Mã đặt phòng: 001421". Same (label,
    # value) shape as `left`/`right`, drawn as one run rather than a column,
    # and kept apart from them so the layout decides which of the two it wants.
    strip: list[tuple[str, str]] = field(default_factory=list)
    # "Tổng hợp": the money regrouped by tax rate, which is how a VAT form ends
    # instead of with a single tax line. Each row is already formatted, because
    # money spelling belongs to the receipt and not to the layout.
    summary: list[dict[str, str]] = field(default_factory=list)
    # The names printed under the signature titles -- a hotel bill is signed by
    # the receptionist and the guest, both named on the page.
    signature_names: list[str] = field(default_factory=list)


@dataclass
class Receipt:
    profile: str                       # 'eatery' | 'market' | 'invoice' | 'utility_*'
    title: str
    store: Store
    meta: list[tuple[str, str]]
    items: list[Item]
    totals: list[tuple[str, str]]      # (label, formatted amount), in print order
    footer: list[str]
    money_style: str
    upper: bool
    folded: bool
    # How every amount on this page is spelled. Held here rather than passed
    # around because `layout.py` formats item money too, and a suffix that
    # reached the totals but not the lines above them is exactly the kind of
    # split that made `rulebase.style` necessary.
    money_prefix: str = ""
    money_suffix: str = ""
    # Which entry of `totals` is the amount actually owed. Not the last one:
    # the cash tendered and the change come after it.
    grand_index: int = 0
    numbers: dict[str, Any] = field(default_factory=dict)
    # Set only for the document kinds that are invoices. `None` is the signal
    # every invoice-only section of a layout checks before drawing anything.
    invoice: Invoice | None = None

    def cash(self, value: float) -> str:
        """One amount, spelled the way this page spells them."""
        return money(value, self.money_style, self.money_suffix, self.money_prefix)

    def ground_truth(self) -> dict[str, Any]:
        """CORD-style nested label, built from the same objects as the render."""
        store: dict[str, str] = {"name": self.store.name}
        for key in ("branch", "address", "address2", "phone", "website",
                    "tax_code", "account"):
            value = getattr(self.store, key)
            if value:
                store[key] = value
        menu = []
        for item in self.items:
            # The label describes what the image shows, so it uses the same
            # display values the grid does; the true weight rides along
            # separately rather than replacing the printed quantity.
            shown_qty = item.display_qty()
            entry: dict[str, str] = {
                "nm": item.name,
                "cnt": quantity(shown_qty, self.money_style, 3 if shown_qty % 1 else 0),
                "price": self.cash(item.amount),
            }
            if item.weighed:
                entry["weight"] = f"{quantity(item.qty, 'dot', 3)} {item.unit}"
                entry["unitprice_per_unit"] = self.cash(item.unit_price)
            if item.display_unit_price():
                entry["unitprice"] = self.cash(item.display_unit_price())
            if item.barcode:
                entry["barcode"] = item.barcode
            if item.discount:
                entry["discountprice"] = self.cash(-abs(item.discount))
            if item.vat_rate:
                entry["vatrate"] = f"{item.vat_rate}%"
            if item.meter_now or item.meter_prev:
                entry["meter_now"] = str(item.meter_now)
                entry["meter_prev"] = str(item.meter_prev)
            if item.date:
                entry["date"] = item.date
            if item.ref:
                entry["ref"] = item.ref
            # Only an invoice has an "Đơn vị tính" column. A till knows the unit
            # too, and prints it nowhere; recording it here would put a field in
            # the label that no reader of the image can check.
            if item.unit and self.invoice:
                entry["unit"] = item.unit
            menu.append(entry)
        parse: dict[str, Any] = {
            "doc_type": f"receipt_{self.profile}",
            "title": self.title,
            "store": store,
            "menu": menu,
            "total": {label: value for label, value in self.totals},
            "footer": list(self.footer),
        }
        if self.invoice:
            parse["invoice"] = self._invoice_label()
        return parse

    def _invoice_label(self) -> dict[str, Any]:
        """The invoice half of the label.

        Every entry here is something a layout prints. That is not a style
        rule: `tests/test_content.py` measures how much of the label the page
        never shows, and a field recorded but not drawn teaches a model to
        hallucinate it.
        """
        invoice = self.invoice
        assert invoice is not None
        data: dict[str, Any] = {}
        for key in ("serial", "number", "form_no", "subtitle", "period", "words"):
            value = getattr(invoice, key)
            if value:
                data[key] = value
        for name, entries in (
            ("left", invoice.left), ("right", invoice.right), ("strip", invoice.strip)
        ):
            fields = {label: value for label, value in entries if value}
            if fields:
                data[name] = fields
        if invoice.summary:
            data["summary"] = [
                {key: value for key, value in row.items() if value}
                for row in invoice.summary
            ]
        if invoice.signature_names:
            data["signed_names"] = list(invoice.signature_names)
        if invoice.signed_by:
            data["signed_by"] = invoice.signed_by
        if invoice.signed_at:
            data["signed_at"] = invoice.signed_at
        return data

    def text_sequence(self) -> str:
        """Flat reading order, for text-only pre-training and for OCR scoring."""
        parts = [self.store.name]
        for value in (self.store.branch, self.store.address, self.store.address2,
                      self.store.phone, self.store.website, self.store.tax_code,
                      self.store.account, self.title):
            if value:
                parts.append(value)
        invoice = self.invoice
        if invoice:
            for value in (invoice.serial, invoice.number, invoice.form_no,
                          invoice.subtitle, invoice.period):
                if value:
                    parts.append(value)
            for label, value in (
                list(invoice.strip) + list(invoice.left) + list(invoice.right)
            ):
                parts.append(f"{label} {value}".strip())
        for label, value in self.meta:
            parts.append(f"{label} {value}".strip())
        for item in self.items:
            parts.append(item.name)
            parts.append(self.cash(item.amount))
        for label, value in self.totals:
            parts.append(f"{label} {value}".strip())
        if invoice and invoice.words:
            parts.append(f"{invoice.words_label} {invoice.words}".strip())
        if invoice:
            for row in invoice.summary:
                parts.append(" ".join(value for value in row.values() if value))
            for title, instruction in invoice.signatures:
                parts.append(f"{title} {instruction}".strip())
            parts.extend(invoice.signature_names)
            for value in (invoice.signed_by, invoice.signed_at):
                if value:
                    parts.append(value)
        parts.extend(self.footer)
        return " ".join(part for part in parts if part)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["store"] = asdict(self.store)
        data["items"] = [asdict(item) for item in self.items]
        data["invoice"] = asdict(self.invoice) if self.invoice else None
        return data


def _round_to(value: float, step: int) -> int:
    return int(round(value / step)) * step


def _barcode(rng: random.Random) -> str:
    """13 digits, the way EAN-13 looks on a Vietnamese product."""
    return "".join(str(rng.randrange(10)) for _ in range(13))


def _build_store(profile: str, rng: random.Random, case) -> Store:
    if profile == "market":
        brand, branch = rng.choice(corpus.shops("market"))
        ward, district, _city = rng.choice(corpus.wards())
        street = rng.choice(corpus.streets())
        number = rng.randrange(1, 400)
        store = Store(
            name=case(brand),
            branch=case(branch),
            address=case(f"Số {number}A đường {street}"),
            # "Q.1" for a numbered district, "Q.Thanh Xuân" for a named one --
            # the same shape either way, which is how tills print it.
            address2=case(f"P.{ward}, Q.{district}"),
            phone=case(f"ĐT: 0{rng.randrange(24, 29)}.7{rng.randrange(1000000, 9999999)}"),
        )
        if rng.random() < 0.35:
            store.website = case(f"Website: www.{brand.lower().replace(' ', '').replace('.', '')}.com.vn")
        return store

    name = f"{rng.choice(SHOP_PREFIXES)} {rng.choice(corpus.shops('eatery'))[0]}"
    if rng.random() < 0.25:
        name = f"{name} {rng.randrange(1, 300)}"
    ward, district, city = rng.choice(corpus.wards())
    street = rng.choice(corpus.streets())
    number = (
        str(rng.randrange(1, 300))
        if rng.random() < 0.7
        else f"{rng.randrange(1, 60)}-{rng.randrange(61, 200)}"
    )
    store = Store(name=case(name))
    if rng.random() < 0.92:
        store.address = case(f"{number} {street} - {district} - {city}")
    if rng.random() < 0.85:
        phone = f"0{rng.randrange(2, 10)}{rng.randrange(10000000, 99999999)}"[:11]
        store.phone = case(phone if rng.random() < 0.5 else f"ĐT: {phone}")
    return store


def _build_items(profile: str, rng: random.Random, case, params: dict) -> list[Item]:
    lo, hi = params.get("num_items", [3, 12])
    count = rng.randint(int(lo), int(hi))
    lang = params.get("lang", corpus.DEFAULT_LANG)
    catalogue = corpus.items(profile, lang)
    prob_discount = float(params.get("prob_item_discount", 0.0))
    prob_weighed = float(params.get("prob_weighed", 0.0))
    vat_rates = params.get("vat_rates") or []
    # A till rounds a price to the nearest 500 or 1000 because that is what the
    # shelf label says. A tariff does not: `price_step: 1` is what lets an
    # invoice carry a unit price of 1.678 without it rounding away to 2.000.
    step = int(params.get("price_step", 500 if profile == "market" else 1000))
    units = list(params.get("units") or [])
    # A basket holds one or two of a thing; an export lot holds four hundred.
    # Without this the quantity column of an export invoice reads like a
    # corner shop's, and the amounts stop being export amounts.
    qty_range = params.get("qty_range")

    items: list[Item] = []
    for index in range(count):
        name, price_lo, price_hi = rng.choice(catalogue)
        unit_price = _round_to(rng.uniform(price_lo, price_hi), step)
        by_weight = rng.random() < prob_weighed
        if by_weight:
            qty: float = round(rng.uniform(0.1, 2.0), 3)
            amount = _round_to(unit_price * qty, 5)
            unit = "KG"
        elif qty_range:
            qty = rng.randrange(int(qty_range[0]), int(qty_range[1]))
            amount = int(unit_price * qty)
            unit = case(rng.choice(units)) if units else ""
        else:
            qty = rng.randrange(1, 13) if rng.random() < 0.2 else rng.randrange(1, 4)
            amount = int(unit_price * qty)
            if profile == "market":
                unit = rng.choice(UNITS[2:]) if rng.random() < 0.3 else ""
            else:
                # An invoice always fills its "Đơn vị tính" column; the words
                # that go in it are printed, so they come from the rules.
                unit = case(rng.choice(units)) if units else ""
        item = Item(
            stt=index + 1,
            name=case(name),
            qty=qty,
            unit_price=unit_price,
            amount=amount,
            unit=unit,
            weighed=by_weight,
        )
        if profile == "market":
            item.barcode = _barcode(rng)
            # A supermarket till prints the barcode and the money on one line
            # and the product name, indented, on the next. Weighed goods add
            # the per-kilo price and the weight to that second line.
            item.note = (
                case(f"{name} {money(unit_price, 'dot')}/KG {quantity(qty, 'dot', 3)} KG")
                if by_weight
                else item.name
            )
            if vat_rates:
                item.vat_rate = int(rng.choice(vat_rates))
            if rng.random() < 0.2:
                item.original_price = _round_to(unit_price * rng.uniform(1.05, 1.4), 500)
        elif vat_rates and params.get("item_vat"):
            # A VAT invoice states the rate on every line, because two lines of
            # the same invoice may be taxed differently.
            item.vat_rate = int(rng.choice(vat_rates))
        if rng.random() < prob_discount:
            item.discount = _round_to(amount * rng.uniform(0.05, 0.45), 100)
        items.append(item)
    return items


def _build_meta(profile: str, rng: random.Random, case, params: dict) -> list[tuple[str, str]]:
    day, month, year = rng.randrange(1, 29), rng.randrange(1, 13), rng.randrange(2017, 2027)
    hour, minute = rng.randrange(6, 24), rng.randrange(0, 60)
    date = (
        f"{day:02d}/{month:02d}/{year}"
        if rng.random() < 0.6
        else f"{day:02d}-{month:02d}-{year}"
    )
    stamp = f"{date} {hour:02d}:{minute:02d}"

    if profile == "market":
        meta = [
            (case("Ngày bán:"), f"{stamp}"),
            (case("HD:"), f"{rng.randrange(1, 999999):08d}"),
            (case("Quầy:"), f"{rng.randrange(1, 40):03d}"),
            (case("NVBH:"), f"{rng.randrange(1, 99999999):08d}"),
        ]
        if params.get("show_tax_code") and rng.random() < 0.7:
            code = f"M{rng.randrange(1, 9)}-{year % 100}-{rng.randrange(100000, 999999)}"
            meta.append((case("Mã CQT:"), code))
        return meta

    meta = [(case("Số phiếu:"), f"{rng.randrange(100, 99999)}")]
    if rng.random() < float(params.get("prob_table", 0.6)):
        meta.append((case("Bàn"), f"{rng.randrange(1, 40)}"))
    meta.append((case("Thời gian:"), stamp))
    if rng.random() < 0.35:
        meta.append((case("Thu ngân:"), f"{rng.randrange(1000, 99999)}"))
    return meta


# ------------------------------------------------------------ VAT invoices
#
# A till receipt records a transaction; an invoice is a legal instrument, and
# the difference is visible on the paper. It names both parties, carries a
# serial the tax office can look up, states the period it covers, writes the
# total out in words so the figure cannot be altered, and ends in signatures.
# What follows builds that half. `profile` decides which of the three kinds it
# is -- a general VAT invoice, a water bill or an electricity bill -- and the
# labels, being printed on the page, come from `rules/document.yaml`.


def _tax_code(rng: random.Random) -> str:
    """Mã số thuế: ten digits, sometimes with the three-digit branch suffix."""
    body = f"{rng.randrange(10 ** 9, 10 ** 10)}"
    return f"{body}-{rng.randrange(1, 40):03d}" if rng.random() < 0.25 else body


def _bank_account(rng: random.Random) -> str:
    return f"{rng.randrange(10 ** 11, 10 ** 12)}"


def _fill(template: str, values: dict[str, str]) -> str:
    """Substitute `{key}` in a rules-owned string. Not `str.format`.

    The strings are Vietnamese sentences typed into YAML by hand; one stray
    brace would make `format` raise in the middle of a long run, and a
    `KeyError` on a footer line is a poor reason to lose an hour of rendering.
    """
    for key, value in values.items():
        template = template.replace("{" + key + "}", value)
    return template


# Ký hiệu, as Decree 123 spells it: 1K25TAE -- kind, K, the year, three
# letters. An English invoice numbers itself differently, so the shape is a
# template rather than a format string in the code.
SERIAL_FORMAT = "{k}K{yy}{letters}"


def _serial(rng: random.Random, year: int, template: str = SERIAL_FORMAT) -> str:
    return _fill(template or SERIAL_FORMAT, {
        "k": str(rng.randrange(1, 7)),
        "yy": f"{year % 100:02d}",
        "year": str(year),
        "letters": "".join(rng.choice("ABCDEGHKLMNPQRSTUVXY") for _ in range(3)),
        "n": f"{rng.randrange(1, 9999):04d}",
    })


def _build_issuer(profile: str, rng: random.Random, case, params: dict) -> Store:
    """The letterhead: who issued the invoice, well enough to be found again."""
    lang = params.get("lang", corpus.DEFAULT_LANG)
    name, unit = (rng.choice(corpus.shops(profile, lang)) + ("",))[:2]
    ward, district, city = rng.choice(corpus.wards(lang))
    street = rng.choice(corpus.streets(lang))
    number = rng.randrange(1, 400)

    address = params.get("address_format", "Số {number} {street}, {ward}, {district}, {city}")
    address = (
        address.replace("{number}", str(number)).replace("{street}", street)
        .replace("{ward}", ward).replace("{district}", district).replace("{city}", city)
    )
    store = Store(
        name=case(name),
        branch=case(unit) if unit and params.get("show_issuer_unit", True) else "",
        address=case(address),
        # A VAT invoice must identify its issuer to the tax office; a hotel
        # bill and a bakery order need not, and printing a tax code no layout
        # of theirs has a line for would put a field in the label that no
        # reader of the image can check.
        tax_code=_tax_code(rng) if params.get("show_seller_tax_code", True) else "",
    )
    if params.get("show_seller_website"):
        slug = "".join(c for c in ascii_fold(name).lower() if c.isalnum())[:18]
        store.website = f"www.{slug or 'shop'}.vn"
    if params.get("show_seller_phone", True):
        # The bare number. A till embeds its own "ĐT:" because it prints one
        # centred line; a letterhead sets the label in its own cell so the
        # label can quote the value exactly -- see `_put_field`.
        store.phone = f"0{rng.randrange(2, 10)}{rng.randrange(10000000, 99999999)}"[:11]
    if params.get("show_seller_account"):
        store.account = _bank_account(rng)
    return store


def _build_utility_items(profile: str, rng: random.Random, case, params: dict) -> list[Item]:
    """Tariff bands off one meter.

    The quantity is not a basket count but the difference between two readings
    printed beside it, which is the whole point of a utility bill: the reader
    can redo the subtraction. Only the first band carries the readings -- the
    bands below it are the same meter, split by price -- and a row whose fields
    are all empty is skipped by the layout, so one item template serves both.
    """
    lo, hi = params.get("num_items", [1, 3])
    catalogue = corpus.items(profile, params.get("lang", corpus.DEFAULT_LANG))
    count = min(rng.randint(int(lo), int(hi)), len(catalogue))
    step = int(params.get("price_step", 1))
    tiers = list(params.get("tier_codes") or [])
    vat_rates = params.get("vat_rates") or []

    # Bands are consecutive and start at the first: a bill charging band 3
    # without band 1 would not survive being read. A one-line bill is the
    # exception -- that is a flat tariff, and any of them may be the one.
    start = rng.randrange(0, max(len(catalogue) - count, 0) + 1) if count == 1 else 0
    previous = rng.randrange(60, 9800)
    items: list[Item] = []
    for index in range(count):
        name, price_lo, price_hi = catalogue[start + index]
        unit_price = _round_to(rng.uniform(price_lo, price_hi), step)
        qty = rng.randrange(*params.get("qty_range", [3, 90]))
        item = Item(
            stt=index + 1,
            name=case(name),
            qty=qty,
            unit_price=unit_price,
            amount=int(unit_price * qty),
            # A water bill puts "(m3)" in the column heading, not on the row,
            # so there is no unit to record unless the layout has a column for
            # one -- and a label field the page never shows is the defect
            # `pipeline/invariants.py` exists to catch.
            unit=case(params.get("unit", "")),
            quota=qty,
            tier=case(rng.choice(tiers)) if tiers else "",
        )
        if vat_rates and params.get("item_vat"):
            item.vat_rate = int(rng.choice(vat_rates))
        items.append(item)

    consumed = sum(int(item.qty) for item in items)
    items[0].meter_prev = previous
    items[0].meter_now = previous + consumed
    return items


def _build_stay(rng: random.Random, params: dict) -> dict[str, Any]:
    """One booking: when it starts, how many nights, which room.

    Drawn before the lines because both halves of the page describe the same
    stay -- the row dates are the nights between check-in and check-out, and
    the party block states them again as a date range. Two draws would let the
    block say three nights over a table with four rows in it, which is the one
    error a reader of a hotel bill notices immediately.
    """
    lo, hi = params.get("nights", [1, 4])
    nights = max(int(rng.randint(int(lo), int(hi))), 1)
    start = _date(rng.randrange(2019, 2027), rng.randrange(1, 13), rng.randrange(1, 26))
    return {
        "nights": nights,
        "dates": [start + timedelta(days=offset) for offset in range(nights)],
        "checkin": start,
        "checkout": start + timedelta(days=nights),
        # Floor and door, the way a room is numbered: 3rd floor, room 04.
        "room": f"{rng.randrange(1, 13)}{rng.randrange(1, 21):02d}",
        "code": f"{rng.randrange(1, 999999):06d}",
    }


def _build_stay_items(profile: str, rng: random.Random, case, params: dict,
                      stay: dict) -> list[Item]:
    """One line per night at one nightly rate, then whatever else was used.

    The nightly rate is drawn once and repeated, because that is what a hotel
    charges and what makes the arithmetic on the page checkable: four identical
    rows and a total that is four times one of them. The room charges are the
    first `room_items` entries of the corpus -- order carries meaning in
    `items_hotel.txt`, the same way it does in the utility corpora -- and the
    rest of the file is the extras that may be added underneath.
    """
    catalogue = corpus.items(profile, params.get("lang", corpus.DEFAULT_LANG))
    room_count = max(min(int(params.get("room_items", 5)), len(catalogue)), 1)
    step = int(params.get("price_step", 1000))

    name, price_lo, price_hi = catalogue[rng.randrange(room_count)]
    nightly = _round_to(rng.uniform(price_lo, price_hi), step)
    notes = list(params.get("item_notes") or [])
    # One note for the whole stay, not one per night: the line under the room
    # charge says what the rate includes, and it includes the same thing every
    # night of the same booking.
    note = case(rng.choice(notes)) if notes and rng.random() < 0.7 else ""

    items = [
        Item(
            stt=index + 1,
            name=case(name),
            qty=1,
            unit_price=nightly,
            amount=nightly,
            note=note,
            date=night.strftime("%d/%m/%Y"),
            ref=stay["room"],
        )
        for index, night in enumerate(stay["dates"])
    ]
    for _ in range(rng.randint(0, int(params.get("extra_items", 2)))):
        if len(catalogue) <= room_count:
            break
        extra, price_lo, price_hi = catalogue[rng.randrange(room_count, len(catalogue))]
        price = _round_to(rng.uniform(price_lo, price_hi), step)
        quantity_used = rng.randint(1, 3)
        items.append(Item(
            stt=len(items) + 1,
            name=case(extra),
            qty=quantity_used,
            unit_price=price,
            amount=price * quantity_used,
            date=rng.choice(stay["dates"]).strftime("%d/%m/%Y"),
            ref=stay["room"],
        ))
    # A folio is printed in date order and numbered down the page: an extra
    # billed on the second night belongs between the second and third nights,
    # not under them. Sorting is stable, so a drink and the room it was drunk
    # in keep the order they were built in.
    items.sort(key=lambda item: tuple(reversed(item.date.split("/"))))
    for index, item in enumerate(items):
        item.stt = index + 1
    return items


def _tax_by_rate(items: list[Item]) -> dict[int, tuple[int, int]]:
    """{rate: (net, tax)} -- the grouping a VAT form's summary is built from.

    Rounded per RATE rather than per line, and used by both the summary block
    and the amount owed. Rounding each line and adding those up differs from
    rounding the group by a đồng often enough to matter, and the two halves of
    the same page would then disagree about the tax.
    """
    groups: dict[int, int] = {}
    for item in items:
        if item.vat_rate:
            groups[item.vat_rate] = groups.get(item.vat_rate, 0) + item.amount
    return {rate: (net, _round_to(net * rate / 100.0, 1)) for rate, net in groups.items()}


def _vat_summary(items: list[Item], params: dict, case, cash, grand: int) -> list[dict[str, str]]:
    """"Tổng hợp": the money regrouped by tax rate.

    A VAT form does not end with one tax line, because two lines of the same
    invoice may be taxed differently -- it ends with a small table saying how
    much was sold at each rate and how much tax that came to. The rows printed
    are the rates the FORM carries (`summary_rates`), not the rates this sale
    happened to use: a blank 5% row is part of the paper, and leaving it out
    would make every generated form a different shape.
    """
    labels = params.get("summary_labels") or {}
    rows: list[dict[str, str]] = [{
        "label": case(str(labels.get("exempt", "Hàng hoá không chịu thuế GTGT:"))),
        "rate": "", "net": "", "vat": "", "gross": "",
    }]
    taxed = case(str(labels.get("taxed", "Hàng hoá chịu thuế suất:")))
    charged = _tax_by_rate(items)
    net_total = tax_total = 0
    for rate in params.get("summary_rates") or params.get("vat_rates") or []:
        rate = int(rate)
        net, tax = charged.get(rate, (0, 0))
        net_total += net
        tax_total += tax
        rows.append({
            "label": taxed,
            "rate": f"{rate}%",
            # A rate nobody sold at prints its label and its rate and nothing
            # else -- an empty cell, not a zero. The form is pre-printed; the
            # money is not.
            "net": cash(net) if net else "",
            "vat": cash(tax) if net else "",
            "gross": cash(net + tax) if net else "",
        })
    rows.append({
        "label": case(str(labels.get("total", "Tổng cộng tiền thanh toán:"))),
        "rate": "",
        "net": cash(net_total),
        "vat": cash(tax_total),
        "gross": cash(grand),
    })
    return rows


def _build_invoice(profile: str, store: Store, items: list[Item], rng: random.Random,
                   case, cash, params: dict, grand: int,
                   stay: dict | None = None) -> Invoice:
    """The invoice half: the parties, the serial, the words, the signatures."""
    lang = params.get("lang", corpus.DEFAULT_LANG)
    day, month, year = rng.randrange(1, 29), rng.randrange(1, 13), rng.randrange(2019, 2027)
    # A stay is invoiced when the guest leaves, so the date on the paper is the
    # check-out date rather than a date of its own. Drawing a second one would
    # put an invoice date outside the stay it bills.
    if stay:
        day, month, year = stay["checkout"].day, stay["checkout"].month, stay["checkout"].year
    issued = f"{day:02d}/{month:02d}/{year}"

    buyer = Party(
        name=case(rng.choice(corpus.people(lang))),
        tax_code=_tax_code(rng),
        code=f"{rng.randrange(10 ** 8, 10 ** 9)}",
        account=_bank_account(rng),
        phone=f"0{rng.randrange(2, 10)}{rng.randrange(10000000, 99999999)}"[:11],
    )
    ward, district, city = rng.choice(corpus.wards(lang))
    street = rng.choice(corpus.streets(lang))
    buyer.address = case(f"{rng.randrange(1, 300)} {street}")
    buyer.locality = case(f"{ward}, {district}, {city}")

    consignee = Party(name=buyer.name, address=buyer.address, locality=buyer.locality)
    if rng.random() < 0.45:            # delivered somewhere other than the billing address
        ward2, district2, city2 = rng.choice(corpus.wards(lang))
        consignee.name = case(rng.choice(corpus.people(lang)))
        consignee.address = case(f"{rng.randrange(1, 300)} {rng.choice(corpus.streets(lang))}")
        consignee.locality = case(f"{ward2}, {district2}, {city2}")

    consumed = sum(int(item.qty) for item in items)
    values = {
        "seller_name": store.name,
        "seller_unit": store.branch,
        "seller_address": store.address,
        "seller_tax_code": store.tax_code,
        "seller_phone": store.phone,
        "seller_account": store.account,
        "buyer_name": buyer.name,
        "buyer_address": buyer.address,
        "buyer_locality": buyer.locality,
        "buyer_tax_code": buyer.tax_code,
        "buyer_account": buyer.account,
        "buyer_code": buyer.code,
        "buyer_phone": buyer.phone,
        # "Tên đơn vị" / "Importer's name": the buyer of a business document is
        # a legal person, named separately from whoever signs for it.
        "buyer_company": case(rng.choice(corpus.shops("invoice", lang))[0]),
        "ship_name": consignee.name,
        "ship_address": consignee.address,
        "ship_locality": consignee.locality,
        "serial": _serial(rng, year, params.get("serial_format", SERIAL_FORMAT)),
        "number": f"{rng.randrange(1, 999999):08d}",
        "form_no": f"01GTKT{rng.randrange(0, 4)}/{rng.randrange(1, 999):03d}",
        # Two keys an e-invoice rendition prints in its seller block, both of
        # them a reader's way back to the record behind the paper.
        "security_code": f"{rng.randrange(10 ** 6, 10 ** 7)}",
        "transaction_no": f"{rng.randrange(10 ** 9, 10 ** 10)}",
        "invoice_code": f"{rng.randrange(10 ** 11, 10 ** 12)}",
        "date": issued,
        "due_date": f"{day:02d}/{(month % 12) + 1:02d}/{year + (month // 12)}",
        "households": str(rng.randrange(1, 9)),
        "meter": f"{rng.choice('ABCDE')}{rng.randrange(1, 999):03d} - {rng.randrange(1000, 9999)}",
        "usage_period": (
            f"{day:02d}/{month:02d}/{year} - "
            f"{day:02d}/{(month % 12) + 1:02d}/{year + (month // 12)}"
        ),
        "consumption": quantity(consumed, params.get("money_style", "dot")),
        "currency": case(params.get("currency", "VND")),
        "payment_form": case(rng.choice(params.get("payment_forms") or ["Chuyển khoản"])),
        "grand": cash(grand),
        "bank_name": case(rng.choice(params.get("banks") or ["Ngân hàng TMCP Ngoại thương"])),
    }
    # ---- lưu trú: the booking this bill closes.
    if stay:
        checkin, checkout = stay["checkin"], stay["checkout"]
        values.update({
            "room_no": stay["room"],
            "room_type": case(rng.choice(params.get("room_types") or ["Phòng tiêu chuẩn"])),
            "nights": str(stay["nights"]),
            "checkin_date": checkin.strftime("%d/%m/%Y"),
            "checkout_date": checkout.strftime("%d/%m/%Y"),
            # Fixed hours, not random ones: a hotel has one check-in time and
            # one check-out time, printed on the bill because they are policy.
            "checkin_time": str(params.get("checkin_time", "14:00")),
            "checkout_time": str(params.get("checkout_time", "12:00")),
            "booking_code": stay["code"],
            "channel_code": f"{rng.randrange(10 ** 9, 10 ** 10)}",
            "booking_source": case(rng.choice(params.get("booking_sources") or ["Trực tiếp"])),
            "guests": str(rng.randint(1, 4)),
            "issued_at": f"{issued} {rng.randrange(6, 23):02d}:{rng.randrange(0, 60):02d}",
        })
    # ---- xuất khẩu: the shipment the invoice travels with.
    values.update({
        "contract_no": f"{rng.randrange(1, 999):03d}/{year % 100:02d}/HĐXK",
        "contract_date": f"{day:02d}/{month:02d}/{year}",
        "bill_of_lading": f"{''.join(rng.choice('ABCDEFGHJKLMNP') for _ in range(4))}"
                          f"{rng.randrange(10 ** 7, 10 ** 8)}",
        "container_no": f"{''.join(rng.choice('ABCDEFGHJKLMNP') for _ in range(4))}"
                        f"U{rng.randrange(10 ** 6, 10 ** 7)}",
        "place_of_delivery": case(rng.choice(params.get("delivery_places") or ["Cảng Hải Phòng"])),
        "place_of_destination": case(rng.choice(params.get("destinations") or ["Busan, Korea"])),
        "transporter": case(rng.choice(params.get("transporters") or ["Hãng tàu ONE"])),
        "seller_account_usd": _bank_account(rng),
        "exchange_rate": quantity(
            rng.randrange(23000, 26500), params.get("money_style", "dot")
        ),
    })

    def block(entries) -> list[tuple[str, str]]:
        pairs = []
        for entry in entries or []:
            key, label = (list(entry) + [""])[:2]
            value = values.get(str(key), "")
            if value:
                pairs.append((case(str(label)), value))
        return pairs

    fields = params.get("party_fields") or {}
    invoice = Invoice(
        serial=values["serial"],
        # "Số hoá đơn: INV001421" on a designed invoice is the serial, and
        # there is no second number underneath it. Issuing one anyway would put
        # a field in the label that no layout of that document prints.
        number=values["number"] if params.get("show_number", True) else "",
        form_no=values["form_no"] if params.get("show_form_no") else "",
        subtitle=case(params.get("subtitle", "")),
        # Substituted first, cased after: `case` may upper-case the template,
        # and "{MONTH}" matches no key.
        period=case(_fill(params.get("period_format", ""),
                          {**values, "month": f"{month:02d}", "year": str(year)})),
        buyer=buyer,
        consignee=consignee,
        left_title=case(fields.get("left_title", "")),
        right_title=case(fields.get("right_title", "")),
        left=block(fields.get("left")),
        right=block(fields.get("right")),
        strip=block(fields.get("strip")),
        notes=[case(_fill(str(line), values)) for line in params.get("notes") or []],
    )
    if params.get("summary"):
        invoice.summary = _vat_summary(items, params, case, cash, grand)
    if params.get("show_amount_words", True):
        invoice.words_label = case(params.get("words_label", "Số tiền bằng chữ:"))
        invoice.words = case(words_vi(grand, params.get("words_unit", "đồng")))
    invoice.signatures = [
        (case(str(title)), case(str(instruction)))
        for title, instruction in (params.get("signature_labels") or [])
    ]
    if params.get("signature_names"):
        # A hotel bill is signed by two named people, and both names are
        # printed under the titles rather than left to handwriting.
        invoice.signature_names = [
            case(rng.choice(corpus.people(lang))), buyer.name
        ][:len(invoice.signatures) or 2]
    if params.get("digital_signature"):
        invoice.signed_by = case(f"{params.get('signed_by_label', 'Được ký bởi:')} {store.name}")
        invoice.signed_at = case(f"{params.get('signed_at_label', 'Ngày ký:')} {issued}")
    return invoice


def build(recipe, rng: random.Random | None = None) -> Receipt:
    """Fill in one receipt for `recipe`."""
    rng = rng or random.Random(recipe.seed)
    document = recipe.choices["document"].params
    content = recipe.choices["content"].params

    profile = document.get("profile", "eatery")
    money_style = content.get("money_style", "dot")
    money_suffix = content.get("money_suffix", "")
    money_prefix = content.get("money_prefix", "")
    folded = rng.random() < float(content.get("prob_ascii_fold", 0.0))
    upper = rng.random() < float(content.get("prob_uppercase", 0.5))
    # An invoice is a different document, not a wider receipt: it has a
    # letterhead instead of a shop name, a party block instead of a meta block,
    # and an amount written out in words. `document.invoice` is what says so.
    is_invoice = bool(document.get("invoice"))
    params = {**document, **content}
    params.setdefault("lang", corpus.DEFAULT_LANG)

    def case(text: str) -> str:
        return apply_case(text, upper=upper, fold=folded)

    def switch(name: str, default: bool = False) -> bool:
        """A yes/no the content value decides -- unless the document knows better.

        `show_vat` and `show_payment` are written in `rules/content.yaml`
        because they are largely a matter of how a page is typeset. They are
        not only that: an export invoice carries no VAT line however the
        content value is spelled, and a hotel bill always closes with what was
        paid and what is still owed. Where the document states one of these it
        wins, because it is a fact about the document and not about its style.
        """
        if name in document:
            return bool(document[name])
        return bool(content.get(name, default))

    def cash(value: float) -> str:
        return money(value, money_style, money_suffix, money_prefix)

    if is_invoice:
        store = _build_issuer(profile, rng, case, params)
        # The stay is drawn before its lines because both describe it -- see
        # `_build_stay`. `None` for every document that is not a bill for one.
        stay = _build_stay(rng, params) if params.get("stay") else None
        if params.get("metered"):
            items = _build_utility_items(profile, rng, case, params)
        elif stay:
            items = _build_stay_items(profile, rng, case, params, stay)
        else:
            items = _build_items(profile, rng, case, params)
        # The party block carries what a till prints as meta, and it is emitted
        # by its own section; leaving `meta` filled as well would put the same
        # facts into `text_sequence` twice, once for text nobody drew.
        meta: list[tuple[str, str]] = []
    else:
        stay = None
        store = _build_store(profile, rng, case)
        items = _build_items(profile, rng, case, params)
        meta = _build_meta(profile, rng, case, params)

    subtotal = sum(item.amount for item in items)
    item_discount = sum(item.discount for item in items)
    grand = subtotal - item_discount

    totals: list[tuple[str, str]] = []
    numbers: dict[str, Any] = {"subtotal": subtotal, "discount": item_discount}

    labels = document.get("total_labels") or {}
    if switch("show_subtotal", True):
        totals.append((case(labels.get("subtotal", "Tiền hàng")), cash(subtotal)))
    if item_discount:
        totals.append((case(labels.get("discount", "Tổng tiền giảm")), cash(-item_discount)))

    vat_rate = 0
    # A form that summarises by rate carries no single VAT line: the tax is the
    # sum over the rates actually charged, and the "Tổng hợp" block below the
    # table is where it is printed. Computing it here anyway is what lets the
    # amount in words spell the figure the summary adds up to.
    summarised = bool(document.get("summary"))
    if summarised:
        vat = sum(tax for _net, tax in _tax_by_rate(items).values())
        grand += vat
        numbers["vat"] = vat
    # A till prints the VAT line when it feels like it; a VAT invoice without
    # one is not a VAT invoice, so the coin is only tossed for the till.
    elif switch("show_vat") and (is_invoice or rng.random() < 0.8):
        vat_rate = int(rng.choice(document.get("vat_rates") or [8, 10]))
        vat = _round_to(grand * vat_rate / 100.0, 1)
        totals.append((case(f"{labels.get('vat', 'Thuế GTGT')} {vat_rate}%"), cash(vat)))
        grand += vat
        numbers["vat_rate"] = vat_rate
        numbers["vat"] = vat

    # Charges the utility adds on top of the tax: the environment levy on a
    # water bill is 10% of the goods line, printed as its own row and included
    # in the amount owed. A value below 1 is read as a rate, one at or above it
    # as a flat amount -- shipping on an English invoice is not a percentage.
    for entry in document.get("surcharges") or []:
        label, rate = (list(entry) + [0])[:2]
        charge = _round_to(subtotal * float(rate), 1) if float(rate) < 1 else int(rate)
        if charge:
            totals.append((case(str(label)), cash(charge)))
            grand += charge
            numbers.setdefault("surcharges", []).append([str(label), charge])

    # A summarising form prints what is owed in its "Tổng hợp" block rather
    # than as a line of this list, so the index deliberately points past the
    # end: there is nothing here to set in bold.
    grand_index = len(totals)
    if not summarised:
        totals.append((case(labels.get("grand", "Thanh toán")), cash(grand)))
    numbers["grand"] = grand

    if switch("show_payment", True):
        choices = corpus.payments(params["lang"])
        wanted = params.get("payment_groups")
        if wanted:
            # A room booked through a channel is not settled in cash at the
            # desk. Narrowing the group is how a document says so without a
            # second payments corpus -- and it falls back rather than failing,
            # since an empty shortlist is a typo, not a receipt with no total.
            choices = [entry for entry in choices if entry[1] in wanted] or choices
        label, group = rng.choice(choices)
        paid = grand if group != "tienmat" else _round_to(grand + rng.uniform(0, 60000), 10000)
        paid = max(paid, grand)
        totals.append((case(label), cash(paid)))
        totals.append((case(labels.get("change", "Tiền trả lại")), cash(paid - grand)))
        numbers["paid"] = paid
        numbers["change"] = paid - grand

    if content.get("show_item_count"):
        total_qty = sum(item.qty for item in items)
        totals.append((case("Tổng số lượng hàng"), quantity(total_qty, money_style, 3)))

    footer_lines = corpus.footers(profile, params["lang"])
    lo, hi = content.get("num_footers", [1, 3])
    count = rng.randint(int(lo), int(hi))
    footer = [case(line) for line in rng.sample(footer_lines, min(count, len(footer_lines)))]

    title = case(rng.choice(document.get("titles") or TITLES[profile]))
    invoice = (
        _build_invoice(profile, store, items, rng, case, cash, params, grand, stay)
        if is_invoice
        else None
    )

    return Receipt(
        profile=profile,
        title=title,
        store=store,
        meta=meta,
        items=items,
        totals=totals,
        footer=footer,
        money_style=money_style,
        money_prefix=money_prefix,
        money_suffix=money_suffix,
        upper=upper,
        folded=folded,
        grand_index=grand_index,
        numbers=numbers,
        invoice=invoice,
    )


__all__ = ["Invoice", "Item", "Party", "Receipt", "Store", "build"]
