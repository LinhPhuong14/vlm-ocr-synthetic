"""
Donut / SynthDoG-VN
MIT License

Vẽ lưới ô của rule-base thành các `TextLayer` của synthtiger.

File này KHÔNG còn tự sinh nội dung nữa. Nội dung, bố cục, chính tả tiếng Việt
đều do `rulebase` quyết định; ở đây chỉ còn phần "đặt chữ nào ở đâu, cỡ bao
nhiêu, màu gì" — nghĩa là đúng phần mà renderer glyph phải tự làm và hai
renderer HTML làm theo cách khác.

Vẫn giữ hai điểm khác SynthDoG gốc:
  * mỗi ô vẽ bằng MỘT `TextLayer` cho cả chuỗi, không phải một layer cho từng
    ký tự — hoá đơn dày chữ nên vẽ theo ký tự (~2.7 ms/ký tự) là không dùng được;
  * toạ độ ô tính theo lưới ký tự, nên map lại được sang polygon cho từng trường.
"""
import random
import sys
from pathlib import Path

from synthtiger import layers

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import rulebase  # noqa: E402

SHARED_FONTS = REPO_ROOT / "fonts"


class Receipt:
    """rule-base -> danh sách TextLayer + nhãn."""

    def __init__(self, config=None):
        config = config or {}
        self.font_root = Path(config.get("font_root", SHARED_FONTS))
        self.local_font_root = Path(config.get("local_font_root", "resources/font"))
        self.margin_scale = config.get("margin_scale", [1.0, 1.0])
        self._font_cache: dict[str, list[str]] = {}

    # ---------- font ----------

    def _fonts(self, group):
        """Font trong `resources/font/<group>` được ưu tiên hơn font chung."""
        if group in self._font_cache:
            return self._font_cache[group]
        found = []
        for root in (self.local_font_root / group, self.font_root / group):
            if root.is_dir():
                found.extend(
                    str(path) for path in sorted(root.iterdir())
                    if path.suffix.lower() in (".ttf", ".otf")
                )
            if found:
                break
        if not found:
            raise RuntimeError(
                f"Không tìm thấy font nào cho nhóm {group!r} trong "
                f"{self.local_font_root / group} hay {self.font_root / group}"
            )
        self._font_cache[group] = found
        return found

    # ---------- sinh ----------

    def generate(self, seed=None, force=None):
        recipe, receipt, grid = rulebase.make(seed=seed, force=force)
        rng = random.Random(recipe.seed)
        visual = recipe.visual.params

        fonts = self._fonts(visual.get("font_dir", "mono"))
        font_path = rng.choice(fonts)
        size = rng.randint(*visual.get("font_size", [20, 30]))
        spacing = rng.uniform(*visual.get("line_spacing", [1.05, 1.4]))
        bold_prob = float(visual.get("bold", 0.2))

        # Màu mực tính ở `rulebase.style` để cả ba renderer ra cùng một màu.
        palette = rulebase.inks(recipe, rng)
        ink = (*palette["ink"], 255)
        accent = (*palette["accent"], 255)

        base = {"path": font_path, "size": size}

        # font mono nên mọi ký tự bằng nhau -> đo một lần là đủ.
        # `TextLayer.height` là chiều cao DÒNG của font (không đổi theo nội
        # dung), nên đo bằng chữ số vẫn đúng cho chữ có dấu.
        probe = layers.TextLayer("0" * 10, **base, color=ink)
        char_w = probe.width / 10.0
        line_h = probe.height * spacing

        margin = rng.uniform(*visual.get("margin", [0.04, 0.10]))
        margin *= rng.uniform(*self.margin_scale)
        pad_x = grid.ncols * char_w * margin
        pad_y = line_h * rng.uniform(0.6, 1.8)
        width = int(grid.ncols * char_w + pad_x * 2)
        height = int(grid.nrows * line_h + pad_y * 2)

        # Dòng tên cửa hàng và dòng tiêu đề được in bằng màu nhấn nếu có.
        accent_roles = {"store.name", "title"}

        text_layers, fields = [], []
        for cell in grid.cells:
            bold = cell.bold or rng.random() < bold_prob
            color = accent if cell.role in accent_roles else ink
            layer = layers.TextLayer(cell.text, **base, bold=bold, color=color)
            if cell.scale != 1.0:
                layer.size = layer.size * cell.scale

            y = pad_y + cell.row * line_h
            x0 = pad_x + cell.col0 * char_w
            x1 = pad_x + cell.col1 * char_w
            span = max(x1 - x0, 1.0)
            # chữ phóng to (tên quán, dòng tổng tiền) không được tràn khỏi cột
            if layer.width > span:
                layer.size = layer.size * (span / layer.width)
            if cell.align == "left":
                layer.left = x0
            elif cell.align == "right":
                layer.right = x1
            else:
                layer.centerx = (x0 + x1) / 2
            layer.top = y

            text_layers.append(layer)
            fields.append({"text": cell.text, "kind": cell.role})

        return {
            "size": (width, height),
            "text_layers": text_layers,
            "fields": fields,
            "recipe": recipe,
            "receipt": receipt,
            "grid": grid,
        }

    # ---------- nhãn ----------

    @staticmethod
    def to_gt_parse(receipt):
        return receipt.ground_truth()

    @staticmethod
    def to_text_sequence(receipt):
        return receipt.text_sequence()


__all__ = ["Receipt", "SHARED_FONTS"]
