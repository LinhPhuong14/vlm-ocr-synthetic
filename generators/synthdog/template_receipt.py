"""
Donut / SynthDoG-VN
MIT License

Template synthtiger sinh ảnh hoá đơn Việt Nam theo rule-base.

    synthtiger -o ./outputs/VNReceipt -c 100 -w 4 -v \
        template_receipt.py SynthVNReceipt config_vi_receipt.yaml

Thứ tự dựng ảnh — cố ý theo đúng thứ tự vật lý:

    1. vẽ chữ lên tờ giấy trắng           (cấu trúc chuẩn)
    2. chạy chuỗi làm cũ của recipe        (giấy thật + mực mòn + vết bẩn)
    3. làm cong tờ giấy                    (toạ độ vẫn map lại được)
    4. đặt lên nền và chụp                 (bóng, tương phản, nhoè)

Layer giấy được áp ở BƯỚC 2 chứ không phải bước 1, nên texture giấy không bị
kéo giãn theo chữ, và cũng là chuỗi làm cũ y hệt hai renderer HTML dùng.
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import List

import numpy as np
from elements import Background
from elements.receipt import Receipt
from elements.warp import CurlWarp
from PIL import Image
from synthtiger import components, layers, templates

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import profiling  # noqa: E402
from degradation.pipeline import apply_recipe  # noqa: E402


class SynthVNReceipt(templates.Template):
    def __init__(self, config=None, split_ratio: List[float] = [0.8, 0.1, 0.1]):
        super().__init__(config)
        config = config or {}

        self.quality = config.get("quality", [50, 95])
        self.short_size = config.get("short_size", [720, 1024])
        self.canvas_fill = config.get("canvas_fill", [0.55, 0.95])
        self.canvas_aspect = config.get("canvas_aspect", [1.0, 1.9])
        self.label_format = config.get("label_format", "parse")
        self.seed_base = config.get("seed_base", 0)

        self.background = Background(config.get("background", {}))
        self.receipt = Receipt(config.get("receipt", {}))
        self.curl = CurlWarp(config.get("curl", {}))

        self.doc_effect = components.Iterator(
            [
                components.Switch(components.ElasticDistortion()),
                components.Switch(components.AdditiveGaussianNoise()),
                components.Switch(components.Perspective()),
            ],
            **config.get("doc_effect", {}),
        )
        self.effect = components.Iterator(
            [
                components.Switch(components.RGB()),
                components.Switch(components.Shadow()),
                components.Switch(components.Contrast()),
                components.Switch(components.Brightness()),
                components.Switch(components.MotionBlur()),
                components.Switch(components.GaussianBlur()),
            ],
            **config.get("effect", {}),
        )

        self.splits = ["train", "validation", "test"]
        self.split_indexes = np.random.choice(3, size=10000, p=split_ratio)
        self._counter = 0

    # ------------------------------------------------------------------

    def generate(self, force=None):
        # synthtiger không truyền chỉ số vào generate(), nên seed tự đếm ở đây;
        # `seed_base` cho phép chạy hai lần mà không ra trùng ảnh. `force` chỉ
        # dùng khi gọi trực tiếp từ `render.py` để ghim một bố cục.
        seed = self.seed_base + self._counter
        self._counter += 1

        out = self.receipt.generate(seed=seed, force=force)
        text_layers, fields = out["text_layers"], out["fields"]
        # Reversed: `Group` composites front to back -- index 0 is the topmost
        # layer, which is why the paper goes last -- while `Grid.marks` is in
        # painter's order, back to front, because that is what the two HTML
        # backends need. Without the flip the shading under a column header is
        # laid on top of the rules that bound it and rubs them out.
        mark_layers = list(reversed(out.get("mark_layers") or []))
        recipe, receipt = out["recipe"], out["receipt"]
        width, height = out["size"]

        # ----- 1. chữ trên tờ giấy trắng -----
        with profiling.stage("render"):
            sheet = layers.RectLayer((width, height), (255, 255, 255, 255))
            # Marks go between the text and the paper: a table rule is drawn by
            # the printer and the text sits in the cell it makes, so a line that
            # crossed a word would be wrong. The distortion is applied to all of
            # them together, or the rules would not follow the text when the
            # sheet warps.
            self.doc_effect.apply([*text_layers, *mark_layers, sheet])

            doc_group = layers.Group([*text_layers, *mark_layers, sheet])
            origin = doc_group.topleft
            quads = (np.array([layer.quad for layer in text_layers], dtype=np.float32)
                     - origin)
            doc_image = doc_group.output()

            rgb = doc_image[..., :3].astype(np.uint8)
            alpha = doc_image[..., 3:] if doc_image.shape[2] == 4 else None

        # ----- 2. chuỗi làm cũ của recipe (giấy thật nằm trong đây) -----
        # degradation làm việc trên BGR của OpenCV
        with profiling.stage("degradation"):
            aged = apply_recipe(rgb[..., ::-1], recipe, seed=seed)[..., ::-1]
        with profiling.stage("render"):
            doc_image = (
                np.concatenate([aged.astype(np.float32), alpha], axis=2)
                if alpha is not None
                else aged.astype(np.float32)
            )

        # ----- 3. cong giấy (ảnh được pad, quad đã cộng offset pad) -----
        # Biên độ lấy theo `visual.curl` của recipe: giấy nhiệt mỏng cong
        # nhiều, hoá đơn in laser trên giấy A5 gần như phẳng. Không nhân hệ số
        # này thì tờ nào cũng cong như nhau, mà cong quá thì cột tiền lệch hẳn
        # một dòng so với cột tên hàng.
        with profiling.stage("geometry"):
            curl_meta = self.curl.sample()
            strength = float(recipe.get("visual", "curl", 1.0))
            for key in ("shift", "squeeze", "wave"):
                curl_meta[key] *= strength
            doc_image, quads = self.curl.apply(doc_image, quads, meta=curl_meta)
            doc_layer = layers.Layer(doc_image)
            dw, dh = doc_layer.size

            # ----- 4. khung ảnh, nền, hiệu ứng chụp -----
            fill = np.random.uniform(*self.canvas_fill)
            aspect = np.random.uniform(*self.canvas_aspect)
            canvas_h = int(dh / fill)
            canvas_w = int(max(dw / fill, canvas_h / aspect))
            canvas = (canvas_w, canvas_h)

            bg_layer = self.background.generate(canvas)

            left = np.random.randint(max(canvas_w - int(dw), 0) + 1)
            top = np.random.randint(max(canvas_h - int(dh), 0) + 1)
            doc_layer.left, doc_layer.top = left, top
            quads = quads + (left, top)

            merged = layers.Group([doc_layer, bg_layer]).merge()
            self.effect.apply([merged])
            image = merged.output(bbox=[0, 0, *canvas])

            # thu nhỏ về kích thước mục tiêu (luôn là downscale -> chữ vẫn nét)
            short = np.random.randint(self.short_size[0], self.short_size[1] + 1)
            scale = short / min(canvas)
            if scale < 1.0:
                new_size = (max(int(canvas_w * scale), 1), max(int(canvas_h * scale), 1))
                image = np.array(
                    Image.fromarray(image[..., :3].astype(np.uint8)).resize(new_size, Image.LANCZOS),
                    dtype=np.float32,
                )
                quads = quads * scale
            else:
                image = image[..., :3]

            boxes = [
                {"kind": f["kind"], "text": f["text"], "quad": np.round(q, 1).tolist()}
                for f, q in zip(fields, quads)
                if f["kind"] != "sep"
            ]

        with profiling.stage("annotation"):
            return {
                "image": image,
                "gt_parse": receipt.ground_truth(),
                "text_sequence": re.sub(r"\s+", " ", receipt.text_sequence()).strip(),
                "boxes": boxes,
                "recipe": recipe.to_dict(),
                "quality": int(np.random.randint(self.quality[0], self.quality[1] + 1)),
            }

    # ------------------------------------------------------------------

    def init_save(self, root):
        os.makedirs(root, exist_ok=True)

    def save(self, root, data, idx):
        split_idx = self.split_indexes[idx % len(self.split_indexes)]
        output_dirpath = os.path.join(root, self.splits[split_idx])
        os.makedirs(output_dirpath, exist_ok=True)

        image_filename = f"image_{idx}.jpg"
        Image.fromarray(data["image"].astype(np.uint8)).save(
            os.path.join(output_dirpath, image_filename), quality=data["quality"]
        )

        if self.label_format == "text":
            gt_parse = {"text_sequence": data["text_sequence"]}
        else:
            gt_parse = data["gt_parse"]

        metadata = {
            "file_name": image_filename,
            "ground_truth": json.dumps({"gt_parse": gt_parse}, ensure_ascii=False),
            # Donut bỏ qua các khoá lạ trong ground_truth, nên box và recipe
            # để riêng ở đây
            "boxes": data["boxes"],
            "recipe": data["recipe"],
        }
        with open(os.path.join(output_dirpath, "metadata.jsonl"), "a", encoding="utf-8") as fp:
            json.dump(metadata, fp, ensure_ascii=False)
            fp.write("\n")

    def end_save(self, root):
        pass
