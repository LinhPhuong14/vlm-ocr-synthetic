# Khảo sát: tám kho mã sinh chữ viết tay

Commit `ff9a9f0` gỡ cả họ nét tay ra khỏi bộ sinh với một lý do ghi rõ trong
thông điệp: *"Muốn làm đúng thì cần dữ liệu nét — toạ độ bút theo thời gian —
hoặc một mặt chữ viết tay có giấy phép cho phép phát hành lại."*
[`docs/hoa-tiet-de-xuat.md`](hoa-tiet-de-xuat.md) giữ `handwriting_fill` lại
trong danh mục và gọi nó là **khoảng trống lớn nhất** của bộ dữ liệu: tờ mẫu
sinh ra để được điền tay, mà mọi tờ đến giờ đều trống trơn hoặc in máy toàn bộ.

Tài liệu này khảo sát tám kho mã có thể lấp khoảng trống đó, và xếp hạng chúng
theo đúng hai câu hỏi mà bộ dữ liệu này cần trả lời — chứ không theo số sao hay
theo độ mới của bài báo.

**(1) Độ general cho data** — kho mã cho ta *bao nhiêu thứ khác nhau*? Đo bằng
bốn thứ, xếp theo mức quan trọng với bộ dữ liệu tiếng Việt này:

- **Bảng chữ.** Chữ Việt có dấu chồng dấu — `ế`, `ộ`, `ữ`. Một mô hình chưa
  từng thấy dấu trong lúc học thì không sinh ra dấu được, và đây là tiêu chí
  **loại**, không phải tiêu chí trừ điểm.
- **Dạng đầu ra.** Nét (toạ độ bút) vẽ lại được ở mọi độ phân giải, mọi bề rộng
  ngòi, mọi màu mực, và xoay theo ô của tờ mẫu. Ảnh raster cao 32 px thì không.
- **Đơn vị sinh.** Ký tự rời, từ, hay dòng. Ô "Họ tên người mua" cần một dòng;
  ô "Số tiền" cần một cụm số.
- **Đường huấn luyện lại.** Có giao diện nạp dữ liệu riêng và bảng chữ riêng
  không, hay phải sửa vào ruột mô hình.

**(2) Độ thật** — đặt cạnh một tờ scan thật thì có lộ không? Đo bằng FID/KID ở
đâu có số đo, và bằng chỗ mà `ff9a9f0` đã chỉ ra ở đâu không: **hình dạng nét**
(chỗ bút nhấc, nét nối, mực đọng cuối nét) chứ không phải mức độ rung.

---

## Bảng tổng

| Kho mã | Kiến trúc | Dữ liệu học | Đầu ra | Bảng chữ Việt | Trọng số sẵn |
| --- | --- | --- | --- | --- | --- |
| **hnam-1765/WriteViT** | ViT + Transformer | IAM + VNOnDB | ảnh, cao 32 px, mức từ | **có, đủ dấu** | `eng_ckpt.pth`, `vn_ckpt.pth` |
| **X-rayLaser/pytorch-…-toolkit** | Graves + MDN, PyTorch | IAM-OnDB | nét → PNG | không, **nạp được** | `checkpoints/` |
| **dailenson/SDT** | Tách phong cách/nội dung | CASIA, TUATHANDS | nét **và** ảnh, mức ký tự | không | có, cả 4 mô hình |
| **ankanbhunia/Handwriting-Transformers** | Transformer | IAM + CVL | ảnh, cao 32 px, mức từ | **không — 94 ký tự ASCII** | có (Drive, HF) |
| **sleep3r/Diffusion-…pytorch** | Khuếch tán trên nét | IAM-OnDB | nét | không | `data/best_exp/` |
| **Grzego/handwriting-generation** | Graves LSTM, TF 1.2 | IAM-OnDB | nét | không | `pretrained/` |
| **swechhasingh/Handwriting-synthesis** | Graves RNN | 6.000 chuỗi nét | nét | không | `models/` |
| **fractal2k/Handwriting-Synthesis** | GAN (Alonso 2019) | tự thu 8.539 mẫu + IAM | ảnh mức từ | không | **không** |

---

## Xếp hạng 1 — độ general cho data

### 1. hnam-1765/WriteViT

Kho duy nhất trong tám kho **có tiếng Việt ngay khi tải về**. `params.py` khai
báo thẳng bảng chữ đủ dấu:

```
aáàảãạăắằẳẵặâấầẩẫậb…AÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬ…0123456789!
```

Kèm `VN.pickle` (106 người viết) và `vn_ckpt.pth`. Bài báo (*Expert Systems with
Applications* 2026, arXiv 2505.13235) nói đúng vào chỗ khó của tiếng Việt: các
phương pháp khác "thường bỏ sót hoặc làm méo dấu thanh, hoặc đặt sai chỗ", còn
WriteViT đặt được `ỗ`, `ậ`, `ư`. Học phong cách **một ảnh mẫu** nên số kiểu chữ
không bị chặn ở 106 — đưa vào một mẫu chữ mới thì có một kiểu chữ mới.

*Chặn ở:* ảnh raster cao 32 px, rộng 16 px mỗi ký tự, **mức từ**. Không có nét,
không đổi được màu mực sau khi sinh, ghép dòng thì phải tự nối từ.

### 2. X-rayLaser/pytorch-handwriting-synthesis-toolkit

Không có tiếng Việt, nhưng là kho **được dựng để nhận bảng chữ khác**: bảng chữ
nằm trong một file văn bản, và huấn luyện trên dữ liệu riêng chỉ cần viết một
lớp cung cấp dữ liệu có `get_training_data()` / `get_validation_data()` — README
kèm sẵn một lớp giả để bắt chước. Đầu ra là **nét**, tức là dạng general nhất
có thể: vẽ lại ở 150 dpi hay 600 dpi tuỳ ý, ngòi 0,3 mm hay 0,7 mm tuỳ ý, mực
xanh hay đen tuỳ ý, xoay theo dòng kẻ của ô tuỳ ý — một ảnh 32 px không cho làm
gì trong số đó.

Đường đi có sẵn: **HANDS-VNOnDB** (ICFHR2018 VOHTR) là dữ liệu **nét trực tuyến
tiếng Việt** — 1.146 đoạn, 7.296 dòng, hơn 480.000 nét, 200 người viết. Đúng
định dạng mà mô hình kiểu Graves cần.

### 3. dailenson/SDT

Ba hệ chữ (Hán, Nhật, Latin), sinh được **cả nét lẫn ảnh** — kho duy nhất làm
được cả hai. Nhưng sinh **theo từng ký tự rời**, vì bài toán gốc là chữ Hán.
Với tiếng Việt thì đây vừa là điểm mạnh vừa là điểm yếu: một chữ có dấu chỉ là
thêm một lớp ký tự (dễ), nhưng nối các ký tự thành một dòng viết tay Latin có
nét nối thì mô hình không làm — nó không học chuyện đó.

### 4. ankanbhunia/Handwriting-Transformers

Sinh từ tiếng Anh bất kỳ, học phong cách từ 15 ảnh mẫu, 622 người viết
(IAM 339 + CVL 283). Nhưng `params.py` khai `ALPHABET` là **94 ký tự ASCII** —
không một dấu tiếng Việt nào. Với bộ dữ liệu này thì đó là **trượt tiêu chí
loại**, dù ICCV 2021 và 263 sao. Huấn luyện lại được (định dạng pickle có ghi
tài liệu), nhưng khi đã phải huấn luyện lại thì WriteViT đã làm đúng việc đó
rồi và làm tốt hơn — xem xếp hạng 2.

### 5–7. Ba kho Graves còn lại và kho khuếch tán

**Grzego** (595 sao) chọn phong cách bằng `--style 0..7` — **tám kiểu chữ cố
định**, hết. Chạy trên TensorFlow 1.2, lần đẩy mã cuối tháng 1/2018; dựng lại
môi trường cho nó là một việc riêng. **swechhasingh** (260 sao) mồi được bằng
mẫu chữ nên phong cách không bị chặn ở con số, kèm một ứng dụng web demo.
**sleep3r** (7 sao) sinh nét bằng khuếch tán, có `model_final.pth` sẵn, dùng
`uv`. Cả ba đều là IAM tiếng Anh, và bảng chữ đi theo dữ liệu học.

### 8. fractal2k/Handwriting-Synthesis

Tác giả tự ghi trong README: *"We couldn't get the model to converge for some
reason."* Không có trọng số. Không xếp được vì không chạy ra kết quả.

---

## Xếp hạng 2 — độ thật

Số đo dưới đây lấy từ bảng của bài WriteViT, nên đọc với lưu ý là **tác giả tự
báo cáo**. Cái đáng tin trong bảng không phải thứ hạng tuyệt đối mà là khoảng
cách: trên tiếng Việt, mô hình xếp nhất và mô hình xếp bét cách nhau gần 4 lần.

| Trên VNOnDB | FID ↓ | KID ↓ | | Trên IAM | FID ↓ | KID ↓ |
| --- | --- | --- | --- | --- | --- | --- |
| **WriteViT** | **6,179** | 0,512 | | **WriteViT** | **11,102** | 0,37 |
| HWT | 9,851 | 0,72 | | VATr | 13,577 | 0,47 |
| HiGAN | 11,257 | 0,79 | | HWT | 13,615 | 0,49 |
| ScrabbleGAN | 19,232 | 1,11 | | HiGAN+ | 16,114 | 0,81 |
| VATr | 23,883 | 2,72 | | HiGAN | 17,086 | 1,18 |

### 1. WriteViT — thật nhất trên tiếng Việt, và có số đo để nói thế

FID 6,18 trên VNOnDB, hơn HWT (9,85) một khoảng rộng. Đáng chú ý hơn con số:
**VATr tụt xuống 23,88 trên tiếng Việt trong khi đứng nhì trên tiếng Anh** —
tức là thứ hạng độ thật trên tiếng Anh *không chuyển sang* tiếng Việt. Dấu
thanh là một bài riêng, và một mô hình giỏi chữ Latin trơn có thể hỏng hẳn ở
đó. Đây là lý do không nên đọc bảng IAM rồi suy ra.

Có thêm một số đo gián tiếp: nuôi mô hình nhận dạng bằng 5.000 ảnh thật +
25.000 ảnh sinh, CER tụt từ 25,50 xuống 3,13. Ảnh đủ thật để **dạy được**, chứ
không chỉ đủ thật để nhìn.

### 2. ankanbhunia/Handwriting-Transformers

FID 13,6 trên IAM, và là mốc so sánh mà mọi bài sau đều phải đo lại — ICCV 2021,
đã qua tay nhiều nhóm khác. Con số 9,85 trên tiếng Việt ở bảng trên là **HWT
được huấn luyện lại trên VNOnDB**, không phải trọng số phát hành; tải về chạy
ngay thì không ra chữ Việt.

### 3. dailenson/SDT

CVPR 2023, 1.4k sao — nhiều sao nhất trong tám kho. Chữ Hán sinh ra rất thật,
và tách được phong cách người viết khỏi phong cách từng ký tự là một ý hay. Với
tiếng Việt thì hạn chế nằm ở chỗ nó sinh ký tự rời: dòng chữ ghép từ ký tự rời
đều khoảng cách sẽ lộ ngay, vì chữ tay thật không đều khoảng cách.

### 4. sleep3r — khuếch tán trên nét

Quỹ đạo bút do khuếch tán sinh ra mượt và tự nhiên hơn kiểu lấy mẫu tự hồi quy
của Graves, ít bị trôi khi câu dài. Nhưng kho nhỏ (7 sao), chỉ IAM, và không có
FID công bố để đối chiếu.

### 5. Ba kho Graves (Grzego, X-rayLaser, swechhasingh)

Cần tách hai chuyện, vì đây đúng là chỗ `ff9a9f0` đã vấp:

- **Quỹ đạo thì thật.** Mô hình học từ toạ độ bút người thật, nên chỗ nhấc bút,
  nét nối, độ nghiêng thay đổi trong câu — đều đúng. Đây chính là thứ mà "làm
  lệch từng ký tự của một mặt chữ in" không bao giờ có.
- **Mực thì chưa thật.** Đầu ra là đường vector bề rộng đều: không có chỗ mực
  đọng cuối nét, không có nét nhạt dần khi bút đi nhanh, không có mực thấm vào
  thớ giấy. Vẽ trần ra PNG thì được một nét bút bi lý tưởng.

Nghĩa là dùng họ này thì **vẫn còn một bước phải tự làm**: biến quỹ đạo thành
mực. Đổi lại, bước đó nằm trong tay mình và làm được đúng ở 150 dpi.

### Không xếp: fractal2k

Mô hình không hội tụ.

---

## Đề xuất cho kho này

Hai câu trả lời khác nhau vì hai đường đi khác nhau, và **cả hai đều dùng
được** — chọn theo việc muốn làm trước.

**Muốn có chữ Việt viết tay trên tờ giấy sớm nhất → WriteViT.** Là kho duy nhất
đứng đầu **cả hai** bảng xếp hạng, và là kho duy nhất không đòi huấn luyện gì
trước khi cho ra chữ có dấu. Chuyện cao 32 px hoá ra không chặn: tờ A4 ở
150 dpi (`generators/genalog/render.py`, `samples/invoice-templates/render.py`)
là 1240 × 1754 px, một dòng chữ tay điền vào ô cao chừng 6–8 mm tức 35–47 px —
phóng 1,1 đến 1,5 lần. Phần mềm còn lại thì tầng
[`degradation/`](../degradation/README.md) vốn đã làm nhoè ảnh sẵn.

**Muốn nét bút thật sự, dùng được lâu → X-rayLaser toolkit huấn luyện trên
VNOnDB.** Đầu ra là nét nên vẽ được ở mọi độ phân giải, đổi được màu mực, xoay
được theo ô — và ký được cả chữ ký, việc mà ảnh 32 px không làm. Giá phải trả
là một đợt huấn luyện, và một bước dựng mực sau đó.

Cả hai đường đều còn nguyên **hai ràng buộc của kho này**, chưa đường nào giải:

1. **Nội dung phải đi đường `from_receipt`.** Ảnh và nhãn không được nói hai
   chuyện khác nhau — chữ điền tay phải lấy từ chính `receipt` đã sinh ra tờ
   giấy, không phải từ một danh sách từ rời. Cả hai mô hình đều nhận chuỗi văn
   bản đầu vào nên chỗ này thông, nhưng phải nối tay.
2. **Giấy phép.** Cả tám kho đều MIT, nhưng trọng số học từ IAM-OnDB và VNOnDB —
   điều khoản phát hành lại của **dữ liệu** mới là thứ phải đọc trước khi đưa
   ảnh sinh ra vào một bộ dữ liệu công bố, không phải giấy phép của **mã**.

## Nguồn

Bài báo và bảng số: [WriteViT, arXiv 2505.13235](https://arxiv.org/html/2505.13235) ·
[Handwriting Transformers, arXiv 2104.03964](https://arxiv.org/abs/2104.03964) ·
[SDT, CVPR 2023](https://github.com/dailenson/SDT) ·
[Graves 2013, arXiv 1308.0850](https://arxiv.org/abs/1308.0850)

Dữ liệu: [HANDS-VNOnDB](https://tc11.cvc.uab.es/datasets/HANDS-VNOnDB_1/) ·
[IAM-OnDB](https://fki.tic.heia-fr.ch/databases/iam-on-line-handwriting-database)
