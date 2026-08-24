# Chữ ký: khảo sát mẫu trước, rồi mới dựng engine kéo giãn

[`hoa-tiet-de-xuat.md`](hoa-tiet-de-xuat.md) đếm những thứ có trên tờ giấy thật
mà bộ dữ liệu này chưa có. `handwriting_fill` đã được lấp bằng
[`handwriting-html.md`](handwriting-html.md). Còn **một ô trống nữa, và nó nằm
ngay dưới mỗi cái tên in**: khối chữ ký. Mọi bố cục trong rule space đều in ra
chú thích *(Ký, ghi rõ họ tên)* rồi để trắng — và cái để trắng ấy, trên tờ giấy
quay về, **không bao giờ trắng**.

Tài liệu này ghi lại hai việc, theo đúng thứ tự đã làm: **khảo sát xem chữ ký
là cái gì**, rồi **biến từng phát hiện thành một tham số hình học**. Không có
tham số nào trong `generators/html/signature.py` mà không truy được về một dòng
trong bảng dưới đây; những chỗ là **phán đoán** chứ không phải đo đạc thì được
ghi thẳng là phán đoán, ngay tại chỗ khai báo.

![18 chữ ký, 18 hạt giống](../samples/signatures/styles.jpg)

## Vì sao đây không phải là thứ đã bị gỡ ở `ff9a9f0`

Đây là câu hỏi phải trả lời đầu tiên, vì kho này đã từng từ chối đúng một việc
nghe rất giống việc đang làm.

`ff9a9f0` lấy **mặt chữ in**, làm lệch từng ký tự, rồi gọi kết quả là chữ viết
tay. Nó bị gỡ vì cái ra được là *chữ in bị run tay*: hình dạng nét vẫn là hình
dạng nét của một mặt chữ in, và không có lượng jitter nào sửa được điều đó.
`handwriting.py` từ đó không nhúc nhích một glyph nào.

Điều khẳng định ở đây hẹp hơn, và khác về bản chất: **chữ ký tự nó đã là một
phép biến dạng.** Mọi nguồn khảo sát bên dưới đều mô tả nó giống nhau — chữ cái
đầu phóng to quá cỡ, phần thân bị giản lược hoặc bỏ hẳn, nét cuối kéo dài và
hất lên, cộng thêm một nét hoa **không thuộc về chữ cái nào cả**. Biến dạng
không phải lớp ngụy trang phủ lên chữ viết; **nó chính là chữ ký**, và nó là
phần duy nhất của chữ ký có thể phát biểu được bằng hình học.

Nói ngắn: `ff9a9f0` làm lệch chữ in để **giả vờ** thành chữ viết. Engine này
kéo giãn chữ viết để thành **chữ ký**, là thứ mà chữ ký vốn dĩ được tạo ra như
thế.

## Khảo sát: chữ ký khác chữ viết ở chỗ nào

Mười lượt tìm, bốn nhóm nguồn: giám định tài liệu (forensic document
examination), bút tướng học (graphology), thư pháp con chữ (calligraphy stroke
construction), và hai nhóm thực dụng hơn — các hướng dẫn **tạo chữ ký tiếng
Việt**, và các **bộ dữ liệu chữ ký offline** (GPDS, CEDAR, MCYT) mà giới nhận
dạng dùng làm chuẩn.

| Phát hiện | Nguồn | Thành tham số nào |
| --- | --- | --- |
| Chữ ký có **ba vùng**: nét đầu lớn, thân giản lược, nét cuối hất lên | giám định + hướng dẫn VN | `CAP_STRETCH`, `BODY_SQUEEZE`, `FLOURISH` |
| "Chữ ký bắt đầu với nét chữ lớn… nét kết thúc được nâng lên" | hướng dẫn chữ ký VN | `CAP_STRETCH` = 1,35–2,40 x-height; `RISE` |
| Nét đầu và nét cuối được giám định **thành một cặp** đặc điểm cá nhân | giám định | `LEAD` + `FLOURISH` |
| Giản lược là **quá trình tích lũy**; viết nhanh thì giản lược mạnh | giám định | `BODY_FADE`, nhân theo số chữ cái |
| Nét nghiêng về trước; chữ viết thường 60–75° so với phương ngang, thư pháp đặt trục ô-van ở 55° | bút tướng + thư pháp | `SLANT` = 5°–25° lệch khỏi phương thẳng đứng |
| Đường chân chữ **đi lên** là phổ biến nhất, đi xuống là hiếm | bút tướng | `BASELINE`, trọng số 5/3/2/1 |
| **Paraph** — nét gạch/nét hoa dưới tên — là *một phần của chữ ký*, không phải trang trí | giám định (thuật ngữ AHAF) | `PARAPH`, 5 kiểu |
| Chữ cái nối liền nhau; **nét nối là một nét riêng**, không phải khoảng cách âm | giám định | `CONNECTED` + `_connectors` |
| Chữ ký khó đọc là bình thường, phổ biến nhất ở người ký nhiều lần mỗi ngày | phân tích chữ ký | `LEGIBILITY`, 4 mức |
| Phần thân bị **giản lược hoặc bỏ hẳn** | giám định | `SCRAWL`, `SURVIVES`, `_scrawl` |
| **Chuyển động sống lâu hơn hình dạng**: chữ chết rồi vẫn giữ hướng nét | giám định | `_slot_up` / `_slot_down` / `_slot_hump` |
| Người Việt thường ký **tên** (từ cuối), kéo dài chữ cái đầu của nó | hướng dẫn chữ ký VN | `parts_of` + `legibility="given"` |
| Nét xuống dày, nét lên mảnh; nét vào và nét ra thon lại thành mũi | thư pháp | `ribbon(w0, w1, bulge)` |
| Ô thu mẫu chuẩn: GPDS 5×1,8 cm và 4,5×2,5 cm; CEDAR 50×50 mm | bộ dữ liệu offline | `ASPECT` = 1,8–3,0, **chỉ để báo cáo** |
| Chữ ký lệch khỏi dòng kẻ của tờ giấy, và mỗi người ký một cỡ | giám định (kích cỡ là đặc điểm cá nhân) | `SIZE`, `TILT`, `DRIFT` — **dải là phán đoán** |
| Viết nhanh thì rụng dấu phụ | giám định (giản lược) | `MARKS` = 0,34 — **tỷ lệ là phán đoán**, không phải số đo |

Hai điều đáng nói về bảng này.

**Cột thứ ba là toàn bộ engine.** Không có tham số nào ngoài bảng, và mỗi hằng
số trong `signature.py` đều có một chú thích trỏ về đúng dòng ở đây.

**Trọng số thì không đo được.** Khảo sát nói rằng cả bốn mức dễ đọc đều xảy ra
và đọc được hoàn toàn là thiểu số; nó **không** nói bốn mức chia nhau bao nhiêu
phần trăm. Chỗ nào con số là phán đoán, khai báo trong mã nguồn viết thẳng
`WEIGHTS ARE A JUDGEMENT` bằng chữ hoa. Đó là ranh giới giữa "đọc được từ nguồn"
và "chọn cho hợp lý", và nó phải nhìn thấy được từ chỗ khai báo, không phải chỉ
ở đây.

## Chữ thôi không còn là chữ

Đây là phần phải làm hai lượt mới đúng, và đáng ghi lại vì sao.

**Lượt một sai.** Bóp hẹp một chữ rồi cho nó nhỏ dần thì nó vẫn là một chữ:
engine ra những dấu ký đọc được thành `Nguyễn Thị Bích Ngọc` bằng một nét hơi
nghiêng. Mà **một chữ ký đọc được rành mạch như thế thì không phải là thứ quay
về trên tờ giấy.** Khảo sát đã nói điều này ngay từ đầu, chỉ là lượt một mới
đọc một nửa của nó.

Nửa còn lại, nói bằng ba giọng khác nhau: phần thân *bị giản lược hoặc bỏ hẳn*;
chữ ký khó đọc là bình thường và phổ biến nhất ở người ký nhiều lần mỗi ngày —
tức là chính những người ký các tờ giấy mà kho này sinh ra; và câu hữu dụng
nhất, từ giám định: **chuyển động sống lâu hơn hình dạng.** Một chữ `g` đã chết
vẫn cắm xuống dưới dòng, một chữ `l` đã chết vẫn quăng một vòng lên trên.

Nên một dấu ký ở đây có **phần đầu là chữ** và **phần đuôi là một nét lượn
chạy**:

| | |
| --- | --- |
| `head_and_tail` | quyết định bàn tay buông ở đâu |
| `SURVIVES` = 1–2 | số chữ giữ được hình trước khi buông |
| chữ IN HOA | **không bao giờ tan** — chữ lồng là phần cố ý cho người ta đọc |
| `_scrawl` | dựng nét lượn từ **lớp** của những chữ nó thay, không phải từ nhiễu |
| `SCRAWL_SLOTS` = 6 | nét lượn **ngắn hơn cái tên** — buông chín chữ thì không đặt xuống chín cái bướu |

Chỗ "từ lớp của chữ" là điểm mấu chốt. Chữ trong `TAIL_LETTERS` (g j p q y) để
lại một vòng cắm xuống; chữ trong `TALL_LETTERS` (b d h k l t) và chữ hoa để
lại một vòng vắt lên; còn lại là một cái bướu. Vì thế nét lượn thay cho "uyễn"
và nét lượn thay cho "ọc" là **hai nét khác nhau**, chứ không phải một cái
ngoằng dùng chung.

Đo trên engine hiện tại, 300 hạt giống × 5 tên: **222 tan thành nét lượn, 39 là
chữ lồng toàn chữ hoa** (loại này *cố ý* đọc được — ba chữ cái đầu là để đọc),
**39 giữ nguyên mọi chữ** (một phần mười số người ký). Có test giữ đúng phân bố
ấy, vì một lần chỉnh tham số vô tình kéo nó về phía đọc được sẽ không làm hỏng
bất kỳ test nào khác trong tệp.

Hai chi tiết nữa cũng chỉ lộ ra khi nhìn ảnh, cùng lượt: nét lượn phải **mảnh
hơn và thưa hơn nét chữ** (vẽ dày và dày nhịp thì các bướu dính vào nhau thành
một cái nêm đặc); và bề rộng bướu với chiều cao bướu phải rút **hai số ngẫu
nhiên riêng** — dùng chung một số thì chúng cùng phình cùng xẹp, ra một đường
răng cưa chứ không ra chữ.

## Hai nguồn mực

Engine không vẽ chữ cái. Nó lấy **chữ thật** rồi kéo giãn — và chữ thật đến từ
một trong hai chỗ, đúng hai chỗ mà `handwriting.py` đã có:

| | `font` | `model` |
| --- | --- | --- |
| là gì | đường viền glyph trong `fonts/hand/` | mực WriteViT, **trace thành contour** |
| nét | của một mặt chữ, dù kéo giãn thế nào | **mỏng, nối liền, do mô hình sinh** |
| khác nhau mỗi lần | không — mọi chữ `a` giống hệt nhau | có, 106 kiểu người viết |
| chữ số, IN HOA | viết được | **không** — xem `writevit.md` |
| chuỗi chữ hoa liền (`LQĐ`) | viết được | **không** — nên không bao giờ được hỏi |
| cần gì | không gì cả | clone 1,7 GB, ~7 giây mỗi từ trên CPU |
| mặc định | ✔ | |

Không phải một cái hơn cái kia. `model` viết một cái tên rất đẹp và **không**
viết nổi `LQĐ`; `font` viết được mọi thứ nhưng lần nào cũng y hệt lần nào.

Chỗ khác biệt ấy rơi vào **kiểu chữ ký, không rơi vào mực**. Nguồn mực khai báo
nó vẽ được kiểu nào trong bốn kiểu khảo sát nêu, và `Style` bốc từ đúng những
kiểu ấy — nên model **không bao giờ bị đưa cho một chữ lồng để rồi từ chối**.

Thứ tự trước đây ngược lại, và nó tốn 11 trên 18 hạt giống mẫu: bốc kiểu trước,
model từ chối, dấu ký quay về mực mặt chữ. Một lượt chạy xin mực model mà nhận
về phần lớn là mặt chữ thì cờ ấy không có nghĩa gì. `fill` vẫn còn đường lùi
theo từng khối, nhưng là **lưới an toàn chứ không phải đường đi chính** — đo
trên toàn bộ kho tên × 2000 hạt giống: **0 lần lùi**.

Cái giá phải nói thẳng: **một bộ ký bằng mực model không có chữ lồng nào**. Dải
kiểu hẹp lại thật, chỉ còn `given` và `full`. Đó là một sự thu hẹp có thật, và
nó khác hẳn với việc vẽ chữ ký bằng mực sai.

![7 chữ ký từ mực WriteViT](../samples/signatures/styles-model.jpg)

### `trace`: chỗ raster lọt được vào engine vector

WriteViT trả về **ảnh**, engine này làm việc trên **điểm điều khiển**. `trace`
là đoạn nối, và một khi các pixel ấy thành contour thì mọi phép biến đổi trong
tệp áp lên chúng y như áp lên một glyph — không phần nào phía sau biết có sự
khác biệt.

Ba chi tiết, mỗi cái là một lỗi nhìn thấy được trước khi thành một quy tắc:

- **Phóng to trước khi trace, và bắt buộc.** `Hand._ask` trả tile ở **32 px
  gốc**, nét rộng một hai pixel; trace ra **rỗng**, chữ đầu biến mất, vai trò
  "initial" rơi sang cả từ còn lại rồi bị kéo dọc thành lưỡi dao. Phóng 6× thì
  một nét 1 px thành một hình có ruột.
- **Làm mờ trước khi lấy ngưỡng, và chỉ một chút.** Ảnh có khử răng cưa, lấy
  ngưỡng thẳng để lại bậc thang trên mọi mép nét; sigma 0,6 xoá bậc thang,
  sigma 1,2 làm béo nét và **bít luôn bụng chữ `g`**.
- **Chiều quấn tính theo diện tích có dấu**, không tin quy ước của thư viện.
  Contour ngoài và lỗ của nó phải quấn ngược chiều nhau, nếu không
  `fill-rule:nonzero` tô đặc ruột chữ `o` — đúng chuyện đã xảy ra khi mã này
  tin `findContours` trả sẵn ngược chiều rồi đảo thêm một lần nữa.

### Một đơn vị là một **từ**, không phải một chữ cái

Đây là chỗ đo được chứ không phải chọn cho gọn. Hỏi model `T` và `uan` riêng ra
thì được một chữ `T` cứng đơ và một `uan` đẹp; hỏi `Tuan` một lần thì được một
nét viết liền có chữ hoa đầu đúng kiểu chữ ký. Model được huấn luyện theo từ, và
nó thể hiện ra. Nên với nguồn `model`:

- một đơn vị = một từ, mọi nét nối **bên trong** từ là của model, tệp này chỉ
  thêm nét nối **giữa** các đơn vị;
- `head_and_tail` cắt ở **ranh giới từ** — cắt lấy hai chữ cái sẽ đưa cho model
  đúng ca yếu nhất của nó trên mọi chữ ký;
- **không kéo dọc chữ đầu.** Chữ hoa của font là chữ hoa nhà in, không có dạng
  chữ ký nên phải kéo; chữ hoa model viết ra vốn đã là chữ hoa chữ ký rồi, kéo
  thêm chỉ thành lưỡi dao.

## Engine: bảy phép biến đổi trên đường bậc ba

Toàn bộ hình học là **Python thuần**: một `contour` là đường bậc ba khép kín
giữ dưới dạng 3n+1 điểm, một `path` là danh sách contour, đơn vị là x-height và
**trục y hướng lên** như trong font. Không numpy, không Pillow. `fontTools` chỉ
xuất hiện bên trong `Ink`, numpy và OpenCV chỉ trong `trace`, và không ở đâu khác — đúng lý do `handwriting.py`
nêu cho các import cục bộ của nó: CI chạy bộ test bằng pytest và PyYAML, thế
thôi, nên mọi phép biến đổi ở đây phải kiểm được mà không cần một cái `.ttf`.

| Phép | Làm gì | Đến từ |
| --- | --- | --- |
| `affine` | co giãn + nghiêng quanh đường chân chữ | slant, cap stretch, body squeeze |
| `bow` | uốn đường chân chữ: `rise` nâng đầu phải, `arch` phình giữa | baseline đi lên / phẳng / lượn / đi xuống |
| `fade` | ép dần chiều cao về cuối chữ ký | giản lược tích lũy |
| `swell` | giãn/nén dần khoảng cách theo chiều ngang | nhịp chữ trôi về cuối |
| `ribbon` | biến một đường tâm thành nét có bề dày thon | nét nối, nét cuối, paraph |
| `subdivided` | chẻ nhỏ đoạn trước khi uốn phi tuyến | cái giá phải trả của việc uốn điểm điều khiển |
| `_scrawl` | phần thân đã tan, thành một nét chạy | thân bị bỏ hẳn |
| `_entry` | tìm điểm mà nét vào **thật sự chạm được** vào chữ | xem bên dưới |

Ba phép đầu là biến đổi *chữ*, `ribbon` và `_scrawl` vẽ những nét không phải
chữ, hai phép cuối là hạ tầng. `_entry` là thứ học được
từ việc **nhìn ảnh ra**, không phải từ khảo sát: nét vào nhắm vào mép trái của
hộp bao chữ cái đầu thì với chữ `T` nó kết thúc **giữa không khí**, thành một
cái gạch nhỏ lơ lửng bên cạnh. Nó phải nhắm vào một điểm mà chữ thật sự đi qua.

Hai chỗ khác cũng chỉ lộ ra khi nhìn ảnh, và cả hai đều đã ghi lại trong mã:
nét nối phải **chạy ngay trên** đường chân chữ chứ không võng xuống dưới (một
cái võng ngắn giữa hai chữ hẹp không đọc thành nét nối, nó đọc thành **dấu
chấm** — một chữ ký monogram ra thành `P.MT`); và **không nối hai chữ in hoa**,
vì trong một mặt chữ in hoa không có nét ra để mà nối, và một gạch kẻ giữa hai
chữ hoa đọc thành dấu gạch nối.

### Thứ tự thì không phải chuyện thẩm mỹ

```
chữ cái -> nét nối -> nét vào -> nét lượn -> [swell, fade, bow] -> nét cuối -> paraph -> nghiêng
```

Nét lượn rời chữ cái cuối cùng còn hình, nên phải dựng **trước** các phép uốn
— nó đi theo đường chân chữ cùng với chữ, chứ không phải bị vắt ngang qua sau.
Nét cuối thì rời cả dấu ký **sau khi** đường chân chữ đã uốn, nên nó rời đúng
chỗ mực thực sự kết thúc. Paraph đo trên toàn bộ dấu ký **kể cả nét cuối** — một
đường gạch dừng lại lịch sự trước nét hất sẽ đọc thành hai dấu ký chứ không
phải một. Nghiêng đi cuối cùng, một lần, cho tất cả.

### Một hạt giống là một người

`Style.__init__` rút **mọi thứ**, kể cả độ võng của đường gạch dưới. Đó không
phải sạch sẽ cho vui: `render.py` ký nhiều khối trên một trang từ một hạt giống,
và có một bug đã tồn tại đúng như vậy — `bow()` rút từ bộ sinh ngẫu nhiên tại
thời điểm ký, nên chữ ký thứ hai phụ thuộc vào việc chữ ký thứ nhất tên là gì.
Một dấu ký phải là **hàm thuần của `(seed, name)`**. Thuộc tính `Style.rng` bây
giờ ném `AttributeError` kèm lời giải thích, để lỗi ấy không quay lại lặng lẽ.

## Nối vào tờ giấy

```bash
# mực mặt chữ — chạy được ngay, không cần gì thêm
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --signature --layout invoice_vat_form -c 3 -o out/

# mực mô hình — cần `python tools/writevit/setup.py` trước
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --signature model --layout invoice_vat_form -c 3 -o out/
```

`--signature` đi cùng `--template`, cùng lý do với `--handwriting`: lưới ký tự
không có khối chữ ký, chỉ có ô.

**Khối chữ ký có hai hình dạng**, và đây là điều đáng biết nhất về rule space
này. Chỉ tài liệu bật `signature_names` mới in tên dưới chú thích; phần còn lại
phát ra `<div class="who"></div>` rỗng dưới một dòng đọc đúng là *(Ký, ghi rõ
họ tên)* — và **đó mới là đa số**. Cả hai hình dạng đều được ký.

| | tờ có in tên | tờ để trắng |
| --- | --- | --- |
| ví dụ | `invoice_hotel_stay` | `invoice_vat_form`, `medical_statement`, `authorisation_letter` |
| ký tên ai | tên đã in trên tờ | `names=` do người gọi đưa vào |
| nguồn tên | tài liệu | `rulebase.corpus.people` — cùng kho tên mà tài liệu rút người mua |
| nếu không đưa `names` | vẫn ký | **để trắng, và đếm vào `skipped["unnamed"]`** |

Chỗ cuối bảng là có chủ ý. Engine không bịa tên: một trang muốn có chữ ký mà
không ký được thì phải **nói ra trong nhãn của chính nó**, chứ không phải quay
về im lặng không có chữ ký.

### Ký trước, điền sau

`render.py` chạy `signature.fill` **trước** `handwriting.fill`, và không phải vì
người ta làm thế. `handwriting.fill` có thể thay một run `sign.name` bằng một
`<img>` mực của mô hình, còn `signature.WHO` cố ý **không** khớp một run có
markup bên trong. Ký sau thì trên đúng những trang được điền tay nhiều nhất,
chữ ký sẽ lặng lẽ không xuất hiện.

### Dấu ký không bao giờ là một run có nhãn

Đây là điểm tựa của cả thiết kế. Chữ ký là **mực không có hộp và không có
chữ**: nó phải nằm trên trang và phải nằm ngoài nhãn.

* thẻ phát ra là `<span class="sig">`, **không có `data-kind`**;
* `sheets.labelled_runs` và `sheets.structure_from_markup` cho kết quả **y hệt**
  trước và sau khi ký — có test trên sáu họ bố cục;
* `handwriting._check_contract` vẫn qua trên trang đã ký;
* thứ duy nhất ghi lại dấu ký trong nhãn là `record["signature"]`, và nó ghi
  *kiểu dáng*, không ghi chữ.

Ngược hẳn với `handwriting.ink_span`, vốn là mực **chính là một giá trị** và vì
thế mang theo `data-text`. Hai loại mực, hai hợp đồng, và chúng không được lẫn.

## Giới hạn, nói thẳng

**Nét là nét của một mặt chữ.** Cái ra được là một **dấu ký có hình dạng chữ
ký**: đúng cỡ, đúng độ nghiêng, đúng đường chân chữ, đúng cách nối và đúng nét
hoa — vẽ bằng đường viền của một mặt chữ. Đủ để làm hoa tiết trên tờ giấy: mực
mà bộ đọc phải học cách bỏ qua, nằm đúng chỗ chữ ký nằm. **Không** đủ để làm
mẫu chữ ký của một người, và một bộ dựng từ đây **không phải** corpus để huấn
luyện xác thực chữ ký: hai dấu ký cùng hạt giống là giống hệt nhau, và hai mặt
chữ là hai mặt chữ, không phải 106 người viết. Cùng một sự đánh đổi như
`FontHand`, và được ghi lại theo đúng cách ấy.

**Chưa viết tay tên vào dòng để trắng.** Chú thích nói *(Ký, ghi rõ họ tên)* —
tức là trên tờ giấy thật có **hai** thứ được viết vào đó: chữ ký và tên viết
tay. Engine này vẽ thứ nhất. Thứ hai là việc của `handwriting.fill`, và nó chưa
được nối vào vì `<div class="who">` rỗng không có run nào để điền. Đây là bước
tiếp theo rõ ràng nhất.

**Chữ ký ướt trên khối "chữ ký số".** `invoice_vat_form` in *(CHỮ KÝ ĐIỆN TỬ,
CHỮ KÝ SỐ)* dưới chú thích và có sẵn ô xanh chữ ký số ở bên. Hoá đơn điện tử in
ra ngoài đời thường **không** có chữ ký ướt ở đó. Ở đây vẫn ký, vì bộ dữ liệu
cần mẫu chữ ký nhiều hơn là cần sự chuẩn xác ấy — nhưng đó là một lựa chọn, và
lật lại nó là một điều kiện đọc `sign.note`. Ghi ra đây để nó là lựa chọn chứ
không phải sơ suất.

**Chữ lồng thì vẫn đọc được, và đó là cố ý.** Chữ hoa không bao giờ tan, nên
`LQĐ` ra `LQĐ`. Ba chữ cái đầu là để người ta đọc — đó là toàn bộ công dụng của
một chữ lồng — và một chữ lồng đã tan thì chỉ còn là cái ngoằng không nhận ra
được ai. Khoảng 13 % số dấu ký là loại này.

**`model` mất hẳn hai trong bốn kiểu.** `monogram` và `initials` theo định
nghĩa là chuỗi chữ hoa, mà chuỗi chữ hoa là thứ checkpoint không viết được. Nên
một bộ ký bằng mực model **không có chữ lồng nào** — dải kiểu hẹp lại còn
`given` và `full`. Đổi lại, nó không lẫn mực: đo trên toàn bộ kho tên × 2000
hạt giống, không lần nào phải lùi về mặt chữ.

**Phần đầu phải đủ dài.** Model viết một mẩu ngắn rất tệ: `N` đứng một mình ra
nét nguệch trong khi `Nguyen` ra một nét viết liền, và `Lê` theo sau là mười ô
sóng thì đọc như một dấu ký rỗng. `HEAD_LETTERS = 3` — đọc ra từ ảnh chứ không
từ khảo sát — nên một từ đầu quá ngắn sẽ lấy thêm từ kế tiếp.

**Trace không lấy lại được phần thon của nét.** Ngưỡng cứng luôn cắt cụt đuôi
nét: chỗ bút nhấc mảnh hơn mọi ngưỡng, nên nó thành đầu tù. Đã quét thử
70/100/140 trên chính ảnh gốc — ngưỡng thấp **không** trả lại phần thon, nó chỉ
làm béo toàn bộ nét và rời xa cây bút của mô hình hơn. Muốn có phần thon thật
thì phải dựng xương và biên dạng bề rộng rồi vẽ lại nét, chứ không phải trace
đường viền. Chưa làm, và ghi ra đây thay vì vờ như đã làm.

**Bao nhiêu phần tan ra**, đo trên 600 hạt giống × kho tên:

| | tan thành nét lượn | đọc nguyên vẹn |
| --- | --- | --- |
| `font` | 74 % | 15 % |
| `model` | 67 % | 10 % |

Con số của `model` từng là **56 % đọc nguyên vẹn** — vì `given` là một từ, mà
phần đầu cắt theo ranh giới từ thì nuốt trọn cả từ và `_scrawl` không bao giờ
với tới được. Cắt trong từ được cho phép khi phần đầu chỉ có một từ và dài hơn
`HEAD_LETTERS`; `Ngọc` thành `Ngo` + một ô sóng, còn `Đạo` ba chữ thì giữ
nguyên vì không có gì để cắt.

**Tỷ lệ khung không bị ép.** `ASPECT` chỉ để báo cáo: `Mark.report()` trả về
`in_capture_box`, và với tên ngắn thì dấu ký hay rơi ra ngoài dải 1,8–3,0. Ép
nó vào dải sẽ là bóp méo một dấu ký cho khớp một cái hộp mà tờ giấy này không
có.

## Chạy thử

```bash
# một chữ ký
generators/html/.venv/bin/python generators/html/signature.py \
    --name "Nguyễn Thị Bích Ngọc" --seed 7 --out /tmp/sig.svg

# 18 kiểu cạnh nhau, để nhìn dải tham số làm việc
generators/html/.venv/bin/python generators/html/signature.py \
    --name "Lê Quang Đạo|Trần Văn Hùng" --grid 18 --out /tmp/sheet.svg

# bộ mẫu trong samples/signatures/
make signatures
```

Nhìn **một** chữ ký không chứng minh được gì. Cái đáng nhìn là lưới: một dải
tham số bị đẩy quá tay hiện ra trong mười tám ô cùng lúc, chứ không hiện ra
trong một ô.

## Nguồn

Giám định tài liệu và bút tướng học:

- [Class and Individual Characteristics of Handwriting — Forensics Digest](https://forensicsdigest.com/class-and-individual-characteristics-of-handwriting/)
- [General Principles of Forensic Handwriting Examination](https://www.forensicforgerydetection.com/handwriting-examination-principles)
- [Individual Characteristics of Handwriting — Forensic's blog](https://forensicfield.blog/individual-characteristics-of-handwriting/)
- [AHAF, Whiting glossary of handwriting terms (PDF)](https://ahafhandwriting.org/images/downloads/whiting_glossary2.pdf) — thuật ngữ *paraph*
- [The Complete Guide to Signature Analysis — PenLoops](https://www.penloops.com/signature-analysis-guide)
- [Slant (handwriting) — Wikipedia](https://en.wikipedia.org/wiki/Slant_(handwriting))
- [Slant in Handwriting — Graphology](https://graphology.scry3d.com/slant-in-handwriting/)

Cấu tạo nét, từ thư pháp:

- [8 Basic Calligraphy Strokes — Loveleigh Loops](https://loveleighloops.com/blog/8-basic-calligraphy-strokes/)
- [Copperplate Script with a Pointed Nib — Youblob](https://youblob.com/us/blueprints/copperplate-script-pointed-nib)
- [The Basic Calligraphy Strokes Guide — Lettering Daily](https://www.lettering-daily.com/basic-calligraphy-strokes/)

Chữ ký tiếng Việt:

- [25+ Chữ Ký Tên Việt Đơn Giản Đẹp Nhất](https://chuky.vn/chu-ky-ten-viet.html)
- [30+ Mẫu chữ ký đẹp ý nghĩa theo tên — Sforum](https://cellphones.com.vn/sforum/chu-ky-dep)
- [Chữ ký đẹp theo tên — Kingpen](https://kingpen.vn/chu-ky-dep-theo-ten/)
- [Tổng hợp 100+ mẫu chữ ký tên Việt — MISA eSign](https://esign.misa.vn/16099/chu-ky-ten-viet/)

Bộ dữ liệu chữ ký offline, cho kích thước ô thu mẫu:

- [Fixed-sized representation learning from Offline Handwritten Signatures of different sizes (arXiv 1804.00448)](https://arxiv.org/pdf/1804.00448) — ô GPDS 5×1,8 cm và 4,5×2,5 cm
- [Learning Features for Offline Handwritten Signature Verification using Deep CNNs (arXiv 1705.05787)](https://arxiv.org/pdf/1705.05787) — GPDS, CEDAR, MCYT
- [Intrapersonal Parameter Optimization for Offline Handwritten Signature Augmentation (arXiv 2010.06663)](https://arxiv.org/pdf/2010.06663)

## Đọc tiếp

- [`generators/html/signature.py`](../generators/html/signature.py) — engine, và mọi hằng số kèm chú thích nguồn
- [`samples/signatures/`](../samples/signatures) — lưới kiểu dáng và hai tờ đã ký
- [`handwriting-html.md`](handwriting-html.md) — mực điền vào ô, và vì sao nó không nhúc nhích một glyph nào
- [`hoa-tiet-de-xuat.md`](hoa-tiet-de-xuat.md) — bản đếm những gì tờ giấy thật có mà bộ này chưa có
