# Khảo sát: 6 root document phổ biến cho OCR/VLM, ngoài phạm vi hiện tại của kho

> Đây là tài liệu **nghiên cứu**, không phải luật sinh — không file nào trong
> `rulebase/` bị đổi. Kho hiện chỉ phủ hoá đơn / biên lai / chứng từ hành
> chính Việt Nam: 17 `documents/` và 16 `layouts/`, xem
> [rulebase/README.md](../rulebase/README.md). Tài liệu này khảo sát **6 root
> document** khác — đều thuộc nhóm giấy tờ tuỳ thân & tài liệu hành
> chính-tài chính, phổ biến bậc nhất trong OCR/eKYC nhưng kho **chưa có** —
> để dùng làm tham khảo nếu sau này muốn thêm một "họ chứng từ" mới theo đúng
> quy trình ở [README.md §6](../README.md#-6-thêm-một-loại-chứng-từ-mới).

## Phương pháp

- **6 root**, mỗi root do một lượt tìm kiếm web **độc lập** thực hiện (tránh
  một góc nhìn duy nhất chi phối cả sáu); mỗi lượt tự tra cứu, không bịa
  thông tin hay bịa link.
- **Layout** ở đây giữ đúng nghĩa mà `rulebase/README.md` dùng: một biến thể
  **cấu trúc/thiết kế** thật (đời/mẫu giấy tờ, quốc gia phát hành, tổ chức
  phát hành, chất liệu vật lý) — không phải mười lần chụp cùng một mẫu.
- **An toàn ảnh minh hoạ (bắt buộc với mọi lượt tra cứu):** chỉ nhận ảnh
  **mẫu / specimen / blank / template**, ưu tiên Wikimedia Commons và các
  trang chính thức; **cấm tuyệt đối** ảnh trông giống giấy tờ thật của một cá
  nhân cụ thể (tên thật, ảnh chân dung thật, số giấy tờ/tài khoản thật). Khi
  không chắc, lượt tra cứu phải bỏ qua và ghi rõ "không tìm được ảnh an
  toàn" thay vì liều đưa link — điều này xảy ra ở **2 trong 60** bố cục bên
  dưới (mục 1.2 và mục 3.1), giữ nguyên như vậy thay vì trám cho đủ.
- **Đã xác minh HTTP** (status code + `content-type`) toàn bộ 58 link ảnh tìm
  được, thành nhiều đợt có giãn cách vì `upload.wikimedia.org` giới hạn tần
  suất trên IP dùng chung của môi trường này:
  - **52/58** xác nhận `200` và đúng kiểu ảnh (`image/jpeg`, `image/png`...).
  - **5 link** (đều trên `upload.wikimedia.org`) vẫn trả về `429` sau nhiều
    lần thử lại giãn cách 15–25 giây — cùng domain và cùng khuôn dạng URL với
    52 link đã xác nhận, nên nhiều khả năng vẫn hợp lệ, nhưng **chưa xác
    minh lại được** trong phiên này; đánh dấu `⁺` trong các bảng bên dưới.
  - **1 link** (mục 4.2) trả về `200` nhưng là **PDF**, không phải ảnh — ghi
    rõ là "tài liệu mẫu (PDF)" thay vì gắn nhãn ảnh.
- Không tự ý thay ảnh đã xác nhận bằng ảnh khác chỉ vì có sẵn — mỗi link là
  kết quả tìm kiếm thật, giữ nguyên nguồn đã tra được.

## Tổng quan

| # | Root document | Bố cục có ảnh xác nhận | Bố cục chưa xác nhận lại (`429`, cùng domain) | Không có ảnh an toàn |
| ---: | :--- | :---: | :---: | :---: |
| 1 | [Căn cước công dân / CMND](#1-căn-cước-công-dân--chứng-minh-nhân-dân-national-id-card) | 8/10 | 1/10 | 1/10 |
| 2 | [Hộ chiếu](#2-hộ-chiếu-passport) | 8/10 | 2/10 | 0/10 |
| 3 | [Giấy phép lái xe](#3-giấy-phép-lái-xe-drivers-license) | 7/10 | 2/10 | 1/10 |
| 4 | [Sao kê ngân hàng](#4-sao-kê-ngân-hàng-bank-statement) | 9/10 (+1 PDF) | 0/10 | 0/10 |
| 5 | [Sơ yếu lý lịch / CV](#5-sơ-yếu-lý-lịch--cv-xin-việc-resume--cv) | 10/10 | 0/10 | 0/10 |
| 6 | [Hợp đồng](#6-hợp-đồng-contract) | 10/10 | 0/10 | 0/10 |
| | **Tổng (60 bố cục)** | **52** | **5** | **2** |

---

## 1. Căn cước công dân / Chứng minh nhân dân (National ID Card)

**Mô tả ngắn:** Giấy tờ tuỳ thân bắt buộc và dùng nhiều nhất của công dân
Việt Nam (và loại tương đương ở hầu hết các nước), xuất hiện trong gần như
mọi giao dịch hành chính, ngân hàng, eKYC. Thách thức OCR đặc trưng: chữ có
dấu tiếng Việt cỡ nhỏ chồng lên hoạ tiết nền bảo an (bản đồ, trống đồng), bề
mặt nhựa phản chiếu ánh sáng/loá khi chụp, và nhãn + vị trí trường liên tục
đổi qua nhiều thế hệ mẫu (9 số, 12 số, mã vạch, gắn chip, mẫu 2024).

**Từ khoá (EN):** national ID card, citizen identity card, identification
card, CCCD, CMND, personal identification number, chip-based ID card,
machine readable zone (MRZ), QR code, barcode ID card, place of origin,
place of residence, date of expiry, national emblem, fingerprint biometric

**Từ khoá (VI):** căn cước công dân, chứng minh nhân dân, thẻ căn cước, số
định danh cá nhân, họ và tên, ngày tháng năm sinh, quê quán, nơi thường trú,
nơi cư trú, nơi đăng ký khai sinh, đặc điểm nhận dạng, vân tay, mã vạch, gắn
chip điện tử, quốc huy

| # | Tên bố cục (VI) | slug (EN) | Đặc điểm nhận diện | Link ảnh | Nguồn |
|---|---|---|---|---|---|
| 1 | CMND mẫu cũ (9 số, trước 2012) | `cmnd_9so_cu` | Nền xanh lục-ngọc hoạ tiết ngôi sao lặp lại, khung viền kép, tiêu đề đỏ "GIẤY CHỨNG MINH NHÂN DÂN" chỉ tiếng Việt; dùng "Nguyên quán"/"Nơi ĐKHK thường trú", không mã vạch/chip/QR. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/b/b8/Obsolete_S.R._Vietnam_National_ID_card.png) | Wikimedia Commons |
| 2 | CMND 12 số (2012–2016) | `cmnd_12so_2012` | Thẻ nhựa PET hai mặt hoạ tiết xanh nhạt-trắng (trống đồng, bản đồ, hoa sen); lần đầu in ảnh trực tiếp lên thẻ, mặt sau có mã vạch 2D; riêng mẫu này có thêm "Họ tên cha"/"Họ tên mẹ". | *Không tìm được ảnh an toàn* — chỉ tìm thấy thẻ thật của cá nhân, không có specimen công khai đáng tin | — |
| 3 | CCCD mã vạch (2016–2021) | `cccd_mavach_2016` | Nền trắng/xám in mờ bản đồ Việt Nam, tiêu đề đỏ "CĂN CƯỚC CÔNG DÂN" chỉ tiếng Việt; thêm "Họ và tên gọi khác", mặt sau in mã vạch 2D thay vì chip, không QR. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/3/31/Thẻ_Căn_cước_Công_dân_(Việt_Nam).jpg) | Wikimedia Commons |
| 4 | CCCD gắn chip — mặt trước (2021+) | `cccd_chip_front_2021` | Nền hoạ tiết xanh ngọc chuyển be, bản đồ Việt Nam lớn, song ngữ Việt-Anh kèm cờ nhỏ cạnh "Citizen Identity Card"; trường Số/Họ tên/Ngày sinh/Giới tính/Quốc tịch/Quê quán/Nơi thường trú xếp dọc bên phải ảnh chân dung. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/9/96/Căn_cước_công_dân_gắn_chíp_mặt_trước.jpg) | Wikimedia Commons |
| 5 | CCCD gắn chip — mặt sau (2021+) | `cccd_chip_back_2021` | Chip điện tử vàng ánh kim góc trái, hai ô vân tay trỏ trái/phải góc phải, chức danh người ký "CỤC TRƯỞNG CỤC CẢNH SÁT...", mục "Đặc điểm nhận dạng" — không còn mã vạch. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/c/ce/Căn_cước_công_dân_gắn_chíp_điện_tử.jpg) | Wikimedia Commons |
| 6 | Thẻ Căn cước mẫu mới (từ 01/7/2024) | `cancuoc_moi_2024` | Đổi tiêu đề "CĂN CƯỚC/Identity Card" (bỏ "công dân"), nền chuyển vàng-lam thay vì xanh ngọc; "Số" → "Số định danh cá nhân", bỏ Quê quán/Nơi thường trú khỏi mặt trước, chuyển "Nơi đăng ký khai sinh"/"Nơi cư trú" ra mặt sau. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/1/18/VIetnamese_biometric_national_identity_card.jpg) | Wikimedia Commons |
| 7 | Thẻ Aadhaar (Ấn Độ) | `india_aadhaar_card` | Khổ ngang nền trắng, quốc huy trụ đá Ashoka trái + logo vân tay cam "आधार/AADHAAR" phải; song ngữ Hindi-Anh, số định danh 12 số cỡ lớn giữa thẻ, không có địa chỉ ở mặt trước. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/1/15/Specimen_of_an_Aadhaar_Card_2024.png) | Wikimedia Commons (specimen, dữ liệu hư cấu) |
| 8 | Personalausweis (Đức) | `germany_personalausweis` | Thẻ polycarbonate, MRZ 3 dòng ở mặt sau; còn ghi "màu mắt"/"chiều cao" (CCCD Việt Nam không có), chip RFID ẩn, số truy cập tách riêng số thẻ. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/4/45/Neuer_deutscher_Personalausweis_ab_1._November_2010%2C_Vorder-_und_R%C3%BCckseite_%28Muster%29.jpg) | Wikimedia Commons (Muster/specimen chính thức, dữ liệu "Erika Mustermann") |
| 9 | Cư dân chứng Trung Quốc | `china_resident_id_card` | Nhãn trường xếp dọc một cột chữ Hán (姓名/性别/民族/出生/住址), ảnh chân dung không khung màu bên phải, số định danh 18 số; không song ngữ Anh, không hoạ tiết bản đồ. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/4/49/The_People%27s_Republic_of_China_resident_identity_card_%28SAMPLE%29_front.png) | Wikimedia Commons (mẫu SAMPLE/样本, nguồn Bộ Công an TQ) |
| 10 | Thẻ My Number (Nhật Bản) | `japan_my_number_card` | Nền hồng nhạt in mờ "JAPAN" lặp lại, biểu tượng thỏ hồng "個人番号カード" góc trên phải; có checkbox "ý nguyện hiến tạng" (臓器提供意思) — không xuất hiện ở mẫu nào khác. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/6/6a/マイナンバーカードみほん表.jpg)⁺ | Wikimedia Commons (mẫu みほん/sample, nguồn Digital Agency Nhật Bản) |

---

## 2. Hộ chiếu (Passport)

**Mô tả ngắn:** Giấy tờ do cơ quan có thẩm quyền một quốc gia cấp để công
dân xuất nhập cảnh, với "trang thông tin/bio-data page" chuẩn hoá theo ICAO
9303 nên rất thường là mục tiêu OCR/eKYC. Thách thức OCR đặc trưng: hoa văn
an ninh (guilloché) và hình mờ chồng chữ, văn bản song/tam ngữ, vùng MRZ
font OCR-B cần tách khỏi chữ thường, ảnh chân dung chèn lệch bố cục, và bố
cục đổi liên tục qua nhiều đời hộ chiếu (Việt Nam đổi mẫu 3 lần chỉ trong
2022–2023).

**Từ khoá (EN):** passport, passport booklet, biographic data page /
bio-data page, machine-readable zone (MRZ), travel document, ICAO Doc 9303,
TD3 size document, biometric passport (e-passport), passport number, visa
page / endorsement page, issuing authority, date of expiry, nationality
field

**Từ khoá (VI):** hộ chiếu, hộ chiếu phổ thông, hộ chiếu công vụ, hộ chiếu
ngoại giao, trang thông tin (trang lý lịch/nhân thân), vùng mã vạch đọc máy
(MRZ), số hộ chiếu, nơi sinh, ngày cấp, ngày hết hạn, cơ quan cấp hộ chiếu,
quốc tịch, hộ chiếu gắn chip điện tử, chữ ký người mang hộ chiếu, trang bìa
hộ chiếu

| # | Tên bố cục (VI) | slug (EN) | Đặc điểm nhận diện | Link ảnh | Nguồn |
|---|---|---|---|---|---|
| 1 | Hộ chiếu VN mẫu cũ (trước 07/2022) — trang bìa | `passport_vn_old_green_cover_pre2022` | Bìa cứng xanh lá đậm, quốc huy + "HỘ CHIẾU/PASSPORT" dập nhũ vàng, không biểu tượng chip. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/7/70/Vietnam_passport_1998.JPG)⁺ | Wikimedia Commons |
| 2 | Trang dữ liệu hộ chiếu VN mẫu cũ (trước 07/2022) | `passport_vn_old_biodata_page_pre2022` | Trang song ngữ Việt-Anh nền xanh nhạt, có "Nơi sinh/Place of birth", không chip; MRZ 2 dòng "P&lt;VNM..."; trang đối diện có dấu tròn đỏ + chữ ký cán bộ (thông tin cá nhân đã bị làm mờ trong ảnh). | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/d/d2/Vietnamese_passport_data_page.jpg) | Wikimedia Commons |
| 3 | Hộ chiếu VN mẫu mới 2022 — trang bìa | `passport_vn_2022_navy_cover_nochip` | Bìa xanh tím than, quốc huy vàng giữa bìa; **không** có biểu tượng chip ở cạnh dưới (khác bản 2023). Áp dụng từ 1/7/2022. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/a/ae/Vietnamese_passport_2022.jpg) | Wikimedia Commons |
| 4 | Trang dữ liệu hộ chiếu VN 2022 — thiếu "Nơi sinh" | `passport_vn_2022_biodata_no_birthplace` | 1 dòng "Họ và tên" (chưa tách Họ/Chữ đệm-tên), **không** có "Nơi sinh"; từng bị một số nước Schengen từ chối cấp thị thực vì lý do này (dữ liệu cá nhân trong ảnh đã được che). | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/a/a9/Biodata_page_of_Vietnamese_passport.jpg) | Wikimedia Commons |
| 5 | Trang dữ liệu hộ chiếu VN bản sửa (từ 01/2023) | `passport_vn_2023_biodata_birthplace_specimen` | Ảnh **specimen chính thức** của Bộ Công an, dữ liệu placeholder; so với mẫu 2022 đã tách "Họ" và "Chữ đệm và tên" thành 2 dòng, bổ sung "Nơi sinh/Place of birth". | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/4/40/S.R._Viet_Nam_passport_-_early_2023_revision.png)⁺ | Wikimedia Commons (nguồn: Bộ Công an) |
| 6 | Hộ chiếu VN gắn chip điện tử (từ 03/2023) — trang bìa | `passport_vn_biochip_2023_cover` | Bìa như mẫu 2022 nhưng thêm biểu tượng chip sinh trắc (chữ nhật nhỏ mạ vàng) in nổi giữa cạnh dưới bìa. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/0/04/Vietnamese_Biometric_passport.jpg) | Wikimedia Commons |
| 7 | Hộ chiếu EU/Schengen bìa đỏ burgundy — Đức | `passport_eu_burgundy_germany_cover` | Bìa đỏ burgundy theo quy chuẩn EU, "REISEPASS" + quốc huy đại bàng đen giữa bìa, "BUNDESREPUBLIK DEUTSCHLAND" phía dưới. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/4/44/Reisepass_Bundesrepublik_Deutschland_–_Einband_Vorderseite_2017.jpg) | Wikimedia Commons |
| 8 | Hộ chiếu Mỹ (US) biometric — trang bìa | `passport_us_biometric_navy_cover` | Bìa navy đậm, quốc huy đại bàng vàng giữa bìa, "PASSPORT" trên/"United States of America" dưới, biểu tượng chip sinh trắc đáy bìa. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/3/35/Us-passport.jpg) | Wikimedia Commons (U.S. Dept. of State) |
| 9 | Hộ chiếu Anh (UK) mẫu hậu Brexit (từ 2020) — trang bìa | `passport_uk_post_brexit_blue_cover` | Bìa navy gần đen, **không** còn dòng "EUROPEAN UNION" phía trên; huy hiệu Anh giữa bìa, "UNITED KINGDOM OF GREAT BRITAIN AND NORTHERN IRELAND". | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/c/c6/British_Passport_2020.png) | Wikimedia Commons |
| 10 | Trang dữ liệu hộ chiếu Đức/EU (chuẩn ICAO) | `passport_eu_germany_biodata_page` | Trang polycarbonate: ảnh chân dung trái, trường dạng bảng phải, nền guilloché nhiều lớp + ngôi sao EU, MRZ 2 dòng OCR-B, biểu tượng chip — đại diện bố cục "TD3" chuẩn ICAO 9303. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/0/02/Bio_data_page_of_German_Passport.png) | Wikimedia Commons (nguồn: PRADO – Council of the EU) |

---

## 3. Giấy phép lái xe (Driver's License)

**Mô tả ngắn:** Chứng từ tuỳ thân xác nhận quyền điều khiển phương tiện,
tồn tại song song nhiều thế hệ vật liệu (giấy bìa, thẻ nhựa PET) và nhiều
biến thể theo quốc gia/hạng xe. Xuất hiện thường xuyên trong hồ sơ KYC,
thuê xe, bảo hiểm, xử phạt giao thông. Thách thức OCR đặc trưng: hoa văn an
ninh dày đặc chồng chữ, cỡ chữ nhỏ song ngữ, con dấu/chữ ký/hologram đè lên
vùng dữ liệu, bề mặt PET loá khi chụp, bảng phân hạng xe mặt sau dạng
lưới khó tách trường.

**Từ khoá (EN):** driver's license, driving licence, license number,
license class/category, date of birth, issue date, expiration date,
issuing authority, restrictions/endorsements, vehicle classification,
portrait photo, QR code, PET card, signature, international driving permit
(IDP)

**Từ khoá (VI):** giấy phép lái xe, bằng lái xe, hạng bằng lái (A1, A2, B1,
B2, C, D, E), số giấy phép lái xe, họ và tên, ngày sinh, quốc tịch, nơi cư
trú, ngày cấp, ngày hết hạn, cơ quan cấp, ảnh chân dung, mã QR, chữ ký, giấy
phép lái xe quốc tế

| # | Tên bố cục (VI) | slug (EN) | Đặc điểm nhận diện | Link ảnh | Nguồn |
|---|---|---|---|---|---|
| 1 | GPLX giấy bìa mẫu cũ (trước 7/2012) | `dl_vn_paper_old` | Chất liệu giấy bìa ép màng mỏng (không phải thẻ cứng), nền hoa văn vàng nhạt, tiêu đề đỏ "GIẤY PHÉP LÁI XE" + quốc huy nhỏ góc trái, dấu đỏ tròn + chữ ký lãnh đạo Sở GTVT, không QR, in một mặt. | *Không tìm được ảnh an toàn* — ảnh trên báo chí đều là bản thật đã làm mờ, không phải specimen | — |
| 2 | GPLX thẻ PET "vàng rơm" — mặt trước (mẫu 2017, phổ biến 2013–đầu 2025) | `dl_vn_pet_yellow_front` | Thẻ PET khổ ID-1, nền vàng rơm + quốc huy chìm cỡ lớn giữa-phải, tiêu đề đỏ "GIẤY PHÉP LÁI XE/DRIVER'S LICENSE", khung ảnh nền xanh da trời; bản gốc Phụ lục 17 không có mã QR. | [Ảnh mẫu](https://cdn.accgroup.vn/wp-content/uploads/2022/08/2-6.jpg) | ACC Group (trích Phụ lục 17, TT 12/2017/TT-BGTVT) |
| 3 | GPLX thẻ PET "vàng rơm" — mặt sau | `dl_vn_pet_yellow_back` | Nền vàng rơm, "CÁC LOẠI XE CƠ GIỚI ĐƯỜNG BỘ ĐƯỢC ĐIỀU KHIỂN/CLASSIFICATION OF MOTOR VEHICLES", hoa văn hoa thị lớn giữa thẻ, số phôi in nhỏ dưới cùng; không chia cột số hoá như mẫu 2025. | [Ảnh mẫu](https://cdn.accgroup.vn/wp-content/uploads/2022/08/3-3.jpg) | ACC Group (trích Phụ lục 17, TT 12/2017/TT-BGTVT) |
| 4 | GPLX thẻ PET hồng mẫu mới (hiệu lực từ 1/3/2025) — mặt trước | `dl_vn_pet_pink_front` | Nền hồng nhạt thay vàng rơm, quốc huy chìm lớn phía trên phải, tiêu đề in đen đậm (không còn đỏ); do **Bộ Công an** cấp thay Bộ GTVT. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/f/f4/Mặt_trước_GPLX_(2025).jpg) | Wikimedia Commons (Bộ Công an) |
| 5 | GPLX thẻ PET hồng mẫu mới — mặt sau | `dl_vn_pet_pink_back` | Nền hồng, cột "Ngày đạt kết quả/Date of passing driving test" ngăn bằng đường kẻ dọc, **mã QR** vuông góc dưới trái cạnh "Số phôi" — khác biệt rõ so với mẫu vàng rơm không QR. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/d/d1/Mặt_sau_GPLX_(2025).png) | Wikimedia Commons (Bộ Công an) |
| 6 | Giấy phép lái xe quốc tế (IDP) do Việt Nam cấp | `dl_vn_idp` | Dạng sổ nhỏ khổ A6 bìa xám (khác hẳn thẻ nhựa); bìa song ngữ "GIẤY PHÉP LÁI XE QUỐC TẾ/INTERNATIONAL DRIVING PERMIT" dẫn chiếu Công ước Vienna 1968; 9 trang nhiều thứ tiếng. | [Ảnh mẫu](https://xdcs.cdnchinhphu.vn/zoom/200_125/446259493575335936/2025/3/3/g1-17410167833151096650281-38-0-316-444-crop-17410176310171295828858.jpg) | Cổng TTĐT Chính phủ |
| 7 | Bằng lái xe Mỹ (mẫu bang California) | `dl_us_license` | Thẻ ngang kiểu Mỹ, "California DRIVER LICENSE" góc trên trái, ảnh chân dung có chữ "SAMPLE" in chìm, số DL/EXP in đỏ, "CLASS" hạng xe, gấu vàng California mờ nền. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/7/79/Californian_sample_driver%27s_license%2C_c._2019.jpg)⁺ | Wikimedia Commons (specimen chính thức California DMV) |
| 8 | Bằng lái xe EU — thẻ nhựa hồng chuẩn châu Âu (mẫu Đức 2013) | `dl_eu_pink_card` | Thẻ nhựa nền hồng-cam hoạ tiết an ninh dày đặc, hộp xanh 12 sao EU + mã quốc gia góc trên trái, trường đánh số cố định theo chuẩn EU (1 họ, 2 tên, 3 ngày/nơi sinh...), chữ "MUSTER" in chìm — khuôn số lặp lại ở mọi nước EU. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/d/dd/DE_Licence_2013_Front.jpg) | Wikimedia Commons (CHLB Đức) |
| 9 | Bằng lái xe EU — sổ giấy hồng kiểu cũ (trước ~1999) | `dl_eu_paper_pink` | Bìa sổ giấy hồng (không phải thẻ nhựa), khổ gần hộ chiếu nhỏ, in "FÜHRERSCHEIN/Permis de conduire/Driving licence..." nhiều ngôn ngữ EC — thế hệ trước khi EU chuyển sang thẻ nhựa từ 2013. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/3/39/Rosa_Führerschein_Vorderseite.jpg)⁺ | Wikimedia Commons |
| 10 | Bằng lái xe Nhật Bản (運転免許証) | `dl_jp_license` | Tên/ngày sinh hàng trên cùng, địa chỉ chiếm nguyên một hàng ngang, dải màu vàng nổi bật ghi hạn dùng, lưới nhỏ liệt kê nhiều hạng xe kèm ngày cấp theo niên hiệu Nhật, đóng chữ "見本" (mẫu) chính giữa. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/6/68/運転免許みほん.jpg) | Wikimedia Commons (Cục Cảnh sát Quốc gia Nhật – 警察庁) |

---

## 4. Sao kê ngân hàng (Bank Statement)

**Mô tả ngắn:** Chứng từ liệt kê giao dịch phát sinh trên một tài khoản/thẻ
trong một kỳ (số dư đầu kỳ, danh sách giao dịch nợ/có, số dư cuối kỳ). Được
yêu cầu phổ biến trong thẩm định tín dụng, KYC, chứng minh tài chính
(visa/du học), đối chiếu kế toán. Thách thức OCR đặc trưng: bảng số liệu
nhiều cột dễ lệch dòng khi ảnh nghiêng/cong, định dạng số tiền khác nhau
giữa các nguồn, và bố cục/phông/độ phân giải biến thiên lớn vì nguồn xuất đa
dạng (PDF từ app, giấy in tại quầy có dấu mộc, ảnh chụp màn hình web/app).

**Từ khoá (EN):** bank statement, account statement, transaction history,
opening balance, closing balance, debit, credit, IBAN, SWIFT/BIC code,
statement period, running balance, credit card statement, e-statement,
MT940, account number

**Từ khoá (VI):** sao kê ngân hàng, sổ phụ ngân hàng, sao kê tài khoản,
lịch sử giao dịch, số dư đầu kỳ, số dư cuối kỳ, ghi nợ, ghi có, số tài
khoản, kỳ sao kê, nội dung giao dịch, sao kê thẻ tín dụng, dấu mộc ngân
hàng, giấy báo nợ, giấy báo có

| # | Tên bố cục (VI) | slug (EN) | Đặc điểm nhận diện | Link ảnh | Nguồn |
|---|---|---|---|---|---|
| 1 | Sao kê ngân hàng quốc tế kiểu Bắc Mỹ (mẫu minh hoạ chung) | `bank_stmt_intl_generic_specimen` | Bảng cột kinh điển: Date/Description/Ref/Withdrawals/Deposits/Balance; dòng "Previous balance" mở đầu, "*** Totals ***" kết thúc; logo ngân hàng hư cấu. | [Ảnh mẫu](https://upload.wikimedia.org/wikipedia/commons/c/cb/BankStatementChequing.png) | Wikimedia Commons ("fictional bank") |
| 2 | Sao kê ngân hàng Anh (UK) — mẫu minh hoạ hồ sơ visa du học | `bank_stmt_intl_uk_visa_specimen` | Bố cục thư tín dụng Anh: logo/địa chỉ ngân hàng góc trên phải, tên/địa chỉ chủ tài khoản kiểu thư bưu điện trái; bảng có hàng tiêu đề xám (Date/Description/Money out/Money in/Balance). | [Tài liệu mẫu (PDF, không phải ảnh)](https://www.ucl.ac.uk/study/sites/study/files/2026-05/Example%20bank%20statement%202026%202.pdf) | UCL — hướng dẫn tài chính visa sinh viên (ngân hàng/tên hư cấu "Berkeley Bank") |
| 3 | Sao kê thẻ tín dụng Techcombank | `bank_stmt_vn_techcombank_creditcard` | Song ngữ Việt-Anh, logo đỏ Techcombank; khối đầu trang 2 cột (ngày sao kê, dư nợ đầu/cuối kỳ, hạn mức, thanh toán tối thiểu, hạn thanh toán); bảng giao dịch tách "Ngày giao dịch" và "Ngày cập nhật hệ thống". | [Ảnh mẫu](https://9746c6837f.vws.vegacdn.vn/posts/images/bang-sao-ke-ghi-chi-tiet-cac-thong-tin-giao-dich.jpg) | Topi.vn (dữ liệu minh hoạ) |
| 4 | Sao kê/lịch sử giao dịch MB Bank (website) | `bank_stmt_vn_mbbank_web` | Giao diện web: khối tìm kiếm trên cùng (số TK, khoảng thời gian, định dạng PDF/Excel); bảng kết quả nhiều cột hẹp, ô nhạy cảm che mờ trong ảnh minh hoạ. | [Ảnh mẫu](https://9746c6837f.vws.vegacdn.vn/posts/images/4%282%29.jpg) | Topi.vn |
| 5 | Sao kê/lịch sử giao dịch BIDV SmartBanking (web) | `bank_stmt_vn_bidv_smartbanking_web` | Thanh điều hướng "SmartBanking" giữa trang, khung thẻ bên phải (số thẻ che một phần); danh sách giao dịch dòng đơn giản, tab lọc "Tất cả/Ghi nợ/Ghi có", số tiền ghi có tô xanh lá. | [Ảnh mẫu](https://omni.bidv.com.vn/static/bidv/hdsdib/media/screenshot/vi/12-dich-vu-the/9-lich-su-giao-dich/3.jpg) | BIDV — hướng dẫn chính thức, dữ liệu demo |
| 6 | Sao kê tài khoản ACB ONE Internet Banking (web) | `bank_stmt_vn_acb_one_web` | Logo "ACB ONE" trái, lời chào tên khách hàng trên cùng; khung lọc theo ngày/theo tháng song song, mỗi khung có 3 nút "In sao kê – Xem – Xuất Excel". | [Ảnh mẫu](https://cdn11.dienmaycholon.vn/filewebdmclnew/public/userupload/files/blog-2025/thiet-bi-di-dong/hay-thiet-lap-moc-thoi-gian-muon-xem-de-he-thong-hien-thi-cac-giao-dich-tuong-ung.jpg) | Điện Máy Chợ Lớn (hướng dẫn ACB) |
| 7 | Sao kê tài khoản VietinBank iPay (web) | `bank_stmt_vn_vietinbank_ipay_web` | Menu ngang gradient tím-đỏ đặc trưng VietinBank; khung "Lịch sử giao dịch" chiếm phần lớn màn hình trái (Ngày/Nội dung/Số tiền/Số dư), icon "Tải về"/"In" cạnh bộ lọc. | [Ảnh mẫu](https://cdn11.dienmaycholon.vn/filewebdmclnew/public/userupload/files/blog-2025/thiet-bi-di-dong/ban-co-the-su-dung-bo-loc.jpg) | Điện Máy Chợ Lớn (hướng dẫn VietinBank) |
| 8 | Sao kê tài khoản Vietcombank — VCB Digibank (app di động) | `bank_stmt_vn_vietcombank_digibank_app` | Giao diện app khung dọc tông xanh lá VCB; màn hình "Thông tin tài khoản" trình bày từng dòng nhãn-giá trị ngang hàng (không phải bảng nhiều cột). | [Ảnh mẫu](https://cdn11.dienmaycholon.vn/filewebdmclnew/public/userupload/files/blog-2025/thiet-bi-di-dong/ban-chon-muc-lich-su-giao-dich.jpg) | Điện Máy Chợ Lớn (hướng dẫn Vietcombank), dữ liệu minh hoạ |
| 9 | Sao kê tài khoản Vietcombank — VCB Digibank (web) | `bank_stmt_vn_vietcombank_digibank_web` | Dashboard nhiều khối trên nền laptop mockup: banner quảng cáo trên, menu dọc trái, khung "Danh sách tài khoản/thẻ" hiển thị số dư dạng dropdown thay vì liệt kê nhiều dòng. | [Ảnh mẫu](https://cdn11.dienmaycholon.vn/filewebdmclnew/public/userupload/files/blog-2025/thiet-bi-di-dong/tim-chuc-nang-tra-cuu-va-chon-tai-khoan.jpg) | Điện Máy Chợ Lớn (hướng dẫn Vietcombank) |
| 10 | Sao kê/lịch sử giao dịch Agribank Internet Banking (bản xuất file) | `bank_stmt_vn_agribank_ibanking_export` | Kết quả 2 nửa: trái là bảng web nút đỏ đô đặc trưng Agribank (STT/Ngày/Số tiền/Số dư); phải là bản xuất Excel thô dạng lưới ô vuông, tên file "transactions_...". | [Ảnh mẫu](https://cdn11.dienmaycholon.vn/filewebdmclnew/public/userupload/files/blog-2025/thiet-bi-di-dong/ban-co-the-tai-file-excel.jpg) | Điện Máy Chợ Lớn (hướng dẫn Agribank) |

---

## 5. Sơ yếu lý lịch / CV xin việc (Resume / CV)

**Mô tả ngắn:** Tài liệu tóm tắt thông tin cá nhân, học vấn, kinh nghiệm và
kỹ năng để nộp hồ sơ xin việc hoặc kê khai với cơ quan nhà nước (ở Việt Nam
gồm cả "sơ yếu lý lịch tự thuật" bán hành chính, có xác nhận địa phương). Độ
đa dạng bố cục thuộc hàng lớn nhất trong các loại chứng từ OCR. Thách thức
đặc trưng: chữ viết tay xen chữ đánh máy trên cùng mẫu, nhiều cột/khung/bảng,
ảnh chân dung và dấu giáp lai đè lên vùng chữ, khác biệt lớn về
font/màu/icon giữa hàng trăm mẫu CV thiết kế khác nhau.

**Từ khoá (EN):** resume, curriculum vitae (CV), work experience,
employment history, education background, skills summary, professional
summary, career objective, references, certifications, chronological
resume, ATS-friendly format, contact information, cover letter

**Từ khoá (VI):** sơ yếu lý lịch, lý lịch tự thuật, hồ sơ xin việc, đơn xin
việc, kinh nghiệm làm việc, quá trình công tác, trình độ học vấn, kỹ năng,
thông tin cá nhân, mục tiêu nghề nghiệp, người tham chiếu, chứng chỉ, xác
nhận địa phương, ảnh chân dung 4x6

| # | Tên bố cục (VI) | slug (EN) | Đặc điểm nhận diện | Link ảnh | Nguồn |
|---|---|---|---|---|---|
| 1 | Sơ yếu lý lịch tự thuật (mẫu phổ thông, viết tay) | `cv_vn_so_yeu_ly_lich_tu_thuat` | 2 trang A4, quốc hiệu/tiêu ngữ đầu trang, khung ảnh 4x6cm góc trên trái ghi chú đóng dấu giáp lai; toàn bộ trường là dòng chấm để điền tay, không màu/đồ hoạ; trang 2 có mục "Hoàn cảnh gia đình". | [Ảnh mẫu](https://images.careerviet.vn/content/images/so-yeu-ly-lich-CareerBuilder-1.jpg) | CareerViet.vn |
| 2 | Sơ yếu lý lịch cán bộ, công chức (mẫu 2C-BNV/2008) | `cv_vn_can_bo_cong_chuc_2c_bnv` | Bảng kê đánh số dày đặc (ngạch công chức, hệ số lương, ngày tuyển dụng, quá trình công tác Đảng/Đoàn...), khung ảnh 4x6cm gắn mép trái; mật độ trường cao hơn hẳn sơ yếu lý lịch phổ thông. | [Ảnh mẫu](https://thanhlap.net/wp-content/uploads/2024/05/Mau-2C-so-yeu-ly-lich-danh-cho-can-bo-cong-chuc.png) | Thanhlap.net |
| 3 | CV tiếng Việt hiện đại có ảnh, banner màu | `cv_vn_modern_photo_banner` | Ảnh chân dung lớn phủ dải trên cùng bên trái, tên/chức danh ngang hàng ảnh; mỗi mục có thanh tiêu đề nền đen full-width, một cột duy nhất bên dưới. | [Ảnh mẫu](https://static.vietcv.io/image/vng/confidential/3a94057586d7fb3bfba60b4b8ff5c2bd.png) | VietCV.io |
| 4 | CV tiếng Việt hai cột khung viền, không ảnh | `cv_vn_two_column_bordered_no_photo` | Khung viền mảnh bao quanh toàn trang; 2 cột không đều (trái hẹp: kỹ năng/chứng chỉ/ngôn ngữ, phải rộng: kinh nghiệm/học vấn); không ảnh/icon, chỉ đường kẻ ngang phân mục. | [Ảnh mẫu](https://static.vietcv.io/image/vng/confidential/ee449ba579a75a2a32a375c843dce5c4.png) | VietCV.io |
| 5 | CV một cột đơn giản kiểu ATS/chronological | `cv_single_column_ats_chronological` | Một cột duy nhất suốt trang, không bảng/icon/ảnh; tiêu đề mục in đậm căn trái, liên hệ ngay dưới tên — tối ưu để ATS đọc tuần tự. | [Ảnh mẫu](https://s3.resume.io/cdn-cgi/image/width=380,format=auto/uploads/local_template_image/image/7492/persistent-resource/athens-resume-templates.jpg) | Resume.io |
| 6 | CV hai cột sidebar hiện đại | `cv_two_column_sidebar` | Cột trái hẹp nền màu riêng (ảnh tròn, liên hệ, kỹ năng dạng chấm/thanh); cột phải rộng chứa tóm tắt, kinh nghiệm, học vấn theo thời gian. | [Ảnh mẫu](https://s3.resume.io/cdn-cgi/image/width=380,format=auto/uploads/local_template_image/image/511/persistent-resource/barcelona-resume-templates.jpg) | Resume.io |
| 7 | CV dạng infographic nhiều màu | `cv_infographic_colorful` | Khối màu nổi bật (cam/đỏ) phủ header; biểu đồ tròn (donut) minh hoạ phân bổ thời gian, icon riêng mỗi kỹ năng — thông tin trực quan hoá bằng đồ hoạ thay vì chỉ chữ. | [Ảnh mẫu](https://cdn.enhancv.com/predefined-examples/Ou7FzSMTqBtU8oPSHAImCqb70WiZzRQgmXrk3Mqf/image.png) | Enhancv |
| 8 | CV dạng timeline (mốc thời gian) | `cv_timeline` | Trục dọc chấm tròn nối các mốc thời gian bên lề trái mục Kinh nghiệm; ngày tháng tách cột riêng, nội dung công việc bên phải trục. | [Ảnh mẫu](https://cdn.enhancv.com/predefined-examples/XkhhOiWYXBft7XTV4BmZ0AS1N0fcxxLb2Z5hGqNy/image.png) | Enhancv |
| 9 | CV học thuật (Academic CV) nhiều trang | `cv_academic_multipage` | Từ 2 trang trở lên (đánh số "Page 1 of 2"); có mục riêng Research Interests, Publications (tách Book/Journal), Teaching Experience, Conferences — một cột, mật độ chữ rất dày. | [Ảnh mẫu](https://cdn-image.novoresume.com/image/cms/media/how-to-write-a-cv-drafts-academic-cv-example.png) | Novoresume |
| 10 | CV kiểu Europass (châu Âu) | `cv_europass` | Header xanh dương đậm cố định với logo "europass" + cờ EU góc phải; trường cá nhân dạng nhãn-giá trị cố định; mục Language skills ghi "Mother tongue(s)" theo khung tham chiếu chung châu Âu. | [Ảnh mẫu](https://resumegenius.com/wp-content/uploads/europass-cv-example.png) | Resume Genius (định dạng Europass chính thức) |

---

## 6. Hợp đồng (Contract)

**Mô tả ngắn:** Văn bản pháp lý ghi nhận thoả thuận giữa các bên, tồn tại
dưới hàng chục loại (lao động, thuê nhà, mua bán, dịch vụ, góp vốn...) với
tần suất cao trong hồ sơ hành chính, pháp lý, kế toán doanh nghiệp. Thách
thức OCR đặc trưng: nhiều trang, mật độ chữ dày xen bảng/phụ lục, trường
điền tay trên nền dot-leader, chữ ký/con dấu/dấu giáp lai đè lên văn bản in,
và hợp đồng điện tử ký số có giao diện khác hẳn giấy in truyền thống.

**Từ khoá (EN):** contract, agreement, parties (party A / party B),
effective date, term and termination, governing law, signature block,
witness, notarization / notary public, company seal / corporate stamp,
consideration, breach of contract, counterparts, appendix / annex, digital
signature / e-signing

**Từ khoá (VI):** hợp đồng, bên A - bên B, ngày hiệu lực, điều khoản hợp
đồng, chữ ký - ký tên, con dấu - đóng dấu, công chứng, chứng thực, dấu giáp
lai - dấu treo, căn cứ pháp lý, phụ lục hợp đồng, chấm dứt - thanh lý hợp
đồng, vi phạm hợp đồng, người đại diện theo pháp luật, chữ ký số - hợp đồng
điện tử

| # | Tên bố cục (VI) | slug (EN) | Đặc điểm nhận diện | Link ảnh | Nguồn |
|---|---|---|---|---|---|
| 1 | Hợp đồng lao động (mẫu chuẩn) | `contract_vn_labor_standard` | Quốc hiệu tiêu ngữ đầu trang, tiêu đề "HỢP ĐỒNG LAO ĐỘNG" + "Số:.../HĐLĐ"; "BÊN A:" liệt kê Đại diện/Chức vụ/Địa chỉ/MST/Số TK trên dòng chấm để điền tay, một cột, chưa đánh số Điều ở đầu. | [Ảnh mẫu](https://easyhrm.vn/wp-content/uploads/2025/10/mau-hop-dong-lao-dong-thong-dung-nhat.jpg) | easyhrm.vn |
| 2 | Hợp đồng thuê nhà ở | `contract_vn_lease_house` | Quốc hiệu tiêu ngữ, tiêu đề "HỢP ĐỒNG CHO THUÊ NHÀ Ở"; mở đầu văn xuôi "Hôm nay, ngày... Chúng tôi gồm"; không có khối "Căn cứ" pháp lý mở đầu, không đánh số Điều ngay từ đầu — bố cục đơn giản kiểu giấy tờ cá nhân. | [Ảnh mẫu](https://sudospaces.com/ketoanleanh/2020/10/hop-dong-thue-nha-o.png.webp) | ketoanleanh.edu.vn |
| 3 | Hợp đồng mua bán/chuyển nhượng nhà đất (dạng công chứng) | `contract_vn_realestate_notarized` | Hai bên đánh số La Mã "I/ BÊN BÁN" và "II/ BÊN MUA", liệt kê cả vợ và chồng cùng CMND/hộ khẩu; nhiều trang, thuộc loại bắt buộc công chứng nên bản ký thật có lời chứng công chứng viên + dấu giáp lai. | [Ảnh mẫu](https://sudospaces.com/ketoanleanh/2020/10/hop-dong-mua-ban-nha-dat.png.webp) | ketoanleanh.edu.vn |
| 4 | Hợp đồng kinh tế / mua bán hàng hoá doanh nghiệp | `contract_vn_goods_b2b` | Tiêu đề "HỢP ĐỒNG KINH TẾ" + "Số:.../HĐKT"; hai bên là "A/ Đại diện bên A"/"B/ Đại diện bên B" với Địa chỉ trụ sở, Số TK ngân hàng, MST thay vì CMND cá nhân; thường kèm phụ lục bảng kê hàng hoá. | [Ảnh mẫu](https://sudospaces.com/ketoanleanh/2024/06/mau-hop-dong-kinh-te-pho-bien.jpg) | ketoanleanh.edu.vn |
| 5 | Hợp đồng dịch vụ | `contract_vn_service` | Khối "Căn cứ" nhiều dòng in nghiêng (Căn cứ Bộ luật Dân sự, Căn cứ..., Căn cứ yêu cầu...) trước "Bên thuê dịch vụ (Bên A)"/"Bên cung cấp dịch vụ (Bên B)"; Điều chia mục nhỏ 1.1, 1.2 — preamble dài hơn hợp đồng cá nhân. | [Ảnh mẫu](https://blog.slimcrm.vn/sites/default/files/inline/images/xmau-hop-dong-dich-vu-phap-ly.jpg.pagespeed.ic.205WtvO6R2t5QGZm12Ea.jpg) | blog.slimcrm.vn |
| 6 | Hợp đồng góp vốn kinh doanh | `contract_vn_capital_contribution` | Preamble dạng gạch đầu dòng "•"; hai bên KHÔNG đối xứng — "BÊN NHẬN GÓP VỐN" là tổ chức (MST/Đại diện/Chức vụ), "BÊN GÓP VỐN" là cá nhân (CMND/nơi cấp/thường trú); Điều in hoa đậm toàn bộ. | [Ảnh mẫu](https://sudospaces.com/ketoanleanh/2024/11/hop-dong-gop-von-kinh-doanh.png.webp) | ketoanleanh.edu.vn |
| 7 | Hợp đồng điện tử ký số | `contract_vn_esignature` | KHÔNG phải trang giấy in — ảnh chụp giao diện phần mềm ký số (thanh trên cùng màu thương hiệu nền tảng, thumbnail các trang bên phải, nút "Tải xuống/Lưu/Từ chối"); khối ký hai cột "ĐẠI DIỆN BÊN A"/"ĐẠI DIỆN BÊN B" song song trong khung xem. | [Ảnh mẫu](https://businesswiki.codx.vn/wp-content/uploads/2023/06/hop-dong-dien-tu-fpt-12.jpg) | businesswiki.codx.vn |
| 8 | Hợp đồng giao khoán (khoán việc) | `contract_vn_task_assignment_form` | KHÔNG có quốc hiệu tiêu ngữ; góc trên là "Đơn vị:.../Bộ phận:..." và "Mẫu số: 08-LĐTL (TT 200/2014/TT-BTC...)" — biểu mẫu kế toán nội bộ; kết thúc bằng khối ký BỐN cột (nhận khoán, giao khoán, người lập, kế toán trưởng). | [Ảnh mẫu](https://sudospaces.com/ketoanleanh/2023/05/mau-hop-dong-khoan-viec-theo-thong-tu-200.jpg.webp) | ketoanleanh.edu.vn |
| 9 | Hợp đồng quốc tế — dạng đoạn văn một trang | `contract_intl_one_page_paragraph` | Tiếng Anh, một cột, không đánh số điều mà dùng đoạn văn dưới tiêu đề đậm ("Scope of Work:", "Payment Terms:"...); banner hình học đầu trang chứa liên hệ công ty; hai dòng chữ ký kiểu chữ thảo xếp CHỒNG. | [Ảnh mẫu](https://images.template.net/337692/One-Page-Contract-Template-edit-online.png) | template.net |
| 10 | Hợp đồng quốc tế — dạng điều khoản đánh số | `contract_intl_numbered_clauses` | Tiếng Anh, mở đầu định danh các bên kiểu "This Sales Contract... between..."; danh sách điều khoản đánh số 1–5; chữ ký chỉ là dòng gạch chân trơn "Seller's Signature: ___" xếp chồng, không có hình chữ ký thảo. | [Ảnh mẫu](https://images.template.net/484522/Sample-One-Page-Sales-Contract-Template-edit-online.png) | template.net |

---

## Lưu ý bản quyền & sử dụng

- Đây là **link tham khảo**, không phải asset đã cấp phép lại. Trước khi tải
  về / đưa vào một tập dữ liệu công bố, kiểm giấy phép từng nguồn — các ảnh
  Wikimedia Commons phần lớn ở giấy phép public domain hoặc CC (ghi trên
  từng trang File:), còn ảnh từ blog/trang thương mại (ACC Group, Điện Máy
  Chợ Lớn, ketoanleanh.edu.vn, template.net...) có thể mang bản quyền riêng
  của nơi đăng.
- Đường link do bên thứ ba lưu trữ, có thể đổi hoặc gỡ theo thời gian — đã
  xác minh còn truy cập được tại thời điểm viết tài liệu này
  (2026-08-24), không đảm bảo mãi mãi.
- Không dùng các ảnh này để suy luận ngược về danh tính người thật: mọi ảnh
  đã chọn đều được lượt tra cứu xác định là mẫu/specimen/blank, nhưng nguồn
  bên thứ ba luôn có rủi ro dữ liệu bị thay đổi sau khi tài liệu này được viết.

## Gợi ý bước tiếp theo nếu muốn đưa vào `rulebase/`

Khảo sát này dừng ở bước "biết cần vẽ gì" — biến nó thành dữ liệu sinh được
theo đúng quy trình ở [README.md §6](../README.md#-6-thêm-một-loại-chứng-từ-mới)
vẫn cần, cho **mỗi root** ở trên:

1. Một **phôi gốc** đo được (ảnh/scan thật hoặc đặc tả chính thức đủ chi
   tiết vị trí trường) — xem khái niệm "phôi gốc" ở
   [rulebase/README.md §1b](../rulebase/README.md#phôi-gốc-the-form-before-anyone-measured-it).
   Các specimen chính thức (Bộ Công an, DMV, PRADO...) trong bảng trên là
   điểm khởi đầu tốt hơn ảnh chụp thật, vì đã có sẵn ở trạng thái "được phép
   dùng làm mẫu".
2. **Corpus** tên/địa chỉ/số liệu hợp lý cho root đó trong `rulebase/corpus/`
   (ví dụ CCCD cần một corpus họ tên + quê quán + nơi cư trú Việt Nam, khác
   hẳn `items_market.txt`/`shops_market.txt` hiện có).
3. Với ID card / hộ chiếu / GPLX: một **sheet CSS mới** trong
   `generators/html/sheets/` vì đây là "họ giấy" hoàn toàn khác — thẻ nhựa
   khổ ID-1 ngang, ảnh chân dung cố định vị trí, hoa văn nền — không dùng lại
   được layout hoá đơn/biên lai hiện có.
4. Cân nhắc quy tắc `pipeline/invariants.py` riêng cho từng root — ví dụ số
   định danh cá nhân có checksum, ngày hết hạn phải sau ngày cấp, MRZ hộ
   chiếu phải khớp các trường in — tương tự cách kho đang kiểm số học tiền
   trên hoá đơn.
