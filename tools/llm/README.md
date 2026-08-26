# tools/llm — bước sinh, chạy **cạnh** pipeline chứ không nằm trong

```bash
ollama serve &
ollama pull qwen2.5:7b-instruct

# xem trước, không ghi gì
python -m tools.llm.augment_content --file items_market --want 20
# ghi vào corpus
python -m tools.llm.augment_content --file items_market --want 20 --write

# kiểm luật ngược lại chính corpus đang có
python -m tools.llm.corpus_rules --audit
```

## Ranh giới, và vì sao nó là toàn bộ kiến trúc

**Không file nào dưới `tools/llm/` được `generators/` hay `pipeline/` import,
và `tests/test_llm.py` khẳng định điều đó bằng một assertion.**

Thiết kế hấp dẫn là gọi model ngay lúc vẽ trang, để mỗi trang có chữ mới. Cái
giá của nó là lời hứa mà cả kho này dựng lên: **cùng seed thì ra cùng byte**.
`tools/baseline.py` vân tay từng ảnh, `tests/test_worklist.py` vẽ một trang hai
đường rồi so sha256, và `docs/renderers.md` so hai renderer trên đúng một tuyên
bố — chỉ cách vẽ khác nhau. Một bộ sinh nằm trong đường render cho cả ba nghỉ
việc, và cho nghỉ **lặng lẽ**: ảnh vẫn ra, chỉ là không còn là ảnh cũ nữa.

Nên model chạy **ở đây**, một bước riêng, và thứ nó tạo ra là **file thường
trong git**: một dòng corpus, một file layout YAML, một danh sách biến thể. Có
người đọc diff trước khi nó vẽ ra bất cứ thứ gì. Renderer vẫn đọc file như
trước, và không phân biệt được file do model viết hay do người viết — đúng cái
tính chất giữ đường render vừa deterministic vừa offline.

```
tools/llm/                          rulebase/                generators/
  client.py     ──ollama──►           corpus/*.txt   ──────►   render.py
  corpus_rules.py  (gác cổng)         layouts/*.yaml           (không biết
  augment_content.py ──ghi──►         variants/*.yaml           tools/llm tồn tại)
  provenance.py (đóng dấu)
```

## Cái gì lặp lại được, cái gì không

Model nhận seed và temperature, Ollama tôn trọng cả hai, nên cùng prompt trên
cùng trọng số và cùng bản build **thường** ra cùng chữ. "Thường" là xa nhất
file này dám nói: đổi bản Ollama, đổi mức lượng tử hoá, đổi số luồng đều có thể
xê một token, và không thứ gì phía sau được phép dựa vào chuyện nó không xê.

Cái **lặp lại được** là file đã commit. Đó mới là sản phẩm; prompt và model
được ghi ngay bên cạnh nó bởi `provenance.py`. Chạy lại bộ sinh là cách lấy
**thêm** vật liệu, không phải cách lấy **lại** vật liệu cũ.

## Dấu vết trong corpus

Một khối do model viết được rào bằng comment — mọi trình đọc sẵn có đều bỏ qua
dòng bắt đầu bằng `#`, và đã bỏ qua từ trước khi có file này:

```
# >>> llm qwen2.5:7b-instruct@845dbda0ea48 prompt=items:3f2a seed=11 2026-08-26
Nước mắm Nam Ngư 500ml	28000	35000
# <<< llm
```

Có nó thì câu hỏi "dòng này là thật hay 7B bịa ra?" mới có chỗ trả lời. Không
có nó thì corpus có hai loại dòng mà người đọc không phân biệt được — và người
đọc chính là người phải sửa khi model viết sai.

## Gác cổng: `corpus_rules.py`

Model là bên **đề xuất**; luật trong `corpus_rules.py` là thứ duy nhất đứng
giữa nó và dataset. Mọi ngưỡng ở đó **đo từ corpus đã commit**, không phải chọn
— và `--audit` là phép thử của chính bộ luật:

> **Luật nào loại một dòng người đã viết là luật sai, không phải dòng sai.**

Bản đầu đoán thay vì đo, và audit ném đi **354/737 dòng, 48 %**. Vòng hai còn
**209/828, 25,2 %** — toàn bộ vì đúng một ký tự: `đ` và `Đ` không phân rã được
bằng NFD, nên phép thử Latin viết theo dải `a`–`z` loại sạch mọi từ tiếng Việt
chứa chữ cái Việt Nam nhất. Vòng ba còn 6 dòng vì bao ngưỡng đo theo cột 1 mà
áp cho cột 2 (chi nhánh dài hơn tên chuỗi). Vòng bốn còn 8 dòng vì `Quận 1` là
một chữ số. Hiện tại **0/828**, và lệnh trả về mã lỗi khác 0 nếu không còn thế.

Bao ngưỡng độ dài đo **theo từng file và từng cột**, và chỉ đo trên **dòng do
người viết**: nếu tính cả dòng model viết thì mỗi vòng nới ra một chút, và vòng
thứ mười sẽ được kiểm bằng sai sót của vòng thứ chín.

## Cái gác cổng KHÔNG bắt được

Luật là cơ học. Nó bắt được model trả lời bằng tiếng Anh, bịa một cái tên 200
ký tự, hay ghi giá có dấu chấm. Nó **không** bắt được một dòng đúng ngữ pháp mà
sai sự thật: `Dầu-tahini` là tiếng Việt hợp lệ và không phải thứ tiệm tạp hoá
nào bán. Đó là việc của dấu vết provenance và của người đọc diff — và là lý do
`--write` chỉ ghi file chứ không commit.

## Giá phải trả

Qwen2.5 7B lượng tử hoá 4-bit chạy CPU: **~5 token/giây**. Một vòng 20 dòng mất
hai tới ba phút, và một file corpus là cả buổi chiều. Bộ sinh in tiến độ từng
vòng vì lý do đó. Máy có GPU thì `--model` trỏ sang model lớn hơn.
