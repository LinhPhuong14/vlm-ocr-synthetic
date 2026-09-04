#!/usr/bin/env python3
"""Draw the measured boxes back onto the page, one mark per axis.

    generators/html/.venv/bin/python samples/label-axes/measure.py
    generators/html/.venv/bin/python samples/label-axes/proof.py

Same idea as `tools/proof_boxes.py` -- a proof sheet is how you find out
whether a label describes the ink under it -- but drawn for three axes at once,
because the claim being checked is that the three are independent:

    region  the OUTLINE colour, and the legend along the top
    role    the TAG written on the box, on a chip in the region's colour
    ink     the outline STYLE: solid for print, and a distinct dash, dot or
            double rule for each of the other five

If the three axes really are orthogonal, a reader can name all three for any
box on this sheet without looking anything up. That is the whole test, and it
is a test only a picture can run.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent

# BGR, because OpenCV. Thirteen regions need thirteen colours that stay apart
# on white paper and on printed text, so these are picked for hue separation
# rather than for looking like a palette.
REGION: dict[str, tuple[int, int, int]] = {
    "Letterhead":   (190,  60, 180),
    "DocTitle":     ( 30,  30, 210),
    "FieldGroup":   (200, 120,  40),
    "ItemTable":    ( 60, 170,  60),
    "Summary":      ( 40,  90, 220),
    "Prose":        (120,  90, 200),
    "ListGroup":    ( 20, 160, 200),
    "Signature":    ( 30, 190, 220),
    "Mark":         ( 40,  40, 140),
    "RunningHead":  (150, 150, 150),
    "RunningFoot":  (150, 150, 150),
    "Caption":      (170, 110,  70),
    "Note":         (110, 110, 110),
}
OTHER = (80, 80, 80)

# How the outline is drawn. The ink axis is a PROPERTY of the stroke rather
# than a second colour on purpose: colour is spent on region, and an axis drawn
# in the same visual language as another axis is an axis a reader will conflate.
INK_STYLE = {
    "print":     "solid",
    "hand":      "dash",
    "stamp":     "double",
    "dotmatrix": "dot",
    "thermal":   "thin",
    "reversed":  "thick",
}


def _stroke(img, x, y, w, h, colour, style: str) -> None:
    """One box outline, drawn in the style its `ink` calls for."""
    p1, p2 = (int(x), int(y)), (int(x + w), int(y + h))
    if style == "solid":
        cv2.rectangle(img, p1, p2, colour, 2)
    elif style == "thin":
        cv2.rectangle(img, p1, p2, colour, 1)
    elif style == "thick":
        cv2.rectangle(img, p1, p2, colour, 4)
    elif style == "double":
        cv2.rectangle(img, p1, p2, colour, 2)
        cv2.rectangle(img, (p1[0] - 4, p1[1] - 4), (p2[0] + 4, p2[1] + 4), colour, 1)
    else:
        # dash and dot: walk the perimeter and paint only some of it. OpenCV has
        # no dashed rectangle, and drawing four dashed lines by hand is fewer
        # moving parts than a LineIterator over a polygon.
        on, off = (9, 6) if style == "dash" else (2, 5)
        step = on + off
        for a, b in (((p1[0], p1[1]), (p2[0], p1[1])),
                     ((p1[0], p2[1]), (p2[0], p2[1]))):
            for xx in range(a[0], b[0], step):
                cv2.line(img, (xx, a[1]), (min(xx + on, b[0]), a[1]), colour, 2)
        for a, b in (((p1[0], p1[1]), (p1[0], p2[1])),
                     ((p2[0], p1[1]), (p2[0], p2[1]))):
            for yy in range(a[1], b[1], step):
                cv2.line(img, (a[0], yy), (a[0], min(yy + on, b[1])), colour, 2)


def _tag(img, text: str, x: int, y: int, colour, scale: float = 0.34) -> None:
    """The box's `role`, on a filled chip in its region's colour.

    On the page rather than beside it, because a tag in a margin is a tag the
    reader has to match back to a box by eye; and on a chip rather than bare,
    because half of these land on printed text or a table rule.
    """
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    top = max(0, y - h - 5)
    cv2.rectangle(img, (x, top), (x + w + 5, top + h + 5), colour, -1)
    cv2.putText(img, text, (x + 3, top + h + 2), cv2.FONT_HERSHEY_SIMPLEX,
                scale, (255, 255, 255), 1, cv2.LINE_AA)


def _legend(width: int, seen_regions, seen_inks) -> np.ndarray:
    """Two strips: the region colours, and what each ink style looks like."""
    rows, pad = 2, 10
    strip = np.full((30 * rows + pad, width, 3), 250, np.uint8)

    x = 12
    cv2.putText(strip, "region", (x, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (60, 60, 60), 1, cv2.LINE_AA)
    x += 62
    for name in seen_regions:
        colour = REGION.get(name, OTHER)
        cv2.rectangle(strip, (x, 9), (x + 15, 22), colour, -1)
        cv2.putText(strip, name, (x + 20, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (40, 40, 40), 1, cv2.LINE_AA)
        x += 20 + 8 * len(name) + 18

    x, y = 12, 30
    cv2.putText(strip, "ink", (x, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (60, 60, 60), 1, cv2.LINE_AA)
    x += 62
    for name in seen_inks:
        _stroke(strip, x, y + 8, 30, 14, (70, 70, 70), INK_STYLE.get(name, "solid"))
        cv2.putText(strip, name, (x + 36, y + 21), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (40, 40, 40), 1, cv2.LINE_AA)
        x += 36 + 8 * len(name) + 22
    return strip


def draw(page: Path, boxes: Path, out: Path) -> None:
    image = cv2.imread(str(page))
    if image is None:
        raise SystemExit(f"không đọc được {page}")
    rects = json.loads(boxes.read_text(encoding="utf-8"))

    # The screenshot is taken at device_scale_factor=2, so it is twice the size
    # the boxes were measured in. Scaling here rather than re-measuring keeps
    # the boxes the ones the renderer would record.
    scale = image.shape[1] / max(
        max(b["x"] + b["w"] for b in rects), 1)
    scale = round(scale)

    overlay = image.copy()
    for box in rects:
        colour = REGION.get(box["region"], OTHER)
        _stroke(overlay, box["x"] * scale, box["y"] * scale,
                box["w"] * scale, box["h"] * scale, colour,
                INK_STYLE.get(box["ink"], "solid"))
    # Half-transparent, so the ink underneath stays readable -- the point of a
    # proof sheet is reading the label against the pixels, not instead of them.
    image = cv2.addWeighted(overlay, 0.72, image, 0.28, 0)

    for box in rects:
        colour = REGION.get(box["region"], OTHER)
        _tag(image, box["role"], int(box["x"] * scale), int(box["y"] * scale), colour)

    order = [r for r in REGION if any(b["region"] == r for b in rects)]
    inks = [i for i in INK_STYLE if any(b["ink"] == i for b in rects)]
    out_image = np.vstack([_legend(image.shape[1], order, inks), image])
    cv2.imwrite(str(out), out_image)
    print(f"{len(rects)} hộp · {len(order)} region · {len(inks)} ink -> {out}")


if __name__ == "__main__":
    draw(HERE / "page.png", HERE / "boxes.json", HERE / "proof.png")
