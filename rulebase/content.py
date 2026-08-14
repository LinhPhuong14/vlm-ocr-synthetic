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
from typing import Any

from . import corpus
from .text import apply_case, money, quantity

# What the title line says, by document kind. Taken from the sample photos.
TITLES = {
    "quan": ["PHIẾU THANH TOÁN", "HOÁ ĐƠN THANH TOÁN", "PHIẾU TÍNH TIỀN", "HOÁ ĐƠN"],
    "sieuthi": ["HOÁ ĐƠN BÁN HÀNG", "PHIẾU TÍNH TIỀN", "HOÁ ĐƠN GTGT", "PHIẾU THANH TOÁN"],
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

    @property
    def weighed(self) -> bool:
        return self.unit == "KG"

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
    name: str
    branch: str = ""
    address: str = ""
    address2: str = ""
    phone: str = ""
    website: str = ""


@dataclass
class Receipt:
    profile: str                       # 'quan' | 'sieuthi'
    title: str
    store: Store
    meta: list[tuple[str, str]]
    items: list[Item]
    totals: list[tuple[str, str]]      # (label, formatted amount), in print order
    footer: list[str]
    money_style: str
    upper: bool
    folded: bool
    # Which entry of `totals` is the amount actually owed. Not the last one:
    # the cash tendered and the change come after it.
    grand_index: int = 0
    numbers: dict[str, Any] = field(default_factory=dict)

    def ground_truth(self) -> dict[str, Any]:
        """CORD-style nested label, built from the same objects as the render."""
        store: dict[str, str] = {"name": self.store.name}
        for key in ("branch", "address", "address2", "phone", "website"):
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
                "price": money(item.amount, self.money_style),
            }
            if item.weighed:
                entry["weight"] = f"{quantity(item.qty, 'dot', 3)} {item.unit}"
                entry["unitprice_per_unit"] = money(item.unit_price, self.money_style)
            if item.display_unit_price():
                entry["unitprice"] = money(item.display_unit_price(), self.money_style)
            if item.barcode:
                entry["barcode"] = item.barcode
            if item.discount:
                entry["discountprice"] = money(-abs(item.discount), self.money_style)
            if item.vat_rate:
                entry["vatrate"] = f"{item.vat_rate}%"
            menu.append(entry)
        return {
            "doc_type": f"receipt_{self.profile}",
            "title": self.title,
            "store": store,
            "menu": menu,
            "total": {label: value for label, value in self.totals},
            "footer": list(self.footer),
        }

    def text_sequence(self) -> str:
        """Flat reading order, for text-only pre-training and for OCR scoring."""
        parts = [self.store.name]
        for value in (self.store.branch, self.store.address, self.store.address2,
                      self.store.phone, self.store.website, self.title):
            if value:
                parts.append(value)
        for label, value in self.meta:
            parts.append(f"{label} {value}".strip())
        for item in self.items:
            parts.append(item.name)
            parts.append(money(item.amount, self.money_style))
        for label, value in self.totals:
            parts.append(f"{label} {value}".strip())
        parts.extend(self.footer)
        return " ".join(part for part in parts if part)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["store"] = asdict(self.store)
        data["items"] = [asdict(item) for item in self.items]
        return data


def _round_to(value: float, step: int) -> int:
    return int(round(value / step)) * step


def _barcode(rng: random.Random) -> str:
    """13 digits, the way EAN-13 looks on a Vietnamese product."""
    return "".join(str(rng.randrange(10)) for _ in range(13))


def _build_store(profile: str, rng: random.Random, case) -> Store:
    if profile == "sieuthi":
        brand, branch = rng.choice(corpus.shops("sieuthi"))
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

    name = f"{rng.choice(SHOP_PREFIXES)} {rng.choice(corpus.shops('quan'))[0]}"
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
    catalogue = corpus.items(profile)
    prob_discount = float(params.get("prob_item_discount", 0.0))
    prob_weighed = float(params.get("prob_weighed", 0.0))
    vat_rates = params.get("vat_rates") or []

    items: list[Item] = []
    for index in range(count):
        name, price_lo, price_hi = rng.choice(catalogue)
        unit_price = _round_to(rng.uniform(price_lo, price_hi), 500 if profile == "sieuthi" else 1000)
        weighed = rng.random() < prob_weighed
        if weighed:
            qty: float = round(rng.uniform(0.1, 2.0), 3)
            amount = _round_to(unit_price * qty, 5)
            unit = "KG"
        else:
            qty = rng.randrange(1, 13) if rng.random() < 0.2 else rng.randrange(1, 4)
            amount = int(unit_price * qty)
            unit = rng.choice(UNITS[2:]) if profile == "sieuthi" and rng.random() < 0.3 else ""
        item = Item(
            stt=index + 1,
            name=case(name),
            qty=qty,
            unit_price=unit_price,
            amount=amount,
            unit=unit,
        )
        if profile == "sieuthi":
            item.barcode = _barcode(rng)
            # A supermarket till prints the barcode and the money on one line
            # and the product name, indented, on the next. Weighed goods add
            # the per-kilo price and the weight to that second line.
            item.note = (
                case(f"{name} {money(unit_price, 'dot')}/KG {quantity(qty, 'dot', 3)} KG")
                if weighed
                else item.name
            )
            if vat_rates:
                item.vat_rate = int(rng.choice(vat_rates))
            if rng.random() < 0.2:
                item.original_price = _round_to(unit_price * rng.uniform(1.05, 1.4), 500)
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

    if profile == "sieuthi":
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


def build(recipe, rng: random.Random | None = None) -> Receipt:
    """Fill in one receipt for `recipe`."""
    rng = rng or random.Random(recipe.seed)
    document = recipe.choices["document"].params
    content = recipe.choices["content"].params

    profile = document.get("profile", "quan")
    money_style = content.get("money_style", "dot")
    folded = rng.random() < float(content.get("prob_ascii_fold", 0.0))
    upper = rng.random() < float(content.get("prob_uppercase", 0.5))

    def case(text: str) -> str:
        return apply_case(text, upper=upper, fold=folded)

    def cash(value: float) -> str:
        return money(value, money_style, content.get("money_suffix", ""))

    store = _build_store(profile, rng, case)
    items = _build_items(profile, rng, case, {**document, **content})
    meta = _build_meta(profile, rng, case, {**document, **content})

    subtotal = sum(item.amount for item in items)
    item_discount = sum(item.discount for item in items)
    grand = subtotal - item_discount

    totals: list[tuple[str, str]] = []
    numbers: dict[str, Any] = {"subtotal": subtotal, "discount": item_discount}

    labels = document.get("total_labels") or {}
    if content.get("show_subtotal", True):
        totals.append((case(labels.get("subtotal", "Tiền hàng")), cash(subtotal)))
    if item_discount:
        totals.append((case(labels.get("discount", "Tổng tiền giảm")), cash(-item_discount)))

    vat_rate = 0
    if content.get("show_vat") and rng.random() < 0.8:
        vat_rate = int(rng.choice(document.get("vat_rates") or [8, 10]))
        vat = _round_to(grand * vat_rate / 100.0, 1)
        totals.append((case(f"{labels.get('vat', 'Thuế GTGT')} {vat_rate}%"), cash(vat)))
        grand += vat
        numbers["vat_rate"] = vat_rate
        numbers["vat"] = vat

    grand_index = len(totals)
    totals.append((case(labels.get("grand", "Thanh toán")), cash(grand)))
    numbers["grand"] = grand

    if content.get("show_payment", True):
        label, group = rng.choice(corpus.payments())
        paid = grand if group != "tienmat" else _round_to(grand + rng.uniform(0, 60000), 10000)
        paid = max(paid, grand)
        totals.append((case(label), cash(paid)))
        totals.append((case(labels.get("change", "Tiền trả lại")), cash(paid - grand)))
        numbers["paid"] = paid
        numbers["change"] = paid - grand

    if content.get("show_item_count"):
        total_qty = sum(item.qty for item in items)
        totals.append((case("Tổng số lượng hàng"), quantity(total_qty, money_style, 3)))

    footer_lines = corpus.footers(profile)
    lo, hi = content.get("num_footers", [1, 3])
    count = rng.randint(int(lo), int(hi))
    footer = [case(line) for line in rng.sample(footer_lines, min(count, len(footer_lines)))]

    title = case(rng.choice(document.get("titles") or TITLES[profile]))

    return Receipt(
        profile=profile,
        title=title,
        store=store,
        meta=meta,
        items=items,
        totals=totals,
        footer=footer,
        money_style=money_style,
        upper=upper,
        folded=folded,
        grand_index=grand_index,
        numbers=numbers,
    )


__all__ = ["Item", "Receipt", "Store", "build"]
