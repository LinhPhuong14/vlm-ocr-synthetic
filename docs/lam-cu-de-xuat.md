# Nhiễu và làm cũ — kiểm kê hiện có, và danh mục đề xuất

Thuộc tính `augmentation` là thuộc tính **thứ 7 và cuối cùng** trong
[`rules/_order.yaml`](../rulebase/rules/_order.yaml): nó bốc sau cùng nên thấy
được mọi thẻ phía trên, và nó chạy sau khi trang đã vẽ xong nên không được phép
dịch một pixel nào — [`generators/html/render.py`](../generators/html/render.py)
assert lại kích thước trước và sau chuỗi, vì một phép resize lọt vào giữa sẽ
làm lệch mọi hộp nhãn mà ảnh nhìn vẫn bình thường.

Tài liệu này chia làm ba phần:

* **A** — 14 mô hình đã dựng và đang được bốc tới, kèm số lượt gọi thật.
* **B** — những gì đã dựng nhưng **không kịch bản nào bốc tới được**: tham số
  chết, giá trị hợp lệ chưa dùng, thư mục tài nguyên chưa nối, mô hình nằm
  trong nhánh đã nghỉ hưu.
* **C, D, E** — nhiễu chưa có: từ thư viện ngoài, từ kỹ thuật đồ hoạ, và từ
  chỗ trống riêng của chứng từ Việt Nam.

Mỗi mục ghi: **nó là gì**, **dựng bằng gì**, **vì sao đáng làm cho OCR tiếng
Việt**, và — chỗ này mới đáng giá — **nó có làm hỏng nhãn không**.

> ### ✅ Đã làm kể từ bản đầu của tài liệu này
>
> Bản đầu là một bản kiểm kê thuần. Từ đó tới nay:
>
> * **Mười hai mô hình của Augraphy đã chuyển thể** (mục D1) — `bad_photocopy`,
>   `color_shift`, `delaunay_tessellation`, `dirty_drum`, `dirty_rollers`,
>   `dot_matrix`, `glitch_effect`, `letterpress`, `markup`,
>   `voronoi_tessellation`, `hollow`, `scribbles`. Registry lên **26 mô hình**,
>   và chín kịch bản mới trong `rules/augmentation.yaml` bốc tới cả mười hai.
> * **Ba mô hình của cái máy thành ba THUỘC TÍNH riêng.** `bad_photocopy`,
>   `dirty_drum` và `dirty_rollers` mỗi cái một file và mỗi cái một thuộc tính
>   rule-base (`toner`, `drum`, `rollers`), vì chúng là ba bộ phận hỏng độc lập
>   của một cái máy. Rule-base đi từ 7 lên **10 thuộc tính**, và `chain_of` giờ
>   ghép chuỗi của MỌI thuộc tính theo thứ tự bốc — vốn đã là hình dạng của mã
>   từ đầu, chỉ chưa ai dùng tới.
> * **`tools/rules_report.py` giờ đối chiếu HAI CHIỀU.** Chiều cũ: chuỗi không
>   được gọi tên mô hình không tồn tại. Chiều mới — chiều mà cả mục B của tài
>   liệu này nói tới — **mô hình nào không chuỗi nào gọi tên thì báo lỗi**. Từ
>   nay một năng lực dựng xong rồi bỏ quên không lọt qua được `make preflight`.
> * **`by_box`** — bọc một mô hình bất kỳ để nó chỉ ăn vào vài ô chữ thay vì cả
>   trang, theo sáu lối bốc. Đây là câu trả lời cho câu hỏi mà bản đầu chưa đặt
>   ra: mọi mô hình ở đây áp ĐỀU khắp mặt giấy, mà hỏng thật thì có chỗ.
> * **Việc số 1 của bảng ưu tiên (mục G) đã làm**: `make legibility` đo độ
>   tương phản mực/giấy trong từng hộp nhãn trước và sau khi làm cũ.
>
> Ba mục còn lại của mục G — ánh sáng không đều, `carbon_copy`, mở khoá hình
> học — vẫn còn nguyên. Bảng ở mục G đã cập nhật theo.

> **Ranh giới hai tầng.** Đừng lẫn hai thứ:
> **primitive** là một hàm trong [`degradation/`](../degradation), ghi tên trong
> registry `DEGRADATIONS`; **kịch bản** là một `id` trong
> [`rules/augmentation.yaml`](../rulebase/rules/augmentation.yaml), tức là một
> *chuỗi* các primitive có trọng số. Hiện có **14 primitive** và **15 kịch bản**
> (một trong số đó, `pristine`, là chuỗi rỗng). Thêm một primitive là thêm một
> file Python; thêm một kịch bản là thêm mươi dòng YAML.

---

## A · 14 primitive đã có, tất cả đều đang được dùng

Số ở cột **lượt gọi** đếm số lần primitive đó xuất hiện trong một `chain` của
`rules/augmentation.yaml`. Không có primitive nào bằng 0 — registry và luật
hiện khớp nhau.

| # | primitive | file | lượt gọi | mô hình vật lý | nguồn |
| ---: | --- | --- | ---: | --- | --- |
| 1 | `paper_texture` | [`texture.py`](../degradation/texture.py) | 14 | tờ giấy hiện dưới chữ, có thớ và nếp gấp | DocCreator `Context::BackgroundContext` |
| 2 | `ink_degradation` | [`ink_degradation.py`](../degradation/ink_degradation.py) | 10 | mực mòn: vùng nhiễu hình ê-líp quanh điểm mầm, mờ dần theo Gauss | DocCreator `GrayscaleCharsDegradationModel.cpp` (Kieu) |
| 3 | `blur_zones` | [`blur_zones.py`](../degradation/blur_zones.py) | 8 | nhoè **theo mảng**, không nhoè cả trang | DocCreator `BlurFilter.cpp` |
| 4 | `paper_overlay` | [`texture.py`](../degradation/texture.py) | 4 | ảnh chụp giấy thật phủ lên **cả mực** | SynthDoG `resources/paper/` |
| 5 | `shadow_binding` | [`shadow_binding.py`](../degradation/shadow_binding.py) | 4 | bóng của gáy sách đổ vào mép trang | DocCreator `ShadowBinding.cpp` |
| 6 | `holes` | [`holes.py`](../degradation/holes.py) | 4 | rách, thủng — phần giấy mất đi lấp bằng **màu đen** | DocCreator `HoleDegradation.cpp` |
| 7 | `blur` | [`blur_zones.py`](../degradation/blur_zones.py) | 3 | nhoè đều toàn trang (ống kính) | — |
| 8 | `scan_banding` | [`capture.py`](../degradation/capture.py) | 3 | dải sáng tối theo trục lăn của máy quét / fax | repo này |
| 9 | `gradient_domain` | [`texture.py`](../degradation/texture.py) | 2 | vết bẩn ghép bằng Poisson blending (`cv::seamlessClone`) | Seuret và cs., ICDAR 2015 |
| 10 | `phantom_character` | [`texture.py`](../degradation/texture.py) | 2 | mực thừa của bản in mòn, dán vào sườn chữ | DocCreator `PhantomCharacter.cpp` |
| 11 | `halftone_screen` | [`capture.py`](../degradation/capture.py) | 2 | lưới tram 45° của máy photocopy | repo này |
| 12 | `jpeg_blocks` | [`capture.py`](../degradation/capture.py) | 2 | lưới 8×8, sai số dồn qua nhiều lần nén | repo này |
| 13 | `bleed_through` | [`bleed_through.py`](../degradation/bleed_through.py) | 1 | mực mặt sau thấm sang | DocCreator `BleedThrough.cpp` |
| 14 | `pattern_overlay` | [`texture.py`](../degradation/texture.py) | 1 | dấu / hoa văn đóng lên **bản sao**, trộn theo lối nhân | repo này |

### 15 kịch bản, và chúng mô tả cái gì

| id | trọng số | ràng buộc | đọc ra là |
| --- | ---: | --- | --- |
| `pristine` | 2 | — | không làm gì. Đây là **trần** để đo mọi kịch bản khác. |
| `real_paper` | 4 | — | in trên giấy thật, chưa hỏng gì. Chỉ hai lớp giấy, không mòn mực. |
| `light` | 4 | — | mòn nhẹ + nhoè một mảng. `level: 1`. |
| `medium` | 4 | — | mòn vừa + bóng gáy + phủ giấy. `level: 3`. |
| `heavy` | 2 | `excludes: thermal` | mòn + thấm hai mặt + rách mép. Giấy nhiệt in một mặt nên bị loại. |
| `stains` | 3 | — | vết ố ghép Poisson, 5 vết. |
| `ghost_text` | 3 | — | bóng mực thừa quanh chữ (`phantom_character`). |
| `photocopy` | 3 | — | dáng bản photo **không** có lưới tram: tương phản cao, mực bệt, nhoè. |
| `crumpled` | 2 | `requires: thermal` | nhàu — 4 nếp gấp. Chỉ giấy nhiệt mỏng mới nhàu kiểu này. |
| `torn_edges` | 2 | — | rách mép + rách góc, lấp đen. |
| `punched` | 1 | — | thủng giữa trang (3 lỗ). |
| `photocopy_screened` | 3 | `excludes: thermal` | bản photo **có** lưới tram thật. Cố ý **không** có `ink_degradation`. |
| `photocopy_stamped` | 2 | `excludes: thermal` | như trên + dấu `ĐÃ SAO Y` đóng đè lên lưới tram. |
| `flatbed_scan` | 3 | — | quét phẳng: dải lăn nghiêng 1.5° + nén JPEG một lần. |
| `forwarded_photo` | 3 | — | chụp điện thoại rồi chuyển tiếp 3 chặng: `quality: 30, passes: 3`. |

Hai chú thích trong `augmentation.yaml` đáng nhắc lại vì chúng là **quyết định
đo bằng mắt, không suy ra được từ mô hình**:

1. `photocopy_screened` không có `ink_degradation`. Lưới tram *đã là* hỏng mực
   rồi — nó băm nét chữ thành chấm. Chồng thêm mòn mực lên thì chữ không đọc
   được nữa, mà nhãn vẫn khai là có chữ ở đó. **Một tờ không đọc được mang nhãn
   đầy đủ là dữ liệu độc**, không phải dữ liệu khó.
2. Thứ tự `halftone_screen` → `blur` chứ không ngược lại: máy photo tạo chấm
   rồi ống kính mới làm mềm mép chấm. Ngược lại ra chấm sắc trên nền đã nhoè,
   không máy nào cho ra như thế.

---

## B · Đã dựng nhưng chưa bốc tới được

Đây là phần đáng đọc nhất của tài liệu: **năng lực đã trả tiền rồi mà chưa
tiêu**. Thêm một dòng YAML là dùng được ngay, không phải viết mã.

### B1 · Tham số không kịch bản nào truyền

| primitive | tham số chết | mặc định đang chạy | thêm nó vào thì được gì |
| --- | --- | --- | --- |
| `blur_zones` | `feather` | `0.12` | độ loe của mép mảng nhoè. Mảng nhoè mép sắc đọc ra là ảnh ghép; loe rộng đọc ra là độ sâu trường ảnh nông của điện thoại. |
| `shadow_binding` | `angle` | `30.0` | góc đổ bóng. Cố định 30° nghĩa là **mọi trang trong bộ dữ liệu có nguồn sáng cùng một hướng** — mô hình học được điều đó và sẽ hỏng trên ảnh sáng từ hướng khác. |
| `bleed_through` | `verso`, `blur_sigma` | `None` (lật gương chính nó), `1.2` | `verso=None` nghĩa là mặt sau **luôn** là ảnh gương của mặt trước. Trang hai mặt thật thì mặt sau là trang khác. Truyền được một trang đã render khác vào đây là xong. |
| `gradient_domain` | `stains_dir`, `rotate` | `None`, `True` | `stains_dir` trỏ vào một thư mục **ảnh vết ố quét thật**. Xem B3. |
| `holes` | `ratio_outside`, `roughness`, `shadow_width`, `shadow_intensity`, `patterns`, `paper_colour`, `below` | `0.0, 1.0, 3, 0.45, None, 255, None` | `below` là **ảnh lộ ra qua chỗ rách** — hiện luôn là màu phẳng. Đặt một ảnh mặt bàn vào đây thì chỗ rách có vân gỗ chứ không phải một mảng đen. `roughness` đổi độ răng cưa của đường rách. |
| `ink_degradation` | `density`, `config` | `0.35`, `InkDegradationConfig()` | `density` là liều speckle. Con số 0.35 chỉnh bằng mắt qua ba lượt (0.25 → 0.175 → 0.35) và **không có gì suy ra nó**; `config` mở được `min_axis`/`max_axis` (cỡ hạt) và hai ngưỡng mực/giấy. |
| `paper_texture` | `papers_dir` | `None` → `textures/paper/` | trỏ sang một thư mục giấy quét thật. |
| `paper_overlay` | `overlay`, `overlays_dir` | `None` → bốc ngẫu nhiên 1 trong 6 ảnh | **không kịch bản nào chọn được ảnh giấy cụ thể**. Giấy nhiệt và giấy A4 văn phòng đang bốc chung một rổ 6 ảnh. |
| `pattern_overlay` | `patterns_dir` | `None` → `textures/ornament/` | — |

### B2 · Giá trị hợp lệ nhưng chưa lần nào bốc

| chỗ | giá trị đang dùng | giá trị bỏ không | ghi chú |
| --- | --- | --- | --- |
| `ink_degradation.level` | 1, 2, 3, 4 | **5 … 10** | Thang của DocCreator là 1–10 và tỉ lệ điểm mầm **đổi theo ngưỡng**: ≤4 là 50/30/20 (chấm trên giấy), ≤7 là 30/50/20 (chấm cưỡi lên rìa chữ), >7 là 20/30/50 (chấm ăn vào trong nét). Dừng ở 4 nghĩa là **cả hai chế độ trên chưa từng xuất hiện trong bộ dữ liệu** — mới chỉ có giấy bẩn, chưa có chữ mục. |
| `holes.fill` | `black` | `paper`, `white`, bộ ba BGR | `paper` là tờ giấy phía sau lộ ra (xấp giấy), `white` là mặt bàn sáng. Hiện mọi chỗ rách đều đen tuyền. |
| `shadow_binding.border` | `left`, `top`, `bottom` | **`right`** | bốn hướng có mã, ba hướng có dữ liệu. |
| `phantom_character.frequency` | `rare` | `frequent` (mặc định), `very_frequent` | `FREQUENCIES = {rare: 15, frequent: 40, very_frequent: 70}`. Đang dùng đúng mức thấp nhất; `tools/degradation_showcase.py` thì trưng `very_frequent`, nên **ảnh minh hoạ trong README nặng hơn dữ liệu thật**. |
| `pattern_overlay.anchor` | `bottom_right` | `random` + mọi neo khác | dùng **đúng một lần**, với **đúng một** trong 27 file của `textures/ornament/` (`seal_square_copy`). 26 file còn lại chỉ vào được trang qua thuộc tính `ornament` (tức là **dưới** lớp làm cũ), không bao giờ đóng lên bản sao. |
| `holes.placement` | cả 3 | — | `center`, `border`, `corner` đều đã dùng. |

### B3 · Thư mục tài nguyên thật chưa nối

* **`textures/stain/` không tồn tại.** `degradation/texture.py` khai
  `STAIN_DIR = textures/stain` và `gradient_domain` ưu tiên đọc từ đó, nhưng
  thư mục ấy không có trong cây. Nên **mọi vết ố hiện nay đều là
  `stain_patch()` sinh bằng số ngẫu nhiên**, không phải vết ố quét thật. Poisson
  blending ghép rất khéo, nhưng nó ghép một hình sinh ra chứ không phải một vết
  cà phê thật.
* **`holes.patterns` chưa trỏ vào đâu.** DocCreator phát hành 18 mặt nạ rách
  mép + 18 rách giữa + 28 rách góc (giấy phép LGPL, nên không vendor). Port này
  sinh mặt nạ bằng bước đi ngẫu nhiên được làm trơn. Đủ dùng, nhưng đường vào
  cho mặt nạ thật đã mở sẵn mà chưa ai đi.
* **`phantom_character.patterns`** — như trên, với `phantomPatterns` của
  DocCreator.

### B4 · Mô hình sống trong nhánh đã nghỉ hưu

`backends: [html]` — `genalog` và `synthdog` đã rút khỏi việc sinh dữ liệu
(xem [`docs/renderers.md`](renderers.md)). Kéo theo:

* **`CurlWarp`** ([`generators/synthdog/elements/warp.py`](../generators/synthdog/elements/warp.py))
  — cong giấy phi tuyến hai lượt, **và có công thức nghịch nên map lại được toạ
  độ từng ô chữ**. Đây là thứ giá trị nhất trong nhóm này: nó giải đúng bài toán
  mà mục **C** dưới đây nói là đang bỏ trống. `visual.curl` (0.85 / 0.9 / 1.0
  cho ba loại giấy nhiệt) vẫn nằm trong luật, vẫn được bốc, và **không ai đọc
  nữa** — chỉ `template_receipt.py` của synthdog đọc.
* **`generators/genalog/genalog/degradation/effect.py`** — cả một họ nhiễu đã
  vendor sẵn, chưa lần nào chạy qua đường `apply_recipe`: `salt`, `pepper`,
  `salt_then_pepper`, `pepper_then_salt`, `morphology` (`open` / `close` /
  `erode` / `dilate`), `translation`, `overlay_weighted`, `bleed_through` bản
  của genalog. `erode`/`dilate` là **mô hình nét mực dày lên / mỏng đi**, thứ mà
  `degradation/` hiện không có — `ink_degradation` ăn mực theo mảng chứ không
  làm cả nét béo ra đều.
* **`textures/background/`** — 8 ảnh cảnh nền chụp thật (SynthDoG). Chỉ
  `config_vi_receipt.yaml` của synthdog trỏ vào. Renderer HTML cho ra ảnh quét
  phẳng không có ngoại cảnh, nên **bộ dữ liệu hiện tại không có tờ nào nằm trên
  bàn**.

### B5 · `DEFAULT_CHAIN` chỉ có công cụ dùng

`degradation/__init__.py` khai một chuỗi mặc định 5 bước; chỉ
`tools/augment_samples.py` gọi tới. Đường sinh dữ liệu luôn đi qua
`apply_recipe`, tức là qua YAML. Không sai, nhưng ai sửa `DEFAULT_CHAIN` mà
tưởng mình đang đổi dữ liệu thì sẽ không thấy gì thay đổi.

---

## C · Lỗ hổng lớn nhất: đường đang chạy không có một biến dạng hình học nào

Mọi primitive ở phần A **đều là lọc hoặc ghép tại chỗ**, và sau đợt chuyển thể
Augraphy thì còn **đúng một ngoại lệ**: `glitch_effect` dịch cả một dải dòng
ảnh sang ngang. Nó không đổi kích thước trang nên đi qua được assert dưới đây,
nhưng chữ trong dải bị dịch thì lệch khỏi hộp nhãn của nó — docstring của nó
nói thẳng điều ấy, và kịch bản `screen_photo` để `max_shift` ở 0.004 bề rộng
trang, dưới nửa bề rộng một ký tự, chính vì lý do ấy. Ngoài nó ra, không mô
hình nào dịch một pixel — và điều đó được assert:

```python
if aged.shape[:2] != before:
    raise RuntimeError("a degradation resized the page ...")
```

Nên bộ dữ liệu hiện tại có mọi kiểu bẩn, và **không có một tờ nào nghiêng,
cong, hay chụp xiên**. Trong khi ảnh hoá đơn thật tới tay OCR thì gần như luôn
có ít nhất một trong ba thứ đó.

Đây không phải lỗi thiết kế — đó là cái giá đã chọn có ý thức: nhãn hộp được
tính **trước** khi làm cũ, nên bất kỳ phép biến hình nào cũng phải biến hộp
theo. Muốn mở khoá thì có đúng ba đường:

| đường | việc phải làm | rủi ro nhãn |
| --- | --- | --- |
| **1. Ánh xạ hộp cùng ảnh** | mỗi primitive hình học trả về `(ảnh, ma trận)` hoặc `(ảnh, hàm map)`; `apply_recipe` nhân dồn và áp lên `boxes`/`cells` sau chuỗi. `CurlWarp` (B4) đã làm đúng thế này rồi. | thấp, nếu có test giữ. Hộp thành **tứ giác** chứ không còn là chữ nhật — schema nhãn đã là quad (`quads_from_rects`) nên chịu được. |
| **2. Tầng hình học riêng, sau nhãn** | đặt biến dạng ngoài `augmentation`, thành thuộc tính thứ 8 `capture`, chạy sau cùng, và ghi phép biến hình vào metadata để ai cần thì tự áp. | trung bình: nhãn trong file không còn khớp pixel, ai đọc mà không áp phép biến hình sẽ sai hoàn toàn. **Không nên.** |
| **3. Chỉ nhận biến dạng bảo toàn chữ nhật** | xoay bội số 90°, lật, cắt biên. | không rủi ro, nhưng cũng gần như không thêm được gì thật. |

**Khuyến nghị: đường 1.** Và `CurlWarp` đã có sẵn công thức nghịch, nên nó là
chỗ để bắt đầu chứ không phải viết mới.

---

## D · Từ thư viện ngoài

Bốn thư viện dưới đây phủ đúng bài toán này. Ghi ra để lần sau khỏi khảo sát
lại, kèm **những gì repo này chưa có**.

> Giấy phép ghi theo trí nhớ tại thời điểm viết — **kiểm lại trước khi vendor
> hay copy mã**, và nhớ repo này chưa chọn giấy phép cho chính nó.

### D1 · Augraphy — sát đề bài nhất

Thư viện Python chuyên **document image augmentation**, chia ba pha
`ink → paper → post` đúng như lối `paper_texture` chạy đầu chuỗi ở đây.

**✅ Mười hai mô hình đánh dấu ✅ dưới đây đã chuyển thể xong** — xem
[`degradation/README.md`](../degradation/README.md) và năm file
`copier.py` · `printing.py` · `marks.py` · `tessellation.py` · `channel.py`.
Mã của Augraphy không vendor: mỗi mô hình viết lại, ghi rõ chuyển thể từ đâu,
đúng lối đã làm với DocCreator. Những mục còn lại vẫn là đề xuất:

* ✅ `Letterpress` — mực in typo: nét đậm ở rìa, nhạt ở giữa vì áp lực bản in.
* `LowInkPeriodicLines` / `LowInkRandomLines` (một nửa: `dot_matrix.dead_pins` đã làm đúng hình dạng ấy cho máy in kim) — **máy in kim hoặc laser sắp hết
  mực: những vạch trắng ngang cắt qua chữ**. Xem thêm E-VN-1.
* `Dithering` (Floyd–Steinberg / Bayer) — khác `halftone_screen` ở chỗ khuếch
  tán sai số chứ không ngưỡng theo lưới; đây là thứ máy fax và ảnh 1-bit thật
  cho ra.
* ✅ `DirtyDrum`, `DirtyRollers` — trống mực bẩn để lại vệt **dọc theo hướng giấy
  chạy**, khác `scan_banding` (vuông góc).
* ✅ `BadPhotoCopy` — mảng đen loang và vùng cháy sáng của máy photo cũ.
* `Folding` — nếp gấp có **bóng đổ hai bên** chứ không chỉ đổi độ sáng.
* `BookBinding`, `BindingsAndFasteners` — gáy sách cong, ghim, kẹp, lò xo.
* ✅ `Markup`, `Scribbles` — bút dạ quang, gạch chân, khoanh tròn, chữ viết đè.
* `WaterMark` — chữ chìm.
* `LightingGradient`, `ShadowCast`, `ReflectedLight` — **ánh sáng không đều và
  vệt loá**; xem E3.
* `Moire` — vân moiré khi chụp lại một bản đã có lưới tram, hoặc chụp màn hình.
* ✅ `ColorShift`, `GlitchEffect` (còn `InkShifter`) — lệch kênh màu; xem E1.
* ✅ `VoronoiTessellation`, `DelaunayTessellation` — sinh hoạ tiết nền.
* `SubtleNoise`, `NoiseTexturize`, `BrightnessTexturize` — nhiễu biên độ nhỏ.
* `Squish`, `Geometric`, `Rescale` — biến dạng hình học (đụng mục C).

**Nên làm gì:** không vendor cả thư viện. Hai lý do: nó kéo theo phụ thuộc, và
lối thiết kế ở đây là **mỗi mô hình một file, ghi rõ nguồn, kiểm lại được với
bản gốc**. Cách hợp hơn là chọn 5–8 mô hình còn thiếu, viết lại trong
`degradation/` theo đúng lối `capture.py`, và ghi Augraphy vào phần nguồn.
Nếu chỉ để **so sánh nhanh xem mô hình nào đáng port**, thì cài tạm và chạy
qua `tools/augment_samples.py` là đủ.

### D2 · `straug` — nhiễu cho nhận dạng chữ dòng đơn

Bộ 36 phép cho STR, chia 8 nhóm: `warp` (Curve, Distort, Stretch), `geometry`
(Perspective, Rotate, Shrink), `blur` (Gaussian, Defocus, Motion, Glass, Zoom),
`noise` (Gaussian, Shot, Impulse, Speckle), `weather` (Fog, Snow, Frost, Rain,
Shadow), `camera` (Contrast, Brightness, JpegCompression, Pixelate), `pattern`
(các kiểu lưới), `process` (Posterize, Solarize, Invert, Equalize,
AutoContrast, Sharpness, Color).

**Đáng lấy:** `MotionBlur` **có hướng** (repo này chỉ có nhoè Gauss đẳng
hướng — mà rung tay khi chụp thì luôn có hướng), `GlassBlur`, `Pixelate`,
`Solarize`/`Posterize` (ảnh qua ứng dụng nhắn tin bị nén màu).
**Không hợp:** cả nhóm `weather` — hoá đơn không chụp dưới mưa tuyết.
**Chú ý:** thư viện này thiết kế cho **ảnh dòng chữ đã cắt**, không cho cả
trang; lấy công thức chứ đừng lấy tham số.

### D3 · `ocrodeg` — nhiễu kiểu máy in cũ

Nhỏ, cũ, và có vài thứ không ai khác có:

* `printlike_multiscale`, `printlike_fibrous` — mô hình **thớ giấy ăn vào nét
  mực**, nhiễu đa tỉ lệ, khác hẳn nhiễu cộng.
* `random_blobs`, `random_blotches` — đốm mực ngẫu nhiên theo phân phối
  Poisson trên mặt giấy.
* `noise_distort1d` — bóp méo theo một trục bằng nhiễu trơn, tức là **mặt giấy
  gợn sóng**; đây là dạng nhẹ và rẻ của `CurlWarp`.
* `binary_blur` + `autoinvert` — chuỗi ngưỡng hoá làm nét chữ đứt đoạn.

### D4 · `albumentations` / `imgaug` — hạ tầng chung

Không chuyên tài liệu, nhưng có ba thứ đáng lấy vì **chúng biến đổi cả toạ độ**
(giải luôn mục C): `Perspective`, `Affine`, `ElasticTransform`, `GridDistortion`,
`OpticalDistortion` đều nhận `keypoints`/`bboxes` và trả về đã map.
Ngoài ra: `ISONoise` (nhiễu cảm biến đúng mô hình, có cả nhiễu màu),
`ChromaticAberration`, `RingingOvershoot` (viền vọng của nén và của làm nét),
`Downscale` (thu nhỏ rồi phóng lại — **đúng thứ ứng dụng nhắn tin làm**),
`Spatter`, `RandomToneCurve`.

### D5 · DocCreator — phần chưa port

Đã port 8 mô hình. Bản gốc còn ít nhất hai nhóm chưa đụng tới, và cả hai đều
liên quan tới hình học nên vướng mục C: **biến dạng 3D theo lưới mesh** (trang
giấy dựng thành mặt cong trong không gian rồi chiếu lại, có ánh sáng), và
**nhiễu ảnh chụp/ánh sáng** đi kèm. Đây là nguồn tốt nhất cho E3 vì mô hình của
họ dựng từ bản quét thật.

---

## E · Kỹ thuật đồ hoạ dựng tay được

Phần này không cần thư viện: OpenCV + numpy là đủ, và mỗi mục dưới đây dựng
được trong một file cỡ `capture.py` (100–150 dòng).

### E1 · Lỗi in ấn

**`misregistration` — lệch bản in.** Máy in offset in từng màu một bản; bản
lệch nhau vài chục micron thì chữ đen viền xanh một bên, đỏ bên kia. Dựng:
tách kênh BGR, dịch mỗi kênh 1–3 px theo hướng khác nhau, ghép lại.
*Vì sao đáng:* đây là **nguồn nhiễu màu duy nhất mà repo này chưa có** — mọi
mô hình hiện tại đều thao tác trên độ sáng. Mô hình OCR học trên dữ liệu không
có lệch kênh sẽ coi viền màu là ký tự lạ.
*Nhãn:* an toàn tuyệt đối, không pixel nào ra khỏi vị trí về mặt hình học.

**`dot_gain` — mực loang trên giấy thấm.** Chấm tram in ra to hơn chấm trên
bản. Dựng: `cv2.dilate` với kernel elliptic 2–3 px **chỉ trên vùng mực**, rồi
làm mềm mép. Đây cũng là chỗ dùng `erode`/`dilate` đã vendor sẵn ở B4 —
**mô hình nét dày lên / mỏng đi** mà `degradation/` đang thiếu.
*Vì sao đáng cho tiếng Việt:* xem khung dưới.

> ### ⚠️ Dấu thanh là chỗ mọi mô hình nhiễu ở đây chưa được đo
>
> Chữ Việt có `ắ ằ ẳ ẵ ặ ế ề ể ễ ệ ố ồ ổ ỗ ộ ớ ờ ở ỡ ợ ứ ừ ử ữ ự` — **hai dấu
> chồng lên nhau trên một nguyên âm**, mỗi dấu chỉ vài pixel ở cỡ chữ hoá đơn.
>
> `ink_degradation` ăn mực theo mảng ê-líp; `dot_gain` làm nét béo ra;
> `halftone_screen` băm nét thành chấm. Cả ba đều có thể **xoá dấu hỏi thành
> dấu ngã, hoặc dính hai dấu thành một** — mà nhãn vẫn khai đúng chữ gốc. Sai
> một dấu là sai một từ khác hẳn (`mà` / `má` / `mã` / `mạ` / `mả`).
>
> Bảng đo trong [`degradation/README.md`](../degradation/README.md) đếm
> **connected component** và **recall theo bố cục**, chưa có dòng nào đếm
> **recall riêng của ký tự có dấu**. Trước khi thêm bất kỳ mô hình nào ở phần
> E, nên có sẵn một phép đo tách riêng nhóm ký tự đó — nếu không thì mỗi mô
> hình mới là một cách mới để sinh ra dữ liệu độc mà không ai biết.

**`toner_mottling` — mực laser loang không đều.** Độ đậm mực dao động chậm
theo mặt trang. Dựng: nhiễu Perlin/value noise tần số thấp, nhân vào vùng mực.

**`risograph` — in Riso.** Từng màu một trục lăn, lệch nhau, mực loang và có
vệt lăn. Ở Việt Nam gần với **in lụa / in typo ở tiệm nhỏ** — phiếu thu, biên
lai viết tay in sẵn.

### E2 · Blend mode và tông màu

`paper_texture` (nhân) và `paper_overlay` (nhân + sàng) đã dùng blend mode.
Còn thiếu:

* **`gradient_map` — đổ tông giấy cũ.** Ánh xạ độ sáng qua một dải màu
  (trắng→kem→nâu) thay vì nhân một màu phẳng. Cho ra tờ ố vàng đúng kiểu giấy
  cũ: chỗ tối ngả nâu chứ không ngả xám.
* **`duotone` / `posterize`** — ảnh qua ứng dụng nhắn tin ở chất lượng thấp
  nhất bị giảm số mức màu; khác nén JPEG (`jpeg_blocks`) ở chỗ nó tạo **dải
  bậc thang** (banding) trên vùng chuyển màu êm.
* **`levels_clip` — cắt trắng / cắt đen.** Máy quét đặt sai ngưỡng: mọi thứ
  sáng hơn 240 thành trắng, tối hơn 20 thành đen. **Mực nhạt biến mất hẳn** —
  đây là kịch bản hỏng đáng có, và là kịch bản `thermal_faint` gặp trong đời
  thật.
* **`white_balance_error`** — chụp dưới đèn huỳnh quang ngả xanh, đèn sợi đốt
  ngả cam. Repo có `color.yaml` cho màu mực, nhưng **không có mô hình nào làm
  lệch màu cả tờ**.

### E3 · Ánh sáng và ống kính

Cả nhóm này mô tả **cái máy ảnh làm**, không phải cái tờ giấy chịu — đúng họ
với `capture.py`, nên đặt vào đó.

* **`vignette`** — tối bốn góc. Rẻ nhất trong nhóm, một mặt nạ radial.
* **`lighting_gradient`** — ánh sáng chéo không đều. Trang chụp trên bàn luôn
  có một phía sáng hơn. **Đây là nhiễu phổ biến nhất trong ảnh hoá đơn thật, và
  repo này hoàn toàn không có.** `shadow_binding` là bóng gáy sách, phạm vi hẹp
  và góc cố định 30° (xem B1).
* **`specular_glare`** — vệt loá đèn flash điện thoại: một vùng elip cháy trắng,
  **chữ dưới nó mất hẳn**. Kịch bản hỏng có thật và rất khó cho OCR.
* **`hand_shadow`** — bóng bàn tay hoặc bóng chính cái điện thoại đổ lên trang.
* **`chromatic_aberration`** — quang sai màu ở rìa ảnh: kênh đỏ và xanh lệch
  nhau, càng xa tâm càng lệch. Khác `misregistration` (E1) ở chỗ nó **phụ thuộc
  bán kính**, và nó nằm ở khâu chụp chứ không ở khâu in.
* **`motion_blur` có hướng** — rung tay. Kernel đường thẳng có góc, thay vì
  Gauss đẳng hướng.
* **`rolling_shutter`** — cảm biến CMOS quét dòng: chụp trong khi tay đang di
  làm trang **xiên dần từ trên xuống**. Đụng mục C (biến hình).
* **`barrel_distortion`** — méo thùng của ống kính góc rộng điện thoại. Đụng
  mục C.

### E4 · Bề mặt và vật liệu

* **`displacement_crumple`** — nhàu **có ánh sáng thật**. `paper_texture.creases`
  hiện vẽ nếp gấp bằng cách đổi độ sáng dọc theo đường. Làm đúng thì sinh một
  **normal map** của mặt giấy nhàu, chiếu sáng nó bằng một nguồn sáng, rồi dùng
  chính normal map đó làm **displacement** để bẻ pixel. Nếp gấp lúc đó có mặt
  sáng và mặt tối đúng vật lý, và chữ trên nếp gấp bị bẻ theo.
  *Đụng mục C*, nhưng là mục đáng nhất trong cả tài liệu này: **tờ hoá đơn gấp
  tư bỏ túi rồi chụp lại là ảnh hoá đơn phổ biến nhất Việt Nam.**
* **`emboss` / `bevel`** — dấu nổi, dấu giáp lai dập chìm. Không có mực, chỉ có
  bóng: `cv2.filter2D` với kernel hướng.
* **`deckle_edge`** — mép giấy xé tay có thớ (khác `holes` ở chỗ nó chạy dọc
  toàn bộ một cạnh).
* **`staple` / `paperclip` / `punch`** — ghim, kẹp, lỗ bấm **có bóng và có
  gỉ**. `holes` làm được lỗ nhưng không làm được kim loại.
* **`tape` / `sticky_note`** — băng dính trong (vùng bóng, hơi mờ, có bọt khí)
  và giấy note dán đè.

### E5 · Lớp phủ grunge

Toàn nhóm này dựng theo đúng lối `pattern_overlay` đã có — sinh file PNG vào
một thư mục, khai trong YAML:

* **`dust_scratches`** — bụi và xước trên mặt kính máy quét. Vệt sáng mảnh chạy
  **suốt chiều dài trang, cùng một chỗ trên mọi trang cùng máy quét**.
* **`fingerprint`** — vân tay mờ trên mặt kính.
* **`coffee_ring`** — vòng cà phê (`gradient_domain` ghép được, nhưng cần ảnh
  vệt thật — xem B3).
* **`highlighter`** — vệt bút dạ quang phủ lên chữ, trộn theo lối nhân, màu
  vàng/xanh bão hoà.
* **`pen_markup`** — gạch chân, khoanh tròn, dấu tick viết tay. Repo đã có
  engine chữ ký ([`generators/html/signature.py`](../generators/html/signature.py))
  với Bézier bề rộng thay đổi — **nét bút đã có sẵn**, chỉ cần đường đi khác.
* **`redaction`** — bôi đen thông tin. Nhãn phải biết chỗ đó **không còn chữ**,
  nếu không là dữ liệu độc.

### E6 · Sinh hoạ tiết

Nền cho E1/E4/E5, và thay được `stain_patch()` hiện tại:

* **Perlin / fBm** — nhiễu trơn đa tần, cho thớ giấy và mực loang.
  `_value_noise` trong `texture.py` đã là bản một tầng; chồng nhiều tầng là ra
  fBm.
* **Voronoi / Delaunay** — cấu trúc thớ và vết ố có ranh giới.
* **Reaction–diffusion** — vết ố loang có rìa gợn, giống vết ẩm thật hơn hẳn
  nhiễu Gauss ngưỡng hoá.
* **Tram ngẫu nhiên (FM/stochastic screening)** — chấm cùng cỡ, vị trí ngẫu
  nhiên, mật độ theo độ sáng. Máy in phun dùng lối này; `halftone_screen` hiện
  chỉ có tram AM (lưới đều 45°).
* **Khuếch tán sai số (Floyd–Steinberg)** — xem D1 `Dithering`.

---

## F · Chỗ trống riêng của chứng từ Việt Nam

Sáu mục dưới đây **không thư viện nào có sẵn** vì chúng gắn với thói quen giấy
tờ ở đây. Đây là phần có tỉ lệ *giá trị / công sức* cao nhất.

### E-VN-1 · `carbon_copy` — liên 2, liên 3
Hoá đơn giấy Việt Nam in nhiều liên chồng giấy than: liên 1 lưu, **liên 2 giao
khách** (đây mới là tờ được chụp), liên 3 nội bộ. Liên 2 khác liên 1 ở ba chỗ
đo được: **mực nhạt hơn hẳn và ngả tím than**, **nét bị nhoè do áp lực truyền
qua lớp giấy**, và **có vệt ép của nét bút ở những ô điền tay** — chữ viết tay
hằn xuống mạnh hơn chữ in.
*Vì sao đáng:* tờ tới tay OCR **thường là liên 2**, mà bộ dữ liệu hiện tại toàn
liên 1. Dựng: giảm tương phản, dịch tông sang tím, dilate nhẹ, cộng thêm một
lớp "vệt ép" lấy từ chính lớp chữ viết tay.
*Nhãn:* an toàn.

### E-VN-2 · `dot_matrix_dead_pin` — máy in kim thiếu kim
Máy in kim (`visual.dot_matrix` đã có trong luật, dùng cho hoá đơn bán lẻ và
phiếu xuất kho) khi gãy một kim sẽ để lại **một vạch trắng ngang chạy suốt mọi
dòng chữ, cùng một độ cao trong mỗi ký tự**. Ruy băng mòn thì nửa trên đậm hơn
nửa dưới.
*Vì sao đáng:* repo đã mô hình *mặt chữ* của máy kim nhưng chưa mô hình *cái
đầu in*. Và nhiễu này **có cấu trúc** (đều đặn, cùng độ cao) chứ không ngẫu
nhiên — mô hình OCR học được nó, nên nó là dữ liệu tốt.
Gần với `LowInkPeriodicLines` của Augraphy (D1).

**✅ Đã làm.** `dot_matrix` trong [`degradation/printing.py`](../degradation/printing.py)
dựng lưới chấm của đầu kim, `dead_pins` là số kim gãy, `ribbon` là độ mòn ruy
băng. Kịch bản `impact_ribbon` (`requires: [impact]`) bốc tới nó. Chưa làm nốt:
**mực ngả tím của giấy than** — đó là E-VN-1 dưới đây, và hai thứ hay đi cùng
nhau trên cùng một tờ.

### E-VN-3 · `thermal_patch_fade` — giấy nhiệt phai theo mảng
Giấy nhiệt để trong ví hoặc gần nguồn nhiệt phai **không đều**: chỗ tiếp xúc
phai trắng hẳn, và nếu bị nóng quá thì **ngả xám cả tờ, chữ chìm vào nền**.
Hiện `thermal_faint` chỉ hạ `ink_gray` đều toàn trang.
*Dựng:* mặt nạ tần số thấp nhân vào vùng mực, cộng một biến thể "cháy nhiệt"
làm tối nền.

### E-VN-4 · `sprocket_edge` — mép giấy liên tục
Giấy in liên tục cho máy kim có **dải lỗ kéo hai bên**, xé đi để lại **mép răng
cưa đều tăm tắp**. Khác `holes` ở chỗ nó **tuần hoàn và thẳng hàng** chứ không
ngẫu nhiên.
*Dựng:* đơn giản nhất trong cả danh sách — một dãy lỗ tròn cách đều 12.7 mm dọc
mép, hoặc một đường răng cưa chu kỳ cố định.

### E-VN-5 · `quarter_fold` — gấp tư bỏ túi
Tờ A4 gấp làm tư rồi mở ra chụp: **hai nếp gấp vuông góc chia trang thành bốn**,
mỗi nếp có bóng hai bên và một dải mực bị nứt dọc theo nếp.
`paper_texture.creases` vẽ nếp gấp **ngẫu nhiên**; cái này có **cấu trúc cố
định** và vì thế mô hình học được.
*Là bản rẻ của E4 `displacement_crumple`* — làm cái này trước.

### E-VN-6 · `screen_photo` — chụp lại màn hình
Hoá đơn điện tử ngày càng nhiều: người ta mở PDF trên máy tính rồi **chụp màn
hình bằng điện thoại**. Ảnh đó mang ba dấu vết cùng lúc: **vân moiré** (lưới
điểm ảnh của màn hình gặp lưới cảm biến), **viền màu RGB của subpixel** ở mép
chữ, và **vệt loá/độ sáng nền của màn hình**.
*Vì sao đáng:* đây là loại ảnh đang tăng nhanh nhất, và **không có mô hình nào
trong repo tạo ra nó**. Ba thành phần đều dựng được bằng những gì đã có:
moiré = hai lưới `halftone_screen` khác tần số chồng nhau; subpixel = lệch kênh
kiểu E1; nền màn hình = `lighting_gradient` của E3.

---

## G · Nên làm theo thứ tự nào

Xếp theo *giá trị cho OCR ÷ công sức*, và ghi rõ mục nào đụng nhãn.

| # | việc | công | nhãn | vì sao trước |
| ---: | --- | --- | --- | --- |
| 1 | **Đo recall riêng của ký tự có dấu** | thấp | — | Không có phép đo này thì mọi mục dưới đây là đoán. Xem khung ở E1. |
| 2 | **Tiêu phần B2** — `level` 5–8, `fill: paper`, `border: right`, `frequency: frequent` | rất thấp | an toàn | Chỉ là YAML. Mở ngay được hai chế độ điểm mầm của DocCreator hiện chưa từng xuất hiện. |
| 3 | `lighting_gradient` + `vignette` (E3) | thấp | an toàn | Nhiễu phổ biến nhất trong ảnh thật, repo hoàn toàn không có. |
| 4 | `misregistration` / `chromatic_aberration` (E1, E3) | thấp | an toàn | Nguồn nhiễu **màu** đầu tiên của repo. |
| 5 | `motion_blur` có hướng (D2) | rất thấp | an toàn | `blur` hiện đẳng hướng; rung tay thì không. |
| 6 | **E-VN-1 `carbon_copy`** | trung bình | an toàn | Tờ tới tay OCR thường là liên 2. |
| 7 | **E-VN-6 `screen_photo`** | trung bình | an toàn | Loại ảnh đang tăng nhanh nhất; dựng lại từ ba thứ đã có. |
| 8 | **E-VN-5 `quarter_fold`** | trung bình | an toàn nếu chỉ làm bóng | Bản rẻ của nhàu. |
| 9 | **Mở khoá hình học theo đường 1 của mục C**, bắt đầu bằng `CurlWarp` ở B4 | cao | **cần test giữ hộp** | Mở đường cho perspective, rotate, elastic, `displacement_crumple`, `rolling_shutter` — tức là hơn nửa danh sách E. |
| 10 | `textures/stain/` + mặt nạ rách thật (B3) | thấp, nhưng cần dữ liệu | an toàn | Đường vào đã mở sẵn trong mã, chỉ thiếu file. Vướng giấy phép ảnh. |

---

## Thêm một mô hình vào đây thì làm gì

1. Viết một file trong [`degradation/`](../degradation), **ghi rõ nguồn** (bài
   báo hay file gốc) ngay đầu docstring, theo lối
   [`capture.py`](../degradation/capture.py).
2. Đăng ký tên vào `DEGRADATIONS` trong
   [`degradation/__init__.py`](../degradation/__init__.py), kèm cờ `takes_rng`.
3. Khai vào một `chain` của
   [`rules/augmentation.yaml`](../rulebase/rules/augmentation.yaml) — **không
   khai thì không bao giờ chạy**, đó chính là cả mục B của tài liệu này.
4. `make preflight` đối chiếu tên trong luật với registry cả hai chiều.
5. `make showcase` sinh một ảnh trước/sau cho từng mô hình
   (`tools/degradation_showcase.py`, nhớ thêm mục vào `SHOWCASE`).
6. Nếu mô hình **dịch pixel**, nó phải trả về phép biến hình để `apply_recipe`
   áp lên hộp nhãn — xem mục C. Assert kích thước trong
   `generators/html/render.py` sẽ chặn nếu không.
