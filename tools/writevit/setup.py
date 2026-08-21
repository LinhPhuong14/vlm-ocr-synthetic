"""Clone WriteViT, patch it, fetch the Vietnamese checkpoint, build a venv.

WriteViT (Dang Hoai Nam et al., ESWA 2026, MIT) is the only released
handwriting-synthesis model that ships a Vietnamese checkpoint. It is not a
dependency of this repository -- nothing here imports it -- so it is cloned
beside the repository rather than vendored.

    python tools/writevit/setup.py [--dir ../WriteViT] [--no-download]

Idempotent: re-running skips a clone, a patch or a download that is already
done. See docs/writevit.md for what the patches are and why each is needed.
"""
import argparse
import os
import subprocess
import sys
import urllib.request

REPO = "https://github.com/hnam-1765/WriteViT.git"
HF = "https://huggingface.co/DAIR-Group/WriteViT/resolve/main/File"
ARTIFACTS = [("vn_ckpt.pth", 101210076), ("VN.pickle", 192989152)]
REQUIREMENTS = [
    "lmdb", "numpy", "opencv-python-headless", "Pillow", "scikit-learn",
    "scipy", "six", "timm", "tqdm", "xmltodict",
]

# (file, marker, old, new, why). `marker` appears only once the patch is in;
# it cannot be derived from `old` or `new`, since either can be a substring of
# the other -- dropping a call leaves the rest of the line, and adding an
# import leaves the line it was anchored to.
PATCHES = [
    (
        "params.py",
        "WRITEVIT_DATASET",
        "EXP_NAME = \"IAM-339W\"\nDATASET = 'IAM'\n",
        'DATASET = os.environ.get("WRITEVIT_DATASET", "IAM")\n'
        'EXP_NAME = {"IAM": "IAM-339W", "VNDB": "VN-106W", "CVL": "CVL-283W"}'
        ".get(DATASET, DATASET)\n",
        "pick the language without editing the file",
    ),
    (
        "params.py",
        "import os\n\nimport torch",
        "import torch\n",
        "import os\n\nimport torch\n",
        "params.py now reads os.environ",
    ),
    (
        "models/Unifront.py",
        "from params import DEVICE",
        "from PIL import Image\n",
        "from PIL import Image\n\nfrom params import DEVICE\n",
        "import the resolved device",
    ),
    (
        "models/Unifront.py",
        "device=DEVICE",
        "device='cuda'",
        "device=DEVICE",
        "hardcoded cuda: the font table is moved to the GPU unconditionally, "
        "so nothing runs on a CPU-only machine",
    ),
    (
        "models/Generator.py",
        "tgt = QRS[:, i, :]\n",
        "tgt = QRS[:, i, :].squeeze(1)",
        "tgt = QRS[:, i, :]",
        "QRS[:, i, :] is already [B, L]; the squeeze is a no-op unless L == 1, "
        "where it drops the length axis and Eval crashes on one-character words",
    ),
]


def run(command, **kwargs):
    print("  $", " ".join(command))
    subprocess.run(command, check=True, **kwargs)


def clone(target):
    if os.path.isdir(os.path.join(target, ".git")):
        print(f"clone: {target} exists, skipping")
        return
    run(["git", "clone", "--depth", "1", REPO, target])


def patch(target):
    for name, marker, old, new, why in PATCHES:
        path = os.path.join(target, name)
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        if marker in source:
            print(f"patch: {name} already patched -- {why[:44]}")
            continue
        if old not in source:
            sys.exit(f"patch: cannot find the anchor in {name}; upstream changed")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(source.replace(old, new, 1))
        print(f"patch: {name} -- {why}")


def download(target):
    for name, size in ARTIFACTS:
        path = os.path.join(target, "File", name)
        if os.path.isfile(path) and os.path.getsize(path) == size:
            print(f"fetch: {name} present, skipping")
            continue
        print(f"fetch: {name} ({size / 1e6:.0f} MB)")
        urllib.request.urlretrieve(f"{HF}/{name}", path)


def venv(target):
    python = os.path.join(target, ".venv", "bin", "python")
    if not os.path.isfile(python):
        run([sys.executable, "-m", "venv", os.path.join(target, ".venv")])
    run([python, "-m", "pip", "install", "-q", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-q", "torch", "torchvision",
         "--index-url", "https://download.pytorch.org/whl/cpu"])
    run([python, "-m", "pip", "install", "-q", *REQUIREMENTS])


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--dir", default=os.path.join(os.path.dirname(here), "WriteViT"))
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--no-venv", action="store_true")
    args = parser.parse_args()

    target = os.path.abspath(args.dir)
    print(f"WriteViT -> {target}")
    clone(target)
    patch(target)
    if not args.no_download:
        download(target)
    if not args.no_venv:
        venv(target)
    print(
        f"\nready. generate with:\n"
        f"  python tools/writevit/infer.py --writevit-dir {target} \\\n"
        f'      --text "Hoá đơn giá trị gia tăng" --out out/'
    )


if __name__ == "__main__":
    main()
