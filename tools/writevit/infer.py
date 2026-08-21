"""Generate handwritten Vietnamese words with a WriteViT checkpoint.

WriteViT ships training code only; this is the missing inference entry point.
It loads a checkpoint, takes a writer's style from one reference image, and
writes one PNG per word plus a composed line, ready to be composited into a
form field.

    python tools/writevit/infer.py --text "Hoá đơn giá trị gia tăng" --out out/

Run tools/writevit/setup.py first. The clone is expected beside this
repository; pass --writevit-dir to point elsewhere.

The Vietnamese checkpoint writes letters and diacritics well and **cannot
write digits or all-caps words** -- see docs/writevit.md for the measurement.
"""
import argparse
import os
import sys

# params.py branches on the dataset at import time, and models/Unifront.py
# opens ./File/unifont.pickle by relative path, so the clone has to be on
# sys.path and be the working directory before anything is imported.
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--lang", default="vn", choices=["vn", "eng"])
_pre.add_argument("--writevit-dir", default=None)
_args, _ = _pre.parse_known_args()
_here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WRITEVIT_DIR = os.path.abspath(
    _args.writevit_dir or os.path.join(os.path.dirname(_here), "WriteViT")
)
if not os.path.isdir(WRITEVIT_DIR):
    sys.exit(f"WriteViT not found at {WRITEVIT_DIR}. Run tools/writevit/setup.py.")
os.environ["WRITEVIT_DATASET"] = {"vn": "VNDB", "eng": "IAM"}[_args.lang]
CALLER_CWD = os.getcwd()  # captured before the chdir, so --out stays the caller's
sys.path.insert(0, WRITEVIT_DIR)
os.chdir(WRITEVIT_DIR)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from data.dataset import get_transform  # noqa: E402
from models.model import WriteViT  # noqa: E402
from params import (  # noqa: E402
    ALPHABET,
    DATASET_PATHS,
    DEVICE,
    IMG_HEIGHT,
    resolution,
)
from PIL import Image  # noqa: E402

# models/model.py feeds netW `input["img"]` -- ONE reference image of shape
# [B, 1, H, W], not the 15 `simg` examples, which are inherited from
# Handwriting Transformers and left unused. The framework is one-shot.


def check_alphabet(words):
    """Fail early and legibly on characters the checkpoint never learned."""
    missing = sorted({c for w in words for c in w if c not in ALPHABET})
    if missing:
        sys.exit(
            "These characters are not in the model's alphabet: "
            + " ".join(repr(c) for c in missing)
            + "\nThe Vietnamese checkpoint covers letters, digits and '!' only "
            "-- no comma, full stop, slash or hyphen. Split the text around "
            "them and draw the separators yourself, or retrain with a wider "
            "ALPHABET."
        )


def prep_style(image):
    """One reference image -> [1, 1, IMG_HEIGHT, W], as data/dataset.py builds it."""
    image = image.convert("L")
    if image.height != IMG_HEIGHT:
        width = max(1, round(image.width * IMG_HEIGHT / image.height))
        image = image.resize((width, IMG_HEIGHT), Image.BICUBIC)
    return get_transform(grayscale=True)(image).unsqueeze(0)


def style_from_dataset(path, writer, rng):
    import pickle

    with open(path, "rb") as handle:
        data = pickle.load(handle)["train"]
    data.pop("None", None)
    ids = list(data.keys())
    writer_id = ids[writer % len(ids)]
    samples = data[writer_id]
    pick = int(rng.integers(len(samples)))
    return samples[pick], writer_id, len(ids), len(samples)


def style_from_dir(path, index):
    names = sorted(
        n
        for n in os.listdir(path)
        if n.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"))
    )
    if not names:
        sys.exit(f"No images found in {path}")
    name = names[index % len(names)]
    return Image.open(os.path.join(path, name)), name, len(names)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--lang", default="vn", choices=["vn", "eng"])
    parser.add_argument("--writevit-dir", default=None, help="the clone")
    parser.add_argument("--text", required=True, help="words separated by spaces")
    parser.add_argument("--ckpt", default=None, help="default: File/<lang>_ckpt.pth")
    parser.add_argument("--writer", type=int, default=0, help="writer index")
    parser.add_argument("--style-dir", default=None, help="own reference images")
    parser.add_argument("--out", default="out", help="output directory")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--gap", type=int, default=16, help="px between words")
    parser.add_argument(
        "--scale", type=float, default=1.0, help="upscale the output image"
    )
    args = parser.parse_args()
    args.out = os.path.abspath(os.path.join(CALLER_CWD, args.out))
    if args.style_dir:
        args.style_dir = os.path.abspath(os.path.join(CALLER_CWD, args.style_dir))

    words = args.text.split()
    if not words:
        sys.exit("--text is empty")
    check_alphabet(words)

    ckpt = args.ckpt or f"File/{'vn' if args.lang == 'vn' else 'eng'}_ckpt.pth"
    if not os.path.isfile(ckpt):
        sys.exit(f"Checkpoint not found: {ckpt}")

    rng = np.random.default_rng(args.seed)
    torch.manual_seed(args.seed)

    if args.style_dir:
        image, name, total = style_from_dir(args.style_dir, args.writer)
        source = f"{args.style_dir}/{name} (1 of {total})"
    else:
        if not os.path.isfile(DATASET_PATHS):
            sys.exit(
                f"Style source not found: {DATASET_PATHS}. Download it, or pass "
                "--style-dir with your own reference image."
            )
        sample, writer_id, total, n = style_from_dataset(DATASET_PATHS, args.writer, rng)
        image = sample["img"]
        source = (
            f"writer {writer_id} ({args.writer % total} of {total}), "
            f"sample {sample['label']!r} of {n}"
        )
    print(f"style: {source}")

    model = WriteViT().to(DEVICE)
    model.load_state_dict(torch.load(ckpt, map_location=DEVICE, weights_only=True))
    model.eval()
    print(f"loaded {ckpt} on {DEVICE}")

    style = prep_style(image).to(DEVICE)
    encoded, lengths = model.netconverter.encode([w.encode() for w in words])
    encoded = encoded.to(DEVICE).unsqueeze(0)

    with torch.no_grad():
        features = model.netW(style, None, training=False)
        fakes = model.netG.Eval(features, encoded)

    os.makedirs(args.out, exist_ok=True)
    tiles = []
    for index, word in enumerate(words):
        width = int(lengths[index]) * resolution
        tile = (fakes[index][0, 0, :, :width].cpu().numpy() + 1) / 2
        tiles.append(np.clip(tile, 0, 1))
        save(tiles[-1], os.path.join(args.out, f"{index:02d}_{safe(word)}.png"), args)

    gap = np.ones([IMG_HEIGHT, args.gap])
    line = np.concatenate(
        [t for tile in tiles for t in (tile, gap)][:-1], axis=1
    )
    line_path = os.path.join(args.out, "line.png")
    save(line, line_path, args)
    print(f"{len(words)} words -> {args.out}/  ({line_path}: {line.shape[1]}x{line.shape[0]} px)")


def safe(word):
    return "".join(c if c.isalnum() else "_" for c in word)[:40] or "word"


def save(array, path, args):
    image = Image.fromarray((255 * array).astype("uint8"), mode="L")
    if args.scale != 1.0:
        image = image.resize(
            (round(image.width * args.scale), round(image.height * args.scale)),
            Image.LANCZOS,
        )
    image.save(path)


if __name__ == "__main__":
    main()
