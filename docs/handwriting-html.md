# Nối chữ viết tay vào engine HTML

[`hoa-tiet-de-xuat.md`](hoa-tiet-de-xuat.md) gọi `handwriting_fill` là **khoảng
trống lớn nhất** của bộ dữ liệu: tờ mẫu sinh ra để được điền tay, mà mọi tờ sinh
ra đến giờ đều in máy toàn bộ. [`writevit.md`](writevit.md) dựng mô hình duy
nhất có trọng số tiếng Việt và đo xem nó viết được gì. Tài liệu này là **đoạn
dây nối hai đầu**, và — quan trọng hơn — **đo xem nối xong thì lấp được bao
nhiêu phần của khoảng trống ấy**.

Câu trả lời ngắn: **14,6 %** với mô hình, **100 %** với một mặt chữ viết tay có
giấy phép. Đoạn dây chạy được, ảnh ra đúng, nhãn không xê dịch một chữ nào;
nhưng mô hình để lại bảy phần tám số ô vẫn in máy, và **82 % số ô bị từ chối là
vì có chữ số**. Có hai nguồn mực vì thế, và chúng **không thay thế nhau**.

![Hai nguồn mực trên cùng một kiểu tờ: mặt chữ lấp hết, mô hình dừng ở chữ số](figures/handwriting-html.jpg)

*Dựng lại bằng `generators/html/.venv/bin/python docs/figures/make_handwriting_figure.py`, từ hai ảnh trong `samples/handwriting/`.*

## Nó là THUỘC TÍNH 7, không còn là một cờ dòng lệnh

Kể từ khi `rules/handwriting.yaml` tồn tại, **luật bốc mực bút cho từng trang**:
`typed` (chữ in) hoặc `hand_font`, và một lượt chạy bình thường ra một tập
**trộn** — khoảng 17 % số trang có nét bút, đo trên 3 000 lượt bốc. Trước đó
`--handwriting` là một cái công tắc cho cả lượt chạy: hoặc mọi trang đều điền
tay, hoặc không trang nào. Không tập thật nào trông như thế.

Ba điều đi kèm với việc nó là một thuộc tính:

* **Đứng trước `augmentation`.** Người ta điền vào tờ giấy rồi tờ giấy mới bị
  photo, nên nét bút mờ đi và nhoè ra **y như chữ in**. Đặt sau thì nét bút sẽ
  sắc nét nằm trên một trang đã cũ — cảnh "photo tờ mẫu trắng rồi mới điền",
  có thật nhưng là một cảnh khác.
* **`hand_*` `requires: [fillable]`**, thẻ của 25 bố cục thật sự có ô cho bút
  chạm tới. Đo chứ không đoán, và `tests/test_sheets.py` đo lại rồi so với thẻ.
* **`hand_model` và `hand_both` đang `enabled: false`** — có mặt, không bao giờ
  bốc trúng, vẫn gọi được đích danh. WriteViT là 294 MB không nằm trong kho, và
  bốc được nó nghĩa là ai clone kho về cũng phải tải trước khi chạy được.

```bash
# Luật tự bốc, tập ra trộn:
generators/html/.venv/bin/python generators/html/render.py --template auto -c 20 -o out/

# Ghim cả lượt chạy vào một nguồn mực (đây là cái `--handwriting` làm bây giờ:
# nó thêm `--force handwriting=hand_font`, nên BẢN GHI khớp với PIXEL):
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --handwriting font --layout invoice_hotel_stay -c 3 -o out/

python tools/writevit/setup.py                    # một lần, ~294 MB
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --handwriting model --layout invoice_hotel_stay -c 3 -o out/
```

`--handwriting` chỉ đi cùng `--template`: lưới ký tự vẽ một glyph một ô, không
có "chỗ trống" nào để điền. Không có WriteViT thì lệnh **dừng**, không có đường
lùi nào vẽ chữ thay — xem phần "Không có đường lùi" bên dưới.

`--handwriting` nhận tên nguồn mực: `model` (mặc định, WriteViT), `font`, hoặc
`both`. [`data/hand12/`](../data/hand12) là đợt thử, dựng bằng **`font`**: 12
trang, 6 bố cục, **159 ô điền tay, 0 ô in máy**. Cùng 12 trang ấy chạy bằng
`model` chỉ được **30 ô**, 129 ô còn lại vẫn in máy — chênh lệch ấy là toàn bộ
nội dung của tài liệu này.

Mực của mô hình có tập riêng để **đo** chứ không phải để huấn luyện:
[`data/hand18_model/`](../data/hand18_model), 18 bố cục × 1 trang bằng
`--handwriting model`. **30/191 run có mực (16 %)**, và **8/18 trang không có
một nét mực nào** — vì hai lý do khác hẳn nhau mà README của nó tách ra. Ngoài
ra còn `samples/handwriting/hand-filled-folio.jpg`, một tờ để nhìn.

## Ba nguồn mực

| | `model` | `font` | `both` |
| --- | --- | --- | --- |
| là gì | checkpoint WriteViT, sinh từng từ | mặt chữ viết tay trong `fonts/hand/` | model viết phần nó viết được, mặt chữ viết phần còn lại |
| đưa lên trang thế nào | ảnh PNG mực trong một `<img>` | **chữ thật**, trình duyệt dựng | cả hai, mỗi run một kiểu |
| phủ được | 14,6 % (tốt nhất một trang: 42 %) | **mọi ô** | **mọi ô** |
| chữ số, IN HOA, dấu câu | không | có | có (do mặt chữ gánh) |
| nét chữ | mỗi lần một khác, 106 người viết | một mặt chữ; mọi `a` giống hệt nhau | **hai nét chữ trên cùng một trang** |
| xuống dòng | không — ảnh không ngắt dòng được | có, và hộp cắt theo từng dòng | chỉ phần mặt chữ |
| chạy trên WeasyPrint | **không** — xem dưới | có | **không** — cùng lý do với `model` |

Cả hai đường đều là đường `hoa-tiet-de-xuat.md` nêu là hợp lệ: **dữ liệu nét
thật, hoặc một mặt chữ viết tay có giấy phép cho phép phát hành lại.** Cái bị
gỡ ở `ff9a9f0` là đường thứ ba — lấy mặt chữ **in** rồi làm lệch từng ký tự —
và không có gì ở đây làm lệch một ký tự nào.

Điều phải nói thẳng là **mặt chữ thì lặp**. Một tờ là một nét chữ, và có hai
mặt chữ chứ không phải 106 người viết. Một tập dựng bằng `--handwriting font`
phải khai điều đó, và `record["handwriting"]["source"]` khai.

`FontHand` đặt chữ bằng CSS chứ không dán ảnh, nên run vẫn là nút văn bản: hai
chỗ đọc hộp không cần biết nguồn mực này tồn tại, và một giá trị dài vẫn **xuống
dòng** rồi được cắt hộp theo dòng — thứ một ảnh mực không làm được.

Nhờ đúng chỗ ấy mà **đường WeasyPrint chạy được với nguồn `font`**:

```bash
generators/genalog/.venv/bin/python generators/genalog/render.py \
    --template auto --handwriting font --jobs data/hand12/jobs.json -o out/
```

Đo trên 12 trang của `jobs.json`, hai renderer cùng nội dung:

| | |
| --- | --- |
| hộp | 1 219 (html) / 1 224 (genalog) |
| nhãn giống nhau giữa cặp | **12/12** |
| run có nhãn WeasyPrint dựng lại được | 1 099/1 155 — **bằng đúng bản không viết tay** |
| `check_boxes` | sạch cả hai renderer |

Con số cuối là con số đáng giá: điền tay **không làm mất một run nào**. 4,8 %
còn thiếu là khoảng cách vốn có, do run bị xuống dòng — xem mục cuối tài liệu.

### Một cái bẫy mất 81 hộp mà không báo lỗi

Bản đầu của `FontHand` nhích chữ khỏi dòng kẻ bằng `position:relative` + `top`.
Trên trình duyệt trông đúng. Trên WeasyPrint, định vị tương đối vẽ ở **lượt xếp
chồng sau**, nên mọi run đã điền rơi xuống **cuối** lớp text của PDF thay vì
nằm đúng thứ tự tài liệu — và `match_runs` đi theo thứ tự ấy. Một tờ hoá đơn
GTGT ra **16 hộp thay vì 97**, không một dòng lỗi nào. Nhích bằng
`vertical-align` — dịch chuyển inline, không tạo ngữ cảnh xếp chồng — và
`tests/test_handwriting.py` giữ cho nó không quay lại.

`fonts/hand/` có hai mặt chữ, cả hai OFL 1.1 và cả hai qua được
`check_fonts.py`. Việc kiểm tra ấy không phải thủ tục: **Caveat — lựa chọn hiển
nhiên cho nét chữ thường — thiếu 80 ký tự tiếng Việt** và sẽ vẽ ra ô vuông rỗng
trong khi nhãn vẫn khai là đã viết. Xem [`fonts/README.md`](../fonts/README.md).

## `both` — và cái giá của nó, đo chứ không giấu

`both` sinh ra vì một họ tờ giấy: [`notebook_ledger`](../generators/html/sheets/notebook.py),
quyển vở kẻ ngang mà **không một chữ nào được in ra trước**. Trên tờ in sẵn,
một run bị bỏ lại thành chữ in vẫn đúng — nó vốn được in sẵn. Trên quyển vở thì
sai: đó là một dòng tiêu đề không ai đánh máy cả.

Mà một mình checkpoint thì không gánh nổi quyển vở. Đo trên 5 hạt giống của
`notebook_ledger`: **17/226 run (8 %)** và **256/2 755 ký tự (9 %)** là viết
được; lý do từ chối là `{digit: 152, allcaps: 44, alphabet: 13}` — sổ bán hàng
là tiền, ngày và số lượng. Một trang do model viết một mình là chín phần đánh
máy.

Nên `both` ghép hai nguồn theo từng run: cái nào model viết được thì model
viết, còn lại mặt chữ viết. **Không run nào còn là chữ in.** Đo lại trên hai
trang vừa dựng (`--seed 4100 --layout notebook_ledger`):

| | trang 1 | trang 2 |
| --- | --- | --- |
| run đã viết | 50/50 | 43/43 |
| `by_source` | `{font: 50}` | `{font: 40, model: 3}` |
| còn là chữ in | 0 | 0 |

`record["handwriting"]["by_source"]` khai đúng con số ấy cho từng trang, và
`kinds` khai trang này được mời viết những run nào (`"all"` với quyển vở, danh
sách `HAND_KINDS` với tờ in sẵn) — không có nó thì "3 viết, 40 in" không phân
biệt được với "40 run kia vốn không phải phần người ta viết".

**Hai nét chữ trên một trang là một cái giá thật.** Không có bản phát hành nào
vừa điều kiện được nét chữ vừa viết được chữ số:
[VATr++](https://github.com/EDM-Research/VATr-pp),
[One-DM](https://github.com/dailenson/One-DM) và
[DiffusionPen](https://github.com/koninik/DiffusionPen) đều điều kiện được nét
chữ nhưng đều huấn luyện trên ảnh cắt từ IAM — tài liệu của chính DiffusionPen
nói "punctuation and digits are not rendered natively because DiffusionPen's
training crops do not contain them".
[pytorch-handwriting-synthesis-toolkit](https://github.com/X-rayLaser/pytorch-handwriting-synthesis-toolkit)
(Graves LSTM, MIT, chạy CPU) **có** chữ số và dấu câu nhưng **không điều kiện
được nét chữ**, nên ghép nó vào cũng vẫn là hai nét chữ. Việc đó là ngõ cụt
chứ không phải việc chưa làm.

### Một thứ đã sửa được: hai nét chữ, nhưng một cỡ chữ

Bản đầu ghép xong thì phần model **to hơn hẳn** phần mặt chữ — đọc ra như hai
người viết chứ không phải một người. Nguyên do là `INK_HEIGHT_EM` và hệ số cỡ
chữ của từng mặt chữ được chuẩn **riêng lẻ**, mỗi cái so với ô của một tờ in
sẵn, và chưa bao giờ có gì bắt chúng khớp nhau; đo trên trang đã dựng, chiều
cao chữ x của model gấp khoảng **1,5 lần** của mặt chữ.

`BothHands._matched_height` sửa đúng chỗ đó: ô mực phủ `above + 1 + below` lần
chiều cao chữ x, nên đặt chiều cao ô bằng `x_height × (above + 1 + below)` là
đặt chữ x của model trùng chữ x của mặt chữ. `x_height` đọc từ bảng `OS/2` của
chính mặt chữ, không đoán. `tests/test_handwriting.py` kiểm tỉ lệ ấy bằng 1.

### Một thứ chưa sửa được, và không nên đoán

Checkpoint viết **rõ ràng** những từ tiếng Việt và viết **nát** những tên
thương hiệu không phải tiếng Việt. Cùng một người viết (writer 30), cùng một
hạt giống:

```
WinMart  Pulppy  Zealand  Emart   ->  kirWlart  Duegpy  Dcalana  Smart
Khăn giấy  Gừng ta  Gạo túi       ->  đọc được hết
```

Nhãn vẫn khai `WinMart`, còn ảnh thì không phải chữ ấy — nên đây là lỗi thật,
và nó có từ trước `both` chứ không phải do `both` (nguồn `model` một mình cũng
thế). Cái bẫy là **giả thuyết dễ nhất lại sai**: không phải "từ ngoài từ điển".
`Nguyễn` không có trong 10 131 từ của `vn_words.txt` mà vẫn viết ra đọc được,
nên một guard theo từ điển sẽ từ chối đúng những cái tên mà tính năng này sinh
ra để viết. Ranh giới thật gần với "có phải chính tả tiếng Việt không", và chưa
có số đo nào đủ để dựng luật ấy. Ghi lại ở đây thay vì đoán một luật.

## Đoạn dây gồm ba mảnh

```
rulebase ─► sheets/ ─► handwriting.fill ─► Chromium ─► degradation
   nội dung   tờ in sẵn      điền tay         ảnh        làm cũ
                                 │
                          tools/writevit/serve.py
                          (tiến trình WriteViT sống suốt lượt chạy)
```

**`tools/writevit/serve.py`** — tiến trình sống lâu, mỗi dòng stdin một yêu cầu
JSON, mỗi dòng stdout một câu trả lời. Lý do nó tồn tại là con số trong
`writevit.md`: `infer.py` mất **11 giây một lượt gọi**, gần như toàn bộ là nạp
checkpoint 97 MB và `VN.pickle` 193 MB. Trả cái giá ấy cho từng ô, hay cả cho
từng trang, là trả toàn bộ giá của tính năng. Giữ mô hình trong bộ nhớ thì đúng
là cách `HtmlReceiptRenderer` giữ một Chromium cho cả lượt chạy.

**`generators/html/handwriting.py`** — chính sách và phép ghép. Nó quyết định ô
nào điền tay, gọi worker, tô màu mực, và **viết lại markup**. Nó không import
numpy hay Pillow ở mức module: nửa chính sách là hàm thuần trên chuỗi, và CI
chạy bộ test chỉ với pytest và PyYAML.

**Một lượt viết lại markup, không phải một họ tờ giấy thứ bảy.** Tờ mẫu được in
trước, người ta điền sau — nên mực cũng đi sau, quét một lượt trên markup đã
dựng xong. Nhờ vậy **cả sáu họ trong `sheets/` đều điền tay được** mà không họ
nào phải biết mực là gì.

## Chính sách: mỗi ô một quyết định

Một từ viết được khi checkpoint thật sự viết được nó — ba điều kiện, cả ba đều
đã đo trong `writevit.md`, và đo lại trực tiếp một lần nữa ở đây:

| yêu cầu | ví dụ hỏng | máy viết ra |
| --- | --- | --- |
| không có chữ số | `0956100526` | `DtSơeii Bới` |
| không IN HOA toàn từ | `LÊ QUANG ĐẠO` | `Lã ạ̀ựnhị trờ` |
| mọi ký tự trong `ALPHABET` | `15/06/2018` | (chặn sớm: không có `/`) |

`Lê Quang Đạo` viết hoa đầu từ thì ra đúng `Lê Quang Đạo`. Chỗ hỏng là chữ hoa
**toàn phần** và chữ số, không phải chữ hoa nói chung.

Quyết định lấy **theo ô, không theo từ**. Một dòng nửa mực nửa chữ in không phải
là tờ giấy ai điền tay, và trộn hai thứ trong một run có nhãn còn cắt một hộp
ground-truth làm đôi.

`handwriting.ALPHABET` là bản chép của bảng chữ trong checkpoint, để engine
quyết định được mà không phải import torch. Bản chép lệch thì sẽ từ chối nhầm,
hoặc tệ hơn là hỏi nhầm — nên worker gửi kèm bảng chữ của nó trong dòng "ready"
và `Hand.open` đối chiếu, một lần mỗi lượt chạy.

## Lấp được bao nhiêu — đo trên 16 bố cục, 20 hạt giống mỗi bố cục

2.954 run thuộc ba `data-kind` mà người ta điền tay (`invoice.field`,
`invoice.words`, `sign.name`):

| | run | % |
| --- | ---: | ---: |
| **viết được** | **432** | **14,6 %** |
| bị chặn vì chữ số | 2.075 | 70,2 % |
| bị chặn vì IN HOA | 418 | 14,2 % |
| bị chặn vì ký tự ngoài bảng | 29 | 1,0 % |

Theo bố cục, và đây là chỗ đáng nhìn nhất:

| bố cục | viết được | ghi chú |
| --- | ---: | --- |
| `invoice_hotel_stay` / `_compact` | 30,0 % | tên khách, loại phòng, nguồn khách, **hai tên ký** |
| `invoice_tax_en` | 25,7 % | |
| `invoice_vat_form` | 20,6 % | tên người mua, hình thức thanh toán, tiền bằng chữ |
| `authorisation_letter` | 12,7 % | **tờ dựng ra để điền tay, và điền được đúng một ô** |
| `medical_statement` | 8,3 % | |
| `invoice_export` | 4,0 % | tên hàng IN HOA, còn lại là số |

`authorisation_letter` là chỗ mỉa mai nhất và vì thế đáng in ra: file bố cục của
nó viết thẳng *"đây là tờ để ĐIỀN TAY, và dòng chấm là chỗ để điền"*, thế mà
mười ô trong khối trường là số CMND, ngày cấp, mã số tư vấn, số điện thoại, số
tiền — cộng thêm hai ô họ tên mà chính tờ giấy bắt viết **(CHỮ IN HOA)**. Chỉ
"Bằng chữ" là viết được.

## Bức tường chữ số, và tại sao không trèo qua được bằng mẹo

`writevit.md` đã nói vì sao mô hình không viết được chữ số, và nói thêm rằng
`VN.pickle` **có** 2.579 nhãn chứa chữ số, nên huấn luyện tiếp là làm được. Đúng
— nhưng chỉ đúng cho **huấn luyện tiếp**. Đường tắt hiển nhiên là cắt luôn ảnh
chữ số thật trong `VN.pickle` ra rồi ghép thành số. Đường ấy **đã đo và đã
chết**:

| | train | test | val |
| --- | ---: | ---: | ---: |
| ảnh nhãn một chữ số | 614 | 188 | 125 |
| trong đó là chữ **`0`** | **1** | **0** | **0** |
| người viết có đủ cả mười chữ số | 1 / 106 | 0 / 60 | 0 / 34 |

Cả kho VNOnDB có **đúng một** ảnh chữ số `0` viết rời. `1.500.000` có bốn số
không. Ghép chúng lại thì bốn cái giống hệt nhau đến từng điểm ảnh, và tờ giấy
tự tố cáo. Còn ghép từ nhiều người viết thì một con số gồm bốn nét chữ của bốn
người — nhìn ra ngay.

Nhãn nhiều chữ số thì có 143 chuỗi khác nhau (`000`, `2005`, `150`…), nhưng phủ
chưa tới 5 % số nhóm ba chữ số, và cắt chữ số ra khỏi một ảnh nhiều chữ số thì
lại là bài phân đoạn.

Nên: **chữ số cần một đợt huấn luyện, không có mẹo thay thế.** Đó là một câu
đã đo, không phải một phỏng đoán.

### Checkpoint tiếng Anh cũng không

Đường tắt thứ hai ai cũng nghĩ tới: `eng_ckpt.pth` học từ IAM, mà IAM là chữ
viết tay tiếng Anh — chữ số thì hình dạng nào cũng như nhau. Đã tải về và chạy
thử (lấy ảnh mẫu phong cách từ `VN.pickle` qua `--style-dir`): `0 1 2 3 4 5 6 7
8 9` ra một dãy nét giống chữ cái, `1500000` ra một nét ngoằn ngoèo. Cùng một
lỗi, cùng một nguyên nhân — `File/english_words.txt` có 466.550 token, bộ lọc
`word.isupper() or word.isdigit()` đẩy 5.643 token sang `lex_upper_number`, và
trong 460.907 token còn lại chỉ **26 token** chứa chữ số (`10th`, `1st`,
`2,4-d`…). Bộ sinh tiếng Anh cũng gần như chưa từng thấy chữ số.

### Trần là 42 %

Quét 11 bố cục có ô trường × mọi tuỳ chọn `content` hợp lệ × 40 hạt giống:
trang nhiều mực nhất trong toàn bộ không gian luật là **42 %** — folio khách
sạn, 5/12 ô. Ghim `content` xoá sạch nhóm bị chặn vì IN HOA (chữ hoa toàn phần
đến từ `prob_uppercase`/`prob_ascii_fold`, không phải từ tài liệu), và thứ duy
nhất còn đứng lại là chữ số. Trang ấy nằm ở
[`samples/handwriting/`](../samples/handwriting) để nhìn.

**Một trang 100 % điền tay không dựng được từ mô hình**, và không phải vì chưa
tìm đúng hạt giống: mọi hoá đơn trong kho đều mang số hoá đơn, ngày, mã số thuế,
số tài khoản. Đó là thứ tài liệu này *là*. Muốn 100 % thì hoặc đổi nguồn mực
sang `font`, hoặc huấn luyện lại checkpoint.

### Còn dấu ngăn thì sao

`Tân Mai - Biên Hoà - Đồng Nai` bị chặn vì dấu gạch nối, mà gạch nối là một
**nét**, không phải hình dạng chữ — vẽ nó không rơi vào cái bẫy của `ff9a9f0`.
Đã đo: vẽ tay dấu ngăn nâng độ phủ từ 14,6 % lên **15,8 %**. **1,2 điểm.** Không
làm, và đây là lý do được ghi lại chứ không phải bị bỏ quên.

## Không có đường lùi

`ff9a9f0` ("Drop the hand marks: a jittered typeface is not handwriting") đã gỡ
cả họ nét tay vì cách dựng sai từ gốc: lấy mặt chữ in rồi làm lệch từng ký tự,
ra chữ in bị rung. Module này **không có nhánh nào vẽ chữ**. Mọi nét trên trang
đều từ bộ sinh WriteViT, hoặc ô ấy giữ nguyên chữ in. Không tìm thấy checkpoint
thì `render.py` dừng ngay lúc khởi động, chứ không lặng lẽ sinh ra một tập ảnh
in máy mà metadata khai là viết tay.

## Hộp nhãn vẫn là hộp nhãn

Một ô đã điền tay không còn nút văn bản trong DOM — nó có một `<img>`. Nên nó
mang thêm `data-text`, và hai chỗ đọc hộp đọc thuộc tính đó khi có:

* `CELL_RECTS_JS` (`page.py`) — vốn đã đo `span.firstElementChild || span`, nên
  **quad tự nhiên là hộp của ảnh mực**, không cần sửa gì về hình học;
* `_Runs` (`sheets/__init__.py`) — đường WeasyPrint đọc run từ markup.

Không đổi gì khác trong hai engine. Tính chất quan trọng nhất — **điền mực không
làm đổi tờ giấy nói gì** — có test riêng trên sáu họ tờ giấy:
`sheets.labelled_runs` trước và sau khi điền phải bằng nhau từng cặp. Nếu nó
lệch, `check_boxes` sẽ báo mọi ảnh viết tay là mất trường; nếu nó lệch **im
lặng**, nhãn sẽ mô tả một tờ giấy chưa từng được vẽ.

Đo trên `data/hand12/`: **1.219 hộp, 12 ảnh, `check_boxes` sạch** — mọi hộp nằm
trong khung và mọi hộp đè lên mực.

## Ghép mực lên giấy

Ba việc nhỏ, mỗi việc có một lý do đo được.

**Nền phải trong suốt.** WriteViT sinh chữ đen trên nền trắng. Dán đè thì dòng
kẻ chấm dưới ô bị xoá trắng. `alpha = 255 - giá trị điểm ảnh`, đúng như
`writevit.md` dặn, rồi tô màu bút — xanh mực là chính, đen ít hơn.

**Không được thu nhỏ ảnh mực.** Bản đầu của `compose` chọn tỉ lệ sao cho một từ
dùng **hết** dải chữ giữ nguyên 32 px của bộ sinh. Nhưng phần lớn từ không dùng
hết dải: `Chu Văn Lâm` không có nét nào thõng xuống, nên cả dòng ra 25 px, rồi
trình duyệt phóng ngược lên ~35 px mà ô trường dành cho nó — **thu rồi phóng**,
và nét mất cạnh. Đo trên một ô: trung bình nét đi từ 91 (đầu ra của mô hình) lên
133 trên trang. Lấy `max(chiều cao / dải)` thay vì `max(chiều cao) / dải trọn`
thì từ nào lẽ ra bị co nhiều nhất sẽ giữ nguyên điểm ảnh, mọi ảnh còn lại được
phóng lên — không ảnh nào bị thu. Trung bình nét về 122.

Có thử **ghép ở độ phân giải cao hơn** rồi để trình duyệt thu xuống, theo lập
luận thu thì giữ cạnh tốt hơn phóng. Đo ở 1×, 2×, 3×, 4×: lệch 7 điểm và
**không đơn điệu** — nhiễu, không phải tín hiệu, vì nguồn có 32 px mà ô cho 35.
Không đưa vào.

**Phần lớn chỗ nhạt còn lại là màu bút, không phải phép lấy mẫu.** Ghép alpha
lên giấy trắng cho `giá trị = bút·a + 255·(1−a)`, nên với bút `#1a1a20` (độ sáng
27) thì nét đậm nhất **không bao giờ** xuống dưới 27, và trung bình 91 của mô
hình thành 108. Đó là chủ ý — bút bi không đen tuyệt đối — nhưng nó là yếu tố
lớn nhất, và nói ra thì hơn để người đọc tự đoán. `INK_GAMMA = 0.8` bẻ phần phủ
một phần về phía đục, lấy lại chừng ba điểm tương phản; quét tới 0,5 thì nét phủ
19,2 % ô trong khi bản gốc phủ 15,9 % — lúc ấy không còn là ghép nét của mô hình
mà là làm dày nó, nên dừng ở 0,8.

**Các từ phải chung một dòng kẻ chân.** Đây là chỗ đáng kể nhất. WriteViT cắt
sát từng từ rồi kéo về 32 px, nên `Tiền` và `mặt` trả về **cùng chiều cao** dù
`mặt` không có nét vươn lên. Nối thẳng hai ảnh ấy ra một dòng đọc như hai cỡ chữ
khác nhau. Chiều cao chữ x không đọc lại được từ ảnh, nên nó được **suy từ chính
các chữ cái** — từ này vươn lên bao nhiêu (chữ cao `b d đ h k l t`, chữ hoa, hay
chỉ một dấu trên `ề`), thõng xuống bao nhiêu (`g j p q y`, hay dấu nặng) — rồi
mỗi ảnh được co về đúng phần của nó và đặt sao cho các chân chữ trùng nhau.

**Cỡ chữ và chỗ ngồi trên dòng kẻ.** Một người viết một cỡ cho cả tờ, nên cỡ
chữ bốc một lần mỗi trang. Chỗ ngồi so với dòng kẻ thì bốc **từng ô**, vì đó
đúng là thứ tay người không giữ đều.

Ảnh mực khai chiều rộng bằng `em` và để chiều cao chạy theo, nên ô hẹp hơn nét
chữ sẽ **thu nhỏ cả nét** thay vì bóp ngang — `height` cộng `max-width` sẽ bóp.

## Chỗ chưa nối

* **Mực của mô hình trên đường WeasyPrint.** `generators/genalog/` dựng lại hộp
  bằng `match_runs`, đi song song giữa danh sách run và **lớp glyph của chính
  file PDF**. Một ô mực của mô hình là một `<img>`, không góp glyph nào, nên hai
  dãy lệch nhau ngay ở ô đầu tiên và mọi run sau đó nhận nhầm hộp — đúng kiểu
  hỏng mà commit `forms16` đã tả. Nối được, nhưng phải dạy `match_runs` biết có
  run lấy hộp từ khối ảnh; chưa làm, nên `--handwriting` ở genalog chỉ nhận
  `font` và từ chối `model` bằng tên.
* **`sign.name` chỉ có ở tờ lưu trú.** Bốn ô ký của `authorisation_letter` đều
  đề *"(Ký và ghi rõ họ tên)"* và đều để trắng, vì `signature_names` không bật
  cho tài liệu ấy. Bật nó là đổi `ground_truth()`, tức là đổi nhãn của mọi ảnh
  cũ — một việc thuộc `rulebase/`, không thuộc đoạn dây này.
* **Chữ ký ngoằn ngoèo** (`signature_scrawl`) vẫn chưa có gì. Chữ ký là một
  động tác đã luyện thành nếp, không phải một từ; WriteViT không sinh ra nó.
* **Chữ số trong mực của mô hình.** `font` lấp được chỗ ấy nhưng bằng một mặt
  chữ lặp lại; chỉ **huấn luyện tiếp WriteViT** cho `lex_upper_number` mới cho
  chữ số bằng nét sinh, và việc đó cần GPU.
* **Điều khoản dữ liệu.** Trọng số học từ VNOnDB. Trước khi công bố ảnh sinh ra
  thì thứ phải đọc là điều khoản phát hành lại của **dữ liệu**, không phải giấy
  phép MIT của **mã**. Câu này đã có trong `writevit.md` và được nhắc lại ở đây
  vì giờ đã có ảnh thật để công bố.

## Một lỗi tìm thấy trên đường, không thuộc phần này

`tools/check_boxes.py` báo thiếu hộp cho một run bị **xuống dòng**.
`CELL_RECTS_JS` cố ý cắt một run tràn hai dòng thành hai hộp — đó là hành vi
đúng và có lý do viết trong `page.py` — nhưng `check_image` chờ đúng một hộp mỗi
run, nên nó báo `menu.name "ÁO SƠ MI NAM DÀI TAY (MEN'S LONG-SLEEVE SHIRT)"` là
mất hộp trong khi hai nửa của nó đều có hộp. Đây là **lỗi có sẵn**, tái hiện
được với `--layout invoice_export --seed 2026` mà không cần bật `--handwriting`.
`data/hand12/` dùng hạt giống khác để đợt thử này sạch; sửa công cụ là việc
riêng.
