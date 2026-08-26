"""docs/figures/handwriting-html.jpg — one page per ink source, boxes drawn.

Built from `samples/handwriting/`, which is committed, rather than from
`data/hand12/`: that set is drawn with the `font` source now, so every field on
it is inked and it can no longer show the model's coverage limit, which is the
whole point of the figure.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples" / "handwriting"
INK, PRINT = (60, 60, 220), (150, 150, 150)   # BGR: red, grey
KINDS = ("invoice.field", "invoice.words", "sign.name")


def panel(stem, y0, y1, caption, width=1180):
    rec = json.loads((SAMPLES / f"{stem}.json").read_text(encoding="utf-8"))
    img = cv2.imread(str(SAMPLES / f"{stem}.jpg"))
    inked = {i["text"] for i in rec["handwriting"]["inked"]}
    over = img.copy()
    for box in rec["boxes"]:
        if box["kind"] not in KINDS:
            continue
        q = np.array(box["quad"], dtype=np.int32)
        hand = box["text"] in inked
        cv2.rectangle(over, tuple(q[0]), tuple(q[2]), INK if hand else PRINT,
                      2 if hand else 1)
    crop = over[y0:y1]
    scale = width / crop.shape[1]
    crop = cv2.resize(crop, (width, max(int(crop.shape[0] * scale), 1)),
                      interpolation=cv2.INTER_AREA)
    bar = np.full((34, width, 3), 255, np.uint8)
    cv2.putText(bar, caption, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (25, 25, 25),
                1, cv2.LINE_AA)
    return np.vstack([bar, crop])


top = panel("hand-filled-form", 312, 500,
            "font: 9 of 9 filled - red = ink, grey = printed")
mid = panel("hand-filled-folio", 370, 600,
            "model: 5 of 12 - the seven in grey are all digits it cannot write")
low = panel("hand-filled-folio", 1020, 1240,
            "     ... and the two names under the signature captions")
gap = np.full((14, top.shape[1], 3), 255, np.uint8)
out = np.vstack([top, gap, mid, gap, low])
cv2.imwrite(str(ROOT / "docs" / "figures" / "handwriting-html.jpg"), out,
            [cv2.IMWRITE_JPEG_QUALITY, 92])
print(out.shape)
