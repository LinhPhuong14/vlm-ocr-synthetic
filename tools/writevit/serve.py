"""A long-lived WriteViT worker, one JSON request per line on stdin.

    ../WriteViT/.venv/bin/python tools/writevit/serve.py

`infer.py` is the one-shot entry point and costs **11 s per invocation on CPU**
-- almost all of it loading the 97 MB checkpoint and the 193 MB `VN.pickle`.
A page needs a handful of fields and a run needs many pages, so paying that per
field, or even per page, is the whole cost of the feature. This keeps the model
in memory and answers requests, exactly as `HtmlReceiptRenderer` keeps one
browser alive across a run rather than launching Chromium per page.

Protocol, one JSON object per line each way:

    -> {"words": ["Lê", "Thị", "Kiều", "Trinh"], "writer": 30, "seed": 7}
    <- {"writer": "0007", "words": [{"text": "Lê", "png": "<base64>"}, ...]}

    -> {"words": ["15/06/2018"]}
    <- {"error": "characters outside the alphabet: '/'"}

An error is an **answer**, not an exit: a worker that dies on the first
unwritable word takes the run with it, and unwritable words are the normal
case here -- see `docs/writevit.md`, and `generators/html/handwriting.py`,
which decides what to even ask for.

Ink comes back as a grayscale PNG at the model's native 32 px, one per word,
white paper and black ink. Compositing -- the gap between words, the pen
colour, the alpha -- belongs to the caller and is done in `handwriting.py`,
which knows what page the ink is going onto. This process only writes.

Everything the model prints while loading ("initialize network with N02") is
redirected to stderr. One stray line on stdout and every reply after it is
unparseable.
"""
import argparse
import base64
import contextlib
import io
import json
import sys

# infer.py does the chdir-into-the-clone dance at import time, and reads
# --writevit-dir and --lang off sys.argv to do it -- so this module accepts the
# same two flags, and importing it is what puts the clone on sys.path.
import infer  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from params import ALPHABET, DATASET_PATHS, DEVICE  # noqa: E402
from PIL import Image  # noqa: E402


class Writer:
    """The checkpoint, plus one cached style tensor per writer index.

    The style is one reference image drawn from a writer's samples in
    `VN.pickle`; caching it matters because the pickle is 193 MB and re-reading
    it per request would put the per-call cost straight back.
    """

    def __init__(self, checkpoint: str, dataset: str):
        # WriteViT() prints as it builds, and stdout is the protocol.
        with contextlib.redirect_stdout(sys.stderr):
            from models.model import WriteViT

            self.model = WriteViT().to(DEVICE)
            self.model.load_state_dict(
                torch.load(checkpoint, map_location=DEVICE, weights_only=True))
            self.model.eval()
        self.dataset = dataset
        self._samples: dict | None = None
        self._styles: dict[int, tuple] = {}

    def style(self, writer: int, seed: int):
        if writer not in self._styles:
            if self._samples is None:
                import pickle

                with open(self.dataset, "rb") as handle:
                    self._samples = pickle.load(handle)["train"]
                self._samples.pop("None", None)
            ids = list(self._samples)
            writer_id = ids[writer % len(ids)]
            samples = self._samples[writer_id]
            pick = int(np.random.default_rng(seed).integers(len(samples)))
            tensor = infer.prep_style(samples[pick]["img"]).to(DEVICE)
            self._styles[writer] = (tensor, writer_id)
        return self._styles[writer]

    def write(self, words: list[str], writer: int, seed: int):
        """One grayscale PNG per word, at the model's native height."""
        from params import resolution

        style, writer_id = self.style(writer, seed)
        torch.manual_seed(seed)
        encoded, lengths = self.model.netconverter.encode([w.encode() for w in words])
        encoded = encoded.to(DEVICE).unsqueeze(0)
        with torch.no_grad():
            features = self.model.netW(style, None, training=False)
            fakes = self.model.netG.Eval(features, encoded)

        out = []
        for index, word in enumerate(words):
            # `lengths` is in characters and the generator emits `resolution`
            # columns per character, so this is where the padding is cut off --
            # the same slice infer.py takes.
            width = int(lengths[index]) * resolution
            tile = np.clip((fakes[index][0, 0, :, :width].cpu().numpy() + 1) / 2, 0, 1)
            buffer = io.BytesIO()
            Image.fromarray((255 * tile).astype("uint8"), mode="L").save(
                buffer, format="PNG", optimize=True)
            out.append({
                "text": word,
                "png": base64.b64encode(buffer.getvalue()).decode("ascii"),
            })
        return out, writer_id


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", default="vn", choices=["vn", "eng"])
    parser.add_argument("--writevit-dir", default=None, help="the clone")
    parser.add_argument("--ckpt", default=None, help="default: File/<lang>_ckpt.pth")
    args = parser.parse_args()

    checkpoint = args.ckpt or f"File/{'vn' if args.lang == 'vn' else 'eng'}_ckpt.pth"
    writer = Writer(checkpoint, DATASET_PATHS)
    # The readiness line: the client blocks on it rather than guessing how long
    # a cold load takes, which on a busy machine is anything from 8 s to 30 s.
    # The alphabet rides along so the caller can check its own copy of the
    # policy against the checkpoint's rather than trusting a transcription.
    print(json.dumps({"ready": True, "device": str(DEVICE), "alphabet": ALPHABET}),
          flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except ValueError as error:
            print(json.dumps({"error": f"bad request: {error}"}), flush=True)
            continue
        if request.get("stop"):
            break
        words = [w for w in request.get("words", []) if w]
        if not words:
            print(json.dumps({"error": "no words"}), flush=True)
            continue
        missing = infer.missing_characters(words)
        if missing:
            print(json.dumps({
                "error": "characters outside the alphabet: "
                         + " ".join(repr(c) for c in missing)}), flush=True)
            continue
        try:
            tiles, writer_id = writer.write(
                words, int(request.get("writer", 0)), int(request.get("seed", 0)))
        except Exception as error:  # noqa: BLE001 -- reported, not fatal
            print(json.dumps({"error": f"{type(error).__name__}: {error}"}), flush=True)
            continue
        print(json.dumps({"writer": writer_id, "words": tiles}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
