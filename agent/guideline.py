"""What to tell the LLM that takes over from the coverage objective.

    python tools/critic_review.py --dataset data/5k_llm --guideline agent/guideline

`agent/client.py` will talk to any OpenAI-compatible server, and the moment one
is configured the planner asks *it* what every page should be instead of asking
the coverage objective. That model arrives knowing nothing about this
repository: not that a birth certificate may not be redrawn, not that a till
roll cannot wear a 16 mm margin, not that `hand_font` is switched off on
purpose. Handing it the rules as a JSON schema and hoping is how you get 5000
pages of the same three documents with a QR code over the title.

So this writes it a briefing, and writes it **from the repository rather than
from memory**:

* the classes and the reasons come from `agent/policy.yaml`,
* the attributes and their values from the composed rules,
* the page architectures from `agent/redesign.py`,
* and the mistakes to avoid from `agent/critic.py`'s findings on a real run --
  with the measured rates, so the model is told what actually goes wrong here
  rather than what somebody guessed might.

Three files, because they are read at three different times. `SYSTEM_PROMPT.md`
goes in the system turn every request. `KNOWLEDGE.md` is the reference a person
reads once and a long-context model can be given whole. `CHECKLIST.md` is what
the model runs its own answer past before returning it.

Regenerated, never hand-edited: a guideline that drifts from the rules it
describes is worse than none, because it is believed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from agent import critic, policy as policy_module

DEFAULT_DIR = Path(__file__).resolve().parent / "guideline"

FILES = ("SYSTEM_PROMPT.md", "KNOWLEDGE.md", "CHECKLIST.md")


def _stamp(dataset: str) -> str:
    return (f"<!-- Sinh tự động bởi agent/guideline.py ngày {date.today()} "
            f"từ {dataset or 'rule-base'}. Đừng sửa tay: chạy lại "
            f"`tools/critic_review.py --guideline` sau mỗi lần đổi rules. -->")


def system_prompt(rules: dict, pol, review: critic.Review | None = None) -> str:
    """The system turn. Short on purpose -- it is paid for on every request."""
    order = list(rules.keys())
    locked = pol.documents("locked")
    livery = pol.documents("livery")
    worst = []
    if review is not None:
        worst = [row for row in review.rank() if row["lift"] >= critic.LIFT][:8]

    lines = [
        _stamp(review.dataset if review else ""),
        "",
        "# Vai trò",
        "",
        "Bạn là bộ chọn tham số cho một máy sinh ảnh chứng từ Việt Nam. Mỗi lần "
        "gọi, bạn quyết định **một trang giấy sẽ là gì**: loại giấy tờ nào, in "
        "trên phôi nào, khoác bộ áo nào, nội dung kiểu gì, mực gì, dấu gì, cũ "
        "cỡ nào. Bạn thay cho một bộ sinh số ngẫu nhiên, nên việc của bạn không "
        "phải là chọn cho *đẹp* mà là chọn cho **cả bộ dữ liệu đa dạng và có "
        "thật** — 5000 trang giống nhau thì mô hình OCR không học được gì, mà "
        "5000 trang vô lý thì học sai.",
        "",
        "# Cách trả lời",
        "",
        "Trả về **JSON thuần**, không giải thích, không rào đầu, đúng schema "
        "được đưa trong lượt người dùng. Mỗi phần tử là một trang, gồm đủ "
        f"{len(order)} khoá theo đúng thứ tự rút: `{'`, `'.join(order)}`.",
        "",
        "Mỗi giá trị phải là **một id có trong danh sách được đưa**. Bịa một id "
        "không có trong danh sách thì trang đó bị bộ luật từ chối và hệ thống "
        "tự rút lại — coi như lượt gọi của bạn bị bỏ.",
        "",
        "# Ba luật cứng",
        "",
        "1. **Giấy tờ do pháp luật quy định thì không dựng lại bố cục.** "
        f"{len(locked)} loại sau chỉ được thay mực, nền, dấu — không đổi hình: "
        f"`{'`, `'.join(locked)}`. "
        "Với chúng, `variant` phải là `none` hoặc một dressing hạng `locked`.",
        "2. **Giấy tờ theo nhận diện ngành thì đổi màu được, đổi hình thì "
        f"không.** {len(livery)} loại: `{'`, `'.join(livery)}`. "
        "`variant` tối đa hạng `livery`.",
        "3. **Còn lại thì dựng lại thoải mái**, càng khác phôi càng tốt — "
        "nhưng vẫn phải là một tờ giấy người ta in ra được.",
        "",
        "Bộ luật tự chặn cả ba điều trên bằng tag, nên bạn không phá được nó. "
        "Nói ở đây để bạn **đừng phí lượt** đề xuất những tổ hợp sẽ bị từ chối.",
        "",
        "# Cân bằng",
        "",
        "Lượt người dùng đưa kèm bảng đếm: mỗi thuộc tính, mỗi giá trị đã được "
        "vẽ bao nhiêu lần. **Ưu tiên giá trị đếm thấp.** Đó là toàn bộ lý do "
        "bạn thay cho random: random không nhớ, bạn thì nhớ.",
        "",
        "Đừng cân bằng đến mức máy móc. Một hoá đơn siêu thị in bằng máy in "
        "kim trên giấy nhiệt là thật; một giấy khai sinh in trên giấy nhiệt thì "
        "không. Khi bảng đếm và lẽ thường đánh nhau, **nghe lẽ thường**.",
    ]

    if worst:
        lines += [
            "",
            "# Những giá trị đã gây lỗi ở lượt trước",
            "",
            "Đo trên một lượt chạy thật bằng `agent/critic.py`. `lift` là tỉ lệ "
            "trang hỏng của giá trị đó chia cho tỉ lệ hỏng chung. Không cấm — "
            "vẫn chọn được — nhưng **chọn thưa ra**, và tránh dùng chung với "
            "nhau trên cùng một trang:",
            "",
        ]
        for row in worst:
            codes = ", ".join(row["codes"]) or "—"
            lines.append(f"- `{row['attribute']}={row['option']}` — hỏng "
                         f"{row['rate'] * 100:.0f}% ({row['lift']:.1f}× mức "
                         f"chung), lỗi hay gặp: {codes}")
    lines += [
        "",
        "# Trước khi trả lời",
        "",
        "Chạy qua `CHECKLIST.md`. Nếu một trang trong lô của bạn trượt một mục "
        "trong đó, sửa trang ấy rồi hãy trả về.",
        "",
    ]
    return "\n".join(lines)


def knowledge(rules: dict, pol, review: critic.Review | None = None) -> str:
    """The reference. Everything the model would otherwise have to guess."""
    from agent import redesign, variants

    counts = {name: len(options) for name, options in rules.items()}
    lines = [
        _stamp(review.dataset if review else ""),
        "",
        "# Máy này sinh ra cái gì",
        "",
        "Ảnh chứng từ Việt Nam có nhãn: hoá đơn GTGT, phiếu tính tiền quán ăn, "
        "hoá đơn điện nước, giấy khai sinh, giấy chứng nhận bảo hiểm, báo, tạp "
        "chí, sổ tay. Mỗi ảnh đi kèm một record JSON ghi từng ô chữ: `kind` "
        "(trường gì), `text` (chữ gì), `quad` (nằm ở đâu). Bộ dữ liệu này dùng "
        "để huấn luyện OCR và trích xuất trường, nên **cái nhãn phải đúng với "
        "cái ảnh** — đó là ràng buộc trên tất cả.",
        "",
        "## Một trang được quyết bằng gì",
        "",
        "| thuộc tính | số giá trị | nghĩa |",
        "|---|---:|---|",
        f"| `document` | {counts.get('document', 0)} | loại giấy tờ — quyết "
        "định nội dung, và quyết định luôn được phép dựng lại hay không |",
        f"| `layout` | {counts.get('layout', 0)} | phôi: khung HTML gốc của "
        "trang, thuộc một trong 10 họ giấy |",
        f"| `variant` | {counts.get('variant', 0)} | bộ áo: CSS chồng lên phôi. "
        "`none` là mặc phôi trần |",
        f"| `content` | {counts.get('content', 0)} | ngôn ngữ, dấu tiếng Việt, "
        "hoa/thường, đơn vị tiền |",
        f"| `visual` | {counts.get('visual', 0)} | loại máy in và loại giấy |",
        f"| `color` | {counts.get('color', 0)} | hệ màu mực |",
        f"| `ornament` | {counts.get('ornament', 0)} | dấu, QR, mã vạch, hoa "
        "văn nền, chữ ký |",
        f"| `augmentation` | {counts.get('augmentation', 0)} | tờ giấy đã đi "
        "qua những gì: photocopy, chụp lệch, ố, gấp |",
        "",
        "Rút theo đúng thứ tự trên. Giá trị rút trước gắn tag lên trang, và "
        "tag quyết định giá trị nào còn hợp lệ ở bước sau — nên `document` và "
        "`layout` là hai quyết định lớn nhất, phần còn lại chảy theo.",
        "",
        "## Ba hạng giấy tờ",
        "",
    ]
    for name in policy_module.ORDER:
        documents = pol.documents(name)
        lines += [f"### `{name}` — {len(documents)} loại", "",
                  pol.reasons.get(name, ""), "",
                  "`" + "`, `".join(documents) + "`", ""]

    lines += [
        "## Bộ áo (`variant`) được dựng ra sao",
        "",
        f"Hai nguồn. **Trục** — {len(variants.AXES)} trục độc lập "
        f"(`{'`, `'.join(axis.name for axis in variants.AXES)}`), tổ hợp lại "
        f"cho {' và '.join(f'{count:,} bộ áo hạng {level}' for level, count in variants.space().items())}. "
        "Rẻ và rộng, nhưng mỗi bộ vẫn là *cùng một trang sơn khác màu*.",
        "",
        f"**Kiến trúc** — {len(redesign.DESIGNS)} bản vẽ tay trong "
        "`agent/redesign.py`, mỗi bản là một cách dựng trang khác hẳn: cột "
        "nhận diện dọc bên trái, sổ cái không đường viền, băng-rôn tối chữ đảo "
        "màu, bảng thang bậc lệch phải. Đây mới là thứ làm bố cục khác đi thật.",
        "",
        "Khác bao nhiêu thì có đo, không nói miệng: `agent/distance.py` vẽ cùng "
        "một trang hai lần — một lần `variant=none`, một lần mặc bộ áo — rồi "
        "đếm tỉ lệ ô chữ đã dời chỗ **sau khi trừ đi độ dịch chung của cả "
        "trang**. Trừ độ dịch chung là điểm mấu chốt: nới lề đẩy cả trang xuống "
        "15 mm thì đó vẫn là trang cũ nằm thấp hơn, không phải bố cục mới.",
        "",
    ]
    graphic = [d for d in redesign.DESIGNS if d.graphic]
    lines += [
        f"{len(graphic)} trong số đó được đánh dấu `graphic`: chúng đủ tính "
        "thiết kế để một giấy tờ hạng `locked` cũng mặc được mà vẫn ra dáng ấn "
        "phẩm chính thức — `" + "`, `".join(d.id for d in graphic) + "`.",
        "",
        "## Cái gì bộ áo không được đụng vào",
        "",
        "`generators/html/sheets/variant.py::forbidden` chặn hai thứ, và chặn "
        "vì cùng một lý do: nhãn được đo từ DOM sau khi CSS chạy, nên CSS nào "
        "**đổi chữ** sẽ làm nhãn nói dối.",
        "",
        "- `text-transform` — chữ hiện lên là HOA còn nhãn ghi thường.",
        "- `content:` có chữ trong đó — thêm chữ không ai gán nhãn.",
        "",
        "`content:''` rỗng thì được: đó là cách bật một pseudo-element trang "
        "trí, và nó không thêm chữ nào.",
        "",
        "## Chữ viết tay",
        "",
        "`hand_both` là giá trị chính: WriteViT viết được chữ nào thì viết, "
        "phần nó không viết được (chữ số, chữ hoa, dấu câu) mới rơi về font. "
        "`hand_font` bị tắt bằng `enabled: false` — dùng font ngay từ đầu thì "
        "trang ghi nhãn 'viết tay' mà pixel là chữ in, tức là nhãn sai.",
        "",
        "## Dấu và QR",
        "",
        "`generators/html/ornament.py` đóng dấu **trước** khi làm cũ tờ giấy, "
        "vì ngoài đời cũng vậy. Chỗ đóng do `clearest()` tìm: nó dò ba vòng — "
        "quanh mỏ neo, dải ngang cùng độ cao, rồi cả tờ — và lấy **vòng đầu "
        "tiên có chỗ trống hẳn**. Không có ngưỡng 'chồng bao nhiêu thì chấp "
        "nhận': ngưỡng ấy từng là 15% và gần như không bao giờ kích hoạt, nên "
        "QR vẫn đè lên tiêu đề.",
        "",
        "Ngoại lệ là `page_full` và `page_center` — mỏ neo của con dấu chìm "
        "BẢN SAO, vốn *phải* vắt ngang chữ. Chúng khai trong "
        "`OVERPRINT_ANCHORS` và bộ phản biện bỏ qua.",
        "",
        "## Hai cách một giá trị bị tắt",
        "",
        "- `weight: 0` — tắt vì lỡ tay, chưa ai quyết.",
        "- `enabled: false` — tắt có chủ ý, và `degradation.SWITCHED_OFF` khai "
        "tên nó ra. `ink_degradation` (hiệu ứng đốm trên giấy nhiệt) nằm ở "
        "đây; `tools/rules_report.py --check` bắt cả hai chiều, nên khai mà "
        "không tắt hay tắt mà không khai đều gãy.",
        "",
        "Bộ chọn đọc **cả hai**. Một bộ chọn chỉ nhìn `weight` sẽ vẽ "
        "`torn_edges` và `punched`, tức là đục lỗ qua những trang mà nhãn "
        "khẳng định là còn nguyên chữ.",
        "",
    ]
    if review is not None:
        lines += ["## Lượt chạy gần nhất nói gì", "",
                  f"`{review.dataset}` — {review.pages} trang, "
                  f"{len(review.bad_pages())} trang có lỗi nặng "
                  f"({len(review.bad_pages()) / max(review.pages, 1) * 100:.1f}%).",
                  ""]
        for code, times in review.by_code().items():
            severity, _, means = critic.CODES.get(code, ("?", "?", ""))
            lines.append(f"- `{code}` ({severity}) ×{times} — {means}")
        lines.append("")
    return "\n".join(lines)


def checklist(review: critic.Review | None = None) -> str:
    """The critic's own checks, written as something to run before answering."""
    lines = [
        _stamp(review.dataset if review else ""),
        "",
        "# Soi lại trước khi trả lời",
        "",
        "Đây chính là những gì `agent/critic.py` sẽ soi sau khi trang được vẽ. "
        "Nó chạy dù bạn có đọc hay không, và cái gì nó bắt được sẽ quay lại "
        "thành hệ số phạt cho đúng những giá trị bạn vừa chọn. Đọc trước thì "
        "rẻ hơn.",
        "",
        "## Lỗi nặng — một trang dính là một trang hỏng",
        "",
    ]
    for code, (severity, side, means) in critic.CODES.items():
        if severity != critic.SEVERE:
            continue
        where = "đọc từ record" if side == "record" else "đọc từ ảnh giấy"
        lines.append(f"- **`{code}`** ({where}) — {means}")
    lines += ["", "## Lỗi nhẹ — chấp nhận được lác đác, không chấp nhận được cả loạt", ""]
    for code, (severity, side, means) in critic.CODES.items():
        if severity == critic.SEVERE:
            continue
        where = "đọc từ record" if side == "record" else "đọc từ ảnh giấy"
        lines.append(f"- **`{code}`** ({where}) — {means}")

    lines += [
        "",
        "## Suy ra được gì khi đang chọn",
        "",
        "Bạn chọn trước khi trang được vẽ, nên không thấy được ô nào đè ô nào. "
        "Nhưng phần lớn lỗi trên có nguyên nhân đoán được từ chính tổ hợp:",
        "",
        "1. **Dấu to trên phôi chật.** Một con dấu hay QR cỡ lớn trên phôi kín "
        "chữ thì `clearest()` không còn chỗ để né. Phôi càng đặc thì dấu càng "
        "phải nhỏ, hoặc đừng đóng dấu.",
        "2. **Làm cũ chồng làm cũ.** Photocopy chồng ố chồng chụp lệch thì mực "
        "và giấy dính vào nhau: đó là `nhat` và `chu_nhat_mau`. Một trang nên "
        "có một câu chuyện, không phải ba.",
        "3. **Mực nhạt trên nền có hoa văn.** `faded_gray` cộng nền guilloche "
        "làm tiêu đề cột biến mất — lỗi `khong_muc` hay gặp nhất trong bộ hiện "
        "tại rơi vào `colhdr`.",
        "4. **Lề rộng trên giấy hẹp.** Bộ áo đặt lề theo milimet tuyệt đối sẽ "
        "đẩy ô ra ngoài một cuộn giấy nhiệt 80 mm. Các bộ áo ấy gắn "
        "`excludes: [till_receipt]`, nên bộ luật đã chặn — đừng đề xuất.",
        "5. **Cùng một món ba lần.** Nội dung lặp là `lap_noi_dung`. Nếu bạn "
        "cũng sinh nội dung, hãy để một hoá đơn kể một lần mua hàng có lý.",
        "",
        "## Câu hỏi cuối",
        "",
        "*Tờ giấy này có tồn tại ngoài đời không?* Nếu phải nghĩ quá ba giây "
        "để bênh nó thì đổi đi. Đa dạng mà vô lý còn tệ hơn là đơn điệu — dữ "
        "liệu vô lý dạy mô hình những thứ nó sẽ không bao giờ gặp.",
        "",
    ]
    return "\n".join(lines)


def write(directory: Path | str, rules: dict, pol,
          review: critic.Review | None = None) -> dict[str, Any]:
    """All three files. Returns what was written and how big."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    pages = {
        "SYSTEM_PROMPT.md": system_prompt(rules, pol, review),
        "KNOWLEDGE.md": knowledge(rules, pol, review),
        "CHECKLIST.md": checklist(review),
    }
    for name, body in pages.items():
        (directory / name).write_text(body, encoding="utf-8")
    return {name: len(body) for name, body in pages.items()}


__all__ = ["DEFAULT_DIR", "FILES", "checklist", "knowledge", "system_prompt",
           "write"]
